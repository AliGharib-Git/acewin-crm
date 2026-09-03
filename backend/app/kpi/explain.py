"""
On-demand natural-language explanation for one KPI.

Reuses the exact same provider-agnostic AI layer the Copilot uses
(app/ai/client.py) -- whatever AI_PROVIDER is configured in
backend/.env answers this too, with zero KPI-specific provider code.
The prompt is built ONLY from the KPI's own already-computed numbers
(app/kpi/engine.py); the model is instructed not to invent data, and
its answer is never used to alter those numbers, only to narrate them.

If no provider is configured (AI_PROVIDER=none) or the call fails for
any reason, this falls back to a deterministic, rule-based sentence
built from the same numbers -- so "explain this KPI" never just
errors out for a user who hasn't set up an AI key yet.
"""
from app.ai.client import AIClientError, AIMessage, MessageRole, NullAIClient, get_ai_client
from app.kpi.engine import KPIResult


def _format_value(value: float, unit: str) -> str:
    if unit == "currency":
        return f"${value:,.0f}"
    if unit == "percent":
        return f"{value:.1f}%"
    if unit in ("days", "hours"):
        return f"{value:.1f} {unit}"
    return f"{value:,.2f}"


def _rule_based_explanation(result: KPIResult, language: str) -> str:
    improving = result.change_pct is not None and ((result.change_pct > 0) == result.higher_is_better)
    current_fmt = _format_value(result.current_value, result.unit)

    if language == "fa":
        trend_word = "در حال بهبود" if improving else "در حال افت" if result.change_pct else "بدون تغییر محسوس"
        parts = [f"{result.name} در حال حاضر {current_fmt} است ({trend_word})."]
        if result.stats and result.stats.volatility_pct is not None:
            stability = "پایدار" if result.stats.volatility_pct < 15 else "نسبتاً نوسانی" if result.stats.volatility_pct < 40 else "بسیار نوسانی"
            parts.append(f"در بازهٔ اخیر، این شاخص {stability} بوده (میانگین {_format_value(result.stats.mean, result.unit)}).")
        if result.target is not None:
            parts.append(f"هدف تعیین‌شده {_format_value(result.target, result.unit)} است.")
        if result.prediction_next is not None:
            parts.append(f"با روند فعلی، پیش‌بینی دورهٔ بعد {_format_value(result.prediction_next, result.unit)} است.")
        if result.breakdown:
            top = result.breakdown[0]
            parts.append(f"بیشترین سهم را «{top['label']}» دارد.")
        if result.risk_level == "critical":
            parts.append("این شاخص در وضعیت بحرانی است و نیاز به بررسی فوری دارد.")
        elif result.risk_level == "at_risk":
            parts.append("این شاخص در معرض ریسک عقب‌ماندن از هدف است.")
        return " ".join(parts)

    trend_word = "improving" if improving else "declining" if result.change_pct else "roughly flat"
    parts = [f"{result.name} is currently {current_fmt} ({trend_word})."]
    if result.stats and result.stats.volatility_pct is not None:
        stability = "stable" if result.stats.volatility_pct < 15 else "somewhat volatile" if result.stats.volatility_pct < 40 else "highly volatile"
        parts.append(f"Over the recent window it has been {stability} (averaging {_format_value(result.stats.mean, result.unit)}).")
    if result.target is not None:
        parts.append(f"The target is {_format_value(result.target, result.unit)}.")
    if result.prediction_next is not None:
        parts.append(f"At the current trend, next period is projected at {_format_value(result.prediction_next, result.unit)}.")
    if result.breakdown:
        top = result.breakdown[0]
        parts.append(f"The top contributor is {top['label']}.")
    if result.risk_level == "critical":
        parts.append("This metric is in a critical state and needs immediate attention.")
    elif result.risk_level == "at_risk":
        parts.append("This metric is at risk of missing its target.")
    return " ".join(parts)


def explain_kpi(result: KPIResult, language: str = "en") -> tuple[str, str]:
    """Returns (explanation_text, generated_by), where generated_by is
    "ai" or "rule-based". Never raises."""
    client = get_ai_client()
    if isinstance(client, NullAIClient):
        return _rule_based_explanation(result, language), "rule-based"

    lang_instruction = "Respond in Persian (Farsi)." if language == "fa" else "Respond in English."
    trend_desc = ", ".join(f"{p['period']}={p['value']}" for p in (result.trend or [])) or "not tracked for this KPI"
    stats_desc = (
        f"mean={result.stats.mean}, median={result.stats.median}, min={result.stats.min}, "
        f"max={result.stats.max}, stdev={result.stats.stdev}, volatility={result.stats.volatility_pct}%"
        if result.stats
        else "not available"
    )
    breakdown_desc = (
        ", ".join(f"{b['label']}={b['value']}" for b in result.breakdown) if result.breakdown else "not available"
    )
    prompt = (
        "You are a CRM business analyst. In 4-5 sentences, explain why this KPI is at its current "
        "value, how stable/volatile it has been, what it's likely to do next, and one concrete "
        "suggested action. Use ONLY the numbers given below -- never invent data or cite figures not "
        f"listed here. {lang_instruction}\n\n"
        f"KPI: {result.name} (unit: {result.unit})\n"
        f"Current value: {result.current_value}\n"
        f"Previous period: {result.previous_value}\n"
        f"Change vs previous period: {result.change_pct}%\n"
        f"Monthly trend: {trend_desc}\n"
        f"Window statistics: {stats_desc}\n"
        f"Top contributors: {breakdown_desc}\n"
        f"Target: {result.target}\n"
        f"Linear-trend projection for next period: {result.prediction_next} "
        f"(range: {result.prediction_low} to {result.prediction_high})\n"
        f"Risk level: {result.risk_level}\n"
    )
    try:
        response = client.complete([AIMessage(role=MessageRole.user, content=prompt)])
        text = response.content.strip()
        if text:
            return text, "ai"
    except AIClientError:
        pass
    return _rule_based_explanation(result, language), "rule-based"
