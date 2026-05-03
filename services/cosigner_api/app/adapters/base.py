"""Cosign adapter abstract base."""

from __future__ import annotations

import abc
from dataclasses import dataclass
from decimal import Decimal
from typing import Any


class InvalidSignature(Exception):
    """Webhook signature did not verify."""


class ReplayWindowExceeded(Exception):
    """Webhook timestamp is older than the allowed replay window (5 min)."""


@dataclass(frozen=True)
class AdapterResult:
    """What an adapter returns after parsing a webhook.

    `match_key` is `(field_name, field_value)`; the cosigner looks up rows
    whose `meta` JSONB column has `field_name == field_value`.
    """

    event_id: str
    match_key: tuple[str, str]
    actual_outcome_usd: Decimal | None
    cosigned_by: str
    payload: dict[str, Any]


class CosignAdapter(abc.ABC):
    """Abstract cosign adapter."""

    name: str

    @abc.abstractmethod
    def verify_signature(
        self, headers: dict[str, str], raw_body: bytes, secret: str
    ) -> None:
        """Raise InvalidSignature on bad signature, ReplayWindowExceeded on stale timestamps."""

    @abc.abstractmethod
    def parse(self, body: dict[str, Any]) -> AdapterResult:
        """Convert the parsed JSON body into a normalized AdapterResult."""
