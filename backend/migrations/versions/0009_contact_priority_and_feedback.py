"""add contacts.priority and public_feedback (homepage comments/complaints)

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-30
"""
from alembic import op
import sqlalchemy as sa

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

contact_priority = sa.Enum("low", "medium", "high", name="contactpriority")
public_feedback_category = sa.Enum("suggestion", "complaint", "question", name="publicfeedbackcategory")
# Reuses the exact same enum type/name support_requests already created in
# 0008 -- both tables share the identical open/in_progress/resolved
# lifecycle (see app/models.py:PublicFeedback), so this migration only
# needs to reference it, not redefine it (checkfirst=True guards against
# a second CREATE TYPE either way).
support_request_status = sa.Enum("open", "in_progress", "resolved", name="supportrequeststatus")


def upgrade() -> None:
    bind = op.get_bind()
    contact_priority.create(bind, checkfirst=True)
    public_feedback_category.create(bind, checkfirst=True)
    support_request_status.create(bind, checkfirst=True)

    op.add_column(
        "contacts",
        sa.Column("priority", contact_priority, nullable=False, server_default="medium"),
    )
    op.create_index("ix_contacts_priority", "contacts", ["priority"])

    op.create_table(
        "public_feedback",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("category", public_feedback_category, nullable=False, server_default="suggestion"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", support_request_status, nullable=False, server_default="open"),
        sa.Column("admin_reply", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_public_feedback_category", "public_feedback", ["category"])
    op.create_index("ix_public_feedback_status", "public_feedback", ["status"])
    op.create_index("ix_public_feedback_created_at", "public_feedback", ["created_at"])


def downgrade() -> None:
    op.drop_table("public_feedback")
    bind = op.get_bind()
    public_feedback_category.drop(bind, checkfirst=True)
    contact_priority.drop(bind, checkfirst=True)

    op.drop_index("ix_contacts_priority", table_name="contacts")
    op.drop_column("contacts", "priority")
