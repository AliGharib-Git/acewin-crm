"""
Enterprise OKR Engine.

    Objectives -> Key Results -> Progress -> Department Score -> Company Score

Every score here is computed live from real data -- a Key Result's
progress from its stored value (or, if `linked_kpi_key` is set, from
the live KPI Engine -- see app/kpi/engine.py), an Objective's score
from its Key Results, and roll-ups from there. Nothing is stored or
guessed.

Risk classification and priority ranking are both rule-based and time-
aware: an Objective's risk isn't "is the number big enough" (that's
what KPI risk does) but "are we on pace, given how much of the period
has elapsed" -- the OKR equivalent of a burn-down chart. AI is used
only for the *why/what-to-do* narrative (app/okr/explain.py), never for
the score or the risk level itself, so those numbers stay auditable
and reproducible.
"""
import re
from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.kpi.engine import KPI_DEFINITIONS, compute_kpi
from app.models import KeyResult, KeyResultType, Objective, ObjectiveStatus

_QUARTER_RE = re.compile(r"^(?P<year>\d{4})-Q(?P<quarter>[1-4])$")


def parse_period(period_key: str) -> tuple[date, date]:
    """"2026-Q3" -> (2026-07-01, 2026-09-30). Raises ValueError for
    anything else -- OKRs are quarter-boxed by convention in this
    engine, so a malformed period is a user input error, not something
    to silently guess at."""
    from calendar import monthrange

    match = _QUARTER_RE.match(period_key.strip())
    if not match:
        raise ValueError(f"Invalid period '{period_key}'. Expected format: YYYY-Q1 .. YYYY-Q4.")
    year = int(match.group("year"))
    quarter = int(match.group("quarter"))
    start_month = (quarter - 1) * 3 + 1
    end_month = start_month + 2
    start = date(year, start_month, 1)
    end = date(year, end_month, monthrange(year, end_month)[1])
    return start, end


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def key_result_current_value(db: Session, kr: KeyResult) -> float | None:
    """The number to *display* for this KR. For a KPI-linked metric,
    this is always read live from the KPI Engine -- kr.current_value is
    never trusted, so it can never drift out of sync with reality."""
    if kr.measurement_type == KeyResultType.milestone:
        return 1.0 if kr.is_done else 0.0
    if kr.linked_kpi_key:
        try:
            # kr.objective.organization_id, not a passed-in org -- a
            # KPI-linked Key Result must always read the KPI Engine
            # scoped to the SAME tenant the Key Result itself belongs
            # to, so this can't be tricked into reading another
            # organization's numbers by whichever org happens to be
            # making the request.
            return compute_kpi(db, kr.objective.organization_id, kr.linked_kpi_key).current_value
        except ValueError:
            return None  # linked KPI key no longer exists -- treat as unmeasurable, not zero
    return float(kr.current_value) if kr.current_value is not None else None


def key_result_score(db: Session, kr: KeyResult) -> float:
    """0.0-1.0 progress score for one Key Result."""
    if kr.measurement_type == KeyResultType.milestone:
        return 1.0 if kr.is_done else 0.0

    current = key_result_current_value(db, kr)
    baseline = float(kr.baseline_value) if kr.baseline_value is not None else 0.0
    target = float(kr.target_value) if kr.target_value is not None else None
    if current is None or target is None or target == baseline:
        return 0.0
    return _clamp((current - baseline) / (target - baseline))


@dataclass
class ObjectiveScore:
    objective: Objective
    score_pct: float  # 0-100, weighted average of its Key Results
    expected_pct: float  # 0-100, how far along we SHOULD be given elapsed time
    gap_pct: float  # expected - actual; positive means behind schedule
    risk_level: str  # "on_track" | "at_risk" | "critical" | "draft" | "archived"
    days_remaining: int | None


def expected_progress_fraction(objective: Objective, as_of: date | None = None) -> float:
    """What fraction of the objective's period has elapsed -- the
    "expected" progress if work were paced perfectly evenly across the
    period. Not a claim about how OKRs *should* be paced (many are
    back-loaded), just the honest, simple baseline used for risk
    classification below."""
    as_of = as_of or datetime.now(timezone.utc).date()
    total_days = (objective.end_date - objective.start_date).days
    if total_days <= 0:
        return 1.0
    elapsed_days = (as_of - objective.start_date).days
    return _clamp(elapsed_days / total_days)


def compute_objective_score(db: Session, objective: Objective, as_of: date | None = None) -> ObjectiveScore:
    key_results = objective.key_results
    if key_results:
        total_weight = sum(float(kr.weight) for kr in key_results) or len(key_results)
        weighted = sum(key_result_score(db, kr) * float(kr.weight) for kr in key_results)
        score_fraction = weighted / total_weight
    else:
        score_fraction = 0.0  # an objective with no Key Results yet has no measurable progress

    as_of = as_of or datetime.now(timezone.utc).date()
    days_remaining = (objective.end_date - as_of).days
    expected_fraction = expected_progress_fraction(objective, as_of)
    gap_fraction = expected_fraction - score_fraction

    if objective.status == ObjectiveStatus.draft:
        risk = "draft"
    elif objective.status == ObjectiveStatus.archived:
        risk = "archived"
    elif objective.status == ObjectiveStatus.completed:
        risk = "on_track" if score_fraction >= 0.7 else "at_risk"
    elif gap_fraction <= 0.05:
        risk = "on_track"
    elif gap_fraction <= 0.20:
        risk = "at_risk"
    else:
        risk = "critical"

    return ObjectiveScore(
        objective=objective,
        score_pct=round(score_fraction * 100, 1),
        expected_pct=round(expected_fraction * 100, 1),
        gap_pct=round(gap_fraction * 100, 1),
        risk_level=risk,
        days_remaining=days_remaining,
    )


def compute_department_score(objective_scores: list[ObjectiveScore]) -> float | None:
    """Average score across an department's *active or completed*
    objectives (draft/archived excluded -- they're not live commitments).
    None when there's nothing to score yet."""
    relevant = [o for o in objective_scores if o.objective.status in (ObjectiveStatus.active, ObjectiveStatus.completed)]
    if not relevant:
        return None
    return round(sum(o.score_pct for o in relevant) / len(relevant), 1)


def compute_company_score(department_scores: dict[str, float | None]) -> float | None:
    """Average of department scores (each department weighted equally,
    regardless of how many objectives it has) -- so a department with
    one objective doesn't get drowned out by one with ten."""
    values = [v for v in department_scores.values() if v is not None]
    if not values:
        return None
    return round(sum(values) / len(values), 1)


_RISK_SEVERITY = {"critical": 3, "at_risk": 2, "on_track": 1, "draft": 0, "archived": 0}


def rank_by_priority(objective_scores: list[ObjectiveScore]) -> list[ObjectiveScore]:
    """Deterministic priority order: worst risk first, then largest
    schedule gap first. No AI involved -- this is a sort, not a
    judgment call, so it stays reproducible."""
    return sorted(
        objective_scores,
        key=lambda o: (_RISK_SEVERITY.get(o.risk_level, 0), o.gap_pct),
        reverse=True,
    )


def known_kpi_keys() -> list[str]:
    """KPI keys available for linking a Key Result to the KPI Engine --
    exposed so the frontend can offer a dropdown instead of a free-text
    field prone to typos."""
    return list(KPI_DEFINITIONS.keys())
