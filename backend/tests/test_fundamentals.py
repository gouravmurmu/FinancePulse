"""SEC company facts normalization and the fundamentals endpoint."""

import os
from datetime import UTC, date, datetime

import pytest

from app.providers.sec import normalize_companyfacts

NOW = datetime(2026, 10, 10, tzinfo=UTC)


def fact(start, end, val, form="10-K", filed="2025-11-01", fp="FY", accn="0000320193-25-000079"):
    e = {"end": end, "val": val, "form": form, "filed": filed, "fp": fp, "accn": accn, "fy": 2025}
    if start:
        e["start"] = start
    return e


PAYLOAD = {
    "cik": 320193,
    "entityName": "Apple Inc.",
    "facts": {
        "us-gaap": {
            "RevenueFromContractWithCustomerExcludingAssessedTax": {
                "units": {
                    "USD": [
                        fact("2023-10-01", "2024-09-28", 391_035e6, filed="2024-11-01"),
                        # Same year repeated as a comparative in the next 10-K (later filing wins)
                        fact("2023-10-01", "2024-09-28", 391_000e6, filed="2025-11-01"),
                        fact("2024-09-29", "2025-09-27", 416_161e6),
                        # Quarter from a 10-Q: ignored
                        fact("2025-06-29", "2025-09-27", 102_466e6, form="10-Q", fp="Q4"),
                        # Year-to-date in a 10-K but not a full year: ignored
                        fact("2025-03-30", "2025-09-27", 200_000e6),
                    ]
                }
            },
            # Older tag only covers an earlier year: fills the gap
            "SalesRevenueNet": {
                "units": {"USD": [fact("2016-09-25", "2017-09-30", 229_234e6, filed="2017-11-03")]}
            },
            "NetIncomeLoss": {
                "units": {
                    "USD": [
                        fact("2023-10-01", "2024-09-28", 93_736e6),
                        fact("2024-09-29", "2025-09-27", 112_010e6),
                    ]
                }
            },
            "EarningsPerShareDiluted": {
                "units": {"USD/shares": [fact("2024-09-29", "2025-09-27", 7.46)]}
            },
            "Assets": {
                "units": {
                    "USD": [
                        fact(None, "2025-09-27", 359_241e6),
                        # A duration value under an instant concept is malformed: ignored
                        fact("2024-09-29", "2025-09-27", 1.0),
                    ]
                }
            },
            "GrossProfit": {"units": {"USD": [fact("2024-09-29", "2025-09-27", "NaN")]}},
        }
    },
}


def by(facts, concept):
    return {f.period_end: f for f in facts if f.concept == concept}


def test_annual_facts_only_and_restatement_wins():
    facts = normalize_companyfacts(PAYLOAD, "eq:us:AAPL", NOW)
    rev = by(facts, "revenue")
    assert set(rev) == {date(2017, 9, 30), date(2024, 9, 28), date(2025, 9, 27)}
    assert rev[date(2024, 9, 28)].value == 391_000e6
    assert rev[date(2024, 9, 28)].filed == date(2025, 11, 1)
    assert rev[date(2025, 9, 27)].value == 416_161e6
    assert rev[date(2017, 9, 30)].source_tag == "SalesRevenueNet"
    assert rev[date(2025, 9, 27)].fiscal_year == 2025


def test_units_instants_and_non_finite():
    facts = normalize_companyfacts(PAYLOAD, "eq:us:AAPL", NOW)
    assert by(facts, "eps_diluted")[date(2025, 9, 27)].unit == "USD/shares"
    assets = by(facts, "total_assets")
    assert list(assets) == [date(2025, 9, 27)] and assets[date(2025, 9, 27)].value == 359_241e6
    assert by(facts, "gross_profit") == {}


def test_keeps_latest_years_only():
    facts = normalize_companyfacts(PAYLOAD, "eq:us:AAPL", NOW, years=2)
    assert set(by(facts, "revenue")) == {date(2024, 9, 28), date(2025, 9, 27)}


@pytest.mark.db
@pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"), reason="TEST_DATABASE_URL not set")
def test_fundamentals_endpoint():
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
    from fastapi.testclient import TestClient

    from app.core.config import Settings, get_settings
    from app.data.universe import UNIVERSE
    from app.db.session import _session_factory, get_engine
    from app.main import create_app
    from app.services import cache, market_store

    for f in (get_settings, get_engine, _session_factory):
        f.cache_clear()
    cache.clear()
    from alembic import command
    from alembic.config import Config

    command.upgrade(Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini")), "head")
    with _session_factory()() as s:
        market_store.sync_universe(s, UNIVERSE)
        market_store.upsert_fundamentals(s, normalize_companyfacts(PAYLOAD, "eq:us:AAPL", NOW))
        s.commit()
    client = TestClient(create_app(Settings()))

    body = client.get("/api/v1/instruments/eq:us:AAPL/fundamentals").json()
    assert body["available"] is True
    last = body["years"][-1]
    assert last["fiscal_year"] == 2025
    assert last["net_margin"] == pytest.approx(112_010 / 416_161)
    assert last["revenue_growth"] == pytest.approx(416_161 / 391_000 - 1)
    assert last["gross_margin"] is None
    first = body["years"][0]
    assert first["fiscal_year"] == 2017 and first["revenue_growth"] is None
    assert body["years"][1]["revenue_growth"] is None  # 2017 -> 2024 is not consecutive
    assert body["last_filed"] == "2025-11-01"

    india = client.get("/api/v1/instruments/eq:in:TCS/fundamentals").json()
    assert india["available"] is False and "US-listed" in india["reason"]
