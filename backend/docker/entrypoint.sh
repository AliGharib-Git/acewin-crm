#!/usr/bin/env bash
# Entrypoint for the ACEWIN API container.
#
# Responsibilities, in order:
#   1. Wait for the database to accept connections (Postgres only — SQLite
#      is a local file, there's nothing to wait for).
#   2. Apply Alembic migrations (Postgres only — see app/main.py and
#      backend/migrations/env.py for why SQLite instead relies on
#      Base.metadata.create_all at app import time).
#   3. exec the real process (uvicorn by default, from the Dockerfile CMD)
#      so it becomes PID 1 and receives signals directly — no shell left
#      in between to swallow SIGTERM on `docker stop`/`docker compose down`.
set -euo pipefail

DATABASE_URL="${DATABASE_URL:-sqlite:///./crm.db}"

is_sqlite() {
    [[ "$DATABASE_URL" == sqlite* ]]
}

if ! is_sqlite; then
    echo "[entrypoint] Waiting for the database to accept connections..."
    python - <<'PYEOF'
import sys
import time

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from app.config import settings

deadline = time.monotonic() + 60
engine = create_engine(settings.database_url)

while True:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        break
    except OperationalError as exc:
        if time.monotonic() > deadline:
            print(f"[entrypoint] Database never became reachable: {exc}", file=sys.stderr)
            sys.exit(1)
        time.sleep(1)
PYEOF
    echo "[entrypoint] Database is reachable."

    echo "[entrypoint] Applying Alembic migrations (alembic upgrade head)..."
    alembic upgrade head
    echo "[entrypoint] Migrations applied."
else
    echo "[entrypoint] SQLite database in use — skipping DB wait and Alembic"
    echo "[entrypoint] (tables are created automatically on app startup)."
fi

echo "[entrypoint] Starting: $*"
exec "$@"
