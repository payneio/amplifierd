# amplifierd Implementation Plan

> **Execution:** Use the subagent-driven-development workflow to implement this plan.

**Goal:** Build `amplifierd`, a long-running localhost daemon that exposes amplifier-core and amplifier-foundation capabilities over HTTP, SSE, and WebSocket.

**Architecture:** FastAPI + uvicorn daemon with in-memory `SessionManager` (per-session serialized execution queue), global `EventBus` (async pub/sub with session-tree propagation), and filesystem persistence. All state accessed via `app.state` — no module-level singletons. Plugin system via Python entry points.

**Tech Stack:** Python 3.12, FastAPI, uvicorn, pydantic / pydantic-settings, sse-starlette, click, amplifier-core, amplifier-foundation, httpx (tests), pytest + pytest-asyncio (tests)

---

## Phase 1: Scaffold & Foundation

### Task 1: Project Skeleton

**Files:**
- Create: `amplifier-distro/amplifierd/pyproject.toml`
- Create: `amplifier-distro/amplifierd/src/amplifierd/__init__.py`
- Create: `amplifier-distro/amplifierd/src/amplifierd/__main__.py`
- Create: `amplifier-distro/amplifierd/src/amplifierd/state/__init__.py`
- Create: `amplifier-distro/amplifierd/src/amplifierd/models/__init__.py`
- Create: `amplifier-distro/amplifierd/src/amplifierd/routes/__init__.py`
- Create: `amplifier-distro/amplifierd/tests/__init__.py`
- Create: `amplifier-distro/amplifierd/tests/conftest.py`

**Step 1: Create `pyproject.toml`**

Create `amplifier-distro/amplifierd/pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "amplifierd"
version = "0.1.0"
description = "Amplifier daemon - HTTP/SSE/WebSocket API for amplifier-core and amplifier-foundation"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "pydantic>=2.10.0",
    "pydantic-settings>=2.6.0",
    "sse-starlette>=2.2.1",
    "click>=8.1.0",
    "amplifier-core",
    "amplifier-foundation",
]

[project.scripts]
amplifierd = "amplifierd.cli:main"

[tool.setuptools.packages.find]
where = ["src"]
include = ["amplifierd*"]

[dependency-groups]
dev = [
    "httpx>=0.28.1",
    "pytest>=8.3.5",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=6.1.1",
    "pyright>=1.1.407",
    "ruff>=0.11.10",
]

[tool.pyright]
venvPath = "."
venv = ".venv"
typeCheckingMode = "basic"
pythonVersion = "3.12"

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = [
    "-v",
    "--tb=short",
    "--strict-markers",
    "--import-mode=importlib",
]
asyncio_mode = "auto"
markers = [
    "unit: Unit tests for state and models",
    "integration: Integration tests for routes",
    "smoke: Smoke tests requiring real provider (AMPLIFIERD_SMOKE_TEST=1)",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP"]
```

**Step 2: Create package files**

Create `amplifier-distro/amplifierd/src/amplifierd/__init__.py`:

```python
"""amplifierd - Amplifier daemon exposing core + foundation over HTTP/SSE/WebSocket."""

from __future__ import annotations

__version__ = "0.1.0"
```

Create `amplifier-distro/amplifierd/src/amplifierd/__main__.py`:

```python
"""Support `python -m amplifierd`."""

from __future__ import annotations

from amplifierd.cli import main

main()
```

Create `amplifier-distro/amplifierd/src/amplifierd/state/__init__.py`:

```python
"""State management: SessionManager, EventBus, SessionHandle."""

from __future__ import annotations
```

Create `amplifier-distro/amplifierd/src/amplifierd/models/__init__.py`:

```python
"""Pydantic request/response models."""

from __future__ import annotations
```

Create `amplifier-distro/amplifierd/src/amplifierd/routes/__init__.py`:

```python
"""FastAPI route modules."""

from __future__ import annotations
```

Create `amplifier-distro/amplifierd/tests/__init__.py`:

```python
```

Create `amplifier-distro/amplifierd/tests/conftest.py`:

```python
"""Shared test fixtures for amplifierd."""

from __future__ import annotations
```

**Step 3: Verify the package installs**

Run from `amplifier-distro/amplifierd/`:
```bash
cd amplifier-distro/amplifierd && uv pip install -e ".[dev]"
```
Expected: Installs successfully, `amplifierd` command is available.

Run:
```bash
python -c "import amplifierd; print(amplifierd.__version__)"
```
Expected: `0.1.0`

**Step 4: Commit**
```bash
cd amplifier-distro/amplifierd && git add -A && git commit -m "feat(amplifierd): project skeleton with pyproject.toml and package layout"
```

---

### Task 2: Daemon Configuration (`config.py`)

**Files:**
- Create: `amplifier-distro/amplifierd/src/amplifierd/config.py`
- Create: `amplifier-distro/amplifierd/tests/test_config.py`

**Step 1: Write the failing test**

Create `amplifier-distro/amplifierd/tests/test_config.py`:

```python
"""Tests for DaemonSettings configuration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from amplifierd.config import DaemonSettings


class TestDaemonSettings:
    """Test DaemonSettings loading and priority."""

    def test_defaults(self) -> None:
        """Settings have correct defaults when no config file or env vars exist."""
        settings = DaemonSettings()
        assert settings.host == "127.0.0.1"
        assert settings.port == 8410
        assert settings.default_working_dir is None
        assert settings.log_level == "info"
        assert settings.disabled_plugins == []

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Environment variables override defaults."""
        monkeypatch.setenv("AMPLIFIERD_PORT", "9999")
        monkeypatch.setenv("AMPLIFIERD_HOST", "0.0.0.0")
        monkeypatch.setenv("AMPLIFIERD_LOG_LEVEL", "debug")
        settings = DaemonSettings()
        assert settings.port == 9999
        assert settings.host == "0.0.0.0"
        assert settings.log_level == "debug"

    def test_json_settings_file(self, tmp_path: Path) -> None:
        """Settings file is read when it exists."""
        settings_dir = tmp_path / ".amplifierd"
        settings_dir.mkdir()
        settings_file = settings_dir / "settings.json"
        settings_file.write_text(json.dumps({
            "port": 7777,
            "default_working_dir": "/home/testuser/projects",
            "disabled_plugins": ["voice"],
        }))
        settings = DaemonSettings(_settings_dir=settings_dir)
        assert settings.port == 7777
        assert settings.default_working_dir == Path("/home/testuser/projects")
        assert settings.disabled_plugins == ["voice"]

    def test_env_overrides_json_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Env vars take priority over settings.json."""
        settings_dir = tmp_path / ".amplifierd"
        settings_dir.mkdir()
        settings_file = settings_dir / "settings.json"
        settings_file.write_text(json.dumps({"port": 7777}))
        monkeypatch.setenv("AMPLIFIERD_PORT", "1234")
        settings = DaemonSettings(_settings_dir=settings_dir)
        assert settings.port == 1234

    def test_missing_settings_file_uses_defaults(self, tmp_path: Path) -> None:
        """Missing settings file is not an error — defaults are used."""
        settings_dir = tmp_path / ".amplifierd"
        # Don't create the directory — it shouldn't exist yet.
        settings = DaemonSettings(_settings_dir=settings_dir)
        assert settings.port == 8410
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd amplifier-distro/amplifierd && python -m pytest tests/test_config.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'amplifierd.config'`

**Step 3: Write the implementation**

Create `amplifier-distro/amplifierd/src/amplifierd/config.py`:

```python
"""Daemon configuration via pydantic-settings.

Priority (highest wins):
    1. CLI flags (applied by cli.py after loading)
    2. Environment variables (AMPLIFIERD_ prefix)
    3. Settings file (~/.amplifierd/settings.json)
    4. Built-in defaults
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource

logger = logging.getLogger(__name__)

_DEFAULT_SETTINGS_DIR = Path.home() / ".amplifierd"


class JsonFileSettingsSource(PydanticBaseSettingsSource):
    """Load settings from ~/.amplifierd/settings.json."""

    def __init__(self, settings_cls: type[BaseSettings], settings_dir: Path) -> None:
        super().__init__(settings_cls)
        self._settings_dir = settings_dir

    def get_field_value(
        self, field: Any, field_name: str
    ) -> tuple[Any, str, bool]:
        # Not used — we override __call__ instead.
        return None, field_name, False  # pragma: no cover

    def __call__(self) -> dict[str, Any]:
        settings_file = self._settings_dir / "settings.json"
        if not settings_file.exists():
            return {}
        try:
            text = settings_file.read_text(encoding="utf-8")
            data = json.loads(text)
            if not isinstance(data, dict):
                logger.warning("settings.json is not a JSON object, ignoring")
                return {}
            return data
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to read settings.json: %s", exc)
            return {}


class DaemonSettings(BaseSettings):
    """amplifierd daemon settings."""

    host: str = Field(default="127.0.0.1", description="Bind host address")
    port: int = Field(default=8410, description="Bind port")
    default_working_dir: Path | None = Field(
        default=None,
        description="Default working directory for new sessions",
    )
    log_level: str = Field(default="info", description="Log level")
    disabled_plugins: list[str] = Field(
        default_factory=list,
        description="Plugin names to skip during discovery",
    )

    # Internal: allow tests to override the settings directory.
    _settings_dir: Path = _DEFAULT_SETTINGS_DIR

    model_config = {"env_prefix": "AMPLIFIERD_"}

    def __init__(self, _settings_dir: Path | None = None, **kwargs: Any) -> None:
        if _settings_dir is not None:
            # Store for use by settings_customise_sources before super().__init__.
            self.__dict__["_settings_dir"] = _settings_dir
        super().__init__(**kwargs)
        if _settings_dir is not None:
            self._settings_dir = _settings_dir

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Priority: init kwargs > env vars > JSON file > defaults."""
        # We need to get the settings_dir from the init_settings if available.
        # Use the class-level default; __init__ will override for tests.
        settings_dir = _DEFAULT_SETTINGS_DIR
        return (
            init_settings,
            env_settings,
            JsonFileSettingsSource(settings_cls, settings_dir),
        )
```

**Step 4: Run tests to verify they pass**

Run:
```bash
cd amplifier-distro/amplifierd && python -m pytest tests/test_config.py -v
```
Expected: All 5 tests PASS.

**Step 5: Commit**
```bash
cd amplifier-distro/amplifierd && git add -A && git commit -m "feat(amplifierd): DaemonSettings with JSON file + env var support"
```

---

### Task 3: Pydantic Models — Common & Errors

**Files:**
- Create: `amplifier-distro/amplifierd/src/amplifierd/models/common.py`
- Create: `amplifier-distro/amplifierd/src/amplifierd/models/errors.py`
- Create: `amplifier-distro/amplifierd/tests/test_models.py`

**Step 1: Write the failing test**

Create `amplifier-distro/amplifierd/tests/test_models.py`:

```python
"""Tests for Pydantic request/response models."""

from __future__ import annotations

from amplifierd.models.common import ProblemDetail
from amplifierd.models.errors import ErrorTypeURI


class TestProblemDetail:
    """Test RFC 7807 Problem Details model."""

    def test_minimal(self) -> None:
        pd = ProblemDetail(
            type="https://amplifier.dev/errors/rate-limit",
            title="Rate Limit Exceeded",
            status=429,
            detail="Too many requests",
            instance="/sessions/abc/execute",
        )
        assert pd.status == 429
        assert pd.retryable is None

    def test_with_llm_fields(self) -> None:
        pd = ProblemDetail(
            type="https://amplifier.dev/errors/rate-limit",
            title="Rate Limit Exceeded",
            status=429,
            detail="Hit rate limit",
            instance="/sessions/abc/execute",
            retryable=True,
            retry_after_seconds=30.0,
            provider="anthropic",
            model="claude-sonnet-4-20250514",
            error_class="RateLimitError",
        )
        dumped = pd.model_dump(exclude_none=True)
        assert dumped["retry_after_seconds"] == 30.0
        assert dumped["provider"] == "anthropic"


class TestErrorTypeURI:
    """Test error type URI constants."""

    def test_rate_limit_uri(self) -> None:
        assert ErrorTypeURI.RATE_LIMIT == "https://amplifier.dev/errors/rate-limit"

    def test_session_not_found_uri(self) -> None:
        assert ErrorTypeURI.SESSION_NOT_FOUND == "https://amplifier.dev/errors/session-not-found"
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd amplifier-distro/amplifierd && python -m pytest tests/test_models.py -v
```
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write the implementation**

Create `amplifier-distro/amplifierd/src/amplifierd/models/common.py`:

```python
"""Common Pydantic models used across routes."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProblemDetail(BaseModel):
    """RFC 7807 Problem Details error response.

    Every error from amplifierd uses this shape, whether returned as
    an HTTP JSON body, an SSE `event: error` frame, or a WebSocket error message.
    """

    type: str = Field(..., description="URI identifying the error type")
    title: str = Field(..., description="Short human-readable summary")
    status: int = Field(..., description="HTTP status code")
    detail: str = Field(..., description="Human-readable explanation of this occurrence")
    instance: str = Field(..., description="Request path that triggered the error")

    # LLM error extensions
    retryable: bool | None = Field(default=None, description="Whether the client should retry")
    retry_after_seconds: float | None = Field(
        default=None, description="Seconds to wait before retrying"
    )
    provider: str | None = Field(default=None, description="LLM provider name")
    model: str | None = Field(default=None, description="LLM model identifier")
    error_class: str | None = Field(default=None, description="Python exception class name")
    upstream_status: int | None = Field(
        default=None, description="HTTP status from upstream provider"
    )

    # InvalidToolCallError extensions
    tool_name: str | None = Field(default=None, description="Tool that caused the error")
    raw_arguments: str | None = Field(default=None, description="Raw tool call arguments")
```

Create `amplifier-distro/amplifierd/src/amplifierd/models/errors.py`:

```python
"""Error type URI constants and mapping tables."""

from __future__ import annotations

_BASE = "https://amplifier.dev/errors"


class ErrorTypeURI:
    """Canonical error type URIs for RFC 7807 Problem Details."""

    # LLM errors (provider-originated)
    RATE_LIMIT: str = f"{_BASE}/rate-limit"
    QUOTA_EXCEEDED: str = f"{_BASE}/quota-exceeded"
    PROVIDER_AUTH: str = f"{_BASE}/provider-auth"
    PROVIDER_ACCESS_DENIED: str = f"{_BASE}/provider-access-denied"
    CONTEXT_TOO_LARGE: str = f"{_BASE}/context-too-large"
    CONTENT_FILTERED: str = f"{_BASE}/content-filtered"
    INVALID_REQUEST: str = f"{_BASE}/invalid-request"
    PROVIDER_UNAVAILABLE: str = f"{_BASE}/provider-unavailable"
    NETWORK_ERROR: str = f"{_BASE}/network-error"
    PROVIDER_TIMEOUT: str = f"{_BASE}/provider-timeout"
    PROVIDER_NOT_FOUND: str = f"{_BASE}/provider-not-found"
    STREAM_ERROR: str = f"{_BASE}/stream-error"
    ABORTED: str = f"{_BASE}/aborted"
    INVALID_TOOL_CALL: str = f"{_BASE}/invalid-tool-call"
    CONFIGURATION_ERROR: str = f"{_BASE}/configuration-error"
    LLM_ERROR: str = f"{_BASE}/llm-error"

    # Bundle errors (foundation-originated)
    BUNDLE_NOT_FOUND: str = f"{_BASE}/bundle-not-found"
    BUNDLE_LOAD_ERROR: str = f"{_BASE}/bundle-load-error"
    BUNDLE_VALIDATION_ERROR: str = f"{_BASE}/bundle-validation-error"
    BUNDLE_DEPENDENCY_ERROR: str = f"{_BASE}/bundle-dependency-error"
    BUNDLE_ERROR: str = f"{_BASE}/bundle-error"

    # Module errors
    MODULE_NOT_FOUND: str = f"{_BASE}/module-not-found"
    MODULE_LOAD_ERROR: str = f"{_BASE}/module-load-error"
    MODULE_VALIDATION_ERROR: str = f"{_BASE}/module-validation-error"
    MODULE_ACTIVATION_ERROR: str = f"{_BASE}/module-activation-error"

    # Session errors (daemon-originated)
    SESSION_NOT_FOUND: str = f"{_BASE}/session-not-found"
    SESSION_NOT_RUNNING: str = f"{_BASE}/session-not-running"
    SESSION_ALREADY_EXISTS: str = f"{_BASE}/session-already-exists"
    EXECUTION_IN_PROGRESS: str = f"{_BASE}/execution-in-progress"
    APPROVAL_NOT_FOUND: str = f"{_BASE}/approval-not-found"
    APPROVAL_ALREADY_RESOLVED: str = f"{_BASE}/approval-already-resolved"
    APPROVAL_TIMEOUT: str = f"{_BASE}/approval-timeout"

    # Request validation
    VALIDATION_ERROR: str = f"{_BASE}/validation-error"
    MALFORMED_REQUEST: str = f"{_BASE}/malformed-request"
```

Update `amplifier-distro/amplifierd/src/amplifierd/models/__init__.py`:

```python
"""Pydantic request/response models."""

from __future__ import annotations

from amplifierd.models.common import ProblemDetail
from amplifierd.models.errors import ErrorTypeURI

__all__ = ["ErrorTypeURI", "ProblemDetail"]
```

**Step 4: Run tests to verify they pass**

Run:
```bash
cd amplifier-distro/amplifierd && python -m pytest tests/test_models.py -v
```
Expected: All tests PASS.

**Step 5: Commit**
```bash
cd amplifier-distro/amplifierd && git add -A && git commit -m "feat(amplifierd): ProblemDetail and ErrorTypeURI models"
```

---

### Task 4: Pydantic Models — Sessions, Bundles, Events, Agents, Modules

**Files:**
- Create: `amplifier-distro/amplifierd/src/amplifierd/models/sessions.py`
- Create: `amplifier-distro/amplifierd/src/amplifierd/models/bundles.py`
- Create: `amplifier-distro/amplifierd/src/amplifierd/models/events.py`
- Create: `amplifier-distro/amplifierd/src/amplifierd/models/agents.py`
- Create: `amplifier-distro/amplifierd/src/amplifierd/models/modules.py`
- Modify: `amplifier-distro/amplifierd/tests/test_models.py`

**Step 1: Write failing tests**

Append to `amplifier-distro/amplifierd/tests/test_models.py`:

```python
from amplifierd.models.sessions import (
    CreateSessionRequest,
    ExecuteRequest,
    ExecuteResponse,
    ExecuteStreamAccepted,
    PatchSessionRequest,
    SessionDetail,
    SessionSummary,
)


class TestSessionModels:
    def test_create_session_minimal(self) -> None:
        req = CreateSessionRequest(bundle="foundation")
        assert req.bundle == "foundation"
        assert req.working_dir is None
        assert req.session_id is None

    def test_create_session_full(self) -> None:
        req = CreateSessionRequest(
            bundle="foundation",
            bundle_uri="git+https://github.com/microsoft/amplifier-foundation@main",
            working_dir="/home/user/project",
            session_id="custom-id",
            config_overrides={"session": {"orchestrator": "loop-basic"}},
        )
        assert req.working_dir == "/home/user/project"

    def test_execute_request(self) -> None:
        req = ExecuteRequest(prompt="Hello world")
        assert req.prompt == "Hello world"
        assert req.metadata == {}

    def test_session_summary(self) -> None:
        summary = SessionSummary(
            session_id="abc123",
            status="idle",
            bundle="foundation",
            created_at="2026-03-02T11:30:00Z",
        )
        assert summary.session_id == "abc123"

    def test_execute_stream_accepted(self) -> None:
        resp = ExecuteStreamAccepted(
            correlation_id="prompt_abc_1",
            session_id="abc",
            status="accepted",
        )
        assert resp.correlation_id == "prompt_abc_1"

    def test_patch_session(self) -> None:
        req = PatchSessionRequest(working_dir="/new/path")
        assert req.working_dir == "/new/path"
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd amplifier-distro/amplifierd && python -m pytest tests/test_models.py::TestSessionModels -v
```
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write the implementation**

Create `amplifier-distro/amplifierd/src/amplifierd/models/sessions.py`:

```python
"""Session-related request/response models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    """POST /sessions request body."""

    bundle: str | None = Field(default=None, description="Registry bundle name")
    bundle_uri: str | None = Field(default=None, description="Direct bundle URI")
    session_id: str | None = Field(default=None, description="Custom session ID")
    parent_id: str | None = Field(default=None, description="Parent session ID for lineage")
    working_dir: str | None = Field(default=None, description="Absolute working directory path")
    config_overrides: dict[str, Any] = Field(
        default_factory=dict, description="Deep-merged into mount plan"
    )


class PatchSessionRequest(BaseModel):
    """PATCH /sessions/{id} request body."""

    working_dir: str | None = Field(default=None, description="New working directory")
    name: str | None = Field(default=None, description="Session display name")


class ResumeSessionRequest(BaseModel):
    """POST /sessions/{id}/resume request body."""

    session_dir: str | None = Field(
        default=None, description="Path to session directory on disk"
    )


class ExecuteRequest(BaseModel):
    """POST /sessions/{id}/execute request body."""

    prompt: str = Field(..., description="User prompt to execute")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Arbitrary metadata")


class CancelRequest(BaseModel):
    """POST /sessions/{id}/cancel request body."""

    immediate: bool = Field(default=False, description="Immediate vs graceful cancellation")


class ForkRequest(BaseModel):
    """POST /sessions/{id}/fork request body."""

    turn: int = Field(..., description="Turn number to fork at")
    handle_orphaned_tools: str = Field(
        default="complete", description="How to handle orphaned tool calls"
    )


class StaleRequest(BaseModel):
    """POST /sessions/{id}/stale request body (currently empty, extensible)."""

    pass


# --- Response models ---


class SessionSummary(BaseModel):
    """Lightweight session info for list endpoints."""

    session_id: str
    status: str
    bundle: str
    created_at: str
    last_activity: str | None = None
    total_messages: int = 0
    tool_invocations: int = 0
    parent_session_id: str | None = None
    stale: bool = False


class SessionDetail(BaseModel):
    """Full session details for GET /sessions/{id}."""

    session_id: str
    status: str
    parent_id: str | None = None
    bundle: str
    created_at: str
    last_activity: str | None = None
    working_dir: str | None = None
    stale: bool = False
    stats: dict[str, Any] = Field(default_factory=dict)
    mounted_modules: dict[str, Any] = Field(default_factory=dict)
    capabilities: list[str] = Field(default_factory=list)


class SessionListResponse(BaseModel):
    """GET /sessions response."""

    sessions: list[SessionSummary]
    total: int


class ExecuteResponse(BaseModel):
    """POST /sessions/{id}/execute response."""

    response: str
    usage: dict[str, Any] = Field(default_factory=dict)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    finish_reason: str = "end_turn"


class ExecuteStreamAccepted(BaseModel):
    """POST /sessions/{id}/execute/stream 202 response."""

    correlation_id: str
    session_id: str
    status: Literal["accepted"] = "accepted"


class CancelResponse(BaseModel):
    """POST /sessions/{id}/cancel response."""

    state: str
    running_tools: list[str] = Field(default_factory=list)


class CancelStatusResponse(BaseModel):
    """GET /sessions/{id}/cancel/status response."""

    state: str
    is_cancelled: bool
    is_graceful: bool
    is_immediate: bool
    running_tools: list[dict[str, str]] = Field(default_factory=list)


class SessionTreeNode(BaseModel):
    """A node in the session tree."""

    session_id: str
    agent: str | None = None
    status: str = "idle"
    children: list[SessionTreeNode] = Field(default_factory=list)


class ForkResponse(BaseModel):
    """POST /sessions/{id}/fork response."""

    session_id: str
    parent_id: str
    forked_from_turn: int
    message_count: int
```

Create `amplifier-distro/amplifierd/src/amplifierd/models/bundles.py`:

```python
"""Bundle-related request/response models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RegisterBundleRequest(BaseModel):
    """POST /bundles/register request body."""

    name: str = Field(..., description="Bundle name for the registry")
    uri: str = Field(..., description="Bundle source URI")


class LoadBundleRequest(BaseModel):
    """POST /bundles/load request body."""

    source: str = Field(..., description="Bundle source URI")


class PrepareBundleRequest(BaseModel):
    """POST /bundles/prepare request body."""

    source: str = Field(..., description="Bundle source URI or registry name")
    install_deps: bool = Field(default=True, description="Install module dependencies")


class ComposeBundlesRequest(BaseModel):
    """POST /bundles/compose request body."""

    bundles: list[str] = Field(..., description="List of bundle names or URIs to compose")
    overrides: dict[str, Any] = Field(default_factory=dict, description="Merge overrides")


class BundleSummary(BaseModel):
    """Bundle info for list endpoints."""

    name: str
    uri: str | None = None
    version: str = "unknown"
    loaded_at: str | None = None
    has_updates: bool = False


class BundleListResponse(BaseModel):
    """GET /bundles response."""

    bundles: list[BundleSummary]


class BundleDetail(BaseModel):
    """Detailed bundle info from POST /bundles/load."""

    name: str
    version: str
    description: str = ""
    includes: list[str] = Field(default_factory=list)
    providers: list[dict[str, Any]] = Field(default_factory=list)
    tools: list[dict[str, Any]] = Field(default_factory=list)
    hooks: list[dict[str, Any]] = Field(default_factory=list)
    agents: dict[str, Any] = Field(default_factory=dict)
    context_files: list[str] = Field(default_factory=list)


class BundleUpdateCheck(BaseModel):
    """Single bundle update status."""

    name: str
    current_version: str
    available_version: str | None = None
    has_update: bool = False
```

Create `amplifier-distro/amplifierd/src/amplifierd/models/events.py`:

```python
"""Event-related models for SSE streaming."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SSEEnvelope(BaseModel):
    """Full SSE event envelope sent to clients."""

    event: str = Field(..., description="Event name (e.g., 'tool:pre')")
    data: dict[str, Any] = Field(default_factory=dict, description="Event payload")
    session_id: str = Field(..., description="Source session ID")
    timestamp: str = Field(..., description="ISO 8601 UTC timestamp")
    correlation_id: str | None = Field(default=None, description="Prompt execution ID")
    sequence: int = Field(default=0, description="Monotonic sequence per connection")


class EventHistoryResponse(BaseModel):
    """GET /sessions/{id}/events/history response."""

    events: list[dict[str, Any]]
    total: int
    has_more: bool = False
```

Create `amplifier-distro/amplifierd/src/amplifierd/models/agents.py`:

```python
"""Agent-related request/response models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SpawnRequest(BaseModel):
    """POST /sessions/{id}/spawn request body."""

    agent: str = Field(..., description="Agent name (e.g., 'foundation:explorer')")
    instruction: str = Field(..., description="Task instruction for the child agent")
    context_depth: str = Field(default="recent", description="How much parent context to share")
    context_scope: str = Field(default="conversation", description="What context to share")
    context_turns: int = Field(default=5, description="Number of recent turns to share")
    provider_preferences: list[dict[str, Any]] = Field(
        default_factory=list, description="Ordered provider/model preferences"
    )
    model_role: str | None = Field(default=None, description="Model role hint")


class SpawnResumeRequest(BaseModel):
    """POST /sessions/{id}/spawn/{child_id}/resume request body."""

    instruction: str = Field(..., description="Follow-up instruction for the child agent")


class SpawnResponse(BaseModel):
    """POST /sessions/{id}/spawn response."""

    output: str
    session_id: str
    status: str = "success"
    turn_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentInfo(BaseModel):
    """Single agent info."""

    description: str = ""
    model_role: str | None = None


class AgentListResponse(BaseModel):
    """GET /sessions/{id}/agents response."""

    agents: dict[str, AgentInfo]
```

Create `amplifier-distro/amplifierd/src/amplifierd/models/modules.py`:

```python
"""Module-related request/response models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class MountModuleRequest(BaseModel):
    """POST /sessions/{id}/modules/mount request body."""

    module_id: str = Field(..., description="Module identifier")
    config: dict[str, Any] = Field(default_factory=dict, description="Module configuration")
    source: str | None = Field(default=None, description="Module source URI")


class UnmountModuleRequest(BaseModel):
    """POST /sessions/{id}/modules/unmount request body."""

    mount_point: str = Field(..., description="Mount point (e.g., 'tools')")
    name: str = Field(..., description="Module name to unmount")


class ModuleSummary(BaseModel):
    """Module info for list endpoints."""

    id: str
    name: str
    version: str = "unknown"
    type: str = ""
    mount_point: str = ""
    description: str = ""


class ModuleListResponse(BaseModel):
    """GET /modules response."""

    modules: list[ModuleSummary]


class ValidateMountPlanRequest(BaseModel):
    """POST /validate/mount-plan request body."""

    mount_plan: dict[str, Any] = Field(..., description="Mount plan to validate")


class ValidateModuleRequest(BaseModel):
    """POST /validate/module request body."""

    module_id: str
    type: str
    source: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)


class ValidateBundleRequest(BaseModel):
    """POST /validate/bundle request body."""

    source: str = Field(..., description="Bundle source URI or inline definition")


class ValidationResponse(BaseModel):
    """Validation result for mount-plan, module, or bundle."""

    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    checks: list[dict[str, Any]] = Field(default_factory=list)
```

**Step 4: Run tests to verify they pass**

Run:
```bash
cd amplifier-distro/amplifierd && python -m pytest tests/test_models.py -v
```
Expected: All tests PASS.

**Step 5: Commit**
```bash
cd amplifier-distro/amplifierd && git add -A && git commit -m "feat(amplifierd): Pydantic models for sessions, bundles, events, agents, modules"
```

---

### Task 5: Error Handlers (`errors.py`)

**Files:**
- Create: `amplifier-distro/amplifierd/src/amplifierd/errors.py`
- Create: `amplifier-distro/amplifierd/tests/test_errors.py`

**Step 1: Write the failing test**

Create `amplifier-distro/amplifierd/tests/test_errors.py`:

```python
"""Tests for error handling and LLM error mapping."""

from __future__ import annotations

from amplifier_core import (
    AbortError,
    ConfigurationError,
    ContextLengthError,
    LLMError,
    NetworkError,
    QuotaExceededError,
    RateLimitError,
)

from amplifierd.errors import build_problem_detail, map_llm_error
from amplifierd.models.common import ProblemDetail


class TestLLMErrorMapping:
    """Test LLM error to HTTP status code mapping."""

    def test_rate_limit_maps_to_429(self) -> None:
        err = RateLimitError("Too fast", retry_after=30.0, provider="anthropic")
        status, uri_suffix = map_llm_error(err)
        assert status == 429
        assert uri_suffix == "rate-limit"

    def test_quota_exceeded_before_rate_limit(self) -> None:
        """QuotaExceededError (subclass) must be caught before RateLimitError."""
        err = QuotaExceededError("Billing limit hit", provider="anthropic")
        status, uri_suffix = map_llm_error(err)
        assert status == 429
        assert uri_suffix == "quota-exceeded"

    def test_network_error_before_provider_unavailable(self) -> None:
        """NetworkError (subclass) must be caught before ProviderUnavailableError."""
        err = NetworkError("DNS failed", provider="openai")
        status, uri_suffix = map_llm_error(err)
        assert status == 503
        assert uri_suffix == "network-error"

    def test_context_length_maps_to_413(self) -> None:
        err = ContextLengthError("Too long")
        status, _ = map_llm_error(err)
        assert status == 413

    def test_abort_maps_to_499(self) -> None:
        err = AbortError("Cancelled by user")
        status, _ = map_llm_error(err)
        assert status == 499

    def test_configuration_maps_to_500(self) -> None:
        err = ConfigurationError("Missing API key")
        status, _ = map_llm_error(err)
        assert status == 500

    def test_base_llm_error_maps_to_502(self) -> None:
        err = LLMError("Unknown provider error")
        status, _ = map_llm_error(err)
        assert status == 502


class TestBuildProblemDetail:
    """Test building ProblemDetail from exceptions."""

    def test_rate_limit_includes_retry_after(self) -> None:
        err = RateLimitError("Slow down", retry_after=30.0, provider="anthropic")
        pd = build_problem_detail(err, instance="/sessions/abc/execute")
        assert isinstance(pd, ProblemDetail)
        assert pd.status == 429
        assert pd.retry_after_seconds == 30.0
        assert pd.retryable is True
        assert pd.provider == "anthropic"
        assert pd.error_class == "RateLimitError"

    def test_quota_exceeded_not_retryable(self) -> None:
        err = QuotaExceededError("Billing limit")
        pd = build_problem_detail(err, instance="/sessions/abc/execute")
        assert pd.retryable is False
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd amplifier-distro/amplifierd && python -m pytest tests/test_errors.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'amplifierd.errors'`

**Step 3: Write the implementation**

Create `amplifier-distro/amplifierd/src/amplifierd/errors.py`:

```python
"""Error handling: LLM/Bundle/Session error mapping to RFC 7807 Problem Details.

The LLM_ERROR_MAP list is ordered so subclasses appear before parents.
This ensures isinstance() matching catches the most specific type first.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from amplifier_core import (
    AbortError,
    AccessDeniedError,
    AuthenticationError,
    ConfigurationError,
    ContentFilterError,
    ContextLengthError,
    InvalidRequestError,
    InvalidToolCallError,
    LLMError,
    LLMTimeoutError,
    NetworkError,
    NotFoundError,
    ProviderUnavailableError,
    QuotaExceededError,
    RateLimitError,
    StreamError,
)
from amplifier_foundation import (
    BundleDependencyError,
    BundleError,
    BundleLoadError,
    BundleNotFoundError,
    BundleValidationError,
)

from amplifierd.models.common import ProblemDetail
from amplifierd.models.errors import ErrorTypeURI

logger = logging.getLogger(__name__)

# Order matters: subclasses MUST appear before their parents.
# QuotaExceededError before RateLimitError, AccessDeniedError before AuthenticationError, etc.
LLM_ERROR_MAP: list[tuple[type[LLMError], int, str]] = [
    (QuotaExceededError, 429, "quota-exceeded"),
    (RateLimitError, 429, "rate-limit"),
    (AccessDeniedError, 502, "provider-access-denied"),
    (AuthenticationError, 502, "provider-auth"),
    (ContextLengthError, 413, "context-too-large"),
    (ContentFilterError, 422, "content-filtered"),
    (InvalidRequestError, 400, "invalid-request"),
    (NetworkError, 503, "network-error"),
    (ProviderUnavailableError, 503, "provider-unavailable"),
    (LLMTimeoutError, 504, "provider-timeout"),
    (NotFoundError, 502, "provider-not-found"),
    (StreamError, 502, "stream-error"),
    (AbortError, 499, "aborted"),
    (InvalidToolCallError, 502, "invalid-tool-call"),
    (ConfigurationError, 500, "configuration-error"),
    (LLMError, 502, "llm-error"),
]

BUNDLE_ERROR_MAP: list[tuple[type[BundleError], int, str]] = [
    (BundleNotFoundError, 404, "bundle-not-found"),
    (BundleLoadError, 422, "bundle-load-error"),
    (BundleValidationError, 422, "bundle-validation-error"),
    (BundleDependencyError, 422, "bundle-dependency-error"),
    (BundleError, 500, "bundle-error"),
]

_URI_BASE = "https://amplifier.dev/errors"

# Title lookup for clean error messages
_TITLE_MAP: dict[str, str] = {
    "rate-limit": "Rate Limit Exceeded",
    "quota-exceeded": "Quota Exceeded",
    "provider-auth": "Provider Authentication Failed",
    "provider-access-denied": "Provider Access Denied",
    "context-too-large": "Context Too Large",
    "content-filtered": "Content Filtered",
    "invalid-request": "Invalid Request",
    "provider-unavailable": "Provider Unavailable",
    "network-error": "Network Error",
    "provider-timeout": "Provider Timeout",
    "provider-not-found": "Provider Resource Not Found",
    "stream-error": "Stream Error",
    "aborted": "Request Aborted",
    "invalid-tool-call": "Invalid Tool Call",
    "configuration-error": "Configuration Error",
    "llm-error": "LLM Error",
    "bundle-not-found": "Bundle Not Found",
    "bundle-load-error": "Bundle Load Error",
    "bundle-validation-error": "Bundle Validation Error",
    "bundle-dependency-error": "Bundle Dependency Error",
    "bundle-error": "Bundle Error",
}


def map_llm_error(exc: LLMError) -> tuple[int, str]:
    """Map an LLMError to (http_status, uri_suffix)."""
    for error_cls, status, suffix in LLM_ERROR_MAP:
        if isinstance(exc, error_cls):
            return status, suffix
    return 502, "llm-error"


def map_bundle_error(exc: BundleError) -> tuple[int, str]:
    """Map a BundleError to (http_status, uri_suffix)."""
    for error_cls, status, suffix in BUNDLE_ERROR_MAP:
        if isinstance(exc, error_cls):
            return status, suffix
    return 500, "bundle-error"


def build_problem_detail(
    exc: LLMError | BundleError,
    *,
    instance: str = "",
) -> ProblemDetail:
    """Build a ProblemDetail from an LLMError or BundleError."""
    if isinstance(exc, LLMError):
        status, suffix = map_llm_error(exc)
        return ProblemDetail(
            type=f"{_URI_BASE}/{suffix}",
            title=_TITLE_MAP.get(suffix, "Error"),
            status=status,
            detail=str(exc),
            instance=instance,
            retryable=exc.retryable,
            retry_after_seconds=getattr(exc, "retry_after", None),
            provider=exc.provider,
            model=exc.model,
            upstream_status=exc.status_code,
            error_class=type(exc).__name__,
            tool_name=getattr(exc, "tool_name", None),
            raw_arguments=getattr(exc, "raw_arguments", None),
        )
    elif isinstance(exc, BundleError):
        status, suffix = map_bundle_error(exc)
        return ProblemDetail(
            type=f"{_URI_BASE}/{suffix}",
            title=_TITLE_MAP.get(suffix, "Bundle Error"),
            status=status,
            detail=str(exc),
            instance=instance,
            error_class=type(exc).__name__,
        )
    else:
        return ProblemDetail(
            type=f"{_URI_BASE}/internal-error",
            title="Internal Server Error",
            status=500,
            detail=str(exc),
            instance=instance,
        )


def register_error_handlers(app: FastAPI) -> None:
    """Register FastAPI exception handlers for all known error types."""

    @app.exception_handler(LLMError)
    async def handle_llm_error(request: Request, exc: LLMError) -> JSONResponse:
        pd = build_problem_detail(exc, instance=str(request.url.path))
        headers: dict[str, str] = {}
        if isinstance(exc, RateLimitError) and exc.retry_after is not None:
            headers["Retry-After"] = str(int(exc.retry_after))
        return JSONResponse(
            status_code=pd.status,
            content=pd.model_dump(exclude_none=True),
            headers=headers or None,
        )

    @app.exception_handler(BundleError)
    async def handle_bundle_error(request: Request, exc: BundleError) -> JSONResponse:
        pd = build_problem_detail(exc, instance=str(request.url.path))
        return JSONResponse(
            status_code=pd.status,
            content=pd.model_dump(exclude_none=True),
        )
```

**Step 4: Run tests to verify they pass**

Run:
```bash
cd amplifier-distro/amplifierd && python -m pytest tests/test_errors.py -v
```
Expected: All tests PASS.

**Step 5: Commit**
```bash
cd amplifier-distro/amplifierd && git add -A && git commit -m "feat(amplifierd): error handlers with LLM/Bundle error mapping to Problem Details"
```

---

## Phase 2: Core State

### Task 6: TransportEvent

**Files:**
- Create: `amplifier-distro/amplifierd/src/amplifierd/state/transport_event.py`
- Create: `amplifier-distro/amplifierd/tests/test_transport_event.py`

**Step 1: Write the failing test**

Create `amplifier-distro/amplifierd/tests/test_transport_event.py`:

```python
"""Tests for TransportEvent lightweight event carrier."""

from __future__ import annotations

from amplifierd.state.transport_event import TransportEvent


class TestTransportEvent:
    def test_creation(self) -> None:
        evt = TransportEvent(
            event_name="tool:pre",
            data={"tool_name": "bash"},
            session_id="abc123",
            timestamp="2026-03-02T11:31:00Z",
            correlation_id="prompt_abc_1",
            sequence=5,
        )
        assert evt.event_name == "tool:pre"
        assert evt.data["tool_name"] == "bash"
        assert evt.session_id == "abc123"
        assert evt.correlation_id == "prompt_abc_1"
        assert evt.sequence == 5

    def test_uses_slots(self) -> None:
        """TransportEvent uses __slots__ for memory efficiency."""
        evt = TransportEvent(
            event_name="test",
            data={},
            session_id="s",
            timestamp="t",
        )
        assert hasattr(evt, "__slots__")
        # __slots__ classes don't have __dict__ unless they inherit it
        assert not hasattr(evt, "__dict__")

    def test_defaults(self) -> None:
        evt = TransportEvent(
            event_name="test",
            data={},
            session_id="s",
            timestamp="t",
        )
        assert evt.correlation_id is None
        assert evt.sequence == 0

    def test_to_dict(self) -> None:
        evt = TransportEvent(
            event_name="tool:pre",
            data={"tool": "bash"},
            session_id="abc",
            timestamp="2026-03-02T00:00:00Z",
            correlation_id="cid",
            sequence=3,
        )
        d = evt.to_sse_dict()
        assert d["event"] == "tool:pre"
        assert d["data"]["tool"] == "bash"
        assert d["session_id"] == "abc"
        assert d["correlation_id"] == "cid"
        assert d["sequence"] == 3
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd amplifier-distro/amplifierd && python -m pytest tests/test_transport_event.py -v
```
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write the implementation**

Create `amplifier-distro/amplifierd/src/amplifierd/state/transport_event.py`:

```python
"""Lightweight event carrier for the internal EventBus hot path.

Uses __slots__ instead of Pydantic to avoid serialization overhead
on every event emission. Pydantic is only used at the HTTP boundary.
"""

from __future__ import annotations

from typing import Any


class TransportEvent:
    """Immutable event carrier flowing through the EventBus.

    Attributes:
        event_name: Amplifier event name (e.g., "tool:pre", "content_block:delta").
        data: Event payload dict from HookRegistry.emit().
        session_id: Source session UUID.
        timestamp: ISO 8601 UTC timestamp string.
        correlation_id: Ties events to a specific prompt execution.
            Format: "prompt_{session_id}_{turn}".
        sequence: Monotonic counter per SSE connection (set by subscriber, not publisher).
    """

    __slots__ = (
        "event_name",
        "data",
        "session_id",
        "timestamp",
        "correlation_id",
        "sequence",
    )

    def __init__(
        self,
        *,
        event_name: str,
        data: dict[str, Any],
        session_id: str,
        timestamp: str,
        correlation_id: str | None = None,
        sequence: int = 0,
    ) -> None:
        self.event_name = event_name
        self.data = data
        self.session_id = session_id
        self.timestamp = timestamp
        self.correlation_id = correlation_id
        self.sequence = sequence

    def to_sse_dict(self) -> dict[str, Any]:
        """Convert to a dict suitable for SSE JSON serialization."""
        return {
            "event": self.event_name,
            "data": self.data,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "correlation_id": self.correlation_id,
            "sequence": self.sequence,
        }
```

**Step 4: Run tests to verify they pass**

Run:
```bash
cd amplifier-distro/amplifierd && python -m pytest tests/test_transport_event.py -v
```
Expected: All tests PASS.

**Step 5: Commit**
```bash
cd amplifier-distro/amplifierd && git add -A && git commit -m "feat(amplifierd): TransportEvent __slots__-based event carrier"
```

---

### Task 7: EventBus

**Files:**
- Create: `amplifier-distro/amplifierd/src/amplifierd/state/event_bus.py`
- Create: `amplifier-distro/amplifierd/tests/test_event_bus.py`

**Step 1: Write the failing test**

Create `amplifier-distro/amplifierd/tests/test_event_bus.py`:

```python
"""Tests for the global EventBus."""

from __future__ import annotations

import asyncio

import pytest

from amplifierd.state.event_bus import EventBus
from amplifierd.state.transport_event import TransportEvent


class TestEventBus:
    @pytest.fixture
    def bus(self) -> EventBus:
        return EventBus()

    async def test_publish_and_subscribe(self, bus: EventBus) -> None:
        """Subscriber receives published events."""
        received: list[TransportEvent] = []

        async def collect() -> None:
            async for evt in bus.subscribe():
                received.append(evt)
                if len(received) >= 2:
                    break

        task = asyncio.create_task(collect())
        # Give subscriber time to register
        await asyncio.sleep(0.01)

        bus.publish(session_id="s1", event_name="tool:pre", data={"tool": "bash"})
        bus.publish(session_id="s1", event_name="tool:post", data={"tool": "bash"})
        await asyncio.wait_for(task, timeout=2.0)

        assert len(received) == 2
        assert received[0].event_name == "tool:pre"
        assert received[1].event_name == "tool:post"

    async def test_session_filter(self, bus: EventBus) -> None:
        """Subscriber only receives events from filtered session."""
        received: list[TransportEvent] = []

        async def collect() -> None:
            async for evt in bus.subscribe(session_id="s1"):
                received.append(evt)
                break

        task = asyncio.create_task(collect())
        await asyncio.sleep(0.01)

        # This event should be filtered out
        bus.publish(session_id="s2", event_name="tool:pre", data={})
        # This event should be received
        bus.publish(session_id="s1", event_name="tool:post", data={})

        await asyncio.wait_for(task, timeout=2.0)
        assert len(received) == 1
        assert received[0].session_id == "s1"

    async def test_session_tree_propagation(self, bus: EventBus) -> None:
        """Subscriber to parent receives child events when tree is registered."""
        bus.register_child("parent", "child1")

        received: list[TransportEvent] = []

        async def collect() -> None:
            async for evt in bus.subscribe(session_id="parent"):
                received.append(evt)
                if len(received) >= 2:
                    break

        task = asyncio.create_task(collect())
        await asyncio.sleep(0.01)

        bus.publish(session_id="parent", event_name="session:start", data={})
        bus.publish(session_id="child1", event_name="tool:pre", data={})

        await asyncio.wait_for(task, timeout=2.0)
        assert len(received) == 2
        assert received[1].session_id == "child1"

    async def test_subscriber_count(self, bus: EventBus) -> None:
        assert bus.subscriber_count == 0

        async def quick() -> None:
            async for _ in bus.subscribe():
                break

        task = asyncio.create_task(quick())
        await asyncio.sleep(0.01)
        assert bus.subscriber_count == 1

        bus.publish(session_id="s", event_name="e", data={})
        await asyncio.wait_for(task, timeout=2.0)
        # After subscriber exits, count should drop (eventually)
        await asyncio.sleep(0.01)
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd amplifier-distro/amplifierd && python -m pytest tests/test_event_bus.py -v
```
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write the implementation**

Create `amplifier-distro/amplifierd/src/amplifierd/state/event_bus.py`:

```python
"""Global event bus with session-tree propagation.

All sessions publish events to a single EventBus. Subscribers can filter
by session_id, and subscribing to a parent automatically includes all
descendants (children, grandchildren, etc.).
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any

from amplifierd.state.transport_event import TransportEvent

logger = logging.getLogger(__name__)

_MAX_QUEUE_SIZE = 10_000


class EventBus:
    """Global event fanout for all sessions.

    Publishes TransportEvents to all subscribers. Supports:
    - Unfiltered subscription (all events from all sessions)
    - Session-filtered subscription (events from a specific session + its descendants)
    - Event name glob filtering (future: not implemented in v1)
    - Bounded per-subscriber queues with oldest-drop backpressure
    """

    def __init__(self) -> None:
        self._subscribers: list[_Subscriber] = []
        self._lock = asyncio.Lock()
        # Parent -> set of children mapping for tree propagation
        self._children: dict[str, set[str]] = {}

    @property
    def subscriber_count(self) -> int:
        """Number of active subscribers."""
        return len(self._subscribers)

    def register_child(self, parent_id: str, child_id: str) -> None:
        """Register a parent-child session relationship for tree propagation."""
        if parent_id not in self._children:
            self._children[parent_id] = set()
        self._children[parent_id].add(child_id)

    def unregister_child(self, parent_id: str, child_id: str) -> None:
        """Remove a parent-child session relationship."""
        children = self._children.get(parent_id)
        if children:
            children.discard(child_id)
            if not children:
                del self._children[parent_id]

    def get_descendants(self, session_id: str) -> set[str]:
        """Get all descendants of a session (children, grandchildren, etc.)."""
        result: set[str] = set()
        queue = [session_id]
        while queue:
            current = queue.pop()
            for child in self._children.get(current, set()):
                if child not in result:
                    result.add(child)
                    queue.append(child)
        return result

    def publish(
        self,
        *,
        session_id: str,
        event_name: str,
        data: dict[str, Any],
        correlation_id: str | None = None,
    ) -> None:
        """Publish an event to all matching subscribers.

        This is synchronous (non-blocking) — it puts events on subscriber queues
        without awaiting. If a subscriber's queue is full, the oldest event is dropped.
        """
        event = TransportEvent(
            event_name=event_name,
            data=data,
            session_id=session_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            correlation_id=correlation_id,
        )

        for sub in self._subscribers:
            if sub.matches(session_id, self):
                try:
                    sub.queue.put_nowait(event)
                except asyncio.QueueFull:
                    # Drop oldest event (backpressure)
                    try:
                        sub.queue.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                    try:
                        sub.queue.put_nowait(event)
                    except asyncio.QueueFull:
                        pass

    async def subscribe(
        self,
        *,
        session_id: str | None = None,
        filter_patterns: list[str] | None = None,
    ) -> AsyncIterator[TransportEvent]:
        """Subscribe to events. Yields TransportEvents as they arrive.

        Args:
            session_id: If provided, only events from this session and its
                descendants are yielded.
            filter_patterns: Reserved for future glob-based event name filtering.
        """
        sub = _Subscriber(
            session_id=session_id,
            filter_patterns=filter_patterns,
            queue=asyncio.Queue(maxsize=_MAX_QUEUE_SIZE),
        )
        self._subscribers.append(sub)
        try:
            sequence = 0
            while True:
                event = await sub.queue.get()
                event.sequence = sequence
                sequence += 1
                yield event
        finally:
            self._subscribers.remove(sub)


class _Subscriber:
    """Internal subscriber state."""

    __slots__ = ("session_id", "filter_patterns", "queue")

    def __init__(
        self,
        *,
        session_id: str | None,
        filter_patterns: list[str] | None,
        queue: asyncio.Queue[TransportEvent],
    ) -> None:
        self.session_id = session_id
        self.filter_patterns = filter_patterns
        self.queue = queue

    def matches(self, event_session_id: str, bus: EventBus) -> bool:
        """Check if this subscriber should receive an event from the given session."""
        if self.session_id is None:
            return True  # Unfiltered — receives all events
        if event_session_id == self.session_id:
            return True
        # Check if event_session_id is a descendant of our subscribed session
        return event_session_id in bus.get_descendants(self.session_id)
```

**Step 4: Run tests to verify they pass**

Run:
```bash
cd amplifier-distro/amplifierd && python -m pytest tests/test_event_bus.py -v
```
Expected: All tests PASS.

**Step 5: Commit**
```bash
cd amplifier-distro/amplifierd && git add -A && git commit -m "feat(amplifierd): EventBus with session-tree propagation and backpressure"
```

---

### Task 8: SessionHandle

**Files:**
- Create: `amplifier-distro/amplifierd/src/amplifierd/state/session_handle.py`
- Create: `amplifier-distro/amplifierd/tests/test_session_handle.py`

**Step 1: Write the failing test**

Create `amplifier-distro/amplifierd/tests/test_session_handle.py`:

```python
"""Tests for SessionHandle — the per-session state wrapper."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from amplifierd.state.event_bus import EventBus
from amplifierd.state.session_handle import SessionHandle, SessionStatus


class TestSessionHandle:
    @pytest.fixture
    def mock_session(self) -> MagicMock:
        session = MagicMock()
        session.session_id = "test-session"
        session.parent_id = None
        session.execute = AsyncMock(return_value="Hello from test!")
        session.cleanup = AsyncMock()
        session.coordinator = MagicMock()
        session.coordinator.get_capability = MagicMock(return_value=None)
        return session

    @pytest.fixture
    def bus(self) -> EventBus:
        return EventBus()

    async def test_initial_status(self, mock_session: MagicMock, bus: EventBus) -> None:
        handle = SessionHandle(
            session=mock_session,
            prepared_bundle=None,
            bundle_name="test-bundle",
            event_bus=bus,
        )
        assert handle.status == SessionStatus.IDLE
        assert handle.session_id == "test-session"
        assert handle.stale is False

    async def test_execute_sets_status(self, mock_session: MagicMock, bus: EventBus) -> None:
        handle = SessionHandle(
            session=mock_session,
            prepared_bundle=None,
            bundle_name="test-bundle",
            event_bus=bus,
        )
        result = await handle.execute("Hello")
        assert result == "Hello from test!"
        # After execution completes, status should return to idle
        assert handle.status == SessionStatus.IDLE

    async def test_mark_stale(self, mock_session: MagicMock, bus: EventBus) -> None:
        handle = SessionHandle(
            session=mock_session,
            prepared_bundle=None,
            bundle_name="test-bundle",
            event_bus=bus,
        )
        assert handle.stale is False
        handle.mark_stale()
        assert handle.stale is True

    async def test_children_tracking(self, mock_session: MagicMock, bus: EventBus) -> None:
        handle = SessionHandle(
            session=mock_session,
            prepared_bundle=None,
            bundle_name="test-bundle",
            event_bus=bus,
        )
        handle.register_child("child-1", "explorer")
        assert "child-1" in handle.children
        assert handle.children["child-1"] == "explorer"

    async def test_turn_counter(self, mock_session: MagicMock, bus: EventBus) -> None:
        handle = SessionHandle(
            session=mock_session,
            prepared_bundle=None,
            bundle_name="test-bundle",
            event_bus=bus,
        )
        assert handle.turn_count == 0
        await handle.execute("First prompt")
        assert handle.turn_count == 1
        await handle.execute("Second prompt")
        assert handle.turn_count == 2
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd amplifier-distro/amplifierd && python -m pytest tests/test_session_handle.py -v
```
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write the implementation**

Create `amplifier-distro/amplifierd/src/amplifierd/state/session_handle.py`:

```python
"""SessionHandle — wraps one live AmplifierSession with serialized execution.

Each SessionHandle owns:
- The live AmplifierSession
- A PreparedBundle reference (for reloads)
- An asyncio.Queue + worker for serializing executes
- Stale flag for bundle reload-on-next-execute
- Children tracking for the session tree
- Approval futures for human-in-the-loop gates
"""

from __future__ import annotations

import enum
import logging
from datetime import datetime, timezone
from typing import Any

from amplifierd.state.event_bus import EventBus

logger = logging.getLogger(__name__)


class SessionStatus(str, enum.Enum):
    """Session lifecycle states."""

    IDLE = "idle"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"


class SessionHandle:
    """Wraps one live AmplifierSession and serializes access to it.

    Execution requests go through execute() which serializes them:
    only one execute() runs at a time per session.

    Reads (status, messages, tree) are safe to call concurrently with execution.
    """

    def __init__(
        self,
        *,
        session: Any,  # AmplifierSession — untyped to avoid import at module level
        prepared_bundle: Any | None,  # PreparedBundle
        bundle_name: str,
        event_bus: EventBus,
        working_dir: str | None = None,
    ) -> None:
        self._session = session
        self._prepared_bundle = prepared_bundle
        self._bundle_name = bundle_name
        self._event_bus = event_bus
        self._status = SessionStatus.IDLE
        self._stale = False
        self._children: dict[str, str] = {}  # child_session_id -> agent_name
        self._turn_count = 0
        self._created_at = datetime.now(timezone.utc)
        self._last_activity = self._created_at
        self._working_dir = working_dir
        self._correlation_id: str | None = None
        # Allow-always cache for approvals: tool_name -> True
        self._approval_cache: dict[str, bool] = {}

    # --- Properties (safe for concurrent reads) ---

    @property
    def session(self) -> Any:
        return self._session

    @property
    def session_id(self) -> str:
        return self._session.session_id

    @property
    def parent_id(self) -> str | None:
        return self._session.parent_id

    @property
    def status(self) -> SessionStatus:
        return self._status

    @property
    def stale(self) -> bool:
        return self._stale

    @property
    def children(self) -> dict[str, str]:
        return dict(self._children)

    @property
    def bundle_name(self) -> str:
        return self._bundle_name

    @property
    def turn_count(self) -> int:
        return self._turn_count

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def last_activity(self) -> datetime:
        return self._last_activity

    @property
    def working_dir(self) -> str | None:
        return self._working_dir

    @property
    def correlation_id(self) -> str | None:
        return self._correlation_id

    # --- Mutators ---

    def mark_stale(self) -> None:
        """Mark this session for bundle reload on next execute()."""
        self._stale = True

    def register_child(self, child_session_id: str, agent_name: str) -> None:
        """Register a child session (from delegate/spawn)."""
        self._children[child_session_id] = agent_name
        self._event_bus.register_child(self.session_id, child_session_id)

    # --- Execution (serialized) ---

    async def execute(self, prompt: str) -> str:
        """Execute a prompt on this session.

        Only one execute() can run at a time per session. If a second
        call arrives while one is running, it will raise an error.

        If the session is marked stale, the bundle is reloaded first.
        """
        if self._status == SessionStatus.EXECUTING:
            msg = f"Session {self.session_id} is already executing"
            raise RuntimeError(msg)

        self._turn_count += 1
        self._correlation_id = f"prompt_{self.session_id}_{self._turn_count}"
        self._status = SessionStatus.EXECUTING
        self._last_activity = datetime.now(timezone.utc)

        try:
            # TODO: if self._stale, reload bundle before executing
            result = await self._session.execute(prompt)
            self._status = SessionStatus.IDLE
            self._last_activity = datetime.now(timezone.utc)
            return result
        except Exception:
            self._status = SessionStatus.FAILED
            self._last_activity = datetime.now(timezone.utc)
            raise

    async def cancel(self, *, immediate: bool = False) -> None:
        """Cancel the running execution."""
        coordinator = self._session.coordinator
        coordinator.request_cancel(immediate)

    async def cleanup(self) -> None:
        """Clean up session resources."""
        try:
            await self._session.cleanup()
        except Exception as exc:
            logger.warning("Session %s cleanup failed: %s", self.session_id, exc)
        self._status = SessionStatus.COMPLETED
```

Update `amplifier-distro/amplifierd/src/amplifierd/state/__init__.py`:

```python
"""State management: SessionManager, EventBus, SessionHandle."""

from __future__ import annotations

from amplifierd.state.event_bus import EventBus
from amplifierd.state.session_handle import SessionHandle, SessionStatus
from amplifierd.state.transport_event import TransportEvent

__all__ = ["EventBus", "SessionHandle", "SessionStatus", "TransportEvent"]
```

**Step 4: Run tests to verify they pass**

Run:
```bash
cd amplifier-distro/amplifierd && python -m pytest tests/test_session_handle.py -v
```
Expected: All tests PASS.

**Step 5: Commit**
```bash
cd amplifier-distro/amplifierd && git add -A && git commit -m "feat(amplifierd): SessionHandle with serialized execution and stale flag"
```

---

### Task 9: SessionManager

**Files:**
- Create: `amplifier-distro/amplifierd/src/amplifierd/state/session_manager.py`
- Create: `amplifier-distro/amplifierd/tests/test_session_manager.py`

**Step 1: Write the failing test**

Create `amplifier-distro/amplifierd/tests/test_session_manager.py`:

```python
"""Tests for SessionManager — the central session registry."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from amplifierd.config import DaemonSettings
from amplifierd.state.event_bus import EventBus
from amplifierd.state.session_manager import SessionManager


class TestSessionManager:
    @pytest.fixture
    def bus(self) -> EventBus:
        return EventBus()

    @pytest.fixture
    def settings(self) -> DaemonSettings:
        return DaemonSettings()

    @pytest.fixture
    def manager(self, bus: EventBus, settings: DaemonSettings) -> SessionManager:
        return SessionManager(event_bus=bus, settings=settings)

    def test_initially_empty(self, manager: SessionManager) -> None:
        assert manager.list_sessions() == []

    def test_get_nonexistent(self, manager: SessionManager) -> None:
        assert manager.get("nonexistent") is None

    async def test_register_and_get(self, manager: SessionManager) -> None:
        """Register a pre-built SessionHandle and retrieve it."""
        mock_session = MagicMock()
        mock_session.session_id = "test-123"
        mock_session.parent_id = None

        handle = manager.register(
            session=mock_session,
            prepared_bundle=None,
            bundle_name="test-bundle",
        )
        assert handle.session_id == "test-123"
        assert manager.get("test-123") is handle

    async def test_destroy(self, manager: SessionManager) -> None:
        mock_session = MagicMock()
        mock_session.session_id = "to-destroy"
        mock_session.parent_id = None
        mock_session.cleanup = AsyncMock()

        manager.register(
            session=mock_session,
            prepared_bundle=None,
            bundle_name="test-bundle",
        )
        assert manager.get("to-destroy") is not None
        await manager.destroy("to-destroy")
        assert manager.get("to-destroy") is None

    async def test_list_sessions(self, manager: SessionManager) -> None:
        for i in range(3):
            mock = MagicMock()
            mock.session_id = f"session-{i}"
            mock.parent_id = None
            manager.register(session=mock, prepared_bundle=None, bundle_name="b")

        sessions = manager.list_sessions()
        assert len(sessions) == 3
        ids = {h.session_id for h in sessions}
        assert ids == {"session-0", "session-1", "session-2"}
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd amplifier-distro/amplifierd && python -m pytest tests/test_session_manager.py -v
```
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write the implementation**

Create `amplifier-distro/amplifierd/src/amplifierd/state/session_manager.py`:

```python
"""SessionManager — central registry of all live sessions.

The SessionManager is the only component that creates, stores, or destroys
SessionHandle instances. All route handlers access sessions through it.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from amplifierd.config import DaemonSettings
from amplifierd.state.event_bus import EventBus
from amplifierd.state.session_handle import SessionHandle

logger = logging.getLogger(__name__)


class SessionManager:
    """Central owner of all live sessions.

    A single instance is created at startup and stored in app.state.
    """

    def __init__(
        self,
        *,
        event_bus: EventBus,
        settings: DaemonSettings,
    ) -> None:
        self._sessions: dict[str, SessionHandle] = {}
        self._event_bus = event_bus
        self._settings = settings

    @property
    def event_bus(self) -> EventBus:
        return self._event_bus

    @property
    def settings(self) -> DaemonSettings:
        return self._settings

    def resolve_working_dir(self, request_working_dir: str | None) -> str:
        """Resolve working directory using the fallback chain:
        request > daemon config > user home.
        """
        if request_working_dir:
            return request_working_dir
        if self._settings.default_working_dir:
            return str(self._settings.default_working_dir)
        return str(Path.home())

    def register(
        self,
        *,
        session: Any,  # AmplifierSession
        prepared_bundle: Any | None,  # PreparedBundle
        bundle_name: str,
        working_dir: str | None = None,
    ) -> SessionHandle:
        """Register a pre-created session and wrap it in a SessionHandle."""
        session_id: str = session.session_id
        if session_id in self._sessions:
            msg = f"Session {session_id} already exists"
            raise ValueError(msg)

        handle = SessionHandle(
            session=session,
            prepared_bundle=prepared_bundle,
            bundle_name=bundle_name,
            event_bus=self._event_bus,
            working_dir=working_dir,
        )
        self._sessions[session_id] = handle
        logger.info("Registered session %s (bundle=%s)", session_id, bundle_name)
        return handle

    def get(self, session_id: str) -> SessionHandle | None:
        """Get a session by ID, or None if not found."""
        return self._sessions.get(session_id)

    def list_sessions(self) -> list[SessionHandle]:
        """List all live sessions."""
        return list(self._sessions.values())

    async def destroy(self, session_id: str) -> None:
        """Destroy a session: cleanup resources and remove from registry."""
        handle = self._sessions.pop(session_id, None)
        if handle is None:
            logger.warning("Attempted to destroy unknown session %s", session_id)
            return
        await handle.cleanup()
        logger.info("Destroyed session %s", session_id)

    async def shutdown(self) -> None:
        """Gracefully shutdown all sessions (called on daemon shutdown)."""
        session_ids = list(self._sessions.keys())
        for sid in session_ids:
            try:
                await self.destroy(sid)
            except Exception as exc:
                logger.warning("Error destroying session %s during shutdown: %s", sid, exc)
```

**Step 4: Run tests to verify they pass**

Run:
```bash
cd amplifier-distro/amplifierd && python -m pytest tests/test_session_manager.py -v
```
Expected: All tests PASS.

**Step 5: Commit**
```bash
cd amplifier-distro/amplifierd && git add -A && git commit -m "feat(amplifierd): SessionManager — central session registry with create/get/destroy"
```

---

### Task 10: Plugin Discovery

**Files:**
- Create: `amplifier-distro/amplifierd/src/amplifierd/plugins.py`
- Create: `amplifier-distro/amplifierd/tests/test_plugins.py`

**Step 1: Write the failing test**

Create `amplifier-distro/amplifierd/tests/test_plugins.py`:

```python
"""Tests for plugin discovery via entry points."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi import APIRouter

from amplifierd.plugins import discover_plugins


class TestPluginDiscovery:
    def test_no_plugins_installed(self) -> None:
        """When no plugins are installed, returns empty list."""
        with patch("amplifierd.plugins._get_entry_points", return_value=[]):
            result = discover_plugins(disabled=[])
        assert result == []

    def test_disabled_plugin_skipped(self) -> None:
        """Plugins in the disabled list are not loaded."""
        ep = MagicMock()
        ep.name = "slack"
        ep.load.return_value = lambda state: APIRouter()

        with patch("amplifierd.plugins._get_entry_points", return_value=[ep]):
            result = discover_plugins(disabled=["slack"])
        assert result == []
        ep.load.assert_not_called()

    def test_broken_plugin_does_not_crash(self) -> None:
        """A broken plugin logs a warning but doesn't prevent others from loading."""
        good_ep = MagicMock()
        good_ep.name = "good"
        good_router = APIRouter()
        good_ep.load.return_value = lambda state: good_router

        bad_ep = MagicMock()
        bad_ep.name = "bad"
        bad_ep.load.side_effect = ImportError("broken")

        with patch("amplifierd.plugins._get_entry_points", return_value=[bad_ep, good_ep]):
            result = discover_plugins(disabled=[], state=MagicMock())
        assert len(result) == 1
        assert result[0][0] == "good"
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd amplifier-distro/amplifierd && python -m pytest tests/test_plugins.py -v
```
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write the implementation**

Create `amplifier-distro/amplifierd/src/amplifierd/plugins.py`:

```python
"""Plugin discovery via Python entry points.

Plugins are pip-installable packages that declare an entry point in the
`amplifierd.plugins` group. Each entry point resolves to a
`create_router(state) -> fastapi.APIRouter` callable.
"""

from __future__ import annotations

import importlib.metadata
import logging
from typing import Any

from fastapi import APIRouter

logger = logging.getLogger(__name__)

_ENTRY_POINT_GROUP = "amplifierd.plugins"


def _get_entry_points() -> list[Any]:
    """Get entry points for the amplifierd.plugins group.

    Extracted for testability — tests can patch this function.
    """
    return list(importlib.metadata.entry_points(group=_ENTRY_POINT_GROUP))


def discover_plugins(
    *,
    disabled: list[str],
    state: Any = None,
) -> list[tuple[str, APIRouter]]:
    """Discover and load plugins from entry points.

    Args:
        disabled: Plugin names to skip.
        state: The app.state object passed to each plugin's create_router().

    Returns:
        List of (plugin_name, router) tuples for successfully loaded plugins.
    """
    entry_points = _get_entry_points()
    loaded: list[tuple[str, APIRouter]] = []

    for ep in entry_points:
        name: str = ep.name
        if name in disabled:
            logger.info("Skipping disabled plugin: %s", name)
            continue

        try:
            create_router = ep.load()
            router = create_router(state)
            if not isinstance(router, APIRouter):
                logger.warning(
                    "Plugin %s: create_router() did not return an APIRouter, skipping",
                    name,
                )
                continue
            loaded.append((name, router))
            logger.info("Loaded plugin: %s", name)
        except Exception:
            logger.exception("Failed to load plugin: %s", name)

    return loaded
```

**Step 4: Run tests to verify they pass**

Run:
```bash
cd amplifier-distro/amplifierd && python -m pytest tests/test_plugins.py -v
```
Expected: All tests PASS.

**Step 5: Commit**
```bash
cd amplifier-distro/amplifierd && git add -A && git commit -m "feat(amplifierd): plugin discovery via entry points with disabled list and error resilience"
```

---

## Phase 3: Routes — Core

### Task 11: App Factory + Health Routes

**Files:**
- Create: `amplifier-distro/amplifierd/src/amplifierd/app.py`
- Create: `amplifier-distro/amplifierd/src/amplifierd/routes/health.py`
- Create: `amplifier-distro/amplifierd/tests/test_health.py`

**Step 1: Write the failing test**

Create `amplifier-distro/amplifierd/tests/test_health.py`:

```python
"""Integration tests for health and info endpoints."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from amplifierd.app import create_app
from amplifierd.config import DaemonSettings


@pytest.fixture
def settings() -> DaemonSettings:
    return DaemonSettings()


@pytest.fixture
async def client(settings: DaemonSettings) -> AsyncClient:
    app = create_app(settings=settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestHealthEndpoint:
    async def test_health_returns_200(self, client: AsyncClient) -> None:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "uptime_seconds" in data
        assert "active_sessions" in data

    async def test_info_returns_200(self, client: AsyncClient) -> None:
        resp = await client.get("/info")
        assert resp.status_code == 200
        data = resp.json()
        assert "version" in data
        assert "amplifier_core_version" in data
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd amplifier-distro/amplifierd && python -m pytest tests/test_health.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'amplifierd.app'`

**Step 3: Write the implementation**

Create `amplifier-distro/amplifierd/src/amplifierd/routes/health.py`:

```python
"""Health and info endpoints."""

from __future__ import annotations

import time
from typing import Any

import amplifier_core
from fastapi import APIRouter, Request

import amplifierd

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(request: Request) -> dict[str, Any]:
    """Health check endpoint."""
    manager = request.app.state.session_manager
    start_time: float = request.app.state.start_time
    return {
        "status": "healthy",
        "version": amplifierd.__version__,
        "uptime_seconds": round(time.time() - start_time, 1),
        "active_sessions": len(manager.list_sessions()),
        "rust_engine": getattr(amplifier_core, "RUST_AVAILABLE", False),
    }


@router.get("/info")
async def info(request: Request) -> dict[str, Any]:
    """Server info and capabilities."""
    return {
        "version": amplifierd.__version__,
        "amplifier_core_version": amplifier_core.__version__,
        "rust_available": getattr(amplifier_core, "RUST_AVAILABLE", False),
        "capabilities": [
            "streaming",
            "websocket",
            "approval",
            "cancellation",
            "hot_mount",
            "fork",
            "spawn",
        ],
        "module_types": [
            "orchestrator",
            "provider",
            "tool",
            "hook",
            "context",
            "resolver",
        ],
    }
```

Create `amplifier-distro/amplifierd/src/amplifierd/app.py`:

```python
"""FastAPI application factory.

create_app() builds a fully-configured FastAPI application with:
- Lifespan manager (startup resilience, graceful shutdown)
- Error handlers (LLMError, BundleError -> Problem Details)
- Plugin discovery and mounting
- All core route modules

Tests create isolated app instances via create_app(settings=...).
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from amplifierd.config import DaemonSettings
from amplifierd.errors import register_error_handlers
from amplifierd.plugins import discover_plugins
from amplifierd.state.event_bus import EventBus
from amplifierd.state.session_manager import SessionManager

logger = logging.getLogger(__name__)


def create_app(
    *,
    settings: DaemonSettings | None = None,
) -> FastAPI:
    """Create a fully-configured FastAPI application.

    Args:
        settings: Daemon settings. If None, loads from default sources.
    """
    if settings is None:
        settings = DaemonSettings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> Any:
        """Application lifespan: startup and shutdown."""
        # --- Startup ---
        app.state.start_time = time.time()
        app.state.settings = settings

        # Step 1: Create EventBus
        event_bus = EventBus()
        app.state.event_bus = event_bus
        logger.info("EventBus created")

        # Step 2: Create SessionManager
        session_manager = SessionManager(event_bus=event_bus, settings=settings)
        app.state.session_manager = session_manager
        logger.info("SessionManager created")

        # Step 3: Create BundleRegistry (resilient)
        try:
            from amplifier_foundation import BundleRegistry
            from pathlib import Path

            amplifier_home = Path.home() / ".amplifier"
            registry = BundleRegistry(home=amplifier_home)
            app.state.bundle_registry = registry
            logger.info("BundleRegistry created (home=%s)", amplifier_home)
        except Exception:
            logger.warning("BundleRegistry init failed, starting without registry", exc_info=True)
            app.state.bundle_registry = None

        # Step 4: Discover and mount plugins (resilient)
        try:
            plugins = discover_plugins(
                disabled=settings.disabled_plugins,
                state=app.state,
            )
            for name, plugin_router in plugins:
                app.include_router(plugin_router, prefix=f"/plugins/{name}")
                logger.info("Mounted plugin: %s at /plugins/%s/", name, name)
        except Exception:
            logger.warning("Plugin discovery failed", exc_info=True)

        yield

        # --- Shutdown ---
        logger.info("Shutting down amplifierd")
        await session_manager.shutdown()
        logger.info("All sessions cleaned up")

    app = FastAPI(
        title="amplifierd",
        description="Amplifier daemon - HTTP/SSE/WebSocket API",
        version="0.1.0",
        lifespan=lifespan,
    )

    # CORS — permissive for localhost daemon
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Error handlers
    register_error_handlers(app)

    # Core routes
    from amplifierd.routes.health import router as health_router

    app.include_router(health_router)

    return app
```

**Step 4: Run tests to verify they pass**

Run:
```bash
cd amplifier-distro/amplifierd && python -m pytest tests/test_health.py -v
```
Expected: All tests PASS.

**Step 5: Commit**
```bash
cd amplifier-distro/amplifierd && git add -A && git commit -m "feat(amplifierd): app factory with lifespan, health/info routes, plugin mounting"
```

---

### Task 12: CLI (`cli.py`)

**Files:**
- Create: `amplifier-distro/amplifierd/src/amplifierd/cli.py`
- Create: `amplifier-distro/amplifierd/tests/test_cli.py`

**Step 1: Write the failing test**

Create `amplifier-distro/amplifierd/tests/test_cli.py`:

```python
"""Tests for the CLI entry point."""

from __future__ import annotations

from click.testing import CliRunner

from amplifierd.cli import main


class TestCLI:
    def test_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(main, ["serve", "--help"])
        assert result.exit_code == 0
        assert "--port" in result.output
        assert "--host" in result.output
        assert "--reload" in result.output
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd amplifier-distro/amplifierd && python -m pytest tests/test_cli.py -v
```
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write the implementation**

Create `amplifier-distro/amplifierd/src/amplifierd/cli.py`:

```python
"""amplifierd CLI.

Usage:
    amplifierd serve                    # Start on 127.0.0.1:8410
    amplifierd serve --port 9000        # Custom port
    amplifierd serve --host 0.0.0.0     # Bind all interfaces
    amplifierd serve --reload           # Dev hot-reload via uvicorn
    amplifierd serve --log-level debug  # Debug logging
"""

from __future__ import annotations

import logging
import os

import click
import uvicorn


@click.group()
def main() -> None:
    """amplifierd — Amplifier daemon."""
    pass


@main.command()
@click.option("--host", default=None, help="Bind host (default: from settings or 127.0.0.1)")
@click.option("--port", default=None, type=int, help="Bind port (default: from settings or 8410)")
@click.option("--reload", is_flag=True, help="Auto-reload on code changes (dev mode)")
@click.option(
    "--log-level",
    default=None,
    help="Log level: debug, info, warning, error (overrides AMPLIFIERD_LOG_LEVEL)",
)
def serve(
    host: str | None,
    port: int | None,
    reload: bool,
    log_level: str | None,
) -> None:
    """Start the amplifierd HTTP server."""
    from amplifierd.config import DaemonSettings

    settings = DaemonSettings()

    # CLI flags override settings
    effective_host = host or settings.host
    effective_port = port or settings.port
    effective_log_level = (
        log_level or os.environ.get("AMPLIFIERD_LOG_LEVEL") or settings.log_level
    ).lower()

    # Configure root logger
    logging.basicConfig(
        level=effective_log_level.upper(),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

    click.echo(
        f"Starting amplifierd on http://{effective_host}:{effective_port} "
        f"(log-level={effective_log_level})"
    )
    click.echo("Press Ctrl+C to stop")

    uvicorn.run(
        "amplifierd.app:create_app",
        host=effective_host,
        port=effective_port,
        reload=reload,
        factory=True,
        log_level=effective_log_level,
    )


if __name__ == "__main__":
    main()
```

**Step 4: Run tests to verify they pass**

Run:
```bash
cd amplifier-distro/amplifierd && python -m pytest tests/test_cli.py -v
```
Expected: All tests PASS.

**Step 5: Commit**
```bash
cd amplifier-distro/amplifierd && git add -A && git commit -m "feat(amplifierd): CLI with 'amplifierd serve' command"
```

---

### Task 13: Session CRUD Routes

**Files:**
- Create: `amplifier-distro/amplifierd/src/amplifierd/routes/sessions.py`
- Modify: `amplifier-distro/amplifierd/src/amplifierd/app.py`
- Create: `amplifier-distro/amplifierd/tests/test_sessions_routes.py`

**Step 1: Write the failing test**

Create `amplifier-distro/amplifierd/tests/test_sessions_routes.py`:

```python
"""Integration tests for session CRUD routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from amplifierd.app import create_app
from amplifierd.config import DaemonSettings


@pytest.fixture
def settings() -> DaemonSettings:
    return DaemonSettings()


@pytest.fixture
async def client(settings: DaemonSettings) -> AsyncClient:
    app = create_app(settings=settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _register_mock_session(app_state: MagicMock, session_id: str = "test-123") -> None:
    """Helper to register a mock session into the SessionManager."""
    mock_session = MagicMock()
    mock_session.session_id = session_id
    mock_session.parent_id = None
    mock_session.cleanup = AsyncMock()
    mock_session.coordinator = MagicMock()
    mock_session.coordinator.get_capability = MagicMock(return_value=None)
    app_state.session_manager.register(
        session=mock_session,
        prepared_bundle=None,
        bundle_name="test-bundle",
    )


class TestSessionListRoute:
    async def test_list_empty(self, client: AsyncClient) -> None:
        resp = await client.get("/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["sessions"] == []
        assert data["total"] == 0


class TestSessionGetRoute:
    async def test_get_not_found(self, client: AsyncClient) -> None:
        resp = await client.get("/sessions/nonexistent")
        assert resp.status_code == 404


class TestSessionDeleteRoute:
    async def test_delete_not_found(self, client: AsyncClient) -> None:
        resp = await client.delete("/sessions/nonexistent")
        assert resp.status_code == 404
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd amplifier-distro/amplifierd && python -m pytest tests/test_sessions_routes.py -v
```
Expected: FAIL — `ModuleNotFoundError` or route not found (404 for list)

**Step 3: Write the implementation**

Create `amplifier-distro/amplifierd/src/amplifierd/routes/sessions.py`:

```python
"""Session CRUD, execution, cancellation, fork, and stale endpoints."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from amplifierd.models.common import ProblemDetail
from amplifierd.models.errors import ErrorTypeURI
from amplifierd.models.sessions import (
    CancelRequest,
    ExecuteRequest,
    ExecuteResponse,
    ExecuteStreamAccepted,
    PatchSessionRequest,
    SessionDetail,
    SessionListResponse,
    SessionSummary,
    StaleRequest,
)
from amplifierd.state.session_handle import SessionHandle, SessionStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _get_handle_or_404(request: Request, session_id: str) -> SessionHandle:
    """Get a SessionHandle or raise 404."""
    handle = request.app.state.session_manager.get(session_id)
    if handle is None:
        raise HTTPException(
            status_code=404,
            detail={
                "type": ErrorTypeURI.SESSION_NOT_FOUND,
                "title": "Session Not Found",
                "status": 404,
                "detail": f"Session {session_id} not found",
                "instance": str(request.url.path),
            },
        )
    return handle


def _summarize(handle: SessionHandle) -> SessionSummary:
    return SessionSummary(
        session_id=handle.session_id,
        status=handle.status.value,
        bundle=handle.bundle_name,
        created_at=handle.created_at.isoformat(),
        last_activity=handle.last_activity.isoformat(),
        parent_session_id=handle.parent_id,
        stale=handle.stale,
    )


# --- CRUD ---


@router.get("")
async def list_sessions(request: Request) -> SessionListResponse:
    """List all active sessions."""
    manager = request.app.state.session_manager
    handles = manager.list_sessions()
    summaries = [_summarize(h) for h in handles]
    return SessionListResponse(sessions=summaries, total=len(summaries))


@router.get("/{session_id}")
async def get_session(request: Request, session_id: str) -> SessionDetail:
    """Get session details."""
    handle = _get_handle_or_404(request, session_id)
    return SessionDetail(
        session_id=handle.session_id,
        status=handle.status.value,
        parent_id=handle.parent_id,
        bundle=handle.bundle_name,
        created_at=handle.created_at.isoformat(),
        last_activity=handle.last_activity.isoformat(),
        working_dir=handle.working_dir,
        stale=handle.stale,
    )


@router.patch("/{session_id}")
async def patch_session(
    request: Request, session_id: str, body: PatchSessionRequest
) -> SessionDetail:
    """Update session properties (working_dir, name)."""
    handle = _get_handle_or_404(request, session_id)
    if body.working_dir is not None:
        from amplifier_foundation import set_working_dir

        set_working_dir(handle.session.coordinator, body.working_dir)
        handle._working_dir = body.working_dir
    return await get_session(request, session_id)


@router.delete("/{session_id}", status_code=204)
async def delete_session(request: Request, session_id: str) -> None:
    """Destroy a session."""
    handle = request.app.state.session_manager.get(session_id)
    if handle is None:
        raise HTTPException(status_code=404, detail="Session not found")
    await request.app.state.session_manager.destroy(session_id)


# --- Execution ---


@router.post("/{session_id}/execute")
async def execute(
    request: Request, session_id: str, body: ExecuteRequest
) -> ExecuteResponse:
    """Execute a prompt synchronously (blocks until done)."""
    handle = _get_handle_or_404(request, session_id)
    if handle.status == SessionStatus.EXECUTING:
        raise HTTPException(status_code=409, detail="Execution already in progress")
    result = await handle.execute(body.prompt)
    return ExecuteResponse(response=result)


@router.post("/{session_id}/execute/stream", status_code=202)
async def execute_stream(
    request: Request, session_id: str, body: ExecuteRequest
) -> ExecuteStreamAccepted:
    """Fire-and-forget execution. Returns 202 with correlation_id.
    Results flow through GET /events SSE stream.
    """
    import asyncio

    handle = _get_handle_or_404(request, session_id)
    if handle.status == SessionStatus.EXECUTING:
        raise HTTPException(status_code=409, detail="Execution already in progress")

    # Increment turn to get correlation_id, then fire task
    handle._turn_count += 1
    correlation_id = f"prompt_{handle.session_id}_{handle.turn_count}"
    handle._correlation_id = correlation_id

    async def _run() -> None:
        try:
            await handle.execute(body.prompt)
        except Exception:
            logger.exception("Async execution failed for session %s", session_id)

    asyncio.create_task(_run())

    return ExecuteStreamAccepted(
        correlation_id=correlation_id,
        session_id=session_id,
    )


# --- Cancellation ---


@router.post("/{session_id}/cancel")
async def cancel(
    request: Request, session_id: str, body: CancelRequest
) -> dict[str, Any]:
    """Cancel a running execution."""
    handle = _get_handle_or_404(request, session_id)
    await handle.cancel(immediate=body.immediate)
    return {"state": "immediate" if body.immediate else "graceful"}


# --- Stale ---


@router.post("/{session_id}/stale")
async def mark_stale(
    request: Request, session_id: str, body: StaleRequest | None = None
) -> dict[str, Any]:
    """Mark session for bundle reload on next execute."""
    handle = _get_handle_or_404(request, session_id)
    handle.mark_stale()
    return {"session_id": session_id, "stale": True}


# --- Tree ---


@router.get("/{session_id}/tree")
async def get_tree(request: Request, session_id: str) -> dict[str, Any]:
    """Get the live session tree (parent + all descendants)."""
    handle = _get_handle_or_404(request, session_id)
    manager = request.app.state.session_manager

    def _build_tree(h: SessionHandle) -> dict[str, Any]:
        child_nodes = []
        for child_id, agent_name in h.children.items():
            child_handle = manager.get(child_id)
            if child_handle:
                child_nodes.append(_build_tree(child_handle))
        return {
            "session_id": h.session_id,
            "agent": h.children.get(h.session_id),
            "status": h.status.value,
            "children": child_nodes,
        }

    return _build_tree(handle)
```

Now register this router in `app.py`. Add the import and include_router call after the health router:

In `amplifier-distro/amplifierd/src/amplifierd/app.py`, after the health router include, add:

```python
    from amplifierd.routes.sessions import router as sessions_router

    app.include_router(sessions_router)
```

**Step 4: Run tests to verify they pass**

Run:
```bash
cd amplifier-distro/amplifierd && python -m pytest tests/test_sessions_routes.py -v
```
Expected: All tests PASS.

**Step 5: Commit**
```bash
cd amplifier-distro/amplifierd && git add -A && git commit -m "feat(amplifierd): session CRUD, execute, cancel, stale, tree routes"
```

---

### Task 14: Global SSE Events Route

**Files:**
- Create: `amplifier-distro/amplifierd/src/amplifierd/routes/events.py`
- Modify: `amplifier-distro/amplifierd/src/amplifierd/app.py` (add events router)
- Create: `amplifier-distro/amplifierd/tests/test_events_route.py`

**Step 1: Write the failing test**

Create `amplifier-distro/amplifierd/tests/test_events_route.py`:

```python
"""Tests for the global SSE events endpoint."""

from __future__ import annotations

import asyncio
import json

import pytest
from httpx import ASGITransport, AsyncClient

from amplifierd.app import create_app
from amplifierd.config import DaemonSettings


@pytest.fixture
def settings() -> DaemonSettings:
    return DaemonSettings()


@pytest.fixture
async def app(settings: DaemonSettings):
    return create_app(settings=settings)


class TestEventsEndpoint:
    async def test_events_endpoint_exists(self, app) -> None:
        """The /events endpoint should return a streaming response."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Publish an event so the stream has something to yield
            async def publish_and_close():
                await asyncio.sleep(0.05)
                app.state.event_bus.publish(
                    session_id="s1",
                    event_name="test:event",
                    data={"hello": "world"},
                )

            task = asyncio.create_task(publish_and_close())

            # Use a streaming request with a short timeout
            async with client.stream("GET", "/events") as resp:
                assert resp.status_code == 200
                # Read at least one line
                lines = []
                async for line in resp.aiter_lines():
                    lines.append(line)
                    if len(lines) >= 2:
                        break

            await task
            # We should have received at least the event
            assert len(lines) >= 1
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd amplifier-distro/amplifierd && python -m pytest tests/test_events_route.py -v
```
Expected: FAIL — route not found or `ModuleNotFoundError`

**Step 3: Write the implementation**

Create `amplifier-distro/amplifierd/src/amplifierd/routes/events.py`:

```python
"""Global SSE event streaming endpoint.

GET /events - subscribe to events from all sessions (or filtered by session/pattern).
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from starlette.responses import StreamingResponse

from amplifierd.state.event_bus import EventBus
from amplifierd.state.transport_event import TransportEvent

logger = logging.getLogger(__name__)

router = APIRouter(tags=["events"])

_KEEPALIVE_INTERVAL = 15.0  # seconds


async def _event_generator(
    event_bus: EventBus,
    *,
    session_id: str | None = None,
    filter_patterns: list[str] | None = None,
) -> AsyncIterator[str]:
    """Generate SSE frames from the EventBus.

    Yields SSE-formatted strings: "event: {name}\\ndata: {json}\\n\\n"
    """
    async for event in event_bus.subscribe(
        session_id=session_id,
        filter_patterns=filter_patterns,
    ):
        sse_data = json.dumps(event.to_sse_dict(), ensure_ascii=False)
        yield f"event: {event.event_name}\ndata: {sse_data}\n\n"


@router.get("/events")
async def events_stream(
    request: Request,
    session: str | None = None,
    filter: str | None = None,
    preset: str | None = None,
) -> StreamingResponse:
    """Global SSE event stream.

    Query params:
        session: Session ID (auto-includes descendants).
        filter: Comma-separated glob patterns for event names.
        preset: Named filter shorthand (streaming, tools, minimal, full, debug).
    """
    event_bus: EventBus = request.app.state.event_bus

    filter_patterns: list[str] | None = None
    if filter:
        filter_patterns = [f.strip() for f in filter.split(",")]

    return StreamingResponse(
        _event_generator(
            event_bus,
            session_id=session,
            filter_patterns=filter_patterns,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
```

In `amplifier-distro/amplifierd/src/amplifierd/app.py`, add after the sessions router:

```python
    from amplifierd.routes.events import router as events_router

    app.include_router(events_router)
```

**Step 4: Run tests to verify they pass**

Run:
```bash
cd amplifier-distro/amplifierd && python -m pytest tests/test_events_route.py -v
```
Expected: All tests PASS.

**Step 5: Commit**
```bash
cd amplifier-distro/amplifierd && git add -A && git commit -m "feat(amplifierd): global SSE events endpoint with session-tree filtering"
```

---

### Tasks 15-20: Remaining Routes

The remaining route tasks follow the same pattern established in Tasks 11-14. For each, create the route file, register it in `app.py`, and write integration tests.

### Task 15: Approvals Routes

**Files:**
- Create: `amplifier-distro/amplifierd/src/amplifierd/routes/approvals.py`
- Create: `amplifier-distro/amplifierd/tests/test_approvals_routes.py`
- Modify: `amplifier-distro/amplifierd/src/amplifierd/app.py` (add router)

Implement the three approval endpoints:
- `GET /sessions/{id}/approvals` — list pending approvals
- `POST /sessions/{id}/approvals/{request_id}` — respond to an approval
- `WS /sessions/{id}/approvals/ws` — bidirectional WebSocket approval channel

The approval handler uses `asyncio.Future` per `PendingApproval` keyed by `request_id`. The WebSocket handler pushes `approval:required` events and accepts `approval_response` messages.

Register the router in `app.py` after the events router.

**Commit:** `feat(amplifierd): approval routes with asyncio.Future-based gates`

---

### Task 16: Agent/Spawn Routes

**Files:**
- Create: `amplifier-distro/amplifierd/src/amplifierd/routes/agents.py`
- Create: `amplifier-distro/amplifierd/tests/test_agents_routes.py`
- Modify: `amplifier-distro/amplifierd/src/amplifierd/app.py`

Implement the four agent endpoints:
- `POST /sessions/{id}/spawn` — spawn child session (synchronous)
- `POST /sessions/{id}/spawn/stream` — spawn with SSE streaming
- `POST /sessions/{id}/spawn/{child_id}/resume` — resume child agent
- `GET /sessions/{id}/agents` — list available agents from bundle config

Uses `SessionManager.register()` for child sessions and `EventBus.register_child()` for tree propagation.

Register the router in `app.py`.

**Commit:** `feat(amplifierd): agent spawn/resume routes with session tree integration`

---

### Task 17: Bundle Routes

**Files:**
- Create: `amplifier-distro/amplifierd/src/amplifierd/routes/bundles.py`
- Create: `amplifier-distro/amplifierd/tests/test_bundles_routes.py`
- Modify: `amplifier-distro/amplifierd/src/amplifierd/app.py`

Implement the eight bundle endpoints:
- `GET /bundles` — list registered bundles
- `POST /bundles/register` — register name→URI
- `DELETE /bundles/{name}` — unregister
- `POST /bundles/load` — load and inspect
- `POST /bundles/prepare` — prepare for session creation
- `POST /bundles/compose` — compose multiple bundles
- `POST /bundles/{name}/check-updates` — check for updates
- `POST /bundles/{name}/update` — update to latest

Uses `app.state.bundle_registry` (the `BundleRegistry` from `amplifier_foundation`).

Register the router in `app.py`.

**Commit:** `feat(amplifierd): bundle management routes`

---

### Task 18: Context + Module Routes

**Files:**
- Create: `amplifier-distro/amplifierd/src/amplifierd/routes/context.py`
- Create: `amplifier-distro/amplifierd/src/amplifierd/routes/modules.py`
- Create: `amplifier-distro/amplifierd/tests/test_context_routes.py`
- Create: `amplifier-distro/amplifierd/tests/test_modules_routes.py`
- Modify: `amplifier-distro/amplifierd/src/amplifierd/app.py`

Context endpoints:
- `GET /sessions/{id}/context/messages` — get conversation messages
- `POST /sessions/{id}/context/messages` — inject a message
- `PUT /sessions/{id}/context/messages` — replace all messages
- `DELETE /sessions/{id}/context/messages` — clear context

Module endpoints:
- `GET /modules` — discover available modules
- `GET /modules/{id}` — module detail
- `POST /sessions/{id}/modules/mount` — hot-mount a module
- `POST /sessions/{id}/modules/unmount` — unmount a module
- `GET /sessions/{id}/modules` — list mounted modules

Register both routers in `app.py`.

**Commit:** `feat(amplifierd): context management and module management routes`

---

### Task 19: Validation + Reload Routes

**Files:**
- Create: `amplifier-distro/amplifierd/src/amplifierd/routes/validation.py`
- Create: `amplifier-distro/amplifierd/src/amplifierd/routes/reload.py`
- Create: `amplifier-distro/amplifierd/tests/test_validation_routes.py`
- Modify: `amplifier-distro/amplifierd/src/amplifierd/app.py`

Validation endpoints:
- `POST /validate/mount-plan` — validate mount plan configuration
- `POST /validate/module` — validate module protocol compliance
- `POST /validate/bundle` — validate a bundle

Reload endpoints:
- `POST /reload/bundles` — reload all registered bundles daemon-wide
- `GET /reload/status` — check what has updates available

Register both routers in `app.py`.

**Commit:** `feat(amplifierd): validation and reload routes`

---

### Task 20: Fork Endpoints (in sessions.py)

**Files:**
- Modify: `amplifier-distro/amplifierd/src/amplifierd/routes/sessions.py`
- Create: `amplifier-distro/amplifierd/tests/test_fork_routes.py`

Add fork endpoints to the existing sessions router:
- `POST /sessions/{id}/fork` — fork session at a turn
- `GET /sessions/{id}/fork/preview` — preview fork result
- `GET /sessions/{id}/turns` — list turn boundaries
- `GET /sessions/{id}/lineage` — get fork lineage
- `GET /sessions/{id}/forks` — list child forks

Uses `amplifier_foundation.session` fork/slice/lineage functions.

**Commit:** `feat(amplifierd): fork, lineage, and turn endpoints in sessions router`

---

## Phase 4: Assembly & Deployment

### Task 21: Wire All Routers in `routes/__init__.py`

**Files:**
- Modify: `amplifier-distro/amplifierd/src/amplifierd/routes/__init__.py`
- Modify: `amplifier-distro/amplifierd/src/amplifierd/app.py`

Update `routes/__init__.py` to export all routers for clean registration:

```python
"""FastAPI route modules — all routers registered here."""

from __future__ import annotations

from amplifierd.routes.agents import router as agents_router
from amplifierd.routes.approvals import router as approvals_router
from amplifierd.routes.bundles import router as bundles_router
from amplifierd.routes.context import router as context_router
from amplifierd.routes.events import router as events_router
from amplifierd.routes.health import router as health_router
from amplifierd.routes.modules import router as modules_router
from amplifierd.routes.reload import router as reload_router
from amplifierd.routes.sessions import router as sessions_router
from amplifierd.routes.validation import router as validation_router

ALL_ROUTERS = [
    health_router,
    sessions_router,
    events_router,
    approvals_router,
    agents_router,
    bundles_router,
    context_router,
    modules_router,
    validation_router,
    reload_router,
]
```

Update `app.py` to use the centralized router list:

```python
    from amplifierd.routes import ALL_ROUTERS

    for r in ALL_ROUTERS:
        app.include_router(r)
```

Run the full test suite:
```bash
cd amplifier-distro/amplifierd && python -m pytest tests/ -v
```
Expected: All tests PASS.

**Commit:** `feat(amplifierd): wire all routers via centralized routes/__init__.py`

---

### Task 22: Dockerfile + docker-compose.yml

**Files:**
- Create: `amplifier-distro/amplifierd/Dockerfile`
- Create: `amplifier-distro/amplifierd/docker-compose.yml`

**Step 1: Create Dockerfile**

Create `amplifier-distro/amplifierd/Dockerfile`:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install uv for fast dependency resolution
RUN pip install --no-cache-dir uv

# Copy project files
COPY pyproject.toml .
COPY src/ src/

# Install dependencies
RUN uv pip install --system -e .

# Expose the default port
EXPOSE 8410

# Run the daemon
CMD ["amplifierd", "serve", "--host", "0.0.0.0", "--port", "8410"]
```

**Step 2: Create docker-compose.yml**

Create `amplifier-distro/amplifierd/docker-compose.yml`:

```yaml
version: "3.8"

services:
  amplifierd:
    build: .
    ports:
      - "8410:8410"
    volumes:
      - ~/.amplifier:/root/.amplifier
      - ~/.amplifierd:/root/.amplifierd
    environment:
      - AMPLIFIERD_LOG_LEVEL=info
    restart: unless-stopped
```

**Step 3: Verify Docker build**

Run:
```bash
cd amplifier-distro/amplifierd && docker build -t amplifierd .
```
Expected: Builds successfully.

**Step 4: Commit**
```bash
cd amplifier-distro/amplifierd && git add -A && git commit -m "feat(amplifierd): Dockerfile and docker-compose.yml"
```

---

### Task 23: Full Test Suite Run + Type Check

**Step 1: Run full test suite**

Run:
```bash
cd amplifier-distro/amplifierd && python -m pytest tests/ -v --tb=short
```
Expected: All tests PASS.

**Step 2: Run type checks**

Run:
```bash
cd amplifier-distro/amplifierd && python -m pyright src/amplifierd/
```
Expected: No errors (warnings are acceptable for amplifier-core untyped imports).

**Step 3: Run linter**

Run:
```bash
cd amplifier-distro/amplifierd && python -m ruff check src/ tests/
```
Expected: No errors.

**Step 4: Format**

Run:
```bash
cd amplifier-distro/amplifierd && python -m ruff format src/ tests/
```

**Step 5: Final commit**
```bash
cd amplifier-distro/amplifierd && git add -A && git commit -m "chore(amplifierd): pass full test suite, type checks, and linting"
```

---

## Deferred (Not in Scope)

These items are explicitly deferred per design decisions:

- **File-watch auto-detection for stale** — The stale flag pattern supports this; add `watchfiles` dependency and a file watcher that calls `handle.mark_stale()`.
- **CamelCaseModel base class** — Add a `CamelCaseModel(BaseModel)` with alias generator if frontend consumers need camelCase JSON.
- **Automation/scheduler** — Not needed for a programmatic daemon.
- **Database persistence** — Filesystem only for now.
- **gRPC transport** — HTTP + SSE + WebSocket only for now.
- **StreamingHookRegistry decorator** — Implement when wiring real amplifier-core sessions (wraps `HookRegistry` to intercept `emit()` and publish to `EventBus`).
- **Session Index (`index.json`)** — Add when session counts justify the optimization. Currently `list_sessions()` iterates in-memory handles which is O(n) and fast.
- **Atomic file persistence (tmp+rename)** — Add when persistence hooks are wired to `SessionHandle`.

---

## Appendix: Import Reference

### amplifier-core imports used in this project

```python
from amplifier_core import (
    # Session + orchestration
    AmplifierSession, ModuleCoordinator, HookRegistry, CancellationToken,
    # Testing
    TestCoordinator, MockTool, ScriptedOrchestrator, MockContextManager, EventRecorder,
    create_test_coordinator, wait_for,
    # Models
    HookResult, ToolResult, SessionStatus, ModuleInfo, ProviderInfo, ModelInfo,
    # Errors (all 16 classes)
    LLMError, RateLimitError, QuotaExceededError, AuthenticationError,
    AccessDeniedError, ContextLengthError, ContentFilterError, InvalidRequestError,
    ProviderUnavailableError, NetworkError, LLMTimeoutError, NotFoundError,
    StreamError, AbortError, InvalidToolCallError, ConfigurationError,
    # Engine
    RUST_AVAILABLE,
)
from amplifier_core.events import ALL_EVENTS  # list of all 51 event name strings
```

### amplifier-foundation imports used in this project

```python
from amplifier_foundation import (
    # Bundle system
    Bundle, BundleRegistry, BundleState, UpdateInfo,
    load_bundle, validate_bundle, validate_bundle_or_raise,
    # Errors
    BundleError, BundleNotFoundError, BundleLoadError,
    BundleValidationError, BundleDependencyError,
    # Session capabilities
    get_working_dir, set_working_dir, WORKING_DIR_CAPABILITY,
    # Mentions
    BaseMentionResolver,
)
# PreparedBundle is returned by Bundle.prepare(), not directly imported
```
