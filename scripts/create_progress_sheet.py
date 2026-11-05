import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

def build_progress_tracker():
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    font_family = "Segoe UI"
    
    font_title = Font(name=font_family, size=15, bold=True, color="1E3A8A")
    font_subtitle = Font(name=font_family, size=9, italic=True, color="475569")
    font_section = Font(name=font_family, size=11, bold=True, color="1E3A8A")
    font_header = Font(name=font_family, size=9, bold=True, color="FFFFFF")
    font_bold = Font(name=font_family, size=9, bold=True)
    font_regular = Font(name=font_family, size=9)
    font_kpi_value = Font(name=font_family, size=18, bold=True, color="1E3A8A")
    font_kpi_sub = Font(name=font_family, size=9, bold=True, color="15803D")
    font_kpi_label = Font(name=font_family, size=8, bold=True, color="475569")

    # Fills
    fill_header = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid") # Dark Navy
    fill_subheader = PatternFill(start_color="2563EB", end_color="2563EB", fill_type="solid") # Royal Blue
    fill_kpi_bg = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
    fill_zebra = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
    
    # Status fills
    fill_done = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid") # Light Green
    font_done = Font(name=font_family, size=9, bold=True, color="166534")
    
    fill_progress = PatternFill(start_color="DBEAFE", end_color="DBEAFE", fill_type="solid") # Light Blue
    font_progress = Font(name=font_family, size=9, bold=True, color="1E40AF")
    
    fill_review = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid") # Light Yellow
    font_review = Font(name=font_family, size=9, bold=True, color="92400E")
    
    fill_todo = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid") # Light Gray
    font_todo = Font(name=font_family, size=9, color="475569")

    # Priority fills
    fill_p_high = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")
    font_p_high = Font(name=font_family, size=9, bold=True, color="991B1B")
    fill_p_med = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid")
    font_p_med = Font(name=font_family, size=9, color="92400E")
    fill_p_low = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
    font_p_low = Font(name=font_family, size=9, color="475569")

    # Usability tier fills
    fill_u_ready = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid")
    font_u_ready = Font(name=font_family, size=9, bold=True, color="166534")
    fill_u_minor = PatternFill(start_color="DBEAFE", end_color="DBEAFE", fill_type="solid")
    font_u_minor = Font(name=font_family, size=9, color="1E40AF")
    fill_u_rework = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid")
    font_u_rework = Font(name=font_family, size=9, color="92400E")
    fill_u_reject = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")
    font_u_reject = Font(name=font_family, size=9, bold=True, color="991B1B")

    # Borders
    thin_border_side = Side(border_style="thin", color="CBD5E1")
    cell_border = Border(left=thin_border_side, right=thin_border_side, top=thin_border_side, bottom=thin_border_side)
    kpi_border = Border(left=thin_border_side, right=thin_border_side, top=thin_border_side, bottom=thin_border_side)

    # Alignments
    align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    align_left = Alignment(horizontal="left", vertical="center", wrap_text=True)
    align_right = Alignment(horizontal="right", vertical="center")
    align_header = Alignment(horizontal="center", vertical="center", wrap_text=True)

    # =========================================================================
    # TAB 1: DASHBOARD & TỔNG QUAN
    # =========================================================================
    ws1 = wb.create_sheet(title="1. Dashboard & TongQuan")
    ws1.views.sheetView[0].showGridLines = True

    # Title
    ws1["A1"] = "BẢNG THEO DÕI TIẾN ĐỘ & HIỆU QUẢ DỰ ÁN TOOL AI (AUTOTC)"
    ws1["A1"].font = font_title
    ws1["A2"] = "Theo dõi tiến độ phát triển hệ thống và đo lường tỷ lệ dùng được thực tế của Test Case do AI sinh ra"
    ws1["A2"].font = font_subtitle

    info_rows = [
        ("Tên dự án:", "AutoTC - AI Automated Test Case Generator", "Ngày bắt đầu:", "15/08/2026"),
        ("Mục tiêu:", "Tự động hóa bóc tách SRS/PRD và sinh Testcase chuẩn hóa sang Google Sheets", "Ngày dự kiến hoàn thành:", "15/11/2026"),
        ("Kiến trúc chính:", "Frontend (JS/Tailwind) + Backend (Python) + Supabase + n8n + Gemini + Google Workspace", "Trạng thái tổng thể:", "Đang triển khai & Tinh chỉnh")
    ]
    
    start_row = 4
    for idx, (lbl1, val1, lbl2, val2) in enumerate(info_rows):
        r = start_row + idx
        ws1[f"A{r}"] = lbl1
        ws1[f"A{r}"].font = font_bold
        ws1[f"B{r}"] = val1
        ws1[f"B{r}"].font = font_regular
        ws1[f"E{r}"] = lbl2
        ws1[f"E{r}"].font = font_bold
        ws1[f"F{r}"] = val2
        ws1[f"F{r}"].font = font_regular
        if lbl2 == "Trạng thái tổng thể:":
            ws1[f"F{r}"].font = font_progress

    # KPI Row 1: Tiến độ phát triển (Development Progress)
    ws1["A8"] = "TIẾN ĐỘ PHÁT TRIỂN CÁC HẠNG MỤC CÔNG VIỆC (WBS PROGRESS)"
    ws1["A8"].font = font_section

    kpis_dev = [
        ("A9", "B10", "A11", "B11", "TỔNG SỐ TASK", "=COUNTA('2. TienDo_ChiTiet'!A5:A48)", "tasks"),
        ("C9", "D10", "C11", "D11", "ĐÃ HOÀN THÀNH", '=COUNTIF(\'2. TienDo_ChiTiet\'!H5:H48, "Hoàn thành")', "tasks"),
        ("E9", "F10", "E11", "F11", "ĐANG THỰC HIỆN", '=COUNTIF(\'2. TienDo_ChiTiet\'!H5:H48, "Đang thực hiện")', "tasks"),
        ("G9", "H10", "G11", "H11", "ĐANG REVIEW / TEST", '=COUNTIF(\'2. TienDo_ChiTiet\'!H5:H48, "Đang review/test")', "tasks"),
        ("I9", "J10", "I11", "J11", "TIẾN ĐỘ CHUNG", "=AVERAGE('2. TienDo_ChiTiet'!I5:I48)", "% hoàn thành")
    ]

    for top_l_val, btm_r_val, top_l_lbl, btm_r_lbl, label, formula, unit in kpis_dev:
        ws1.merge_cells(f"{top_l_val}:{btm_r_val}")
        cell_val = ws1[top_l_val]
        cell_val.value = formula
        cell_val.font = font_kpi_value
        cell_val.alignment = align_center
        cell_val.fill = fill_kpi_bg
        if label == "TIẾN ĐỘ CHUNG":
            cell_val.number_format = "0.0%"

        ws1.merge_cells(f"{top_l_lbl}:{btm_r_lbl}")
        cell_lbl = ws1[top_l_lbl]
        cell_lbl.value = f"{label} ({unit})"
        cell_lbl.font = font_kpi_label
        cell_lbl.alignment = align_center
        cell_lbl.fill = fill_kpi_bg

        for col in range(openpyxl.utils.column_index_from_string(top_l_val[0]), openpyxl.utils.column_index_from_string(btm_r_val[0]) + 1):
            for row in range(int(top_l_val[1:]), int(btm_r_lbl[1:]) + 1):
                col_letter = get_column_letter(col)
                ws1[f"{col_letter}{row}"].border = kpi_border

    # KPI Row 2: Độ dùng được của Test Case AI (AI Usability KPIs)
    ws1["A13"] = "CHỈ SỐ ĐỘ DÙNG ĐƯỢC CỦA TEST CASE DO AI SINH RA (AI TC USABILITY KPIS)"
    ws1["A13"].font = font_section

    kpis_usability = [
        ("A14", "B15", "A16", "B16", "TỔNG SỐ TC ĐÃ ĐÁNH GIÁ", "='4. DanhGia_DoDungDuoc_TC'!E35", "test cases"),
        ("C14", "D15", "C16", "D16", "DÙNG ĐƯỢC NGAY", "='4. DanhGia_DoDungDuoc_TC'!F35", "test cases (61.9%)"),
        ("E14", "F15", "E16", "F16", "SỬA NHỎ LÀ DÙNG ĐƯỢC", "='4. DanhGia_DoDungDuoc_TC'!G35", "test cases (24.3%)"),
        ("G14", "H15", "G16", "H16", "TỶ LỆ DÙNG ĐƯỢC TỔNG THỂ", "='4. DanhGia_DoDungDuoc_TC'!J35", "Mục tiêu: ≥ 85%"),
        ("I14", "J15", "I16", "J16", "TIẾT KIỆM THỜI GIAN", "='4. DanhGia_DoDungDuoc_TC'!L35", "giờ làm việc của Tester")
    ]

    for top_l_val, btm_r_val, top_l_lbl, btm_r_lbl, label, formula, unit in kpis_usability:
        ws1.merge_cells(f"{top_l_val}:{btm_r_val}")
        cell_val = ws1[top_l_val]
        cell_val.value = formula
        cell_val.font = font_kpi_value
        cell_val.alignment = align_center
        cell_val.fill = fill_kpi_bg
        if label == "TỶ LỆ DÙNG ĐƯỢC TỔNG THỂ":
            cell_val.number_format = "0.0%"
            cell_val.font = Font(name=font_family, size=18, bold=True, color="15803D")

        ws1.merge_cells(f"{top_l_lbl}:{btm_r_lbl}")
        cell_lbl = ws1[top_l_lbl]
        cell_lbl.value = f"{label} ({unit})"
        cell_lbl.font = font_kpi_label
        cell_lbl.alignment = align_center
        cell_lbl.fill = fill_kpi_bg

        for col in range(openpyxl.utils.column_index_from_string(top_l_val[0]), openpyxl.utils.column_index_from_string(btm_r_val[0]) + 1):
            for row in range(int(top_l_val[1:]), int(btm_r_lbl[1:]) + 1):
                col_letter = get_column_letter(col)
                ws1[f"{col_letter}{row}"].border = kpi_border

    # Section 3: Module Progress Summary Table (Row 18+)
    ws1["A18"] = "THEO DÕI TIẾN ĐỘ THEO PHÂN HỆ (MODULE BREAKDOWN)"
    ws1["A18"].font = font_section

    mod_headers = ["STT", "Phân hệ / Module", "Số lượng Task", "Đã xong", "Đang làm", "Review/Test", "Chưa làm", "Tỷ lệ hoàn thành", "Đánh giá trạng thái"]
    for c_idx, h in enumerate(mod_headers, 1):
        cell = ws1.cell(row=20, column=c_idx, value=h)
        cell.font = font_header
        cell.fill = fill_header
        cell.alignment = align_header
        cell.border = cell_border
    ws1.row_dimensions[20].height = 24

    modules_data = [
        ("1", "Kiến trúc & Hạ tầng (Infra, DB Supabase, ChromaDB, Tailscale)", "=COUNTIF('2. TienDo_ChiTiet'!C5:C48, \"*Hạ tầng*\")", "=COUNTIFS('2. TienDo_ChiTiet'!C5:C48, \"*Hạ tầng*\", '2. TienDo_ChiTiet'!H5:H48, \"Hoàn thành\")", "=COUNTIFS('2. TienDo_ChiTiet'!C5:C48, \"*Hạ tầng*\", '2. TienDo_ChiTiet'!H5:H48, \"Đang thực hiện\")", "=COUNTIFS('2. TienDo_ChiTiet'!C5:C48, \"*Hạ tầng*\", '2. TienDo_ChiTiet'!H5:H48, \"Đang review/test\")", "=COUNTIFS('2. TienDo_ChiTiet'!C5:C48, \"*Hạ tầng*\", '2. TienDo_ChiTiet'!H5:H48, \"Chưa bắt đầu\")", "=AVERAGEIFS('2. TienDo_ChiTiet'!I5:I48, '2. TienDo_ChiTiet'!C5:C48, \"*Hạ tầng*\")", "Đã hoàn thành phần cốt lõi"),
        ("2", "Backend Service (Python HTTP/Router/Controller/CRUD)", "=COUNTIF('2. TienDo_ChiTiet'!C5:C48, \"*Backend*\")", "=COUNTIFS('2. TienDo_ChiTiet'!C5:C48, \"*Backend*\", '2. TienDo_ChiTiet'!H5:H48, \"Hoàn thành\")", "=COUNTIFS('2. TienDo_ChiTiet'!C5:C48, \"*Backend*\", '2. TienDo_ChiTiet'!H5:H48, \"Đang thực hiện\")", "=COUNTIFS('2. TienDo_ChiTiet'!C5:C48, \"*Backend*\", '2. TienDo_ChiTiet'!H5:H48, \"Đang review/test\")", "=COUNTIFS('2. TienDo_ChiTiet'!C5:C48, \"*Backend*\", '2. TienDo_ChiTiet'!H5:H48, \"Chưa bắt đầu\")", "=AVERAGEIFS('2. TienDo_ChiTiet'!I5:I48, '2. TienDo_ChiTiet'!C5:C48, \"*Backend*\")", "Hoạt động ổn định, cần bổ sung JWT"),
        ("3", "Google Workspace Integration (Drive, Docs, Sheets, OAuth)", "=COUNTIF('2. TienDo_ChiTiet'!C5:C48, \"*Google Workspace*\")", "=COUNTIFS('2. TienDo_ChiTiet'!C5:C48, \"*Google Workspace*\", '2. TienDo_ChiTiet'!H5:H48, \"Hoàn thành\")", "=COUNTIFS('2. TienDo_ChiTiet'!C5:C48, \"*Google Workspace*\", '2. TienDo_ChiTiet'!H5:H48, \"Đang thực hiện\")", "=COUNTIFS('2. TienDo_ChiTiet'!C5:C48, \"*Google Workspace*\", '2. TienDo_ChiTiet'!H5:H48, \"Đang review/test\")", "=COUNTIFS('2. TienDo_ChiTiet'!C5:C48, \"*Google Workspace*\", '2. TienDo_ChiTiet'!H5:H48, \"Chưa bắt đầu\")", "=AVERAGEIFS('2. TienDo_ChiTiet'!I5:I48, '2. TienDo_ChiTiet'!C5:C48, \"*Google Workspace*\")", "Đã xong Service Account + Desktop OAuth"),
        ("4", "Frontend Dashboard (Quản lý bài toán, Form upload, Timer)", "=COUNTIF('2. TienDo_ChiTiet'!C5:C48, \"*Frontend Dashboard*\")", "=COUNTIFS('2. TienDo_ChiTiet'!C5:C48, \"*Frontend Dashboard*\", '2. TienDo_ChiTiet'!H5:H48, \"Hoàn thành\")", "=COUNTIFS('2. TienDo_ChiTiet'!C5:C48, \"*Frontend Dashboard*\", '2. TienDo_ChiTiet'!H5:H48, \"Đang thực hiện\")", "=COUNTIFS('2. TienDo_ChiTiet'!C5:C48, \"*Frontend Dashboard*\", '2. TienDo_ChiTiet'!H5:H48, \"Đang review/test\")", "=COUNTIFS('2. TienDo_ChiTiet'!C5:C48, \"*Frontend Dashboard*\", '2. TienDo_ChiTiet'!H5:H48, \"Chưa bắt đầu\")", "=AVERAGEIFS('2. TienDo_ChiTiet'!I5:I48, '2. TienDo_ChiTiet'!C5:C48, \"*Frontend Dashboard*\")", "Đã hoàn thiện đầy đủ UX/UI"),
        ("5", "Module Review & Phê duyệt Testcase (Review Modal + Page)", "=COUNTIF('2. TienDo_ChiTiet'!C5:C48, \"*Review Module*\")", "=COUNTIFS('2. TienDo_ChiTiet'!C5:C48, \"*Review Module*\", '2. TienDo_ChiTiet'!H5:H48, \"Hoàn thành\")", "=COUNTIFS('2. TienDo_ChiTiet'!C5:C48, \"*Review Module*\", '2. TienDo_ChiTiet'!H5:H48, \"Đang thực hiện\")", "=COUNTIFS('2. TienDo_ChiTiet'!C5:C48, \"*Review Module*\", '2. TienDo_ChiTiet'!H5:H48, \"Đang review/test\")", "=COUNTIFS('2. TienDo_ChiTiet'!C5:C48, \"*Review Module*\", '2. TienDo_ChiTiet'!H5:H48, \"Chưa bắt đầu\")", "=AVERAGEIFS('2. TienDo_ChiTiet'!I5:I48, '2. TienDo_ChiTiet'!C5:C48, \"*Review Module*\")", "Hỗ trợ natural sorting & feedback prompt"),
        ("6", "AI Pipeline & Prompt Engineering (n8n, Dify, Gemini)", "=COUNTIF('2. TienDo_ChiTiet'!C5:C48, \"*AI Pipeline*\")", "=COUNTIFS('2. TienDo_ChiTiet'!C5:C48, \"*AI Pipeline*\", '2. TienDo_ChiTiet'!H5:H48, \"Hoàn thành\")", "=COUNTIFS('2. TienDo_ChiTiet'!C5:C48, \"*AI Pipeline*\", '2. TienDo_ChiTiet'!H5:H48, \"Đang thực hiện\")", "=COUNTIFS('2. TienDo_ChiTiet'!C5:C48, \"*AI Pipeline*\", '2. TienDo_ChiTiet'!H5:H48, \"Đang review/test\")", "=COUNTIFS('2. TienDo_ChiTiet'!C5:C48, \"*AI Pipeline*\", '2. TienDo_ChiTiet'!H5:H48, \"Chưa bắt đầu\")", "=AVERAGEIFS('2. TienDo_ChiTiet'!I5:I48, '2. TienDo_ChiTiet'!C5:C48, \"*AI Pipeline*\")", "Đang tinh chỉnh prompt giảm ảo giác & tăng độ dùng được"),
        ("7", "Kiểm thử chất lượng & Đánh giá Độ dùng được (QA / UAT)", "=COUNTIF('2. TienDo_ChiTiet'!C5:C48, \"*Kiểm thử QA*\")", "=COUNTIFS('2. TienDo_ChiTiet'!C5:C48, \"*Kiểm thử QA*\", '2. TienDo_ChiTiet'!H5:H48, \"Hoàn thành\")", "=COUNTIFS('2. TienDo_ChiTiet'!C5:C48, \"*Kiểm thử QA*\", '2. TienDo_ChiTiet'!H5:H48, \"Đang thực hiện\")", "=COUNTIFS('2. TienDo_ChiTiet'!C5:C48, \"*Kiểm thử QA*\", '2. TienDo_ChiTiet'!H5:H48, \"Đang review/test\")", "=COUNTIFS('2. TienDo_ChiTiet'!C5:C48, \"*Kiểm thử QA*\", '2. TienDo_ChiTiet'!H5:H48, \"Chưa bắt đầu\")", "=AVERAGEIFS('2. TienDo_ChiTiet'!I5:I48, '2. TienDo_ChiTiet'!C5:C48, \"*Kiểm thử QA*\")", "Đang khảo sát đo lường trên 15 bài toán thực tế"),
        ("8", "Bảo mật & Vận hành Production (Security, DevOps, Host)", "=COUNTIF('2. TienDo_ChiTiet'!C5:C48, \"*Bảo mật & DevOps*\")", "=COUNTIFS('2. TienDo_ChiTiet'!C5:C48, \"*Bảo mật & DevOps*\", '2. TienDo_ChiTiet'!H5:H48, \"Hoàn thành\")", "=COUNTIFS('2. TienDo_ChiTiet'!C5:C48, \"*Bảo mật & DevOps*\", '2. TienDo_ChiTiet'!H5:H48, \"Đang thực hiện\")", "=COUNTIFS('2. TienDo_ChiTiet'!C5:C48, \"*Bảo mật & DevOps*\", '2. TienDo_ChiTiet'!H5:H48, \"Đang review/test\")", "=COUNTIFS('2. TienDo_ChiTiet'!C5:C48, \"*Bảo mật & DevOps*\", '2. TienDo_ChiTiet'!H5:H48, \"Chưa bắt đầu\")", "=AVERAGEIFS('2. TienDo_ChiTiet'!I5:I48, '2. TienDo_ChiTiet'!C5:C48, \"*Bảo mật & DevOps*\")", "Cần hoàn thiện Supabase RLS và token webhook")
    ]

    for r_idx, row_data in enumerate(modules_data, 21):
        ws1.row_dimensions[r_idx].height = 20
        for c_idx, val in enumerate(row_data, 1):
            cell = ws1.cell(row=r_idx, column=c_idx, value=val)
            cell.font = font_regular
            cell.border = cell_border
            if c_idx == 1:
                cell.alignment = align_center
            elif c_idx == 2:
                cell.alignment = align_left
                cell.font = font_bold
            elif 3 <= c_idx <= 7:
                cell.alignment = align_center
            elif c_idx == 8:
                cell.alignment = align_center
                cell.font = font_bold
                cell.number_format = "0.0%"
            else:
                cell.alignment = align_left

    tot_row = 21 + len(modules_data)
    ws1.row_dimensions[tot_row].height = 22
    ws1.cell(row=tot_row, column=1, value="")
    cell_tot_lbl = ws1.cell(row=tot_row, column=2, value="TỔNG CỘNG HỆ THỐNG")
    cell_tot_lbl.font = font_bold
    cell_tot_lbl.alignment = align_left
    
    for c_idx in range(3, 8):
        c_letter = get_column_letter(c_idx)
        cell = ws1.cell(row=tot_row, column=c_idx, value=f"=SUM({c_letter}21:{c_letter}{tot_row-1})")
        cell.font = font_bold
        cell.alignment = align_center
        cell.border = cell_border
    
    cell_p = ws1.cell(row=tot_row, column=8, value=f"=AVERAGE(H21:H{tot_row-1})")
    cell_p.font = font_bold
    cell_p.alignment = align_center
    cell_p.number_format = "0.0%"
    cell_p.border = cell_border

    cell_stat = ws1.cell(row=tot_row, column=9, value="Dự án đang bám sát tiến độ")
    cell_stat.font = font_bold
    cell_stat.alignment = align_left
    cell_stat.border = cell_border

    for c in range(1, 10):
        ws1.cell(row=tot_row, column=c).border = cell_border
        ws1.cell(row=tot_row, column=c).fill = fill_zebra

    # =========================================================================
    # TAB 2: TIẾN ĐỘ CHI TIẾT (WBS)
    # =========================================================================
    ws2 = wb.create_sheet(title="2. TienDo_ChiTiet")
    ws2.views.sheetView[0].showGridLines = True

    ws2["A1"] = "DANH SÁCH CHI TIẾT CÁC HẠNG MỤC PHÁT TRIỂN (WBS - WORK BREAKDOWN STRUCTURE)"
    ws2["A1"].font = font_title
    ws2["A2"] = "Theo dõi chi tiết trạng thái, người phụ trách, tiến độ thực hiện và sản phẩm bàn giao của từng task"
    ws2["A2"].font = font_subtitle

    wbs_headers = [
        "STT", "Mã Task", "Phân hệ / Module", "Hạng mục công việc",
        "Chi tiết kỹ thuật & Nghiệp vụ", "Độ ưu tiên", "Người phụ trách",
        "Trạng thái", "Tiến độ (%)", "Ngày bắt đầu", "Hạn xong", "Ngày xong TT", "Sản phẩm bàn giao / Ghi chú"
    ]

    for c_idx, h in enumerate(wbs_headers, 1):
        cell = ws2.cell(row=4, column=c_idx, value=h)
        cell.font = font_header
        cell.fill = fill_header
        cell.alignment = align_header
        cell.border = cell_border
    ws2.row_dimensions[4].height = 26

    tasks = [
        # INFRA & DATABASE
        ("1", "INF-01", "Kiến trúc & Hạ tầng", "Thiết kế kiến trúc hệ thống phân tán", "Xác định luồng tương tác FE -> BE -> Supabase -> n8n -> LLM Gemini -> Google Workspace", "Cao", "Tech Lead", "Hoàn thành", 1.0, "2026-08-15", "2026-08-20", "2026-08-19", "Tài liệu thiết kế kiến trúc hệ thống & README"),
        ("2", "INF-02", "Kiến trúc & Hạ tầng", "Khởi tạo CSDL Supabase (PostgreSQL)", "Tạo bảng public.problems, thiết lập các trường UUID, legacy_id, URLs, status, assignee, index", "Cao", "Data Engineer", "Hoàn thành", 1.0, "2026-08-20", "2026-08-25", "2026-08-24", "Database Supabase hoạt động & script migrate"),
        ("3", "INF-03", "Kiến trúc & Hạ tầng", "Cấu hình ChromaDB Vector Database", "Tích hợp ChromaDB lưu trữ vector nhúng tài liệu đặc tả & testcase mẫu hỗ trợ RAG", "Trung bình", "AI Engineer", "Hoàn thành", 1.0, "2026-08-25", "2026-08-30", "2026-08-29", "File Chroma SQLite3 sẵn sàng trong BE/chroma_db"),
        ("4", "INF-04", "Kiến trúc & Hạ tầng", "Thiết lập mạng Tailscale Tunnel", "Public Dify qua cổng 8888 và n8n qua HTTPS 8443 chuyển tiếp an toàn nội bộ", "Cao", "DevOps", "Hoàn thành", 1.0, "2026-09-01", "2026-09-05", "2026-09-04", "Lệnh tailscale funnel & kết nối webhook ổn định"),

        # BACKEND
        ("5", "BE-01", "Backend Service", "Xây dựng khung kiến trúc Backend Python", "HTTP Server, Router tùy biến dispatch theo method + path, Web handler, ApiResponse chuẩn hóa", "Cao", "Backend Dev", "Hoàn thành", 1.0, "2026-09-05", "2026-09-10", "2026-09-09", "Cấu trúc mã nguồn BE/app.py, router.py, web/"),
        ("6", "BE-02", "Backend Service", "Xây dựng SupabaseRepository", "Thực hiện CRUD bài toán với Supabase REST API qua urllib chuẩn, mapping cấu trúc DTO", "Cao", "Backend Dev", "Hoàn thành", 1.0, "2026-09-10", "2026-09-15", "2026-09-14", "Module BE/repositories/supabase_repository.py"),
        ("7", "BE-03", "Backend Service", "API Thêm bài toán (Create Task)", "Nhận multipart/form-data, hỗ trợ thêm bằng Link tài liệu gốc hoặc Upload file tài liệu", "Cao", "Backend Dev", "Hoàn thành", 1.0, "2026-09-15", "2026-09-20", "2026-09-19", "Endpoint POST /api/tasks"),
        ("8", "BE-04", "Backend Service", "API Sửa, Xóa và Đổi trạng thái bài toán", "Chỉnh sửa tên/URL tài liệu gốc, xóa bài toán khỏi Supabase, cập nhật trạng thái làm việc", "Cao", "Backend Dev", "Hoàn thành", 1.0, "2026-09-20", "2026-09-24", "2026-09-23", "Endpoints PUT /api/tasks, DELETE /api/tasks, PATCH /status"),
        ("9", "BE-05", "Backend Service", "API Chuyển giao người phụ trách (Transfer)", "Cập nhật người làm (Assignee) cho bài toán trong Supabase kèm kiểm tra quyền", "Trung bình", "Backend Dev", "Hoàn thành", 1.0, "2026-09-25", "2026-09-27", "2026-09-26", "Endpoint PATCH /api/tasks/assignee"),
        ("10", "BE-06", "Backend Service", "Đồng bộ thời gian chạy (ExecutionTracker)", "Lưu trữ mốc bắt đầu chạy của bài toán trên backend để đồng bộ thời gian chạy giữa nhiều client", "Cao", "Backend Dev", "Hoàn thành", 1.0, "2026-09-28", "2026-10-02", "2026-10-01", "Module BE/services/execution_tracker.py, API executions"),
        ("11", "BE-07", "Backend Service", "Tiếp nhận kết quả từ AI (AiCallbackService)", "Tiếp nhận webhook callback từ n8n/Worker, cập nhật trạng thái, lưu link Docs & link Sheet", "Cao", "Backend Dev", "Hoàn thành", 1.0, "2026-10-02", "2026-10-06", "2026-10-05", "Endpoint POST /api/tasks/ai-callback"),
        ("12", "BE-08", "Backend Service", "Middleware xác thực quyền Admin", "Kiểm tra quyền quản trị qua header tương thích X-User-Role và chuẩn bị tích hợp Supabase JWT", "Cao", "Backend Dev", "Đang thực hiện", 0.7, "2026-10-15", "2026-11-05", "", "Module BE/middleware/auth.py, cần nâng cấp JWT chuẩn"),

        # GOOGLE WORKSPACE
        ("13", "GW-01", "Google Workspace", "Tích hợp Service Account Drive & Sheets", "Cấu hình Google Workspace API thao tác file trên Shared Drive tránh lỗi quota", "Cao", "Backend Dev", "Hoàn thành", 1.0, "2026-09-12", "2026-09-18", "2026-09-17", "BE/repositories/google_workspace.py"),
        ("14", "GW-02", "Google Workspace", "Giải pháp Desktop OAuth cho Google cá nhân", "Xây dựng kịch bản setup_google_oauth.py lấy authorized-user.json vượt quota My Drive", "Cao", "Backend Dev", "Hoàn thành", 1.0, "2026-10-07", "2026-10-12", "2026-10-11", "Script BE/scripts/setup_google_oauth.py hoàn chỉnh"),
        ("15", "GW-03", "Google Workspace", "Chuẩn hóa định dạng file tải lên", "Tự động convert file docx, doc, pdf, txt sang Google Docs và xls, xlsx sang Google Sheets", "Cao", "Backend Dev", "Hoàn thành", 1.0, "2026-10-08", "2026-10-13", "2026-10-12", "Module BE/services/file_processing.py"),
        ("16", "GW-04", "Google Workspace", "Tự động tạo Google Doc Phân tích yêu cầu", "Hàm create_analysis_doc tự động tạo văn bản tóm tắt phân tích đặc tả từ AI và cấp quyền đọc", "Trung bình", "Backend Dev", "Hoàn thành", 1.0, "2026-10-10", "2026-10-15", "2026-10-14", "Xuất file Doc phân tích tự động"),
        ("17", "GW-05", "Google Workspace", "Tự động tạo Google Sheet Testcase", "Hàm create_testcase_sheet tạo sheet bảng biểu testcase với đầy đủ cột ID, Step, Expected", "Cao", "Backend Dev", "Hoàn thành", 1.0, "2026-10-12", "2026-10-17", "2026-10-16", "Xuất file Sheet testcase chuẩn hóa"),

        # FRONTEND DASHBOARD
        ("18", "FE-01", "Frontend Dashboard", "Thiết kế Dashboard giao diện người dùng", "Giao diện hiện đại sử dụng Tailwind CSS, font chữ Outfit, hệ thống Lucide Icons đồng nhất", "Cao", "Frontend Dev", "Hoàn thành", 1.0, "2026-09-01", "2026-09-08", "2026-09-07", "Mã nguồn FE/index.html & style.css"),
        ("19", "FE-02", "Frontend Dashboard", "Form Thêm bài toán URL & Import File", "Hỗ trợ 2 chế độ: Nhập danh sách URL hoặc tải file đính kèm (.doc, .docx, .xls, .xlsx, .pdf, .txt)", "Cao", "Frontend Dev", "Hoàn thành", 1.0, "2026-09-08", "2026-09-14", "2026-09-13", "Form phản hồi tức thời & validation dữ liệu"),
        ("20", "FE-03", "Frontend Dashboard", "Bảng danh sách bài toán & Tìm kiếm tức thời", "Bảng dữ liệu: checkbox chọn nhiều, tìm kiếm bài toán tức thời, hiển thị trạng thái và người làm", "Cao", "Frontend Dev", "Hoàn thành", 1.0, "2026-09-14", "2026-09-18", "2026-09-17", "Component Table có phân trang và filter"),
        ("21", "FE-04", "Frontend Dashboard", "Modal cập nhật & quản lý link bài toán", "Cho phép sửa tên bài toán, thêm/xóa linh hoạt danh sách nhiều link tài liệu gốc", "Trung bình", "Frontend Dev", "Hoàn thành", 1.0, "2026-09-18", "2026-09-22", "2026-09-21", "Modal Edit trực quan"),
        ("22", "FE-05", "Frontend Dashboard", "Modal Chạy AI & tùy biến Prompt bổ sung", "Popup cấu hình chạy AI: cho phép nhập yêu cầu bổ sung (negative case, boundary case, bảo mật)", "Cao", "Frontend Dev", "Hoàn thành", 1.0, "2026-09-22", "2026-09-26", "2026-09-25", "Modal runAIModal và tích hợp trigger sang n8n"),
        ("23", "FE-06", "Frontend Dashboard", "Đồng bộ đồng hồ đếm thời gian thực", "Hiển thị thời gian chạy AI theo giây/phút, tự động phục hồi state khi tải lại trang", "Trung bình", "Frontend Dev", "Hoàn thành", 1.0, "2026-09-26", "2026-09-30", "2026-09-29", "Module formatElapsedTime và persistProcessingState"),

        # REVIEW MODULE
        ("24", "REV-01", "Review Module", "Màn hình Duyệt Testcase chuyên biệt", "Trang toàn màn hình review.html cho phép xem xét, phân tích chuyên sâu từng kịch bản test", "Cao", "Frontend Dev", "Hoàn thành", 1.0, "2026-10-05", "2026-10-12", "2026-10-11", "File FE/review.html với giao diện responsive"),
        ("25", "REV-02", "Review Module", "Modal Duyệt Testcase nhanh trên Dashboard", "Tích hợp modal testcaseReviewModal xem trước và duyệt ngay không cần chuyển tab", "Cao", "Frontend Dev", "Hoàn thành", 1.0, "2026-10-12", "2026-10-16", "2026-10-15", "Modal preview trên FE/index.html"),
        ("26", "REV-03", "Review Module", "Cơ chế Phê duyệt / Từ chối (Approve/Reject)", "Nút Giữ lại hoặc Bỏ từng testcase, tự động đổi màu trạng thái thẻ (Xanh lá / Đỏ)", "Cao", "Frontend Dev", "Hoàn thành", 1.0, "2026-10-16", "2026-10-19", "2026-10-18", "Tương tác mượt mà & lưu trữ trạng thái duyệt"),
        ("27", "REV-04", "Review Module", "Bộ lọc trạng thái & Thao tác hàng loạt", "Filter: Tất cả, Chưa duyệt, Đã giữ, Đã bỏ; Nút bấm nhanh 'Giữ tất cả' và 'Bỏ tất cả'", "Trung bình", "Frontend Dev", "Hoàn thành", 1.0, "2026-10-19", "2026-10-22", "2026-10-21", "Bulk action toolbar và bộ lọc tab trực quan"),
        ("28", "REV-05", "Review Module", "Thuật toán sắp xếp tự nhiên Natural Numerical Order", "Sắp xếp testcase thông minh theo thứ tự số học (TC01, TC02... TC10) kèm nút đảo chiều", "Trung bình", "Frontend Dev", "Hoàn thành", 1.0, "2026-10-22", "2026-10-25", "2026-10-24", "Hàm compareTestcaseOrder và nút đổi chiều"),
        ("29", "REV-06", "Review Module", "Khung Góp ý & Điều chỉnh testcase bằng AI", "Revision feedback panel: Gợi ý nhanh các điểm cần sửa và gửi prompt yêu cầu AI tạo lại", "Cao", "Frontend Dev", "Hoàn thành", 1.0, "2026-10-25", "2026-10-28", "2026-10-27", "Panel testcaseReviewRevision với preset tags"),

        # AI PIPELINE & PROMPT ENGINEERING
        ("30", "AI-01", "AI Pipeline", "Thiết kế Workflow n8n xử lý dữ liệu kiểm thử", "Tạo luồng Webhook nhận request -> Tải tài liệu -> Chuyển định dạng -> Gọi LLM -> Phản hồi", "Cao", "AI Engineer", "Hoàn thành", 1.0, "2026-09-10", "2026-09-20", "2026-09-19", "Workflow n8n hoàn chỉnh và file JSON xuất"),
        ("31", "AI-02", "AI Pipeline", "Tích hợp mô hình Gemini 1.5 Pro / Flash qua Dify", "Kết nối API Gemini xử lý bối cảnh dài (Long-context window) để đọc trọn bộ tài liệu lớn", "Cao", "AI Engineer", "Hoàn thành", 1.0, "2026-09-20", "2026-09-28", "2026-09-27", "Ứng dụng Dify Chat/Completion kết nối Gemini"),
        ("32", "AI-03", "AI Pipeline", "Prompt Engineering bóc tách yêu cầu đặc tả (SRS)", "Xây dựng prompt chuyên sâu phân tích thực thể, luồng nghiệp vụ chính và các ngoại lệ", "Cao", "AI Engineer", "Hoàn thành", 1.0, "2026-09-28", "2026-10-06", "2026-10-05", "Tập System Prompt phân tích nghiệp vụ"),
        ("33", "AI-04", "AI Pipeline", "Prompt Engineering sinh Testcase chuẩn quốc tế", "Định dạng JSON output gồm Testcase ID, Module, Pre-condition, Test Steps, Test Data, Expected Result", "Cao", "AI Engineer", "Hoàn thành", 1.0, "2026-10-06", "2026-10-14", "2026-10-13", "Prompt sinh cấu trúc JSON kiểm thử chuẩn"),
        ("34", "AI-05", "AI Pipeline", "Tối ưu sinh kịch bản biên và kiểm thử phân quyền", "Nâng cấp prompt bao phủ các trường hợp biên, SQL Injection cơ bản, kiểm tra phân quyền User/Admin", "Cao", "AI Engineer", "Đang thực hiện", 0.8, "2026-10-14", "2026-11-04", "", "Bộ Prompt nâng cao đạt độ bao phủ 85%"),
        ("35", "AI-06", "AI Pipeline", "Tích hợp ChromaDB nạp mẫu Test Case chuẩn vào Context", "Kỹ thuật RAG đưa các mẫu test case tiêu biểu của dự án vào prompt để tăng độ chính xác", "Trung bình", "AI Engineer", "Đang thực hiện", 0.6, "2026-10-20", "2026-11-08", "", "Pipeline RAG thử nghiệm với ChromaDB"),
        ("36", "AI-07", "AI Pipeline", "Tối ưu Prompt giảm ảo giác và tăng độ dùng được", "Cải tiến prompt dựa trên phản hồi của Tester: ép format data cụ thể, cấm bịa tính năng ngoài SRS", "Cao", "AI Engineer", "Đang thực hiện", 0.75, "2026-10-25", "2026-11-08", "", "Prompt v2.1 tăng độ dùng ngay từ 50% lên 62%"),

        # QA & KIỂM THỬ
        ("37", "QA-01", "Kiểm thử QA", "Xây dựng bộ Unit Test Backend", "Viết test_router, test_service, test_supabase_repository, test_file_processing kiểm tra tự động", "Cao", "QA / Tester", "Hoàn thành", 1.0, "2026-10-08", "2026-10-15", "2026-10-14", "Thư mục BE/tests/ với độ bao phủ > 80%"),
        ("38", "QA-02", "Kiểm thử QA", "Kiểm thử luồng tích hợp End-to-End (E2E)", "Kiểm thử toàn bộ luồng từ tạo bài toán, upload file, trigger AI, nhận callback đến duyệt testcase", "Cao", "QA / Tester", "Đang review/test", 0.85, "2026-10-16", "2026-11-03", "", "Kịch bản kiểm thử E2E và báo cáo lỗi"),
        ("39", "QA-03", "Kiểm thử QA", "Xây dựng khung đánh giá độ dùng được của Test Case", "Thiết lập 4 mức phân loại độ dùng được (Dùng ngay, Sửa nhỏ, Viết lại, Bỏ) và công thức tính Usability", "Cao", "QA Lead", "Hoàn thành", 1.0, "2026-10-18", "2026-10-24", "2026-10-23", "Khung tiêu chuẩn đánh giá Usability Framework"),
        ("40", "QA-04", "Kiểm thử QA", "Khảo sát đo lường độ dùng được trên 15 bài toán thực tế", "Tester trực tiếp chạy và đánh giá độ dùng được trên 450+ Test Case sinh ra từ dự án thật", "Cao", "QA Team", "Đang thực hiện", 0.8, "2026-10-24", "2026-11-09", "", "Báo cáo nghiệm thu độ dùng được đạt 86.2%"),

        # BẢO MẬT & DEVOPS
        ("41", "SEC-01", "Bảo mật & DevOps", "Kích hoạt Supabase Auth & Row Level Security (RLS)", "Thiết lập phân quyền người dùng theo tài khoản, bảo vệ bảng public.problems", "Cao", "DevOps", "Đang thực hiện", 0.6, "2026-10-18", "2026-11-06", "", "Chính sách RLS và xác thực Supabase"),
        ("42", "SEC-02", "Bảo mật & DevOps", "Bảo mật Webhook n8n và Backend API", "Thêm secret token xác thực hai chiều giữa Backend và Webhook n8n tránh tấn công giả mạo", "Cao", "DevOps", "Chưa bắt đầu", 0.3, "2026-11-01", "2026-11-12", "", "Module xác thực Webhook Token"),
        ("43", "PROD-01", "Bảo mật & DevOps", "Triển khai Frontend Production", "Host giao diện lên hệ thống domain quanlv.io.vn với chứng chỉ SSL/TLS bảo mật", "Trung bình", "DevOps", "Hoàn thành", 1.0, "2026-09-25", "2026-09-28", "2026-09-27", "Domain quanlv.io.vn hoạt động ổn định"),
        ("44", "PROD-02", "Bảo mật & DevOps", "Đóng gói triển khai tự động (Docker / Script)", "Tối ưu script run_backend.bat và đóng gói Docker container chạy nền tự khởi động lại khi lỗi", "Trung bình", "DevOps", "Đang thực hiện", 0.5, "2026-10-26", "2026-11-14", "", "Dockerfile & script khởi chạy tự động")
    ]

    for r_idx, task_info in enumerate(tasks, 5):
        ws2.row_dimensions[r_idx].height = 20
        row_fill = fill_zebra if r_idx % 2 == 0 else PatternFill(fill_type=None)
        
        for c_idx, val in enumerate(task_info, 1):
            cell = ws2.cell(row=r_idx, column=c_idx, value=val)
            cell.font = font_regular
            cell.border = cell_border
            cell.fill = row_fill

            if c_idx == 1:
                cell.alignment = align_center
            elif c_idx == 2:
                cell.alignment = align_center
                cell.font = font_bold
            elif c_idx == 3:
                cell.alignment = align_left
            elif c_idx == 4:
                cell.alignment = align_left
                cell.font = font_bold
            elif c_idx == 5:
                cell.alignment = align_left
            elif c_idx == 6:
                cell.alignment = align_center
                if val == "Cao":
                    cell.fill = fill_p_high
                    cell.font = font_p_high
                elif val == "Trung bình":
                    cell.fill = fill_p_med
                    cell.font = font_p_med
                else:
                    cell.fill = fill_p_low
                    cell.font = font_p_low
            elif c_idx == 7:
                cell.alignment = align_center
            elif c_idx == 8:
                cell.alignment = align_center
                if val == "Hoàn thành":
                    cell.fill = fill_done
                    cell.font = font_done
                elif val == "Đang thực hiện":
                    cell.fill = fill_progress
                    cell.font = font_progress
                elif val == "Đang review/test":
                    cell.fill = fill_review
                    cell.font = font_review
                else:
                    cell.fill = fill_todo
                    cell.font = font_todo
            elif c_idx == 9:
                cell.alignment = align_center
                cell.number_format = "0%"
                cell.font = font_bold
            elif 10 <= c_idx <= 12:
                cell.alignment = align_center
            elif c_idx == 13:
                cell.alignment = align_left

    # =========================================================================
    # TAB 3: DANH SÁCH TÍNH NĂNG (FEATURES & ROADMAP)
    # =========================================================================
    ws3 = wb.create_sheet(title="3. DanhSach_TinhNang")
    ws3.views.sheetView[0].showGridLines = True

    ws3["A1"] = "DANH SÁCH TÍNH NĂNG & LỘ TRÌNH PHÁT TRIỂN (FEATURE SPECIFICATION)"
    ws3["A1"].font = font_title
    ws3["A2"] = "Mô tả chi tiết các tính năng cốt lõi của Tool AI AutoTC và phân bổ phiên bản phát hành"
    ws3["A2"].font = font_subtitle

    feat_headers = ["STT", "Nhóm tính năng (Module)", "Tên tính năng", "Mô tả chi tiết & Lợi ích", "Công nghệ áp dụng", "Mức độ phức tạp", "Phiên bản", "Trạng thái tính năng"]
    for c_idx, h in enumerate(feat_headers, 1):
        cell = ws3.cell(row=4, column=c_idx, value=h)
        cell.font = font_header
        cell.fill = fill_header
        cell.alignment = align_header
        cell.border = cell_border
    ws3.row_dimensions[4].height = 26

    features_list = [
        ("1", "Quản lý bài toán", "Thêm bài toán đa nguồn", "Hỗ trợ nhập trực tiếp danh sách URL Docs/Drive hoặc tải lên các tệp tài liệu local (.docx, .xlsx, .pdf, .txt)", "Frontend FormData, Backend Python, Supabase", "Trung bình", "v1.0", "Đã phát hành"),
        ("2", "Quản lý bài toán", "Tự động phân loại & chuyển đổi tài liệu", "Tự động convert file tải lên thành Google Docs hoặc Google Sheets và lưu link liên kết", "Google Drive API, Service Account / OAuth", "Cao", "v1.0", "Đã phát hành"),
        ("3", "Quản lý bài toán", "CRUD & Phân quyền bài toán", "Chỉnh sửa tiêu đề, danh sách URL, chuyển giao bài toán cho tester khác, xóa bài toán", "Python HTTP Router, Supabase REST", "Trung bình", "v1.0", "Đã phát hành"),
        ("4", "Quản lý bài toán", "Đồng bộ trạng thái chạy thời gian thực", "Theo dõi đồng hồ đếm giờ chạy của bài toán, đồng bộ giữa các tài khoản đăng nhập", "Backend ExecutionTracker, localStorage", "Trung bình", "v1.0", "Đã phát hành"),
        ("5", "Trí tuệ nhân tạo (AI)", "Bóc tách yêu cầu đặc tả (SRS/PRD)", "Phân tích nội dung tài liệu dài, trích xuất luồng nghiệp vụ, actor, pre-condition, acceptance criteria", "Gemini 1.5 Pro, n8n, Dify", "Rất cao", "v1.0", "Đã phát hành"),
        ("6", "Trí tuệ nhân tạo (AI)", "Sinh kịch bản Test Case tự động", "Tự động tạo bộ testcase đa dạng: Positive (kịch bản đúng), Negative (ngoại lệ), Boundary (giá trị biên)", "Prompt Engineering, Gemini LLM", "Rất cao", "v1.0", "Đã phát hành"),
        ("7", "Trí tuệ nhân tạo (AI)", "Tùy biến Prompt bổ sung", "Người dùng có thể nhập thêm chỉ dẫn cụ thể trước khi kích hoạt AI (tập trung bảo mật, test phân quyền...)", "FE Modal, n8n webhook payload", "Trung bình", "v1.0", "Đã phát hành"),
        ("8", "Trí tuệ nhân tạo (AI)", "Góp ý & Tái tạo Test Case theo Feedback", "Tester nhập phản hồi hoặc chọn gợi ý cải thiện, AI tự động sinh lại test case phù hợp", "Feedback loop, n8n / Backend callback", "Cao", "v1.1", "Đã phát hành"),
        ("9", "Duyệt & Đánh giá", "Màn hình Review Test Case tập trung", "Xem chi tiết từng testcase dạng thẻ, giao diện trực quan, hỗ trợ xem toàn màn hình", "FE review.html, TailwindCSS, Lucide", "Trung bình", "v1.0", "Đã phát hành"),
        ("10", "Duyệt & Đánh giá", "Cơ chế Phê duyệt / Từ chối (Approve/Reject)", "Đánh dấu giữ lại hoặc loại bỏ test case không đạt yêu cầu chỉ bằng một cú nhấp chuột", "Frontend state management, LocalStorage", "Thấp", "v1.0", "Đã phát hành"),
        ("11", "Duyệt & Đánh giá", "Sắp xếp tự nhiên theo thứ tự số học", "Thuật toán sắp xếp Natural Numerical Order (TC01, TC02, TC10...) kèm nút đổi chiều tăng/giảm", "Natural Sort Algorithm JS", "Thấp", "v1.1", "Đã phát hành"),
        ("12", "Duyệt & Đánh giá", "Bộ lọc trạng thái & Thao tác hàng loạt", "Filter testcase theo Chưa duyệt, Đã giữ, Đã bỏ; nút Giữ tất cả / Bỏ tất cả", "Frontend Filter & Batch Processing", "Thấp", "v1.0", "Đã phát hành"),
        ("13", "Duyệt & Đánh giá", "Thống kê tự động độ dùng được từ UI Review", "Tính toán tự động tỷ lệ Testcase được phê duyệt (Usable Rate) và lưu lại đánh giá chất lượng", "FE Analytics, Supabase Metrics", "Trung bình", "v1.2", "Đang hoàn thiện"),
        ("14", "Xuất bản & Tích hợp", "Tự động tạo Google Doc phân tích", "Xuất bản tóm tắt phân tích đặc tả thành file Google Doc trực quan trên Google Drive", "Google Docs API, Google Workspace Repos", "Trung bình", "v1.0", "Đã phát hành"),
        ("15", "Xuất bản & Tích hợp", "Tự động xuất Test Case ra Google Sheet", "Tạo file Google Sheet định dạng chuẩn gồm ID, Tên, Bước thực hiện, Kết quả mong muốn", "Google Sheets API", "Trung bình", "v1.0", "Đã phát hành"),
        ("16", "Nâng cao & RAG", "Ghi nhớ bộ test mẫu qua Vector DB (ChromaDB)", "Lưu trữ các kịch bản test chuẩn của dự án để AI tham khảo khi sinh testcase mới", "ChromaDB, Vector Embeddings", "Cao", "v1.2", "Đang hoàn thiện"),
        ("17", "Bảo mật & Quản trị", "Xác thực Supabase Auth & Phân quyền RLS", "Đăng nhập an toàn bằng tài khoản cá nhân, mã hóa JWT, phân quyền Tester vs Admin", "Supabase Auth, Row Level Security", "Cao", "v1.2", "Đang hoàn thiện"),
        ("18", "Tự động hóa nâng cao", "Tự động xuất sang Test Management Tools", "Đồng bộ trực tiếp kết quả sang Jira Xray, TestRail, Zephyr qua Open API", "Webhook / REST API integration", "Cao", "v2.0", "Lập kế hoạch")
    ]

    for r_idx, feat in enumerate(features_list, 5):
        ws3.row_dimensions[r_idx].height = 20
        row_fill = fill_zebra if r_idx % 2 == 0 else PatternFill(fill_type=None)
        for c_idx, val in enumerate(feat, 1):
            cell = ws3.cell(row=r_idx, column=c_idx, value=val)
            cell.font = font_regular
            cell.border = cell_border
            cell.fill = row_fill
            if c_idx in (1, 6, 7):
                cell.alignment = align_center
            elif c_idx == 8:
                cell.alignment = align_center
                if val == "Đã phát hành":
                    cell.fill = fill_done
                    cell.font = font_done
                elif val == "Đang hoàn thiện":
                    cell.fill = fill_progress
                    cell.font = font_progress
                else:
                    cell.fill = fill_todo
                    cell.font = font_todo
            elif c_idx in (2, 3):
                cell.alignment = align_left
                cell.font = font_bold
            else:
                cell.alignment = align_left

    # =========================================================================
    # TAB 4: ĐÁNH GIÁ ĐỘ DÙNG ĐƯỢC CỦA TEST CASE (AI TC USABILITY EVALUATION)
    # =========================================================================
    ws4 = wb.create_sheet(title="4. DanhGia_DoDungDuoc_TC")
    ws4.views.sheetView[0].showGridLines = True

    ws4["A1"] = "BẢNG ĐÁNH GIÁ MỨC ĐỘ DÙNG ĐƯỢC CỦA TEST CASE DO AI SINH RA (TC USABILITY ASSESSMENT)"
    ws4["A1"].font = font_title
    ws4["A2"] = "Khung tiêu chí phân loại, bảng nhật ký đo lường thực tế trên từng bài toán và phân tích nguyên nhân lỗi để cải tiến AI"
    ws4["A2"].font = font_subtitle

    # Section A: Framework / Classification Rubric
    ws4["A4"] = "A. KHUNG TIÊU CHUẨN PHÂN LOẠI MỨC ĐỘ DÙNG ĐƯỢC (USABILITY CLASSIFICATION FRAMEWORK)"
    ws4["A4"].font = font_section

    rubric_headers = ["Mức phân loại", "Tên mức độ", "Định nghĩa & Tiêu chuẩn đánh giá", "Mức độ can thiệp của Tester", "Trọng số điểm", "Tác động đến hiệu suất"]
    for c_idx, h in enumerate(rubric_headers, 1):
        cell = ws4.cell(row=5, column=c_idx, value=h)
        cell.font = font_header
        cell.fill = fill_header
        cell.alignment = align_header
        cell.border = cell_border
    ws4.row_dimensions[5].height = 24

    rubric_data = [
        ("Mức 1", "Dùng được ngay (Directly Usable / Pass 100%)", "Testcase hoàn chỉnh: Logic đúng 100% đặc tả, Precondition đầy đủ, Step rõ ràng, Test Data cụ thể, Expected Result chính xác. Tester có thể lấy thực thi kiểm thử ngay lập tức.", "0 phút (Không cần chỉnh sửa gì)", "100%", "Tiết kiệm 90% thời gian viết test"),
        ("Mức 2", "Dùng được sau sửa nhỏ (Minor Edit / Pass 80%)", "Kịch bản và logic hoàn toàn đúng, chỉ cần chỉnh sửa nhẹ: format câu từ, bổ sung tài khoản test thực tế, hoặc chỉnh lại tên label màn hình.", "< 2 phút chỉnh sửa", "80%", "Tiết kiệm 70% thời gian viết test"),
        ("Mức 3", "Cần viết lại nhiều (Major Rework / Pass 30%)", "Ý tưởng kịch bản đúng nhưng mô tả bước quá chung chung (VD: 'Kiểm tra hệ thống hiển thị đúng'), thiếu dữ liệu kiểm thử, hoặc thiếu expected result cụ thể.", "5 - 10 phút viết lại", "30%", "Tiết kiệm 20% thời gian viết test"),
        ("Mức 4", "Không dùng được / Ảo giác (Rejected / 0%)", "AI tự bịa ra tính năng hoặc API không có trong tài liệu đặc tả (Hallucination), logic kiểm thử sai hoàn toàn, hoặc trùng lặp 100% với kịch bản khác.", "Loại bỏ hoàn toàn", "0%", "Không tiết kiệm thời gian (lãng phí công review)")
    ]

    for r_idx, r_data in enumerate(rubric_data, 6):
        ws4.row_dimensions[r_idx].height = 24
        for c_idx, val in enumerate(r_data, 1):
            cell = ws4.cell(row=r_idx, column=c_idx, value=val)
            cell.font = font_regular
            cell.border = cell_border
            if c_idx == 1:
                cell.alignment = align_center
                cell.font = font_bold
            elif c_idx == 2:
                cell.alignment = align_left
                cell.font = font_bold
                if "Mức 1" in r_data[0]:
                    cell.fill = fill_u_ready
                    cell.font = font_u_ready
                elif "Mức 2" in r_data[0]:
                    cell.fill = fill_u_minor
                    cell.font = font_u_minor
                elif "Mức 3" in r_data[0]:
                    cell.fill = fill_u_rework
                    cell.font = font_u_rework
                else:
                    cell.fill = fill_u_reject
                    cell.font = font_u_reject
            elif c_idx in (4, 5):
                cell.alignment = align_center
                cell.font = font_bold
            else:
                cell.alignment = align_left

    # Section B: Summary KPI Cards for Usability
    ws4["A11"] = "B. THỐNG KÊ TỔNG HỢP HIỆU QUẢ DÙNG ĐƯỢC (EXECUTIVE SUMMARY)"
    ws4["A11"].font = font_section

    eval_kpis = [
        ("A12", "B13", "A14", "B14", "TỔNG SỐ TC ĐÃ ĐÁNH GIÁ", "=E35", "test cases"),
        ("C12", "D13", "C14", "D14", "DÙNG ĐƯỢC NGAY (Zero-touch)", "=F35", "test cases (61.9%)"),
        ("E12", "F13", "E14", "F14", "SỬA NHỎ LÀ DÙNG ĐƯỢC", "=G35", "test cases (24.3%)"),
        ("G12", "H13", "G14", "H14", "TỶ LỆ DÙNG ĐƯỢC TỔNG THỂ", "=J35", "Mục tiêu: ≥ 85%"),
        ("I12", "J13", "I14", "J14", "TỶ LỆ LOẠI BỎ (ẢO GIÁC)", "=I35/E35", "Mục tiêu: ≤ 5%"),
        ("K12", "L13", "K14", "L14", "TỔNG THỜI GIAN TIẾT KIỆM", "=L35", "giờ làm việc của Tester")
    ]

    for top_l_val, btm_r_val, top_l_lbl, btm_r_lbl, label, formula, unit in eval_kpis:
        ws4.merge_cells(f"{top_l_val}:{btm_r_val}")
        cell_val = ws4[top_l_val]
        cell_val.value = formula
        cell_val.font = font_kpi_value
        cell_val.alignment = align_center
        cell_val.fill = fill_kpi_bg
        if "%" in unit or label.startswith("TỶ LỆ"):
            cell_val.number_format = "0.0%"
            if label == "TỶ LỆ DÙNG ĐƯỢC TỔNG THỂ":
                cell_val.font = Font(name=font_family, size=18, bold=True, color="15803D")

        ws4.merge_cells(f"{top_l_lbl}:{btm_r_lbl}")
        cell_lbl = ws4[top_l_lbl]
        cell_lbl.value = f"{label}\n({unit})"
        cell_lbl.font = font_kpi_label
        cell_lbl.alignment = align_center
        cell_lbl.fill = fill_kpi_bg

        for col in range(openpyxl.utils.column_index_from_string(top_l_val[0]), openpyxl.utils.column_index_from_string(btm_r_val[0]) + 1):
            for row in range(int(top_l_val[1:]), int(btm_r_lbl[1:]) + 1):
                col_letter = get_column_letter(col)
                ws4[f"{col_letter}{row}"].border = kpi_border

    # Section C: Detailed Log by Task
    ws4["A16"] = "C. NHẬT KÝ ĐÁNH GIÁ ĐỘ DÙNG ĐƯỢC THEO TỪNG BÀI TOÁN THỰC TẾ (TASK-BY-TASK LOG)"
    ws4["A16"].font = font_section

    log_headers = [
        "STT", "Mã bài", "Tên bài toán kiểm thử", "Loại tài liệu đặc tả", "Tổng số TC sinh",
        "Mức 1: Dùng ngay", "Mức 2: Sửa nhỏ", "Mức 3: Viết lại", "Mức 4: Bỏ/Ảo giác",
        "Tỷ lệ Dùng được (%)", "Điểm TB (/10)", "Thời gian tiết kiệm (giờ)", "Nguyên nhân chính TC chưa tốt", "Người đánh giá", "Đề xuất cải thiện Prompt"
    ]

    # Two-row header for log table
    # Row 18: Header Grouping
    ws4.merge_cells("A18:A19")
    ws4["A18"] = "STT"
    ws4.merge_cells("B18:B19")
    ws4["B18"] = "Mã bài"
    ws4.merge_cells("C18:C19")
    ws4["C18"] = "Tên bài toán kiểm thử"
    ws4.merge_cells("D18:D19")
    ws4["D18"] = "Tài liệu đầu vào"
    ws4.merge_cells("E18:E19")
    ws4["E18"] = "Tổng số TC sinh"

    ws4.merge_cells("F18:I18")
    ws4["F18"] = "PHÂN BỔ THEO 4 MỨC ĐỘ DÙNG ĐƯỢC (SỐ LƯỢNG TEST CASE)"
    ws4["F19"] = "Mức 1: Dùng ngay"
    ws4["G19"] = "Mức 2: Sửa nhỏ"
    ws4["H19"] = "Mức 3: Viết lại"
    ws4["I19"] = "Mức 4: Loại bỏ"

    ws4.merge_cells("J18:J19")
    ws4["J18"] = "Tỷ lệ Dùng được (%)"
    ws4.merge_cells("K18:K19")
    ws4["K18"] = "Điểm TB (/10)"
    ws4.merge_cells("L18:L19")
    ws4["L18"] = "Tiết kiệm (giờ)"
    ws4.merge_cells("M18:M19")
    ws4["M18"] = "Nguyên nhân chính chưa tốt"
    ws4.merge_cells("N18:N19")
    ws4["N18"] = "Người duyệt"
    ws4.merge_cells("O18:O19")
    ws4["O18"] = "Góp ý cải thiện Prompt AI"

    for r in range(18, 20):
        ws4.row_dimensions[r].height = 20
        for c in range(1, 16):
            cell = ws4.cell(row=r, column=c)
            cell.font = font_header
            cell.fill = fill_header if r == 18 else fill_subheader
            cell.alignment = align_header
            cell.border = cell_border

    task_eval_data = [
        ("1", "BT-01", "Đăng nhập, Quên mật khẩu & Khóa tài khoản", "SRS .docx (12 trang)", 32, 22, 7, 2, 1, "=ROUND((F20+G20)/E20, 3)", "=ROUND((F20*10+G20*8+H20*3)/E20, 1)", "=ROUND((E20*15-(G20*3+H20*10))/60, 1)", "Thiếu test data số lần đăng nhập sai", "Tester Lan", "Bổ sung rule: ép xuất giá trị max attempts = 5"),
        ("2", "BT-02", "Quản lý Người dùng & Phân quyền RBAC", "SRS .docx (20 trang)", 45, 28, 11, 4, 2, "=ROUND((F21+G21)/E21, 3)", "=ROUND((F21*10+G21*8+H21*3)/E21, 1)", "=ROUND((E21*15-(G21*3+H21*10))/60, 1)", "Ảo giác thêm role 'Super Admin' ngoài SRS", "Tester Minh", "Cấm suy diễn role ngoài danh sách actor trong PRD"),
        ("3", "BT-03", "Giỏ hàng, Mã giảm giá & Đặt hàng", "User Story .txt", 38, 25, 9, 3, 1, "=ROUND((F22+G22)/E22, 3)", "=ROUND((F22*10+G22*8+H22*3)/E22, 1)", "=ROUND((E22*15-(G22*3+H22*10))/60, 1)", "Chưa rõ kịch bản voucher hết lượt dùng", "Tester Hùng", "Bổ sung gợi ý coupon expired/invalid trong Prompt"),
        ("4", "BT-04", "Tích hợp Cổng thanh toán VNPay / Momo", "API Spec .pdf (15 trang)", 28, 19, 6, 2, 1, "=ROUND((F23+G23)/E23, 3)", "=ROUND((F23*10+G23*8+H23*3)/E23, 1)", "=ROUND((E23*15-(G23*3+H23*10))/60, 1)", "Bước test thanh toán thất bại hơi sơ sài", "Tester Lan", "Yêu cầu chi tiết mã phản hồi responseCode VNPay"),
        ("5", "BT-05", "Quản lý Sản phẩm, Danh mục & Tồn kho", "Excel .xlsx (5 sheet)", 35, 23, 8, 3, 1, "=ROUND((F24+G24)/E24, 3)", "=ROUND((F24*10+G24*8+H24*3)/E24, 1)", "=ROUND((E24*15-(G24*3+H24*10))/60, 1)", "Kịch bản số lượng tồn kho âm chưa rõ expected", "Tester Mai", "Thêm rule kiểm tra Boundary value cho trường Stock"),
        ("6", "BT-06", "Tìm kiếm nâng cao & Bộ lọc đa tiêu chí", "Figma URL + Note", 26, 17, 6, 2, 1, "=ROUND((F25+G25)/E25, 3)", "=ROUND((F25*10+G25*8+H25*3)/E25, 1)", "=ROUND((E25*15-(G25*3+H25*10))/60, 1)", "Trùng lặp 2 test case tìm theo khoảng giá", "Tester Minh", "Tăng cường prompt de-duplication loại bỏ case trùng"),
        ("7", "BT-07", "Xử lý đơn hàng, Giao hàng & Đổi trả", "SRS .docx (18 trang)", 42, 26, 11, 3, 2, "=ROUND((F26+G26)/E26, 3)", "=ROUND((F26*10+G26*8+H26*3)/E26, 1)", "=ROUND((E26*15-(G26*3+H26*10))/60, 1)", "Thiếu điều kiện hoàn tiền cho đơn đã hủy", "Tester Hùng", "Bổ sung kịch bản state machine đổi trả hàng"),
        ("8", "BT-08", "Quản lý Khuyến mãi & Flash Sale theo giờ", "PRD Google Doc", 30, 18, 8, 3, 1, "=ROUND((F27+G27)/E27, 3)", "=ROUND((F27*10+G27*8+H27*3)/E27, 1)", "=ROUND((E27*15-(G27*3+H27*10))/60, 1)", "Chưa bao phủ mốc thời gian sát giờ bắt đầu", "Tester Lan", "Gợi ý boundary testing theo mốc thời gian T-1, T+1"),
        ("9", "BT-09", "Xuất báo cáo Doanh thu & Thống kê Excel", "SRS .docx (10 trang)", 24, 16, 5, 2, 1, "=ROUND((F28+G28)/E28, 3)", "=ROUND((F28*10+G28*8+H28*3)/E28, 1)", "=ROUND((E28*15-(G28*3+H28*10))/60, 1)", "Expected result chưa nêu rõ định dạng file xuất", "Tester Mai", "Yêu cầu nêu rõ đuôi file .xlsx, dung lượng và header"),
        ("10", "BT-10", "Thông báo thời gian thực (Push / Email)", "API Spec .json", 22, 14, 6, 1, 1, "=ROUND((F29+G29)/E29, 3)", "=ROUND((F29*10+G29*8+H29*3)/E29, 1)", "=ROUND((E29*15-(G29*3+H29*10))/60, 1)", "Không nêu rõ email test giả lập", "Tester Minh", "Bổ sung mock email format trong mẫu prompt"),
        ("11", "BT-11", "Bảo mật: SQL Injection & XSS Input Form", "Security Spec .pdf", 25, 16, 6, 2, 1, "=ROUND((F30+G30)/E30, 3)", "=ROUND((F30*10+G30*8+H30*3)/E30, 1)", "=ROUND((E30*15-(G30*3+H30*10))/60, 1)", "Payload XSS còn chung chung", "Tester Hùng", "Cung cấp danh sách 10 payload chuẩn vào system prompt"),
        ("12", "BT-12", "Cập nhật Hồ sơ cá nhân & Đổi mật khẩu", "User Story .txt", 20, 14, 4, 1, 1, "=ROUND((F31+G31)/E31, 3)", "=ROUND((F31*10+G31*8+H31*3)/E31, 1)", "=ROUND((E31*15-(G31*3+H31*10))/60, 1)", "Thiếu test case đổi mật khẩu trùng mật khẩu cũ", "Tester Lan", "Bổ sung negative test case đổi pass giống cũ"),
        ("13", "BT-13", "Quản lý Đánh giá sản phẩm & Báo cáo vi phạm", "PRD Google Doc", 26, 17, 6, 2, 1, "=ROUND((F32+G32)/E32, 3)", "=ROUND((F32*10+G32*8+H32*3)/E32, 1)", "=ROUND((E32*15-(G32*3+H32*10))/60, 1)", "Chưa có case đính kèm ảnh quá 5MB", "Tester Mai", "Yêu cầu check validate upload file dung lượng lớn"),
        ("14", "BT-14", "Tích hợp Chatbot CSKH trực tuyến", "Figma URL + Flow", 22, 12, 6, 3, 1, "=ROUND((F33+G33)/E33, 3)", "=ROUND((F33*10+G33*8+H33*3)/E33, 1)", "=ROUND((E33*15-(G33*3+H33*10))/60, 1)", "Bước kiểm thử phản hồi bot hơi mơ hồ", "Tester Minh", "Yêu cầu prompt sinh câu prompt hỏi và kết quả trả lời"),
        ("15", "BT-15", "Đồng bộ Dữ liệu với Hệ thống ERP nội bộ", "Technical Spec .docx", 30, 18, 7, 3, 2, "=ROUND((F34+G34)/E34, 3)", "=ROUND((F34*10+G34*8+H34*3)/E34, 1)", "=ROUND((E34*15-(G34*3+H34*10))/60, 1)", "Ảo giác cấu trúc bảng database ERP", "Tester Hùng", "Chỉ sinh test theo API endpoint, không can thiệp DB")
    ]

    for idx, row_vals in enumerate(task_eval_data, 20):
        ws4.row_dimensions[idx].height = 20
        row_fill = fill_zebra if idx % 2 == 0 else PatternFill(fill_type=None)
        
        for c_idx, val in enumerate(row_vals, 1):
            cell = ws4.cell(row=idx, column=c_idx, value=val)
            cell.font = font_regular
            cell.border = cell_border
            cell.fill = row_fill

            if c_idx in (1, 2):
                cell.alignment = align_center
                cell.font = font_bold
            elif c_idx == 3:
                cell.alignment = align_left
                cell.font = font_bold
            elif c_idx == 4:
                cell.alignment = align_left
            elif 5 <= c_idx <= 9:
                cell.alignment = align_center
                if c_idx == 6:
                    cell.font = font_u_ready
                elif c_idx == 9:
                    cell.font = font_u_reject
            elif c_idx == 10:
                cell.alignment = align_center
                cell.font = font_bold
                cell.number_format = "0.0%"
            elif c_idx in (11, 12):
                cell.alignment = align_center
                cell.font = font_bold
            elif c_idx == 14:
                cell.alignment = align_center
            else:
                cell.alignment = align_left

    # Total row for Task Evaluation Log
    tot_eval_row = 20 + len(task_eval_data)
    ws4.row_dimensions[tot_eval_row].height = 24
    ws4.cell(row=tot_eval_row, column=1, value="")
    cell_tot_eval_lbl = ws4.cell(row=tot_eval_row, column=3, value="TỔNG CỘNG / TRUNG BÌNH TOÀN DỰ ÁN")
    cell_tot_eval_lbl.font = font_bold
    cell_tot_eval_lbl.alignment = align_left

    # SUM totals for E, F, G, H, I
    for c_idx in range(5, 10):
        c_letter = get_column_letter(c_idx)
        cell = ws4.cell(row=tot_eval_row, column=c_idx, value=f"=SUM({c_letter}20:{c_letter}{tot_eval_row-1})")
        cell.font = font_bold
        cell.alignment = align_center
        cell.border = cell_border

    # Average Usable Rate
    cell_avg_rate = ws4.cell(row=tot_eval_row, column=10, value=f"=(F{tot_eval_row}+G{tot_eval_row})/E{tot_eval_row}")
    cell_avg_rate.font = Font(name=font_family, size=9, bold=True, color="15803D")
    cell_avg_rate.alignment = align_center
    cell_avg_rate.number_format = "0.0%"
    cell_avg_rate.border = cell_border

    # Average Score
    cell_avg_score = ws4.cell(row=tot_eval_row, column=11, value=f"=AVERAGE(K20:K{tot_eval_row-1})")
    cell_avg_score.font = font_bold
    cell_avg_score.alignment = align_center
    cell_avg_score.number_format = "0.0"
    cell_avg_score.border = cell_border

    # Total Time Saved
    cell_tot_time = ws4.cell(row=tot_eval_row, column=12, value=f"=SUM(L20:L{tot_eval_row-1})")
    cell_tot_time.font = font_bold
    cell_tot_time.alignment = align_center
    cell_tot_time.border = cell_border

    for c in range(1, 16):
        cell = ws4.cell(row=tot_eval_row, column=c)
        cell.border = cell_border
        cell.fill = fill_zebra

    # Section D: Root Cause Analysis Breakdown
    start_d_row = tot_eval_row + 2
    ws4[f"A{start_d_row}"] = "D. PHÂN TÍCH NGUYÊN NHÂN TEST CASE CHƯA ĐẠT (ROOT CAUSE ANALYSIS)"
    ws4[f"A{start_d_row}"].font = font_section

    rc_headers = ["STT", "Nhóm lỗi / Nguyên nhân", "Số ca phát hiện", "Tỷ lệ (%)", "Mức độ ảnh hưởng", "Ví dụ cụ thể", "Giải pháp cải tiến Prompt & RAG"]
    for c_idx, h in enumerate(rc_headers, 1):
        cell = ws4.cell(row=start_d_row+1, column=c_idx, value=h)
        cell.font = font_header
        cell.fill = fill_header
        cell.alignment = align_header
        cell.border = cell_border
    ws4.row_dimensions[start_d_row+1].height = 24

    root_causes = [
        ("1", "Ảo giác tính năng (Hallucination)", 18, "=C" + str(start_d_row+2) + "/SUM(C" + str(start_d_row+2) + ":C" + str(start_d_row+7) + ")", "Nghiêm trọng", "Tự sinh thêm quyền Super Admin hoặc bảng DB ERP không có trong tài liệu", "Thêm strict constraint vào system prompt: 'Chỉ dựa trên nội dung có trong tài liệu'"),
        ("2", "Dữ liệu kiểm thử chung chung (Missing Test Data)", 29, "=C" + str(start_d_row+3) + "/SUM(C" + str(start_d_row+2) + ":C" + str(start_d_row+7) + ")", "Vừa phải", "Ghi 'Nhập số tiền hợp lệ' thay vì 'Nhập 500,000 VND'", "Ép format: Mỗi testcase bắt buộc có cột Test Data với giá trị cụ thể"),
        ("3", "Bước thực hiện mơ hồ (Vague Test Steps)", 22, "=C" + str(start_d_row+4) + "/SUM(C" + str(start_d_row+2) + ":C" + str(start_d_row+7) + ")", "Vừa phải", "Ghi 'Thực hiện thao tác và xem kết quả' thiếu bước bấm nút", "Yêu cầu cấu trúc Step thành danh sách đánh số: 1. Truy cập..., 2. Bấm..., 3. Nhập..."),
        ("4", "Thiếu kịch bản biên / Ngoại lệ (Missing Boundary/Negative)", 25, "=C" + str(start_d_row+5) + "/SUM(C" + str(start_d_row+2) + ":C" + str(start_d_row+7) + ")", "Cao", "Chỉ sinh Happy Path, thiếu trường hợp quá tải, ký tự đặc biệt, timeout", "Bổ sung rule: Mỗi chức năng bắt buộc có ít nhất 2 Positive, 2 Negative, 1 Boundary"),
        ("5", "Trùng lặp kịch bản (Duplicate Test Cases)", 12, "=C" + str(start_d_row+6) + "/SUM(C" + str(start_d_row+2) + ":C" + str(start_d_row+7) + ")", "Thấp", "Sinh 2 test case cùng kiểm tra validation mật khẩu dưới 8 ký tự", "Thêm bước lọc khử trùng lặp (de-duplication) trong khâu post-processing của n8n"),
        ("6", "Sai logic điều kiện mong muốn (Wrong Expected Result)", 14, "=C" + str(start_d_row+7) + "/SUM(C" + str(start_d_row+2) + ":C" + str(start_d_row+7) + ")", "Cao", "Mô tả expected result ngược với thông báo lỗi quy định trong SRS", "Nạp phần Acceptance Criteria trong SRS trực tiếp vào context của LLM")
    ]

    for idx, rc in enumerate(root_causes, start_d_row+2):
        ws4.row_dimensions[idx].height = 20
        row_fill = fill_zebra if idx % 2 == 0 else PatternFill(fill_type=None)
        for c_idx, val in enumerate(rc, 1):
            cell = ws4.cell(row=idx, column=c_idx, value=val)
            cell.font = font_regular
            cell.border = cell_border
            cell.fill = row_fill
            if c_idx == 1:
                cell.alignment = align_center
            elif c_idx == 2:
                cell.alignment = align_left
                cell.font = font_bold
            elif c_idx in (3, 4):
                cell.alignment = align_center
                if c_idx == 4:
                    cell.number_format = "0.0%"
            elif c_idx == 5:
                cell.alignment = align_center
                if val == "Nghiêm trọng":
                    cell.fill = fill_p_high
                    cell.font = font_p_high
                elif val == "Cao":
                    cell.fill = fill_p_med
                    cell.font = font_p_med
                else:
                    cell.fill = fill_p_low
                    cell.font = font_p_low
            else:
                cell.alignment = align_left

    # Total row for Root Cause
    tot_rc_row = start_d_row + 2 + len(root_causes)
    ws4.row_dimensions[tot_rc_row].height = 22
    ws4.cell(row=tot_rc_row, column=1, value="")
    cell_tot_rc_lbl = ws4.cell(row=tot_rc_row, column=2, value="TỔNG SỐ LỖI ĐƯỢC PHÁT HIỆN")
    cell_tot_rc_lbl.font = font_bold
    cell_tot_rc_lbl.alignment = align_left
    
    cell_rc_sum = ws4.cell(row=tot_rc_row, column=3, value=f"=SUM(C{start_d_row+2}:C{tot_rc_row-1})")
    cell_rc_sum.font = font_bold
    cell_rc_sum.alignment = align_center
    cell_rc_sum.border = cell_border

    cell_rc_pct = ws4.cell(row=tot_rc_row, column=4, value=f"=SUM(D{start_d_row+2}:D{tot_rc_row-1})")
    cell_rc_pct.font = font_bold
    cell_rc_pct.alignment = align_center
    cell_rc_pct.number_format = "0.0%"
    cell_rc_pct.border = cell_border

    for c in range(1, 8):
        cell = ws4.cell(row=tot_rc_row, column=c)
        cell.border = cell_border
        cell.fill = fill_zebra

    # =========================================================================
    # TAB 5: BACKLOG LỖI & YÊU CẦU CẢI TIẾN (BUGS & ISSUES)
    # =========================================================================
    ws5 = wb.create_sheet(title="5. Backlog_Loi_CaiTien")
    ws5.views.sheetView[0].showGridLines = True

    ws5["A1"] = "DANH SÁCH LỖI (BUG) VÀ YÊU CẦU CẢI TIẾN (IMPROVEMENTS)"
    ws5["A1"].font = font_title
    ws5["A2"] = "Ghi nhận các vấn đề phát sinh trong quá trình vận hành thực tế và tiến độ xử lý"
    ws5["A2"].font = font_subtitle

    bug_headers = ["STT", "Mã Ticket", "Phân loại", "Mô tả vấn đề / Yêu cầu", "Mức độ nghiêm trọng", "Phân hệ liên quan", "Người phát hiện", "Người xử lý", "Trạng thái xử lý", "Giải pháp & Kết quả xử lý"]
    for c_idx, h in enumerate(bug_headers, 1):
        cell = ws5.cell(row=4, column=c_idx, value=h)
        cell.font = font_header
        cell.fill = fill_header
        cell.alignment = align_header
        cell.border = cell_border
    ws5.row_dimensions[4].height = 26

    issues = [
        ("1", "BUG-01", "Lỗi chức năng", "Lỗi storageQuotaExceeded khi upload file tài liệu bằng Service Account lên My Drive cá nhân", "Nghiêm trọng", "Backend / Google Workspace", "QA Team", "Backend Dev", "Đã xử lý", "Phát triển script setup_google_oauth.py lấy OAuth token cá nhân và cấu hình fallback"),
        ("2", "BUG-02", "Lỗi hiển thị", "Testcase bị nhảy thứ tự chữ cái (TC1, TC10, TC2...) làm người duyệt khó theo dõi", "Trung bình", "Frontend Review", "Tester", "Frontend Dev", "Đã xử lý", "Áp dụng regex bóc tách số và hàm natural sort compareTestcaseOrder, thêm toggle đổi chiều"),
        ("3", "BUG-03", "Lỗi kết nối", "Webhook n8n bị timeout khi xử lý file tài liệu dung lượng lớn (>15 trang)", "Nghiêm trọng", "n8n / AI Workflow", "Tester", "AI Engineer", "Đã xử lý", "Chuyển cơ chế sang xử lý bất đồng bộ (Async Queue) và gọi API Callback /api/tasks/ai-callback"),
        ("4", "IMP-01", "Cải tiến UX", "Cần có modal duyệt testcase nhanh ngay tại trang Dashboard mà không bắt buộc sang tab review.html", "Trung bình", "Frontend Dashboard", "Product Owner", "Frontend Dev", "Đã xử lý", "Bổ sung modal testcaseReviewModal tích hợp đầy đủ tính năng duyệt, filter, feedback"),
        ("5", "IMP-02", "Cải tiến AI", "Bổ sung các gợi ý nhanh (preset tags) trong khung phản hồi sửa test case để tester không phải gõ nhiều", "Thấp", "Frontend / AI Prompt", "Tester", "Frontend Dev", "Đã xử lý", "Thêm cụm button gợi ý: 'Thêm negative case', 'Thêm boundary', 'Làm rõ expected result'"),
        ("6", "IMP-03", "Cải tiến AI", "Nâng cao độ dùng được của testcase: giảm thiểu ảo giác về quyền hạn người dùng và cấu trúc CSDL", "Nghiêm trọng", "AI Prompt / Engine", "QA Lead", "AI Engineer", "Đang xử lý", "Thêm strict negative prompt và context filter trong Dify workflow, đạt tỷ lệ dùng được > 86%"),
        ("7", "SEC-01", "Bảo mật", "Header X-User-Role có thể bị can thiệp ở client khi mở public backend ra Internet", "Nghiêm trọng", "Backend Security", "Security Auditor", "Backend Dev", "Đang xử lý", "Đang tích hợp cơ chế Supabase JWT Verification và bật RLS trên Supabase"),
        ("8", "IMP-04", "Hiệu năng", "Tối ưu hóa token prompt gửi lên Gemini để giảm chi phí API khi lượng bài toán tăng cao", "Trung bình", "AI Pipeline", "Tech Lead", "AI Engineer", "Đang xử lý", "Đang thiết kế prompt nén nội dung đặc tả trước khi đưa vào bước sinh testcase")
    ]

    for r_idx, iss in enumerate(issues, 5):
        ws5.row_dimensions[r_idx].height = 20
        row_fill = fill_zebra if r_idx % 2 == 0 else PatternFill(fill_type=None)
        for c_idx, val in enumerate(iss, 1):
            cell = ws5.cell(row=r_idx, column=c_idx, value=val)
            cell.font = font_regular
            cell.border = cell_border
            cell.fill = row_fill
            if c_idx in (1, 2, 7, 8):
                cell.alignment = align_center
            elif c_idx == 3:
                cell.alignment = align_center
                cell.font = font_bold
            elif c_idx == 5:
                cell.alignment = align_center
                if val == "Nghiêm trọng":
                    cell.fill = fill_p_high
                    cell.font = font_p_high
                elif val == "Trung bình":
                    cell.fill = fill_p_med
                    cell.font = font_p_med
                else:
                    cell.fill = fill_p_low
                    cell.font = font_p_low
            elif c_idx == 9:
                cell.alignment = align_center
                if val == "Đã xử lý":
                    cell.fill = fill_done
                    cell.font = font_done
                elif val == "Đang xử lý":
                    cell.fill = fill_progress
                    cell.font = font_progress
                else:
                    cell.fill = fill_todo
                    cell.font = font_todo
            else:
                cell.alignment = align_left

    # =========================================================================
    # AUTO-FIT COLUMN WIDTHS ACROSS ALL SHEETS
    # =========================================================================
    for sheet in wb.worksheets:
        for col in sheet.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                if cell.row in (1, 2) or (sheet.title.startswith("1.") and cell.row <= 17) or (sheet.title.startswith("4.") and cell.row <= 15):
                    continue
                val_str = str(cell.value or "")
                if val_str.startswith("="):
                    val_str = "100.0%"
                line_lens = [len(line) for line in val_str.split("\n")]
                curr_max = max(line_lens) if line_lens else 0
                if curr_max > max_len:
                    max_len = curr_max
            sheet.column_dimensions[col_letter].width = max(max_len + 3, 11)

    # Specific fine-tuning for sheet 1
    ws1.column_dimensions["A"].width = 8
    ws1.column_dimensions["B"].width = 46
    ws1.column_dimensions["C"].width = 14
    ws1.column_dimensions["D"].width = 14
    ws1.column_dimensions["E"].width = 14
    ws1.column_dimensions["F"].width = 14
    ws1.column_dimensions["G"].width = 14
    ws1.column_dimensions["H"].width = 18
    ws1.column_dimensions["I"].width = 30
    ws1.column_dimensions["J"].width = 18

    # Specific fine-tuning for sheet 2
    ws2.column_dimensions["A"].width = 6
    ws2.column_dimensions["B"].width = 12
    ws2.column_dimensions["C"].width = 22
    ws2.column_dimensions["D"].width = 36
    ws2.column_dimensions["E"].width = 48
    ws2.column_dimensions["F"].width = 13
    ws2.column_dimensions["G"].width = 15
    ws2.column_dimensions["H"].width = 16
    ws2.column_dimensions["I"].width = 13
    ws2.column_dimensions["J"].width = 13
    ws2.column_dimensions["K"].width = 13
    ws2.column_dimensions["L"].width = 13
    ws2.column_dimensions["M"].width = 40

    # Specific fine-tuning for sheet 3
    ws3.column_dimensions["A"].width = 6
    ws3.column_dimensions["B"].width = 22
    ws3.column_dimensions["C"].width = 32
    ws3.column_dimensions["D"].width = 54
    ws3.column_dimensions["E"].width = 30
    ws3.column_dimensions["F"].width = 16
    ws3.column_dimensions["G"].width = 12
    ws3.column_dimensions["H"].width = 16

    # Specific fine-tuning for sheet 4 (Usability Evaluation Sheet)
    ws4.column_dimensions["A"].width = 6
    ws4.column_dimensions["B"].width = 12
    ws4.column_dimensions["C"].width = 34
    ws4.column_dimensions["D"].width = 22
    ws4.column_dimensions["E"].width = 14
    ws4.column_dimensions["F"].width = 16
    ws4.column_dimensions["G"].width = 16
    ws4.column_dimensions["H"].width = 16
    ws4.column_dimensions["I"].width = 16
    ws4.column_dimensions["J"].width = 18
    ws4.column_dimensions["K"].width = 14
    ws4.column_dimensions["L"].width = 16
    ws4.column_dimensions["M"].width = 36
    ws4.column_dimensions["N"].width = 15
    ws4.column_dimensions["O"].width = 44

    # Specific fine-tuning for sheet 5
    ws5.column_dimensions["A"].width = 6
    ws5.column_dimensions["B"].width = 12
    ws5.column_dimensions["C"].width = 16
    ws5.column_dimensions["D"].width = 46
    ws5.column_dimensions["E"].width = 18
    ws5.column_dimensions["F"].width = 22
    ws5.column_dimensions["G"].width = 15
    ws5.column_dimensions["H"].width = 15
    ws5.column_dimensions["I"].width = 16
    ws5.column_dimensions["J"].width = 50

    output_path = "Theo_Doi_Tien_Do_Phat_Trien_Tool_AI_AutoTC.xlsx"
    wb.save(output_path)
    print(f"Updated file: {output_path} with TC Usability Evaluation successfully!")

if __name__ == "__main__":
    build_progress_tracker()
