from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from services.file_processing import prepare_workspace_file


ALLOWED_EXTENSIONS = {"doc", "docx", "xls", "xlsx", "pdf", "txt"}
ALLOWED_STATUSES = {"Chưa làm", "Waiting", "Đã xong"}


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

    def list_tasks(self) -> list[dict[str, Any]]:
        return self.workspace.list_tasks()

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
            return self.workspace.update_task(name, {"Trạng thái": status})
        except KeyError:
            raise ApiError(404, f'Không tìm thấy bài toán "{name}"') from None

    def transfer_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        name = required_text(payload, "baiToan")
        assignee = required_text(payload, "nguoiNhanMoi", 150)
        try:
            return self.workspace.update_task(name, {"Người làm": assignee})
        except KeyError:
            raise ApiError(404, f'Không tìm thấy bài toán "{name}"') from None
