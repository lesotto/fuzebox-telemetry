"""Cosign state machine.

For an open or closed PEL row matched by webhook payload:

1. Bump trust_level from 1/2 to 3.
2. Set cosigned_by, cosigned_at, actual_outcome_usd.
3. Compute lift_usd = actual_outcome_usd - counterfactual_outcome_usd
   (only if counterfactual_confidence >= 0.30).
4. Re-link to chain tail, recompute row_hash, re-sign.
5. Append a signed entry to cosign_event_log (also chained, also signed).
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from .chain import compute_row_hash
from .models import CosignEvent, PELRow
from .repo import _row_to_dict, _set_tenant
from .signing import SigningProvider

LIFT_CONFIDENCE_THRESHOLD = Decimal("0.30")


class CosignError(Exception):
    """Cosign couldn't be applied."""


def _hash_payload(payload: dict[str, Any]) -> bytes:
    canon = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canon).digest()


def _compute_event_hash(
    *,
    adapter: str,
    event_id: str,
    tenant_id: str,
    row_id: uuid.UUID | None,
    match_status: str,
    payload_hash: bytes,
    prev_hash: bytes | None,
) -> bytes:
    h = hashlib.sha256()
    h.update(b"|".join([adapter.encode(), event_id.encode(), tenant_id.encode()]))
    h.update(b"|")
    h.update(str(row_id or "").encode())
    h.update(b"|")
    h.update(match_status.encode())
    h.update(b"|")
    h.update(payload_hash)
    if prev_hash is not None:
        h.update(prev_hash)
    return h.digest()


async def _last_event_hash(session: AsyncSession, tenant_id: str) -> bytes | None:
    stmt = (
        select(CosignEvent.event_hash)
        .where(CosignEvent.tenant_id == tenant_id)
        .order_by(CosignEvent.received_at.desc())
        .limit(1)
    )
    row = (await session.execute(stmt)).first()
    return bytes(row[0]) if row else None


async def _existing_event(
    session: AsyncSession, adapter: str, event_id: str, tenant_id: str
) -> CosignEvent | None:
    stmt = select(CosignEvent).where(
        CosignEvent.adapter == adapter,
        CosignEvent.event_id == event_id,
        CosignEvent.tenant_id == tenant_id,
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def _find_row_by_meta(
    session: AsyncSession, tenant_id: str, key: str, value: str
) -> PELRow | None:
    stmt = (
        select(PELRow)
        .where(
            PELRow.tenant_id == tenant_id,
            PELRow.meta.cast(JSONB)[key].astext == value,  # type: ignore[index]
            PELRow.status.in_(("open", "closed", "cosign_pending")),
        )
        .order_by(PELRow.created_at.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def apply_cosign(
    session: AsyncSession,
    *,
    tenant_id: str,
    adapter: str,
    event_id: str,
    match_key: tuple[str, str],
    actual_outcome_usd: Decimal | None,
    cosigned_by: str,
    payload: dict[str, Any],
    signer: SigningProvider,
) -> tuple[PELRow | None, CosignEvent]:
    """Apply a cosign event end-to-end. Idempotent on (adapter, event_id)."""

    await _set_tenant(session, tenant_id)

    existing = await _existing_event(session, adapter, event_id, tenant_id)
    if existing is not None:
        row: PELRow | None = None
        if existing.row_id is not None:
            stmt = select(PELRow).where(
                PELRow.row_id == existing.row_id, PELRow.tenant_id == tenant_id
            )
            row = (await session.execute(stmt)).scalar_one_or_none()
        return row, existing

    key, value = match_key
    row = await _find_row_by_meta(session, tenant_id, key, value)
    match_status = "matched" if row is not None else "unmatched"

    if row is not None and actual_outcome_usd is not None:
        row.actual_outcome_usd = actual_outcome_usd
        row.cosigned_by = cosigned_by
        row.cosigned_at = datetime.now(tz=UTC)
        row.trust_level = max(int(row.trust_level), 3)
        if (
            row.counterfactual_outcome_usd is not None
            and row.counterfactual_confidence is not None
            and Decimal(row.counterfactual_confidence) >= LIFT_CONFIDENCE_THRESHOLD
        ):
            row.lift_usd = actual_outcome_usd - Decimal(row.counterfactual_outcome_usd)

        # Re-link this row to the latest chain tail (excluding itself).
        prev_stmt = (
            select(PELRow.row_hash)
            .where(PELRow.tenant_id == tenant_id, PELRow.row_id != row.row_id)
            .order_by(PELRow.created_at.desc())
            .limit(1)
        )
        prev_row = (await session.execute(prev_stmt)).first()
        prev_hash = bytes(prev_row[0]) if prev_row else None
        link = compute_row_hash(_row_to_dict(row), prev_hash)
        row.prev_hash = prev_hash
        row.row_hash = link.row_hash
        row.signature = signer.sign(link.row_hash)

    # Always append an audit log entry — matched OR unmatched.
    payload_hash = _hash_payload(payload)
    prev_event_hash = await _last_event_hash(session, tenant_id)
    received_at = datetime.now(tz=UTC)
    event_hash = _compute_event_hash(
        adapter=adapter,
        event_id=event_id,
        tenant_id=tenant_id,
        row_id=row.row_id if row else None,
        match_status=match_status,
        payload_hash=payload_hash,
        prev_hash=prev_event_hash,
    )

    event = CosignEvent(
        event_pk=uuid.uuid4(),
        tenant_id=tenant_id,
        adapter=adapter,
        event_id=event_id,
        row_id=row.row_id if row else None,
        match_status=match_status,
        received_at=received_at,
        payload_hash=payload_hash,
        prev_hash=prev_event_hash,
        event_hash=event_hash,
        signature=signer.sign(event_hash),
        details={"match_key": [key, value]},
    )
    session.add(event)
    await session.flush()
    return row, event
