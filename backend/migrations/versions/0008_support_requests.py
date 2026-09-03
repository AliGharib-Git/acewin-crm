"""add support_requests (user -> Platform Admin messages)

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-30
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

support_request_status = sa.Enum("open", "in_progress", "resolved", name="supportrequeststatus")


def upgrade() -> None:
    bind = op.get_bind()
    support_request_status.create(bind, checkfirst=True)

    op.create_table(
        "support_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", support_request_status, nullable=False, server_default="open"),
        sa.Column("admin_reply", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_support_requests_organization_id", "support_requests", ["organization_id"])
    op.create_index("ix_support_requests_user_id", "support_requests", ["user_id"])
    op.create_index("ix_support_requests_status", "support_requests", ["status"])
    op.create_index("ix_support_requests_created_at", "support_requests", ["created_at"])


def downgrade() -> None:
    op.drop_table("support_requests")
    bind = op.get_bind()
    support_request_status.drop(bind, checkfirst=True)
