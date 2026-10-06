#!/bin/sh
# Container entrypoint: apply migrations, then start the API.
set -e

echo "Applying database migrations..."
alembic upgrade head

# Worker count comes from $WEB_CONCURRENCY (uvicorn's default), so it's set per deployment.
exec uvicorn src.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --proxy-headers \
    --forwarded-allow-ips "*" \
    "$@"
