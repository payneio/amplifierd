"""Sessions router for amplifierd API.

Handles session lifecycle operations: create, list, get, resume, delete.
"""

import logging

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException

from amplifier_library.sessions.manager import SessionManager

from ..models import CreateSessionRequest
from ..models import SessionInfoResponse
from ..models import SessionResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


def get_session_manager() -> SessionManager:
    """Dependency to get SessionManager instance.

    Returns:
        SessionManager instance
    """
    return SessionManager()


@router.post("", response_model=SessionResponse, status_code=201)
async def create_session(
    request: CreateSessionRequest,
    manager: SessionManager = Depends(get_session_manager),
) -> SessionResponse:
    """Create a new session.

    Args:
        request: Session creation request
        manager: SessionManager dependency

    Returns:
        Created session details

    Raises:
        HTTPException: 500 if session creation fails
    """
    try:
        session = manager.create_session(
            profile=request.profile,
            context=request.context,
        )

        return SessionResponse(
            id=session.id,
            profile=session.profile,
            context=session.context,
            created_at=session.created_at,
            updated_at=session.updated_at,
            message_count=session.message_count,
        )

    except Exception as e:
        logger.error(f"Failed to create session: {e}")
        raise HTTPException(status_code=500, detail="Failed to create session") from e


@router.get("", response_model=list[SessionInfoResponse])
async def list_sessions(
    manager: SessionManager = Depends(get_session_manager),
) -> list[SessionInfoResponse]:
    """List all sessions.

    Args:
        manager: SessionManager dependency

    Returns:
        List of session info objects
    """
    try:
        sessions = manager.list_sessions()

        return [
            SessionInfoResponse(
                id=s.id,
                profile=s.profile,
                created_at=s.created_at,
                updated_at=s.updated_at,
                message_count=s.message_count,
            )
            for s in sessions
        ]

    except Exception as e:
        logger.error(f"Failed to list sessions: {e}")
        raise HTTPException(status_code=500, detail="Failed to list sessions") from e


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    manager: SessionManager = Depends(get_session_manager),
) -> SessionResponse:
    """Get session details.

    Args:
        session_id: Session ID
        manager: SessionManager dependency

    Returns:
        Session details

    Raises:
        HTTPException: 404 if session not found
    """
    try:
        session = manager.resume_session(session_id)

        return SessionResponse(
            id=session.id,
            profile=session.profile,
            context=session.context,
            created_at=session.created_at,
            updated_at=session.updated_at,
            message_count=session.message_count,
        )

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found") from e
    except Exception as e:
        logger.error(f"Failed to get session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/{session_id}/resume", response_model=SessionResponse)
async def resume_session(
    session_id: str,
    manager: SessionManager = Depends(get_session_manager),
) -> SessionResponse:
    """Resume an existing session.

    Args:
        session_id: Session ID
        manager: SessionManager dependency

    Returns:
        Session details

    Raises:
        HTTPException: 404 if session not found
    """
    try:
        session = manager.resume_session(session_id)

        return SessionResponse(
            id=session.id,
            profile=session.profile,
            context=session.context,
            created_at=session.created_at,
            updated_at=session.updated_at,
            message_count=session.message_count,
        )

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found") from e
    except Exception as e:
        logger.error(f"Failed to resume session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.delete("/{session_id}", status_code=204)
async def delete_session(
    session_id: str,
    manager: SessionManager = Depends(get_session_manager),
) -> None:
    """Delete a session.

    Args:
        session_id: Session ID
        manager: SessionManager dependency

    Raises:
        HTTPException: 404 if session not found
    """
    try:
        manager.delete_session(session_id)

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found") from e
    except Exception as e:
        logger.error(f"Failed to delete session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e
