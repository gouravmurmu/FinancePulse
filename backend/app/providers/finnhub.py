"""Finnhub free tier: company news for US stocks and ETFs, plus the crypto
news feed matched to coins by name or ticker. Needs FINNHUB_API_KEY.

Only headline, source, URL, time and the provider's short summary are kept,
never article text. Every item links back to its source.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

import httpx

from app.data.universe import InstrumentDef
from app.providers.base import ProviderError

PROVIDER = "finnhub"
BASE_URL = "https://finnhub.io/api/v1"
SUMMARY_MAX = 500


@dataclass
class NewsItem:
    provider_id: str
    published_at: datetime
    source: str
    headline: str
    summary: str | None
    url: str
    instrument_ids: set[str] = field(default_factory=set)


def api_key() -> str | None:
    return os.getenv("FINNHUB_API_KEY") or None


def company_symbol(inst: InstrumentDef) -> str | None:
    """Finnhub's free company news covers North American listings only."""
    if inst.asset_class in ("equity", "etf") and inst.country == "US":
        return inst.aliases.get("yfinance")
    return None


def _clean(text: Any, limit: int) -> str | None:
    if not isinstance(text, str):
        return None
    t = re.sub(r"\s+", " ", text).strip()
    return t[:limit] if t else None


def normalize(rows: list[dict[str, Any]], instrument_ids: set[str]) -> list[NewsItem]:
    out: list[NewsItem] = []
    for r in rows:
        headline = _clean(r.get("headline"), 400)
        url = r.get("url")
        ts = r.get("datetime")
        if not headline or not isinstance(url, str) or not url.startswith("http"):
            continue
        if not isinstance(ts, int | float) or ts <= 0:
            continue
        out.append(
            NewsItem(
                provider_id=str(r.get("id") or url),
                published_at=datetime.fromtimestamp(ts, UTC),
                source=_clean(r.get("source"), 80) or "Unknown source",
                headline=headline,
                summary=_clean(r.get("summary"), SUMMARY_MAX),
                url=url[:1000],
                instrument_ids=set(instrument_ids),
            )
        )
    return out


def crypto_matchers(instruments: list[InstrumentDef]) -> dict[str, re.Pattern[str]]:
    """Coin names match case-insensitively; tickers only in capitals (so "SOL"
    matches but "sol" does not)."""
    out: dict[str, re.Pattern[str]] = {}
    for i in instruments:
        if i.asset_class != "crypto":
            continue
        ticker = i.id.split(":", 1)[1]
        names = {i.name, *(s for s in i.search if s.upper() != s)}
        pattern = "|".join(
            [rf"(?i:\b{re.escape(n)}\b)" for n in sorted(names)] + [rf"\b{re.escape(ticker)}\b"]
        )
        out[i.id] = re.compile(pattern)
    return out


def tag_crypto(items: list[NewsItem], matchers: dict[str, re.Pattern[str]]) -> list[NewsItem]:
    for item in items:
        text = f"{item.headline} {item.summary or ''}"
        item.instrument_ids |= {iid for iid, rx in matchers.items() if rx.search(text)}
    return [i for i in items if i.instrument_ids]


def _get(client: httpx.Client, path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    key = api_key()
    if not key:
        raise ProviderError("FINNHUB_API_KEY is not set")
    try:
        res = client.get(f"{BASE_URL}{path}", params=params, headers={"X-Finnhub-Token": key})
    except httpx.HTTPError as exc:
        raise ProviderError(f"finnhub: {exc}") from exc
    if res.status_code == 429:
        raise ProviderError("finnhub rate limited (429)")
    if res.status_code in (401, 403):
        raise ProviderError(f"finnhub rejected the API key ({res.status_code})")
    if res.status_code >= 400:
        raise ProviderError(f"finnhub HTTP {res.status_code}")
    data = res.json()
    if not isinstance(data, list):
        raise ProviderError("finnhub returned an unexpected payload")
    return data


def fetch_company_news(
    client: httpx.Client, inst: InstrumentDef, start: date, end: date
) -> list[NewsItem]:
    sym = company_symbol(inst)
    if not sym:
        return []
    rows = _get(
        client,
        "/company-news",
        {"symbol": sym, "from": start.isoformat(), "to": end.isoformat()},
    )
    return normalize(rows, {inst.id})


def fetch_crypto_news(client: httpx.Client, instruments: list[InstrumentDef]) -> list[NewsItem]:
    rows = _get(client, "/news", {"category": "crypto"})
    return tag_crypto(normalize(rows, set()), crypto_matchers(instruments))
