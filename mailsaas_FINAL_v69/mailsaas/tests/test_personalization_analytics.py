"""Dynamic Personalization (merge tags + preview) and Live Analytics."""
from mailsaas import db as D
from mailsaas import sending as SEND
from mailsaas import analytics as A


# --------------------------------------------------------------------------- #
#  Merge-tag rendering — the new fields
# --------------------------------------------------------------------------- #
def test_render_resolves_new_personalization_fields():
    c = {"name": "Neo", "email": "neo@x.com", "city": "Chennai",
         "country": "India", "balance": "₹500", "last_purchase": "2026-06-01"}
    subj = SEND.render_subject("Hi {{name}} from {{city}}, {{country}}", c)
    assert subj == "Hi Neo from Chennai, India"
    html = SEND.render_html("<p>Bal {{balance}}, last {{last_purchase}}</p>",
                            c, "http://h", "tok")
    assert "₹500" in html and "2026-06-01" in html


def test_render_fallback_syntax():
    assert SEND.render_subject("{{city|your area}}", {"email": "a@b.com"}) \
        == "your area"


# --------------------------------------------------------------------------- #
#  Contact stores the new fields; edit round-trips them
# --------------------------------------------------------------------------- #
def test_contact_add_saves_new_fields(app, auth):
    auth.post("/contacts", data={"action": "add", "email": "p@example.com",
                                 "name": "P", "country": "India",
                                 "balance": "₹99", "last_purchase": "2026-05-05"})
    with app.app_context():
        row = D.query("SELECT country, balance, last_purchase FROM contacts"
                      " WHERE email='p@example.com'", one=True)
    assert row["country"] == "India"
    assert row["balance"] == "₹99"
    assert row["last_purchase"] == "2026-05-05"


# --------------------------------------------------------------------------- #
#  Personalization Preview cycles real recipients
# --------------------------------------------------------------------------- #
def test_personalize_preview_steps_through_recipients(app, auth):
    auth.post("/contacts", data={"action": "add", "email": "aa@example.com",
                                 "name": "Aaa", "city": "Chennai"})
    auth.post("/contacts", data={"action": "add", "email": "bb@example.com",
                                 "name": "Bbb", "city": "Delhi"})
    r0 = auth.post("/campaigns/personalize-preview",
                   data={"subject": "Hi {{name}}",
                         "body": "<p>{{name}} in {{city}}</p>", "index": "0"})
    j0 = r0.get_json()
    assert j0["total"] >= 2
    r1 = auth.post("/campaigns/personalize-preview",
                   data={"subject": "Hi {{name}}",
                         "body": "<p>{{name}}</p>", "index": "1"})
    j1 = r1.get_json()
    assert j1["index"] == 1
    assert j0["name"] != j1["name"] or j0["email"] != j1["email"]
    # subject actually personalised (no raw tag left)
    assert "{{" not in j0["subject"]


# --------------------------------------------------------------------------- #
#  Analytics breakdowns are exact + deterministic
# --------------------------------------------------------------------------- #
def test_breakdowns_sum_to_opens_and_100pct():
    for opens in (0, 1, 37, 1000):
        for split in (A.device_split(opens, 3), A.client_split(opens, 3),
                      A.geo_split(opens, 3)):
            assert sum(r["value"] for r in split) == opens
            assert sum(r["pct"] for r in split) == 100


def test_breakdowns_deterministic():
    assert A.device_split(500, 9) == A.device_split(500, 9)
    assert A.client_split(500, 9) == A.client_split(500, 9)


def test_hourly_uses_real_timestamps_then_derives():
    real = A.hourly(["2026-07-01 09:15:00", "2026-07-01 09:40:00",
                     "2026-07-01 12:00:00"], 3, 1)
    assert {"hour": "9 AM", "opens": 2} in real
    derived = A.hourly([], 100, 1)
    assert sum(h["opens"] for h in derived) == 100
    assert A.hourly([], 0, 1) == []


# --------------------------------------------------------------------------- #
#  Live Analytics routes
# --------------------------------------------------------------------------- #
def test_live_analytics_page_and_json(app, auth):
    auth.post("/campaigns", data={"action": "create_send", "name": "LA",
                                  "subject": "Hi", "body": "<p>Hi</p>",
                                  "list_id": ""})
    with app.app_context():
        cid = D.query("SELECT id FROM campaigns WHERE name='LA'",
                      one=True)["id"]
    assert auth.get(f"/campaigns/{cid}/live").status_code == 200
    j = auth.get(f"/campaigns/{cid}/live.json").get_json()
    assert j["sent"] == j["delivered"] + j["bounces"]
    assert len(j["devices"]) == 3 and len(j["clients"]) == 5
    assert "hourly" in j and "geo" in j


# --------------------------------------------------------------------------- #
#  Custom variables — define, store, resolve, import
# --------------------------------------------------------------------------- #
def test_custom_field_add_store_and_render(app, auth):
    from mailsaas import sending as S
    auth.post("/contacts", data={"action": "add_field", "label": "Postal Pincode"})
    auth.post("/contacts", data={"action": "add_field", "label": "DIN Number"})
    auth.post("/contacts", data={"action": "add", "email": "cv@example.com",
                                 "name": "CV", "cf_postal_pincode": "600001",
                                 "cf_din_number": "DIN123"})
    with app.app_context():
        row = D.query("SELECT custom_json FROM contacts WHERE email='cv@example.com'",
                      one=True)
    contact = {"email": "cv@example.com", "name": "CV",
               "custom_json": row["custom_json"]}
    assert S.render_subject("{{postal_pincode}}/{{din_number}}", contact) \
        == "600001/DIN123"
    html = S.render_html("<p>{{postal_pincode}}</p>", contact, "http://h", "t")
    assert "600001" in html


def test_custom_field_shows_in_template_builder(auth):
    auth.post("/contacts", data={"action": "add_field", "label": "Loyalty Tier"})
    html = auth.get("/templates?tab=mine").get_data(as_text=True)
    assert "Loyalty Tier" in html


def test_custom_field_csv_import(app, auth):
    auth.post("/contacts", data={"action": "add_field", "label": "Postal Pincode"})
    csv = "Email,Name,Postal Pincode\nimp@example.com,Imp,560002\n"
    auth.post("/contacts", data={"action": "import", "list_id": "", "csv": csv})
    with app.app_context():
        row = D.query("SELECT custom_json FROM contacts WHERE email='imp@example.com'",
                      one=True)
    assert row and '"postal_pincode": "560002"' in row["custom_json"]


def test_custom_field_never_shadows_builtin():
    from mailsaas import sending as S
    # A custom field literally named 'name' must not override the real name.
    contact = {"email": "x@y.com", "name": "Real",
               "custom": {"name": "Spoofed"}}
    assert S.render_subject("{{name}}", contact) == "Real"


def test_custom_fields_capped_at_five(app, auth):
    for i in range(7):
        auth.post("/contacts", data={"action": "add_field", "label": f"F{i}"})
    with app.app_context():
        n = D.query("SELECT COUNT(*) c FROM contact_fields WHERE account_id=1",
                    one=True)["c"]
    assert n == 5
    html = auth.get("/contacts?list=all").get_data(as_text=True)
    assert "5 / 5 used" in html
