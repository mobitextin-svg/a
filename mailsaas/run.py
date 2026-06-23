"""Convenience launcher so you can run `python run.py` from the mailsaas folder."""
import os
import sys

# Allow running both as `python run.py` and `python -m mailsaas.run`.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mailsaas.app import app  # noqa: E402

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5005))
    print(f"\n  MailSaaS running →  http://127.0.0.1:{port}\n")
    app.run(host="127.0.0.1", port=port, debug=True)
