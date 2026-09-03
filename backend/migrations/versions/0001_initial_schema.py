"""initial multi-tenant schema

Revision ID: 0001
Revises:
Create Date: 2026-08-13

Baseline schema for a clean database, hand-authored to match
app/models.py as of the multi-tenancy migration (Organization +
organization_id on every tenant-owned table).

IMPORTANT: this was authored without a live database connection in the
sandbox that produced it (no network access to install psycopg2 /
run alembic here), so it could not be verified against `alembic
revision --autogenerate`. Before relying on it:

    cd backend
    alembic upgrade head                 # against a throwaway DB
    alembic check                        # (Alembic >=1.13) diffs models vs. migration state
    # or: alembic revision --autogenerate -m "check" and confirm the
    # generated diff is empty.

If `alembic check`/autogenerate reports drift, that's the model
definition to trust -- fix this file (or add a follow-up migration)
rather than the other way around.
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


# --- native PostgreSQL enum types, one per Python enum in app/models.py ---
# Names match SQLAlchemy's default derivation (lowercased Python class
# name) since no models.py Enum() call passes an explicit `name=`.
user_role = sa.Enum("admin", "member", name="userrole")
contact_status = sa.Enum("lead", "prospect", "customer", "inactive", name="contactstatus")
task_priority = sa.Enum("low", "medium", "high", name="taskpriority")
task_status = sa.Enum("pending", "completed", name="taskstatus")
task_type = sa.Enum("general", "call", name="tasktype")
activity_type = sa.Enum("note", "call", "email", "meeting", "status_change", name="activitytype")
agent_action_status = sa.Enum("success", "denied", "error", "undone", name="agentactionstatus")
objective_status = sa.Enum("draft", "active", "completed", "archived", name="objectivestatus")
key_result_type = sa.Enum("metric", "milestone", name="keyresulttype")

ALL_ENUMS = [
    user_role, contact_status, task_priority, task_status, task_type,
    activity_type, agent_action_status, objective_status, key_result_type,
]


def upgrade() -> None:
    bind = op.get_bind()
    for enum_type in ALL_ENUMS:
        enum_type.create(bind, checkfirst=True)

    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("slug", name="uq_organizations_slug"),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"])

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("role", user_role, nullable=False, server_default="member"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_organization_id", "users", ["organization_id"])
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("industry", sa.String(120), nullable=True),
        sa.Column("website", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_companies_organization_id", "companies", ["organization_id"])
    op.create_index("ix_companies_name", "companies", ["name"])

    op.create_table(
        "tags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(60), nullable=False),
        sa.Column("color", sa.String(20), server_default="#1B3A63"),
        sa.UniqueConstraint("organization_id", "name", name="uq_tags_org_name"),
    )
    op.create_index("ix_tags_organization_id", "tags", ["organization_id"])

    op.create_table(
        "pipeline_stages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("color", sa.String(20), server_default="#1B3A63"),
        sa.Column("is_won", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_lost", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_pipeline_stages_organization_id", "pipeline_stages", ["organization_id"])

    op.create_table(
        "contacts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("first_name", sa.String(120), nullable=False),
        sa.Column("last_name", sa.String(120), nullable=False, server_default=""),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("job_title", sa.String(150), nullable=True),
        sa.Column("status", contact_status, nullable=False, server_default="lead"),
        sa.Column("source", sa.String(120), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("assigned_to_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_contacts_organization_id", "contacts", ["organization_id"])
    op.create_index("ix_contacts_email", "contacts", ["email"])

    op.create_table(
        "contact_tags",
        sa.Column("contact_id", sa.Integer(), sa.ForeignKey("contacts.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tag_id", sa.Integer(), sa.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
    )

    op.create_table(
        "deals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("value", sa.Numeric(14, 2), server_default="0"),
        sa.Column("probability", sa.Integer(), server_default="50"),
        sa.Column("expected_close_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("stage_id", sa.Integer(), sa.ForeignKey("pipeline_stages.id"), nullable=False),
        sa.Column("contact_id", sa.Integer(), sa.ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("assigned_to_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_deals_organization_id", "deals", ["organization_id"])

    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("priority", task_priority, nullable=False, server_default="medium"),
        sa.Column("status", task_status, nullable=False, server_default="pending"),
        sa.Column("task_type", task_type, nullable=False, server_default="general"),
        sa.Column("reminder_minutes_before", sa.Integer(), nullable=True, server_default="15"),
        sa.Column("assigned_to_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("contact_id", sa.Integer(), sa.ForeignKey("contacts.id", ondelete="CASCADE"), nullable=True),
        sa.Column("deal_id", sa.Integer(), sa.ForeignKey("deals.id", ondelete="CASCADE"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_tasks_organization_id", "tasks", ["organization_id"])

    op.create_table(
        "activities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", activity_type, nullable=False, server_default="note"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("contact_id", sa.Integer(), sa.ForeignKey("contacts.id", ondelete="CASCADE"), nullable=True),
        sa.Column("deal_id", sa.Integer(), sa.ForeignKey("deals.id", ondelete="CASCADE"), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_activities_organization_id", "activities", ["organization_id"])

    op.create_table(
        "kpi_targets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kpi_key", sa.String(60), nullable=False),
        sa.Column("target_value", sa.Numeric(14, 2), nullable=False),
        sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "kpi_key", name="uq_kpi_targets_org_key"),
    )
    op.create_index("ix_kpi_targets_organization_id", "kpi_targets", ["organization_id"])
    op.create_index("ix_kpi_targets_kpi_key", "kpi_targets", ["kpi_key"])

    op.create_table(
        "agent_action_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("tool_name", sa.String(100), nullable=False),
        sa.Column("source", sa.String(20), nullable=False, server_default="copilot"),
        sa.Column("status", agent_action_status, nullable=False),
        sa.Column("arguments_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("entity_type", sa.String(40), nullable=True),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("is_undoable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("previous_state_json", sa.Text(), nullable=True),
        sa.Column("undone_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("undone_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_agent_action_logs_organization_id", "agent_action_logs", ["organization_id"])
    op.create_index("ix_agent_action_logs_tool_name", "agent_action_logs", ["tool_name"])
    op.create_index("ix_agent_action_logs_source", "agent_action_logs", ["source"])
    op.create_index("ix_agent_action_logs_status", "agent_action_logs", ["status"])
    op.create_index("ix_agent_action_logs_created_at", "agent_action_logs", ["created_at"])

    op.create_table(
        "objectives",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("department", sa.String(40), nullable=False, server_default="general"),
        sa.Column("period_key", sa.String(20), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", objective_status, nullable=False, server_default="active"),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_objectives_organization_id", "objectives", ["organization_id"])
    op.create_index("ix_objectives_period_key", "objectives", ["period_key"])

    op.create_table(
        "key_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("objective_id", sa.Integer(), sa.ForeignKey("objectives.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("measurement_type", key_result_type, nullable=False),
        sa.Column("weight", sa.Numeric(4, 2), nullable=False, server_default="1.0"),
        sa.Column("unit", sa.String(20), nullable=True),
        sa.Column("baseline_value", sa.Numeric(14, 2), nullable=True),
        sa.Column("target_value", sa.Numeric(14, 2), nullable=True),
        sa.Column("current_value", sa.Numeric(14, 2), nullable=True),
        sa.Column("linked_kpi_key", sa.String(60), nullable=True),
        sa.Column("is_done", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "key_result_updates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key_result_id", sa.Integer(), sa.ForeignKey("key_results.id", ondelete="CASCADE"), nullable=False),
        sa.Column("value", sa.Numeric(14, 2), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("key_result_updates")
    op.drop_table("key_results")
    op.drop_table("objectives")
    op.drop_table("agent_action_logs")
    op.drop_table("kpi_targets")
    op.drop_table("activities")
    op.drop_table("tasks")
    op.drop_table("deals")
    op.drop_table("contact_tags")
    op.drop_table("contacts")
    op.drop_table("pipeline_stages")
    op.drop_table("tags")
    op.drop_table("companies")
    op.drop_table("users")
    op.drop_table("organizations")

    bind = op.get_bind()
    for enum_type in ALL_ENUMS:
        enum_type.drop(bind, checkfirst=True)
