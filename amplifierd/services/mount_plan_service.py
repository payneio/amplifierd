"""Mount plan service for generating session mount plans from cached profiles.

This service transforms cached profile resources into mount plans that amplifier-core
can use to initialize sessions. It handles:
- Converting manifest resources to mount points (embedded or referenced)
- Module ID generation with collision handling
- Session configuration creation
- Resource discovery in cache directories
"""

import logging
import uuid
from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from amplifierd.services.profile_service import ProfileService

from amplifierd.models.mount_plans import EmbeddedMount
from amplifierd.models.mount_plans import MountPlan
from amplifierd.models.mount_plans import MountPlanRequest
from amplifierd.models.mount_plans import MountPoint
from amplifierd.models.mount_plans import ReferencedMount
from amplifierd.models.mount_plans import SessionConfig

logger = logging.getLogger(__name__)


class MountPlanService:
    """Service for generating mount plans from cached profiles.

    Transforms cached profile resources into structured mount plans that specify
    how to assemble a session. Handles both embedded content (agents, context)
    and referenced modules (providers, tools, hooks).

    The service discovers resources in the profile cache directory and converts
    them to appropriate mount point types based on their purpose.
    """

    def __init__(
        self,
        profile_service: "ProfileService",
        share_dir: Path,
    ) -> None:
        """Initialize mount plan service.

        Args:
            profile_service: ProfileService for getting profile data
            share_dir: Path to share directory (for finding cached resources)
        """
        self.profile_service = profile_service
        self.share_dir = Path(share_dir)
        logger.info(f"MountPlanService initialized with share_dir={self.share_dir}")

    async def generate_mount_plan(self, request: MountPlanRequest) -> MountPlan:
        """Generate mount plan from cached profile.

        Takes a mount plan request and generates a complete mount plan by:
        1. Loading the cached profile details
        2. Finding all cached resources in the profile directory
        3. Converting resources to appropriate mount points (embedded or referenced)
        4. Creating session configuration
        5. Organizing mount points by type

        Args:
            request: MountPlanRequest with profile_id and optional settings

        Returns:
            MountPlan with all resources mounted and organized by type

        Raises:
            ValueError: If profile_id format is invalid
            FileNotFoundError: If profile not found or expected resources missing
        """
        logger.info(f"Generating mount plan for profile: {request.profile_id}")

        # Parse profile_id (format: "collection/profile" e.g., "foundation/base")
        parts = request.profile_id.split("/")
        if len(parts) != 2:
            raise ValueError(
                f"Invalid profile_id format: {request.profile_id}. "
                "Expected format: collection/profile (e.g., 'foundation/base')"
            )
        collection_id, profile_name = parts

        # Find profile cache directory
        profile_dir = self.share_dir / "profiles" / collection_id / profile_name
        if not profile_dir.exists():
            raise FileNotFoundError(
                f"Profile cache directory not found: {profile_dir}. "
                f"Profile {request.profile_id} must be compiled/cached first."
            )

        logger.debug(f"Using profile cache directory: {profile_dir}")

        # Generate session ID if not provided
        session_id = request.session_id or f"session_{uuid.uuid4().hex[:8]}"
        created_at = datetime.now(UTC).isoformat()

        logger.debug(f"Session ID: {session_id}, created_at: {created_at}")

        # Create session config
        session_config = SessionConfig(
            session_id=session_id,
            profile_id=request.profile_id,
            parent_session_id=request.parent_session_id,
            settings=request.settings_overrides,
            created_at=created_at,
        )

        # Convert cached resources to mount points
        mount_points: list[MountPoint] = []
        seen_ids: set[str] = set()

        # Process each resource type
        for resource_type in ["agents", "context", "providers", "tools", "hooks"]:
            resources = self._find_resources(profile_dir, resource_type)
            logger.debug(f"Found {len(resources)} {resource_type} resources")

            for resource_path, resource_name in resources:
                try:
                    mount_point = self._create_mount_point(
                        resource_path=resource_path,
                        profile_id=request.profile_id,
                        resource_type=resource_type,
                        resource_name=resource_name,
                        seen_ids=seen_ids,
                    )
                    mount_points.append(mount_point)
                    logger.debug(f"Created mount point: {mount_point.module_id}")
                except Exception as e:
                    logger.error(f"Error creating mount point for {resource_type}/{resource_name}: {e}")
                    # Continue processing other resources even if one fails

        logger.info(f"Generated mount plan with {len(mount_points)} mount points for session {session_id}")

        # Create and return mount plan (organizing happens in model_post_init)
        return MountPlan(
            session=session_config,
            mount_points=mount_points,
        )

    def _create_mount_point(
        self,
        resource_path: Path,
        profile_id: str,
        resource_type: str,
        resource_name: str,
        seen_ids: set[str],
    ) -> MountPoint:
        """Convert resource file to mount point.

        Determines whether to create an EmbeddedMount (for agents/context) or
        ReferencedMount (for providers/tools/hooks) based on the resource type.
        Handles module ID collision detection and resolution.

        Args:
            resource_path: Path to resource file
            profile_id: Profile ID for module_id generation
            resource_type: Type of resource (agents, context, providers, tools, hooks)
            resource_name: Name of resource (filename without extension)
            seen_ids: Set of module IDs seen so far (for collision detection)

        Returns:
            EmbeddedMount or ReferencedMount based on resource type

        Note:
            Implements deterministic collision handling by appending .2, .3, etc.
            to module IDs that would otherwise conflict.
        """
        # Generate base module_id (format: {profile_id}.{resource_type}.{resource_name})
        # Convert resource_type plural to singular for module_id (e.g., "agents" -> "agent")
        module_type_singular = resource_type.rstrip("s")
        module_id = f"{profile_id}.{module_type_singular}.{resource_name}"

        # Handle collisions with deterministic counter
        if module_id in seen_ids:
            counter = 2
            while f"{module_id}.{counter}" in seen_ids:
                counter += 1
            module_id = f"{module_id}.{counter}"
            logger.warning(f"Module ID collision detected, using: {module_id} (counter={counter})")

        seen_ids.add(module_id)

        # Determine mount type and create appropriate mount point
        if resource_type in ["agents", "context"]:
            # EMBEDDED: Read content and create EmbeddedMount
            content = resource_path.read_text(encoding="utf-8")
            return EmbeddedMount(
                module_id=module_id,
                module_type=module_type_singular,  # type: ignore[arg-type]  # Will be "agent" or "context"
                content=content,
                metadata={},
            )
        # REFERENCED: Create file:// URL and ReferencedMount
        abs_path = resource_path.resolve()
        file_url = f"file://{abs_path}"
        return ReferencedMount(
            module_id=module_id,
            module_type=module_type_singular,  # type: ignore[arg-type]  # Will be "provider", "tool", or "hook"
            source_path=file_url,
            metadata={},
        )

    def _find_resources(
        self,
        profile_dir: Path,
        resource_type: str,
    ) -> list[tuple[Path, str]]:
        """Find all resources of a given type in profile directory.

        Searches the appropriate subdirectory for the resource type and returns
        a list of (path, name) tuples for each resource found.

        Args:
            profile_dir: Path to profile cache directory
            resource_type: Type of resource (agents, context, providers, tools, hooks)

        Returns:
            List of (resource_path, resource_name) tuples
            Empty list if subdirectory doesn't exist
        """
        resource_dir = profile_dir / resource_type
        if not resource_dir.exists():
            logger.debug(f"Resource directory not found: {resource_dir}")
            return []

        resources: list[tuple[Path, str]] = []

        if resource_type in ["agents"]:
            # Agents: glob "*.md" files (flat structure)
            for resource_path in resource_dir.glob("*.md"):
                resource_name = resource_path.stem  # filename without extension
                resources.append((resource_path, resource_name))

        elif resource_type in ["context"]:
            # Context: recursively glob "**/*.md" files (nested directories)
            for resource_path in resource_dir.rglob("**/*.md"):
                # Use relative path from resource_dir as name (preserves nested structure)
                relative_path = resource_path.relative_to(resource_dir)
                resource_name = str(relative_path.with_suffix("")).replace("/", ".")
                resources.append((resource_path, resource_name))

        elif resource_type in ["providers", "tools", "hooks"]:
            # Code modules: recursively glob "**/*.py" files
            for resource_path in resource_dir.rglob("**/*.py"):
                # Use relative path from resource_dir as name (preserves nested structure)
                relative_path = resource_path.relative_to(resource_dir)
                resource_name = str(relative_path.with_suffix("")).replace("/", ".")
                resources.append((resource_path, resource_name))

        logger.debug(f"Found {len(resources)} resources in {resource_dir}")
        return resources
