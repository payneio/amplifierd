"""Messages router for amplifierd API.

Handles message operations: send message, get transcript, execute with streaming.
"""

import logging

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from sse_starlette.sse import EventSourceResponse

from amplifier_library.execution.runner import ExecutionRunner
from amplifier_library.sessions.manager import SessionManager
from amplifier_library.sessions.state import add_message
from amplifier_library.sessions.state import get_transcript

from ..models import MessageResponse
from ..models import SendMessageRequest
from ..models import TranscriptResponse
from ..streaming import sse_event_stream
from ..streaming import wrap_execution_stream

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/sessions/{session_id}", tags=["messages"])


def get_session_manager() -> SessionManager:
    """Dependency to get SessionManager instance.

    Returns:
        SessionManager instance
    """
    return SessionManager()


@router.post("/messages", response_model=MessageResponse, status_code=201)
async def send_message(
    session_id: str,
    request: SendMessageRequest,
    manager: SessionManager = Depends(get_session_manager),
) -> MessageResponse:
    """Send a message to a session (synchronous).

    This endpoint adds a user message to the session transcript without
    executing it. Use the /execute endpoint for execution with streaming.

    Args:
        session_id: Session ID
        request: Message request
        manager: SessionManager dependency

    Returns:
        Created message

    Raises:
        HTTPException: 404 if session not found, 500 on error
    """
    try:
        # Resume session
        session = manager.resume_session(session_id)

        # Add user message
        message = add_message(session, role="user", content=request.content)

        # Save updated session
        manager.save_session(session)

        return MessageResponse(
            role=message.role,
            content=message.content,
            timestamp=message.timestamp,
            metadata=message.metadata,
        )

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found") from e
    except Exception as e:
        logger.error(f"Failed to send message to session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.get("/messages", response_model=TranscriptResponse)
async def get_messages(
    session_id: str,
    manager: SessionManager = Depends(get_session_manager),
) -> TranscriptResponse:
    """Get session transcript.

    Args:
        session_id: Session ID
        manager: SessionManager dependency

    Returns:
        Session transcript with all messages

    Raises:
        HTTPException: 404 if session not found
    """
    try:
        # Verify session exists
        manager.resume_session(session_id)

        # Get transcript
        messages = get_transcript(session_id)

        return TranscriptResponse(
            session_id=session_id,
            messages=[
                MessageResponse(
                    role=msg.role,
                    content=msg.content,
                    timestamp=msg.timestamp,
                    metadata=msg.metadata,
                )
                for msg in messages
            ],
        )

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found") from e
    except Exception as e:
        logger.error(f"Failed to get transcript for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e


@router.post("/execute")
async def execute_with_streaming(
    session_id: str,
    request: SendMessageRequest,
    manager: SessionManager = Depends(get_session_manager),
) -> EventSourceResponse:
    """Execute user input with SSE streaming.

    This endpoint executes the user input and streams the response using
    Server-Sent Events (SSE).

    Args:
        session_id: Session ID
        request: Message/execution request
        manager: SessionManager dependency

    Returns:
        SSE EventSourceResponse with execution events

    Raises:
        HTTPException: 404 if session not found

    Events:
        - message: Content chunks during execution
        - done: Execution completed successfully
        - error: Execution failed with error
    """
    try:
        # Resume session
        session = manager.resume_session(session_id)

        # Create execution runner with empty config
        # amplifier-core configuration is loaded from its own config system
        runner = ExecutionRunner(config={}, search_paths=[])

        # Create async generator for streaming
        async def event_generator():
            """Generate SSE events from execution."""
            try:
                # Wrap execution in event stream
                event_stream = wrap_execution_stream(runner.execute(session, request.content))

                # Convert to SSE format
                async for event_str in sse_event_stream(event_stream):
                    yield event_str

                # Save updated session
                manager.save_session(session)

            except Exception as e:
                logger.error(f"Execution error in session {session_id}: {e}")
                # Yield error event
                yield f"event: error\ndata: {{'type': 'error', 'error': '{e!s}'}}\n\n"

        return EventSourceResponse(event_generator())

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found") from e
    except Exception as e:
        logger.error(f"Failed to execute in session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error") from e
