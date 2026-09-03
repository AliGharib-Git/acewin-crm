"""Reusable defaults shared between real signups (auth.py:register) and
the seed/demo scripts, so the two don't quietly drift apart -- a
default someone tunes for the demo data should also be what a real
new tenant gets."""
from app.models import PipelineStage

# Every organization needs at least one Won and one Lost stage for the
# Deal-won gamification/reporting logic to have somewhere to land --
# see app/routers/deals.py's PipelineStage lookups. Kept in sync with
# backend/seed.py's stages_data.
DEFAULT_PIPELINE_STAGES = [
    ("New Lead", 0, "#5B6B84", False, False),
    ("Contacted", 1, "#2E5590", False, False),
    ("Proposal Sent", 2, "#2F6FEB", False, False),
    ("Negotiation", 3, "#1E4FBE", False, False),
    ("Won", 4, "#1B3A63", True, False),
    ("Lost", 5, "#B23A3A", False, True),
]


def create_default_pipeline_stages(db, org) -> None:
    for name, order, color, is_won, is_lost in DEFAULT_PIPELINE_STAGES:
        db.add(PipelineStage(organization_id=org.id, name=name, order=order, color=color, is_won=is_won, is_lost=is_lost))
