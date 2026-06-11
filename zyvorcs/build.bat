@echo off
echo ============================================
echo  ZyvoRCS Sender - Build Script
echo  Zyvo Tools
echo ============================================
echo.

echo [1/3] Installing dependencies...
pip install -r requirements.txt
pip install pyinstaller

echo.
echo [2/3] Building .exe with PyInstaller...
pyinstaller ZyvoRCS.spec --clean --noconfirm

echo.
echo [3/3] Done!
echo Output: dist\ZyvoRCS.exe
echo.

pause
