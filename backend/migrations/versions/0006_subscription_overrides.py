"""add platform-admin limit/feature overrides to subscriptions

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-18
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("subscriptions", sa.Column("limit_overrides", sa.Text(), nullable=False, server_default="{}"))
    op.add_column("subscriptions", sa.Column("feature_overrides", sa.Text(), nullable=False, server_default="{}"))


def downgrade() -> None:
    op.drop_column("subscriptions", "feature_overrides")
    op.drop_column("subscriptions", "limit_overrides")
