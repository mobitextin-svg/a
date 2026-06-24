"""Pure-logic engine tests (no app/DB needed)."""
from mailsaas import verify, rotation as ROT, deliver_ai as DAI, totp, sending as SEND


# --------------------------- verification --------------------------------- #

def test_verify_valid_and_invalid():
    assert verify.verify_email("good@gmail.com")["result"] == "valid"
    assert verify.verify_email("not-an-email")["result"] == "invalid"


def test_verify_disposable_and_role_are_risky():
    assert verify.verify_email("info@mailinator.com")["result"] == "risky"
    r = verify.verify_email("typo@gmial.com")
    assert r["suggestion"] == "gmail.com"


def test_verify_has_risk_and_confidence():
    r = verify.verify_email("sarah@gmail.com")
    assert 0 <= r["risk_score"] <= 100 and "score" in r


# ----------------------------- rotation ----------------------------------- #

def _node(i, purpose="normal", health="Healthy", warmup="Completed", limit=10000,
          sent=0, busy=0, ip=95):
    return {"id": i, "name": f"R{i}", "ip": f"10.0.0.{i}", "purpose": purpose,
            "busy": busy, "healthy": health in ("Healthy", "Warming"), "ip_score": ip,
            "warmup_ok": warmup == "Completed", "daily_limit": limit, "sent_today": sent,
            "bounce_rate": {"Healthy": 0.01, "Warming": 0.03}.get(health, 0.08)}


def test_sending_skips_unwarmed_and_caps_to_plan():
    nodes = [_node(1), _node(2, warmup="Day 5"), _node(3, health="Down")]
    p = ROT.plan_sending(15000, nodes, plan_daily_limit=12000)
    names = {n["name"] for n, _ in p["assigned"]}
    assert "R1" in names and "R2" not in names and "R3" not in names
    assert p["capped"] and p["assigned_total"] <= 12000


def test_verification_ignores_warmup():
    nodes = [_node(1), _node(2, warmup="Day 5")]
    names = {n["name"] for n, _ in ROT.plan_verification(5000, nodes)["assigned"]}
    assert {"R1", "R2"} <= names  # warm-up irrelevant for verification


def test_burst_excludes_normal_and_busy_ips():
    reserved = [_node(10, "burst", limit=50000), _node(11, "burst", busy=1),
                _node(1, "normal")]
    p = ROT.plan_burst(40000, reserved, batch_limit=5000)
    names = {n["name"] for n, _ in p["assigned"]}
    assert names == {"R10"} and p["ok"]


# ------------------------- deliverability AI ------------------------------ #

def test_predict_high_and_low():
    good = DAI.predict_deliverability({"reputation": 94, "bounce_rate": 0.5,
                                       "complaint_rate": 0.02, "auth_ok": True})
    bad = DAI.predict_deliverability({"reputation": 60, "bounce_rate": 9,
                                      "complaint_rate": 0.6, "auth_ok": False,
                                      "blacklisted": True})
    assert good["score"] >= 85 and bad["score"] < good["score"]


def test_recommendations_prioritise_critical():
    recs = DAI.recommendations({"blacklisted": True, "auth_ok": False})
    assert recs[0]["severity"] == "critical"


# --------------------------- AI predictions ------------------------------- #

def test_ai_bounce_prediction():
    from mailsaas import ai
    assert ai.predict_bounce("typo@gmial.com")["band"] in ("High", "Medium")
    assert ai.predict_bounce("real@gmail.com")["band"] == "Low"


def test_ai_subject_optimizer():
    from mailsaas import ai
    bad = ai.optimize_subject("FREE!!! WIN BIG NOW")
    good = ai.optimize_subject("Your weekly product update")
    assert bad["score"] < good["score"] and bad["tips"]


# ------------------------------ TOTP -------------------------------------- #

def test_totp_roundtrip():
    s = totp.new_secret()
    assert totp.verify(s, totp.totp_now(s))
    assert not totp.verify(s, "000000")


# ----------------------------- rendering ---------------------------------- #

def test_render_wraps_links_and_adds_pixel():
    html = SEND.render_html('Hi {{name}} <a href="https://x.com">go</a>',
                            {"email": "a@b.com", "name": "Ann"}, "http://h", "TK")
    assert "Hi Ann" in html and "/t/c/TK?u=" in html and "/t/o/TK.gif" in html
    assert "/t/u/TK" in html  # unsubscribe footer
