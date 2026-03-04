# Extending amplifierd with Plugins

Plugins add custom endpoints to the daemon. A plugin is a Python package that registers a FastAPI router via an entry point. No SDK, no base class -- just one function.

## The plugin contract

A plugin must:

1. Register an entry point in the `amplifierd.plugins` group.
2. Export a `create_router(state) -> fastapi.APIRouter` function.

That's it.

## Minimal plugin example

Create a package with this structure:

```
my-amplifierd-plugin/
  pyproject.toml
  src/my_plugin/__init__.py
```

**`pyproject.toml`**:

```toml
[project]
name = "my-amplifierd-plugin"
version = "0.1.0"
dependencies = ["fastapi"]

[project.entry-points."amplifierd.plugins"]
my-plugin = "my_plugin"

[tool.setuptools.packages.find]
where = ["src"]
```

**`src/my_plugin/__init__.py`**:

```python
from fastapi import APIRouter


def create_router(state) -> APIRouter:
    router = APIRouter(prefix="/my-plugin", tags=["my-plugin"])

    @router.get("/hello")
    async def hello():
        return {"message": "Hello from my plugin"}

    return router
```

Install it into the amplifierd environment and restart:

```bash
cd amplifierd
uv pip install -e ../my-amplifierd-plugin
uv run amplifierd serve
```

Your endpoint is now live at `GET /my-plugin/hello`.

## Accessing daemon state

The `state` argument passed to `create_router` is `app.state` from the FastAPI application. It gives plugins access to everything the daemon manages:

| Attribute | Type | What it gives you |
|-----------|------|-------------------|
| `state.session_manager` | `SessionManager` | Create, lookup, list, and destroy sessions |
| `state.event_bus` | `EventBus` | Publish events, subscribe to SSE streams |
| `state.bundle_registry` | `BundleRegistry` or `None` | Load, prepare, compose bundles |
| `state.settings` | `DaemonSettings` | Read daemon configuration |

**Example -- a plugin that publishes custom events:**

```python
from fastapi import APIRouter, Request


def create_router(state) -> APIRouter:
    router = APIRouter(prefix="/metrics", tags=["metrics"])

    @router.post("/report")
    async def report_metric(request: Request, name: str, value: float):
        event_bus = request.app.state.event_bus
        event_bus.publish(
            session_id="system",
            event_name="metrics:report",
            data={"name": name, "value": value},
        )
        return {"status": "published"}

    return router
```

**Example -- a plugin that wraps session creation with custom logic:**

```python
from fastapi import APIRouter, Request


def create_router(state) -> APIRouter:
    router = APIRouter(prefix="/quick", tags=["quick"])

    @router.post("/ask")
    async def quick_ask(request: Request, prompt: str, bundle: str = "default"):
        manager = request.app.state.session_manager
        registry = request.app.state.bundle_registry

        # Load and prepare the bundle
        loaded = registry.load(bundle)
        prepared = loaded.prepare()

        # Create a session, execute, and tear down
        handle = manager.register(
            session=prepared.create_session(),
            prepared_bundle=prepared,
            bundle_name=bundle,
        )
        try:
            result = await handle.execute(prompt)
            return {"response": str(result)}
        finally:
            await manager.destroy(handle.session_id)

    return router
```

## Disabling plugins

In `~/.amplifierd/settings.json`:

```json
{
    "disabled_plugins": ["my-plugin"]
}
```

Or via environment variable:

```bash
AMPLIFIERD_DISABLED_PLUGINS='["my-plugin"]' amplifierd serve
```

## Plugin resilience

Plugin failures never crash the daemon. If `create_router` raises an exception or returns something that isn't an `APIRouter`, the error is logged and that plugin is skipped. All other plugins and core endpoints continue to work.
