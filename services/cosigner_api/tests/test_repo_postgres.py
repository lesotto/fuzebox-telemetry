"""Integration tests for the repo layer + RLS + chain integrity.

Skipped unless `FUZEBOX_TEST_DATABASE_URL` points at a real Postgres. CI sets
this. The CI Postgres image is plain Postgres 15 (no Timescale), so the
migration's hypertable conversion no-ops gracefully.
"""

from __future__ import annotations

import os
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from services.cosigner_api.app.ledger.chain import compute_row_hash
from services.cosigner_api.app.ledger.models import Base
from services.cosigner_api.app.ledger.repo import (
    CloseRowRequest,
    OpenRowRequest,
    close_row,
    get_chain,
    open_row,
)
from services.cosigner_api.app.ledger.signing import StaticHMACProvider

PG_URL = os.getenv("FUZEBOX_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not PG_URL, reason="set FUZEBOX_TEST_DATABASE_URL to run")


@pytest.fixture
async def session() -> AsyncSession:
    engine = create_async_engine(PG_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
        # Enable RLS so tenant isolation tests are meaningful.
        for tbl in ("pel_rows", "spans", "cosign_event_log"):
            await conn.execute(text(f"ALTER TABLE {tbl} ENABLE ROW LEVEL SECURITY"))
            await conn.execute(text(f"ALTER TABLE {tbl} FORCE ROW LEVEL SECURITY"))
            await conn.execute(
                text(
                    f"CREATE POLICY tenant_isolation ON {tbl} "
                    "USING (tenant_id = current_setting('app.tenant_id', true)) "
                    "WITH CHECK (tenant_id = current_setting('app.tenant_id', true))"
                )
            )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as sess:
        async with sess.begin():
            yield sess
    await engine.dispose()


async def test_open_then_close_chains_correctly(session: AsyncSession) -> None:
    signer = StaticHMACProvider(secret="repo-test")

    r1 = await open_row(
        session,
        OpenRowRequest(tenant_id="acme", agent_id="a", skill="s", case_id="c1"),
        signer,
    )
    r2 = await open_row(
        session,
        OpenRowRequest(tenant_id="acme", agent_id="a", skill="s", case_id="c2"),
        signer,
    )

    assert r1.prev_hash is None
    assert r2.prev_hash == r1.row_hash
    assert signer.verify(r1.row_hash, bytes(r1.signature))
    assert signer.verify(r2.row_hash, bytes(r2.signature))


async def test_close_reseals_with_outcome(session: AsyncSession) -> None:
    signer = StaticHMACProvider(secret="repo-test")
    opened = await open_row(
        session,
        OpenRowRequest(tenant_id="acme", agent_id="a", skill="s", case_id="c1"),
        signer,
    )
    original_hash = bytes(opened.row_hash)
    closed = await close_row(
        session,
        CloseRowRequest(
            row_id=opened.row_id,
            tenant_id="acme",
            predicted_outcome_usd=Decimal("12.5"),
        ),
        signer,
    )
    assert closed.status == "closed"
    assert closed.predicted_outcome_usd == Decimal("12.5")
    assert bytes(closed.row_hash) != original_hash
    assert signer.verify(closed.row_hash, bytes(closed.signature))


async def test_rls_blocks_cross_tenant_reads(session: AsyncSession) -> None:
    signer = StaticHMACProvider(secret="repo-test")
    await open_row(
        session,
        OpenRowRequest(tenant_id="acme", agent_id="a", skill="s", case_id="c1"),
        signer,
    )
    # Same session, different tenant context.
    other = await get_chain(session, tenant_id="evilcorp")
    assert other == []


async def test_chain_recomputes_offline(session: AsyncSession) -> None:
    """Walk the chain and verify each row hash by recomputation."""

    signer = StaticHMACProvider(secret="repo-test")
    for i in range(5):
        await open_row(
            session,
            OpenRowRequest(
                tenant_id="acme", agent_id="a", skill="s", case_id=f"c-{i}"
            ),
            signer,
        )

    rows = await get_chain(session, tenant_id="acme")
    prev: bytes | None = None
    for r in rows:
        link = compute_row_hash(
            {
                "row_id": str(r.row_id),
                "tenant_id": r.tenant_id,
                "agent_id": r.agent_id,
                "skill": r.skill,
                "case_id": r.case_id,
                "model": r.model,
                "cost_usd": r.cost_usd,
                "predicted_outcome_usd": r.predicted_outcome_usd,
                "actual_outcome_usd": r.actual_outcome_usd,
                "counterfactual_outcome_usd": r.counterfactual_outcome_usd,
                "counterfactual_confidence": r.counterfactual_confidence,
                "counterfactual_method": r.counterfactual_method,
                "lift_usd": r.lift_usd,
                "trust_level": r.trust_level,
                "cosigned_by": r.cosigned_by,
                "cosigned_at": r.cosigned_at,
                "meta": r.meta or {},
                "status": r.status,
                "created_at": r.created_at,
                "closed_at": r.closed_at,
            },
            prev,
        )
        assert link.row_hash == bytes(r.row_hash)
        assert signer.verify(link.row_hash, bytes(r.signature))
        prev = bytes(r.row_hash)
