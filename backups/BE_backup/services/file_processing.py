from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


GOOGLE_DOC_MIME_TYPE = "application/vnd.google-apps.document"
GOOGLE_SHEET_MIME_TYPE = "application/vnd.google-apps.spreadsheet"
DOCUMENT_EXTENSIONS = {"doc", "docx", "pdf", "txt"}
SPREADSHEET_EXTENSIONS = {"xls", "xlsx"}


@dataclass(frozen=True)
class WorkspaceFile:
    title: str
    source_mime_type: str
    target_mime_type: str
    content: bytes


def prepare_workspace_file(
    filename: str, content_type: str, content: bytes
) -> WorkspaceFile:
    """Chuẩn hóa file local trước khi gửi Drive API chuyển đổi."""
    safe_name = Path(filename).name
    extension = Path(safe_name).suffix.lower().lstrip(".")
    title = Path(safe_name).stem.strip() or "Tài liệu AutoTC"

    if extension in DOCUMENT_EXTENSIONS:
        target_mime_type = GOOGLE_DOC_MIME_TYPE
    elif extension in SPREADSHEET_EXTENSIONS:
        target_mime_type = GOOGLE_SHEET_MIME_TYPE
    else:
        raise ValueError(f"Không hỗ trợ chuyển đổi file: {safe_name}")

    return WorkspaceFile(
        title=title,
        source_mime_type=content_type or "application/octet-stream",
        target_mime_type=target_mime_type,
        content=content,
    )

