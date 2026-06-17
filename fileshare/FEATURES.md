# FileShare — Feature Notes

A Flask file-sharing app with secure, expiring download links, device-locking,
2FA, SMTP password recovery and a Cloudflare-tunnel launcher.

## Newly added

1. **File Analytics** — per-link dashboard at `/admin/analytics/<token>`.
   Tracks **Total Views**, **Total Downloads**, **Unique Visitors**,
   **Conversion %**, plus breakdowns by **Country**, **Browser**, **Device**
   and **OS**, with a recent-activity log. Country uses the Cloudflare
   `CF-IPCountry` header; user-agent is parsed locally (no external service).
   Events are recorded on the download page (view) and on file streaming
   (download), and stored in `analytics.json`.

2. **QR Codes** — every link gets a scannable QR (`/qr/<token>.png`,
   add `?dl=1` to download). Surfaced in the admin link row (📱 QR modal),
   the analytics page, and the recipient download page.

5. **Folder Sharing** — tick *"Share as browsable folder"* when uploading
   multiple files. Instead of one ZIP, recipients browse the files online
   (`/download/<token>/view`), with an image grid and per-file view/download.
   Individual files are served via `/download/<token>/file?p=<relpath>`
   (path-traversal guarded).

6–9. **Inline Viewers** — `/download/<token>/view` renders the right viewer
   by file type: **image gallery** (prev/next/zoom/slideshow/keyboard),
   **PDF** (in-browser iframe), **video** (HTML5 player with seek/fullscreen
   and optional `.vtt` subtitles in folders), and **audio** (streaming
   player). Files are served inline and Range-aware via `/download/<token>/raw`.

10. **Link Branding** — replace `/download/<random>` with a custom slug like
   `/invoice` or `/product-demo` (🏷 Link modal in the admin row →
   `/admin/set-slug/<token>`). Slugs are validated and reserved words are
   blocked. Mappings live in `slugs.json`.

## Already present (kept as-is)

3. **Drag & Drop Upload** — drop zone in the admin upload card.
4. **Upload Queue** — chunked, parallel uploads with pause/resume/cancel and
   resume-after-refresh.

## Run

```
pip install flask bcrypt filelock flask-limiter pyotp "qrcode[pil]"
python app.py            # http://localhost:5000
# or: python launcher.py / START_SERVER.bat  (adds a Cloudflare tunnel)
```
