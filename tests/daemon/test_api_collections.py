"""Integration tests for collection API endpoints."""

from typing import Any

import pytest
from fastapi.testclient import TestClient

from amplifierd.main import app
from amplifierd.routers.collections import get_collection_service


class MockCollectionService:
    """Mock CollectionService for testing."""

    async def list_collections(self) -> list[dict[str, Any]]:
        """List all collections."""
        return [
            {
                "identifier": "core",
                "source": "/path/to/core",
                "type": "local",
            },
            {
                "identifier": "github.com/org/repo",
                "source": "https://github.com/org/repo.git",
                "type": "git",
            },
        ]

    async def get_collection(self, identifier: str) -> dict[str, Any]:
        """Get collection by identifier."""
        if identifier == "core":
            return {
                "identifier": "core",
                "source": "/path/to/core",
                "type": "local",
                "profiles": ["default.yaml", "advanced.yaml"],
                "agents": ["helper.yaml", "reviewer.yaml"],
                "modules": {
                    "providers": ["openai.py", "anthropic.py"],
                    "tools": ["bash.py", "git.py", "search.py"],
                    "hooks": ["pre-commit.py"],
                    "orchestrators": ["parallel.py"],
                },
            }
        if identifier == "github.com/org/repo":
            return {
                "identifier": "github.com/org/repo",
                "source": "https://github.com/org/repo.git",
                "type": "git",
                "profiles": ["production.yaml"],
                "agents": [],
                "modules": {
                    "providers": [],
                    "tools": ["custom-tool.py"],
                    "hooks": [],
                    "orchestrators": [],
                },
            }
        raise ValueError(f"Collection not found: {identifier}")

    async def mount_collection(self, identifier: str, source: str) -> dict[str, Any]:
        """Mount a collection."""
        if identifier == "existing-collection":
            raise ValueError("Collection already mounted: existing-collection")
        if source == "invalid":
            raise ValueError("Invalid source")
        return {"identifier": identifier, "source": source, "status": "mounted"}

    async def unmount_collection(self, identifier: str) -> dict[str, Any]:
        """Unmount a collection."""
        if identifier == "core":
            return {"unmounted": True}
        raise ValueError(f"Collection not found: {identifier}")


@pytest.fixture
def override_collection_service():
    """Override CollectionService dependency with mock."""
    app.dependency_overrides[get_collection_service] = lambda: MockCollectionService()
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client(override_collection_service):
    """Create FastAPI test client with mocked dependencies."""
    return TestClient(app)


@pytest.mark.integration
class TestCollectionsAPI:
    """Test collection API endpoints."""

    def test_list_collections_returns_200(self, client: TestClient) -> None:
        """Test GET /api/v1/collections/ returns 200."""
        response = client.get("/api/v1/collections/")

        assert response.status_code == 200

    def test_list_collections_includes_collection_info(self, client: TestClient) -> None:
        """Test GET /api/v1/collections/ returns CollectionInfo objects."""
        response = client.get("/api/v1/collections/")

        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2

        core = next(c for c in data if c["identifier"] == "core")
        assert core["source"] == "/path/to/core"
        assert core["type"] == "local"

        git_repo = next(c for c in data if c["identifier"] == "github.com/org/repo")
        assert git_repo["source"] == "https://github.com/org/repo.git"
        assert git_repo["type"] == "git"

    def test_get_collection_returns_details(self, client: TestClient) -> None:
        """Test GET /api/v1/collections/{identifier} returns details."""
        response = client.get("/api/v1/collections/core")

        assert response.status_code == 200
        data = response.json()
        assert data["identifier"] == "core"
        assert data["source"] == "/path/to/core"
        assert data["type"] == "local"
        assert len(data["profiles"]) == 2
        assert "default.yaml" in data["profiles"]
        assert "advanced.yaml" in data["profiles"]
        assert len(data["agents"]) == 2
        assert "helper.yaml" in data["agents"]

    def test_get_collection_includes_modules(self, client: TestClient) -> None:
        """Test GET /api/v1/collections/{identifier} includes module listings."""
        response = client.get("/api/v1/collections/core")

        data = response.json()
        assert "modules" in data
        modules = data["modules"]
        assert "providers" in modules
        assert "tools" in modules
        assert "hooks" in modules
        assert "orchestrators" in modules
        assert len(modules["providers"]) == 2
        assert "openai.py" in modules["providers"]
        assert len(modules["tools"]) == 3
        assert "bash.py" in modules["tools"]
        assert len(modules["hooks"]) == 1
        assert len(modules["orchestrators"]) == 1

    def test_get_collection_git_type(self, client: TestClient) -> None:
        """Test GET /api/v1/collections/{identifier} for git collection."""
        response = client.get("/api/v1/collections/github.com%2Forg%2Frepo")

        assert response.status_code == 200
        data = response.json()
        assert data["identifier"] == "github.com/org/repo"
        assert data["type"] == "git"
        assert data["source"].startswith("https://")
        assert len(data["profiles"]) == 1
        assert len(data["agents"]) == 0

    def test_get_collection_404_for_nonexistent(self, client: TestClient) -> None:
        """Test GET /api/v1/collections/{identifier} returns 404."""
        response = client.get("/api/v1/collections/nonexistent")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_collection_info_schema(self, client: TestClient) -> None:
        """Test CollectionInfo objects have required fields."""
        response = client.get("/api/v1/collections/")

        data = response.json()
        for collection in data:
            assert "identifier" in collection
            assert "source" in collection
            assert "type" in collection
            assert isinstance(collection["identifier"], str)
            assert isinstance(collection["source"], str)
            assert isinstance(collection["type"], str)
            assert collection["type"] in ["local", "git"]

    def test_collection_details_schema(self, client: TestClient) -> None:
        """Test CollectionDetails objects have required fields."""
        response = client.get("/api/v1/collections/core")

        data = response.json()
        assert "identifier" in data
        assert "source" in data
        assert "type" in data
        assert "profiles" in data
        assert "agents" in data
        assert "modules" in data
        assert isinstance(data["profiles"], list)
        assert isinstance(data["agents"], list)
        assert isinstance(data["modules"], dict)

    def test_collection_modules_schema(self, client: TestClient) -> None:
        """Test CollectionModules objects have required fields."""
        response = client.get("/api/v1/collections/core")

        data = response.json()
        modules = data["modules"]
        assert "providers" in modules
        assert "tools" in modules
        assert "hooks" in modules
        assert "orchestrators" in modules
        assert isinstance(modules["providers"], list)
        assert isinstance(modules["tools"], list)
        assert isinstance(modules["hooks"], list)
        assert isinstance(modules["orchestrators"], list)

    def test_collection_with_empty_modules(self, client: TestClient) -> None:
        """Test collection with minimal modules."""
        response = client.get("/api/v1/collections/github.com%2Forg%2Frepo")

        data = response.json()
        modules = data["modules"]
        assert len(modules["providers"]) == 0
        assert len(modules["tools"]) == 1
        assert len(modules["hooks"]) == 0
        assert len(modules["orchestrators"]) == 0

    def test_mount_collection_success(self, client: TestClient) -> None:
        """Test POST /api/v1/collections/ mounts collection."""
        response = client.post(
            "/api/v1/collections/",
            json={"identifier": "new-collection", "source": "/path/to/new"},
        )

        assert response.status_code == 201
        data = response.json()
        assert data["identifier"] == "new-collection"
        assert data["source"] == "/path/to/new"
        assert data["status"] == "mounted"

    def test_mount_collection_already_exists(self, client: TestClient) -> None:
        """Test POST /api/v1/collections/ returns 409 for existing collection."""
        response = client.post(
            "/api/v1/collections/",
            json={"identifier": "existing-collection", "source": "/path/to/existing"},
        )

        assert response.status_code == 409
        assert "already mounted" in response.json()["detail"].lower()

    def test_mount_collection_invalid_source(self, client: TestClient) -> None:
        """Test POST /api/v1/collections/ returns 400 for invalid source."""
        response = client.post(
            "/api/v1/collections/",
            json={"identifier": "test-collection", "source": "invalid"},
        )

        assert response.status_code == 400
        assert "invalid source" in response.json()["detail"].lower()

    def test_unmount_collection_success(self, client: TestClient) -> None:
        """Test DELETE /api/v1/collections/{identifier} unmounts collection."""
        response = client.delete("/api/v1/collections/core")

        assert response.status_code == 200
        data = response.json()
        assert data["unmounted"] is True

    def test_unmount_collection_not_found(self, client: TestClient) -> None:
        """Test DELETE /api/v1/collections/{identifier} returns 404."""
        response = client.delete("/api/v1/collections/nonexistent")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
