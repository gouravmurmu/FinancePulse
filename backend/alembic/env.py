from alembic import context
from sqlalchemy import create_engine, pool

import app.models  # noqa: F401  (registers tables on the metadata)
from app.core.config import get_settings
from app.db.base import Base

target_metadata = Base.metadata


# Foreign keys into Supabase-managed schemas (auth.users) are created in
# migrations but cannot be declared on our metadata.
EXTERNAL_FKS = {
    "fk_profiles_id_users",
    "fk_portfolios_user_id_users",
    "fk_transactions_user_id_users",
    "fk_watchlists_user_id_users",
    "fk_watchlist_items_user_id_users",
    "fk_alert_rules_user_id_users",
    "fk_alert_events_user_id_users",
}


def include_object(
    obj: object, name: str | None, type_: str, reflected: bool, compare_to: object
) -> bool:
    return not (type_ == "foreign_key_constraint" and name in EXTERNAL_FKS)


def _url() -> str:
    url = get_settings().database_url
    if not url:
        raise SystemExit("DATABASE_URL is not set; cannot run migrations.")
    return url


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(
        _url(), poolclass=pool.NullPool, connect_args={"prepare_threshold": None}
    )
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
