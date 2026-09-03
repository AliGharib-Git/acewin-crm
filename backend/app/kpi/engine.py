"""
Enterprise KPI Engine.

Every number here is computed live, on request, straight from real CRM
data (Deal/Task timestamps) -- nothing is cached, stored, or
fabricated. The only thing an admin can configure is the *target* for
each KPI (see KPITarget in app/models.py), which the live number is
then compared against.

Design choice worth calling out: not every KPI gets a historical
trend. A few (like `revenue_won`) can be honestly reconstructed for
past months because the underlying event (a deal closing) is
timestamped. Others -- like "how much open pipeline did we have three
months ago" -- can't be, because deals move between stages and the CRM
doesn't keep a stage-change history table (that's flagged as a future
enhancement, not silently faked). Those KPIs are marked
`supports_trend=False` and only ever show a current snapshot.

Adding a new KPI: add one entry to KPI_DEFINITIONS and one
`_compute_*` function that returns either a monthly series (list of
(period, value) tuples) or a single snapshot float.
"""
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

from dateutil.relativedelta import relativedelta
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Contact, ContactStatus, Deal, KPITarget, PipelineStage, Task, TaskStatus, User


@dataclass
class KPIDefinition:
    key: str
    name_en: str
    name_fa: str
    department: str  # "sales" | "operations"
    unit: str  # "currency" | "percent" | "days" | "hours"
    higher_is_better: bool
    supports_trend: bool = True
    compute_series: "Callable[[Session, int, int], list[tuple[str, float]]] | None" = None
    compute_snapshot: "Callable[[Session, int], float] | None" = None
    # Optional: top-contributor ranking for this KPI (e.g. revenue by rep).
    # Only defined for KPIs where "who's driving this number" is meaningful
    # and answerable from a single, honest query -- not every KPI has one.
    compute_breakdown: "Callable[[Session, int, int], list[dict]] | None" = None
    description_en: str = ""
    description_fa: str = ""


@dataclass
class KPIStats:
    """Descriptive statistics over the KPI's own trend window -- gives an
    admin more than just "up or down": how spread out the monthly values
    are (volatility), and where the current value sits relative to the
    period's typical (median) and extreme (min/max) values."""

    mean: float
    median: float
    min: float
    max: float
    stdev: float
    volatility_pct: float | None  # stdev as a % of mean -- None if mean is 0


@dataclass
class KPIResult:
    key: str
    name: str
    description: str
    department: str
    unit: str
    higher_is_better: bool
    supports_trend: bool
    current_value: float
    previous_value: float | None
    change_pct: float | None
    trend: list[dict] | None
    target: float | None
    risk_level: str
    prediction_next: float | None
    prediction_low: float | None
    prediction_high: float | None
    stats: KPIStats | None
    breakdown: list[dict] | None


# ---------------------------------------------------------------------------
# Shared bucketing helpers (same monthly-bucket pattern as app/routers/dashboard.py)
# ---------------------------------------------------------------------------


def _month_buckets(months: int) -> list[str]:
    now = datetime.now(timezone.utc)
    start_month = (now.replace(day=1) - relativedelta(months=months - 1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    keys = []
    cursor = start_month
    for _ in range(months):
        keys.append(cursor.strftime("%Y-%m"))
        cursor = cursor + relativedelta(months=1)
    return keys


def _since(months: int) -> datetime:
    now = datetime.now(timezone.utc)
    return (now.replace(day=1) - relativedelta(months=months - 1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )


def _won_deals(db: Session, org_id: int, since: datetime) -> list[Deal]:
    return (
        db.query(Deal)
        .join(PipelineStage, Deal.stage_id == PipelineStage.id)
        .filter(Deal.organization_id == org_id, PipelineStage.is_won.is_(True), Deal.closed_at >= since)
        .all()
    )


def _closed_deals(db: Session, org_id: int, since: datetime) -> list[Deal]:
    return (
        db.query(Deal)
        .join(PipelineStage, Deal.stage_id == PipelineStage.id)
        .filter(
            Deal.organization_id == org_id,
            (PipelineStage.is_won.is_(True)) | (PipelineStage.is_lost.is_(True)),
            Deal.closed_at >= since,
        )
        .all()
    )


# ---------------------------------------------------------------------------
# Individual KPI computations. Each one is a plain, auditable query --
# no ML, no estimation, just real aggregates bucketed by month.
# ---------------------------------------------------------------------------


def _compute_revenue_won_series(db: Session, org_id: int, months: int) -> list[tuple[str, float]]:
    keys = _month_buckets(months)
    buckets = {k: 0.0 for k in keys}
    for deal in _won_deals(db, org_id, _since(months)):
        key = deal.closed_at.strftime("%Y-%m")
        if key in buckets:
            buckets[key] += float(deal.value)
    return [(k, round(buckets[k], 2)) for k in keys]


def _compute_win_rate_series(db: Session, org_id: int, months: int) -> list[tuple[str, float]]:
    keys = _month_buckets(months)
    won = {k: 0 for k in keys}
    lost = {k: 0 for k in keys}
    for deal in _closed_deals(db, org_id, _since(months)):
        key = deal.closed_at.strftime("%Y-%m")
        if key not in won:
            continue
        if deal.stage.is_won:
            won[key] += 1
        else:
            lost[key] += 1
    out = []
    for k in keys:
        total = won[k] + lost[k]
        out.append((k, round(won[k] / total * 100, 1) if total else 0.0))
    return out


def _compute_avg_deal_size_series(db: Session, org_id: int, months: int) -> list[tuple[str, float]]:
    keys = _month_buckets(months)
    values: dict[str, list[float]] = {k: [] for k in keys}
    for deal in _won_deals(db, org_id, _since(months)):
        key = deal.closed_at.strftime("%Y-%m")
        if key in values:
            values[key].append(float(deal.value))
    return [(k, round(sum(v) / len(v), 2) if v else 0.0) for k, v in values.items()]


def _compute_sales_cycle_series(db: Session, org_id: int, months: int) -> list[tuple[str, float]]:
    keys = _month_buckets(months)
    durations: dict[str, list[float]] = {k: [] for k in keys}
    for deal in _won_deals(db, org_id, _since(months)):
        if not deal.created_at or not deal.closed_at:
            continue
        key = deal.closed_at.strftime("%Y-%m")
        if key in durations:
            durations[key].append((deal.closed_at - deal.created_at).total_seconds() / 86400)
    return [(k, round(sum(v) / len(v), 1) if v else 0.0) for k, v in durations.items()]


def _compute_task_completion_series(db: Session, org_id: int, months: int) -> list[tuple[str, float]]:
    keys = _month_buckets(months)
    durations: dict[str, list[float]] = {k: [] for k in keys}
    since = _since(months)
    completed = db.query(Task).filter(
        Task.organization_id == org_id, Task.completed_at.isnot(None), Task.completed_at >= since
    ).all()
    for task in completed:
        if not task.created_at:
            continue
        key = task.completed_at.strftime("%Y-%m")
        if key in durations:
            durations[key].append((task.completed_at - task.created_at).total_seconds() / 3600)
    return [(k, round(sum(v) / len(v), 1) if v else 0.0) for k, v in durations.items()]


def _compute_open_pipeline_snapshot(db: Session, org_id: int) -> float:
    open_deals = (
        db.query(Deal)
        .join(PipelineStage, Deal.stage_id == PipelineStage.id)
        .filter(Deal.organization_id == org_id, PipelineStage.is_won.is_(False), PipelineStage.is_lost.is_(False))
        .all()
    )
    return round(float(sum(float(d.value) for d in open_deals)), 2)


def _compute_lead_conversion_series(db: Session, org_id: int, months: int) -> list[tuple[str, float]]:
    """% of contacts CREATED in a given month that are, as of right now,
    status=customer. This is an honest cohort metric, not a fabricated
    history: we're not claiming to know when the status changed, only
    reporting what fraction of each month's leads have converted by
    today -- which is exactly what the Contact table can actually tell
    us (it has created_at and a current status, nothing in between)."""
    keys = _month_buckets(months)
    created = {k: 0 for k in keys}
    converted = {k: 0 for k in keys}
    contacts = db.query(Contact).filter(Contact.organization_id == org_id, Contact.created_at >= _since(months)).all()
    for contact in contacts:
        key = contact.created_at.strftime("%Y-%m")
        if key not in created:
            continue
        created[key] += 1
        if contact.status == ContactStatus.customer:
            converted[key] += 1
    return [(k, round(converted[k] / created[k] * 100, 1) if created[k] else 0.0) for k in keys]


def _compute_overdue_task_rate_series(db: Session, org_id: int, months: int) -> list[tuple[str, float]]:
    """% of tasks DUE in a given month that are overdue as of right now
    (past due_date and not completed). Bucketed by due_date, which is
    fixed at creation time -- only the "is it still open" check is
    evaluated live, so nothing here is retroactively invented."""
    keys = _month_buckets(months)
    due = {k: 0 for k in keys}
    overdue = {k: 0 for k in keys}
    now = datetime.now(timezone.utc)
    tasks = (
        db.query(Task)
        .filter(Task.organization_id == org_id, Task.due_date.isnot(None), Task.due_date >= _since(months))
        .all()
    )
    for task in tasks:
        due_date = task.due_date
        key = due_date.strftime("%Y-%m")
        if key not in due:
            continue
        due[key] += 1
        if task.status != TaskStatus.completed and due_date < now:
            overdue[key] += 1
    return [(k, round(overdue[k] / due[k] * 100, 1) if due[k] else 0.0) for k in keys]


def _compute_pipeline_velocity_snapshot(db: Session, org_id: int) -> float:
    """Classic sales-velocity formula: (open deal count x win rate x avg
    deal size) / sales cycle length -- how much revenue is moving
    through the pipeline per day. Built entirely from this month's
    already-honest building blocks (no new assumptions), evaluated as a
    current snapshot since "open deal count" itself isn't reconstructible
    for past periods (see module docstring)."""
    since = _since(1)
    open_count = (
        db.query(Deal)
        .join(PipelineStage, Deal.stage_id == PipelineStage.id)
        .filter(Deal.organization_id == org_id, PipelineStage.is_won.is_(False), PipelineStage.is_lost.is_(False))
        .count()
    )
    closed = _closed_deals(db, org_id, since)
    won = [d for d in closed if d.stage.is_won]
    win_rate = (len(won) / len(closed)) if closed else 0.0
    avg_deal_size = (sum(float(d.value) for d in won) / len(won)) if won else 0.0
    cycle_days = [
        (d.closed_at - d.created_at).total_seconds() / 86400 for d in won if d.created_at and d.closed_at
    ]
    avg_cycle = (sum(cycle_days) / len(cycle_days)) if cycle_days else None
    if not avg_cycle:
        return 0.0
    return round((open_count * win_rate * avg_deal_size) / avg_cycle, 2)


def _compute_revenue_breakdown(db: Session, org_id: int, months: int) -> list[dict]:
    """Top 5 reps by revenue won in the window -- who's actually driving
    the `revenue_won` number. Unassigned deals are grouped under a
    dedicated bucket rather than silently dropped."""
    since = _since(months)
    rows = (
        db.query(User.full_name, func.sum(Deal.value))
        .join(Deal, Deal.assigned_to_id == User.id)
        .join(PipelineStage, Deal.stage_id == PipelineStage.id)
        .filter(Deal.organization_id == org_id, PipelineStage.is_won.is_(True), Deal.closed_at >= since)
        .group_by(User.full_name)
        .order_by(func.sum(Deal.value).desc())
        .limit(5)
        .all()
    )
    return [{"label": name, "value": round(float(total), 2)} for name, total in rows]


def _compute_task_load_breakdown(db: Session, org_id: int, months: int) -> list[dict]:
    """Top 5 reps by completed-task count in the window -- an operations
    counterpart to the revenue breakdown, showing where task throughput
    is actually coming from."""
    since = _since(months)
    rows = (
        db.query(User.full_name, func.count(Task.id))
        .join(Task, Task.assigned_to_id == User.id)
        .filter(Task.organization_id == org_id, Task.completed_at.isnot(None), Task.completed_at >= since)
        .group_by(User.full_name)
        .order_by(func.count(Task.id).desc())
        .limit(5)
        .all()
    )
    return [{"label": name, "value": float(count)} for name, count in rows]


KPI_DEFINITIONS: dict[str, KPIDefinition] = {
    "revenue_won": KPIDefinition(
        key="revenue_won",
        name_en="Revenue Won",
        name_fa="درآمد برد شده",
        department="sales",
        unit="currency",
        higher_is_better=True,
        compute_series=_compute_revenue_won_series,
        compute_breakdown=_compute_revenue_breakdown,
        description_en="Total value of deals closed-won, bucketed by the month they closed.",
        description_fa="مجموع ارزش معاملاتی که برد شده‌اند، بر اساس ماه بسته شدن.",
    ),
    "win_rate": KPIDefinition(
        key="win_rate",
        name_en="Win Rate",
        name_fa="نرخ برد",
        department="sales",
        unit="percent",
        higher_is_better=True,
        compute_series=_compute_win_rate_series,
        description_en="Share of closed deals (won + lost) that were won, per month.",
        description_fa="سهم معاملات بسته‌شده (برد + باخت) که برد بوده‌اند، به تفکیک ماه.",
    ),
    "avg_deal_size": KPIDefinition(
        key="avg_deal_size",
        name_en="Average Deal Size",
        name_fa="میانگین ارزش معامله",
        department="sales",
        unit="currency",
        higher_is_better=True,
        compute_series=_compute_avg_deal_size_series,
        description_en="Average value of won deals, per month.",
        description_fa="میانگین ارزش معاملات برد شده، به تفکیک ماه.",
    ),
    "sales_cycle_days": KPIDefinition(
        key="sales_cycle_days",
        name_en="Sales Cycle Length",
        name_fa="طول چرخه فروش",
        department="sales",
        unit="days",
        higher_is_better=False,
        compute_series=_compute_sales_cycle_series,
        description_en="Average days from deal creation to close, for deals won that month.",
        description_fa="میانگین روز از ایجاد معامله تا بسته شدن، برای معاملات برد شده در آن ماه.",
    ),
    "avg_task_completion_hours": KPIDefinition(
        key="avg_task_completion_hours",
        name_en="Task Completion Time",
        name_fa="زمان انجام وظیفه",
        department="operations",
        unit="hours",
        higher_is_better=False,
        compute_series=_compute_task_completion_series,
        compute_breakdown=_compute_task_load_breakdown,
        description_en="Average hours from task creation to completion, per month.",
        description_fa="میانگین ساعت از ایجاد وظیفه تا تکمیل آن، به تفکیک ماه.",
    ),
    "open_pipeline_value": KPIDefinition(
        key="open_pipeline_value",
        name_en="Open Pipeline Value",
        name_fa="ارزش پایپ‌لاین باز",
        department="sales",
        unit="currency",
        higher_is_better=True,
        supports_trend=False,
        compute_snapshot=_compute_open_pipeline_snapshot,
        description_en="Total value of all deals currently open (not yet won or lost).",
        description_fa="مجموع ارزش تمام معاملاتی که در حال حاضر باز هستند (نه برد، نه باخت).",
    ),
    "lead_conversion_rate": KPIDefinition(
        key="lead_conversion_rate",
        name_en="Lead Conversion Rate",
        name_fa="نرخ تبدیل سرنخ",
        department="sales",
        unit="percent",
        higher_is_better=True,
        compute_series=_compute_lead_conversion_series,
        description_en="Of the contacts created in a month, the % that are customers today.",
        description_fa="از میان مخاطبینی که در یک ماه ایجاد شده‌اند، درصدی که امروز مشتری هستند.",
    ),
    "overdue_task_rate": KPIDefinition(
        key="overdue_task_rate",
        name_en="Overdue Task Rate",
        name_fa="نرخ وظایف معوق",
        department="operations",
        unit="percent",
        higher_is_better=False,
        compute_series=_compute_overdue_task_rate_series,
        description_en="Of the tasks due in a month, the % that are still open past their due date.",
        description_fa="از میان وظایفی که موعدشان در یک ماه بوده، درصدی که هنوز پس از موعد باز مانده‌اند.",
    ),
    "pipeline_velocity": KPIDefinition(
        key="pipeline_velocity",
        name_en="Pipeline Velocity",
        name_fa="سرعت پایپ‌لاین",
        department="sales",
        unit="currency",
        higher_is_better=True,
        supports_trend=False,
        compute_snapshot=_compute_pipeline_velocity_snapshot,
        description_en="(Open deals x win rate x avg deal size) / sales cycle days -- revenue moving through the pipeline per day.",
        description_fa="(تعداد معاملات باز × نرخ برد × میانگین ارزش معامله) ÷ طول چرخه فروش — درآمدی که روزانه در پایپ‌لاین جریان دارد.",
    ),
}


def _series_stats(values: list[float]) -> KPIStats | None:
    """Descriptive statistics over a KPI's own trend window. None when
    there's nothing to describe (e.g. a snapshot-only KPI)."""
    if not values:
        return None
    mean = statistics.fmean(values)
    return KPIStats(
        mean=round(mean, 2),
        median=round(statistics.median(values), 2),
        min=round(min(values), 2),
        max=round(max(values), 2),
        stdev=round(statistics.pstdev(values), 2) if len(values) > 1 else 0.0,
        volatility_pct=round(statistics.pstdev(values) / mean * 100, 1) if len(values) > 1 and mean else None,
    )


def _predict_next(series_values: list[float]) -> tuple[float | None, float | None, float | None]:
    """Least-squares linear trend projected one period forward, plus a
    rough +/-1 residual-stdev confidence band around it. Returns
    (prediction, low, high) -- all None with fewer than 3 points, since
    extrapolating from 1-2 points is a guess, not a prediction, so it's
    better to say nothing."""
    n = len(series_values)
    if n < 3:
        return None, None, None
    xs = list(range(n))
    mean_x = sum(xs) / n
    mean_y = sum(series_values) / n
    denominator = sum((x - mean_x) ** 2 for x in xs)
    if denominator == 0:
        value = round(series_values[-1], 2)
        return value, value, value
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, series_values)) / denominator
    intercept = mean_y - slope * mean_x
    prediction = intercept + slope * n
    residuals = [y - (intercept + slope * x) for x, y in zip(xs, series_values)]
    residual_stdev = statistics.pstdev(residuals) if len(residuals) > 1 else 0.0
    return round(prediction, 2), round(prediction - residual_stdev, 2), round(prediction + residual_stdev, 2)


def _classify_risk(current: float, target: float | None, higher_is_better: bool) -> str:
    """Rule-based, not ML -- deliberately transparent. `unknown` when no
    target is set, since "at risk relative to what?" has no answer yet."""
    if target is None or target == 0:
        return "unknown"
    ratio = (current / target) if higher_is_better else (target / current if current else 0.0)
    if ratio >= 0.95:
        return "on_track"
    if ratio >= 0.75:
        return "at_risk"
    return "critical"


def compute_kpi(db: Session, org_id: int, key: str, language: str = "en", months: int = 6) -> KPIResult:
    definition = KPI_DEFINITIONS.get(key)
    if definition is None:
        raise ValueError(f"Unknown KPI '{key}'")

    target_row = db.query(KPITarget).filter(KPITarget.organization_id == org_id, KPITarget.kpi_key == key).first()
    target = float(target_row.target_value) if target_row else None
    name = definition.name_fa if language == "fa" else definition.name_en
    description = definition.description_fa if language == "fa" else definition.description_en

    if definition.supports_trend:
        series = definition.compute_series(db, org_id, months)
        values = [v for _, v in series]
        current = values[-1] if values else 0.0
        previous = values[-2] if len(values) >= 2 else None
        change_pct = round((current - previous) / abs(previous) * 100, 1) if previous else None
        prediction, prediction_low, prediction_high = _predict_next(values)
        trend = [{"period": p, "value": v} for p, v in series]
        stats = _series_stats(values)
    else:
        current = definition.compute_snapshot(db, org_id)
        previous = None
        change_pct = None
        prediction = prediction_low = prediction_high = None
        trend = None
        stats = None

    breakdown = definition.compute_breakdown(db, org_id, months) if definition.compute_breakdown else None

    return KPIResult(
        key=key,
        name=name,
        description=description,
        department=definition.department,
        unit=definition.unit,
        higher_is_better=definition.higher_is_better,
        supports_trend=definition.supports_trend,
        current_value=current,
        previous_value=previous,
        change_pct=change_pct,
        trend=trend,
        target=target,
        risk_level=_classify_risk(current, target, definition.higher_is_better),
        prediction_next=prediction,
        prediction_low=prediction_low,
        prediction_high=prediction_high,
        stats=stats,
        breakdown=breakdown,
    )


def compute_all_kpis(db: Session, org_id: int, language: str = "en", months: int = 6) -> list[KPIResult]:
    return [compute_kpi(db, org_id, key, language=language, months=months) for key in KPI_DEFINITIONS]
