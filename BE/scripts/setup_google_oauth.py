from __future__ import annotations

from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow


BACKEND_ROOT = Path(__file__).resolve().parents[1]
CLIENT_FILE = BACKEND_ROOT / "oauth-client.json"
TOKEN_FILE = BACKEND_ROOT / "authorized-user.json"
ENV_FILE = BACKEND_ROOT / ".env"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]


def update_env() -> None:
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    setting = "GOOGLE_APPLICATION_CREDENTIALS=./authorized-user.json"
    updated = False
    for index, line in enumerate(lines):
        if line.strip().startswith("GOOGLE_APPLICATION_CREDENTIALS="):
            lines[index] = setting
            updated = True
            break
    if not updated:
        lines.append(setting)
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    if not CLIENT_FILE.exists():
        raise SystemExit(
            "Không tìm thấy BE/oauth-client.json. "
            "Hãy tải OAuth Client ID loại Desktop app từ Google Cloud và đặt đúng tên này."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_FILE), SCOPES)
    credentials = flow.run_local_server(
        port=0,
        access_type="offline",
        prompt="consent",
        success_message="Đã cấp quyền cho AutoTC. Bạn có thể đóng cửa sổ này.",
    )
    TOKEN_FILE.write_text(credentials.to_json(), encoding="utf-8")
    update_env()
    print(f"Đã tạo: {TOKEN_FILE}")
    print("Đã cập nhật BE/.env để sử dụng OAuth người dùng.")
    print("Hãy dừng và chạy lại backend: py BE\\app.py")


if __name__ == "__main__":
    main()

