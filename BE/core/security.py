from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    pad_len = (-len(s)) % 4
    return base64.urlsafe_b64decode(s + ("=" * pad_len))


def create_jwt_token(payload: dict[str, Any], secret: str, expires_in_seconds: int = 7 * 86400) -> str:
    """Tạo JWT Token chuẩn HS256 sử dụng thư viện chuẩn của Python."""
    now = int(time.time())
    full_payload = {
        **payload,
        "iat": now,
        "exp": now + expires_in_seconds
    }

    header_bytes = json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode("utf-8")
    payload_bytes = json.dumps(full_payload, separators=(",", ":")).encode("utf-8")

    header_part = _b64url_encode(header_bytes)
    payload_part = _b64url_encode(payload_bytes)
    signing_input = f"{header_part}.{payload_part}".encode("ascii")

    secret_bytes = secret.encode("utf-8")
    signature = hmac.new(secret_bytes, signing_input, hashlib.sha256).digest()
    signature_part = _b64url_encode(signature)

    return f"{header_part}.{payload_part}.{signature_part}"


def decode_jwt_token(token: str, secret: str) -> dict[str, Any] | None:
    """Giải mã và xác thực chữ ký JWT Token."""
    if not token or not isinstance(token, str):
        return None

    parts = token.strip().split(".")
    if len(parts) != 3:
        return None

    header_part, payload_part, signature_part = parts
    signing_input = f"{header_part}.{payload_part}".encode("ascii")
    secret_bytes = secret.encode("utf-8")

    try:
        expected_sig = hmac.new(secret_bytes, signing_input, hashlib.sha256).digest()
        actual_sig = _b64url_decode(signature_part)
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None

        payload_bytes = _b64url_decode(payload_part)
        payload = json.loads(payload_bytes.decode("utf-8"))

        # Kiểm tra hạn dùng
        exp = payload.get("exp")
        if exp and isinstance(exp, (int, float)) and time.time() > exp:
            return None

        return payload
    except Exception:
        return None
