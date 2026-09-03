"""add subscriptions table

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-13
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

subscription_plan = sa.Enum("basic", "pro", "vip", name="subscriptionplan")
subscription_status = sa.Enum("trialing", "active", "past_due", "canceled", name="subscriptionstatus")


def upgrade() -> None:
    bind = op.get_bind()
    subscription_plan.create(bind, checkfirst=True)
    subscription_status.create(bind, checkfirst=True)

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("plan", subscription_plan, nullable=False, server_default="basic"),
        sa.Column("status", subscription_status, nullable=False, server_default="trialing"),
        sa.Column("billing_cycle", sa.String(10), nullable=False, server_default="monthly"),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("external_customer_id", sa.String(255), nullable=True),
        sa.Column("external_subscription_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", name="uq_subscriptions_organization_id"),
    )
    op.create_index("ix_subscriptions_organization_id", "subscriptions", ["organization_id"])


def downgrade() -> None:
    op.drop_table("subscriptions")
    bind = op.get_bind()
    subscription_status.drop(bind, checkfirst=True)
    subscription_plan.drop(bind, checkfirst=True)
