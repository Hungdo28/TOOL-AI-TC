# -*- coding: utf-8 -*-
"""
Script tạo file tài liệu Word (.docx) chuyên nghiệp:
"Tài liệu Tổng quan, Các Chức năng Chính và Kiến trúc Hạ tầng Hệ thống AutoTC"
"""

import docx
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls

def set_cell_background(cell, fill_hex):
    """Đặt màu nền cho cell trong table"""
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tcPr.append(shd)

def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    """Đặt padding cho cell (đơn vị dxa: 1 pt = 20 dxa)"""
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = parse_xml(
        f'<w:tcMar {nsdecls("w")}>'
        f'<w:top w:w="{top}" w:type="dxa"/>'
        f'<w:bottom w:w="{bottom}" w:type="dxa"/>'
        f'<w:left w:w="{left}" w:type="dxa"/>'
        f'<w:right w:w="{right}" w:type="dxa"/>'
        f'</w:tcMar>'
    )
    tcPr.append(tcMar)

def set_cell_border(cell, **kwargs):
    tcPr = cell._tc.get_or_add_tcPr()
    tcBorders = parse_xml(f'<w:tcBorders {nsdecls("w")}/>')
    for edge in ('top', 'left', 'bottom', 'right'):
        edge_data = kwargs.get(edge)
        if edge_data:
            b_elm = parse_xml(
                f'<w:{edge} {nsdecls("w")} '
                f'w:val="{edge_data.get("val", "single")}" '
                f'w:sz="{edge_data.get("sz", "4")}" '
                f'w:space="{edge_data.get("space", "0")}" '
                f'w:color="{edge_data.get("color", "auto")}"/>'
            )
            tcBorders.append(b_elm)
        else:
            b_elm = parse_xml(f'<w:{edge} {nsdecls("w")} w:val="none"/>')
            tcBorders.append(b_elm)
    tcPr.append(tcBorders)

def add_image_placeholder(doc, title, note, suggested_filename=""):
    """Thêm khung để người dùng dán ảnh trong Word"""
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = tbl.cell(0, 0)
    cell.width = Inches(6.5)
    
    set_cell_background(cell, "F8FAFC")
    set_cell_margins(cell, top=200, bottom=200, left=250, right=250)
    set_cell_border(cell, 
        top={"val": "dashed", "sz": "8", "color": "93C5FD"},
        bottom={"val": "dashed", "sz": "8", "color": "93C5FD"},
        left={"val": "single", "sz": "24", "color": "2563EB"},
        right={"val": "dashed", "sz": "8", "color": "93C5FD"}
    )
    
    p = cell.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_icon = p.add_run("📸 ")
    run_icon.font.size = Pt(14)
    run_title = p.add_run(f"KHUNG CHÈN HÌNH ẢNH: {title.upper()}\n")
    run_title.bold = True
    run_title.font.size = Pt(11)
    run_title.font.color.rgb = RGBColor(30, 64, 175) # Blue 800
    
    p_box = cell.add_paragraph()
    p_box.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_box.paragraph_format.space_before = Pt(8)
    p_box.paragraph_format.space_after = Pt(8)
    run_space = p_box.add_run("\n[ >>> DÁN HOẶC CHÈN ẢNH VÀO VỊ TRÍ NÀY <<< ]\n\n")
    run_space.font.size = Pt(10)
    run_space.font.bold = True
    run_space.font.color.rgb = RGBColor(148, 163, 184) # Slate 400
    
    p_note = cell.add_paragraph()
    p_note.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_note = p_note.add_run(f"Gợi ý nội dung: {note}")
    run_note.italic = True
    run_note.font.size = Pt(9.5)
    run_note.font.color.rgb = RGBColor(100, 116, 139) # Slate 500
    
    if suggested_filename:
        p_file = cell.add_paragraph()
        p_file.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run_file = p_file.add_run(f"Tên file đề xuất: {suggested_filename}")
        run_file.font.size = Pt(9)
        run_file.font.color.rgb = RGBColor(71, 85, 105)
        
    doc.add_paragraph() # Dãn dòng

def style_heading1(p):
    p.paragraph_format.space_before = Pt(18)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.keep_with_next = True
    for r in p.runs:
        r.font.name = 'Calibri'
        r.font.size = Pt(16)
        r.bold = True
        r.font.color.rgb = RGBColor(30, 58, 138) # Dark Blue

def style_heading2(p):
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.keep_with_next = True
    for r in p.runs:
        r.font.name = 'Calibri'
        r.font.size = Pt(13)
        r.bold = True
        r.font.color.rgb = RGBColor(15, 23, 42) # Slate 900

def style_heading3(p):
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.keep_with_next = True
    for r in p.runs:
        r.font.name = 'Calibri'
        r.font.size = Pt(11.5)
        r.bold = True
        r.font.color.rgb = RGBColor(37, 99, 235) # Blue 600

def create_document():
    doc = Document()
    
    # Thiết lập lề trang tiêu chuẩn (1 inch = 2.54cm)
    for section in doc.sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)
        
    # Set default font
    doc.styles['Normal'].font.name = 'Calibri'
    doc.styles['Normal'].font.size = Pt(11)
    doc.styles['Normal'].font.color.rgb = RGBColor(51, 65, 85) # Slate 700
    
    # TIÊU ĐỀ CHÍNH
    title_p = doc.add_paragraph()
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_p.paragraph_format.space_before = Pt(12)
    title_p.paragraph_format.space_after = Pt(4)
    run_t = title_p.add_run("TÀI LIỆU TỔNG QUAN, CÁC CHỨC NĂNG CHÍNH\nVÀ KIẾN TRÚC HẠ TẦNG HỆ THỐNG")
    run_t.font.name = 'Calibri'
    run_t.font.size = Pt(20)
    run_t.bold = True
    run_t.font.color.rgb = RGBColor(30, 58, 138)
    
    sub_p = doc.add_paragraph()
    sub_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub_p.paragraph_format.space_after = Pt(18)
    run_sub = sub_p.add_run("HỆ THỐNG TỰ ĐỘNG HÓA KIỂM THỬ (AUTOTC - AI AUTOMATION DASHBOARD)")
    run_sub.font.name = 'Calibri'
    run_sub.font.size = Pt(12)
    run_sub.bold = True
    run_sub.font.color.rgb = RGBColor(71, 85, 105)
    
    # Khung ghi chú hướng dẫn
    notice_tbl = doc.add_table(rows=1, cols=1)
    notice_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    n_cell = notice_tbl.cell(0, 0)
    n_cell.width = Inches(6.5)
    set_cell_background(n_cell, "EFF6FF") # Blue 50
    set_cell_margins(n_cell, top=140, bottom=140, left=180, right=180)
    set_cell_border(n_cell, left={"val": "single", "sz": "18", "color": "3B82F6"})
    np = n_cell.paragraphs[0]
    nr1 = np.add_run("📌 HƯỚNG DẪN DÀNH CHO BẠN:\n")
    nr1.bold = True
    nr1.font.size = Pt(10.5)
    nr1.font.color.rgb = RGBColor(29, 78, 216)
    nr2 = np.add_run("Tài liệu này bao gồm 2 phần trọng tâm: ")
    nr2.font.size = Pt(10)
    nr3 = np.add_run("Kiến trúc Hạ tầng Hệ thống ")
    nr3.bold = True
    nr3.font.size = Pt(10)
    nr4 = np.add_run("và ")
    nr4.font.size = Pt(10)
    nr5 = np.add_run("Chi tiết Chức năng của Tool.\n")
    nr5.bold = True
    nr5.font.size = Pt(10)
    nr6 = np.add_run("Các ô có viền đứt nét ")
    nr6.font.size = Pt(10)
    nr7 = np.add_run("📸 [KHUNG CHÈN HÌNH ẢNH]")
    nr7.bold = True
    nr7.font.size = Pt(10)
    nr7.font.color.rgb = RGBColor(30, 64, 175)
    nr8 = np.add_run(" đã được để trống sẵn. Bạn chỉ việc nhấp chuột vào ô và nhấn dán (Ctrl+V) hoặc chọn Insert > Pictures để chèn ảnh chụp màn hình thực tế.")
    nr8.font.size = Pt(10)
    doc.add_paragraph()
    
    # ==================== PHẦN I ====================
    p_p1 = doc.add_paragraph()
    p_p1.add_run("PHẦN I: KIẾN TRÚC HẠ TẦNG HỆ THỐNG (SYSTEM INFRASTRUCTURE ARCHITECTURE)")
    style_heading1(p_p1)
    
    p_intro = doc.add_paragraph()
    p_intro.add_run("Hệ thống ")
    p_intro.add_run("AutoTC").bold = True
    p_intro.add_run(" được thiết kế theo mô hình kiến trúc phân tán hiện đại, bao gồm giao diện web Single Page Application, máy chủ Backend Python đa luồng hiệu năng cao, cơ sở dữ liệu Supabase Cloud thời gian thực, hệ sinh thái Google Workspace và dịch vụ mô hình AI chuyên dụng. Toàn bộ pipeline từ trích xuất tài liệu đặc tả, phân tích BA, trích xuất yêu cầu, đối chiếu bộ nhớ QA đến sinh kịch bản testcase và xuất Google Workspace đều được lập trình native trực tiếp trong Backend Python.")
    
    # 1. Sơ đồ kiến trúc tổng thể
    p_arch = doc.add_paragraph()
    p_arch.add_run("1. Sơ đồ Kiến trúc Hạ tầng Tổng thể")
    style_heading2(p_arch)
    
    p_arch_desc = doc.add_paragraph()
    p_arch_desc.add_run("Hạ tầng phân định rõ ràng thành các phân lớp kỹ thuật:")
    
    bullets = [
        ("Lớp Giao diện (Client / Frontend): ", "Web Application viết bằng HTML5/TailwindCSS/JS hiện đại, triển khai trên domain public https://quanlv.io.vn kết nối trực tiếp RESTful API của Backend và nhúng Trợ lý Dify QA."),
        ("Lớp Mạng & Định tuyến Bảo mật (Tailscale): ", "Tailscale Mesh VPN bảo vệ kết nối nội bộ giữa Backend và Dify. Tailscale Funnel đóng vai trò Reverse Proxy mở HTTPS bảo mật cổng 8888 cho Dify Chatbot."),
        ("Lớp Pipeline AI Backend (AiPipelineService trong Python): ", "Trực tiếp thực thi toàn bộ luồng: DocumentCrawler -> BA Analysis Engine -> Requirement Extractor -> MemoryService -> Condition & Testcase Generator -> Multi-thread Controller."),
        ("Lớp Cơ sở Dữ liệu & Lưu trữ Đám mây: ", "Supabase Cloud quản lý người dùng, phân quyền và dữ liệu bài toán thời gian thực; Google Workspace (Docs, Sheets, Drive) quản lý tài liệu và lưu kết quả testcase đã duyệt qua Google API Client."),
        ("Lớp Trí tuệ Nhân tạo & Tích hợp: ", "Viettel AI MaaS (DeepSeek-V4.1-Flash), Dify AI Chatbot Agent và Figma REST API.")
    ]
    for b_title, b_desc in bullets:
        bp = doc.add_paragraph(style='List Bullet')
        br_title = bp.add_run(b_title)
        br_title.bold = True
        br_title.font.color.rgb = RGBColor(15, 23, 42)
        bp.add_run(b_desc)
        
    doc.add_paragraph()
    add_image_placeholder(doc, "Sơ đồ Kiến trúc Hạ tầng Tổng thể", 
                          "Chèn ảnh sơ đồ khối kiến trúc hạ tầng hệ thống hoặc sơ đồ luồng dữ liệu (Data Flow Diagram)", 
                          "infra_architecture.png")
    
    # 2. Chi tiết các thành phần hạ tầng
    p_comp = doc.add_paragraph()
    p_comp.add_run("2. Chi tiết các Thành phần Hạ tầng Kỹ thuật")
    style_heading2(p_comp)
    
    # A. Frontend
    p_fe = doc.add_paragraph()
    p_fe.add_run("A. Lớp Giao diện Người dùng (Frontend)")
    style_heading3(p_fe)
    p_fe_desc = doc.add_paragraph()
    p_fe_desc.add_run("• Công nghệ sử dụng: HTML5, CSS3, Tailwind CSS (CDN), bộ icon Lucide, Vanilla JavaScript hiện đại (ES6+), Supabase JS Client v2.\n"
                     "• Domain triển khai: Production chạy tại https://quanlv.io.vn (quản lý qua CNAME / GitHub Pages). Môi trường phát triển cục bộ chạy qua Live Server tại cổng http://127.0.0.1:5500.\n"
                     "• Trang thành phần: index.html (Bảng điều khiển & quản lý danh sách), review.html (Giao diện duyệt & chỉnh sửa testcase toàn màn hình), login.html (Cổng đăng nhập an toàn).\n"
                     "• Giao tiếp API: Gọi trực tiếp các Endpoint RESTful của Backend Python (/api/tasks, /api/tasks/run, /api/tasks/stop...) với cơ chế AbortController cho phép hủy request an toàn.")
    
    # B. Backend AI Pipeline
    p_be = doc.add_paragraph()
    p_be.add_run("B. Lớp Máy chủ Ứng dụng & Pipeline AI Backend (Python 3.10+)")
    style_heading3(p_be)
    p_be_desc = doc.add_paragraph()
    p_be_desc.add_run("• Ngôn ngữ & Máy chủ: Python 3.10+ sử dụng ThreadingHTTPServer đa luồng, xử lý non-blocking.\n"
                     "• Cổng lắng nghe: http://0.0.0.0:3000 (mặc định), khởi động nhanh qua file run_backend.bat.\n"
                     "• Kiến trúc Pipeline AI (AiPipelineService):\n"
                     "   + DocumentCrawler: Tự động trích xuất nội dung từ Google Docs, Google Sheets, trang web và đọc thiết kế UI/UX từ Figma REST API qua token.\n"
                     "   + BA Analysis Engine: Phân tích đặc tả nghiệp vụ, xây dựng cây chức năng và phạm vi kiểm thử tự động.\n"
                     "   + Requirement Extraction: Trích xuất danh sách yêu cầu kèm ID và tiêu chuẩn chấp nhận (Acceptance Criteria).\n"
                     "   + MemoryService & ChromaDB: Quản lý bộ nhớ testcase và vector embeddings ngữ nghĩa tại BE/chroma_db giúp loại bỏ trùng lặp và học từ lịch sử.\n"
                     "   + Condition & Testcase Generator: Sinh bộ điều kiện kiểm thử và kịch bản testcase chi tiết (tiền điều kiện, các bước, kết quả mong đợi, độ ưu tiên).\n"
                     "   + Multi-thread & Cancel Controller: Quản lý chạy song song đa luồng bằng ThreadPoolExecutor và dừng tiến trình tức thì bằng _cancelled_tasks.\n"
                     "   + ExecutionTracker: Đồng hồ bấm giờ thực thi ghi nhận thời gian chạy chính xác của từng bài toán.\n"
                     "   + FileProcessing: Kiểm tra định dạng MIME, giới hạn dung lượng upload (20MB/file, 50MB/tổng), chuẩn hóa tài liệu tải lên.")

    # C. Tailscale
    p_ts = doc.add_paragraph()
    p_ts.add_run("C. Mạng riêng ảo & Bảo mật (Tailscale Mesh VPN & Funnel)")
    style_heading3(p_ts)
    p_ts_desc = doc.add_paragraph()
    p_ts_desc.add_run("• Tailscale Mesh VPN: Kết nối mạng nội bộ riêng an toàn giữa máy chủ Backend và Dify trên domain riêng: vdtc-hungdv.tailfb2503.ts.net.\n"
                     "• Tailscale Funnel: Mở kết nối HTTPS an toàn cho Dify Chatbot qua cổng 8888 để nhúng trợ lý ảo vào frontend https://quanlv.io.vn mà không bị lỗi CORS hay Mixed-Content.")

    # D. Supabase & Google Workspace
    p_data = doc.add_paragraph()
    p_data.add_run("D. Cơ sở Dữ liệu & Lưu trữ Đám mây (Supabase & Google Workspace)")
    style_heading3(p_data)
    p_data_desc = doc.add_paragraph()
    p_data_desc.add_run("• Supabase Cloud (PostgreSQL):\n"
                       "   + Endpoint: https://zrwlzthteixjxdhsevkh.supabase.co\n"
                       "   + Quản lý bảng public.problems (danh sách bài toán, trạng thái, kết quả testcase JSON, người phụ trách).\n"
                       "   + Quản lý bảng public.users (tài khoản, mật khẩu băm, phân quyền vai trò admin/tester).\n"
                       "   + Cập nhật dữ liệu thời gian thực qua Supabase Realtime API.\n"
                       "• Google Workspace (Drive, Docs, Sheets API):\n"
                       "   + Tích hợp trực tiếp bằng thư viện Google API Client trong Python.\n"
                       "   + Hỗ trợ cả Service Account (Shared Drive tổ chức) và OAuth Desktop App (tài khoản cá nhân).\n"
                       "   + Tự động upload file gốc, chuyển đổi sang Google Docs/Sheets và ghi nhận toàn bộ testcase đã duyệt.")

    # E. AI Engine
    p_ai = doc.add_paragraph()
    p_ai.add_run("E. Nền tảng Trí tuệ Nhân tạo & Tích hợp Thiết kế")
    style_heading3(p_ai)
    p_ai_desc = doc.add_paragraph()
    p_ai_desc.add_run("• Viettel AI MaaS: Mô hình DeepSeek-V4.1-Flash với khả năng suy luận nhanh, hiểu sâu ngữ cảnh tiếng Việt và tuân thủ chuẩn cấu trúc testcase kiểm thử.\n"
                     "• Dify AI Agent Platform: Cung cấp Chatbot trợ lý QA Assistant hỗ trợ hỏi đáp nghiệp vụ và logic kiểm thử theo thời gian thực.\n"
                     "• Figma REST API: Trích xuất trực tiếp thiết kế UI/UX từ link Figma thông qua Access Token giúp AI sinh testcase giao diện chính xác.")

    doc.add_paragraph()
    add_image_placeholder(doc, "Cấu trúc Hạ tầng & Dịch vụ Backend", 
                          "Chèn ảnh chụp cấu trúc thư mục BE, kiến trúc pipeline hoặc giao diện máy chủ", 
                          "infra_backend_code.png")

    # ==================== PHẦN II ====================
    doc.add_page_break()
    p_p2 = doc.add_paragraph()
    p_p2.add_run("PHẦN II: CHI TIẾT CÁC CHỨC NĂNG CHÍNH CỦA TOOL")
    style_heading1(p_p2)
    
    # Chức năng 1
    p_f1 = doc.add_paragraph()
    p_f1.add_run("1. Đăng nhập & Quản lý Phân quyền (Authentication & Authorization)")
    style_heading2(p_f1)
    p_f1_desc = doc.add_paragraph()
    p_f1_desc.add_run("• Mục đích: Kiểm soát an ninh, xác thực quyền truy cập và phân công trách nhiệm rõ ràng giữa các thành viên.\n"
                     "• Tính năng chi tiết:\n"
                     "   + Đăng nhập bảo mật: Kiểm tra xác thực trực tiếp qua cơ sở dữ liệu Supabase.\n"
                     "   + Phân quyền 2 cấp độ: Admin (toàn quyền thêm/sửa/xóa bài toán, kích hoạt AI pipeline, duyệt và chuyển giao) và Tester/Viewer (xem bài toán, theo dõi tiến độ và duyệt bài toán được phân công).\n"
                     "   + Quản lý phiên làm việc: Tự động lưu trữ thông tin phiên, áp dụng cơ chế tự động gia hạn (Rolling Renewal) khi người dùng tương tác, tự động đăng xuất sau 7 ngày.\n"
                     "   + Giao diện Header: Hiển thị trực quan họ tên người dùng, vai trò và nút đăng xuất an toàn.")
    add_image_placeholder(doc, "Màn hình Đăng nhập Hệ thống", 
                          "Chèn ảnh chụp màn hình form đăng nhập login.html", 
                          "01_login_screen.png")

    # Chức năng 2
    p_f2 = doc.add_paragraph()
    p_f2.add_run("2. Quản lý Bài toán Kiểm thử (Task & Document Management)")
    style_heading2(p_f2)
    p_f2_desc = doc.add_paragraph()
    p_f2_desc.add_run("• Mục đích: Cho phép tester khởi tạo, cập nhật và quản lý tập trung toàn bộ danh sách các bài toán kiểm thử phần mềm.\n"
                     "• Tính năng chi tiết:\n"
                     "   + Thêm bài toán bằng URL: Nhập liên kết tài liệu Google Docs, Google Sheets hoặc link Figma thiết kế; hỗ trợ thêm nhiều liên kết đồng thời.\n"
                     "   + Import File từ máy tính: Hỗ trợ các định dạng .doc, .docx, .xls, .xlsx, .pdf, .txt; backend tự động upload lên Google Drive và chuyển đổi định dạng tương ứng.\n"
                     "   + Danh sách bài toán dạng bảng: Hiển thị Tên bài toán, Người làm, Trạng thái, Link tài liệu gốc, Link Testcase, Link Phân tích.\n"
                     "   + Tìm kiếm theo thời gian thực: Ô tìm kiếm nhanh lọc bài toán theo từ khóa ngay khi gõ phím.\n"
                     "   + Cập nhật & Xóa bài toán: Modal chỉnh sửa tên bài toán, thay đổi danh sách liên kết tài liệu; nút xóa bài toán khi không còn sử dụng.")
    add_image_placeholder(doc, "Bảng Điều khiển & Danh sách Bài toán", 
                          "Chèn ảnh chụp màn hình Dashboard chính bao gồm form thêm bài toán và bảng danh sách", 
                          "02_dashboard_tasks.png")

    # Chức năng 3
    p_f3 = doc.add_paragraph()
    p_f3.add_run("3. Phân chia & Chuyển giao Bài toán (Task Assignment & Transfer)")
    style_heading2(p_f3)
    p_f3_desc = doc.add_paragraph()
    p_f3_desc.add_run("• Mục đích: Đảm bảo tính minh bạch trong phân công công việc và dễ dàng chuyển giao trách nhiệm giữa các thành viên.\n"
                     "• Tính năng chi tiết:\n"
                     "   + Hiển thị người phụ trách: Cột 'Người làm' hiển thị tên tài khoản tester chịu trách nhiệm chính.\n"
                     "   + Modal chuyển giao: Cho phép chọn thành viên trong danh sách người dùng để bàn giao bài toán nhanh chóng.\n"
                     "   + Đồng bộ tức thì: Trạng thái phân công mới được lưu ngay vào Supabase và cập nhật tức thì trên bảng điều khiển.")
    add_image_placeholder(doc, "Hộp thoại Chuyển giao Bài toán", 
                          "Chèn ảnh chụp popup chuyển giao bài toán cho thành viên khác", 
                          "03_transfer_task.png")

    # Chức năng 4
    p_f4 = doc.add_paragraph()
    p_f4.add_run("4. Điều khiển Luồng AI Sinh Testcase (AI Execution & Control)")
    style_heading2(p_f4)
    p_f4_desc = doc.add_paragraph()
    p_f4_desc.add_run("• Mục đích: Kích hoạt pipeline AI tự động phân tích tài liệu và sinh bộ testcase chi tiết.\n"
                     "• Tính năng chi tiết:\n"
                     "   + Thực thi linh hoạt: Chạy lẻ từng bài toán hoặc chọn nhiều bài toán qua ô checkbox để chạy hàng loạt đa luồng (ThreadPoolExecutor).\n"
                     "   + Tùy biến Prompt AI: Hộp thoại cho phép nhập thêm yêu cầu kiểm thử chuyên sâu (bổ sung Negative Case, Boundary Values, kiểm thử phân quyền, v.v.).\n"
                     "   + Đồng hồ đo thời gian thực thi: Bộ đếm giờ (Execution Tracker) ghi nhận chính xác thời gian xử lý của từng bài toán.\n"
                     "   + Quản lý trạng thái trực quan: Cập nhật liên tục các trạng thái: Chưa làm, Đang chạy, Chờ duyệt, Hoàn thành, Lỗi.\n"
                     "   + Dừng luồng khẩn cấp tức thì (Stop Stream): Cho phép dừng ngay bài toán đang chạy mà không gây nghẽn tài nguyên.")
    add_image_placeholder(doc, "Modal Cấu hình Chạy AI & Theo dõi Tiến độ", 
                          "Chèn ảnh chụp popup nhập Prompt AI và trạng thái khi bài toán đang chạy", 
                          "04_run_ai_prompt.png")

    # Chức năng 5
    p_f5 = doc.add_paragraph()
    p_f5.add_run("5. Xem trước, Đánh giá & Duyệt Testcase (Testcase Preview & Review)")
    style_heading2(p_f5)
    p_f5_desc = doc.add_paragraph()
    p_f5_desc.add_run("• Mục đích: Giúp Tester chủ động kiểm tra, tinh chỉnh và phê duyệt chất lượng testcase do AI tạo ra trước khi xuất thành tài liệu chính thức.\n"
                     "• Hai chế độ hiển thị tiện lợi:\n"
                     "   1. Quick Modal Preview: Cửa sổ xem nhanh và thao tác duyệt trực tiếp ngay trên Dashboard.\n"
                     "   2. Dedicated Fullscreen Review (review.html): Màn hình chuyên dụng toàn trang với bộ công cụ kiểm thử đầy đủ.\n"
                     "• Tính năng nổi bật:\n"
                     "   + Thống kê tiến độ trực quan: Bảng đếm tức thời Tổng số testcase, Số testcase chờ duyệt, Đã giữ (Approved) và Đã bỏ (Rejected).\n"
                     "   + Bộ lọc & Sắp xếp: Lọc nhanh theo trạng thái (Tất cả / Chưa duyệt / Đã giữ / Đã bỏ), tìm kiếm từ khóa trong testcase, đổi chiều thứ tự tăng/giảm dần.\n"
                     "   + Thao tác hàng loạt: Nút 'Giữ tất cả' và 'Bỏ tất cả' giúp tiết kiệm tối đa thời gian thao tác.\n"
                     "   + Chỉnh sửa trực tiếp từng testcase: Sửa tiêu đề, điều kiện tiên quyết (Pre-conditions), các bước thực hiện (Steps), kết quả mong đợi (Expected Results), độ ưu tiên (Priority), loại kiểm thử (Type).\n"
                     "   + Cơ chế Phản hồi & AI Chạy lại (Revision & Re-run): Các nút gợi ý cải thiện có sẵn kèm khung nhập ý kiến để AI tạo lại các testcase chưa đạt yêu cầu.\n"
                     "   + Phê duyệt & Xuất dữ liệu: Tự động ghi nhận và đẩy các testcase được chọn vào file Google Sheets của dự án qua Google Sheets API.")
    add_image_placeholder(doc, "Giao diện Xem trước và Duyệt Testcase", 
                          "Chèn ảnh chụp giao diện review.html hoặc modal duyệt testcase với các thao tác Giữ/Bỏ/Sửa", 
                          "05_review_testcase.png")

    # Chức năng 6
    p_f6 = doc.add_paragraph()
    p_f6.add_run("6. Trợ lý QA AI Tương tác trực tiếp (Embedded Dify Chat Assistant)")
    style_heading2(p_f6)
    p_f6_desc = doc.add_paragraph()
    p_f6_desc.add_run("• Mục đích: Trợ lý ảo đồng hành giúp tester giải đáp thắc mắc về nghiệp vụ và gợi ý các kịch bản kiểm thử phức tạp.\n"
                     "• Tính năng chi tiết:\n"
                     "   + Nút nổi (Floating Action Button): Luôn hiển thị ở góc dưới bên phải màn hình để mở nhanh khung chat.\n"
                     "   + Cửa sổ trợ lý Dify nhúng trực tiếp: Kết nối an toàn qua Tailscale Funnel.\n"
                     "   + Năng lực hỗ trợ: Giải thích chi tiết tài liệu đặc tả, gợi ý các bộ dữ liệu kiểm thử (Test Data), tư vấn các kịch bản ngoại lệ hóc búa.")
    add_image_placeholder(doc, "Cửa sổ Trợ lý QA AI Chatbot (Dify)", 
                          "Chèn ảnh chụp khung chat Dify Assistant bên phải màn hình", 
                          "06_ai_chat_assistant.png")

    # Chức năng 7
    p_f7 = doc.add_paragraph()
    p_f7.add_run("7. Tự động Đồng bộ Kết quả lên Google Workspace")
    style_heading2(p_f7)
    p_f7_desc = doc.add_paragraph()
    p_f7_desc.add_run("• Mục đích: Xuất bản tài liệu kiểm thử hoàn chỉnh, đồng bộ theo định dạng chuẩn của tổ chức để bàn giao cho khách hàng hoặc đội ngũ phát triển.\n"
                     "• Tính năng chi tiết:\n"
                     "   + Gọi trực tiếp Google Sheets API để tạo Sheet mới theo tên bài toán trong bảng tính Google Sheet tổng thể.\n"
                     "   + Định dạng bảng chuyên nghiệp với tiêu đề cột, màu sắc phân loại và công thức tính toán tự động.\n"
                     "   + Cung cấp liên kết mở trực tiếp file Google Sheets và tài liệu Google Docs ngay trên giao diện web.")
    add_image_placeholder(doc, "Kết quả Bộ Testcase Đồng bộ trên Google Sheets", 
                          "Chèn ảnh chụp file Google Sheet chứa các testcase được xuất tự động", 
                          "07_google_sheet_result.png")

    # ==================== PHẦN III ====================
    doc.add_page_break()
    p_p3 = doc.add_paragraph()
    p_p3.add_run("PHẦN III: BẢNG TỔNG KẾT MA TRẬN HẠ TẦNG VÀ TÍNH NĂNG")
    style_heading1(p_p3)
    
    matrix_data = [
        ("Phân hệ", "Công nghệ / Nền tảng", "Vai trò trong hệ thống", "Giao diện / Điểm tích hợp"),
        ("Giao diện Web", "HTML5, TailwindCSS, Lucide, JS ES6+", "Bảng điều khiển quản lý và điều phối toàn bộ hệ thống", "index.html, review.html, login.html"),
        ("Máy chủ Dịch vụ", "Python 3.10+ (ThreadingHTTPServer)", "Xử lý CRUD, điều phối AI pipeline, quản lý phiên", "REST API (/api/tasks, /api/tasks/run...)"),
        ("AI Pipeline Engine", "Native Python (AiPipelineService)", "Trích xuất tài liệu, phân tích BA, sinh testcase", "BE/services/ai_pipeline_service.py"),
        ("Thu thập Tài liệu", "Python DocumentCrawler", "Cào nội dung Google Docs, Sheets, Web, Figma API", "BE/services/doc_crawler.py"),
        ("Bộ nhớ & RAG", "MemoryService & ChromaDB", "Quản lý bộ nhớ testcase và vector embeddings", "BE/chroma_db, memory_service.py"),
        ("Mạng & Bảo mật", "Tailscale Mesh VPN + Funnel", "Kết nối an toàn mạng nội bộ và public Dify qua HTTPS", "Domain vdtc-hungdv.tailfb2503.ts.net"),
        ("Cơ sở dữ liệu", "Supabase Cloud (PostgreSQL)", "Lưu trữ người dùng, bài toán, kết quả JSON thời gian thực", "Tables: problems, users"),
        ("Lưu trữ & Xuất bản", "Google Drive / Docs / Sheets API", "Upload tài liệu gốc, xuất file Testcase chuẩn", "Google Workspace Python Client"),
        ("Trí tuệ Nhân tạo", "Viettel AI (DeepSeek-V4.1-Flash)", "Sinh testcase tốc độ cao, bám sát nghiệp vụ", "Viettel AI MaaS API"),
        ("Trợ lý Trò chuyện", "Dify Chatbot Platform", "Trợ lý ảo giải đáp nghiệp vụ trực tuyến", "Side-panel iframe nhúng"),
        ("Thiết kế Giao diện", "Figma REST API", "Đọc wireframe UI/UX để sinh testcase màn hình", "Figma Access Token")
    ]
    
    tbl = doc.add_table(rows=len(matrix_data), cols=4)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False
    
    col_widths = [Inches(1.3), Inches(1.8), Inches(2.0), Inches(1.4)]
    
    for row_idx, row in enumerate(tbl.rows):
        is_header = (row_idx == 0)
        trPr = row._tr.get_or_add_trPr()
        trPr.append(parse_xml(f'<w:cantSplit {nsdecls("w")}/>'))
        if is_header:
            trPr.append(parse_xml(f'<w:tblHeader {nsdecls("w")}/>'))
            
        for col_idx, cell in enumerate(row.cells):
            cell.width = col_widths[col_idx]
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            set_cell_margins(cell, top=100, bottom=100, left=120, right=120)
            
            if is_header:
                set_cell_background(cell, "1E3A8A") # Navy Blue
                set_cell_border(cell, 
                    top={"val": "single", "sz": "6", "color": "1E3A8A"},
                    bottom={"val": "single", "sz": "12", "color": "1E3A8A"},
                    left={"val": "single", "sz": "4", "color": "3B82F6"},
                    right={"val": "single", "sz": "4", "color": "3B82F6"}
                )
            else:
                bg = "F8FAFC" if row_idx % 2 == 1 else "FFFFFF"
                set_cell_background(cell, bg)
                set_cell_border(cell, 
                    top={"val": "single", "sz": "4", "color": "E2E8F0"},
                    bottom={"val": "single", "sz": "4", "color": "E2E8F0"},
                    left={"val": "single", "sz": "4", "color": "E2E8F0"},
                    right={"val": "single", "sz": "4", "color": "E2E8F0"}
                )
                
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
            text_val = matrix_data[row_idx][col_idx]
            run = p.add_run(text_val)
            run.font.name = 'Calibri'
            if is_header:
                run.bold = True
                run.font.size = Pt(10)
                run.font.color.rgb = RGBColor(255, 255, 255)
            else:
                if col_idx == 0:
                    run.bold = True
                    run.font.color.rgb = RGBColor(15, 23, 42)
                else:
                    run.font.color.rgb = RGBColor(51, 65, 85)
                run.font.size = Pt(9.5)
                
    doc.add_paragraph()
    p_foot = doc.add_paragraph()
    p_foot.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r_foot = p_foot.add_run("Tài liệu kỹ thuật hệ thống AutoTC.")
    r_foot.italic = True
    r_foot.font.size = Pt(9)
    r_foot.font.color.rgb = RGBColor(148, 163, 184)
    
    output_path = "TAI_LIEU_CHUC_NANG_VA_KIEN_TRUC_AUTOTC.docx"
    doc.save(output_path)
    print(f"Xuat thanh cong: {output_path}")

if __name__ == "__main__":
    create_document()
