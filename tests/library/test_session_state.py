"""
Unit tests for session state management.

Tests message handling, context updates, and transcript operations.
"""

from datetime import UTC
from datetime import datetime

import pytest

from amplifier_library.models import Message
from amplifier_library.models import Session
from amplifier_library.sessions import state
from amplifier_library.storage.json_store import exists


@pytest.mark.unit
class TestSessionState:
    """Test session state management functions."""

    def test_add_message_creates_message(self, sample_session: Session) -> None:
        """Test add_message creates a Message object."""
        msg = state.add_message(sample_session, "user", "Hello, world!")

        assert isinstance(msg, Message)
        assert msg.role == "user"
        assert msg.content == "Hello, world!"
        assert msg.timestamp is not None

    def test_add_message_sets_timestamp(self, sample_session: Session) -> None:
        """Test add_message sets current timestamp."""
        before = datetime.now(UTC)
        msg = state.add_message(sample_session, "user", "Test")
        after = datetime.now(UTC)

        assert before <= msg.timestamp <= after

    def test_add_message_with_metadata(self, sample_session: Session) -> None:
        """Test add_message stores metadata."""
        metadata = {"model": "gpt-4", "temperature": 0.7}
        msg = state.add_message(sample_session, "assistant", "Response", metadata=metadata)

        assert msg.metadata == metadata
        assert msg.metadata["model"] == "gpt-4"

    def test_add_message_without_metadata(self, sample_session: Session) -> None:
        """Test add_message creates empty metadata dict when not provided."""
        msg = state.add_message(sample_session, "user", "Test")
        assert msg.metadata == {}

    def test_add_message_updates_message_count(self, sample_session: Session) -> None:
        """Test add_message updates session message count."""
        assert sample_session.message_count == 0

        state.add_message(sample_session, "user", "Message 1")
        assert sample_session.message_count == 1

        state.add_message(sample_session, "assistant", "Message 2")
        assert sample_session.message_count == 2

    def test_add_message_persists_transcript(self, sample_session: Session) -> None:
        """Test add_message saves transcript to storage."""
        state.add_message(sample_session, "user", "Test message")

        # Verify transcript file exists
        transcript_key = f"{sample_session.id}_transcript"
        assert exists(transcript_key, category="sessions")

    def test_add_multiple_messages(self, sample_session: Session) -> None:
        """Test adding multiple messages to session."""
        state.add_message(sample_session, "user", "Hello")
        state.add_message(sample_session, "assistant", "Hi there!")
        state.add_message(sample_session, "user", "How are you?")

        assert sample_session.message_count == 3

        transcript = state.get_transcript(sample_session.id)
        assert len(transcript) == 3
        assert transcript[0].content == "Hello"
        assert transcript[1].content == "Hi there!"
        assert transcript[2].content == "How are you?"

    def test_update_context_merges_updates(self, sample_session: Session) -> None:
        """Test update_context merges new values into existing context."""
        # Initial context from fixture
        assert sample_session.context.get("test_key") == "test_value"

        # Update with new values
        state.update_context(sample_session, {"new_key": "new_value"})

        # Both old and new keys should be present
        assert sample_session.context["test_key"] == "test_value"
        assert sample_session.context["new_key"] == "new_value"

    def test_update_context_overwrites_existing(self, sample_session: Session) -> None:
        """Test update_context overwrites existing keys."""
        sample_session.context["key"] = "old_value"

        state.update_context(sample_session, {"key": "new_value"})

        assert sample_session.context["key"] == "new_value"

    def test_update_context_with_nested_dict(self, sample_session: Session) -> None:
        """Test update_context handles nested dictionaries."""
        updates = {"settings": {"theme": "dark", "language": "en"}, "flags": ["feature_a", "feature_b"]}

        state.update_context(sample_session, updates)

        assert sample_session.context["settings"]["theme"] == "dark"
        assert "feature_a" in sample_session.context["flags"]

    def test_get_transcript_returns_messages(self, sample_session: Session) -> None:
        """Test get_transcript returns all messages in order."""
        state.add_message(sample_session, "user", "First")
        state.add_message(sample_session, "assistant", "Second")
        state.add_message(sample_session, "user", "Third")

        transcript = state.get_transcript(sample_session.id)

        assert len(transcript) == 3
        assert all(isinstance(msg, Message) for msg in transcript)
        assert transcript[0].content == "First"
        assert transcript[1].content == "Second"
        assert transcript[2].content == "Third"

    def test_get_transcript_empty_for_new_session(self, sample_session: Session) -> None:
        """Test get_transcript returns empty list for new session."""
        transcript = state.get_transcript(sample_session.id)
        assert transcript == []

    def test_get_transcript_raises_for_nonexistent_session(self, mock_storage_env) -> None:
        """Test get_transcript raises FileNotFoundError for nonexistent session."""
        with pytest.raises(FileNotFoundError, match="Session .* not found"):
            state.get_transcript("nonexistent-session-id")

    def test_get_transcript_preserves_metadata(self, sample_session: Session) -> None:
        """Test get_transcript preserves message metadata."""
        metadata = {"model": "gpt-4", "tokens": 150}
        state.add_message(sample_session, "assistant", "Response", metadata=metadata)

        transcript = state.get_transcript(sample_session.id)

        assert transcript[0].metadata == metadata
        assert transcript[0].metadata["model"] == "gpt-4"

    def test_get_transcript_preserves_timestamps(self, sample_session: Session) -> None:
        """Test get_transcript preserves message timestamps."""
        msg = state.add_message(sample_session, "user", "Test")
        original_timestamp = msg.timestamp

        transcript = state.get_transcript(sample_session.id)

        assert transcript[0].timestamp == original_timestamp

    def test_message_roles(self, sample_session: Session) -> None:
        """Test different message roles work correctly."""
        state.add_message(sample_session, "user", "User message")
        state.add_message(sample_session, "assistant", "Assistant message")
        state.add_message(sample_session, "system", "System message")

        transcript = state.get_transcript(sample_session.id)

        assert transcript[0].role == "user"
        assert transcript[1].role == "assistant"
        assert transcript[2].role == "system"

    def test_transcript_persistence_across_loads(self, sample_session: Session, session_manager) -> None:
        """Test transcript persists across session resume operations."""
        # Add messages
        state.add_message(sample_session, "user", "Hello")
        state.add_message(sample_session, "assistant", "Hi")

        # Resume session
        resumed = session_manager.resume_session(sample_session.id)

        # Get transcript from resumed session
        transcript = state.get_transcript(resumed.id)

        assert len(transcript) == 2
        assert transcript[0].content == "Hello"
        assert transcript[1].content == "Hi"
