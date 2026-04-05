from __future__ import annotations

import operator
from typing import Any, Dict, List, TypedDict
from typing_extensions import Annotated

from langchain_core.messages import BaseMessage


class PlanStep(TypedDict):
    step_id: str
    description: str
    tool_name: str
    tool_args: Dict[str, Any]
    status: str
    observation: str


class ReportState(TypedDict):
    # IO
    messages: Annotated[List[BaseMessage], operator.add]
    user_input: str
    final_response: str

    # Legacy fields (kept for service.py persistence compatibility)
    plan: List[PlanStep]
    current_step_index: int
    gathered_context: Dict[str, Any]
    past_steps: Annotated[List[Dict[str, Any]], operator.add]

    # Artifacts
    report_slots: Dict[str, Any]
    report_outline: List[Dict[str, Any]]
    report_content: str

    # Control
    status: str
    human_feedback: str
    error: str
    replan_count: int
    max_replans: int

    # === Explicit phase state (v2 state machine) ===
    phase: str                  # extracting|evaluating|asking|confirming|outlining|generating|finished
    soft_confirmed: bool        # Whether soft-confirm (length/depth/style) is done
    outline_confirmed: bool     # Whether user has confirmed the outline
    ask_count: Dict[str, int]   # Per-slot ask count, e.g. {"core_topic": 1, "focus_area": 0}
    ask_limit: int              # Max asks per slot (default 2, from SKILL schema)
    _missing_slot: str          # Transient: slot name the asker should ask about

    # === Focus sufficiency assessment (v2 enhancement) ===
    focus_sufficient: bool      # Whether focus_area is sufficiently specific
    focus_assessment_reason: str  # Reason for sufficiency judgment
    focus_suggested_question: str  # Associative follow-up question if not sufficient
    generation_ready: bool      # Whether runtime has already judged the preparation as ready
