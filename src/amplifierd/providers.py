"""Provider configuration loading and injection.

Reads provider config from ~/.amplifier/settings.yaml (same source as amplifier-app-cli)
and injects it into PreparedBundle before session creation.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_ENV_PATTERN = re.compile(r"\$\{([^}:]+)(?::([^}]*))?}")


def load_provider_config(home: Path | None = None) -> list[dict[str, Any]]:
    """Load provider configuration from ~/.amplifier/settings.yaml.

    Args:
        home: Amplifier home directory. Falls back to AMPLIFIER_HOME env var,
              then ~/.amplifier.

    Returns:
        List of provider config dicts from config.providers, or empty list.
    """
    if home is None:
        home = Path(os.environ.get("AMPLIFIER_HOME", Path.home() / ".amplifier"))
    settings_path = home / "settings.yaml"
    if not settings_path.is_file():
        logger.debug("No settings file at %s", settings_path)
        return []
    try:
        data = yaml.safe_load(settings_path.read_text()) or {}
    except Exception:
        logger.warning("Failed to read %s", settings_path, exc_info=True)
        return []
    providers = data.get("config", {}).get("providers", [])
    if not isinstance(providers, list):
        return []
    logger.info(
        "Loaded %d provider(s) from %s: %s",
        len(providers),
        settings_path,
        [p.get("module", "?") for p in providers if isinstance(p, dict)],
    )
    return providers


def expand_env_vars(value: Any) -> Any:
    """Recursively expand ${VAR} and ${VAR:default} references in config values.

    After expansion, dict entries whose values are empty strings are removed.
    This prevents empty env vars (e.g. ANTHROPIC_BASE_URL='') from overriding
    provider defaults with blank values.
    """
    if isinstance(value, str):
        return _ENV_PATTERN.sub(
            lambda m: os.environ.get(m.group(1), m.group(2) if m.group(2) is not None else ""),
            value,
        )
    if isinstance(value, dict):
        expanded = {k: expand_env_vars(v) for k, v in value.items()}
        return {k: v for k, v in expanded.items() if v != ""}
    if isinstance(value, list):
        return [expand_env_vars(item) for item in value]
    return value


def inject_providers(prepared: Any, providers: list[dict[str, Any]]) -> None:
    """Inject provider config into a PreparedBundle.

    Sets both mount_plan["providers"] (for root sessions) and
    bundle.providers (for child/spawned sessions).

    Args:
        prepared: A PreparedBundle instance.
        providers: Provider config list from load_provider_config().
    """
    if not providers:
        return

    expanded = expand_env_vars(providers)

    # Merge with any existing bundle providers (settings override by module ID)
    existing = prepared.mount_plan.get("providers", [])
    if existing:
        by_module: dict[str, dict[str, Any]] = {
            p["module"]: p for p in existing if isinstance(p, dict) and "module" in p
        }
        for p in expanded:
            if isinstance(p, dict) and "module" in p:
                by_module[p["module"]] = p
        expanded = list(by_module.values())

    prepared.mount_plan["providers"] = expanded

    # Sync to bundle dataclass for child sessions (spawned via PreparedBundle.spawn())
    bundle = getattr(prepared, "bundle", None)
    if bundle is not None and hasattr(bundle, "providers"):
        bundle.providers = list(expanded)
