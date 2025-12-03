"""Profile compilation service.

Resolves profile refs and caches compiled assets for dynamic import.
Creates Python module structure from profile manifests with all refs resolved.
"""

import hashlib
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path

from amplifierd.models.profiles import ProfileDetails
from amplifierd.services.ref_resolution import RefResolutionService

logger = logging.getLogger(__name__)


class RefResolutionError(Exception):
    """Raised when ref resolution fails."""


class ProfileCompilationError(Exception):
    """Raised when profile compilation fails."""


class ProfileCompilationService:
    """Compiles profiles by resolving all refs and caching assets.

    Creates Python module structure for dynamic import with all referenced
    assets (agents, context, modules) fetched and organized into a standard
    directory layout.

    Compiled Structure:
        share/profiles/{collection-id}/{profile-name}/
          {profile-name}.md  (manifest from discovery)
          orchestrator/
            __init__.py
            (orchestrator files)
          agents/
            __init__.py
            agent1.md
          context/
            __init__.py
            doc1.md
          tools/
            __init__.py
          hooks/
            __init__.py
          providers/
            __init__.py
    """

    def __init__(self, share_dir: Path, ref_resolution: RefResolutionService):
        """Initialize with share directory and ref resolution service.

        Args:
            share_dir: Path to share directory (compiled profiles go here)
            ref_resolution: RefResolutionService for resolving refs
        """
        self.share_dir = Path(share_dir)
        self.profiles_dir = self.share_dir / "profiles"
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        self.ref_resolution = ref_resolution

    def _hash_profile_manifest(self, profile: ProfileDetails) -> str:
        """Hash profile manifest for change detection.

        Creates a stable hash of the profile manifest by serializing key fields
        that affect compilation output. Changes to profile definition will change
        the hash, triggering recompilation.

        Args:
            profile: ProfileDetails to hash

        Returns:
            SHA256 hex digest of manifest content
        """
        manifest_data = {
            "name": profile.name,
            "version": profile.version,
            "agents": sorted((profile.agents or {}).items()),  # Dict items for hashing
            "context": sorted((profile.context or {}).items()),  # Dict items for hashing
            "tools": [{"module": t.module, "source": t.source} for t in profile.tools],
            "hooks": [{"module": h.module, "source": h.source} for h in profile.hooks],
            "providers": [{"module": p.module, "source": p.source} for p in profile.providers],
        }

        # Add session orchestrator if present
        if profile.session and profile.session.orchestrator:
            manifest_data["orchestrator"] = {
                "module": profile.session.orchestrator.module,
                "source": profile.session.orchestrator.source,
            }

        # Add context manager if present
        if profile.session and profile.session.context_manager:
            manifest_data["context_manager"] = {
                "module": profile.session.context_manager.module,
                "source": profile.session.context_manager.source,
            }

        content = json.dumps(manifest_data, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()

    def compile_profile(self, collection_id: str, profile: ProfileDetails, force: bool = False) -> Path:
        """Compile profile by resolving all refs with change detection.

        Creates a staging directory for compilation, resolves all referenced
        assets (agents, context, module sources), and creates a Python module
        structure ready for dynamic import. On success, atomically renames
        staging to final location. On failure, cleans up staging directory.

        Uses hash-based change detection to skip compilation if profile manifest
        is unchanged and force=False. Saves compilation metadata for future checks.

        Args:
            collection_id: Collection identifier
            profile: ProfileDetails with refs to resolve
            force: If True, recompile even if manifest unchanged

        Returns:
            Path to compiled profile directory (share/profiles/{collection}/{profile-name}/)

        Side Effects:
            - Fetches and caches all referenced assets via RefResolutionService
            - Creates Python module structure with __init__.py files
            - Copies resolved assets into compilation directory
            - Uses staging directory for atomic compilation
            - Saves .compilation_meta.json for change detection

        Raises:
            RefResolutionError: If any ref cannot be resolved
            ProfileCompilationError: If compilation fails

        Atomicity Guarantee:
            Uses staging directory pattern - final compilation directory only
            exists if ALL assets resolved successfully. No partial state on failure.

        Example:
            >>> service = ProfileCompilationService(share_dir, ref_resolution)
            >>> compiled_path = service.compile_profile("mycollection", profile)
            >>> print(compiled_path)
            /path/to/share/profiles/mycollection/general/
        """
        logger.info(f"Compiling profile {collection_id}/{profile.name}")

        # Define final and staging paths
        final_dir = self.profiles_dir / collection_id / profile.name
        staging_dir = self.profiles_dir / collection_id / f".staging-{profile.name}"
        meta_file = final_dir / ".compilation_meta.json"

        # Check if recompilation needed via hash comparison
        if not force and meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text())
                current_hash = self._hash_profile_manifest(profile)

                if meta["manifest_hash"] == current_hash:
                    logger.info(f"Profile {collection_id}/{profile.name} unchanged, skipping compilation")
                    return final_dir
            except Exception as e:
                logger.warning(f"Failed to read compilation metadata: {e}, will recompile")

        # Create staging directory
        staging_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Created staging directory: {staging_dir}")

        try:
            # Initialize assets dictionary for all module types
            assets: dict[str, list[Path]] = {
                "orchestrator": [],
                "context-manager": [],  # Python module for context management
                "agents": [],
                "context": [],  # Embedded markdown context files
                "tools": [],
                "hooks": [],
                "providers": [],
            }

            # Resolve orchestrator module source (if present)
            if profile.session and profile.session.orchestrator.source:
                resolved_path = self._resolve_ref(profile.session.orchestrator.source, "orchestrator")
                assets["orchestrator"].append(resolved_path)
                logger.debug(f"Resolved orchestrator: {profile.session.orchestrator.module}")

            # Resolve context-manager module source (if present)
            if profile.session and profile.session.context_manager and profile.session.context_manager.source:
                resolved_path = self._resolve_ref(profile.session.context_manager.source, "context-manager")
                assets["context-manager"].append(resolved_path)
                logger.debug(f"Resolved context-manager: {profile.session.context_manager.module}")

            # Resolve agent refs (schema v2: dict of name -> file refs)
            if profile.agents:
                logger.debug(f"Resolving {len(profile.agents)} agent refs")
                for agent_name, agent_ref in profile.agents.items():
                    try:
                        resolved_path = self._resolve_ref(agent_ref, "agent")
                        assets["agents"].append(resolved_path)
                        logger.debug(f"Resolved agent '{agent_name}': {agent_ref}")
                    except RefResolutionError as e:
                        logger.error(f"Failed to resolve agent ref '{agent_ref}' for '{agent_name}': {e}")
                        raise

            # Resolve context refs (schema v2: dict of name -> directory refs)
            if profile.context:
                logger.debug(f"Resolving {len(profile.context)} context directory refs")
                for _context_name, context_ref in profile.context.items():
                    try:
                        resolved_path = self._resolve_ref(context_ref, "context")

                        # Verify it's a directory
                        if not resolved_path.is_dir():
                            raise RefResolutionError(
                                f"Context ref must be a directory: {context_ref}\nResolved to: {resolved_path}"
                            )

                        assets["context"].append(resolved_path)
                        logger.debug(f"Resolved context directory: {context_ref}")
                    except RefResolutionError as e:
                        logger.error(f"Failed to resolve context ref '{context_ref}': {e}")
                        raise

            # Resolve tool module sources
            for tool in profile.tools:
                if tool.source:
                    resolved_path = self._resolve_ref(tool.source, "tool")
                    assets["tools"].append(resolved_path)

            # Resolve hook module sources
            for hook in profile.hooks:
                if hook.source:
                    resolved_path = self._resolve_ref(hook.source, "hook")
                    assets["hooks"].append(resolved_path)

            # Resolve provider module sources
            for provider in profile.providers:
                if provider.source:
                    resolved_path = self._resolve_ref(provider.source, "provider")
                    assets["providers"].append(resolved_path)

            # Create Python module structure in STAGING directory
            self._create_module_structure(staging_dir, assets, profile)

            # Copy the cached manifest file from discovery cache into staging
            # The manifest is preserved by the discovery service and must exist in the final compiled profile
            manifest_source = self.profiles_dir / collection_id / profile.name / f"{profile.name}.md"
            if manifest_source.exists():
                manifest_dest = staging_dir / f"{profile.name}.md"
                shutil.copy2(manifest_source, manifest_dest)
                logger.debug(f"Copied profile manifest to staging: {profile.name}.md")
            else:
                logger.warning(f"Profile manifest not found in discovery cache: {manifest_source}")

            # Atomic rename: staging -> final (only happens if we got here without exception)
            # Remove existing directory if present (profiles are fully regenerated on sync)
            if final_dir.exists():
                logger.debug(f"Removing existing directory: {final_dir}")
                shutil.rmtree(final_dir)
            logger.debug(f"Compilation successful, atomically renaming {staging_dir} -> {final_dir}")
            staging_dir.rename(final_dir)

            # Save compilation metadata for change detection
            metadata = {
                "manifest_hash": self._hash_profile_manifest(profile),
                "compiled_at": datetime.now().isoformat(),
                "source_commit": "main",
            }
            meta_file_final = final_dir / ".compilation_meta.json"
            meta_file_final.write_text(json.dumps(metadata, indent=2))
            logger.debug(f"Saved compilation metadata: {meta_file_final}")

            logger.info(f"Successfully compiled profile: {collection_id}/{profile.name} → {final_dir}")
            return final_dir

        except Exception as e:
            # Cleanup staging directory on failure - no partial state left behind
            logger.error(f"Compilation failed for {collection_id}/{profile.name}: {e}")
            if staging_dir.exists():
                logger.debug(f"Cleaning up staging directory: {staging_dir}")
                shutil.rmtree(staging_dir)
            raise ProfileCompilationError(f"Failed to compile profile {profile.name}: {e}") from e

    def _resolve_ref(self, ref: str, ref_type: str) -> Path:
        """Resolve reference with profile-specific error context.

        Args:
            ref: Reference string (git+URL, absolute path, fsspec)
            ref_type: Type of ref for error messages (agent, context, module)

        Returns:
            Path to resolved asset

        Raises:
            RefResolutionError: If resolution fails with profile context
        """
        try:
            return self.ref_resolution.resolve_ref(ref)
        except RefResolutionError as e:
            raise RefResolutionError(f"Failed to resolve {ref_type} reference '{ref}': {e}") from e

    def _create_module_structure(
        self, target_dir: Path, assets: dict[str, list[Path]], profile_spec: ProfileDetails
    ) -> None:
        """Create Python module structure using profile names from profile spec.

        For each module type:
        1. Get module name from profile spec
        2. Create directory: {mount_type}/{module_name}/
        3. Copy module package into that directory

        Args:
            target_dir: Staging directory for compilation
            assets: Dict of resolved asset paths from cache
            profile_spec: Profile details with module names

        Side Effects:
            - Creates directory structure using profile names
            - Copies module packages from cache
            - Creates __init__.py files

        Structure Created:
            target_dir/
              __init__.py
              orchestrator/
                loop-streaming/              ← Profile name
                  amplifier_module_loop_streaming/
              context/
                context-simple/              ← Profile name
                  amplifier_module_context_simple/
              providers/
                provider-anthropic/          ← Profile name
                  amplifier_module_provider_anthropic/
        """
        # Create root __init__.py
        root_init = target_dir / "__init__.py"
        root_init.write_text('"""Compiled profile module."""\n')
        logger.debug(f"Created {root_init}")

        # Process session.orchestrator
        orchestrator_dir = target_dir / "orchestrator"
        orchestrator_dir.mkdir(exist_ok=True)
        (orchestrator_dir / "__init__.py").write_text('"""Orchestrator assets."""\n')

        if assets.get("orchestrator") and profile_spec.session:
            module_name = profile_spec.session.orchestrator.module
            source_path = assets["orchestrator"][0]

            dest_dir = orchestrator_dir / module_name
            dest_dir.mkdir(parents=True, exist_ok=True)

            # Copy module package
            self._copy_module_package(source_path, dest_dir)
            logger.debug(f"Created orchestrator/{module_name}/ with module package")

        # Process session.context-manager (note: context directory might also be used for context files)
        if assets.get("context-manager") and profile_spec.session and profile_spec.session.context_manager:
            module_name = profile_spec.session.context_manager.module
            source_path = assets["context-manager"][0]

            context_dir = target_dir / "context"
            context_dir.mkdir(exist_ok=True)
            # Create __init__.py if not already created
            init_file = context_dir / "__init__.py"
            if not init_file.exists():
                init_file.write_text('"""Context assets."""\n')

            dest_dir = context_dir / module_name
            dest_dir.mkdir(parents=True, exist_ok=True)

            # Copy module package
            self._copy_module_package(source_path, dest_dir)
            logger.debug(f"Created context/{module_name}/ with module package")

        # Process agents (list of file refs)
        if assets.get("agents"):
            agents_dir = target_dir / "agents"
            agents_dir.mkdir(exist_ok=True)

            # Create __init__.py
            (agents_dir / "__init__.py").write_text('"""Agent assets."""\n')

            # Copy agent files
            for agent_path in assets["agents"]:
                if agent_path.is_file():
                    dest = agents_dir / agent_path.name
                    shutil.copy2(agent_path, dest)
                    logger.debug(f"Copied agent {agent_path.name} to agents/")

        # Process contexts (dict of name -> directory refs)
        if assets.get("context") and profile_spec.context:
            contexts_dir = target_dir / "contexts"  # Plural!
            contexts_dir.mkdir(exist_ok=True)
            (contexts_dir / "__init__.py").write_text('"""Context documentation assets."""\n')

            # Copy context directories using names from profile spec
            context_names = list(profile_spec.context.keys())
            for context_name, context_path in zip(context_names, assets["context"], strict=False):
                if context_path.is_dir():
                    dest = contexts_dir / context_name  # Use profile's context name!

                    def ignore_non_essential(dir: str, files: list[str]) -> set[str]:
                        """Ignore .git, __pycache__, .venv, and other non-essential directories."""
                        return {name for name in files if name in {".git", "__pycache__", ".venv", "node_modules"}}

                    shutil.copytree(context_path, dest, dirs_exist_ok=True, ignore=ignore_non_essential)
                    logger.debug(f"Copied context directory to contexts/{context_name}/")

        # Process providers, tools, hooks (lists)
        for module_type in ["providers", "tools", "hooks"]:
            if not assets.get(module_type):
                # Create empty directories for consistency
                type_dir = target_dir / module_type
                type_dir.mkdir(exist_ok=True)
                (type_dir / "__init__.py").write_text(f'"""{module_type.capitalize()} assets."""\n')
                logger.debug(f"Created empty {module_type}/ directory")
                continue

            type_dir = target_dir / module_type
            type_dir.mkdir(exist_ok=True)

            # Create __init__.py
            (type_dir / "__init__.py").write_text(f'"""{module_type.capitalize()} assets."""\n')

            # Get module list from profile spec
            module_list = getattr(profile_spec, module_type, [])

            # Match assets to modules by index (assets are in same order as profile spec)
            for module_config, source_path in zip(module_list, assets[module_type], strict=False):
                module_name = module_config.module

                dest_dir = type_dir / module_name
                dest_dir.mkdir(parents=True, exist_ok=True)

                # Copy module package
                self._copy_module_package(source_path, dest_dir)
                logger.debug(f"Created {module_type}/{module_name}/ with module package")

        logger.info(f"Created Python module structure at {target_dir}")

    def _copy_module_package(self, source_path: Path, dest_dir: Path) -> None:
        """Copy module package from cache to destination.

        Handles both:
        - Directories: Copy entire tree (e.g., amplifier_module_*/ directory)
        - Files: Copy single file (e.g., agent.md)

        Args:
            source_path: Path in cache (may be hash directory or package directly)
            dest_dir: Destination directory
        """
        if source_path.is_dir():
            # Find the amplifier_module_* package inside (if in hash directory)
            package_dirs = list(source_path.glob("amplifier_module_*"))

            if package_dirs:
                # Copy the package directory
                package_dir = package_dirs[0]
                dest_package = dest_dir / package_dir.name
                shutil.copytree(
                    package_dir,
                    dest_package,
                    dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns(".git", "__pycache__", ".venv", "node_modules"),
                )
                logger.debug(f"Copied module package {package_dir.name}/ to {dest_dir}/")
            else:
                # Might be the package itself
                if source_path.name.startswith("amplifier_module_"):
                    dest_package = dest_dir / source_path.name
                    shutil.copytree(
                        source_path,
                        dest_package,
                        dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns(".git", "__pycache__", ".venv", "node_modules"),
                    )
                    logger.debug(f"Copied module package {source_path.name}/ to {dest_dir}/")
                else:
                    logger.warning(f"No amplifier_module_* package found in {source_path}")
        elif source_path.is_file():
            # Single file (agents, context markdown)
            shutil.copy2(source_path, dest_dir / source_path.name)
            logger.debug(f"Copied file {source_path.name} to {dest_dir}/")
