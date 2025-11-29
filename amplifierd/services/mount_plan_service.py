"""Mount plan service for generating session mount plans from profile frontmatter.

This service reads profile YAML frontmatter and generates dict-based mount plans
that amplifier-core can use to initialize sessions with the DaemonModuleSourceResolver.
"""

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


class MountPlanService:
    """Service for generating mount plans from profile YAML frontmatter.

    Reads profile.md YAML frontmatter and transforms it into dict-based mount plans
    using profile hint format (source: "collection/profile") that the resolver understands.
    """

    def __init__(self, share_dir: Path) -> None:
        """Initialize mount plan service.

        Args:
            share_dir: Path to share directory (for finding cached profiles)
        """
        self.share_dir = Path(share_dir)
        logger.info(f"MountPlanService initialized with share_dir={self.share_dir}")

    def generate_mount_plan(self, profile_id: str) -> dict[str, Any]:
        """Generate mount plan from profile frontmatter.

        Reads profile.md YAML frontmatter and transforms it into dict-based mount plan
        with profile hint format for source fields (e.g., "foundation/base").

        Args:
            profile_id: Profile ID in format "collection/profile" (e.g., "foundation/base")

        Returns:
            Dict mount plan with session, providers, tools, hooks, agents sections

        Raises:
            ValueError: If profile_id format is invalid
            FileNotFoundError: If profile not found in cache
        """
        logger.info(f"Generating mount plan for profile: {profile_id}")

        # Parse profile_id
        parts = profile_id.split("/")
        if len(parts) != 2:
            raise ValueError(
                f"Invalid profile_id format: {profile_id}. "
                "Expected format: collection/profile (e.g., 'foundation/base')"
            )
        collection_id, profile_name = parts

        # Find cached profile directory
        profile_dir = self.share_dir / "profiles" / collection_id / profile_name
        if not profile_dir.exists():
            raise FileNotFoundError(
                f"Profile cache directory not found: {profile_dir}. Profile {profile_id} must be compiled/cached first."
            )

        logger.debug(f"Using profile cache directory: {profile_dir}")

        # Read agents directory if it exists
        agents_dict = self._load_agents(profile_dir / "agents", profile_id)

        # Find profile.md in the registry (source)
        # The cached profile directory mirrors the registry structure
        # Use profile_id to construct the registry path
        registry_profile_path = (
            Path("/data/repos/msft/payneio/amplifierd/registry/profiles") / collection_id / f"{profile_name}.md"
        )

        if not registry_profile_path.exists():
            raise FileNotFoundError(
                f"Profile source not found: {registry_profile_path}. Expected profile definition at this location."
            )

        # Parse YAML frontmatter from profile.md
        frontmatter = self._parse_frontmatter(registry_profile_path)

        # Transform to mount plan dict
        mount_plan = self._transform_to_mount_plan(frontmatter, profile_id, agents_dict)

        logger.info(f"Generated mount plan for {profile_id} with {len(agents_dict)} agents")
        return mount_plan

    def _parse_frontmatter(self, profile_path: Path) -> dict[str, Any]:
        """Parse YAML frontmatter from profile.md.

        Args:
            profile_path: Path to profile.md file

        Returns:
            Dict of parsed YAML frontmatter

        Raises:
            ValueError: If file has no frontmatter or invalid YAML
        """
        content = profile_path.read_text(encoding="utf-8")

        # Extract frontmatter between --- delimiters
        if not content.startswith("---\n"):
            raise ValueError(f"Profile {profile_path} has no YAML frontmatter")

        # Find end of frontmatter
        end_idx = content.find("\n---\n", 4)
        if end_idx == -1:
            raise ValueError(f"Profile {profile_path} has unclosed frontmatter")

        frontmatter_text = content[4:end_idx]

        # Parse YAML
        try:
            frontmatter = yaml.safe_load(frontmatter_text)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in {profile_path}: {e}") from e

        return frontmatter

    def _load_agents(self, agents_dir: Path, profile_id: str) -> dict[str, dict[str, Any]]:
        """Load agent markdown files from profile agents directory.

        Args:
            agents_dir: Path to agents directory
            profile_id: Profile ID for metadata

        Returns:
            Dict mapping agent names to content/metadata
        """
        if not agents_dir.exists():
            logger.debug(f"No agents directory at {agents_dir}")
            return {}

        agents = {}
        for agent_file in agents_dir.glob("*.md"):
            agent_name = agent_file.stem
            content = agent_file.read_text(encoding="utf-8")
            agents[agent_name] = {"content": content, "metadata": {"source": f"{profile_id}:agents/{agent_file.name}"}}
            logger.debug(f"Loaded agent: {agent_name}")

        return agents

    def _transform_to_mount_plan(
        self, frontmatter: dict[str, Any], profile_id: str, agents_dict: dict[str, dict[str, Any]]
    ) -> dict[str, Any]:
        """Transform frontmatter YAML to mount plan dict.

        Args:
            frontmatter: Parsed YAML frontmatter
            profile_id: Profile ID for source hints
            agents_dict: Loaded agents

        Returns:
            Mount plan dict with session, providers, tools, hooks, agents
        """
        mount_plan: dict[str, Any] = {}

        # Session section (orchestrator + context + session-level config)
        if "session" in frontmatter:
            session_data = frontmatter["session"]
            mount_plan["session"] = {}

            # Transform orchestrator
            if "orchestrator" in session_data:
                orch = session_data["orchestrator"]
                mount_plan["session"]["orchestrator"] = {
                    "module": orch.get("module"),
                    "source": profile_id,  # Profile hint for resolver
                    "config": orch.get("config", {}),
                }

            # Transform context
            if "context" in session_data:
                ctx = session_data["context"]
                mount_plan["session"]["context"] = {
                    "module": ctx.get("module"),
                    "source": profile_id,  # Profile hint for resolver
                    "config": ctx.get("config", {}),
                }

            # Copy session-level configuration fields (injection limits, etc.)
            if "injection_size_limit" in session_data:
                mount_plan["session"]["injection_size_limit"] = session_data["injection_size_limit"]
            if "injection_budget_per_turn" in session_data:
                mount_plan["session"]["injection_budget_per_turn"] = session_data["injection_budget_per_turn"]

        # Transform providers
        if "providers" in frontmatter:
            mount_plan["providers"] = [
                {
                    "module": p.get("module"),
                    "source": profile_id,  # Profile hint for resolver
                    "config": p.get("config", {}),
                }
                for p in frontmatter["providers"]
            ]

        # Transform tools
        if "tools" in frontmatter:
            mount_plan["tools"] = [
                {
                    "module": t.get("module"),
                    "source": profile_id,  # Profile hint for resolver
                    "config": t.get("config", {}),
                }
                for t in frontmatter["tools"]
            ]

        # Transform hooks
        if "hooks" in frontmatter:
            mount_plan["hooks"] = [
                {
                    "module": h.get("module"),
                    "source": profile_id,  # Profile hint for resolver
                    "config": h.get("config", {}),
                }
                for h in frontmatter["hooks"]
            ]

        # Add agents
        if agents_dict:
            mount_plan["agents"] = agents_dict

        return mount_plan
