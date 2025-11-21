"""JSON-based storage with atomic writes and retry logic.

This module provides simple JSON persistence with:
- Atomic writes using temp files
- Retry logic for cloud sync scenarios (OneDrive, Dropbox, etc.)
- Category-based organization (sessions, config, etc.)
- Error recovery and logging

Contract:
- Inputs: Storage keys, data dictionaries, category names
- Outputs: Loaded data, write confirmations
- Side Effects: Creates/updates JSON files in share directory
"""

import contextlib
import json
import logging
import time
from pathlib import Path
from typing import Any

from .paths import get_share_dir

logger = logging.getLogger(__name__)

# Retry configuration for cloud sync scenarios
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 0.5  # seconds


def _get_category_dir(category: str) -> Path:
    """Get directory for a storage category.

    Args:
        category: Category name (e.g., "sessions", "config")

    Returns:
        Path to category directory

    Example:
        >>> cat_dir = _get_category_dir("sessions")
        >>> assert cat_dir.parent == get_share_dir()
    """
    cat_dir = get_share_dir() / category
    cat_dir.mkdir(parents=True, exist_ok=True)
    return cat_dir


def _sanitize_for_json(obj: Any) -> Any:
    """Sanitize object for JSON serialization.

    Handles common non-serializable types by converting them to
    JSON-compatible representations.

    Args:
        obj: Object to sanitize

    Returns:
        JSON-serializable object

    Example:
        >>> from datetime import datetime
        >>> dt = datetime(2025, 1, 1)
        >>> result = _sanitize_for_json({"time": dt})
        >>> assert isinstance(result["time"], str)
    """
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [_sanitize_for_json(item) for item in obj]
    if hasattr(obj, "isoformat"):  # datetime objects
        return obj.isoformat()
    if hasattr(obj, "__dict__"):  # dataclass or custom objects
        return _sanitize_for_json(obj.__dict__)
    return obj


def save_json(key: str, data: dict[str, Any], category: str = "sessions") -> None:
    """Save data to JSON file with atomic write.

    Uses temp file + rename for atomic write. Includes retry logic
    for cloud sync scenarios (OneDrive, Dropbox, etc.).

    Args:
        key: Storage key (becomes filename)
        data: Data to save
        category: Storage category (default: "sessions")

    Raises:
        OSError: If write fails after retries
        ValueError: If key is invalid

    Example:
        >>> save_json("test-session", {"id": "123", "data": "value"})
        >>> loaded = load_json("test-session")
        >>> assert loaded["id"] == "123"
    """
    if not key or "/" in key or "\\" in key:
        raise ValueError(f"Invalid storage key: {key}")

    cat_dir = _get_category_dir(category)
    target_path = cat_dir / f"{key}.json"
    temp_path = cat_dir / f"{key}.json.tmp"

    # Sanitize data for JSON serialization
    sanitized_data = _sanitize_for_json(data)

    retry_delay = INITIAL_RETRY_DELAY
    for attempt in range(MAX_RETRIES):
        try:
            # Write to temp file
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(sanitized_data, f, indent=2, ensure_ascii=False)
                f.flush()

            # Atomic rename
            temp_path.replace(target_path)
            logger.debug(f"Saved {category}/{key}.json")
            return

        except OSError as e:
            if e.errno == 5 and attempt < MAX_RETRIES - 1:
                if attempt == 0:
                    logger.warning(
                        f"File I/O error writing to {target_path} - retrying. "
                        "This may be due to cloud-synced files (OneDrive, Dropbox, etc.). "
                        "If using cloud sync, consider enabling 'Always keep on this device' "
                        f"for the data folder: {target_path.parent}"
                    )
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                logger.error(f"Failed to save {category}/{key}.json after {attempt + 1} attempts")
                raise
        finally:
            # Clean up temp file if it exists
            if temp_path.exists():
                with contextlib.suppress(Exception):
                    temp_path.unlink()


def load_json(key: str, category: str = "sessions") -> dict[str, Any]:
    """Load data from JSON file with error recovery.

    Args:
        key: Storage key (filename without .json)
        category: Storage category (default: "sessions")

    Returns:
        Loaded data dictionary

    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If file is corrupted

    Example:
        >>> save_json("test-session", {"id": "123"})
        >>> data = load_json("test-session")
        >>> assert data["id"] == "123"
    """
    if not key or "/" in key or "\\" in key:
        raise ValueError(f"Invalid storage key: {key}")

    cat_dir = _get_category_dir(category)
    file_path = cat_dir / f"{key}.json"

    if not file_path.exists():
        raise FileNotFoundError(f"Storage file not found: {category}/{key}.json")

    retry_delay = INITIAL_RETRY_DELAY
    for attempt in range(MAX_RETRIES):
        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)
            logger.debug(f"Loaded {category}/{key}.json")
            return data

        except OSError as e:
            if e.errno == 5 and attempt < MAX_RETRIES - 1:
                if attempt == 0:
                    logger.warning(
                        f"File I/O error reading from {file_path} - retrying. This may be due to cloud-synced files."
                    )
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                logger.error(f"Failed to load {category}/{key}.json after {attempt + 1} attempts")
                raise

    raise RuntimeError(f"Failed to load {category}/{key}.json after all retries")


def list_stored(pattern: str = "*", category: str = "sessions") -> list[str]:
    """List stored items matching pattern.

    Args:
        pattern: Glob pattern (default: "*" for all)
        category: Storage category (default: "sessions")

    Returns:
        List of storage keys (without .json extension)

    Example:
        >>> save_json("test-1", {"id": "1"})
        >>> save_json("test-2", {"id": "2"})
        >>> keys = list_stored("test-*")
        >>> assert len(keys) == 2
    """
    cat_dir = _get_category_dir(category)
    pattern_with_ext = f"{pattern}.json"

    files = sorted(cat_dir.glob(pattern_with_ext))
    return [f.stem for f in files]


def delete_stored(key: str, category: str = "sessions") -> None:
    """Delete stored item.

    Args:
        key: Storage key
        category: Storage category (default: "sessions")

    Raises:
        FileNotFoundError: If file doesn't exist

    Example:
        >>> save_json("test-delete", {"id": "123"})
        >>> delete_stored("test-delete")
        >>> # File is now deleted
    """
    if not key or "/" in key or "\\" in key:
        raise ValueError(f"Invalid storage key: {key}")

    cat_dir = _get_category_dir(category)
    file_path = cat_dir / f"{key}.json"

    if not file_path.exists():
        raise FileNotFoundError(f"Storage file not found: {category}/{key}.json")

    file_path.unlink()
    logger.debug(f"Deleted {category}/{key}.json")


def exists(key: str, category: str = "sessions") -> bool:
    """Check if stored item exists.

    Args:
        key: Storage key
        category: Storage category (default: "sessions")

    Returns:
        True if file exists, False otherwise

    Example:
        >>> assert not exists("nonexistent")
        >>> save_json("exists-test", {"id": "123"})
        >>> assert exists("exists-test")
    """
    if not key or "/" in key or "\\" in key:
        return False

    cat_dir = _get_category_dir(category)
    file_path = cat_dir / f"{key}.json"
    return file_path.exists()
