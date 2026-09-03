import calendar
from datetime import datetime, timezone

from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_org, get_current_user
from app.models import Company, Contact, Deal, Organization, PipelineStage, Task, TaskStatus, User
from app.schemas import DashboardSummary, FunnelStage, RevenuePoint, WonLostPoint
from app.tenancy import scoped

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _month_bounds(dt: datetime) -> tuple[datetime, datetime]:
    start = dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    last_day = calendar.monthrange(start.year, start.month)[1]
    end = start.replace(day=last_day, hour=23, minute=59, second=59)
    return start, end


@router.get("/summary", response_model=DashboardSummary)
def summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    now = datetime.now(timezone.utc)
    month_start, month_end = _month_bounds(now)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = now.replace(hour=23, minute=59, second=59, microsecond=0)

    open_deals = (
        scoped(db, Deal, org)
        .join(PipelineStage, Deal.stage_id == PipelineStage.id)
        .filter(PipelineStage.is_won.is_(False), PipelineStage.is_lost.is_(False))
        .all()
    )
    won_this_month = (
        scoped(db, Deal, org)
        .join(PipelineStage, Deal.stage_id == PipelineStage.id)
        .filter(PipelineStage.is_won.is_(True), Deal.closed_at >= month_start, Deal.closed_at <= month_end)
        .all()
    )

    tasks_due_today = (
        scoped(db, Task, org)
        .filter(Task.status == TaskStatus.pending, Task.due_date >= today_start, Task.due_date <= today_end)
        .count()
    )
    overdue_tasks = (
        scoped(db, Task, org).filter(Task.status == TaskStatus.pending, Task.due_date < today_start).count()
    )

    return DashboardSummary(
        total_contacts=scoped(db, Contact, org).count(),
        total_companies=scoped(db, Company, org).count(),
        open_deals_count=len(open_deals),
        open_deals_value=float(sum(float(d.value) for d in open_deals)),
        won_this_month_count=len(won_this_month),
        won_this_month_value=float(sum(float(d.value) for d in won_this_month)),
        tasks_due_today=tasks_due_today,
        overdue_tasks=overdue_tasks,
    )


@router.get("/pipeline-funnel", response_model=list[FunnelStage])
def pipeline_funnel(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    stages = scoped(db, PipelineStage, org).order_by(PipelineStage.order).all()
    result = []
    for stage in stages:
        deals = scoped(db, Deal, org).filter(Deal.stage_id == stage.id).all()
        result.append(
            FunnelStage(
                stage_id=stage.id,
                stage_name=stage.name,
                color=stage.color,
                count=len(deals),
                value=float(sum(float(d.value) for d in deals)),
            )
        )
    return result


@router.get("/revenue-trend", response_model=list[RevenuePoint])
def revenue_trend(
    months: int = Query(6, ge=1, le=24),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    now = datetime.now(timezone.utc)
    start_month = (now.replace(day=1) - relativedelta(months=months - 1)).replace(hour=0, minute=0, second=0, microsecond=0)

    won_deals = (
        scoped(db, Deal, org)
        .join(PipelineStage, Deal.stage_id == PipelineStage.id)
        .filter(PipelineStage.is_won.is_(True), Deal.closed_at >= start_month)
        .all()
    )

    buckets: dict[str, float] = {}
    cursor = start_month
    for _ in range(months):
        key = cursor.strftime("%Y-%m")
        buckets[key] = 0.0
        cursor = cursor + relativedelta(months=1)

    for deal in won_deals:
        if deal.closed_at:
            key = deal.closed_at.strftime("%Y-%m")
            if key in buckets:
                buckets[key] += float(deal.value)

    return [RevenuePoint(period=k, won_value=v) for k, v in buckets.items()]


@router.get("/deals-won-lost", response_model=list[WonLostPoint])
def deals_won_lost(
    months: int = Query(6, ge=1, le=24),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    now = datetime.now(timezone.utc)
    start_month = (now.replace(day=1) - relativedelta(months=months - 1)).replace(hour=0, minute=0, second=0, microsecond=0)

    closed_deals = (
        scoped(db, Deal, org)
        .join(PipelineStage, Deal.stage_id == PipelineStage.id)
        .filter((PipelineStage.is_won.is_(True)) | (PipelineStage.is_lost.is_(True)), Deal.closed_at >= start_month)
        .all()
    )

    won_buckets: dict[str, int] = {}
    lost_buckets: dict[str, int] = {}
    cursor = start_month
    for _ in range(months):
        key = cursor.strftime("%Y-%m")
        won_buckets[key] = 0
        lost_buckets[key] = 0
        cursor = cursor + relativedelta(months=1)

    for deal in closed_deals:
        if not deal.closed_at:
            continue
        key = deal.closed_at.strftime("%Y-%m")
        if key not in won_buckets:
            continue
        if deal.stage.is_won:
            won_buckets[key] += 1
        elif deal.stage.is_lost:
            lost_buckets[key] += 1

    return [WonLostPoint(period=k, won_count=won_buckets[k], lost_count=lost_buckets[k]) for k in won_buckets]
