"""Session lifecycle management.

Handles creating, resuming, listing, and deleting sessions.

Contract:
- Inputs: Profile names, session IDs
- Outputs: Session objects, session info lists
- Side Effects: Persists sessions to JSON storage via json_store
"""

import logging
import uuid
from datetime import UTC
from datetime import datetime
from typing import Any

from ..models import Session
from ..models import SessionInfo
from ..storage.json_store import delete_stored
from ..storage.json_store import exists
from ..storage.json_store import list_stored
from ..storage.json_store import load_json
from ..storage.json_store import save_json

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages session lifecycle operations.

    Provides methods for creating, resuming, listing, and deleting sessions.
    All sessions are persisted to JSON storage automatically.

    Example:
        >>> manager = SessionManager()
        >>> session = manager.create_session(profile="default", context={})
        >>> assert session.id is not None
        >>> assert session.profile == "default"
    """

    def __init__(self: "SessionManager") -> None:
        """Initialize session manager.

        No initialization needed - all operations are stateless
        and use the storage layer directly.
        """

    def create_session(
        self: "SessionManager",
        profile: str,
        context: dict[str, Any] | None = None,
    ) -> Session:
        """Create a new session.

        Args:
            profile: Profile name for this session
            context: Optional session-specific context data

        Returns:
            New Session object with unique ID

        Example:
            >>> manager = SessionManager()
            >>> session = manager.create_session("default", {"key": "value"})
            >>> assert session.message_count == 0
        """
        session_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        session = Session(
            id=session_id,
            profile=profile,
            context=context or {},
            created_at=now,
            updated_at=now,
            message_count=0,
        )

        # Persist session immediately
        self.save_session(session)

        logger.info(f"Created new session: {session_id} (profile={profile})")
        return session

    def resume_session(self: "SessionManager", session_id: str) -> Session:
        """Resume an existing session.

        Args:
            session_id: Session ID to resume

        Returns:
            Session object loaded from storage

        Raises:
            FileNotFoundError: If session doesn't exist
            ValueError: If session data is invalid

        Example:
            >>> manager = SessionManager()
            >>> session = manager.create_session("default")
            >>> resumed = manager.resume_session(session.id)
            >>> assert resumed.id == session.id
        """
        if not exists(session_id, category="sessions"):
            raise FileNotFoundError(f"Session '{session_id}' not found")

        data = load_json(session_id, category="sessions")

        # Parse datetime strings back to datetime objects
        created_at = datetime.fromisoformat(data["created_at"])
        updated_at = datetime.fromisoformat(data["updated_at"])

        session = Session(
            id=data["id"],
            profile=data["profile"],
            context=data.get("context", {}),
            created_at=created_at,
            updated_at=updated_at,
            message_count=data.get("message_count", 0),
        )

        logger.info(f"Resumed session: {session_id}")
        return session

    def list_sessions(self: "SessionManager") -> list[SessionInfo]:
        """List all sessions with metadata.

        Returns:
            List of SessionInfo objects sorted by update time (newest first)

        Example:
            >>> manager = SessionManager()
            >>> manager.create_session("default")
            >>> sessions = manager.list_sessions()
            >>> assert len(sessions) > 0
        """
        session_ids = list_stored(pattern="*", category="sessions")

        sessions: list[SessionInfo] = []
        for session_id in session_ids:
            try:
                data = load_json(session_id, category="sessions")

                info = SessionInfo(
                    id=data["id"],
                    profile=data["profile"],
                    created_at=datetime.fromisoformat(data["created_at"]),
                    updated_at=datetime.fromisoformat(data["updated_at"]),
                    message_count=data.get("message_count", 0),
                )
                sessions.append(info)

            except Exception as e:
                logger.warning(f"Failed to load session {session_id}: {e}")
                continue

        # Sort by updated_at (newest first)
        sessions.sort(key=lambda s: s.updated_at, reverse=True)

        return sessions

    def get_session_info(self: "SessionManager", session_id: str) -> SessionInfo | None:
        """Get session metadata.

        Args:
            session_id: Session ID

        Returns:
            SessionInfo object or None if session doesn't exist

        Example:
            >>> manager = SessionManager()
            >>> session = manager.create_session("default")
            >>> info = manager.get_session_info(session.id)
            >>> assert info is not None
            >>> assert info.id == session.id
        """
        if not exists(session_id, category="sessions"):
            return None

        try:
            data = load_json(session_id, category="sessions")

            return SessionInfo(
                id=data["id"],
                profile=data["profile"],
                created_at=datetime.fromisoformat(data["created_at"]),
                updated_at=datetime.fromisoformat(data["updated_at"]),
                message_count=data.get("message_count", 0),
            )
        except Exception as e:
            logger.error(f"Failed to load session info for {session_id}: {e}")
            return None

    def delete_session(self: "SessionManager", session_id: str) -> None:
        """Delete a session.

        Args:
            session_id: Session ID to delete

        Raises:
            FileNotFoundError: If session doesn't exist

        Example:
            >>> manager = SessionManager()
            >>> session = manager.create_session("default")
            >>> manager.delete_session(session.id)
            >>> assert not exists(session.id, category="sessions")
        """
        delete_stored(session_id, category="sessions")
        logger.info(f"Deleted session: {session_id}")

    def save_session(self: "SessionManager", session: Session) -> None:
        """Save session to storage.

        Updates the session's updated_at timestamp automatically.

        Args:
            session: Session object to save

        Example:
            >>> manager = SessionManager()
            >>> session = manager.create_session("default")
            >>> session.context["key"] = "new_value"
            >>> manager.save_session(session)
        """
        # Update timestamp
        session.updated_at = datetime.now(UTC)

        # Convert to dict for JSON storage
        data = {
            "id": session.id,
            "profile": session.profile,
            "context": session.context,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
            "message_count": session.message_count,
        }

        save_json(session.id, data, category="sessions")
        logger.debug(f"Saved session: {session.id}")
