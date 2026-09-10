@echo off
title AutoTC Backend Server (Port 3000)

echo ======================================================
echo          KHOI DONG AUTOTC BACKEND SERVER
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
        echo [LOI] Khong tim thay Python tren may cua ban!
        echo Vui long cai dat Python 3.10 tro len.
        echo.
        pause
        exit /b 1
    )
)

if not exist ".env" (
    if exist ".env.example" (
        echo [THONG BAO] Chua co file .env, dang sao chep tu .env.example...
        copy .env.example .env > nul
    ) else (
        echo [CANH BAO] Khong tim thay file .env trong thu muc BE!
    )
)

echo [OK] Dang khoi dong Backend tai http://127.0.0.1:3000 ...
echo [!] Luu y: GIU CUA SO NAY CHAY NGAM trong khi su dung Tool Kiem thu AI.
echo.

%PY_CMD% app.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [LOI] Server bi dung hoac xay ra loi!
    pause
)
