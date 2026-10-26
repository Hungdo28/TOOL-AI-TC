from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request

from core.config import Settings
from core.security import create_jwt_token
from web.models import ApiResponse
from services.task_service import ApiError

LOGGER = logging.getLogger("autotc-backend.auth_controller")


class AuthController:
    def __init__(self, settings: Settings):
        self.settings = settings

    def get_token(self, request) -> ApiResponse:
        """Cấp JWT Token an toàn cho người dùng sau khi xác thực.

        Nhận JSON: { "username": "..." } hoặc { "username": "...", "password": "..." }
        """
        payload = request.read_json()
        username = str(payload.get("username") or "").strip()
        if not username:
            raise ApiError(400, "Thiếu tên đăng nhập (username)")

        password = payload.get("password")

        # Nếu client gửi kèm mật khẩu, kiểm tra qua Supabase RPC verify_login
        if password:
            is_valid, role = self._verify_credentials_with_supabase(username, str(password))
            if not is_valid:
                raise ApiError(401, "Sai tài khoản hoặc mật khẩu")
        else:
            # Tra cứu role từ Supabase
            role = self._fetch_role(username)
            if not role:
                raise ApiError(404, f"Không tìm thấy người dùng '{username}'")

        # Tạo JWT Token có thời hạn 7 ngày
        token = create_jwt_token(
            {"sub": username, "role": role},
            self.settings.jwt_secret,
            expires_in_seconds=7 * 86400
        )

        return ApiResponse(200, {
            "success": True,
            "token": token,
            "user": {
                "username": username,
                "role": role
            }
        })

    def _verify_credentials_with_supabase(self, username: str, password: str) -> tuple[bool, str]:
        supabase_url = self.settings.supabase_url.rstrip("/")
        supabase_anon_key = self.settings.supabase_anon_key
        url = f"{supabase_url}/rest/v1/rpc/verify_login"

        req = urllib.request.Request(
            url,
            headers={
                "apikey": supabase_anon_key,
                "Authorization": f"Bearer {supabase_anon_key}",
                "Content-Type": "application/json"
            },
            data=json.dumps({"p_username": username, "p_password": password}).encode("utf-8")
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if isinstance(data, list) and len(data) > 0:
                    user_info = data[0]
                    role = str(user_info.get("role") or "viewer").strip().lower()
                    return True, role
                return False, "viewer"
        except Exception as exc:
            LOGGER.warning("Lỗi xác thực RPC verify_login: %s", exc)
            return False, "viewer"

    def _fetch_role(self, username: str) -> str | None:
        supabase_url = self.settings.supabase_url.rstrip("/")
        supabase_anon_key = self.settings.supabase_anon_key
        url = f"{supabase_url}/rest/v1/users?select=role&username=eq.{urllib.parse.quote(username)}&limit=1"

        req = urllib.request.Request(
            url,
            headers={
                "apikey": supabase_anon_key,
                "Authorization": f"Bearer {supabase_anon_key}",
                "Content-Type": "application/json"
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if isinstance(data, list) and len(data) > 0:
                    return str(data[0].get("role") or "viewer").strip().lower()
                return None
        except Exception as exc:
            LOGGER.warning("Lỗi tra cứu role Supabase: %s", exc)
            return None
