"""Report session state management."""
from __future__ import annotations

from typing import Any, Dict, Optional

from ..chat.agents.report_state import ReportState
from ..chat.agents.universal_report_engine import make_initial_report_state


class ReportSessionManager:
    """Manages report generation session states."""

    def __init__(self, storage_type: str = "memory"):
        """
        Initialize session manager.

        Args:
            storage_type: "memory" for in-memory storage (default)
        """
        self.storage_type = storage_type
        self.sessions: Dict[str, ReportState] = {}

    def get_or_create(self, session_id: str, user_input: str) -> ReportState:
        """
        Get existing session or create new one.

        Args:
            session_id: Unique session identifier
            user_input: Initial user input for new sessions

        Returns:
            ReportState for the session
        """
        if session_id not in self.sessions:
            self.sessions[session_id] = make_initial_report_state(user_input=user_input)
        return self.sessions[session_id]

    def save(self, session_id: str, state: ReportState) -> None:
        """
        Save session state.

        Args:
            session_id: Session identifier
            state: ReportState to save
        """
        self.sessions[session_id] = state

    def load(self, session_id: str) -> Optional[ReportState]:
        """
        Load session state.

        Args:
            session_id: Session identifier

        Returns:
            ReportState if exists, None otherwise
        """
        return self.sessions.get(session_id)

    def delete(self, session_id: str) -> None:
        """
        Delete session.

        Args:
            session_id: Session identifier
        """
        if session_id in self.sessions:
            del self.sessions[session_id]

    def exists(self, session_id: str) -> bool:
        """Check if session exists."""
        return session_id in self.sessions
