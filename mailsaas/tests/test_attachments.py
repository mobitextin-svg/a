"""Campaign attachments: validation, limits, linking and message assembly."""
import io
import os

import pytest

from mailsaas import db as D
import mailsaas.sending as SEND


@pytest.fixture
def attach_dir(app, monkeypatch, tmp_path):
    """Redirect attachment storage to a throwaway directory."""
    d = tmp_path / "attachments"
    d.mkdir()
    monkeypatch.setattr("mailsaas.app.ATTACH_DIR", str(d))
    return str(d)


def _upload(auth, token, name, data, **extra):
    payload = {"token": token, "file": (io.BytesIO(data), name)}
    payload.update(extra)
    return auth.post("/campaigns/attachments/upload", data=payload,
                     content_type="multipart/form-data")


def test_upload_valid_pdf(auth, attach_dir):
    r = _upload(auth, "tok", "Offer.pdf", b"%PDF-1.4 data")
    j = r.get_json()
    assert r.status_code == 200 and j["name"] == "Offer.pdf"
    assert os.listdir(attach_dir)               # a file landed on disk


def test_executable_is_rejected(auth, attach_dir):
    r = _upload(auth, "tok", "virus.exe", b"MZ")
    assert r.status_code == 400
    assert "not supported" in r.get_json()["error"].lower()


def test_oversize_file_rejected(auth, attach_dir):
    r = _upload(auth, "tok", "big.pdf", b"x" * (10 * 1024 * 1024 + 1))
    assert r.status_code == 400
    assert "10 MB" in r.get_json()["error"]


def test_total_size_cap(auth, attach_dir):
    nine_mb = b"x" * (9 * 1024 * 1024)
    assert _upload(auth, "t", "a.pdf", nine_mb).status_code == 200
    assert _upload(auth, "t", "b.pdf", nine_mb).status_code == 200
    r = _upload(auth, "t", "c.pdf", nine_mb)    # 27 MB total > 25 MB
    assert r.status_code == 400
    assert "25 MB" in r.get_json()["error"]


def test_link_to_campaign_and_send_builds_multipart(app, auth, attach_dir):
    _upload(auth, "wiztok", "Spec.pdf", b"%PDF data")
    auth.post("/campaigns/new", data={
        "name": "AttCamp", "subject": "Hi",
        "body": "<p>hi {{unsubscribe_url}}</p>", "rcpt_mode": "all",
        "decision": "draft", "attach_token": "wiztok"},
        follow_redirects=True)
    with app.app_context():
        cid = D.query("SELECT id FROM campaigns WHERE name='AttCamp'",
                      one=True)["id"]
        atts = [{"path": os.path.join(attach_dir, a["stored"]),
                 "filename": a["filename"], "mime": a["mime"]}
                for a in D.query("SELECT * FROM campaign_attachments"
                                 " WHERE campaign_id=?", (cid,))]
    assert len(atts) == 1
    msg = SEND.build_message({}, "to@x.com", "Hi", "<p>hi</p>", attachments=atts)
    assert msg.get_content_type() == "multipart/mixed"
    assert [p.get_filename() for p in msg.iter_attachments()] == ["Spec.pdf"]


def test_manage_existing_campaign_and_download_delete(app, auth, attach_dir):
    auth.post("/campaigns/new", data={
        "name": "Draft1", "subject": "S", "body": "<p>x {{unsubscribe_url}}</p>",
        "rcpt_mode": "all", "decision": "draft"}, follow_redirects=True)
    with app.app_context():
        cid = D.query("SELECT id FROM campaigns WHERE name='Draft1'",
                      one=True)["id"]
    assert auth.get(f"/campaigns/{cid}/attachments").status_code == 200
    r = _upload(auth, "", "Doc.pdf", b"%PDF", campaign_id=str(cid))
    attid = r.get_json()["id"]
    assert auth.get(f"/campaigns/attachments/{attid}").status_code == 200
    assert auth.post("/campaigns/attachments/delete",
                     data={"id": str(attid)}).get_json()["ok"] is True
    with app.app_context():
        left = D.query("SELECT COUNT(*) c FROM campaign_attachments"
                       " WHERE campaign_id=?", (cid,), one=True)["c"]
    assert left == 0
