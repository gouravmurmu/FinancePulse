"""CoinGecko public/Demo API: market cap, supply and 24h volume for crypto.

Daily price history comes from Yahoo (CoinGecko's free tier limits history to
365 days). Set COINGECKO_API_KEY to use a free Demo key (higher rate limit).
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any

import httpx

from app.data.universe import InstrumentDef
from app.providers.base import ProviderError, Snapshot, finite

PROVIDER = "coingecko"
BASE_URL = "https://api.coingecko.com/api/v3"


def normalize_markets(
    payload: list[dict[str, Any]], instruments: list[InstrumentDef], retrieved_at: datetime
) -> list[Snapshot]:
    by_cg = {i.aliases[PROVIDER]: i for i in instruments if PROVIDER in i.aliases}
    out: list[Snapshot] = []
    for row in payload:
        inst = by_cg.get(row.get("id", ""))
        if inst is None:
            continue
        last = row.get("last_updated")
        as_of = datetime.fromisoformat(last.replace("Z", "+00:00")) if last else retrieved_at
        out.append(
            Snapshot(
                instrument_id=inst.id,
                provider=PROVIDER,
                as_of=as_of,
                retrieved_at=retrieved_at,
                price=finite(row.get("current_price")),
                market_cap=finite(row.get("market_cap")),
                circulating_supply=finite(row.get("circulating_supply")),
                total_supply=finite(row.get("total_supply")),
                max_supply=finite(row.get("max_supply")),
                volume_24h=finite(row.get("total_volume")),
            )
        )
    return out


def fetch_markets(
    instruments: list[InstrumentDef], retrieved_at: datetime, client: httpx.Client | None = None
) -> list[Snapshot]:
    ids = [i.aliases[PROVIDER] for i in instruments if PROVIDER in i.aliases]
    if not ids:
        return []
    headers = {"Accept": "application/json"}
    if key := os.getenv("COINGECKO_API_KEY"):
        headers["x-cg-demo-api-key"] = key
    owns = client is None
    client = client or httpx.Client(timeout=20)
    try:
        res = client.get(
            f"{BASE_URL}/coins/markets",
            params={"vs_currency": "usd", "ids": ",".join(ids), "per_page": 250},
            headers=headers,
        )
        if res.status_code == 429:
            raise ProviderError("coingecko rate limited (429)")
        res.raise_for_status()
        return normalize_markets(res.json(), instruments, retrieved_at)
    except httpx.HTTPError as exc:
        raise ProviderError(f"coingecko: {exc}") from exc
    finally:
        if owns:
            client.close()
