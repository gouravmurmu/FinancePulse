#!/bin/sh
# Apply pending migrations before serving (idempotent). Render's free tier has
# no pre-deploy hook, so this runs on every boot. A failed migration is logged
# but does not stop the server: the health check then reports the database
# state, and stored-data endpoints return clear errors instead of the whole
# service being down.
if [ -n "$DATABASE_URL" ]; then
  alembic upgrade head || echo '{"level": "ERROR", "msg": "migration_failed"}'
fi
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --proxy-headers --forwarded-allow-ips='*'
