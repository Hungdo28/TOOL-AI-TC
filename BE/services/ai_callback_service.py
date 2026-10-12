from __future__ import annotations

import logging
from typing import Any

from services.common import ApiError

LOGGER = logging.getLogger("autotc-backend")


class AiCallbackService:
    """Xử lý kết quả trả về từ n8n / AI Worker sau khi quá trình sinh testcase hoàn tất."""

    @staticmethod
    def handle_ai_callback(
        workspace: Any,
        payload: dict[str, Any],
        execution_tracker: Any = None,
    ) -> dict[str, Any]:
        task_id = (
            payload.get("problem_id")
            or payload.get("id")
            or payload.get("baiToan")
            or payload.get("taskName")
            or payload.get("job_id")
        )
        if not task_id:
            raise ApiError(400, "Thiếu định danh bài toán (problem_id hoặc baiToan)")

        task = workspace.find_task(str(task_id))
        if not task:
            raise ApiError(404, f'Không tìm thấy bài toán "{task_id}"')

        task_name = task.get("Bài toán", "")
        changes: dict[str, Any] = {}

        # 1. Trạng thái
        status = str(payload.get("status") or payload.get("trangThai") or "Đã xong").strip()
        changes["Trạng thái"] = status

        # 2. Xử lý Link tài liệu phân tích Docs
        analysis_doc_url = payload.get("analysis_doc_url") or payload.get("linkTaiLieuPhanTich")
        analysis_text = payload.get("analysis_text") or payload.get("final_text")
        if analysis_doc_url:
            changes["Link tài liệu phân tích"] = str(analysis_doc_url).strip()
        elif analysis_text and hasattr(workspace, "create_analysis_doc"):
            try:
                changes["Link tài liệu phân tích"] = workspace.create_analysis_doc(
                    task_name, str(analysis_text)
                )
            except Exception as e:
                LOGGER.warning("Không thể tạo Google Doc phân tích: %s", e)

        # 3. Xử lý Link Sheet Testcase
        testcase_url = payload.get("testcase_url") or payload.get("linkTestcase")
        testcases = payload.get("testcases") or payload.get("test_cases")
        if testcase_url:
            changes["Link Testcase"] = str(testcase_url).strip()
        elif testcases and isinstance(testcases, list) and hasattr(workspace, "create_testcase_sheet"):
            try:
                changes["Link Testcase"] = workspace.create_testcase_sheet(
                    task_name, testcases
                )
            except Exception as e:
                LOGGER.warning("Không thể tạo Google Sheet testcase: %s", e)

        # 4. Cập nhật vào Supabase / Workspace
        target_id = task.get("id") or task_name
        updated = workspace.update_task(target_id, changes)

        # 5. Dừng đồng hồ đang chạy ở Backend
        if execution_tracker:
            execution_tracker.clear_execution(task_name)

        return updated
