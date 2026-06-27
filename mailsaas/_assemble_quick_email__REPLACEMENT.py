    # ====================================================================== #
    #  REPLACE the existing _assemble_quick_email() in app.py with this one.
    #  Same name, same single argument `f`, same return (one HTML string),
    #  same fields read and same {{merge}}/{{compliance}} tokens — only the
    #  visual shell changes (corporate look) and the harmful "Report Spam"
    #  link is removed.
    # ====================================================================== #
    def _assemble_quick_email(f):
        """Stitch the saved field values into one responsive, client-safe,
        corporate-looking HTML email. Carries merge + compliance tokens so
        send-time fills per-recipient values: {{name}}, {{company}},
        {{unsubscribe_url}}, {{view_in_browser_url}}."""
        import html as _h
        accent = (f.get("accent") or "#1F4E78").strip() or "#1F4E78"
        logo = (f.get("logo") or "").strip()
        hero = (f.get("hero") or "").strip()
        company = _h.escape((f.get("company") or "Your Company").strip() or "Your Company")
        logo_mode = (f.get("logo_mode") or "logo_name").strip()
        preheader = (f.get("preheader") or "").strip()
        body = (f.get("body_html") or "").strip() or "<p>Write your message here.</p>"
        btn_text = (f.get("btn_text") or "").strip()
        btn_url = (f.get("btn_url") or "#").strip() or "#"
        btn_style = (f.get("btn_style") or "filled").strip()
        signoff = (f.get("signoff") or "Regards,<br>The Team").strip()
        address = (f.get("address") or "").strip()
        font = ("-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,"
                "Helvetica,Arial,sans-serif")

        # --- Brand header (filled accent bar, white text) ------------------ #
        name_span = ('<span style="font-size:19px;font-weight:700;color:#ffffff;'
                     'letter-spacing:-.2px;vertical-align:middle">%s</span>' % company)
        img_tag = ('<img src="%s" alt="%s" style="height:34px;vertical-align:middle;'
                   'border:0">' % (logo, company)) if logo else ""
        if logo_mode == "name" or (logo_mode != "logo" and not logo):
            logo_cell = name_span
        elif logo_mode == "logo" and logo:
            logo_cell = img_tag
        elif logo:  # logo_name
            logo_cell = img_tag + '<span style="display:inline-block;width:10px"></span>' + name_span
        else:
            logo_cell = name_span

        # Hidden preheader (inbox preview text) — first thing in the email.
        pre = ('<div style="display:none;max-height:0;overflow:hidden;opacity:0;'
               'color:transparent;height:0;width:0">%s</div>' % _h.escape(preheader)) \
            if preheader else ""

        # Optional full-width banner, optionally clickable.
        hero_url = (f.get("hero_url") or "").strip()
        if hero:
            hero_img = ('<img src="%s" alt="" style="width:100%%;display:block;'
                        'border:0">' % hero)
            if hero_url:
                hero_img = '<a href="%s" style="text-decoration:none">%s</a>' % (
                    hero_url, hero_img)
            hero_row = '<tr><td style="padding:0">%s</td></tr>' % hero_img
        else:
            hero_row = ""

        # Button — four styles.
        button = ""
        if btn_text:
            if btn_style == "outline":
                css = ('background:#ffffff;color:%s;border:2px solid %s;'
                       'padding:13px 40px;border-radius:8px' % (accent, accent))
            elif btn_style == "pill":
                css = 'background:%s;color:#fff;padding:15px 44px;border-radius:999px' % accent
            elif btn_style == "link":
                css = 'color:%s;text-decoration:underline;padding:6px' % accent
            else:  # filled
                css = 'background:%s;color:#fff;padding:15px 44px;border-radius:8px' % accent
            button = (
                '<table width="100%%" cellpadding="0" cellspacing="0" role="presentation">'
                '<tr><td align="center" style="padding:28px 32px 4px">'
                '<a href="%s" style="%s;text-decoration:none;font-family:%s;'
                'font-size:15px;font-weight:700;display:inline-block">%s</a>'
                '</td></tr></table>' % (btn_url, css, font, btn_text))

        # Optional business address (trust + compliance).
        address_block = ""
        if address:
            address_block = ('<td style="color:#8a97ad;font-size:12px;line-height:1.6">'
                             + address.replace("\n", "<br>") + '</td>')
        else:
            address_block = ('<td style="color:#8a97ad;font-size:12px">%s</td>' % company)

        # Social links — clean TEXT links in the accent colour (emoji icons
        # render as broken boxes in Outlook, so we don't use them).
        social = [
            ("Facebook", (f.get("soc_facebook") or "").strip()),
            ("Instagram", (f.get("soc_instagram") or "").strip()),
            ("X", (f.get("soc_twitter") or "").strip()),
            ("LinkedIn", (f.get("soc_linkedin") or "").strip()),
            ("YouTube", (f.get("soc_youtube") or "").strip()),
            ("WhatsApp", (f.get("soc_whatsapp") or "").strip()),
        ]
        social_links = " &nbsp; ".join(
            '<a href="%s" style="color:%s;text-decoration:none;font-weight:600;'
            'font-size:12px">%s</a>' % (url, accent, label)
            for label, url in social if url)
        social_cell = ('<td align="right" valign="top">%s</td>' % social_links) \
            if social_links else "<td></td>"

        return (
            '<table width="100%" cellpadding="0" cellspacing="0" role="presentation" '
            'style="background:#f4f6f9;font-family:' + font + ';margin:0;padding:32px 0">'
            '<tr><td align="center">' + pre +
            '<table width="600" cellpadding="0" cellspacing="0" role="presentation" '
            'style="width:600px;max-width:100%;background:#ffffff;border-radius:12px;'
            'overflow:hidden;box-shadow:0 1px 3px rgba(16,40,80,.08)">'
            # Brand header — filled accent, logo/name left, view-in-browser right.
            '<tr><td style="background:' + accent + ';padding:20px 32px">'
            '<table width="100%" cellpadding="0" cellspacing="0" role="presentation"><tr>'
            '<td align="left" valign="middle">' + logo_cell + '</td>'
            '<td align="right" valign="middle" style="font-size:12px;white-space:nowrap">'
            '<a href="{{view_in_browser_url}}" style="color:#ffffff;opacity:.75;'
            'text-decoration:none">View in browser &rsaquo;</a></td>'
            '</tr></table></td></tr>'
            + hero_row +
            # Body.
            '<tr><td style="padding:28px 32px 0;color:#3a4661;font-size:15px;line-height:1.7">'
            '<p style="margin:0 0 14px">Hi {{name}},</p>' + body + '</td></tr>'
            # Button.
            '<tr><td>' + button + '</td></tr>'
            # Sign-off.
            '<tr><td style="padding:18px 32px 0;color:#3a4661;font-size:14px;line-height:1.6">'
            + signoff + '</td></tr>'
            # Divider.
            '<tr><td style="padding:22px 32px 0">'
            '<div style="border-top:1px solid #e8ecf3;font-size:0;line-height:0">&nbsp;</div></td></tr>'
            # Footer: address left, social right.
            '<tr><td style="padding:16px 32px 6px">'
            '<table width="100%" cellpadding="0" cellspacing="0" role="presentation"><tr>'
            + address_block + social_cell +
            '</tr></table></td></tr>'
            # Legal / compliance line — NO "Report Spam" (it trains filters
            # against you). One-click unsubscribe + a trust line instead.
            '<tr><td style="padding:14px 32px 22px;border-top:1px solid #f0f3f8;'
            'color:#aab4c6;font-size:11px;line-height:1.6;text-align:center">'
            'You\u2019re receiving this because you opted in to updates from ' + company + '.<br>'
            '<a href="{{unsubscribe_url}}" style="color:#8a97ad">Unsubscribe</a> '
            '&middot; <a href="{{view_in_browser_url}}" style="color:#8a97ad">View in browser</a>'
            '</td></tr>'
            '</table>'
            '<div style="color:#b9c2d2;font-size:11px;padding:14px 0 0;font-family:' + font + '">'
            'Sent securely via ' + company + '</div>'
            '</td></tr></table>')
