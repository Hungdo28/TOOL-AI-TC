from __future__ import annotations

import io
import json
import logging
import re
import time
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


def build_testcase_excel_bytes(
    task_name: str,
    testcases: list[dict[str, Any]],
    *,
    tc_prefix: str = "TC",
) -> bytes:
    """
    Sinh file Excel (.xlsx) giữ nguyên 100% Template gốc (dòng 1..14 là Header gộp ô, câu lệnh tự sinh ID ở cột A giữ nguyên):
    - Font chữ toàn bộ dữ liệu: Sarabun, căn lề trên (TOP).
    - Tự động điền C3 (Tên chức năng) và C4 (Mã TC, mặc định 'TC').
    - CHỈ điền dữ liệu vào 3 cột B (Mục đích kiểm thử), C (Các bước thực hiện), D (Kết quả mong muốn) bắt đầu từ dòng 15.
    - KHÔNG ghi đè cột A (giữ nguyên câu lệnh tự sinh ID testcase của Template).
    - Nếu bài toán chỉ có 1 chức năng: Đổi tên trực tiếp sheet đầu tiên thành tên chức năng đó (không tạo 2 sheet trùng nhau).
    - Nếu bài toán có >= 2 chức năng: Sheet đầu là 'Tổng hợp', kèm các Sheet con cho từng chức năng.
    """
    from openpyxl.cell.cell import MergedCell
    from openpyxl.formatting.formatting import ConditionalFormattingList

    grouped_suites = _group_testcases_by_suite(testcases)
    wb = load_template_workbook()
    master_ws = wb.worksheets[0]

    # Bỏ hoàn toàn Conditional Formatting tự động của Sheet (để Tool trực tiếp bôi màu dòng Test Suite)
    master_ws.conditional_formatting = ConditionalFormattingList()

    # Lưu ý: Trong Template gốc, dòng 13 & 14 là Header gộp ô (A13:A14, B13:B14, C13:C14, D13:D14...),
    # nên dòng dữ liệu bắt đầu từ DÒNG 15. Chỉ xóa giá trị cũ ở cột B, C, D từ dòng 15 trở xuống.
    for r_clear in range(15, master_ws.max_row + 1):
        for c_clear in (2, 3, 4):
            cell_obj = master_ws.cell(row=r_clear, column=c_clear)
            if not isinstance(cell_obj, MergedCell) and cell_obj.value is not None:
                cell_obj.value = None

    clean_prefix = re.sub(r"[\[\]\s]+", "", str(tc_prefix or "TC")).strip() or "TC"
    f_meta_val = Font(name=FONT_NAME, size=10, bold=True, color="000000")

    # Tool trực tiếp bôi màu dòng Test Suite (#FFE599 hoặc xanh dịu) + chữ In đậm Sarabun, dòng Test con nền trắng
    f_suite = Font(name=FONT_NAME, size=11, bold=True, color="000000")
    fill_suite = PatternFill(start_color="FFE599", end_color="FFE599", fill_type="solid")
    f_tc = Font(name=FONT_NAME, size=11, bold=False, color="000000")
    f_id_cell = Font(name=FONT_NAME, size=11, bold=False, color="000000")
    fill_clear = PatternFill(fill_type=None)
    s_thin = Side(border_style="thin", color="000000")
    b_data = Border(left=s_thin, right=s_thin, top=s_thin, bottom=s_thin)
    al_left_top = Alignment(horizontal="left", vertical="top", wrap_text=True)
    al_center_mid = Alignment(horizontal="center", vertical="center", wrap_text=True)
    al_suite = Alignment(horizontal="left", vertical="center", wrap_text=True)

    if not isinstance(master_ws["A13"], MergedCell):
        master_ws["A13"].value = "ID"

    def write_rows_from_row_15(
        ws,
        screen_title: str,
        suites_data: list[tuple[str, list[dict[str, Any]]]],
    ) -> None:
        ws.conditional_formatting = ConditionalFormattingList()
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
        for suite_name, suite_tcs in suites_data:
            # Giữ câu lệnh tự động điền ID ở cột A
            c_a = ws.cell(row=curr_row, column=1)
            if not isinstance(c_a, MergedCell):
                c_a.value = f'=IF(LEN(TRIM(C{curr_row}))=0,"","["&$C$4&"]_"&COUNTA($C$15:C{curr_row}))'
                c_a.font = f_suite
                c_a.fill = fill_suite
                c_a.alignment = al_center_mid
                c_a.border = b_data

            # 1. Dòng Test Suite: Tool trực tiếp bôi màu nền (cột A..T) và in đậm chữ tên Test Suite ở cột B
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

            # 2. Các dòng Test con: chỉ ghi đúng 3 cột B (Mục đích), C (Các bước), D (Kết quả mong muốn), nền trắng
            for tc in suite_tcs:
                c_a_tc = ws.cell(row=curr_row, column=1)
                if not isinstance(c_a_tc, MergedCell):
                    c_a_tc.value = f'=IF(LEN(TRIM(C{curr_row}))=0,"","["&$C$4&"]_"&COUNTA($C$15:C{curr_row}))'
                    c_a_tc.font = f_id_cell
                    c_a_tc.fill = fill_clear
                    c_a_tc.alignment = al_center_mid
                    c_a_tc.border = b_data

                purpose = tc.get("muc_dich") or ""
                steps = tc.get("cac_buoc") or ""
                expected = tc.get("ket_qua_mong_muon") or ""

                for col_i, val in ((2, purpose), (3, steps), (4, expected)):
                    c = ws.cell(row=curr_row, column=col_i)
                    if not isinstance(c, MergedCell):
                        c.value = val
                        c.font = f_tc
                        c.fill = fill_clear
                        c.alignment = al_left_top
                        c.border = b_data

                ws.row_dimensions[curr_row].height = _estimate_row_height(
                    [(purpose, 30), (steps, 38), (expected, 38)],
                    min_height=28.0,
                )
                curr_row += 1

    used_sheet_titles: set[str] = set()

    if len(grouped_suites) == 1:
        # Chỉ có 1 chức năng: Đổi tên trực tiếp sheet đầu tiên thành tên chức năng đó (không nhân bản thành 2 trang giống nhau)
        only_suite_name, only_tcs = grouped_suites[0]
        master_ws.title = _clean_excel_sheet_title(only_suite_name, 1, used_sheet_titles)
        master_ws.sheet_properties.tabColor = TAB_COLORS[0]
        sub_suites = _organize_subsuites_for_sheet(only_suite_name, only_tcs)
        write_rows_from_row_15(master_ws, only_suite_name, sub_suites)
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

        write_rows_from_row_15(master_ws, task_name, grouped_suites)
        for child_ws, suite_name, suite_tcs in child_sheets:
            sub_suites = _organize_subsuites_for_sheet(suite_name, suite_tcs)
            write_rows_from_row_15(child_ws, suite_name, sub_suites)
    else:
        write_rows_from_row_15(master_ws, task_name, [])

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def read_testcases_from_local_excel(excel_path: str | Path) -> list[dict[str, Any]]:
    """
    Đọc lại danh sách các dòng Test Suite và Test con từ dòng 15 trở xuống
    trên Sheet tổng của file Excel Local.
    """
    wb = openpyxl.load_workbook(excel_path, data_only=True)
    ws = wb.worksheets[0]
    rows_out: list[dict[str, Any]] = []
    current_suite = "General"

    for r_idx in range(15, ws.max_row + 1):
        b_val = str(ws.cell(row=r_idx, column=2).value or "").strip()
        c_val = str(ws.cell(row=r_idx, column=3).value or "").strip()
        d_val = str(ws.cell(row=r_idx, column=4).value or "").strip()

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
            rows_out.append(
                {
                    "row_type": "testcase",
                    "id": "",
                    "test_suite": current_suite,
                    "muc_dich": b_val,
                    "cac_buoc": c_val,
                    "ket_qua_mong_muon": d_val,
                    "ghi_chu": "",
                }
            )

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
    Tự động tô đậm và đổi màu các nhãn kỹ thuật như [System], [POST], Params:, Response:, Errors:, (CHÚ Ý)... với font Sarabun.
    """
    pattern = re.compile(
        r"(\[[A-Za-zÀ-ỹ0-9_\-\s/&\+()]+\]|\(CHÚ Ý\)\s*:?|(?:Params/Body|Params|Response|Errors|Tech note|Key Columns|PK/FK|Status Lifecycle|Đề xuất)\s*:)",
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


def build_analysis_word_bytes(
    task_name: str,
    analysis_text: str,
    *,
    testcase_count: int = 0,
) -> bytes:
    """
    Sinh tài liệu Word (.docx) Báo cáo Phân tích SRS:
    - Giữ nguyên 100% Trang bìa gốc của bạn (từ TEMPLATE_DOC_CACHE_PATH tải về từ TEMPLATE_DOC_ID).
    - Toàn bộ nội dung sử dụng font chữ Sarabun.
    - Bố cục 6 phần chuẩn Phân tích SRS (Mục tiêu/Phạm vi, Hệ thống & API, Luồng nghiệp vụ & Validation,
      Mô hình Dữ liệu & Trạng thái, Kịch bản Kiểm thử Trọng tâm, Rủi ro & Q&A BA).
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

    normal_style = doc.styles["Normal"]
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
        # Đảm bảo sau trang bìa gốc có khoảng ngắt rõ ràng và căn lề trái cho phần nội dung
        p_break = doc.add_paragraph()
        p_break.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p_break.paragraph_format.space_before = Pt(6)
        p_break.paragraph_format.space_after = Pt(6)

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

    doc.add_paragraph().paragraph_format.space_after = Pt(4)

    # -------------------------------------------------------------------------
    # RENDER 6 PHẦN TRONG BÁO CÁO PHÂN TÍCH SRS (FONT SARABUN)
    # -------------------------------------------------------------------------
    sections = _parse_sections_from_analysis_text(analysis_text)

    def add_section_heading(title_text: str, is_risk: bool = False) -> None:
        h_tbl = doc.add_table(rows=1, cols=1)
        h_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        hc = h_tbl.cell(0, 0)
        hc.width = Cm(16.8)
        bg = "FEF3C7" if is_risk else "F1F5F9"
        left_color = "D97706" if is_risk else "1E3A8A"
        text_rgb = RGBColor(146, 64, 14) if is_risk else RGBColor(30, 58, 138)

        _set_cell_bg(hc, bg)
        _set_cell_margins(hc, top=110, bottom=110, left=180, right=140)
        _set_cell_borders(
            hc,
            left={"val": "single", "sz": "24", "color": left_color},
            top={"val": "single", "sz": "4", "color": "E2E8F0"},
            bottom={"val": "single", "sz": "4", "color": "E2E8F0"},
            right={"val": "single", "sz": "4", "color": "E2E8F0"},
        )
        hp = hc.paragraphs[0]
        hp.alignment = WD_ALIGN_PARAGRAPH.LEFT
        hp.paragraph_format.space_before = Pt(0)
        hp.paragraph_format.space_after = Pt(0)
        hr = hp.add_run(title_text.upper())
        _apply_sarabun_font(hr, 12.0, bold=True, color=text_rgb)

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
        for idx, line in enumerate(lines):
            p = cell.paragraphs[0] if idx == 0 else cell.add_paragraph()
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.space_before = Pt(2)
            p.paragraph_format.space_after = Pt(3)
            p.paragraph_format.line_spacing = 1.25
            clean_line = re.sub(r"^[-*•]\s*", "", line.strip())
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

            sub_parts = [sp.strip() for sp in right_val.split(" | ") if sp.strip()] or [right_val]
            for sp_idx, sp in enumerate(sub_parts):
                p1 = c1.paragraphs[0] if sp_idx == 0 else c1.add_paragraph()
                p1.alignment = WD_ALIGN_PARAGRAPH.LEFT
                p1.paragraph_format.space_before = Pt(1)
                p1.paragraph_format.space_after = Pt(2)
                p1.paragraph_format.line_spacing = 1.2
                prefix = "• " if len(sub_parts) > 1 and sp_idx > 0 else ""
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

    for sec_title, sec_lines in sections:
        up_title = sec_title.upper()
        is_risk_sec = "RỦI RO" in up_title or "ĐIỂM CHƯA RÕ" in up_title or "ĐIỂM KHUYẾT" in up_title
        add_section_heading(sec_title, is_risk=is_risk_sec)

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
