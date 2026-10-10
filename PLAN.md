# MarketPulse plan

Source spec: `MarketPulse_Final_Prompt.md` (project files). This plan groups the
spec's six phases into four build steps. The deployed app must keep working
after every step.

## Steps

| Step | Spec phases | Delivers | Status |
|---|---|---|---|
| 1. Foundation and first deploy | 0 | Repo layout, design tokens, app shell, FastAPI service, schema + RLS, CI, hosting verification, live web + API + DB | Done |
| 2. Markets, Research, Risk Lab | 1, 2 | Provider adapters, curated universe, daily refresh job, Markets dashboard, search, asset pages, technicals, fundamentals (where reliable), Risk Lab with tested metrics | Done |
| 3. Portfolio and intelligence | 3, 4 | Auth, ledger, P&L, allocation, RLS tests per table, AI assistant with tools, sentiment/anomaly/forecast jobs, Monte Carlo, alerts, reports | In progress |
| 4. Polish and launch | 5 | Design verification (screenshots, contrast, Lighthouse ≥ 90), accessibility, monitoring, complete docs, final smoke tests | Planned |

## Step 1 acceptance
- [x] Next.js app shell with the six destinations, dark/light themes from tokens
- [x] FastAPI service with health check, error envelope, structured logs, CORS
- [x] Alembic migration with RLS; tests prove users cannot read or change each other's rows
- [x] CI: lint, type-check and tests for web and API; API image build
- [x] Free-tier limits verified and recorded (`docs/HOSTING.md`)
- [x] Web app live on Vercel, API live on Render, database on Supabase
- [x] Live API health check reports the database as connected

## Step 2 acceptance
- [x] Analytics library (returns, risk, technicals, Monte Carlo, stress) tested against hand-calculated values
- [x] 56-instrument universe with canonical IDs; Yahoo and CoinGecko adapters with quality flags
- [x] Twice-daily refresh job; 5-year backfill loaded (74,486 bars, no failures)
- [x] Market, instrument, risk and fundamentals API with seeded-database tests
- [x] Markets dashboard, ⌘K search, Research, asset pages, Risk Lab
- [x] Colour-vision validated chart palette; every chart has a table view
- [x] US fundamentals from SEC (switched on once `SEC_CONTACT_EMAIL` is set)
- [x] `docs/DATA_SOURCES.md` and `docs/METHODOLOGY.md`

## Step 3 parts
Each part ships on its own.
- **3a Sign-in, portfolios, watchlists** (done): Supabase Auth (email + password),
  JWT verification in the API, ledger with weighted-average cost, P&L split into
  price and currency effects, allocation, time-weighted performance vs
  benchmark, risk contribution, correlation, stress, rebalancing planner, CSV
  import/export, watchlists. RLS and API isolation tests per table.
- **3b Alerts and anomaly scans** (done): price, daily-move, volatility and
  anomaly alerts evaluated after each data refresh, in-app history with unread
  badge; robust z-score anomaly scan for return, volume, volatility and
  correlation, shown on asset pages and the Alerts page.
- **3c News, sentiment, forecasts**: forecast baselines (no change, drift,
  damped-trend smoothing) with walk-forward evaluation and a significance test
  against no change, shown on asset pages (`docs/MODELS.md`) (done). Headlines
  with attribution and FinBERT sentiment (done; switched on once
  `FINNHUB_API_KEY` is set).
- **3d AI assistant and reports**: Groq behind a provider interface, tools that
  call backend functions, per-user budget; PDF and CSV reports.

## Key decisions
- **Canonical instrument IDs** are readable strings (`eq:us:AAPL`,
  `crypto:BTC`, `metal:XAU:comex-fut`), never provider symbols. Provider symbols
  live in `instrument_aliases`.
- **Daily bars only** by default to stay inside 500 MB (see `docs/HOSTING.md`).
- **Migrations run on API boot**: Render's free tier has no pre-deploy hook,
  and `alembic upgrade head` is idempotent.
- **No Redis yet**: in-process TTL cache first; Upstash only if needed.
- **The API owns all writes**; Supabase's public endpoints are read-only for
  market data and owner-only for user data (RLS).

## Risks
| Risk | Mitigation |
|---|---|
| Render cold starts (~1 min) | Waking state in UI, retries with backoff, serve stored data |
| Render bandwidth (reported 5 GB/month on Hobby workspaces) | Compact JSON, client caching, no large payloads from the API |
| Supabase pauses after 7 idle days | Daily refresh job writes to the DB |
| yfinance is unofficial and may break | Provider adapter interface, recorded fixtures in tests, honest "unavailable" states |
| Vercel Hobby is non-commercial only | Documented; Cloudflare Pages fallback |
| Free LLM quotas | Per-user budget, app fully usable without AI |
| Supabase free email sender is rate-limited | Clear message on sign-up; custom SMTP (Resend free) before launch |
