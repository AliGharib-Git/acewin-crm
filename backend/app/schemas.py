from datetime import datetime, date
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import (
    ActivityType,
    BillingType,
    ContactPriority,
    ContactStatus,
    PublicFeedbackCategory,
    SubscriptionPlan,
    SubscriptionStatus,
    TaskPriority,
    TaskStatus,
    TaskType,
    UserRole,
)


class UserBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    full_name: str
    email: str
    role: UserRole
    organization_id: int
    # Cross-tenant Platform Admin access (see app/deps.py:is_platform_admin).
    # NOT derived from `role` -- deliberately set by the router from the
    # PLATFORM_ADMIN_EMAILS allowlist, since UserOut/UserBrief are built
    # with `from_attributes=True` off the ORM row and User has no such
    # column. Defaults to False; auth.py overwrites it after validation.
    is_platform_admin: bool = False


class OrganizationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    slug: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
    # Registration always creates a brand-new organization with this
    # user as its first admin -- there is no "join an existing
    # organization by email domain" flow yet (that needs an invitation
    # system, tracked as a follow-up). See routers/auth.py:register.
    organization_name: str = Field(min_length=1, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserBrief


class UserOut(UserBrief):
    is_active: bool
    created_at: datetime
    restricted_permissions: list[str] = []


class UserRoleUpdate(BaseModel):
    role: UserRole


class UserPermissionsUpdate(BaseModel):
    """Full replace of one user's restricted-permission set -- the admin
    UI sends the complete list of keys that should be revoked, not a
    diff, so a stale client can't accidentally re-grant something
    another admin just restricted."""

    restricted_permissions: list[str] = []


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    full_name: str = Field(min_length=1, max_length=255)
    role: UserRole = UserRole.member


class TagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    color: str = "#1B3A63"


class TagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    color: str


class CatalogCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    order: int = 0
    color: str = "#1B3A63"


class CatalogCategoryUpdate(BaseModel):
    name: str | None = None
    order: int | None = None
    color: str | None = None


class CatalogCategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    order: int
    color: str
    item_count: int = 0


class CatalogItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    sku: str | None = None
    price: float = Field(default=0, ge=0)
    currency: str = "USD"
    billing_type: BillingType = BillingType.one_time
    category_id: int | None = None
    is_active: bool = True


class CatalogItemUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    sku: str | None = None
    price: float | None = Field(default=None, ge=0)
    currency: str | None = None
    billing_type: BillingType | None = None
    category_id: int | None = None
    is_active: bool | None = None


class CatalogItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str | None
    sku: str | None
    price: float
    currency: str
    billing_type: BillingType
    category_id: int | None
    category_name: str | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CompanyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    industry: str | None = None
    website: str | None = None
    phone: str | None = None
    address: str | None = None
    notes: str | None = None


class CompanyUpdate(BaseModel):
    name: str | None = None
    industry: str | None = None
    website: str | None = None
    phone: str | None = None
    address: str | None = None
    notes: str | None = None


class CompanyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    industry: str | None
    website: str | None
    phone: str | None
    address: str | None
    notes: str | None
    created_at: datetime
    contact_count: int = 0
    open_deal_value: float = 0


class ContactCreate(BaseModel):
    first_name: str = Field(min_length=1, max_length=120)
    last_name: str = ""
    email: EmailStr | None = None
    phone: str | None = None
    job_title: str | None = None
    status: ContactStatus = ContactStatus.lead
    priority: ContactPriority = ContactPriority.medium
    source: str | None = None
    notes: str | None = None
    company_id: int | None = None
    assigned_to_id: int | None = None
    tag_ids: list[int] = []


class ContactUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    job_title: str | None = None
    status: ContactStatus | None = None
    priority: ContactPriority | None = None
    source: str | None = None
    notes: str | None = None
    company_id: int | None = None
    assigned_to_id: int | None = None
    tag_ids: list[int] | None = None


class EngagementOut(BaseModel):
    """Computed, not stored -- see app/scoring/engine.py. Attached to
    ContactOut/ContactListItem by the router after the ORM row loads."""

    score: int
    label: str
    total_activities: int
    last_activity_at: datetime | None
    days_since_last_activity: int | None
    open_deal_count: int
    open_deal_value: float
    open_task_count: int


class ContactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    first_name: str
    last_name: str
    email: str | None
    phone: str | None
    job_title: str | None
    status: ContactStatus
    priority: ContactPriority
    source: str | None
    notes: str | None
    company_id: int | None
    company_name: str | None = None
    assigned_to: UserBrief | None
    tags: list[TagOut]
    engagement: EngagementOut | None = None
    created_at: datetime
    updated_at: datetime


class ContactListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    first_name: str
    last_name: str
    email: str | None
    phone: str | None
    status: ContactStatus
    priority: ContactPriority
    company_id: int | None
    company_name: str | None = None
    assigned_to: UserBrief | None
    tags: list[TagOut]
    engagement: EngagementOut | None = None
    updated_at: datetime


class PipelineStageCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    order: int = 0
    color: str = "#1B3A63"
    is_won: bool = False
    is_lost: bool = False


class PipelineStageUpdate(BaseModel):
    name: str | None = None
    order: int | None = None
    color: str | None = None
    is_won: bool | None = None
    is_lost: bool | None = None


class PipelineStageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    order: int
    color: str
    is_won: bool
    is_lost: bool


class DealItemInput(BaseModel):
    """One line on a deal's quote. Either pick from the catalog
    (catalog_item_id set -- name/unit_price default to that item's current
    values unless explicitly overridden, e.g. a one-off discount) or type a
    fully custom line (catalog_item_id omitted, name required)."""

    catalog_item_id: int | None = None
    name: str | None = Field(default=None, max_length=255)
    unit_price: float | None = Field(default=None, ge=0)
    quantity: int = Field(default=1, ge=1)


class DealItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    catalog_item_id: int | None
    name: str
    unit_price: float
    quantity: int
    line_total: float = 0


class DealCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    value: float = 0
    probability: int = Field(default=50, ge=0, le=100)
    expected_close_date: date | None = None
    notes: str | None = None
    stage_id: int
    contact_id: int | None = None
    company_id: int | None = None
    assigned_to_id: int | None = None
    # When non-empty, `value` above is ignored and recomputed as the sum
    # of these lines (quantity * unit_price) -- see routers/deals.py.
    items: list[DealItemInput] = []


class DealUpdate(BaseModel):
    title: str | None = None
    value: float | None = None
    probability: int | None = Field(default=None, ge=0, le=100)
    expected_close_date: date | None = None
    notes: str | None = None
    stage_id: int | None = None
    contact_id: int | None = None
    company_id: int | None = None
    assigned_to_id: int | None = None
    # Omitted -> leave existing lines untouched. Present (including `[]`,
    # which clears the quote) -> replace the deal's lines wholesale, the
    # same "full replace" semantics ContactUpdate.tag_ids already uses.
    items: list[DealItemInput] | None = None


class DealOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    value: float
    probability: int
    expected_close_date: date | None
    notes: str | None
    stage_id: int
    stage_name: str | None = None
    contact_id: int | None
    contact_name: str | None = None
    company_id: int | None
    company_name: str | None = None
    assigned_to: UserBrief | None
    items: list[DealItemOut] = []
    created_at: datetime
    updated_at: datetime
    closed_at: datetime | None


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    due_date: datetime | None = None
    priority: TaskPriority = TaskPriority.medium
    task_type: TaskType = TaskType.general
    reminder_minutes_before: int | None = 15
    assigned_to_id: int | None = None
    contact_id: int | None = None
    deal_id: int | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    due_date: datetime | None = None
    priority: TaskPriority | None = None
    status: TaskStatus | None = None
    task_type: TaskType | None = None
    reminder_minutes_before: int | None = None
    assigned_to_id: int | None = None
    contact_id: int | None = None
    deal_id: int | None = None


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    description: str | None
    due_date: datetime | None
    priority: TaskPriority
    status: TaskStatus
    task_type: TaskType
    reminder_minutes_before: int | None
    assigned_to: UserBrief | None
    contact_id: int | None
    contact_name: str | None = None
    contact_phone: str | None = None
    deal_id: int | None
    deal_title: str | None = None
    created_at: datetime
    completed_at: datetime | None


class ActivityCreate(BaseModel):
    type: ActivityType = ActivityType.note
    content: str = Field(min_length=1)
    contact_id: int | None = None
    deal_id: int | None = None


class ActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    type: ActivityType
    content: str
    contact_id: int | None
    deal_id: int | None
    created_by: UserBrief | None
    created_at: datetime


class DashboardSummary(BaseModel):
    total_contacts: int
    total_companies: int
    open_deals_count: int
    open_deals_value: float
    won_this_month_count: int
    won_this_month_value: float
    tasks_due_today: int
    overdue_tasks: int


class FunnelStage(BaseModel):
    stage_id: int
    stage_name: str
    color: str
    count: int
    value: float


class RevenuePoint(BaseModel):
    period: str
    won_value: float


class WonLostPoint(BaseModel):
    period: str
    won_count: int
    lost_count: int


class Page(BaseModel):
    items: list
    total: int
    page: int
    page_size: int


class AgentActionLogOut(BaseModel):
    """One entry in ACEWIN's unified audit trail -- a write performed
    either by a human through the REST API (source="api") or by the
    Copilot Action Agent through tool-calling (source="copilot")."""

    id: int
    tool_name: str
    source: str
    status: str
    arguments: dict
    result: dict | None = None
    error_message: str | None = None
    entity_type: str | None = None
    entity_id: int | None = None
    is_undoable: bool
    undone_at: datetime | None = None
    user_name: str | None = None
    created_at: datetime


class KPISeriesPoint(BaseModel):
    period: str
    value: float


class KPIStatsOut(BaseModel):
    mean: float
    median: float
    min: float
    max: float
    stdev: float
    volatility_pct: float | None = None


class KPIBreakdownEntry(BaseModel):
    label: str
    value: float


class KPIOut(BaseModel):
    """One KPI Engine metric -- current_value/trend/prediction are always
    computed live (app/kpi/engine.py); target is the only stored, and
    only admin-settable, part of this."""

    key: str
    name: str
    description: str = ""
    department: str
    unit: str
    higher_is_better: bool
    supports_trend: bool
    current_value: float
    previous_value: float | None = None
    change_pct: float | None = None
    trend: list[KPISeriesPoint] | None = None
    target: float | None = None
    risk_level: str
    prediction_next: float | None = None
    prediction_low: float | None = None
    prediction_high: float | None = None
    stats: KPIStatsOut | None = None
    breakdown: list[KPIBreakdownEntry] | None = None


class KPITargetUpdate(BaseModel):
    target_value: float = Field(gt=0)


class KPIExplanation(BaseModel):
    kpi_key: str
    explanation: str
    generated_by: str


# ---------- OKR Engine ----------


class KeyResultUpdateIn(BaseModel):
    value: float
    note: str | None = None


class KeyResultUpdateOut(BaseModel):
    id: int
    value: float
    note: str | None = None
    created_by_name: str | None = None
    created_at: datetime


class KeyResultCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    measurement_type: str = Field(pattern="^(metric|milestone)$")
    weight: float = Field(default=1.0, gt=0, le=10)
    unit: str | None = None
    baseline_value: float | None = None
    target_value: float | None = None
    current_value: float | None = None
    linked_kpi_key: str | None = None
    owner_id: int | None = None


class KeyResultEdit(BaseModel):
    title: str | None = None
    weight: float | None = Field(default=None, gt=0, le=10)
    baseline_value: float | None = None
    target_value: float | None = None
    current_value: float | None = None
    is_done: bool | None = None
    owner_id: int | None = None


class KeyResultOut(BaseModel):
    id: int
    objective_id: int
    title: str
    measurement_type: str
    weight: float
    unit: str | None = None
    baseline_value: float | None = None
    target_value: float | None = None
    current_value: float | None = None
    is_done: bool
    linked_kpi_key: str | None = None
    owner: UserBrief | None = None
    score_pct: float
    updates: list[KeyResultUpdateOut] = []


class ObjectiveCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    department: str = "general"
    period_key: str = Field(pattern=r"^\d{4}-Q[1-4]$")
    owner_id: int | None = None


class ObjectiveEdit(BaseModel):
    title: str | None = None
    description: str | None = None
    department: str | None = None
    status: str | None = Field(default=None, pattern="^(draft|active|completed|archived)$")
    owner_id: int | None = None


class ObjectiveOut(BaseModel):
    id: int
    title: str
    description: str | None = None
    department: str
    period_key: str
    start_date: date
    end_date: date
    status: str
    owner: UserBrief | None = None
    created_by: UserBrief | None = None
    key_results: list[KeyResultOut] = []
    score_pct: float
    expected_pct: float
    gap_pct: float
    risk_level: str
    days_remaining: int | None = None
    created_at: datetime
    updated_at: datetime


class OKRScoreboard(BaseModel):
    period_key: str
    company_score: float | None = None
    department_scores: dict[str, float | None]
    objectives: list[ObjectiveOut]


class ObjectiveExplanation(BaseModel):
    objective_id: int
    explanation: str
    generated_by: str


# --- Billing / Subscription -------------------------------------------


class PlanOut(BaseModel):
    plan: str
    name: str
    tagline: str
    monthly_price_toman: int | None  # None = custom/contact-sales pricing (VIP)
    yearly_price_toman: int | None
    is_custom_pricing: bool
    is_coming_soon: bool = False
    features: list[str]
    limits: dict[str, int | None]
    is_current: bool = False


class UsageMetricOut(BaseModel):
    metric: str
    current: int
    limit: int | None
    percent_used: float | None


class SubscriptionOut(BaseModel):
    plan: str
    effective_plan: str
    status: str
    billing_cycle: str
    trial_ends_at: datetime | None
    current_period_end: datetime | None
    is_trial_expired: bool
    usage: list[UsageMetricOut]


class PlanChangeRequest(BaseModel):
    plan: SubscriptionPlan
    billing_cycle: str = Field(default="monthly", pattern="^(monthly|yearly)$")


# --- Platform Admin (cross-tenant, PLATFORM_ADMIN_EMAILS-gated) --------


class PlatformOrganizationOut(BaseModel):
    """One row of the Platform Admin organizations table -- enough to
    triage every tenant at a glance without opening each one."""

    id: int
    name: str
    slug: str
    is_active: bool
    created_at: datetime
    user_count: int
    plan: str
    effective_plan: str
    status: str
    trial_ends_at: datetime | None
    is_trial_expired: bool
    limit_overrides: dict[str, int]
    feature_overrides: dict[str, bool]


class PlatformOrganizationDetailOut(PlatformOrganizationOut):
    usage: list[UsageMetricOut]
    available_features: list[str]  # every feature code that exists on any plan, for the override picker


class SupportRequestCreate(BaseModel):
    """What a tenant user submits from the in-app "Contact support" form
    (any signed-in user, not just their org's admin)."""

    subject: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1)


class SupportRequestOut(BaseModel):
    """A user's own view of a request they filed."""

    id: int
    subject: str
    message: str
    status: str
    admin_reply: str | None = None
    created_at: datetime
    resolved_at: datetime | None = None


class SupportRequestAdminOut(SupportRequestOut):
    """The Platform Admin's view: same fields, plus who/where it came
    from, since a Platform Admin is reading these across every tenant."""

    organization_id: int
    organization_name: str
    user_name: str
    user_email: str


class SupportRequestAdminUpdate(BaseModel):
    """A Platform Admin resolving/replying to a request. Any field left
    unset is left unchanged, so a status-only update (e.g. "in_progress")
    doesn't require re-sending an existing reply."""

    status: str | None = Field(default=None, pattern="^(open|in_progress|resolved)$")
    admin_reply: str | None = None


class PublicFeedbackCreate(BaseModel):
    """What a site visitor submits from the homepage's comments/
    complaints form -- no account required."""

    name: str = Field(min_length=1, max_length=150)
    email: EmailStr | None = None
    category: PublicFeedbackCategory = PublicFeedbackCategory.suggestion
    message: str = Field(min_length=1)


class PublicFeedbackOut(BaseModel):
    """What's returned to the visitor right after they submit -- just
    confirmation of what was recorded, no cross-tenant/admin fields."""

    id: int
    category: str
    status: str
    created_at: datetime


class PublicFeedbackAdminOut(BaseModel):
    """The Platform Admin's view in the Requests tab's Feedback sub-tab."""

    id: int
    name: str
    email: str | None
    category: str
    message: str
    status: str
    admin_reply: str | None = None
    created_at: datetime
    resolved_at: datetime | None = None


class PublicFeedbackAdminUpdate(BaseModel):
    status: str | None = Field(default=None, pattern="^(open|in_progress|resolved)$")
    admin_reply: str | None = None


class PlatformAgentActionLogOut(BaseModel):
    """AgentActionLog rows for the Platform Admin's cross-tenant "Requests"
    tab -- same shape as AgentActionLogOut, plus which org/user it came
    from, since this view spans every tenant rather than being scoped to
    one (see AgentActionLogOut in app/routers/agent_actions.py for the
    single-tenant equivalent)."""

    id: int
    tool_name: str
    source: str
    status: str
    entity_type: str | None = None
    entity_id: int | None = None
    organization_id: int
    organization_name: str
    user_name: str | None = None
    created_at: datetime


class OrgStatusUpdate(BaseModel):
    is_active: bool


class OrgSubscriptionAdminUpdate(BaseModel):
    """Direct, unconditional subscription edit for a Platform Admin --
    unlike PATCH /api/billing/subscription (routers/billing.py), this
    is allowed to set a `coming_soon` plan (e.g. hand-pick an early
    customer onto a plan not yet open for public sign-ups) and to set
    status/trial_ends_at directly rather than only through
    change_plan()'s trial-clearing behavior."""

    plan: SubscriptionPlan | None = None
    status: SubscriptionStatus | None = None
    billing_cycle: str | None = Field(default=None, pattern="^(monthly|yearly)$")
    trial_ends_at: datetime | None = None
    clear_trial_end: bool = False  # explicit flag so "omit the field" and "null it out" are distinguishable


class OrgLimitOverridesUpdate(BaseModel):
    """Full replace of one org's limit overrides, the same pattern as
    UserPermissionsUpdate above -- the admin UI sends the complete map
    it wants in effect, not a diff. Omit a metric to fall back to the
    plan's own limit for it."""

    overrides: dict[str, int]


class OrgFeatureOverridesUpdate(BaseModel):
    """Full replace of one org's feature overrides. true force-grants,
    false force-revokes, an absent key defers to the plan."""

    overrides: dict[str, bool]


# --- Gamification Engine (docs/gamification-rnd.md) ---------------------


class GamificationSettingsOut(BaseModel):
    enabled: bool
    leaderboard_default_period: str
    include_admins_in_leaderboard: bool
    token_name_en: str
    token_name_fa: str
    token_icon: str


class GamificationSettingsUpdate(BaseModel):
    enabled: bool | None = None
    leaderboard_default_period: str | None = Field(default=None, pattern="^(weekly|monthly|all_time)$")
    include_admins_in_leaderboard: bool | None = None
    token_name_en: str | None = Field(default=None, max_length=40)
    token_name_fa: str | None = Field(default=None, max_length=40)
    token_icon: str | None = Field(default=None, max_length=8)


class BadgeOut(BaseModel):
    code: str
    name: str
    description: str
    icon_key: str
    is_seasonal: bool
    earned: bool
    awarded_at: datetime | None = None


class LeaderboardEntryOut(BaseModel):
    user_id: int
    full_name: str
    role: str
    is_you: bool = False
    points: int
    rank: int
    level: int
    level_title: str


class GamificationSummaryOut(BaseModel):
    """None fields mean gamification is switched off org-wide (see
    GamificationSettings.enabled) -- `enabled=False` distinguishes that
    cleanly from a 402 "you need to upgrade", which is a plan problem,
    not an admin preference."""

    enabled: bool
    total_points: int | None = None
    level: int | None = None
    level_title: str | None = None
    points_in_level: int | None = None
    points_for_next_level: int | None = None
    progress_ratio: float | None = None
    weekly_points: int | None = None
    monthly_points: int | None = None
    weekly_rank: int | None = None
    monthly_rank: int | None = None
    badge_count: int | None = None
    token_name: str | None = None
    token_icon: str | None = None
    # Accountability -- the follow-through side, not just the rewards
    # side (see app/gamification/engine.py:task_accountability). Tasks
    # ASSIGNED in the last 30 days vs. how many actually got COMPLETED,
    # plus how many are sitting overdue right now.
    tasks_completed: int | None = None
    tasks_total: int | None = None
    tasks_overdue: int | None = None


class LedgerEntryOut(BaseModel):
    id: int
    source_type: str
    points: int
    reason: str
    created_at: datetime


class LedgerPage(BaseModel):
    items: list[LedgerEntryOut]
    total: int
    page: int
    page_size: int


# --- Gamification admin panel -------------------------------------------


class AdminUserSummaryOut(BaseModel):
    user_id: int
    full_name: str
    role: str
    total_points: int
    level: int
    level_title: str
    badge_count: int
    weekly_points: int
    monthly_points: int
    tasks_completed: int
    tasks_total: int
    tasks_overdue: int


class AdminLedgerEntryOut(BaseModel):
    id: int
    user_id: int
    full_name: str
    source_type: str
    points: int
    reason: str
    created_at: datetime


class AdminLedgerPage(BaseModel):
    items: list[AdminLedgerEntryOut]
    total: int
    page: int
    page_size: int
