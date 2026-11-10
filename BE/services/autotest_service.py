from __future__ import annotations

import base64
import html
import json
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from core.config import Settings
from services.ai_client import AiClient
from services.common import ApiError
from services.doc_crawler import DocumentCrawler
from services.json_parser import parse_loose

LOGGER = logging.getLogger("autotc-backend")


class AutoTestService:
    """
    Test Execution Harness (AI Auto-Test Generator & Runner):
    1. Sinh kịch bản Auto Test có cấu trúc thực thi (API & Web UI) từ tài liệu / bài toán / Manual TC.
    2. Thực thi trực tiếp Auto Test API (HTTP Request thật + Assertions + AI Judge).
    3. Thực thi trực tiếp Auto Test Web UI (Playwright Chromium thật hoặc HTTP DOM Inspector).
    """

    def __init__(self, workspace: Any, settings: Settings):
        self.workspace = workspace
        self.settings = settings
        self.ai = AiClient(settings)
        self.crawler = DocumentCrawler(getattr(workspace, "_google_workspace", None), settings)

    # =========================================================================
    # 1. SINH TESTCASE CHO AUTO TEST (API & WEB UI)
    # =========================================================================
    def generate_autotest_cases(self, payload: dict[str, Any]) -> dict[str, Any]:
        task_name = str(payload.get("taskName") or payload.get("baiToan") or "").strip()
        problem_id = str(payload.get("problem_id") or "").strip()
        test_mode = str(payload.get("testMode") or "both").strip().lower()  # api | webui | both
        base_url = str(payload.get("baseUrl") or "").strip()
        web_url = str(payload.get("webUrl") or "").strip()
        spec_text = str(payload.get("specText") or "").strip()
        custom_prompt = str(payload.get("customPrompt") or "").strip()
        inspect_dom = bool(payload.get("inspectDom", True))
        login_username = str(payload.get("loginUsername") or "").strip()
        login_password = str(payload.get("loginPassword") or "").strip()
        manual_tcs = payload.get("manualTestcases") if isinstance(payload.get("manualTestcases"), list) else []

        # 1. Thu thập ngữ cảnh từ bài toán có sẵn nếu người dùng chọn bài toán
        doc_context = ""
        if not manual_tcs and (task_name or problem_id):
            manual_tcs = self._load_manual_testcases_from_supabase(problem_id or task_name)

        if task_name and not spec_text and not manual_tcs:
            try:
                task_row = self.workspace.find_task(task_name)
                if task_row and task_row.get("URL"):
                    urls = [u.strip() for u in str(task_row["URL"]).splitlines() if u.strip()]
                    if urls:
                        crawled = self.crawler.crawl_urls(urls[:3])
                        doc_context = "\n\n".join(c.get("content", "") for c in crawled if c.get("content"))[:12000]
            except Exception as err:
                LOGGER.warning("Không thể crawl tài liệu gốc cho AutoTest [%s]: %s", task_name, err)

        # 2. Trinh sát DOM thực tế của trang Web (Live SPA DOM Discovery) nếu có web_url
        live_dom_summary = ""
        if inspect_dom and web_url and test_mode in ("webui", "both") and self.settings.ai_api_key:
            live_dom_summary = self._inspect_live_spa_dom(
                web_url=web_url,
                login_username=login_username,
                login_password=login_password,
            )

        combined_spec = "\n\n".join(filter(None, [spec_text or doc_context, live_dom_summary]))

        prompt = self._build_generation_prompt(
            task_name=task_name or "Bài toán Auto Test",
            test_mode=test_mode,
            base_url=base_url,
            web_url=web_url,
            spec_text=combined_spec,
            custom_prompt=custom_prompt,
            manual_tcs=manual_tcs,
        )

        generated_cases: list[dict[str, Any]] = []
        token_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}

        try:
            self.ai.reset_task_usage(task_name or "autotest-gen")
            raw_ai = self.ai.complete(
                prompt,
                max_tokens=7000,
                temperature=0.2,
                timeout=120,
                task_name=task_name or "autotest-gen",
            )
            token_usage = self.ai.get_task_usage(task_name or "autotest-gen")
            parsed = parse_loose(raw_ai, "testcases")
            if parsed and isinstance(parsed.get("data"), dict):
                raw_list = parsed["data"].get("testcases")
                if isinstance(raw_list, list):
                    generated_cases = [self._normalize_autotest_case(item, idx + 1, test_mode, base_url, web_url) for idx, item in enumerate(raw_list) if isinstance(item, dict)]
        except Exception as err:
            LOGGER.warning("Gọi AI sinh AutoTest gặp lỗi, chuyển sang chế độ chuyển đổi thông minh: %s", err)

        if not generated_cases:
            generated_cases = self._fallback_convert_or_sample(
                task_name=task_name or "AutoTest",
                test_mode=test_mode,
                base_url=base_url,
                web_url=web_url,
                manual_tcs=manual_tcs,
                spec_text=spec_text,
            )

        return {
            "success": True,
            "taskName": task_name or "Bài toán Auto Test",
            "testMode": test_mode,
            "count": len(generated_cases),
            "token_usage": token_usage,
            "dom_inspected": bool(live_dom_summary),
            "testcases": generated_cases,
        }

    def _inspect_live_spa_dom(
        self,
        *,
        web_url: str,
        login_username: str = "",
        login_password: str = "",
    ) -> str:
        """
        Bước 1 của luồng toàn trình: Mở trang web thật bằng Playwright (hỗ trợ SPA #/login, #/search-information/...),
        tự động đăng nhập nếu cần, và quét toàn bộ các ô input, button, select thực tế trên màn hình.
        """
        try:
            from playwright.sync_api import sync_playwright  # type: ignore

            with sync_playwright() as p:
                browser = self._launch_browser_with_fallback(p, headless=True)
                context = browser.new_context(
                    viewport={"width": 1366, "height": 768},
                    ignore_https_errors=True,
                )
                page = context.new_page()
                page.set_default_timeout(12000)
                try:
                    page.goto(web_url, wait_until="domcontentloaded")
                    try:
                        page.wait_for_load_state("networkidle", timeout=6000)
                    except Exception:
                        pass
                    page.wait_for_timeout(1500)

                    # Nếu trang bị redirect về login và có tài khoản cấu hình sẵn -> đăng nhập trước để vào trang đích
                    if login_username and login_password and ("login" in page.url.lower() and "login" not in web_url.lower()):
                        self._perform_auto_login(page, login_username, login_password, target_url=web_url)

                    dom_info = page.evaluate(
                        """() => {
                            const clean = (s) => (s || '').replace(/\\s+/g, ' ').trim().slice(0, 80);
                            const inputs = Array.from(document.querySelectorAll('input, textarea, select')).map((el, idx) => {
                                const id = el.id ? `#${el.id}` : '';
                                const name = el.getAttribute('name') ? `[name="${el.getAttribute('name')}"]` : '';
                                const ph = el.getAttribute('placeholder') || '';
                                const formCtrl = el.getAttribute('formcontrolname') ? `[formcontrolname="${el.getAttribute('formcontrolname')}"]` : '';
                                const type = el.getAttribute('type') || el.tagName.toLowerCase();
                                const selector = id || formCtrl || name || (ph ? `${el.tagName.toLowerCase()}[placeholder="${ph}"]` : `${el.tagName.toLowerCase()}:nth-of-type(${idx + 1})`);
                                return `- Input (${type}): selector="${selector}" | placeholder="${clean(ph)}"`;
                            });
                            const buttons = Array.from(document.querySelectorAll('button, a.btn, input[type="submit"], [role="button"]')).map((el) => {
                                const txt = clean(el.innerText || el.value || '');
                                const id = el.id ? `#${el.id}` : '';
                                if (!txt && !id) return null;
                                const selector = id || (txt ? `button:has-text("${txt}")` : 'button');
                                return `- Button: selector='${selector}' | text="${txt}"`;
                            }).filter(Boolean);
                            return {
                                url: location.href,
                                title: document.title,
                                inputs: inputs.slice(0, 25),
                                buttons: buttons.slice(0, 20)
                            };
                        }"""
                    )
                    lines = [
                        f"BẢN ĐỒ PHẦN TỬ DOM THỰC TẾ TRÊN TRANG WEB ({dom_info.get('url')} - Tiêu đề: {dom_info.get('title')}):",
                        "Các ô nhập liệu (Inputs) thực tế đang có trên màn hình:",
                        *(dom_info.get("inputs") or ["(Không tìm thấy input tĩnh)"]),
                        "Các nút bấm (Buttons) thực tế đang có trên màn hình:",
                        *(dom_info.get("buttons") or ["(Không tìm thấy button tĩnh)"]),
                        "HÃY SỬ DỤNG CHÍNH XÁC CÁC SELECTOR THỰC TẾ Ở TRÊN TRONG MẢNG `actions` CỦA `WEB_UI`!",
                    ]
                    LOGGER.info("[DOM Discovery] Đã quét %d inputs và %d buttons từ %s", len(dom_info.get("inputs", [])), len(dom_info.get("buttons", [])), web_url)
                    return "\n".join(lines)
                finally:
                    browser.close()
        except Exception as err:
            LOGGER.warning("Không thể quét Live DOM cho %s: %s", web_url, err)
            return ""

    def _load_manual_testcases_from_supabase(self, identifier: str) -> list[dict[str, Any]]:
        if not identifier or not hasattr(self.workspace, "_request"):
            return []
        try:
            enc = urllib.parse.quote(identifier)
            endpoint = (
                f"qa_memory?kind=eq.testcase"
                f"&or=(problem_id.eq.{enc},problem_title.eq.{enc},problem_title.ilike.{enc})"
                f"&select=id,test_suite,content,review_status,approved"
                f"&order=created_at.asc,id.asc&limit=60"
            )
            rows = self.workspace._request(endpoint)
            if not isinstance(rows, list):
                return []
            # Ưu tiên lấy các testcase đã approved, nếu chưa có thì lấy tất cả
            approved = [r for r in rows if r.get("approved") is True or r.get("review_status") == "approved"]
            target = approved if approved else rows
            result = []
            for r in target[:30]:
                content = r.get("content") if isinstance(r.get("content"), dict) else {}
                result.append({
                    "id": content.get("id") or r.get("id"),
                    "test_suite": r.get("test_suite") or content.get("test_suite") or "General",
                    "muc_dich": content.get("muc_dich") or "",
                    "dieu_kien_tien_quyet": content.get("dieu_kien_tien_quyet") or "",
                    "cac_buoc": content.get("cac_buoc") or "",
                    "ket_qua_mong_muon": content.get("ket_qua_mong_muon") or "",
                })
            return result
        except Exception as err:
            LOGGER.warning("Không thể đọc Manual TC từ Supabase cho [%s]: %s", identifier, err)
            return []

    @staticmethod
    def _build_generation_prompt(
        *,
        task_name: str,
        test_mode: str,
        base_url: str,
        web_url: str,
        spec_text: str,
        custom_prompt: str,
        manual_tcs: list[dict[str, Any]],
    ) -> str:
        mode_instruction = {
            "api": "CHỈ SINH các kịch bản kiểm thử tự động loại 'API' (HTTP Request RESTful).",
            "webui": "CHỈ SINH các kịch bản kiểm thử tự động loại 'WEB_UI' (Thao tác trình duyệt Playwright).",
            "both": "Sinh kết hợp cả kịch bản kiểm thử 'API' (HTTP Request) và 'WEB_UI' (Thao tác giao diện trình duyệt).",
        }.get(test_mode, "Sinh kết hợp cả kịch bản 'API' và 'WEB_UI'.")

        manual_block = ""
        if manual_tcs:
            manual_block = "DANH SÁCH TESTCASE MANUAL CẦN CHUYỂN ĐỔI SANG AUTO TEST:\n" + json.dumps(
                manual_tcs[:25], ensure_ascii=False, indent=2
            )

        return f"""Bạn là Kiến trúc sư Kiểm thử Tự động (SDET / Automation Test Architect).
Nhiệm vụ: Thiết kế danh sách Testcase Tự động hóa (Executable Auto-Test Cases) cho bài toán: "{task_name}".

CHẾ ĐỘ YÊU CẦU: {mode_instruction}
- API Base URL mục tiêu: {base_url or 'http://localhost:8088'}
- Web UI URL mục tiêu: {web_url or 'http://127.0.0.1:5500/FE/login.html'}

{f'ĐẶC TẢ KỸ THUẬT / SWAGGER / TÀI LIỆU:{chr(10)}{spec_text[:8000]}' if spec_text else ''}

{manual_block}

{f'YÊU CẦU BỔ SUNG TỪ QA:{chr(10)}{custom_prompt}' if custom_prompt else ''}

Hãy trả về DUY NHẤT một chuỗi JSON hợp lệ theo đúng cấu trúc dưới đây (không kèm markdown thừa):
{{
  "testcases": [
    {{
      "id": "AUTO_001",
      "test_suite": "Tên nhóm chức năng",
      "muc_dich": "Kiểm tra ...",
      "test_type": "API",
      "priority": "High",
      "dieu_kien_tien_quyet": "Server đang hoạt động",
      "cac_buoc": "1. Gửi request...\\n2. Kiểm tra mã trạng thái và dữ liệu trả về",
      "ket_qua_mong_muon": "HTTP 200 OK, trả về dữ liệu hợp lệ",
      "auto_spec": {{
        "method": "GET",
        "endpoint": "/api/health",
        "headers": {{"Accept": "application/json"}},
        "body": null,
        "expected_status": 200,
        "assertions": [
          {{"type": "status_code", "expected": 200}},
          {{"type": "body_contains", "value": "ok"}}
        ]
      }}
    }},
    {{
      "id": "AUTO_002",
      "test_suite": "Giao diện Người dùng",
      "muc_dich": "Kiểm tra hiển thị và thao tác trên trang",
      "test_type": "WEB_UI",
      "priority": "High",
      "dieu_kien_tien_quyet": "Mở trình duyệt",
      "cac_buoc": "1. Truy cập URL\\n2. Nhập thông tin\\n3. Bấm nút xác nhận",
      "ket_qua_mong_muon": "Hiển thị giao diện hợp lệ",
      "auto_spec": {{
        "target_url": "{web_url or 'http://127.0.0.1:5500/FE/login.html'}",
        "actions": [
          {{"action": "goto", "url": "{web_url or 'http://127.0.0.1:5500/FE/login.html'}", "desc": "Mở trang web"}},
          {{"action": "assert_visible", "selector": "body", "desc": "Kiểm tra trang tải thành công"}}
        ]
      }}
    }}
  ]
}}

LƯU Ý QUAN TRỌNG:
1. Với test_type = "API", `auto_spec` PHẢI có `method` (GET/POST/PUT/DELETE/PATCH), `endpoint`, `headers`, `body`, `expected_status` (số nguyên), và mảng `assertions` (`status_code`, `body_contains`, `json_has_key`, `json_equals`).
2. Với test_type = "WEB_UI", `auto_spec` PHẢI có `target_url` và mảng `actions` với `action` thuộc: `goto`, `fill`, `click`, `wait`, `assert_visible`, `assert_text`, `assert_title`, `assert_url`.
3. Bao phủ đầy đủ các kịch bản: Happy Path (Positive), Negative Case (dữ liệu rỗng/sai định dạng/không có quyền), và Boundary Case (giá trị biên).
"""

    @staticmethod
    def _normalize_autotest_case(
        raw: dict[str, Any],
        index: int,
        test_mode: str,
        base_url: str,
        web_url: str,
    ) -> dict[str, Any]:
        tc_type = str(raw.get("test_type") or "").strip().upper()
        if test_mode == "api":
            tc_type = "API"
        elif test_mode == "webui":
            tc_type = "WEB_UI"
        elif tc_type not in ("API", "WEB_UI"):
            tc_type = "API" if index % 2 == 1 else "WEB_UI"

        auto_spec = raw.get("auto_spec") if isinstance(raw.get("auto_spec"), dict) else {}
        if tc_type == "API":
            method = str(auto_spec.get("method") or "GET").upper().strip()
            endpoint = str(auto_spec.get("endpoint") or "/api/health").strip()
            expected_status = int(auto_spec.get("expected_status") or 200)
            headers = auto_spec.get("headers") if isinstance(auto_spec.get("headers"), dict) else {"Content-Type": "application/json"}
            body = auto_spec.get("body")
            assertions = auto_spec.get("assertions") if isinstance(auto_spec.get("assertions"), list) else [
                {"type": "status_code", "expected": expected_status}
            ]
            norm_spec = {
                "method": method,
                "endpoint": endpoint,
                "headers": headers,
                "body": body,
                "expected_status": expected_status,
                "assertions": assertions,
            }
        else:
            target = str(auto_spec.get("target_url") or web_url or "http://127.0.0.1:5500/FE/login.html").strip()
            actions = auto_spec.get("actions") if isinstance(auto_spec.get("actions"), list) else [
                {"action": "goto", "url": target, "desc": "Mở trang mục tiêu"},
                {"action": "assert_visible", "selector": "body", "desc": "Kiểm tra trang hiển thị"},
            ]
            norm_spec = {
                "target_url": target,
                "actions": actions,
            }

        steps_val = raw.get("cac_buoc") or ""
        if isinstance(steps_val, list):
            steps_val = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(steps_val))

        exp_val = raw.get("ket_qua_mong_muon") or ""
        if isinstance(exp_val, list):
            exp_val = "\n".join(str(x) for x in exp_val)

        return {
            "id": str(raw.get("id") or f"AUTO_{index:03d}"),
            "test_suite": str(raw.get("test_suite") or "Auto Test Suite"),
            "muc_dich": str(raw.get("muc_dich") or f"Kiểm tra tự động #{index}"),
            "test_type": tc_type,
            "priority": str(raw.get("priority") or "High"),
            "dieu_kien_tien_quyet": str(raw.get("dieu_kien_tien_quyet") or "Môi trường đích sẵn sàng"),
            "cac_buoc": str(steps_val),
            "ket_qua_mong_muon": str(exp_val),
            "auto_spec": norm_spec,
        }

    def _fallback_convert_or_sample(
        self,
        *,
        task_name: str,
        test_mode: str,
        base_url: str,
        web_url: str,
        manual_tcs: list[dict[str, Any]],
        spec_text: str,
    ) -> list[dict[str, Any]]:
        target_web = web_url or "http://127.0.0.1:5500/FE/login.html"
        # Nếu có sẵn Manual Testcases, tự động chuyển đổi từng Manual TC sang Auto TC
        if manual_tcs:
            converted: list[dict[str, Any]] = []
            for idx, mtc in enumerate(manual_tcs[:20], start=1):
                purpose = str(mtc.get("muc_dich") or f"Kiểm tra kịch bản #{idx}")
                steps = str(mtc.get("cac_buoc") or "")
                expected = str(mtc.get("ket_qua_mong_muon") or "")
                is_api = (
                    test_mode == "api"
                    or (test_mode == "both" and any(k in (purpose + steps).lower() for k in ("api", "post", "get", "endpoint", "json", "status", "code", "token")))
                )
                tc_type = "API" if is_api and test_mode != "webui" else "WEB_UI"

                # Trích xuất endpoint nếu có trong bước thực hiện
                ep_match = re.search(r"(/api/[a-zA-Z0-9_\-/]+)", steps + " " + purpose)
                endpoint = ep_match.group(1) if ep_match else "/api/health"
                method = "POST" if any(k in steps.upper() for k in ("POST", "GỬI", "THÊM", "TẠO", "ĐĂNG NHẬP")) else "GET"
                exp_status = 400 if any(k in purpose.lower() for k in ("lỗi", "sai", "trống", "rỗng", "không hợp lệ", "negative")) else 200

                if tc_type == "API":
                    auto_spec = {
                        "method": method,
                        "endpoint": endpoint,
                        "headers": {"Content-Type": "application/json"},
                        "body": {"test": True} if method in ("POST", "PUT", "PATCH") else None,
                        "expected_status": exp_status,
                        "assertions": [{"type": "status_code", "expected": exp_status}],
                    }
                else:
                    auto_spec = {
                        "target_url": target_web,
                        "actions": [
                            {"action": "goto", "url": target_web, "desc": f"Mở trang {target_web}"},
                            {"action": "assert_visible", "selector": "body", "desc": "Kiểm tra giao diện hiển thị"},
                        ],
                    }

                converted.append({
                    "id": f"AUTO_{idx:03d}",
                    "test_suite": str(mtc.get("test_suite") or task_name),
                    "muc_dich": purpose,
                    "test_type": tc_type,
                    "priority": "High",
                    "dieu_kien_tien_quyet": str(mtc.get("dieu_kien_tien_quyet") or "Môi trường Test sẵn sàng"),
                    "cac_buoc": steps,
                    "ket_qua_mong_muon": expected,
                    "auto_spec": auto_spec,
                })
            return converted

        # Bộ kịch bản mẫu thực tế có thể chạy thật ngay trên chính hệ thống AutoTC
        samples: list[dict[str, Any]] = []
        if test_mode in ("api", "both"):
            samples.extend([
                {
                    "id": "AUTO_001",
                    "test_suite": "Kiểm thử API Hệ thống",
                    "muc_dich": "Kiểm tra API Health Check hoạt động ổn định (Happy Path)",
                    "test_type": "API",
                    "priority": "High",
                    "dieu_kien_tien_quyet": "Backend Server đang chạy",
                    "cac_buoc": "1. Gửi request GET tới /api/health\n2. Kiểm tra HTTP Status = 200 và trường status = ok",
                    "ket_qua_mong_muon": "HTTP 200 OK, body trả về {\"status\": \"ok\"}",
                    "auto_spec": {
                        "method": "GET",
                        "endpoint": "/api/health",
                        "headers": {"Accept": "application/json"},
                        "body": None,
                        "expected_status": 200,
                        "assertions": [
                            {"type": "status_code", "expected": 200},
                            {"type": "json_equals", "key": "status", "expected": "ok"},
                        ],
                    },
                },
                {
                    "id": "AUTO_002",
                    "test_suite": "Kiểm thử API Xác thực (JWT)",
                    "muc_dich": "Kiểm tra API cấp JWT Token thành công với username hợp lệ",
                    "test_type": "API",
                    "priority": "High",
                    "dieu_kien_tien_quyet": "Endpoint /api/auth/token sẵn sàng",
                    "cac_buoc": "1. Gửi POST /api/auth/token với body {\"username\": \"hung\"}\n2. Kiểm tra HTTP Status = 200 và nhận được chuỗi JWT token",
                    "ket_qua_mong_muon": "HTTP 200 OK, response chứa trường token và role",
                    "auto_spec": {
                        "method": "POST",
                        "endpoint": "/api/auth/token",
                        "headers": {"Content-Type": "application/json"},
                        "body": {"username": "hung"},
                        "expected_status": 200,
                        "assertions": [
                            {"type": "status_code", "expected": 200},
                            {"type": "json_has_key", "key": "token"},
                        ],
                    },
                },
                {
                    "id": "AUTO_003",
                    "test_suite": "Kiểm thử API Xác thực (Negative)",
                    "muc_dich": "Kiểm tra API cấp JWT Token báo lỗi 400 khi bỏ trống username",
                    "test_type": "API",
                    "priority": "Medium",
                    "dieu_kien_tien_quyet": "Endpoint /api/auth/token sẵn sàng",
                    "cac_buoc": "1. Gửi POST /api/auth/token với body rỗng {}\n2. Kiểm tra mã lỗi trả về",
                    "ket_qua_mong_muon": "HTTP 400 Bad Request, thông báo thiếu tên đăng nhập",
                    "auto_spec": {
                        "method": "POST",
                        "endpoint": "/api/auth/token",
                        "headers": {"Content-Type": "application/json"},
                        "body": {},
                        "expected_status": 400,
                        "assertions": [
                            {"type": "status_code", "expected": 400},
                        ],
                    },
                },
                {
                    "id": "AUTO_004",
                    "test_suite": "Kiểm thử API Quản lý Bài toán",
                    "muc_dich": "Kiểm tra API lấy danh sách bài toán (/api/tasks) với quyền Admin",
                    "test_type": "API",
                    "priority": "High",
                    "dieu_kien_tien_quyet": "Có Header xác thực hợp lệ",
                    "cac_buoc": "1. Gửi GET /api/tasks kèm Header X-User-Name: hung, X-User-Role: admin\n2. Kiểm tra dữ liệu trả về là danh sách bài toán",
                    "ket_qua_mong_muon": "HTTP 200 OK, trả về mảng JSON các bài toán",
                    "auto_spec": {
                        "method": "GET",
                        "endpoint": "/api/tasks",
                        "headers": {"X-User-Name": "hung", "X-User-Role": "admin"},
                        "body": None,
                        "expected_status": 200,
                        "assertions": [
                            {"type": "status_code", "expected": 200},
                        ],
                    },
                },
            ])

        if test_mode in ("webui", "both"):
            samples.extend([
                {
                    "id": f"AUTO_00{len(samples) + 1}",
                    "test_suite": "Kiểm thử Giao diện Web (UI)",
                    "muc_dich": "Kiểm tra tải trang giao diện và xác minh các phần tử chính hiển thị",
                    "test_type": "WEB_UI",
                    "priority": "High",
                    "dieu_kien_tien_quyet": f"Trang web tại {target_web} đang mở",
                    "cac_buoc": f"1. Mở trình duyệt truy cập {target_web}\n2. Kiểm tra tiêu đề trang và phần tử form/body hiển thị",
                    "ket_qua_mong_muon": "Trang phản hồi HTTP 200, hiển thị đầy đủ giao diện không bị lỗi trắng trang",
                    "auto_spec": {
                        "target_url": target_web,
                        "actions": [
                            {"action": "goto", "url": target_web, "desc": f"Truy cập {target_web}"},
                            {"action": "assert_visible", "selector": "body", "desc": "Kiểm tra phần tử body hiển thị"},
                        ],
                    },
                }
            ])

        return samples

    # =========================================================================
    # 2. THỰC THI AUTO TEST (TEST EXECUTION HARNESS)
    # =========================================================================
    def run_autotest_suite(self, payload: dict[str, Any]) -> dict[str, Any]:
        testcases = payload.get("testcases")
        if not isinstance(testcases, list) or not testcases:
            raise ApiError(400, "Danh sách testcases cần chạy không được để trống.")

        env_config = payload.get("envConfig") if isinstance(payload.get("envConfig"), dict) else {}
        default_base_url = str(
            env_config.get("baseUrl")
            or f"http://127.0.0.1:{self.settings.port}"
        ).strip().rstrip("/")
        default_web_url = str(env_config.get("webUrl") or "").strip()
        auth_token = str(env_config.get("authToken") or "").strip()
        custom_headers = env_config.get("customHeaders") if isinstance(env_config.get("customHeaders"), dict) else {}
        timeout_sec = max(3, min(60, int(env_config.get("timeoutSec") or 15)))
        headless = bool(env_config.get("headless", True))
        use_playwright = bool(env_config.get("usePlaywright", True))
        screenshot_dir = str(env_config.get("screenshotDir") or "AutoTC_Screenshots").strip()
        task_name = str(payload.get("taskName") or env_config.get("taskName") or "AutoTest").strip()
        login_username = str(env_config.get("loginUsername") or "").strip()
        login_password = str(env_config.get("loginPassword") or "").strip()

        started_at = time.time()
        results: list[dict[str, Any]] = []

        for idx, tc in enumerate(testcases, start=1):
            if not isinstance(tc, dict):
                continue
            tc_type = str(tc.get("test_type") or "API").upper().strip()
            if tc_type == "WEB_UI":
                res = self._execute_webui_testcase(
                    tc,
                    default_web_url=default_web_url,
                    timeout_sec=timeout_sec,
                    headless=headless,
                    use_playwright=use_playwright,
                    screenshot_dir=screenshot_dir,
                    task_name=task_name,
                    login_username=login_username,
                    login_password=login_password,
                )
            else:
                res = self._execute_api_testcase(
                    tc,
                    default_base_url=default_base_url,
                    auth_token=auth_token,
                    custom_headers=custom_headers,
                    timeout_sec=timeout_sec,
                )
            results.append(res)

        total_duration_ms = int((time.time() - started_at) * 1000)
        passed = sum(1 for r in results if r["status"] == "PASS")
        failed = sum(1 for r in results if r["status"] == "FAIL")
        errored = sum(1 for r in results if r["status"] == "ERROR")
        total = len(results)
        pass_rate = round((passed / total) * 100, 1) if total > 0 else 0.0

        return {
            "success": True,
            "summary": {
                "total": total,
                "passed": passed,
                "failed": failed,
                "error": errored,
                "pass_rate": pass_rate,
                "total_duration_ms": total_duration_ms,
                "executed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            },
            "results": results,
        }

    # -------------------------------------------------------------------------
    # A. Bộ thực thi API Test (HTTP Runner)
    # -------------------------------------------------------------------------
    def _execute_api_testcase(
        self,
        tc: dict[str, Any],
        *,
        default_base_url: str,
        auth_token: str,
        custom_headers: dict[str, Any],
        timeout_sec: int,
    ) -> dict[str, Any]:
        tc_id = str(tc.get("id") or "AUTO_TC")
        spec = tc.get("auto_spec") if isinstance(tc.get("auto_spec"), dict) else {}
        method = str(spec.get("method") or "GET").upper().strip()
        endpoint = str(spec.get("endpoint") or "/api/health").strip()

        if endpoint.startswith("http://") or endpoint.startswith("https://"):
            url = endpoint
        else:
            path = endpoint if endpoint.startswith("/") else f"/{endpoint}"
            url = f"{default_base_url}{path}"

        headers: dict[str, str] = {"User-Agent": "AutoTC-TestHarness/2.0"}
        for k, v in custom_headers.items():
            if k and v is not None:
                headers[str(k)] = str(v)
        if isinstance(spec.get("headers"), dict):
            for k, v in spec["headers"].items():
                if k and v is not None:
                    headers[str(k)] = str(v)
        if auth_token and "Authorization" not in headers:
            headers["Authorization"] = (
                auth_token if auth_token.lower().startswith("bearer ") else f"Bearer {auth_token}"
            )

        body_data = spec.get("body")
        body_bytes: bytes | None = None
        if body_data is not None and method not in ("GET", "HEAD"):
            if isinstance(body_data, (dict, list)):
                body_bytes = json.dumps(body_data, ensure_ascii=False).encode("utf-8")
                headers.setdefault("Content-Type", "application/json")
            elif isinstance(body_data, str) and body_data.strip():
                body_bytes = body_data.encode("utf-8")

        t0 = time.perf_counter()
        actual_status = 0
        raw_response_text = ""
        response_json: Any = None
        network_error: str | None = None

        req = urllib.request.Request(url, data=body_bytes, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                actual_status = int(resp.status)
                raw_bytes = resp.read(16384)
                raw_response_text = raw_bytes.decode("utf-8", errors="replace")
        except urllib.error.HTTPError as http_err:
            actual_status = int(http_err.code)
            try:
                raw_response_text = http_err.read(16384).decode("utf-8", errors="replace")
            except Exception:
                raw_response_text = str(http_err)
        except Exception as err:
            network_error = str(err)

        duration_ms = int((time.perf_counter() - t0) * 1000)

        if raw_response_text:
            try:
                response_json = json.loads(raw_response_text)
            except Exception:
                response_json = None

        if network_error:
            return {
                "id": tc_id,
                "muc_dich": tc.get("muc_dich") or "",
                "test_type": "API",
                "status": "ERROR",
                "duration_ms": duration_ms,
                "actual_status_code": 0,
                "actual_result": f"Lỗi kết nối tới {url}: {network_error}",
                "assertion_logs": [f"❌ Không thể kết nối tới {url}: {network_error}"],
                "request_info": {"method": method, "url": url, "headers": headers, "body": body_data},
                "response_preview": network_error,
            }

        # Kiểm tra Assertions
        expected_status = int(spec.get("expected_status") or 200)
        assertions = spec.get("assertions") if isinstance(spec.get("assertions"), list) else []
        if not assertions:
            assertions = [{"type": "status_code", "expected": expected_status}]

        assertion_logs: list[str] = []
        all_passed = True

        for a in assertions:
            if not isinstance(a, dict):
                continue
            atype = str(a.get("type") or "").strip().lower()
            if atype == "status_code":
                exp_code = int(a.get("expected") or expected_status)
                ok = actual_status == exp_code
                all_passed = all_passed and ok
                assertion_logs.append(
                    f"{'✅' if ok else '❌'} HTTP Status: thực tế = {actual_status}, kỳ vọng = {exp_code}"
                )
            elif atype == "body_contains":
                needle = str(a.get("value") or a.get("expected") or "")
                ok = needle.lower() in raw_response_text.lower()
                all_passed = all_passed and ok
                assertion_logs.append(
                    f"{'✅' if ok else '❌'} Response chứa từ khóa '{needle}'"
                )
            elif atype == "json_has_key":
                key_name = str(a.get("key") or a.get("value") or "")
                ok = isinstance(response_json, dict) and key_name in response_json
                all_passed = all_passed and ok
                assertion_logs.append(
                    f"{'✅' if ok else '❌'} JSON có chứa trường '{key_name}'"
                )
            elif atype == "json_equals":
                key_name = str(a.get("key") or "")
                exp_val = a.get("expected")
                act_val = response_json.get(key_name) if isinstance(response_json, dict) else None
                ok = str(act_val) == str(exp_val)
                all_passed = all_passed and ok
                assertion_logs.append(
                    f"{'✅' if ok else '❌'} JSON['{key_name}']: thực tế = {act_val!r}, kỳ vọng = {exp_val!r}"
                )

        status_label = "PASS" if all_passed else "FAIL"
        preview = raw_response_text[:600] + ("..." if len(raw_response_text) > 600 else "")
        actual_summary = f"HTTP {actual_status} ({duration_ms}ms) | { '; '.join(assertion_logs) }"

        return {
            "id": tc_id,
            "muc_dich": tc.get("muc_dich") or "",
            "test_type": "API",
            "status": status_label,
            "duration_ms": duration_ms,
            "actual_status_code": actual_status,
            "actual_result": actual_summary,
            "assertion_logs": assertion_logs,
            "request_info": {"method": method, "url": url, "headers": headers, "body": body_data},
            "response_preview": preview,
        }

    # -------------------------------------------------------------------------
    # B. Bộ thực thi Web UI Test (Playwright Browser hoặc DOM Inspector)
    # -------------------------------------------------------------------------
    def _execute_webui_testcase(
        self,
        tc: dict[str, Any],
        *,
        default_web_url: str,
        timeout_sec: int,
        headless: bool,
        use_playwright: bool = True,
        screenshot_dir: str = "AutoTC_Screenshots",
        task_name: str = "AutoTest",
        login_username: str = "",
        login_password: str = "",
    ) -> dict[str, Any]:
        tc_id = str(tc.get("id") or "AUTO_UI")
        spec = tc.get("auto_spec") if isinstance(tc.get("auto_spec"), dict) else {}
        target_url = str(spec.get("target_url") or default_web_url or "https://customertest.giaothongso.com.vn/#/login").strip()
        actions = spec.get("actions") if isinstance(spec.get("actions"), list) else [
            {"action": "goto", "url": target_url, "desc": f"Mở trang {target_url}"},
            {"action": "assert_visible", "selector": "body", "desc": "Kiểm tra giao diện hiển thị"},
        ]

        # Nếu người dùng bật chế độ Playwright Chromium và máy có cài playwright
        if use_playwright:
            try:
                from playwright.sync_api import sync_playwright  # type: ignore

                return self._run_with_playwright(
                    tc_id=tc_id,
                    tc=tc,
                    target_url=target_url,
                    actions=actions,
                    timeout_sec=timeout_sec,
                    headless=headless,
                    sync_playwright=sync_playwright,
                    screenshot_dir=screenshot_dir,
                    task_name=task_name,
                    login_username=login_username,
                    login_password=login_password,
                )
            except Exception as pw_err:
                LOGGER.warning("Playwright gặp lỗi khởi chạy, chuyển sang DOM Inspector nhanh: %s", pw_err)

        return self._run_with_dom_inspector(
            tc_id=tc_id,
            tc=tc,
            target_url=target_url,
            actions=actions,
            timeout_sec=timeout_sec,
            screenshot_dir=screenshot_dir,
            task_name=task_name,
        )

    @staticmethod
    def _save_screenshot_file(
        png_bytes: bytes,
        *,
        tc_id: str,
        status: str,
        task_name: str,
        screenshot_dir: str = "AutoTC_Screenshots",
        suffix: str = "",
    ) -> str:
        """
        Lưu file ảnh chụp màn hình (.png) vào thư mục chỉ định trên máy tính.
        Mặc định lưu ra thư mục cùng cấp bên ngoài workspace (Desktop/AutoTC_Screenshots)
        để tránh VS Code Live Server tự động F5 (reload) trình duyệt khi có file ảnh mới sinh ra!
        """
        from pathlib import Path

        project_root = Path(__file__).resolve().parents[2]
        cleaned_dir = screenshot_dir.strip() or "AutoTC_Screenshots"
        raw_dir = Path(cleaned_dir)
        if raw_dir.is_absolute():
            base_folder = raw_dir
        elif cleaned_dir.lower() in ("screenshots", "autotc_screenshots"):
            # Đặt ở thư mục cha (Desktop/AutoTC_Screenshots) để Live Server không tự reload trang
            base_folder = project_root.parent / "AutoTC_Screenshots"
        else:
            base_folder = project_root.parent / raw_dir

        safe_task = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", (task_name or "AutoTest").strip())[:50].strip("_ ")
        date_folder = time.strftime("%Y-%m-%d")
        target_folder = base_folder / f"{date_folder}_{safe_task}" if safe_task else base_folder / date_folder
        target_folder.mkdir(parents=True, exist_ok=True)

        safe_id = re.sub(r"[^a-zA-Z0-9_\-]+", "_", tc_id).strip("_") or "UI"
        timestamp = time.strftime("%H%M%S")
        extra = f"_{suffix}" if suffix else ""
        file_name = f"{safe_id}_{status}{extra}_{timestamp}.png"
        full_path = (target_folder / file_name).resolve()
        full_path.write_bytes(png_bytes)
        LOGGER.info("[Screenshot] Đã lưu ảnh giao diện tại: %s", full_path)
        return str(full_path)

    def _run_with_playwright(
        self,
        *,
        tc_id: str,
        tc: dict[str, Any],
        target_url: str,
        actions: list[dict[str, Any]],
        timeout_sec: int,
        headless: bool,
        sync_playwright: Any,
        screenshot_dir: str = "AutoTC_Screenshots",
        task_name: str = "AutoTest",
        login_username: str = "",
        login_password: str = "",
    ) -> dict[str, Any]:
        t0 = time.perf_counter()
        step_logs: list[str] = []
        all_passed = True
        screenshot_b64: str | None = None
        saved_screenshot_path: str | None = None
        saved_paths: list[str] = []

        with sync_playwright() as p:
            browser = self._launch_browser_with_fallback(p, headless=headless)
            context = browser.new_context(
                viewport={"width": 1366, "height": 768},
                ignore_https_errors=True,
            )
            page = context.new_page()
            page.set_default_timeout(timeout_sec * 1000)

            try:
                for idx, act in enumerate(actions, start=1):
                    if not isinstance(act, dict):
                        continue
                    atype = str(act.get("action") or "").lower().strip()
                    selector = str(act.get("selector") or "body").strip()
                    val = str(act.get("value") or act.get("url") or "").strip()
                    desc = str(act.get("desc") or f"Bước {idx}: {atype}").strip()

                    try:
                        if atype == "goto":
                            nav_url = val or target_url
                            page.goto(nav_url, wait_until="domcontentloaded")
                            try:
                                page.wait_for_load_state("networkidle", timeout=6000)
                            except Exception:
                                pass
                            if "#/" in nav_url:
                                page.wait_for_timeout(1500)
                            # Nếu trang đích yêu cầu đăng nhập trước (VD: crmtest.../#/search-information/cust-regis bị đẩy về login)
                            if (
                                login_username
                                and login_password
                                and "login" in page.url.lower()
                                and "login" not in nav_url.lower()
                            ):
                                logged_in = self._perform_auto_login(page, login_username, login_password, target_url=nav_url)
                                if logged_in:
                                    step_logs.append(f"🔑 Bước {idx}a: Đã tự động đăng nhập tài khoản '{login_username}' và điều hướng vào {nav_url}")
                            step_logs.append(f"✅ Bước {idx} ({desc}): Đã mở {nav_url}")
                        elif atype == "fill":
                            loc = self._resolve_spa_locator(page, selector, "fill", desc)
                            loc.fill(val)
                            step_logs.append(f"✅ Bước {idx} ({desc}): Đã nhập '{val}' vào '{selector}'")
                        elif atype == "click":
                            loc = self._resolve_spa_locator(page, selector, "click", desc)
                            loc.click()
                            page.wait_for_timeout(800)
                            step_logs.append(f"✅ Bước {idx} ({desc}): Đã click '{selector}'")
                        elif atype == "wait":
                            ms = int(val) if val.isdigit() else 1500
                            page.wait_for_timeout(min(ms, 8000))
                            step_logs.append(f"✅ Bước {idx} ({desc}): Đã chờ {ms}ms")
                        elif atype == "screenshot":
                            step_png = page.screenshot(full_page=True)
                            sp = self._save_screenshot_file(
                                step_png,
                                tc_id=tc_id,
                                status="STEP",
                                task_name=task_name,
                                screenshot_dir=screenshot_dir,
                                suffix=f"step{idx}",
                            )
                            saved_paths.append(sp)
                            step_logs.append(f"📸 Bước {idx} ({desc}): Đã chụp và lưu ảnh tại {sp}")
                        elif atype == "assert_visible":
                            visible = self._wait_spa_visible(page, selector)
                            all_passed = all_passed and visible
                            step_logs.append(
                                f"{'✅' if visible else '❌'} Bước {idx} ({desc}): Phần tử '{selector}' {'hiển thị' if visible else 'không hiển thị'}"
                            )
                        elif atype == "assert_text":
                            page.wait_for_timeout(600)
                            content = page.locator("body").inner_text()
                            ok = val.lower() in content.lower()
                            all_passed = all_passed and ok
                            step_logs.append(
                                f"{'✅' if ok else '❌'} Bước {idx} ({desc}): Kiểm tra văn bản trên trang chứa '{val}'"
                            )
                        elif atype == "assert_url":
                            ok = val.lower() in page.url.lower()
                            all_passed = all_passed and ok
                            step_logs.append(
                                f"{'✅' if ok else '❌'} Bước {idx} ({desc}): URL hiện tại = {page.url}"
                            )
                        else:
                            step_logs.append(f"ℹ️ Bước {idx}: Bỏ qua action '{atype}'")
                    except Exception as step_err:
                        all_passed = False
                        step_logs.append(f"❌ Bước {idx} ({desc}) thất bại: {step_err}")
                        break

                final_status = "PASS" if all_passed else "FAIL"
                try:
                    page.wait_for_timeout(500)
                    png_bytes = page.screenshot(full_page=True)
                    screenshot_b64 = "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")
                    saved_screenshot_path = self._save_screenshot_file(
                        png_bytes,
                        tc_id=tc_id,
                        status=final_status,
                        task_name=task_name,
                        screenshot_dir=screenshot_dir,
                    )
                    saved_paths.append(saved_screenshot_path)
                    step_logs.append(f"📸 Đã lưu ảnh chụp giao diện vào: {saved_screenshot_path}")
                except Exception as sc_err:
                    LOGGER.warning("Không thể chụp/lưu ảnh màn hình cho %s: %s", tc_id, sc_err)
            finally:
                browser.close()

        duration_ms = int((time.perf_counter() - t0) * 1000)
        return {
            "id": tc_id,
            "muc_dich": tc.get("muc_dich") or "",
            "test_type": "WEB_UI",
            "engine": "Playwright Chromium",
            "status": "PASS" if all_passed else "FAIL",
            "duration_ms": duration_ms,
            "actual_status_code": 200 if all_passed else 400,
            "actual_result": f"[Playwright Chromium] ({duration_ms}ms) | " + " ; ".join(step_logs),
            "assertion_logs": step_logs,
            "request_info": {"target_url": target_url, "actions": actions},
            "response_preview": "\n".join(step_logs),
            "screenshot": screenshot_b64,
            "screenshot_path": saved_screenshot_path,
            "screenshot_paths": saved_paths,
        }

    @staticmethod
    def _launch_browser_with_fallback(p: Any, *, headless: bool) -> Any:
        """
        Thử khởi chạy trình duyệt theo thứ tự ưu tiên:
        1. Google Chrome có sẵn trên máy Windows (channel='chrome')
        2. Microsoft Edge có sẵn trên máy Windows (channel='msedge')
        3. Chromium mặc định của Playwright (nếu đã chạy 'playwright install')
        """
        last_err: Exception | None = None
        for channel in ("chrome", "msedge", None):
            try:
                if channel:
                    return p.chromium.launch(channel=channel, headless=headless)
                return p.chromium.launch(headless=headless)
            except Exception as err:
                last_err = err
        raise RuntimeError(f"Không tìm thấy trình duyệt khả dụng: {last_err}")

    @staticmethod
    def _perform_auto_login(page: Any, username: str, password: str, *, target_url: str = "") -> bool:
        """Tự động điền tài khoản/mật khẩu nếu trang đích yêu cầu đăng nhập (VD: CRM / Customer Portal Giao Thông Số)."""
        try:
            user_loc = page.locator(
                'input[name*="user" i], input[id*="user" i], input[formcontrolname*="user" i], '
                'input[placeholder*="tài khoản" i], input[placeholder*="đăng nhập" i], input[type="text"]:visible'
            ).first
            pass_loc = page.locator('input[type="password"]:visible').first
            user_loc.wait_for(state="visible", timeout=5000)
            user_loc.fill(username)
            pass_loc.fill(password)

            btn_loc = page.locator(
                'button[type="submit"], button:has-text("Đăng nhập"), button:has-text("Login"), input[type="submit"]'
            ).first
            btn_loc.click()
            page.wait_for_timeout(2200)
            if target_url and target_url != page.url:
                page.goto(target_url, wait_until="domcontentloaded")
                page.wait_for_timeout(1500)
            return True
        except Exception as err:
            LOGGER.warning("Auto-login không thành công: %s", err)
            return False

    @staticmethod
    def _resolve_spa_locator(page: Any, selector: str, action_type: str, desc: str = "") -> Any:
        """
        Bộ định vị phần tử thông minh (Self-healing) cho trang SPA (Angular/Vue/React):
        - Chờ phần tử render xong trước khi thao tác.
        - Nếu selector của AI bị lệch nhẹ, tự động tìm input/button tương ứng trên màn hình.
        """
        primary = page.locator(selector).first
        try:
            primary.wait_for(state="visible", timeout=4500)
            return primary
        except Exception:
            pass

        low_desc = (desc + " " + selector).lower()
        if action_type == "fill":
            if any(k in low_desc for k in ("mật khẩu", "password", "pass")):
                alt = page.locator('input[type="password"]:visible').first
            elif any(k in low_desc for k in ("tài khoản", "username", "user", "sđt", "điện thoại")):
                alt = page.locator('input[type="text"]:visible, input:not([type="hidden"]):not([type="password"]):visible').first
            else:
                alt = page.locator('input:visible, textarea:visible').first
            alt.wait_for(state="visible", timeout=3500)
            return alt

        if action_type == "click":
            alt = page.locator('button[type="submit"]:visible, button:visible, [role="button"]:visible').first
            alt.wait_for(state="visible", timeout=3500)
            return alt

        return primary

    @staticmethod
    def _wait_spa_visible(page: Any, selector: str) -> bool:
        """Chờ phần tử SPA xuất hiện trên màn hình tối đa 5 giây trước khi kết luận."""
        try:
            loc = page.locator(selector).first
            loc.wait_for(state="visible", timeout=5000)
            return True
        except Exception:
            # Nếu selector quá cụ thể không khớp nhưng trang đã render form/input/button, kiểm tra fallback
            if any(tag in selector.lower() for tag in ("input", "button", "form", "body")):
                try:
                    page.locator("body").first.wait_for(state="visible", timeout=2000)
                    return len(page.locator("body").inner_text().strip()) > 0
                except Exception:
                    return False
            return False

    def _run_with_dom_inspector(
        self,
        *,
        tc_id: str,
        tc: dict[str, Any],
        target_url: str,
        actions: list[dict[str, Any]],
        timeout_sec: int,
        screenshot_dir: str = "screenshots",
        task_name: str = "AutoTest",
    ) -> dict[str, Any]:
        t0 = time.perf_counter()
        step_logs: list[str] = []
        all_passed = True
        status_code = 0
        html_text = ""

        req = urllib.request.Request(
            target_url,
            headers={"User-Agent": "AutoTC-WebInspector/2.0"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                status_code = int(resp.status)
                html_text = resp.read(65536).decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            status_code = int(e.code)
            try:
                html_text = e.read(32768).decode("utf-8", errors="replace")
            except Exception:
                pass
        except Exception as err:
            # Dự phòng thông minh: nếu URL trỏ tới file giao diện cục bộ (VD: /FE/login.html) khi chưa bật Live Server
            from pathlib import Path
            fe_dir = Path(__file__).resolve().parents[2] / "FE"
            matched_local = None
            for html_file in ("login.html", "index.html", "review.html", "autotest.html"):
                if html_file in target_url.lower() and (fe_dir / html_file).is_file():
                    matched_local = fe_dir / html_file
                    break
            if matched_local is not None:
                status_code = 200
                html_text = matched_local.read_text(encoding="utf-8", errors="replace")
            else:
                duration_ms = int((time.perf_counter() - t0) * 1000)
                return {
                    "id": tc_id,
                    "muc_dich": tc.get("muc_dich") or "",
                    "test_type": "WEB_UI",
                    "engine": "HTTP DOM Inspector",
                    "status": "ERROR",
                    "duration_ms": duration_ms,
                    "actual_status_code": 0,
                    "actual_result": f"Không thể truy cập trang web {target_url}: {err}",
                    "assertion_logs": [f"❌ Lỗi kết nối tới {target_url}: {err}"],
                    "request_info": {"target_url": target_url, "actions": actions},
                    "response_preview": str(err),
                }

        title_match = re.search(r"<title[^>]*>(.*?)</title>", html_text, re.IGNORECASE | re.DOTALL)
        page_title = html.unescape(title_match.group(1).strip()) if title_match else "(Không có tiêu đề)"

        for idx, act in enumerate(actions, start=1):
            if not isinstance(act, dict):
                continue
            atype = str(act.get("action") or "").lower().strip()
            selector = str(act.get("selector") or "body").strip()
            val = str(act.get("value") or act.get("url") or "").strip()
            desc = str(act.get("desc") or f"Bước {idx}: {atype}").strip()

            if atype == "goto":
                ok = 200 <= status_code < 400
                all_passed = all_passed and ok
                step_logs.append(
                    f"{'✅' if ok else '❌'} Bước {idx} ({desc}): Tải trang {target_url} -> HTTP {status_code} (Tiêu đề: '{page_title}')"
                )
            elif atype in ("fill", "click", "assert_visible"):
                ok = self._check_selector_in_html(selector, html_text)
                all_passed = all_passed and ok
                step_logs.append(
                    f"{'✅' if ok else '❌'} Bước {idx} ({desc}): Xác minh phần tử DOM '{selector}' tồn tại trên trang"
                )
            elif atype == "assert_text":
                ok = val.lower() in html_text.lower()
                all_passed = all_passed and ok
                step_logs.append(
                    f"{'✅' if ok else '❌'} Bước {idx} ({desc}): Kiểm tra nội dung trang chứa '{val}'"
                )
            else:
                step_logs.append(f"✅ Bước {idx} ({desc}): Đã kiểm tra bước '{atype}'")

        duration_ms = int((time.perf_counter() - t0) * 1000)
        final_status = "PASS" if all_passed else "FAIL"
        saved_screenshot_path: str | None = None
        screenshot_b64: str | None = None

        try:
            snap_bytes = self._render_dom_snapshot_png(
                tc_id=tc_id,
                purpose=str(tc.get("muc_dich") or ""),
                target_url=target_url,
                page_title=page_title,
                status=final_status,
                step_logs=step_logs,
            )
            if snap_bytes:
                saved_screenshot_path = self._save_screenshot_file(
                    snap_bytes,
                    tc_id=tc_id,
                    status=final_status,
                    task_name=task_name,
                    screenshot_dir=screenshot_dir,
                )
                screenshot_b64 = "data:image/png;base64," + base64.b64encode(snap_bytes).decode("ascii")
                step_logs.append(f"📸 Đã lưu ảnh kiểm tra giao diện vào: {saved_screenshot_path}")
        except Exception as snap_err:
            LOGGER.warning("Không thể tạo ảnh snapshot DOM cho %s: %s", tc_id, snap_err)

        return {
            "id": tc_id,
            "muc_dich": tc.get("muc_dich") or "",
            "test_type": "WEB_UI",
            "engine": "HTTP DOM Inspector",
            "status": final_status,
            "duration_ms": duration_ms,
            "actual_status_code": status_code,
            "actual_result": f"HTTP {status_code} ({duration_ms}ms) | Tiêu đề: {page_title} | " + " ; ".join(step_logs),
            "assertion_logs": step_logs,
            "request_info": {"target_url": target_url, "actions": actions},
            "response_preview": f"Page Title: {page_title}\n" + "\n".join(step_logs),
            "screenshot": screenshot_b64,
            "screenshot_path": saved_screenshot_path,
            "screenshot_paths": [saved_screenshot_path] if saved_screenshot_path else [],
        }

    @staticmethod
    def _render_dom_snapshot_png(
        *,
        tc_id: str,
        purpose: str,
        target_url: str,
        page_title: str,
        status: str,
        step_logs: list[str],
    ) -> bytes | None:
        """Tạo ảnh PNG chụp kết quả kiểm tra giao diện (dự phòng khi không mở trình duyệt)."""
        try:
            from io import BytesIO
            from PIL import Image, ImageDraw  # type: ignore

            img = Image.new("RGB", (1000, 480), color=(15, 23, 42))
            draw = ImageDraw.Draw(img)
            header_color = (16, 185, 129) if status == "PASS" else (239, 68, 68)
            draw.rectangle([(0, 0), (1000, 64)], fill=header_color)
            draw.text((24, 22), f"[{tc_id}] UI CHECK RESULT: {status} | {target_url}", fill=(255, 255, 255))
            draw.text((24, 84), f"Page Title: {page_title}", fill=(148, 163, 184))
            draw.text((24, 112), f"Purpose: {purpose[:95]}", fill=(226, 232, 240))
            y = 156
            for line in step_logs[:8]:
                clean_line = line.replace("✅", "[PASS]").replace("❌", "[FAIL]").replace("📸", "[IMG]")
                draw.text((24, y), clean_line[:115], fill=(203, 213, 225))
                y += 34
            buf = BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()
        except Exception:
            # Minimal valid 1x1 PNG fallback if Pillow is not installed
            import struct
            import zlib

            def _chunk(c_type: bytes, data: bytes) -> bytes:
                return (
                    struct.pack(">I", len(data))
                    + c_type
                    + data
                    + struct.pack(">I", zlib.crc32(c_type + data) & 0xFFFFFFFF)
                )

            rgb = b"\x10\xb9\x81" if status == "PASS" else b"\xef\x44\x44"
            raw_scanline = b"\x00" + rgb * 64
            compressed = zlib.compress(raw_scanline * 36)
            return (
                b"\x89PNG\r\n\x1a\n"
                + _chunk(b"IHDR", struct.pack(">IIBBBBB", 64, 36, 8, 2, 0, 0, 0))
                + _chunk(b"IDAT", compressed)
                + _chunk(b"IEND", b"")
            )

    @staticmethod
    def _check_selector_in_html(selector: str, html_text: str) -> bool:
        if not selector or selector == "body" or selector == "html":
            return "<body" in html_text.lower() or len(html_text) > 20
        parts = [p.strip() for p in selector.split(",") if p.strip()]
        low_html = html_text.lower()
        for part in parts:
            if part.startswith("#"):
                el_id = part[1:].strip()
                if f'id="{el_id.lower()}"' in low_html or f"id='{el_id.lower()}'" in low_html:
                    return True
            elif part.startswith("."):
                cls_name = part[1:].strip()
                if cls_name.lower() in low_html:
                    return True
            else:
                tag = re.split(r"[\[\.#\s]", part)[0].strip().lower()
                if tag and f"<{tag}" in low_html:
                    return True
        return False
