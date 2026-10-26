from __future__ import annotations

from collections.abc import Callable

from controllers.auth_controller import AuthController
from controllers.health_controller import get_health
from controllers.task_controller import TaskController
from web.models import ApiResponse
from services.task_service import ApiError


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
            ("PATCH", "/api/tasks/assignee"): task_controller.transfer_task,
            ("POST", "/api/tasks/ai-callback"): task_controller.ai_callback,
        }
        if auth_controller:
            self.routes[("POST", "/api/auth/token")] = auth_controller.get_token
            self.routes[("POST", "/api/auth/login")] = auth_controller.get_token


    def dispatch(self, method: str, request) -> ApiResponse:
        handler = self.routes.get((method.upper(), request.path))
        if not handler:
            raise ApiError(404, "API không tồn tại")
        return handler(request)

