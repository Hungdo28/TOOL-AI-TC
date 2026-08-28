from __future__ import annotations

import json
import mimetypes
from email.parser import BytesParser
from email.policy import default
from typing import Any
from urllib.parse import urlparse

from core.config import Settings
from services.task_service import ApiError, UploadedFile


class HttpRequest:
    def __init__(self, handler, settings: Settings):
        self.handler = handler
        self.settings = settings

    @property
    def path(self) -> str:
        return urlparse(self.handler.path).path.rstrip("/") or "/"

    @property
    def headers(self):
        return self.handler.headers

    def read_body(self) -> bytes:
        content_length = int(self.headers.get("Content-Length", "0") or 0)
        max_request_size = self.settings.max_total_file_size + 1024 * 1024
        if content_length > max_request_size:
            raise ApiError(413, "Request vượt quá giới hạn dung lượng")
        return self.handler.rfile.read(content_length)

    def read_json(self) -> dict[str, Any]:
        if "application/json" not in self.headers.get("Content-Type", ""):
            raise ApiError(415, "Content-Type phải là application/json")
        try:
            data = json.loads(self.read_body().decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ApiError(400, "JSON không hợp lệ") from None
        if not isinstance(data, dict):
            raise ApiError(400, "Body phải là một JSON object")
        return data

    def read_form(self) -> tuple[dict[str, str], list[UploadedFile]]:
        content_type = self.headers.get("Content-Type", "")
        if "multipart/form-data" not in content_type:
            raise ApiError(415, "Content-Type phải là multipart/form-data")

        raw_message = (
            f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8")
            + self.read_body()
        )
        message = BytesParser(policy=default).parsebytes(raw_message)
        if not message.is_multipart():
            raise ApiError(400, "FormData không hợp lệ")

        fields: dict[str, str] = {}
        files: list[UploadedFile] = []
        for part in message.iter_parts():
            field_name = part.get_param("name", header="content-disposition")
            filename = part.get_filename()
            content = part.get_payload(decode=True) or b""
            if filename:
                files.append(
                    UploadedFile(
                        filename=filename,
                        content_type=part.get_content_type()
                        or mimetypes.guess_type(filename)[0]
                        or "application/octet-stream",
                        content=content,
                    )
                )
            elif field_name:
                fields[field_name] = content.decode(part.get_content_charset() or "utf-8")
        return fields, files

