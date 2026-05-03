"""SQLAlchemy 2 models for ledger tables.

These mirror the canonical schema in `alembic/versions/0001_initial_schema.py`.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
    LargeBinary,
    Numeric,
    SmallInteger,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class PELRow(Base):
    """A signed, hash-chained execution row."""

    __tablename__ = "pel_rows"
    __table_args__ = ({"info": {"timescale_hypertable": "created_at"}},)

    row_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False)
    agent_id: Mapped[str] = mapped_column(Text, nullable=False)
    skill: Mapped[str] = mapped_column(Text, nullable=False)
    case_id: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str | None] = mapped_column(Text)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal("0"))
    predicted_outcome_usd: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    actual_outcome_usd: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    counterfactual_outcome_usd: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    counterfactual_confidence: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    counterfactual_method: Mapped[str | None] = mapped_column(Text)
    lift_usd: Mapped[Decimal | None] = mapped_column(Numeric(20, 6))
    trust_level: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    cosigned_by: Mapped[str | None] = mapped_column(Text)
    cosigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    prev_hash: Mapped[bytes | None] = mapped_column(LargeBinary)
    row_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    signature: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    meta: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, server_default=func.now()
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Span(Base):
    """An OTEL-compatible span attached to a PEL row."""

    __tablename__ = "spans"

    span_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    trace_id: Mapped[str] = mapped_column(Text, nullable=False)
    parent_span_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    row_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, server_default=func.now()
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attributes: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)


class CosignEvent(Base):
    """Signed, hash-chained record of every cosign webhook attempt."""

    __tablename__ = "cosign_event_log"
    __table_args__ = (
        UniqueConstraint("adapter", "event_id", "received_at", name="uq_cosign_event"),
    )

    event_pk: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False)
    adapter: Mapped[str] = mapped_column(Text, nullable=False)
    event_id: Mapped[str] = mapped_column(Text, nullable=False)
    row_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    match_status: Mapped[str] = mapped_column(Text, nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, server_default=func.now()
    )
    payload_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    prev_hash: Mapped[bytes | None] = mapped_column(LargeBinary)
    event_hash: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    signature: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
