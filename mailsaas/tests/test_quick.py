"""Tests for the Quick Email form-builder, AI fill, import, and the system gate."""


def _personal_templates(query):
    return query("SELECT * FROM templates ORDER BY id")


def test_quick_get_renders(user):
    r = user.get("/templates/quick")
    assert r.status_code == 200
    assert b"Create Email Template" in r.data


def test_quick_save_personal(user, query):
    r = user.post("/templates/quick", data={
        "action": "save", "name": "BPCL Offer", "subject": "2,000 bonus points",
        "logo": "https://x.com/logo.png", "accent": "#3b4edb",
        "body_html": "<p>Start your <b>BPCL SBI Card</b> today.</p>",
        "btn_text": "View Offer >>", "btn_url": "https://x.com/offer",
        "signoff": "Regards, Team", "folder": "General",
    }, follow_redirects=True)
    assert r.status_code == 200
    rows = query("SELECT * FROM templates WHERE name='BPCL Offer'")
    assert len(rows) == 1
    t = rows[0]
    assert t["name"] == "BPCL Offer"
    assert t["subject"] == "2,000 bonus points"
    # Assembled HTML carries the compliance + merge tokens for send-time fill.
    assert "{{name}}" in t["content"]
    assert "{{unsubscribe_url}}" in t["content"]
    assert "{{view_in_browser_url}}" in t["content"]
    assert "View Offer &gt;&gt;" in t["content"] or "View Offer >>" in t["content"]
    assert "https://x.com/offer" in t["content"]
    # Field values round-trip so re-edit reopens the form, not raw HTML.
    assert t["fields_json"] and "BPCL SBI Card" in t["fields_json"]


def test_quick_reedit_loads_fields(user, query):
    user.post("/templates/quick", data={
        "action": "save", "name": "Reopen me",
        "body_html": "<p>Hello there friend</p>", "folder": "General",
    }, follow_redirects=True)
    tid = query("SELECT id FROM templates WHERE name='Reopen me'")[0]["id"]
    # The form should pre-fill the saved body when editing.
    r = user.get(f"/templates/quick?edit={tid}")
    assert r.status_code == 200
    assert b"Hello there friend" in r.data


def test_quick_ai_fill_no_save(user, query):
    r = user.post("/templates/quick", data={
        "action": "ai", "name": "Draft", "ai_topic": "a school admission email",
        "tone": "friendly", "folder": "General",
    })
    assert r.status_code == 200
    # AI path re-renders the form and must NOT persist a row yet.
    assert query("SELECT * FROM templates WHERE name='Draft'") == []
    assert b"<p>" in r.data  # generated body landed in the editor


def test_import_html(user, query):
    r = user.post("/templates", data={
        "action": "import", "tab": "mine", "name": "Pasted email",
        "folder": "General", "subject": "Hi",
        "content": "<table><tr><td>Hello</td></tr></table>",
    }, follow_redirects=True)
    assert r.status_code == 200
    rows = query("SELECT * FROM templates WHERE name='Pasted email'")
    assert len(rows) == 1
    assert "Hello" in rows[0]["content"]


def test_quick_system_requires_admin(user):
    # Regular user cannot save to the shared system library.
    assert user.get("/templates/quick?target=system").status_code == 403
    assert user.post("/templates/quick", data={
        "target": "system", "action": "save", "name": "x", "folder": "General",
    }).status_code == 403


def test_quick_system_admin_publishes(admin, query):
    r = admin.post("/templates/quick?target=system", data={
        "target": "system", "action": "save", "name": "Finance Promo",
        "subject": "Card offer", "category": "Finance", "published": "on",
        "body_html": "<p>Apply now</p>", "btn_text": "Apply", "btn_url": "#",
    }, follow_redirects=True)
    assert r.status_code == 200
    rows = query("SELECT * FROM system_templates WHERE name='Finance Promo'")
    assert len(rows) == 1
    assert rows[0]["category"] == "Finance"
    assert rows[0]["published"] == 1
    assert "{{unsubscribe_url}}" in rows[0]["content"]
    assert rows[0]["fields_json"]


def test_image_upload_returns_url(user):
    import io
    png = (b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)  # minimal bytes; ext drives validation
    r = user.post("/upload/image", data={
        "file": (io.BytesIO(png), "logo.png"),
    }, content_type="multipart/form-data")
    assert r.status_code == 200
    body = r.get_json()
    assert body["url"].startswith("/static/uploads/")
    assert body["url"].endswith(".png")


def test_image_upload_rejects_bad_type(user):
    import io
    r = user.post("/upload/image", data={
        "file": (io.BytesIO(b"#!/bin/sh"), "evil.sh"),
    }, content_type="multipart/form-data")
    assert r.status_code == 400


def test_quick_save_includes_header_image(user, query):
    user.post("/templates/quick", data={
        "action": "save", "name": "With hero",
        "hero": "/static/uploads/1/banner.png",
        "body_html": "<p>Body</p>", "folder": "General",
    }, follow_redirects=True)
    t = query("SELECT * FROM templates WHERE name='With hero'")[0]
    assert "/static/uploads/1/banner.png" in t["content"]
    assert "banner.png" in (t["fields_json"] or "")


def test_ai_fills_all_fields(user):
    r = user.post("/templates/quick", data={
        "action": "ai", "name": "Untitled", "ai_topic": "school admission open 2026",
        "tone": "friendly",
    })
    assert r.status_code == 200
    # Body + a button + subject should now be present in the re-rendered form.
    assert b"<p>" in r.data or b"<ul>" in r.data
    assert b"value=\"School Admission" in r.data or b"admission" in r.data.lower()


def test_button_style_and_address_saved(user, query):
    user.post("/templates/quick", data={
        "action": "save", "name": "Styled", "body_html": "<p>Hi</p>",
        "btn_text": "Apply", "btn_url": "https://x.com", "btn_style": "pill",
        "address": "Zyvo Tools, Chennai", "folder": "General",
    }, follow_redirects=True)
    t = query("SELECT * FROM templates WHERE name='Styled'")[0]
    assert "border-radius:999px" in t["content"]          # pill style rendered
    assert "Zyvo Tools, Chennai" in t["content"]          # address block rendered
    assert "pill" in (t["fields_json"] or "")


def test_generate_banner_image(user):
    r = user.post("/templates/generate-image", data={
        "kind": "banner", "accent": "#1F4E78", "company": "Zyvo",
        "headline": "Big Offer",
    })
    assert r.status_code == 200
    assert r.get_json()["url"].endswith(".png")


def test_generate_logo_image(user):
    r = user.post("/templates/generate-image", data={
        "kind": "logo", "accent": "#1F4E78", "company": "Zyvo Tools",
    })
    assert r.status_code == 200
    assert r.get_json()["url"].endswith(".png")


def test_variables_resolve_with_fallback():
    """Send-time merge fills known fields and uses fallbacks when blank."""
    from mailsaas import sending
    body = ("Hi {{name}}, from {{company}} in {{city | your area}}. "
            "State: {{state}}.")
    contact = {"name": "Mari", "email": "m@x.com", "company": "CC Reality",
               "city": "", "state": "Tamil Nadu"}
    out = sending.render_html(body, contact, "http://h", "tok123")
    assert "Hi Mari" in out
    assert "CC Reality" in out
    assert "your area" in out          # city blank → fallback used
    assert "Tamil Nadu" in out
    assert "{{" not in out.split("<img")[0]  # all tags resolved in the body


def test_preheader_and_logo_modes_and_accent(user, query):
    user.post("/templates/quick", data={
        "action": "save", "name": "Polished",
        "preheader": "Apply before 27 Jun for {{city | your area}}",
        "logo_mode": "name", "company": "Zyvo Tools",
        "accent": "#1F4E78", "body_html": "<p>Hi</p>", "folder": "General",
    }, follow_redirects=True)
    t = query("SELECT * FROM templates WHERE name='Polished'")[0]
    c = t["content"]
    # Hidden preheader present near the top, before the visible header.
    assert "Apply before 27 Jun" in c
    assert "display:none" in c.split("View in browser")[0]
    # Company-name-only header (no <img>), name shown.
    assert "Zyvo Tools" in c
    # Accent bar + themed button color applied.
    assert "#1F4E78" in c
    assert "height:4px;background:#1F4E78" in c


def test_logo_name_mode_renders_image_and_name(user, query):
    user.post("/templates/quick", data={
        "action": "save", "name": "WithLogo", "logo_mode": "logo_name",
        "logo": "/static/uploads/1/l.png", "company": "CC Reality",
        "body_html": "<p>x</p>", "folder": "General",
    }, follow_redirects=True)
    c = query("SELECT content FROM templates WHERE name='WithLogo'")[0]["content"]
    assert "/static/uploads/1/l.png" in c   # image shown
    assert "CC Reality" in c                # name beside it


def test_ai_generates_preheader(user):
    r = user.post("/templates/quick", data={
        "action": "ai", "name": "Untitled", "ai_topic": "diwali festival offer",
        "tone": "friendly",
    })
    assert r.status_code == 200
    assert b'name="preheader"' in r.data
