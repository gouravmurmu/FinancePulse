"""Financial conventions used everywhere. Documented in docs/METHODOLOGY.md."""

from typing import Literal

AssetClass = Literal["equity", "index", "etf", "crypto", "commodity", "fx", "macro"]

TRADING_DAYS_PER_YEAR = 252
CALENDAR_DAYS_PER_YEAR = 365

# Below this many return observations, statistics are reported as undefined
# rather than computed from too little data.
MIN_OBSERVATIONS = 20


def periods_per_year(asset_class: str) -> int:
    """Crypto trades every day; everything else on exchange trading days."""
    return CALENDAR_DAYS_PER_YEAR if asset_class == "crypto" else TRADING_DAYS_PER_YEAR


def mixed_periods_per_year(asset_classes: list[str]) -> int:
    """When series are aligned on common dates, any non-crypto member forces the
    exchange calendar (crypto prices are sampled on exchange trading days)."""
    if asset_classes and all(a == "crypto" for a in asset_classes):
        return CALENDAR_DAYS_PER_YEAR
    return TRADING_DAYS_PER_YEAR
