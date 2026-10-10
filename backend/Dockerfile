# Slim API image for free-tier hosts (~512 MB RAM). No ML libraries here.
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements/api.txt requirements/api.txt
RUN pip install -r requirements/api.txt

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY scripts/start.sh ./start.sh

RUN useradd --create-home --uid 10001 appuser && chmod +x start.sh
USER appuser

ENV PORT=8000
EXPOSE 8000
CMD ["./start.sh"]
