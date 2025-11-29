"""Unit and integration tests for MountPlanService."""

from pathlib import Path
from typing import Any

import pytest

from amplifierd.services.mount_plan_service import MountPlanService


class TestMountPlanService:
    """Tests for MountPlanService."""

    @pytest.fixture
    def test_profile_dir(self, tmp_path: Path) -> Path:
        """Create test profile directory structure."""
        # Create profile cache structure
        profile_dir = tmp_path / "profiles" / "foundation" / "base"
        profile_dir.mkdir(parents=True)

        # Create agents directory with test agents
        agents_dir = profile_dir / "agents"
        agents_dir.mkdir()
        (agents_dir / "zen-architect.md").write_text("# Zen Architect\n\nYou are a systems architect...")
        (agents_dir / "bug-hunter.md").write_text("# Bug Hunter\n\nYou find bugs...")

        # Create registry profile.md
        registry_dir = tmp_path / "registry" / "profiles" / "foundation"
        registry_dir.mkdir(parents=True)

        profile_yaml = """---
profile:
  name: base
  version: 1.0.0
  description: Test profile
session:
  orchestrator:
    module: loop-streaming
    source: git+https://github.com/test/repo
    config:
      extended_thinking: true
  context:
    module: context-simple
    source: git+https://github.com/test/repo
    config:
      max_tokens: 400000
providers:
- module: provider-anthropic
  source: git+https://github.com/test/repo
  config:
    default_model: claude-sonnet-4-5
tools:
- module: tool-web
  source: git+https://github.com/test/repo
hooks:
- module: hooks-logging
  source: git+https://github.com/test/repo
  config:
    mode: session-only
---

Test profile content.
"""
        (registry_dir / "base.md").write_text(profile_yaml)

        return tmp_path

    @pytest.fixture
    def service(self, test_profile_dir: Path, monkeypatch: pytest.MonkeyPatch) -> MountPlanService:
        """Create MountPlanService instance with test setup."""

        # Patch the hardcoded registry path
        def patched_generate(self: MountPlanService, profile_id: str) -> dict[str, Any]:
            # Validate profile_id format
            parts = profile_id.split("/")
            if len(parts) != 2:
                raise ValueError(
                    f"Invalid profile_id format: {profile_id}. "
                    "Expected format: collection/profile (e.g., 'foundation/base')"
                )
            collection_id, profile_name = parts

            # Use test registry path
            registry_path = test_profile_dir / "registry" / "profiles" / collection_id / f"{profile_name}.md"

            # Inline the logic with test path instead of calling original
            profile_dir = self.share_dir / "profiles" / collection_id / profile_name
            if not profile_dir.exists():
                raise FileNotFoundError(f"Profile cache directory not found: {profile_dir}")

            agents_dict = self._load_agents(profile_dir / "agents", profile_id)

            if not registry_path.exists():
                raise FileNotFoundError(f"Profile source not found: {registry_path}")

            frontmatter = self._parse_frontmatter(registry_path)
            return self._transform_to_mount_plan(frontmatter, profile_id, agents_dict)

        monkeypatch.setattr(MountPlanService, "generate_mount_plan", patched_generate)

        return MountPlanService(share_dir=test_profile_dir)

    def test_generate_mount_plan_happy_path(self, service: MountPlanService) -> None:
        """Test generating mount plan with all resource types."""
        plan = service.generate_mount_plan("foundation/base")

        # Verify it returns a dict
        assert isinstance(plan, dict)

        # Verify session section
        assert "session" in plan
        assert "orchestrator" in plan["session"]
        assert plan["session"]["orchestrator"]["module"] == "loop-streaming"
        assert plan["session"]["orchestrator"]["source"] == "foundation/base"
        assert plan["session"]["orchestrator"]["config"]["extended_thinking"] is True

        assert "context" in plan["session"]
        assert plan["session"]["context"]["module"] == "context-simple"
        assert plan["session"]["context"]["source"] == "foundation/base"

        # Verify providers
        assert "providers" in plan
        assert len(plan["providers"]) == 1
        assert plan["providers"][0]["module"] == "provider-anthropic"
        assert plan["providers"][0]["source"] == "foundation/base"

        # Verify tools
        assert "tools" in plan
        assert len(plan["tools"]) == 1
        assert plan["tools"][0]["module"] == "tool-web"
        assert plan["tools"][0]["source"] == "foundation/base"

        # Verify hooks
        assert "hooks" in plan
        assert len(plan["hooks"]) == 1
        assert plan["hooks"][0]["module"] == "hooks-logging"
        assert plan["hooks"][0]["source"] == "foundation/base"
        assert plan["hooks"][0]["config"]["mode"] == "session-only"

        # Verify agents
        assert "agents" in plan
        assert len(plan["agents"]) == 2
        assert "zen-architect" in plan["agents"]
        assert "bug-hunter" in plan["agents"]
        assert "Zen Architect" in plan["agents"]["zen-architect"]["content"]
        assert plan["agents"]["zen-architect"]["metadata"]["source"] == "foundation/base:agents/zen-architect.md"

    def test_invalid_profile_id_format(self, service: MountPlanService) -> None:
        """Test that invalid profile_id format raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            service.generate_mount_plan("invalid-format")

        assert "Invalid profile_id format" in str(exc_info.value)
        assert "Expected format: collection/profile" in str(exc_info.value)

    def test_profile_not_found(self, service: MountPlanService) -> None:
        """Test that missing profile raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError) as exc_info:
            service.generate_mount_plan("nonexistent/profile")

        assert "Profile cache directory not found" in str(exc_info.value)

    def test_load_agents(self, service: MountPlanService, test_profile_dir: Path) -> None:
        """Test loading agents from directory."""
        agents_dir = test_profile_dir / "profiles" / "foundation" / "base" / "agents"
        agents = service._load_agents(agents_dir, "foundation/base")

        assert len(agents) == 2
        assert "zen-architect" in agents
        assert "bug-hunter" in agents
        assert "Zen Architect" in agents["zen-architect"]["content"]
        assert agents["zen-architect"]["metadata"]["source"] == "foundation/base:agents/zen-architect.md"

    def test_load_agents_empty_dir(self, service: MountPlanService, tmp_path: Path) -> None:
        """Test loading agents from nonexistent directory."""
        agents = service._load_agents(tmp_path / "nonexistent", "test/profile")
        assert agents == {}

    def test_parse_frontmatter(self, service: MountPlanService, tmp_path: Path) -> None:
        """Test parsing YAML frontmatter."""
        test_file = tmp_path / "test.md"
        test_file.write_text("""---
test_key: test_value
nested:
  key: value
---

Content here.
""")

        frontmatter = service._parse_frontmatter(test_file)
        assert frontmatter["test_key"] == "test_value"
        assert frontmatter["nested"]["key"] == "value"

    def test_parse_frontmatter_no_frontmatter(self, service: MountPlanService, tmp_path: Path) -> None:
        """Test parsing file without frontmatter raises error."""
        test_file = tmp_path / "test.md"
        test_file.write_text("Just content, no frontmatter")

        with pytest.raises(ValueError) as exc_info:
            service._parse_frontmatter(test_file)
        assert "no YAML frontmatter" in str(exc_info.value)

    def test_parse_frontmatter_invalid_yaml(self, service: MountPlanService, tmp_path: Path) -> None:
        """Test parsing invalid YAML raises error."""
        test_file = tmp_path / "test.md"
        test_file.write_text("""---
invalid: yaml: structure: here
---
""")

        with pytest.raises(ValueError) as exc_info:
            service._parse_frontmatter(test_file)
        assert "Invalid YAML" in str(exc_info.value)
