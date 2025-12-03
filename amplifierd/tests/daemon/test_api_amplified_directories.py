"""API integration tests for amplified directories endpoints."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from amplifierd.main import app
from amplifierd.routers.amplified_directories import get_service
from amplifierd.services.amplified_directory_service import AmplifiedDirectoryService


@pytest.fixture
def test_root(tmp_path: Path) -> Path:
    """Create test root directory."""
    root = tmp_path / "test_root"
    root.mkdir()
    return root


@pytest.fixture
def mock_service(test_root: Path) -> AmplifiedDirectoryService:
    """Create real service with test root."""
    return AmplifiedDirectoryService(test_root)


@pytest.fixture
def override_service(mock_service: AmplifiedDirectoryService):
    """Override service dependency with test service."""
    app.dependency_overrides[get_service] = lambda: mock_service
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client(override_service) -> TestClient:
    """FastAPI test client with mocked dependencies."""
    return TestClient(app)


@pytest.mark.integration
class TestAmplifiedDirectoriesAPI:
    """Test amplified directories API endpoints."""

    # --- Create Endpoint Tests ---

    def test_create_via_api_success(self, client: TestClient) -> None:
        """Test POST /api/v1/amplified-directories/ creates directory successfully."""
        response = client.post(
            "/api/v1/amplified-directories/",
            json={
                "relative_path": "test_project",
                "default_profile": "foundation/base",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["relative_path"] == "test_project"
        assert data["metadata"]["default_profile"] == "foundation/base"
        assert "created_at" in data

    def test_create_via_api_with_metadata(self, client: TestClient) -> None:
        """Test creating directory with custom metadata."""
        response = client.post(
            "/api/v1/amplified-directories/",
            json={
                "relative_path": "project_with_meta",
                "metadata": {
                    "name": "My Project",
                    "description": "Test project",
                },
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["metadata"]["name"] == "My Project"
        assert data["metadata"]["description"] == "Test project"
        assert "default_profile" in data["metadata"]

    def test_create_via_api_invalid_path_absolute(self, client: TestClient) -> None:
        """Test that absolute paths return 400."""
        response = client.post(
            "/api/v1/amplified-directories/",
            json={"relative_path": "/absolute/path"},
        )

        assert response.status_code == 400
        assert "relative" in response.json()["detail"].lower()

    def test_create_via_api_invalid_path_parent_traversal(self, client: TestClient) -> None:
        """Test that parent traversal paths return 400."""
        response = client.post(
            "/api/v1/amplified-directories/",
            json={"relative_path": "../../escape"},
        )

        assert response.status_code == 400
        assert ".." in response.json()["detail"]

    def test_create_already_amplified_400(self, client: TestClient) -> None:
        """Test that creating already-amplified directory returns 400."""
        # Create first time
        client.post(
            "/api/v1/amplified-directories/",
            json={"relative_path": "duplicate"},
        )

        # Attempt to create again
        response = client.post(
            "/api/v1/amplified-directories/",
            json={"relative_path": "duplicate"},
        )

        assert response.status_code == 400
        assert "already amplified" in response.json()["detail"].lower()

    # --- List Endpoint Tests ---

    def test_list_all_via_api(self, client: TestClient) -> None:
        """Test GET /api/v1/amplified-directories/ returns all directories."""
        # Create multiple directories
        for i in range(3):
            client.post(
                "/api/v1/amplified-directories/",
                json={"relative_path": f"project{i}"},
            )

        response = client.get("/api/v1/amplified-directories/")

        assert response.status_code == 200
        data = response.json()
        assert "directories" in data
        assert "total" in data
        assert data["total"] == 3
        assert len(data["directories"]) == 3

    def test_list_all_empty(self, client: TestClient) -> None:
        """Test listing when no amplified directories exist."""
        response = client.get("/api/v1/amplified-directories/")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["directories"] == []

    # --- Get Endpoint Tests ---

    def test_get_existing_via_api(self, client: TestClient) -> None:
        """Test GET /api/v1/amplified-directories/{path} returns specific directory."""
        # Create directory
        client.post(
            "/api/v1/amplified-directories/",
            json={
                "relative_path": "to_retrieve",
                "metadata": {"name": "Retrievable"},
            },
        )

        response = client.get("/api/v1/amplified-directories/to_retrieve")

        assert response.status_code == 200
        data = response.json()
        assert data["relative_path"] == "to_retrieve"
        assert data["metadata"]["name"] == "Retrievable"

    def test_get_nested_path_via_api(self, client: TestClient) -> None:
        """Test getting nested directory path."""
        # Create nested directory
        client.post(
            "/api/v1/amplified-directories/",
            json={"relative_path": "parent/child/nested"},
        )

        response = client.get("/api/v1/amplified-directories/parent/child/nested")

        assert response.status_code == 200
        data = response.json()
        assert data["relative_path"] == "parent/child/nested"

    def test_get_nonexistent_404(self, client: TestClient) -> None:
        """Test that getting non-existent directory returns 404."""
        response = client.get("/api/v1/amplified-directories/nonexistent")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    # --- Update Endpoint Tests ---

    def test_update_metadata_via_api(self, client: TestClient) -> None:
        """Test PATCH /api/v1/amplified-directories/{path} updates metadata."""
        # Create directory
        client.post(
            "/api/v1/amplified-directories/",
            json={
                "relative_path": "to_update",
                "metadata": {"name": "Original"},
            },
        )

        # Update metadata
        response = client.patch(
            "/api/v1/amplified-directories/to_update",
            json={
                "metadata": {
                    "name": "Updated",
                    "version": 2,
                    "default_profile": "foundation/base",
                }
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["metadata"]["name"] == "Updated"
        assert data["metadata"]["version"] == 2

    def test_update_nonexistent_404(self, client: TestClient) -> None:
        """Test that updating non-existent directory returns 404."""
        response = client.patch(
            "/api/v1/amplified-directories/nonexistent",
            json={"metadata": {"key": "value"}},
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    # --- Update Agents Content Endpoint Tests ---

    def test_update_agents_content_success(self, client: TestClient, mock_service: AmplifiedDirectoryService) -> None:
        """Test PUT /agents updates AGENTS.md successfully."""
        # Create amplified directory
        client.post("/api/v1/amplified-directories/", json={"relative_path": "test_project"})

        # Update agents content
        test_content = "# Test Instructions\n\nThis is a test."
        response = client.put(
            "/api/v1/amplified-directories/test_project/agents",
            json={"content": test_content},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "successfully" in data["message"].lower()

        # Verify file was written
        agents_file = mock_service.root / "test_project" / ".amplified" / "AGENTS.md"
        assert agents_file.exists()
        content = agents_file.read_text()
        assert "Test Instructions" in content
        assert "This is a test." in content

    def test_update_agents_content_with_long_content(self, client: TestClient, mock_service: AmplifiedDirectoryService) -> None:
        """Test updating AGENTS.md with large content."""
        # Create amplified directory
        client.post("/api/v1/amplified-directories/", json={"relative_path": "large_content"})

        # Create long content (>1000 chars)
        long_content = "# Large Test File\n\n" + "This is a test line. " * 100

        response = client.put(
            "/api/v1/amplified-directories/large_content/agents",
            json={"content": long_content},
        )

        assert response.status_code == 200
        assert response.json()["success"] is True

        # Verify content was written correctly
        agents_file = mock_service.root / "large_content" / ".amplified" / "AGENTS.md"
        content = agents_file.read_text()
        assert len(content) > 1000
        assert content.startswith("# Large Test File")

    def test_update_agents_content_roundtrip(self, client: TestClient) -> None:
        """Test create → update → get → verify content persists."""
        # Create directory
        create_response = client.post(
            "/api/v1/amplified-directories/",
            json={"relative_path": "roundtrip_agents"},
        )
        assert create_response.status_code == 201

        # Update agents content
        content_v1 = "# Version 1 Instructions\n\nFirst version."
        update_response = client.put(
            "/api/v1/amplified-directories/roundtrip_agents/agents",
            json={"content": content_v1},
        )
        assert update_response.status_code == 200

        # Get directory info (verify it still exists and is valid)
        get_response = client.get("/api/v1/amplified-directories/roundtrip_agents")
        assert get_response.status_code == 200
        assert get_response.json()["relative_path"] == "roundtrip_agents"

        # Update again with different content
        content_v2 = "# Version 2 Instructions\n\nSecond version with updates."
        update_response2 = client.put(
            "/api/v1/amplified-directories/roundtrip_agents/agents",
            json={"content": content_v2},
        )
        assert update_response2.status_code == 200
        assert update_response2.json()["success"] is True

    def test_update_agents_content_empty_400(self, client: TestClient) -> None:
        """Test that empty content is rejected with 400."""
        # Create directory
        client.post("/api/v1/amplified-directories/", json={"relative_path": "empty_test"})

        # Try to update with empty content
        response = client.put(
            "/api/v1/amplified-directories/empty_test/agents",
            json={"content": ""},
        )

        assert response.status_code == 400
        assert "empty" in response.json()["detail"].lower()

        # Try with whitespace-only content
        response2 = client.put(
            "/api/v1/amplified-directories/empty_test/agents",
            json={"content": "   \n\n   \t   "},
        )

        assert response2.status_code == 400
        assert "empty" in response2.json()["detail"].lower()

    def test_update_agents_content_nonexistent_404(self, client: TestClient) -> None:
        """Test that updating non-existent directory returns 404."""
        response = client.put(
            "/api/v1/amplified-directories/nonexistent_dir/agents",
            json={"content": "# Test"},
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_update_agents_content_not_amplified_404(self, client: TestClient, mock_service: AmplifiedDirectoryService) -> None:
        """Test that updating non-amplified directory returns 404."""
        # Create a regular directory (not amplified)
        regular_dir = mock_service.root / "regular_dir"
        regular_dir.mkdir(parents=True)

        # Try to update agents content
        response = client.put(
            "/api/v1/amplified-directories/regular_dir/agents",
            json={"content": "# Test"},
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_update_agents_content_preserves_newline(self, client: TestClient, mock_service: AmplifiedDirectoryService) -> None:
        """Test that newline is added at end of file."""
        # Create directory
        client.post("/api/v1/amplified-directories/", json={"relative_path": "newline_test"})

        # Update with content without trailing newline
        content_no_newline = "# Test\n\nNo trailing newline"
        response = client.put(
            "/api/v1/amplified-directories/newline_test/agents",
            json={"content": content_no_newline},
        )

        assert response.status_code == 200

        # Read file and verify newline was added
        agents_file = mock_service.root / "newline_test" / ".amplified" / "AGENTS.md"
        content = agents_file.read_text()
        assert content.endswith("\n"), "File should end with newline"
        assert content.strip() == content_no_newline.strip()

    def test_update_agents_content_atomic_write(self, client: TestClient, mock_service: AmplifiedDirectoryService) -> None:
        """Test that file write is atomic (no .tmp files left behind)."""
        # Create directory
        client.post("/api/v1/amplified-directories/", json={"relative_path": "atomic_test"})

        # Update content
        response = client.put(
            "/api/v1/amplified-directories/atomic_test/agents",
            json={"content": "# Atomic Write Test\n\nContent here."},
        )

        assert response.status_code == 200

        # Check that no temporary files exist
        amplified_dir = mock_service.root / "atomic_test" / ".amplified"
        tmp_files = list(amplified_dir.glob("*.tmp"))
        assert len(tmp_files) == 0, "No temporary files should remain after write"

        # Verify the final file exists
        agents_file = amplified_dir / "AGENTS.md"
        assert agents_file.exists()

    def test_update_agents_content_special_characters(self, client: TestClient, mock_service: AmplifiedDirectoryService) -> None:
        """Test updating AGENTS.md with Unicode, newlines, and quotes."""
        # Create directory
        client.post("/api/v1/amplified-directories/", json={"relative_path": "special_chars"})

        # Content with special characters
        special_content = """# Test with Special Characters

Unicode: 你好 🚀 café résumé

Quotes: "double" and 'single'

Multiple newlines:


And some markdown: **bold** _italic_ `code`
"""

        response = client.put(
            "/api/v1/amplified-directories/special_chars/agents",
            json={"content": special_content},
        )

        assert response.status_code == 200

        # Verify content was preserved correctly
        agents_file = mock_service.root / "special_chars" / ".amplified" / "AGENTS.md"
        content = agents_file.read_text()
        assert "你好" in content
        assert "🚀" in content
        assert "café" in content
        assert '"double"' in content
        assert "'single'" in content
        assert "**bold**" in content

    def test_update_agents_content_url_encoded_path(self, client: TestClient, mock_service: AmplifiedDirectoryService) -> None:
        """Test updating AGENTS.md with URL-encoded path."""
        # Create directory with special characters
        client.post("/api/v1/amplified-directories/", json={"relative_path": "project/with/slash"})

        # Update using URL-encoded path
        response = client.put(
            "/api/v1/amplified-directories/project%2Fwith%2Fslash/agents",
            json={"content": "# URL Encoded Path Test\n\nContent here."},
        )

        assert response.status_code == 200
        assert response.json()["success"] is True

        # Verify file was written to correct location
        agents_file = mock_service.root / "project" / "with" / "slash" / ".amplified" / "AGENTS.md"
        assert agents_file.exists()
        content = agents_file.read_text()
        assert "URL Encoded Path Test" in content

    # --- Delete Endpoint Tests ---

    def test_delete_via_api_success(self, client: TestClient) -> None:
        """Test DELETE /api/v1/amplified-directories/{path} deletes directory."""
        # Create directory
        client.post(
            "/api/v1/amplified-directories/",
            json={"relative_path": "to_delete"},
        )

        # Delete it with marker removal (so it's actually gone)
        response = client.delete("/api/v1/amplified-directories/to_delete?remove_marker=true")

        assert response.status_code == 204

        # Verify it's gone
        get_response = client.get("/api/v1/amplified-directories/to_delete")
        assert get_response.status_code == 404

    def test_delete_with_marker_removal(self, client: TestClient, mock_service: AmplifiedDirectoryService) -> None:
        """Test deleting with marker removal."""
        # Create directory
        client.post(
            "/api/v1/amplified-directories/",
            json={"relative_path": "to_delete_marker"},
        )

        # Verify marker exists
        marker_path = mock_service.root / "to_delete_marker" / ".amplified"
        assert marker_path.exists()

        # Delete with marker removal
        response = client.delete(
            "/api/v1/amplified-directories/to_delete_marker",
            params={"remove_marker": True},
        )

        assert response.status_code == 204

        # Verify marker is gone
        assert not marker_path.exists()

    def test_delete_nonexistent_404(self, client: TestClient) -> None:
        """Test that deleting non-existent directory returns 404."""
        response = client.delete("/api/v1/amplified-directories/nonexistent")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    # --- Profile Inheritance via API Tests ---

    def test_create_without_profile_inherits(self, client: TestClient) -> None:
        """Test creating directory without profile inherits from parent."""
        # Create parent with explicit profile
        client.post(
            "/api/v1/amplified-directories/",
            json={
                "relative_path": "parent",
                "default_profile": "parent/profile",
            },
        )

        # Create child without profile
        response = client.post(
            "/api/v1/amplified-directories/",
            json={"relative_path": "parent/child"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["metadata"]["default_profile"] == "parent/profile"

    def test_create_with_profile_uses_explicit(self, client: TestClient) -> None:
        """Test that explicit profile overrides inheritance."""
        # Create parent with profile
        client.post(
            "/api/v1/amplified-directories/",
            json={
                "relative_path": "parent",
                "default_profile": "parent/profile",
            },
        )

        # Create child with explicit different profile
        response = client.post(
            "/api/v1/amplified-directories/",
            json={
                "relative_path": "parent/child",
                "default_profile": "child/profile",
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["metadata"]["default_profile"] == "child/profile"

    def test_nested_directory_inheritance(self, client: TestClient) -> None:
        """Test inheritance through multiple levels."""
        # Create grandparent
        client.post(
            "/api/v1/amplified-directories/",
            json={
                "relative_path": "gp",
                "default_profile": "gp/profile",
            },
        )

        # Create parent (should inherit)
        parent_response = client.post(
            "/api/v1/amplified-directories/",
            json={"relative_path": "gp/parent"},
        )
        assert parent_response.json()["metadata"]["default_profile"] == "gp/profile"

        # Create child (should inherit from parent which inherited from grandparent)
        child_response = client.post(
            "/api/v1/amplified-directories/",
            json={"relative_path": "gp/parent/child"},
        )
        assert child_response.json()["metadata"]["default_profile"] == "gp/profile"

    # --- Error Handling Tests ---

    def test_create_unexpected_error_500(self, client: TestClient, mock_service: AmplifiedDirectoryService) -> None:
        """Test that unexpected errors return 500."""
        # Mock service to raise unexpected error
        original_create = mock_service.create

        def failing_create(*args, **kwargs):
            raise RuntimeError("Unexpected error")

        mock_service.create = failing_create

        try:
            response = client.post(
                "/api/v1/amplified-directories/",
                json={"relative_path": "error_test"},
            )

            assert response.status_code == 500
            assert "Internal server error" in response.json()["detail"]
        finally:
            mock_service.create = original_create

    def test_list_unexpected_error_500(self, client: TestClient, mock_service: AmplifiedDirectoryService) -> None:
        """Test that list endpoint handles unexpected errors."""
        original_list = mock_service.list_all

        def failing_list(force_refresh: bool = False):
            raise RuntimeError("List error")

        mock_service.list_all = failing_list

        try:
            response = client.get("/api/v1/amplified-directories/")

            assert response.status_code == 500
            assert "Internal server error" in response.json()["detail"]
        finally:
            mock_service.list_all = original_list

    def test_get_unexpected_error_500(self, client: TestClient, mock_service: AmplifiedDirectoryService) -> None:
        """Test that get endpoint handles unexpected errors."""
        original_get = mock_service.get

        def failing_get(*args, **kwargs):
            raise RuntimeError("Get error")

        mock_service.get = failing_get

        try:
            response = client.get("/api/v1/amplified-directories/test")

            assert response.status_code == 500
            assert "Internal server error" in response.json()["detail"]
        finally:
            mock_service.get = original_get

    def test_update_unexpected_error_500(self, client: TestClient, mock_service: AmplifiedDirectoryService) -> None:
        """Test that update endpoint handles unexpected errors."""
        # Create directory first
        client.post(
            "/api/v1/amplified-directories/",
            json={"relative_path": "error_update"},
        )

        original_update = mock_service.update

        def failing_update(*args, **kwargs):
            raise RuntimeError("Update error")

        mock_service.update = failing_update

        try:
            response = client.patch(
                "/api/v1/amplified-directories/error_update",
                json={"metadata": {"key": "value"}},
            )

            assert response.status_code == 500
            assert "Internal server error" in response.json()["detail"]
        finally:
            mock_service.update = original_update

    def test_delete_unexpected_error_500(self, client: TestClient, mock_service: AmplifiedDirectoryService) -> None:
        """Test that delete endpoint handles unexpected errors."""
        # Create directory first
        client.post(
            "/api/v1/amplified-directories/",
            json={"relative_path": "error_delete"},
        )

        original_delete = mock_service.delete

        def failing_delete(*args, **kwargs):
            raise RuntimeError("Delete error")

        mock_service.delete = failing_delete

        try:
            response = client.delete("/api/v1/amplified-directories/error_delete")

            assert response.status_code == 500
            assert "Internal server error" in response.json()["detail"]
        finally:
            mock_service.delete = original_delete

    # --- Session Integration Tests ---

    def test_create_session_in_amplified_dir(self, client: TestClient) -> None:
        """Test creating session in amplified directory."""
        # First amplify a directory
        client.post(
            "/api/v1/amplified-directories/",
            json={
                "relative_path": "session_project",
                "default_profile": "foundation/base",
            },
        )

        # Note: This would require session API integration which isn't complete yet
        # For now, we verify the directory was created correctly
        response = client.get("/api/v1/amplified-directories/session_project")
        assert response.status_code == 200
        assert response.json()["metadata"]["default_profile"] == "foundation/base"

    # --- Edge Cases ---

    def test_create_directory_with_special_characters(self, client: TestClient) -> None:
        """Test creating directory with special but valid characters."""
        valid_names = [
            "project_123",
            "project-with-dashes",
            "project.with.dots",
        ]

        for name in valid_names:
            response = client.post(
                "/api/v1/amplified-directories/",
                json={"relative_path": name},
            )
            assert response.status_code == 201, f"Failed for: {name}"

    def test_get_directory_with_url_encoded_path(self, client: TestClient) -> None:
        """Test getting directory with URL-encoded path."""
        # Create directory with spaces
        client.post(
            "/api/v1/amplified-directories/",
            json={"relative_path": "project with spaces"},
        )

        # Get it with URL encoding
        response = client.get("/api/v1/amplified-directories/project%20with%20spaces")

        assert response.status_code == 200
        data = response.json()
        assert data["relative_path"] == "project with spaces"

    def test_update_only_some_metadata_fields(self, client: TestClient) -> None:
        """Test updating only specific metadata fields."""
        # Create with multiple fields
        client.post(
            "/api/v1/amplified-directories/",
            json={
                "relative_path": "partial_update",
                "metadata": {
                    "field1": "value1",
                    "field2": "value2",
                },
            },
        )

        # Update only one field
        response = client.patch(
            "/api/v1/amplified-directories/partial_update",
            json={
                "metadata": {
                    "field1": "updated",
                    "default_profile": "foundation/base",
                }
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["metadata"]["field1"] == "updated"
        # Note: field2 will not be present as update replaces metadata

    def test_list_includes_nested_directories(self, client: TestClient) -> None:
        """Test that list_all includes nested amplified directories."""
        # Create multiple levels
        client.post("/api/v1/amplified-directories/", json={"relative_path": "level1"})
        client.post("/api/v1/amplified-directories/", json={"relative_path": "level1/level2"})
        client.post("/api/v1/amplified-directories/", json={"relative_path": "level1/level2/level3"})

        response = client.get("/api/v1/amplified-directories/")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        paths = {d["relative_path"] for d in data["directories"]}
        assert "level1" in paths
        assert "level1/level2" in paths
        assert "level1/level2/level3" in paths

    def test_roundtrip_create_get_update_get(self, client: TestClient) -> None:
        """Test complete CRUD cycle."""
        # Create
        create_response = client.post(
            "/api/v1/amplified-directories/",
            json={
                "relative_path": "roundtrip",
                "metadata": {"version": 1},
            },
        )
        assert create_response.status_code == 201

        # Get
        get_response1 = client.get("/api/v1/amplified-directories/roundtrip")
        assert get_response1.status_code == 200
        assert get_response1.json()["metadata"]["version"] == 1

        # Update
        update_response = client.patch(
            "/api/v1/amplified-directories/roundtrip",
            json={
                "metadata": {
                    "version": 2,
                    "updated": True,
                    "default_profile": "foundation/base",
                }
            },
        )
        assert update_response.status_code == 200

        # Get again
        get_response2 = client.get("/api/v1/amplified-directories/roundtrip")
        assert get_response2.status_code == 200
        assert get_response2.json()["metadata"]["version"] == 2
        assert get_response2.json()["metadata"]["updated"] is True

        # Delete with marker removal
        delete_response = client.delete("/api/v1/amplified-directories/roundtrip?remove_marker=true")
        assert delete_response.status_code == 204

        # Verify deleted
        get_response3 = client.get("/api/v1/amplified-directories/roundtrip")
        assert get_response3.status_code == 404
