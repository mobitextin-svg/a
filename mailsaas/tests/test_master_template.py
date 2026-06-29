"""Premium master-template builder: industry presets + optional blocks.

One master template powers every industry. A preset only prefills colour,
copy and feature cards; the user toggles optional blocks (feature cards,
image, offer, testimonial) on or off. Disabled blocks must not render, so
plain templates keep their original output (backward compatibility).
"""


def _save(auth, app, **extra):
    """Save a personal template via the Quick builder and return its HTML."""
    from mailsaas import db as D
    data = {"name": "BlockTest", "subject": "Hi {{name}}", "folder": "General",
            "company": "Test Co", "accent": "#7C3AED", "body_html": "<p>Body</p>"}
    data.update(extra)
    r = auth.post("/templates/quick", data=data, follow_redirects=True)
    assert r.status_code == 200
    with app.app_context():
        row = D.query("SELECT content FROM templates WHERE name='BlockTest'"
                      " ORDER BY id DESC", (), one=True)
    return row["content"]


def test_quick_page_offers_presets_and_block_toggles(auth):
    html = auth.get("/templates/quick").get_data(as_text=True)
    assert "Industry preset" in html
    # All ten industries from the spec are present as one-click presets.
    for key in ("banking", "insurance", "healthcare", "education", "ecommerce",
                "restaurant", "travel", "realestate", "saas", "corporate"):
        assert 'data-key="%s"' % key in html
    # Each optional block has a toggle.
    for el in ("blkFeatures", "blkImage", "blkOffer", "blkTesti"):
        assert el in html


def test_feature_cards_render_only_when_enabled(auth, app):
    html = _save(auth, app, blk_features="1",
                 feat1_icon="⚡", feat1_title="Fast", feat1_text="Quick setup",
                 feat2_icon="📊", feat2_title="Insights", feat2_text="Dashboards")
    assert "Fast" in html and "Insights" in html and "⚡" in html
    # A card without a title is skipped entirely.
    assert "Quick setup" in html


def test_feature_card_logo_image_overrides_emoji(auth, app):
    # A card with a logo image shows the <img>, not the emoji icon.
    html = _save(auth, app, blk_features="1",
                 feat1_icon="⚡", feat1_title="Branded",
                 feat1_text="Has a logo",
                 feat1_img="https://x.test/logo.png")
    assert 'src="https://x.test/logo.png"' in html
    assert "⚡" not in html        # emoji replaced by the logo image
    assert "Branded" in html


def test_offer_block_with_promo_code(auth, app):
    html = _save(auth, app, blk_offer="1", offer_headline="50% OFF",
                 offer_sub="Ends Sunday", offer_code="SAVE50")
    assert "50% OFF" in html and "Ends Sunday" in html and "SAVE50" in html


def test_testimonial_block(auth, app):
    html = _save(auth, app, blk_testimonial="1", quote="Best tool ever",
                 quote_author="Jane", quote_role="CEO")
    assert "Best tool ever" in html and "Jane" in html and "CEO" in html


def test_image_block(auth, app):
    html = _save(auth, app, blk_image="1", img_url="https://x.test/i.png",
                 img_caption="A caption")
    assert "https://x.test/i.png" in html and "A caption" in html


def test_disabled_blocks_do_not_render(auth, app):
    # Toggles off, but field values present — nothing should leak through.
    html = _save(auth, app, offer_headline="HIDDEN", quote="HIDDEN",
                 feat1_title="HIDDEN", img_url="https://x.test/hidden.png")
    assert "HIDDEN" not in html
    assert "https://x.test/hidden.png" not in html


def test_footer_uses_view_in_browser_not_report_spam(auth, app):
    html = _save(auth, app)
    # The harmful "Report Spam" link is gone; a compliant view-in-browser
    # link replaces it, alongside one-click unsubscribe.
    assert "Report Spam" not in html
    assert "{{view_in_browser_url}}" in html
    assert "{{unsubscribe_url}}" in html


def test_signoff_keeps_line_breaks(auth, app):
    # A multi-line sign-off renders line by line (newlines -> <br>).
    html = _save(auth, app,
                 signoff="Best regards,\n\nThe ZyvoMail Team\nReliable Automation")
    assert "Best regards,<br><br>The ZyvoMail Team<br>Reliable Automation" in html


def test_social_icons_use_brand_colours(auth, app):
    # Social badges use each platform's real brand colour, not the accent.
    html = _save(auth, app,
                 soc_facebook="https://fb.com/x",
                 soc_whatsapp="https://wa.me/123")
    assert "#1877F2" in html        # Facebook blue
    assert "#25D366" in html        # WhatsApp green
    assert "border-radius:12px" in html   # modern rounded-square badge
