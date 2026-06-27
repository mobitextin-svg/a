"""
Payments — Razorpay (India) integration + UPI / bank-transfer helpers.

Goes live the moment these env vars are set (use Razorpay **Test Mode** keys —
free, no real charge):

    RAZORPAY_KEY_ID       rzp_test_xxxxxxxx
    RAZORPAY_KEY_SECRET   xxxxxxxxxxxxxxxx
    UPI_VPA               yourname@okhdfcbank      (for the scannable UPI QR)
    UPI_NAME              Your Business
    BANK_NAME / BANK_ACC / BANK_IFSC                (for manual bank transfer)

Without keys the checkout falls back to a test confirmation so the flow is
still demonstrable. Razorpay Checkout natively offers UPI, UPI-QR, cards,
net-banking and wallets — so one integration covers all Indian methods.
"""
import os
import json
import hmac
import base64
import hashlib
import urllib.request
from urllib.parse import quote


def razorpay_configured():
    return bool(os.environ.get("RAZORPAY_KEY_ID")
                and os.environ.get("RAZORPAY_KEY_SECRET"))


def key_id():
    return os.environ.get("RAZORPAY_KEY_ID", "")


def create_order(amount_inr, receipt):
    """Create a Razorpay order (amount in paise). Returns the order dict.
    Raises on failure so the caller can fall back to test mode."""
    secret = os.environ["RAZORPAY_KEY_SECRET"]
    payload = json.dumps({
        "amount": int(round(amount_inr * 100)),   # paise
        "currency": "INR",
        "receipt": receipt,
        "payment_capture": 1,
    }).encode()
    auth = base64.b64encode(f"{key_id()}:{secret}".encode()).decode()
    req = urllib.request.Request(
        "https://api.razorpay.com/v1/orders", data=payload,
        headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def verify_signature(order_id, payment_id, signature):
    """Verify the Razorpay Checkout callback signature (HMAC-SHA256)."""
    secret = os.environ.get("RAZORPAY_KEY_SECRET", "")
    if not (secret and order_id and payment_id and signature):
        return False
    expected = hmac.new(secret.encode(), f"{order_id}|{payment_id}".encode(),
                        hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def upi_link(amount, note="MailSaaS burst pack"):
    """Build a UPI deep-link that any UPI app (or a QR scan) can pay."""
    vpa = os.environ.get("UPI_VPA", "merchant@upi")
    name = os.environ.get("UPI_NAME", "MailSaaS")
    return (f"upi://pay?pa={quote(vpa)}&pn={quote(name)}&am={amount}"
            f"&cu=INR&tn={quote(note)}")


def upi_details():
    return {"vpa": os.environ.get("UPI_VPA", "merchant@upi"),
            "name": os.environ.get("UPI_NAME", "MailSaaS")}


def bank_details():
    return {
        "bank": os.environ.get("BANK_NAME", "HDFC Bank (sample)"),
        "account": os.environ.get("BANK_ACC", "50100XXXXXX1234"),
        "ifsc": os.environ.get("BANK_IFSC", "HDFC0000123"),
        "name": os.environ.get("UPI_NAME", "MailSaaS"),
    }
