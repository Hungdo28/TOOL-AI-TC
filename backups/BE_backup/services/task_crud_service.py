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
from services.file_processing import prepare_workspace_file


class TaskCrudService:
    """Xử lý các nghiệp vụ Thêm, Sửa, Xóa, Cập nhật trạng thái, Chuyển giao bài toán."""

    @staticmethod
    def add_task(
        workspace: Any,
        payload: dict[str, Any],
        files: list[UploadedFile],
        max_file_size: int,
        max_total_file_size: int,
    ) -> dict[str, Any]:
        name = required_text(payload, "baiToan")
        if workspace.find_task(name):
            raise ApiError(409, f'Bài toán "{name}" đã tồn tại')

        mode = str(payload.get("mode", "manual")).strip().lower()
        if mode == "manual":
            url_value = validate_urls(str(payload.get("urlGoc", "")))
        elif mode == "import":
            if not files:
                raise ApiError(400, "Chưa chọn file để import")
            if sum(len(file.content) for file in files) > max_total_file_size:
                raise ApiError(413, "Tổng dung lượng file vượt quá giới hạn")

            for file in files:
                extension = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
                if extension not in ALLOWED_EXTENSIONS:
                    raise ApiError(400, f"Không hỗ trợ định dạng file: {file.filename}")
                if len(file.content) > max_file_size:
                    raise ApiError(413, f"File vượt quá giới hạn: {file.filename}")

            urls = []
            for file in files:
                try:
                    workspace_file = prepare_workspace_file(
                        file.filename, file.content_type, file.content
                    )
                    urls.append(
                        workspace.upload_file(
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
        workspace.append_task(task)
        return task

    @staticmethod
    def edit_task(workspace: Any, payload: dict[str, Any]) -> dict[str, Any]:
        old_name = required_text(payload, "oldBaiToan")
        new_name = required_text(payload, "newBaiToan")
        new_url = validate_urls(str(payload.get("newUrl", "")), require_one=False)
        duplicate = workspace.find_task(new_name)
        if duplicate and new_name.casefold() != old_name.casefold():
            raise ApiError(409, f'Bài toán "{new_name}" đã tồn tại')
        try:
            return workspace.update_task(
                old_name, {"Bài toán": new_name, "URL": new_url}
            )
        except KeyError:
            raise ApiError(404, f'Không tìm thấy bài toán "{old_name}"') from None

    @staticmethod
    def delete_task(workspace: Any, payload: dict[str, Any]) -> None:
        task_id = payload.get("id")
        name = payload.get("baiToan")
        if task_id is not None:
            try:
                workspace.delete_task_by_id(task_id)
            except (KeyError, ValueError):
                raise ApiError(404, f'Không tìm thấy bài toán có id "{task_id}"') from None
        elif name:
            try:
                workspace.delete_task(str(name).strip())
            except KeyError:
                raise ApiError(404, f'Không tìm thấy bài toán "{name}"') from None
        else:
            raise ApiError(400, "Thiếu id bài toán")

    @staticmethod
    def update_status(workspace: Any, payload: dict[str, Any]) -> dict[str, Any]:
        name = required_text(payload, "baiToan")
        status = required_text(payload, "trangThai", 100)
        if status not in ALLOWED_STATUSES:
            raise ApiError(400, "Trạng thái không hợp lệ")
        try:
            return workspace.update_task(name, {"Trạng thái": status})
        except KeyError:
            raise ApiError(404, f'Không tìm thấy bài toán "{name}"') from None

    @staticmethod
    def transfer_task(workspace: Any, payload: dict[str, Any]) -> dict[str, Any]:
        name = required_text(payload, "baiToan")
        assignee = required_text(payload, "nguoiNhanMoi", 150)
        try:
            return workspace.update_task(name, {"Người làm": assignee})
        except KeyError:
            raise ApiError(404, f'Không tìm thấy bài toán "{name}"') from None
