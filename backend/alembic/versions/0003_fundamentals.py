"""Annual company fundamentals from SEC EDGAR.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "fundamentals",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column(
            "instrument_id",
            sa.String(64),
            sa.ForeignKey(
                "instruments.id",
                ondelete="CASCADE",
                name="fk_fundamentals_instrument_id_instruments",
            ),
            nullable=False,
        ),
        sa.Column("concept", sa.String(32), nullable=False),
        sa.Column("fiscal_year", sa.Integer, nullable=False),
        sa.Column("period_start", sa.Date),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("value", sa.Numeric(28, 4), nullable=False),
        sa.Column("unit", sa.String(16), nullable=False),
        sa.Column("source_tag", sa.String(128), nullable=False),
        sa.Column("form", sa.String(16), nullable=False),
        sa.Column("filed", sa.Date, nullable=False),
        sa.Column("accession", sa.String(32)),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("instrument_id", "concept", "period_end", name="uq_fundamentals_key"),
    )
    op.execute("alter table fundamentals enable row level security")
    op.execute(
        "create policy fundamentals_public_read on fundamentals "
        "for select to anon, authenticated using (true)"
    )
    op.execute("grant select on fundamentals to anon, authenticated")


def downgrade() -> None:
    op.drop_table("fundamentals")
