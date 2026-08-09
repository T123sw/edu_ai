from __future__ import annotations

from typing import TypedDict


class AgentState(TypedDict):
    # ── Per-turn (reset via initial_input each call) ──────────────────────────
    messages: list          # full message list rebuilt from snapshot
    tool_exchange: list     # tool call/result msgs for persistence
    retrieval_sources: list # RAG/Web citations accumulated during this turn
    fallback_reason: str    # non-empty triggers fallback in run_stream
    needs_planning: bool    # set by run_stream() via should_plan(), cleared by planner_node
    task_contract: dict     # TeachingTaskContract.to_dict(), current-turn execution authority
    logical_task_id: str   # stable id for one logical task across retries/reconnects
    verification_report: dict  # rule-first VerificationReport after verify_task

    # ── Cross-turn checkpointed fields ────────────────────────────────────────
    active_draft_outline: dict  # last outline shown to user (L2 working memory)
    pending_tasks: list         # submitted background generation tasks
    agent_memory: dict          # working facts + task ledger + bounded summary

    # ── Plan fields (cross-turn, persisted via checkpoint) ───────────────────
    current_plan: dict      # Plan.to_dict(), None if no plan yet
    plan_step_index: int    # current step being executed (guided/strict mode)
    plan_mode: str          # "display_only" | "guided" | "strict"

    # ── Reflect fields (node-to-node within turn, persisted across turns for replan) ──
    reflect_verdict: str    # "pass"|"pass_with_warning"|"retry"|"replan"|"abort"|""
    reflect_hint: str       # failure reason injected into executor context
    reflect_filtered: dict  # filtered clean data (e.g. approved images)
    retry_counts: dict      # {"step_2:web_search": 1} — prevents reflect dead loops
    last_tool_results: list  # raw results from last tools_node, consumed by reflect_node

    # ── Phase 6-A: accumulated visual assets across image_search calls in this run ──
    # Each entry is the normalized image dict from image_search handler
    # ({url, source_page, title, width, height, thumbnail, license, proxy_url, provenance}).
    # Written by reflect_node when image_search verdict passes;
    # read by tools_node before dispatching generate_report so the handler can
    # inject these images into the final report markdown.
    accumulated_images: list
