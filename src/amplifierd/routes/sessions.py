"""Session CRUD routes and action endpoints for amplifierd."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from amplifierd.models.errors import ErrorTypeURI, ProblemDetail
from amplifierd.models.sessions import (
    CancelRequest,
    CancelResponse,
    CreateSessionRequest,
    ExecuteRequest,
    ExecuteResponse,
    ExecuteStreamAccepted,
    ForkRequest,
    ForkResponse,
    PatchSessionRequest,
    SessionDetail,
    SessionListResponse,
    SessionSummary,
    SessionTreeNode,
    StaleResponse,
)
from amplifierd.state.session_handle import SessionHandle, SessionStatus
from amplifierd.state.session_manager import SessionManager

logger = logging.getLogger(__name__)

sessions_router = APIRouter(prefix="/sessions", tags=["sessions"])

_MAX_TREE_DEPTH = 50


def _get_handle_or_404(request: Request, session_id: str) -> SessionHandle:
    """Return SessionHandle or raise HTTPException 404 with RFC 7807 ProblemDetail body."""
    manager = request.app.state.session_manager
    handle = manager.get(session_id)
    if handle is None:
        detail = ProblemDetail(
            type=ErrorTypeURI.SESSION_NOT_FOUND,
            title="Session Not Found",
            status=404,
            detail=f"Session '{session_id}' not found",
            instance=str(request.url.path),
        )
        raise HTTPException(
            status_code=404,
            detail=detail.model_dump(exclude_none=True),
        )
    return handle


def _summarize(handle: SessionHandle) -> SessionSummary:
    """Build a SessionSummary from a SessionHandle."""
    return SessionSummary(
        session_id=handle.session_id,
        status=handle.status.value,
        bundle=handle.bundle_name,
        created_at=handle.created_at.isoformat(),
        last_activity=handle.last_activity.isoformat(),
        parent_session_id=handle.parent_id,
        stale=handle.stale,
    )


def _summarize_from_dict(session: dict) -> SessionSummary:
    """Build a SessionSummary from a session dict (from list_sessions())."""
    return SessionSummary(
        session_id=session["session_id"],
        status=session["status"],
        bundle=session.get("bundle"),
        created_at=session.get("created_at"),
        last_activity=session.get("last_activity"),
        parent_session_id=session.get("parent_session_id"),
        stale=session.get("stale"),
    )


# ------------------------------------------------------------------
# CRUD endpoints
# ------------------------------------------------------------------


@sessions_router.post("", status_code=201)
async def create_session(request: Request, body: CreateSessionRequest) -> dict:
    """Create a new session by loading and preparing a bundle."""
    manager: SessionManager = request.app.state.session_manager
    registry = getattr(request.app.state, "bundle_registry", None)
    if registry is None:
        detail = ProblemDetail(
            type=ErrorTypeURI.BUNDLE_ERROR,
            title="Bundle Registry Unavailable",
            status=503,
            detail="Bundle registry is not available; cannot create session",
            instance=str(request.url.path),
        )
        raise HTTPException(
            status_code=503,
            detail=detail.model_dump(exclude_none=True),
        )
    if not body.bundle_name and not body.bundle_uri:
        detail = ProblemDetail(
            type=ErrorTypeURI.INVALID_REQUEST,
            title="Invalid Request",
            status=400,
            detail="bundle_name or bundle_uri is required",
            instance=str(request.url.path),
        )
        raise HTTPException(
            status_code=400,
            detail=detail.model_dump(exclude_none=True),
        )
    try:
        handle = await manager.create(
            bundle_name=body.bundle_name,
            bundle_uri=body.bundle_uri,
            working_dir=body.working_dir,
        )
    except ValueError as exc:
        logger.warning("Invalid session creation request: %s", exc)
        detail = ProblemDetail(
            type=ErrorTypeURI.INVALID_REQUEST,
            title="Invalid Request",
            status=400,
            detail=str(exc),
            instance=str(request.url.path),
        )
        raise HTTPException(
            status_code=400,
            detail=detail.model_dump(exclude_none=True),
        ) from exc
    except Exception as exc:
        logger.exception("Failed to create session")
        detail = ProblemDetail(
            type=ErrorTypeURI.BUNDLE_LOAD_ERROR,
            title="Session Creation Failed",
            status=502,
            detail=f"Failed to create session: {exc}",
            instance=str(request.url.path),
        )
        raise HTTPException(
            status_code=502,
            detail=detail.model_dump(exclude_none=True),
        ) from exc
    return {
        "session_id": handle.session_id,
        "status": str(handle.status),
        "bundle_name": handle.bundle_name,
        "working_dir": handle.working_dir,
        "created_at": handle.created_at.isoformat(),
    }


@sessions_router.get("", response_model=SessionListResponse)
async def list_sessions(request: Request) -> SessionListResponse:
    """List all sessions (active + historical)."""
    manager = request.app.state.session_manager
    sessions = manager.list_sessions()
    summaries = [_summarize_from_dict(s) for s in sessions]
    return SessionListResponse(sessions=summaries, total=len(summaries))


@sessions_router.get("/{session_id}", response_model=SessionDetail)
async def get_session(request: Request, session_id: str) -> SessionDetail:
    """Get detailed info for a single session."""
    handle = _get_handle_or_404(request, session_id)
    summary = _summarize(handle)
    return SessionDetail(
        **summary.model_dump(),
        working_dir=handle.working_dir,
    )


@sessions_router.patch("/{session_id}", response_model=SessionDetail)
async def patch_session(
    request: Request, session_id: str, body: PatchSessionRequest
) -> SessionDetail:
    """Patch session properties (e.g. working_dir)."""
    handle = _get_handle_or_404(request, session_id)
    if body.working_dir is not None:
        try:
            from amplifier_foundation import set_working_dir

            set_working_dir(handle.session, body.working_dir)
        except (ImportError, AttributeError):
            logger.warning("amplifier_foundation.set_working_dir not available or failed")
        handle._working_dir = body.working_dir  # noqa: SLF001
    summary = _summarize(handle)
    return SessionDetail(
        **summary.model_dump(),
        working_dir=handle.working_dir,
    )


@sessions_router.delete("/{session_id}", status_code=204)
async def delete_session(request: Request, session_id: str) -> None:
    """Destroy a session."""
    _get_handle_or_404(request, session_id)
    manager = request.app.state.session_manager
    await manager.destroy(session_id)


# ------------------------------------------------------------------
# Action endpoints
# ------------------------------------------------------------------


@sessions_router.post("/{session_id}/execute", response_model=ExecuteResponse)
async def execute(request: Request, session_id: str, body: ExecuteRequest) -> ExecuteResponse:
    """Execute a prompt synchronously (blocks until complete)."""
    handle = _get_handle_or_404(request, session_id)
    if handle.status == SessionStatus.EXECUTING:
        detail = ProblemDetail(
            type=ErrorTypeURI.EXECUTION_IN_PROGRESS,
            title="Execution In Progress",
            status=409,
            detail=f"Session '{session_id}' is already executing",
            instance=str(request.url.path),
        )
        raise HTTPException(
            status_code=409,
            detail=detail.model_dump(exclude_none=True),
        )
    result = await handle.execute(body.prompt)
    return ExecuteResponse(
        response=str(result) if result is not None else None,
    )


@sessions_router.post(
    "/{session_id}/execute/stream",
    status_code=202,
    response_model=ExecuteStreamAccepted,
)
async def execute_stream(
    request: Request, session_id: str, body: ExecuteRequest
) -> ExecuteStreamAccepted:
    """Fire-and-forget streaming execution (returns immediately with correlation_id)."""
    handle = _get_handle_or_404(request, session_id)
    turn_count = handle.turn_count + 1
    correlation_id = f"prompt_{session_id}_{turn_count}"

    async def _run() -> None:
        try:
            await handle.execute(body.prompt)
        except Exception:
            logger.exception("Streaming execution failed for session %s", session_id)
        finally:
            background_tasks.discard(task)

    background_tasks: set[asyncio.Task[None]] = request.app.state.background_tasks
    task = asyncio.create_task(_run())
    background_tasks.add(task)
    return ExecuteStreamAccepted(
        correlation_id=correlation_id,
        session_id=session_id,
    )


@sessions_router.post("/{session_id}/cancel", response_model=CancelResponse)
async def cancel_session(request: Request, session_id: str, body: CancelRequest) -> CancelResponse:
    """Cancel the current execution."""
    handle = _get_handle_or_404(request, session_id)
    immediate = body.immediate or False
    handle.cancel(immediate=immediate)
    state = "immediate" if immediate else "graceful"
    return CancelResponse(state=state)


@sessions_router.post("/{session_id}/stale", response_model=StaleResponse)
async def mark_stale(request: Request, session_id: str) -> StaleResponse:
    """Mark a session as stale."""
    handle = _get_handle_or_404(request, session_id)
    handle.mark_stale()
    return StaleResponse(session_id=session_id, stale=True)


# ------------------------------------------------------------------
# Fork / turns / lineage endpoints
# ------------------------------------------------------------------


@sessions_router.post("/{session_id}/fork", response_model=ForkResponse)
async def fork_session_endpoint(
    request: Request, session_id: str, body: ForkRequest
) -> ForkResponse:
    """Fork a session at a specific turn, returning the new session's metadata."""
    handle = _get_handle_or_404(request, session_id)
    handle_orphaned = body.handle_orphaned_tools or "complete"

    new_session_id: str
    message_count = 0
    forked_from_turn = body.turn

    try:
        from amplifier_foundation.session import fork_session_in_memory

        messages: list[Any] = []
        context = getattr(handle.session, "context", None)
        if context is not None:
            try:
                messages = list(context.get_messages() or [])
            except Exception:
                pass

        result = fork_session_in_memory(
            messages,
            turn=body.turn,
            parent_id=session_id,
            handle_orphaned_tools=handle_orphaned,
        )
        new_session_id = result.session_id
        message_count = result.message_count
        forked_from_turn = result.forked_from_turn if result.forked_from_turn else body.turn
    except (ImportError, AttributeError):
        logger.warning("fork_session_in_memory not available; using stub fork for %s", session_id)
        new_session_id = f"{session_id}-fork-t{body.turn}-{uuid.uuid4().hex[:8]}"

    return ForkResponse(
        session_id=new_session_id,
        parent_id=session_id,
        forked_from_turn=forked_from_turn,
        message_count=message_count,
    )


@sessions_router.get("/{session_id}/fork/preview")
async def fork_preview(request: Request, session_id: str, turn: int) -> dict[str, Any]:
    """Preview what forking a session at a given turn would produce."""
    handle = _get_handle_or_404(request, session_id)

    try:
        from amplifier_foundation.session import fork_session_in_memory, get_turn_boundaries

        messages: list[Any] = []
        context = getattr(handle.session, "context", None)
        if context is not None:
            try:
                messages = list(context.get_messages() or [])
            except Exception:
                pass

        result = fork_session_in_memory(messages, turn=turn, parent_id=session_id)
        boundaries = get_turn_boundaries(messages)
        return {
            "session_id": session_id,
            "turn": turn,
            "max_turns": len(boundaries),
            "message_count": result.message_count,
            "messages": result.messages or [],
        }
    except (ImportError, AttributeError):
        logger.warning("fork preview foundation functions not available for %s", session_id)
        return {
            "session_id": session_id,
            "turn": turn,
            "max_turns": handle.turn_count,
            "message_count": 0,
            "messages": [],
        }


@sessions_router.get("/{session_id}/turns")
async def list_turns(request: Request, session_id: str) -> dict[str, Any]:
    """List turn boundaries for a session derived from its context messages."""
    handle = _get_handle_or_404(request, session_id)

    turns: list[dict[str, Any]] = []
    try:
        from amplifier_foundation.session import get_turn_boundaries

        messages: list[Any] = []
        context = getattr(handle.session, "context", None)
        if context is not None:
            try:
                messages = list(context.get_messages() or [])
            except Exception:
                pass

        boundaries = get_turn_boundaries(messages)
        for i, start_idx in enumerate(boundaries, start=1):
            turns.append({"turn": i, "start_index": start_idx})
    except (ImportError, AttributeError):
        logger.warning("get_turn_boundaries not available; using turn_count for %s", session_id)
        for i in range(1, handle.turn_count + 1):
            turns.append({"turn": i})

    return {"turns": turns, "total": len(turns)}


@sessions_router.get("/{session_id}/lineage")
async def session_lineage(request: Request, session_id: str) -> dict[str, Any]:
    """Return the ancestor chain from the root session down to this session."""
    handle = _get_handle_or_404(request, session_id)
    manager = request.app.state.session_manager

    chain: list[dict[str, Any]] = []
    current: SessionHandle | None = handle
    visited: set[str] = set()

    while current is not None and current.session_id not in visited:
        visited.add(current.session_id)
        chain.append(_summarize(current).model_dump())
        parent_id = current.parent_id
        if parent_id is None:
            break
        current = manager.get(parent_id)

    # Reverse so root (oldest ancestor) appears first
    chain.reverse()
    return {"sessions": chain, "total": len(chain)}


@sessions_router.get("/{session_id}/forks")
async def list_forks(request: Request, session_id: str) -> dict[str, Any]:
    """List all direct child forks of a session (sessions whose parent_id matches)."""
    _get_handle_or_404(request, session_id)
    manager = request.app.state.session_manager

    all_sessions = manager.list_sessions()
    fork_summaries = [
        _summarize_from_dict(s).model_dump()
        for s in all_sessions
        if s.get("parent_session_id") == session_id
    ]
    return {"sessions": fork_summaries, "total": len(fork_summaries)}


# ------------------------------------------------------------------
# Tree endpoint
# ------------------------------------------------------------------


@sessions_router.get("/{session_id}/tree", response_model=SessionTreeNode)
async def session_tree(request: Request, session_id: str) -> SessionTreeNode:
    """Build recursive session tree from this session."""
    handle = _get_handle_or_404(request, session_id)
    manager = request.app.state.session_manager

    def _build_tree(h: SessionHandle, depth: int = 0) -> SessionTreeNode:
        if depth > _MAX_TREE_DEPTH:
            return SessionTreeNode(
                session_id=h.session_id,
                agent=h.bundle_name,
                status="truncated",
            )
        children_list: list[SessionTreeNode] = []
        for child_id, agent_name in h.children.items():
            child_handle = manager.get(child_id)
            if child_handle is not None:
                children_list.append(_build_tree(child_handle, depth + 1))
            else:
                children_list.append(SessionTreeNode(session_id=child_id, agent=agent_name))
        return SessionTreeNode(
            session_id=h.session_id,
            agent=h.bundle_name,
            status=h.status.value,
            children=children_list,
        )

    return _build_tree(handle)
