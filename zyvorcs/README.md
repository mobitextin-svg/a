# ZyvoRCS Sender v1.0
**Zyvo Tools** | Web-based bulk RCS sender via ADB + Google Messages

---

## Stack
- **Backend** — Flask + Python threading
- **Frontend** — Vanilla HTML/JS (dark navy + teal theme)
- **ADB Engine** — subprocess + UIAutomator2 (Google Messages intent)
- **Report** — openpyxl Excel (.xlsx)
- **Tray** — pystray

---

## Setup (Dev)

```bash
pip install -r requirements.txt
python launcher.py
```

Browser opens at `http://127.0.0.1:5000` automatically.

---

## Setup (Production .exe)

1. Install Python 3.10+
2. Put `adb.exe` in the project folder
3. Run `build.bat`
4. Output: `dist\ZyvoRCS.exe`

---

## Phone Setup (Android 11+)

1. Enable Developer Options
2. Enable **Wireless Debugging**
3. Note the IP address shown on screen
4. Tap **Pair device with QR code**
5. In ZyvoRCS → **Devices** → **Pair New Device**
6. Scan QR with webcam → enter IP → Pair

---

## Usage Flow

```
1. Devices    → Pair + connect Android phone
2. Contacts   → Upload .xlsx → Map columns
3. Templates  → Write message with {name} {city} etc.
4. Send       → Select device + delay → Start Send
5. Report     → Download Excel report
```

---

## Custom Buttons

Reusable one-tap snippets for the message box. In the **Templates** tab,
each custom button has a **label** and the **text** it inserts:

- **Add**    — fill Label + Inserted Text → *Add Button*
- **Update** — click ✎ on a button → edit → *Update Button*
- **Delete** — click ✕ on a button → confirm

Click a button's label to insert its text into the message at the cursor.
Buttons appear under both the **Templates** editor and the **Send**
message box, and persist in `data/buttons.json`.

Backend API: `GET/POST /buttons`, `DELETE /buttons/<id>`.

---

## Excel Format

Your contacts `.xlsx` should have columns like:

| Name  | Mobile     | City    | State      | Company  |
|-------|------------|---------|------------|----------|
| Rahul | 9876543210 | Chennai | Tamil Nadu | ABC Corp |

Column names are flexible — you map them in the app.

---

## Template Variables

| Variable    | Description        |
|-------------|--------------------|
| `{name}`    | Contact name       |
| `{mobile}`  | Mobile number      |
| `{city}`    | City               |
| `{state}`   | State              |
| `{company}` | Company name       |

---

## Files

```
zyvorcs/
├── app.py           ← Flask server + all routes
├── adb_engine.py    ← ADB send logic + watchdog + report
├── launcher.py      ← Entry point (tray + browser)
├── requirements.txt
├── ZyvoRCS.spec     ← PyInstaller config
├── build.bat        ← One-click build
├── templates/
│   └── index.html   ← Full UI
├── data/
│   └── templates.json   ← Saved templates (auto-created)
├── uploads/             ← Excel contacts (auto-created)
└── reports/             ← Generated reports (auto-created)
```

---

## ADB Notes

- Requires Android 11+ for wireless QR pairing
- ADB must be on system PATH or bundled as `adb.exe`
- Google Messages must be default SMS app on phone
- Keep phone screen unlocked during bulk send for best results

---

## Known Limitations (v1.0)

- No RCS delivery confirmation without root access
- Long messages may get split into SMS if RCS handshake fails
- UIAutomator element IDs may need update if Google Messages updates

---

*Zyvo Tools — Built for Indian market bulk messaging*
