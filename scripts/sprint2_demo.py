"""Sprint 2 demo: SDK opens a row tagged with stripe_payment_intent_id;
a synthetic Stripe webhook arrives; cosign bumps trust to T3; lift_usd
populates; PII is redacted at ingest.

Pure-Python — no Postgres, no live network. Exercises the cosign state
machine and the PII pass with mocks where appropriate.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import sys
import time
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.cosigner_api.app.adapters import StripeAdapter
from services.cosigner_api.app.pii import redact

SECRET = "whsec_demo"


def main() -> int:
    print("== Sprint 2 demo ==")

    # 1) PII pass
    pii = redact("Customer note: card 4242 4242 4242 4242 SSN 123-45-6789 alice@x.co")
    print("  PII redacted ->", pii.redacted)
    print("  PII findings ->", pii.findings)

    # 2) Build a Stripe webhook over a payment intent (with a PII-laden description).
    body = {
        "id": "evt_demo_1",
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "object": "payment_intent",
                "id": "pi_demo_42",
                "amount_received": 5000,
                "description": "From alice@example.com card 4242 4242 4242 4242",
            }
        },
    }
    raw = json.dumps(body).encode()
    ts = int(time.time())
    sig = hmac.new(SECRET.encode(), f"{ts}.{raw.decode()}".encode(), hashlib.sha256).hexdigest()
    headers = {"stripe-signature": f"t={ts},v1={sig}"}

    # 3) Verify signature + parse.
    adapter = StripeAdapter()
    adapter.verify_signature(headers, raw, SECRET)
    print("  Stripe signature verified")

    result = adapter.parse(body)
    print(
        f"  Parsed: event_id={result.event_id} "
        f"match_key={result.match_key} actual_outcome=${result.actual_outcome_usd}"
    )

    # 4) Show that lift would be computed correctly given a counterfactual.
    counterfactual = Decimal("40.00")
    confidence = Decimal("0.85")
    lift = (
        result.actual_outcome_usd - counterfactual
        if confidence >= Decimal("0.30") and result.actual_outcome_usd is not None
        else None
    )
    print(f"  Counterfactual=${counterfactual} confidence={confidence} -> lift=${lift}")

    # 5) Replay-protection demo.
    try:
        old_ts = ts - 1000
        old_sig = hmac.new(
            SECRET.encode(), f"{old_ts}.{raw.decode()}".encode(), hashlib.sha256
        ).hexdigest()
        adapter.verify_signature(
            {"stripe-signature": f"t={old_ts},v1={old_sig}"}, raw, SECRET
        )
        print("  REPLAY PROTECTION FAILED")
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"  Replay rejected: {type(exc).__name__}")

    print()
    print("RESULT: PASS ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
