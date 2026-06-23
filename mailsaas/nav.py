"""
The full product information architecture for the platform.

Defining it once, declaratively, lets us:
  * render a consistent sidebar everywhere
  * auto-generate landing pages for modules that aren't deeply built yet
  * keep the sitemap from the product brief as the single source of truth

Each top-level module has:
    key   - url slug / identifier
    label - sidebar text
    icon  - emoji glyph (keeps it dependency-free)
    items - list of (label, description) sub-features
    built - True if it has a bespoke functional view; False -> generic page
"""

NAV = [
    {
        "key": "dashboard", "label": "Dashboard", "icon": "📊", "built": True,
        "items": [
            ("Overview", "High-level health of your account"),
            ("Recent Activity", "Latest events across the workspace"),
            ("Quick Actions", "Jump straight into common tasks"),
            ("Usage Statistics", "Credits, sends and verifications used"),
        ],
    },
    {
        "key": "verification", "label": "Email Verification", "icon": "✅", "built": True,
        "items": [
            ("Single Verification", "Check one address in real time"),
            ("Bulk Verification", "Paste or upload thousands at once"),
            ("Verification History", "Every check you've run"),
            ("Catch-all Detection", "Flag accept-all domains"),
            ("SMTP Validation", "Mailbox-level reachability"),
            ("Disposable Email Detection", "Block throwaway domains"),
            ("Role Email Detection", "Spot info@/support@ addresses"),
            ("Syntax Validation", "RFC-compliant format checks"),
            ("MX Record Check", "Confirm the domain can receive mail"),
            ("Export Results", "Download as CSV"),
            ("Webhook", "Push results to your endpoint"),
        ],
    },
    {
        "key": "sender", "label": "Bulk Email Sender", "icon": "📤", "built": True,
        "items": [
            ("Compose Email", "Rich composer with personalization"),
            ("Templates", "Reusable, branded layouts"),
            ("Schedule Campaign", "Send at the perfect time"),
            ("A/B Testing", "Test subjects and content"),
            ("Personalization", "Merge tags and dynamic blocks"),
            ("Attachments", "Add files to your sends"),
            ("Inbox Test", "Preview placement before sending"),
            ("Warm-up Status", "Track sender reputation ramp"),
            ("Delivery Queue", "Live view of what's sending"),
        ],
    },
    {
        "key": "contacts", "label": "Contacts", "icon": "👥", "built": True,
        "items": [
            ("Contact Lists", "Organise your audience"),
            ("Import CSV/Excel", "Bring contacts in"),
            ("Export", "Take your data out"),
            ("Segments", "Dynamic, rule-based groups"),
            ("Tags", "Label and filter contacts"),
            ("Duplicate Removal", "Keep lists clean"),
            ("Suppression List", "Never-contact addresses"),
            ("Unsubscribed Contacts", "Honoured opt-outs"),
        ],
    },
    {
        "key": "campaigns", "label": "Campaigns", "icon": "🚀", "built": True,
        "items": [
            ("Draft", "Work in progress"),
            ("Scheduled", "Queued to send"),
            ("Running", "Currently sending"),
            ("Completed", "Finished campaigns"),
            ("Failed", "Needs attention"),
            ("Clone Campaign", "Duplicate and tweak"),
            ("Campaign Reports", "Per-campaign analytics"),
        ],
    },
    {
        "key": "smtp", "label": "SMTP Servers", "icon": "🖧", "built": True,
        "items": [
            ("Add SMTP", "Connect a relay"),
            ("Dedicated IP", "Isolated sending IPs"),
            ("SMTP Rotation", "Spread load across relays"),
            ("Health Monitor", "Live deliverability signals"),
            ("Warm-up", "Gradually build reputation"),
            ("Sending Limits", "Throttle per server"),
        ],
    },
    {
        "key": "domains", "label": "Domains", "icon": "🌐", "built": True,
        "items": [
            ("Add Domain", "Authenticate a sending domain"),
            ("SPF", "Sender Policy Framework"),
            ("DKIM", "Cryptographic signing"),
            ("DMARC", "Alignment & reporting policy"),
            ("DNS Verification", "Confirm records are live"),
            ("Domain Reputation", "Track your standing"),
        ],
    },
    {
        "key": "reports", "label": "Reports", "icon": "📈", "built": True,
        "items": [
            ("Delivery", "Delivered vs attempted"),
            ("Opens", "Engagement by open"),
            ("Clicks", "Link engagement"),
            ("Bounce", "Hard & soft bounces"),
            ("Complaints", "Spam reports"),
            ("Unsubscribes", "Opt-out trends"),
            ("Geo Reports", "Where your audience is"),
            ("Device Reports", "Desktop vs mobile"),
        ],
    },
    {
        "key": "api", "label": "API", "icon": "🔌", "built": True,
        "items": [
            ("API Keys", "Create and revoke keys"),
            ("API Documentation", "Endpoints & examples"),
            ("Usage Logs", "Every API call"),
            ("Webhooks", "Event subscriptions"),
            ("SDKs", "Official client libraries"),
        ],
    },
    {
        "key": "billing", "label": "Billing", "icon": "💳", "built": True,
        "items": [
            ("Plans", "Compare and upgrade"),
            ("Credits", "Top up verification credits"),
            ("Invoices", "Download receipts"),
            ("Payment Methods", "Cards on file"),
            ("Transactions", "Billing history"),
            ("Usage", "Metered consumption"),
        ],
    },
    {
        "key": "team", "label": "Team", "icon": "🧑‍🤝‍🧑", "built": True,
        "items": [
            ("Users", "Invite and manage members"),
            ("Roles", "Owner, Admin, Member, Viewer"),
            ("Permissions", "Fine-grained access"),
            ("Activity Log", "Who did what, when"),
        ],
    },
    {
        "key": "integrations", "label": "Integrations", "icon": "🧩", "built": False,
        "items": [
            ("CRM", "Salesforce, HubSpot, Pipedrive"),
            ("Webhooks", "Real-time event delivery"),
            ("Zapier", "5,000+ app connections"),
            ("WordPress", "Plugin for forms & lists"),
            ("Shopify", "Sync customers & orders"),
            ("Custom API", "Build your own"),
        ],
    },
    {
        "key": "automation", "label": "Automation", "icon": "⚙️", "built": False,
        "items": [
            ("Auto Verify", "Verify on contact creation"),
            ("Auto Clean Lists", "Scheduled list hygiene"),
            ("Scheduled Verification", "Recurring bulk checks"),
            ("Scheduled Campaigns", "Set-and-forget sends"),
            ("Rules Engine", "If-this-then-that workflows"),
        ],
    },
    {
        "key": "notifications", "label": "Notifications", "icon": "🔔", "built": False,
        "items": [
            ("Email Alerts", "Important events by email"),
            ("SMS Alerts", "Critical alerts by text"),
            ("Push Notifications", "Browser & mobile push"),
            ("System Status", "Platform health"),
        ],
    },
    {
        "key": "enterprise", "label": "Enterprise Modules", "icon": "🏢", "built": True,
        "items": [
            ("SMTP Pool Manager", "Manage relay pools at scale"),
            ("Dedicated IP Rotation", "Rotate IPs intelligently"),
            ("Domain Warm-up", "Automated reputation ramp"),
            ("Email Queue Manager", "Backpressure & retries"),
            ("Bounce Processor", "Classify & act on bounces"),
            ("Feedback Loop Processing", "Ingest ISP FBL data"),
            ("Suppression Lists", "Global never-send registry"),
            ("Blacklist Monitoring", "RBL/DNSBL watch"),
            ("Inbox Placement Testing", "Seed-list placement"),
            ("AI Deliverability Optimization", "ML send-time & content"),
            ("Real-time Analytics", "Streaming event metrics"),
            ("Event Webhooks", "At-least-once delivery"),
            ("White-label Support", "Your brand, our engine"),
            ("Multi-tenant Architecture", "Isolated tenant data"),
            ("Multi-region Deployment", "Data residency by region"),
        ],
    },
    {
        "key": "support", "label": "Support", "icon": "🛟", "built": False,
        "items": [
            ("Help Center", "Guides & how-tos"),
            ("Tickets", "Track your requests"),
            ("Live Chat", "Talk to us"),
            ("Documentation", "Full reference"),
            ("FAQ", "Quick answers"),
        ],
    },
    {
        "key": "settings", "label": "Settings", "icon": "🛠️", "built": True,
        "items": [
            ("Profile", "Your details"),
            ("Security", "Password & sessions"),
            ("2FA", "Two-factor authentication"),
            ("Branding", "Logo & colours"),
            ("Time Zone", "Localise timestamps"),
            ("Audit Logs", "Security event trail"),
        ],
    },
]

# Quick lookup by key.
NAV_BY_KEY = {m["key"]: m for m in NAV}
