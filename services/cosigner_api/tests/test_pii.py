"""PII redactor tests."""

from __future__ import annotations

from services.cosigner_api.app.pii import redact
from services.cosigner_api.app.pii.presidio_redactor import redact_dict


def test_credit_card_redacted() -> None:
    r = redact("Card 4111 1111 1111 1111 ok?")
    assert "4111" not in r.redacted
    assert "[CREDIT_CARD]" in r.redacted
    assert "CREDIT_CARD" in r.findings


def test_ssn_redacted() -> None:
    r = redact("SSN 123-45-6789 here")
    assert "123-45-6789" not in r.redacted
    assert "US_SSN" in r.findings


def test_email_redacted() -> None:
    r = redact("ping me at alice@example.com")
    assert "alice@example.com" not in r.redacted


def test_phone_redacted() -> None:
    r = redact("call 415-555-1234 back")
    assert "415-555-1234" not in r.redacted


def test_redact_dict_recursive() -> None:
    out = redact_dict(
        {"note": "card 4111 1111 1111 1111", "items": [{"email": "a@b.co"}], "n": 5}
    )
    assert "[CREDIT_CARD]" in out["note"]
    assert "[EMAIL_ADDRESS]" in out["items"][0]["email"]
    assert out["n"] == 5


def test_idempotent() -> None:
    once = redact("alice@example.com").redacted
    twice = redact(once).redacted
    assert once == twice


def test_clean_string_unchanged() -> None:
    r = redact("nothing sensitive here")
    assert r.redacted == "nothing sensitive here"
    assert r.findings == []


def test_empty_string() -> None:
    r = redact("")
    assert r.redacted == ""
