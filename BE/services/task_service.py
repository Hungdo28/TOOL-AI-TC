from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import threading
from typing import Any
from urllib.parse import urlparse

from services.file_processing import prepare_workspace_file


ALLOWED_EXTENSIONS = {"doc", "docx", "xls", "xlsx", "pdf", "txt"}
ALLOWED_STATUSES = {"Chưa làm", "Waiting", "Đã xong"}


def _normalized(value: Any) -> str:
    return str(value or "").strip().casefold()


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


@dataclass(frozen=True)
class UploadedFile:
    filename: str
    content_type: str
    content: bytes


def required_text(payload: dict[str, Any], key: str, max_length: int = 300) -> str:
    value = str(payload.get(key, "")).strip()
    if not value:
        raise ApiError(400, f"Thiếu trường bắt buộc: {key}")
    if len(value) > max_length:
        raise ApiError(400, f"{key} dài quá {max_length} ký tự")
    return value


def validate_urls(raw_urls: str, require_one: bool = True) -> str:
    urls = [value.strip() for value in raw_urls.replace(",", "\n").splitlines() if value.strip()]
    if not urls and require_one:
        raise ApiError(400, "Cần ít nhất một URL tài liệu")
    for url in urls:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ApiError(400, f"URL không hợp lệ: {url}")
    return "\n".join(urls)


class TaskService:
    def __init__(self, workspace, max_file_size: int, max_total_file_size: int):
        self.workspace = workspace
        self.max_file_size = max_file_size
        self.max_total_file_size = max_total_file_size
        # Nguồn trạng thái dùng chung cho mọi phiên frontend đang kết nối backend.
        self._running_tasks: dict[str, dict[str, str]] = {}
        self._running_tasks_lock = threading.RLock()

    def list_tasks(self) -> list[dict[str, Any]]:
        # Không làm thay đổi object do repository trả về khi gắn metadata tạm thời.
        tasks = [dict(task) for task in self.workspace.list_tasks()]
        active_names = {
            _normalized(task.get("Bài toán"))
            for task in tasks
            if not self._is_terminal_status(task.get("Trạng thái"))
        }
        with self._running_tasks_lock:
            # n8n cập nhật trạng thái hoàn thành/lỗi trong Sheet; khi đó không phát
            # execution cũ nữa để tất cả tài khoản dừng đồng hồ đồng thời.
            self._running_tasks = {
                name: execution
                for name, execution in self._running_tasks.items()
                if name in active_names
            }
            for task in tasks:
                execution = self._running_tasks.get(_normalized(task.get("Bài toán")))
                if execution:
                    task["_execution"] = dict(execution)
        return tasks

    @staticmethod
    def _is_terminal_status(status: Any) -> bool:
        normalized = _normalized(status)
        return (
            normalized == _normalized("Đã xong")
            or "lỗi" in normalized
            or "thất bại" in normalized
            or "error" in normalized
        )

    def start_executions(self, payload: dict[str, Any]) -> list[dict[str, str]]:
        raw_names = payload.get("taskNames")
        if not isinstance(raw_names, list) or not raw_names:
            raise ApiError(400, "taskNames phải là danh sách bài toán không rỗng")
        request_id = required_text(payload, "requestId", 150)
        names = list(dict.fromkeys(required_text({"taskName": name}, "taskName") for name in raw_names))

        existing_tasks = {_normalized(task.get("Bài toán")) for task in self.workspace.list_tasks()}
        missing = [name for name in names if _normalized(name) not in existing_tasks]
        if missing:
            raise ApiError(404, f'Không tìm thấy bài toán: {", ".join(missing)}')

        started_at = datetime.now(timezone.utc).isoformat()
        executions: list[dict[str, str]] = []
        with self._running_tasks_lock:
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
        raw_names = payload.get("taskNames")
        if not isinstance(raw_names, list) or not raw_names:
            raise ApiError(400, "taskNames phải là danh sách bài toán không rỗng")
        request_id = required_text(payload, "requestId", 150)
        with self._running_tasks_lock:
            for name in raw_names:
                key = _normalized(name)
                execution = self._running_tasks.get(key)
                # Không xóa lượt chạy mới hơn nếu một phản hồi cũ về muộn.
                if execution and execution["requestId"] == request_id:
                    self._running_tasks.pop(key, None)

    def add_task(self, payload: dict[str, Any], files: list[UploadedFile]) -> dict[str, Any]:
        name = required_text(payload, "baiToan")
        if self.workspace.find_task(name):
            raise ApiError(409, f'Bài toán "{name}" đã tồn tại')

        mode = str(payload.get("mode", "manual")).strip().lower()
        if mode == "manual":
            url_value = validate_urls(str(payload.get("urlGoc", "")))
        elif mode == "import":
            if not files:
                raise ApiError(400, "Chưa chọn file để import")
            if sum(len(file.content) for file in files) > self.max_total_file_size:
                raise ApiError(413, "Tổng dung lượng file vượt quá giới hạn")

            for file in files:
                extension = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
                if extension not in ALLOWED_EXTENSIONS:
                    raise ApiError(400, f"Không hỗ trợ định dạng file: {file.filename}")
                if len(file.content) > self.max_file_size:
                    raise ApiError(413, f"File vượt quá giới hạn: {file.filename}")

            urls = []
            for file in files:
                try:
                    workspace_file = prepare_workspace_file(
                        file.filename, file.content_type, file.content
                    )
                    urls.append(
                        self.workspace.upload_file(
                            workspace_file.title,
                            workspace_file.source_mime_type,
                            workspace_file.content,
                            workspace_file.target_mime_type,
                        )
                    )
                except Exception as error:
                    error_text = str(error)
                    if "storageQuotaExceeded" in error_text or "do not have storage quota" in error_text:
                        raise ApiError(
                            503,
                            "Service account không có dung lượng Google Drive. "
                            "Hãy chạy setup_google_oauth.py và khởi động lại backend.",
                        ) from None
                    raise ApiError(
                        502, f'Không thể upload file "{file.filename}" lên Google Drive'
                    ) from None
            url_value = "\n".join(urls)
        else:
            raise ApiError(400, "mode chỉ nhận manual hoặc import")

        task = {
            "Bài toán": name,
            "URL": url_value,
            "Trạng thái": "Chưa làm",
            "Người làm": str(payload.get("username", "")).strip(),
        }
        self.workspace.append_task(task)
        return task

    def edit_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        old_name = required_text(payload, "oldBaiToan")
        new_name = required_text(payload, "newBaiToan")
        new_url = validate_urls(str(payload.get("newUrl", "")), require_one=False)
        duplicate = self.workspace.find_task(new_name)
        if duplicate and new_name.casefold() != old_name.casefold():
            raise ApiError(409, f'Bài toán "{new_name}" đã tồn tại')
        try:
            return self.workspace.update_task(
                old_name, {"Bài toán": new_name, "URL": new_url}
            )
        except KeyError:
            raise ApiError(404, f'Không tìm thấy bài toán "{old_name}"') from None

    def delete_task(self, payload: dict[str, Any]) -> None:
        name = required_text(payload, "baiToan")
        try:
            self.workspace.delete_task(name)
        except KeyError:
            raise ApiError(404, f'Không tìm thấy bài toán "{name}"') from None

    def update_status(self, payload: dict[str, Any]) -> dict[str, Any]:
        name = required_text(payload, "baiToan")
        status = required_text(payload, "trangThai", 100)
        if status not in ALLOWED_STATUSES:
            raise ApiError(400, "Trạng thái không hợp lệ")
        try:
            task = self.workspace.update_task(name, {"Trạng thái": status})
            if self._is_terminal_status(status):
                with self._running_tasks_lock:
                    self._running_tasks.pop(_normalized(name), None)
            return task
        except KeyError:
            raise ApiError(404, f'Không tìm thấy bài toán "{name}"') from None

    def transfer_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        name = required_text(payload, "baiToan")
        assignee = required_text(payload, "nguoiNhanMoi", 150)
        try:
            return self.workspace.update_task(name, {"Người làm": assignee})
        except KeyError:
            raise ApiError(404, f'Không tìm thấy bài toán "{name}"') from None
