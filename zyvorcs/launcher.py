"""
ZyvoRCS Sender - Launcher
Zyvo Tools | launcher.py

Starts Flask, opens browser, shows tray icon
"""

import sys
import os
import threading
import webbrowser
import time


def resource_path(rel):
    """Works both in dev and PyInstaller .exe"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, rel)
    return os.path.join(os.path.abspath('.'), rel)


def start_flask():
    # Ensure working dir is set correctly for PyInstaller
    if hasattr(sys, '_MEIPASS'):
        os.chdir(os.path.dirname(sys.executable))

    from app import app
    app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)


def open_browser():
    time.sleep(1.8)  # Wait for Flask to start
    webbrowser.open('http://127.0.0.1:5000')


def _make_icon_image():
    """Create Zyvo tray icon — dark navy circle with Z"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        # Navy background circle
        draw.ellipse([2, 2, 62, 62], fill='#1F4E78')
        # Teal border
        draw.ellipse([2, 2, 62, 62], outline='#00C6FF', width=3)
        # Z text
        draw.text((20, 14), 'Z', fill='#00C6FF')
        return img
    except Exception:
        # Fallback: plain colored image
        from PIL import Image
        img = Image.new('RGB', (64, 64), color='#1F4E78')
        return img


def run_tray():
    try:
        import pystray

        icon_image = _make_icon_image()

        def on_open(icon, item):
            webbrowser.open('http://127.0.0.1:5000')

        def on_quit(icon, item):
            icon.stop()
            os._exit(0)

        icon = pystray.Icon(
            name='ZyvoRCS',
            icon=icon_image,
            title='ZyvoRCS Sender',
            menu=pystray.Menu(
                pystray.MenuItem('Open ZyvoRCS', on_open, default=True),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem('Quit', on_quit),
            )
        )
        icon.run()

    except ImportError:
        # pystray not installed — just keep main thread alive
        print('ZyvoRCS running at http://127.0.0.1:5000')
        print('Press Ctrl+C to stop.')
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            os._exit(0)


if __name__ == '__main__':
    # 1. Start Flask in background thread
    flask_t = threading.Thread(target=start_flask, daemon=True)
    flask_t.start()

    # 2. Open browser after short delay
    browser_t = threading.Thread(target=open_browser, daemon=True)
    browser_t.start()

    # 3. Tray icon — blocks main thread (keeps process alive)
    run_tray()
