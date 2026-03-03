# amplifierd Implementation Plan — Resume (Tasks 15–23)

> **This is a trimmed resume of the original `implementation-plan.md`.** Tasks 1–14 have already been implemented and committed. This file contains only the remaining tasks (15–23) with all specification details preserved verbatim.

**Goal:** Build `amplifierd`, a long-running localhost daemon that exposes amplifier-core and amplifier-foundation capabilities over HTTP, SSE, and WebSocket.

**Architecture:** FastAPI + uvicorn daemon with in-memory `SessionManager` (per-session serialized execution queue), global `EventBus` (async pub/sub with session-tree propagation), and filesystem persistence. All state accessed via `app.state` — no module-level singletons. Plugin system via Python entry points.

**Tech Stack:** Python 3.12, FastAPI, uvicorn, pydantic / pydantic-settings, sse-starlette, click, amplifier-core, amplifier-foundation, httpx (tests), pytest + pytest-asyncio (tests)

---

## Context: What's Already Built (Tasks 1–14)

### Package & Config (Tasks 1–2)
- `amplifier-distro/amplifierd/pyproject.toml`
- `amplifier-distro/amplifierd/src/amplifierd/__init__.py`
- `amplifier-distro/amplifierd/src/amplifierd/__main__.py`
- `amplifier-distro/amplifierd/src/amplifierd/config.py` — `DaemonSettings` via pydantic-settings, `AMPLIFIERD_` prefix, port 8410

### Pydantic Models (Tasks 3–4)
- `amplifier-distro/amplifierd/src/amplifierd/models/__init__.py`
- `amplifier-distro/amplifierd/src/amplifierd/models/common.py` — `ProblemDetail` (RFC 7807), `ErrorTypeURI`, `CamelCaseModel`
- `amplifier-distro/amplifierd/src/amplifierd/models/errors.py`
- `amplifier-distro/amplifierd/src/amplifierd/models/sessions.py`
- `amplifier-distro/amplifierd/src/amplifierd/models/events.py`
- `amplifier-distro/amplifierd/src/amplifierd/models/agents.py`
- `amplifier-distro/amplifierd/src/amplifierd/models/bundles.py`
- `amplifier-distro/amplifierd/src/amplifierd/models/modules.py`

### Error Handlers (Task 5)
- `amplifier-distro/amplifierd/src/amplifierd/errors.py` — LLM/Bundle error → HTTP status mapping, `register_error_handlers()`

### Core State (Tasks 6–9)
- `amplifier-distro/amplifierd/src/amplifierd/state/__init__.py`
- `amplifier-distro/amplifierd/src/amplifierd/state/transport_event.py` — `__slots__`-based event carrier with `to_sse_dict()`
- `amplifier-distro/amplifierd/src/amplifierd/state/event_bus.py` — async pub/sub, session-tree propagation, bounded queues, backpressure
- `amplifier-distro/amplifierd/src/amplifierd/state/session_handle.py` — wraps `AmplifierSession`, serialized `execute()`, stale flag, children tracking
- `amplifier-distro/amplifierd/src/amplifierd/state/session_manager.py` — central registry: `register()`, `get()`, `list_sessions()`, `destroy()`, `shutdown()`

### Plugin Discovery (Task 10)
- `amplifier-distro/amplifierd/src/amplifierd/plugins.py` — entry point group `amplifierd.plugins`, disabled list, error resilience

### App Factory + Health Routes (Task 11)
- `amplifier-distro/amplifierd/src/amplifierd/app.py` — `create_app()` factory, lifespan manager (EventBus → SessionManager → BundleRegistry → plugins)
- `amplifier-distro/amplifierd/src/amplifierd/routes/__init__.py` (stub)
- `amplifier-distro/amplifierd/src/amplifierd/routes/health.py` — `GET /health`, `GET /info`

### CLI (Task 12)
- `amplifier-distro/amplifierd/src/amplifierd/cli.py` — Click `amplifierd serve` command with `--host`, `--port`, `--reload`, `--log-level`

### Session CRUD Routes (Task 13)
- `amplifier-distro/amplifierd/src/amplifierd/routes/sessions.py` — `GET /sessions`, `GET /{id}`, `PATCH /{id}`, `DELETE /{id}`, `POST /{id}/execute`, `POST /{id}/execute/stream` (202), `POST /{id}/cancel`, `POST /{id}/stale`, `GET /{id}/tree`

### Global SSE Events (Task 14)
- `amplifier-distro/amplifierd/src/amplifierd/routes/events.py` — `GET /events` via `StreamingResponse`, session filter, pattern filtering

### Tests (Tasks 1–14)
- `amplifier-distro/amplifierd/tests/conftest.py`
- `amplifier-distro/amplifierd/tests/test_config.py`
- `amplifier-distro/amplifierd/tests/test_errors.py`
- `amplifier-distro/amplifierd/tests/test_event_bus.py`
- `amplifier-distro/amplifierd/tests/test_health.py`
- `amplifier-distro/amplifierd/tests/test_models.py`
- `amplifier-distro/amplifierd/tests/test_package_skeleton.py`
- `amplifier-distro/amplifierd/tests/test_plugins.py`
- `amplifier-distro/amplifierd/tests/test_session_handle.py`
- `amplifier-distro/amplifierd/tests/test_session_manager.py`
- `amplifier-distro/amplifierd/tests/test_transport_event.py`
- `amplifier-distro/amplifierd/tests/test_cli.py`
- `amplifier-distro/amplifierd/tests/test_sessions_routes.py`
- `amplifier-distro/amplifierd/tests/test_events_route.py`

---

## Phase 3: Routes — Remaining (Tasks 15–20)

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
