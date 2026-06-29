@echo off
REM ============================================================
REM  MailSaaS - one-click start for Windows
REM  Double-click this file, or run it from cmd.
REM ============================================================
setlocal
cd /d "%~dp0"

echo.
echo   ==============================================
echo     MailSaaS - starting up...
echo   ==============================================
echo.

REM Pick a Python launcher (py -> python -> python3)
set "PY="
where py >nul 2>nul && set "PY=py"
if not defined PY ( where python  >nul 2>nul && set "PY=python" )
if not defined PY ( where python3 >nul 2>nul && set "PY=python3" )

if not defined PY (
  echo   [ERROR] Python was not found.
  echo   Install Python 3.8+ from https://python.org/downloads
  echo   and tick "Add Python to PATH" during setup.
  echo.
  pause
  exit /b 1
)

echo   Using Python: %PY%
echo   Installing dependencies (first run only)...
%PY% -m pip install -r requirements.txt

if not defined PORT set "PORT=5005"
echo.
echo   Opening http://127.0.0.1:%PORT% in your browser...
start "" "http://127.0.0.1:%PORT%"

echo   Starting server (press Ctrl+C to stop)...
echo.
%PY% run.py

pause
