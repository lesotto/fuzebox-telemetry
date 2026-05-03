"""Stripe cosign adapter.

Stripe signs webhooks with HMAC-SHA256 over `t.{timestamp}.{payload}` using a
per-endpoint signing secret. Their docs:
https://stripe.com/docs/webhooks/signatures

We match `meta.stripe_payment_intent_id` against the event's
`data.object.id` (for `payment_intent.*` events) or `data.object.payment_intent`
(for `charge.*` events).
"""

from __future__ import annotations

import hashlib
import hmac
import time
from decimal import Decimal
from typing import Any

from .base import AdapterResult, CosignAdapter, InvalidSignature, ReplayWindowExceeded

REPLAY_WINDOW_SECONDS = 300


class StripeAdapter(CosignAdapter):
    name = "stripe"

    def verify_signature(
        self, headers: dict[str, str], raw_body: bytes, secret: str
    ) -> None:
        sig_header = headers.get("stripe-signature") or headers.get("Stripe-Signature")
        if not sig_header:
            raise InvalidSignature("missing Stripe-Signature header")

        parts = dict(p.split("=", 1) for p in sig_header.split(",") if "=" in p)
        timestamp = parts.get("t")
        v1 = parts.get("v1")
        if not (timestamp and v1):
            raise InvalidSignature("malformed Stripe-Signature header")

        now = int(time.time())
        try:
            ts = int(timestamp)
        except ValueError as exc:
            raise InvalidSignature("non-numeric timestamp") from exc
        if abs(now - ts) > REPLAY_WINDOW_SECONDS:
            raise ReplayWindowExceeded(f"timestamp {ts} outside ±{REPLAY_WINDOW_SECONDS}s")

        signed = f"{timestamp}.{raw_body.decode('utf-8')}".encode()
        expected = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, v1):
            raise InvalidSignature("v1 signature mismatch")

    def parse(self, body: dict[str, Any]) -> AdapterResult:
        event_id = str(body.get("id", ""))
        if not event_id:
            raise ValueError("Stripe event missing id")

        obj = body.get("data", {}).get("object", {})
        # payment_intent.* events: object is the payment intent itself.
        # charge.* events: object is a charge with `payment_intent` field.
        match_value = obj.get("id") if obj.get("object") == "payment_intent" else obj.get(
            "payment_intent"
        )
        if not match_value:
            raise ValueError("Stripe event has no payment_intent id to match on")

        amount_received = obj.get("amount_received") or obj.get("amount") or 0
        # Stripe amounts are in the smallest currency unit (cents for USD).
        actual = Decimal(amount_received) / Decimal(100)

        return AdapterResult(
            event_id=event_id,
            match_key=("stripe_payment_intent_id", match_value),
            actual_outcome_usd=actual,
            cosigned_by="stripe",
            payload=body,
        )
