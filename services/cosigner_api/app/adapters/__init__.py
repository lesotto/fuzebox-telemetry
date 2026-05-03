"""Cosign adapters: convert webhook payloads into ledger updates.

Each adapter:
- Verifies its provider's signature (Stripe, Salesforce, etc.).
- Enforces a 5-minute replay window.
- Extracts a stable `event_id` for idempotency.
- Returns a `match_key` (typically a `meta` field) so we can find the open
  PEL row to cosign.
"""

from __future__ import annotations

from .base import (
    AdapterResult,
    CosignAdapter,
    InvalidSignature,
    ReplayWindowExceeded,
)
from .salesforce import SalesforceAdapter
from .stripe import StripeAdapter

ADAPTERS: dict[str, type[CosignAdapter]] = {
    "stripe": StripeAdapter,
    "salesforce": SalesforceAdapter,
}


def get_adapter(name: str) -> CosignAdapter:
    if name not in ADAPTERS:
        raise KeyError(f"unknown cosign adapter: {name}")
    return ADAPTERS[name]()


__all__ = [
    "ADAPTERS",
    "AdapterResult",
    "CosignAdapter",
    "InvalidSignature",
    "ReplayWindowExceeded",
    "SalesforceAdapter",
    "StripeAdapter",
    "get_adapter",
]
