"""Convenience launcher so you can run `python run.py` from the mailsaas folder."""
import os
import sys

# Allow running both as `python run.py` and `python -m mailsaas.run`.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mailsaas.app import app  # noqa: E402

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5005))
    # Debug (Werkzeug reloader + interactive console) is OFF by default — the
    # console is a remote-code-execution risk if ever exposed. Opt in for local
    # development with MAILSAAS_DEBUG=1.
    debug = os.environ.get("MAILSAAS_DEBUG") == "1"
    print(f"\n  MailSaaS running →  http://127.0.0.1:{port}"
          f"  (debug={'on' if debug else 'off'})\n")
    app.run(host="127.0.0.1", port=port, debug=debug, threaded=True)
