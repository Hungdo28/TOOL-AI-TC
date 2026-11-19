from __future__ import annotations

import io
import json
import logging
import re
import time
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any

import docx
from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls
from docx.shared import Cm, Inches, Pt, RGBColor

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

LOGGER = logging.getLogger("autotc-backend")

# Bảng màu Tab cho các Sheet chức năng con
TAB_COLORS = [
    "2563EB",  # Blue
    "059669",  # Emerald
    "7C3AED",  # Violet
    "D97706",  # Amber
    "0891B2",  # Cyan
    "DB2777",  # Pink
    "4F46E5",  # Indigo
    "65A30D",  # Lime
]


def _clean_excel_sheet_title(raw_title: str, index: int, used_titles: set[str]) -> str:
    """
    Chuẩn hóa tên Sheet con trong Excel (tối đa 31 ký tự, không chứa \\ / ? * : [ ], không trùng lặp).
    """
    cleaned = re.sub(r'[\\/?*:\[\]\x00-\x1f]+', " ", str(raw_title or "").strip())
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" '")
    if not cleaned:
        cleaned = f"Chuc_nang_{index}"

    prefix = f"{index}. "
    max_body = 31 - len(prefix)
    candidate = f"{prefix}{cleaned[:max_body].rstrip()}"

    if candidate.lower() in used_titles:
        suffix = f"_{index}"
        candidate = f"{prefix}{cleaned[: max_body - len(suffix)].rstrip()}{suffix}"

    used_titles.add(candidate.lower())
    return candidate


def _estimate_row_height(texts: list[tuple[str, int]], min_height: float = 28.0, max_height: float = 420.0) -> float:
    """
    Tính chiều cao dòng tự động dựa trên số dòng xuống hàng (\n) và độ rộng cột ước tính.
    texts: danh sách (nội dung, số ký tự trung bình trên 1 dòng của cột đó).
    """
    max_lines = 1
    for text, chars_per_line in texts:
        if not text:
            continue
        lines = 0
        for raw_line in str(text).splitlines() or [""]:
            wrapped = max(1, (len(raw_line) // max(10, chars_per_line)) + 1)
            lines += wrapped
        if lines > max_lines:
            max_lines = lines
    return min(max_height, max(min_height, max_lines * 18.0 + 14.0))


def _group_testcases_by_suite(testcases: list[dict[str, Any]]) -> list[tuple[str, list[dict[str, Any]]]]:
    """
    Nhận danh sách testcases (có thể ở dạng sheet_rows có row_type='suite'|'testcase'
    hoặc danh sách phẳng từ qa_memory) và gom theo từng nhóm chức năng (Test Suite) giữ đúng thứ tự.
    """
    suites: dict[str, list[dict[str, Any]]] = {}
    suite_order: list[str] = []
    current_suite = "Chức năng chung"

    for item in testcases or []:
        if not isinstance(item, dict):
            continue
        row_type = str(item.get("row_type") or "").strip().lower()
        content = item.get("content") if isinstance(item.get("content"), dict) else item

        if row_type == "suite":
            s_name = str(item.get("test_suite") or item.get("muc_dich") or "").strip()
            if s_name:
                current_suite = s_name
                if current_suite not in suites:
                    suites[current_suite] = []
                    suite_order.append(current_suite)
            continue

        suite_name = (
            str(item.get("test_suite") or content.get("test_suite") or current_suite or "Chức năng chung").strip()
            or "Chức năng chung"
        )
        muc_dich = str(content.get("muc_dich") or item.get("muc_dich") or "").strip()
        cac_buoc = str(content.get("cac_buoc") or item.get("cac_buoc") or "").strip()
        ket_qua = str(content.get("ket_qua_mong_muon") or item.get("ket_qua_mong_muon") or "").strip()
        ghi_chu = str(content.get("ghi_chu") or item.get("ghi_chu") or "").strip()
        tc_id = str(content.get("id") or item.get("id") or "").strip()

        if not (muc_dich or cac_buoc or ket_qua):
            continue

        if suite_name not in suites:
            suites[suite_name] = []
            suite_order.append(suite_name)

        suites[suite_name].append(
            {
                "id": tc_id,
                "test_suite": suite_name,
                "muc_dich": muc_dich,
                "cac_buoc": cac_buoc,
                "ket_qua_mong_muon": ket_qua,
                "ghi_chu": ghi_chu,
            }
        )

    return [(s, suites[s]) for s in suite_order if suites.get(s)]


# =============================================================================
# 1. SINH FILE EXCEL TESTCASE (.XLSX) GIỮ NGUYÊN TEMPLATE GỐC (GHI TỪ DÒNG 14)
#    - Chỉ bôi chữ đậm / màu dòng Test Suite để phân biệt với Test con
#    - Phân trang Sheet theo từng chức năng (nhân bản từ chính Sheet Template)
# =============================================================================
TEMPLATE_CACHE_PATH = Path(__file__).resolve().parents[1] / "templates" / "template_testcase.xlsx"
TEMPLATE_DOC_CACHE_PATH = Path(__file__).resolve().parents[1] / "templates" / "template_analysis.docx"
FONT_NAME = "Sarabun"


def _build_fallback_template_workbook() -> openpyxl.Workbook:
    """
    Khởi tạo khung Template dự phòng đúng cấu trúc 13 dòng đầu (dòng 13 là Header A..L)
    trong trường hợp máy chưa tải được file template_testcase.xlsx gốc từ Google Drive.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Trang tính1"
    ws.views.sheetView[0].showGridLines = True

    f_title = Font(name=FONT_NAME, size=14, bold=True, color="1E3A8A")
    f_meta = Font(name=FONT_NAME, size=10, bold=True, color="0F172A")
    f_hdr = Font(name=FONT_NAME, size=10, bold=True, color="FFFFFF")
    fill_hdr = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    s_thin = Side(border_style="thin", color="CBD5E1")
    b_cell = Border(left=s_thin, right=s_thin, top=s_thin, bottom=s_thin)
    al_center = Alignment(horizontal="center", vertical="center", wrap_text=True)

    ws["B2"] = "KỊCH BẢN KIỂM THỬ (TEST CASE TEMPLATE)"
    ws["B2"].font = f_title
    ws["B4"] = "Dự án / Bài toán:"
    ws["B4"].font = f_meta

    # Dòng 13: Header chuẩn 12 cột (A..L) của Template gốc
    headers_row_13 = [
        "ID",
        "Mục đích kiểm thử",
        "Các bước thực hiện",
        "Kết quả mong muốn",
        "Kết quả thực tế",
        "UAT",
        "Prod",
        "Trạng thái",
        "Mức độ",
        "Bug ID",
        "Người thực hiện",
        "Ghi chú",
    ]
    col_widths = [12, 34, 46, 46, 22, 12, 12, 14, 12, 14, 16, 30]
    ws.row_dimensions[13].height = 28
    for c_idx, (h_text, w) in enumerate(zip(headers_row_13, col_widths), start=1):
        ws.column_dimensions[get_column_letter(c_idx)].width = w
        cell = ws.cell(row=13, column=c_idx, value=h_text)
        cell.font = f_hdr
        cell.fill = fill_hdr
        cell.alignment = al_center
        cell.border = b_cell

    # Cột A (từ dòng 14) có sẵn công thức tự sinh ID Testcase khi dòng là Test con (có cả cột B và C)
    f_id = Font(name=FONT_NAME, size=10, bold=False, color="000000")
    for r_i in range(14, 250):
        c_a = ws.cell(
            row=r_i,
            column=1,
            value=f'=IF(OR(B{r_i}="",C{r_i}=""),"", "TC_" & TEXT(COUNTIFS($B$14:B{r_i},"<>",$C$14:C{r_i},"<>"),"00"))',
        )
        c_a.font = f_id
        c_a.alignment = al_center

    return wb


def _ensure_safe_openpyxl_cleanup() -> None:
    """Tránh [WinError 32] trên Windows khi Defender giữ khóa file tạm của openpyxl lúc xóa."""
    import openpyxl.worksheet._writer as _ww

    if getattr(_ww.WorksheetWriter, "_safe_cleanup_patched", False):
        return
    orig_cleanup = _ww.WorksheetWriter.cleanup

    def _safe_cleanup(self) -> None:
        for delay in (0.0, 0.05, 0.1, 0.2):
            if delay:
                time.sleep(delay)
            try:
                orig_cleanup(self)
                return
            except PermissionError:
                continue
            except (FileNotFoundError, ValueError):
                return
        LOGGER.debug("Bỏ qua xóa file tạm openpyxl đang bị Windows khóa: %s", getattr(self, "out", ""))

    _ww.WorksheetWriter.cleanup = _safe_cleanup  # type: ignore[method-assign]
    _ww.WorksheetWriter._safe_cleanup_patched = True  # type: ignore[attr-defined]


def load_template_workbook() -> openpyxl.Workbook:
    """Mở file Template Testcase gốc (nếu đã được đồng bộ về BE/templates/template_testcase.xlsx)."""
    if TEMPLATE_CACHE_PATH.is_file():
        try:
            return openpyxl.load_workbook(TEMPLATE_CACHE_PATH)
        except Exception as err:
            LOGGER.warning("Không thể đọc file template cache %s: %s", TEMPLATE_CACHE_PATH, err)
    return _build_fallback_template_workbook()


def _organize_subsuites_for_sheet(
    suite_name: str,
    suite_tcs: list[dict[str, Any]],
) -> list[tuple[str, list[dict[str, Any]]]]:
    """
    Trong phạm vi 1 Sheet chức năng, phân tách các Testcase con thành các phần Test Suite rõ ràng
    (VD: Kiểm tra Giao diện & Validate dữ liệu vs Kiểm tra Luồng nghiệp vụ & API)
    để luôn nhìn rõ cấu trúc phân cấp: Dòng Test Suite (bôi đậm) -> Các dòng Test con bên dưới.
    """
    if len(suite_tcs) <= 1:
        return [(f"Test Suite: {suite_name}", suite_tcs)]

    ui_val_tcs: list[dict[str, Any]] = []
    api_flow_tcs: list[dict[str, Any]] = []
    sec_edge_tcs: list[dict[str, Any]] = []

    for tc in suite_tcs:
        text = f"{tc.get('muc_dich', '')} {tc.get('cac_buoc', '')}".lower()
        if any(k in text for k in ("bảo mật", "phân quyền", "token", "timeout", "mất mạng", "đồng thời", "duplicate", "trùng")):
            sec_edge_tcs.append(tc)
        elif any(k in text for k in ("api", "endpoint", "request", "response", "db", "database", "luồng", "trạng thái")):
            api_flow_tcs.append(tc)
        else:
            ui_val_tcs.append(tc)

    non_empty_buckets = [b for b in (ui_val_tcs, api_flow_tcs, sec_edge_tcs) if b]
    if len(non_empty_buckets) <= 1:
        return [(f"Test Suite: {suite_name}", suite_tcs)]

    result: list[tuple[str, list[dict[str, Any]]]] = []
    idx = 1
    if ui_val_tcs:
        result.append((f"Test Suite {idx}: Kiểm tra Giao diện & Ràng buộc dữ liệu ({suite_name})", ui_val_tcs))
        idx += 1
    if api_flow_tcs:
        result.append((f"Test Suite {idx}: Kiểm tra Luồng nghiệp vụ & Tích hợp API ({suite_name})", api_flow_tcs))
        idx += 1
    if sec_edge_tcs:
        result.append((f"Test Suite {idx}: Kiểm tra Ngoại lệ, Bảo mật & Phân quyền ({suite_name})", sec_edge_tcs))
    return result


_OOXML_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_OOXML_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_OOXML_PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def _inject_cached_formula_values_xlsx(
    xlsx_bytes: bytes,
    sheet_caches: dict[str, dict[str, str | int | float]],
) -> bytes:
    """
    Điền sẵn giá trị tính toán (<v>) vào XML của các ô công thức trong file .xlsx.
    Giúp Excel hiển thị ngay [TC]_1, [TC]_2... và tổng số TC ngay cả khi mở ở
    chế độ Calculation=Manual, Protected View, hoặc trình xem trước chỉ đọc.
    """
    if not sheet_caches:
        return xlsx_bytes

    ET.register_namespace("", _OOXML_MAIN_NS)
    ET.register_namespace("r", _OOXML_REL_NS)
    ET.register_namespace("mc", "http://schemas.openxmlformats.org/markup-compatibility/2006")
    ET.register_namespace("x14ac", "http://schemas.microsoft.com/office/spreadsheetml/2009/9/ac")

    in_buf = io.BytesIO(xlsx_bytes)
    out_buf = io.BytesIO()
    with zipfile.ZipFile(in_buf, "r") as zin:
        try:
            wb_xml = ET.fromstring(zin.read("xl/workbook.xml"))
            rels_xml = ET.fromstring(zin.read("xl/_rels/workbook.xml.rels"))
        except KeyError:
            return xlsx_bytes

        rid_to_target: dict[str, str] = {}
        for rel in rels_xml.findall(f"{{{_OOXML_PKG_REL_NS}}}Relationship"):
            rid = rel.attrib.get("Id", "")
            target = rel.attrib.get("Target", "").lstrip("/")
            if target and not target.startswith("xl/"):
                target = f"xl/{target}"
            if rid and target:
                rid_to_target[rid] = target

        path_to_cache: dict[str, dict[str, str | int | float]] = {}
        for sh in wb_xml.findall(f".//{{{_OOXML_MAIN_NS}}}sheet"):
            sh_name = sh.attrib.get("name", "")
            rid = sh.attrib.get(f"{{{_OOXML_REL_NS}}}id", "")
            target = rid_to_target.get(rid)
            if target and sh_name in sheet_caches:
                path_to_cache[target] = sheet_caches[sh_name]

        if not path_to_cache:
            return xlsx_bytes

        with zipfile.ZipFile(out_buf, "w", compression=zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                cache_map = path_to_cache.get(item.filename)
                if cache_map:
                    root = ET.fromstring(data)
                    for c_el in root.iter(f"{{{_OOXML_MAIN_NS}}}c"):
                        ref = c_el.attrib.get("r", "")
                        if ref not in cache_map:
                            continue
                        val = cache_map[ref]
                        v_el = c_el.find(f"{{{_OOXML_MAIN_NS}}}v")
                        if v_el is None:
                            v_el = ET.SubElement(c_el, f"{{{_OOXML_MAIN_NS}}}v")
                        if isinstance(val, str):
                            c_el.set("t", "str")
                            v_el.text = val
                        else:
                            if "t" in c_el.attrib:
                                del c_el.attrib["t"]
                            v_el.text = str(val)
                    data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
                zout.writestr(item, data)
    return out_buf.getvalue()


def build_testcase_excel_bytes(
    task_name: str,
    testcases: list[dict[str, Any]],
    *,
    tc_prefix: str = "TC",
) -> bytes:
    """
    Sinh file Excel (.xlsx) giữ nguyên 100% Template gốc (dòng 1..14 là Header gộp ô):
    - Font chữ toàn bộ dữ liệu: Sarabun, căn lề trên (TOP).
    - Tự động điền C3 (Tên chức năng), C4 (Mã TC, mặc định 'TC') và cập nhật C11 tổng số TC.
    - Điền dữ liệu vào 3 cột B (Mục đích), C (Các bước thực hiện), D (Kết quả mong muốn) từ dòng 15.
    - Cột A từ dòng 15 trở xuống (kèm dòng dự phòng bên dưới) chứa công thức Excel/Sheets tương thích
      COUNTIFS + giá trị cache sẵn để tự điền [TC]_1, [TC]_2... ngay lập tức trên mọi chế độ Excel.
    - Nếu bài toán chỉ có 1 chức năng: Đổi tên trực tiếp sheet đầu tiên thành tên chức năng đó.
    - Nếu bài toán có >= 2 chức năng: Sheet đầu là 'Tổng hợp', kèm các Sheet con cho từng chức năng.
    """
    from openpyxl.cell.cell import MergedCell
    from openpyxl.formatting.formatting import ConditionalFormattingList

    grouped_suites = _group_testcases_by_suite(testcases)
    wb = load_template_workbook()
    master_ws = wb.worksheets[0]

    # Bỏ hoàn toàn Conditional Formatting tự động của Sheet (để Tool trực tiếp bôi màu dòng Test Suite)
    master_ws.conditional_formatting = ConditionalFormattingList()

    # Dòng 13 & 14 là Header gộp ô (A13:A14, B13:B14...), dữ liệu bắt đầu từ DÒNG 15.
    for r_clear in range(15, master_ws.max_row + 1):
        for c_clear in (1, 2, 3, 4):
            cell_obj = master_ws.cell(row=r_clear, column=c_clear)
            if not isinstance(cell_obj, MergedCell) and cell_obj.value is not None:
                cell_obj.value = None

    clean_prefix = re.sub(r"[\[\]\s]+", "", str(tc_prefix or "TC")).strip() or "TC"
    f_meta_val = Font(name=FONT_NAME, size=10, bold=True, color="FF000000")

    # Tool trực tiếp bôi màu dòng Test Suite (#FFE599) + chữ In đậm Sarabun, dòng Test con nền trắng
    f_suite = Font(name=FONT_NAME, size=11, bold=True, color="FF000000")
    fill_suite = PatternFill(start_color="FFE599", end_color="FFE599", fill_type="solid")
    f_tc = Font(name=FONT_NAME, size=11, bold=False, color="FF000000")
    f_id_cell = Font(name=FONT_NAME, size=11, bold=False, color="FF000000")
    fill_clear = PatternFill(fill_type=None)
    s_thin = Side(border_style="thin", color="FF000000")
    b_data = Border(left=s_thin, right=s_thin, top=s_thin, bottom=s_thin)
    al_left_top = Alignment(horizontal="left", vertical="top", wrap_text=True)
    al_center_mid = Alignment(horizontal="center", vertical="center", wrap_text=True)
    al_suite = Alignment(horizontal="left", vertical="center", wrap_text=True)

    if not isinstance(master_ws["A13"], MergedCell):
        master_ws["A13"].value = "ID"

    sheet_caches: dict[str, dict[str, str | int | float]] = {}

    def write_rows_from_row_15(
        ws,
        screen_title: str,
        suites_data: list[tuple[str, list[dict[str, Any]]]],
        *,
        trailing_buffer_rows: int = 80,
    ) -> None:
        ws.conditional_formatting = ConditionalFormattingList()
        cache_map: dict[str, str | int | float] = {}

        # Điền thông tin C3 (Tên màn hình/chức năng) và C4 (Mã trường hợp kiểm thử) trên Template
        try:
            if not isinstance(ws["A13"], MergedCell):
                ws["A13"].value = "ID"
            if not isinstance(ws["C3"], MergedCell):
                ws["C3"].value = screen_title
                ws["C3"].font = f_meta_val
            if not isinstance(ws["C4"], MergedCell):
                ws["C4"].value = clean_prefix
                ws["C4"].font = f_meta_val
        except Exception:
            pass

        curr_row = 15
        tc_counter = 0
        d_nonempty_count = 0

        for suite_name, suite_tcs in suites_data:
            c_a = ws.cell(row=curr_row, column=1)
            if not isinstance(c_a, MergedCell):
                c_a.value = f'=IF(LEN(TRIM(C{curr_row}))=0,"","["&$C$4&"]_"&COUNTIFS($C$15:C{curr_row},"?*"))'
                c_a.font = f_suite
                c_a.fill = fill_suite
                c_a.alignment = al_center_mid
                c_a.border = b_data
                cache_map[f"A{curr_row}"] = ""

            # 1. Dòng Test Suite: bôi màu nền vàng (cột A..T) và in đậm tên Test Suite ở cột B
            ws.row_dimensions[curr_row].height = 26
            for col_i in range(2, 21):
                c = ws.cell(row=curr_row, column=col_i)
                if not isinstance(c, MergedCell):
                    if col_i in (2, 3, 4):
                        c.value = suite_name if col_i == 2 else None
                    c.font = f_suite
                    c.fill = fill_suite
                    c.alignment = al_suite
                    c.border = b_data
            curr_row += 1

            # 2. Các dòng Test con: ghi 3 cột B (Mục đích), C (Các bước), D (Kết quả mong muốn), nền trắng
            for tc in suite_tcs:
                purpose = str(tc.get("muc_dich") or "").strip()
                steps = str(tc.get("cac_buoc") or "").strip()
                expected = str(tc.get("ket_qua_mong_muon") or "").strip()

                c_a_tc = ws.cell(row=curr_row, column=1)
                if not isinstance(c_a_tc, MergedCell):
                    c_a_tc.value = f'=IF(LEN(TRIM(C{curr_row}))=0,"","["&$C$4&"]_"&COUNTIFS($C$15:C{curr_row},"?*"))'
                    c_a_tc.font = f_id_cell
                    c_a_tc.fill = fill_clear
                    c_a_tc.alignment = al_center_mid
                    c_a_tc.border = b_data
                    if steps:
                        tc_counter += 1
                        cache_map[f"A{curr_row}"] = f"[{clean_prefix}]_{tc_counter}"
                    else:
                        cache_map[f"A{curr_row}"] = ""

                if expected:
                    d_nonempty_count += 1

                for col_i, val in ((2, purpose), (3, steps), (4, expected)):
                    c = ws.cell(row=curr_row, column=col_i)
                    if not isinstance(c, MergedCell):
                        c.value = val if val != "" else None
                        c.font = f_tc
                        c.fill = fill_clear
                        c.alignment = al_left_top
                        c.border = b_data

                ws.row_dimensions[curr_row].height = _estimate_row_height(
                    [(purpose, 30), (steps, 38), (expected, 38)],
                    min_height=28.0,
                )
                curr_row += 1

        # Đặt sẵn công thức tự điền ID ở cột A cho các dòng trống phía dưới để thêm tay testcase vẫn tự nhảy ID
        buffer_end = curr_row + max(0, trailing_buffer_rows) - 1
        for r_buf in range(curr_row, buffer_end + 1):
            c_a_buf = ws.cell(row=r_buf, column=1)
            if not isinstance(c_a_buf, MergedCell):
                c_a_buf.value = f'=IF(LEN(TRIM(C{r_buf}))=0,"","["&$C$4&"]_"&COUNTIFS($C$15:C{r_buf},"?*"))'
                c_a_buf.font = f_id_cell
                c_a_buf.alignment = al_center_mid
                cache_map[f"A{r_buf}"] = ""

        # Cập nhật ô tổng số trường hợp kiểm thử C11 phủ hết số dòng thực tế (tránh kẹt ở dòng 977 của Template)
        max_count_row = max(1040, buffer_end)
        try:
            if not isinstance(ws["C11"], MergedCell):
                ws["C11"].value = f"=COUNTA($D$15:$D${max_count_row})"
            cache_map["C7"] = 0
            cache_map["C8"] = 0
            cache_map["C9"] = 0
            cache_map["C10"] = d_nonempty_count
            cache_map["C11"] = d_nonempty_count
        except Exception:
            pass

        sheet_caches[ws.title] = cache_map

    used_sheet_titles: set[str] = set()

    if len(grouped_suites) == 1:
        # Chỉ có 1 chức năng: Đổi tên trực tiếp sheet đầu tiên thành tên chức năng đó
        only_suite_name, only_tcs = grouped_suites[0]
        master_ws.title = _clean_excel_sheet_title(only_suite_name, 1, used_sheet_titles)
        master_ws.sheet_properties.tabColor = TAB_COLORS[0]
        sub_suites = _organize_subsuites_for_sheet(only_suite_name, only_tcs)
        write_rows_from_row_15(master_ws, only_suite_name, sub_suites, trailing_buffer_rows=200)
    elif len(grouped_suites) > 1:
        # Có từ 2 chức năng trở lên: Sheet đầu là 'Tổng hợp', kèm các Sheet con cho từng chức năng
        master_ws.title = "Tổng hợp"
        master_ws.sheet_properties.tabColor = "1E3A8A"
        used_sheet_titles.add(master_ws.title.lower())

        child_sheets: list[tuple[Any, str, list[dict[str, Any]]]] = []
        for s_idx, (suite_name, suite_tcs) in enumerate(grouped_suites, start=1):
            child_ws = wb.copy_worksheet(master_ws)
            child_title = _clean_excel_sheet_title(suite_name, s_idx, used_sheet_titles)
            child_ws.title = child_title
            child_ws.sheet_properties.tabColor = TAB_COLORS[(s_idx - 1) % len(TAB_COLORS)]
            child_sheets.append((child_ws, suite_name, suite_tcs))

        write_rows_from_row_15(master_ws, task_name, grouped_suites, trailing_buffer_rows=200)
        for child_ws, suite_name, suite_tcs in child_sheets:
            sub_suites = _organize_subsuites_for_sheet(suite_name, suite_tcs)
            write_rows_from_row_15(child_ws, suite_name, sub_suites, trailing_buffer_rows=60)
    else:
        write_rows_from_row_15(master_ws, task_name, [], trailing_buffer_rows=200)

    _ensure_safe_openpyxl_cleanup()
    buf = io.BytesIO()
    try:
        wb.save(buf)
        raw_bytes = buf.getvalue()
    finally:
        try:
            wb.close()
        except Exception:
            pass

    return _inject_cached_formula_values_xlsx(raw_bytes, sheet_caches)


def read_testcases_from_local_excel(excel_path: str | Path) -> list[dict[str, Any]]:
    """
    Đọc lại danh sách các dòng Test Suite và Test con từ dòng 15 trở xuống
    trên Sheet tổng của file Excel Local.
    """
    wb = openpyxl.load_workbook(excel_path, read_only=True, data_only=True)
    rows_out: list[dict[str, Any]] = []
    try:
        ws = wb.worksheets[0]
        current_suite = "General"
        tc_no = 0

        for r_idx, row_vals in enumerate(ws.iter_rows(min_row=15, max_col=4, values_only=True), start=15):
            a_val = str(row_vals[0] if len(row_vals) > 0 and row_vals[0] is not None else "").strip()
            b_val = str(row_vals[1] if len(row_vals) > 1 and row_vals[1] is not None else "").strip()
            c_val = str(row_vals[2] if len(row_vals) > 2 and row_vals[2] is not None else "").strip()
            d_val = str(row_vals[3] if len(row_vals) > 3 and row_vals[3] is not None else "").strip()

            if not (b_val or c_val or d_val):
                continue

            # Nếu chỉ có cột B (Mục đích / Tên Suite) mà cột C (Các bước) và D (Kết quả) trống -> Dòng Test Suite
            if b_val and not c_val and not d_val:
                current_suite = b_val
                rows_out.append(
                    {
                        "row_type": "suite",
                        "id": "",
                        "test_suite": current_suite,
                        "muc_dich": current_suite,
                        "cac_buoc": "",
                        "ket_qua_mong_muon": "",
                        "ghi_chu": "",
                    }
                )
            else:
                tc_no += 1
                tc_id = a_val if (a_val and not a_val.startswith("=")) else f"[TC]_{tc_no}"
                rows_out.append(
                    {
                        "row_type": "testcase",
                        "id": tc_id,
                        "test_suite": current_suite,
                        "muc_dich": b_val,
                        "cac_buoc": c_val,
                        "ket_qua_mong_muon": d_val,
                        "ghi_chu": "",
                    }
                )
    finally:
        try:
            wb.close()
        except Exception:
            pass

    return rows_out


# =============================================================================
# 2. SINH FILE WORD BÁO CÁO PHÂN TÍCH BÀI TOÁN (.DOCX) ĐẸP CHUẨN BÁO CÁO
# =============================================================================
def _set_cell_bg(cell, hex_color: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_pr.append(parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>'))


def _set_cell_margins(cell, top: int = 120, bottom: int = 120, left: int = 160, right: int = 160) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_pr.append(
        parse_xml(
            f'<w:tcMar {nsdecls("w")}>'
            f'<w:top w:w="{top}" w:type="dxa"/>'
            f'<w:bottom w:w="{bottom}" w:type="dxa"/>'
            f'<w:left w:w="{left}" w:type="dxa"/>'
            f'<w:right w:w="{right}" w:type="dxa"/>'
            f"</w:tcMar>"
        )
    )


def _set_cell_borders(cell, **edges: dict[str, str]) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    borders_xml = [f"<w:tcBorders {nsdecls('w')}>"]
    for edge in ("top", "left", "bottom", "right"):
        cfg = edges.get(edge)
        if cfg:
            val = cfg.get("val", "single")
            sz = cfg.get("sz", "4")
            color = cfg.get("color", "CBD5E1")
            borders_xml.append(f'<w:{edge} w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>')
        else:
            borders_xml.append(f'<w:{edge} w:val="none"/>')
    borders_xml.append("</w:tcBorders>")
    tc_pr.append(parse_xml("".join(borders_xml)))


def _apply_sarabun_font(
    run,
    size_pt: float = 11.0,
    *,
    bold: bool = False,
    italic: bool = False,
    color: RGBColor | None = None,
) -> None:
    """Đặt font Sarabun chuẩn xác trên cả thuộc tính cơ bản lẫn OpenXML rFonts."""
    run.font.name = FONT_NAME
    run.font.size = Pt(size_pt)
    run.bold = bold
    run.italic = italic
    if color is not None:
        run.font.color.rgb = color
    r_pr = run._r.get_or_add_rPr()
    r_fonts = r_pr.find(docx.oxml.ns.qn("w:rFonts"))
    if r_fonts is not None:
        r_pr.remove(r_fonts)
    r_pr.append(
        parse_xml(
            f'<w:rFonts {nsdecls("w")} w:ascii="{FONT_NAME}" w:hAnsi="{FONT_NAME}" w:cs="{FONT_NAME}" w:eastAsia="{FONT_NAME}"/>'
        )
    )


def _add_formatted_runs(paragraph, text: str, base_size: float = 11.0, default_color: RGBColor = RGBColor(30, 41, 59)) -> None:
    """
    Tự động tô đậm và đổi màu các nhãn kỹ thuật như [System], [POST], Bước 1:, (1), Params:, Response:, Errors:, (CHÚ Ý)... với font Sarabun.
    """
    pattern = re.compile(
        r"(\[[A-Za-zÀ-ỹ0-9_\-\s/&\+():.,]+\]|\(CHÚ Ý\)\s*:?|(?:Bước\s+\d+\s*[:.)]|\(\d+\))|(?:Params/Body|Params|Body|Response|Errors|Tech note|Key Columns|PK/FK|Status Lifecycle|Đề xuất)\s*:)",
        re.IGNORECASE,
    )
    parts = pattern.split(text)
    for part in parts:
        if not part:
            continue
        run = paragraph.add_run(part)
        if pattern.fullmatch(part):
            up = part.upper()
            if "CHÚ Ý" in up or "ERROR" in up or "RỦI RO" in up or "THIẾU" in up or "CHƯA RÕ" in up:
                clr = RGBColor(180, 83, 9)  # Amber 700
            elif "Q&A" in up or "ĐỀ XUẤT" in up:
                clr = RGBColor(124, 58, 237)  # Violet 600
            elif part.startswith("[") and part.endswith("]"):
                clr = RGBColor(30, 64, 175)  # Blue 800
            else:
                clr = RGBColor(15, 23, 42)
            _apply_sarabun_font(run, base_size, bold=True, color=clr)
        else:
            _apply_sarabun_font(run, base_size, bold=False, color=default_color)


def _split_into_sub_bullets(text: str) -> list[str]:
    """
    Tách một đoạn văn bản dày đặc (chứa Bước 1..N, (1)..(N), dấu | hoặc nhiều mệnh đề ;)
    thành danh sách các ý nhỏ riêng biệt để trình bày thoáng, dễ đọc trên Word & Google Docs.
    """
    s = str(text or "").strip()
    if not s:
        return []

    if " | " in s:
        parts = [p.strip() for p in s.split(" | ") if p.strip()]
        if len(parts) > 1:
            out: list[str] = []
            for p in parts:
                out.extend(_split_into_sub_bullets(p))
            return out

    if re.search(r"\bBước\s+\d+\s*[:.)]", s, re.IGNORECASE):
        parts = re.split(
            r"(?:(?<=[.;!])\s+|\s*(?:->|→)\s*)(?=Bước\s+\d+\s*[:.)])",
            s,
            flags=re.IGNORECASE,
        )
        cleaned = [p.strip() for p in parts if p and p.strip()]
        if len(cleaned) > 1:
            return cleaned

    if re.search(r"(?:^|[.;:])\s*\(\d+\)\s+", s):
        parts = re.split(r"(?:^|(?<=[.;:]))\s*(?=\(\d+\)\s+)", s)
        cleaned = [p.strip() for p in parts if p and p.strip()]
        if len(cleaned) > 1:
            return cleaned

    if s.count(";") >= 2:
        chunks: list[str] = []
        depth = 0
        start = 0
        for i, ch in enumerate(s):
            if ch == "(":
                depth += 1
            elif ch == ")" and depth > 0:
                depth -= 1
            elif ch == ";" and depth == 0:
                seg = s[start:i].strip()
                if seg:
                    chunks.append(seg)
                start = i + 1
        tail = s[start:].strip()
        if tail:
            chunks.append(tail)
        if len(chunks) > 1:
            return chunks

    return [s]


def _parse_sections_from_analysis_text(analysis_text: str) -> list[tuple[str, list[str]]]:
    """
    Tách văn bản phân tích 6 mục SRS thành danh sách [(Tiêu đề mục, [các dòng nội dung])].
    """
    raw = str(analysis_text or "").strip()
    if not raw:
        return [("1. TỔNG QUAN, MỤC TIÊU & PHẠM VI NGHIỆP VỤ (SRS OVERVIEW & SCOPE)", ["Chưa có dữ liệu phân tích."])]

    heading_re = re.compile(
        r"^(?:[1-6]\.\s+[A-ZÀ-Ỹ0-9\s/&(),\-]+)$",
        re.MULTILINE,
    )
    lines = raw.splitlines()
    sections: list[tuple[str, list[str]]] = []
    curr_title = "1. TỔNG QUAN, MỤC TIÊU & PHẠM VI NGHIỆP VỤ (SRS OVERVIEW & SCOPE)"
    curr_lines: list[str] = []

    for line in lines:
        s = line.strip()
        if not s:
            continue
        if heading_re.match(s) or re.match(
            r"^[1-6]\.\s+(TỔNG QUAN|MỤC TIÊU|KIẾN TRÚC|CÁC HỆ THỐNG|LUỒNG|MÔ HÌNH|CÁC BẢNG DỮ LIỆU|ĐỊNH HƯỚNG|KỊCH BẢN KIỂM THỬ|RỦI RO)",
            s,
            re.IGNORECASE,
        ):
            if curr_lines:
                sections.append((curr_title, curr_lines))
            curr_title = s
            curr_lines = []
        else:
            curr_lines.append(s)

    if curr_lines:
        sections.append((curr_title, curr_lines))

    return sections


def read_analysis_text_from_local_word(docx_source: str | Path | bytes | io.BytesIO) -> str:
    """
    Khôi phục lại nguyên vẹn văn bản 6 mục phân tích SRS từ một file Word (.docx) đã có sẵn
    (hỗ trợ cả định dạng Bảng 2 cột / Callout Box lẫn định dạng đoạn văn thuần).
    """
    if isinstance(docx_source, (bytes, bytearray)):
        doc = Document(io.BytesIO(docx_source))
    elif isinstance(docx_source, io.BytesIO):
        docx_source.seek(0)
        doc = Document(docx_source)
    else:
        doc = Document(str(docx_source))

    from docx.table import Table
    from docx.text.paragraph import Paragraph

    heading_pat = re.compile(
        r"^[1-6]\.\s+(TỔNG QUAN|MỤC TIÊU|KIẾN TRÚC|CÁC HỆ THỐNG|LUỒNG|MÔ HÌNH|CÁC BẢNG DỮ LIỆU|ĐỊNH HƯỚNG|KỊCH BẢN KIỂM THỬ|RỦI RO|[A-ZÀ-Ỹ0-9\s/&(),\-]{8,})",
        re.IGNORECASE,
    )

    out_lines: list[str] = []
    in_sections = False

    for child in doc.element.body.iterchildren():
        tag = child.tag.split("}")[-1]
        if tag == "p":
            p = Paragraph(child, doc)
            txt = p.text.strip()
            if not txt:
                continue
            if "\tPhần " in txt or "\tMục " in txt or txt.upper() == "MỤC LỤC TÀI LIỆU":
                continue
            if heading_pat.match(txt):
                in_sections = True
                out_lines.append(txt)
            elif in_sections:
                is_sub_bullet = txt.startswith("•")
                clean_p = re.sub(r"^[▸\-*•]+\s*", "", txt).strip()
                if clean_p:
                    if is_sub_bullet and out_lines and out_lines[-1].startswith("- "):
                        sep = " " if out_lines[-1].endswith(":") else " | "
                        out_lines[-1] = f"{out_lines[-1]}{sep}{clean_p}"
                    else:
                        out_lines.append(f"- {clean_p}")
        elif tag == "tbl":
            tbl = Table(child, doc)
            rows = tbl.rows
            if not rows:
                continue
            cols_count = len(rows[0].cells)
            if cols_count >= 4:
                continue
            if cols_count == 1 and len(rows) == 1:
                cell_lines = [p.text.strip() for p in rows[0].cells[0].paragraphs if p.text.strip()]
                if not cell_lines:
                    continue
                if len(cell_lines) == 1 and heading_pat.match(cell_lines[0]):
                    in_sections = True
                    out_lines.append(cell_lines[0])
                elif in_sections:
                    for cl in cell_lines:
                        is_sub = cl.startswith("•")
                        clean_cl = re.sub(r"^[▸\-*•]+\s*", "", cl).strip()
                        if clean_cl:
                            if is_sub and out_lines and out_lines[-1].startswith("- "):
                                sep = " " if out_lines[-1].endswith(":") else " | "
                                out_lines[-1] = f"{out_lines[-1]}{sep}{clean_cl}"
                            else:
                                out_lines.append(f"- {clean_cl}")
            elif cols_count == 2 and in_sections:
                for r_i, row in enumerate(rows):
                    if r_i == 0:
                        continue
                    left_txt = row.cells[0].text.strip()
                    right_parts = [
                        re.sub(r"^[•▸\-*]+\s*", "", p.text.strip()).strip()
                        for p in row.cells[1].paragraphs
                        if p.text.strip()
                    ]
                    right_txt = " | ".join(p for p in right_parts if p)
                    if left_txt and not left_txt.startswith("Hạng mục #"):
                        out_lines.append(f"- {left_txt} - {right_txt}" if right_txt else f"- {left_txt}")
                    elif right_txt:
                        out_lines.append(f"- {right_txt}")

    return "\n".join(out_lines).strip()


def _extract_toc_subitems(sec_idx: int, sec_title: str, sec_lines: list[str]) -> list[tuple[str, str]]:
    """
    Trích xuất danh sách các mục con (1.1, 1.2, ...) cho từng phần lớn trong Mục lục (Table of Contents).
    """
    up_title = sec_title.upper()
    subitems: list[tuple[str, str]] = []

    if sec_idx == 2 or "API" in up_title or "HỆ THỐNG" in up_title or "KIẾN TRÚC" in up_title:
        has_sys = any("[SYSTEM]" in ln.upper() for ln in sec_lines)
        has_api = any(
            any(k in ln.upper() for k in ("[METHOD]", "[GET]", "[POST]", "[PUT]", "[DELETE]", "/API/"))
            for ln in sec_lines
        )
        sub_i = 1
        if has_sys:
            subitems.append((f"{sec_idx}.{sub_i}", "Các hệ thống & Phân hệ tích hợp (Systems Overview)"))
            sub_i += 1
        if has_api or not subitems:
            subitems.append((f"{sec_idx}.{sub_i}", "Đặc tả chi tiết Giao tiếp API (Endpoints, Params, Response, Errors)"))
        return subitems

    if sec_idx == 4 or "DỮ LIỆU" in up_title or "DATA MODEL" in up_title:
        seen_tables: set[str] = set()
        for ln in sec_lines:
            clean = re.sub(r"^[-*•]\s*", "", ln.strip())
            m = re.match(r"^\[([^\]]+)\]\s*(?:[-:]\s*([^|]+))?", clean)
            if m:
                tbl_name = m.group(1).strip()
                desc = (m.group(2) or "").strip()
                if tbl_name.upper() not in seen_tables:
                    seen_tables.add(tbl_name.upper())
                    sub_code = f"{sec_idx}.{len(subitems) + 1}"
                    lbl = f"Bảng dữ liệu {tbl_name}" + (f" — {desc}" if desc else "")
                    if len(lbl) > 78:
                        lbl = lbl[:75].rstrip() + "..."
                    subitems.append((sub_code, lbl))
            if len(subitems) >= 8:
                break
        return subitems

    seen_labels: set[str] = set()
    for ln in sec_lines:
        clean = re.sub(r"^[-*•]\s*", "", ln.strip())
        m = re.match(r"^\[([^\]]+)\]", clean)
        if m:
            raw_lbl = m.group(1).strip()
            norm_lbl = raw_lbl.upper()
            if (
                raw_lbl.startswith(".")
                or "CẮT CỤT" in norm_lbl
                or "TÀI LIỆU CHƯA" in norm_lbl
            ):
                continue
            if norm_lbl not in seen_labels:
                seen_labels.add(norm_lbl)
                sub_code = f"{sec_idx}.{len(subitems) + 1}"
                if len(raw_lbl) > 78:
                    raw_lbl = raw_lbl[:75].rstrip() + "..."
                subitems.append((sub_code, raw_lbl))
        if len(subitems) >= 6:
            break

    return subitems


def _add_internal_hyperlink(
    paragraph,
    anchor: str,
    text: str,
    *,
    size_pt: float = 11.0,
    bold: bool = False,
    color: RGBColor = RGBColor(30, 58, 138),
) -> None:
    """Tạo liên kết nội bộ (internal bookmark hyperlink) trong Word & Google Docs với font Sarabun."""
    hyperlink = parse_xml(f'<w:hyperlink {nsdecls("w")} w:anchor="{anchor}" w:history="1"/>')
    run = paragraph.add_run(text)
    _apply_sarabun_font(run, size_pt, bold=bold, color=color)
    hyperlink.append(run._r)
    paragraph._p.append(hyperlink)


def build_analysis_word_bytes(
    task_name: str,
    analysis_text: str,
    *,
    testcase_count: int = 0,
) -> bytes:
    """
    Sinh tài liệu Word (.docx) Báo cáo Phân tích SRS:
    - Giữ nguyên 100% Trang bìa gốc của bạn (từ TEMPLATE_DOC_CACHE_PATH tải về từ TEMPLATE_DOC_ID).
    - Trang 2: Bảng thông tin tổng quan tài liệu + MỤC LỤC TÀI LIỆU (Table of Contents) có phân cấp & liên kết nội bộ.
    - Toàn bộ nội dung sử dụng font chữ Sarabun.
    - Bố cục 6 phần chuẩn Phân tích SRS đồng nhất 100% giữa Word (.docx) và Google Docs.
    """
    has_cover_template = False
    if TEMPLATE_DOC_CACHE_PATH.is_file():
        try:
            doc = Document(str(TEMPLATE_DOC_CACHE_PATH))
            has_cover_template = True
        except Exception as err:
            LOGGER.warning("Không thể mở file template_analysis.docx (%s), tạo mới: %s", TEMPLATE_DOC_CACHE_PATH, err)
            doc = Document()
    else:
        doc = Document()

    normal_style = next(
        (
            s
            for s in doc.styles
            if str(getattr(s, "name", "")).lower() == "normal"
            or getattr(s, "style_id", "") == "Normal"
        ),
        None,
    )
    if normal_style is not None:
        normal_style.font.name = FONT_NAME
        normal_style.font.size = Pt(11.0)
        normal_style.font.color.rgb = RGBColor(30, 41, 59)

    now_str = time.strftime("%d/%m/%Y %H:%M")

    if not has_cover_template:
        section = doc.sections[0]
        section.page_width = Cm(21.0)
        section.page_height = Cm(29.7)
        section.top_margin = Cm(2.0)
        section.bottom_margin = Cm(2.0)
        section.left_margin = Cm(2.2)
        section.right_margin = Cm(2.0)
    else:
        if len(doc.paragraphs) > 1 and not doc.paragraphs[-1].text.strip():
            last_p = doc.paragraphs[-1]._p
            if "w:br" not in last_p.xml and "w:drawing" not in last_p.xml:
                last_p.getparent().remove(last_p)

    # -------------------------------------------------------------------------
    # BẢNG THÔNG TIN TỔNG QUAN BÀI TOÁN PHÂN TÍCH SRS (METADATA TABLE)
    # -------------------------------------------------------------------------
    meta_rows_data = [
        ("Tên bài toán / Chức năng SRS", task_name, "Ngày phân tích", now_str),
        (
            "Phạm vi tài liệu",
            "Phân tích đặc tả yêu cầu phần mềm (SRS Analysis)",
            "Trạng thái rà soát",
            "Sẵn sàng cho BA / Dev / QA",
        ),
    ]
    meta_tbl = doc.add_table(rows=len(meta_rows_data), cols=4)
    meta_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    meta_widths = [Cm(4.0), Cm(5.0), Cm(3.6), Cm(4.2)]

    thin_b = {"val": "single", "sz": "4", "color": "CBD5E1"}
    for r_idx, (k1, v1, k2, v2) in enumerate(meta_rows_data):
        row_cells = meta_tbl.rows[r_idx].cells
        vals = [(k1, True), (v1, False), (k2, True), (v2, False)]
        for c_idx, (txt, is_lbl) in enumerate(vals):
            c = row_cells[c_idx]
            c.width = meta_widths[c_idx]
            _set_cell_bg(c, "EFF6FF" if is_lbl else "FFFFFF")
            _set_cell_margins(c, top=90, bottom=90, left=130, right=130)
            _set_cell_borders(c, top=thin_b, bottom=thin_b, left=thin_b, right=thin_b)
            p = c.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            run = p.add_run(str(txt))
            _apply_sarabun_font(
                run,
                10.0,
                bold=is_lbl,
                color=RGBColor(30, 58, 138) if is_lbl else RGBColor(15, 23, 42),
            )

    doc.add_paragraph().paragraph_format.space_after = Pt(6)

    # -------------------------------------------------------------------------
    # PHẦN MỤC LỤC TÀI LIỆU (TABLE OF CONTENTS) - HIỂN THỊ TRÊN CẢ WORD & DOCS
    # -------------------------------------------------------------------------
    sections = _parse_sections_from_analysis_text(analysis_text)

    toc_hdr = doc.add_paragraph()
    toc_hdr.alignment = WD_ALIGN_PARAGRAPH.LEFT
    toc_hdr.paragraph_format.space_before = Pt(4)
    toc_hdr.paragraph_format.space_after = Pt(8)
    toc_hdr_pPr = toc_hdr._p.get_or_add_pPr()
    toc_hdr_pPr.append(
        parse_xml(
            f'<w:pBdr {nsdecls("w")}>'
            f'<w:bottom w:val="single" w:sz="12" w:space="4" w:color="1E3A8A"/>'
            f"</w:pBdr>"
        )
    )
    toc_hdr_run = toc_hdr.add_run("MỤC LỤC TÀI LIỆU")
    _apply_sarabun_font(toc_hdr_run, 13.5, bold=True, color=RGBColor(30, 58, 138))

    for sec_idx, (sec_title, sec_lines) in enumerate(sections, start=1):
        anchor_name = f"sec_{sec_idx}"
        is_risk_toc = "RỦI RO" in sec_title.upper() or "ĐIỂM CHƯA RÕ" in sec_title.upper()
        main_color = RGBColor(146, 64, 14) if is_risk_toc else RGBColor(30, 58, 138)

        p_toc1 = doc.add_paragraph()
        p_toc1.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p_toc1.paragraph_format.space_before = Pt(5)
        p_toc1.paragraph_format.space_after = Pt(2)
        p_toc1._p.get_or_add_pPr().append(
            parse_xml(f'<w:tabs {nsdecls("w")}><w:tab w:val="right" w:leader="dot" w:pos="9500"/></w:tabs>')
        )
        _add_internal_hyperlink(p_toc1, anchor_name, sec_title, size_pt=11.0, bold=True, color=main_color)
        r_tab1 = p_toc1.add_run(f"\tPhần {sec_idx:02d}")
        _apply_sarabun_font(r_tab1, 10.5, bold=True, color=main_color)

        subitems = _extract_toc_subitems(sec_idx, sec_title, sec_lines)
        for sub_code, sub_label in subitems:
            p_toc2 = doc.add_paragraph()
            p_toc2.alignment = WD_ALIGN_PARAGRAPH.LEFT
            p_toc2.paragraph_format.left_indent = Cm(0.65)
            p_toc2.paragraph_format.space_before = Pt(1)
            p_toc2.paragraph_format.space_after = Pt(2)
            p_toc2._p.get_or_add_pPr().append(
                parse_xml(f'<w:tabs {nsdecls("w")}><w:tab w:val="right" w:leader="dot" w:pos="9500"/></w:tabs>')
            )
            _add_internal_hyperlink(
                p_toc2,
                anchor_name,
                f"{sub_code}. {sub_label}",
                size_pt=10.0,
                bold=False,
                color=RGBColor(51, 65, 85),
            )
            r_tab2 = p_toc2.add_run(f"\tMục {sub_code}")
            _apply_sarabun_font(r_tab2, 9.5, bold=False, color=RGBColor(100, 116, 139))

    doc.add_page_break()

    # -------------------------------------------------------------------------
    # RENDER 6 PHẦN TRONG BÁO CÁO PHÂN TÍCH SRS (FONT SARABUN)
    # -------------------------------------------------------------------------
    def add_section_heading(title_text: str, sec_idx: int, is_risk: bool = False) -> None:
        bg = "FEF3C7" if is_risk else "F1F5F9"
        left_color = "D97706" if is_risk else "1E3A8A"
        text_rgb = RGBColor(146, 64, 14) if is_risk else RGBColor(30, 58, 138)
        anchor_name = f"sec_{sec_idx}"
        bm_id = 100 + sec_idx

        hp = doc.add_paragraph()
        hp.alignment = WD_ALIGN_PARAGRAPH.LEFT
        hp.paragraph_format.space_before = Pt(10)
        hp.paragraph_format.space_after = Pt(6)
        hp.paragraph_format.keep_with_next = True

        p_pr = hp._p.get_or_add_pPr()
        p_pr.append(parse_xml(f'<w:outlineLvl {nsdecls("w")} w:val="0"/>'))
        p_pr.append(parse_xml(f'<w:shd {nsdecls("w")} w:val="clear" w:color="auto" w:fill="{bg}"/>'))
        p_pr.append(
            parse_xml(
                f'<w:pBdr {nsdecls("w")}>'
                f'<w:top w:val="single" w:sz="4" w:space="6" w:color="E2E8F0"/>'
                f'<w:left w:val="single" w:sz="24" w:space="10" w:color="{left_color}"/>'
                f'<w:bottom w:val="single" w:sz="4" w:space="6" w:color="E2E8F0"/>'
                f'<w:right w:val="single" w:sz="4" w:space="8" w:color="E2E8F0"/>'
                f"</w:pBdr>"
            )
        )

        hp._p.append(parse_xml(f'<w:bookmarkStart {nsdecls("w")} w:id="{bm_id}" w:name="{anchor_name}"/>'))
        hr = hp.add_run(title_text.upper())
        _apply_sarabun_font(hr, 12.0, bold=True, color=text_rgb)
        hp._p.append(parse_xml(f'<w:bookmarkEnd {nsdecls("w")} w:id="{bm_id}"/>'))

    def render_callout_box(lines: list[str], *, bg_hex: str = "EFF6FF", border_hex: str = "2563EB") -> None:
        box = doc.add_table(rows=1, cols=1)
        box.alignment = WD_TABLE_ALIGNMENT.CENTER
        cell = box.cell(0, 0)
        cell.width = Cm(16.8)
        _set_cell_bg(cell, bg_hex)
        _set_cell_margins(cell, top=140, bottom=140, left=200, right=180)
        _set_cell_borders(
            cell,
            left={"val": "single", "sz": "20", "color": border_hex},
            top={"val": "single", "sz": "4", "color": "BFDBFE"},
            bottom={"val": "single", "sz": "4", "color": "BFDBFE"},
            right={"val": "single", "sz": "4", "color": "BFDBFE"},
        )
        p_count = 0
        for line in lines:
            clean_line = re.sub(r"^[-*•]\s*", "", line.strip())
            if not clean_line:
                continue
            m_hdr = re.match(r"^(\[[^\]]+\])\s*:?\s*(.+)$", clean_line)
            if m_hdr:
                hdr_label = m_hdr.group(1).strip() + ":"
                body_str = m_hdr.group(2).strip()
                sub_items = _split_into_sub_bullets(body_str)
            else:
                hdr_label = ""
                sub_items = _split_into_sub_bullets(clean_line)

            if hdr_label and len(sub_items) > 1:
                p_hdr = cell.paragraphs[0] if p_count == 0 else cell.add_paragraph()
                p_count += 1
                p_hdr.alignment = WD_ALIGN_PARAGRAPH.LEFT
                p_hdr.paragraph_format.space_before = Pt(3)
                p_hdr.paragraph_format.space_after = Pt(1)
                _add_formatted_runs(p_hdr, hdr_label, base_size=11.0)
                for si in sub_items:
                    p_sub = cell.add_paragraph()
                    p_count += 1
                    p_sub.alignment = WD_ALIGN_PARAGRAPH.LEFT
                    p_sub.paragraph_format.left_indent = Cm(0.55)
                    p_sub.paragraph_format.space_before = Pt(1)
                    p_sub.paragraph_format.space_after = Pt(2)
                    p_sub.paragraph_format.line_spacing = 1.22
                    _add_formatted_runs(p_sub, f"• {si}", base_size=10.5)
            else:
                p = cell.paragraphs[0] if p_count == 0 else cell.add_paragraph()
                p_count += 1
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                p.paragraph_format.space_before = Pt(2)
                p.paragraph_format.space_after = Pt(3)
                p.paragraph_format.line_spacing = 1.25
                _add_formatted_runs(p, clean_line, base_size=11.0)

    def render_structured_table(
        items: list[tuple[str, str]],
        col1_title: str,
        col2_title: str,
        *,
        header_bg: str = "1E3A8A",
    ) -> None:
        tbl = doc.add_table(rows=len(items) + 1, cols=2)
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        col_w = [Cm(4.5), Cm(12.3)]

        hdr_cells = tbl.rows[0].cells
        for c_i, h_text in enumerate((col1_title, col2_title)):
            c = hdr_cells[c_i]
            c.width = col_w[c_i]
            _set_cell_bg(c, header_bg)
            _set_cell_margins(c, top=110, bottom=110, left=140, right=140)
            _set_cell_borders(c, top=thin_b, bottom=thin_b, left=thin_b, right=thin_b)
            p = c.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            r = p.add_run(h_text)
            _apply_sarabun_font(r, 10.5, bold=True, color=RGBColor(255, 255, 255))

        for idx, (left_val, right_val) in enumerate(items, start=1):
            row_cells = tbl.rows[idx].cells
            bg = "FFFFFF" if idx % 2 == 1 else "F8FAFC"

            c0 = row_cells[0]
            c0.width = col_w[0]
            _set_cell_bg(c0, bg)
            _set_cell_margins(c0, top=100, bottom=100, left=140, right=120)
            _set_cell_borders(c0, top=thin_b, bottom=thin_b, left=thin_b, right=thin_b)
            p0 = c0.paragraphs[0]
            p0.alignment = WD_ALIGN_PARAGRAPH.LEFT
            p0.paragraph_format.space_before = Pt(1)
            p0.paragraph_format.space_after = Pt(1)
            _add_formatted_runs(p0, left_val, base_size=10.5, default_color=RGBColor(30, 58, 138))

            c1 = row_cells[1]
            c1.width = col_w[1]
            _set_cell_bg(c1, bg)
            _set_cell_margins(c1, top=100, bottom=100, left=140, right=140)
            _set_cell_borders(c1, top=thin_b, bottom=thin_b, left=thin_b, right=thin_b)

            sub_parts = _split_into_sub_bullets(right_val) or [right_val]
            for sp_idx, sp in enumerate(sub_parts):
                p1 = c1.paragraphs[0] if sp_idx == 0 else c1.add_paragraph()
                p1.alignment = WD_ALIGN_PARAGRAPH.LEFT
                p1.paragraph_format.space_before = Pt(1)
                p1.paragraph_format.space_after = Pt(2)
                p1.paragraph_format.line_spacing = 1.2
                prefix = "• " if len(sub_parts) > 1 else ""
                _add_formatted_runs(p1, prefix + sp, base_size=10.5)

    def split_label_and_detail(line: str, fallback_idx: int) -> tuple[str, str]:
        clean = re.sub(r"^[-*•]\s*", "", line.strip())
        m = re.match(r"^(\[[^\]]+\](?:\s+[^\-:|]+)?)\s*(?:[-:]|\|)\s*(.+)$", clean)
        if m:
            return m.group(1).strip(), m.group(2).strip()
        m2 = re.match(r"^(\[[^\]]+\])\s+(.+)$", clean)
        if m2:
            return m2.group(1).strip(), m2.group(2).strip()
        if ":" in clean and clean.index(":") < 45:
            k, v = clean.split(":", 1)
            return k.strip(), v.strip()
        return f"Hạng mục #{fallback_idx:02d}", clean

    for sec_idx, (sec_title, sec_lines) in enumerate(sections, start=1):
        up_title = sec_title.upper()
        is_risk_sec = "RỦI RO" in up_title or "ĐIỂM CHƯA RÕ" in up_title or "ĐIỂM KHUYẾT" in up_title
        add_section_heading(sec_title, sec_idx, is_risk=is_risk_sec)

        p_spacer = doc.add_paragraph()
        p_spacer.paragraph_format.space_before = Pt(0)
        p_spacer.paragraph_format.space_after = Pt(2)

        if "MỤC TIÊU" in up_title or "TỔNG QUAN" in up_title:
            render_callout_box(sec_lines, bg_hex="EFF6FF", border_hex="2563EB")
        elif "HỆ THỐNG" in up_title or "API" in up_title or "KIẾN TRÚC" in up_title:
            rows = [split_label_and_detail(ln, i + 1) for i, ln in enumerate(sec_lines)]
            render_structured_table(rows, "Hệ thống / Endpoint API", "Đặc tả kỹ thuật (Params, Response, Errors)", header_bg="1E3A8A")
        elif "BẢNG DỮ LIỆU" in up_title or "MÔ HÌNH DỮ LIỆU" in up_title:
            rows = [split_label_and_detail(ln, i + 1) for i, ln in enumerate(sec_lines)]
            render_structured_table(rows, "Bảng / Đối tượng Dữ liệu", "Cấu trúc trường (Columns), Khóa & Trạng thái", header_bg="0F172A")
        elif "KỊCH BẢN KIỂM THỬ" in up_title or "SCENARIO" in up_title:
            rows = [split_label_and_detail(ln, i + 1) for i, ln in enumerate(sec_lines)]
            render_structured_table(rows, "Nhóm Kịch bản (Category)", "Nội dung kiểm thử trọng tâm & Kỳ vọng", header_bg="1E40AF")
        elif is_risk_sec:
            rows = [split_label_and_detail(ln, i + 1) for i, ln in enumerate(sec_lines)]
            render_structured_table(rows, "Phân loại Rủi ro / Q&A BA", "Chi tiết vấn đề & Đề xuất phương án xử lý", header_bg="B45309")
        else:
            for ln in sec_lines:
                clean_ln = re.sub(r"^[-*•]\s*", "", ln.strip())
                if not clean_ln:
                    continue
                m_flow = re.match(r"^(\[[^\]]+\])\s*:?\s*(.+)$", clean_ln)
                if m_flow:
                    flow_hdr = m_flow.group(1).strip() + ":"
                    flow_body = m_flow.group(2).strip()
                    sub_steps = _split_into_sub_bullets(flow_body)
                else:
                    flow_hdr = ""
                    sub_steps = _split_into_sub_bullets(clean_ln)

                if flow_hdr and len(sub_steps) > 1:
                    p_hdr = doc.add_paragraph()
                    p_hdr.alignment = WD_ALIGN_PARAGRAPH.LEFT
                    p_hdr.paragraph_format.left_indent = Cm(0.3)
                    p_hdr.paragraph_format.space_before = Pt(6)
                    p_hdr.paragraph_format.space_after = Pt(2)
                    p_hdr.paragraph_format.keep_with_next = True
                    bullet_run = p_hdr.add_run("▸ ")
                    _apply_sarabun_font(bullet_run, 11.0, bold=True, color=RGBColor(37, 99, 235))
                    _add_formatted_runs(p_hdr, flow_hdr, base_size=11.0)

                    for step_txt in sub_steps:
                        p_step = doc.add_paragraph()
                        p_step.alignment = WD_ALIGN_PARAGRAPH.LEFT
                        p_step.paragraph_format.left_indent = Cm(1.0)
                        p_step.paragraph_format.space_before = Pt(1.5)
                        p_step.paragraph_format.space_after = Pt(2.5)
                        p_step.paragraph_format.line_spacing = 1.22
                        _add_formatted_runs(p_step, f"• {step_txt}", base_size=10.5)
                else:
                    p = doc.add_paragraph()
                    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                    p.paragraph_format.left_indent = Cm(0.4)
                    p.paragraph_format.space_before = Pt(3)
                    p.paragraph_format.space_after = Pt(4)
                    p.paragraph_format.line_spacing = 1.25
                    bullet_run = p.add_run("▸ ")
                    _apply_sarabun_font(bullet_run, 11.0, bold=True, color=RGBColor(37, 99, 235))
                    _add_formatted_runs(p, clean_ln, base_size=11.0)

        p_after = doc.add_paragraph()
        p_after.paragraph_format.space_before = Pt(0)
        p_after.paragraph_format.space_after = Pt(4)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def ensure_word_file_has_toc(word_path: str | Path, task_title: str = "", fallback_text: str = "") -> bool:
    """
    Kiểm tra file Word (.docx) hiện có tại word_path:
    Nếu file chưa có phần 'MỤC LỤC TÀI LIỆU', tự động trích xuất nội dung 6 mục phân tích
    từ chính file .docx đó (hoặc dùng fallback_text) và dựng lại file .docx mới có đầy đủ Mục lục + Bảng biểu chuẩn.
    """
    p_obj = Path(word_path)
    if not p_obj.is_file():
        if fallback_text and fallback_text.strip() and task_title:
            new_bytes = build_analysis_word_bytes(task_title, fallback_text)
            p_obj.parent.mkdir(parents=True, exist_ok=True)
            p_obj.write_bytes(new_bytes)
            return True
        return False

    try:
        doc = Document(str(p_obj))
        has_toc = any("MỤC LỤC TÀI LIỆU" in p.text.upper() for p in doc.paragraphs)
        has_clumped_flows = any(
            ("Bước 1:" in p.text and "Bước 2:" in p.text)
            or ("(1)" in p.text and "(2)" in p.text)
            for p in doc.paragraphs
        )
        if has_toc and not has_clumped_flows:
            return False

        extracted = fallback_text.strip() if fallback_text and fallback_text.strip() else read_analysis_text_from_local_word(p_obj)
        if not extracted:
            return False

        inferred_title = task_title.strip() or p_obj.stem.replace("Phân tích bài toán - ", "").strip()
        new_bytes = build_analysis_word_bytes(inferred_title, extracted)
        p_obj.write_bytes(new_bytes)
        LOGGER.info("[DocumentBuilder] Đã nâng cấp bổ sung Mục lục cho file Word: %s", p_obj)
        return True
    except Exception as err:
        LOGGER.warning("Không thể nâng cấp Mục lục cho file Word (%s): %s", p_obj, err)
        return False
