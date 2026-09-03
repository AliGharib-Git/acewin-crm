"""add gamification engine tables

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-16
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

point_source_type = sa.Enum(
    "deal_won",
    "task_completed",
    "activity_logged",
    "contact_converted",
    "streak_bonus",
    "team_assist",
    name="pointsourcetype",
)


def upgrade() -> None:
    bind = op.get_bind()
    point_source_type.create(bind, checkfirst=True)

    op.create_table(
        "points_ledger",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_type", point_source_type, nullable=False),
        sa.Column("source_id", sa.String(80), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("reason_en", sa.String(255), nullable=False),
        sa.Column("reason_fa", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_points_ledger_organization_id", "points_ledger", ["organization_id"])
    op.create_index("ix_points_ledger_user_id", "points_ledger", ["user_id"])
    op.create_index("ix_points_ledger_source_type", "points_ledger", ["source_type"])
    op.create_index("ix_points_ledger_source_id", "points_ledger", ["source_id"])
    op.create_index("ix_points_ledger_created_at", "points_ledger", ["created_at"])

    op.create_table(
        "badges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(60), nullable=False),
        sa.Column("name_en", sa.String(120), nullable=False),
        sa.Column("name_fa", sa.String(120), nullable=False),
        sa.Column("description_en", sa.String(255), nullable=False),
        sa.Column("description_fa", sa.String(255), nullable=False),
        sa.Column("icon_key", sa.String(60), nullable=False),
        sa.Column("is_seasonal", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("code", name="uq_badges_code"),
    )
    op.create_index("ix_badges_code", "badges", ["code"])

    op.create_table(
        "user_badges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("badge_id", sa.Integer(), sa.ForeignKey("badges.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period_key", sa.String(20), nullable=True),
        sa.Column("awarded_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "badge_id", "period_key", name="uq_user_badges_user_badge_period"),
    )
    op.create_index("ix_user_badges_organization_id", "user_badges", ["organization_id"])
    op.create_index("ix_user_badges_user_id", "user_badges", ["user_id"])
    # NULL isn't deduplicated by a plain UNIQUE constraint (see
    # UserBadge's docstring in app/models.py) -- this partial index is
    # what actually makes a one-time milestone badge (period_key IS
    # NULL) earnable only once, on both Postgres and SQLite.
    op.create_index(
        "uq_user_badges_milestone_once",
        "user_badges",
        ["user_id", "badge_id"],
        unique=True,
        postgresql_where=sa.text("period_key IS NULL"),
        sqlite_where=sa.text("period_key IS NULL"),
    )

    op.create_table(
        "gamification_settings",
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("leaderboard_default_period", sa.String(10), nullable=False, server_default="weekly"),
        sa.Column("include_admins_in_leaderboard", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("gamification_settings")
    op.drop_table("user_badges")
    op.drop_table("badges")
    op.drop_table("points_ledger")
    bind = op.get_bind()
    point_source_type.drop(bind, checkfirst=True)
