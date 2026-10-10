# Deployment

| Tier | Where | Live URL | How it deploys |
|---|---|---|---|
| Web | Vercel project `marketpulse` (root `frontend/`) | https://marketpulse-grv4.vercel.app | Every push to `main` (production) and every branch (preview) |
| API | Render service `marketpulse-api` (Docker, Singapore) | https://marketpulse-api-kp70.onrender.com | Every push to `main`; migrations run on boot |
| Database | Supabase project `marketpulse` (ap-south-1, Mumbai) | (private) | Alembic migrations, applied by the API on start |

## First-time database setup
Run `infra/supabase/setup.sql` as `postgres` (Supabase SQL editor). It creates
the `marketpulse_api` login used by Render and grants what migrations need.
Its last statement adds the `profiles → auth.users` foreign key, which the app
role is not allowed to create; run it after the first deploy.

## Environment variables

**Vercel (web)**
- `NEXT_PUBLIC_API_URL`: the Render URL, e.g. `https://marketpulse-api.onrender.com`
- `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`: public values from Supabase (step 3)

**Render (API)**
- `DATABASE_URL`: Supabase **session pooler** connection string (IPv4) for the `marketpulse_api` role,
  `postgresql://marketpulse_api.<ref>:<password>@aws-0-ap-south-1.pooler.supabase.com:5432/postgres?sslmode=require`
- `CORS_ORIGINS`: the production web URL(s), comma-separated
- `CORS_ORIGIN_REGEX`: Vercel preview URLs for this account only, `^https://marketpulse-[a-z0-9-]+-grv4\.vercel\.app$`
- `ENVIRONMENT=production`

**GitHub Actions (repository secrets)**
- `DATABASE_URL`: same value as Render; used by the market data and fundamentals jobs.
- `SEC_CONTACT_EMAIL`: contact email SEC requires in the User-Agent. Without it the
  weekly fundamentals job is skipped with a warning.
- `COINGECKO_API_KEY` (optional): free CoinGecko Demo key for a higher rate limit.

## Scheduled jobs
| Workflow | Schedule (UTC) | Manual run |
|---|---|---|
| `market-data.yml` | 11:00 and 22:30 daily | `backfill` (5 years) and `only` (instrument IDs) inputs |
| `fundamentals.yml` | Sundays 06:00 | yes |
| `record-fixtures.yml` | manual only | pushes real provider samples to `fixtures/recorded` |

Secrets live only in the provider dashboards, never in the repository.

## Running locally

```bash
# Everything in containers
docker compose up --build        # web :3000, api :8000, postgres :5432

# Or natively
cd backend && python -m venv .venv && . .venv/bin/activate
pip install -r requirements/dev.txt
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/marketpulse alembic upgrade head
uvicorn app.main:app --reload

cd frontend && npm ci && npm run dev
```

Plain Postgres needs `infra/postgres/00-supabase-stub.sql` loaded first (docker
compose does this automatically) so migrations and RLS behave like Supabase.

## Smoke test after a deploy

1. `GET <api>/api/v1/health` returns `"status": "ok"` and `"database": {"status": "ok"}`.
2. The web app's Markets page shows all three tiers green in **System status**.
3. After 15+ idle minutes, reloading shows "Waking up the analytics server…"
   and then turns green without an error.
