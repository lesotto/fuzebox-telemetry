"""Salesforce cosign adapter.

Salesforce outbound webhooks ship an HMAC over the raw body in the
`Sforce-HMAC-SHA256` header (custom integrations do this; Salesforce's native
outbound messages use SOAP, which we don't accept here). The match key is
`meta.salesforce_opportunity_id` against `body.opportunity.id`.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
from decimal import Decimal
from typing import Any

from .base import AdapterResult, CosignAdapter, InvalidSignature, ReplayWindowExceeded

REPLAY_WINDOW_SECONDS = 300


class SalesforceAdapter(CosignAdapter):
    name = "salesforce"

    def verify_signature(
        self, headers: dict[str, str], raw_body: bytes, secret: str
    ) -> None:
        sig = headers.get("sforce-hmac-sha256") or headers.get("Sforce-HMAC-SHA256")
        ts = headers.get("sforce-timestamp") or headers.get("Sforce-Timestamp")
        if not (sig and ts):
            raise InvalidSignature("missing Salesforce signature headers")

        try:
            ts_int = int(ts)
        except ValueError as exc:
            raise InvalidSignature("non-numeric Sforce-Timestamp") from exc
        if abs(int(time.time()) - ts_int) > REPLAY_WINDOW_SECONDS:
            raise ReplayWindowExceeded("Salesforce timestamp outside replay window")

        signed = ts.encode() + b"." + raw_body
        expected = base64.b64encode(
            hmac.new(secret.encode(), signed, hashlib.sha256).digest()
        ).decode()
        if not hmac.compare_digest(expected, sig):
            raise InvalidSignature("Salesforce signature mismatch")

    def parse(self, body: dict[str, Any]) -> AdapterResult:
        event_id = str(body.get("event_id") or body.get("id") or "")
        if not event_id:
            raise ValueError("Salesforce payload missing event_id")

        opp = body.get("opportunity") or {}
        match_value = opp.get("id")
        if not match_value:
            raise ValueError("Salesforce payload missing opportunity.id")

        amount = opp.get("amount") or 0
        actual = Decimal(str(amount))

        return AdapterResult(
            event_id=event_id,
            match_key=("salesforce_opportunity_id", str(match_value)),
            actual_outcome_usd=actual,
            cosigned_by="salesforce",
            payload=body,
        )
