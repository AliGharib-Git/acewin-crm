from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.analytics.router import router as analytics_router
from app.config import settings
from app.database import Base, SessionLocal, engine
from app.gamification.badges import sync_badge_catalog
from app.routers import activities, agent_actions, auth, billing, catalog, companies, contacts, copilot, dashboard, deals, feedback, gamification, kpis, okrs, pipeline, platform_admin, sales_leads, support_requests, tags, tasks, users

# SQLite (the zero-setup local/dev path) has no separate migration
# runner in most quick-start workflows, so it's still fine to
# create-all here. PostgreSQL (staging/production) is governed by
# Alembic (see backend/migrations/) instead -- `Base.metadata.create_all`
# on Postgres would create tables with no alembic_version row, which
# then makes `alembic upgrade head` think it needs to create tables
# that already exist. Run `alembic upgrade head` before starting the
# app against Postgres.
if settings.database_url.startswith("sqlite"):
    Base.metadata.create_all(bind=engine)

# Gamification's badge catalog is code-defined (app/gamification/badges.py)
# but needs real `badges` rows for UserBadge's foreign key -- sync them on
# every boot, the same "code is the source of truth, DB just mirrors it"
# reasoning as app/billing/plans.py. Cheap (a handful of rows) and
# idempotent, so running it unconditionally on every startup is fine.
_startup_db = SessionLocal()
try:
    sync_badge_catalog(_startup_db)
finally:
    _startup_db.close()

app = FastAPI(
    title="ACEWIN API",
    description=(
        "Artificial CRM Intelligence: CRM Core (contacts, pipeline, tasks, reporting), "
        "the ACEWIN Copilot (natural-language assistant), and the Analytics Engine "
        "(ML modules trained on the Olist e-commerce dataset)."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(billing.router)
app.include_router(companies.router)
app.include_router(contacts.router)
app.include_router(tags.router)
app.include_router(pipeline.router)
app.include_router(catalog.router)
app.include_router(deals.router)
app.include_router(tasks.router)
app.include_router(activities.router)
app.include_router(dashboard.router)
app.include_router(kpis.router)
app.include_router(okrs.router)
app.include_router(gamification.router)
app.include_router(copilot.router)
app.include_router(agent_actions.router)
app.include_router(analytics_router)
app.include_router(platform_admin.router)
app.include_router(support_requests.router)
app.include_router(feedback.router)
app.include_router(sales_leads.router)


@app.get("/api/health", tags=["health"])
def health_check():
    """Liveness: is the process up and serving requests at all. Deliberately
    checks nothing external -- a dependency outage should show up in
    /api/ready, not make the process look dead to an orchestrator that
    would restart it for a problem a restart can't fix."""
    return {"status": "ok"}


@app.get("/api/ready", tags=["health"])
def readiness_check():
    """Readiness: can this instance actually serve traffic right now.
    Checks the one hard dependency every request needs (the database);
    the AI provider is deliberately NOT checked here, since Copilot is
    an optional feature (AI_PROVIDER=none is a supported, valid
    configuration) and its absence must never take the whole API out
    of the load balancer's rotation."""
    checks = {"database": "ok"}
    healthy = True
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001 -- deliberately broad: any DB failure means "not ready"
        checks["database"] = "unreachable"
        healthy = False
    finally:
        db.close()

    return {"status": "ready" if healthy else "not_ready", "checks": checks}
