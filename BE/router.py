from __future__ import annotations

import re
from collections.abc import Callable

from controllers.health_controller import get_health
from controllers.task_controller import TaskController
from controllers.job_controller import JobController
from web.models import ApiResponse
from services.task_service import ApiError


RouteHandler = Callable[[object], ApiResponse]


def _path_pattern_to_regex(pattern: str) -> tuple[re.Pattern, list[str]]:
    """Chuyển pattern '/api/jobs/:id/status' thành regex và danh sách tên tham số."""
    param_names: list[str] = []

    def replace_param(match: re.Match) -> str:
        param_names.append(match.group(1))
        return r"([^/]+)"

    regex_str = re.sub(r":([a-zA-Z_][a-zA-Z0-9_]*)", replace_param, re.escape(pattern))
    # re.escape biến '/' thành '\\/', cần bỏ escape đó lại
    regex_str = regex_str.replace("\\/", "/")
    return re.compile(f"^{regex_str}$"), param_names


class Router:
    def __init__(self, task_controller: TaskController, job_controller: JobController):
        # --- Routes cố định (exact match) ---
        self._exact_routes: dict[tuple[str, str], RouteHandler] = {
            ("GET",    "/api/health"):              get_health,
            ("GET",    "/api/tasks"):               task_controller.list_tasks,
            ("POST",   "/api/tasks"):               task_controller.create_task,
            ("PUT",    "/api/tasks"):               task_controller.edit_task,
            ("DELETE", "/api/tasks"):               task_controller.delete_task,
            ("PATCH",  "/api/tasks/status"):        task_controller.update_status,
            ("POST",   "/api/tasks/executions"):    task_controller.start_executions,
            ("DELETE", "/api/tasks/executions"):    task_controller.stop_executions,
            ("PATCH",  "/api/tasks/assignee"):      task_controller.transfer_task,
            # --- Hàng đợi AI (Queue) ---
            ("POST",   "/api/jobs"):                job_controller.enqueue_jobs,
            ("GET",    "/api/jobs/status"):         job_controller.get_jobs_status,
            ("GET",    "/api/jobs/next"):            job_controller.get_next_job,
        }

        # --- Routes động (có path params) ---
        self._dynamic_routes: list[
            tuple[str, re.Pattern, list[str], RouteHandler]
        ] = [
            (
                "PATCH",
                *_path_pattern_to_regex("/api/jobs/:id/status"),
                job_controller.update_job_status,
            ),
        ]

    def dispatch(self, method: str, request) -> ApiResponse:
        method_upper = method.upper()
        path = request.path

        # 1. Thử exact match trước (nhanh hơn)
        handler = self._exact_routes.get((method_upper, path))
        if handler:
            return handler(request)

        # 2. Thử dynamic match
        for route_method, pattern, param_names, dyn_handler in self._dynamic_routes:
            if route_method != method_upper:
                continue
            match = pattern.match(path)
            if match:
                request.path_params = dict(zip(param_names, match.groups()))
                return dyn_handler(request)

        raise ApiError(404, "API khong ton tai")

