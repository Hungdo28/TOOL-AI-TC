@echo off
chcp 65001 > nul
title AutoTC Backend Server (Port 3000)

echo ======================================================
echo          KHỞI ĐỘNG AUTOTC BACKEND SERVER
echo ======================================================
echo.

cd /d "%~dp0BE"

where py >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set PY_CMD=py
) else (
    where python >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        set PY_CMD=python
    ) else (
        echo [LỖI] Không tìm thấy Python trên máy của bạn!
        echo Vui lòng cài đặt Python 3.10 trở lên.
        echo.
        pause
        exit /b 1
    )
)

if not exist ".env" (
    if exist ".env.example" (
        echo [THÔNG BÁO] Chưa có file .env, đang sao chép từ .env.example...
        copy .env.example .env > nul
    ) else (
        echo [CẢNH BÁO] Không tìm thấy file .env trong thư mục BE!
    )
)

echo [✓] Đang khởi động Backend tại http://127.0.0.1:3000 ...
echo [!] Lưu ý: GIỮ CỬA SỔ NÀY CHẠY NGẦM trong khi sử dụng Tool Kiểm thử AI.
echo.

%PY_CMD% app.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [LỖI] Server bị dừng hoặc xảy ra lỗi!
    pause
)
