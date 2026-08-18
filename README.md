# FE AutoTC

Frontend quản lý bài toán kiểm thử, kết nối Supabase, n8n và Dify.

## Chạy local

Phục vụ thư mục bằng một web server tĩnh, ví dụ Live Server, rồi mở `login.html`. Không mở trực tiếp bằng giao thức `file://` vì một số API trình duyệt và request CORS có thể không hoạt động đúng.

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

