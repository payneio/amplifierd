"""Collection discovery service using amplifier_collections library.

NOTE: This service requires amplifier_collections package from the amplifier-dev workspace.
The package is not included in standard dependencies as it's development-only.
Tests use mocking to avoid the dependency.
"""

from pathlib import Path

from amplifier_collections import CollectionResolver  # type: ignore[import-untyped]
from amplifier_collections import discover_collection_resources  # type: ignore[import-untyped]


def _get_collection_search_paths() -> list[Path]:
    """Get daemon-specific collection search paths.

    Returns:
        List of paths to search for collections
    """
    return [
        Path.cwd() / ".amplifier" / "collections",
        Path.home() / ".amplifier" / "collections",
    ]


class CollectionService:
    """Service for collection discovery operations."""

    def __init__(self: "CollectionService") -> None:
        """Initialize collection service."""
        self._resolver = CollectionResolver(search_paths=_get_collection_search_paths())

    async def list_collections(self: "CollectionService") -> list[dict[str, str]]:
        """List all available collections.

        Returns:
            List of collection info dictionaries with identifier, source, and type
        """
        collections = self._resolver.list_collections()
        result = []

        for metadata_name, collection_path in collections:
            # Determine type based on path
            collection_type = "local"
            if ".git" in str(collection_path):
                collection_type = "git"

            result.append(
                {
                    "identifier": metadata_name,
                    "source": str(collection_path),
                    "type": collection_type,
                }
            )

        return result

    async def get_collection(
        self: "CollectionService", identifier: str
    ) -> dict[str, str | list[str] | dict[str, list[str]]]:
        """Get collection details by identifier.

        Args:
            identifier: Collection identifier

        Returns:
            Collection details dictionary

        Raises:
            ValueError: If collection not found
        """
        collection_path = self._resolver.resolve_collection(identifier)  # type: ignore[attr-defined]
        if not collection_path:
            raise ValueError(f"Collection not found: {identifier}")

        # Discover resources in the collection
        resources = discover_collection_resources(collection_path)  # type: ignore[call-arg]

        # Determine type
        collection_type = "local"
        if ".git" in str(collection_path):
            collection_type = "git"

        return {
            "identifier": identifier,
            "source": str(collection_path),
            "type": collection_type,
            "profiles": [str(p) for p in resources.profiles],  # type: ignore[attr-defined]
            "agents": [str(a) for a in resources.agents],  # type: ignore[attr-defined]
            "modules": {
                "providers": [str(m) for m in resources.modules.get("providers", [])],  # type: ignore[union-attr]
                "tools": [str(m) for m in resources.modules.get("tools", [])],  # type: ignore[union-attr]
                "hooks": [str(m) for m in resources.modules.get("hooks", [])],  # type: ignore[union-attr]
                "orchestrators": [str(m) for m in resources.modules.get("orchestrators", [])],  # type: ignore[union-attr]
            },
        }

    async def mount_collection(self: "CollectionService", identifier: str, source: str) -> dict[str, str]:
        """Mount a collection by identifier and source.

        Args:
            identifier: Collection identifier (name or path)
            source: Collection source (git URL or local path)

        Returns:
            Dictionary with identifier, source, and mount status

        Raises:
            ValueError: If collection already mounted or source invalid
        """
        from amplifier_collections import CollectionLock  # type: ignore[import-untyped]

        lock_path = Path.home() / ".amplifier" / "collections.lock"
        lock = CollectionLock(lock_path=lock_path)

        # Check if already mounted
        if lock.get_entry(identifier):  # type: ignore[attr-defined]
            raise ValueError(f"Collection already mounted: {identifier}")

        # Add to lock (CollectionLock handles cloning/validation)
        try:
            lock.add_entry(identifier, source)  # type: ignore[attr-defined]
        except Exception as e:
            raise ValueError(f"Failed to mount collection: {str(e)}")

        return {
            "identifier": identifier,
            "source": source,
            "status": "mounted",
        }

    async def unmount_collection(self: "CollectionService", identifier: str) -> dict[str, bool]:
        """Unmount a collection by identifier.

        Args:
            identifier: Collection identifier

        Returns:
            Dictionary with unmounted status

        Raises:
            ValueError: If collection not found
        """
        from amplifier_collections import CollectionLock  # type: ignore[import-untyped]

        lock_path = Path.home() / ".amplifier" / "collections.lock"
        lock = CollectionLock(lock_path=lock_path)

        # Check if exists
        if not lock.get_entry(identifier):  # type: ignore[attr-defined]
            raise ValueError(f"Collection not found: {identifier}")

        # Remove from lock
        lock.remove_entry(identifier)  # type: ignore[attr-defined]

        return {"unmounted": True}
