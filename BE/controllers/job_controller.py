from __future__ import annotations

from web.models import ApiResponse
from services.job_service import JobService


class JobController:
    def __init__(self, service: JobService) -> None:
        self.service = service

    def enqueue_jobs(self, request) -> ApiResponse:
        """
        POST /api/jobs
        Luong Me: Nhan yeu cau chay, ghi vao hang doi Supabase, tra 200 ngay.
        FE nhan ve {jobId, status='queued'} va bat dau polling.
        """
        payload = request.read_json()
        # Bổ sung username từ header xác thực
        if "username" not in payload or not payload["username"]:
            payload["username"] = request.headers.get("X-User-Name", "unknown")
        result = self.service.enqueue_jobs(payload)
        return ApiResponse(200, {"success": True, **result})

    def get_jobs_status(self, request) -> ApiResponse:
        """
        GET /api/jobs/status?requestId=xxx
        FE polling: Tra cuu trang thai tat ca job cua 1 lan bam chay.
        """
        request_id = request.query_params.get("requestId", "").strip()
        jobs = self.service.get_jobs_status(request_id)
        return ApiResponse(200, {"success": True, "jobs": jobs})

    def get_next_job(self, _request) -> ApiResponse:
        """
        GET /api/jobs/next
        Danh cho n8n Worker: lay 1 job dau hang doi (FIFO).
        Neu khong co job nao, tra ra {"job": null}.
        """
        job = self.service.get_next_queued_job()
        return ApiResponse(200, {"success": True, "job": job})

    def update_job_status(self, request) -> ApiResponse:
        """
        PATCH /api/jobs/:id/status
        Danh cho n8n Worker: cap nhat trang thai sau khi xu ly.
        Body: {"status": "processing" | "completed" | "failed", "errorMsg": "..."}
        """
        payload = request.read_json()
        job_id = request.path_params.get("id", "").strip()
        if not job_id:
            from services.task_service import ApiError
            raise ApiError(400, "Thieu job id")

        new_status = str(payload.get("status", "")).strip()
        if new_status == "processing":
            self.service.mark_job_processing(job_id)
        elif new_status == "completed":
            self.service.mark_job_completed(job_id)
        elif new_status == "failed":
            error_msg = str(payload.get("errorMsg", "Unknown error")).strip()
            self.service.mark_job_failed(job_id, error_msg)
        else:
            from services.task_service import ApiError
            raise ApiError(400, f"Trang thai khong hop le: {new_status}")

        return ApiResponse(200, {"success": True, "jobId": job_id, "status": new_status})
