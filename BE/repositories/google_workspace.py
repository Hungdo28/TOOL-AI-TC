from __future__ import annotations

import io
import threading
from typing import Any

from google.auth import load_credentials_from_file
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials as UserCredentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

from core.config import Settings


SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"


def _column_name(index: int) -> str:
    result = ""
    current = index + 1
    while current:
        current, remainder = divmod(current - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _normalized(value: Any) -> str:
    return str(value or "").strip().casefold()


class GoogleWorkspace:
    def __init__(self, settings: Settings):
        self.settings = settings
        scopes = [SHEETS_SCOPE, DRIVE_SCOPE]
        if settings.credentials_json:
            credential_type = settings.credentials_json.get("type")
            if credential_type == "service_account":
                credentials = service_account.Credentials.from_service_account_info(
                    settings.credentials_json, scopes=scopes
                )
            elif credential_type == "authorized_user":
                credentials = UserCredentials.from_authorized_user_info(
                    settings.credentials_json, scopes=scopes
                )
            else:
                raise ValueError("JSON credential Google có type không được hỗ trợ")
        else:
            credentials, _ = load_credentials_from_file(settings.credentials_file, scopes=scopes)

        self.sheets = build("sheets", "v4", credentials=credentials, cache_discovery=False)
        self.drive = build("drive", "v3", credentials=credentials, cache_discovery=False)
        self._mutation_lock = threading.RLock()

    @property
    def _range(self) -> str:
        escaped = self.settings.sheet_name.replace("'", "''")
        return f"'{escaped}'!A:ZZ"

    def _read_grid(self) -> tuple[list[str], list[list[Any]]]:
        response = (
            self.sheets.spreadsheets()
            .values()
            .get(
                spreadsheetId=self.settings.spreadsheet_id,
                range=self._range,
                valueRenderOption="FORMATTED_VALUE",
            )
            .execute()
        )
        values = response.get("values", [])
        header_index = self.settings.header_row - 1
        if len(values) <= header_index:
            raise RuntimeError("Google Sheet chưa có dòng tiêu đề")
        headers = [str(value).strip() for value in values[header_index]]
        return headers, values[header_index + 1 :]

    @staticmethod
    def _header_index(headers: list[str], column: str) -> int:
        wanted = _normalized(column)
        for index, header in enumerate(headers):
            if _normalized(header) == wanted:
                return index
        raise RuntimeError(f"Google Sheet thiếu cột bắt buộc: {column}")

    def list_tasks(self) -> list[dict[str, Any]]:
        headers, rows = self._read_grid()
        result = []
        for offset, row in enumerate(rows, start=self.settings.header_row + 1):
            if not any(str(value).strip() for value in row):
                continue
            item = {
                header: row[index] if index < len(row) else ""
                for index, header in enumerate(headers)
                if header
            }
            item["row_number"] = offset
            result.append(item)
        return result

    def find_task(self, task_name: str) -> dict[str, Any] | None:
        wanted = _normalized(task_name)
        return next(
            (
                task
                for task in self.list_tasks()
                if _normalized(task.get("Bài toán")) == wanted
            ),
            None,
        )

    def append_task(self, values_by_column: dict[str, Any]) -> None:
        with self._mutation_lock:
            headers, _ = self._read_grid()
            row = [""] * len(headers)
            normalized_values = {_normalized(key): value for key, value in values_by_column.items()}
            for index, header in enumerate(headers):
                if _normalized(header) in normalized_values:
                    row[index] = normalized_values[_normalized(header)]

            self.sheets.spreadsheets().values().append(
                spreadsheetId=self.settings.spreadsheet_id,
                range=self._range,
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body={"values": [row]},
            ).execute()

    def update_task(self, task_name: str, changes: dict[str, Any]) -> dict[str, Any]:
        with self._mutation_lock:
            headers, rows = self._read_grid()
            name_index = self._header_index(headers, "Bài toán")
            wanted = _normalized(task_name)
            for offset, original_row in enumerate(rows, start=self.settings.header_row + 1):
                current_name = original_row[name_index] if name_index < len(original_row) else ""
                if _normalized(current_name) != wanted:
                    continue

                row = list(original_row) + [""] * (len(headers) - len(original_row))
                normalized_changes = {_normalized(key): value for key, value in changes.items()}
                for index, header in enumerate(headers):
                    if _normalized(header) in normalized_changes:
                        row[index] = normalized_changes[_normalized(header)]

                end_column = _column_name(len(headers) - 1)
                escaped = self.settings.sheet_name.replace("'", "''")
                self.sheets.spreadsheets().values().update(
                    spreadsheetId=self.settings.spreadsheet_id,
                    range=f"'{escaped}'!A{offset}:{end_column}{offset}",
                    valueInputOption="USER_ENTERED",
                    body={"values": [row]},
                ).execute()
                return {
                    header: row[index] if index < len(row) else ""
                    for index, header in enumerate(headers)
                    if header
                }

        raise KeyError(task_name)

    def delete_task(self, task_name: str) -> None:
        with self._mutation_lock:
            task = self.find_task(task_name)
            if not task:
                raise KeyError(task_name)
            row_number = int(task["row_number"])
            self.sheets.spreadsheets().batchUpdate(
                spreadsheetId=self.settings.spreadsheet_id,
                body={
                    "requests": [
                        {
                            "deleteDimension": {
                                "range": {
                                    "sheetId": self.settings.sheet_id,
                                    "dimension": "ROWS",
                                    "startIndex": row_number - 1,
                                    "endIndex": row_number,
                                }
                            }
                        }
                    ]
                },
            ).execute()

    def upload_file(
        self,
        filename: str,
        content_type: str,
        content: bytes,
        target_mime_type: str,
    ) -> str:
        metadata: dict[str, Any] = {
            "name": filename,
            "mimeType": target_mime_type,
        }
        if self.settings.drive_folder_id:
            metadata["parents"] = [self.settings.drive_folder_id]

        media = MediaIoBaseUpload(
            io.BytesIO(content),
            mimetype=content_type or "application/octet-stream",
            resumable=False,
        )
        uploaded = (
            self.drive.files()
            .create(
                body=metadata,
                media_body=media,
                fields="id,webViewLink",
                supportsAllDrives=True,
            )
            .execute()
        )
        file_id = uploaded["id"]

        if self.settings.drive_share_mode == "anyone":
            self.drive.permissions().create(
                fileId=file_id,
                body={"type": "anyone", "role": "reader"},
                fields="id",
                supportsAllDrives=True,
            ).execute()

        return uploaded.get("webViewLink") or f"https://drive.google.com/file/d/{file_id}/view"
