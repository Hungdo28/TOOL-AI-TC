from __future__ import annotations

import json
import logging
import threading
import urllib.parse
import urllib.request
from typing import Any

from core.config import Settings

LOGGER = logging.getLogger("autotc-backend")


def _normalized(value: Any) -> str:
    return str(value or "").strip().casefold()


class SupabaseRepository:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.supabase_url = settings.supabase_url.strip().rstrip("/")
        self.api_key = (
            getattr(settings, "supabase_service_role_key", None)
            or settings.supabase_anon_key
        ).strip()
        self._lock = threading.RLock()

        # Giữ lại google workspace upload file nếu có cấu hình Google Drive
        self._google_workspace = None
        if settings.credentials_file or settings.credentials_json:
            try:
                from repositories.google_workspace import GoogleWorkspace
                self._google_workspace = GoogleWorkspace(settings)
            except Exception as e:
                LOGGER.warning("Không thể khởi tạo Google Drive upload: %s", e)

    def _headers(self, prefer: str | None = None) -> dict[str, str]:
        headers = {
            "apikey": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if prefer:
            headers["Prefer"] = prefer
        return headers

    def _request(
        self,
        endpoint: str,
        method: str = "GET",
        data: dict[str, Any] | list[Any] | None = None,
        prefer: str | None = None,
    ) -> Any:
        url = f"{self.supabase_url}/rest/v1/{endpoint}"
        body_bytes = json.dumps(data).encode("utf-8") if data is not None else None
        req = urllib.request.Request(
            url,
            data=body_bytes,
            headers=self._headers(prefer),
            method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                resp_bytes = resp.read()
                if resp_bytes:
                    return json.loads(resp_bytes.decode("utf-8"))
                return None
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            LOGGER.error("Supabase API error %s on %s %s: %s", e.code, method, endpoint, error_body)
            raise RuntimeError(f"Supabase lỗi ({e.code}): {error_body}") from e
        except Exception as e:
            LOGGER.error("Lỗi kết nối Supabase %s %s: %s", method, endpoint, e)
            raise RuntimeError(f"Không thể kết nối Supabase: {e}") from e

    @staticmethod
    def _to_task_dict(row: dict[str, Any]) -> dict[str, Any]:
        """Chuyển đổi 1 record từ Supabase problems sang cấu trúc Dictionary chuẩn của hệ thống."""
        p_id = str(row.get("id") or "")
        legacy_id = row.get("legacy_id")
        return {
            "id": p_id,
            "problem_id": p_id,
            "legacy_id": legacy_id,
            "ID": legacy_id if legacy_id is not None else "",
            "row_number": p_id,  # Luôn dùng UUID làm mã định danh duy nhất cho Frontend
            "Bài toán": str(row.get("title") or ""),
            "URL": str(row.get("source_url") or ""),
            "Link Testcase": str(row.get("testcase_url") or ""),
            "Link tài liệu phân tích": str(row.get("analysis_doc_url") or ""),
            "Trạng thái": str(row.get("status") or "Chưa làm"),
            "Người làm": str(row.get("assignee") or ""),
        }

    def list_tasks(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._request("problems?select=*&order=legacy_id.asc.nullslast,created_at.asc")
            if not isinstance(rows, list):
                return []
            return [self._to_task_dict(r) for r in rows]

    def find_task(self, identifier: str) -> dict[str, Any] | None:
        if not identifier:
            return None
        ident_norm = _normalized(identifier)
        for task in self.list_tasks():
            if (
                _normalized(task.get("Bài toán")) == ident_norm
                or _normalized(task.get("id")) == ident_norm
                or str(task.get("legacy_id")) == str(identifier).strip()
            ):
                return task
        return None

    def append_task(self, task: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            tasks = self.list_tasks()
            # Tính legacy_id lớn nhất + 1
            max_legacy = 0
            for t in tasks:
                lid = t.get("legacy_id")
                if isinstance(lid, int) and lid > max_legacy:
                    max_legacy = lid

            payload = {
                "title": str(task.get("Bài toán") or "").strip(),
                "source_url": str(task.get("URL") or "").strip(),
                "status": str(task.get("Trạng thái") or "Chưa làm").strip(),
                "assignee": str(task.get("Người làm") or "").strip(),
                "legacy_id": max_legacy + 1,
            }
            if task.get("Link Testcase"):
                payload["testcase_url"] = str(task["Link Testcase"]).strip()
            if task.get("Link tài liệu phân tích"):
                payload["analysis_doc_url"] = str(task["Link tài liệu phân tích"]).strip()

            created = self._request(
                "problems",
                method="POST",
                data=payload,
                prefer="return=representation",
            )
            if isinstance(created, list) and len(created) > 0:
                return self._to_task_dict(created[0])
            return self.find_task(payload["title"]) or task

    def update_task(self, name_or_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            existing = self.find_task(name_or_id)
            if not existing:
                raise KeyError(name_or_id)

            task_uuid = existing["id"]
            db_changes: dict[str, Any] = {}

            mapping = {
                "Bài toán": "title",
                "URL": "source_url",
                "Trạng thái": "status",
                "Người làm": "assignee",
                "Link Testcase": "testcase_url",
                "Link tài liệu phân tích": "analysis_doc_url",
            }
            for k, v in changes.items():
                target_key = mapping.get(k)
                if target_key:
                    db_changes[target_key] = v

            if not db_changes:
                return existing

            updated = self._request(
                f"problems?id=eq.{urllib.parse.quote(task_uuid)}",
                method="PATCH",
                data=db_changes,
                prefer="return=representation",
            )
            if isinstance(updated, list) and len(updated) > 0:
                return self._to_task_dict(updated[0])

            existing.update(changes)
            return existing

    def delete_task_by_id(self, task_id: Any) -> None:
        with self._lock:
            existing = self.find_task(str(task_id))
            if not existing:
                raise KeyError(task_id)

            task_uuid = existing["id"]
            self._request(
                f"problems?id=eq.{urllib.parse.quote(task_uuid)}",
                method="DELETE",
            )

    def delete_task(self, task_name: str) -> None:
        self.delete_task_by_id(task_name)

    def upload_file(
        self,
        filename: str,
        content_type: str,
        content: bytes,
        target_mime_type: str,
    ) -> str:
        if self._google_workspace:
            return self._google_workspace.upload_file(
                filename, content_type, content, target_mime_type
            )
        raise RuntimeError(
            "Chưa cấu hình tài khoản Google Workspace / Drive để upload file."
        )
