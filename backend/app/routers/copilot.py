"""
ACEWIN Copilot router (Layer 2).

Runs a real tool-calling loop against the configured AIClient. The model
never sees raw SQL and never invents CRM data -- it can only ask for
information, or make a change, through the tools registered in
app/ai/tools.py (CRM Core reads/writes and Analytics Engine modules), and
every tool call is logged and returned to the user in `tool_calls` for
transparency.

If AI_PROVIDER=none (default, no key configured), the pipeline still runs
end-to-end through NullAIClient, which explains that no model is connected
yet -- so nothing here needs to change once a real key is added, only
backend/.env.
"""
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.ai.client import AIClientError, AIMessage, MessageRole, get_ai_client
from app.ai.config import get_ai_settings
from app.ai.schemas import CopilotAnswer, CopilotAskRequest, CopilotToolTrace, ToolInfo
from app.ai.tools import ToolContext, ToolError, call_tool, list_tool_definitions
from app.audit import record_action
from app.database import get_db
from app.deps import enforce_feature, enforce_within_limit, get_current_org, get_current_user
from app.models import AgentActionStatus, Organization, User

router = APIRouter(prefix="/api/copilot", tags=["copilot"])

MAX_TOOL_ROUNDS = 6

SYSTEM_PROMPT = """You are the ACEWIN Copilot, an experienced CRM and business
advisor embedded inside the ACEWIN platform (CRM Core + Analytics Engine).

The current date and time is {now}. Resolve any relative date/time the user
gives you ("tomorrow", "next Monday", "in an hour") against this, and always
pass due_date/date arguments to tools as absolute ISO 8601 datetimes.

Rules:
- You NEVER write or execute SQL.
- You NEVER invent CRM data, numbers, customer names, or predictions. Every
  factual claim must come from a tool call result.
- If you need information, call a tool. You may call multiple tools across
  several turns before answering.
- Some tools change data (create_task, update_task, create_deal,
  update_deal_stage). Only call these when the user actually asked you to
  create, change, schedule, add, or move something -- never as a side effect
  of answering a question. If a name is ambiguous or not found, use
  find_contact first, or ask the user to clarify instead of guessing an id.
- Once you have enough information, reply in plain text with EXACTLY these
  six labeled sections, one per line, in this order:
  Summary: ...
  Analysis: ...
  Recommendation: ...
  Confidence Score: <a number between 0 and 1>
  Business Impact: ...
  Next Action: ...
- Confidence Score reflects how well the tool data supports your answer, not
  how fluent you feel. Be honest and specific rather than generic."""


def _localized_prompt(lang: str) -> str:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC (%A)")
    prompt = SYSTEM_PROMPT.format(now=now)
    if lang == "fa":
        return prompt + "\n- پاسخ را کامل و روان به زبان فارسی بنویس. نام دقیق شش برچسب بخش‌ها (Summary:, Analysis:, Recommendation:, Confidence Score:, Business Impact:, Next Action:) را انگلیسی نگه دار تا رابط کاربری بتواند پاسخ را پردازش کند."
    return prompt


def _fallback(lang: str, kind: str, query: str = "", error: str = "") -> dict:
    fa = lang == "fa"
    messages = {
        "unconfigured": ("دستیار هوشمند پیکربندی نشده است.", error, "در backend/.env مقدار AI_PROVIDER=avalai و AI_API_KEY را تنظیم و بک‌اند را دوباره اجرا کنید.", "تا اتصال ارائه‌دهندهٔ هوش مصنوعی، دستیار نمی‌تواند پاسخ تولید کند.", "ارائه‌دهندهٔ هوش مصنوعی را تنظیم کنید و دوباره درخواست بفرستید.") if fa else ("Copilot is not configured.", error, "Set AI_PROVIDER=avalai and AI_API_KEY in backend/.env, then restart the backend.", "The Copilot cannot answer until a provider is connected.", "Configure an AI provider, then resend this request."),
        "disabled": ("دستیار هوشمند هنوز به ارائه‌دهندهٔ هوش مصنوعی وصل نیست.", f"سؤال شما دریافت شد: «{query}»، اما هیچ مدلی آن را پردازش نکرده است.", "برای پاسخ‌های واقعی، یک ارائه‌دهنده را در backend/.env متصل کنید.", "این پاسخ هنوز اثر تجاری قابل‌اندازه‌گیری ندارد.", "راهنمای backend/.env.example را بررسی کنید.") if fa else ("Copilot is not connected to an AI provider.", f"Your question was received: “{query}”, but no model has processed it.", "Connect a provider in backend/.env to enable real answers.", "Not yet measurable — Copilot is in architecture-only mode.", "See backend/.env.example for AI_PROVIDER / AI_API_KEY / AI_MODEL."),
        "limit": ("داده‌ها جمع‌آوری شد اما استدلال دستیار در سقف تعداد فراخوانی ابزار کامل نشد.", "پاسخ نهایی در زمان تعیین‌شده تولید نشد.", "سؤال را محدودتر و مشخص‌تر بپرسید.", "نامشخص است؛ پاسخ کامل نشد.", "سؤال را با جزئیات بیشتر دوباره بپرسید.") if fa else ("I gathered data but couldn't finish reasoning within the tool-call limit.", "The final answer was not completed in the allowed tool-call rounds.", "Try a narrower question, or ask again.", "Unclear — answer was not completed.", "Re-ask with a more specific question."),
        "failure": ("درخواست دستیار هوشمند ناموفق بود.", error, "کلید API، مدل و دسترسی شبکهٔ ارائه‌دهنده را بررسی کنید.", "برای این درخواست پاسخی تولید نشد.", "پس از رفع مشکل ارائه‌دهنده، دوباره تلاش کنید.") if fa else ("Copilot request failed.", error, "Check AI_API_KEY, AI_MODEL and network access to the configured provider.", "No answer produced for this request.", "Retry once the provider issue is resolved."),
    }[kind]
    return dict(summary=messages[0], analysis=messages[1], recommendation=messages[2], confidence_score=0.2 if kind == "limit" else 0.0, business_impact=messages[3], next_action=messages[4])


def _parse_sections(text: str) -> dict:
    labels = ["Summary", "Analysis", "Recommendation", "Confidence Score", "Business Impact", "Next Action"]
    values = {label: "" for label in labels}
    current = None
    for line in text.splitlines():
        matched = False
        for label in labels:
            if line.strip().lower().startswith(label.lower() + ":"):
                current = label
                values[label] = line.split(":", 1)[1].strip()
                matched = True
                break
        if not matched and current:
            values[current] = (values[current] + " " + line.strip()).strip()
    return values


@router.get("/tools", response_model=list[ToolInfo])
def list_tools(current_user: User = Depends(get_current_user)):
    """What the Copilot can actually do right now. Every tool here queries
    real CRM/analytics data -- there is no other path."""
    return [
        ToolInfo(name=t.name, description=t.description, parameters=t.parameters)
        for t in list_tool_definitions()
    ]


@router.post("/ask", response_model=CopilotAnswer)
def ask(
    payload: CopilotAskRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    org: Organization = Depends(get_current_org),
):
    settings = get_ai_settings()

    # Plan gate + usage limit BEFORE spending a real AI call -- checking
    # after the fact would mean the org already paid the token cost for
    # a request they weren't entitled to make.
    enforce_feature(db, org, "ai.copilot")
    enforce_within_limit(db, org, "ai_requests_per_month")

    ctx = ToolContext(db=db, current_user=current_user, org=org)

    try:
        client = get_ai_client()
    except AIClientError as exc:
        return CopilotAnswer(**_fallback(payload.lang, "unconfigured", error=str(exc)), is_connected=False)

    tool_defs = list_tool_definitions()
    messages = [
        AIMessage(role=MessageRole.system, content=_localized_prompt(payload.lang)),
        AIMessage(role=MessageRole.user, content=payload.query),
    ]

    trace: list[CopilotToolTrace] = []

    if not settings.is_configured:
        return CopilotAnswer(**_fallback(payload.lang, "disabled", query=payload.query), is_connected=False)

    # One audit/usage row per /ask call from here on, independent of
    # whether the model happens to invoke a CRM tool -- a pure Q&A turn
    # still consumes a real AI request and must still count against the
    # monthly limit enforced above (which reads FROM these very rows),
    # or a chatty-but-tool-free conversation would look free forever.
    # Logged only once we know a real provider call is about to happen,
    # so an unconfigured Copilot never burns an org's quota.
    record_action(
        db, current_user, "copilot:ask", source="copilot", status=AgentActionStatus.success,
        arguments={"query": payload.query, "lang": payload.lang}, organization_id=org.id,
    )

    try:
        for _ in range(MAX_TOOL_ROUNDS):
            response = client.complete(messages=messages, tools=tool_defs)

            if not response.tool_calls:
                sections = _parse_sections(response.content)
                return CopilotAnswer(
                    summary=sections["Summary"] or response.content,
                    analysis=sections["Analysis"],
                    recommendation=sections["Recommendation"],
                    confidence_score=_safe_float(sections["Confidence Score"]),
                    business_impact=sections["Business Impact"],
                    next_action=sections["Next Action"],
                    tool_calls=trace,
                    is_connected=True,
                )

            messages.append(
                AIMessage(role=MessageRole.assistant, content=response.content or "", tool_calls=response.tool_calls)
            )
            for call in response.tool_calls:
                try:
                    result = call_tool(call.tool_name, call.arguments, ctx)
                except ToolError as exc:
                    result = {"error": str(exc)}
                trace.append(CopilotToolTrace(tool_name=call.tool_name, arguments=call.arguments, result=result))
                messages.append(
                    AIMessage(
                        role=MessageRole.tool,
                        name=call.tool_name,
                        content=json.dumps(result, default=str),
                        tool_call_id=call.call_id,
                    )
                )

        result = _fallback(payload.lang, "limit")
        result["analysis"] = f"{len(trace)} فراخوانی ابزار انجام شد اما پاسخ نهایی تولید نشد." if payload.lang == "fa" else f"Made {len(trace)} tool call(s) but did not reach a final answer in {MAX_TOOL_ROUNDS} rounds."
        return CopilotAnswer(**result, tool_calls=trace, is_connected=True)
    except AIClientError as exc:
        return CopilotAnswer(**_fallback(payload.lang, "failure", error=str(exc)), tool_calls=trace, is_connected=True)


def _safe_float(value: str) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return 0.5
    return max(0.0, min(1.0, f))
