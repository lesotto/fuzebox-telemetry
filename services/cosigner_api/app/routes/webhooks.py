"""Cosign webhook routes."""

from __future__ import annotations

import os

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..adapters import (
    ADAPTERS,
    InvalidSignature,
    ReplayWindowExceeded,
    get_adapter,
)
from ..db import get_session
from ..ledger.cosign import apply_cosign
from ..ledger.signing import SigningProvider, build_provider

router = APIRouter(prefix="/v1/webhooks", tags=["webhooks"])
log = structlog.get_logger(__name__)


def _adapter_secret(adapter: str) -> str:
    env = f"FUZEBOX_{adapter.upper()}_WEBHOOK_SECRET"
    secret = os.getenv(env)
    if not secret:
        raise HTTPException(status_code=500, detail=f"{env} is not configured")
    return secret


def _tenant_for_adapter(adapter: str) -> str:
    # Sprint 2: a single tenant per adapter via env. Sprint 5 makes this a
    # tenant-scoped webhook URL with per-tenant secrets.
    env = f"FUZEBOX_{adapter.upper()}_TENANT"
    return os.getenv(env, os.getenv("FUZEBOX_DEFAULT_TENANT", "default"))


def get_signer() -> SigningProvider:
    return build_provider()


@router.post("/cosign/{adapter}")
async def cosign_webhook(
    adapter: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    signer: SigningProvider = Depends(get_signer),
) -> dict[str, str]:
    if adapter not in ADAPTERS:
        raise HTTPException(status_code=404, detail=f"unknown adapter: {adapter}")

    raw = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}

    impl = get_adapter(adapter)
    secret = _adapter_secret(adapter)
    try:
        impl.verify_signature(headers, raw, secret)
    except InvalidSignature as exc:
        log.warning("webhook.invalid_signature", adapter=adapter, error=str(exc))
        raise HTTPException(status_code=401, detail="invalid signature") from exc
    except ReplayWindowExceeded as exc:
        log.warning("webhook.replay_window", adapter=adapter, error=str(exc))
        raise HTTPException(status_code=400, detail="replay window exceeded") from exc

    import json

    body = json.loads(raw.decode("utf-8") or "{}")
    try:
        result = impl.parse(body)
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    tenant_id = _tenant_for_adapter(adapter)
    row, event = await apply_cosign(
        session,
        tenant_id=tenant_id,
        adapter=adapter,
        event_id=result.event_id,
        match_key=result.match_key,
        actual_outcome_usd=result.actual_outcome_usd,
        cosigned_by=result.cosigned_by,
        payload=result.payload,
        signer=signer,
    )

    log.info(
        "webhook.cosign.applied",
        adapter=adapter,
        event_id=result.event_id,
        tenant=tenant_id,
        matched=row is not None,
        row_id=str(row.row_id) if row else None,
    )
    return {
        "status": event.match_status,
        "row_id": str(row.row_id) if row else "",
        "trust_level": str(row.trust_level) if row else "0",
    }
