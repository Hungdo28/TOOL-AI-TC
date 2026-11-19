from __future__ import annotations

import hashlib
import json
import logging
import re
import urllib.parse
from datetime import datetime, timezone
from typing import Any

LOGGER = logging.getLogger("autotc-backend")

_WORD_CLEAN_RE = re.compile(r"[^\w\s]", re.UNICODE)


def content_hash(text: str) -> str:
    """Sinh mã băm ngắn gọn (tương đương cyrb53/sha256 prefix) để chống trùng bản ghi."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _normalize_text(s: Any) -> str:
    return _WORD_CLEAN_RE.sub(" ", str(s or "").lower())


def _tokenize(s: Any) -> set[str]:
    return {w for w in _normalize_text(s).split() if len(w) >= 3}


class MemoryService:
    """
    Quản lý lưu trữ tài liệu (`problem_documents`), bản phân tích và truy xuất bộ nhớ testcase đã duyệt (`qa_memory`).
    Mọi thao tác đều bọc an toàn (non-fatal) để không bao giờ làm gãy luồng chính.
    """

    def __init__(self, supabase_repo: Any):
        self.sb = supabase_repo

    def get_crawled_document(self, problem_id: str, source_urls: str) -> str | None:
        """Lấy tài liệu đã crawl gần nhất từ Supabase nếu danh sách link URL không thay đổi."""
        if not problem_id or not hasattr(self.sb, "_request"):
            return None
        try:
            pid = urllib.parse.quote(str(problem_id))
            endpoint = f"problem_documents?problem_id=eq.{pid}&select=content,source_urls&order=crawled_at.desc&limit=1"
            rows = self.sb._request(endpoint, method="GET")
            if isinstance(rows, list) and rows:
                cached_row = rows[0]
                cached_urls = str(cached_row.get("source_urls") or "").strip()
                cached_content = str(cached_row.get("content") or "").strip()
                if cached_urls == source_urls.strip() and cached_content:
                    LOGGER.info("[%s] Đã tái sử dụng tài liệu crawl từ bộ nhớ đệm (Cache Hit - 0s).", problem_id)
                    return cached_content
        except Exception as e:
            LOGGER.debug("Không thể lấy cache problem_documents: %s", e)
        return None

    def save_crawled_document(
        self,
        *,
        problem_id: str,
        problem_title: str,
        source_urls: str,
        content: str,
    ) -> None:
        if not problem_id or not problem_title or not content.strip():
            return
        try:
            row = {
                "problem_id": str(problem_id),
                "problem_title": problem_title.strip(),
                "source_urls": str(source_urls or ""),
                "content": content.strip(),
                "content_hash": content_hash(content.strip()),
                "char_count": len(content.strip()),
                "crawled_at": datetime.now(timezone.utc).isoformat(),
            }
            self.sb._request(
                "problem_documents?on_conflict=problem_id,content_hash",
                method="POST",
                data=[row],
                prefer="resolution=merge-duplicates,return=minimal",
            )
        except Exception as e:
            LOGGER.warning("Lưu problem_documents thất bại (bỏ qua): %s", e)

    def save_analysis(
        self,
        *,
        problem_id: str,
        problem_title: str,
        final_text: str,
        doc_url: str,
    ) -> None:
        if not problem_id or not final_text.strip():
            return
        try:
            row = {
                "kind": "analysis",
                "problem_id": str(problem_id),
                "problem_title": problem_title.strip(),
                "test_suite": None,
                "content": {"final_text": final_text.strip(), "doc_url": doc_url or ""},
                "embed_text": None,
                "content_hash": content_hash(final_text.strip()),
            }
            self.sb._request(
                "qa_memory?on_conflict=kind,problem_id,content_hash",
                method="POST",
                data=[row],
                prefer="resolution=merge-duplicates,return=minimal",
            )
        except Exception as e:
            LOGGER.warning("Lưu qa_memory (analysis) thất bại (bỏ qua): %s", e)

    def save_testcases(
        self,
        *,
        problem_id: str,
        problem_title: str,
        sheet_rows: list[dict[str, Any]],
        approved: bool = False,
    ) -> None:
        if not problem_id or not sheet_rows:
            return
        try:
            records: list[dict[str, Any]] = []
            seen_hashes: set[str] = set()
            tc_idx = 0
            target_status = "approved" if approved else "pending"
            for r in sheet_rows:
                if r.get("row_type") != "testcase":
                    continue
                tc_idx += 1
                inner = r.get("content") if isinstance(r.get("content"), dict) else r
                content = {
                    "id": str(inner.get("id") or r.get("id") or f"[TC]_{tc_idx}").strip(),
                    "muc_dich": str(inner.get("muc_dich") or r.get("muc_dich") or ""),
                    "cac_buoc": str(inner.get("cac_buoc") or r.get("cac_buoc") or ""),
                    "ket_qua_mong_muon": str(inner.get("ket_qua_mong_muon") or r.get("ket_qua_mong_muon") or ""),
                    "ghi_chu": str(inner.get("ghi_chu") or r.get("ghi_chu") or ""),
                }
                hash_input = f"{r.get('test_suite', '')}|{content['id']}|{content['muc_dich']}"
                c_hash = content_hash(hash_input)
                if c_hash in seen_hashes:
                    c_hash = content_hash(f"{hash_input}#{tc_idx}")
                seen_hashes.add(c_hash)
                records.append({
                    "kind": "testcase",
                    "problem_id": str(problem_id),
                    "problem_title": str(problem_title).strip(),
                    "test_suite": r.get("test_suite") or "General",
                    "content": content,
                    "review_status": target_status,
                    "approved": bool(approved),
                    "content_hash": c_hash,
                })
            if records:
                # Xóa các testcase của các phiên chạy cũ thuộc cùng bài toán này để không bị cộng dồn qua nhiều lần chạy
                try:
                    pid_enc = urllib.parse.quote(str(problem_id))
                    title_enc = urllib.parse.quote(str(problem_title).strip())
                    self.sb._request(
                        f"qa_memory?kind=eq.testcase&or=(problem_id.eq.{pid_enc},problem_title.eq.{title_enc},problem_title.ilike.{title_enc})",
                        method="DELETE",
                        prefer="return=minimal",
                    )
                except Exception as del_err:
                    LOGGER.debug("Không thể dọn qa_memory cũ của bài toán %s: %s", problem_id, del_err)

                # Chia nhỏ thành từng lô 200 bản ghi để tránh quá tải/timeout REST API khi có hàng nghìn testcase
                batch_size = 200
                for start in range(0, len(records), batch_size):
                    chunk = records[start : start + batch_size]
                    self.sb._request(
                        "qa_memory?on_conflict=kind,problem_id,content_hash",
                        method="POST",
                        data=chunk,
                        prefer="resolution=merge-duplicates,return=minimal",
                    )
        except Exception as e:
            LOGGER.warning("Lưu qa_memory (testcases) thất bại (bỏ qua): %s", e)

    def fetch_task_testcases(
        self,
        *,
        problem_id: str = "",
        problem_title: str = "",
    ) -> list[dict[str, Any]]:
        """Lấy toàn bộ testcase mới nhất của 1 bài toán từ qa_memory (hỗ trợ phân trang >500 dòng)."""
        if not (problem_id or problem_title) or not hasattr(self.sb, "_request"):
            return []
        try:
            clauses: list[str] = []
            if problem_id:
                pid_enc = urllib.parse.quote(str(problem_id).strip())
                clauses.append(f"problem_id.eq.{pid_enc}")
            if problem_title:
                t_enc = urllib.parse.quote(str(problem_title).strip())
                clauses.append(f"problem_title.eq.{t_enc}")
                clauses.append(f"problem_title.ilike.{t_enc}")

            all_rows: list[dict[str, Any]] = []
            page_size = 1000
            offset = 0
            while offset < 10000:
                endpoint = (
                    f"qa_memory?kind=eq.testcase&or=({','.join(clauses)})"
                    "&select=id,problem_id,problem_title,test_suite,content,review_status,approved,created_at"
                    f"&order=created_at.desc,id.asc&limit={page_size}&offset={offset}"
                )
                page = self.sb._request(endpoint, method="GET")
                if not isinstance(page, list) or not page:
                    break
                all_rows.extend(r for r in page if isinstance(r, dict))
                if len(page) < page_size:
                    break
                offset += page_size

            if not all_rows:
                return []

            # Giữ phiên sinh mới nhất (trong vòng 3 phút kể từ bản ghi mới nhất)
            ts_list: list[float] = []
            for r in all_rows:
                raw_ts = str(r.get("created_at") or "").strip()
                if raw_ts:
                    try:
                        ts_list.append(datetime.fromisoformat(raw_ts.replace("Z", "+00:00")).timestamp())
                    except Exception:
                        pass
            if ts_list:
                max_ts = max(ts_list)
                filtered: list[dict[str, Any]] = []
                for r in all_rows:
                    raw_ts = str(r.get("created_at") or "").strip()
                    if not raw_ts:
                        continue
                    try:
                        t_val = datetime.fromisoformat(raw_ts.replace("Z", "+00:00")).timestamp()
                        if max_ts - t_val <= 180.0:
                            filtered.append(r)
                    except Exception:
                        pass
                if filtered:
                    return filtered
            return all_rows
        except Exception as e:
            LOGGER.warning("Truy vấn fetch_task_testcases thất bại: %s", e)
            return []

    def fetch_approved_testcases(self, exclude_problem_id: str) -> list[dict[str, Any]]:
        try:
            pid = urllib.parse.quote(str(exclude_problem_id or "none"))
            endpoint = (
                f"qa_memory?kind=eq.testcase&approved=eq.true&problem_id=neq.{pid}"
                "&select=problem_title,test_suite,content&order=reviewed_at.desc.nullslast&limit=300"
            )
            rows = self.sb._request(endpoint, method="GET")
            if not isinstance(rows, list):
                return []
            return [
                r
                for r in rows
                if isinstance(r, dict)
                and isinstance(r.get("content"), dict)
                and r["content"].get("muc_dich")
            ]
        except Exception as e:
            LOGGER.warning("Truy vấn qa_memory (approved testcases) thất bại (bỏ qua): %s", e)
            return []

    @staticmethod
    def build_memory_text_for_chunks(
        chunks: list[dict[str, Any]],
        approved_rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Chọn tối đa 4 testcase ĐÃ DUYỆT giống từng chunk nhất (khớp từ khóa + cộng điểm nếu trùng tên suite).
        """
        if not approved_rows:
            return [{**c, "memory_text": ""} for c in chunks]

        mem_tokens = []
        for r in approved_rows:
            c = r.get("content") or {}
            suite_str = str(r.get("test_suite") or "")
            title_str = str(r.get("problem_title") or "")
            purpose_str = str(c.get("muc_dich") or "")
            mem_tokens.append(
                {
                    "row": r,
                    "tokens": _tokenize(f"{suite_str} {title_str} {purpose_str}"),
                    "suite_norm": _normalize_text(suite_str).strip(),
                }
            )

        enriched: list[dict[str, Any]] = []
        for chunk in chunks:
            ctx_str = json.dumps(chunk.get("context") or {}, ensure_ascii=False)[:5000]
            suite_name = str(chunk.get("suite_name") or "")
            chunk_toks = _tokenize(f"{suite_name} {ctx_str}")
            suite_norm = _normalize_text(suite_name).strip()

            scored: list[tuple[int, dict[str, Any]]] = []
            for m in mem_tokens:
                score = sum(1 for w in m["tokens"] if w in chunk_toks)
                if m["suite_norm"] and m["suite_norm"] == suite_norm:
                    score += 5
                if score >= 3:
                    scored.append((score, m["row"]))

            scored.sort(key=lambda x: x[0], reverse=True)

            picked: list[dict[str, Any]] = []
            seen: set[str] = set()
            for _, row in scored:
                purpose_key = _normalize_text(row["content"].get("muc_dich")).strip()
                if purpose_key in seen:
                    continue
                seen.add(purpose_key)
                picked.append(row)
                if len(picked) >= 4:
                    break

            lines: list[str] = []
            for idx, r in enumerate(picked, start=1):
                c = r["content"]
                exp = re.sub(r"\s+", " ", str(c.get("ket_qua_mong_muon") or "")).strip()[:220]
                lines.append(
                    f"{idx}. [{r.get('problem_title', '')} | {r.get('test_suite', '')}] {c.get('muc_dich', '')}\n"
                    f"   Kết quả: {exp}"
                )

            enriched.append({**chunk, "memory_text": "\n".join(lines)})

        return enriched
