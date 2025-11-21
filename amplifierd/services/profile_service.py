"""Profile discovery service using amplifier_profiles library.

NOTE: This service requires amplifier-dev workspace packages:
- amplifier_profiles
- amplifier_config
- amplifier_collections

These are not included in standard dependencies as they're development-only.
Tests use mocking to avoid the dependency.
"""

from pathlib import Path

from amplifier_collections import CollectionResolver  # type: ignore[import-untyped]
from amplifier_config import ConfigManager  # type: ignore[import-untyped]
from amplifier_config import ConfigPaths  # type: ignore[import-untyped]
from amplifier_profiles import ProfileLoader  # type: ignore[import-untyped]


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


def _get_collection_search_paths() -> list[Path]:
    """Get daemon-specific collection search paths.

    Returns:
        List of paths to search for collections
    """
    return [
        Path.cwd() / ".amplifier" / "collections",
        Path.home() / ".amplifier" / "collections",
    ]


def _get_profile_search_paths(resolver: CollectionResolver) -> list[Path]:
    """Get daemon-specific profile search paths.

    Args:
        resolver: Collection resolver for discovering collection profiles

    Returns:
        List of paths to search for profiles
    """
    from amplifier_collections import discover_collection_resources

    paths = []

    # Project profiles
    project_profiles = Path.cwd() / ".amplifier" / "profiles"
    if project_profiles.exists():
        paths.append(project_profiles)

    # User profiles
    user_profiles = Path.home() / ".amplifier" / "profiles"
    if user_profiles.exists():
        paths.append(user_profiles)

    # Collection profiles
    for _metadata_name, collection_path in resolver.list_collections():
        resources = discover_collection_resources(collection_path)
        if resources.profiles:
            profile_dir = resources.profiles[0].parent
            if profile_dir not in paths:
                paths.append(profile_dir)

    return paths


class ProfileService:
    """Service for profile discovery and management operations."""

    def __init__(self: "ProfileService") -> None:
        """Initialize profile service with necessary dependencies."""
        self._config_manager = ConfigManager(paths=_get_config_paths())
        self._collection_resolver = CollectionResolver(search_paths=_get_collection_search_paths())
        self._profile_loader: ProfileLoader | None = None

    def _get_loader(self: "ProfileService") -> ProfileLoader:
        """Get or create profile loader.

        Returns:
            ProfileLoader instance
        """
        if self._profile_loader is None:
            # Create a minimal mention loader that returns empty string
            class MinimalMentionLoader:
                """Minimal mention loader for daemon."""

                async def load_mention(self: "MinimalMentionLoader", mention: str) -> str:
                    """Load mention content.

                    Args:
                        mention: Mention reference

                    Returns:
                        Empty string (mentions not supported in daemon)
                    """
                    return ""

            self._profile_loader = ProfileLoader(
                search_paths=_get_profile_search_paths(self._collection_resolver),
                collection_resolver=self._collection_resolver,
                mention_loader=MinimalMentionLoader(),  # type: ignore[arg-type]
            )
        return self._profile_loader

    async def list_profiles(self: "ProfileService") -> list[dict[str, str | bool]]:
        """List all available profiles.

        Returns:
            List of profile info dictionaries with name, description, source, and is_active
        """
        loader = self._get_loader()
        profiles = loader.list_profiles()
        active_profile = self._config_manager.get_active_profile()

        result = []
        for profile_name in profiles:
            source = loader.get_profile_source(profile_name) or "unknown"
            result.append(
                {
                    "name": profile_name,
                    "source": source,
                    "is_active": profile_name == active_profile,
                }
            )

        return result

    async def get_profile(
        self: "ProfileService", name: str
    ) -> dict[str, str | bool | list[str] | list[dict[str, object]]]:
        """Get profile details by name.

        Args:
            name: Profile name

        Returns:
            Profile details dictionary

        Raises:
            FileNotFoundError: If profile not found
            ValueError: If profile invalid
        """
        loader = self._get_loader()
        profile_obj = loader.load_profile(name)
        chain_names = loader.get_inheritance_chain(name)
        active_profile = self._config_manager.get_active_profile()

        return {
            "name": profile_obj.profile.name,
            "version": profile_obj.profile.version,
            "description": profile_obj.profile.description,
            "source": loader.get_profile_source(name) or "unknown",
            "is_active": name == active_profile,
            "inheritance_chain": chain_names,
            "providers": [
                {"module": item["module"], "source": item.get("source"), "config": item.get("config")}  # type: ignore[index, union-attr]
                for item in profile_obj.providers
            ],
            "tools": [
                {"module": item["module"], "source": item.get("source"), "config": item.get("config")}  # type: ignore[index, union-attr]
                for item in profile_obj.tools
            ],
            "hooks": [
                {"module": item["module"], "source": item.get("source"), "config": item.get("config")}  # type: ignore[index, union-attr]
                for item in profile_obj.hooks
            ],
        }

    async def get_active_profile(self: "ProfileService") -> dict[str, str | bool] | None:
        """Get currently active profile.

        Returns:
            Active profile info or None if no profile active
        """
        active_profile = self._config_manager.get_active_profile()
        if not active_profile:
            return None

        loader = self._get_loader()
        source = loader.get_profile_source(active_profile) or "unknown"

        return {
            "name": active_profile,
            "source": source,
            "is_active": True,
        }

    async def activate_profile(self: "ProfileService", name: str) -> dict[str, str]:
        """Activate a profile by name.

        Args:
            name: Profile name to activate

        Returns:
            Dictionary with profile name and status

        Raises:
            ValueError: If profile not found
        """
        # Validate profile exists
        try:
            await self.get_profile(name)
        except (FileNotFoundError, KeyError):
            raise ValueError(f"Profile not found: {name}")

        # Import Scope for scope parameter
        from amplifier_config import Scope  # type: ignore[import-untyped]

        # Set active profile
        self._config_manager.set_active_profile(name, Scope.LOCAL)

        return {
            "name": name,
            "status": "activated",
        }

    async def deactivate_profile(self: "ProfileService") -> dict[str, bool]:
        """Deactivate the current profile.

        Returns:
            Dictionary with deactivated status
        """
        from amplifier_config import Scope  # type: ignore[import-untyped]

        # Set to None/empty
        self._config_manager.set_active_profile(None, Scope.LOCAL)  # type: ignore[arg-type]

        return {"deactivated": True}
