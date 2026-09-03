"""
Alembic environment.

Deliberately does NOT read sqlalchemy.url from alembic.ini. Instead it
imports the exact same `app.config.settings` (and therefore the exact
same DATABASE_URL env var / .env file) the running application uses,
so migrations always target whatever database the app itself would
connect to -- dev, staging, or production -- with zero duplicated
configuration and zero risk of alembic.ini drifting out of sync with
the real connection string.
"""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import settings
from app.database import Base

# Import every model module so its tables register on Base.metadata
# before Alembic compares "what the models say" against "what the
# database actually has". A model class that exists but was never
# imported here is invisible to autogenerate -- it would silently
# produce an empty/incomplete migration instead of an error, so this
# import is not optional.
from app import models  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Inject the real URL from app settings instead of alembic.ini.
config.set_main_option("sqlalchemy.url", settings.database_url)


def run_migrations_offline() -> None:
    """Emit SQL to stdout without a live DB connection (`alembic upgrade head --sql`).
    Useful for review before running against production, or for
    handing the SQL to a DBA who has direct DB access this app doesn't."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,  # catch column type drift, not just add/drop
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
