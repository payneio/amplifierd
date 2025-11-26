"""Unit and integration tests for MountPlanService."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from amplifierd.models.mount_plans import EmbeddedMount
from amplifierd.models.mount_plans import MountPlanRequest
from amplifierd.models.mount_plans import ReferencedMount
from amplifierd.services.mount_plan_service import MountPlanService


class TestMountPlanService:
    """Tests for MountPlanService."""

    @pytest.fixture
    def profile_service_mock(self) -> Mock:
        """Mock ProfileService for testing."""
        return Mock()

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

        # Create context directory with nested structure
        context_dir = profile_dir / "context"
        context_dir.mkdir()
        (context_dir / "design-principles.md").write_text("# Design Principles\n\nFollow these...")
        nested_context = context_dir / "shared"
        nested_context.mkdir()
        (nested_context / "common-base.md").write_text("# Common Base\n\nShared context...")

        # Create providers directory
        providers_dir = profile_dir / "providers"
        providers_dir.mkdir()
        (providers_dir / "anthropic.py").write_text("# Provider code")

        # Create tools directory
        tools_dir = profile_dir / "tools"
        tools_dir.mkdir()
        (tools_dir / "file-reader.py").write_text("# Tool code")

        # Create hooks directory
        hooks_dir = profile_dir / "hooks"
        hooks_dir.mkdir()
        (hooks_dir / "pre-commit.py").write_text("# Hook code")

        return tmp_path

    @pytest.fixture
    def service(self, profile_service_mock: Mock, test_profile_dir: Path) -> MountPlanService:
        """Create MountPlanService instance with test setup."""
        return MountPlanService(
            profile_service=profile_service_mock,
            share_dir=test_profile_dir,
        )

    @pytest.mark.asyncio
    async def test_generate_mount_plan_happy_path(self, service: MountPlanService) -> None:
        """Test generating mount plan with all resource types."""
        request = MountPlanRequest(profile_id="foundation/base")

        plan = await service.generate_mount_plan(request)

        # Verify session config
        assert plan.session.profile_id == "foundation/base"
        assert plan.session.session_id.startswith("session_")
        assert plan.session.parent_session_id is None
        assert plan.session.created_at  # ISO format datetime

        # Verify mount points were created
        assert len(plan.mount_points) > 0

        # Verify agents (flat structure)
        assert len(plan.agents) == 2
        assert "foundation/base.agent.zen-architect" in plan.agents
        assert "foundation/base.agent.bug-hunter" in plan.agents

        # Verify agent content is embedded
        zen_agent = plan.agents["foundation/base.agent.zen-architect"]
        assert isinstance(zen_agent, EmbeddedMount)
        assert "Zen Architect" in zen_agent.content

        # Verify context (nested structure)
        assert len(plan.context) == 2
        assert "foundation/base.context.design-principles" in plan.context
        assert "foundation/base.context.shared.common-base" in plan.context

        # Verify context content is embedded
        design_context = plan.context["foundation/base.context.design-principles"]
        assert isinstance(design_context, EmbeddedMount)
        assert "Design Principles" in design_context.content

        # Verify providers
        assert len(plan.providers) == 1
        assert "foundation/base.provider.anthropic" in plan.providers
        provider = plan.providers["foundation/base.provider.anthropic"]
        assert isinstance(provider, ReferencedMount)
        assert provider.source_path.startswith("file://")
        assert "anthropic.py" in provider.source_path

        # Verify tools
        assert len(plan.tools) == 1
        assert "foundation/base.tool.file-reader" in plan.tools

        # Verify hooks
        assert len(plan.hooks) == 1
        assert "foundation/base.hook.pre-commit" in plan.hooks

    @pytest.mark.asyncio
    async def test_generate_with_custom_session_id(self, service: MountPlanService) -> None:
        """Test generating mount plan with explicit session ID."""
        request = MountPlanRequest(
            profile_id="foundation/base",
            session_id="custom_session_123",
        )

        plan = await service.generate_mount_plan(request)

        assert plan.session.session_id == "custom_session_123"

    @pytest.mark.asyncio
    async def test_generate_with_settings_overrides(self, service: MountPlanService) -> None:
        """Test generating mount plan with settings overrides."""
        request = MountPlanRequest(
            profile_id="foundation/base",
            settings_overrides={"max_turns": 20, "streaming": False},
        )

        plan = await service.generate_mount_plan(request)

        assert plan.session.settings["max_turns"] == 20
        assert plan.session.settings["streaming"] is False

    @pytest.mark.asyncio
    async def test_generate_with_parent_session(self, service: MountPlanService) -> None:
        """Test generating mount plan for sub-session."""
        request = MountPlanRequest(
            profile_id="foundation/base",
            parent_session_id="parent_session_456",
        )

        plan = await service.generate_mount_plan(request)

        assert plan.session.parent_session_id == "parent_session_456"

    @pytest.mark.asyncio
    async def test_invalid_profile_id_format(self, service: MountPlanService) -> None:
        """Test that invalid profile_id format raises ValueError."""
        request = MountPlanRequest(profile_id="invalid-format")

        with pytest.raises(ValueError) as exc_info:
            await service.generate_mount_plan(request)

        assert "Invalid profile_id format" in str(exc_info.value)
        assert "Expected format: collection/profile" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_profile_not_found(self, service: MountPlanService) -> None:
        """Test that missing profile raises FileNotFoundError."""
        request = MountPlanRequest(profile_id="nonexistent/profile")

        with pytest.raises(FileNotFoundError) as exc_info:
            await service.generate_mount_plan(request)

        assert "Profile cache directory not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_empty_profile(self, tmp_path: Path, profile_service_mock: Mock) -> None:
        """Test generating mount plan from profile with no resources."""
        # Create empty profile directory
        empty_profile_dir = tmp_path / "profiles" / "empty" / "profile"
        empty_profile_dir.mkdir(parents=True)

        service = MountPlanService(
            profile_service=profile_service_mock,
            share_dir=tmp_path,
        )

        request = MountPlanRequest(profile_id="empty/profile")

        plan = await service.generate_mount_plan(request)

        # Should succeed with empty mount points
        assert len(plan.mount_points) == 0
        assert len(plan.agents) == 0
        assert len(plan.context) == 0
        assert len(plan.providers) == 0

    @pytest.mark.asyncio
    async def test_module_id_collision_handling(self, tmp_path: Path, profile_service_mock: Mock) -> None:
        """Test that module ID collisions are handled with counter suffix."""
        # Create profile with duplicate resource names in different locations
        profile_dir = tmp_path / "profiles" / "test" / "collision"
        profile_dir.mkdir(parents=True)

        agents_dir = profile_dir / "agents"
        agents_dir.mkdir()
        (agents_dir / "helper.md").write_text("# Helper 1")

        # We can't create actual collisions in file system (same name same dir)
        # But we can test the logic by manually calling _create_mount_point
        # This test verifies the collision handling code path exists
        # Real collisions would require complex setup or integration test

        service = MountPlanService(
            profile_service=profile_service_mock,
            share_dir=tmp_path,
        )

        seen_ids: set[str] = set()

        # Create first mount point
        mount1 = service._create_mount_point(
            resource_path=agents_dir / "helper.md",
            profile_id="test/collision",
            resource_type="agents",
            resource_name="helper",
            seen_ids=seen_ids,
        )

        assert mount1.module_id == "test/collision.agent.helper"
        assert mount1.module_id in seen_ids

        # Create second mount point with same name (simulating collision)
        mount2 = service._create_mount_point(
            resource_path=agents_dir / "helper.md",
            profile_id="test/collision",
            resource_type="agents",
            resource_name="helper",
            seen_ids=seen_ids,
        )

        # Second one should have .2 suffix
        assert mount2.module_id == "test/collision.agent.helper.2"
        assert mount2.module_id in seen_ids

        # Third one should have .3 suffix
        mount3 = service._create_mount_point(
            resource_path=agents_dir / "helper.md",
            profile_id="test/collision",
            resource_type="agents",
            resource_name="helper",
            seen_ids=seen_ids,
        )

        assert mount3.module_id == "test/collision.agent.helper.3"

    def test_find_resources_flat_structure(self, service: MountPlanService, test_profile_dir: Path) -> None:
        """Test finding resources in flat directory (agents)."""
        profile_dir = test_profile_dir / "profiles" / "foundation" / "base"

        resources = service._find_resources(profile_dir, "agents")

        assert len(resources) == 2
        names = [name for _, name in resources]
        assert "zen-architect" in names
        assert "bug-hunter" in names

    def test_find_resources_nested_structure(self, service: MountPlanService, test_profile_dir: Path) -> None:
        """Test finding resources in nested directories (context)."""
        profile_dir = test_profile_dir / "profiles" / "foundation" / "base"

        resources = service._find_resources(profile_dir, "context")

        assert len(resources) == 2
        names = [name for _, name in resources]
        assert "design-principles" in names
        assert "shared.common-base" in names  # Nested path preserved with dots

    def test_find_resources_code_modules(self, service: MountPlanService, test_profile_dir: Path) -> None:
        """Test finding Python module resources."""
        profile_dir = test_profile_dir / "profiles" / "foundation" / "base"

        providers = service._find_resources(profile_dir, "providers")
        tools = service._find_resources(profile_dir, "tools")
        hooks = service._find_resources(profile_dir, "hooks")

        assert len(providers) == 1
        assert len(tools) == 1
        assert len(hooks) == 1

    def test_find_resources_missing_directory(self, service: MountPlanService, tmp_path: Path) -> None:
        """Test finding resources when directory doesn't exist."""
        profile_dir = tmp_path / "nonexistent"

        resources = service._find_resources(profile_dir, "agents")

        assert resources == []

    def test_create_mount_point_embedded(self, service: MountPlanService, tmp_path: Path) -> None:
        """Test creating embedded mount point for agent."""
        test_file = tmp_path / "test-agent.md"
        test_file.write_text("# Test Agent\n\nAgent content")

        seen_ids: set[str] = set()

        mount = service._create_mount_point(
            resource_path=test_file,
            profile_id="test/profile",
            resource_type="agents",
            resource_name="test-agent",
            seen_ids=seen_ids,
        )

        assert isinstance(mount, EmbeddedMount)
        assert mount.module_id == "test/profile.agent.test-agent"
        assert mount.module_type == "agent"
        assert "Test Agent" in mount.content
        assert mount.module_id in seen_ids

    def test_create_mount_point_referenced(self, service: MountPlanService, tmp_path: Path) -> None:
        """Test creating referenced mount point for provider."""
        test_file = tmp_path / "test-provider.py"
        test_file.write_text("# Provider code")

        seen_ids: set[str] = set()

        mount = service._create_mount_point(
            resource_path=test_file,
            profile_id="test/profile",
            resource_type="providers",
            resource_name="test-provider",
            seen_ids=seen_ids,
        )

        assert isinstance(mount, ReferencedMount)
        assert mount.module_id == "test/profile.provider.test-provider"
        assert mount.module_type == "provider"
        assert mount.source_path.startswith("file://")
        assert "test-provider.py" in mount.source_path
        assert mount.module_id in seen_ids
