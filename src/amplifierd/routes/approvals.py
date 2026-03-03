"""Approval routes with asyncio.Future-based gates and WebSocket channel."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from amplifierd.models.errors import ErrorTypeURI, ProblemDetail
from amplifierd.state.event_bus import EventBus

logger = logging.getLogger(__name__)

approvals_router = APIRouter(tags=["approvals"])


# ------------------------------------------------------------------
# Domain objects
# ------------------------------------------------------------------


class PendingApproval:
    """An approval request waiting for a response, backed by an asyncio.Future.

    The Future is created lazily so that instances can be constructed
    outside of a running event loop (e.g. in synchronous test setup).
    """

    def __init__(
        self,
        request_id: str,
        session_id: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        self.request_id = request_id
        self.session_id = session_id
        self.data = data or {}
        self._future: asyncio.Future[dict[str, Any]] | None = None
        self._resolved = False
        self._result: dict[str, Any] | None = None

    @property
    def future(self) -> asyncio.Future[dict[str, Any]]:
        """Lazily create and return the asyncio.Future gate."""
        if self._future is None:
            self._future = asyncio.get_running_loop().create_future()
        return self._future

    @property
    def resolved(self) -> bool:
        if self._future is not None:
            return self._future.done()
        return self._resolved

    def resolve(self, result: dict[str, Any]) -> None:
        """Resolve this approval with the given result."""
        self._resolved = True
        self._result = result
        if self._future is not None and not self._future.done():
            self._future.set_result(result)

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "session_id": self.session_id,
            "data": self.data,
            "resolved": self.resolved,
        }


class ApprovalResponse(BaseModel):
    """Request body for responding to an approval."""

    approved: bool
    message: str | None = None


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _get_pending(app: Any) -> dict[str, dict[str, PendingApproval]]:
    """Get or initialize the pending approvals registry on app.state."""
    if not hasattr(app.state, "pending_approvals"):
        app.state.pending_approvals = {}
    return app.state.pending_approvals


def _get_handle_or_404(request: Request, session_id: str) -> Any:
    """Return SessionHandle or raise HTTPException 404."""
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


# ------------------------------------------------------------------
# Endpoints
# ------------------------------------------------------------------


@approvals_router.get("/sessions/{session_id}/approvals")
async def list_approvals(request: Request, session_id: str) -> dict[str, Any]:
    """List pending approvals for a session."""
    _get_handle_or_404(request, session_id)
    pending = _get_pending(request.app)
    session_approvals = pending.get(session_id, {})
    pending_list = [a.to_dict() for a in session_approvals.values() if not a.resolved]
    return {"session_id": session_id, "approvals": pending_list, "total": len(pending_list)}


@approvals_router.post("/sessions/{session_id}/approvals/{request_id}")
async def respond_to_approval(
    request: Request,
    session_id: str,
    request_id: str,
    body: ApprovalResponse,
) -> dict[str, Any]:
    """Respond to a pending approval, resolving its asyncio.Future gate."""
    _get_handle_or_404(request, session_id)
    pending = _get_pending(request.app)
    session_approvals = pending.get(session_id, {})
    approval = session_approvals.get(request_id)
    if approval is None:
        detail = ProblemDetail(
            type=ErrorTypeURI.APPROVAL_NOT_FOUND,
            title="Approval Not Found",
            status=404,
            detail=f"Approval request '{request_id}' not found in session '{session_id}'",
            instance=str(request.url.path),
        )
        raise HTTPException(status_code=404, detail=detail.model_dump(exclude_none=True))
    approval.resolve({"approved": body.approved, "message": body.message})
    return {"request_id": request_id, "status": "resolved"}


@approvals_router.websocket("/sessions/{session_id}/approvals/ws")
async def approval_ws(websocket: WebSocket, session_id: str) -> None:
    """Bidirectional WebSocket channel for approval events.

    Pushes ``approval:required`` events from the EventBus and accepts
    ``approval_response`` messages from the client.
    """
    manager = websocket.app.state.session_manager
    if manager.get(session_id) is None:
        await websocket.close(code=4004, reason="Session not found")
        return

    await websocket.accept()
    event_bus: EventBus = websocket.app.state.event_bus

    async def _push_approval_events() -> None:
        async for event in event_bus.subscribe(session_id=session_id):
            if event.event_name == "approval:required":
                await websocket.send_json(event.to_sse_dict())

    async def _receive_responses() -> None:
        try:
            while True:
                data = await websocket.receive_json()
                if data.get("type") == "approval_response":
                    request_id = data.get("request_id")
                    if request_id:
                        pending = _get_pending(websocket.app)
                        session_approvals = pending.get(session_id, {})
                        approval = session_approvals.get(request_id)
                        if approval and not approval.resolved:
                            approval.resolve(
                                {
                                    "approved": data.get("approved", False),
                                    "message": data.get("message"),
                                }
                            )
                            await websocket.send_json(
                                {
                                    "type": "approval_ack",
                                    "request_id": request_id,
                                    "status": "resolved",
                                }
                            )
        except WebSocketDisconnect:
            pass

    push_task = asyncio.create_task(_push_approval_events())
    try:
        await _receive_responses()
    finally:
        push_task.cancel()
        try:
            await push_task
        except asyncio.CancelledError:
            pass
