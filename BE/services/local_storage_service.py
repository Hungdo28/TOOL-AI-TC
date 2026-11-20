from __future__ import annotations

import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any

from services.common import ApiError
from services.document_builder import (
    build_analysis_word_bytes,
    build_testcase_excel_bytes,
    ensure_word_file_has_toc,
)

LOGGER = logging.getLogger("autotc-backend")


class LocalStorageService:
    """
    Quản lý truy cập, tự động tạo thư mục (folder) và sinh bản ghi (records)
    trực tiếp trên máy cá nhân một cách an toàn (sandboxed trong root_dir).
    """

    def __init__(self, root_dir: str | Path):
        primary_dir = Path(root_dir).resolve()
        try:
            primary_dir.mkdir(parents=True, exist_ok=True)
            self.root_dir = primary_dir
        except OSError as err:
            fallback_dir = (Path(__file__).resolve().parents[2] / "AutoTC_Records").resolve()
            fallback_dir.mkdir(parents=True, exist_ok=True)
            LOGGER.warning(
                "Không thể tạo thư mục '%s' (%s). Tự động chuyển sang thư mục dự phòng: %s",
                primary_dir,
                err,
                fallback_dir,
            )
            self.root_dir = fallback_dir

    def _resolve_safe_path(self, relative_path: str = "") -> Path:
        """
        Đảm bảo mọi thao tác đọc/tạo folder/ghi file chỉ diễn ra bên trong self.root_dir.
        Chặn tuyệt đối lỗi leo thang thư mục (../) hoặc nhảy sang thư mục hệ thống khác.
        """
        raw = str(relative_path or "").strip()
        if not raw or raw in {".", "/", "\\"}:
            return self.root_dir

        # Chuẩn hóa các phần của đường dẫn, loại bỏ ký tự cấm trên Windows cho từng cấp thư mục
        parts = [p for p in re.split(r"[/\\]+", raw) if p and p != "."]
        if any(p == ".." for p in parts):
            raise ApiError(400, "Truy cập bị từ chối: Không cho phép dùng '..' trong đường dẫn.")

        safe_parts = [self.sanitize_name(p) for p in parts]
        target = (self.root_dir.joinpath(*safe_parts)).resolve()

        try:
            target.relative_to(self.root_dir)
        except ValueError:
            raise ApiError(400, "Truy cập bị từ chối: Đường dẫn nằm ngoài thư mục cho phép trên máy!")

        return target

    @staticmethod
    def sanitize_name(name: str) -> str:
        """Làm sạch tên folder/file để hợp lệ trên Windows/macOS/Linux."""
        cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", str(name or "").strip())
        cleaned = cleaned.strip(". ")
        return cleaned[:100] or "unnamed"

    def list_folder(self, relative_dir: str = "") -> dict[str, Any]:
        """Liệt kê danh sách các folder và file bản ghi trong thư mục chỉ định."""
        target_dir = self._resolve_safe_path(relative_dir)
        self.root_dir.mkdir(parents=True, exist_ok=True)

        if not target_dir.exists():
            return {
                "success": True,
                "rootDir": str(self.root_dir),
                "currentDir": str(target_dir),
                "relativeDir": str(relative_dir or ""),
                "items": [],
            }

        if not target_dir.is_dir():
            raise ApiError(400, "Đường dẫn chỉ định không phải là một thư mục.")

        items: list[dict[str, Any]] = []
        for entry in sorted(target_dir.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            stat = entry.stat()
            items.append(
                {
                    "name": entry.name,
                    "type": "folder" if entry.is_dir() else "file",
                    "relativePath": str(entry.relative_to(self.root_dir)).replace("\\", "/"),
                    "fullPath": str(entry.resolve()),
                    "sizeBytes": 0 if entry.is_dir() else stat.st_size,
                    "updatedAt": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime)),
                }
            )

        return {
            "success": True,
            "rootDir": str(self.root_dir),
            "currentDir": str(target_dir),
            "relativeDir": str(target_dir.relative_to(self.root_dir)).replace("\\", "/")
            if target_dir != self.root_dir
            else "",
            "items": items,
        }

    def create_folder(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Tự động tạo mới một hoặc nhiều cấp folder trong thư mục gốc."""
        folder = str(payload.get("folder") or payload.get("path") or "").strip()
        if not folder:
            raise ApiError(400, "Vui lòng truyền tên hoặc đường dẫn folder cần tạo.")

        target_dir = self._resolve_safe_path(folder)
        target_dir.mkdir(parents=True, exist_ok=True)
        LOGGER.info("[LocalStorage] Đã tạo/mở folder: %s", target_dir)

        return {
            "success": True,
            "message": "Đã tạo thư mục thành công.",
            "rootDir": str(self.root_dir),
            "folderPath": str(target_dir),
            "relativePath": str(target_dir.relative_to(self.root_dir)).replace("\\", "/"),
        }

    def save_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        """
        Tự động tạo folder (nếu chưa có) và sinh ra file bản ghi trong folder đó.
        Hỗ trợ ghi đè hoặc ghi nối tiếp (append=True).
        """
        folder = str(payload.get("folder") or "").strip()
        file_name = str(payload.get("fileName") or payload.get("filename") or "").strip()
        content = payload.get("content")
        append_mode = bool(payload.get("append", False))

        if not file_name:
            raise ApiError(400, "Thiếu tên file bản ghi (fileName).")
        if content is None:
            raise ApiError(400, "Thiếu nội dung bản ghi (content).")

        target_dir = self._resolve_safe_path(folder)
        target_dir.mkdir(parents=True, exist_ok=True)

        safe_file = self.sanitize_name(Path(file_name).name)
        if "." not in safe_file:
            safe_file = f"{safe_file}.json" if isinstance(content, (dict, list)) else f"{safe_file}.txt"

        file_path = (target_dir / safe_file).resolve()
        try:
            file_path.relative_to(self.root_dir)
        except ValueError:
            raise ApiError(400, "Tên file không hợp lệ.")

        if isinstance(content, (dict, list)):
            text_content = json.dumps(content, ensure_ascii=False, indent=2)
        else:
            text_content = str(content)

        if append_mode and file_path.exists():
            existing = file_path.read_text(encoding="utf-8")
            sep = "" if existing.endswith("\n") else "\n"
            file_path.write_text(f"{existing}{sep}{text_content}\n", encoding="utf-8")
        else:
            file_path.write_text(text_content, encoding="utf-8")

        LOGGER.info("[LocalStorage] Đã lưu bản ghi tại: %s", file_path)
        return {
            "success": True,
            "message": "Đã tạo folder và lưu bản ghi thành công.",
            "rootDir": str(self.root_dir),
            "folderPath": str(target_dir),
            "filePath": str(file_path),
            "relativePath": str(file_path.relative_to(self.root_dir)).replace("\\", "/"),
        }

    def read_record(self, relative_path: str) -> dict[str, Any]:
        """Đọc nội dung một bản ghi có sẵn trong folder trên máy."""
        if not relative_path:
            raise ApiError(400, "Thiếu đường dẫn file cần đọc (path).")

        file_path = self._resolve_safe_path(relative_path)
        if not file_path.exists() or not file_path.is_file():
            raise ApiError(404, f"Không tìm thấy bản ghi: {relative_path}")

        raw_text = file_path.read_text(encoding="utf-8")
        parsed_json = None
        if file_path.suffix.lower() == ".json":
            try:
                parsed_json = json.loads(raw_text)
            except Exception:
                parsed_json = None

        return {
            "success": True,
            "filePath": str(file_path),
            "relativePath": str(file_path.relative_to(self.root_dir)).replace("\\", "/"),
            "content": parsed_json if parsed_json is not None else raw_text,
            "rawText": raw_text,
        }

    # =========================================================================
    # TỰ ĐỘNG TẠO FOLDER THEO TÊN BÀI TOÁN & SINH SHEET TC (.XLSX) + WORD (.DOCX)
    # =========================================================================
    def save_binary_file(self, folder: str, file_name: str, data: bytes) -> dict[str, Any]:
        """Tự động tạo folder theo tên bài toán (nếu chưa có) và lưu file nhị phân (.xlsx, .docx)."""
        target_dir = self._resolve_safe_path(folder)
        target_dir.mkdir(parents=True, exist_ok=True)
        safe_file = self.sanitize_name(Path(file_name).name)
        file_path = (target_dir / safe_file).resolve()
        try:
            file_path.relative_to(self.root_dir)
        except ValueError:
            raise ApiError(400, "Tên file không hợp lệ.")

        # Nếu file đang được mở trong Excel/Word trên máy (PermissionError), tự lưu kèm hậu tố thời gian để không lỗi
        try:
            file_path.write_bytes(data)
        except PermissionError:
            stem = file_path.stem
            suffix = file_path.suffix
            alt_name = f"{stem}_{time.strftime('%H%M%S')}{suffix}"
            file_path = (target_dir / alt_name).resolve()
            file_path.write_bytes(data)

        LOGGER.info("[LocalStorage] Đã xuất tài liệu tại: %s", file_path)
        return {
            "folderPath": str(target_dir),
            "filePath": str(file_path),
            "relativePath": str(file_path.relative_to(self.root_dir)).replace("\\", "/"),
        }

    def save_analysis_word(
        self,
        task_title: str,
        analysis_text: str,
        *,
        testcase_count: int = 0,
    ) -> dict[str, Any]:
        """Tự tạo folder theo tên bài toán và sinh file Word Báo cáo phân tích (.docx) chuẩn đẹp."""
        folder_name = self.sanitize_name(task_title)
        safe_title = self.sanitize_name(task_title)
        docx_bytes = build_analysis_word_bytes(
            task_title,
            analysis_text,
            testcase_count=testcase_count,
        )
        return self.save_binary_file(
            folder_name,
            f"Phân tích bài toán - {safe_title}.docx",
            docx_bytes,
        )

    def save_testcase_excel(
        self,
        task_title: str,
        testcases: list[dict[str, Any]],
        *,
        tc_prefix: str = "TC",
    ) -> dict[str, Any]:
        """
        Tự tạo folder theo tên bài toán và sinh file Excel Testcase (.xlsx)
        gồm Sheet Tổng hợp (phân rõ Test Suite & Test con) và các Sheet con theo từng chức năng.
        """
        folder_name = self.sanitize_name(task_title)
        safe_title = self.sanitize_name(task_title)
        xlsx_bytes = build_testcase_excel_bytes(
            task_title,
            testcases,
            tc_prefix=tc_prefix,
        )
        return self.save_binary_file(
            folder_name,
            f"[TC] {safe_title}.xlsx",
            xlsx_bytes,
        )

    def save_pipeline_task_bundle(
        self,
        *,
        task_title: str,
        problem_id: str,
        testcases: list[dict[str, Any]],
        analysis_text: str = "",
        analysis_doc_url: str = "",
        testcase_url: str = "",
        token_usage: dict[str, Any] | None = None,
        tc_prefix: str = "TC",
        skip_excel_if_exists: bool = False,
    ) -> dict[str, Any]:
        """
        Tự động tạo 1 folder đúng theo tên Bài toán khi AI chạy xong, bên trong gồm:
        1. [TC] <Tên bài toán>.xlsx (Sheet Tổng hợp phân rõ Test Suite & Test con + các Sheet chức năng con)
        2. Phân tích bài toán - <Tên bài toán>.docx (Báo cáo phân tích chuẩn đẹp)
        """
        folder_name = self.sanitize_name(task_title)
        safe_title = self.sanitize_name(task_title)
        target_dir = self._resolve_safe_path(folder_name)
        target_dir.mkdir(parents=True, exist_ok=True)

        excel_path = ""
        word_path = ""
        existing_excel = target_dir / f"[TC] {safe_title}.xlsx"

        if skip_excel_if_exists and existing_excel.is_file():
            excel_path = str(existing_excel)
        elif testcases:
            excel_res = self.save_testcase_excel(
                task_title,
                testcases,
                tc_prefix=tc_prefix,
            )
            excel_path = excel_res["filePath"]

        if analysis_text and analysis_text.strip():
            word_res = self.save_analysis_word(
                task_title,
                analysis_text,
                testcase_count=len([t for t in testcases if t.get("row_type") != "suite"]),
            )
            word_path = word_res["filePath"]

        return {
            "folderPath": str(target_dir),
            "excelSheetPath": excel_path,
            "wordDocPath": word_path,
        }

    def get_task_bundle_info(self, task_title: str) -> dict[str, Any]:
        """Lấy thông tin folder và đường dẫn file .xlsx / .docx hiện có của bài toán trong Local."""
        folder_name = self.sanitize_name(task_title)
        target_dir = self._resolve_safe_path(folder_name)
        excel_file: Path | None = None
        word_file: Path | None = None

        if target_dir.exists() and target_dir.is_dir():
            xlsx_list = sorted(
                [p for p in target_dir.glob("*.xlsx") if not p.name.startswith("~$")],
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            docx_list = sorted(
                [p for p in target_dir.glob("*.docx") if not p.name.startswith("~$")],
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if xlsx_list:
                excel_file = xlsx_list[0]
            if docx_list:
                word_file = docx_list[0]
                ensure_word_file_has_toc(word_file, task_title)

        return {
            "exists": target_dir.exists(),
            "folderPath": str(target_dir),
            "excelSheetPath": str(excel_file) if excel_file else "",
            "wordDocPath": str(word_file) if word_file else "",
        }

    def open_task_folder(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Mở trực tiếp cửa sổ Windows Explorer tại folder của bài toán trên máy cá nhân."""
        task_name = str(payload.get("taskName") or payload.get("baiToan") or payload.get("folder") or "").strip()
        target_dir = self._resolve_safe_path(self.sanitize_name(task_name) if task_name else "")
        target_dir.mkdir(parents=True, exist_ok=True)
        try:
            if hasattr(os, "startfile"):
                os.startfile(str(target_dir))  # type: ignore[attr-defined]
            else:
                import subprocess
                subprocess.Popen(["explorer.exe", str(target_dir)])
        except Exception:
            try:
                import subprocess
                subprocess.Popen(["explorer.exe", str(target_dir)])
            except Exception as err:
                LOGGER.warning("Không thể tự mở File Explorer cho %s: %s", target_dir, err)

        info = self.get_task_bundle_info(task_name) if task_name else {"folderPath": str(target_dir)}
        return {
            "success": True,
            "message": f"Đã mở folder bài toán: {target_dir}",
            **info,
        }

    def open_task_file(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Mở trực tiếp file Word (.docx) hoặc Excel (.xlsx) của bài toán bằng ứng dụng mặc định trên máy."""
        task_name = str(payload.get("taskName") or payload.get("baiToan") or payload.get("folder") or "").strip()
        file_type = str(payload.get("fileType") or payload.get("type") or "folder").lower().strip()

        info = self.get_task_bundle_info(task_name) if task_name else {}
        target_path: str | None = None
        if file_type in ("word", "doc", "docx"):
            target_path = info.get("wordDocPath")
        elif file_type in ("excel", "sheet", "xlsx"):
            target_path = info.get("excelSheetPath")
        elif file_type == "folder" or not file_type:
            target_path = info.get("folderPath") or str(self._resolve_safe_path(self.sanitize_name(task_name) if task_name else ""))

        if not target_path or not Path(target_path).exists():
            folder_dir = self._resolve_safe_path(self.sanitize_name(task_name) if task_name else "")
            folder_dir.mkdir(parents=True, exist_ok=True)
            target_path = str(folder_dir)

        opened = False
        try:
            if hasattr(os, "startfile"):
                os.startfile(str(target_path))  # type: ignore[attr-defined]
                opened = True
        except Exception as err:
            LOGGER.warning("Không thể mở file/folder %s: %s", target_path, err)

        return {
            "success": True,
            "opened": opened,
            "targetPath": str(target_path),
            "fileType": file_type,
            "message": f"Đã mở: {Path(target_path).name if target_path else task_name}",
            **info,
        }

    def get_task_file_bytes(self, task_name: str, file_type: str) -> tuple[bytes, str, str]:
        """
        Lấy nội dung nhị phân, mime-type và tên file để phục vụ download/mở trực tiếp từ browser.
        Trả về: (bytes_data, mime_type, file_name)
        """
        info = self.get_task_bundle_info(task_name)
        f_type = (file_type or "").lower().strip()
        target_path_str = ""
        if f_type in ("word", "doc", "docx"):
            target_path_str = info.get("wordDocPath") or ""
            default_mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        elif f_type in ("excel", "sheet", "xlsx"):
            target_path_str = info.get("excelSheetPath") or ""
            default_mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        else:
            raise ApiError(400, f"Loại file không hợp lệ: {file_type}. Chỉ hỗ trợ 'word' hoặc 'excel'.")

        if not target_path_str or not Path(target_path_str).is_file():
            raise ApiError(404, f'Không tìm thấy file {file_type} của bài toán "{task_name}" trong folder local.')

        p = Path(target_path_str)
        content_bytes = p.read_bytes()
        return content_bytes, default_mime, p.name

    def save_autotest_bundle(
        self,
        *,
        task_name: str,
        kind: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Tự động tạo folder theo tên Bài toán và lưu kịch bản/báo cáo AutoTest.
        """
        folder_name = self.sanitize_name(task_name or "AutoTest")
        file_name = f"{kind}.json"
        return self.save_record(
            {
                "folder": folder_name,
                "fileName": file_name,
                "content": data,
            }
        )
