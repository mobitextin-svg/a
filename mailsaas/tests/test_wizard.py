"""Campaign wizard: 7-step order, select-only template, working submission."""
import re

from mailsaas import db as D


def test_step_order_is_template_before_recipients(auth):
    html = auth.get("/campaigns/new").get_data(as_text=True)
    heads = re.findall(r"<h2[^>]*>([①-⑦][^<]*)", html)
    labels = [h.strip().split(" ", 1)[1] if " " in h else h for h in heads[:3]]
    assert labels[0].startswith("Campaign Details")
    assert "Email Template" in heads[1]
    assert "Recipients" in heads[2]


def test_template_step_is_select_only(auth):
    html = auth.get("/campaigns/new").get_data(as_text=True)
    # body is a hidden field (set by template selection), not an editable area,
    # and the inline visual builder link is gone.
    assert 'name="body"' in html
    assert "Open Visual Builder" not in html
    assert "tpl-preview-frame" in html        # preview of the chosen template


def test_campaign_submits_with_subject_and_body(app, auth):
    auth.post("/campaigns/new", data={
        "name": "FlowTest", "subject": "Hello", "preview_text": "Peek",
        "body": "<h1>Hi {{name}}</h1>", "rcpt_mode": "all", "decision": "draft"},
        follow_redirects=True)
    with app.app_context():
        row = D.query("SELECT subject, preview_text, body FROM campaigns"
                      " WHERE name='FlowTest'", one=True)
    assert row["subject"] == "Hello"
    assert row["preview_text"] == "Peek"
    assert "{{name}}" in row["body"]
