import unittest

from services.task_service import ApiError, TaskService, UploadedFile, validate_urls


class FakeWorkspace:
    def __init__(self):
        self.tasks = []
        self.uploads = []

    def list_tasks(self):
        return list(self.tasks)

    def find_task(self, name):
        return next((task for task in self.tasks if task["Bài toán"].casefold() == name.casefold()), None)

    def append_task(self, task):
        self.tasks.append(dict(task))

    def update_task(self, name, changes):
        task = self.find_task(name)
        if not task:
            raise KeyError(name)
        task.update(changes)
        return task

    def delete_task(self, name):
        task = self.find_task(name)
        if not task:
            raise KeyError(name)
        self.tasks.remove(task)

    def upload_file(self, filename, content_type, content, target_mime_type):
        self.uploads.append(filename)
        return f"https://drive.example/{filename}"


class TaskServiceTests(unittest.TestCase):
    def setUp(self):
        self.workspace = FakeWorkspace()
        self.service = TaskService(self.workspace, 10, 20)

    def test_manual_crud_and_transfer(self):
        self.service.add_task(
            {
                "baiToan": "Đăng nhập",
                "mode": "manual",
                "urlGoc": "https://example.com/spec",
                "username": "tester",
            },
            [],
        )
        self.service.edit_task(
            {
                "oldBaiToan": "Đăng nhập",
                "newBaiToan": "Đăng nhập SSO",
                "newUrl": "https://example.com/sso",
            }
        )
        self.service.update_status({"baiToan": "Đăng nhập SSO", "trangThai": "Đã xong"})
        result = self.service.transfer_task(
            {"baiToan": "Đăng nhập SSO", "nguoiNhanMoi": "qa02"}
        )
        self.assertEqual(result["Người làm"], "qa02")
        self.assertEqual(result["Trạng thái"], "Đã xong")
        self.service.delete_task({"baiToan": "Đăng nhập SSO"})
        self.assertEqual(self.service.list_tasks(), [])

    def test_import_uploads_supported_file(self):
        file = UploadedFile("spec.pdf", "application/pdf", b"123")
        task = self.service.add_task(
            {"baiToan": "Thanh toán", "mode": "import", "username": "qa01"},
            [file],
        )
        self.assertEqual(task["URL"], "https://drive.example/spec")

    def test_rejects_duplicate_and_bad_url(self):
        payload = {"baiToan": "A", "mode": "manual", "urlGoc": "https://example.com"}
        self.service.add_task(payload, [])
        with self.assertRaises(ApiError) as duplicate:
            self.service.add_task(payload, [])
        self.assertEqual(duplicate.exception.status, 409)
        with self.assertRaises(ApiError):
            validate_urls("javascript:alert(1)")

    def test_running_execution_is_returned_to_every_client_and_stops_when_done(self):
        self.workspace.append_task({"Bài toán": "Đăng nhập", "Trạng thái": "Chưa làm"})
        execution = self.service.start_executions(
            {"taskNames": ["Đăng nhập"], "requestId": "request-1"}
        )[0]
        self.assertEqual(execution["requestId"], "request-1")
        self.assertIn("_execution", self.service.list_tasks()[0])

        self.service.update_status({"baiToan": "Đăng nhập", "trangThai": "Đã xong"})
        self.assertNotIn("_execution", self.service.list_tasks()[0])

    def test_invalid_import_does_not_upload_partial_files(self):
        files = [
            UploadedFile("valid.pdf", "application/pdf", b"123"),
            UploadedFile("blocked.exe", "application/octet-stream", b"456"),
        ]
        with self.assertRaises(ApiError):
            self.service.add_task(
                {"baiToan": "Import lỗi", "mode": "import"}, files
            )
        self.assertEqual(self.workspace.uploads, [])

    def test_drive_quota_error_has_actionable_message(self):
        def fail_upload(*_args):
            raise RuntimeError("storageQuotaExceeded: Service Accounts do not have storage quota")

        self.workspace.upload_file = fail_upload
        with self.assertRaises(ApiError) as error:
            self.service.add_task(
                {"baiToan": "Import OAuth", "mode": "import"},
                [UploadedFile("spec.pdf", "application/pdf", b"123")],
            )
        self.assertEqual(error.exception.status, 503)
        self.assertIn("setup_google_oauth.py", error.exception.message)


if __name__ == "__main__":
    unittest.main()
