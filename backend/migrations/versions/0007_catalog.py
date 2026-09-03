"""add catalog (categories, items) and deal line items

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-20
"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

billing_type = sa.Enum("one_time", "monthly", "yearly", name="billingtype")


def upgrade() -> None:
    bind = op.get_bind()
    billing_type.create(bind, checkfirst=True)

    op.create_table(
        "catalog_categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("color", sa.String(20), nullable=False, server_default="#1B3A63"),
        sa.UniqueConstraint("organization_id", "name", name="uq_catalog_categories_org_name"),
    )
    op.create_index("ix_catalog_categories_organization_id", "catalog_categories", ["organization_id"])

    op.create_table(
        "catalog_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category_id", sa.Integer(), sa.ForeignKey("catalog_categories.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sku", sa.String(80), nullable=True),
        sa.Column("price", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(20), nullable=False, server_default="USD"),
        sa.Column("billing_type", billing_type, nullable=False, server_default="one_time"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_catalog_items_organization_id", "catalog_items", ["organization_id"])
    op.create_index("ix_catalog_items_name", "catalog_items", ["name"])

    op.create_table(
        "deal_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("deal_id", sa.Integer(), sa.ForeignKey("deals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("catalog_item_id", sa.Integer(), sa.ForeignKey("catalog_items.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index("ix_deal_items_organization_id", "deal_items", ["organization_id"])
    op.create_index("ix_deal_items_deal_id", "deal_items", ["deal_id"])


def downgrade() -> None:
    op.drop_table("deal_items")
    op.drop_table("catalog_items")
    op.drop_table("catalog_categories")
    bind = op.get_bind()
    billing_type.drop(bind, checkfirst=True)
