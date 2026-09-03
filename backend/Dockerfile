# syntax=docker/dockerfile:1

# ─────────────────────────────────────────────────────────────────────────
# Stage 1: builder — compiles/installs Python deps into an isolated venv.
# Kept separate from the runtime stage so build tools (gcc, headers, etc.)
# never ship in the final image.
# ─────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

# build-essential + libpq-dev cover the rare case where a dependency has no
# prebuilt wheel for the target platform (e.g. building on arm64) and falls
# back to compiling from source (psycopg2, pandas, scikit-learn, pyarrow).
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ─────────────────────────────────────────────────────────────────────────
# Stage 2: runtime — small final image, no compilers, non-root user.
# ─────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# libpq5: runtime shared lib some psycopg2-binary builds still dlopen.
# curl: used by the container HEALTHCHECK below.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1000 app \
    && useradd --uid 1000 --gid app --shell /bin/bash --create-home app

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

# Copy application code. .dockerignore keeps out venvs, caches, .env, etc.
COPY --chown=app:app . .

COPY --chown=app:app docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# backend/data/olist holds the (large, user-supplied) Olist CSVs the
# Analytics Engine reads at request time, plus its on-disk feature cache —
# mounted as a volume in docker-compose.yml so it survives image rebuilds
# and doesn't bloat the image itself.
RUN mkdir -p /app/data/olist /app/data/_cache && chown -R app:app /app/data

USER app

EXPOSE 8000

# Liveness/readiness already modeled by the app itself (see app/main.py);
# just poll the liveness endpoint here.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://localhost:8000/api/health || exit 1

ENTRYPOINT ["entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
