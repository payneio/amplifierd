"""Test enhanced RefResolutionService with git subpath support."""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock
from unittest.mock import Mock
from unittest.mock import patch

import pytest

from amplifierd.services.ref_resolution import RefResolutionError
from amplifierd.services.ref_resolution import RefResolutionService


@pytest.fixture
def ref_service(tmp_path: Path) -> RefResolutionService:
    """Create RefResolutionService for testing."""
    state_dir = tmp_path / "state"
    state_dir.mkdir(parents=True)
    return RefResolutionService(state_dir=state_dir)


@pytest.fixture
def isolated_ref_service(tmp_path: Path) -> RefResolutionService:
    """Create RefResolutionService with isolated cache directory per test."""
    state_dir = tmp_path / "state"
    state_dir.mkdir()

    service = RefResolutionService(state_dir=state_dir)

    service.fsspec_cache_dir = tmp_path / "fsspec_cache"
    service.fsspec_cache_dir.mkdir()

    return service


def test_resolve_git_ref_with_subpath(ref_service: RefResolutionService, tmp_path: Path) -> None:
    """Test resolving git ref with repo-relative path (after @ref/)."""
    # Mock _fetch_git to return a temporary repo path
    mock_repo_path = tmp_path / "mock_repo"
    mock_repo_path.mkdir()

    # Create mock asset at subpath
    agent_dir = mock_repo_path / "agents"
    agent_dir.mkdir()
    agent_file = agent_dir / "researcher.md"
    agent_file.write_text("# Researcher Agent")

    with patch.object(ref_service, "_fetch_git", return_value=mock_repo_path):
        # Test git ref with repo-relative path: git+URL@ref/path/to/file
        result = ref_service.resolve_ref("git+https://github.com/org/repo@main/agents/researcher.md")

        assert result == agent_file
        assert result.exists()


def test_resolve_git_ref_without_subpath(ref_service: RefResolutionService, tmp_path: Path) -> None:
    """Test resolving git ref without subpath (repo root)."""
    # Mock _fetch_git to return a temporary repo path
    mock_repo_path = tmp_path / "mock_repo"
    mock_repo_path.mkdir()

    # Create some content at repo root
    readme = mock_repo_path / "README.md"
    readme.write_text("# Test Repo")

    with patch.object(ref_service, "_fetch_git", return_value=mock_repo_path):
        # Test git ref without subpath
        result = ref_service.resolve_ref("git+https://github.com/org/repo@main")

        assert result == mock_repo_path
        assert result.exists()


def test_resolve_git_ref_missing_subpath(ref_service: RefResolutionService, tmp_path: Path) -> None:
    """Test resolving git ref with non-existent subpath."""
    # Mock _fetch_git to return a temporary repo path
    mock_repo_path = tmp_path / "mock_repo"
    mock_repo_path.mkdir()

    with (
        patch.object(ref_service, "_fetch_git", return_value=mock_repo_path),
        pytest.raises(RefResolutionError, match="Asset not found"),
    ):
        ref_service.resolve_ref("git+https://github.com/org/repo@main/missing/path.md")


def test_resolve_absolute_path(ref_service: RefResolutionService, tmp_path: Path) -> None:
    """Test resolving absolute path."""
    # Create test file
    test_file = tmp_path / "test.md"
    test_file.write_text("# Test")

    result = ref_service.resolve_ref(str(test_file))

    assert result == test_file
    assert result.exists()


def test_resolve_absolute_path_not_exists(ref_service: RefResolutionService, tmp_path: Path) -> None:
    """Test resolving non-existent absolute path."""
    missing_file = tmp_path / "missing.md"

    with pytest.raises(RefResolutionError, match="Absolute path does not exist"):
        ref_service.resolve_ref(str(missing_file))


def test_resolve_git_ref_with_subdirectory_syntax(ref_service: RefResolutionService, tmp_path: Path) -> None:
    """Test resolving git ref with #subdirectory= syntax."""
    # Mock _fetch_git to return subdirectory path
    mock_subdir_path = tmp_path / "subdirectory"
    mock_subdir_path.mkdir(parents=True)

    # Create test file in subdirectory
    test_file = mock_subdir_path / "test.md"
    test_file.write_text("# Test content")

    with patch.object(ref_service, "_fetch_git", return_value=mock_subdir_path):
        # Test with #subdirectory= syntax
        result = ref_service.resolve_ref("git+https://github.com/org/repo@main#subdirectory=packages/tools")

        assert result == mock_subdir_path
        assert result.exists()


def test_resolve_git_ref_missing_at_symbol(ref_service: RefResolutionService) -> None:
    """Test git ref without @ref fails with clear error."""
    with pytest.raises(RefResolutionError, match="Invalid git ref format.*missing @ref"):
        ref_service.resolve_ref("git+https://github.com/org/repo")


class TestHttpUrlResolution:
    """Tests for HTTP(S) URL resolution."""

    @patch("fsspec.core.url_to_fs")
    def test_resolve_http_url_downloads_and_caches(
        self, mock_url_to_fs: Mock, isolated_ref_service: RefResolutionService, tmp_path: Path
    ) -> None:
        """Test resolving HTTP URL downloads and caches content."""
        mock_fs = MagicMock()
        mock_fs.protocol = "http"
        mock_fs.isdir = MagicMock(return_value=False)

        def mock_download(src: str, dest: str) -> None:
            Path(dest).parent.mkdir(parents=True, exist_ok=True)
            Path(dest).write_text("downloaded content")

        mock_fs.get_file = mock_download
        mock_url_to_fs.return_value = (mock_fs, "/path/to/file.md")

        result = isolated_ref_service.resolve_ref("http://example.com/path/to/file.md")

        assert result.exists()
        assert result.name == "file.md"
        assert result.read_text() == "downloaded content"
        assert result.parent == isolated_ref_service.fsspec_cache_dir / "http"

    @patch("fsspec.core.url_to_fs")
    def test_resolve_https_url_downloads_and_caches(
        self, mock_url_to_fs: Mock, isolated_ref_service: RefResolutionService, tmp_path: Path
    ) -> None:
        """Test resolving HTTPS URL downloads and caches content."""
        mock_fs = MagicMock()
        mock_fs.protocol = "https"
        mock_fs.isdir = MagicMock(return_value=False)

        def mock_download(src: str, dest: str) -> None:
            Path(dest).parent.mkdir(parents=True, exist_ok=True)
            Path(dest).write_text("secure content")

        mock_fs.get_file = mock_download
        mock_url_to_fs.return_value = (mock_fs, "/secure/file.md")

        result = isolated_ref_service.resolve_ref("https://example.com/secure/file.md")

        assert result.exists()
        assert result.name == "file.md"
        assert result.read_text() == "secure content"

    @patch("fsspec.core.url_to_fs")
    def test_resolve_http_url_uses_cache_on_second_call(
        self, mock_url_to_fs: Mock, isolated_ref_service: RefResolutionService, tmp_path: Path
    ) -> None:
        """Test that subsequent calls use cached content without re-downloading."""
        mock_fs = MagicMock()
        mock_fs.protocol = "http"
        mock_fs.isdir = MagicMock(return_value=False)

        download_count = 0

        def mock_download(src: str, dest: str) -> None:
            nonlocal download_count
            download_count += 1
            Path(dest).parent.mkdir(parents=True, exist_ok=True)
            Path(dest).write_text(f"content_{download_count}")

        mock_fs.get_file = mock_download
        mock_url_to_fs.return_value = (mock_fs, "/file.md")

        result1 = isolated_ref_service.resolve_ref("http://example.com/file.md")
        result2 = isolated_ref_service.resolve_ref("http://example.com/file.md")

        assert result1 == result2
        assert result1.read_text() == "content_1"
        assert result2.read_text() == "content_1"
        assert download_count == 1

    @patch("fsspec.core.url_to_fs")
    def test_resolve_http_url_invalid_url_raises_error(
        self, mock_url_to_fs: Mock, isolated_ref_service: RefResolutionService
    ) -> None:
        """Test error handling for invalid HTTP URLs."""
        mock_url_to_fs.side_effect = ValueError("Invalid URL format")

        with pytest.raises(RefResolutionError, match="Failed to resolve HTTP URL"):
            isolated_ref_service.resolve_ref("http://invalid url with spaces.com/file.md")

    @patch("fsspec.core.url_to_fs")
    def test_resolve_http_url_network_error_raises_error(
        self, mock_url_to_fs: Mock, isolated_ref_service: RefResolutionService
    ) -> None:
        """Test error handling for network errors during download."""
        mock_fs = MagicMock()
        mock_fs.protocol = "http"
        mock_fs.isdir = MagicMock(return_value=False)
        mock_fs.get_file.side_effect = RuntimeError("Network timeout")

        mock_url_to_fs.return_value = (mock_fs, "/file.md")

        with pytest.raises(RefResolutionError, match="Failed to resolve HTTP URL"):
            isolated_ref_service.resolve_ref("http://example.com/file.md")

    @patch("fsspec.core.url_to_fs")
    def test_resolve_http_url_preserves_filename(
        self, mock_url_to_fs: Mock, isolated_ref_service: RefResolutionService, tmp_path: Path
    ) -> None:
        """Test that cached HTTP content preserves original filename."""
        mock_fs = MagicMock()
        mock_fs.protocol = "http"
        mock_fs.isdir = MagicMock(return_value=False)

        def mock_download(src: str, dest: str) -> None:
            Path(dest).parent.mkdir(parents=True, exist_ok=True)
            Path(dest).write_text("content")

        mock_fs.get_file = mock_download
        mock_url_to_fs.return_value = (mock_fs, "/path/to/complex_filename.v2.md")

        result = isolated_ref_service.resolve_ref("http://example.com/path/to/complex_filename.v2.md")

        assert result.name == "complex_filename.v2.md"
        assert result.exists()

    @patch("fsspec.core.url_to_fs")
    def test_resolve_http_url_atomic_write_prevents_corruption(
        self, mock_url_to_fs: Mock, isolated_ref_service: RefResolutionService, tmp_path: Path
    ) -> None:
        """Test that interrupted downloads don't corrupt cache."""
        mock_fs = MagicMock()
        mock_fs.protocol = "http"
        mock_fs.isdir = MagicMock(return_value=False)

        def mock_download_fails(src: str, dest: str) -> None:
            Path(dest).parent.mkdir(parents=True, exist_ok=True)
            Path(dest).write_text("partial content")
            raise RuntimeError("Download interrupted")

        mock_fs.get_file = mock_download_fails
        mock_url_to_fs.return_value = (mock_fs, "/file.md")

        with pytest.raises(RefResolutionError):
            isolated_ref_service.resolve_ref("http://example.com/file.md")

        cache_dir = isolated_ref_service.fsspec_cache_dir / "http"
        content_path = cache_dir / "file.md"

        assert not content_path.exists()

    @patch("fsspec.core.url_to_fs")
    def test_resolve_http_url_same_filename_uses_cache(
        self, mock_url_to_fs: Mock, isolated_ref_service: RefResolutionService, tmp_path: Path
    ) -> None:
        """Test that same filename from different sources uses cache (current limitation).

        NOTE: Current implementation caches by filename only, not by full URL.
        This means files with the same name from different sources will collide.
        This is a known limitation that should be addressed in a future improvement.
        """
        mock_fs = MagicMock()
        mock_fs.protocol = "http"
        mock_fs.isdir = MagicMock(return_value=False)

        download_count = 0

        def mock_download(src: str, dest: str) -> None:
            nonlocal download_count
            download_count += 1
            Path(dest).parent.mkdir(parents=True, exist_ok=True)
            Path(dest).write_text(f"content from download {download_count}")

        mock_fs.get_file = mock_download
        mock_url_to_fs.return_value = (mock_fs, "/file.md")

        result1 = isolated_ref_service.resolve_ref("http://site1.com/file.md")
        result2 = isolated_ref_service.resolve_ref("http://site2.com/file.md")

        assert result1 == result2
        assert result1.read_text() == "content from download 1"
        assert result2.read_text() == "content from download 1"
        assert download_count == 1

    def test_http_url_not_treated_as_local_path(
        self, isolated_ref_service: RefResolutionService, tmp_path: Path
    ) -> None:
        """Test that HTTP URLs are not treated as local filesystem paths."""
        with patch("fsspec.core.url_to_fs") as mock_url_to_fs:
            mock_fs = MagicMock()
            mock_fs.protocol = "http"
            mock_fs.isdir = MagicMock(return_value=False)

            def mock_download(src: str, dest: str) -> None:
                Path(dest).parent.mkdir(parents=True, exist_ok=True)
                Path(dest).write_text("downloaded via http")

            mock_fs.get_file = mock_download
            mock_url_to_fs.return_value = (mock_fs, "/file.md")

            result = isolated_ref_service.resolve_ref("https://example.com/file.md")

            assert result.exists()
            assert result.read_text() == "downloaded via http"

    @patch("fsspec.core.url_to_fs")
    def test_resolve_http_url_with_query_params(
        self, mock_url_to_fs: Mock, isolated_ref_service: RefResolutionService, tmp_path: Path
    ) -> None:
        """Test resolving HTTP URL with query parameters."""
        mock_fs = MagicMock()
        mock_fs.protocol = "http"
        mock_fs.isdir = MagicMock(return_value=False)

        def mock_download(src: str, dest: str) -> None:
            Path(dest).parent.mkdir(parents=True, exist_ok=True)
            Path(dest).write_text("content with params")

        mock_fs.get_file = mock_download
        mock_url_to_fs.return_value = (mock_fs, "/file.md")

        result = isolated_ref_service.resolve_ref("http://example.com/file.md?version=2&format=json")

        assert result.exists()
        assert result.name == "file.md"
        assert result.read_text() == "content with params"
