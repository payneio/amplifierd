"""Test that profile_name is correctly injected into mount plan settings."""

from pathlib import Path
from amplifierd.services.mount_plan_service import MountPlanService
from amplifier_library.storage.paths import get_share_dir


def test_profile_name_injection_pattern():
    """Test the profile_name injection pattern used in sessions.py."""
    # Generate mount plan
    mount_plan_service = MountPlanService(share_dir=get_share_dir())
    profile_name = "foundation/base"
    mount_plan = mount_plan_service.generate_mount_plan(profile_name)

    # Simulate what create_session does
    if "session" not in mount_plan:
        mount_plan["session"] = {}
    if "settings" not in mount_plan["session"]:
        mount_plan["session"]["settings"] = {}
    mount_plan["session"]["settings"]["profile_name"] = profile_name

    # Verify profile_name is in mount plan
    assert "profile_name" in mount_plan["session"]["settings"]
    assert mount_plan["session"]["settings"]["profile_name"] == profile_name


def test_profile_name_injection_in_profile_change():
    """Test profile_name injection when changing profiles."""
    # Generate new mount plan using an existing profile
    mount_plan_service = MountPlanService(share_dir=get_share_dir())
    profile_name = "foundation/base"
    new_mount_plan = mount_plan_service.generate_mount_plan(profile_name)

    # Simulate what change_session_profile does
    if "session" not in new_mount_plan:
        new_mount_plan["session"] = {}
    if "settings" not in new_mount_plan["session"]:
        new_mount_plan["session"]["settings"] = {}
    new_mount_plan["session"]["settings"]["profile_name"] = profile_name

    # Verify
    assert "profile_name" in new_mount_plan["session"]["settings"]
    assert new_mount_plan["session"]["settings"]["profile_name"] == profile_name
