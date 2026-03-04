"""Tests for session CRUD routes."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from amplifierd.app import create_app
from amplifierd.config import DaemonSettings
from amplifierd.state.event_bus import EventBus
from amplifierd.state.session_handle import SessionHandle
from amplifierd.state.session_manager import SessionManager


@pytest.fixture()
def client(tmp_path: Path) -> Generator[TestClient]:
    """Create a test client with an isolated session_manager."""
    app = create_app()
    with TestClient(app) as c:
        # Override AFTER lifespan so the real sessions_dir is not scanned
        event_bus = EventBus()
        settings = DaemonSettings(sessions_dir=tmp_path / "sessions")
        c.app.state.session_manager = SessionManager(  # type: ignore[union-attr]
            event_bus=event_bus, settings=settings, sessions_dir=tmp_path / "sessions"
        )
        yield c


async def _fake_cleanup() -> None:
    """No-op async cleanup for fake sessions."""


def _make_handle(
    session_id: str,
    *,
    children: dict[str, str] | None = None,
    event_bus: EventBus,
    working_dir: str | None = None,
) -> SessionHandle:
    """Create a minimal SessionHandle with a fake session for testing."""
    fake_coordinator = SimpleNamespace(request_cancel=lambda immediate: None)
    fake_session = SimpleNamespace(
        session_id=session_id,
        parent_id=None,
        coordinator=fake_coordinator,
        cleanup=_fake_cleanup,
    )
    handle = SessionHandle(
        session=fake_session,
        prepared_bundle=None,
        bundle_name="test-agent",
        event_bus=event_bus,
        working_dir=working_dir,
    )
    if children:
        for child_id, agent_name in children.items():
            handle._children[child_id] = agent_name  # noqa: SLF001
    return handle


def _register_handle(
    client: TestClient,
    session_id: str = "test-session-1",
    *,
    children: dict[str, str] | None = None,
    working_dir: str | None = None,
) -> SessionHandle:
    """Register a handle in the session manager and return it."""
    manager: SessionManager = client.app.state.session_manager  # type: ignore[union-attr]
    event_bus = manager._event_bus  # noqa: SLF001
    handle = _make_handle(
        session_id, event_bus=event_bus, children=children, working_dir=working_dir
    )
    manager._sessions[session_id] = handle  # noqa: SLF001
    return handle


@pytest.mark.unit
class TestSessionListEndpoint:
    """Tests for GET /sessions."""

    def test_list_empty(self, client: TestClient) -> None:
        """GET /sessions returns 200 with empty list and total=0 when no sessions exist."""
        resp = client.get("/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["sessions"] == []
        assert data["total"] == 0


@pytest.mark.unit
class TestSessionGetEndpoint:
    """Tests for GET /sessions/{session_id}."""

    def test_get_not_found(self, client: TestClient) -> None:
        """GET /sessions/nonexistent returns 404 with RFC 7807 ProblemDetail."""
        resp = client.get("/sessions/nonexistent")
        assert resp.status_code == 404
        data = resp.json()
        detail = data["detail"]
        assert detail["type"] == "https://amplifier.dev/errors/session-not-found"
        assert detail["status"] == 404


@pytest.mark.unit
class TestSessionDeleteEndpoint:
    """Tests for DELETE /sessions/{session_id}."""

    def test_delete_not_found(self, client: TestClient) -> None:
        """DELETE /sessions/nonexistent returns 404 with RFC 7807 ProblemDetail."""
        resp = client.delete("/sessions/nonexistent")
        assert resp.status_code == 404
        data = resp.json()
        detail = data["detail"]
        assert detail["type"] == "https://amplifier.dev/errors/session-not-found"
        assert detail["status"] == 404


@pytest.mark.unit
class TestSessionTreeEndpoint:
    """Tests for GET /sessions/{session_id}/tree."""

    def test_tree_truncates_at_max_depth(self, client: TestClient) -> None:
        """Deep session trees are truncated rather than hitting Python's recursion limit."""
        manager: SessionManager = client.app.state.session_manager  # type: ignore[union-attr]
        event_bus = manager._event_bus  # noqa: SLF001
        depth = 55  # exceeds the expected max_depth guard of 50

        # Build a linear chain: s-0 -> s-1 -> s-2 -> ... -> s-54
        ids = [f"s-{i}" for i in range(depth)]
        for i, sid in enumerate(ids):
            child_id = ids[i + 1] if i + 1 < depth else None
            children = {child_id: "child-agent"} if child_id else None
            handle = _make_handle(sid, children=children, event_bus=event_bus)
            manager._sessions[sid] = handle  # noqa: SLF001

        resp = client.get("/sessions/s-0/tree")
        assert resp.status_code == 200
        tree = resp.json()

        # Walk down the tree to find the truncation point
        node = tree
        levels = 0
        while node.get("children") and len(node["children"]) > 0:
            levels += 1
            node = node["children"][0]

        # The deepest leaf should be truncated (status="truncated")
        assert node["status"] == "truncated"
        assert node["children"] == []
        # Should have stopped well before the full chain depth
        assert levels <= 51  # 50 depth limit + root level


@pytest.mark.unit
class TestSessionListWithData:
    """Tests for GET /sessions with registered sessions."""

    def test_list_returns_registered_sessions(self, client: TestClient) -> None:
        """GET /sessions returns summaries of registered sessions."""
        _register_handle(client, "sess-a")
        _register_handle(client, "sess-b")
        resp = client.get("/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        ids = {s["session_id"] for s in data["sessions"]}
        assert ids == {"sess-a", "sess-b"}


@pytest.mark.unit
class TestSessionGetDetail:
    """Tests for GET /sessions/{session_id} with an existing session."""

    def test_get_existing_returns_detail(self, client: TestClient) -> None:
        """GET /sessions/{id} returns SessionDetail with working_dir and stale."""
        _register_handle(client, "sess-x", working_dir="/tmp/work")
        resp = client.get("/sessions/sess-x")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == "sess-x"
        assert data["working_dir"] == "/tmp/work"
        assert data["stale"] is False
        assert "status" in data
        assert "bundle" in data


@pytest.mark.unit
class TestSessionPatchEndpoint:
    """Tests for PATCH /sessions/{session_id}."""

    def test_patch_returns_session_detail(self, client: TestClient) -> None:
        """PATCH /sessions/{id} returns updated SessionDetail per spec."""
        _register_handle(client, "sess-p", working_dir="/old")
        resp = client.patch("/sessions/sess-p", json={"working_dir": "/new"})
        assert resp.status_code == 200
        data = resp.json()
        # Response must be a SessionDetail, not just {"status": "updated"}
        assert data["session_id"] == "sess-p"
        assert "working_dir" in data
        assert "status" in data
        assert "bundle" in data

    def test_patch_not_found(self, client: TestClient) -> None:
        """PATCH /sessions/nonexistent returns 404."""
        resp = client.patch("/sessions/nonexistent", json={"working_dir": "/x"})
        assert resp.status_code == 404


@pytest.mark.unit
class TestSessionDeleteExisting:
    """Tests for DELETE /sessions/{session_id} with an existing session."""

    def test_delete_existing_returns_204(self, client: TestClient) -> None:
        """DELETE /sessions/{id} for existing session returns 204 and removes it."""
        _register_handle(client, "sess-d")
        resp = client.delete("/sessions/sess-d")
        assert resp.status_code == 204
        # Verify the session is gone
        resp2 = client.get("/sessions/sess-d")
        assert resp2.status_code == 404


@pytest.mark.unit
class TestSessionCancelEndpoint:
    """Tests for POST /sessions/{session_id}/cancel."""

    def test_cancel_immediate_returns_immediate_state(self, client: TestClient) -> None:
        """Cancel with immediate=True returns {state: 'immediate'}."""
        _register_handle(client, "sess-c")
        resp = client.post("/sessions/sess-c/cancel", json={"immediate": True})
        assert resp.status_code == 200
        data = resp.json()
        assert data["state"] == "immediate"

    def test_cancel_graceful_returns_graceful_state(self, client: TestClient) -> None:
        """Cancel with immediate=False returns {state: 'graceful'}."""
        _register_handle(client, "sess-c2")
        resp = client.post("/sessions/sess-c2/cancel", json={"immediate": False})
        assert resp.status_code == 200
        data = resp.json()
        assert data["state"] == "graceful"

    def test_cancel_not_found(self, client: TestClient) -> None:
        """Cancel on nonexistent session returns 404."""
        resp = client.post("/sessions/nonexistent/cancel", json={"immediate": False})
        assert resp.status_code == 404


@pytest.mark.unit
class TestSessionStaleEndpoint:
    """Tests for POST /sessions/{session_id}/stale."""

    def test_mark_stale_returns_correct_response(self, client: TestClient) -> None:
        """POST /sessions/{id}/stale returns {session_id, stale: true}."""
        _register_handle(client, "sess-s")
        resp = client.post("/sessions/sess-s/stale")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == "sess-s"
        assert data["stale"] is True

    def test_stale_not_found(self, client: TestClient) -> None:
        """POST stale on nonexistent session returns 404."""
        resp = client.post("/sessions/nonexistent/stale")
        assert resp.status_code == 404
