"""Independent report generation service."""
from __future__ import annotations

from typing import Any, Dict, Optional

from langchain_openai import ChatOpenAI

from ..chat.agents.report_state import ReportState
from ..chat.agents.universal_report_engine import (
    build_universal_report_graph,
    make_initial_report_state,
)
from ..chat.tools.agent_tools import get_default_tool_registry
from .config import ReportConfig
from .session_manager import ReportSessionManager


class ReportService:
    """Standalone report generation service."""

    def __init__(
        self,
        llm: Optional[ChatOpenAI] = None,
        config: Optional[ReportConfig] = None,
        session_manager: Optional[ReportSessionManager] = None,
    ):
        """
        Initialize report service.

        Args:
            llm: ChatOpenAI instance (creates default if None)
            config: ReportConfig instance (creates default if None)
            session_manager: ReportSessionManager instance (creates default if None)
        """
        self.config = config or ReportConfig()
        self.llm = llm or self._create_default_llm()
        self.session_manager = session_manager or ReportSessionManager()

        # Build report engine graph
        self.graph = build_universal_report_graph(
            planner_llm=self.llm,
            analyzer_llm=self.llm,
            extractor_llm=self.llm,
            extractor_prompt_template=(
                "你是需求提取器。请从用户输入提取报告槽位，仅输出JSON。\n"
                "【当前已知】：{current_slots}\n"
                "【用户输入】：{user_input}"
            ),
            planner_skill_prompt="",
            analyzer_skill_prompt="",
            tool_registry=get_default_tool_registry(),
        )

    def _create_default_llm(self) -> ChatOpenAI:
        """Create default LLM instance."""
        return ChatOpenAI(
            model=self.config.llm_model,
            api_key=self.config.llm_api_key,
            base_url=self.config.llm_base_url,
        )

    def generate(
        self,
        session_id: str,
        user_input: str,
        initial_slots: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Start new report generation flow.

        Args:
            session_id: Unique session identifier
            user_input: User's initial request
            initial_slots: Optional initial report slots

        Returns:
            {
                "status": "awaiting_human" | "finished" | "executing",
                "phase": current phase,
                "slots": extracted slots,
                "outline": report outline,
                "content": generated content,
                "response": question or confirmation text,
                "error": error message if any,
            }
        """
        state = self.session_manager.get_or_create(session_id, user_input)

        # Inject initial slots if provided
        if initial_slots:
            state["report_slots"].update(initial_slots)

        # Execute engine (phase is preserved, not reset)
        result_state = self.graph.invoke(state)

        # Save state
        self.session_manager.save(session_id, result_state)

        return self._format_response(result_state)

    def continue_with_feedback(
        self,
        session_id: str,
        feedback: str,
    ) -> Dict[str, Any]:
        """
        Continue report generation with user feedback.

        Args:
            session_id: Session identifier
            feedback: User's response or feedback

        Returns:
            Response dict (same format as generate())

        Raises:
            ValueError: If session not found
        """
        state = self.session_manager.load(session_id)
        if not state:
            raise ValueError(f"Session {session_id} not found")

        # Inject user feedback (phase is preserved)
        state["human_feedback"] = feedback

        # Execute engine
        result_state = self.graph.invoke(state)

        # Save state
        self.session_manager.save(session_id, result_state)

        return self._format_response(result_state)

    def _format_response(self, state: ReportState) -> Dict[str, Any]:
        """Format engine state into response dict."""
        return {
            "status": state.get("status", ""),
            "phase": state.get("phase", ""),
            "slots": state.get("report_slots", {}),
            "outline": state.get("report_outline", []),
            "content": state.get("report_content", ""),
            "response": state.get("final_response", ""),
            "error": state.get("error", ""),
        }

    def get_session_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get formatted session state (for debugging)."""
        state = self.session_manager.load(session_id)
        return self._format_response(state) if state else None

    def delete_session(self, session_id: str) -> None:
        """Delete session."""
        self.session_manager.delete(session_id)
