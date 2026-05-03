"""Repository layer for ledger operations.

All writes happen in transactions. All reads/writes set `app.tenant_id` so RLS
policies enforce isolation at the database level.

Sprint 1 surface:

- `open_row(...)`: create a new PEL row, link to chain tail, sign, persist.
- `close_row(...)`: seal the row with predicted/actual outcome, re-link, re-sign.
- `get_chain(...)`: return rows in chain order for a tenant.

Cosign and counterfactual logic land in Sprint 2 / 3.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from .chain import compute_row_hash
from .models import PELRow
from .signing import SigningProvider


class LedgerError(Exception):
    """Raised when a ledger invariant is violated."""


@dataclass(frozen=True)
class OpenRowRequest:
    tenant_id: str
    agent_id: str
    skill: str
    case_id: str
    model: str | None = None
    cost_usd: Decimal = Decimal("0")
    meta: dict[str, Any] | None = None


@dataclass(frozen=True)
class CloseRowRequest:
    row_id: uuid.UUID
    tenant_id: str
    predicted_outcome_usd: Decimal | None = None
    actual_outcome_usd: Decimal | None = None
    extra_meta: dict[str, Any] | None = None


async def _set_tenant(session: AsyncSession, tenant_id: str) -> None:
    """Set `app.tenant_id` for the current transaction so RLS applies."""

    # set_config(true) → transaction-local. Must be inside a transaction.
    await session.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": tenant_id})


async def _chain_tail_hash(session: AsyncSession, tenant_id: str) -> bytes | None:
    """Return the most-recent row_hash for this tenant, or None if empty."""

    stmt = (
        select(PELRow.row_hash)
        .where(PELRow.tenant_id == tenant_id)
        .order_by(PELRow.created_at.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    row = result.first()
    return bytes(row[0]) if row else None


def _row_to_dict(row: PELRow) -> dict[str, Any]:
    return {
        "row_id": str(row.row_id),
        "tenant_id": row.tenant_id,
        "agent_id": row.agent_id,
        "skill": row.skill,
        "case_id": row.case_id,
        "model": row.model,
        "cost_usd": row.cost_usd,
        "predicted_outcome_usd": row.predicted_outcome_usd,
        "actual_outcome_usd": row.actual_outcome_usd,
        "counterfactual_outcome_usd": row.counterfactual_outcome_usd,
        "counterfactual_confidence": row.counterfactual_confidence,
        "counterfactual_method": row.counterfactual_method,
        "lift_usd": row.lift_usd,
        "trust_level": row.trust_level,
        "cosigned_by": row.cosigned_by,
        "cosigned_at": row.cosigned_at,
        "meta": row.meta or {},
        "status": row.status,
        "created_at": row.created_at,
        "closed_at": row.closed_at,
    }


async def open_row(
    session: AsyncSession,
    req: OpenRowRequest,
    signer: SigningProvider,
) -> PELRow:
    """Open a new PEL row, link it to the chain tail, sign it, persist it.

    Trust level starts at 1 (locally signed, not yet cosigned).
    Status starts at "open".
    """

    await _set_tenant(session, req.tenant_id)
    prev_hash = await _chain_tail_hash(session, req.tenant_id)

    now = datetime.now(tz=UTC)
    row_id = uuid.uuid4()

    proto: dict[str, Any] = {
        "row_id": str(row_id),
        "tenant_id": req.tenant_id,
        "agent_id": req.agent_id,
        "skill": req.skill,
        "case_id": req.case_id,
        "model": req.model,
        "cost_usd": req.cost_usd,
        "predicted_outcome_usd": None,
        "actual_outcome_usd": None,
        "counterfactual_outcome_usd": None,
        "counterfactual_confidence": None,
        "counterfactual_method": None,
        "lift_usd": None,
        "trust_level": 1,
        "cosigned_by": None,
        "cosigned_at": None,
        "meta": req.meta or {},
        "status": "open",
        "created_at": now,
        "closed_at": None,
    }

    link = compute_row_hash(proto, prev_hash)
    signature = signer.sign(link.row_hash)

    row = PELRow(
        row_id=row_id,
        tenant_id=req.tenant_id,
        agent_id=req.agent_id,
        skill=req.skill,
        case_id=req.case_id,
        model=req.model,
        cost_usd=req.cost_usd,
        trust_level=1,
        prev_hash=prev_hash,
        row_hash=link.row_hash,
        signature=signature,
        meta=req.meta or {},
        status="open",
        created_at=now,
    )
    session.add(row)
    await session.flush()
    return row


async def close_row(
    session: AsyncSession,
    req: CloseRowRequest,
    signer: SigningProvider,
) -> PELRow:
    """Seal an open row: set outcomes, re-hash with up-to-date chain tail, re-sign.

    Re-linking on close means the chain reflects the *closed* state. The
    original opening signature is rotated out by design — auditors verify the
    final, sealed row.
    """

    await _set_tenant(session, req.tenant_id)

    stmt = select(PELRow).where(
        PELRow.row_id == req.row_id, PELRow.tenant_id == req.tenant_id
    )
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        raise LedgerError(f"row {req.row_id} not found")
    if row.status not in {"open", "unledgered"}:
        raise LedgerError(f"row {req.row_id} is not open (status={row.status})")

    if req.predicted_outcome_usd is not None:
        row.predicted_outcome_usd = req.predicted_outcome_usd
    if req.actual_outcome_usd is not None:
        row.actual_outcome_usd = req.actual_outcome_usd
    if req.extra_meta:
        merged = dict(row.meta or {})
        merged.update(req.extra_meta)
        row.meta = merged

    row.status = "closed"
    row.closed_at = datetime.now(tz=UTC)

    # Re-link to the latest chain tail OTHER than this row.
    prev_stmt = (
        select(PELRow.row_hash)
        .where(PELRow.tenant_id == req.tenant_id, PELRow.row_id != row.row_id)
        .order_by(PELRow.created_at.desc())
        .limit(1)
    )
    prev_result = await session.execute(prev_stmt)
    prev_row = prev_result.first()
    prev_hash = bytes(prev_row[0]) if prev_row else None

    link = compute_row_hash(_row_to_dict(row), prev_hash)
    row.prev_hash = prev_hash
    row.row_hash = link.row_hash
    row.signature = signer.sign(link.row_hash)

    await session.flush()
    return row


async def get_chain(session: AsyncSession, tenant_id: str) -> list[PELRow]:
    """Return rows for a tenant in chain order (oldest first)."""

    await _set_tenant(session, tenant_id)
    stmt = (
        select(PELRow).where(PELRow.tenant_id == tenant_id).order_by(PELRow.created_at.asc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


__all__ = [
    "LedgerError",
    "OpenRowRequest",
    "CloseRowRequest",
    "open_row",
    "close_row",
    "get_chain",
]
