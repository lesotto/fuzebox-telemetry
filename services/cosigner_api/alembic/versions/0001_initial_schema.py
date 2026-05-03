"""Initial schema: pel_rows, spans, cosign_event_log with RLS.

Revision ID: 0001
Revises:
Create Date: 2026-05-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # TimescaleDB is optional. Create the extension if available; otherwise
    # fall back to plain Postgres tables. Hypertable conversion is conditional.
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')

    op.create_table(
        "pel_rows",
        sa.Column("row_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.Text, nullable=False),
        sa.Column("agent_id", sa.Text, nullable=False),
        sa.Column("skill", sa.Text, nullable=False),
        sa.Column("case_id", sa.Text, nullable=False),
        sa.Column("model", sa.Text),
        sa.Column("cost_usd", sa.Numeric(20, 6), nullable=False, server_default="0"),
        sa.Column("predicted_outcome_usd", sa.Numeric(20, 6)),
        sa.Column("actual_outcome_usd", sa.Numeric(20, 6)),
        sa.Column("counterfactual_outcome_usd", sa.Numeric(20, 6)),
        sa.Column("counterfactual_confidence", sa.Numeric(3, 2)),
        sa.Column("counterfactual_method", sa.Text),
        sa.Column("lift_usd", sa.Numeric(20, 6)),
        sa.Column("trust_level", sa.SmallInteger, nullable=False, server_default="0"),
        sa.Column("cosigned_by", sa.Text),
        sa.Column("cosigned_at", sa.DateTime(timezone=True)),
        sa.Column("prev_hash", sa.LargeBinary),
        sa.Column("row_hash", sa.LargeBinary, nullable=False),
        sa.Column("signature", sa.LargeBinary, nullable=False),
        sa.Column(
            "meta",
            sa.dialects.postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint("row_id", "created_at"),
    )

    op.create_index(
        "idx_pel_rows_meta_gin",
        "pel_rows",
        ["meta"],
        postgresql_using="gin",
    )
    op.create_index(
        "idx_pel_rows_lookup",
        "pel_rows",
        ["tenant_id", "skill", "status", sa.text("created_at DESC")],
    )
    op.create_index(
        "idx_pel_rows_tenant_created",
        "pel_rows",
        ["tenant_id", sa.text("created_at DESC")],
    )

    op.create_table(
        "spans",
        sa.Column("span_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trace_id", sa.Text, nullable=False),
        sa.Column("parent_span_id", sa.dialects.postgresql.UUID(as_uuid=True)),
        sa.Column("row_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.Column(
            "attributes",
            sa.dialects.postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.PrimaryKeyConstraint("span_id", "started_at"),
    )
    op.create_index("idx_spans_row", "spans", ["row_id", "started_at"])
    op.create_index("idx_spans_tenant", "spans", ["tenant_id", "started_at"])

    op.create_table(
        "cosign_event_log",
        sa.Column("event_pk", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.Text, nullable=False),
        sa.Column("adapter", sa.Text, nullable=False),
        sa.Column("event_id", sa.Text, nullable=False),
        sa.Column("row_id", sa.dialects.postgresql.UUID(as_uuid=True)),
        sa.Column("match_status", sa.Text, nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("payload_hash", sa.LargeBinary, nullable=False),
        sa.Column("prev_hash", sa.LargeBinary),
        sa.Column("event_hash", sa.LargeBinary, nullable=False),
        sa.Column("signature", sa.LargeBinary, nullable=False),
        sa.Column(
            "details",
            sa.dialects.postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.PrimaryKeyConstraint("event_pk", "received_at"),
        sa.UniqueConstraint("adapter", "event_id", "received_at", name="uq_cosign_event"),
    )

    # Optional: convert to hypertables when TimescaleDB is present.
    op.execute(
        """
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_extension WHERE extname='timescaledb') THEN
            PERFORM create_hypertable('pel_rows', 'created_at', if_not_exists => TRUE);
            PERFORM create_hypertable('spans', 'started_at', if_not_exists => TRUE);
            PERFORM create_hypertable('cosign_event_log', 'received_at', if_not_exists => TRUE);
          END IF;
        END
        $$;
        """
    )

    # Row level security — every read/write must set app.tenant_id.
    for table in ("pel_rows", "spans", "cosign_event_log"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation ON {table}
            USING (tenant_id = current_setting('app.tenant_id', true))
            WITH CHECK (tenant_id = current_setting('app.tenant_id', true));
            """
        )


def downgrade() -> None:
    for table in ("cosign_event_log", "spans", "pel_rows"):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table};")
        op.drop_table(table)
