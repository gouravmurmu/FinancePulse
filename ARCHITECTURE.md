# Architecture

```
 Browser ──HTTPS──▶ Vercel (Next.js web app)
    │
    └──HTTPS (CORS)──▶ Render (FastAPI, Docker, slim)
                          │
                          └──Postgres (session pooler)──▶ Supabase (Postgres, Auth, RLS)
                                                             ▲
 GitHub Actions cron (data refresh, ML batch jobs) ──────────┘
```

- The browser never calls data providers or the database directly for app data;
  it calls the API. Supabase Auth issues JWTs; the browser sends them as a
  Bearer token and the API verifies them against the project's public keys
  (JWKS). The API connects as the table owner, so every user-data query also
  filters on the verified user id; RLS protects Supabase's public endpoints.
- The API serves stored data and computes analytics on demand. It never loads
  ML libraries.
- Batch jobs share the backend codebase (`backend/jobs/`) with a heavier
  requirements file and write results to Postgres.

## Repository layout

```
frontend/            Next.js App Router, TypeScript strict, Tailwind v4 tokens
  src/app/           routes (Markets, Research, Risk Lab, Portfolio, AI Assistant, Alerts)
  src/components/    ui/ (Card, MetricCard, FreshnessChip, states), layout/, system/
  src/lib/           api client (zod-validated), formatting, config
backend/
  app/core/          settings, JSON logging, error envelope
  app/db/            engine/session, declarative base
  app/models/        SQLAlchemy models
  app/api/v1/        versioned routers
  app/schemas/       Pydantic response models
  alembic/           migrations (RLS policies live here)
  jobs/              batch jobs (step 2+)
  tests/             pytest, incl. RLS isolation tests
infra/postgres/      Supabase auth stub for plain Postgres (local, CI)
docs/                hosting, deployment, design system, later data sources and methodology
```

## API conventions
- Versioned under `/api/v1`; OpenAPI at `/docs` and `/openapi.json`.
- Errors always use `{"error": {"code", "message", "details?"}}`.
- Thin routes; logic in services (from step 2).
- Every request gets an `x-request-id`, a 15 s timeout and one JSON log line
  (no secrets or personal data).

## Data model (step 1)

| Table | Purpose | Access |
|---|---|---|
| `instruments` | Canonical instruments with currency, time zone and price definition | Public read |
| `instrument_aliases` | Provider symbols and search aliases, unique per provider | Public read |
| `market_observations` | Daily bars, unique on (instrument, observed_at, provider, frequency); keeps retrieval time, currency, quote type, quality and provenance | Public read |
| `profiles` | Per-user preferences, keyed by `auth.users.id` | Owner only (RLS) |

Step 2 added `fundamentals`, `instrument_snapshots` and `job_runs` (public read).
Step 3 adds user-owned tables, each with owner-only RLS and isolation tests:

| Table | Purpose |
|---|---|
| `portfolios` | Name, base currency (USD/INR), benchmark |
| `transactions` | Buy/sell ledger: date, quantity, unit (unit, troy_oz, gram), price, fees, currency |
| `watchlists`, `watchlist_items` | Named instrument lists |
| `alert_rules` | Instrument, kind, threshold, active, last state (for crossing) |
| `alert_events` | Fired alerts, one per rule and trading date; written only by the job, users can read, mark read and delete |

`anomalies` (public read) holds statistical flags, one per instrument, day and
kind, written by `jobs/scan_alerts.py` after each market data refresh.

`forecast_runs` (public read) holds daily baseline forecasts and their
walk-forward scores, written by `jobs/run_forecasts.py` (see docs/MODELS.md).

`news_articles` and `news_instruments` (public read) hold headlines, their
FinBERT scores and which instruments they mention.

`ai_usage` holds assistant requests and tokens per user per UTC day. Users can
read their own row; only the API writes it, and it enforces the daily limits.

## AI assistant (step 3d)
`app/ai/provider.py` wraps any OpenAI-compatible chat API (Groq by default).
`app/ai/tools.py` exposes ten read-only tools that call the same services as
the REST API, scoped to the signed-in user. `app/services/assistant_service.py`
runs the loop: the model may call tools for up to four rounds, then must
answer; every number in an answer comes from a tool result, which the system
prompt requires and the UI shows ("Data used", sources). Budgets are checked
before each request and recorded after it.

Reports (`/api/v1/reports/...`) are generated on demand with fpdf2 from the
same services and are not stored; portfolio reports use the owner check like
every portfolio endpoint. Every user-owned table gets owner-only RLS policies
and an isolation test.

## Provider interface (step 2)
Each source implements one adapter (`fetch_history`, `fetch_latest`,
`search`) that returns normalized observations. Adapters are the only code
that knows provider symbols, rate limits or payload formats. Business logic
works on canonical IDs only.
