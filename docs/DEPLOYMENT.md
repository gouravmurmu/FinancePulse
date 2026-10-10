# Deployment

| Tier | Where | How it deploys |
|---|---|---|
| Web | Vercel project `marketpulse` (root `frontend/`) | Every push to `main` (production) and every branch (preview) |
| API | Render service `marketpulse-api` (Docker, `backend/`) | Every push to `main` (`autoDeploy`); migrations run on boot |
| Database | Supabase project `marketpulse` | Alembic migrations, applied by the API on start |

## Environment variables

**Vercel (web)**
- `NEXT_PUBLIC_API_URL`: the Render URL, e.g. `https://marketpulse-api.onrender.com`
- `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`: public values from Supabase (step 3)

**Render (API)**
- `DATABASE_URL`: Supabase **session pooler** connection string (IPv4)
- `CORS_ORIGINS`: the production web URL(s), comma-separated
- `CORS_ORIGIN_REGEX`: optional, to allow Vercel preview URLs
- `ENVIRONMENT=production`

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
