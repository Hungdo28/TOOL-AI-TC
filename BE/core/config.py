from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


def load_dotenv(path: Path) -> None:
    """Nạp file .env nhỏ gọn mà không cần thêm thư viện python-dotenv."""
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    spreadsheet_id: str
    sheet_name: str
    sheet_id: int
    header_row: int
    credentials_file: str | None
    credentials_json: dict | None
    drive_folder_id: str | None
    drive_share_mode: str
    allowed_origins: tuple[str, ...]
    enforce_role_header: bool
    max_file_size: int
    max_total_file_size: int

    @classmethod
    def from_env(cls) -> "Settings":
        backend_root = Path(__file__).resolve().parents[1]
        load_dotenv(backend_root / ".env")

        raw_credentials = (
            os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
            or os.getenv("GOOGLE_AUTHORIZED_USER_JSON", "").strip()
        )
        credentials_json = json.loads(raw_credentials) if raw_credentials else None
        credentials_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip() or None
        if credentials_file and not Path(credentials_file).is_absolute():
            credentials_file = str((backend_root / credentials_file).resolve())

        origins = tuple(
            origin.strip()
            for origin in os.getenv(
                "ALLOWED_ORIGINS",
                "http://127.0.0.1:5500,http://localhost:5500,https://quanlv.io.vn",
            ).split(",")
            if origin.strip()
        )
        share_mode = os.getenv("GOOGLE_DRIVE_SHARE_MODE", "private").strip().lower()
        if share_mode not in {"private", "anyone"}:
            raise ValueError("GOOGLE_DRIVE_SHARE_MODE chỉ nhận private hoặc anyone")

        spreadsheet_id = os.getenv("GOOGLE_SPREADSHEET_ID", "").strip()
        if not spreadsheet_id:
            raise ValueError("Thiếu GOOGLE_SPREADSHEET_ID trong BE/.env")
        if not credentials_file and not credentials_json:
            raise ValueError(
                "Thiếu GOOGLE_APPLICATION_CREDENTIALS hoặc JSON credential Google trong BE/.env"
            )

        return cls(
            host=os.getenv("HOST", "0.0.0.0"),
            port=int(os.getenv("PORT", "3000")),
            spreadsheet_id=spreadsheet_id,
            sheet_name=os.getenv("GOOGLE_SHEET_NAME", "Trang tính1"),
            sheet_id=int(os.getenv("GOOGLE_SHEET_ID", "0")),
            header_row=max(1, int(os.getenv("GOOGLE_HEADER_ROW", "1"))),
            credentials_file=credentials_file,
            credentials_json=credentials_json,
            drive_folder_id=os.getenv("GOOGLE_DRIVE_FOLDER_ID", "").strip() or None,
            drive_share_mode=share_mode,
            allowed_origins=origins,
            enforce_role_header=env_bool("ENFORCE_ROLE_HEADER", True),
            max_file_size=int(float(os.getenv("MAX_FILE_SIZE_MB", "20")) * 1024 * 1024),
            max_total_file_size=int(float(os.getenv("MAX_TOTAL_FILE_SIZE_MB", "50")) * 1024 * 1024),
        )
