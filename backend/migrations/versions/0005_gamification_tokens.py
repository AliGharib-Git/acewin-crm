"""add custom token branding to gamification_settings

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-17
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("gamification_settings", sa.Column("token_name_en", sa.String(40), nullable=False, server_default="Points"))
    op.add_column("gamification_settings", sa.Column("token_name_fa", sa.String(40), nullable=False, server_default="امتیاز"))
    op.add_column("gamification_settings", sa.Column("token_icon", sa.String(8), nullable=False, server_default="🏆"))


def downgrade() -> None:
    op.drop_column("gamification_settings", "token_icon")
    op.drop_column("gamification_settings", "token_name_fa")
    op.drop_column("gamification_settings", "token_name_en")
