from __future__ import annotations

from typing import Any

from services.common import (
    ALLOWED_EXTENSIONS,
    ALLOWED_STATUSES,
    ApiError,
    UploadedFile,
    _normalized,
    required_text,
    validate_urls,
)
from services.execution_tracker import ExecutionTracker
from services.task_crud_service import TaskCrudService
from services.ai_callback_service import AiCallbackService


class TaskService:
    """Facade service tập hợp các nghiệp vụ quản lý bài toán và execution tracking."""

    def __init__(self, workspace: Any, max_file_size: int, max_total_file_size: int):
        self.workspace = workspace
        self.max_file_size = max_file_size
        self.max_total_file_size = max_total_file_size
        self.tracker = ExecutionTracker()

    @property
    def _running_tasks(self) -> dict[str, dict[str, str]]:
        return self.tracker._running_tasks

    @property
    def _running_tasks_lock(self):
        return self.tracker._lock

    @staticmethod
    def _is_terminal_status(status: Any) -> bool:
        return ExecutionTracker.is_terminal_status(status)

    def list_tasks(self) -> list[dict[str, Any]]:
        raw_tasks = self.workspace.list_tasks()
        return self.tracker.attach_executions(raw_tasks)

    def start_executions(self, payload: dict[str, Any]) -> list[dict[str, str]]:
        existing_names = {_normalized(task.get("Bài toán")) for task in self.workspace.list_tasks()}
        return self.tracker.start_executions(payload, existing_names)

    def stop_executions(self, payload: dict[str, Any]) -> None:
        self.tracker.stop_executions(payload)

    def add_task(self, payload: dict[str, Any], files: list[UploadedFile]) -> dict[str, Any]:
        return TaskCrudService.add_task(
            self.workspace,
            payload,
            files,
            self.max_file_size,
            self.max_total_file_size,
        )

    def edit_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        return TaskCrudService.edit_task(self.workspace, payload)

    def delete_task(self, payload: dict[str, Any]) -> None:
        TaskCrudService.delete_task(self.workspace, payload)

    def update_status(self, payload: dict[str, Any]) -> dict[str, Any]:
        task = TaskCrudService.update_status(self.workspace, payload)
        status = task.get("Trạng thái", "")
        if self._is_terminal_status(status):
            name = task.get("Bài toán", "")
            self.tracker.clear_execution(name)
        return task

    def transfer_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        return TaskCrudService.transfer_task(self.workspace, payload)

    def handle_ai_callback(self, payload: dict[str, Any]) -> dict[str, Any]:
        return AiCallbackService.handle_ai_callback(
            self.workspace,
            payload,
            execution_tracker=self.tracker,
        )
