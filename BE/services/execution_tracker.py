from __future__ import annotations

from datetime import datetime, timezone
import threading
from typing import Any

from services.common import ApiError, _normalized, required_text


class ExecutionTracker:
    """Quản lý trạng thái các bài toán đang chạy (đồng hồ bấm giờ) trên toàn hệ thống."""

    def __init__(self):
        self._running_tasks: dict[str, dict[str, str]] = {}
        self._lock = threading.RLock()

    @staticmethod
    def is_terminal_status(status: Any) -> bool:
        """Kiểm tra trạng thái kết thúc (không còn chạy nữa)."""
        normalized = _normalized(status)
        return (
            normalized == _normalized("Đã xong")
            or "lỗi" in normalized
            or "thất bại" in normalized
            or "error" in normalized
        )

    def attach_executions(self, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Gắn thông tin execution vào danh sách bài toán và dọn dẹp các bài đã xong."""
        result = [dict(task) for task in tasks]
        active_names = {
            _normalized(task.get("Bài toán"))
            for task in result
            if not self.is_terminal_status(task.get("Trạng thái"))
        }

        with self._lock:
            # Loại bỏ các bài toán đã hoàn thành/lỗi khỏi bộ nhớ đang chạy
            self._running_tasks = {
                name: execution
                for name, execution in self._running_tasks.items()
                if name in active_names
            }
            for task in result:
                execution = self._running_tasks.get(_normalized(task.get("Bài toán")))
                if execution:
                    task["_execution"] = dict(execution)

        return result

    def start_executions(
        self, payload: dict[str, Any], existing_task_names: set[str]
    ) -> list[dict[str, str]]:
        """Bắt đầu tính giờ cho danh sách bài toán."""
        raw_names = payload.get("taskNames")
        if not isinstance(raw_names, list) or not raw_names:
            raise ApiError(400, "taskNames phải là danh sách bài toán không rỗng")

        request_id = required_text(payload, "requestId", 150)
        names = list(
            dict.fromkeys(required_text({"taskName": name}, "taskName") for name in raw_names)
        )

        missing = [name for name in names if _normalized(name) not in existing_task_names]
        if missing:
            raise ApiError(404, f'Không tìm thấy bài toán: {", ".join(missing)}')

        started_at = datetime.now(timezone.utc).isoformat()
        executions: list[dict[str, str]] = []

        with self._lock:
            already_running = [
                name for name in names if _normalized(name) in self._running_tasks
            ]
            if already_running:
                raise ApiError(409, f'Bài toán đang được xử lý: {", ".join(already_running)}')

            for name in names:
                key = _normalized(name)
                execution = {
                    "taskName": name,
                    "requestId": request_id,
                    "startedAt": started_at,
                }
                self._running_tasks[key] = execution
                executions.append(dict(execution))

        return executions

    def stop_executions(self, payload: dict[str, Any]) -> None:
        """Dừng tính giờ cho danh sách bài toán."""
        raw_names = payload.get("taskNames")
        if not isinstance(raw_names, list) or not raw_names:
            raise ApiError(400, "taskNames phải là danh sách bài toán không rỗng")

        request_id = required_text(payload, "requestId", 150)
        with self._lock:
            for name in raw_names:
                key = _normalized(name)
                execution = self._running_tasks.get(key)
                if execution and execution.get("requestId") == request_id:
                    self._running_tasks.pop(key, None)

    def clear_execution(self, task_name: str) -> None:
        """Xóa một bài toán khỏi danh sách đang chạy."""
        with self._lock:
            self._running_tasks.pop(_normalized(task_name), None)
