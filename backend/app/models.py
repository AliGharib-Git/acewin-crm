import enum
import json
from datetime import datetime, date

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    Column,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, TZDateTime


class UserRole(str, enum.Enum):
    admin = "admin"
    member = "member"


class ContactStatus(str, enum.Enum):
    lead = "lead"
    prospect = "prospect"
    customer = "customer"
    inactive = "inactive"


class ContactPriority(str, enum.Enum):
    """How much this contact is worth investing in, in the rep's own
    judgment -- deliberately separate from `Contact.status` (a lifecycle
    stage: lead/prospect/customer/inactive) and from the auto-computed
    engagement score (see app/scoring/engine.py, which reads how much
    follow-up has actually happened). `priority` is the human call on
    *how important* this person/deal is to the business; status is
    *where* they are in the funnel; engagement is *how tended-to* they
    currently are. All three are shown together so a rep can tell a
    high-value lead that's gone quiet from a low-value one that's
    simply new."""

    low = "low"
    medium = "medium"
    high = "high"


class TaskPriority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class TaskStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"


class TaskType(str, enum.Enum):
    general = "general"
    call = "call"


class ActivityType(str, enum.Enum):
    note = "note"
    call = "call"
    email = "email"
    meeting = "meeting"
    status_change = "status_change"


class AgentActionStatus(str, enum.Enum):
    """Outcome of one Copilot tool-call attempt, recorded in AgentActionLog
    regardless of whether it succeeded -- a denied or failed attempt is
    itself an auditable event."""

    success = "success"
    denied = "denied"
    error = "error"
    undone = "undone"


class SubscriptionPlan(str, enum.Enum):
    basic = "basic"
    pro = "pro"
    vip = "vip"


class BillingType(str, enum.Enum):
    """How a CatalogItem is priced -- mirrors the vocabulary a sales rep
    actually uses when quoting a customer (see docs on CatalogItem)."""

    one_time = "one_time"
    monthly = "monthly"
    yearly = "yearly"


class SubscriptionStatus(str, enum.Enum):
    # A brand-new org lands here, not `trialing` -- the 14-day Basic trial
    # no longer starts itself at registration. It starts the moment a
    # Platform Admin approves the request (see app/routers/auth.py's
    # admin-notification email and subscription_service.approve_trial).
    pending_trial = "pending_trial"
    trialing = "trialing"
    active = "active"
    past_due = "past_due"
    canceled = "canceled"


contact_tags = Table(
    "contact_tags",
    Base.metadata,
    Column("contact_id", ForeignKey("contacts.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Organization(Base):
    """A tenant. Every business record in the system belongs to exactly
    one Organization, and every authenticated request is scoped to the
    caller's Organization -- see app/deps.py:get_current_org() and the
    `organization_id` column on every tenant-owned model below.

    Deliberately minimal for now (name/slug/status only). Subscription
    plan, billing status and usage counters are a separate concern
    (Phase E: Subscription + Entitlements) and will hang off this row
    without requiring another migration of the tenant-owned tables.
    """

    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime(), server_default=func.now())

    users: Mapped[list["User"]] = relationship(back_populates="organization")
    subscription: Mapped["Subscription | None"] = relationship(back_populates="organization", uselist=False)


class Subscription(Base):
    """One row per Organization (enforced by the unique constraint on
    organization_id, not just convention -- see the DB-level guarantee
    below). Deliberately stores only what the *product* needs to answer
    "what can this org do right now" (plan, status, period dates) --
    payment method details, invoices, card data etc. belong to whatever
    real payment gateway eventually gets plugged in via
    app/billing/provider.py, never in this table.

    No payment gateway is wired up yet (see app/billing/provider.py:
    NullBillingProvider) -- `plan` here is set directly by an org admin
    or by a support/ops action, not by a completed checkout. That's a
    real, working state machine (trial -> active -> past_due/canceled)
    even without a payment processor behind it; it's just manually
    driven for now instead of webhook-driven.
    """

    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    plan: Mapped[SubscriptionPlan] = mapped_column(Enum(SubscriptionPlan), nullable=False, default=SubscriptionPlan.basic)
    status: Mapped[SubscriptionStatus] = mapped_column(Enum(SubscriptionStatus), nullable=False, default=SubscriptionStatus.trialing)
    billing_cycle: Mapped[str] = mapped_column(String(10), nullable=False, default="monthly")  # "monthly" | "yearly"

    trial_ends_at: Mapped[datetime | None] = mapped_column(TZDateTime(), nullable=True)
    current_period_end: Mapped[datetime | None] = mapped_column(TZDateTime(), nullable=True)
    canceled_at: Mapped[datetime | None] = mapped_column(TZDateTime(), nullable=True)

    # Set by a real BillingProvider once one is wired in (e.g. Stripe's
    # customer/subscription ids). Both nullable and unused today --
    # present so that integrating a provider later is additive
    # (populate these columns) rather than another schema migration.
    external_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    external_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Per-tenant overrides set by a Platform Admin (see app/routers/
    # platform_admin.py), sitting ON TOP of the plan's own numbers from
    # app/billing/plans.py rather than replacing them. Most orgs have
    # both dicts empty and are governed purely by their plan; these
    # exist for the "this one company gets a custom AI question quota"
    # / "give this company early access to ai.actions" cases a flat
    # plan table can't express. JSON-encoded (mirrors
    # User.restricted_permissions_json) since they're small, sparse,
    # per-tenant maps read on every entitlement check rather than
    # something that needs its own relational table.
    #   limit_overrides:   {metric: int}          -- replaces the plan's
    #                       numeric ceiling for that metric only.
    #                       (There's no "unlimited via override" value;
    #                       an admin who wants that sets a very high
    #                       number -- keeps the override type simple:
    #                       always a concrete int, never None.)
    #   feature_overrides: {feature_code: bool}    -- true force-grants a
    #                       feature the plan doesn't include, false
    #                       force-revokes one the plan does. A key
    #                       absent from the dict means "defer to the
    #                       plan", same as an absent limit metric.
    limit_overrides_json: Mapped[str] = mapped_column(
        "limit_overrides", Text, default="{}", server_default="{}", nullable=False
    )
    feature_overrides_json: Mapped[str] = mapped_column(
        "feature_overrides", Text, default="{}", server_default="{}", nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(TZDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TZDateTime(), server_default=func.now(), onupdate=func.now())

    organization: Mapped["Organization"] = relationship(back_populates="subscription")

    @property
    def limit_overrides(self) -> dict[str, int]:
        return json.loads(self.limit_overrides_json or "{}")

    @limit_overrides.setter
    def limit_overrides(self, overrides: dict[str, int]) -> None:
        self.limit_overrides_json = json.dumps(overrides)

    @property
    def feature_overrides(self) -> dict[str, bool]:
        return json.loads(self.feature_overrides_json or "{}")

    @feature_overrides.setter
    def feature_overrides(self, overrides: dict[str, bool]) -> None:
        self.feature_overrides_json = json.dumps(overrides)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # A user account belongs to exactly one Organization for now (one
    # signup = one new tenant, whose creator becomes its first admin --
    # see routers/auth.py:register). Inviting an existing user into a
    # second organization (many-to-many via a Membership table) is a
    # natural fast-follow but is intentionally out of scope here: it
    # does not change how any of the tenant-isolation guarantees below
    # work, since every request is still resolved to exactly one
    # `organization_id` via the JWT-authenticated user.
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.member, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Per-account permission overrides, on top of the role's default grant
    # (see app/ai/permissions.py:ROLE_PERMISSIONS). JSON-encoded list of
    # permission keys (e.g. '["deals:delete", "contacts:update"]") that
    # are explicitly REVOKED for this one user, even though their role
    # would otherwise allow them -- e.g. an admin who wants one specific
    # member locked out of deleting deals without demoting them or
    # touching anyone else's access. Never grants anything beyond the
    # role; it only ever narrows. Stored as text (not a related table)
    # because it's a small, per-user allow/deny list read on every
    # permission check -- see app/ai/permissions.py:_restricted_permissions.
    restricted_permissions_json: Mapped[str] = mapped_column(
        "restricted_permissions", Text, default="[]", server_default="[]", nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(TZDateTime(), server_default=func.now())

    organization: Mapped["Organization"] = relationship(back_populates="users")

    @property
    def restricted_permissions(self) -> list[str]:
        """Parsed view of restricted_permissions_json for callers that want
        the list (schemas.UserOut, the admin UI). See
        app.ai.permissions.get_restricted_permissions for the
        enforcement-side reader, which is deliberately tolerant of bad
        JSON the way this one is not -- this property is used for
        *display*, so a corrupt value should surface as an error rather
        than silently show "nothing restricted"."""
        return json.loads(self.restricted_permissions_json or "[]")

    @restricted_permissions.setter
    def restricted_permissions(self, keys: list[str]) -> None:
        self.restricted_permissions_json = json.dumps(sorted(set(keys)))


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    industry: Mapped[str | None] = mapped_column(String(120), nullable=True)
    website: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TZDateTime(), server_default=func.now(), onupdate=func.now())

    contacts: Mapped[list["Contact"]] = relationship(back_populates="company")
    deals: Mapped[list["Deal"]] = relationship(back_populates="company")


class Tag(Base):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_tags_org_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    color: Mapped[str] = mapped_column(String(20), default="#1B3A63")

    contacts: Mapped[list["Contact"]] = relationship(secondary=contact_tags, back_populates="tags")


class CatalogCategory(Base):
    """A grouping for CatalogItem (e.g. "Subscription plans", "Implementation
    services", "Add-ons") -- purely organizational, like Tag, and managed
    the same way as PipelineStage: admin-only writes, org-scoped, ordered
    for display."""

    __tablename__ = "catalog_categories"
    __table_args__ = (UniqueConstraint("organization_id", "name", name="uq_catalog_categories_org_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    color: Mapped[str] = mapped_column(String(20), default="#1B3A63")

    items: Mapped[list["CatalogItem"]] = relationship(back_populates="category", order_by="CatalogItem.name")


class CatalogItem(Base):
    """One sellable product/service/tariff in the org's own catalog -- what
    a rep picks from when building a quote/deal (see DealItem below). This
    is deliberately separate from Subscription/SubscriptionPlan, which is
    ACEWIN's *own* pricing for the org itself; CatalogItem is what the org
    sells to *its* customers, and is fully org-defined (any business, any
    product mix)."""

    __tablename__ = "catalog_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("catalog_categories.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sku: Mapped[str | None] = mapped_column(String(80), nullable=True)
    price: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    currency: Mapped[str] = mapped_column(String(20), default="USD", nullable=False)
    billing_type: Mapped[BillingType] = mapped_column(Enum(BillingType), default=BillingType.one_time, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TZDateTime(), server_default=func.now(), onupdate=func.now())

    category: Mapped["CatalogCategory | None"] = relationship(back_populates="items")


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    first_name: Mapped[str] = mapped_column(String(120), nullable=False)
    last_name: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    job_title: Mapped[str | None] = mapped_column(String(150), nullable=True)
    status: Mapped[ContactStatus] = mapped_column(Enum(ContactStatus), default=ContactStatus.lead, nullable=False)
    # Rep-assigned business importance -- see ContactPriority's docstring
    # for how this differs from `status` and from the computed engagement
    # score. Defaults to medium so existing contacts (pre-migration) and
    # freshly-created ones don't all silently start at the bottom.
    priority: Mapped[ContactPriority] = mapped_column(
        Enum(ContactPriority), default=ContactPriority.medium, server_default="medium", nullable=False, index=True
    )
    source: Mapped[str | None] = mapped_column(String(120), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"), nullable=True)
    assigned_to_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(TZDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TZDateTime(), server_default=func.now(), onupdate=func.now())

    company: Mapped["Company | None"] = relationship(back_populates="contacts")
    assigned_to: Mapped["User | None"] = relationship(foreign_keys=[assigned_to_id])
    tags: Mapped[list["Tag"]] = relationship(secondary=contact_tags, back_populates="contacts")
    deals: Mapped[list["Deal"]] = relationship(back_populates="contact")
    tasks: Mapped[list["Task"]] = relationship(back_populates="contact")
    activities: Mapped[list["Activity"]] = relationship(back_populates="contact", order_by="desc(Activity.created_at)")


class PipelineStage(Base):
    __tablename__ = "pipeline_stages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    color: Mapped[str] = mapped_column(String(20), default="#1B3A63")
    is_won: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_lost: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    deals: Mapped[list["Deal"]] = relationship(back_populates="stage")


class Deal(Base):
    __tablename__ = "deals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    probability: Mapped[int] = mapped_column(Integer, default=50)
    expected_close_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    stage_id: Mapped[int] = mapped_column(ForeignKey("pipeline_stages.id"), nullable=False)
    contact_id: Mapped[int | None] = mapped_column(ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"), nullable=True)
    assigned_to_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(TZDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TZDateTime(), server_default=func.now(), onupdate=func.now())
    closed_at: Mapped[datetime | None] = mapped_column(TZDateTime(), nullable=True)

    stage: Mapped["PipelineStage"] = relationship(back_populates="deals")
    contact: Mapped["Contact | None"] = relationship(back_populates="deals")
    company: Mapped["Company | None"] = relationship(back_populates="deals")
    assigned_to: Mapped["User | None"] = relationship(foreign_keys=[assigned_to_id])
    activities: Mapped[list["Activity"]] = relationship(back_populates="deal", order_by="desc(Activity.created_at)")
    items: Mapped[list["DealItem"]] = relationship(back_populates="deal", cascade="all, delete-orphan", order_by="DealItem.id")


class DealItem(Base):
    """One catalog item quoted on a Deal, quantity included. `name` and
    `unit_price` are a SNAPSHOT taken when the line was added -- deliberately
    not re-read from CatalogItem on every view, the same reasoning as an
    invoice line item anywhere: if the catalog price changes next month, a
    deal quoted last month must keep showing what the customer was actually
    quoted. `catalog_item_id` is kept (nullable, SET NULL) purely to trace
    "what was this originally picked from"; it's never used to recompute
    the price. A line with no catalog_item_id is a one-off custom line the
    rep typed in by hand -- both are fully supported the same way.
    """

    __tablename__ = "deal_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    deal_id: Mapped[int] = mapped_column(ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True)
    catalog_item_id: Mapped[int | None] = mapped_column(ForeignKey("catalog_items.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    deal: Mapped["Deal"] = relationship(back_populates="items")
    catalog_item: Mapped["CatalogItem | None"] = relationship()


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_date: Mapped[datetime | None] = mapped_column(TZDateTime(), nullable=True)
    priority: Mapped[TaskPriority] = mapped_column(Enum(TaskPriority), default=TaskPriority.medium, nullable=False)
    status: Mapped[TaskStatus] = mapped_column(Enum(TaskStatus), default=TaskStatus.pending, nullable=False)
    task_type: Mapped[TaskType] = mapped_column(Enum(TaskType), default=TaskType.general, nullable=False)
    reminder_minutes_before: Mapped[int | None] = mapped_column(Integer, nullable=True, default=15)

    assigned_to_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    contact_id: Mapped[int | None] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"), nullable=True)
    deal_id: Mapped[int | None] = mapped_column(ForeignKey("deals.id", ondelete="CASCADE"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(TZDateTime(), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(TZDateTime(), nullable=True)

    assigned_to: Mapped["User | None"] = relationship(foreign_keys=[assigned_to_id])
    contact: Mapped["Contact | None"] = relationship(back_populates="tasks")
    deal: Mapped["Deal | None"] = relationship()


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    type: Mapped[ActivityType] = mapped_column(Enum(ActivityType), default=ActivityType.note, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    contact_id: Mapped[int | None] = mapped_column(ForeignKey("contacts.id", ondelete="CASCADE"), nullable=True)
    deal_id: Mapped[int | None] = mapped_column(ForeignKey("deals.id", ondelete="CASCADE"), nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(TZDateTime(), server_default=func.now())

    contact: Mapped["Contact | None"] = relationship(back_populates="activities")
    deal: Mapped["Deal | None"] = relationship(back_populates="activities")
    created_by: Mapped["User | None"] = relationship(foreign_keys=[created_by_id])


class KPITarget(Base):
    """Admin-settable target for one KPI Engine metric (see app/kpi/engine.py
    for the KPI definitions themselves). Deliberately just a key/value
    table -- the KPI's current value, trend, and risk level are always
    computed live from real CRM data, never stored, so they can never
    go stale relative to the underlying Deals/Tasks."""

    __tablename__ = "kpi_targets"
    __table_args__ = (UniqueConstraint("organization_id", "kpi_key", name="uq_kpi_targets_org_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    kpi_key: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    target_value: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    updated_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        TZDateTime(), server_default=func.now(), onupdate=func.now()
    )

    updated_by: Mapped["User | None"] = relationship()


class AgentActionLog(Base):
    """Audit trail for every action the Copilot Action Agent attempts --
    the enterprise requirement being: every AI-initiated action must be
    logged, attributable to a user, and (for writes) reversible.

    This is deliberately a separate table from `Activity` (the CRM's own
    business-facing timeline of notes/calls/emails a *person* logs against
    a contact/deal). AgentActionLog is a security/compliance record of
    what the AI did on someone's behalf, independent of which CRM record
    (if any) it touched.
    """

    __tablename__ = "agent_action_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # "copilot" for anything the AI Action Agent did via tool-calling, "api"
    # for a human acting directly through the REST API. Same table, same
    # permission rules, same undo mechanism where applicable -- one audit
    # trail for the whole system rather than two.
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="copilot", index=True)
    status: Mapped[AgentActionStatus] = mapped_column(Enum(AgentActionStatus), nullable=False, index=True)

    # What was asked for, and what the tool reported back (or the error it raised).
    arguments_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    result_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # What CRM record this touched, for quick filtering ("show me everything
    # the agent did to deal #42").
    entity_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Undo support. `is_undoable` is fixed per tool (only real writes are
    # reversible). `previous_state_json` is the snapshot captured
    # immediately before the write executed -- enough to reconstruct the
    # prior values on undo. `undone_at`/`undone_by_id` are set once, the
    # first (and only) time an action is undone.
    is_undoable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    previous_state_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    undone_at: Mapped[datetime | None] = mapped_column(TZDateTime(), nullable=True)
    undone_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(TZDateTime(), server_default=func.now(), index=True)

    user: Mapped["User | None"] = relationship(foreign_keys=[user_id])
    undone_by: Mapped["User | None"] = relationship(foreign_keys=[undone_by_id])


# ---------------------------------------------------------------------------
# OKR Engine
# ---------------------------------------------------------------------------


class ObjectiveStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    completed = "completed"
    archived = "archived"


class KeyResultType(str, enum.Enum):
    # A numeric metric tracked from baseline -> target, either updated by
    # hand (KeyResultUpdate entries) or pulled live from the KPI Engine
    # (when linked_kpi_key is set -- see app/okr/engine.py).
    metric = "metric"
    # A yes/no deliverable ("ship the new onboarding flow") with no
    # in-between progress -- either done or not.
    milestone = "milestone"


class Objective(Base):
    """One OKR objective for one department, for one time-boxed period
    (a quarter, by convention -- see app/okr/engine.py for period bounds
    parsing). Its score is always derived live from its KeyResults'
    scores, never stored -- see compute_objective_score()."""

    __tablename__ = "objectives"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    department: Mapped[str] = mapped_column(String(40), nullable=False, default="general")
    period_key: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # e.g. "2026-Q3"
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[ObjectiveStatus] = mapped_column(Enum(ObjectiveStatus), default=ObjectiveStatus.active, nullable=False)

    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TZDateTime(), server_default=func.now(), onupdate=func.now())

    owner: Mapped["User | None"] = relationship(foreign_keys=[owner_id])
    created_by: Mapped["User | None"] = relationship(foreign_keys=[created_by_id])
    key_results: Mapped[list["KeyResult"]] = relationship(
        back_populates="objective", cascade="all, delete-orphan", order_by="KeyResult.id"
    )


class KeyResult(Base):
    """One measurable Key Result under an Objective. Its own score
    (0-100%) is always computed live (see compute_key_result_score()) --
    `current_value` is the only thing this row stores for a `metric`
    KR that isn't KPI-linked; for a KPI-linked KR, even current_value is
    ignored in favor of the live KPI value, so it can never drift stale."""

    __tablename__ = "key_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    objective_id: Mapped[int] = mapped_column(ForeignKey("objectives.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    measurement_type: Mapped[KeyResultType] = mapped_column(Enum(KeyResultType), nullable=False)
    weight: Mapped[float] = mapped_column(Numeric(4, 2), default=1.0, nullable=False)

    # metric fields (ignored for milestone KRs)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)  # "currency"|"percent"|"number"|"days"|"hours"
    baseline_value: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    target_value: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    current_value: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    # If set, current_value is always read live from the KPI Engine
    # (app/kpi/engine.py) instead of this row -- see app/okr/engine.py.
    linked_kpi_key: Mapped[str | None] = mapped_column(String(60), nullable=True)

    # milestone field (ignored for metric KRs)
    is_done: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(TZDateTime(), server_default=func.now(), onupdate=func.now())

    objective: Mapped["Objective"] = relationship(back_populates="key_results")
    owner: Mapped["User | None"] = relationship(foreign_keys=[owner_id])
    updates: Mapped[list["KeyResultUpdate"]] = relationship(
        back_populates="key_result", cascade="all, delete-orphan", order_by="desc(KeyResultUpdate.created_at)"
    )


class KeyResultUpdate(Base):
    """One progress check-in on a `metric`-type Key Result -- an honest
    history of how the number moved over time, entered by its owner.
    Never written for KPI-linked or milestone KRs (those update
    current_value/is_done directly, since their "history" already lives
    in the KPI Engine's own trend, or is just a single done/not-done flip)."""

    __tablename__ = "key_result_updates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key_result_id: Mapped[int] = mapped_column(ForeignKey("key_results.id", ondelete="CASCADE"), nullable=False)
    value: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime(), server_default=func.now())

    key_result: Mapped["KeyResult"] = relationship(back_populates="updates")
    created_by: Mapped["User | None"] = relationship(foreign_keys=[created_by_id])


# ---------------------------------------------------------------------------
# Gamification Engine (Pro feature -- see app/billing/plans.py:"gamification.core")
#
# Design follows docs/gamification-rnd.md. Phase 1 (this migration) wires
# three point sources -- deal_won, task_completed, activity_logged -- plus
# levels, a weekly/monthly/all-time leaderboard, and milestone badges. The
# full enum/model surface for Phase 2 (streak_bonus, team_assist) is defined
# now so it ships without another migration, even though app/gamification/
# only awards the Phase 1 sources today -- see app/gamification/engine.py.
# ---------------------------------------------------------------------------


class PointSourceType(str, enum.Enum):
    deal_won = "deal_won"
    task_completed = "task_completed"
    activity_logged = "activity_logged"
    contact_converted = "contact_converted"  # defined, not yet awarded -- Phase 2
    streak_bonus = "streak_bonus"  # defined, not yet awarded -- Phase 2
    team_assist = "team_assist"  # defined, not yet awarded -- Phase 2


class PointsLedger(Base):
    """Append-only -- the single source of truth for every user's score.
    A user's total/level/leaderboard position is always SUM(points) over
    their rows, computed live (app/gamification/engine.py), never a
    mutable counter -- same "derive, don't cache" philosophy as
    subscription_service.effective_plan() and the KPI Engine.

    Rows are never UPDATEd or DELETEd. Reversing a prior award (e.g. a
    Deal gets un-won, or deleted, after points were given for it) adds a
    compensating negative row instead -- see
    app/gamification/engine.py:revoke_points_for_source. This keeps the
    ledger a true audit trail (mirrors AgentActionLog's philosophy for
    Copilot actions) and makes a user's score naturally self-correcting
    without ever touching history.

    `source_id` is a stable, traceable reference of the form
    "<entity>:<id>" (e.g. "deal:123"), not a bare integer -- it's what
    makes both idempotency (has this exact event already been awarded?)
    and revocation (find every row tied to this event) possible.
    """

    __tablename__ = "points_ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    source_type: Mapped[PointSourceType] = mapped_column(Enum(PointSourceType), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    points: Mapped[int] = mapped_column(Integer, nullable=False)  # negative on compensating/revoke rows
    reason_en: Mapped[str] = mapped_column(String(255), nullable=False)
    reason_fa: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(TZDateTime(), server_default=func.now(), index=True)

    user: Mapped["User"] = relationship(foreign_keys=[user_id])


class Badge(Base):
    """Static catalog of earnable badges -- rows are seeded from
    app/gamification/badges.py:BADGE_DEFINITIONS at startup (see
    app.gamification.badges.sync_badge_catalog), not created through the
    API. Kept as a DB table rather than pure code so UserBadge can carry
    a normal foreign key and so a future admin UI could manage seasonal
    badges without a code deploy."""

    __tablename__ = "badges"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(60), unique=True, nullable=False, index=True)
    name_en: Mapped[str] = mapped_column(String(120), nullable=False)
    name_fa: Mapped[str] = mapped_column(String(120), nullable=False)
    description_en: Mapped[str] = mapped_column(String(255), nullable=False)
    description_fa: Mapped[str] = mapped_column(String(255), nullable=False)
    icon_key: Mapped[str] = mapped_column(String(60), nullable=False)  # SVG icon key resolved client-side, never a binary blob
    is_seasonal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class UserBadge(Base):
    """One earned badge. `period_key` (e.g. "2026-08") scopes a seasonal
    badge to the period it was earned in and is what lets it be
    re-earned next period.

    Two constraints, because SQL treats NULL as distinct from itself:
    the plain (user_id, badge_id, period_key) constraint is what
    de-duplicates a *seasonal* badge across periods, but does nothing
    for a one-time milestone badge (period_key IS NULL) -- Postgres and
    SQLite both happily accept multiple NULL-period rows for the same
    (user_id, badge_id) under that constraint alone. The partial index
    below is what actually makes a milestone badge earnable only once,
    including under a race between two concurrent award_points() calls
    that both pass the application-level `already_held` check before
    either has committed."""

    __tablename__ = "user_badges"
    __table_args__ = (
        UniqueConstraint("user_id", "badge_id", "period_key", name="uq_user_badges_user_badge_period"),
        Index(
            "uq_user_badges_milestone_once",
            "user_id",
            "badge_id",
            unique=True,
            postgresql_where=text("period_key IS NULL"),
            sqlite_where=text("period_key IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    badge_id: Mapped[int] = mapped_column(ForeignKey("badges.id", ondelete="CASCADE"), nullable=False)
    period_key: Mapped[str | None] = mapped_column(String(20), nullable=True)
    awarded_at: Mapped[datetime] = mapped_column(TZDateTime(), server_default=func.now())

    user: Mapped["User"] = relationship(foreign_keys=[user_id])
    badge: Mapped["Badge"] = relationship()


class GamificationSettings(Base):
    """One row per Organization -- the admin-facing off switch (design
    principle #6 in the R&D doc: some teams don't want a competitive
    culture, and that must work even on a Pro/VIP plan). When
    `enabled=False`, app.gamification.engine.award_points becomes a
    no-op: no new points accrue, but existing history is never deleted,
    so re-enabling later picks up exactly where the team left off."""

    __tablename__ = "gamification_settings"

    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    leaderboard_default_period: Mapped[str] = mapped_column(String(10), default="weekly", nullable=False)  # "weekly"|"monthly"|"all_time"
    # Section 3.4 of the R&D doc: an org can choose to keep admins out of
    # the member-facing sales leaderboard so a manager's own activity
    # doesn't read as "competing" with their team.
    include_admins_in_leaderboard: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Custom currency branding: an org can rename the generic "points"
    # into its own token -- "ACEWIN Coin" / "سکه اکرمی" / a coin emoji --
    # so the whole panel reads as *their* program, not a stock feature.
    # Every number is still a plain PointsLedger.points int underneath;
    # this only ever changes the label/icon shown next to it.
    token_name_en: Mapped[str] = mapped_column(String(40), default="Points", nullable=False)
    token_name_fa: Mapped[str] = mapped_column(String(40), default="امتیاز", nullable=False)
    token_icon: Mapped[str] = mapped_column(String(8), default="🏆", nullable=False)
    updated_at: Mapped[datetime] = mapped_column(TZDateTime(), server_default=func.now(), onupdate=func.now())


# ---------------------------------------------------------------------------
# Support Requests (tenant user -> Platform Admin)
# ---------------------------------------------------------------------------


class SupportRequestStatus(str, enum.Enum):
    open = "open"
    in_progress = "in_progress"
    resolved = "resolved"


class SupportRequest(Base):
    """A message any signed-in user can send straight to the Platform
    Admin (ali@acewin.ir today, via PLATFORM_ADMIN_EMAILS) -- "I need X",
    a bug report, a billing question, anything that isn't a self-service
    CRM action. Shows up in the Platform Admin panel's "Requests" tab
    (see app/routers/platform_admin.py) and triggers an admin
    notification email (see app/email.py) the moment it's filed.

    Deliberately its own table rather than reusing AgentActionLog: this
    is a human message that expects a human reply and has its own
    open -> in_progress -> resolved lifecycle, not a system-recorded
    fact about a CRM mutation.
    """

    __tablename__ = "support_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[SupportRequestStatus] = mapped_column(
        Enum(SupportRequestStatus), default=SupportRequestStatus.open, nullable=False, index=True
    )
    # The Platform Admin's reply, set together with status when they act on
    # the request. Nullable until then -- there's no separate reply table
    # since, unlike a support ticket thread, this is a single request/single
    # response exchange (a fast, teenager-team-of-five-sized workflow, not a
    # full helpdesk).
    admin_reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime(), server_default=func.now(), index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(TZDateTime(), nullable=True)

    organization: Mapped["Organization"] = relationship()
    user: Mapped["User"] = relationship()


class PublicFeedbackCategory(str, enum.Enum):
    suggestion = "suggestion"
    complaint = "complaint"
    question = "question"


class PublicFeedback(Base):
    """A comment/complaint/suggestion submitted anonymously from the
    public marketing site's homepage (see frontend src/pages/Home.tsx) --
    NOT a tenant's own support request (that's SupportRequest above,
    filed by a signed-in user about their own account). A site visitor
    filing this may not even have an account yet, so there is
    deliberately no organization_id/user_id here.

    Mirrors SupportRequest's own two-destinations design: every
    submission lands in this table (read in the Platform Admin panel's
    Requests tab -- see app/routers/platform_admin.py) and triggers the
    same admin notification email (app/email.py) to
    ali@acewin.ir/PLATFORM_ADMIN_EMAILS, so nothing filed on the public
    site needs a separate inbox to watch. Reuses SupportRequestStatus
    for the same open -> in_progress -> resolved lifecycle and reply
    shape rather than inventing a parallel one.
    """

    __tablename__ = "public_feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category: Mapped[PublicFeedbackCategory] = mapped_column(
        Enum(PublicFeedbackCategory), default=PublicFeedbackCategory.suggestion, nullable=False, index=True
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[SupportRequestStatus] = mapped_column(
        Enum(SupportRequestStatus), default=SupportRequestStatus.open, nullable=False, index=True
    )
    admin_reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TZDateTime(), server_default=func.now(), index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(TZDateTime(), nullable=True)
