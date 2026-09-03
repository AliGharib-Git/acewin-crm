"""
On-demand natural-language analysis for one Objective: why it's behind
(or ahead), and one concrete suggested action.

Same pattern as app/kpi/explain.py: reuses the provider-agnostic AI
client (app/ai/client.py), the prompt is built ONLY from real,
already-computed numbers (app/okr/engine.py's ObjectiveScore + each Key
Result's live value), and it falls back to a deterministic sentence
built from those same numbers if no provider is configured or the call
fails. The risk level and score themselves are never touched by this
module -- only the narrative around them is.
"""
from sqlalchemy.orm import Session

from app.ai.client import AIClientError, AIMessage, MessageRole, NullAIClient, get_ai_client
from app.models import KeyResult, KeyResultType, Objective
from app.okr.engine import ObjectiveScore, key_result_current_value, key_result_score


def _kr_summary_line(db: Session, kr: KeyResult, language: str) -> str:
    score = key_result_score(db, kr) * 100
    if kr.measurement_type == KeyResultType.milestone:
        status = ("انجام شد" if kr.is_done else "انجام‌نشده") if language == "fa" else ("done" if kr.is_done else "not done")
        return f"- {kr.title}: {status}"
    current = key_result_current_value(db, kr)
    return f"- {kr.title}: {current} / {kr.target_value} ({score:.0f}%)"


def _rule_based_explanation(objective: Objective, score: ObjectiveScore, language: str) -> str:
    behind = score.gap_pct > 5

    if language == "fa":
        parts = [f"هدف «{objective.title}» در حال حاضر {score.score_pct}% پیشرفت داشته، در حالی که انتظار می‌رفت {score.expected_pct}% باشه."]
        if score.risk_level == "critical":
            parts.append(f"این هدف با {score.gap_pct} واحد درصد عقب‌تر از برنامه است و در وضعیت بحرانی قرار داره.")
        elif score.risk_level == "at_risk":
            parts.append(f"این هدف کمی عقب‌تر از برنامه است ({score.gap_pct} واحد درصد) و باید زیر نظر باشه.")
        elif score.risk_level == "on_track":
            parts.append("این هدف مطابق یا جلوتر از برنامه پیش می‌ره.")
        if score.days_remaining is not None and score.days_remaining >= 0:
            parts.append(f"{score.days_remaining} روز تا پایان دوره باقی مانده.")
        if behind:
            parts.append("پیشنهاد می‌شود روی Key Result هایی که کمترین پیشرفت را دارند تمرکز بیشتری صورت گیرد.")
        return " ".join(parts)

    parts = [f"Objective \"{objective.title}\" is at {score.score_pct}% progress, versus an expected {score.expected_pct}% at this point in the period."]
    if score.risk_level == "critical":
        parts.append(f"It's {score.gap_pct} points behind schedule and in a critical state.")
    elif score.risk_level == "at_risk":
        parts.append(f"It's somewhat behind schedule ({score.gap_pct} points) and worth watching.")
    elif score.risk_level == "on_track":
        parts.append("It's on pace or ahead of schedule.")
    if score.days_remaining is not None and score.days_remaining >= 0:
        parts.append(f"{score.days_remaining} days remain in the period.")
    if behind:
        parts.append("Consider focusing effort on whichever Key Results are lagging furthest behind.")
    return " ".join(parts)


def explain_objective(db: Session, objective: Objective, score: ObjectiveScore, language: str = "en") -> tuple[str, str]:
    """Returns (explanation_text, generated_by). Never raises."""
    client = get_ai_client()
    if isinstance(client, NullAIClient):
        return _rule_based_explanation(objective, score, language), "rule-based"

    lang_instruction = "Respond in Persian (Farsi)." if language == "fa" else "Respond in English."
    kr_lines = "\n".join(_kr_summary_line(db, kr, language) for kr in objective.key_results) or "(no Key Results yet)"
    prompt = (
        "You are an OKR coach. In 3-4 sentences, explain why this Objective is at its current progress "
        "level relative to schedule, which Key Result(s) are the biggest drag if any, and one concrete "
        "suggested action. Use ONLY the numbers given below -- never invent data. "
        f"{lang_instruction}\n\n"
        f"Objective: {objective.title} (department: {objective.department}, period: {objective.period_key})\n"
        f"Overall progress: {score.score_pct}%\n"
        f"Expected progress at this point in the period: {score.expected_pct}%\n"
        f"Gap (positive = behind schedule): {score.gap_pct} points\n"
        f"Days remaining: {score.days_remaining}\n"
        f"Risk level: {score.risk_level}\n"
        f"Key Results:\n{kr_lines}\n"
    )
    try:
        response = client.complete([AIMessage(role=MessageRole.user, content=prompt)])
        text = response.content.strip()
        if text:
            return text, "ai"
    except AIClientError:
        pass
    return _rule_based_explanation(objective, score, language), "rule-based"
