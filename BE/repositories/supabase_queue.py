"""
Repository tương tác với bảng ai_jobs trong Supabase.

Schema bảng ai_jobs (tạo trên Supabase SQL editor):
---
CREATE TABLE IF NOT EXISTS ai_jobs (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_name    TEXT NOT NULL,
    request_id   TEXT NOT NULL,
    username     TEXT NOT NULL,
    mode         TEXT NOT NULL DEFAULT 'single',
    prompt_ai2   TEXT NOT NULL DEFAULT '',
    status       TEXT NOT NULL DEFAULT 'queued',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at   TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error_msg    TEXT
);

-- Index để worker lấy job nhanh theo thứ tự ưu tiên
CREATE INDEX IF NOT EXISTS ai_jobs_status_created_at ON ai_jobs(status, created_at ASC);
---
"""
from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from typing import Any

from core.config import Settings

LOGGER = logging.getLogger("autotc-backend.supabase_queue")

# Trạng thái hợp lệ của một job
STATUS_QUEUED = "queued"
STATUS_PROCESSING = "processing"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"


class SupabaseQueue:
    """Lớp bao bọc Supabase REST API để quản lý hàng đợi ai_jobs."""

    TABLE = "ai_jobs"

    def __init__(self, settings: Settings) -> None:
        self._base_url = settings.supabase_url.rstrip("/")
        self._api_key = settings.supabase_anon_key
        self._table_url = f"{self._base_url}/rest/v1/{self.TABLE}"

    # ------------------------------------------------------------------
    # HTTP helpers (không phụ thuộc thư viện ngoài)
    # ------------------------------------------------------------------

    def _headers(self, *, prefer: str | None = None) -> dict[str, str]:
        headers = {
            "apikey": self._api_key,
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        if prefer:
            headers["Prefer"] = prefer
        return headers

    def _request(
        self,
        method: str,
        url: str,
        *,
        body: Any = None,
        prefer: str | None = None,
    ) -> Any:
        raw_body = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(
            url,
            data=raw_body,
            headers=self._headers(prefer=prefer),
            method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                content = resp.read()
                return json.loads(content) if content else None
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            LOGGER.error("Supabase %s %s -> %s: %s", method, url, exc.code, detail)
            raise RuntimeError(f"Supabase loi {exc.code}: {detail}") from exc

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def enqueue(
        self,
        task_name: str,
        request_id: str,
        username: str,
        mode: str = "single",
        prompt_ai2: str = "",
    ) -> dict[str, Any]:
        """Ghi một yêu cầu mới vào hàng đợi với trạng thái 'queued'.
        Trả về bản ghi vừa tạo (có trường id, created_at, ...).
        """
        body = {
            "task_name": task_name,
            "request_id": request_id,
            "username": username,
            "mode": mode,
            "prompt_ai2": prompt_ai2,
            "status": STATUS_QUEUED,
        }
        result = self._request(
            "POST",
            self._table_url,
            body=body,
            prefer="return=representation",
        )
        if isinstance(result, list) and result:
            return result[0]
        return result or body

    def get_job_status(self, job_id: str) -> dict[str, Any] | None:
        """Lấy thông tin một job theo id."""
        url = (
            f"{self._table_url}"
            f"?id=eq.{urllib.parse.quote(job_id)}&limit=1"
        )
        result = self._request("GET", url)
        if isinstance(result, list) and result:
            return result[0]
        return None

    def list_jobs_by_request(self, request_id: str) -> list[dict[str, Any]]:
        """Lấy tất cả job của một lần bấm chạy (cùng request_id)."""
        url = (
            f"{self._table_url}"
            f"?request_id=eq.{urllib.parse.quote(request_id)}"
            f"&select=id,task_name,status,created_at,started_at,completed_at,error_msg"
            f"&order=created_at.asc"
        )
        result = self._request("GET", url)
        return result if isinstance(result, list) else []

    def list_jobs_by_task(self, task_name: str, limit: int = 5) -> list[dict[str, Any]]:
        """Lấy N job gần nhất của một bài toán, mới nhất trước."""
        url = (
            f"{self._table_url}"
            f"?task_name=eq.{urllib.parse.quote(task_name)}"
            f"&select=id,status,created_at,started_at,completed_at,error_msg"
            f"&order=created_at.desc&limit={limit}"
        )
        result = self._request("GET", url)
        return result if isinstance(result, list) else []

    def next_queued_job(self) -> dict[str, Any] | None:
        """Lấy job đầu tiên đang ở trạng thái 'queued' (FIFO).
        Worker dùng hàm này mỗi chu kỳ để lấy việc cần làm.
        """
        url = (
            f"{self._table_url}"
            f"?status=eq.{STATUS_QUEUED}"
            f"&order=created_at.asc&limit=1"
        )
        result = self._request("GET", url)
        if isinstance(result, list) and result:
            return result[0]
        return None

    def mark_processing(self, job_id: str) -> None:
        """Cập nhật trạng thái job thành 'processing' và ghi thời điểm bắt đầu."""
        url = f"{self._table_url}?id=eq.{urllib.parse.quote(job_id)}"
        self._request(
            "PATCH",
            url,
            body={"status": STATUS_PROCESSING, "started_at": "now()"},
        )

    def mark_completed(self, job_id: str) -> None:
        """Cập nhật trạng thái job thành 'completed'."""
        url = f"{self._table_url}?id=eq.{urllib.parse.quote(job_id)}"
        self._request(
            "PATCH",
            url,
            body={"status": STATUS_COMPLETED, "completed_at": "now()"},
        )

    def mark_failed(self, job_id: str, error_msg: str) -> None:
        """Cập nhật trạng thái job thành 'failed' và ghi lỗi."""
        url = f"{self._table_url}?id=eq.{urllib.parse.quote(job_id)}"
        self._request(
            "PATCH",
            url,
            body={
                "status": STATUS_FAILED,
                "completed_at": "now()",
                "error_msg": error_msg[:2000],
            },
        )

    def is_task_already_queued(self, task_name: str) -> bool:
        """Kiểm tra xem bài toán này có đang chờ hoặc đang xử lý chưa.
        Tránh enqueue trùng khi nhiều người bấm cùng một bài.
        """
        url = (
            f"{self._table_url}"
            f"?task_name=eq.{urllib.parse.quote(task_name)}"
            f"&status=in.(queued,processing)"
            f"&select=id&limit=1"
        )
        result = self._request("GET", url)
        return bool(result)
