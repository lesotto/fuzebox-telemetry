"""HTTP routes for PEL row open/close."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..ledger.repo import (
    CloseRowRequest,
    LedgerError,
    OpenRowRequest,
    close_row,
    open_row,
)
from ..ledger.signing import SigningProvider, build_provider

router = APIRouter(prefix="/v1/pel", tags=["pel"])
log = structlog.get_logger(__name__)


def get_signer() -> SigningProvider:
    return build_provider()


class OpenRowBody(BaseModel):
    agent_id: str = Field(min_length=1, max_length=256)
    skill: str = Field(min_length=1, max_length=256)
    case_id: str = Field(min_length=1, max_length=256)
    model: str | None = None
    cost_usd: Decimal = Decimal("0")
    meta: dict[str, Any] = Field(default_factory=dict)


class CloseRowBody(BaseModel):
    predicted_outcome_usd: Decimal | None = None
    actual_outcome_usd: Decimal | None = None
    extra_meta: dict[str, Any] = Field(default_factory=dict)


class RowResponse(BaseModel):
    row_id: uuid.UUID
    tenant_id: str
    agent_id: str
    skill: str
    case_id: str
    status: str
    trust_level: int
    row_hash_hex: str
    signature_hex: str
    prev_hash_hex: str | None


def _to_response(row: Any) -> RowResponse:
    return RowResponse(
        row_id=row.row_id,
        tenant_id=row.tenant_id,
        agent_id=row.agent_id,
        skill=row.skill,
        case_id=row.case_id,
        status=row.status,
        trust_level=row.trust_level,
        row_hash_hex=row.row_hash.hex(),
        signature_hex=row.signature.hex(),
        prev_hash_hex=row.prev_hash.hex() if row.prev_hash else None,
    )


@router.post("/open", response_model=RowResponse, status_code=201)
async def open_pel_row(
    body: OpenRowBody,
    x_tenant_id: str = Header(..., alias="X-Tenant-Id"),
    session: AsyncSession = Depends(get_session),
    signer: SigningProvider = Depends(get_signer),
) -> RowResponse:
    """Open a new PEL row. The chain is extended; the row is signed at trust level 1.

    Authentication: in Sprint 1 we trust an `X-Tenant-Id` header forwarded from
    the SDK / API gateway. Sprint 5 swaps this for proper tenant-scoped JWT auth.
    """

    req = OpenRowRequest(
        tenant_id=x_tenant_id,
        agent_id=body.agent_id,
        skill=body.skill,
        case_id=body.case_id,
        model=body.model,
        cost_usd=body.cost_usd,
        meta=body.meta,
    )
    try:
        row = await open_row(session, req, signer)
    except LedgerError as exc:
        log.warning("ledger.open.failed", tenant=x_tenant_id, error=str(exc))
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    log.info(
        "ledger.open.ok",
        tenant=x_tenant_id,
        row_id=str(row.row_id),
        skill=row.skill,
        case_id=row.case_id,
    )
    return _to_response(row)


@router.post("/{row_id}/close", response_model=RowResponse)
async def close_pel_row(
    row_id: uuid.UUID,
    body: CloseRowBody,
    x_tenant_id: str = Header(..., alias="X-Tenant-Id"),
    session: AsyncSession = Depends(get_session),
    signer: SigningProvider = Depends(get_signer),
) -> RowResponse:
    """Seal an open PEL row."""

    req = CloseRowRequest(
        row_id=row_id,
        tenant_id=x_tenant_id,
        predicted_outcome_usd=body.predicted_outcome_usd,
        actual_outcome_usd=body.actual_outcome_usd,
        extra_meta=body.extra_meta,
    )
    try:
        row = await close_row(session, req, signer)
    except LedgerError as exc:
        log.warning(
            "ledger.close.failed", tenant=x_tenant_id, row_id=str(row_id), error=str(exc)
        )
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    log.info(
        "ledger.close.ok",
        tenant=x_tenant_id,
        row_id=str(row.row_id),
        predicted=str(body.predicted_outcome_usd) if body.predicted_outcome_usd else None,
    )
    return _to_response(row)
