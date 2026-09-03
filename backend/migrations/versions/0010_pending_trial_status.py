"""add pending_trial subscription status

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-03
"""
from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

OLD_VALUES = ("trialing", "active", "past_due", "canceled")
NEW_VALUES = ("pending_trial", "trialing", "active", "past_due", "canceled")


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # Postgres enums are a standalone type -- widening it is a type
        # alteration, not a column/table change. ADD VALUE is safe to run
        # inside Alembic's transaction (PG12+); the new value just can't be
        # *used* in the same transaction it was added in, which we don't do
        # here (existing rows are left untouched -- see NOTE below).
        op.execute("ALTER TYPE subscriptionstatus ADD VALUE IF NOT EXISTS 'pending_trial'")
    else:
        # SQLite (and any other non-native-enum dialect) has no standalone
        # enum type -- SQLAlchemy enforces it as a CHECK constraint on the
        # column itself, so widening it means recreating the column via
        # batch mode rather than an ALTER TYPE.
        with op.batch_alter_table("subscriptions", recreate="always") as batch_op:
            batch_op.alter_column(
                "status",
                existing_type=sa.Enum(*OLD_VALUES, name="subscriptionstatus"),
                type_=sa.Enum(*NEW_VALUES, name="subscriptionstatus"),
                existing_nullable=False,
                existing_server_default="trialing",
            )

    # NOTE: existing orgs mid-trial or already active/past_due/canceled keep
    # their current status -- this migration only widens what's *allowed*.
    # Only orgs created after this deploy start out `pending_trial`; nobody
    # already trialing gets bumped back into an approval queue.


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # Postgres has no DROP VALUE -- narrowing a native enum requires
        # creating a new type, remapping every column to it, and dropping
        # the old one. Not worth doing for a downgrade path; if this ever
        # needs to be reversed, do it by hand against the target database.
        pass
    else:
        with op.batch_alter_table("subscriptions", recreate="always") as batch_op:
            batch_op.alter_column(
                "status",
                existing_type=sa.Enum(*NEW_VALUES, name="subscriptionstatus"),
                type_=sa.Enum(*OLD_VALUES, name="subscriptionstatus"),
                existing_nullable=False,
                existing_server_default="trialing",
            )
