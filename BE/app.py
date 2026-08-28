from __future__ import annotations

import logging
from http.server import ThreadingHTTPServer

from controllers.task_controller import TaskController
from core.config import Settings
from web.handler import create_handler
from repositories.google_workspace import GoogleWorkspace
from router import Router
from services.task_service import TaskService


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
LOGGER = logging.getLogger("autotc-backend")


def build_server(settings: Settings) -> ThreadingHTTPServer:
    workspace = GoogleWorkspace(settings)
    task_service = TaskService(
        workspace,
        max_file_size=settings.max_file_size,
        max_total_file_size=settings.max_total_file_size,
    )
    task_controller = TaskController(task_service, settings)
    router = Router(task_controller)
    handler = create_handler(router, settings)
    return ThreadingHTTPServer((settings.host, settings.port), handler)


def main() -> None:
    settings = Settings.from_env()
    server = build_server(settings)
    LOGGER.info("AutoTC backend đang chạy tại http://%s:%s", settings.host, settings.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOGGER.info("Đang dừng backend")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
