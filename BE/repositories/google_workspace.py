from __future__ import annotations

import io
import logging
import re
import threading
from typing import Any

from google.auth import load_credentials_from_file
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials as UserCredentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

from core.config import Settings
from services.document_builder import (
    FONT_NAME,
    TEMPLATE_CACHE_PATH,
    TEMPLATE_DOC_CACHE_PATH,
    _clean_excel_sheet_title,
    _extract_toc_subitems,
    _group_testcases_by_suite,
    _organize_subsuites_for_sheet,
    _parse_sections_from_analysis_text,
    build_analysis_word_bytes,
    build_testcase_excel_bytes,
    read_testcases_from_local_excel,
)

LOGGER = logging.getLogger("autotc-backend")


SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
DRIVE_SCOPE = "https://www.googleapis.com/auth/drive"
DOCS_SCOPE = "https://www.googleapis.com/auth/documents"

TEMPLATE_TC_SHEET_ID = "1JOirPM9SyeyNgdnUtjyrrgrRQ1MmaoZIk5o-cepgV5Y"
TEMPLATE_DOC_ID = "1FWzRAf5wouAzWUVLl9azJAuBKc7m8VTqeNb3YtFr5lM"


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
        self._scopes = [SHEETS_SCOPE, DRIVE_SCOPE, DOCS_SCOPE]
        self._thread_local = threading.local()
        self._mutation_lock = threading.RLock()
        self._task_folder_cache: dict[str, str] = {}
        # Kiểm tra credential hợp lệ ngay lúc khởi tạo
        self._load_credentials()
        self.ensure_template_cache()

    def ensure_template_cache(self) -> None:
        """Tải sẵn 2 bản Template gốc (Testcase Sheet & Analysis Doc có trang bìa) từ Google Drive về BE/templates/."""
        TEMPLATE_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        if not TEMPLATE_CACHE_PATH.is_file():
            try:
                xlsx_bytes = (
                    self.drive.files()
                    .export(
                        fileId=TEMPLATE_TC_SHEET_ID,
                        mimeType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )
                    .execute()
                )
                if xlsx_bytes:
                    TEMPLATE_CACHE_PATH.write_bytes(xlsx_bytes)
                    LOGGER.info("Đã đồng bộ Template Testcase gốc về: %s", TEMPLATE_CACHE_PATH)
            except Exception as err:
                LOGGER.warning("Không thể tải sẵn Template Testcase về máy (sẽ dùng khung dự phòng): %s", err)

        if not TEMPLATE_DOC_CACHE_PATH.is_file():
            try:
                docx_bytes = (
                    self.drive.files()
                    .export(
                        fileId=TEMPLATE_DOC_ID,
                        mimeType="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    )
                    .execute()
                )
                if docx_bytes:
                    TEMPLATE_DOC_CACHE_PATH.write_bytes(docx_bytes)
                    LOGGER.info("Đã đồng bộ Template Phân tích (kèm trang bìa) về: %s", TEMPLATE_DOC_CACHE_PATH)
            except Exception as err:
                LOGGER.warning("Không thể tải sẵn Template Phân tích về máy: %s", err)

    def _load_credentials(self):
        if self.settings.credentials_json:
            credential_type = self.settings.credentials_json.get("type")
            if credential_type == "service_account":
                return service_account.Credentials.from_service_account_info(
                    self.settings.credentials_json, scopes=self._scopes
                )
            if credential_type == "authorized_user":
                return UserCredentials.from_authorized_user_info(
                    self.settings.credentials_json, scopes=self._scopes
                )
            raise ValueError("JSON credential Google có type không được hỗ trợ")
        credentials, _ = load_credentials_from_file(
            self.settings.credentials_file, scopes=self._scopes
        )
        return credentials

    @property
    def sheets(self):
        client = getattr(self._thread_local, "sheets", None)
        if client is None:
            client = build(
                "sheets",
                "v4",
                credentials=self._load_credentials(),
                cache_discovery=False,
            )
            self._thread_local.sheets = client
        return client

    @property
    def drive(self):
        client = getattr(self._thread_local, "drive", None)
        if client is None:
            client = build(
                "drive",
                "v3",
                credentials=self._load_credentials(),
                cache_discovery=False,
            )
            self._thread_local.drive = client
        return client

    @property
    def docs(self):
        client = getattr(self._thread_local, "docs", None)
        if client is None:
            client = build(
                "docs",
                "v1",
                credentials=self._load_credentials(),
                cache_discovery=False,
            )
            self._thread_local.docs = client
        return client

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

    def delete_task_by_id(self, row_number: int) -> None:
        with self._mutation_lock:
            row_number = int(row_number)
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

    def _ensure_task_drive_folder(self, task_name: str) -> str | None:
        """
        Tự động tìm hoặc tạo mới 1 Folder theo tên bài toán trên Google Drive
        để chứa chung cả file Word Phân tích và file Sheet Testcase của bài toán đó.
        """
        clean_name = str(task_name or "Bài toán AutoTC").strip()
        cache_key = _normalized(clean_name)
        if cache_key in self._task_folder_cache:
            return self._task_folder_cache[cache_key]

        try:
            escaped_name = clean_name.replace("\\", "\\\\").replace("'", "\\'")
            q_parts = [
                "mimeType = 'application/vnd.google-apps.folder'",
                "trashed = false",
                f"name = '{escaped_name}'",
            ]
            if self.settings.drive_folder_id:
                q_parts.append(f"'{self.settings.drive_folder_id}' in parents")

            found = (
                self.drive.files()
                .list(
                    q=" and ".join(q_parts),
                    fields="files(id,name)",
                    pageSize=1,
                    supportsAllDrives=True,
                    includeItemsFromAllDrives=True,
                )
                .execute()
            )
            files = found.get("files") or []
            if files and files[0].get("id"):
                folder_id = str(files[0]["id"])
                self._task_folder_cache[cache_key] = folder_id
                return folder_id

            folder_meta: dict[str, Any] = {
                "name": clean_name,
                "mimeType": "application/vnd.google-apps.folder",
            }
            if self.settings.drive_folder_id:
                folder_meta["parents"] = [self.settings.drive_folder_id]

            created = (
                self.drive.files()
                .create(
                    body=folder_meta,
                    fields="id",
                    supportsAllDrives=True,
                )
                .execute()
            )
            folder_id = str(created["id"])
            try:
                self.drive.permissions().create(
                    fileId=folder_id,
                    body={"type": "anyone", "role": "reader"},
                    fields="id",
                    supportsAllDrives=True,
                ).execute()
            except Exception:
                pass

            self._task_folder_cache[cache_key] = folder_id
            return folder_id
        except Exception as err:
            LOGGER.warning("Không thể tạo folder bài toán trên Drive (%s), dùng folder gốc: %s", clean_name, err)
            return self.settings.drive_folder_id

    def create_analysis_doc(self, task_name: str, analysis_text: str) -> str:
        """
        Tạo Google Doc phân tích SRS đồng nhất 100% với bản Word (.docx) ở Local:
        - Sinh bản .docx chuẩn (có Trang bìa gốc từ TEMPLATE_DOC_ID, Bảng thông tin tổng quan,
          MỤC LỤC TÀI LIỆU, Bảng đặc tả API/DB/Test/Rủi ro và Font chữ Sarabun)
        - Tải trực tiếp lên Folder Bài toán trên Google Drive dưới dạng Google Docs để 2 bản Word & Docs giống hệt nhau.
        """
        if analysis_text and analysis_text.strip():
            try:
                docx_bytes = build_analysis_word_bytes(task_name, analysis_text)
                return self.upload_word_bytes_as_doc(task_name, docx_bytes, fallback_text=analysis_text)
            except Exception as build_err:
                LOGGER.warning("Không thể dựng .docx để đồng bộ lên Google Docs, dùng fallback Docs API: %s", build_err)
        return self._create_analysis_doc_via_api(task_name, analysis_text)

    def _create_analysis_doc_via_api(self, task_name: str, analysis_text: str) -> str:
        """Fallback tạo Google Doc trực tiếp qua Google Docs API nếu không thể convert từ .docx."""
        with self._mutation_lock:
            parent_folder_id = self._ensure_task_drive_folder(task_name)

            body: dict[str, Any] = {"name": f"Phân tích bài toán - {task_name}"}
            if parent_folder_id:
                body["parents"] = [parent_folder_id]
            copied = (
                self.drive.files()
                .copy(
                    fileId=TEMPLATE_DOC_ID,
                    body=body,
                    fields="id,webViewLink",
                    supportsAllDrives=True,
                )
                .execute()
            )
            doc_id = copied["id"]

            try:
                self.drive.permissions().create(
                    fileId=doc_id,
                    body={"type": "anyone", "role": "reader"},
                    fields="id",
                    supportsAllDrives=True,
                ).execute()
            except Exception:
                pass

            if analysis_text and analysis_text.strip():
                try:
                    doc_obj = self.docs.documents().get(documentId=doc_id).execute()
                    body_content = doc_obj.get("body", {}).get("content", [])
                    end_index = body_content[-1].get("endIndex", 1) - 1 if body_content else 1

                    text_to_insert = "\n\n" + analysis_text.strip() + "\n"
                    insert_pos = max(1, end_index)
                    end_pos = insert_pos + len(text_to_insert)

                    requests: list[dict[str, Any]] = [
                        {
                            "insertText": {
                                "location": {"index": insert_pos},
                                "text": text_to_insert,
                            }
                        },
                        {
                            # Căn lề trái (START), tránh bị kế thừa căn giữa của trang bìa
                            "updateParagraphStyle": {
                                "range": {
                                    "startIndex": insert_pos,
                                    "endIndex": end_pos,
                                },
                                "paragraphStyle": {
                                    "alignment": "START",
                                    "lineSpacing": 120,
                                    "spaceAbove": {"magnitude": 4, "unit": "PT"},
                                    "spaceBelow": {"magnitude": 4, "unit": "PT"},
                                },
                                "fields": "alignment,lineSpacing,spaceAbove,spaceBelow",
                            }
                        },
                        {
                            # Đặt toàn bộ nội dung phân tích dùng Font chữ Sarabun 11pt
                            "updateTextStyle": {
                                "range": {
                                    "startIndex": insert_pos,
                                    "endIndex": end_pos,
                                },
                                "textStyle": {
                                    "weightedFontFamily": {"fontFamily": FONT_NAME},
                                    "fontSize": {"magnitude": 11, "unit": "PT"},
                                    "bold": False,
                                    "foregroundColor": {
                                        "color": {"rgbColor": {"red": 0.118, "green": 0.161, "blue": 0.231}}
                                    },
                                },
                                "fields": "weightedFontFamily,fontSize,bold,foregroundColor",
                            }
                        },
                    ]

                    # Định dạng nổi bật cho các dòng Tiêu đề 6 Mục lớn (1. ... đến 6. ...)
                    for m in re.finditer(r"(?m)^([1-6]\.\s+[^\n]+)$", text_to_insert):
                        h_start = insert_pos + m.start(1)
                        h_end = insert_pos + m.end(1)
                        is_risk = "RỦI RO" in m.group(1).upper() or "Q&A" in m.group(1).upper()
                        rgb = (
                            {"red": 0.706, "green": 0.325, "blue": 0.035}
                            if is_risk
                            else {"red": 0.118, "green": 0.227, "blue": 0.541}
                        )
                        requests.append(
                            {
                                "updateTextStyle": {
                                    "range": {"startIndex": h_start, "endIndex": h_end},
                                    "textStyle": {
                                        "weightedFontFamily": {"fontFamily": FONT_NAME},
                                        "fontSize": {"magnitude": 13, "unit": "PT"},
                                        "bold": True,
                                        "foregroundColor": {"color": {"rgbColor": rgb}},
                                    },
                                    "fields": "weightedFontFamily,fontSize,bold,foregroundColor",
                                }
                            }
                        )
                        requests.append(
                            {
                                "updateParagraphStyle": {
                                    "range": {"startIndex": h_start, "endIndex": h_end},
                                    "paragraphStyle": {
                                        "spaceAbove": {"magnitude": 12, "unit": "PT"},
                                        "spaceBelow": {"magnitude": 4, "unit": "PT"},
                                        "keepWithNext": True,
                                    },
                                    "fields": "spaceAbove,spaceBelow,keepWithNext",
                                }
                            }
                        )

                    # Tô đậm & đổi màu cho các nhãn kỹ thuật ([System], [POST], Params:, Response:, (CHÚ Ý)...)
                    tag_pattern = re.compile(
                        r"(\[[A-Za-zÀ-ỹ0-9_\-\s/&\+()]+\]|\(CHÚ Ý\)\s*:?|(?:Params/Body|Params|Response|Errors|Tech note|Key Columns|PK/FK|Status Lifecycle|Đề xuất)\s*:)",
                        re.IGNORECASE,
                    )
                    for tm in tag_pattern.finditer(text_to_insert):
                        t_start = insert_pos + tm.start(1)
                        t_end = insert_pos + tm.end(1)
                        up_tag = tm.group(1).upper()
                        if "CHÚ Ý" in up_tag or "ERROR" in up_tag or "RỦI RO" in up_tag or "CHƯA RÕ" in up_tag:
                            t_rgb = {"red": 0.706, "green": 0.325, "blue": 0.035}
                        elif "Q&A" in up_tag or "ĐỀ XUẤT" in up_tag:
                            t_rgb = {"red": 0.486, "green": 0.227, "blue": 0.929}
                        else:
                            t_rgb = {"red": 0.118, "green": 0.251, "blue": 0.686}
                        requests.append(
                            {
                                "updateTextStyle": {
                                    "range": {"startIndex": t_start, "endIndex": t_end},
                                    "textStyle": {
                                        "weightedFontFamily": {"fontFamily": FONT_NAME},
                                        "bold": True,
                                        "foregroundColor": {"color": {"rgbColor": t_rgb}},
                                    },
                                    "fields": "weightedFontFamily,bold,foregroundColor",
                                }
                            }
                        )

                    self.docs.documents().batchUpdate(
                        documentId=doc_id,
                        body={"requests": requests},
                    ).execute()
                except Exception as e:
                    LOGGER.warning("Lỗi ghi nội dung vào Google Doc phân tích: %s", e)

            return copied.get("webViewLink") or f"https://docs.google.com/document/d/{doc_id}/edit"

    def create_testcase_sheet(self, task_name: str, testcases: list[dict[str, Any]]) -> str:
        """
        Tạo Google Sheet Testcase bằng cách COPY TRỰC TIẾP từ file Template gốc (TEMPLATE_TC_SHEET_ID):
        - Giữ nguyên 100% phần đầu (dòng 1..13) VÀ giữ nguyên 100% câu lệnh tự sinh ID Testcase ở cột A!
        - Chỉ ghi đúng 3 cột B (Mục đích kiểm thử), C (Các bước thực hiện), D (Kết quả mong muốn) từ dòng 14 (B14:D).
        - Đặt Font chữ Sarabun cho toàn bộ dữ liệu và bôi chữ đậm dòng Test Suite để phân biệt với Test con.
        - Nhân bản (duplicateSheet) chính Sheet Template gốc ra các Sheet con theo từng chức năng.
        """
        with self._mutation_lock:
            parent_folder_id = self._ensure_task_drive_folder(task_name)

            body: dict[str, Any] = {"name": f"[TC] {task_name}"}
            if parent_folder_id:
                body["parents"] = [parent_folder_id]
            copied = (
                self.drive.files()
                .copy(
                    fileId=TEMPLATE_TC_SHEET_ID,
                    body=body,
                    fields="id,webViewLink",
                    supportsAllDrives=True,
                )
                .execute()
            )
            sheet_id = copied["id"]

            try:
                self.drive.permissions().create(
                    fileId=sheet_id,
                    body={"type": "anyone", "role": "reader"},
                    fields="id",
                    supportsAllDrives=True,
                ).execute()
            except Exception:
                pass

            grouped_suites = _group_testcases_by_suite(testcases or [])
            if not grouped_suites:
                return copied.get("webViewLink") or f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"

            try:
                meta = self.sheets.spreadsheets().get(spreadsheetId=sheet_id).execute()
                sheets_info = meta.get("sheets") or []
                first_sheet = sheets_info[0] if sheets_info else {}
                first_props = first_sheet.get("properties", {})
                master_sheet_id = int(first_props.get("sheetId", 0))
                master_title = str(first_props.get("title") or "Trang tính1")
                cond_rules_count = len(first_sheet.get("conditionalFormats") or [])
            except Exception:
                master_sheet_id = 0
                master_title = "Trang tính1"
                cond_rules_count = 0

            used_titles: set[str] = set()
            child_specs: list[tuple[int, str, str, list[dict[str, Any]]]] = []
            setup_requests: list[dict[str, Any]] = []

            # Xóa bỏ Conditional Formatting tự động có sẵn trên Sheet Template (vì Tool sẽ trực tiếp bôi màu dòng Test Suite)
            for rule_idx in range(cond_rules_count - 1, -1, -1):
                setup_requests.append(
                    {
                        "deleteConditionalFormatRule": {
                            "sheetId": master_sheet_id,
                            "index": rule_idx,
                        }
                    }
                )

            if len(grouped_suites) == 1:
                # Chỉ có 1 chức năng: Đổi tên trực tiếp tab đầu tiên thành tên chức năng đó (không nhân bản thành 2 trang giống nhau)
                only_suite_name, _ = grouped_suites[0]
                master_title = _clean_excel_sheet_title(only_suite_name, 1, used_titles)
                setup_requests.append(
                    {
                        "updateSheetProperties": {
                            "properties": {
                                "sheetId": master_sheet_id,
                                "title": master_title,
                            },
                            "fields": "title",
                        }
                    }
                )
            else:
                # Có từ 2 chức năng trở lên: Đổi tên tab đầu thành 'Tổng hợp' và nhân bản các tab chức năng con
                master_title = "Tổng hợp"
                used_titles.add(master_title.lower())
                setup_requests.append(
                    {
                        "updateSheetProperties": {
                            "properties": {
                                "sheetId": master_sheet_id,
                                "title": master_title,
                            },
                            "fields": "title",
                        }
                    }
                )
                for s_idx, (suite_name, suite_tcs) in enumerate(grouped_suites, start=1):
                    new_sheet_id = 1000 + s_idx
                    child_title = _clean_excel_sheet_title(suite_name, s_idx, used_titles)
                    child_specs.append((new_sheet_id, child_title, suite_name, suite_tcs))
                    setup_requests.append(
                        {
                            "duplicateSheet": {
                                "sourceSheetId": master_sheet_id,
                                "insertSheetIndex": s_idx,
                                "newSheetId": new_sheet_id,
                                "newSheetName": child_title,
                            }
                        }
                    )

            if setup_requests:
                try:
                    self.sheets.spreadsheets().batchUpdate(
                        spreadsheetId=sheet_id,
                        body={"requests": setup_requests},
                    ).execute()
                except Exception as dup_err:
                    LOGGER.warning("Không thể đổi tên / nhân bản các sheet chức năng: %s", dup_err)
                    child_specs = []

            def build_bcd_rows_and_suite_indices(
                suites_list: list[tuple[str, list[dict[str, Any]]]],
            ) -> tuple[list[list[str]], list[int]]:
                """Chỉ sinh đúng 3 cột B (Mục đích), C (Các bước), D (Kết quả mong muốn) bắt đầu từ dòng 15 (index 14)."""
                rows_data: list[list[str]] = []
                suite_row_indices: list[int] = []  # 0-based index trên Google Sheet (dòng 15 là index 14)
                curr_zero_idx = 14
                for s_name, s_tcs in suites_list:
                    suite_row_indices.append(curr_zero_idx)
                    rows_data.append([s_name, "", ""])
                    curr_zero_idx += 1
                    for tc in s_tcs:
                        rows_data.append(
                            [
                                str(tc.get("muc_dich") or "").strip(),
                                str(tc.get("cac_buoc") or "").strip(),
                                str(tc.get("ket_qua_mong_muon") or "").strip(),
                            ]
                        )
                        curr_zero_idx += 1
                return rows_data, suite_row_indices

            value_data_entries: list[dict[str, Any]] = []
            style_requests: list[dict[str, Any]] = []

            def make_sheet_style_requests(target_sheet_id: int, total_rows: int, suite_indices: list[int]) -> list[dict[str, Any]]:
                reqs: list[dict[str, Any]] = [
                    {
                        # Đặt font Sarabun và nền trắng mặc định cho toàn bộ vùng dữ liệu từ dòng 15 (index 14)
                        "repeatCell": {
                            "range": {
                                "sheetId": target_sheet_id,
                                "startRowIndex": 14,
                                "endRowIndex": 14 + total_rows,
                                "startColumnIndex": 0,
                                "endColumnIndex": 20,
                            },
                            "cell": {
                                "userEnteredFormat": {
                                    "backgroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0},
                                    "textFormat": {
                                        "fontFamily": FONT_NAME,
                                    },
                                }
                            },
                            "fields": "userEnteredFormat(backgroundColor,textFormat.fontFamily)",
                        }
                    },
                    {
                        # Căn lề trên (TOP) và ngắt dòng (WRAP) cho 3 cột B, C, D để chữ không bị tụt xuống đáy ô
                        "repeatCell": {
                            "range": {
                                "sheetId": target_sheet_id,
                                "startRowIndex": 14,
                                "endRowIndex": 14 + total_rows,
                                "startColumnIndex": 1,
                                "endColumnIndex": 4,
                            },
                            "cell": {
                                "userEnteredFormat": {
                                    "verticalAlignment": "TOP",
                                    "wrapStrategy": "WRAP",
                                    "textFormat": {
                                        "fontFamily": FONT_NAME,
                                        "bold": False,
                                    },
                                }
                            },
                            "fields": "userEnteredFormat(verticalAlignment,wrapStrategy,textFormat.fontFamily,textFormat.bold)",
                        }
                    },
                ]
                for r_idx in suite_indices:
                    reqs.append(
                        {
                            # Tool trực tiếp bôi màu vàng (#FFE599) + chữ In đậm Sarabun cho dòng Test Suite (từ cột A đến cột T)
                            "repeatCell": {
                                "range": {
                                    "sheetId": target_sheet_id,
                                    "startRowIndex": r_idx,
                                    "endRowIndex": r_idx + 1,
                                    "startColumnIndex": 0,
                                    "endColumnIndex": 20,
                                },
                                "cell": {
                                    "userEnteredFormat": {
                                        "backgroundColor": {"red": 1.0, "green": 0.898, "blue": 0.6},
                                        "verticalAlignment": "MIDDLE",
                                        "textFormat": {
                                            "fontFamily": FONT_NAME,
                                            "bold": True,
                                            "foregroundColor": {"red": 0.0, "green": 0.0, "blue": 0.0},
                                        },
                                    }
                                },
                                "fields": "userEnteredFormat(backgroundColor,verticalAlignment,textFormat.fontFamily,textFormat.bold,textFormat.foregroundColor)",
                            }
                        }
                    )
                return reqs

            # 1. Ghi C3 (Tên chức năng), C4 ('TC') và 3 cột B15:D cho Sheet đầu tiên
            master_suites_to_write = (
                _organize_subsuites_for_sheet(grouped_suites[0][0], grouped_suites[0][1])
                if len(grouped_suites) == 1
                else grouped_suites
            )
            master_screen_name = grouped_suites[0][0] if len(grouped_suites) == 1 else task_name
            master_rows, master_suite_idxs = build_bcd_rows_and_suite_indices(master_suites_to_write)
            escaped_master = master_title.replace("'", "''")
            value_data_entries.append(
                {
                    "range": f"'{escaped_master}'!C3:C4",
                    "values": [[master_screen_name], ["TC"]],
                }
            )
            if master_rows:
                value_data_entries.append(
                    {
                        "range": f"'{escaped_master}'!B15:D{14 + len(master_rows)}",
                        "values": master_rows,
                    }
                )
                style_requests.extend(make_sheet_style_requests(master_sheet_id, len(master_rows), master_suite_idxs))

            # 2. Ghi C3, C4 và 3 cột B15:D cho từng Sheet con (nếu bài toán có >= 2 chức năng)
            for c_sheet_id, c_title, s_name, s_tcs in child_specs:
                sub_suites = _organize_subsuites_for_sheet(s_name, s_tcs)
                c_rows, c_suite_idxs = build_bcd_rows_and_suite_indices(sub_suites)
                escaped_child = c_title.replace("'", "''")
                value_data_entries.append(
                    {
                        "range": f"'{escaped_child}'!C3:C4",
                        "values": [[s_name], ["TC"]],
                    }
                )
                if c_rows:
                    value_data_entries.append(
                        {
                            "range": f"'{escaped_child}'!B15:D{14 + len(c_rows)}",
                            "values": c_rows,
                        }
                    )
                    style_requests.extend(make_sheet_style_requests(c_sheet_id, len(c_rows), c_suite_idxs))

            if value_data_entries:
                try:
                    self.sheets.spreadsheets().values().batchUpdate(
                        spreadsheetId=sheet_id,
                        body={
                            "valueInputOption": "USER_ENTERED",
                            "data": value_data_entries,
                        },
                    ).execute()
                except Exception as val_err:
                    LOGGER.warning("Lỗi ghi dữ liệu vào Google Sheet Testcase: %s", val_err)

            if style_requests:
                try:
                    self.sheets.spreadsheets().batchUpdate(
                        spreadsheetId=sheet_id,
                        body={"requests": style_requests},
                    ).execute()
                except Exception as st_err:
                    LOGGER.warning("Lỗi bôi chữ dòng Test Suite trên Google Sheet: %s", st_err)

            return copied.get("webViewLink") or f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"

    def upload_word_bytes_as_doc(self, task_name: str, docx_bytes: bytes, fallback_text: str = "") -> str:
        """
        Đẩy trực tiếp file Word (.docx) từ Folder Local lên Folder Bài toán trên Google Drive
        và chuyển đổi thành Google Docs (mimeType='application/vnd.google-apps.document').
        Nhờ vậy, bản trên Google Docs sẽ giống hệt 100% bản Word (.docx) ở Local:
        giữ nguyên Trang bìa gốc, Bảng thông tin tổng quan, MỤC LỤC TÀI LIỆU, các Bảng biểu và Font chữ Sarabun.
        """
        with self._mutation_lock:
            parent_folder_id = self._ensure_task_drive_folder(task_name)
            if not docx_bytes and fallback_text:
                docx_bytes = build_analysis_word_bytes(task_name, fallback_text)

            if docx_bytes:
                try:
                    metadata: dict[str, Any] = {
                        "name": f"Phân tích bài toán - {task_name}",
                        "mimeType": "application/vnd.google-apps.document",
                    }
                    if parent_folder_id:
                        metadata["parents"] = [parent_folder_id]

                    media = MediaIoBaseUpload(
                        io.BytesIO(docx_bytes),
                        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
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
                    doc_id = uploaded["id"]
                    try:
                        self.drive.permissions().create(
                            fileId=doc_id,
                            body={"type": "anyone", "role": "reader"},
                            fields="id",
                            supportsAllDrives=True,
                        ).execute()
                    except Exception:
                        pass
                    return uploaded.get("webViewLink") or f"https://docs.google.com/document/d/{doc_id}/edit"
                except Exception as up_err:
                    LOGGER.warning("Không thể convert .docx trực tiếp lên Google Docs, dùng fallback Docs API: %s", up_err)

        return self._create_analysis_doc_via_api(task_name, fallback_text)

    def upload_excel_bytes_as_sheet(self, task_name: str, xlsx_bytes: bytes, fallback_tcs: list[dict[str, Any]] | None = None) -> str:
        """
        Đọc các dòng Test Suite & Test con từ file Excel Local (dòng 14 trở xuống)
        rồi điền vào bản copy của Template gốc (TEMPLATE_TC_SHEET_ID) trên Google Sheets
        kèm phân trang sheet theo chức năng và bôi chữ dòng Test Suite.
        """
        parsed_rows: list[dict[str, Any]] = []
        try:
            parsed_rows = read_testcases_from_local_excel(io.BytesIO(xlsx_bytes))
        except Exception as err:
            LOGGER.warning("Không thể đọc dòng từ Excel local, dùng fallback_tcs: %s", err)
        return self.create_testcase_sheet(task_name, parsed_rows or fallback_tcs or [])
