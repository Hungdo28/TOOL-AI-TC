from __future__ import annotations

from typing import Any

from core.config import Settings
from services.ai_callback_service import AiCallbackService
from services.ai_pipeline_service import AiPipelineService
from services.autotest_service import AutoTestService
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


class TaskService:
    """Facade service tập hợp các nghiệp vụ quản lý bài toán, execution tracking và AI Pipeline."""

    def __init__(
        self,
        workspace: Any,
        max_file_size: int,
        max_total_file_size: int,
        settings: Settings | None = None,
    ):
        self.workspace = workspace
        self.max_file_size = max_file_size
        self.max_total_file_size = max_total_file_size
        self.settings = settings
        self.tracker = ExecutionTracker()
        self.pipeline = (
            AiPipelineService(workspace, settings, execution_tracker=self.tracker)
            if settings is not None
            else None
        )
        self.autotest = (
            AutoTestService(workspace, settings)
            if settings is not None
            else None
        )

    @property
    def _running_tasks(self) -> dict[str, dict[str, str]]:
        return self.tracker._running_tasks

    @property
    def _running_tasks_lock(self):
        return self.tracker._lock

    @staticmethod
    def _is_terminal_status(status: Any) -> bool:
        return ExecutionTracker.is_terminal_status(status)

    def list_tasks(self, assignee: str | None = None) -> list[dict[str, Any]]:
        raw_tasks = self.workspace.list_tasks()
        if assignee:
            wanted = _normalized(assignee)
            raw_tasks = [
                task
                for task in raw_tasks
                if _normalized(
                    task.get("Người làm") or task.get("Username") or task.get("Tài khoản")
                )
                == wanted
            ]
        return self.tracker.attach_executions(raw_tasks)

    def start_executions(self, payload: dict[str, Any]) -> list[dict[str, str]]:
        existing_names = {_normalized(task.get("Bài toán")) for task in self.workspace.list_tasks()}
        return self.tracker.start_executions(payload, existing_names)

    def stop_executions(self, payload: dict[str, Any]) -> None:
        raw_names = payload.get("taskNames")
        if not raw_names and payload.get("taskName"):
            raw_names = [payload["taskName"]]
        elif not raw_names and payload.get("baiToan"):
            raw_names = [payload["baiToan"]]

        if not isinstance(raw_names, list) or not raw_names:
            raise ApiError(400, "taskNames phải là danh sách bài toán không rỗng")

        names = [str(n).strip() for n in raw_names if str(n).strip()]

        # 1. Dừng tính giờ trên execution tracker
        try:
            self.tracker.stop_executions(payload)
        except Exception:
            for name in names:
                self.tracker.clear_execution(name)

        # 2. Hủy luồng trong AI Pipeline nếu đang chạy
        if self.pipeline:
            for name in names:
                self.pipeline.cancel_task(name)

        # 3. Đưa trạng thái bài toán về 'Chưa làm' nếu đang ở Waiting
        for name in names:
            try:
                task = self.workspace.find_task(name)
                if task:
                    task_id = str(task.get("id") or task.get("problem_id") or name)
                    curr_status = str(task.get("Trạng thái") or "")
                    if curr_status.lower() in ("waiting", "đang chạy", "đang xử lý", "đang xử lý ai..."):
                        self.workspace.update_task(task_id, {"Trạng thái": "Chưa làm"})
            except Exception:
                pass

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

    def run_ai_pipeline(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.pipeline:
            raise ApiError(500, "AI Pipeline chưa được khởi tạo trên Backend.")
        return self.pipeline.run_From_payload(payload)

    def generate_autotest(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.autotest:
            raise ApiError(500, "AutoTest Service chưa được khởi tạo trên Backend.")
        return self.autotest.generate_autotest_cases(payload)

    def run_autotest(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.autotest:
            raise ApiError(500, "AutoTest Service chưa được khởi tạo trên Backend.")
        return self.autotest.run_autotest_suite(payload)
