from web.models import ApiResponse


def get_health(_request) -> ApiResponse:
    return ApiResponse(200, {"success": True, "service": "autotc-backend"})
