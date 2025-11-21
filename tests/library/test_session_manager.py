"""
Unit tests for SessionManager.

Tests session CRUD operations, persistence, and error handling.
"""

from datetime import UTC
from datetime import datetime

import pytest

from amplifier_library.models import Session
from amplifier_library.models import SessionInfo
from amplifier_library.sessions.manager import SessionManager
from amplifier_library.storage.json_store import exists


@pytest.mark.unit
class TestSessionManager:
    """Test SessionManager operations."""

    def test_create_session_generates_unique_id(self, session_manager: SessionManager) -> None:
        """Test create_session generates unique session IDs."""
        session1 = session_manager.create_session(profile="default")
        session2 = session_manager.create_session(profile="default")

        assert session1.id != session2.id
        assert len(session1.id) > 0
        assert len(session2.id) > 0

    def test_create_session_sets_profile(self, session_manager: SessionManager) -> None:
        """Test create_session sets the correct profile."""
        session = session_manager.create_session(profile="test-profile")
        assert session.profile == "test-profile"

    def test_create_session_with_context(self, session_manager: SessionManager) -> None:
        """Test create_session stores context data."""
        context = {"user_id": "123", "environment": "test"}
        session = session_manager.create_session(profile="default", context=context)

        assert session.context == context
        assert session.context["user_id"] == "123"

    def test_create_session_without_context(self, session_manager: SessionManager) -> None:
        """Test create_session with no context creates empty dict."""
        session = session_manager.create_session(profile="default")
        assert session.context == {}

    def test_create_session_sets_timestamps(self, session_manager: SessionManager) -> None:
        """Test create_session sets created_at and updated_at."""
        before = datetime.now(UTC)
        session = session_manager.create_session(profile="default")
        after = datetime.now(UTC)

        assert before <= session.created_at <= after
        assert before <= session.updated_at <= after
        # Timestamps should be very close (within 1 second)
        time_diff = abs((session.updated_at - session.created_at).total_seconds())
        assert time_diff < 1.0

    def test_create_session_initializes_message_count(self, session_manager: SessionManager) -> None:
        """Test create_session sets message_count to 0."""
        session = session_manager.create_session(profile="default")
        assert session.message_count == 0

    def test_create_session_persists_to_storage(self, session_manager: SessionManager) -> None:
        """Test create_session saves session to storage immediately."""
        session = session_manager.create_session(profile="default")
        assert exists(session.id, category="sessions")

    def test_resume_session_loads_existing(self, session_manager: SessionManager, sample_session: Session) -> None:
        """Test resume_session loads an existing session."""
        resumed = session_manager.resume_session(sample_session.id)

        assert resumed.id == sample_session.id
        assert resumed.profile == sample_session.profile
        assert resumed.context == sample_session.context

    def test_resume_session_raises_for_nonexistent(self, session_manager: SessionManager) -> None:
        """Test resume_session raises FileNotFoundError for nonexistent session."""
        with pytest.raises(FileNotFoundError, match="Session .* not found"):
            session_manager.resume_session("nonexistent-session-id")

    def test_list_sessions_returns_all(self, session_manager: SessionManager) -> None:
        """Test list_sessions returns all created sessions."""
        session1 = session_manager.create_session(profile="profile1")
        session2 = session_manager.create_session(profile="profile2")

        sessions = session_manager.list_sessions()

        assert len(sessions) >= 2
        ids = [s.id for s in sessions]
        assert session1.id in ids
        assert session2.id in ids

    def test_list_sessions_sorted_by_updated_at(self, session_manager: SessionManager) -> None:
        """Test list_sessions returns sessions sorted by updated_at (newest first)."""
        session1 = session_manager.create_session(profile="first")
        session2 = session_manager.create_session(profile="second")

        sessions = session_manager.list_sessions()

        # Find our sessions in the list
        s1 = next(s for s in sessions if s.id == session1.id)
        s2 = next(s for s in sessions if s.id == session2.id)

        # Second session should come before first (newer)
        s1_index = sessions.index(s1)
        s2_index = sessions.index(s2)
        assert s2_index < s1_index

    def test_list_sessions_returns_session_info(self, session_manager: SessionManager, sample_session: Session) -> None:
        """Test list_sessions returns SessionInfo objects with correct data."""
        sessions = session_manager.list_sessions()

        # Find our sample session
        info = next(s for s in sessions if s.id == sample_session.id)

        assert isinstance(info, SessionInfo)
        assert info.id == sample_session.id
        assert info.profile == sample_session.profile
        assert info.message_count == 0

    def test_get_session_info_returns_metadata(self, session_manager: SessionManager, sample_session: Session) -> None:
        """Test get_session_info returns session metadata."""
        info = session_manager.get_session_info(sample_session.id)

        assert info is not None
        assert info.id == sample_session.id
        assert info.profile == sample_session.profile
        assert info.message_count == 0

    def test_get_session_info_returns_none_for_nonexistent(self, session_manager: SessionManager) -> None:
        """Test get_session_info returns None for nonexistent session."""
        info = session_manager.get_session_info("nonexistent-id")
        assert info is None

    def test_delete_session_removes_from_storage(
        self, session_manager: SessionManager, sample_session: Session
    ) -> None:
        """Test delete_session removes session from storage."""
        assert exists(sample_session.id, category="sessions")

        session_manager.delete_session(sample_session.id)

        assert not exists(sample_session.id, category="sessions")

    def test_delete_nonexistent_session_raises_error(self, session_manager: SessionManager) -> None:
        """Test delete_session raises FileNotFoundError for nonexistent session."""
        with pytest.raises(FileNotFoundError):
            session_manager.delete_session("nonexistent-id")

    def test_save_session_updates_timestamp(self, session_manager: SessionManager, sample_session: Session) -> None:
        """Test save_session updates the updated_at timestamp."""
        original_updated = sample_session.updated_at

        # Modify and save
        sample_session.context["new_key"] = "new_value"
        session_manager.save_session(sample_session)

        # Reload and verify
        reloaded = session_manager.resume_session(sample_session.id)
        assert reloaded.updated_at > original_updated
        assert reloaded.context["new_key"] == "new_value"

    def test_save_session_preserves_data(self, session_manager: SessionManager) -> None:
        """Test save_session preserves all session data correctly."""
        session = session_manager.create_session(profile="test-profile", context={"key1": "value1"})

        # Modify session
        session.context["key2"] = "value2"
        session.message_count = 5
        session_manager.save_session(session)

        # Reload and verify
        reloaded = session_manager.resume_session(session.id)
        assert reloaded.profile == "test-profile"
        assert reloaded.context["key1"] == "value1"
        assert reloaded.context["key2"] == "value2"
        assert reloaded.message_count == 5

    def test_session_lifecycle(self, session_manager: SessionManager) -> None:
        """Test complete session lifecycle: create, modify, resume, delete."""
        # Create
        session = session_manager.create_session(profile="lifecycle-test")
        session_id = session.id

        # Verify exists
        assert exists(session_id, category="sessions")

        # Modify
        session.context["step"] = 1
        session_manager.save_session(session)

        # Resume
        resumed = session_manager.resume_session(session_id)
        assert resumed.context["step"] == 1

        # Delete
        session_manager.delete_session(session_id)
        assert not exists(session_id, category="sessions")
