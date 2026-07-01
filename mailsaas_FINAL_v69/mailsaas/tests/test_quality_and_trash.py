"""Email Quality Check (template + campaign) and contact Trash (soft delete)."""
from mailsaas import db as D


def _add_contact(auth, email, name="X"):
    auth.post("/contacts", data={"action": "add", "email": email, "name": name})


def _cid(app, email):
    with app.app_context():
        return D.query("SELECT id, status FROM contacts WHERE email=?", (email,),
                       one=True)


# --------------------------------------------------------------------------- #
#  Contact Trash — soft delete → restore → permanent delete
# --------------------------------------------------------------------------- #
def test_delete_contact_moves_to_trash_not_gone(app, auth):
    _add_contact(auth, "trash1@example.com")
    row = _cid(app, "trash1@example.com")
    auth.post("/contacts", data={"action": "delete", "id": str(row["id"])})
    after = _cid(app, "trash1@example.com")
    assert after is not None, "soft delete must keep the row"
    assert after["status"] == "trashed"


def test_trashed_contact_excluded_from_all_view_and_counts(app, auth):
    _add_contact(auth, "keep@example.com")
    _add_contact(auth, "gone@example.com")
    gone = _cid(app, "gone@example.com")
    auth.post("/contacts", data={"action": "delete", "id": str(gone["id"])})
    html = auth.get("/contacts?list=all").get_data(as_text=True)
    assert "keep@example.com" in html
    assert "gone@example.com" not in html
    # And it shows in the Trash view.
    trash = auth.get("/contacts?list=trash").get_data(as_text=True)
    assert "gone@example.com" in trash


def test_restore_brings_contact_back_active(app, auth):
    _add_contact(auth, "restore@example.com")
    row = _cid(app, "restore@example.com")
    auth.post("/contacts", data={"action": "delete", "id": str(row["id"])})
    auth.post("/contacts", data={"action": "restore", "id": str(row["id"])})
    after = _cid(app, "restore@example.com")
    assert after["status"] == "active"


def test_purge_permanently_deletes_only_from_trash(app, auth):
    _add_contact(auth, "purge@example.com")
    row = _cid(app, "purge@example.com")
    # purge before trashing must NOT delete an active contact
    auth.post("/contacts", data={"action": "purge", "id": str(row["id"])})
    assert _cid(app, "purge@example.com") is not None
    # trash then purge → gone for good
    auth.post("/contacts", data={"action": "delete", "id": str(row["id"])})
    auth.post("/contacts", data={"action": "purge", "id": str(row["id"])})
    assert _cid(app, "purge@example.com") is None


def test_trashed_contact_not_counted_as_active_recipient(app, auth):
    _add_contact(auth, "rcpt@example.com")
    row = _cid(app, "rcpt@example.com")
    auth.post("/contacts", data={"action": "delete", "id": str(row["id"])})
    with app.app_context():
        n = D.query("SELECT COUNT(*) c FROM contacts WHERE status='active'"
                    " AND email='rcpt@example.com'", one=True)["c"]
    assert n == 0


# --------------------------------------------------------------------------- #
#  Template Email Quality Check
# --------------------------------------------------------------------------- #
def test_template_quality_check_flags_spam(app, auth):
    r = auth.post("/templates/quality-check",
                  data={"subject": "FREE CASH WINNER!!!",
                        "content": "<p>Buy now, act now, 100% free cash</p>"})
    j = r.get_json()
    assert j["spam_count"] >= 1
    assert j["spam_level"] in ("Medium", "High")
    assert j["score"] < 100


def test_template_auto_optimize_improves_score(app, auth):
    subj = "FREE!!!"
    body = "<p>Buy now — free cash, click here</p>"
    r = auth.post("/templates/auto-optimize",
                  data={"subject": subj, "content": body,
                        "preview_text": "free winner"})
    j = r.get_json()
    assert j["after"] >= j["before"]
    assert "unsubscribe" in j["content"].lower()


# --------------------------------------------------------------------------- #
#  Campaign Email Quality Check (wizard step 6)
# --------------------------------------------------------------------------- #
def test_campaign_analyze_returns_auth_and_checks(app, auth):
    r = auth.post("/campaigns/analyze",
                  data={"subject": "Hello {{name}}",
                        "content": "<p>Hi</p>", "body": "<p>Hi {{name}}</p>"})
    j = r.get_json()
    assert isinstance(j["auth"], list) and len(j["auth"]) == 3
    labels = {a["label"] for a in j["auth"]}
    assert labels == {"SPF", "DKIM", "DMARC"}
    assert any(c["label"] == "Personalization" for c in j["checks"])
    assert "spam_level" in j
