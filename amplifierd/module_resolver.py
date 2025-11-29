"""Module source resolver for amplifierd.

Resolves module IDs to filesystem paths in the compiled profile structure.
Uses collection/profile namespacing to isolate module sources per session.

Contract:
- Inputs: Module ID (hyphenated), profile source hint (collection/profile context)
- Outputs: Path to directory containing Python package
- Side Effects: None (read-only discovery)
"""

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ModuleSource:
    """File-based module source for amplifierd."""

    def __init__(self, path: Path, module_id: str):
        """Initialize module source.

        Args:
            path: Path to directory containing module package
            module_id: Module identifier for logging
        """
        self.path = path
        self.module_id = module_id

    def resolve(self) -> Path:
        """Resolve to filesystem path.

        Returns:
            Path to directory containing importable Python module

        Raises:
            FileNotFoundError: If path doesn't exist
        """
        if not self.path.exists():
            raise FileNotFoundError(f"Module path not found: {self.path}")
        return self.path

    def __str__(self) -> str:
        return f"FileSource({self.module_id} @ {self.path})"


class DaemonModuleSourceResolver:
    """Resolves module IDs to paths in compiled profile structure.

    Handles collection/profile namespacing, mount type detection,
    and module directory discovery.

    Example:
        >>> resolver = DaemonModuleSourceResolver(share_dir=Path(".amplifierd/share"))
        >>> profile_hint = {"collection": "foundation", "profile": "base"}
        >>> source = resolver.resolve("provider-anthropic", profile_hint)
        >>> path = source.resolve()
        >>> # Returns: .amplifierd/share/profiles/foundation/base/providers/provider-anthropic
    """

    # Map module ID patterns to mount types
    MOUNT_TYPE_MAP = {
        "orchestrator": "orchestrator",
        "loop": "orchestrator",
        "context": "context",
        "provider": "providers",
        "tool": "tools",
        "hook": "hooks",
    }

    def __init__(self, share_dir: Path):
        """Initialize resolver with share directory.

        Args:
            share_dir: Path to amplifierd share directory
        """
        self.share_dir = Path(share_dir)
        logger.debug(f"DaemonModuleSourceResolver initialized with share_dir={self.share_dir}")

    def resolve(self, module_id: str, profile_hint: dict[str, Any] | str | None = None) -> ModuleSource:
        """Resolve module ID to source path.

        Args:
            module_id: Hyphenated module name (e.g., "provider-anthropic")
            profile_hint: Dict with collection/profile or profile string

        Returns:
            ModuleSource that can be resolved to a Path

        Raises:
            ValueError: If profile hint missing or invalid
            FileNotFoundError: If module not found in profile

        Example:
            >>> resolver.resolve("provider-anthropic", {"collection": "foundation", "profile": "base"})
            ModuleSource(.../.amplifierd/share/profiles/foundation/base/providers/provider-anthropic)
        """
        # Extract collection and profile from hint
        if isinstance(profile_hint, dict):
            collection = profile_hint.get("collection")
            profile = profile_hint.get("profile")
        elif isinstance(profile_hint, str) and "/" in profile_hint:
            # Support "collection/profile" string format
            collection, profile = profile_hint.split("/", 1)
        else:
            raise ValueError(
                f"profile_hint must be dict with collection/profile or 'collection/profile' string, "
                f"got: {type(profile_hint)}"
            )

        if not collection or not profile:
            raise ValueError(f"profile_hint must specify both collection and profile, got: {profile_hint}")

        # Determine mount type from module ID
        mount_type = self._guess_mount_type(module_id)
        if not mount_type:
            raise ValueError(f"Could not determine mount type for module: {module_id}")

        # Build path to module directory
        # Structure: share/profiles/{collection}/{profile}/{mount_type}/{module_id}/
        module_dir = self.share_dir / "profiles" / collection / profile / mount_type / module_id

        logger.debug(f"Resolved '{module_id}' → {module_dir} (mount_type={mount_type})")

        return ModuleSource(path=module_dir, module_id=module_id)

    def _guess_mount_type(self, module_id: str) -> str | None:
        """Guess mount type from module ID.

        Args:
            module_id: Hyphenated module name

        Returns:
            Mount type directory name or None if unknown

        Example:
            >>> resolver._guess_mount_type("provider-anthropic")
            'providers'
            >>> resolver._guess_mount_type("loop-streaming")
            'orchestrator'
            >>> resolver._guess_mount_type("hooks-status-context")
            'hooks'
        """
        # Check patterns in order of specificity (plural forms first to match module type)
        # This ensures "hooks-status-context" matches "hooks" not "context"
        specificity_order = ["provider", "tool", "hook", "loop", "orchestrator", "context"]

        for pattern in specificity_order:
            if pattern in module_id:
                mount_type = self.MOUNT_TYPE_MAP.get(pattern)
                if mount_type:
                    return mount_type

        # Default: if we can't guess, log warning and return None
        logger.warning(f"Could not guess mount type for module: {module_id}")
        return None
