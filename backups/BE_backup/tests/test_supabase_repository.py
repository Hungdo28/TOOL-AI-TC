import unittest
from unittest.mock import MagicMock, patch

from core.config import Settings
from repositories.supabase_repository import SupabaseRepository


class TestSupabaseRepository(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(
            host="127.0.0.1",
            port=3000,
            spreadsheet_id="",
            sheet_name="",
            sheet_id=0,
            header_row=1,
            credentials_file=None,
            credentials_json=None,
            drive_folder_id=None,
            drive_share_mode="private",
            allowed_origins=("*",),
            enforce_role_header=True,
            max_file_size=20 * 1024 * 1024,
            max_total_file_size=50 * 1024 * 1024,
            supabase_url="https://mock.supabase.co",
            supabase_anon_key="mock-key",
            supabase_service_role_key="mock-service-key",
            n8n_webhook_url="https://mock.n8n",
        )
        self.repo = SupabaseRepository(self.settings)

    def test_to_task_dict_mapping(self):
        raw_row = {
            "id": "1111-2222-3333",
            "legacy_id": 5,
            "title": "Bài toán đăng nhập",
            "source_url": "https://example.com/doc",
            "testcase_url": "https://example.com/sheet",
            "analysis_doc_url": "https://example.com/analysis",
            "status": "Chưa làm",
            "assignee": "hung",
        }
        task = self.repo._to_task_dict(raw_row)
        self.assertEqual(task["id"], "1111-2222-3333")
        self.assertEqual(task["legacy_id"], 5)
        self.assertEqual(task["ID"], 5)
        self.assertEqual(task["Bài toán"], "Bài toán đăng nhập")
        self.assertEqual(task["URL"], "https://example.com/doc")
        self.assertEqual(task["Link Testcase"], "https://example.com/sheet")
        self.assertEqual(task["Link tài liệu phân tích"], "https://example.com/analysis")
        self.assertEqual(task["Trạng thái"], "Chưa làm")
        self.assertEqual(task["Người làm"], "hung")
        self.assertEqual(task["row_number"], "1111-2222-3333")

    @patch.object(SupabaseRepository, "_request")
    def test_list_tasks(self, mock_request):
        mock_request.return_value = [
            {
                "id": "abc-123",
                "legacy_id": 1,
                "title": "Task A",
                "source_url": "https://a.com",
                "status": "Chưa làm",
            }
        ]
        tasks = self.repo.list_tasks()
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["Bài toán"], "Task A")
        self.assertEqual(tasks[0]["id"], "abc-123")

    @patch.object(SupabaseRepository, "_request")
    def test_find_task(self, mock_request):
        mock_request.return_value = [
            {
                "id": "abc-123",
                "legacy_id": 1,
                "title": "Task A",
                "source_url": "https://a.com",
                "status": "Chưa làm",
            }
        ]
        # Tìm theo tên
        self.assertIsNotNone(self.repo.find_task("task a"))
        # Tìm theo uuid
        self.assertIsNotNone(self.repo.find_task("abc-123"))
        # Không tìm thấy
        self.assertIsNone(self.repo.find_task("unknown"))


if __name__ == "__main__":
    unittest.main()
