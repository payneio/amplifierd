"""Session state management functions.

Handles adding messages, updating context, and retrieving transcripts.

Contract:
- Inputs: Session objects, messages, context updates
- Outputs: Message objects, updated sessions, transcripts
- Side Effects: Persists transcript to JSON storage via json_store
"""

import logging
from datetime import UTC
from datetime import datetime
from typing import Any

from ..models import Message
from ..models import Session
from ..storage.json_store import exists
from ..storage.json_store import load_json
from ..storage.json_store import save_json

logger = logging.getLogger(__name__)


def add_message(
    session: Session,
    role: str,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> Message:
    """Add a message to session transcript.

    Updates the session's message count and saves the transcript.

    Args:
        session: Session to add message to
        role: Message role (user, assistant, system)
        content: Message content
        metadata: Optional message metadata

    Returns:
        New Message object

    Example:
        >>> from amplifier_library.sessions import SessionManager
        >>> manager = SessionManager()
        >>> session = manager.create_session("default")
        >>> msg = add_message(session, "user", "Hello")
        >>> assert msg.role == "user"
        >>> assert session.message_count == 1
    """
    # Create message
    message = Message(
        role=role,
        content=content,
        timestamp=datetime.now(UTC),
        metadata=metadata or {},
    )

    # Load existing transcript
    transcript = _load_transcript(session.id)

    # Add message
    transcript.append(message)

    # Save transcript
    _save_transcript(session.id, transcript)

    # Update session message count
    session.message_count = len(transcript)

    logger.debug(f"Added {role} message to session {session.id}")

    return message


def update_context(session: Session, context_updates: dict[str, Any]) -> None:
    """Update session context.

    Merges context_updates into session.context.

    Args:
        session: Session to update
        context_updates: Dictionary of context updates to merge

    Example:
        >>> from amplifier_library.sessions import SessionManager
        >>> manager = SessionManager()
        >>> session = manager.create_session("default")
        >>> update_context(session, {"key": "value"})
        >>> assert session.context["key"] == "value"
    """
    session.context.update(context_updates)
    logger.debug(f"Updated context for session {session.id}")


def get_transcript(session_id: str) -> list[Message]:
    """Get session transcript.

    Args:
        session_id: Session ID

    Returns:
        List of Message objects

    Raises:
        FileNotFoundError: If session doesn't exist

    Example:
        >>> from amplifier_library.sessions import SessionManager
        >>> manager = SessionManager()
        >>> session = manager.create_session("default")
        >>> add_message(session, "user", "Hello")
        >>> transcript = get_transcript(session.id)
        >>> assert len(transcript) == 1
    """
    if not exists(session_id, category="sessions"):
        raise FileNotFoundError(f"Session '{session_id}' not found")

    return _load_transcript(session_id)


def _load_transcript(session_id: str) -> list[Message]:
    """Load transcript from storage.

    Args:
        session_id: Session ID

    Returns:
        List of Message objects (empty if transcript doesn't exist)
    """
    transcript_key = f"{session_id}_transcript"

    if not exists(transcript_key, category="sessions"):
        return []

    try:
        data = load_json(transcript_key, category="sessions")
        messages = data.get("messages", [])

        # Convert dicts back to Message objects
        return [
            Message(
                role=msg["role"],
                content=msg["content"],
                timestamp=datetime.fromisoformat(msg["timestamp"]),
                metadata=msg.get("metadata", {}),
            )
            for msg in messages
        ]
    except Exception as e:
        logger.warning(f"Failed to load transcript for {session_id}: {e}")
        return []


def _save_transcript(session_id: str, transcript: list[Message]) -> None:
    """Save transcript to storage.

    Args:
        session_id: Session ID
        transcript: List of Message objects
    """
    transcript_key = f"{session_id}_transcript"

    # Convert Message objects to dicts
    messages = [
        {
            "role": msg.role,
            "content": msg.content,
            "timestamp": msg.timestamp.isoformat(),
            "metadata": msg.metadata,
        }
        for msg in transcript
    ]

    data = {"messages": messages}

    save_json(transcript_key, data, category="sessions")
    logger.debug(f"Saved transcript for session {session_id} ({len(messages)} messages)")
