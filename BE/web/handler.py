from __future__ import annotations

import json
import logging
import mimetypes
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from core.config import Settings
from web.models import ApiResponse
from web.request import HttpRequest
from router import Router
from services.task_service import ApiError


LOGGER = logging.getLogger("autotc-backend")
FE_ROOT = (Path(__file__).resolve().parents[2] / "FE").resolve()
API_PATH_PREFIXES = ("/api/", "/webhook/")


class ApiHandler(BaseHTTPRequestHandler):
    router: Router
    settings: Settings
    server_version = "AutoTCBackend/1.0"

    def _allowed_origin(self) -> str | None:
        origin = self.headers.get("Origin", "")
        if "*" in self.settings.allowed_origins:
            return "*"
        return origin if origin in self.settings.allowed_origins else None

    def _send_cors_headers(self) -> None:
        allowed_origin = self._allowed_origin()
        if allowed_origin:
            self.send_header("Access-Control-Allow-Origin", allowed_origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,PATCH,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type,Authorization,X-User-Name,X-User-Role,X-Callback-Token")

    def _send_json(self, response: ApiResponse) -> None:
        payload = json.dumps(response.body, ensure_ascii=False).encode("utf-8")
        self.send_response(response.status)
        self._send_cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _dispatch(self, method: str) -> None:
        try:
            request = HttpRequest(self, self.settings)
            self._send_json(self.router.dispatch(method, request))
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            LOGGER.warning("Trình duyệt đã đóng kết nối sớm trước khi nhận xong phản hồi.")
        except ApiError as error:
            try:
                self._send_json(ApiResponse(error.status, {"success": False, "message": error.message}))
            except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
                pass
        except Exception:
            LOGGER.exception("Unhandled API error")
            try:
                self._send_json(ApiResponse(500, {"success": False, "message": "Lỗi nội bộ backend"}))
            except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
                pass

    @staticmethod
    def _is_api_path(req_path: str) -> bool:
        return req_path in {"/api", "/webhook"} or req_path.startswith(API_PATH_PREFIXES)

    def _serve_static(self, raw_path: str) -> None:
        clean_path = unquote(raw_path).lstrip("/")
        if not clean_path or clean_path in {"FE", "FE/"}:
            clean_path = "login.html"
        elif clean_path.startswith("FE/"):
            clean_path = clean_path[3:]

        try:
            target = (FE_ROOT / clean_path).resolve()
        except (OSError, ValueError):
            target = None

        if target is None or not target.is_relative_to(FE_ROOT) or not target.is_file():
            try:
                body = b"Not Found"
                self.send_response(404)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
                pass
            return

        mime_type, _ = mimetypes.guess_type(str(target))
        mime_type = mime_type or "application/octet-stream"
        if mime_type.startswith("text/") or mime_type in {"application/javascript", "application/json"}:
            mime_type = f"{mime_type}; charset=utf-8"

        try:
            payload = target.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(payload)
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            LOGGER.warning("Trình duyệt đã đóng kết nối sớm trước khi nhận xong tệp tĩnh.")

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._send_cors_headers()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        req_path = urlparse(self.path).path
        if self._is_api_path(req_path):
            self._dispatch("GET")
            return
        self._serve_static(req_path)

    def do_POST(self) -> None:  # noqa: N802
        self._dispatch("POST")

    def do_PUT(self) -> None:  # noqa: N802
        self._dispatch("PUT")

    def do_DELETE(self) -> None:  # noqa: N802
        self._dispatch("DELETE")

    def do_PATCH(self) -> None:  # noqa: N802
        self._dispatch("PATCH")

    def log_message(self, fmt: str, *args: Any) -> None:
        LOGGER.info("%s - %s", self.address_string(), fmt % args)


def create_handler(router: Router, settings: Settings):
    class ConfiguredApiHandler(ApiHandler):
        pass

    ConfiguredApiHandler.router = router
    ConfiguredApiHandler.settings = settings
    return ConfiguredApiHandler
