from __future__ import annotations

from core.config import Settings
from middleware.auth import require_admin, require_callback_token, require_user, resolve_role
from services.task_service import ApiError, TaskService
from web.models import ApiResponse


class TaskController:
    def __init__(self, service: TaskService, settings: Settings):
        self.service = service
        self.settings = settings

    def list_tasks(self, request) -> ApiResponse:
        if not self.settings.enforce_role_header:
            return ApiResponse(200, self.service.list_tasks())

        username = require_user(request)
        _, role = resolve_role(request, self.settings)
        assignee = None if role == "admin" else username
        return ApiResponse(200, self.service.list_tasks(assignee))

    def create_task(self, request) -> ApiResponse:
        require_admin(request, self.settings)
        fields, files = request.read_form()
        task = self.service.add_task(fields, files)
        return ApiResponse(201, {"success": True, "message": "Đã thêm bài toán", "data": task})

    def edit_task(self, request) -> ApiResponse:
        require_admin(request, self.settings)
        task = self.service.edit_task(request.read_json())
        return ApiResponse(200, {"success": True, "message": "Đã cập nhật bài toán", "data": task})

    def delete_task(self, request) -> ApiResponse:
        require_admin(request, self.settings)
        self.service.delete_task(request.read_json())
        return ApiResponse(200, {"success": True, "message": "Đã xóa bài toán"})

    def update_status(self, request) -> ApiResponse:
        require_admin(request, self.settings)
        task = self.service.update_status(request.read_json())
        return ApiResponse(200, {"success": True, "message": "Đã cập nhật trạng thái", "data": task})

    def start_executions(self, request) -> ApiResponse:
        require_user(request)
        executions = self.service.start_executions(request.read_json())
        return ApiResponse(200, {"success": True, "data": executions})

    def stop_executions(self, request) -> ApiResponse:
        payload = dict(request.read_json() or {})
        self.service.stop_executions(payload)
        return ApiResponse(200, {"success": True, "message": "Đã dừng luồng xử lý thành công."})

    def transfer_task(self, request) -> ApiResponse:
        require_admin(request, self.settings)
        task = self.service.transfer_task(request.read_json())
        return ApiResponse(200, {"success": True, "message": "Đã chuyển giao bài toán", "data": task})

    def ai_callback(self, request) -> ApiResponse:
        require_callback_token(request, self.settings)
        task = self.service.handle_ai_callback(request.read_json())
        return ApiResponse(200, {"success": True, "message": "Đã cập nhật kết quả AI", "data": task})

    def approve_testcases(self, request) -> ApiResponse:
        require_user(request)
        payload = dict(request.read_json() or {})
        payload["status"] = payload.get("status") or "Đã xong"
        task = self.service.handle_ai_callback(payload)
        return ApiResponse(200, {"success": True, "message": "Đã duyệt và xuất Testcase vào Google Sheet", "data": task})

    def run_ai(self, request) -> ApiResponse:
        payload = dict(request.read_json() or {})
        result = self.service.run_ai_pipeline(payload)
        return ApiResponse(200, result)

    def generate_autotest(self, request) -> ApiResponse:
        payload = dict(request.read_json() or {})
        result = self.service.generate_autotest(payload)
        return ApiResponse(200, result)

    def run_autotest(self, request) -> ApiResponse:
        payload = dict(request.read_json() or {})
        result = self.service.run_autotest(payload)
        return ApiResponse(200, result)
