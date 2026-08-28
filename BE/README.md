# AutoTC Backend

Backend Python cho các chức năng quản lý bài toán: lấy danh sách, sửa, xóa, chuyển giao và cập nhật trạng thái. Frontend mặc định gửi chức năng thêm URL/import file và chạy AI sang n8n để dùng credential Google đã cấu hình tại đó.

Yêu cầu Python 3.10 trở lên.

## Cấu trúc mã nguồn

```text
BE/
├── app.py                         # Khởi tạo dependency và chạy HTTP server
├── router.py                      # Bảng ánh xạ method + URL tới controller
├── controllers/
│   ├── health_controller.py       # API health check
│   └── task_controller.py         # Nhận request quản lý bài toán
├── services/
│   └── task_service.py            # Validation và nghiệp vụ CRUD
├── repositories/
│   └── google_workspace.py        # Đọc/ghi Google Sheets và Drive
├── middleware/
│   └── auth.py                    # Kiểm tra quyền admin
├── web/
│   ├── handler.py                 # HTTP response, CORS và xử lý lỗi
│   ├── request.py                 # Đọc JSON/FormData/upload
│   └── models.py                  # Kiểu ApiResponse
├── core/
│   └── config.py                  # Đọc và kiểm tra biến môi trường
└── tests/                         # Unit test service và router
```

Luồng xử lý: `HTTP handler → Router → Controller → Service → Google repository`.

## Chuẩn bị Google

1. Tạo Google Cloud credential và bật **Google Sheets API** + **Google Drive API**. Backend nhận service account hoặc `authorized_user` JSON có refresh token.
2. Chia sẻ Google Sheet hiện tại cho email của service account với quyền Editor.
3. Nếu dùng service account để import file, nên dùng thư mục trong **Shared Drive**, chia sẻ cho service account và điền `GOOGLE_DRIVE_FOLDER_ID`. Service account thông thường không có quota My Drive.
4. Tải JSON key về `BE/service-account.json`. File này đã được `.gitignore` loại trừ.

### Import file với tài khoản Google cá nhân

Service account không có quota My Drive, vì vậy phần Import File sẽ nhận lỗi `storageQuotaExceeded` nếu không dùng Shared Drive. Với tài khoản Google cá nhân, cấu hình OAuth một lần như sau:

1. Vào **Google Auth Platform → Branding**, cấu hình consent screen. Nếu app ở chế độ External/Testing, thêm chính email của bạn vào **Test users**.
2. Vào **Google Auth Platform → Clients → Create Client**.
3. Chọn **Application type: Desktop app**, tạo và tải JSON.
4. Đổi tên JSON thành `oauth-client.json`, đặt trong thư mục `BE`.
5. Chạy `py BE/scripts/setup_google_oauth.py`, đăng nhập tài khoản sở hữu Drive và chấp nhận quyền.
6. Công cụ sẽ tạo `BE/authorized-user.json` và tự cập nhật `.env`. Khởi động lại bằng `py BE/app.py`.

Các file OAuth đều đã được `.gitignore` loại trừ. Quy trình Desktop OAuth này tuân theo hướng dẫn Python Quickstart của Google Drive.

Sau khi OAuth được cấu hình, luồng Import File hoạt động như sau:

```text
File local → validation/chuẩn hóa → Google Drive import → Google Docs/Sheets → lưu link vào Sheet quản lý
```

- `.doc`, `.docx`, `.txt`, `.pdf` được chuyển thành Google Docs.
- `.xls`, `.xlsx` được chuyển thành Google Sheets.

## Chạy local

```powershell
cd BE
Copy-Item .env.example .env
py -m pip install -r requirements.txt
py app.py
```

Kiểm tra: `GET http://127.0.0.1:3000/api/health`.

## API

| Method | Endpoint | Chức năng |
|---|---|---|
| GET | `/api/tasks` | Lấy danh sách |
| POST | `/api/tasks` | Thêm bài toán bằng `multipart/form-data` |
| PUT | `/api/tasks` | Sửa tên và URL |
| DELETE | `/api/tasks` | Xóa bài toán |
| PATCH | `/api/tasks/status` | Chọn/cập nhật trạng thái |
| PATCH | `/api/tasks/assignee` | Phân chia/chuyển giao bài toán |

Các API thay đổi dữ liệu yêu cầu header `X-User-Role: admin`. Đây chỉ là lớp tương thích với cơ chế đăng nhập hiện tại ở frontend, không phải xác thực an toàn vì header trình duyệt có thể bị giả mạo. Khi public backend ra Internet, nên thay đăng nhập hiện tại bằng Supabase Auth/JWT và xác minh JWT ở backend.

## Lưu ý triển khai

- Không commit `.env` hoặc JSON service account.
- Nếu frontend chạy HTTPS, backend cũng phải được reverse proxy qua HTTPS; cấu hình URL bằng `window.AUTO_TC_API_BASE` trước khi tải `app.js`.
- `GOOGLE_DRIVE_SHARE_MODE=private` an toàn hơn. Dùng `anyone` chỉ khi n8n hoặc người dùng bắt buộc phải đọc file qua link mà không có credential Drive.
