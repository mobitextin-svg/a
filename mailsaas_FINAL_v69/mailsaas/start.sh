#!/usr/bin/env bash
# Launch MailSaaS locally.
set -e
cd "$(dirname "$0")"
python3 -m pip install -r requirements.txt
exec python3 run.py
