# amplifierd

REST API daemon for amplifier-core with SSE streaming support.

## Overview

`amplifierd` exposes the `amplifier_library` functionality via a FastAPI REST API with Server-Sent Events (SSE) streaming for real-time execution updates.

## Architecture

```
amplifierd/
├── models/           # Pydantic request/response models
│   ├── requests.py
│   ├── responses.py
│   └── errors.py
├── routers/          # FastAPI routers
│   ├── sessions.py   # Session lifecycle
│   ├── messages.py   # Message operations & SSE streaming
│   └── status.py     # Health & status
├── streaming.py      # SSE utilities
├── main.py          # FastAPI application
└── __main__.py      # CLI entry point
```

## Running the Daemon

### Using Python module

```bash
python -m amplifierd
# or with uv
uv run python -m amplifierd
```

### Using uvicorn directly

```bash
uvicorn amplifierd.main:app --host 0.0.0.0 --port 8420
```

### Configuration

Configuration is loaded from `~/.config/amplifierd/daemon.yaml`:

```yaml
# Server settings
host: "127.0.0.1"
port: 8420
log_level: "info"
workers: 1

# Data directory root
amplifierd_root: "/data"
```

Environment variables override YAML settings (prefixed with `AMPLIFIERD_`):

```bash
AMPLIFIERD_PORT=8421 python -m amplifierd
```

## API Endpoints

### Sessions

- `POST /api/v1/sessions` - Create new session
- `GET /api/v1/sessions` - List all sessions
- `GET /api/v1/sessions/{session_id}` - Get session details
- `POST /api/v1/sessions/{session_id}/resume` - Resume session
- `DELETE /api/v1/sessions/{session_id}` - Delete session

### Messages

- `POST /api/v1/sessions/{session_id}/messages` - Send message (sync)
- `GET /api/v1/sessions/{session_id}/messages` - Get transcript
- `POST /api/v1/sessions/{session_id}/execute` - Execute with SSE streaming

### Status

- `GET /api/v1/status` - Get daemon status
- `GET /api/v1/health` - Health check

## SSE Streaming

The `/execute` endpoint uses Server-Sent Events for streaming responses:

```javascript
const eventSource = new EventSource('/api/v1/sessions/{session_id}/execute');

eventSource.addEventListener('message', (event) => {
  const data = JSON.parse(event.data);
  console.log('Content:', data.content);
});

eventSource.addEventListener('done', (event) => {
  console.log('Execution complete');
  eventSource.close();
});

eventSource.addEventListener('error', (event) => {
  const data = JSON.parse(event.data);
  console.error('Error:', data.error);
  eventSource.close();
});
```

## Interactive API Documentation

Once running, visit:

- **Swagger UI**: http://localhost:8420/docs
- **ReDoc**: http://localhost:8420/redoc
- **OpenAPI Schema**: http://localhost:8420/openapi.json

## Development

```bash
# Install dependencies
uv sync

# Run checks
make check

# Run tests
make test

# Start daemon
uv run python -m amplifierd
```

## Dependencies

- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `sse-starlette` - Server-Sent Events support
- `pydantic` - Data validation
- `amplifier_library` - Core library layer
