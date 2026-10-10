# MarketPulse

A multi-asset market research app covering global and Indian equities and
indices, major cryptocurrencies, gold and silver. It runs entirely on free
tiers.

> **Not investment advice.** MarketPulse is a research and education tool.
> Prices may be delayed or end of day; every figure shows its source and as-of time.

## Status

**Build step 1 of 4 (foundation).** What works today:
- App shell with all six sections, dark and light themes, mobile layout.
- FastAPI service with health check, consistent errors and structured logs.
- Database schema with Row Level Security, with tests proving user isolation.
- CI for lint, types and tests on every push.
- Live status panel showing web, API and database health, including the
  "waking up" state when the free API host is asleep.

Not built yet: market data, research pages, Risk Lab, portfolio, AI assistant,
alerts. Those sections say so in the app. See [PLAN.md](PLAN.md).

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
[docs/DESIGN_SYSTEM.md](docs/DESIGN_SYSTEM.md)
