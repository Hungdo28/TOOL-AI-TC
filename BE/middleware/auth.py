from core.config import Settings
from services.task_service import ApiError


def require_admin(request, settings: Settings) -> None:
    if not settings.enforce_role_header:
        return
    role = request.headers.get("X-User-Role", "").strip().lower()
    if role != "admin":
        raise ApiError(403, "Chức năng này chỉ dành cho admin")

