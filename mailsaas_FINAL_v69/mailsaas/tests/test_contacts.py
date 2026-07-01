"""Contacts: lists, the de-duplicated import, statuses and list actions."""
from mailsaas import db as D
from .conftest import csv_rows


def _list_id(app, name):
    with app.app_context():
        return D.query("SELECT id FROM contact_lists WHERE name=?", (name,),
                       one=True)["id"]


def _count(app, lid):
    with app.app_context():
        return D.query("SELECT COUNT(*) c FROM contacts WHERE list_id=?",
                       (lid,), one=True)["c"]


def test_create_list_defaults_to_universal(app, auth):
    auth.post("/contacts", data={"action": "create_list", "name": "MyList"})
    with app.app_context():
        row = D.query("SELECT list_type FROM contact_lists WHERE name='MyList'",
                      one=True)
    assert row and row["list_type"] == "Universal"


def test_import_dedupe_1000_plus_500_equals_1300(app, auth):
    auth.post("/contacts", data={"action": "create_list", "name": "SUP"})
    lid = _list_id(app, "SUP")
    auth.post("/contacts", data={"action": "import", "list_id": str(lid),
                                 "csv": csv_rows("u", 0, 1000)})
    assert _count(app, lid) == 1000
    # 500 more, 200 overlap (800..999), 300 new (1000..1299)
    r = auth.post("/contacts", data={"action": "import", "list_id": str(lid),
                                     "csv": csv_rows("u", 800, 1300)},
                  follow_redirects=True)
    html = r.get_data(as_text=True)
    assert "Imported" in html and "Duplicates Removed" in html
    assert _count(app, lid) == 1300


def test_import_summary_counts_invalid_and_blank(app, auth):
    auth.post("/contacts", data={"action": "create_list", "name": "L"})
    lid = _list_id(app, "L")
    body = "Email,Name\nok@x.com,OK\nbad-email,Nope\n\n\n"
    r = auth.post("/contacts", data={"action": "import", "list_id": str(lid),
                                     "csv": body}, follow_redirects=True)
    h = r.get_data(as_text=True)
    assert "Invalid Emails" in h and "Blank Rows" in h
    assert _count(app, lid) == 1


def test_update_existing_rule(app, auth):
    auth.post("/contacts", data={"action": "create_list", "name": "U"})
    lid = _list_id(app, "U")
    auth.post("/contacts", data={"action": "import", "list_id": str(lid),
                                 "rule": "update",
                                 "csv": "Email,Name,Company\na@x.com,One,Acme"})
    auth.post("/contacts", data={"action": "import", "list_id": str(lid),
                                 "rule": "update",
                                 "csv": "Email,Name,Company\na@x.com,Two,NewCo"})
    with app.app_context():
        row = D.query("SELECT name, company FROM contacts WHERE email='a@x.com'",
                      one=True)
    assert row["name"] == "Two" and row["company"] == "NewCo"
    assert _count(app, lid) == 1


def test_block_contact_sets_blocked_status(app, auth):
    auth.post("/contacts", data={"action": "add", "email": "z@x.com",
                                 "name": "Z", "sel": "all"})
    with app.app_context():
        cid = D.query("SELECT id FROM contacts WHERE email='z@x.com'",
                      one=True)["id"]
    auth.post("/contacts", data={"action": "block_contact", "id": str(cid),
                                 "sel": "all"})
    with app.app_context():
        st = D.query("SELECT status FROM contacts WHERE id=?", (cid,),
                     one=True)["status"]
    assert st == "blocked"


def test_tag_bulk_and_favorite(app, auth):
    auth.post("/contacts", data={"action": "create_list", "name": "T"})
    lid = _list_id(app, "T")
    auth.post("/contacts", data={"action": "add", "email": "t@x.com",
                                 "name": "T", "list_id": str(lid), "sel": "all"})
    with app.app_context():
        cid = D.query("SELECT id FROM contacts WHERE email='t@x.com'",
                      one=True)["id"]
    auth.post("/contacts", data={"action": "tag", "ids": [str(cid)],
                                 "tag_add": "vip", "sel": "all"})
    auth.post("/contacts", data={"action": "fav_list", "id": str(lid),
                                 "sel": "all"})
    with app.app_context():
        tags = D.query("SELECT tags FROM contacts WHERE id=?", (cid,),
                       one=True)["tags"]
        fav = D.query("SELECT favorite FROM contact_lists WHERE id=?", (lid,),
                      one=True)["favorite"]
    assert "vip" in tags
    assert fav == 1


def test_dashboard_views_render(auth):
    for path in ("/contacts", "/contacts?list=all",
                 "/contacts?list=suppression",
                 "/contacts?list=all&status=blocked"):
        assert auth.get(path).status_code == 200
