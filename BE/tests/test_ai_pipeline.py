from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from services.ai_pipeline_service import AiPipelineService
from services.json_parser import (
    parse_analysis_report,
    parse_loose,
    parse_requirements,
)
from services.memory_service import MemoryService
from services.scope_filter import filter_doc_by_user_scope


class TestJsonParser(unittest.TestCase):
    def test_parse_loose_handles_think_and_fences(self):
        raw = """<think>Đang suy nghĩ...</think>
```json
{
  "results": [
    {"condition_id": "F01_C001", "testcases": [{"muc_dich": "Kiểm tra A"}]},
  ]
}
```"""
        res = parse_loose(raw, "results")
        self.assertIsNotNone(res)
        self.assertFalse(res["salvaged"])
        self.assertEqual(len(res["data"]["results"]), 1)
        self.assertEqual(res["data"]["results"][0]["condition_id"], "F01_C001")

    def test_parse_loose_salvages_truncated_array(self):
        raw = '{"chunk_id": "F01", "conditions": [{"condition_id": "C1", "condition": "Hop le"}, {"condition_id": "C2", "condition": "Bi cat cut giua chung'
        res = parse_loose(raw, "conditions")
        self.assertIsNotNone(res)
        self.assertTrue(res["salvaged"])
        self.assertEqual(res["data"]["chunk_id"], "F01")
        self.assertEqual(len(res["data"]["conditions"]), 1)
        self.assertEqual(res["data"]["conditions"][0]["condition_id"], "C1")

    def test_parse_requirements_repairs_truncated_json(self):
        raw = '{"features": [{"feature_id": "P1-FEAT001", "feature_name": "Đăng nhập", "flow_order": 1}], "requirements": [{"requirement_id": "P1-REQ001", "feature_id": "P1-FEAT001", "requirement": "Kiểm tra OTP", "expected_behavior": "Thành công"}'
        res = parse_requirements(raw)
        self.assertIn("data", res)
        self.assertTrue(res["salvaged"])
        self.assertEqual(len(res["data"]["requirements"]), 1)

    def test_parse_analysis_report_handles_unescaped_quotes(self):
        raw = """{
  "muc_tieu_tai_lieu": "Kiểm tra nút "Lấy OTP" trên màn hình chính.",
  "he_thong_va_api": ["[POST] /api/otp - Gửi mã "OTP" cho khách hàng"]
}"""
        report = parse_analysis_report(raw)
        self.assertIn("1. TỔNG QUAN, MỤC TIÊU & PHẠM VI NGHIỆP VỤ", report)
        self.assertIn("2. KIẾN TRÚC TÍCH HỢP & ĐẶC TẢ GIAO TIẾP API", report)
        self.assertIn("/api/otp", report)


class TestAiPipelineLogic(unittest.TestCase):
    def test_split_by_feature_and_regression(self):
        structured = {
            "features": [
                {"feature_id": "FEAT001", "feature_name": "Gửi OTP", "flow_order": 1}
            ],
            "requirements": [
                {
                    "requirement_id": "REQ001",
                    "feature_id": "FEAT001",
                    "requirement": "Nhập số điện thoại nhận OTP",
                    "expected_behavior": "Gửi OTP thành công",
                    "related_fields": ["phone"],
                }
            ],
            "change_scope": {
                "changed": ["Luồng OTP mới"],
                "unchanged_but_impacted": ["Luồng đăng nhập cũ"],
            },
        }
        chunks = AiPipelineService._split_by_feature(structured)
        # Chỉ giữ chunk chức năng chính, không tự động sinh thêm chunk Hồi quy
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["suite_name"], "Gửi OTP")

    def test_group_by_test_suite_deduplicates_and_numbers(self):
        raw_rows = [
            {
                "test_suite": "Gửi OTP",
                "suite_order": 1,
                "muc_dich": "Kiểm tra gửi OTP thành công",
                "cac_buoc": "Step:\n1. Nhập SĐT",
                "ket_qua_mong_muon": "1. - Thành công",
                "ghi_chu": "[Nguồn: REQ001]",
            },
            # Trùng hệt dòng trên -> phải bị khử trùng
            {
                "test_suite": "Gửi OTP",
                "suite_order": 1,
                "muc_dich": "Kiểm tra   gửi OTP thành công ",
                "cac_buoc": "Step:\n1. Nhập SĐT",
                "ket_qua_mong_muon": "1. - Thành công",
                "ghi_chu": "[Nguồn: REQ001]",
            },
        ]
        grouped = AiPipelineService._group_by_test_suite(raw_rows, "TC")
        self.assertEqual(len(grouped), 2)  # 1 dòng suite + 1 dòng testcase
        self.assertEqual(grouped[0]["row_type"], "suite")
        self.assertEqual(grouped[1]["row_type"], "testcase")
        self.assertEqual(grouped[1]["id"], "")

    def test_memory_matching(self):
        chunks = [
            {
                "chunk_id": "F01",
                "suite_name": "Gửi OTP",
                "context": {"requirements": [{"requirement": "Kiểm tra mã OTP quá hạn 60 giây"}]},
            }
        ]
        approved = [
            {
                "problem_title": "Bài toán Đăng ký",
                "test_suite": "Gửi OTP",
                "content": {
                    "muc_dich": "Kiểm tra nhập mã OTP hết hạn sau 60 giây",
                    "ket_qua_mong_muon": "Hiển thị thông báo Mã OTP đã hết hạn",
                },
            }
        ]
        enriched = MemoryService.build_memory_text_for_chunks(chunks, approved)
        self.assertIn("Kiểm tra nhập mã OTP hết hạn", enriched[0]["memory_text"])

    def test_filter_doc_by_user_scope_isolates_requested_subsystem(self):
        doc = (
            "# GIỚI THIỆU\nTài liệu tổng quan.\n"
            "# THIẾT KẾ CHI TIẾT\n"
            "## PHÂN HỆ CRM\n" + ("Nội dung CRM chi tiết. " * 250) + "\n"
            "## PHÂN HỆ APP AGENCY\n"
            "### Xem tồn kho của trạm\n" + ("Nội dung App Agency tồn kho. " * 120) + "\n"
            "## PHÂN HỆ BÁO CÁO TẬP TRUNG\n" + ("Nội dung báo cáo 52. " * 120)
        )
        filtered = filter_doc_by_user_scope(
            "Hoa Hồng", doc, "Tôi chỉ yêu cầu phân tích phần app agency thôi"
        )
        self.assertIn("PHÂN HỆ APP AGENCY", filtered)
        self.assertIn("Xem tồn kho của trạm", filtered)
        self.assertNotIn("Nội dung CRM chi tiết", filtered)
        self.assertNotIn("Nội dung báo cáo 52", filtered)


if __name__ == "__main__":
    unittest.main()
