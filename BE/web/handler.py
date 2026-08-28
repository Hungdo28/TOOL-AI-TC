from __future__ import annotations

import json
import logging
from http.server import BaseHTTPRequestHandler
from typing import Any

from core.config import Settings
from web.models import ApiResponse
from web.request import HttpRequest
from router import Router
from services.task_service import ApiError


LOGGER = logging.getLogger("autotc-backend")


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
        self.send_header("Access-Control-Allow-Headers", "Content-Type,X-User-Name,X-User-Role")

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
        except ApiError as error:
            self._send_json(ApiResponse(error.status, {"success": False, "message": error.message}))
        except Exception:
            LOGGER.exception("Unhandled API error")
            self._send_json(ApiResponse(500, {"success": False, "message": "Lỗi nội bộ backend"}))

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._send_cors_headers()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        self._dispatch("GET")

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
