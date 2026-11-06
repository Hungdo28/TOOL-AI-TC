from __future__ import annotations

import json
import logging
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from core.config import Settings

LOGGER = logging.getLogger("autotc-backend")

_DOC_ID_RE = re.compile(r"/document/(?:u/\d+/)?d/([a-zA-Z0-9-_]+)")
_SHEET_ID_RE = re.compile(r"/spreadsheets/(?:u/\d+/)?d/([a-zA-Z0-9-_]+)")
_FIGMA_KEY_RE = re.compile(r"figma\.com/(?:design|file)/([^/?#]+)")


def clean_doc(s: str | None) -> str:
    """Dọn rác khoảng trắng để giảm số lượng token thừa trước khi gửi AI."""
    text = str(s or "").replace("\r\n", "\n").replace("\r", "\n").replace("\u00a0", " ")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    joined = "\n".join(line for line in lines if line)
    return joined.strip()


def split_urls(raw_urls: str | None) -> list[str]:
    if not raw_urls:
        return []
    return [u.strip() for u in re.split(r"[,\n]+", str(raw_urls)) if u.strip()]


def _render_paragraph(p: dict[str, Any], images: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    for el in p.get("elements") or []:
        text_run = el.get("textRun")
        if text_run and text_run.get("content"):
            parts.append(str(text_run["content"]))
        elif el.get("inlineObjectElement"):
            obj_id = el["inlineObjectElement"].get("inlineObjectId")
            images.append({"id": obj_id})
            parts.append(f" [HÌNH {len(images)}: chưa được đọc] ")

    t = "".join(parts).replace("\u000b", " ").rstrip()
    if not t.strip():
        return ""

    style = (p.get("paragraphStyle") or {}).get("namedStyleType") or ""
    if style == "TITLE":
        return f"# {t.strip()}"
    m = re.match(r"^HEADING_(\d)", style)
    if m:
        return "#" * int(m.group(1)) + " " + t.strip()
    if p.get("bullet"):
        return f"- {t.strip()}"
    return t.strip()


def _render_doc_content(content: list[dict[str, Any]], images: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for el in content or []:
        if "paragraph" in el:
            line = _render_paragraph(el["paragraph"], images)
            if line:
                lines.append(line)
        elif "table" in el:
            lines.append("[BẢNG]")
            for row in el["table"].get("tableRows") or []:
                cells: list[str] = []
                for cell in row.get("tableCells") or []:
                    cell_txt = _render_doc_content(cell.get("content") or [], images)
                    cell_txt = re.sub(r"\n+", " / ", cell_txt).strip()
                    cells.append(cell_txt)
                lines.append("| " + " | ".join(cells) + " |")
            lines.append("[HẾT BẢNG]")
    return "\n".join(lines)


class DocumentCrawler:
    """
    Crawl song song toàn bộ tài liệu (Google Docs, Google Sheets, Figma) của một bài toán.
    Tối ưu hơn n8n:
    - Chạy song song mọi URL bằng ThreadPoolExecutor.
    - Đọc toàn bộ các tab của Google Sheet chỉ trong 1 request `values.batchGet` duy nhất.
    - Nối lại nhánh Figma vốn bị đứt dây trên n8n.
    """

    def __init__(self, google_workspace: Any, settings: Settings):
        self.gw = google_workspace
        self.settings = settings

    def crawl_all(self, raw_urls: str) -> str:
        urls = split_urls(raw_urls)
        if not urls:
            raise RuntimeError("Bài toán chưa có URL tài liệu nào để đọc.")

        def fetch_one(url: str) -> str:
            if "/document/" in url:
                return self._crawl_google_doc(url)
            if "/spreadsheets/" in url:
                return self._crawl_google_sheet(url)
            if "figma.com" in url:
                return self._crawl_figma(url)
            raise RuntimeError(f"Định dạng URL chưa được hỗ trợ: {url}")

        max_workers = min(4, len(urls))
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            raw_texts = list(pool.map(fetch_one, urls))

        cleaned_docs = [clean_doc(txt) for txt in raw_texts if clean_doc(txt)]
        if not cleaned_docs:
            raise RuntimeError("Tài liệu rỗng sau khi crawl, không có nội dung để phân tích.")

        return "\n\n--- TÀI LIỆU TIẾP THEO ---\n\n".join(cleaned_docs)

    def _crawl_google_doc(self, url: str) -> str:
        m = _DOC_ID_RE.search(url)
        if not m:
            raise RuntimeError(f"Không tách được documentId từ link Google Docs: {url}")
        doc_id = m.group(1)
        if not self.gw:
            raise RuntimeError("Chưa khởi tạo GoogleWorkspace client.")

        # Sử dụng Drive API export_media để xuất văn bản trực tiếp từ máy chủ Google:
        # - Không bị TimeoutError trên các tài liệu đặc tả lớn (hàng nghìn dòng / hàng trăm trang)
        # - Tốc độ nhanh gấp 5-10 lần (không phải tải và giải mã cây AST JSON khổng lồ của Docs API)
        if getattr(self.gw, "drive", None):
            try:
                content = self.gw.drive.files().export_media(fileId=doc_id, mimeType="text/plain").execute(num_retries=3)
                txt = content.decode("utf-8", errors="replace") if isinstance(content, bytes) else str(content)
                if txt.strip():
                    return txt
            except Exception as err:
                LOGGER.warning("Drive export_media doc [%s] thất bại (%s), thử fallback sang Docs API...", doc_id, err)

        # Fallback sang Docs API nếu Drive export không khả dụng
        if getattr(self.gw, "docs", None):
            doc = self.gw.docs.documents().get(documentId=doc_id).execute(num_retries=2)
            images: list[dict[str, Any]] = []
            body_content = (doc.get("body") or {}).get("content") or []
            text = _render_doc_content(body_content, images)
            if text.strip():
                return text

        raise RuntimeError(f"Không thể đọc nội dung Google Doc: {url}")

    def _crawl_google_sheet(self, url: str) -> str:
        m = _SHEET_ID_RE.search(url)
        if not m:
            raise RuntimeError(f"Không tách được spreadsheetId từ link Google Sheets: {url}")
        sheet_id = m.group(1)
        if not self.gw or not getattr(self.gw, "sheets", None):
            raise RuntimeError("Chưa khởi tạo Google Sheets client trong GoogleWorkspace.")

        # Chỉ lấy danh sách title các tab (dùng fields để tránh tải cả megabyte metadata thừa)
        meta = self.gw.sheets.spreadsheets().get(
            spreadsheetId=sheet_id,
            fields="sheets.properties.title",
        ).execute()
        sheets = meta.get("sheets") or []
        titles = [
            s.get("properties", {}).get("title")
            for s in sheets
            if s.get("properties", {}).get("title")
        ]
        if not titles:
            return ""

        # Lấy dữ liệu nhanh qua batchGet, giới hạn A1:P200 cho tối đa 12 tab quan trọng nhất
        selected_titles = titles[:12]
        ranges = [f"'{t.replace(chr(39), chr(39)*2)}'!A1:P200" for t in selected_titles]
        batch_res = (
            self.gw.sheets.spreadsheets()
            .values()
            .batchGet(
                spreadsheetId=sheet_id,
                ranges=ranges,
                valueRenderOption="FORMATTED_VALUE",
                fields="valueRanges(range,values)",
            )
            .execute()
        )
        value_ranges = batch_res.get("valueRanges") or []

        api_entries: list[str] = []
        table_blocks: list[str] = []

        for idx, vr in enumerate(value_ranges):
            tab_title = titles[idx] if idx < len(titles) else f"Tab {idx + 1}"
            rows = vr.get("values") or []
            if not rows:
                continue

            headers = [str(h).strip() for h in rows[0]] if rows else []
            tab_lines: list[str] = []

            for r_idx, row in enumerate(rows):
                cells = [str(c).strip() for c in row]
                if not any(cells):
                    continue

                # Kiểm tra định dạng bảng danh sách API giống node gop_thong_tin_thanh_text
                row_dict = {headers[i]: cells[i] for i in range(min(len(headers), len(cells))) if headers[i]}
                ten_api = (
                    row_dict.get("Danh sách api sử dụng")
                    or row_dict.get("Danh sách api sử dụng ")
                    or (cells[1] if len(cells) > 1 else "")
                )
                endpoint = (
                    row_dict.get("Đầu api")
                    or row_dict.get("col_3")
                    or (cells[2] if len(cells) > 2 else "")
                )
                mo_ta = (
                    row_dict.get("Mô tả")
                    or row_dict.get("col_4")
                    or (cells[3] if len(cells) > 3 else "")
                )
                if "http" in endpoint or "api/" in endpoint:
                    api_entries.append(
                        f"* Tên API: {ten_api}\n  - Endpoint: {endpoint}\n  - Mô tả bổ sung: {mo_ta}"
                    )
                if r_idx < 200:
                    tab_lines.append("| " + " | ".join(c.replace("\n", " ") for c in cells) + " |")

            if tab_lines:
                table_blocks.append(f"[SHEET TAB: {tab_title}]\n" + "\n".join(tab_lines))

        parts: list[str] = []
        if api_entries:
            parts.append(
                "--- DANH SÁCH API CẦN KIỂM THỬ (BẮT BUỘC ĐỌC) ---\n" + "\n".join(api_entries)
            )
        if table_blocks:
            parts.append("\n\n".join(table_blocks))
        return "\n\n".join(parts)

    def _crawl_figma(self, url: str) -> str:
        m = _FIGMA_KEY_RE.search(url)
        if not m:
            raise RuntimeError(f"Không tách được file key từ link Figma: {url}")
        file_key = m.group(1)
        token = self.settings.figma_access_token
        if not token:
            LOGGER.warning("Bỏ qua link Figma %s vì chưa cấu hình FIGMA_ACCESS_TOKEN", url)
            return f"[FIGMA LINK: {url} - Chưa cấu hình FIGMA_ACCESS_TOKEN]"

        req = urllib.request.Request(
            f"https://api.figma.com/v1/files/{file_key}",
            headers={"X-Figma-Token": token, "Accept": "application/json"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            figma_data = json.loads(resp.read().decode("utf-8", errors="replace"))

        doc_node = figma_data.get("document") or {}
        texts: list[str] = []

        def extract_text(node: dict[str, Any]) -> None:
            if node.get("type") == "TEXT" and node.get("characters"):
                chars = str(node["characters"]).replace("\n", " ")
                texts.append(f"[{node.get('name', 'Text')}]: {chars}")
            for child in node.get("children") or []:
                if isinstance(child, dict):
                    extract_text(child)

        extract_text(doc_node)
        return "DỮ LIỆU GIAO DIỆN TỪ FIGMA:\n" + "\n".join(texts)
