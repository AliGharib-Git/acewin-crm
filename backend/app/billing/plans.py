"""
Plan definitions: the single source of truth for what BASIC / PRO / VIP
each unlock, in both directions --

  - `FEATURES`: feature_code -> which plans have it enabled at all
    (a boolean gate: "ai.actions" either works on this plan or it
    doesn't).
  - `LIMITS`: metric -> numeric ceiling per plan (`None` = unlimited).
    A limit of 0 is a legitimate value (a feature that's plan-gated by
    both flag AND count); a limit of None is genuinely unlimited.

This is intentionally plain data, not a database table: entitlements
change with a code deploy (a new feature ships, a limit gets adjusted)
far more often than per-tenant, so keeping them in code -- reviewed,
tested, deployed like any other logic -- is more honest than a DB
table implying they're an ops-editable runtime setting they're not
(yet -- an admin-editable override table is a reasonable follow-up
once there's a real pricing/ops team making that call). What IS
per-tenant is which plan an org is ON, and that lives in the
Subscription row (see models.py) and is what every check below is
keyed by.

Feature codes deliberately match app/ai/permissions.py-style dotted
names (`crm.contacts`, `ai.copilot`, ...) per section 8 of the product
spec ("Entitlement Engine").
"""
from dataclasses import dataclass, field

from app.models import SubscriptionPlan

PLAN_ORDER = [SubscriptionPlan.basic, SubscriptionPlan.pro, SubscriptionPlan.vip]


@dataclass(frozen=True)
class PlanDefinition:
    plan: SubscriptionPlan
    name_en: str
    name_fa: str
    tagline_en: str
    tagline_fa: str
    monthly_price_toman: int | None  # None = custom/contact-sales pricing (no plan currently uses this -- Customized is handled outside the plan model, see pricing.enterpriseCta)
    yearly_price_toman: int | None  # per year, already discounted vs. 12x monthly
    features: set[str] = field(default_factory=set)
    limits: dict[str, int | None] = field(default_factory=dict)  # None = unlimited
    coming_soon: bool = False  # plan exists in the data model but isn't sellable yet (no plan currently sets this)


_BASIC_FEATURES = {
    "crm.contacts", "crm.companies", "crm.deals", "crm.tasks", "crm.pipeline",
    "reports.basic", "ai.copilot",
}
_PRO_FEATURES = _BASIC_FEATURES | {
    "analytics.advanced", "sales.forecasting", "kpi.management", "okr.management",
    "ai.actions", "ai.insights", "team.management", "reports.advanced",
    # Points/levels/leaderboard/badges -- see docs/gamification-rnd.md.
    # Pro-gated for the same reason team.management is: it only becomes
    # meaningful once there's a multi-person team to have a leaderboard
    # with (Basic caps at 3 users; Pro's 15-user ceiling is where real
    # team competition starts).
    "gamification.core",
}
_VIP_FEATURES = _PRO_FEATURES | {
    "erp.foundation", "advanced.permissions", "audit.logs", "ai.actions.controlled",
    "deployment.custom",
}

# Pricing (updated Sep 1 2026 per founders' decision):
#   - BASIC: 2,600,000 Toman/month flat, up to 3 users.
#   - PRO: 9,600,000 Toman/month flat (not per-seat), up to 15 users.
#   - VIP: 15,600,000 Toman/month flat, self-serve -- no longer
#     coming_soon. Custom/bespoke deployments beyond VIP are handled
#     as a separate "Customized" conversation with the sales team
#     (see pricing.enterpriseTitle / pricing.enterpriseCta on the
#     Pricing page), not through this plan's own pricing.
# Yearly prices are 10x the monthly rate (2 months free vs. paying
# monthly every month), consistent across all three plans.
PLAN_DEFINITIONS: dict[SubscriptionPlan, PlanDefinition] = {
    SubscriptionPlan.basic: PlanDefinition(
        plan=SubscriptionPlan.basic,
        name_en="Basic",
        name_fa="پایه",
        tagline_en="For freelancers and early-stage teams",
        tagline_fa="برای شروع حرفه‌ای",
        monthly_price_toman=2_600_000,
        yearly_price_toman=26_000_000,  # 2 months free vs. paying monthly
        features=_BASIC_FEATURES,
        limits={
            "users": 3,
            "contacts": 500,
            "companies": 200,
            "deals": 300,
            "ai_requests_per_month": 50,
            "storage_mb": 200,
        },
    ),
    SubscriptionPlan.pro: PlanDefinition(
        plan=SubscriptionPlan.pro,
        name_en="Pro",
        name_fa="حرفه‌ای",
        tagline_en="For growing sales teams",
        tagline_fa="برای تیم‌های در حال رشد",
        monthly_price_toman=9_600_000,
        yearly_price_toman=96_000_000,  # 2 months free vs. paying monthly
        features=_PRO_FEATURES,
        limits={
            "users": 15,
            "contacts": 10_000,
            "companies": 5_000,
            "deals": 10_000,
            "ai_requests_per_month": 1_000,
            "storage_mb": 5_000,
        },
    ),
    SubscriptionPlan.vip: PlanDefinition(
        plan=SubscriptionPlan.vip,
        name_en="VIP / Enterprise",
        name_fa="سازمانی",
        tagline_en="For organizations with custom needs",
        tagline_fa="برای سازمان‌ها",
        monthly_price_toman=15_600_000,
        yearly_price_toman=156_000_000,  # 2 months free vs. paying monthly
        features=_VIP_FEATURES,
        limits={
            "users": None,
            "contacts": None,
            "companies": None,
            "deals": None,
            "ai_requests_per_month": 10_000,  # generous, not "unlimited" -- an actual API cost sits behind this one
            "storage_mb": 50_000,
        },
        # VIP now has a real, self-serve monthly price -- no longer
        # coming_soon. Fully bespoke deployments are sold separately
        # as "Customized", through the sales-contact flow on the
        # Pricing page (pricing.enterpriseTitle / enterpriseCta),
        # not through this plan.
        coming_soon=False,
    ),
}


def plan_rank(plan: SubscriptionPlan) -> int:
    return PLAN_ORDER.index(plan)


def has_feature(plan: SubscriptionPlan, feature_code: str) -> bool:
    return feature_code in PLAN_DEFINITIONS[plan].features


def get_limit(plan: SubscriptionPlan, metric: str) -> int | None:
    """None means unlimited. A KeyError here is a bug (an unknown metric
    name), not a "no limit" -- callers should only pass metrics that
    appear in every plan's `limits` dict."""
    return PLAN_DEFINITIONS[plan].limits[metric]
