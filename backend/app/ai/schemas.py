"""
API-facing shapes for the ACEWIN Copilot. Kept separate from app/schemas.py
(CRM Core) since this is a distinct layer with its own contract.
"""
from pydantic import BaseModel, Field


class CopilotAskRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000, description="Natural-language request from the user.")
    lang: str = Field(default="en", pattern="^(en|fa)$", description="Requested response language.")


class CopilotToolTrace(BaseModel):
    """One backend tool call the Copilot made while answering -- shown to
    the user for transparency, and to prove no SQL/data was invented."""

    tool_name: str
    arguments: dict
    result: dict


class CopilotAnswer(BaseModel):
    """Every Copilot answer follows this shape, per the ACEWIN spec:
    Summary, Analysis, Recommendation, Confidence Score, Business Impact,
    Next Action. `is_connected` tells the UI whether this came from a real
    model or the not-yet-configured placeholder."""

    summary: str
    analysis: str
    recommendation: str
    confidence_score: float = Field(ge=0, le=1)
    business_impact: str
    next_action: str
    tool_calls: list[CopilotToolTrace] = []
    is_connected: bool


class ToolInfo(BaseModel):
    name: str
    description: str
    parameters: dict
