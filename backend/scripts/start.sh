#!/bin/sh
set -e
# Apply pending migrations before serving (idempotent). Render's free tier has
# no pre-deploy hook, so this runs on every boot.
if [ -n "$DATABASE_URL" ]; then
  alembic upgrade head
fi
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips='*'
