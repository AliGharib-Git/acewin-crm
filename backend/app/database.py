from datetime import timezone

from sqlalchemy import DateTime, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.types import TypeDecorator

from app.config import settings

is_sqlite = settings.database_url.startswith("sqlite")
connect_args = {"check_same_thread": False} if is_sqlite else {}

# pool_pre_ping: for a long-lived server process talking to a real
# database server (PostgreSQL in staging/production), the DB side can
# close idle connections out from under us (firewall timeouts, DB
# restarts, connection poolers). This makes SQLAlchemy check a
# connection with a cheap SELECT 1 before handing it out rather than
# handing the caller a dead connection and surfacing a confusing
# OperationalError deep inside a request. Irrelevant for SQLite (single
# file, no server-side idle timeout) so it's skipped there.
engine = create_engine(settings.database_url, connect_args=connect_args, pool_pre_ping=not is_sqlite)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class TZDateTime(TypeDecorator):
    """Drop-in replacement for `DateTime(timezone=True)` that guarantees
    every value coming back out of the ORM is timezone-aware, even on
    SQLite.

    SQLite has no real datetime/timestamptz type -- it stores whatever
    ISO string SQLAlchemy hands it and, on the way back out, always
    returns a naive `datetime` regardless of `timezone=True` on the
    column. Every piece of app code that does
    `some_model.some_datetime_column < datetime.now(timezone.utc)`
    (trial expiry, token expiry, KPI/OKR date-range checks, gamification
    windows, ...) then raises `TypeError: can't compare offset-naive and
    offset-aware datetimes` the moment that value is read back from the
    database -- not at write time, which is why it's easy to miss in
    quick manual testing (an object still holds its in-memory aware
    value until it's re-fetched). On PostgreSQL this isn't an issue
    (`timestamptz` round-trips tzinfo correctly), but the app's own
    documented dev path is SQLite, so this must hold there too.

    All naive datetimes are treated as UTC, matching the rest of the
    codebase's convention of using `datetime.now(timezone.utc)`
    everywhere.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value

    def process_result_value(self, value, dialect):
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
