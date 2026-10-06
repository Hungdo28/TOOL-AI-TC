"""
JobService: Luồng Mẹ (nhận đơn, ghi queue Supabase, bắn Webhook n8n) + API truy vấn trạng thái job.

Luồng Mẹ (enqueue_jobs):
  - Nhận danh sách bài toán từ FE
  - Ghi mỗi bài toán thành 1 dòng vào bảng ai_jobs (status='queued')
  - Kích hoạt Webhook sang n8n trong background thread
  - Trả ngay 200 về cho FE (KHÔNG làm FE bị block hay timeout)

FE Polling:
  - GET /api/jobs/status?requestId=xxx -> hỏi trạng thái của cả lần chạy
  - Đồng bộ tự động với Google Sheet để phát hiện khi n8n hoàn thành bài toán
"""
from __future__ import annotations

import json
import logging
import ssl
import threading
import urllib.error
import urllib.request
from typing import Any

from repositories.supabase_queue import (
    SupabaseQueue,
    STATUS_QUEUED,
    STATUS_PROCESSING,
    STATUS_COMPLETED,
    STATUS_FAILED,
)
from services.task_service import ApiError

LOGGER = logging.getLogger("autotc-backend.job_service")


def _normalized(value: Any) -> str:
    return str(value or "").strip().casefold()


class JobService:
    def __init__(
        self,
        queue: SupabaseQueue,
        n8n_webhook_url: str = "",
        workspace: Any = None,
    ) -> None:
        self._queue = queue
        self._n8n_webhook_url = n8n_webhook_url.strip()
        self._workspace = workspace

    def enqueue_jobs(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Luồng Mẹ: Nhận yêu cầu chạy, ghi vào hàng đợi Supabase,
        bắn Webhook sang n8n và trả 200 ngay cho FE.

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

        # Kiểm tra xem có bài nào đang trong queue chưa (bỏ qua job cũ > 30p)
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

        # Bắn webhook sang n8n tự động
        self._trigger_n8n(
            task_names=task_names,
            request_id=request_id,
            username=username,
            mode=mode,
            prompt_ai2=prompt_ai2,
            jobs=created_jobs,
        )

        return {
            "message": (
                f"Da xep hang va gui lenh sang n8n cho {len(created_jobs)} bai toan. "
                "He thong dang xu ly, vui long cho!"
            ),
            "requestId": request_id,
            "jobs": created_jobs,
            "queuedCount": len(created_jobs),
        }

    def _trigger_n8n(
        self,
        task_names: list[str],
        request_id: str,
        username: str,
        mode: str,
        prompt_ai2: str,
        jobs: list[dict[str, Any]],
    ) -> None:
        """Kích hoạt webhook n8n trong background thread để trả 200 ngay cho FE."""
        if not self._n8n_webhook_url:
            LOGGER.warning("Chua cau hinh N8N_WEBHOOK_URL, bo qua goi webhook n8n")
            return

        payload = {
            "baiToan": task_names[0] if len(task_names) == 1 else ", ".join(task_names),
            "danhSachBaiToan": task_names,
            "loaiChay": mode,
            "requestId": request_id,
            "username": username,
            "promptAI2": prompt_ai2,
            "jobs": jobs,
        }

        thread = threading.Thread(
            target=self._call_n8n_webhook,
            args=(payload, jobs),
            daemon=True,
        )
        thread.start()

    def _call_n8n_webhook(self, payload: dict[str, Any], jobs: list[dict[str, Any]]) -> None:
        """Gửi POST sang n8n webhook và cập nhật trạng thái trong Supabase."""
        LOGGER.info(
            "Goi n8n webhook: %s (taskNames=%s, requestId=%s)",
            self._n8n_webhook_url, payload.get("danhSachBaiToan"), payload.get("requestId")
        )

        # Chuyển status các job sang processing
        for j in jobs:
            job_id = j.get("jobId")
            if job_id:
                try:
                    self._queue.mark_processing(job_id)
                except Exception as exc:
                    LOGGER.warning("Khong the mark processing cho job %s: %s", job_id, exc)

        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            self._n8n_webhook_url,
            data=data,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": "AutoTC-Backend/1.0",
            },
            method="POST",
        )

        ssl_ctx = ssl.create_default_context()
        try:
            with urllib.request.urlopen(req, timeout=120, context=ssl_ctx) as resp:
                resp_body = resp.read().decode("utf-8", errors="replace")
                LOGGER.info("n8n webhook phan hoi status=%s body=%.200s", resp.status, resp_body)
        except urllib.error.HTTPError as exc:
            err_detail = exc.read().decode("utf-8", errors="replace")
            LOGGER.error("n8n webhook loi HTTP %s: %s", exc.code, err_detail)
            for j in jobs:
                job_id = j.get("jobId")
                if job_id:
                    try:
                        self._queue.mark_failed(job_id, f"n8n tra ve HTTP {exc.code}: {err_detail[:300]}")
                    except Exception:
                        pass
        except Exception as exc:
            if "certificate verify failed" in str(exc).lower():
                try:
                    unverified_ctx = ssl._create_unverified_context()
                    with urllib.request.urlopen(req, timeout=120, context=unverified_ctx) as resp:
                        LOGGER.info("n8n webhook goi thanh cong voi unverified SSL context")
                        return
                except Exception as exc2:
                    exc = exc2

            LOGGER.error("Loi ket noi n8n webhook (%s): %s", self._n8n_webhook_url, exc)
            for j in jobs:
                job_id = j.get("jobId")
                if job_id:
                    try:
                        self._queue.mark_failed(job_id, f"Loi ket noi n8n: {str(exc)[:300]}")
                    except Exception:
                        pass

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

        # Đồng bộ trạng thái từ Google Sheet nếu có bài toán đã hoàn thành
        if self._workspace and jobs:
            jobs = self._sync_jobs_with_sheet(jobs)

        return jobs

    def _sync_jobs_with_sheet(self, jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Nếu Google Sheet đã cập nhật 'Đã xong' hoặc lỗi thì đồng bộ sang Supabase."""
        pending_jobs = [j for j in jobs if j.get("status") in (STATUS_QUEUED, STATUS_PROCESSING)]
        if not pending_jobs:
            return jobs

        try:
            sheet_tasks = {
                _normalized(t.get("Bài toán")): t
                for t in self._workspace.list_tasks()
            }
        except Exception as exc:
            LOGGER.debug("Khong the doc tasks tu Google Sheet de dong bo: %s", exc)
            return jobs

        for j in pending_jobs:
            task_name = j.get("task_name", "")
            task_row = sheet_tasks.get(_normalized(task_name))
            if not task_row:
                continue

            status = str(task_row.get("Trạng thái", "")).strip()
            status_lower = status.lower()

            if status == "Đã xong":
                job_id = j.get("id")
                if job_id:
                    try:
                        self._queue.mark_completed(job_id)
                        j["status"] = STATUS_COMPLETED
                        LOGGER.info("Dong bo job %s ('%s') -> completed tu Google Sheet", job_id, task_name)
                    except Exception as e:
                        LOGGER.warning("Loi mark completed job %s: %s", job_id, e)
            elif any(err_word in status_lower for err_word in ("lỗi", "thất bại", "error")):
                job_id = j.get("id")
                if job_id:
                    try:
                        self._queue.mark_failed(job_id, f"Google Sheet: {status}")
                        j["status"] = STATUS_FAILED
                        j["error_msg"] = f"Google Sheet: {status}"
                        LOGGER.info("Dong bo job %s ('%s') -> failed tu Google Sheet", job_id, task_name)
                    except Exception as e:
                        LOGGER.warning("Loi mark failed job %s: %s", job_id, e)

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

