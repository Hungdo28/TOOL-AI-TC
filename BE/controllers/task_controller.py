from __future__ import annotations

from core.config import Settings
from web.models import ApiResponse
from middleware.auth import require_admin
from services.task_service import TaskService


class TaskController:
    def __init__(self, service: TaskService, settings: Settings):
        self.service = service
        self.settings = settings

    def list_tasks(self, _request) -> ApiResponse:
        return ApiResponse(200, self.service.list_tasks())

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

    def transfer_task(self, request) -> ApiResponse:
        require_admin(request, self.settings)
        task = self.service.transfer_task(request.read_json())
        return ApiResponse(200, {"success": True, "message": "Đã chuyển giao bài toán", "data": task})
