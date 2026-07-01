@echo off
REM Launch MailSaaS locally on Windows.
cd /d "%~dp0"
python -m pip install -r requirements.txt
python run.py
