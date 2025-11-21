"""Session management for amplifier_library.

This module provides session lifecycle management including:
- Creating new sessions with unique IDs
- Resuming existing sessions from storage
- Managing session state and transcripts
- Listing and deleting sessions

Contract:
- Inputs: Profile names, session IDs, user messages
- Outputs: Session objects, session info, transcripts
- Side Effects: Persists sessions to JSON storage
"""

from .manager import SessionManager
from .state import add_message
from .state import get_transcript
from .state import update_context

__all__ = [
    "SessionManager",
    "add_message",
    "get_transcript",
    "update_context",
]
