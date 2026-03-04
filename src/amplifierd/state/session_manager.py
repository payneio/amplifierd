"""SessionManager — central registry of all live sessions.

The SessionManager is the only component that creates, stores, or destroys
SessionHandle instances. All route handlers access sessions through it.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from amplifierd.config import DaemonSettings
from amplifierd.state.event_bus import EventBus
from amplifierd.state.session_handle import SessionHandle
from amplifierd.state.session_index import SessionIndex, SessionIndexEntry

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
        sessions_dir: Path | None = None,
    ) -> None:
        self._sessions: dict[str, SessionHandle] = {}
        self._event_bus = event_bus
        self._settings = settings
        self._bundle_registry = bundle_registry
        self._sessions_dir = sessions_dir
        self._index: SessionIndex | None = None
        if sessions_dir:
            index_path = sessions_dir / "index.json"
            if index_path.exists():
                try:
                    self._index = SessionIndex.load(index_path)
                except Exception:
                    self._index = SessionIndex.rebuild(sessions_dir)
            else:
                self._index = SessionIndex.rebuild(sessions_dir)

    @property
    def event_bus(self) -> EventBus:
        return self._event_bus

    @property
    def settings(self) -> DaemonSettings:
        return self._settings

    @property
    def sessions_dir(self) -> Path | None:
        return self._sessions_dir

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
        if self._index is not None:
            self._index.add(
                SessionIndexEntry(
                    session_id=session_id,
                    status=str(handle.status),
                    bundle=bundle_name,
                    created_at=handle.created_at.isoformat(),
                    last_activity=handle.last_activity.isoformat(),
                    parent_session_id=getattr(session, "parent_id", None),
                )
            )
            self._index.save()
        logger.info("Registered session %s (bundle=%s)", session_id, bundle_name)
        return handle

    def get(self, session_id: str) -> SessionHandle | None:
        """Get a session by ID, or None if not found."""
        return self._sessions.get(session_id)

    def list_sessions(self) -> list[dict]:
        """List all sessions: active in-memory sessions first, then historical from index.

        Returns a list of dicts with a consistent shape:
            session_id, status, bundle, created_at, last_activity,
            parent_session_id, stale, is_active, working_dir
        """
        active_ids = set(self._sessions)
        result: list[dict] = []

        for handle in self._sessions.values():
            result.append(
                {
                    "session_id": handle.session_id,
                    "status": str(handle.status),
                    "bundle": handle.bundle_name,
                    "created_at": handle.created_at.isoformat(),
                    "last_activity": handle.last_activity.isoformat(),
                    "parent_session_id": handle.parent_id,
                    "stale": handle.stale,
                    "is_active": True,
                    "working_dir": handle.working_dir,
                }
            )

        if self._index is not None:
            for entry in self._index.list_entries():
                if entry.session_id not in active_ids:
                    result.append(
                        {
                            "session_id": entry.session_id,
                            "status": entry.status,
                            "bundle": entry.bundle,
                            "created_at": entry.created_at,
                            "last_activity": entry.last_activity,
                            "parent_session_id": entry.parent_session_id,
                            "stale": None,
                            "is_active": False,
                            "working_dir": None,
                        }
                    )

        return result

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

        # Inject providers from ~/.amplifier/settings.yaml BEFORE prepare()
        # so the activation step downloads and installs their dependencies.
        from amplifierd.providers import inject_providers, load_provider_config

        providers = load_provider_config()
        inject_providers(bundle, providers)

        prepared = await bundle.prepare()
        session = await prepared.create_session()

        # Register transcript/metadata persistence hooks
        if self._sessions_dir:
            from amplifierd.persistence import register_persistence_hooks

            session_dir = self._sessions_dir / session.session_id
            session_dir.mkdir(parents=True, exist_ok=True)
            info_path = session_dir / "session-info.json"
            if not info_path.exists():
                info_path.write_text(json.dumps({"working_dir": str(wd)}))
            register_persistence_hooks(
                session,
                session_dir,
                initial_metadata={
                    "session_id": session.session_id,
                    "created": datetime.now(tz=UTC).isoformat(),
                    "bundle": bundle_name or bundle_uri or "unknown",
                    "working_dir": str(wd),
                },
            )

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
        if self._index is not None:
            self._index.update(session_id, status="completed")
            self._index.save()
        logger.info("Destroyed session %s", session_id)

    async def shutdown(self) -> None:
        """Gracefully shutdown all sessions (called on daemon shutdown)."""
        session_ids = list(self._sessions.keys())
        for sid in session_ids:
            try:
                await self.destroy(sid)
            except Exception as exc:
                logger.warning("Error destroying session %s during shutdown: %s", sid, exc)
