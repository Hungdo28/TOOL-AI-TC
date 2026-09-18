from __future__ import annotations

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


