# MarketPulse

A multi-asset market research app covering global and Indian equities and
indices, major cryptocurrencies, gold and silver. It runs entirely on free
tiers.

> **Not investment advice.** MarketPulse is a research and education tool.
> Prices may be delayed or end of day; every figure shows its source and as-of time.

## Status

**Build step 2 of 4 done; step 3 in progress (portfolios live).** What works today:
- **Markets**: global and India views, USD/INR display, periods from 1 day to
  5 years, index and asset cards with freshness, growth-of-100 comparison,
  gainers and losers, sector heatmap, exchange open/closed status.
- **Search** (⌘K) and **Research** across 56 instruments.
- **Asset pages**: line and candlestick charts with volume, SMA/EMA/Bollinger,
  RSI and MACD, a risk panel (volatility, Sharpe, Sortino, drawdown, VaR,
  expected shortfall, beta), crypto market stats, gold/silver context, and US
  company financials from SEC filings.
- **Risk Lab**: compare 2 to 8 assets, correlation, rolling correlation,
  drawdowns, a seeded Monte Carlo simulation and stress scenarios.
- Real daily data refreshed twice a day; 5 years of history stored.

- **Accounts** (email and password) with private **portfolios**: buy/sell
  ledger, weighted-average cost, realized and unrealized P&L with the currency
  effect shown separately, allocation, time-weighted performance against a
  benchmark, risk contribution, correlation, stress tests, a rebalancing
  planner and CSV import/export. **Watchlists** on the Markets page.
- **Alerts** on price levels, daily moves, volatility and statistical
  anomalies, checked after each data refresh and shown in the app. Unusual
  activity flags on every asset page.
- **Forecast check** on asset pages: simple baseline models tested walk-forward
  on past data; when none beats "no change", the page says so
  ([docs/MODELS.md](docs/MODELS.md)).

- **News** with source links and FinBERT headline tone for US stocks, ETFs
  and major coins (needs a free Finnhub key).

- **AI assistant** (page and an "Ask AI" panel that knows the asset or
  portfolio you're viewing): the model only plans and explains; every number
  comes from MarketPulse tools, and each statement is labelled as fact,
  computed, model estimate or hypothesis. Free tier via Groq with a daily
  allowance per user (needs `LLM_API_KEY`).

Not built yet: PDF reports (rest of step 3). See [PLAN.md](PLAN.md). See [PLAN.md](PLAN.md).

## Stack
Next.js 15 · React 19 · TypeScript · Tailwind CSS v4 · TanStack Query · Zod ·
FastAPI · Pydantic v2 · SQLAlchemy 2 · Alembic · PostgreSQL (Supabase) ·
GitHub Actions. Hosting: Vercel (web), Render (API), Supabase (database).

## Run locally
```bash
docker compose up --build
# web http://localhost:3000 · api http://localhost:8000/docs
```
Details and native setup: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Tests
```bash
cd frontend && npm test
cd backend && pytest                      # unit tests
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/marketpulse pytest  # + RLS tests
```

## Free-tier limitations
- The API sleeps after 15 idle minutes and takes about a minute to wake.
- The database is capped at 500 MB, so only daily history is stored.
- Vercel Hobby is for non-commercial use.
Full details: [docs/HOSTING.md](docs/HOSTING.md).

## Docs
[PLAN.md](PLAN.md) · [ARCHITECTURE.md](ARCHITECTURE.md) ·
[docs/HOSTING.md](docs/HOSTING.md) · [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) ·
[docs/DESIGN_SYSTEM.md](docs/DESIGN_SYSTEM.md) ·
[docs/DATA_SOURCES.md](docs/DATA_SOURCES.md) · [docs/METHODOLOGY.md](docs/METHODOLOGY.md)
