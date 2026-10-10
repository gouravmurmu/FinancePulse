# MarketPulse

A multi-asset market research app covering global and Indian equities and
indices, major cryptocurrencies, gold and silver. It runs entirely on free
tiers.

> **Not investment advice.** MarketPulse is a research and education tool.
> Prices may be delayed or end of day; every figure shows its source and as-of time.

## Status

**Live:** https://marketpulse-grv4.vercel.app (API docs: https://marketpulse-api-kp70.onrender.com/docs). All four build steps are done. What works today:
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

- **Reports**: PDF reports for any asset (price, risk, forecast check,
  unusual activity, headlines, SEC financials) and for your portfolio
  (holdings, allocation, performance vs benchmark, risk contribution, stress
  scenarios), plus price and holdings CSVs. Every report lists its sources
  and methodology.

- **Simple / Pro view** in the header: Simple shows the key numbers with
  explanations; Pro adds moving averages, RSI/MACD, Sortino, expected
  shortfall, rolling statistics and forecast model tables.

## What needs an API key
Everything works without these; each feature says plainly when it is off.
| Feature | Key | Where it goes |
|---|---|---|
| AI assistant | `LLM_API_KEY` (free Groq key) | Render environment |
| News and headline tone | `FINNHUB_API_KEY` (free) | GitHub Actions secret |
| US company financials | `SEC_CONTACT_EMAIL` (no key, just a contact) | GitHub Actions secret |
| Higher crypto rate limit | `COINGECKO_API_KEY` (optional) | GitHub Actions secret |

## How fresh the data is
- Prices are **end-of-day daily closes**, refreshed at 11:00 and 22:30 UTC
  from Yahoo Finance (unofficial) and CoinGecko. Nothing is real-time; every
  number carries an "End of day · date" chip, and stale data turns amber.
- Five years of daily history; SEC financials weekly; headlines twice a day;
  forecasts and anomaly scans daily after the refresh.
- Alerts are checked after each refresh and appear in the app (no email or push).

## Free-tier limitations
- The API sleeps after 15 idle minutes and takes about a minute to wake; the
  app shows a "waking up" state and retries.
- The database is capped at 500 MB, so only daily bars are stored.
- AI answers are capped at 25 questions per user per day (shared daily cap
  under Groq's free quota). Reports, simulations and the assistant are rate
  limited per visitor.
- Supabase's built-in email sender allows only a few sign-up emails per hour
  until custom SMTP is configured.
- Vercel Hobby is for non-commercial use.
Full details: [docs/HOSTING.md](docs/HOSTING.md).

## Not supported
Intraday or real-time prices, order execution or broker links, options and
futures analytics, dividends and corporate actions in portfolios (enter them
as transactions), fundamentals outside US filers, push or email alerts, and
news for non-US stocks (the free source has no coverage).

## Screenshots
Every main page in dark and light themes at 1440 px and 390 px:
[docs/screenshots](docs/screenshots). They were captured from a local build
with **synthetic demo prices**, not live data.

## Monitoring
`/api/v1/health` (API and database) and `/api/v1/status` (whether each
scheduled job is on time). The **Live smoke test** workflow checks both and
loads key pages every day after the morning refresh; a failure sends GitHub's
failed-workflow email.

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
cd frontend && npm run e2e                # Playwright, against a seeded local stack (see CI)
E2E_BASE_URL=https://marketpulse-grv4.vercel.app E2E_API_URL=https://marketpulse-api-kp70.onrender.com npm run smoke
```

## Docs
[PLAN.md](PLAN.md) · [ARCHITECTURE.md](ARCHITECTURE.md) ·
[docs/HOSTING.md](docs/HOSTING.md) · [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) ·
[docs/DESIGN_SYSTEM.md](docs/DESIGN_SYSTEM.md) ·
[docs/DATA_SOURCES.md](docs/DATA_SOURCES.md) · [docs/METHODOLOGY.md](docs/METHODOLOGY.md) ·
[docs/MODELS.md](docs/MODELS.md)
