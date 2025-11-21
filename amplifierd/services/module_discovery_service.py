"""Module discovery service using amplifier_module_resolution library.

NOTE: This service requires amplifier-dev workspace packages:
- amplifier_module_resolution
- amplifier_config
- amplifier_collections

These are not included in standard dependencies as they're development-only.
Tests use mocking to avoid the dependency.
"""

from pathlib import Path

from amplifier_collections import CollectionLock  # type: ignore[import-untyped]
from amplifier_config import ConfigManager  # type: ignore[import-untyped]
from amplifier_config import ConfigPaths  # type: ignore[import-untyped]
from amplifier_module_resolution import StandardModuleSourceResolver  # type: ignore[import-untyped]


def _get_config_paths() -> ConfigPaths:
    """Get daemon-specific configuration paths.

    Returns:
        ConfigPaths with daemon conventions
    """
    return ConfigPaths(
        user=Path.home() / ".amplifier" / "settings.yaml",
        project=Path(".amplifier") / "settings.yaml",
        local=Path(".amplifier") / "settings.local.yaml",
    )


def _get_workspace_dir() -> Path:
    """Get daemon-specific workspace directory for local modules.

    Returns:
        Path to workspace directory
    """
    return Path(".amplifier") / "modules"


class ModuleDiscoveryService:
    """Service for module discovery operations."""

    def __init__(self: "ModuleDiscoveryService") -> None:
        """Initialize module discovery service."""
        config = ConfigManager(paths=_get_config_paths())

        # Implement settings provider protocol
        class SettingsProvider:
            """Settings provider for module resolution."""

            def __init__(self: "SettingsProvider", config_manager: ConfigManager) -> None:
                """Initialize settings provider.

                Args:
                    config_manager: Config manager instance
                """
                self._config = config_manager

            def get_module_sources(self: "SettingsProvider") -> dict[str, str]:
                """Get all module sources from settings."""
                return self._config.get_module_sources()

            def get_module_source(self: "SettingsProvider", module_id: str) -> str | None:
                """Get module source from settings."""
                return self._config.get_module_sources().get(module_id)

        # Implement collection module provider protocol
        class CollectionModuleProvider:
            """Collection module provider for module resolution."""

            def get_collection_modules(self: "CollectionModuleProvider") -> dict[str, str]:
                """Get module_id -> absolute_path from installed collections."""
                lock_path = Path.home() / ".amplifier" / "collections.lock"
                if not lock_path.exists():
                    return {}

                lock = CollectionLock(lock_path=lock_path)
                modules = {}

                for entry in lock.list_entries():
                    for module_name, module_info in entry.modules.items():
                        collection_path = Path(entry.path)
                        module_path = collection_path / module_info["path"]
                        modules[module_name] = str(module_path)

                return modules

        self._resolver = StandardModuleSourceResolver(
            settings_provider=SettingsProvider(config),
            collection_provider=CollectionModuleProvider(),
            workspace_dir=_get_workspace_dir(),
        )

    async def list_all_modules(
        self: "ModuleDiscoveryService", type_filter: str | None = None
    ) -> list[dict[str, str | None]]:
        """List all modules with optional type filter.

        Args:
            type_filter: Optional module type filter (provider, hook, tool, orchestrator)

        Returns:
            List of module info dictionaries
        """
        all_modules = []

        # Get all module sources from resolver
        modules = self._resolver.list_all_modules()  # type: ignore[attr-defined]

        for module_id, module_path in modules.items():
            # Extract module type from module_id (e.g., "openai-provider" -> "provider")
            module_type = "unknown"
            if "-provider" in module_id or module_id.endswith("_provider"):
                module_type = "provider"
            elif "-hook" in module_id or module_id.endswith("_hook"):
                module_type = "hook"
            elif "-tool" in module_id or module_id.endswith("_tool"):
                module_type = "tool"
            elif "-orchestrator" in module_id or module_id.endswith("_orchestrator"):
                module_type = "orchestrator"

            # Apply filter if specified
            if type_filter and module_type != type_filter:
                continue

            # Determine collection if module is from collection
            collection = None
            if ".amplifier/collections/" in module_path:
                parts = module_path.split(".amplifier/collections/")
                if len(parts) > 1:
                    collection = parts[1].split("/")[0]

            all_modules.append(
                {
                    "id": module_id,
                    "type": module_type,
                    "name": module_id,
                    "location": module_path,
                    "collection": collection,
                }
            )

        return all_modules

    async def list_providers(self: "ModuleDiscoveryService") -> list[dict[str, str | None]]:
        """List provider modules.

        Returns:
            List of provider module info dictionaries
        """
        return await self.list_all_modules(type_filter="provider")

    async def list_hooks(self: "ModuleDiscoveryService") -> list[dict[str, str | None]]:
        """List hook modules.

        Returns:
            List of hook module info dictionaries
        """
        return await self.list_all_modules(type_filter="hook")

    async def list_tools(self: "ModuleDiscoveryService") -> list[dict[str, str | None]]:
        """List tool modules.

        Returns:
            List of tool module info dictionaries
        """
        return await self.list_all_modules(type_filter="tool")

    async def list_orchestrators(self: "ModuleDiscoveryService") -> list[dict[str, str | None]]:
        """List orchestrator modules.

        Returns:
            List of orchestrator module info dictionaries
        """
        return await self.list_all_modules(type_filter="orchestrator")

    async def get_module_details(
        self: "ModuleDiscoveryService", module_id: str
    ) -> dict[str, str | None | dict[str, object]]:
        """Get module details by ID.

        Args:
            module_id: Module identifier

        Returns:
            Module details dictionary

        Raises:
            ValueError: If module not found
        """
        module_path = self._resolver.resolve_module_source(module_id)  # type: ignore[attr-defined]
        if not module_path:
            raise ValueError(f"Module not found: {module_id}")

        # Extract module type
        module_type = "unknown"
        if "-provider" in module_id or module_id.endswith("_provider"):
            module_type = "provider"
        elif "-hook" in module_id or module_id.endswith("_hook"):
            module_type = "hook"
        elif "-tool" in module_id or module_id.endswith("_tool"):
            module_type = "tool"
        elif "-orchestrator" in module_id or module_id.endswith("_orchestrator"):
            module_type = "orchestrator"

        # Determine collection
        collection = None
        if ".amplifier/collections/" in module_path:
            parts = module_path.split(".amplifier/collections/")
            if len(parts) > 1:
                collection = parts[1].split("/")[0]

        return {
            "id": module_id,
            "type": module_type,
            "name": module_id,
            "location": module_path,
            "collection": collection,
            "description": None,  # Could be enhanced to read from module metadata
        }

    async def add_module_source(
        self: "ModuleDiscoveryService",
        module_id: str,
        source: str,
        scope: str = "project",
    ) -> dict[str, str]:
        """Add a module source override.

        Args:
            module_id: Module identifier
            source: Source path or URL
            scope: Configuration scope (user/project/local)

        Returns:
            Dictionary with module_id, source, and scope
        """
        from amplifier_config import ConfigManager  # type: ignore[import-untyped]
        from amplifier_config import Scope  # type: ignore[import-untyped]

        scope_enum = Scope[scope.upper()]
        config = ConfigManager(paths=_get_config_paths())
        config.add_source_override(module_id, source, scope_enum)  # type: ignore[attr-defined]

        return {
            "module_id": module_id,
            "source": source,
            "scope": scope,
        }

    async def remove_module_source(
        self: "ModuleDiscoveryService",
        module_id: str,
        scope: str = "project",
    ) -> dict[str, bool]:
        """Remove a module source override.

        Args:
            module_id: Module identifier
            scope: Configuration scope (user/project/local)

        Returns:
            Dictionary with removed status

        Raises:
            ValueError: If source override not found
        """
        from amplifier_config import ConfigManager  # type: ignore[import-untyped]
        from amplifier_config import Scope  # type: ignore[import-untyped]

        scope_enum = Scope[scope.upper()]
        config = ConfigManager(paths=_get_config_paths())
        removed = config.remove_source_override(module_id, scope_enum)  # type: ignore[attr-defined]

        if not removed:
            raise ValueError(f"Source override not found for {module_id}")

        return {"removed": True}

    async def update_module_source(
        self: "ModuleDiscoveryService",
        module_id: str,
        source: str,
        scope: str = "project",
    ) -> dict[str, str]:
        """Update a module source override.

        Args:
            module_id: Module identifier
            source: New source path or URL
            scope: Configuration scope (user/project/local)

        Returns:
            Dictionary with module_id, source, and scope
        """
        # Update is just remove + add
        from amplifier_config import ConfigManager  # type: ignore[import-untyped]
        from amplifier_config import Scope  # type: ignore[import-untyped]

        scope_enum = Scope[scope.upper()]
        config = ConfigManager(paths=_get_config_paths())

        # Remove if exists (ignore if not found)
        config.remove_source_override(module_id, scope_enum)  # type: ignore[attr-defined]

        # Add new source
        config.add_source_override(module_id, source, scope_enum)  # type: ignore[attr-defined]

        return {
            "module_id": module_id,
            "source": source,
            "scope": scope,
        }
