"""Row Level Security: one user can never read or change another user's data.

Runs against a real Postgres with the Supabase stub (infra/postgres) loaded:
    TEST_DATABASE_URL=postgresql://postgres@localhost:5432/marketpulse_test pytest -m db
"""

import os
import uuid
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Connection, create_engine, text
from sqlalchemy.exc import DBAPIError

pytestmark = [
    pytest.mark.db,
    pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set"),
]

USER_A = uuid.UUID("00000000-0000-0000-0000-00000000000a")
USER_B = uuid.UUID("00000000-0000-0000-0000-00000000000b")


def _alembic(url: str) -> Config:
    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    os.environ["DATABASE_URL"] = url
    from app.core.config import get_settings

    get_settings.cache_clear()
    return cfg


@pytest.fixture(scope="module")
def engine():
    url = os.environ["TEST_DATABASE_URL"]
    cfg = _alembic(url)
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    eng = create_engine(url.replace("postgresql://", "postgresql+psycopg://", 1))
    with eng.begin() as conn:
        conn.execute(text("delete from auth.users"))
        conn.execute(
            text("insert into auth.users (id, email) values (:a, 'a@x.test'), (:b, 'b@x.test')"),
            {"a": USER_A, "b": USER_B},
        )
        conn.execute(
            text("insert into profiles (id, display_name) values (:a, 'A'), (:b, 'B')"),
            {"a": USER_A, "b": USER_B},
        )
        conn.execute(
            text(
                "insert into instruments (id, name, asset_class, currency, timezone) "
                "values ('crypto:BTC', 'Bitcoin', 'crypto', 'USD', 'UTC')"
            )
        )
    yield eng
    eng.dispose()


def _as(conn: Connection, role: str, user: uuid.UUID | None = None) -> None:
    conn.execute(text(f"set local role {role}"))
    if user is not None:
        conn.execute(text("select set_config('request.jwt.claim.sub', :u, true)"), {"u": str(user)})


@pytest.fixture
def conn(engine) -> Iterator[Connection]:
    with engine.connect() as c:
        tx = c.begin()
        yield c
        tx.rollback()


def test_user_sees_only_own_profile(conn):
    _as(conn, "authenticated", USER_A)
    rows = conn.execute(text("select id from profiles")).scalars().all()
    assert rows == [USER_A]


def test_user_cannot_update_another_profile(conn):
    _as(conn, "authenticated", USER_A)
    result = conn.execute(
        text("update profiles set display_name = 'hacked' where id = :b"), {"b": USER_B}
    )
    assert result.rowcount == 0


def test_user_cannot_delete_another_profile(conn):
    _as(conn, "authenticated", USER_A)
    result = conn.execute(text("delete from profiles where id = :b"), {"b": USER_B})
    assert result.rowcount == 0


def test_user_cannot_insert_row_for_another_user(conn):
    _as(conn, "authenticated", USER_A)
    with pytest.raises(DBAPIError, match="row-level security"):
        conn.execute(
            text("insert into profiles (id) values (:id)"),
            {"id": uuid.UUID("00000000-0000-0000-0000-0000000000cc")},
        )


def test_anonymous_cannot_read_profiles(conn):
    _as(conn, "anon")
    with pytest.raises(DBAPIError, match="permission denied"):
        conn.execute(text("select * from profiles"))


def test_market_data_is_public_read_only(conn):
    _as(conn, "anon")
    assert conn.execute(text("select count(*) from instruments")).scalar_one() == 1
    with pytest.raises(DBAPIError, match="permission denied"):
        conn.execute(
            text(
                "insert into instruments (id, name, asset_class, currency, timezone) "
                "values ('x', 'x', 'crypto', 'USD', 'UTC')"
            )
        )


def test_observation_upsert_key_is_unique(conn):
    insert = text(
        "insert into market_observations (instrument_id, provider, frequency, observed_at, "
        "retrieved_at, currency, close, quote_type) values ('crypto:BTC', 'coingecko', '1d', "
        "'2026-10-09T00:00:00Z', now(), 'USD', :close, 'eod') "
        "on conflict on constraint uq_market_observations_key do update set close = excluded.close"
    )
    conn.execute(insert, {"close": 100})
    conn.execute(insert, {"close": 101})
    rows = conn.execute(text("select close from market_observations")).scalars().all()
    assert [float(r) for r in rows] == [101.0]


# --- portfolios, transactions, watchlists (migration 0004) ---------------------

P_A = uuid.UUID("00000000-0000-0000-0000-0000000001aa")
P_B = uuid.UUID("00000000-0000-0000-0000-0000000001bb")
W_B = uuid.UUID("00000000-0000-0000-0000-0000000002bb")


@pytest.fixture
def user_rows(conn):
    params = {"pa": P_A, "pb": P_B, "wb": W_B, "a": USER_A, "b": USER_B}
    for stmt in (
        "insert into portfolios (id, user_id, name) values (:pa, :a, 'A'), (:pb, :b, 'B')",
        "insert into transactions (id, portfolio_id, user_id, instrument_id, side, trade_date, "
        "quantity, price, currency) values "
        "(gen_random_uuid(), :pb, :b, 'crypto:BTC', 'buy', '2026-01-02', 1, 1, 'USD')",
        "insert into watchlists (id, user_id, name) values (:wb, :b, 'B')",
        "insert into watchlist_items (id, watchlist_id, user_id, instrument_id) values "
        "(gen_random_uuid(), :wb, :b, 'crypto:BTC')",
    ):
        conn.execute(text(stmt), params)


@pytest.mark.parametrize("table", ["portfolios", "transactions", "watchlists", "watchlist_items"])
def test_user_tables_are_owner_only(conn, user_rows, table):
    _as(conn, "authenticated", USER_A)
    owners = conn.execute(text(f"select user_id from {table}")).scalars().all()  # noqa: S608 (fixed table list)
    assert USER_B not in owners
    assert conn.execute(text(f"update {table} set user_id = :a"), {"a": USER_A}).rowcount == len(  # noqa: S608 (fixed table list)
        owners
    )
    assert (
        conn.execute(text(f"delete from {table} where user_id = :b"), {"b": USER_B}).rowcount == 0  # noqa: S608 (fixed table list)
    )


@pytest.mark.parametrize("table", ["portfolios", "transactions", "watchlists", "watchlist_items"])
def test_anonymous_cannot_read_user_tables(conn, table):
    _as(conn, "anon")
    with pytest.raises(DBAPIError, match="permission denied"):
        conn.execute(text(f"select * from {table}"))  # noqa: S608 (fixed table list)


def test_cannot_add_transaction_to_someone_elses_portfolio(conn, user_rows):
    _as(conn, "authenticated", USER_A)
    with pytest.raises(DBAPIError, match="row-level security"):
        conn.execute(
            text(
                "insert into transactions (id, portfolio_id, user_id, instrument_id, side, "
                "trade_date, quantity, price, currency) values (gen_random_uuid(), :pb, :a, "
                "'crypto:BTC', 'buy', '2026-01-02', 1, 1, 'USD')"
            ),
            {"pb": P_B, "a": USER_A},
        )


def test_cannot_add_item_to_someone_elses_watchlist(conn, user_rows):
    _as(conn, "authenticated", USER_A)
    with pytest.raises(DBAPIError, match="row-level security"):
        conn.execute(
            text(
                "insert into watchlist_items (id, watchlist_id, user_id, instrument_id) "
                "values (gen_random_uuid(), :wb, :a, 'crypto:BTC')"
            ),
            {"wb": W_B, "a": USER_A},
        )
