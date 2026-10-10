"""SEC EDGAR company facts (XBRL) for US-listed companies.

Free and official, but SEC's fair-access policy requires a User-Agent that
names a contact email (SEC_CONTACT_EMAIL) and at most 10 requests a second.
Only annual figures from 10-K filings are kept: quarterly XBRL facts mix
three-month and year-to-date durations and are easy to misread.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import httpx

from app.providers.base import ProviderError, finite

PROVIDER = "sec"
BASE_URL = "https://data.sec.gov/api/xbrl/companyfacts"
ANNUAL_FORMS = {"10-K", "10-K/A", "10-KT"}

# Canonical concept -> (us-gaap tags in priority order, unit, kind).
# "duration" facts cover a fiscal year; "instant" facts are year-end balances.
CONCEPTS: dict[str, tuple[tuple[str, ...], str, str]] = {
    "revenue": (
        (
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "Revenues",
            "SalesRevenueNet",
            "RevenueFromContractWithCustomerIncludingAssessedTax",
        ),
        "USD",
        "duration",
    ),
    "gross_profit": (("GrossProfit",), "USD", "duration"),
    "operating_income": (("OperatingIncomeLoss",), "USD", "duration"),
    "net_income": (("NetIncomeLoss", "ProfitLoss"), "USD", "duration"),
    "eps_diluted": (("EarningsPerShareDiluted",), "USD/shares", "duration"),
    "operating_cash_flow": (
        (
            "NetCashProvidedByUsedInOperatingActivities",
            "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
        ),
        "USD",
        "duration",
    ),
    "capex": (("PaymentsToAcquirePropertyPlantAndEquipment",), "USD", "duration"),
    "total_assets": (("Assets",), "USD", "instant"),
    "total_liabilities": (("Liabilities",), "USD", "instant"),
    "equity": (
        (
            "StockholdersEquity",
            "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
        ),
        "USD",
        "instant",
    ),
    "long_term_debt": (("LongTermDebtNoncurrent", "LongTermDebt"), "USD", "instant"),
    "cash": (
        (
            "CashAndCashEquivalentsAtCarryingValue",
            "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
        ),
        "USD",
        "instant",
    ),
}


@dataclass
class FundamentalFact:
    instrument_id: str
    concept: str
    fiscal_year: int
    period_start: date | None
    period_end: date
    value: float
    unit: str
    source_tag: str
    form: str
    filed: date
    accession: str | None
    retrieved_at: datetime


def _d(s: str | None) -> date | None:
    return date.fromisoformat(s) if s else None


def normalize_companyfacts(
    payload: dict[str, Any], instrument_id: str, retrieved_at: datetime, years: int = 6
) -> list[FundamentalFact]:
    gaap: dict[str, Any] = payload.get("facts", {}).get("us-gaap", {})
    out: list[FundamentalFact] = []
    for concept, (tags, unit, kind) in CONCEPTS.items():
        chosen: dict[date, FundamentalFact] = {}
        # Earlier tags win for a given year-end; later tags fill gaps (companies
        # switch tags over time, e.g. after ASC 606 revenue reporting).
        for tag in tags:
            entries = gaap.get(tag, {}).get("units", {}).get(unit, [])
            best: dict[date, FundamentalFact] = {}
            for e in entries:
                if e.get("form") not in ANNUAL_FORMS:
                    continue
                end, start, filed = _d(e.get("end")), _d(e.get("start")), _d(e.get("filed"))
                val = finite(e.get("val"))
                if end is None or filed is None or val is None:
                    continue
                if kind == "duration":
                    if start is None or not 350 <= (end - start).days <= 380:
                        continue
                elif start is not None:
                    continue
                fact = FundamentalFact(
                    instrument_id=instrument_id,
                    concept=concept,
                    fiscal_year=end.year,
                    period_start=start,
                    period_end=end,
                    value=val,
                    unit=unit,
                    source_tag=tag,
                    form=e["form"],
                    filed=filed,
                    accession=e.get("accn"),
                    retrieved_at=retrieved_at,
                )
                prev = best.get(end)
                # Restatements: the most recently filed value wins.
                if prev is None or filed > prev.filed:
                    best[end] = fact
            for end, fact in best.items():
                chosen.setdefault(end, fact)
        latest = sorted(chosen)[-years:]
        out.extend(chosen[e] for e in latest)
    return out


def user_agent() -> str | None:
    contact = os.getenv("SEC_CONTACT_EMAIL", "").strip()
    return f"MarketPulse {contact}" if contact else None


def fetch_companyfacts(cik: int, client: httpx.Client) -> dict[str, Any]:
    ua = user_agent()
    if ua is None:
        raise ProviderError("SEC_CONTACT_EMAIL is not set; SEC requires a contact email")
    res = client.get(
        f"{BASE_URL}/CIK{cik:010d}.json",
        headers={"User-Agent": ua, "Accept": "application/json"},
        timeout=30,
    )
    if res.status_code != 200:
        raise ProviderError(f"SEC returned HTTP {res.status_code} for CIK {cik}")
    data: dict[str, Any] = res.json()
    return data
