import unittest
from types import SimpleNamespace

from controllers.task_controller import TaskController
from router import Router
from services.task_service import ApiError


class FakeService:
    def list_tasks(self):
        return [{"Bài toán": "Đăng nhập"}]

    def update_status(self, payload):
        return {"Bài toán": payload["baiToan"], "Trạng thái": payload["trangThai"]}

    def start_executions(self, payload):
        return [{"taskName": payload["taskNames"][0], "requestId": payload["requestId"]}]


class FakeRequest:
    def __init__(self, path, payload=None, role="admin", username=""):
        self.path = path
        self.payload = payload or {}
        self.headers = {"X-User-Role": role, "X-User-Name": username}

    def read_json(self):
        return self.payload


class RouterTests(unittest.TestCase):
    def setUp(self):
        settings = SimpleNamespace(enforce_role_header=True)
        self.router = Router(TaskController(FakeService(), settings))

    def test_routes_list_tasks(self):
        response = self.router.dispatch("GET", FakeRequest("/api/tasks", role="viewer"))
        self.assertEqual(response.status, 200)
        self.assertEqual(response.body[0]["Bài toán"], "Đăng nhập")

    def test_routes_status_update(self):
        request = FakeRequest(
            "/api/tasks/status",
            {"baiToan": "Đăng nhập", "trangThai": "Đã xong"},
        )
        response = self.router.dispatch("PATCH", request)
        self.assertEqual(response.status, 200)
        self.assertEqual(response.body["data"]["Trạng thái"], "Đã xong")

    def test_routes_start_execution(self):
        request = FakeRequest(
            "/api/tasks/executions", {"taskNames": ["Đăng nhập"], "requestId": "run-1"}
        )
        response = self.router.dispatch("POST", request)
        self.assertEqual(response.status, 200)
        self.assertEqual(response.body["data"][0]["requestId"], "run-1")

    def test_rejects_viewer_mutation(self):
        request = FakeRequest("/api/tasks/status", role="viewer")
        with self.assertRaises(ApiError) as error:
            self.router.dispatch("PATCH", request)
        self.assertEqual(error.exception.status, 403)

    def test_rejects_faked_admin_with_supabase_check(self):
        from unittest.mock import patch
        settings = SimpleNamespace(
            enforce_role_header=True,
            supabase_url="https://mock.supabase.co",
            supabase_anon_key="mock-key"
        )
        router = Router(TaskController(FakeService(), settings))

        # Giả lập người dùng F12 sửa role='admin' nhưng DB lưu là 'user'
        fake_req = FakeRequest("/api/tasks/status", {"baiToan": "T"}, role="admin", username="fake_admin")
        with patch("middleware.auth.fetch_role_from_supabase", return_value="user"):
            with self.assertRaises(ApiError) as error:
                router.dispatch("PATCH", fake_req)
            self.assertEqual(error.exception.status, 403)
            self.assertIn("không có quyền Admin", error.exception.message)

    def test_unknown_route_returns_not_found(self):
        with self.assertRaises(ApiError) as error:
            self.router.dispatch("GET", FakeRequest("/api/not-found"))
        self.assertEqual(error.exception.status, 404)


if __name__ == "__main__":
    unittest.main()
