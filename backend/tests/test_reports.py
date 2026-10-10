"""Reports: valid PDFs and CSVs from stored data; portfolio reports stay private."""

import csv
import io
from datetime import UTC, datetime, timedelta

from tests.test_assistant import USER_A, USER_B, app_env, auth  # noqa: F401 (fixture)


def _portfolio_with_apple(c):
    pid = c.post("/api/v1/portfolios", headers=auth(), json={"name": "Report test"}).json()["id"]
    d = datetime.now(UTC).date() - timedelta(days=20)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    r = c.post(
        f"/api/v1/portfolios/{pid}/transactions",
        headers=auth(),
        json={
            "instrument_id": "eq:us:AAPL",
            "side": "buy",
            "trade_date": d.isoformat(),
            "quantity": 3,
            "price": 150,
            "unit": "unit",
            "fees": 0,
        },
    )
    assert r.status_code == 201, r.text
    return pid


def test_asset_report_pdf_and_csv(app_env):  # noqa: F811
    c = app_env["client"]
    r = c.get("/api/v1/reports/asset/eq:us:AAPL/pdf")
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF") and len(r.content) > 2000
    assert 'filename="eq-us-aapl-' in r.headers["content-disposition"]

    r = c.get("/api/v1/reports/asset/eq:us:AAPL/csv?period=1M")
    assert r.status_code == 200
    rows = list(csv.DictReader(io.StringIO(r.text)))
    assert rows and float(rows[-1]["close"]) == app_env["last"]
    assert rows[-1]["currency"] == "USD"

    assert c.get("/api/v1/reports/asset/nope:X/pdf").status_code == 404
    # No stored prices: a clear error rather than an empty document.
    r = c.get("/api/v1/reports/asset/eq:us:MSFT/pdf")
    assert r.status_code == 404 and r.json()["error"]["code"] == "no_data"


def test_portfolio_report_is_private(app_env):  # noqa: F811
    c = app_env["client"]
    pid = _portfolio_with_apple(c)
    assert c.get(f"/api/v1/reports/portfolio/{pid}/pdf").status_code == 401
    assert c.get(f"/api/v1/reports/portfolio/{pid}/pdf", headers=auth(USER_B)).status_code == 404
    assert c.get(f"/api/v1/reports/portfolio/{pid}/csv", headers=auth(USER_B)).status_code == 404

    r = c.get(f"/api/v1/reports/portfolio/{pid}/pdf", headers=auth(USER_A))
    assert r.status_code == 200, r.text
    assert r.content.startswith(b"%PDF")
    assert r.headers["cache-control"] == "private, no-store"

    r = c.get(f"/api/v1/reports/portfolio/{pid}/csv", headers=auth(USER_A))
    rows = list(csv.DictReader(io.StringIO(r.text)))
    assert len(rows) == 1
    assert rows[0]["instrument_id"] == "eq:us:AAPL" and float(rows[0]["quantity"]) == 3
    assert float(rows[0]["value_usd"]) == 3 * app_env["last"]


def test_empty_portfolio_report_is_refused(app_env):  # noqa: F811
    c = app_env["client"]
    pid = c.post("/api/v1/portfolios", headers=auth(), json={"name": "Empty"}).json()["id"]
    r = c.get(f"/api/v1/reports/portfolio/{pid}/pdf", headers=auth())
    assert r.status_code == 422 and r.json()["error"]["code"] == "empty_portfolio"
