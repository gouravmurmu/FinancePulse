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
  it calls the API. Supabase Auth (step 3) issues JWTs that the API verifies.
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

Later steps add statements, FX, news and sentiment, portfolios and transactions,
watchlists, alerts, forecasts and reports. Every user-owned table gets owner-only
RLS policies and an isolation test.

## Provider interface (step 2)
Each source implements one adapter (`fetch_history`, `fetch_latest`,
`search`) that returns normalized observations. Adapters are the only code
that knows provider symbols, rate limits or payload formats. Business logic
works on canonical IDs only.
