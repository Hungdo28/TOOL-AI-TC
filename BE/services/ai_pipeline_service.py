from __future__ import annotations

import json
import logging
import math
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from core.config import Settings
from services.ai_client import AiClient
from services.ai_prompts import (
    build_analysis_prompt,
    build_condition_generator_prompt,
    build_requirement_extraction_prompt,
    build_testcase_generator_prompt,
)
from services.common import ApiError
from services.doc_crawler import DocumentCrawler
from services.json_parser import (
    parse_analysis_report,
    parse_loose,
    parse_requirements,
)
from services.memory_service import MemoryService

LOGGER = logging.getLogger("autotc-backend")

CHUNK_CHARS = 5000
MAX_REQ_PER_FEATURE_CHUNK = 6
CONDITIONS_PER_BATCH = 4
DOC_SEP = "--- TÀI LIỆU TIẾP THEO ---"

_STARTS_OK_RE = re.compile(r"^(Kiểm tra|Xác minh|Validate)\b", re.IGNORECASE)
_STEP_NUMBER_PREFIX_RE = re.compile(r"^\d+\s*[\.\)]\s*")


def _arr_of(v: Any) -> list[Any]:
    if isinstance(v, list):
        return v
    if v is not None and v != "":
        return [v]
    return []


def _low(x: Any) -> str:
    return str(x if x is not None else "").lower().strip()


def _flat_names(v: Any) -> list[str]:
    return [_low(x) for x in _arr_of(v) if len(_low(x)) >= 2]


def _fuzzy(a: str, b: str) -> bool:
    return bool(a and b and len(a) >= 2 and len(b) >= 2 and (a in b or b in a))


def _any_fuzzy(text: Any, names: list[str]) -> bool:
    t = _low(text)
    return any(_fuzzy(t, n) for n in names)


def _pick_by_names(items: list[dict[str, Any]], text_fn, names: list[str], cap: int) -> list[dict[str, Any]]:
    if not items:
        return []
    hits = [x for x in items if _any_fuzzy(text_fn(x), names)] if names else []
    if hits:
        return hits
    return items if len(items) <= cap else []


class AiPipelineService:
    """
    Thực thi toàn bộ luồng AI (Crawl tài liệu -> Phân tích BA -> Trích xuất Requirement ->
    Sinh Test Condition kèm bộ nhớ qa_memory -> Sinh Test Case -> Xuất Google Docs & Sheets)
    trực tiếp trong Backend Python.
    """

    def __init__(self, workspace: Any, settings: Settings, execution_tracker: Any = None):
        self.workspace = workspace
        self.settings = settings
        self.tracker = execution_tracker
        self.ai = AiClient(settings)
        self.memory = MemoryService(workspace)
        self.crawler = DocumentCrawler(getattr(workspace, "_google_workspace", None), settings)

    def run_From_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Điểm vào chính tương thích 100% với payload từ FE (doRunSingle, doRunMultiple, review.html)."""
        body = payload.get("body") if isinstance(payload.get("body"), dict) else payload
        mode = str(body.get("loaiChay") or "single").strip()
        request_id = str(body.get("requestId") or "req-backend").strip()
        user_prompt = str(
            body.get("promptAI")
            or body.get("promptAI1")
            or body.get("promptAI2")
            or ""
        ).strip()
        prefix = re.sub(
            r"[\[\]]",
            "",
            str(body.get("maTestCase") or body.get("ma_testcase") or body.get("prefix") or "TC"),
        ).strip() or "TC"

        # Nhánh xuất trực tiếp từ màn hình review.html
        if mode == "export_sheet":
            task_ident = body.get("problem_id") or body.get("baiToan")
            testcases = body.get("testcases") or []
            if not task_ident:
                raise ApiError(400, "Thiếu tên hoặc ID bài toán để xuất Sheet.")
            task = self.workspace.find_task(str(task_ident))
            if not task:
                raise ApiError(404, f'Không tìm thấy bài toán "{task_ident}"')
            task_name = task.get("Bài toán") or str(task_ident)
            tc_url = self.workspace.create_testcase_sheet(task_name, testcases)
            updated = self.workspace.update_task(
                task["id"],
                {"Link Testcase": tc_url, "Trạng thái": "Đã xong"},
            )
            return {
                "success": True,
                "message": "Đã xuất Testcase vào Google Sheet thành công.",
                "data": updated,
            }

        # Lấy danh sách bài toán cần chạy
        task_names: list[str] = []
        if isinstance(body.get("danhSachBaiToan"), list):
            task_names = [str(t).strip() for t in body["danhSachBaiToan"] if str(t).strip()]
        elif body.get("baiToan"):
            task_names = [str(body["baiToan"]).strip()]

        if not task_names:
            raise ApiError(400, "Không có bài toán nào được chọn để chạy.")

        # Đăng ký bộ đếm giờ trên ExecutionTracker (nếu chưa có)
        if self.tracker:
            existing_names = {
                str(t.get("Bài toán") or "").strip().casefold()
                for t in self.workspace.list_tasks()
            }
            try:
                self.tracker.start_executions(
                    {"taskNames": task_names, "requestId": request_id},
                    existing_names,
                )
            except Exception:
                pass

        # Xử lý từng bài toán (chạy song song tối đa 2 bài cùng lúc nếu chọn nhiều bài)
        def run_one_safe(task_name: str) -> dict[str, Any]:
            try:
                return self._process_single_task(
                    task_name=task_name,
                    user_prompt=user_prompt,
                    mode=mode,
                    tc_prefix=prefix,
                )
            finally:
                if self.tracker:
                    self.tracker.clear_execution(task_name)

        max_task_workers = min(2, len(task_names))
        with ThreadPoolExecutor(max_workers=max_task_workers) as pool:
            results = list(pool.map(run_one_safe, task_names))

        failed = [r for r in results if not r.get("success")]
        if failed and len(failed) == len(results):
            first_err = failed[0].get("error") or "Lỗi xử lý bài toán"
            raise ApiError(500, f"Xử lý thất bại: {first_err}")

        return {
            "success": True,
            "message": f"Đã xử lý hoàn tất {len(results) - len(failed)}/{len(results)} bài toán.",
            "data": results[0] if len(results) == 1 else results,
        }

    def _process_single_task(
        self,
        *,
        task_name: str,
        user_prompt: str,
        mode: str,
        tc_prefix: str,
    ) -> dict[str, Any]:
        task = self.workspace.find_task(task_name)
        if not task:
            return {"success": False, "baiToan": task_name, "error": f'Không tìm thấy bài toán "{task_name}"'}

        problem_id = str(task.get("id") or task.get("problem_id") or "")
        title = str(task.get("Bài toán") or task_name)
        raw_urls = str(task.get("URL") or "")

        LOGGER.info("Bắt đầu xử lý bài toán [%s] (id=%s, mode=%s)", title, problem_id, mode)

        # 1. Cập nhật trạng thái Waiting theo đúng khóa chính (UUID)
        self.workspace.update_task(problem_id, {"Trạng thái": "Waiting"})

        try:
            # 2. Crawl toàn bộ tài liệu (Docs, Sheets, Figma) song song
            doc_text = self.crawler.crawl_all(raw_urls)

            # 3. Lưu tài liệu đã crawl vào bảng problem_documents (bất đồng bộ / không chặn lỗi)
            self.memory.save_crawled_document(
                problem_id=problem_id,
                problem_title=title,
                source_urls=raw_urls,
                content=doc_text,
            )

            run_analysis = mode in ("single", "multiple", "phan_tich")
            run_testcase = mode in ("single", "multiple", "testcase")

            analysis_doc_url = str(task.get("Link tài liệu phân tích") or "")
            testcase_url = str(task.get("Link Testcase") or "")
            testcase_count = 0

            # Chạy song song Nhánh Phân tích BA (Google Docs) và Nhánh Sinh Testcase (Google Sheets)
            with ThreadPoolExecutor(max_workers=2) as branch_pool:
                fut_analysis = (
                    branch_pool.submit(self._run_analysis_branch, problem_id, title, doc_text, user_prompt)
                    if run_analysis
                    else None
                )
                fut_testcase = (
                    branch_pool.submit(
                        self._run_testcase_branch,
                        problem_id,
                        title,
                        doc_text,
                        user_prompt,
                        tc_prefix,
                    )
                    if run_testcase
                    else None
                )

                if fut_analysis:
                    analysis_doc_url = fut_analysis.result()
                if fut_testcase:
                    testcase_url, testcase_count = fut_testcase.result()

            # 4. Cập nhật trạng thái hoàn tất ("Đã xong")
            changes: dict[str, Any] = {"Trạng thái": "Đã xong"}
            if analysis_doc_url:
                changes["Link tài liệu phân tích"] = analysis_doc_url
            if testcase_url:
                changes["Link Testcase"] = testcase_url

            updated_task = self.workspace.update_task(problem_id, changes)
            LOGGER.info(
                "Hoàn tất bài toán [%s]: %d testcases, Sheet=%s, Doc=%s",
                title,
                testcase_count,
                testcase_url,
                analysis_doc_url,
            )
            return {
                "success": True,
                "baiToan": title,
                "problem_id": problem_id,
                "testcase_count": testcase_count,
                "testcase_url": testcase_url,
                "analysis_doc_url": analysis_doc_url,
                "task": updated_task,
            }

        except Exception as err:
            LOGGER.exception("Lỗi khi xử lý bài toán [%s]: %s", title, err)
            try:
                self.workspace.update_task(problem_id, {"Trạng thái": "Chưa làm"})
            except Exception:
                pass
            return {
                "success": False,
                "baiToan": title,
                "problem_id": problem_id,
                "error": str(err),
            }

    # =========================================================================
    # NHÁNH 1: PHÂN TÍCH BÀI TOÁN & XUẤT GOOGLE DOCS
    # =========================================================================
    def _run_analysis_branch(
        self,
        problem_id: str,
        title: str,
        doc_text: str,
        user_prompt: str,
    ) -> str:
        prompt = build_analysis_prompt(doc_text, user_prompt)
        raw_ai = self.ai.complete(prompt, max_tokens=8000, temperature=0.2)
        final_text = parse_analysis_report(raw_ai)

        doc_url = self.workspace.create_analysis_doc(title, final_text)
        self.workspace.update_task(problem_id, {"Link tài liệu phân tích": doc_url})
        self.memory.save_analysis(
            problem_id=problem_id,
            problem_title=title,
            final_text=final_text,
            doc_url=doc_url,
        )
        return doc_url

    # =========================================================================
    # NHÁNH 2: TRÍCH XUẤT REQUIREMENT -> SINH CONDITION -> SINH TESTCASE & SHEET
    # =========================================================================
    def _run_testcase_branch(
        self,
        problem_id: str,
        title: str,
        doc_text: str,
        user_prompt: str,
        tc_prefix: str,
    ) -> tuple[str, int]:
        # Bước 2.1: Chia tài liệu thành các chunk <= 5000 ký tự
        doc_chunks = self._chunk_document(title, doc_text)
        LOGGER.info("[%s] Đã chia tài liệu thành %d chunk.", title, len(doc_chunks))

        # Bước 2.2: Gọi AI_structured_requirement và truyền previous_feature_names chuẩn xác
        structured_reqs = self._extract_structured_requirements(title, doc_chunks, user_prompt)
        LOGGER.info(
            "[%s] Đã trích xuất %d features, %d requirements.",
            title,
            len(structured_reqs.get("features") or []),
            len(structured_reqs.get("requirements") or []),
        )

        # Bước 2.3: Chia theo Feature (Split_By_Feature) + gắn bộ nhớ qa_memory (Mem_Search + Mem_Format)
        feature_chunks = self._split_by_feature(structured_reqs)
        approved_mem = self.memory.fetch_approved_testcases(problem_id)
        enriched_chunks = self.memory.build_memory_text_for_chunks(feature_chunks, approved_mem)

        # Bước 2.4: Sinh Test Conditions song song (Test_condition_generator + Parse_conditions)
        all_conditions, cond_map = self._generate_test_conditions(enriched_chunks, user_prompt)
        LOGGER.info("[%s] Đã sinh tổng cộng %d test conditions.", title, len(all_conditions))

        # Bước 2.5: Chia batch 4 conditions và gọi AI_Phan_tich_Testcase song song (kèm retry riêng nếu thiếu)
        raw_tc_rows = self._generate_testcases(all_conditions, cond_map, user_prompt)

        # Bước 2.6: Gom theo Test Suite, khử trùng lặp, đánh mã [TC]_1..N
        sheet_rows = self._group_by_test_suite(raw_tc_rows, tc_prefix)
        tc_only_count = sum(1 for r in sheet_rows if r.get("row_type") == "testcase")

        # Bước 2.7: Tạo file Google Sheet Testcase & ghi toàn bộ dòng trong 1 batch
        tc_url = self.workspace.create_testcase_sheet(title, sheet_rows)
        self.workspace.update_task(problem_id, {"Link Testcase": tc_url})
        return tc_url, tc_only_count

    @staticmethod
    def _chunk_document(title: str, doc_text: str) -> list[dict[str, Any]]:
        text = doc_text.strip()
        if not text:
            raise RuntimeError("Tài liệu rỗng, không có gì để chia chunk.")

        doc_title = title.strip() or text[:120].split("\n")[0]
        pieces: list[str] = []

        for line in text.split("\n"):
            if len(line) <= CHUNK_CHARS:
                pieces.append(line)
                continue
            rest = line
            while len(rest) > CHUNK_CHARS:
                cut = rest.rfind(". ", 0, CHUNK_CHARS)
                if cut < int(CHUNK_CHARS * 0.5):
                    cut = rest.rfind(" ", 0, CHUNK_CHARS)
                if cut < int(CHUNK_CHARS * 0.5):
                    cut = CHUNK_CHARS
                pieces.append(rest[: cut + 1].strip())
                rest = rest[cut + 1 :]
            if rest.strip():
                pieces.append(rest.strip())

        chunks: list[str] = []
        cur = ""
        for p in pieces:
            is_sep = p.strip() == DOC_SEP
            if cur and (
                len(cur) + len(p) + 1 > CHUNK_CHARS
                or (is_sep and len(cur) > CHUNK_CHARS * 0.4)
            ):
                chunks.append(cur.strip())
                cur = ""
            if is_sep and not cur:
                continue
            cur = f"{cur}\n{p}" if cur else p
        if cur.strip():
            chunks.append(cur.strip())

        total = len(chunks)
        result: list[dict[str, Any]] = []
        for idx, c in enumerate(chunks):
            header = f"[Tài liệu: {doc_title} | Phần {idx + 1}/{total}]\n" if total > 1 else ""
            result.append(
                {
                    "data": header + c,
                    "chunk_index": idx + 1,
                    "total_chunks": total,
                    "is_last_chunk": idx == total - 1,
                }
            )
        return result

    def _extract_structured_requirements(
        self,
        title: str,
        doc_chunks: list[dict[str, Any]],
        user_prompt: str,
    ) -> dict[str, Any]:
        parsed_chunks: list[tuple[int, dict[str, Any]]] = []
        warnings: list[str] = []
        known_feature_names: list[str] = []

        def call_chunk(chunk: dict[str, Any], prev_names: list[str]) -> str:
            prompt = build_requirement_extraction_prompt(
                task_name=title,
                chunk_data=chunk["data"],
                chunk_index=chunk["chunk_index"],
                total_chunks=chunk["total_chunks"],
                is_last_chunk=chunk["is_last_chunk"],
                previous_feature_names=prev_names,
                user_prompt=user_prompt,
            )
            return self.ai.complete(prompt, max_tokens=6000, temperature=0.1)

        # Tối ưu: chạy chunk 1 trước để lấy danh sách tên Feature chuẩn truyền cho các chunk sau
        raw_outputs: list[str | None] = [None] * len(doc_chunks)
        if doc_chunks:
            try:
                first_raw = call_chunk(doc_chunks[0], [])
                raw_outputs[0] = first_raw
                first_parsed = parse_requirements(first_raw)
                if "data" in first_parsed:
                    for f in first_parsed["data"].get("features") or []:
                        if isinstance(f, dict) and str(f.get("feature_name") or "").strip():
                            fname = str(f["feature_name"]).strip()
                            if fname not in known_feature_names:
                                known_feature_names.append(fname)
            except Exception as e:
                warnings.append(f"Chunk 1 lỗi: {e}")

        if len(doc_chunks) > 1:
            remaining = doc_chunks[1:]

            def run_rem(c: dict[str, Any]) -> str | None:
                try:
                    return call_chunk(c, known_feature_names)
                except Exception as e:
                    LOGGER.warning("Chunk %d lỗi: %s", c["chunk_index"], e)
                    return None

            with ThreadPoolExecutor(max_workers=min(6, len(remaining))) as pool:
                rem_results = list(pool.map(run_rem, remaining))
            for i, r in enumerate(rem_results, start=1):
                raw_outputs[i] = r

        for idx, raw in enumerate(raw_outputs):
            if not raw or not str(raw).strip():
                warnings.append(f"Chunk {idx + 1}/{len(doc_chunks)} không có kết quả, đã bỏ qua.")
                continue
            r = parse_requirements(raw)
            if "fail" in r:
                warnings.append(f"Chunk {idx + 1}/{len(doc_chunks)}: {r['fail']}, đã bỏ qua.")
                continue
            if r.get("salvaged"):
                warnings.append(f"Chunk {idx + 1} bị cắt cụt, đã cứu phần hoàn chỉnh.")
            parsed_chunks.append((idx, r["data"]))

        if not parsed_chunks:
            raise RuntimeError(
                "AI_structured_requirement: không chunk nào trả về JSON hợp lệ.\n" + "\n".join(warnings)
            )

        out: dict[str, Any] = {
            "features": [],
            "requirements": [],
            "business_rules": [],
            "decision_tables": [],
            "inputs": [],
            "flows": [],
            "apis": [],
            "integrations": [],
            "data_objects": [],
            "states": [],
            "exceptions": [],
            "change_scope": {"changed": [], "unchanged_but_impacted": []},
            "dependencies": [],
            "ambiguities": [],
        }

        feat_by_name: dict[str, dict[str, Any]] = {}
        seen: dict[str, set[str]] = {
            "inputs": set(),
            "apis": set(),
            "data_objects": set(),
            "states": set(),
            "dependencies": set(),
            "cs": set(),
        }
        n_feat = n_req = n_br = n_dt = n_flow = n_int = n_exc = 0

        def arr_dict(d: dict[str, Any], k: str) -> list[dict[str, Any]]:
            v = d.get(k)
            return [x for x in v if isinstance(x, dict)] if isinstance(v, list) else []

        for idx, d in parsed_chunks:
            feat_map: dict[str, str] = {}
            req_map: dict[str, str] = {}

            for i, f in enumerate(arr_dict(d, "features")):
                key = _low(f.get("feature_name")) or f"__f{idx}_{i}"
                nf = feat_by_name.get(key)
                if not nf:
                    n_feat += 1
                    try:
                        fo = int(f.get("flow_order") or (i + 1))
                    except Exception:
                        fo = i + 1
                    nf = {
                        **f,
                        "feature_id": f"FEAT{n_feat:03d}",
                        "_ord": idx * 1000 + fo,
                    }
                    feat_by_name[key] = nf
                    out["features"].append(nf)
                old_fid = str(f.get("feature_id") or "")
                if old_fid:
                    feat_map[old_fid] = nf["feature_id"]

            def map_feat(fid: Any) -> str:
                s = str(fid or "")
                return feat_map.get(s, s)

            for r in arr_dict(d, "requirements"):
                if not str(r.get("requirement") or "").strip():
                    continue
                n_req += 1
                nid = f"REQ{n_req:03d}"
                old_rid = str(r.get("requirement_id") or "")
                if old_rid:
                    req_map[old_rid] = nid
                out["requirements"].append(
                    {
                        **r,
                        "requirement_id": nid,
                        "feature_id": map_feat(r.get("feature_id")),
                    }
                )

            def map_req(rid: Any) -> str:
                s = str(rid or "")
                return req_map.get(s, s)

            for x in arr_dict(d, "business_rules"):
                n_br += 1
                out["business_rules"].append(
                    {**x, "rule_id": f"BR{n_br:03d}", "requirement_id": map_req(x.get("requirement_id"))}
                )
            for x in arr_dict(d, "decision_tables"):
                n_dt += 1
                out["decision_tables"].append(
                    {**x, "table_id": f"DT{n_dt:03d}", "requirement_id": map_req(x.get("requirement_id"))}
                )
            for x in arr_dict(d, "integrations"):
                n_int += 1
                out["integrations"].append(
                    {**x, "integration_id": f"INT{n_int:03d}", "requirement_id": map_req(x.get("requirement_id"))}
                )
            for x in arr_dict(d, "exceptions"):
                n_exc += 1
                out["exceptions"].append(
                    {**x, "exception_id": f"EXC{n_exc:03d}", "requirement_id": map_req(x.get("requirement_id"))}
                )
            for x in arr_dict(d, "flows"):
                n_flow += 1
                out["flows"].append(
                    {**x, "flow_id": f"FLOW{n_flow:03d}", "feature_id": map_feat(x.get("feature_id"))}
                )
            for x in arr_dict(d, "ambiguities"):
                out["ambiguities"].append(
                    {**x, "related_requirement_id": map_req(x.get("related_requirement_id"))}
                )

            def dedupe(k: str, key_fn) -> None:
                for x in arr_dict(d, k):
                    kval = key_fn(x)
                    if kval in seen[k]:
                        continue
                    seen[k].add(kval)
                    out[k].append(x)

            dedupe("inputs", lambda x: _low(x.get("name")))
            dedupe("apis", lambda x: f"{_low(x.get('name'))}|{_low(x.get('method'))}")
            dedupe(
                "data_objects",
                lambda x: f"{_low(x.get('table_or_object'))}|{_low(x.get('field'))}|{_low(x.get('data_change'))}",
            )
            dedupe("states", lambda x: f"{_low(x.get('entity'))}|{_low(x.get('state'))}")
            dedupe(
                "dependencies",
                lambda x: f"{_low(x.get('source'))}|{_low(x.get('target'))}|{_low(x.get('dependency'))}",
            )

            cs = d.get("change_scope")
            if isinstance(cs, dict):
                for ck in ("changed", "unchanged_but_impacted"):
                    vals = cs.get(ck)
                    if isinstance(vals, list):
                        for v in vals:
                            cs_key = f"{ck}|{json.dumps(v, ensure_ascii=False).lower()}"
                            if cs_key not in seen["cs"]:
                                seen["cs"].add(cs_key)
                                out["change_scope"][ck].append(v)

        out["features"].sort(key=lambda f: f.get("_ord", 999999))
        ord_of: dict[str, int] = {}
        for i, f in enumerate(out["features"], start=1):
            f["flow_order"] = i
            ord_of[f["feature_id"]] = i
            f.pop("_ord", None)
        for fl in out["flows"]:
            if fl.get("feature_id") in ord_of:
                fl["flow_order"] = ord_of[fl["feature_id"]]

        if not out["requirements"]:
            raise RuntimeError(
                "AI_structured_requirement không trích xuất được requirement nào từ tài liệu.\n"
                + "\n".join(warnings)
            )
        if warnings:
            out["_warning"] = " | ".join(warnings)
        return out

    @staticmethod
    def _split_by_feature(s: dict[str, Any]) -> list[dict[str, Any]]:
        def arr(k: str) -> list[dict[str, Any]]:
            v = s.get(k)
            return [x for x in v if isinstance(x, dict)] if isinstance(v, list) else []

        requirements = arr("requirements")
        if not requirements:
            raise RuntimeError("Không có requirement để chia chunk.")

        BIG = 1_000_000

        def num_ord(v: Any) -> float:
            try:
                return float(v)
            except Exception:
                return float(BIG)

        features = [{**f, "_i": i} for i, f in enumerate(arr("features"))]
        features.sort(key=lambda f: (num_ord(f.get("flow_order")), f["_i"]))
        known = {f.get("feature_id") for f in features}
        orphans = [r for r in requirements if r.get("feature_id") not in known]
        if orphans:
            features.append(
                {
                    "feature_id": "__GENERAL__",
                    "feature_name": "Yêu cầu chung"
                    if features
                    else (orphans[0].get("type") or "Yêu cầu chung"),
                    "description": "",
                    "flow_order": BIG,
                    "_i": BIG,
                }
            )

        suite_names = [str(f.get("feature_name") or "") for f in features]
        change_scope = s.get("change_scope") or {"changed": [], "unchanged_but_impacted": []}
        base_ctx = {
            "all_suites_in_order": suite_names,
            "change_scope": change_scope,
            "dependencies": arr("dependencies")[:30],
        }

        def build_context(feature: dict[str, Any], reqs: list[dict[str, Any]]) -> dict[str, Any]:
            ids = {r.get("requirement_id") for r in reqs}
            names: list[str] = []
            apis: list[str] = []
            sts: list[str] = []
            for r in reqs:
                names.extend(_flat_names(r.get("related_fields")))
                apis.extend(_flat_names(r.get("related_api")))
                sts.extend(_flat_names(r.get("related_state")))

            by_req = lambda x: x.get("requirement_id") in ids
            return {
                **base_ctx,
                "feature": feature,
                "requirements": reqs,
                "business_rules": [x for x in arr("business_rules") if by_req(x)],
                "decision_tables": [x for x in arr("decision_tables") if by_req(x)],
                "integrations": [x for x in arr("integrations") if by_req(x)],
                "exceptions": [x for x in arr("exceptions") if by_req(x)],
                "flows": [f for f in arr("flows") if f.get("feature_id") == feature.get("feature_id")],
                "inputs": _pick_by_names(arr("inputs"), lambda x: x.get("name"), names, 20),
                "apis": _pick_by_names(arr("apis"), lambda x: x.get("name"), apis, 15),
                "data_objects": _pick_by_names(
                    arr("data_objects"),
                    lambda x: f"{x.get('table_or_object', '')} {x.get('field', '')}",
                    names + sts,
                    20,
                ),
                "states": _pick_by_names(
                    arr("states"),
                    lambda x: f"{x.get('entity', '')} {x.get('state', '')}",
                    sts + names,
                    20,
                ),
                "ambiguities": [a for a in arr("ambiguities") if a.get("related_requirement_id") in ids],
            }

        out: list[dict[str, Any]] = []
        for idx, f in enumerate(features):
            fid = f.get("feature_id")
            reqs = [
                r
                for r in requirements
                if (r.get("feature_id") not in known if fid == "__GENERAL__" else r.get("feature_id") == fid)
            ]
            if not reqs:
                continue
            parts = math.ceil(len(reqs) / MAX_REQ_PER_FEATURE_CHUNK)
            for p in range(parts):
                sl = reqs[p * MAX_REQ_PER_FEATURE_CHUNK : (p + 1) * MAX_REQ_PER_FEATURE_CHUNK]
                feat_clean = {
                    "feature_id": fid,
                    "feature_name": f.get("feature_name"),
                    "description": f.get("description") or "",
                }
                chunk_id = f"F{idx + 1:02d}" + (f"-{p + 1}" if parts > 1 else "")
                out.append(
                    {
                        "chunk_id": chunk_id,
                        "suite_name": f.get("feature_name") or "General",
                        "suite_order": idx + 1,
                        "part": p + 1,
                        "total_parts": parts,
                        "context": build_context(feat_clean, sl),
                    }
                )

        has_regression = any(
            re.search(r"hồi quy|regression", str(f.get("feature_name") or ""), re.IGNORECASE)
            for f in features
        )
        cs_has = bool(change_scope.get("changed") or change_scope.get("unchanged_but_impacted"))
        if cs_has and not has_regression:
            order = len(features) + 1
            out.append(
                {
                    "chunk_id": f"F{order:02d}",
                    "suite_name": "Hồi quy các luồng bị ảnh hưởng bởi thay đổi",
                    "suite_order": order,
                    "part": 1,
                    "total_parts": 1,
                    "context": {
                        **base_ctx,
                        "feature": {
                            "feature_id": "__REGRESSION__",
                            "feature_name": "Hồi quy các luồng bị ảnh hưởng bởi thay đổi",
                            "description": "Các luồng đi qua API/module bị thay đổi phải giữ nguyên hành vi cũ.",
                        },
                        "requirements": [
                            {
                                "requirement_id": r.get("requirement_id"),
                                "type": r.get("type"),
                                "requirement": r.get("requirement"),
                                "expected_behavior": r.get("expected_behavior"),
                                "preconditions": r.get("preconditions"),
                                "related_api": r.get("related_api"),
                                "related_fields": r.get("related_fields"),
                                "related_state": r.get("related_state"),
                            }
                            for r in requirements
                        ],
                        "business_rules": arr("business_rules"),
                        "decision_tables": [],
                        "integrations": arr("integrations"),
                        "exceptions": [],
                        "flows": arr("flows"),
                        "inputs": [],
                        "apis": arr("apis"),
                        "data_objects": arr("data_objects")[:30],
                        "states": arr("states")[:30],
                        "ambiguities": [],
                    },
                }
            )

        return out

    def _generate_test_conditions(
        self,
        enriched_chunks: list[dict[str, Any]],
        user_prompt: str,
    ) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
        def call_cond_ai(chunk: dict[str, Any]) -> str | None:
            try:
                prompt = build_condition_generator_prompt(chunk, user_prompt)
                return self.ai.complete(prompt, max_tokens=8000, temperature=0.2)
            except Exception as e:
                LOGGER.warning("Test_condition_generator lỗi ở chunk %s: %s", chunk.get("chunk_id"), e)
                return None

        with ThreadPoolExecutor(max_workers=min(6, max(1, len(enriched_chunks)))) as pool:
            raw_results = list(pool.map(call_cond_ai, enriched_chunks))

        all_conditions: list[dict[str, Any]] = []
        cond_map: dict[str, dict[str, Any]] = {}

        def condition_from_requirement(r: dict[str, Any], suite_name: str) -> dict[str, Any]:
            return {
                "coverage_ids": [],
                "requirement_ids": [r.get("requirement_id")],
                "test_suite": suite_name,
                "condition": "Kiểm tra " + str(r.get("requirement") or ""),
                "context": r.get("context") or "",
                "condition_type": "Positive",
                "test_technique": "Use case",
                "preconditions": _arr_of(r.get("preconditions")),
                "test_data_hint": _arr_of(r.get("validation")),
                "expected_behavior_hint": [r["expected_behavior"]] if r.get("expected_behavior") else [],
                "verify_points": {"ui": [], "network_api": [], "log": [], "database": []},
                "related_api": _arr_of(r.get("related_api")),
                "related_fields": _arr_of(r.get("related_fields")),
                "related_state": _arr_of(r.get("related_state")),
                "requirement_gap": "Condition sinh dự phòng vì AI chưa bao phủ requirement này - cần rà soát/bổ sung",
                "_generated": "requirement_fallback",
            }

        for idx, raw in enumerate(raw_results):
            parsed = parse_loose(raw, "conditions") if raw and str(raw).strip() else None
            chunk = None
            if parsed and parsed["data"].get("chunk_id"):
                cid = parsed["data"]["chunk_id"]
                chunk = next((c for c in enriched_chunks if c.get("chunk_id") == cid), None)
            if not chunk and idx < len(enriched_chunks):
                chunk = enriched_chunks[idx]
            if not chunk:
                continue

            conds = (
                [c for c in parsed["data"].get("conditions", []) if isinstance(c, dict)]
                if parsed and isinstance(parsed["data"].get("conditions"), list)
                else []
            )
            req_ctx = chunk.get("context") or {}
            covered_req_ids: set[str] = set()
            for c in conds:
                for rid in _arr_of(c.get("requirement_ids")):
                    covered_req_ids.add(str(rid or "").strip())

            for r in req_ctx.get("requirements") or []:
                rid = str(r.get("requirement_id") or "").strip()
                if rid and rid not in covered_req_ids:
                    conds.append(condition_from_requirement(r, chunk["suite_name"]))

            for i, c in enumerate(conds, start=1):
                req_ids = [str(x) for x in _arr_of(c.get("requirement_ids")) if x]
                id_set = set(req_ids)
                by_req = lambda x: (x.get("requirement_id") in id_set) if id_set else True
                names = _flat_names(c.get("related_fields")) + _flat_names(c.get("related_state"))

                cond_id = f"{chunk['chunk_id']}_C{i:03d}"
                vp_raw = c.get("verify_points") if isinstance(c.get("verify_points"), dict) else {}
                tech = str(c.get("test_technique") or "Use case")
                cond_type = str(c.get("condition_type") or "Positive")
                is_dt = bool(re.search(r"quyết định", tech, re.IGNORECASE))
                is_int = bool(
                    re.search(r"tích hợp|negative|hồi quy", tech, re.IGNORECASE)
                    or cond_type == "Regression"
                )
                is_reg = bool(re.search(r"hồi quy", tech, re.IGNORECASE) or cond_type == "Regression")

                cond = {
                    **c,
                    "condition_id": cond_id,
                    "test_suite": chunk["suite_name"],
                    "suite_order": chunk["suite_order"],
                    "coverage_ids": _arr_of(c.get("coverage_ids")),
                    "requirement_ids": req_ids,
                    "condition_type": cond_type,
                    "test_technique": tech,
                    "preconditions": _arr_of(c.get("preconditions")),
                    "test_data_hint": _arr_of(c.get("test_data_hint")),
                    "expected_behavior_hint": _arr_of(c.get("expected_behavior_hint")),
                    "verify_points": {
                        "ui": _arr_of(vp_raw.get("ui")),
                        "network_api": _arr_of(vp_raw.get("network_api")),
                        "log": _arr_of(vp_raw.get("log")),
                        "database": _arr_of(vp_raw.get("database")),
                    },
                    "requirement_gap": c.get("requirement_gap") or None,
                    "requirement_context": {
                        "requirements": [
                            {
                                "requirement_id": r.get("requirement_id"),
                                "requirement": r.get("requirement"),
                                "expected_behavior": r.get("expected_behavior"),
                                "validation": r.get("validation"),
                                "error_handling": r.get("error_handling"),
                            }
                            for r in (req_ctx.get("requirements") or [])
                            if by_req(r)
                        ],
                        "business_rules": [x for x in (req_ctx.get("business_rules") or []) if by_req(x)],
                        "decision_tables": [x for x in (req_ctx.get("decision_tables") or []) if by_req(x)]
                        if is_dt
                        else [],
                        "integrations": [x for x in (req_ctx.get("integrations") or []) if by_req(x)]
                        if is_int
                        else [],
                        "exceptions": [x for x in (req_ctx.get("exceptions") or []) if by_req(x)]
                        if is_int
                        else [],
                        "inputs": _pick_by_names(req_ctx.get("inputs") or [], lambda x: x.get("name"), names, 6),
                        "data_objects": _pick_by_names(
                            req_ctx.get("data_objects") or [],
                            lambda x: f"{x.get('table_or_object', '')} {x.get('field', '')}",
                            names,
                            6,
                        )
                        if is_int
                        else [],
                        "states": _pick_by_names(
                            req_ctx.get("states") or [],
                            lambda x: f"{x.get('entity', '')} {x.get('state', '')}",
                            names,
                            6,
                        ),
                        **(
                            {"change_scope": req_ctx.get("change_scope")}
                            if is_reg and req_ctx.get("change_scope")
                            else {}
                        ),
                    },
                }
                all_conditions.append(cond)
                cond_map[cond_id] = {"cond": cond, "order": chunk["suite_order"]}

        if not all_conditions:
            raise RuntimeError("Test_condition_generator không trả về dữ liệu cho chunk nào.")
        return all_conditions, cond_map

    def _generate_testcases(
        self,
        all_conditions: list[dict[str, Any]],
        cond_map: dict[str, dict[str, Any]],
        user_prompt: str,
    ) -> list[dict[str, Any]]:
        batches = [
            all_conditions[i : i + CONDITIONS_PER_BATCH]
            for i in range(0, len(all_conditions), CONDITIONS_PER_BATCH)
        ]

        def run_batch(batch: list[dict[str, Any]]) -> list[dict[str, Any]]:
            prompt = build_testcase_generator_prompt(batch, user_prompt)
            raw = ""
            try:
                raw = self.ai.complete(prompt, max_tokens=8000, temperature=0.2)
            except Exception as e:
                LOGGER.warning("AI_Phan_tich_Testcase lỗi ở batch: %s", e)

            parsed = parse_loose(raw, "results") if raw.strip() else None
            results = (
                [r for r in parsed["data"].get("results", []) if isinstance(r, dict)]
                if parsed and isinstance(parsed["data"].get("results"), list)
                else []
            )
            if not results and parsed and isinstance(parsed["data"].get("testcases"), list):
                results = [parsed["data"]]

            res_by_id = {str(r.get("condition_id") or ""): r for r in results}

            # Tối ưu: nếu có condition trong batch bị thiếu hoặc cắt cụt, thử gọi bù riêng cho các condition đó
            missing_conds = [
                c
                for c in batch
                if c["condition_id"] not in res_by_id
                or not isinstance(res_by_id[c["condition_id"]].get("testcases"), list)
                or len(res_by_id[c["condition_id"]].get("testcases") or []) == 0
            ]
            if missing_conds and len(missing_conds) < len(batch):
                try:
                    retry_prompt = build_testcase_generator_prompt(missing_conds, user_prompt)
                    retry_raw = self.ai.complete(retry_prompt, max_tokens=6000, temperature=0.2)
                    retry_parsed = parse_loose(retry_raw, "results")
                    if retry_parsed and isinstance(retry_parsed["data"].get("results"), list):
                        for r in retry_parsed["data"]["results"]:
                            if isinstance(r, dict) and r.get("condition_id"):
                                res_by_id[str(r["condition_id"])] = r
                except Exception:
                    pass

            batch_rows: list[dict[str, Any]] = []
            for cond in batch:
                cid = cond["condition_id"]
                r = res_by_id.get(cid)
                if not r and len(batch) == 1 and len(results) == 1:
                    r = results[0]
                batch_rows.extend(
                    self._build_tc_rows_for_condition(
                        cond=cond,
                        r=r,
                        cond_map=cond_map,
                        was_salvaged=bool(parsed and parsed.get("salvaged")),
                    )
                )
            return batch_rows

        with ThreadPoolExecutor(max_workers=min(6, max(1, len(batches)))) as pool:
            nested = list(pool.map(run_batch, batches))

        all_rows: list[dict[str, Any]] = []
        for rows in nested:
            for row in rows:
                if row.get("muc_dich") and row.get("cac_buoc"):
                    all_rows.append(row)
        return all_rows

    @staticmethod
    def _build_tc_rows_for_condition(
        *,
        cond: dict[str, Any],
        r: dict[str, Any] | None,
        cond_map: dict[str, dict[str, Any]],
        was_salvaged: bool,
    ) -> list[dict[str, Any]]:
        def to_list(val: Any) -> list[str]:
            if val is None:
                return []
            arr = val if isinstance(val, list) else str(val).split("\n")
            out_list: list[str] = []
            for x in arr:
                s = _STEP_NUMBER_PREFIX_RE.sub("", str(x or "").strip())
                if s:
                    out_list.append(s)
            return out_list

        def build_steps(pre: Any, steps: Any) -> str:
            numbered = lambda lst: "\n".join(f"{i + 1}. {x}" for i, x in enumerate(lst))
            p = to_list(pre)
            s = to_list(steps)
            if not p:
                return "Step:\n" + numbered(s)
            return f"Pre: \n{numbered(p)}\nStep: \n{numbered(s)}"

        def format_result(v: Any) -> str:
            if v is None:
                return ""
            if isinstance(v, list):
                return "\n\n".join(str(x).strip() for x in v if x is not None and str(x).strip())
            return str(v).strip()

        def fallback_tc(c: dict[str, Any], label: str) -> dict[str, Any]:
            data_hints = [label] if label else _arr_of(c.get("test_data_hint"))
            steps = (
                ["Đăng nhập thành công", f'Truy cập chức năng thuộc "{c.get("test_suite") or ""}"']
                + [f"Chuẩn bị/nhập dữ liệu: {h}" for h in data_hints]
                + ([f"Thực hiện thao tác theo ngữ cảnh: {c['context']}"] if c.get("context") else [])
                + ["Quan sát và đối chiếu kết quả mong muốn"]
            )
            exp = _arr_of(c.get("expected_behavior_hint"))
            lines = "\n- ".join(str(x) for x in exp) if exp else "N/A (Tài liệu chưa đặc tả)"
            suffix = f" - {label}" if label else ""
            return {
                "test_suite": c.get("test_suite"),
                "muc_dich": f"Kiểm tra {c.get('condition') or ''}{suffix}",
                "dieu_kien_tien_quyet": c.get("preconditions") or [],
                "cac_buoc": steps,
                "ket_qua_mong_muon": [f"{len(steps)}. - {lines}"],
                "_fallback": True,
            }

        tcs = [tc for tc in (r.get("testcases") or []) if isinstance(tc, dict)] if r else []
        plan = [str(p) for p in (r.get("phan_vung_ap_dung") or []) if p] if r else []
        notes: list[str] = []

        if not tcs:
            notes.append(
                "JSON test case bị cắt cụt, condition này chưa được AI sinh"
                if was_salvaged
                else "AI không trả test case hợp lệ cho condition này"
            )
            labels = plan if plan else [str(x) for x in _arr_of(cond.get("test_data_hint"))]
            tcs = [fallback_tc(cond, lbl) for lbl in labels] if labels else [fallback_tc(cond, "")]
        elif len(plan) > len(tcs):
            notes.append(f"AI lập kế hoạch {len(plan)} phân vùng nhưng chỉ sinh {len(tcs)} TC")
            for i in range(len(tcs), len(plan)):
                tcs.append(fallback_tc(cond, plan[i]))

        ctx_order = (cond_map.get(cond.get("condition_id", "")) or {}).get("order")
        order = (
            cond.get("suite_order")
            if cond.get("suite_order") is not None
            else (ctx_order if ctx_order is not None else 9999)
        )
        src_ref = ", ".join(str(x) for x in _arr_of(cond.get("requirement_ids")))
        tag = f"[Nguồn: {src_ref}]" if src_ref else ""
        gap_note = f" [Thiếu đặc tả: {cond['requirement_gap']}]" if cond.get("requirement_gap") else ""

        rows: list[dict[str, Any]] = []
        for tc in tcs:
            purpose = str(tc.get("muc_dich") or "").strip()
            if purpose and not _STARTS_OK_RE.search(purpose):
                purpose = "Kiểm tra " + purpose[0].lower() + purpose[1:]
            review = (
                f" [CẦN RÀ SOÁT: {'; '.join(notes) or 'nội dung sinh dự phòng, chưa được AI chi tiết hóa'}]"
                if (tc.get("_fallback") or cond.get("_generated"))
                else ""
            )
            rows.append(
                {
                    "test_suite": cond.get("test_suite") or tc.get("test_suite") or "General",
                    "suite_order": order,
                    "condition_id": cond.get("condition_id") or "",
                    "muc_dich": purpose,
                    "cac_buoc": build_steps(tc.get("dieu_kien_tien_quyet"), tc.get("cac_buoc")),
                    "ket_qua_mong_muon": format_result(tc.get("ket_qua_mong_muon")),
                    "ghi_chu": (tag + gap_note + review).strip(),
                }
            )
        return rows

    @staticmethod
    def _group_by_test_suite(items: list[dict[str, Any]], prefix: str = "TC") -> list[dict[str, Any]]:
        if not items:
            return []

        norm = lambda s: re.sub(r"\s+", " ", str(s or "").lower()).strip()
        seen: set[str] = set()
        groups: dict[str, dict[str, Any]] = {}
        seq = 0

        for tc in items:
            suite = str(tc.get("test_suite") or "").strip() or "General"
            key = f"{suite}||{norm(tc.get('muc_dich'))}||{norm(tc.get('cac_buoc'))}||{norm(tc.get('ket_qua_mong_muon'))}"
            if key in seen:
                continue
            seen.add(key)
            if suite not in groups:
                try:
                    s_order = int(tc.get("suite_order", 9999))
                except Exception:
                    s_order = 9999
                groups[suite] = {"order": s_order, "first": seq, "list": []}
                seq += 1
            groups[suite]["list"].append(tc)

        ordered = sorted(groups.items(), key=lambda kv: (kv[1]["order"], kv[1]["first"]))

        tc_no = 0
        result: list[dict[str, Any]] = []
        for suite, g in ordered:
            result.append(
                {
                    "row_type": "suite",
                    "id": "",
                    "test_suite": suite,
                    "muc_dich": suite,
                    "cac_buoc": "",
                    "ket_qua_mong_muon": "",
                    "ghi_chu": "",
                }
            )
            for tc in g["list"]:
                tc_no += 1
                result.append(
                    {
                        "row_type": "testcase",
                        "id": f"[{prefix}]_{tc_no}",
                        "test_suite": suite,
                        "muc_dich": tc.get("muc_dich") or "",
                        "cac_buoc": tc.get("cac_buoc") or "",
                        "ket_qua_mong_muon": tc.get("ket_qua_mong_muon") or "",
                        "ghi_chu": tc.get("ghi_chu") or "",
                    }
                )
        return result
