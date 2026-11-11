import io
import json
import unittest
from types import SimpleNamespace

from controllers.health_controller import get_health
from web.handler import create_handler


class FakeRouter:
    def dispatch(self, method, request):
        if method == "GET" and request.path == "/api/health":
            return get_health(request)
        raise AssertionError(f"Unexpected route: {method} {request.path}")


class FakeSocket:
    def __init__(self, raw_request: bytes):
        self.rfile = io.BytesIO(raw_request)
        self.wfile = io.BytesIO()

    def makefile(self, mode: str, *args, **kwargs):
        return self.rfile if "r" in mode else self.wfile

    def sendall(self, data: bytes):
        self.wfile.write(data)


def run_get(handler_cls, path: str) -> tuple[int, dict[str, str], bytes]:
    raw_req = f"GET {path} HTTP/1.1\r\nHost: localhost\r\n\r\n".encode("ascii")
    sock = FakeSocket(raw_req)
    handler_cls(sock, ("127.0.0.1", 12345), None)
    raw_resp = sock.wfile.getvalue()
    head, _, body = raw_resp.partition(b"\r\n\r\n")
    lines = head.decode("iso-8859-1").split("\r\n")
    status_code = int(lines[0].split(" ", 2)[1])
    headers = {}
    for line in lines[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip().lower()] = v.strip()
    return status_code, headers, body


class StaticHandlerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        settings = SimpleNamespace(
            allowed_origins=("*",),
            max_total_file_size=1024 * 1024,
        )
        cls.handler_cls = create_handler(FakeRouter(), settings)

    def test_root_serves_login_html(self):
        status, headers, body = run_get(self.handler_cls, "/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers.get("content-type", ""))
        self.assertIn(b"<html", body.lower())

    def test_fe_prefix_and_static_js(self):
        status_html, _, _ = run_get(self.handler_cls, "/FE/login.html")
        self.assertEqual(status_html, 200)

        status_js, headers_js, _ = run_get(self.handler_cls, "/app.js")
        self.assertEqual(status_js, 200)
        self.assertIn("javascript", headers_js.get("content-type", ""))

    def test_path_traversal_is_blocked(self):
        status, _, _ = run_get(self.handler_cls, "/..%2FBE%2Fapp.py")
        self.assertEqual(status, 404)

    def test_api_health_still_dispatches_to_router(self):
        status, _, body = run_get(self.handler_cls, "/api/health")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertEqual(data, {"success": True, "service": "autotc-backend"})


if __name__ == "__main__":
    unittest.main()
