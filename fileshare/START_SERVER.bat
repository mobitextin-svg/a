@echo off
setlocal enabledelayedexpansion
title FileShare Server
echo =======================================
echo   FileShare - Starting...
echo =======================================
echo.
cd /d "%~dp0"

python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python.
    pause & exit /b 1
)

if not exist "%~dp0app.py" (
    echo ERROR: app.py not found.
    pause & exit /b 1
)

REM [0/3] Install all required packages
echo [0/3] Installing required packages...
python -m pip install flask bcrypt filelock flask-limiter pyotp "qrcode[pil]" --quiet
if errorlevel 1 (
    echo ERROR: pip install failed. Check your internet connection.
    pause & exit /b 1
)
echo     Packages OK.
echo.

REM Verify app.py syntax
echo     Checking app.py for errors...
python -c "import py_compile; py_compile.compile('app.py', doraise=True)" >nul 2>&1
if errorlevel 1 (
    echo ERROR: app.py has a syntax error:
    python app.py
    pause & exit /b 1
)
echo     app.py OK.
echo.

REM Kill leftovers
taskkill /im cloudflared.exe /f >nul 2>&1
taskkill /fi "WindowTitle eq CF_TUNNEL" /f >nul 2>&1
taskkill /fi "WindowTitle eq FLASK_APP" /f >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5000') do taskkill /pid %%a /f >nul 2>&1
timeout /t 2 /nobreak >nul

if exist cloudflare_log.txt del /f /q cloudflare_log.txt
if exist current_tunnel_url.txt del /f /q current_tunnel_url.txt
if exist flask_error.log del /f /q flask_error.log

REM [1/3] Start Flask
echo [1/3] Starting Flask Server...
start "FLASK_APP" /min cmd /c "python "%~dp0app.py" > "%~dp0flask_error.log" 2>&1"

echo     Waiting for Flask to be ready...
set FLASK_READY=0
for /L %%i in (1,1,30) do (
    if !FLASK_READY!==0 (
        timeout /t 1 /nobreak >nul
        python -c "import socket,sys; s=socket.socket(); s.settimeout(1); r=s.connect_ex(('127.0.0.1',5000)); s.close(); sys.exit(0 if r==0 else 1)" >nul 2>&1
        if !errorlevel!==0 set FLASK_READY=1
    )
)

if !FLASK_READY!==0 (
    echo.
    echo ERROR: Flask did not start on port 5000 within 30 seconds.
    echo.
    echo === Flask error log ===
    if exist "%~dp0flask_error.log" (
        type "%~dp0flask_error.log"
    ) else (
        echo No log file found.
    )
    echo =======================
    pause & exit /b 1
)
echo     Flask is ready.

REM [2/3] Start Cloudflare Tunnel
echo [2/3] Starting Cloudflare Tunnel...
where cloudflared >nul 2>&1
if errorlevel 1 (
    if exist "%~dp0cloudflared.exe" (
        start "CF_TUNNEL" /min "%~dp0cloudflared.exe" tunnel --url http://localhost:5000 --protocol http2 --logfile cloudflare_log.txt
    ) else (
        echo WARNING: cloudflared not found. Running local only.
        start "" "http://localhost:5000"
        goto :showurl
    )
) else (
    start "CF_TUNNEL" /min cloudflared tunnel --url http://localhost:5000 --protocol http2 --logfile cloudflare_log.txt
)

REM [3/3] Wait for tunnel URL
echo [3/3] Waiting 45 seconds for tunnel DNS to go live...
for /L %%i in (1,1,45) do (
    set /a remaining=45-%%i+1
    echo     !remaining! seconds remaining...
    timeout /t 1 /nobreak >nul
)
echo     Done. Detecting URL...
python _detect_url.py

:showurl
echo.
echo =========================================
python _show_url.py
echo =========================================
echo.
echo   Opening browser...
python -c "import webbrowser; url=open('current_tunnel_url.txt').read().strip(); webbrowser.open(url)" >nul 2>&1
echo.
echo   Press CTRL+C or close this window to stop everything.
echo.

:waitloop
timeout /t 5 /nobreak >nul
goto :waitloop

:cleanup
echo.
echo Stopping all services...
taskkill /fi "WindowTitle eq FLASK_APP" /f >nul 2>&1
taskkill /fi "WindowTitle eq CF_TUNNEL" /f >nul 2>&1
taskkill /im cloudflared.exe /f >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5000') do taskkill /pid %%a /f >nul 2>&1
if exist cloudflare_log.txt del /f /q cloudflare_log.txt
if exist current_tunnel_url.txt del /f /q current_tunnel_url.txt
echo Done.
pause
