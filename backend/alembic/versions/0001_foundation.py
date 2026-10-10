"""Foundation schema: instruments, aliases, market observations, profiles + RLS.

Revision ID: 0001
Revises:
Create Date: 2026-10-10

Assumes Supabase's `auth` schema, `auth.uid()` and the `anon` / `authenticated`
roles exist. For plain Postgres (local dev, CI) these are stubbed by
infra/postgres/00-supabase-stub.sql.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "instruments",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("asset_class", sa.String(16), nullable=False),
        sa.Column("exchange", sa.String(32)),
        sa.Column("country", sa.String(2)),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("price_definition", sa.String(200)),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("attributes", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "asset_class in ('equity', 'index', 'etf', 'crypto', 'commodity', 'fx', 'macro')",
            name="ck_instruments_asset_class",
        ),
    )

    op.create_table(
        "instrument_aliases",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column(
            "instrument_id",
            sa.String(64),
            sa.ForeignKey(
                "instruments.id",
                ondelete="CASCADE",
                name="fk_instrument_aliases_instrument_id_instruments",
            ),
            nullable=False,
        ),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("alias", sa.String(100), nullable=False),
        sa.UniqueConstraint("provider", "alias", name="uq_instrument_aliases_provider_alias"),
    )
    op.create_index("ix_instrument_aliases_instrument_id", "instrument_aliases", ["instrument_id"])
    # Case-insensitive alias search.
    op.execute(
        "create index ix_instrument_aliases_alias_lower on instrument_aliases (lower(alias))"
    )

    op.create_table(
        "market_observations",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column(
            "instrument_id",
            sa.String(64),
            sa.ForeignKey(
                "instruments.id",
                ondelete="CASCADE",
                name="fk_market_observations_instrument_id_instruments",
            ),
            nullable=False,
        ),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("frequency", sa.String(8), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("open", sa.Numeric(24, 8)),
        sa.Column("high", sa.Numeric(24, 8)),
        sa.Column("low", sa.Numeric(24, 8)),
        sa.Column("close", sa.Numeric(24, 8), nullable=False),
        sa.Column("adj_close", sa.Numeric(24, 8)),
        sa.Column("volume", sa.Numeric(28, 4)),
        sa.Column("quote_type", sa.String(16), nullable=False),
        sa.Column("quality_status", sa.String(16), nullable=False, server_default="ok"),
        sa.Column("provenance", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.UniqueConstraint(
            "instrument_id",
            "observed_at",
            "provider",
            "frequency",
            name="uq_market_observations_key",
        ),
        sa.CheckConstraint(
            "quote_type in ('live', 'delayed', 'eod', 'historical')",
            name="ck_market_observations_quote_type",
        ),
        sa.CheckConstraint(
            "quality_status in ('ok', 'suspect', 'rejected')",
            name="ck_market_observations_quality_status",
        ),
        sa.CheckConstraint("frequency in ('1d')", name="ck_market_observations_frequency"),
    )
    op.create_index(
        "ix_market_observations_lookup",
        "market_observations",
        ["instrument_id", "frequency", "observed_at"],
    )

    op.create_table(
        "profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("display_name", sa.String(100)),
        sa.Column("base_currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("region", sa.String(8), nullable=False, server_default="global"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("base_currency in ('USD', 'INR')", name="ck_profiles_base_currency"),
        sa.CheckConstraint("region in ('global', 'india')", name="ck_profiles_region"),
    )
    op.execute(
        "alter table profiles add constraint fk_profiles_id_users "
        "foreign key (id) references auth.users (id) on delete cascade"
    )

    # --- Row Level Security -------------------------------------------------
    # The API connects as the table owner and bypasses RLS; these policies
    # protect direct access through Supabase's public REST/realtime endpoints.

    # Reference and market data: anyone may read, nobody may write via the API keys.
    for table in ("instruments", "instrument_aliases", "market_observations"):
        op.execute(f"alter table {table} enable row level security")
        op.execute(
            f"create policy {table}_public_read on {table} "
            "for select to anon, authenticated using (true)"
        )

    # User-owned data: each user sees and changes only their own row.
    op.execute("alter table profiles enable row level security")
    op.execute(
        "create policy profiles_select_own on profiles for select to authenticated "
        "using ((select auth.uid()) = id)"
    )
    op.execute(
        "create policy profiles_insert_own on profiles for insert to authenticated "
        "with check ((select auth.uid()) = id)"
    )
    op.execute(
        "create policy profiles_update_own on profiles for update to authenticated "
        "using ((select auth.uid()) = id) with check ((select auth.uid()) = id)"
    )
    op.execute(
        "create policy profiles_delete_own on profiles for delete to authenticated "
        "using ((select auth.uid()) = id)"
    )
    op.execute("grant select, insert, update, delete on profiles to authenticated")
    op.execute(
        "grant select on instruments, instrument_aliases, market_observations "
        "to anon, authenticated"
    )


def downgrade() -> None:
    op.drop_table("profiles")
    op.drop_table("market_observations")
    op.drop_table("instrument_aliases")
    op.drop_table("instruments")
