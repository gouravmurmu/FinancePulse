# Data sources

MarketPulse shows only data it has fetched from a named source. Nothing is
simulated or filled in. When a source fails, the affected numbers show as
"Unavailable" or "Stale" with their last date.

| Data | Source | Access | Refresh | Notes |
|---|---|---|---|---|
| Daily prices (indices, stocks, ETFs, crypto, gold/silver futures, USD/INR) | Yahoo Finance via `yfinance` | Unofficial, no key | 11:00 and 22:30 UTC daily (GitHub Actions) | Delayed or end of day. Can break without notice; failures are logged per instrument in `job_runs`. |
| Crypto market cap, supply, 24h volume | CoinGecko public API | Free; optional Demo key (`COINGECKO_API_KEY`) | With each price refresh | Snapshot only; history comes from Yahoo. |
| US company financials | SEC EDGAR company facts (XBRL) | Free, official; needs a contact email in the User-Agent (`SEC_CONTACT_EMAIL`) | Weekly (Sunday 06:00 UTC) | Annual 10-K figures only. |
| Indian company financials | None | | | No free, reliable source. Pages say "Fundamentals not available". |
| Headlines (US stocks and ETFs; crypto feed matched by coin name or ticker) | Finnhub free tier | Free key (`FINNHUB_API_KEY`) | 10:45 and 22:15 UTC daily | Headline, source, link, time and short summary only; no article text. No Indian or index news on the free tier. |

## Universe
56 curated instruments (`backend/app/data/universe.py`): 8 global and 4 Indian
indices, 15 US and 15 NSE stocks, 8 cryptocurrencies, COMEX gold and silver
futures, GLD, SLV, GOLDBEES, and USD/INR. Each has a stable ID such as
`eq:us:AAPL`, `idx:in:NIFTY50`, `crypto:BTC` or `metal:XAU:comex-fut`;
provider symbols are stored separately as aliases.

## Storage
- `market_observations`: one daily bar per instrument and date (open, high,
  low, close, adjusted close, volume), with provider, retrieval time, quote
  type (`eod` for completed sessions, `delayed` for today's bar) and a quality
  flag.
- `instrument_snapshots`: latest crypto statistics.
- `fundamentals`: one row per company, concept and fiscal-year end, with the
  XBRL tag, form, filing date and accession number it came from.
- `job_runs`: every refresh with per-instrument results.

The 5-year backfill on 10 Oct 2026 loaded 74,486 bars (41 MB including
indexes), well inside Supabase's 500 MB free tier.

## Quality checks
Each bar is checked before it is stored:
- **Rejected** (not stored): a close of zero or below.
- **Suspect** (stored, flagged): high below low; close more than 1% outside the
  day's high-low range; a one-day move over 50% (80% for crypto).

## Freshness
Every number carries a chip:
- **End of day · date**: the last completed session.
- **Delayed**: today's bar while the market is open (about 15 minutes behind).
- **Stale · date**: no new bar for more than 4 days (2 days for crypto).
- **Unavailable**: no data for this instrument.

Nothing in MarketPulse is real-time.

## Known limits
- Exchange holidays are not modelled; an exchange may show "Open" on a holiday.
- Futures and ETF prices differ from Indian retail gold and silver rates, which
  add import duty, GST and dealer premiums.
- `yfinance` scrapes Yahoo's public endpoints and is not an official API.
