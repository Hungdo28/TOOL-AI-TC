from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from core.config import Settings
from services.autotest_service import AutoTestService


class _FakeHttpResponse:
    def __init__(self, status: int, body: bytes):
        self.status = status
        self._body = body

    def read(self, amt: int | None = None) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


class TestAutoTestService(unittest.TestCase):
    def _make_service(self) -> AutoTestService:
        settings = Settings(
            host="127.0.0.1",
            port=8088,
            spreadsheet_id="",
            sheet_name="Sheet1",
            sheet_id=0,
            header_row=1,
            credentials_file=None,
            credentials_json=None,
            drive_folder_id=None,
            drive_share_mode="private",
            allowed_origins=("*",),
            enforce_role_header=False,
            max_file_size=1024,
            max_total_file_size=2048,
            ai_api_key="",  # Force fallback conversion/sample mode without external network call
        )
        workspace = MagicMock()
        workspace.find_task.return_value = None
        return AutoTestService(workspace, settings)

    def test_generate_converts_manual_testcases_to_autotest(self):
        svc = self._make_service()
        res = svc.generate_autotest_cases({
            "taskName": "Bài toán OTP",
            "testMode": "both",
            "baseUrl": "http://127.0.0.1:8088",
            "webUrl": "http://127.0.0.1:5500/FE/login.html",
            "manualTestcases": [
                {
                    "id": "TC_01",
                    "test_suite": "Gửi OTP",
                    "muc_dich": "Kiểm tra gọi API /api/health thành công",
                    "cac_buoc": "1. Gửi GET /api/health",
                    "ket_qua_mong_muon": "HTTP 200 OK",
                },
                {
                    "id": "TC_02",
                    "test_suite": "Màn hình Login",
                    "muc_dich": "Kiểm tra hiển thị màn hình đăng nhập",
                    "cac_buoc": "1. Mở màn hình đăng nhập",
                    "ket_qua_mong_muon": "Hiển thị ô nhập tài khoản",
                },
            ],
        })
        self.assertTrue(res["success"])
        self.assertEqual(res["count"], 2)
        self.assertEqual(res["testcases"][0]["test_type"], "API")
        self.assertEqual(res["testcases"][1]["test_type"], "WEB_UI")

    @patch("urllib.request.urlopen")
    def test_run_autotest_suite_executes_api_and_webui(self, mock_urlopen):
        def fake_open(req, timeout=15):
            url = req.full_url if hasattr(req, "full_url") else str(req)
            if "/api/health" in url:
                return _FakeHttpResponse(200, b'{"status": "ok"}')
            return _FakeHttpResponse(
                200,
                b"<html><head><title>Login Page</title></head>"
                b"<body><input id=\"username\"/><button type=\"submit\">Login</button></body></html>",
            )

        mock_urlopen.side_effect = fake_open
        svc = self._make_service()
        from pathlib import Path
        test_shot_dir = str((Path(__file__).resolve().parent / "_tmp_screenshots").resolve())
        suite_res = svc.run_autotest_suite({
            "taskName": "Test_UI_Screenshot",
            "envConfig": {
                "baseUrl": "http://127.0.0.1:8088",
                "webUrl": "http://127.0.0.1:5500/FE/login.html",
                "timeoutSec": 5,
                "usePlaywright": False,
                "headless": True,
                "screenshotDir": test_shot_dir,
            },
            "testcases": [
                {
                    "id": "AUTO_001",
                    "muc_dich": "Kiểm tra API /api/health",
                    "test_type": "API",
                    "auto_spec": {
                        "method": "GET",
                        "endpoint": "/api/health",
                        "expected_status": 200,
                        "assertions": [
                            {"type": "status_code", "expected": 200},
                            {"type": "json_equals", "key": "status", "expected": "ok"},
                        ],
                    },
                },
                {
                    "id": "AUTO_002",
                    "muc_dich": "Kiểm tra giao diện trang Login",
                    "test_type": "WEB_UI",
                    "auto_spec": {
                        "target_url": "http://127.0.0.1:5500/FE/login.html",
                        "actions": [
                            {"action": "goto", "url": "http://127.0.0.1:5500/FE/login.html", "desc": "Mở trang"},
                            {"action": "assert_visible", "selector": "#username", "desc": "Kiểm tra ô username"},
                            {"action": "assert_text", "selector": "button", "value": "Login", "desc": "Kiểm tra chữ Login"},
                        ],
                    },
                },
            ],
        })
        self.assertTrue(suite_res["success"])
        self.assertEqual(suite_res["summary"]["total"], 2)
        self.assertEqual(suite_res["summary"]["passed"], 2)
        self.assertEqual(suite_res["summary"]["failed"], 0)
        self.assertEqual(suite_res["summary"]["pass_rate"], 100.0)
        ui_res = suite_res["results"][1]
        self.assertTrue(ui_res.get("screenshot_path"))
        from pathlib import Path
        import shutil
        self.assertTrue(Path(ui_res["screenshot_path"]).is_file())
        shutil.rmtree(test_shot_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
