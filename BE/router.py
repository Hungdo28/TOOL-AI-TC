from __future__ import annotations

from collections.abc import Callable

from controllers.auth_controller import AuthController
from controllers.health_controller import get_health
from controllers.task_controller import TaskController
from services.task_service import ApiError
from web.models import ApiResponse


RouteHandler = Callable[[object], ApiResponse]


class Router:
    def __init__(self, task_controller: TaskController, auth_controller: AuthController | None = None):
        self.routes: dict[tuple[str, str], RouteHandler] = {
            ("GET", "/api/health"): get_health,
            ("GET", "/api/tasks"): task_controller.list_tasks,
            ("POST", "/api/tasks"): task_controller.create_task,
            ("PUT", "/api/tasks"): task_controller.edit_task,
            ("DELETE", "/api/tasks"): task_controller.delete_task,
            ("PATCH", "/api/tasks/status"): task_controller.update_status,
            ("POST", "/api/tasks/executions"): task_controller.start_executions,
            ("DELETE", "/api/tasks/executions"): task_controller.stop_executions,
            ("POST", "/api/tasks/stop"): task_controller.stop_executions,
            ("POST", "/api/tasks/executions/stop"): task_controller.stop_executions,
            ("PATCH", "/api/tasks/assignee"): task_controller.transfer_task,
            ("POST", "/api/tasks/ai-callback"): task_controller.ai_callback,
            ("POST", "/api/tasks/approve-testcases"): task_controller.approve_testcases,
            ("POST", "/api/tasks/run"): task_controller.run_ai,
            ("POST", "/webhook/luong-chuc-nang"): task_controller.run_ai,
            ("POST", "/api/autotest/generate"): task_controller.generate_autotest,
            ("POST", "/api/autotest/run"): task_controller.run_autotest,
            ("GET", "/api/local/files"): task_controller.list_local_files,
            ("POST", "/api/local/folders"): task_controller.create_local_folder,
            ("POST", "/api/local/records"): task_controller.save_local_record,
            ("GET", "/api/local/records"): task_controller.read_local_record,
            ("POST", "/api/local/open-folder"): task_controller.open_local_folder,
            ("POST", "/api/local/open-file"): task_controller.open_local_file,
            ("GET", "/api/local/download"): task_controller.download_local_file,
            ("GET", "/api/local/testcases"): task_controller.get_local_testcases,
            ("POST", "/api/local/push-drive"): task_controller.push_local_to_drive,
        }
        if auth_controller:
            self.routes[("POST", "/api/auth/token")] = auth_controller.get_token
            self.routes[("POST", "/api/auth/login")] = auth_controller.get_token

    def dispatch(self, method: str, request) -> ApiResponse:
        handler = self.routes.get((method.upper(), request.path))
        if not handler:
            raise ApiError(404, "API không tồn tại")
        return handler(request)
