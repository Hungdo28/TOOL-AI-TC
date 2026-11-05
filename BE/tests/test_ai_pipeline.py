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
        self.assertIn("1. MỤC TIÊU TÀI LIỆU", report)
        self.assertIn("2. CÁC HỆ THỐNG VÀ API", report)
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
        # 1 chunk cho FEAT001 + 1 chunk tự động sinh cho Hồi quy
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[0]["suite_name"], "Gửi OTP")
        self.assertIn("Hồi quy", chunks[1]["suite_name"])

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
        self.assertEqual(grouped[1]["id"], "[TC]_1")

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


if __name__ == "__main__":
    unittest.main()
