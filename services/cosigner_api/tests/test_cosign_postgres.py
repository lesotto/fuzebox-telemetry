"""End-to-end cosign integration test (Postgres-gated).

Exercises the full Sprint 2 demo path:

  open row tagged with stripe_payment_intent_id
    -> apply_cosign(...)
    -> row at trust_level 3
    -> lift_usd populated when counterfactual confidence >= 0.30
"""

from __future__ import annotations

import os
from decimal import Decimal

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from services.cosigner_api.app.ledger.cosign import apply_cosign
from services.cosigner_api.app.ledger.models import Base, CosignEvent
from services.cosigner_api.app.ledger.repo import OpenRowRequest, open_row
from services.cosigner_api.app.ledger.signing import StaticHMACProvider

PG_URL = os.getenv("FUZEBOX_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not PG_URL, reason="set FUZEBOX_TEST_DATABASE_URL to run")


@pytest.fixture
async def session() -> AsyncSession:
    engine = create_async_engine(PG_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
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


async def test_cosign_matches_open_row_and_bumps_to_t3(session: AsyncSession) -> None:
    signer = StaticHMACProvider(secret="cosign-test")

    row = await open_row(
        session,
        OpenRowRequest(
            tenant_id="acme",
            agent_id="claims-bot",
            skill="claims_triage",
            case_id="c1",
            meta={"stripe_payment_intent_id": "pi_xyz"},
        ),
        signer,
    )
    # Pretend the miner already populated a counterfactual at high confidence.
    row.counterfactual_outcome_usd = Decimal("40.00")
    row.counterfactual_confidence = Decimal("0.85")
    await session.flush()

    matched, event = await apply_cosign(
        session,
        tenant_id="acme",
        adapter="stripe",
        event_id="evt_1",
        match_key=("stripe_payment_intent_id", "pi_xyz"),
        actual_outcome_usd=Decimal("50.00"),
        cosigned_by="stripe",
        payload={"id": "evt_1"},
        signer=signer,
    )

    assert matched is not None
    assert matched.trust_level == 3
    assert matched.actual_outcome_usd == Decimal("50.00")
    assert matched.cosigned_by == "stripe"
    assert matched.lift_usd == Decimal("10.00")
    assert event.match_status == "matched"
    assert signer.verify(matched.row_hash, bytes(matched.signature))
    assert signer.verify(event.event_hash, bytes(event.signature))


async def test_cosign_unmatched_records_audit(session: AsyncSession) -> None:
    signer = StaticHMACProvider(secret="cosign-test")
    matched, event = await apply_cosign(
        session,
        tenant_id="acme",
        adapter="stripe",
        event_id="evt_orphan",
        match_key=("stripe_payment_intent_id", "pi_nope"),
        actual_outcome_usd=Decimal("10.00"),
        cosigned_by="stripe",
        payload={"id": "evt_orphan"},
        signer=signer,
    )
    assert matched is None
    assert event.match_status == "unmatched"
    assert signer.verify(event.event_hash, bytes(event.signature))


async def test_cosign_idempotent_on_replay(session: AsyncSession) -> None:
    signer = StaticHMACProvider(secret="cosign-test")
    await open_row(
        session,
        OpenRowRequest(
            tenant_id="acme",
            agent_id="a",
            skill="s",
            case_id="c",
            meta={"stripe_payment_intent_id": "pi_dup"},
        ),
        signer,
    )
    a_row, a_event = await apply_cosign(
        session,
        tenant_id="acme",
        adapter="stripe",
        event_id="evt_dup",
        match_key=("stripe_payment_intent_id", "pi_dup"),
        actual_outcome_usd=Decimal("1.00"),
        cosigned_by="stripe",
        payload={"id": "evt_dup"},
        signer=signer,
    )
    b_row, b_event = await apply_cosign(
        session,
        tenant_id="acme",
        adapter="stripe",
        event_id="evt_dup",
        match_key=("stripe_payment_intent_id", "pi_dup"),
        actual_outcome_usd=Decimal("1.00"),
        cosigned_by="stripe",
        payload={"id": "evt_dup"},
        signer=signer,
    )
    assert a_event.event_pk == b_event.event_pk
    # Only one log entry exists.
    count = await session.execute(select(CosignEvent))
    assert len(list(count.scalars().all())) == 1
    assert b_row is not None and a_row is not None
    assert b_row.row_id == a_row.row_id


async def test_lift_skipped_below_confidence(session: AsyncSession) -> None:
    signer = StaticHMACProvider(secret="cosign-test")
    row = await open_row(
        session,
        OpenRowRequest(
            tenant_id="acme",
            agent_id="a",
            skill="s",
            case_id="c",
            meta={"stripe_payment_intent_id": "pi_low"},
        ),
        signer,
    )
    row.counterfactual_outcome_usd = Decimal("40.00")
    row.counterfactual_confidence = Decimal("0.20")  # below threshold
    await session.flush()

    matched, _event = await apply_cosign(
        session,
        tenant_id="acme",
        adapter="stripe",
        event_id="evt_low",
        match_key=("stripe_payment_intent_id", "pi_low"),
        actual_outcome_usd=Decimal("50.00"),
        cosigned_by="stripe",
        payload={"id": "evt_low"},
        signer=signer,
    )
    assert matched is not None
    assert matched.lift_usd is None
    assert matched.trust_level == 3


async def test_chain_audit_log_links(session: AsyncSession) -> None:
    """Two consecutive cosigns chain through the audit log."""

    signer = StaticHMACProvider(secret="cosign-test")
    for i in range(2):
        await apply_cosign(
            session,
            tenant_id="acme",
            adapter="stripe",
            event_id=f"evt_{i}",
            match_key=("stripe_payment_intent_id", f"pi_{i}"),
            actual_outcome_usd=Decimal("1.00"),
            cosigned_by="stripe",
            payload={"id": f"evt_{i}"},
            signer=signer,
        )
    events = list(
        (
            await session.execute(
                select(CosignEvent).order_by(CosignEvent.received_at.asc())
            )
        )
        .scalars()
        .all()
    )
    assert len(events) == 2
    assert events[0].prev_hash is None
    assert events[1].prev_hash == events[0].event_hash
