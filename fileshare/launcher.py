import os
import re
import sys
import time
import urllib.request
import subprocess
import threading
from pathlib import Path

BASE = Path(__file__).parent
CF_EXE = BASE / "cloudflared.exe"
CF_LOG = BASE / "cf_tunnel.log"

# Download cloudflared if missing
if not CF_EXE.exists():
    print("Downloading cloudflared.exe...")
    url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
    urllib.request.urlretrieve(url, CF_EXE)
    print("Downloaded.")

# Clear old log (ignore if tunnel process still has it open)
if CF_LOG.exists():
    try:
        CF_LOG.unlink()
    except PermissionError:
        pass

# Start cloudflared
print("\nStarting Cloudflare Tunnel...")
with open(CF_LOG, "w") as log:
    cf_proc = subprocess.Popen(
        [str(CF_EXE), "tunnel", "--url", "http://localhost:5000", "--no-autoupdate"],
        stdout=log,
        stderr=log,
        creationflags=subprocess.CREATE_NO_WINDOW
    )

# Wait for URL
print("Waiting for tunnel URL", end="", flush=True)
tunnel_url = None
for _ in range(30):
    time.sleep(1)
    print(".", end="", flush=True)
    if CF_LOG.exists():
        text = CF_LOG.read_text(errors="ignore")
        m = re.search(r'https://[a-z0-9-]+\.trycloudflare\.com', text)
        if m:
            tunnel_url = m.group()
            break

print()
if tunnel_url:
    print()
    print("=" * 60)
    print("  TUNNEL IS LIVE!")
    print()
    print(f"  Public URL: {tunnel_url}")
    print()
    print("  Share this link with others!")
    print("=" * 60)
else:
    print("WARNING: Could not get tunnel URL.")
    if CF_LOG.exists():
        print("\n--- cf_tunnel.log ---")
        print(CF_LOG.read_text(errors="ignore"))

print()
print("Starting Flask... (Press CTRL+C to stop)")
print()

# Start Flask
flask_proc = subprocess.Popen([sys.executable, str(BASE / "app.py")])

try:
    flask_proc.wait()
except KeyboardInterrupt:
    print("\nStopping...")
    flask_proc.terminate()
    cf_proc.terminate()
