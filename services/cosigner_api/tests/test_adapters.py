"""Stripe + Salesforce cosign adapter unit tests."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from decimal import Decimal

import pytest

from services.cosigner_api.app.adapters import (
    InvalidSignature,
    ReplayWindowExceeded,
    SalesforceAdapter,
    StripeAdapter,
)

# --- Stripe -----------------------------------------------------------------

STRIPE_SECRET = "whsec_test"


def _stripe_sign(body: bytes, ts: int | None = None) -> dict[str, str]:
    ts = ts or int(time.time())
    signed = f"{ts}.{body.decode()}".encode()
    v1 = hmac.new(STRIPE_SECRET.encode(), signed, hashlib.sha256).hexdigest()
    return {"Stripe-Signature": f"t={ts},v1={v1}"}


def test_stripe_signature_round_trip() -> None:
    body = json.dumps({"id": "evt_1"}).encode()
    headers = _stripe_sign(body)
    StripeAdapter().verify_signature(
        {k.lower(): v for k, v in headers.items()}, body, STRIPE_SECRET
    )


def test_stripe_rejects_bad_signature() -> None:
    body = json.dumps({"id": "evt_1"}).encode()
    ts = int(time.time())
    headers = {"stripe-signature": f"t={ts},v1=deadbeef"}
    with pytest.raises(InvalidSignature):
        StripeAdapter().verify_signature(headers, body, STRIPE_SECRET)


def test_stripe_rejects_replay() -> None:
    body = json.dumps({"id": "evt_1"}).encode()
    headers = _stripe_sign(body, ts=1)  # ancient
    with pytest.raises(ReplayWindowExceeded):
        StripeAdapter().verify_signature(
            {k.lower(): v for k, v in headers.items()}, body, STRIPE_SECRET
        )


def test_stripe_parse_payment_intent() -> None:
    body = {
        "id": "evt_42",
        "type": "payment_intent.succeeded",
        "data": {"object": {"object": "payment_intent", "id": "pi_xyz", "amount_received": 1250}},
    }
    result = StripeAdapter().parse(body)
    assert result.event_id == "evt_42"
    assert result.match_key == ("stripe_payment_intent_id", "pi_xyz")
    assert result.actual_outcome_usd == Decimal("12.5")


def test_stripe_parse_charge_refers_to_payment_intent() -> None:
    body = {
        "id": "evt_99",
        "type": "charge.succeeded",
        "data": {"object": {"object": "charge", "payment_intent": "pi_abc", "amount": 5000}},
    }
    result = StripeAdapter().parse(body)
    assert result.match_key == ("stripe_payment_intent_id", "pi_abc")
    assert result.actual_outcome_usd == Decimal("50")


def test_stripe_missing_id_rejected() -> None:
    with pytest.raises(ValueError):
        StripeAdapter().parse({"data": {"object": {"object": "payment_intent"}}})


# --- Salesforce -------------------------------------------------------------

SF_SECRET = "sf-secret"


def _sf_sign(body: bytes, ts: int | None = None) -> dict[str, str]:
    ts = ts or int(time.time())
    sig = base64.b64encode(
        hmac.new(SF_SECRET.encode(), f"{ts}.".encode() + body, hashlib.sha256).digest()
    ).decode()
    return {"Sforce-Timestamp": str(ts), "Sforce-HMAC-SHA256": sig}


def test_salesforce_signature_round_trip() -> None:
    body = json.dumps({"event_id": "x"}).encode()
    headers = _sf_sign(body)
    SalesforceAdapter().verify_signature(
        {k.lower(): v for k, v in headers.items()}, body, SF_SECRET
    )


def test_salesforce_rejects_bad_signature() -> None:
    body = json.dumps({"event_id": "x"}).encode()
    headers = {"sforce-timestamp": str(int(time.time())), "sforce-hmac-sha256": "bad"}
    with pytest.raises(InvalidSignature):
        SalesforceAdapter().verify_signature(headers, body, SF_SECRET)


def test_salesforce_parse() -> None:
    body = {
        "event_id": "evt-555",
        "opportunity": {"id": "006abc", "amount": "9999.00"},
    }
    result = SalesforceAdapter().parse(body)
    assert result.event_id == "evt-555"
    assert result.match_key == ("salesforce_opportunity_id", "006abc")
    assert result.actual_outcome_usd == Decimal("9999.00")
