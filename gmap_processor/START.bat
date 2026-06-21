@echo off
REM ---- Google Maps Extractor Output Formatter ----
cd /d "%~dp0"

echo Checking dependencies...
python -m pip install --quiet --disable-pip-version-check -r requirements.txt

echo Starting GUI...
python gmap_processor.py

pause
