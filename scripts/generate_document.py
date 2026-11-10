import os
import sys
import docx
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import nsdecls, qn

IMG_DIR = r"D:\PersonalData\ảnh chức năng\ảnh chức năng"
DOCX_OUT = r"C:\Users\vdtchungdv\Desktop\FE_AutoTC\TAI_LIEU_CHUC_NANG_VA_KIEN_TRUC_AUTOTC.docx"

def set_cell_background(cell, hex_color):
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
    cell._tc.get_or_add_tcPr().append(shd)

def set_cell_margins(cell, top=140, bottom=140, left=200, right=200):
    tcMar = parse_xml(f'''
        <w:tcMar {nsdecls("w")}>
            <w:top w:w="{top}" w:type="dxa"/>
            <w:bottom w:w="{bottom}" w:type="dxa"/>
            <w:left w:w="{left}" w:type="dxa"/>
            <w:right w:w="{right}" w:type="dxa"/>
        </w:tcMar>
    ''')
    cell._tc.get_or_add_tcPr().append(tcMar)

def set_cell_borders(cell, top=None, bottom=None, left=None, right=None):
    def border_xml(name, b):
        if not b:
            return f'<w:{name} w:val="none"/>'
        return f'<w:{name} w:val="{b.get("val","single")}" w:sz="{b.get("sz","4")}" w:space="0" w:color="{b.get("color","auto")}"/>'
    
    xml = f'''
        <w:tcBorders {nsdecls("w")}>
            {border_xml("top", top)}
            {border_xml("left", left)}
            {border_xml("bottom", bottom)}
            {border_xml("right", right)}
        </w:tcBorders>
    '''
    cell._tc.get_or_add_tcPr().append(parse_xml(xml))

def add_callout(doc, text, title="LƯU Ý NGHIỆP VỤ", hex_bg="F8FAFC", hex_border="2563EB"):
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = tbl.cell(0, 0)
    set_cell_background(cell, hex_bg)
    set_cell_margins(cell, top=140, bottom=140, left=200, right=180)
    set_cell_borders(cell, 
                     left={"val": "single", "sz": "24", "color": hex_border},
                     top={"val": "single", "sz": "4", "color": "E2E8F0"},
                     right={"val": "single", "sz": "4", "color": "E2E8F0"},
                     bottom={"val": "single", "sz": "4", "color": "E2E8F0"})
    
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.line_spacing = 1.15
    run_t = p.add_run(f"📌 {title}: ")
    run_t.bold = True
    run_t.font.name = "Segoe UI"
    run_t.font.size = Pt(9.5)
    run_t.font.color.rgb = RGBColor(30, 58, 138)
    
    run_c = p.add_run(text)
    run_c.font.name = "Segoe UI"
    run_c.font.size = Pt(9.5)
    run_c.font.color.rgb = RGBColor(51, 65, 85)
    
    p_after = doc.add_paragraph()
    p_after.paragraph_format.space_before = Pt(0)
    p_after.paragraph_format.space_after = Pt(4)

def add_heading_1(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(18)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    run.bold = True
    run.font.name = "Segoe UI"
    run.font.size = Pt(15)
    run.font.color.rgb = RGBColor(15, 23, 42)
    return p

def add_heading_2(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(13)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    run.bold = True
    run.font.name = "Segoe UI"
    run.font.size = Pt(12.5)
    run.font.color.rgb = RGBColor(29, 78, 216)
    return p

def add_heading_3(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(9)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    run.bold = True
    run.font.name = "Segoe UI"
    run.font.size = Pt(11)
    run.font.color.rgb = RGBColor(14, 116, 144)
    return p

def add_body(doc, text, bold_prefix=None, space_after=4):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(1)
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = 1.15
    if bold_prefix:
        r_pre = p.add_run(bold_prefix)
        r_pre.bold = True
        r_pre.font.name = "Segoe UI"
        r_pre.font.size = Pt(10)
        r_pre.font.color.rgb = RGBColor(15, 23, 42)
    r = p.add_run(text)
    r.font.name = "Segoe UI"
    r.font.size = Pt(10)
    r.font.color.rgb = RGBColor(51, 65, 85)
    return p

def add_bullet(doc, text, bold_prefix=None, level=0):
    p = doc.add_paragraph(style='List Bullet')
    p.paragraph_format.space_before = Pt(1)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.line_spacing = 1.15
    p.paragraph_format.left_indent = Inches(0.25 * (level + 1))
    if bold_prefix:
        r_pre = p.add_run(bold_prefix)
        r_pre.bold = True
        r_pre.font.name = "Segoe UI"
        r_pre.font.size = Pt(10)
        r_pre.font.color.rgb = RGBColor(15, 23, 42)
    r = p.add_run(text)
    r.font.name = "Segoe UI"
    r.font.size = Pt(10)
    r.font.color.rgb = RGBColor(51, 65, 85)
    return p

def add_image_box(doc, img_filename, caption, width=Inches(5.8)):
    img_path = os.path.join(IMG_DIR, img_filename)
    if not os.path.exists(img_path):
        print(f"WARNING: Image not found: {img_path}")
        return
    
    p_img = doc.add_paragraph()
    p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_img.paragraph_format.space_before = Pt(8)
    p_img.paragraph_format.space_after = Pt(3)
    p_img.paragraph_format.keep_with_next = True
    run_img = p_img.add_run()
    run_img.add_picture(img_path, width=width)
    
    p_cap = doc.add_paragraph()
    p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_cap.paragraph_format.space_before = Pt(0)
    p_cap.paragraph_format.space_after = Pt(8)
    run_cap = p_cap.add_run(caption)
    run_cap.italic = True
    run_cap.font.name = "Segoe UI"
    run_cap.font.size = Pt(9)
    run_cap.font.color.rgb = RGBColor(100, 116, 139)

def build_document():
    doc = Document()
    
    # Page setup
    for sec in doc.sections:
        sec.top_margin = Inches(0.8)
        sec.bottom_margin = Inches(0.8)
        sec.left_margin = Inches(0.85)
        sec.right_margin = Inches(0.85)

    # Header / Title Block
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_title.paragraph_format.space_before = Pt(10)
    p_title.paragraph_format.space_after = Pt(4)
    run_t1 = p_title.add_run("TÀI LIỆU ĐẶC TẢ YÊU CẦU CHỨC NĂNG VÀ KIẾN TRÚC HẠ TẦNG\n")
    run_t1.bold = True
    run_t1.font.name = "Segoe UI"
    run_t1.font.size = Pt(17)
    run_t1.font.color.rgb = RGBColor(30, 58, 138)
    
    run_t2 = p_title.add_run("HỆ THỐNG TỰ ĐỘNG HÓA KIỂM THỬ THÔNG MINH (AUTOTC - AI DASHBOARD)")
    run_t2.bold = True
    run_t2.font.name = "Segoe UI"
    run_t2.font.size = Pt(13)
    run_t2.font.color.rgb = RGBColor(14, 116, 144)

    # Sub metadata
    p_meta = doc.add_paragraph()
    p_meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_meta.paragraph_format.space_before = Pt(2)
    p_meta.paragraph_format.space_after = Pt(16)
    r_meta = p_meta.add_run("Phiên bản: 2.0  |  Cập nhật: Tháng 11/2026  |  Đội ngũ Phát triển: AutoTC Team  |  Trạng thái: Hoàn thiện")
    r_meta.italic = True
    r_meta.font.name = "Segoe UI"
    r_meta.font.size = Pt(9)
    r_meta.font.color.rgb = RGBColor(100, 116, 139)

    add_callout(doc, 
                "Tài liệu này được biên soạn toàn diện, tích hợp đầy đủ 10 nhóm tính năng cốt lõi theo quy chuẩn vận hành của hệ thống AutoTC, kết hợp kiến trúc hạ tầng kỹ thuật phân tán và bộ ảnh chụp giao diện thực tế từ hệ thống đang chạy. Độc giả có thể tra cứu nhanh quy trình thao tác và cơ chế kỹ thuật tương ứng.", 
                title="MỤC TIÊU & PHẠM VI TÀI LIỆU")

    # =========================================================================
    # PHẦN I: KIẾN TRÚC HẠ TẦNG HỆ THỐNG
    # =========================================================================
    add_heading_1(doc, "PHẦN I: KIẾN TRÚC HẠ TẦNG HỆ THỐNG (SYSTEM INFRASTRUCTURE ARCHITECTURE)")
    
    add_body(doc, 
             "Hệ thống AutoTC (AI Automation Dashboard) được nghiên cứu và xây dựng theo mô hình kiến trúc phân tán hiện đại, hướng dịch vụ (Service-Oriented Architecture), tối ưu hóa xử lý bất đồng bộ non-blocking để phục vụ quy trình tự động hóa kiểm thử phần mềm từ đầu đến cuối (End-to-End Testing Automation). Toàn bộ chu trình từ tiếp nhận tài liệu đặc tả nghiệp vụ ban đầu (SRS/UC/BRD), phân tích bóc tách yêu cầu, tra cứu bộ nhớ QA chống trùng lặp, đến việc ứng dụng mô hình trí tuệ nhân tạo (AI MaaS) sinh kịch bản testcase chi tiết và tự động đồng bộ hóa kết quả lên Google Workspace đều được điều phối trực tiếp bởi máy chủ Backend Python Native đa luồng.")

    add_heading_2(doc, "1. Sơ đồ Phân tầng Hạ tầng Kỹ thuật Tổng thể")
    add_body(doc, "Hạ tầng hệ thống AutoTC được chuẩn hóa thành 5 phân lớp kỹ thuật độc lập, đảm bảo tính mô-đun hóa, khả năng mở rộng quy mô linh hoạt và tính bảo mật nghiêm ngặt:")
    
    add_bullet(doc, "Ứng dụng web Single Page Application (SPA) phát triển trên nền HTML5, Tailwind CSS, Lucide Icons và JavaScript ES6+ thuần. Kết nối trực tiếp với RESTful API Backend và Supabase Realtime.", "• Lớp Giao diện Người dùng (Frontend): ")
    add_bullet(doc, "Ứng dụng Tailscale Mesh VPN bảo vệ kết nối mạng nội bộ giữa máy chủ Backend và cụm trợ lý ảo Dify. Sử dụng Tailscale Funnel đóng vai trò Reverse Proxy an toàn mở cổng HTTPS bảo vệ.", "• Lớp Mạng & Định tuyến Bảo mật (Tailscale): ")
    add_bullet(doc, "Máy chủ Python 3.10+ sử dụng ThreadingHTTPServer đa luồng kết hợp AiPipelineService native, điều phối toàn bộ pipeline phân tích tài liệu và sinh kịch bản kiểm thử.", "• Lớp Pipeline AI Backend (Python Engine): ")
    add_bullet(doc, "Supabase Cloud (PostgreSQL) quản lý người dùng, phân quyền và dữ liệu bài toán thời gian thực; Google Workspace (Docs, Sheets, Drive) lưu trữ tài liệu đặc tả và bảng testcase chuẩn.", "• Lớp Cơ sở Dữ liệu & Lưu trữ Đám mây: ")
    add_bullet(doc, "Viettel AI MaaS (mô hình DeepSeek-V4.1-Flash tiếng Việt) cho tác vụ suy luận testcase tốc độ cao; Figma REST API cho việc trích xuất bố cục giao diện UI/UX trực tiếp từ link thiết kế.", "• Lớp Trí tuệ Nhân tạo & Tích hợp Dịch vụ Ngoài: ")

    add_heading_2(doc, "2. Chi tiết các Phân lớp Hạ tầng Kỹ thuật")
    
    add_heading_3(doc, "A. Lớp Giao diện Người dùng (Frontend)")
    add_bullet(doc, "HTML5, CSS3, Tailwind CSS (triển khai CDN tối ưu tải trang), thư viện biểu tượng Lucide Icons trực quan, Vanilla JavaScript (ES6+), Supabase JS Client v2.", "• Công nghệ nền tảng: ")
    add_bullet(doc, "Hệ thống hỗ trợ cả môi trường phát triển cục bộ qua Live Server (cổng http://127.0.0.1:5500) và triển khai trên máy chủ phân tán có cấu hình HTTPS.", "• Môi trường triển khai: ")
    add_bullet(doc, "Bao gồm index.html (Bảng điều khiển chính, thêm/sửa/xóa bài toán, kích hoạt AI, theo dõi tiến độ), review.html (Màn hình chuyên dụng duyệt, chỉnh sửa và phản hồi testcase), và login.html (Cổng đăng nhập xác thực).", "• Các trang giao diện: ")
    add_bullet(doc, "Toàn bộ tương tác đều sử dụng fetch API bất đồng bộ, tích hợp cơ chế AbortController cho phép người dùng dừng khẩn cấp các request đang xử lý mà không làm treo trình duyệt.", "• Cơ chế truyền thông: ")

    add_heading_3(doc, "B. Lớp Máy chủ Dịch vụ & Pipeline AI Backend (Python 3.10+)")
    add_bullet(doc, "Xây dựng trên nền tảng Python 3.10+ sử dụng ThreadingHTTPServer đa luồng, xử lý non-blocking đồng thời nhiều phiên kiểm thử độc lập.", "• Máy chủ dịch vụ: ")
    add_bullet(doc, "Lắng nghe mặc định tại cổng http://0.0.0.0:3000, khởi động nhanh qua run_backend.bat.", "• Cổng dịch vụ: ")
    add_bullet(doc, "Tự động nhận diện URL, cào nội dung từ Google Docs, Google Sheets, website và trích xuất cấu trúc UI từ Figma qua Figma REST API Access Token.", "• Module DocumentCrawler: ")
    add_bullet(doc, "Phân tích đặc tả nghiệp vụ (SRS/UC), tự động xây dựng cây chức năng, phân loại quy tắc nghiệp vụ và xác định ranh giới kiểm thử.", "• Module BA Analysis Engine: ")
    add_bullet(doc, "Bóc tách từng tiêu chí chức năng kèm ID chuẩn hóa và điều kiện chấp nhận (Acceptance Criteria).", "• Module Requirement Extractor: ")
    add_bullet(doc, "Kho lưu trữ vector embeddings cục bộ tại thư mục BE/chroma_db, lưu trữ các testcase mẫu và tri thức kiểm thử lịch sử nhằm loại bỏ trùng lặp và tăng độ bao phủ.", "• Module MemoryService & ChromaDB: ")
    add_bullet(doc, "Sinh bộ tiền điều kiện (Pre-conditions), các bước thực hiện (Steps), kết quả mong đợi (Expected Results), phân loại Type và gán độ ưu tiên (Priority).", "• Module Condition & Testcase Generator: ")
    add_bullet(doc, "Sử dụng ThreadPoolExecutor để quản lý luồng xử lý song song nhiều bài toán, kết hợp mảng cờ _cancelled_tasks cho phép ngắt tiến trình tức thì.", "• Module Multi-thread & Cancel Controller: ")
    add_bullet(doc, "Đồng hồ bấm giờ chính xác đến mili-giây, ghi nhận thời gian thực thi của từng bài toán phục vụ đo kiểm hiệu năng.", "• Module ExecutionTracker: ")
    add_bullet(doc, "Kiểm tra định dạng MIME hợp lệ, kiểm soát giới hạn dung lượng tải lên (20MB/file, tối đa 50MB/tổng upload), chuyển đổi chuẩn hóa trước khi đẩy lên Drive.", "• Module FileProcessing: ")

    add_heading_3(doc, "C. Lớp Cơ sở Dữ liệu & Lưu trữ Đám mây (Supabase & Google Workspace)")
    add_bullet(doc, "Quản lý bảng public.problems (lưu trữ metadata bài toán, trạng thái thực thi: Chưa làm / Đang chạy / Chờ duyệt / Hoàn thành / Lỗi, JSON testcase chi tiết, người phụ trách) và bảng public.users (tài khoản, mật khẩu băm bảo mật, vai trò admin/tester). Dữ liệu được đồng bộ thời gian thực qua Supabase Realtime WebSocket.", "• Supabase Cloud (PostgreSQL): ")
    add_bullet(doc, "Tích hợp trực tiếp thông qua thư viện Google API Client chính thức trên Python. Hỗ trợ song song cả Service Account (dành cho Shared Drive tổ chức) và OAuth Desktop App (dành cho tài khoản cá nhân, loại bỏ giới hạn quota). Tự động khởi tạo bảng tính, phân trang sheet theo bài toán và điền kịch bản kiểm thử.", "• Google Workspace (Drive, Docs, Sheets API): ")

    add_heading_3(doc, "D. Lớp Mạng & Định tuyến Bảo mật (Tailscale Mesh VPN & Funnel)")
    add_bullet(doc, "Thiết lập mạng ảo an toàn liên kết nội bộ giữa máy chủ Backend AutoTC và dịch vụ Chatbot Dify (domain định danh vdtc-hungdv.tailfb2503.ts.net), cô lập hoàn toàn khỏi internet công cộng.", "• Tailscale Mesh VPN: ")
    add_bullet(doc, "Mở cổng an toàn qua giao thức HTTPS (cổng 8888), giúp giao diện web nhúng trợ lý ảo thông minh mà không bị trình duyệt chặn do vi phạm chính sách Mixed Content hoặc CORS.", "• Tailscale Funnel: ")

    add_heading_3(doc, "E. Nền tảng Trí tuệ Nhân tạo & Tích hợp Thiết kế")
    add_bullet(doc, "Tận dụng mô hình ngôn ngữ lớn DeepSeek-V4.1-Flash với năng lực hiểu sâu ngữ nghĩa tiếng Việt, tốc độ phản hồi tính bằng giây, tối ưu hóa sinh dữ liệu JSON theo khuôn mẫu định sẵn.", "• Viettel AI Model-as-a-Service (MaaS): ")
    add_bullet(doc, "Nền tảng Chatbot QA thông minh, cung cấp trợ lý ảo đồng hành giải đáp thắc mắc nghiệp vụ ngay trên giao diện bảng điều khiển.", "• Dify Agent Platform: ")
    add_bullet(doc, "Cho phép đọc trực tiếp cấu trúc cây phần tử (DOM/Nodes), hình ảnh wireframe từ link file thiết kế để AI sinh kịch bản kiểm thử giao diện chuẩn xác.", "• Figma REST API: ")

    # =========================================================================
    # PHẦN II: CHI TIẾT CÁC CHỨC NĂNG CỦA HỆ THỐNG AUTOTC
    # =========================================================================
    add_heading_1(doc, "PHẦN II: CHI TIẾT CÁC CHỨC NĂNG CỦA HỆ THỐNG AUTOTC")
    add_body(doc, "Phần này trình bày chi tiết và chuyên sâu toàn bộ 10 nhóm tính năng nghiệp vụ của hệ thống AutoTC, đi kèm hình ảnh chụp thực tế và hướng dẫn thao tác chuẩn cho người dùng.")

    # -------------------------------------------------------------------------
    # Chức năng 1: Đăng nhập
    # -------------------------------------------------------------------------
    add_heading_2(doc, "1. Chức năng Đăng nhập & Xác thực Phân quyền (Authentication & Authorization)")
    add_body(doc, "Mục đích: Đảm bảo an ninh thông tin, kiểm soát chặt chẽ quyền truy cập vào tài nguyên kiểm thử và phân định rõ ràng trách nhiệm của từng thành viên trong dự án.")
    add_body(doc, "Các tính năng và cơ chế hoạt động chi tiết:")
    add_bullet(doc, "Người dùng truy cập vào trang login.html, nhập thông tin Tài khoản (Username) và Mật khẩu (Password). Hệ thống thực hiện mã hóa và kiểm tra xác thực trực tiếp với bảng public.users trên Supabase Cloud.", "• Xác thực tập trung: ")
    add_bullet(doc, "Hệ thống hỗ trợ 2 vai trò cơ bản: \n   + Quản trị viên (Admin): Toàn quyền thêm, chỉnh sửa, xóa bài toán; khởi chạy AI pipeline đa luồng; phân chia người phụ trách và duyệt xuất dữ liệu.\n   + Kiểm thử viên (Tester/Viewer): Xem danh sách bài toán, theo dõi tiến độ thực thi và duyệt/chỉnh sửa các bài toán được phân công cho chính mình.", "• Phân quyền 2 cấp độ (Role-Based Access Control): ")
    add_bullet(doc, "Thông tin phiên làm việc được lưu trữ tại LocalStorage/SessionStorage. Áp dụng cơ chế Rolling Renewal (tự động gia hạn khi người dùng thao tác), tự động đăng xuất sau 7 ngày không hoạt động để phòng ngừa rủi ro lộ lọt phiên.", "• Quản lý phiên làm việc thông minh: ")
    add_bullet(doc, "Góc trên bên phải màn hình hiển thị trực quan thông tin người dùng đang đăng nhập (Tên hiển thị, Vai trò quản trị/kiểm thử) kèm nút 'Làm mới' danh sách và nút 'Thoát' (Đăng xuất an toàn).", "• Header thông tin người dùng: ")

    add_image_box(doc, "a3580db5f665763b2f74.jpg", 
                  "Hình 1.1: Giao diện Đăng nhập hệ thống AutoTC (login.html) kết nối xác thực Supabase", 
                  width=Inches(5.6))

    # -------------------------------------------------------------------------
    # Chức năng 2: Thêm sửa xóa bài toán
    # -------------------------------------------------------------------------
    add_heading_2(doc, "2. Chức năng Quản lý Bài toán Kiểm thử: Thao tác Thêm, Sửa, Xóa")
    add_body(doc, "Mục đích: Cho phép Tester và Admin khởi tạo bài toán mới từ nhiều nguồn dữ liệu khác nhau, quản lý danh sách tập trung, cập nhật liên kết tài nguyên và dọn dẹp các bài toán không còn sử dụng.")
    
    add_heading_3(doc, "A. Giao diện Bảng điều khiển Tổng quan (Dashboard)")
    add_body(doc, "Màn hình chính của AutoTC (index.html) được thiết kế hiện đại, khoa học, chia làm 2 khu vực rõ ràng: Form khởi tạo bài toán mới ở cột bên trái và Bảng danh sách bài toán ở khu vực trung tâm.")
    add_bullet(doc, "Bảng danh sách hiển thị đầy đủ các trường thông tin: Ô checkbox chọn bài toán, Tên bài toán, Người làm, Trạng thái (Đã xong, Đang chạy, Chưa làm...), Liên kết URL gốc, Link Testcase (Google Sheets), Link Phân tích (Google Docs) và Cột tác vụ (Sửa, Xóa, Chuyển giao).", "• Bảng danh sách bài toán: ")
    add_bullet(doc, "Thanh tìm kiếm nhanh (Real-time Filter) cho phép lọc danh sách bài toán ngay khi gõ phím, hỗ trợ tìm kiếm theo tên bài toán hoặc người phụ trách.", "• Tìm kiếm thời gian thực: ")

    add_image_box(doc, "61717f7385a305fd5cb2.jpg", 
                  "Hình 2.1: Giao diện Bảng điều khiển (Dashboard) tổng quan và Danh sách bài toán kiểm thử", 
                  width=Inches(6.2))

    add_heading_3(doc, "B. Chức năng Thêm bài toán mới (URL & Import File)")
    add_body(doc, "Hệ thống hỗ trợ 2 phương thức tiếp nhận tài liệu đặc tả đầu vào vô cùng linh hoạt:")
    add_bullet(doc, "Người dùng chọn tab 'Thêm URL', nhập Tên bài toán (ví dụ: 'Bài toán HotFix_Dán thẻ'), dán đường dẫn Google Docs, Google Sheets hoặc link Figma thiết kế. Người dùng có thể nhấn nút '+ Thêm' để đính kèm nhiều đường dẫn tài liệu cùng lúc trước khi bấm 'Lưu'.", "• Phương thức 1 - Thêm URL trực tuyến: ")
    add_bullet(doc, "Người dùng chuyển sang tab 'Import File', chọn các tệp tin từ máy tính cá nhân (hỗ trợ .doc, .docx, .xls, .xlsx, .pdf, .txt). Backend Python tự động upload tệp tin lên Google Drive dự án và chuyển đổi định dạng tương thích để AI dễ dàng phân tích.", "• Phương thức 2 - Import File từ máy tính: ")

    add_image_box(doc, "3ce2dfad3e7dbe23e76c.jpg", 
                  "Hình 2.2: Form Thêm bài toán mới hỗ trợ nhập URL đa liên kết và Import File tài liệu", 
                  width=Inches(4.2))

    add_heading_3(doc, "C. Chức năng Chỉnh sửa và Xóa bài toán")
    add_bullet(doc, "Khi người dùng nhấn vào biểu tượng bút chỉnh sửa tại cột Thao tác, modal 'Cập nhật bài toán' sẽ xuất hiện. Người dùng có thể sửa đổi Tên bài toán, bổ sung thêm link tài liệu hoặc thay thế liên kết cũ, sau đó bấm 'Lưu thay đổi'. Dữ liệu lập tức đồng bộ về CSDL Supabase.", "• Chỉnh sửa bài toán (Update): ")
    add_bullet(doc, "Người dùng nhấn biểu tượng thùng rác để xóa bài toán không còn nhu cầu kiểm thử. Hệ thống hiển thị hộp thoại xác nhận để tránh thao tác nhầm lẫn, sau đó tiến hành gỡ bỏ bản ghi trong CSDL và làm mới bảng dữ liệu.", "• Xóa bài toán (Delete): ")

    add_image_box(doc, "1141ed8b0c5b8c05d54a.jpg", 
                  "Hình 2.3: Hộp thoại Modal 'Cập nhật bài toán' cho phép sửa tên và cập nhật link tài liệu", 
                  width=Inches(4.2))

    # -------------------------------------------------------------------------
    # Chức năng 3: Màn hình prompt thêm
    # -------------------------------------------------------------------------
    add_heading_2(doc, "3. Màn hình Cấu hình Prompt Thêm (AI Custom Prompt Modal)")
    add_body(doc, "Mục đích: Cho phép Tester cung cấp các chỉ thị và yêu cầu kiểm thử bổ sung cho mô hình AI trước khi kích hoạt pipeline phân tích tài liệu và sinh testcase.")
    add_body(doc, "Đặc điểm và khả năng tùy biến chuyên sâu:")
    add_bullet(doc, "Khi Tester nhấn nút chạy một bài toán cụ thể, hệ thống mở modal 'Chạy AI - [Tên bài toán]' (ví dụ: Chạy AI - VTQ_FINTWIN).", "• Kích hoạt linh hoạt: ")
    add_bullet(doc, "Cung cấp khung văn bản PROMPT AI cho phép người dùng nhập các chỉ thị nghiệp vụ riêng biệt, ví dụ:\n   + 'Bổ sung kịch bản Negative case cho trường hợp nhập sai định dạng số điện thoại.'\n   + 'Tập trung kiểm thử Boundary case (giá trị biên) cho hạn mức chuyển tiền từ 1.000 VNĐ đến 500.000.000 VNĐ.'\n   + 'Kiểm tra phân quyền: User thường không được phép truy cập API phê duyệt hợp đồng.'\n   + 'Bổ sung trường hợp mất kết nối mạng và phản hồi timeout từ phía bên thứ 3.'", "• Nội dung prompt tùy biến: ")
    add_bullet(doc, "Sau khi nhập xong prompt, Tester nhấn nút 'Bắt đầu chạy' (màu xanh dương) để chuyển bài toán sang trạng thái thực thi. Nếu không cần thêm prompt, người dùng có thể để trống hoặc nhấn 'Hủy bỏ'.", "• Điều khiển thao tác: ")

    add_image_box(doc, "7cab78289ef81ea647e9.jpg", 
                  "Hình 3.1: Màn hình Modal Cấu hình Prompt AI bổ sung trước khi kích hoạt bài toán", 
                  width=Inches(6.0))

    # -------------------------------------------------------------------------
    # Chức năng 4: Màn phân chia bài toán
    # -------------------------------------------------------------------------
    add_heading_2(doc, "4. Màn hình Phân chia & Chuyển giao Bài toán (Task Assignment & Delegation)")
    add_body(doc, "Mục đích: Phân công trách nhiệm rõ ràng cho từng kiểm thử viên, đảm bảo tiến độ dự án và dễ dàng chuyển giao công việc khi có sự thay đổi nhân sự.")
    add_body(doc, "Chi tiết quy trình chuyển giao:")
    add_bullet(doc, "Tại cột 'NGƯỜI LÀM' trên Dashboard, mỗi bài toán đều hiển thị tài khoản của người đang phụ trách chính (ví dụ: hungtest, namnv...).", "• Trực quan hóa người phụ trách: ")
    add_bullet(doc, "Khi nhấn vào tên người làm hoặc biểu tượng chuyển giao tại hàng bài toán, hệ thống hiển thị modal 'Chuyển giao bài toán' thông báo rõ: 'Bạn đang chuyển giao bài toán: [Tên bài toán]'.", "• Hộp thoại Chuyển giao: ")
    add_bullet(doc, "Dropdown 'CHỌN NGƯỜI NHẬN' liệt kê danh sách toàn bộ các thành viên kiểm thử trong hệ thống (hungtest, namnv, doanhdv, linhvt, anhhk, nhanvtth, detx, ducnm...). Người quản lý chỉ cần chọn người nhận mong muốn.", "• Danh sách nhân sự: ")
    add_bullet(doc, "Sau khi chọn, thông tin người phụ trách mới được cập nhật ngay lập tức vào Supabase và kích hoạt thông báo Realtime hiển thị trực tiếp trên giao diện của cả người chuyển và người nhận mà không cần tải lại trang.", "• Đồng bộ Realtime tức thì: ")

    add_image_box(doc, "3694f6f51325937bca34.jpg", 
                  "Hình 4.1: Hộp thoại Modal 'Chuyển giao bài toán' với danh sách thành viên tiếp nhận", 
                  width=Inches(6.0))

    # -------------------------------------------------------------------------
    # Chức năng 5: Màn bài toán chạy
    # -------------------------------------------------------------------------
    add_heading_2(doc, "5. Màn hình Bài toán Chạy & Theo dõi Tiến trình (Real-time Execution & Tracking)")
    add_body(doc, "Mục đích: Cung cấp góc nhìn trực quan theo thời gian thực về tiến độ phân tích tài liệu và sinh testcase của mô hình AI, giúp Tester nắm bắt tình trạng xử lý của hệ thống.")
    add_body(doc, "Cơ chế hiển thị và theo dõi tiến trình:")
    add_bullet(doc, "Tester có thể tích chọn nhiều bài toán bằng ô checkbox ở đầu mỗi hàng và bấm nút 'Chạy bài chọn' (màu đen) ở góc trên bảng để kích hoạt chạy đồng thời đa luồng thông qua ThreadPoolExecutor của Python Backend.", "• Kích hoạt chạy đơn hoặc chạy hàng loạt: ")
    add_bullet(doc, "Khi bài toán bắt đầu chạy, nhãn trạng thái tại cột TRẠNG THÁI tự động đổi sang màu xanh lơ nhạt với biểu tượng xoay (loading spinner) và nhãn 'Đang chạy'.", "• Hiệu ứng trực quan: ")
    add_bullet(doc, "Tích hợp bộ đếm giờ thực thi (Execution Tracker) ghi nhận thời gian chạy theo định dạng mm:ss (ví dụ: '00:09'). Bộ đếm giờ tăng liên tục theo từng giây, giúp Tester biết chính xác thời gian AI đang xử lý tài liệu.", "• Bộ đếm giờ thời gian thực: ")

    # -------------------------------------------------------------------------
    # Chức năng 6: Chức năng dừng bài toán
    # -------------------------------------------------------------------------
    add_heading_2(doc, "6. Chức năng Dừng Bài toán Khẩn cấp (Stop Stream / Task Cancellation)")
    add_body(doc, "Mục đích: Cho phép người dùng can thiệp ngắt luồng xử lý bài toán ngay lập tức khi phát hiện cung cấp sai tài liệu đặc tả, muốn điều chỉnh lại prompt hoặc không muốn tiếp tục tiêu tốn tài nguyên tính toán.")
    add_body(doc, "Cơ chế kỹ thuật và thao tác dừng:")
    add_bullet(doc, "Ngay khi có ít nhất một bài toán chuyển sang trạng thái Đang chạy, giao diện Dashboard sẽ tự động hiển thị nút bấm màu đỏ nổi bật: 'Dừng bài đang chạy' (Stop button) cạnh nút 'Chạy bài chọn'.", "• Nút dừng nổi bật: ")
    add_bullet(doc, "Khi Tester nhấn nút 'Dừng bài đang chạy', Frontend gửi ngay một HTTP POST request đến endpoint /api/tasks/stop kèm ID bài toán. Tại Backend Python, AiPipelineService kiểm tra cờ _cancelled_tasks và ngắt luồng Thread đang gọi đến Viettel AI MaaS, giải phóng ngay lập tức tài nguyên worker thread.", "• Cơ chế ngắt luồng Backend an toàn: ")
    add_bullet(doc, "Trạng thái bài toán lập tức được cập nhật thành dừng hoặc hủy bỏ, bộ đếm giờ dừng lại và giải phóng giao diện để người dùng có thể thực hiện thao tác khác.", "• Cập nhật trạng thái tức thời: ")

    add_image_box(doc, "70d9ae564886c8d89197.jpg", 
                  "Hình 5.1 & 6.1: Màn hình Bài toán đang chạy kèm đồng hồ đếm giờ (00:09) và Nút đỏ 'Dừng bài đang chạy'", 
                  width=Inches(6.2))

    # -------------------------------------------------------------------------
    # Chức năng 7: Chức năng chọn testcase
    # -------------------------------------------------------------------------
    add_heading_2(doc, "7. Chức năng Chọn Testcase & Duyệt Xem trước (Testcase Preview & Selection)")
    add_body(doc, "Mục đích: Cho phép kiểm thử viên xem trước toàn bộ các kịch bản do AI vừa sinh ra, đánh giá chất lượng và chủ động chọn lọc những testcase phù hợp trước khi đưa vào tài liệu chính thức.")
    add_body(doc, "Các tính năng chọn lọc và điều hướng nổi bật:")
    add_bullet(doc, "Hệ thống hỗ trợ 2 chế độ xem: Cửa sổ Modal xem nhanh trên Dashboard hoặc nút 'Toàn màn hình' để mở trang review.html chuyên dụng.", "• Chế độ hiển thị: ")
    add_bullet(doc, "Thanh tiêu đề hiển thị ngay các chỉ số tổng hợp: Tổng số testcase sinh ra (ví dụ: 286), Số lượng Đã giữ (174), Số lượng Bỏ qua (112).", "• Bảng thống kê tức thời: ")
    add_bullet(doc, "Người dùng có thể tích chọn từng checkbox trước mỗi testcase, hoặc nhấn nút 'Tích chọn tất cả để giữ' để chọn toàn bộ chỉ với 1 click. Thanh thông tin phía dưới hiển thị rõ: 'Đã tích chọn giữ 174/286 testcase. Bấm nút Xác nhận để lưu vào Sheet.'", "• Cơ chế tích chọn linh hoạt: ")
    add_bullet(doc, "Mỗi testcase hiển thị mã định danh (ví dụ: [TC]_1, [TC]_2, [TC]_121...), tiêu đề tóm tắt mục đích kiểm thử và nút trạng thái xanh lá '✓ Giữ testcase'. Người dùng có thể bấm để chuyển đổi qua lại giữa 'Giữ' và 'Bỏ qua'.", "• Tương tác từng kịch bản: ")
    add_bullet(doc, "Tích hợp ô tìm kiếm testcase theo từ khóa và bộ lọc sắp xếp thứ tự Tăng dần / Giảm dần theo ID.", "• Tìm kiếm & Sắp xếp: ")

    add_image_box(doc, "098f4a0aabda2b8472cb.jpg", 
                  "Hình 7.1: Modal Duyệt & Xem trước testcase với cơ chế tích chọn, thống kê số lượng và lọc kịch bản", 
                  width=Inches(6.0))

    # -------------------------------------------------------------------------
    # Chức năng 8: Chức năng chỉnh sửa testcase
    # -------------------------------------------------------------------------
    add_heading_2(doc, "8. Chức năng Chỉnh sửa Testcase Trực tiếp (Direct Testcase Editing)")
    add_body(doc, "Mục đích: Cho phép Tester chủ động can thiệp tinh chỉnh nội dung từng kịch bản kiểm thử nhằm đảm bảo tính chính xác 100% theo đúng nghiệp vụ thực tế của dự án.")
    add_body(doc, "Khả năng chỉnh sửa chi tiết:")
    add_bullet(doc, "Khi click mở rộng một testcase trên màn hình review, Tester có thể chỉnh sửa trực tiếp các trường thông tin:", "• Chỉnh sửa đa trường dữ liệu: ")
    add_bullet(doc, "Sửa đổi câu mô tả hành vi người dùng hoặc đối tượng cần kiểm tra.", "   + Mã & Tiêu đề Testcase: ", level=1)
    add_bullet(doc, "Bổ sung hoặc sửa các điều kiện môi trường, trạng thái tài khoản, số dư, cấu hình hệ thống trước khi thực hiện test.", "   + Tiền điều kiện (Pre-conditions): ", level=1)
    add_bullet(doc, "Chỉnh sửa thứ tự và chi tiết các bước thao tác (ví dụ: gửi request POST tới API /api/v1/request-otp/register với payload cụ thể).", "   + Các bước thực hiện (Test Steps): ", level=1)
    add_bullet(doc, "Quy định rõ ràng mã kết quả trả về (code = 1, mess = 'Gửi OTP thành công'), các trường dữ liệu bắt buộc trong payload response.", "   + Kết quả mong đợi (Expected Results): ", level=1)
    add_bullet(doc, "Thay đổi mức độ ưu tiên (High, Medium, Low) và phân loại kiểm thử (Functional, API, Boundary, Security).", "   + Phân loại & Độ ưu tiên: ", level=1)
    add_bullet(doc, "Toàn bộ thay đổi được lưu tạm thời vào state của giao diện và sẵn sàng ghi đè lên CSDL Supabase khi người dùng xác nhận duyệt.", "• Lưu trữ đồng bộ: ")

    # -------------------------------------------------------------------------
    # Chức năng 9: Chức năng chạy lại testcase
    # -------------------------------------------------------------------------
    add_heading_2(doc, "9. Chức năng Chạy lại Testcase bằng AI (AI Revision & Re-run with Feedback)")
    add_body(doc, "Mục đích: Khi bộ testcase do AI tạo ra lần đầu chưa bao quát hết các kịch bản mong muốn hoặc xuất hiện thiếu sót, Tester có thể yêu cầu AI tái sinh hoặc tạo bổ sung kịch bản dựa trên phản hồi nghiệp vụ cụ thể mà không cần chạy lại từ đầu.")
    add_body(doc, "Cơ chế phản hồi và tinh chỉnh AI chuyên sâu:")
    add_bullet(doc, "Tại chân modal duyệt testcase, Tester nhấn nút 'Cần chỉnh sửa & Chạy lại'. Hệ thống sẽ mở rộng phân vùng 'Gợi ý cải thiện testcase' và khung nhập chỉ thị.", "• Mở khung phản hồi: ")
    add_bullet(doc, "Cung cấp các thẻ gợi ý nhanh (Quick Action Tags), Tester chỉ cần bấm vào thẻ để hệ thống tự động điền yêu cầu vào khung nội dung:\n   + '+ Negative case': Yêu cầu bổ sung các ca kiểm thử giá trị âm, dữ liệu sai định dạng.\n   + '+ Boundary': Yêu cầu bổ sung kiểm thử giá trị biên (ký tự rỗng, vượt quá độ dài tối đa...).\n   + '+ Phân quyền': Yêu cầu bổ sung các case kiểm tra quyền truy cập của từng nhóm vai trò.\n   + '+ Lỗi hệ thống': Bổ sung kiểm tra ngoại lệ hệ thống (mất mạng, server timeout, lỗi 500...).\n   + '+ Expected Result': Yêu cầu chuẩn hóa và làm rõ hơn kết quả mong đợi chi tiết.\n   + '+ Loại bỏ trùng lặp': Yêu cầu AI rà soát loại bỏ các kịch bản bị tương đồng ngữ nghĩa.\n   + '+ Viết lại toàn bộ': Yêu cầu AI xóa bộ testcase hiện tại và sinh lại toàn bộ từ đầu.", "• Bộ nút gợi ý cải thiện sẵn có (Quick Tags): ")
    add_bullet(doc, "Tester có thể gõ thêm các yêu cầu nghiệp vụ chuyên biệt, ví dụ:\n   '- TC: Validate thông báo lỗi khi trùng fullName trên màn hình nhập thông tin khách hàng.'\n   '- TC: Kiểm tra không gọi API /api/v1/request-otp/register khi phone chứa ký tự đặc biệt.'\n   '- TC: Kiểm tra không gọi API khi bỏ trống phone và chọn Đăng ký.'", "• Khung nhập 'NỘI DUNG YÊU CẦU AI ĐIỀU CHỈNH': ")
    add_bullet(doc, "Tester bấm nút 'Chạy lại AI' (màu xanh dương). AI Pipeline Service tiếp nhận nội dung điều chỉnh kết hợp với ngữ cảnh tài liệu gốc và bộ nhớ ChromaDB để sinh bổ sung các testcase đạt yêu cầu.", "• Kích hoạt tái sinh: ")

    add_image_box(doc, "2ec14afbaa2b2a75733a.jpg", 
                  "Hình 9.1: Khung Gợi ý cải thiện testcase với các Tag nghiệp vụ, ô nhập chỉ thị và nút 'Chạy lại AI'", 
                  width=Inches(6.0))

    # -------------------------------------------------------------------------
    # Chức năng 10: Màn hình kết quả sau khi xong: File testcase, File tài liệu phân tích
    # -------------------------------------------------------------------------
    add_heading_2(doc, "10. Màn hình Kết quả Sau khi Hoàn thành: File Testcase & File Tài liệu Phân tích")
    add_body(doc, "Mục đích: Tự động xuất bản các sản phẩm bàn giao kiểm thử hoàn chỉnh (Deliverables) lên hệ sinh thái đám mây Google Workspace, phục vụ công tác kiểm thử thực tế và chia sẻ cho toàn bộ đội ngũ phát triển.")

    add_heading_3(doc, "A. File Testcase Kết quả trên Google Sheets")
    add_body(doc, "Khi Tester nhấn nút 'Xác nhận & Giữ [Số lượng] testcase', hệ thống gọi Google Sheets API để ghi nhận toàn bộ kịch bản đã duyệt vào một Sheet riêng mang tên bài toán (ví dụ: [TC] Bài toán HotFix_Dán thẻ):")
    add_bullet(doc, "Phần đầu trang tính chứa bảng tổng hợp Manual Test với các chỉ số: Số trường hợp kiểm thử đạt (P), Số không đạt (F), Đang xem xét (PE), Chưa thực hiện và Tổng số trường hợp kiểm thử (ví dụ: 174).", "• Bảng thống kê kết quả kiểm thử (Summary Box): ")
    add_bullet(doc, "Kịch bản được tổ chức theo cấu trúc chuẩn mực ngành QA gồm các cột:\n   + ID: Mã kịch bản chuẩn hóa ([Tên_TC]_1, [Tên_TC]_2...).\n   + Mục đích kiểm thử: Mô tả rõ ràng hành vi cần kiểm tra.\n   + Các bước thực hiện: Hướng dẫn chi tiết từng bước thao tác (gửi request, kiểm tra tab Network F12...).\n   + Kết quả mong muốn: Phản hồi dự kiến (Response code, mess, checksum...).\n   + Kết quả thực tế (UAT/Prod): Dành cho Tester ghi nhận kết quả thực tế khi chạy test.\n   + Data test các đợt: Theo dõi dữ liệu kiểm thử qua từng vòng chạy (Lần 1, Lần 2, Lần 3...).", "• Bảng chi tiết Kịch bản kiểm thử (Test Scenario Matrix): ")
    add_bullet(doc, "Toàn bộ tiêu đề cột, nhóm chức năng được đổ màu phân cách chuyên nghiệp (vàng nhạt, xanh lơ), định dạng đường viền rõ ràng, sẵn sàng để đội ngũ QA sử dụng trực tiếp.", "• Định dạng thẩm mỹ chuẩn hóa: ")

    add_image_box(doc, "40db9d667db6fde8a4a7.jpg", 
                  "Hình 10.1: File Google Sheets Kịch bản kiểm thử chức năng tự động xuất bản với đầy đủ tiêu chí chuẩn QA", 
                  width=Inches(6.2))

    add_heading_3(doc, "B. File Tài liệu Phân tích Nghiệp vụ trên Google Docs")
    add_body(doc, "Bên cạnh bảng testcase chi tiết, hệ thống tự động sinh ra một file Google Docs tổng hợp tài liệu phân tích nghiệp vụ (ví dụ: 'Tài liệu phân tích Bài toán HotFix_Dán thẻ') do BA Analysis Engine của AutoTC biên soạn:")
    add_bullet(doc, "Phác thảo rõ ràng mục tiêu thiết kế tính năng, đối tượng người dùng thụ hưởng (ví dụ: khách hàng chưa có tài khoản thu phí tự động), phạm vi nghiệp vụ bao quát từ giao diện, hợp đồng, phương tiện đến xác thực OTP.", "• Mục 1 - Mục tiêu tài liệu: ")
    add_bullet(doc, "Đặc tả chi tiết danh sách hệ thống tham gia (Web Customer FE, BE CRM, MinIO Object Storage...) kèm danh mục API liên quan (phương thức POST /api/v1/request-otp/register, POST /api/v1/register, các tham số bắt buộc, mã phản hồi, mã lỗi...).", "• Mục 2 - Các hệ thống và API: ")
    add_bullet(doc, "Mô tả mạch lạc quy trình luồng chuẩn (Happy Path) theo từng bước từ Bước 1 đến Bước 12, cùng các luồng rẽ nhánh và ngoại lệ (Alternative & Exception Flows) khi nhập sai OTP, quá hạn OTP, dữ liệu trùng lặp...", "• Mục 3 - Luồng nghiệp vụ chính: ")

    add_image_box(doc, "f8a2500fb0df308169ce.jpg", 
                  "Hình 10.2: File Google Docs Tài liệu phân tích nghiệp vụ tự động tổng hợp mục tiêu, API và luồng xử lý", 
                  width=Inches(6.2))

    # =========================================================================
    # PHẦN III: BẢNG TỔNG KẾT MA TRẬN HẠ TẦNG VÀ TÍNH NĂNG
    # =========================================================================
    add_heading_1(doc, "PHẦN III: BẢNG TỔNG KẾT MA TRẬN HẠ TẦNG VÀ TÍNH NĂNG")
    add_body(doc, "Bảng dưới đây tổng hợp chi tiết mối liên hệ giữa các phân hệ kỹ thuật, nền tảng công nghệ, vai trò chức năng và các điểm tích hợp trong toàn bộ hệ thống AutoTC:")

    # Matrix Table
    matrix_data = [
        ("Phân hệ Kỹ thuật", "Công nghệ / Nền tảng", "Vai trò trong Hệ thống", "Điểm Tích hợp / Giao diện"),
        ("Giao diện Người dùng", "HTML5, TailwindCSS, Lucide, JS ES6+", "Bảng điều khiển quản lý và điều phối toàn bộ hệ thống, gọi API non-blocking", "index.html, review.html, login.html"),
        ("Máy chủ Dịch vụ", "Python 3.10+ (ThreadingHTTPServer)", "Xử lý CRUD bài toán, điều phối AI pipeline, quản lý phiên và dừng luồng", "RESTful API (/api/tasks, /api/tasks/run, /api/tasks/stop...)"),
        ("AI Pipeline Engine", "Native Python (AiPipelineService)", "Trích xuất tài liệu, phân tích BA, trích xuất yêu cầu và sinh kịch bản testcase", "BE/services/ai_pipeline_service.py"),
        ("Thu thập Tài liệu", "Python DocumentCrawler", "Cào dữ liệu từ Google Docs, Google Sheets, Website và Figma REST API", "BE/services/doc_crawler.py"),
        ("Bộ nhớ Tri thức & RAG", "MemoryService & ChromaDB", "Lưu trữ vector embeddings, đối chiếu testcase lịch sử nhằm loại bỏ trùng lặp", "BE/chroma_db, memory_service.py"),
        ("Mạng & Bảo mật", "Tailscale Mesh VPN + Funnel", "Bảo vệ kết nối nội bộ giữa Backend và Dify, mở cổng HTTPS an toàn", "Domain vdtc-hungdv.tailfb2503.ts.net (Port 8888)"),
        ("Cơ sở Dữ liệu Đám mây", "Supabase Cloud (PostgreSQL)", "Lưu trữ người dùng, phân quyền, trạng thái bài toán và kết quả testcase JSON Realtime", "Supabase Tables: public.problems, public.users"),
        ("Lưu trữ & Xuất bản", "Google Workspace (Drive, Docs, Sheets API)", "Lưu trữ file gốc, tự động tạo Google Sheet testcase và Google Doc phân tích", "Google API Client (OAuth 2.0 / Service Account)"),
        ("Trí tuệ Nhân tạo", "Viettel AI MaaS (DeepSeek-V4.1-Flash)", "Mô hình ngôn ngữ lớn xử lý suy luận nhanh, sinh testcase bám sát nghiệp vụ", "Viettel AI MaaS REST API"),
        ("Trợ lý Chatbot QA", "Dify AI Agent Platform", "Cung cấp trợ lý ảo hỗ trợ giải đáp thắc mắc nghiệp vụ trực tiếp cho Tester", "Side-panel iframe nhúng trên Dashboard"),
        ("Thiết kế Giao diện", "Figma REST API", "Trích xuất wireframe, layout và thuộc tính UI/UX phục vụ sinh testcase màn hình", "Figma Personal Access Token"),
        ("Điều khiển Thực thi", "ThreadPoolExecutor & Cancel Controller", "Quản lý chạy song song nhiều bài toán và ngắt luồng khẩn cấp khi người dùng yêu cầu", "AiPipelineService._cancelled_tasks")
    ]

    tbl = doc.add_table(rows=len(matrix_data), cols=4)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    
    col_widths = [Inches(1.5), Inches(1.8), Inches(2.2), Inches(1.5)]
    
    for r_idx, row in enumerate(tbl.rows):
        data_row = matrix_data[r_idx]
        is_header = (r_idx == 0)
        
        for c_idx, cell in enumerate(row.cells):
            cell.width = col_widths[c_idx]
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(3)
            p.paragraph_format.space_after = Pt(3)
            p.paragraph_format.line_spacing = 1.15
            
            run = p.add_run(data_row[c_idx])
            run.font.name = "Segoe UI"
            run.font.size = Pt(8.5 if not is_header else 9)
            
            if is_header:
                run.bold = True
                run.font.color.rgb = RGBColor(255, 255, 255)
                set_cell_background(cell, "1E3A8A")
                set_cell_margins(cell, top=140, bottom=140, left=140, right=140)
                set_cell_borders(cell, 
                                 top={"val": "single", "sz": "6", "color": "1E3A8A"},
                                 bottom={"val": "single", "sz": "12", "color": "0F172A"},
                                 left={"val": "single", "sz": "4", "color": "3B82F6"},
                                 right={"val": "single", "sz": "4", "color": "3B82F6"})
            else:
                run.font.color.rgb = RGBColor(30, 41, 59)
                bg_color = "F8FAFC" if r_idx % 2 == 1 else "FFFFFF"
                set_cell_background(cell, bg_color)
                set_cell_margins(cell, top=100, bottom=100, left=120, right=120)
                set_cell_borders(cell, 
                                 top={"val": "single", "sz": "4", "color": "E2E8F0"},
                                 bottom={"val": "single", "sz": "4", "color": "E2E8F0"},
                                 left={"val": "single", "sz": "4", "color": "E2E8F0"},
                                 right={"val": "single", "sz": "4", "color": "E2E8F0"})

    # Ending footer note
    p_end = doc.add_paragraph()
    p_end.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_end.paragraph_format.space_before = Pt(20)
    p_end.paragraph_format.space_after = Pt(10)
    r_end = p_end.add_run("--- HẾT TÀI LIỆU ---")
    r_end.bold = True
    r_end.font.name = "Segoe UI"
    r_end.font.size = Pt(10)
    r_end.font.color.rgb = RGBColor(100, 116, 139)

    doc.save(DOCX_OUT)
    print(f"Document generated successfully: {DOCX_OUT}")

if __name__ == "__main__":
    build_document()
