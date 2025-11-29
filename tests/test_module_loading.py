"""Test module loading with mount plans.

This test verifies that the module loading system works correctly with
the mount plan format we generate.
"""

import sys
from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_module_loader_filesystem_discovery():
    """Test that ModuleLoader can load a module from filesystem with correct search path."""
    from amplifier_core import ModuleLoader

    # Path structure (new profile-named directory structure):
    # /some/parent/dir/
    #   amplifier_module_loop_streaming/
    #     __init__.py  (contains mount function)

    # Use profile-named directory structure (not hash-based)
    parent_dir = Path(
        "/data/repos/msft/payneio/amplifierd/.amplifierd/share/profiles/foundation/base/orchestrator/loop-streaming"
    )

    # Verify the module exists
    module_dir = parent_dir / "amplifier_module_loop_streaming"
    assert module_dir.exists(), f"Module directory not found: {module_dir}"
    assert (module_dir / "__init__.py").exists(), "Module __init__.py not found"

    # Create loader with search path pointing to parent directory
    # This is what mount plan service generates
    loader = ModuleLoader(search_paths=[parent_dir])

    # Try to load the module with ID "loop-streaming" (profile name format)
    # This is what mount plan service puts in the mount plan
    try:
        mount_fn = await loader.load("loop-streaming", config={})
        assert mount_fn is not None, "Module load returned None"
        print("✓ Successfully loaded module 'loop_streaming'")
        print(f"  Module type: {type(mount_fn)}")
    except Exception as e:
        pytest.fail(f"Failed to load module: {e}")


@pytest.mark.asyncio
async def test_module_loader_with_direct_import():
    """Test direct import to understand what ModuleLoader is trying to do."""
    # Use profile-named directory structure (not hash-based)
    parent_dir = Path(
        "/data/repos/msft/payneio/amplifierd/.amplifierd/share/profiles/foundation/base/orchestrator/loop-streaming"
    )

    # Add to sys.path like ModuleLoader does
    parent_str = str(parent_dir)
    if parent_str not in sys.path:
        sys.path.insert(0, parent_str)

    try:
        # This is what ModuleLoader._load_filesystem does:
        # module_name = f"amplifier_module_{module_id.replace('-', '_')}"
        # For module_id "loop_streaming", it tries:
        import amplifier_module_loop_streaming

        assert hasattr(amplifier_module_loop_streaming, "mount"), "Module missing mount function"
        print("✓ Direct import successful")
        print(f"  Module: {amplifier_module_loop_streaming}")
        print(f"  Mount function: {amplifier_module_loop_streaming.mount}")

    except ImportError as e:
        pytest.fail(f"Direct import failed: {e}")


@pytest.mark.asyncio
async def test_mount_plan_format():
    """Test that our mount plan format works with AmplifierSession."""
    from pathlib import Path

    # Use profile-named directory structure (not hash-based)
    parent_dir = Path(
        "/data/repos/msft/payneio/amplifierd/.amplifierd/share/profiles/foundation/base/orchestrator/loop-streaming"
    )

    # This is the format our mount plan service generates
    mount_plan = {
        "session": {
            "orchestrator": {"module": "loop_streaming", "source": f"file://{parent_dir}", "config": {}},
            "context": {"module": "context-simple", "config": {}},
        },
        "providers": [],
        "tools": [],
        "hooks": [],
    }

    # Create AmplifierSession with this config
    from amplifier_core import AmplifierSession
    from amplifier_core import ModuleLoader

    # Create loader with search paths from mount plan
    search_paths = [parent_dir]
    loader = ModuleLoader(search_paths=search_paths)

    # Create session
    session = AmplifierSession(config=mount_plan, loader=loader, session_id="test_session")

    # Try to initialize
    try:
        await session.initialize()
        print("✓ Session initialized successfully")
    except Exception as e:
        pytest.fail(f"Session initialization failed: {e}")
    finally:
        await session.cleanup()


if __name__ == "__main__":
    import asyncio

    print("Test 1: Direct import test")
    print("=" * 60)
    asyncio.run(test_module_loader_with_direct_import())

    print("\nTest 2: ModuleLoader filesystem discovery")
    print("=" * 60)
    asyncio.run(test_module_loader_filesystem_discovery())

    print("\nTest 3: Full mount plan format")
    print("=" * 60)
    asyncio.run(test_mount_plan_format())
