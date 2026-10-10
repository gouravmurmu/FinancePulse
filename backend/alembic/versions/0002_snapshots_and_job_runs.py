"""Instrument snapshots (crypto market stats) and job run log.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "instrument_snapshots",
        sa.Column(
            "instrument_id",
            sa.String(64),
            sa.ForeignKey(
                "instruments.id",
                ondelete="CASCADE",
                name="fk_instrument_snapshots_instrument_id_instruments",
            ),
            primary_key=True,
        ),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("price", sa.Numeric(24, 8)),
        sa.Column("market_cap", sa.Numeric(28, 2)),
        sa.Column("circulating_supply", sa.Numeric(28, 4)),
        sa.Column("total_supply", sa.Numeric(28, 4)),
        sa.Column("max_supply", sa.Numeric(28, 4)),
        sa.Column("volume_24h", sa.Numeric(28, 2)),
    )
    op.create_table(
        "job_runs",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("job", sa.String(64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("details", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.CheckConstraint(
            "status in ('running', 'success', 'partial', 'failed')", name="ck_job_runs_status"
        ),
    )
    op.create_index("ix_job_runs_job_started", "job_runs", ["job", "started_at"])

    op.execute("alter table instrument_snapshots enable row level security")
    op.execute(
        "create policy instrument_snapshots_public_read on instrument_snapshots "
        "for select to anon, authenticated using (true)"
    )
    op.execute("grant select on instrument_snapshots to anon, authenticated")
    # Internal table: RLS on with no policies, so the public API keys see nothing.
    op.execute("alter table job_runs enable row level security")
    op.execute("alter table alembic_version enable row level security")


def downgrade() -> None:
    op.drop_table("job_runs")
    op.drop_table("instrument_snapshots")
