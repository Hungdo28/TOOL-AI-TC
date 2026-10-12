from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

ALLOWED_EXTENSIONS = {"doc", "docx", "xls", "xlsx", "pdf", "txt"}
ALLOWED_STATUSES = {"Chưa làm", "Waiting", "Đã xong"}


def _normalized(value: Any) -> str:
    """Chuẩn hóa chuỗi để so sánh không phân biệt hoa thường và khoảng trắng thừa."""
    return str(value or "").strip().casefold()


class ApiError(Exception):
    """Lỗi API trả về mã HTTP status và thông điệp lỗi rõ ràng cho client."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


@dataclass(frozen=True)
class UploadedFile:
    """Cấu trúc dữ liệu đại diện cho một file tải lên từ client."""

    filename: str
    content_type: str
    content: bytes


def required_text(payload: dict[str, Any], key: str, max_length: int = 300) -> str:
    """Kiểm tra và lấy trường chuỗi bắt buộc từ payload."""
    value = str(payload.get(key, "")).strip()
    if not value:
        raise ApiError(400, f"Thiếu trường bắt buộc: {key}")
    if len(value) > max_length:
        raise ApiError(400, f"{key} dài quá {max_length} ký tự")
    return value


def validate_urls(raw_urls: str, require_one: bool = True) -> str:
    """Kiểm tra và chuẩn hóa danh sách URL hợp lệ."""
    urls = [value.strip() for value in raw_urls.replace(",", "\n").splitlines() if value.strip()]
    if not urls and require_one:
        raise ApiError(400, "Cần ít nhất một URL tài liệu")
    for url in urls:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ApiError(400, f"URL không hợp lệ: {url}")
    return "\n".join(urls)
