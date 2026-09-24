"""
JobService: Luồng Mẹ (nhận đơn) + API truy vấn trạng thái job.

Luồng Mẹ (enqueue_jobs):
  - Nhận danh sách bài toán từ FE
  - Ghi mỗi bài toán thành 1 dòng vào bảng ai_jobs (status='queued')
  - Trả ngay 200 về cho FE (KHÔNG chờ n8n/AI xử lý xong)

Luồng Con (n8n Worker) -- cấu hình trên n8n, KHÔNG phải trong file này:
  - Schedule Trigger (30 giây / 1 phút quét 1 lần)
  - GET /api/jobs/next  -> lấy 1 job đang queued
  - PATCH ai_jobs set status='processing'
  - Thực thi AI (Summarization Chain + Wait node)
  - PATCH ai_jobs set status='completed'

FE Polling:
  - GET /api/jobs/status?requestId=xxx -> hỏi trạng thái của cả lần chạy
"""
from __future__ import annotations

import logging
from typing import Any

from repositories.supabase_queue import SupabaseQueue, STATUS_QUEUED
from services.task_service import ApiError

LOGGER = logging.getLogger("autotc-backend.job_service")


class JobService:
    def __init__(self, queue: SupabaseQueue) -> None:
        self._queue = queue

    def enqueue_jobs(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Luồng Mẹ: Nhận yêu cầu chạy, ghi vào hàng đợi, trả 200 ngay.

        Payload mong đợi:
        {
            "taskNames": ["TC_Login", "TC_Search"],   # list bài toán
            "requestId": "uuid-...",
            "username":  "hungdv",
            "mode":      "single" | "phan_tich" | "testcase",
            "promptAI2": "..."
        }
        """
        raw_names = payload.get("taskNames")
        if not isinstance(raw_names, list) or not raw_names:
            raise ApiError(400, "taskNames phai la danh sach bai toan khong rong")

        request_id = str(payload.get("requestId", "")).strip()
        if not request_id:
            raise ApiError(400, "Thieu requestId")

        username = str(payload.get("username", "")).strip()
        mode = str(payload.get("mode", "single")).strip()
        prompt_ai2 = str(payload.get("promptAI2", "")).strip()

        # Deduplicate, loại bỏ empty
        task_names = list(dict.fromkeys(
            name.strip() for name in raw_names if str(name).strip()
        ))
        if not task_names:
            raise ApiError(400, "Khong co bai toan hop le")

        # Kiểm tra xem có bài nào đang trong queue chưa
        already_queued = [
            name for name in task_names
            if self._queue.is_task_already_queued(name)
        ]
        if already_queued:
            raise ApiError(
                409,
                f"Bai toan dang trong hang doi hoac dang xu ly: {', '.join(already_queued)}"
            )

        # Ghi vào hàng đợi — mỗi bài là 1 job riêng
        created_jobs = []
        for task_name in task_names:
            try:
                job = self._queue.enqueue(
                    task_name=task_name,
                    request_id=request_id,
                    username=username,
                    mode=mode,
                    prompt_ai2=prompt_ai2,
                )
                created_jobs.append({
                    "jobId": job.get("id", ""),
                    "taskName": task_name,
                    "status": STATUS_QUEUED,
                    "createdAt": job.get("created_at", ""),
                })
                LOGGER.info(
                    "Enqueued job %s for task '%s' (request %s)",
                    job.get("id"), task_name, request_id
                )
            except Exception as exc:
                LOGGER.error("Loi enqueue task '%s': %s", task_name, exc)
                raise ApiError(502, f"Khong the ghi hang doi cho bai toan: {task_name}") from exc

        return {
            "message": (
                f"Da xep hang {len(created_jobs)} bai toan. "
                "He thong se xu ly lan luot, vui long cho!"
            ),
            "requestId": request_id,
            "jobs": created_jobs,
            "queuedCount": len(created_jobs),
        }

    def get_jobs_status(self, request_id: str) -> list[dict[str, Any]]:
        """
        Tra cứu trạng thái tất cả job của 1 lần bấm chạy (dùng cho FE polling).
        Trả về danh sách jobs với status: queued | processing | completed | failed
        """
        if not request_id:
            raise ApiError(400, "Thieu requestId")
        try:
            jobs = self._queue.list_jobs_by_request(request_id)
        except Exception as exc:
            LOGGER.error("Loi truy van trang thai jobs (requestId=%s): %s", request_id, exc)
            raise ApiError(502, "Khong the truy van trang thai tu Supabase") from exc
        return jobs

    def get_next_queued_job(self) -> dict[str, Any] | None:
        """
        Dùng cho n8n Worker: lấy job đầu hàng đợi (FIFO).
        n8n gọi GET /api/jobs/next mỗi 30-60 giây.
        """
        try:
            return self._queue.next_queued_job()
        except Exception as exc:
            LOGGER.error("Loi lay job tiep theo: %s", exc)
            raise ApiError(502, "Khong the lay job tu hang doi") from exc

    def mark_job_processing(self, job_id: str) -> None:
        """n8n gọi khi bắt đầu xử lý job."""
        try:
            self._queue.mark_processing(job_id)
        except Exception as exc:
            raise ApiError(502, f"Khong the cap nhat trang thai processing: {exc}") from exc

    def mark_job_completed(self, job_id: str) -> None:
        """n8n gọi khi xử lý xong job."""
        try:
            self._queue.mark_completed(job_id)
        except Exception as exc:
            raise ApiError(502, f"Khong the cap nhat trang thai completed: {exc}") from exc

    def mark_job_failed(self, job_id: str, error_msg: str) -> None:
        """n8n gọi khi xử lý thất bại."""
        try:
            self._queue.mark_failed(job_id, error_msg)
        except Exception as exc:
            raise ApiError(502, f"Khong the cap nhat trang thai failed: {exc}") from exc
