"""SessionManager — central registry of all live sessions.

The SessionManager is the only component that creates, stores, or destroys
SessionHandle instances. All route handlers access sessions through it.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from amplifierd.config import DaemonSettings
from amplifierd.state.event_bus import EventBus
from amplifierd.state.session_handle import SessionHandle

logger = logging.getLogger(__name__)


class SessionManager:
    """Central owner of all live sessions.

    A single instance is created at startup and stored in app.state.
    """

    def __init__(
        self,
        *,
        event_bus: EventBus,
        settings: DaemonSettings,
        bundle_registry: Any = None,
    ) -> None:
        self._sessions: dict[str, SessionHandle] = {}
        self._event_bus = event_bus
        self._settings = settings
        self._bundle_registry = bundle_registry

    @property
    def event_bus(self) -> EventBus:
        return self._event_bus

    @property
    def settings(self) -> DaemonSettings:
        return self._settings

    def resolve_working_dir(self, request_working_dir: str | None) -> str:
        """Resolve working directory using the fallback chain:
        request > daemon config > user home.
        """
        if request_working_dir:
            return request_working_dir
        if self._settings.default_working_dir:
            return str(self._settings.default_working_dir)
        return str(Path.home())

    def register(
        self,
        *,
        session: Any,  # AmplifierSession
        prepared_bundle: Any | None,  # PreparedBundle
        bundle_name: str,
        working_dir: str | None = None,
    ) -> SessionHandle:
        """Register a pre-created session and wrap it in a SessionHandle."""
        session_id: str = session.session_id
        if session_id in self._sessions:
            msg = f"Session {session_id} already exists"
            raise ValueError(msg)

        handle = SessionHandle(
            session=session,
            prepared_bundle=prepared_bundle,
            bundle_name=bundle_name,
            event_bus=self._event_bus,
            working_dir=working_dir,
        )
        self._sessions[session_id] = handle
        logger.info("Registered session %s (bundle=%s)", session_id, bundle_name)
        return handle

    def get(self, session_id: str) -> SessionHandle | None:
        """Get a session by ID, or None if not found."""
        return self._sessions.get(session_id)

    def list_sessions(self) -> list[SessionHandle]:
        """List all live sessions."""
        return list(self._sessions.values())

    async def create(
        self,
        *,
        bundle_name: str | None = None,
        bundle_uri: str | None = None,
        working_dir: str | None = None,
    ) -> SessionHandle:
        """Create a new session by loading and preparing a bundle.

        Args:
            bundle_name: Registered bundle name to load.
            bundle_uri: Bundle URI to load directly.
            working_dir: Working directory override; falls back to daemon config or home.

        Returns:
            The newly created and registered SessionHandle.

        Raises:
            RuntimeError: If BundleRegistry is not available.
            ValueError: If neither bundle_name nor bundle_uri is provided.
        """
        if not self._bundle_registry:
            raise RuntimeError("BundleRegistry not available")
        if not bundle_name and not bundle_uri:
            raise ValueError("bundle_name or bundle_uri required")

        wd = self.resolve_working_dir(working_dir)
        name_or_uri = bundle_uri or bundle_name
        bundle = await self._bundle_registry.load(name_or_uri)
        prepared = await bundle.prepare()
        session = prepared.create_session()
        handle = self.register(
            session=session,
            prepared_bundle=prepared,
            bundle_name=bundle_name or bundle_uri or "unknown",
            working_dir=wd,
        )
        return handle

    async def destroy(self, session_id: str) -> None:
        """Destroy a session: cleanup resources and remove from registry."""
        handle = self._sessions.pop(session_id, None)
        if handle is None:
            logger.warning("Attempted to destroy unknown session %s", session_id)
            return
        await handle.cleanup()
        logger.info("Destroyed session %s", session_id)

    async def shutdown(self) -> None:
        """Gracefully shutdown all sessions (called on daemon shutdown)."""
        session_ids = list(self._sessions.keys())
        for sid in session_ids:
            try:
                await self.destroy(sid)
            except Exception as exc:
                logger.warning("Error destroying session %s during shutdown: %s", sid, exc)
