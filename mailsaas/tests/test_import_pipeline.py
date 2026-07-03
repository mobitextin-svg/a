"""Unit tests for the contact import parser (header mapping + cleaning)."""
from mailsaas.app import _parse_contacts, _normalize_mobile


def test_header_mapping_to_standard_fields():
    rows = [
        ["Email Address", "Full Name", "Phone", "Company Name", "District", "Province"],
        ["  JANE@Acme.com ", "Jane Doe", "+91 98765 43210", "Acme Inc", "Chennai", "TN"],
    ]
    recs, stats = _parse_contacts(rows)
    assert len(recs) == 1
    r = recs[0]
    assert r["email"] == "jane@acme.com"      # trimmed + lowercased
    assert r["name"] == "Jane Doe"
    assert r["mobile"] == "+919876543210"     # normalized
    assert r["company"] == "Acme Inc"
    assert r["city"] == "Chennai"             # District -> City
    assert r["state"] == "TN"                 # Province -> State


def test_invalid_and_blank_rows_are_counted():
    rows = [
        ["Email", "Name"],
        ["good@x.com", "Good"],
        ["not-an-email", "Bad"],
        ["", ""],
    ]
    recs, stats = _parse_contacts(rows)
    assert len(recs) == 1
    assert stats["invalid"] == 1
    assert stats["blanks"] == 1
    assert stats["errors"]                    # the bad row is captured


def test_positional_fallback_without_header():
    rows = [["bob@x.com", "Bob", "12345", "BobCo"]]
    recs, stats = _parse_contacts(rows)
    assert recs[0]["email"] == "bob@x.com"
    assert recs[0]["name"] == "Bob"
    assert recs[0]["company"] == "BobCo"


def test_normalize_mobile():
    assert _normalize_mobile("+91 98765-43210") == "+919876543210"
    assert _normalize_mobile("(044) 1234 5678") == "04412345678"
    assert _normalize_mobile("") == ""
