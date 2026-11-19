from __future__ import annotations

from typing import Any

from core.config import Settings
from services.ai_callback_service import AiCallbackService
from services.ai_pipeline_service import AiPipelineService
from services.autotest_service import AutoTestService
from services.local_storage_service import LocalStorageService
from services.common import (
    ALLOWED_EXTENSIONS,
    ALLOWED_STATUSES,
    ApiError,
    UploadedFile,
    _normalized,
    required_text,
    validate_urls,
)
from services.execution_tracker import ExecutionTracker
from services.task_crud_service import TaskCrudService


class TaskService:
    """Facade service tập hợp các nghiệp vụ quản lý bài toán, execution tracking và AI Pipeline."""

    def __init__(
        self,
        workspace: Any,
        max_file_size: int,
        max_total_file_size: int,
        settings: Settings | None = None,
    ):
        self.workspace = workspace
        self.max_file_size = max_file_size
        self.max_total_file_size = max_total_file_size
        self.settings = settings
        self.tracker = ExecutionTracker()
        self.pipeline = (
            AiPipelineService(workspace, settings, execution_tracker=self.tracker)
            if settings is not None
            else None
        )
        self.autotest = (
            AutoTestService(workspace, settings)
            if settings is not None
            else None
        )
        self.local_storage = (
            LocalStorageService(settings.local_records_dir)
            if settings is not None
            else LocalStorageService("./AutoTC_Records")
        )

    @property
    def _running_tasks(self) -> dict[str, dict[str, str]]:
        return self.tracker._running_tasks

    @property
    def _running_tasks_lock(self):
        return self.tracker._lock

    @staticmethod
    def _is_terminal_status(status: Any) -> bool:
        return ExecutionTracker.is_terminal_status(status)

    def list_tasks(self, assignee: str | None = None) -> list[dict[str, Any]]:
        raw_tasks = self.workspace.list_tasks()
        if assignee:
            wanted = _normalized(assignee)
            raw_tasks = [
                task
                for task in raw_tasks
                if _normalized(
                    task.get("Người làm") or task.get("Username") or task.get("Tài khoản")
                )
                == wanted
            ]
        return self.tracker.attach_executions(raw_tasks)

    def start_executions(self, payload: dict[str, Any]) -> list[dict[str, str]]:
        existing_names = {_normalized(task.get("Bài toán")) for task in self.workspace.list_tasks()}
        return self.tracker.start_executions(payload, existing_names)

    def stop_executions(self, payload: dict[str, Any]) -> None:
        raw_names = payload.get("taskNames")
        if not raw_names and payload.get("taskName"):
            raw_names = [payload["taskName"]]
        elif not raw_names and payload.get("baiToan"):
            raw_names = [payload["baiToan"]]

        if not isinstance(raw_names, list) or not raw_names:
            raise ApiError(400, "taskNames phải là danh sách bài toán không rỗng")

        names = [str(n).strip() for n in raw_names if str(n).strip()]

        # 1. Dừng tính giờ trên execution tracker
        try:
            self.tracker.stop_executions(payload)
        except Exception:
            for name in names:
                self.tracker.clear_execution(name)

        # 2. Hủy luồng trong AI Pipeline nếu đang chạy
        if self.pipeline:
            for name in names:
                self.pipeline.cancel_task(name)

        # 3. Đưa trạng thái bài toán về 'Chưa làm' nếu đang ở Waiting
        for name in names:
            try:
                task = self.workspace.find_task(name)
                if task:
                    task_id = str(task.get("id") or task.get("problem_id") or name)
                    curr_status = str(task.get("Trạng thái") or "")
                    if curr_status.lower() in ("waiting", "đang chạy", "đang xử lý", "đang xử lý ai..."):
                        self.workspace.update_task(task_id, {"Trạng thái": "Chưa làm"})
            except Exception:
                pass

    def add_task(self, payload: dict[str, Any], files: list[UploadedFile]) -> dict[str, Any]:
        return TaskCrudService.add_task(
            self.workspace,
            payload,
            files,
            self.max_file_size,
            self.max_total_file_size,
        )

    def edit_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        return TaskCrudService.edit_task(self.workspace, payload)

    def delete_task(self, payload: dict[str, Any]) -> None:
        TaskCrudService.delete_task(self.workspace, payload)

    def update_status(self, payload: dict[str, Any]) -> dict[str, Any]:
        task = TaskCrudService.update_status(self.workspace, payload)
        status = task.get("Trạng thái", "")
        if self._is_terminal_status(status):
            name = task.get("Bài toán", "")
            self.tracker.clear_execution(name)
        return task

    def transfer_task(self, payload: dict[str, Any]) -> dict[str, Any]:
        return TaskCrudService.transfer_task(self.workspace, payload)

    def handle_ai_callback(self, payload: dict[str, Any]) -> dict[str, Any]:
        return AiCallbackService.handle_ai_callback(
            self.workspace,
            payload,
            execution_tracker=self.tracker,
        )

    def run_ai_pipeline(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.pipeline:
            raise ApiError(500, "AI Pipeline chưa được khởi tạo trên Backend.")
        return self.pipeline.run_From_payload(payload)

    def generate_autotest(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.autotest:
            raise ApiError(500, "AutoTest Service chưa được khởi tạo trên Backend.")
        return self.autotest.generate_autotest_cases(payload)

    def run_autotest(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.autotest:
            raise ApiError(500, "AutoTest Service chưa được khởi tạo trên Backend.")
        return self.autotest.run_autotest_suite(payload)

    def list_local_files(self, relative_dir: str = "") -> dict[str, Any]:
        return self.local_storage.list_folder(relative_dir)

    def create_local_folder(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.local_storage.create_folder(payload)

    def save_local_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.local_storage.save_record(payload)

    def read_local_record(self, relative_path: str) -> dict[str, Any]:
        return self.local_storage.read_record(relative_path)

    def _ensure_local_bundle_restored(self, task_name: str) -> None:
        """Tự động khôi phục file Excel/Word từ qa_memory nếu máy chưa có."""
        if not task_name or not hasattr(self.workspace, "_request"):
            return
        try:
            import urllib.parse
            info = self.local_storage.get_task_bundle_info(task_name)
            task = self.workspace.find_task(task_name)
            task_id = str(task.get("id") or "") if task else ""
            if not task_id:
                return

            if not info.get("excelSheetPath"):
                enc = urllib.parse.quote(task_id)
                rows = self.workspace._request(
                    f"qa_memory?kind=eq.testcase&problem_id=eq.{enc}&select=test_suite,content,approved,review_status&order=created_at.asc,id.asc"
                )
                if isinstance(rows, list) and rows:
                    approved = [r for r in rows if r.get("approved") is True or r.get("review_status") == "approved"]
                    if approved:
                        self.local_storage.save_testcase_excel(task_name, approved)

            if not info.get("wordDocPath"):
                enc = urllib.parse.quote(task_id)
                a_rows = self.workspace._request(
                    f"qa_memory?kind=eq.analysis&problem_id=eq.{enc}&select=content&order=created_at.desc&limit=1"
                )
                if isinstance(a_rows, list) and a_rows:
                    c_obj = a_rows[0].get("content")
                    if isinstance(c_obj, dict) and str(c_obj.get("final_text") or "").strip():
                        self.local_storage.save_analysis_word(task_name, str(c_obj["final_text"]).strip())
        except Exception:
            pass

    def open_local_folder(self, payload: dict[str, Any]) -> dict[str, Any]:
        task_name = str(payload.get("taskName") or payload.get("baiToan") or payload.get("folder") or "").strip()
        self._ensure_local_bundle_restored(task_name)
        return self.local_storage.open_task_folder(payload)

    def open_local_file(self, payload: dict[str, Any]) -> dict[str, Any]:
        task_name = str(payload.get("taskName") or payload.get("baiToan") or payload.get("folder") or "").strip()
        self._ensure_local_bundle_restored(task_name)
        return self.local_storage.open_task_file(payload)

    def download_local_file(self, query: dict[str, str]) -> tuple[bytes, str, str]:
        task_name = str(query.get("taskName") or query.get("baiToan") or "").strip()
        file_type = str(query.get("type") or query.get("fileType") or "word").strip()
        if not task_name:
            raise ApiError(400, "Thiếu tham số taskName")
        self._ensure_local_bundle_restored(task_name)
        return self.local_storage.get_task_file_bytes(task_name, file_type)

    def get_local_testcases(self, query: dict[str, str]) -> dict[str, Any]:
        """Lấy toàn bộ danh sách testcase cho màn Review (ưu tiên qa_memory phân trang, fallback đọc file Excel Local)."""
        task_name = str(query.get("taskName") or query.get("baiToan") or "").strip()
        prob_id = str(query.get("problem_id") or query.get("problemId") or "").strip()
        if not task_name and not prob_id:
            raise ApiError(400, "Thiếu tham số taskName hoặc problem_id")

        if not prob_id and task_name:
            try:
                task = self.workspace.find_task(task_name)
                if task:
                    prob_id = str(task.get("id") or task.get("problem_id") or "")
                    if not task_name:
                        task_name = str(task.get("Bài toán") or "").strip()
            except Exception:
                pass

        mem = self.pipeline.memory if self.pipeline else None
        if mem is None:
            from services.memory_service import MemoryService
            mem = MemoryService(self.workspace)

        rows = mem.fetch_task_testcases(problem_id=prob_id, problem_title=task_name)
        if rows:
            return {
                "success": True,
                "source": "qa_memory",
                "total": len(rows),
                "items": rows,
            }

        if task_name:
            info = self.local_storage.get_task_bundle_info(task_name)
            excel_path = info.get("excelSheetPath") or ""
            if excel_path:
                from services.document_builder import read_testcases_from_local_excel
                parsed = read_testcases_from_local_excel(excel_path)
                tc_items: list[dict[str, Any]] = []
                idx = 0
                for r in parsed:
                    if r.get("row_type") != "testcase":
                        continue
                    idx += 1
                    tc_items.append({
                        "id": f"local_{idx}",
                        "problem_id": prob_id,
                        "problem_title": task_name,
                        "test_suite": r.get("test_suite") or "Chung",
                        "review_status": "approved",
                        "approved": True,
                        "content": {
                            "id": r.get("id") or f"[TC]_{idx}",
                            "muc_dich": r.get("muc_dich") or "",
                            "cac_buoc": r.get("cac_buoc") or "",
                            "ket_qua_mong_muon": r.get("ket_qua_mong_muon") or "",
                            "ghi_chu": r.get("ghi_chu") or "",
                        },
                    })
                if tc_items:
                    return {
                        "success": True,
                        "source": "local_excel",
                        "total": len(tc_items),
                        "items": tc_items,
                    }

        return {
            "success": True,
            "source": "empty",
            "total": 0,
            "items": [],
        }

    def push_local_to_drive(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.pipeline:
            raise ApiError(500, "AI Pipeline chưa được khởi tạo trên Backend.")
        return self.pipeline.push_local_to_drive(payload)
