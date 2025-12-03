"""Tests for reference resolution service."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from amplifierd.services.ref_resolution import RefResolutionError
from amplifierd.services.ref_resolution import RefResolutionService


@pytest.fixture
def temp_state_dir():
    """Create temporary state directory for testing."""
    with tempfile.TemporaryDirectory() as state_dir:
        yield Path(state_dir)


@pytest.fixture
def service(temp_state_dir: Path):
    """Create RefResolutionService instance."""
    return RefResolutionService(state_dir=temp_state_dir)


@pytest.fixture
def isolated_service(tmp_path: Path):
    """Create service with isolated cache directory per test."""
    state_dir = tmp_path / "state"
    state_dir.mkdir()

    service = RefResolutionService(state_dir=state_dir)

    service.fsspec_cache_dir = tmp_path / "fsspec_cache"
    service.fsspec_cache_dir.mkdir()

    return service


class TestCacheKeyGeneration:
    """Tests for _generate_cache_key method."""

    def test_file_url_normalization(self, service: RefResolutionService, tmp_path: Path):
        """Test that file:// URLs normalize to absolute paths."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test")

        # All these should produce the same hash
        file_url = f"file://{test_file}"
        absolute_path = str(test_file)

        hash1 = service._generate_cache_key(file_url)
        hash2 = service._generate_cache_key(absolute_path)

        assert hash1 == hash2, "file:// URL and absolute path should produce same hash"
        assert len(hash1) == 8, "Hash should be 8 characters"

    def test_relative_path_normalization(self, service: RefResolutionService):
        """Test that relative paths resolve to canonical form."""
        # Create a path that exists for resolution
        test_path = Path.cwd()

        # These should all resolve to the same absolute path
        absolute = str(test_path)
        with_dot = str(test_path / ".")

        hash1 = service._generate_cache_key(absolute)
        hash2 = service._generate_cache_key(with_dot)

        assert hash1 == hash2, "Equivalent paths should produce same hash"

    def test_http_default_port_normalization(self, service: RefResolutionService):
        """Test that default HTTP port :80 is normalized."""
        url_with_port = "http://example.com:80/path"
        url_without_port = "http://example.com/path"

        hash1 = service._generate_cache_key(url_with_port)
        hash2 = service._generate_cache_key(url_without_port)

        assert hash1 == hash2, "HTTP URLs with/without :80 should match"

    def test_https_default_port_normalization(self, service: RefResolutionService):
        """Test that default HTTPS port :443 is normalized."""
        url_with_port = "https://example.com:443/path"
        url_without_port = "https://example.com/path"

        hash1 = service._generate_cache_key(url_with_port)
        hash2 = service._generate_cache_key(url_without_port)

        assert hash1 == hash2, "HTTPS URLs with/without :443 should match"

    def test_trailing_slash_normalization(self, service: RefResolutionService):
        """Test that trailing slashes are normalized."""
        url_with_slash = "http://example.com/path/"
        url_without_slash = "http://example.com/path"

        hash1 = service._generate_cache_key(url_with_slash)
        hash2 = service._generate_cache_key(url_without_slash)

        assert hash1 == hash2, "URLs with/without trailing slash should match"

    def test_query_param_ordering(self, service: RefResolutionService):
        """Test that query parameters are sorted for consistent hashing."""
        url1 = "http://example.com/path?b=2&a=1"
        url2 = "http://example.com/path?a=1&b=2"

        hash1 = service._generate_cache_key(url1)
        hash2 = service._generate_cache_key(url2)

        assert hash1 == hash2, "URLs with reordered query params should match"

    def test_case_normalization(self, service: RefResolutionService):
        """Test that scheme and host are case-normalized."""
        url1 = "HTTP://EXAMPLE.COM/path"
        url2 = "http://example.com/path"

        hash1 = service._generate_cache_key(url1)
        hash2 = service._generate_cache_key(url2)

        assert hash1 == hash2, "URLs with different case should match"

    def test_different_urls_produce_different_hashes(self, service: RefResolutionService):
        """Test that different URLs produce different cache keys."""
        url1 = "http://site1.com/researcher.md"
        url2 = "http://site2.com/researcher.md"

        hash1 = service._generate_cache_key(url1)
        hash2 = service._generate_cache_key(url2)

        assert hash1 != hash2, "Different URLs should produce different hashes"

    def test_hash_is_deterministic(self, service: RefResolutionService):
        """Test that same URL always produces same hash."""
        url = "http://example.com/file.txt"

        hash1 = service._generate_cache_key(url)
        hash2 = service._generate_cache_key(url)
        hash3 = service._generate_cache_key(url)

        assert hash1 == hash2 == hash3, "Same URL should always produce same hash"


class TestFsspecCaching:
    """Tests for fsspec caching with hash-based structure."""

    @patch("fsspec.core.url_to_fs")
    def test_cache_miss_downloads_file(self, mock_url_to_fs, service: RefResolutionService):
        """Test that cache miss triggers download for single file."""
        # Mock fsspec filesystem
        mock_fs = MagicMock()
        mock_fs.protocol = "http"
        mock_fs.isdir.return_value = False
        mock_url_to_fs.return_value = (mock_fs, "/path/file.txt")

        # Mock successful download
        def mock_get_file(src, dest):
            Path(dest).parent.mkdir(parents=True, exist_ok=True)
            Path(dest).write_text("test content")

        mock_fs.get_file = mock_get_file

        # Resolve URL (should cache)
        result = service._resolve_fsspec("http://example.com/file.txt")

        # Verify cache structure
        assert result.exists()
        assert result.name == "file.txt"  # Preserves original filename
        assert result.parent.name != "http"  # Should use hash, not protocol
        assert len(result.parent.name) == 8  # 8-char hash
        assert result.read_text() == "test content"

    @patch("fsspec.core.url_to_fs")
    def test_cache_hit_returns_existing(self, mock_url_to_fs, isolated_service: RefResolutionService):
        """Test that cache hit returns existing content without downloading."""
        # Setup: Pre-populate cache with original filename
        cache_key = isolated_service._generate_cache_key("http://example.com/file.txt")
        cache_dir = isolated_service.fsspec_cache_dir / cache_key
        cache_dir.mkdir(parents=True, exist_ok=True)
        content_path = cache_dir / "file.txt"  # Use actual filename
        content_path.write_text("cached content")

        # Mock fsspec (should not be called due to cache hit)
        mock_fs = MagicMock()
        mock_fs.protocol = "http"
        mock_url_to_fs.return_value = (mock_fs, "/path/file.txt")

        # Resolve URL (should use cache)
        result = isolated_service._resolve_fsspec("http://example.com/file.txt")

        # Verify cache was used
        assert result == content_path
        assert result.read_text() == "cached content"
        mock_fs.get_file.assert_not_called()  # Should not download

    @patch("fsspec.core.url_to_fs")
    @patch("pathlib.Path.exists")
    def test_atomic_write_prevents_corruption(
        self, mock_exists, mock_url_to_fs, isolated_service: RefResolutionService
    ):
        """Test that interrupted downloads don't corrupt cache."""

        # Mock Path.exists to return False for the URL check (force remote resolution)
        def exists_side_effect(self):
            # Return False for initial path check to force fsspec resolution
            # Return actual existence for everything else
            if str(self).startswith("http://"):
                return False
            return Path.exists(self)

        mock_exists.side_effect = lambda: False

        # Mock fsspec filesystem that fails during download
        mock_fs = MagicMock()
        mock_fs.protocol = "http"
        mock_fs.isdir.return_value = False

        def mock_get_file_fails(src, dest):
            # Create temp file then fail
            Path(dest).parent.mkdir(parents=True, exist_ok=True)
            Path(dest).write_text("partial")
            raise RuntimeError("Download interrupted")

        mock_fs.get_file = mock_get_file_fails
        mock_url_to_fs.return_value = (mock_fs, "/path/file.txt")

        # Attempt download (should fail and clean up)
        with pytest.raises(RefResolutionError):
            isolated_service._resolve_fsspec("http://example.com/nonexistent-remote-file.txt")

        # Verify cleanup
        cache_key = isolated_service._generate_cache_key("http://example.com/nonexistent-remote-file.txt")
        cache_dir = isolated_service.fsspec_cache_dir / cache_key

        # Final file should not exist (atomic write prevents corruption)
        content_path = cache_dir / "nonexistent-remote-file.txt"
        assert not content_path.exists(), "final file should not exist after failed download"

        # .tmp should be cleaned up
        temp_path = cache_dir / ".tmp_nonexistent-remote-file.txt"
        assert not temp_path.exists(), ".tmp should be cleaned up after failure"

    @patch("fsspec.core.url_to_fs")
    def test_directory_download(self, mock_url_to_fs, service: RefResolutionService):
        """Test that directory downloads work correctly."""
        # Mock fsspec filesystem for directory
        mock_fs = MagicMock()
        mock_fs.protocol = "s3"
        mock_fs.isdir.return_value = True

        def mock_get_dir(src, dest, recursive):
            # Create directory structure
            dest_path = Path(dest)
            dest_path.mkdir(parents=True, exist_ok=True)
            (dest_path / "file1.txt").write_text("content1")
            (dest_path / "file2.txt").write_text("content2")

        mock_fs.get = mock_get_dir
        mock_url_to_fs.return_value = (mock_fs, "/bucket/folder")

        # Resolve directory URL
        result = service._resolve_fsspec("s3://bucket/folder")

        # Verify directory was cached
        assert result.exists()
        assert result.is_dir()
        assert (result / "file1.txt").exists()
        assert (result / "file2.txt").exists()
        assert (result / "file1.txt").read_text() == "content1"

    @patch("fsspec.core.url_to_fs")
    def test_same_filename_different_sources_no_collision(self, mock_url_to_fs, isolated_service: RefResolutionService):
        """Test that same filename from different sources don't collide."""
        # Setup two different sources with same filename
        url1 = "http://site1.com/researcher.md"
        url2 = "http://site2.com/researcher.md"

        # Generate cache keys
        key1 = isolated_service._generate_cache_key(url1)
        key2 = isolated_service._generate_cache_key(url2)

        # Verify different hashes
        assert key1 != key2, "Different source URLs should produce different cache keys"

        # Mock fsspec for both downloads
        mock_fs = MagicMock()
        mock_fs.protocol = "http"
        mock_fs.isdir.return_value = False

        # Track which URL we're currently resolving
        current_url: list[str | None] = [None]

        def mock_download(src, dest):
            Path(dest).parent.mkdir(parents=True, exist_ok=True)
            # Use the tracked URL to determine content
            if current_url[0] and "site1" in current_url[0]:
                Path(dest).write_text("content from site1")
            else:
                Path(dest).write_text("content from site2")

        mock_fs.get_file = mock_download

        # First download
        current_url[0] = url1
        mock_url_to_fs.return_value = (mock_fs, "/researcher.md")
        result1 = isolated_service._resolve_fsspec(url1)

        # Second download
        current_url[0] = url2
        result2 = isolated_service._resolve_fsspec(url2)

        # Verify both cached separately
        assert result1.read_text() == "content from site1"
        assert result2.read_text() == "content from site2"
        assert result1 != result2, "Should be cached in different locations"


class TestLocalPathHandling:
    """Tests for local path handling (bypass cache)."""

    def test_local_path_bypasses_cache(self, isolated_service: RefResolutionService, tmp_path: Path):
        """Test that existing local paths bypass caching."""
        # Create test file
        test_file = tmp_path / "local_file.txt"
        test_file.write_text("local content")

        # Resolve local path
        result = isolated_service._resolve_fsspec(str(test_file))

        # Should return resolved local path, not cache
        assert result == test_file.resolve()
        assert result.read_text() == "local content"

        # Verify no cache entry created
        cache_dirs = list(isolated_service.fsspec_cache_dir.iterdir())
        assert len(cache_dirs) == 0, "Local paths should not create cache entries"

    def test_file_protocol_short_circuits(self, service: RefResolutionService, tmp_path: Path):
        """Test that file:// protocol short-circuits to local path handling."""
        # Create test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        # Resolve via file:// URL
        file_url = f"file://{test_file}"

        with patch("fsspec.core.url_to_fs") as mock_url_to_fs:
            # Mock fsspec to return file protocol
            mock_fs = MagicMock()
            mock_fs.protocol = "file"
            mock_url_to_fs.return_value = (mock_fs, str(test_file))

            result = service._resolve_fsspec(file_url)

            # Should return local path without caching
            assert result == test_file
            assert result.read_text() == "content"


class TestErrorHandling:
    """Tests for error handling and cleanup."""

    @patch("fsspec.core.url_to_fs")
    @patch("pathlib.Path.exists")
    def test_download_failure_cleans_up_temp(self, mock_exists, mock_url_to_fs, isolated_service: RefResolutionService):
        """Test that failed downloads clean up temporary files."""
        # Mock Path.exists to return False for URL check (force remote resolution)
        mock_exists.side_effect = lambda: False

        # Mock filesystem that fails during download
        mock_fs = MagicMock()
        mock_fs.protocol = "http"
        mock_fs.isdir.return_value = False
        mock_fs.get_file.side_effect = RuntimeError("Network error")
        mock_url_to_fs.return_value = (mock_fs, "/file.txt")

        # Attempt download (should fail)
        with pytest.raises(RefResolutionError) as exc_info:
            isolated_service._resolve_fsspec("http://example.com/remote-file.txt")

        # Verify error message includes troubleshooting
        assert "Fsspec resolution failed" in str(exc_info.value)
        assert "Network error" in str(exc_info.value)

        # Verify no temp files left behind
        cache_key = isolated_service._generate_cache_key("http://example.com/remote-file.txt")
        cache_dir = isolated_service.fsspec_cache_dir / cache_key

        if cache_dir.exists():
            assert not (cache_dir / ".tmp_remote-file.txt").exists(), "Temp file should be cleaned up"
            assert not (cache_dir / "remote-file.txt").exists(), "Final file should not exist on failure"

    def test_nonexistent_local_path_raises_error(self, service: RefResolutionService):
        """Test that nonexistent local paths raise clear errors."""
        with pytest.raises(RefResolutionError) as exc_info:
            service.resolve_ref("/nonexistent/path/file.txt")

        assert "does not exist" in str(exc_info.value).lower()


class TestCacheStructure:
    """Tests for cache directory structure."""

    @patch("fsspec.core.url_to_fs")
    def test_cache_uses_hash_not_protocol(self, mock_url_to_fs, service: RefResolutionService):
        """Test that cache uses hash-based directories, not protocol names."""
        # Mock successful download
        mock_fs = MagicMock()
        mock_fs.protocol = "http"
        mock_fs.isdir.return_value = False

        def mock_download(src, dest):
            Path(dest).parent.mkdir(parents=True, exist_ok=True)
            Path(dest).write_text("test")

        mock_fs.get_file = mock_download
        mock_url_to_fs.return_value = (mock_fs, "/file.txt")

        # Download file
        result = service._resolve_fsspec("http://example.com/file.txt")

        # Verify cache structure
        assert result.parent.name != "http", "Should not use protocol as directory name"
        assert len(result.parent.name) == 8, "Should use 8-char hash as directory name"
        assert result.name == "file.txt", "Cached file should preserve original filename"

    @patch("fsspec.core.url_to_fs")
    def test_multiple_downloads_create_separate_caches(self, mock_url_to_fs, service: RefResolutionService):
        """Test that different URLs create separate cache entries."""
        # Mock filesystem
        mock_fs = MagicMock()
        mock_fs.protocol = "http"
        mock_fs.isdir.return_value = False

        call_count = 0

        def mock_download(src, dest):
            nonlocal call_count
            call_count += 1
            Path(dest).parent.mkdir(parents=True, exist_ok=True)
            Path(dest).write_text(f"content{call_count}")

        mock_fs.get_file = mock_download
        mock_url_to_fs.return_value = (mock_fs, "/file.txt")

        # Download multiple URLs
        result1 = service._resolve_fsspec("http://site1.com/file.txt")
        result2 = service._resolve_fsspec("http://site2.com/file.txt")

        # Verify separate cache entries
        assert result1 != result2, "Different URLs should cache separately"
        assert result1.read_text() == "content1"
        assert result2.read_text() == "content2"

        # Verify both are under fsspec cache
        assert result1.parent.parent == service.fsspec_cache_dir
        assert result2.parent.parent == service.fsspec_cache_dir


class TestAtomicWrites:
    """Tests for atomic write behavior."""

    @patch("fsspec.core.url_to_fs")
    def test_successful_download_renames_temp_to_content(self, mock_url_to_fs, isolated_service: RefResolutionService):
        """Test that successful downloads use atomic rename."""
        # Track filesystem operations
        operations = []

        mock_fs = MagicMock()
        mock_fs.protocol = "http"
        mock_fs.isdir.return_value = False

        def mock_download(src, dest):
            operations.append(("download", dest))
            Path(dest).parent.mkdir(parents=True, exist_ok=True)
            Path(dest).write_text("test")
            assert ".tmp_" in dest, "Should download to .tmp_<filename> file"

        mock_fs.get_file = mock_download
        mock_url_to_fs.return_value = (mock_fs, "/file.txt")

        # Download file
        result = isolated_service._resolve_fsspec("http://example.com/file.txt")

        # Verify .tmp_file.txt was used during download
        assert any(".tmp_file.txt" in str(op[1]) for op in operations)

        # Verify final result is 'file.txt' (not .tmp)
        assert result.name == "file.txt"
        assert not str(result).endswith(".tmp")

        # Verify .tmp file doesn't exist anymore
        temp_path = result.parent / ".tmp_file.txt"
        assert not temp_path.exists(), "Temp file should not exist after successful download"

    @patch("fsspec.core.url_to_fs")
    def test_cache_hit_does_not_redownload(self, mock_url_to_fs, isolated_service: RefResolutionService):
        """Test that cache hits don't trigger downloads."""
        # Pre-populate cache with original filename
        cache_key = isolated_service._generate_cache_key("http://example.com/file.txt")
        cache_dir = isolated_service.fsspec_cache_dir / cache_key
        cache_dir.mkdir(parents=True, exist_ok=True)
        content_path = cache_dir / "file.txt"  # Use actual filename
        content_path.write_text("cached")

        # Mock filesystem (should not be called)
        mock_fs = MagicMock()
        mock_fs.protocol = "http"
        mock_url_to_fs.return_value = (mock_fs, "/file.txt")

        # Resolve (should use cache)
        result = isolated_service._resolve_fsspec("http://example.com/file.txt")

        # Verify cache was used
        assert result == content_path
        assert result.read_text() == "cached"

        # Verify download was not attempted
        mock_fs.get_file.assert_not_called()
        mock_fs.get.assert_not_called()


class TestIntegration:
    """Integration tests using resolve_ref public API."""

    def test_resolve_absolute_path(self, service: RefResolutionService, tmp_path: Path):
        """Test resolving absolute paths via public API."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        result = service.resolve_ref(str(test_file))

        assert result == test_file
        assert result.read_text() == "content"

    @patch("fsspec.core.url_to_fs")
    def test_resolve_http_url(self, mock_url_to_fs, isolated_service: RefResolutionService):
        """Test resolving HTTP URLs via public API."""
        mock_fs = MagicMock()
        mock_fs.protocol = "http"
        mock_fs.isdir.return_value = False

        def mock_download(src, dest):
            Path(dest).parent.mkdir(parents=True, exist_ok=True)
            Path(dest).write_text("downloaded")

        mock_fs.get_file = mock_download
        mock_url_to_fs.return_value = (mock_fs, "/file.txt")

        result = isolated_service.resolve_ref("http://example.com/file.txt")

        assert result.exists()
        assert result.read_text() == "downloaded"
        assert result.name == "file.txt"  # Preserves original filename
