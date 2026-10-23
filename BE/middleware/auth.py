from __future__ import annotations

import hmac
import json
import logging
import time
import urllib.parse
import urllib.request
from typing import Optional

from core.config import Settings
from services.task_service import ApiError

LOGGER = logging.getLogger("autotc-backend.auth")

# In-memory cache: {username: (role, expire_timestamp)}
_ROLE_CACHE: dict[str, tuple[str, float]] = {}
CACHE_TTL_SECONDS = 180  # 3 phút


def require_user(request) -> str:
    """Đảm bảo request mang định danh người dùng (header X-User-Name).

    Dùng cho các endpoint mà mọi user đã đăng nhập đều được phép
    (vd: đăng ký/dừng theo dõi execution), khác với require_admin.
    """
    username = (request.headers.get("X-User-Name") or "").strip()
    if not username:
        raise ApiError(401, "Yêu cầu đăng nhập để thực hiện thao tác này")
    return username


def require_callback_token(request, settings: Settings) -> None:
    """Xác thực lời gọi từ n8n / AI Worker bằng shared secret trong header.

    Fail-closed: nếu backend chưa cấu hình AI_CALLBACK_TOKEN thì từ chối mọi
    callback để tránh vô tình mở endpoint ra công chúng.
    """
    expected = getattr(settings, "ai_callback_token", None)
    if not expected:
        LOGGER.error("Từ chối AI callback vì backend chưa cấu hình AI_CALLBACK_TOKEN")
        raise ApiError(
            503,
            "Backend chưa cấu hình AI_CALLBACK_TOKEN. Hãy khai báo trong .env và khởi động lại.",
        )

    provided = (request.headers.get("X-Callback-Token") or "").strip()
    if not hmac.compare_digest(provided, expected):
        LOGGER.warning("Từ chối AI callback: token không hợp lệ")
        raise ApiError(401, "Token callback không hợp lệ")


def fetch_role_from_supabase(username: str, settings: Settings) -> Optional[str]:
    """Truy vấn trực tiếp Database Supabase để lấy role thật của người dùng."""
    if not username:
        return None

    now = time.time()
    cached = _ROLE_CACHE.get(username)
    if cached and cached[1] > now:
        return cached[0]

    supabase_url = getattr(settings, "supabase_url", "").strip().rstrip("/")
    supabase_anon_key = getattr(settings, "supabase_anon_key", "").strip()

    if not supabase_url or not supabase_anon_key:
        return None

    try:
        url = (
            f"{supabase_url}/rest/v1/users"
            f"?select=role&username=eq.{urllib.parse.quote(username)}&limit=1"
        )
        req = urllib.request.Request(
            url,
            headers={
                "apikey": supabase_anon_key,
                "Authorization": f"Bearer {supabase_anon_key}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if isinstance(data, list) and len(data) > 0:
                role = str(data[0].get("role", "")).strip().lower()
                _ROLE_CACHE[username] = (role, now + CACHE_TTL_SECONDS)
                return role
            return None
    except Exception as exc:
        LOGGER.warning("Không thể xác minh role từ Supabase cho user '%s': %s", username, exc)
        return None


def resolve_role(request, settings: Settings) -> tuple[str, str]:
    """Xác định (username, role) tin cậy của request để lọc dữ liệu.

    Role được ưu tiên lấy từ Supabase DB (chống giả mạo header X-User-Role).
    Nếu DB không trả được kết quả (lỗi mạng / user không tồn tại) thì coi như
    viewer để fail-closed: người dùng chỉ thấy task của chính mình.
    """
    username = (request.headers.get("X-User-Name") or "").strip()
    if not username:
        return "", "viewer"

    if not settings.enforce_role_header:
        # Chế độ dev/tin cậy nội bộ: dùng role client gửi lên
        role = (request.headers.get("X-User-Role") or "viewer").strip().lower()
        return username, "admin" if role == "admin" else "viewer"

    db_role = fetch_role_from_supabase(username, settings)
    if db_role in {"admin", "viewer"}:
        return username, db_role
    return username, "viewer"


def require_admin(request, settings: Settings) -> None:
    if not settings.enforce_role_header:
        return

    # 1. Kiểm tra nhanh header phía client: nếu gửi lên không phải admin thì từ chối ngay
    role_header = request.headers.get("X-User-Role", "").strip().lower()
    if role_header != "admin":
        raise ApiError(403, "Chức năng này chỉ dành cho admin")

    # 2. Chống giả mạo F12: Nếu backend có cấu hình Supabase, đối chiếu trực tiếp với DB
    supabase_url = getattr(settings, "supabase_url", None)
    if supabase_url:
        username = request.headers.get("X-User-Name", "").strip()
        if not username:
            raise ApiError(401, "Yêu cầu đăng nhập để thực hiện thao tác này")

        db_role = fetch_role_from_supabase(username, settings)
        if db_role != "admin":
            LOGGER.warning(
                "Chặn giả mạo quyền Admin! User '%s' gửi role '%s' nhưng DB là '%s'",
                username, role_header, db_role
            )
            raise ApiError(403, "Tài khoản của bạn không có quyền Admin trong hệ thống")


