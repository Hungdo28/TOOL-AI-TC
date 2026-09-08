# AutoTC

Mã nguồn được tách thành hai phần:

- `FE`: giao diện quản lý bài toán kiểm thử, kết nối Supabase, n8n và Dify.
- `BE`: backend Python xử lý dữ liệu Google Sheets/Drive.

Các thao tác lấy danh sách, sửa, xóa, chuyển giao và cập nhật trạng thái nằm trong thư mục `BE`. Chức năng thêm tài liệu (URL hoặc file local) và luồng AI tiếp tục chạy bằng n8n để dùng credential Google Drive hiện có. Xem hướng dẫn tại `BE/README.md`.

## Chạy local

1. Chạy nhanh backend bằng cách click đúp vào file `run_backend.bat` ở thư mục gốc (hoặc chạy lệnh `cd BE && py app.py`).
2. Phục vụ thư mục `FE` bằng một web server tĩnh, ví dụ Live Server trong IDE (bấm "Go Live" ở cổng 5500), rồi mở `FE/login.html`. Không mở trực tiếp bằng giao thức `file://` vì một số API trình duyệt và request CORS có thể không hoạt động đúng.

## Tailscale

Chỉ tắt đường dẫn public, vẫn giữ mạng Tailscale nội bộ:

```text
tailscale serve reset
```

Tắt hoàn toàn Tailscale:

```text
tailscale down
```

Bật Tailscale:

```text
tailscale up
```

Public Dify qua cổng 8888:

```text
tailscale funnel --bg 8888
```

Public n8n qua HTTPS 8443, chuyển tiếp tới cổng 1234:

```text
tailscale funnel --bg --https=8443 1234
```

Frontend production: `https://quanlv.io.vn`

## Lưu ý bảo mật

Frontend không thể tự bảo vệ webhook hoặc thay thế phân quyền phía server. Khi triển khai production, cần bật Supabase Auth/RLS và yêu cầu access token hợp lệ tại các webhook n8n.

