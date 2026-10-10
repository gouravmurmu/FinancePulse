"""Record small real provider payloads as test fixtures (run in GitHub Actions,
where providers are reachable). Tests never call providers live.

    python -m jobs.record_fixtures tests/fixtures/recorded
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

YAHOO_SYMBOLS = ["AAPL", "^NSEI", "BTC-USD", "GC=F", "USDINR=X", "RELIANCE.NS"]
COINGECKO_IDS = ["bitcoin", "ethereum", "solana"]
SEC_CIK = "0000320193"  # Apple
SEC_HEADERS = {"User-Agent": "MarketPulse research app (github.com/gouravmurmu/FinancePulse)"}


def main(out_dir: str) -> int:
    import yfinance as yf

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for sym in YAHOO_SYMBOLS:
        frame = yf.Ticker(sym).history(
            period="1mo", interval="1d", auto_adjust=False, actions=False
        )
        safe = sym.replace("^", "idx_").replace("=", "_").replace(".", "_")
        frame.to_csv(out / f"yahoo_{safe}.csv")
        print(sym, len(frame), list(frame.columns), frame.index.dtype)

    res = httpx.get(
        "https://api.coingecko.com/api/v3/coins/markets",
        params={"vs_currency": "usd", "ids": ",".join(COINGECKO_IDS)},
        timeout=20,
    )
    res.raise_for_status()
    (out / "coingecko_markets.json").write_text(json.dumps(res.json(), indent=1))

    res = httpx.get(
        f"https://data.sec.gov/api/xbrl/companyfacts/CIK{SEC_CIK}.json",
        headers=SEC_HEADERS,
        timeout=30,
    )
    res.raise_for_status()
    facts = res.json()
    # Keep a handful of concepts so the fixture stays small.
    keep = {
        "Revenues",
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "NetIncomeLoss",
        "Assets",
        "Liabilities",
        "StockholdersEquity",
        "OperatingIncomeLoss",
        "NetCashProvidedByUsedInOperatingActivities",
        "EarningsPerShareDiluted",
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "LongTermDebtNoncurrent",
        "CashAndCashEquivalentsAtCarryingValue",
        "GrossProfit",
    }
    gaap = facts["facts"].get("us-gaap", {})
    facts["facts"] = {
        "us-gaap": {k: v for k, v in gaap.items() if k in keep},
        "dei": facts["facts"].get("dei", {}),
    }
    (out / "sec_companyfacts_AAPL.json").write_text(json.dumps(facts))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "tests/fixtures/recorded"))
