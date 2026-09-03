"""add sales_leads (VIP "Contact sales" requests)

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-03
"""
from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

# Reuses the existing supportrequeststatus enum (open/in_progress/resolved) --
# same lifecycle as SupportRequest/PublicFeedback, no new enum type needed.


def upgrade() -> None:
    op.create_table(
        "sales_leads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("contact_name", sa.String(150), nullable=False),
        sa.Column("contact_email", sa.String(255), nullable=False),
        sa.Column("contact_phone", sa.String(50), nullable=True),
        sa.Column("company_name", sa.String(200), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("open", "in_progress", "resolved", name="supportrequeststatus"),
            nullable=False,
            server_default="open",
        ),
        sa.Column("admin_reply", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_sales_leads_organization_id", "sales_leads", ["organization_id"])
    op.create_index("ix_sales_leads_user_id", "sales_leads", ["user_id"])
    op.create_index("ix_sales_leads_status", "sales_leads", ["status"])
    op.create_index("ix_sales_leads_created_at", "sales_leads", ["created_at"])


def downgrade() -> None:
    op.drop_table("sales_leads")
