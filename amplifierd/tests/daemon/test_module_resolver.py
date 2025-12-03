"""Tests for DaemonModuleSourceResolver."""

import pytest

from amplifierd.module_resolver import DaemonModuleSourceResolver
from amplifierd.module_resolver import ModuleSource


@pytest.fixture
def mock_share_dir(tmp_path):
    """Create mock share directory structure."""
    share_dir = tmp_path / "share"

    # Create profile structure
    profile_dir = share_dir / "profiles" / "foundation" / "base"
    profile_dir.mkdir(parents=True)

    # Create module directories
    (profile_dir / "orchestrator" / "loop-streaming").mkdir(parents=True)
    (profile_dir / "context" / "context-simple").mkdir(parents=True)
    (profile_dir / "providers" / "provider-anthropic").mkdir(parents=True)
    (profile_dir / "tools" / "tool-web").mkdir(parents=True)
    (profile_dir / "hooks" / "hook-logging").mkdir(parents=True)

    return share_dir


@pytest.mark.unit
class TestDaemonModuleSourceResolver:
    """Test DaemonModuleSourceResolver."""

    def test_resolver_initialization(self, mock_share_dir):
        """Test resolver initializes with share directory."""
        resolver = DaemonModuleSourceResolver(mock_share_dir)
        assert resolver.share_dir == mock_share_dir

    def test_resolve_orchestrator(self, mock_share_dir):
        """Test resolving orchestrator module."""
        resolver = DaemonModuleSourceResolver(mock_share_dir)
        profile_hint = {"collection": "foundation", "profile": "base"}

        source = resolver.resolve("loop-streaming", profile_hint)

        assert isinstance(source, ModuleSource)
        assert source.module_id == "loop-streaming"

        path = source.resolve()
        expected = mock_share_dir / "profiles" / "foundation" / "base" / "orchestrator" / "loop-streaming"
        assert path == expected
        assert path.exists()

    def test_resolve_context(self, mock_share_dir):
        """Test resolving context manager module."""
        resolver = DaemonModuleSourceResolver(mock_share_dir)
        profile_hint = {"collection": "foundation", "profile": "base"}

        source = resolver.resolve("context-simple", profile_hint)
        path = source.resolve()

        expected = mock_share_dir / "profiles" / "foundation" / "base" / "context" / "context-simple"
        assert path == expected

    def test_resolve_provider(self, mock_share_dir):
        """Test resolving provider module."""
        resolver = DaemonModuleSourceResolver(mock_share_dir)
        profile_hint = {"collection": "foundation", "profile": "base"}

        source = resolver.resolve("provider-anthropic", profile_hint)
        path = source.resolve()

        expected = mock_share_dir / "profiles" / "foundation" / "base" / "providers" / "provider-anthropic"
        assert path == expected

    def test_resolve_tool(self, mock_share_dir):
        """Test resolving tool module."""
        resolver = DaemonModuleSourceResolver(mock_share_dir)
        profile_hint = {"collection": "foundation", "profile": "base"}

        source = resolver.resolve("tool-web", profile_hint)
        path = source.resolve()

        expected = mock_share_dir / "profiles" / "foundation" / "base" / "tools" / "tool-web"
        assert path == expected

    def test_resolve_hook(self, mock_share_dir):
        """Test resolving hook module."""
        resolver = DaemonModuleSourceResolver(mock_share_dir)
        profile_hint = {"collection": "foundation", "profile": "base"}

        source = resolver.resolve("hook-logging", profile_hint)
        path = source.resolve()

        expected = mock_share_dir / "profiles" / "foundation" / "base" / "hooks" / "hook-logging"
        assert path == expected

    def test_resolve_with_string_profile_hint(self, mock_share_dir):
        """Test resolving with 'collection/profile' string hint."""
        resolver = DaemonModuleSourceResolver(mock_share_dir)

        source = resolver.resolve("provider-anthropic", "foundation/base")
        path = source.resolve()

        expected = mock_share_dir / "profiles" / "foundation" / "base" / "providers" / "provider-anthropic"
        assert path == expected

    def test_resolve_missing_profile_hint(self, mock_share_dir):
        """Test error when profile hint is missing."""
        resolver = DaemonModuleSourceResolver(mock_share_dir)

        with pytest.raises(ValueError, match="profile_hint must"):
            resolver.resolve("provider-anthropic", None)

    def test_resolve_invalid_profile_hint(self, mock_share_dir):
        """Test error when profile hint is invalid."""
        resolver = DaemonModuleSourceResolver(mock_share_dir)

        with pytest.raises(ValueError, match="profile_hint must"):
            resolver.resolve("provider-anthropic", {"collection": "foundation"})  # Missing profile

    def test_resolve_nonexistent_module(self, mock_share_dir):
        """Test error when module doesn't exist."""
        resolver = DaemonModuleSourceResolver(mock_share_dir)
        profile_hint = {"collection": "foundation", "profile": "base"}

        source = resolver.resolve("provider-nonexistent", profile_hint)

        with pytest.raises(FileNotFoundError, match="Module path not found"):
            source.resolve()

    def test_mount_type_guessing(self, mock_share_dir):
        """Test mount type detection from module IDs."""
        resolver = DaemonModuleSourceResolver(mock_share_dir)

        assert resolver._guess_mount_type("loop-streaming") == "orchestrator"
        assert resolver._guess_mount_type("loop-basic") == "orchestrator"
        assert resolver._guess_mount_type("context-simple") == "context"
        assert resolver._guess_mount_type("context-persistent") == "context"
        assert resolver._guess_mount_type("provider-anthropic") == "providers"
        assert resolver._guess_mount_type("provider-openai") == "providers"
        assert resolver._guess_mount_type("tool-web") == "tools"
        assert resolver._guess_mount_type("tool-search") == "tools"
        assert resolver._guess_mount_type("hook-logging") == "hooks"
        assert resolver._guess_mount_type("hook-redaction") == "hooks"
