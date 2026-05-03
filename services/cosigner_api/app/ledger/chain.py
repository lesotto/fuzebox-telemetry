"""Hash-chain primitives for the PEL.

Every row's `row_hash` is `SHA256(canonical_payload || prev_hash)`. The
`canonical_payload` is a deterministic JSON encoding (sorted keys, no whitespace,
UTF-8) of an explicit allowlist of fields. Anything not in the allowlist is
ignored — auditors can recompute hashes without needing the full row.

Auditors can also re-verify offline: given a chain of rows and a signing
provider's public material, they walk the chain and re-check each `row_hash`
and `signature`. See `services/verify_cli/verify.py`.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

# Fields included in the canonical hash. Ordering is explicit so the hash is
# stable across language implementations.
_HASHED_FIELDS: tuple[str, ...] = (
    "row_id",
    "tenant_id",
    "agent_id",
    "skill",
    "case_id",
    "model",
    "cost_usd",
    "predicted_outcome_usd",
    "actual_outcome_usd",
    "counterfactual_outcome_usd",
    "counterfactual_confidence",
    "counterfactual_method",
    "lift_usd",
    "trust_level",
    "cosigned_by",
    "cosigned_at",
    "meta",
    "status",
    "created_at",
    "closed_at",
)


@dataclass(frozen=True)
class ChainLink:
    """A logical chain link: the canonical bytes plus the resulting hash."""

    payload: bytes
    row_hash: bytes
    prev_hash: bytes | None


def _canonicalize(value: Any) -> Any:
    """Coerce values to JSON-safe canonical forms.

    - Decimal → string with no exponent.
    - datetime → ISO-8601 with explicit UTC offset.
    - bytes → not allowed (raises).
    """

    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    if isinstance(value, float):
        # No floats in the canonical form. Round-tripping floats across
        # languages is too lossy for an audit log.
        raise TypeError("floats are not allowed in canonical hashed fields")
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("datetime must be timezone-aware")
        return value.astimezone(tz=value.tzinfo).isoformat()
    if isinstance(value, dict):
        return {k: _canonicalize(v) for k, v in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_canonicalize(v) for v in value]
    if isinstance(value, bytes):
        raise TypeError("bytes are not allowed in canonical hashed fields")
    # uuid.UUID, etc.
    return str(value)


def canonicalize_row(row: dict[str, Any]) -> bytes:
    """Return the canonical bytes that get hashed.

    Only fields in `_HASHED_FIELDS` participate. Missing fields default to None.

    Example:
        >>> b = canonicalize_row({"row_id": "00000000-0000-0000-0000-000000000001",
        ...                       "tenant_id": "acme", "agent_id": "a", "skill": "s",
        ...                       "case_id": "c", "status": "open",
        ...                       "trust_level": 0, "cost_usd": Decimal("0"),
        ...                       "meta": {"k": "v"},
        ...                       "created_at": "2026-05-03T00:00:00+00:00"})
        >>> isinstance(b, bytes) and len(b) > 0
        True
    """

    canonical = {f: _canonicalize(row.get(f)) for f in _HASHED_FIELDS}
    return json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")


def compute_row_hash(row: dict[str, Any], prev_hash: bytes | None) -> ChainLink:
    """Compute SHA256(canonical(row) || prev_hash) and return a ChainLink."""

    payload = canonicalize_row(row)
    h = hashlib.sha256()
    h.update(payload)
    if prev_hash is not None:
        h.update(prev_hash)
    return ChainLink(payload=payload, row_hash=h.digest(), prev_hash=prev_hash)


def verify_row(
    row: dict[str, Any],
    *,
    prev_hash: bytes | None,
    expected_row_hash: bytes,
) -> bool:
    """Recompute the hash and compare.

    Pure function; safe to call offline.
    """

    link = compute_row_hash(row, prev_hash)
    return link.row_hash == expected_row_hash


def to_export_dict(row: dict[str, Any]) -> dict[str, Any]:
    """Return a JSON-safe dict containing only hashed fields, with values pre-canonicalized.

    Auditors receive this in the export bundle and feed it back into the same
    JSON encoder used here. The bytes are identical, so the hash matches.
    """

    return {f: _canonicalize(row.get(f)) for f in _HASHED_FIELDS}


__all__ = ["ChainLink", "canonicalize_row", "compute_row_hash", "to_export_dict", "verify_row"]
