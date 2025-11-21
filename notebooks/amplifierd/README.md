# Amplifierd API Notebooks

Interactive Jupyter notebooks demonstrating amplifierd HTTP API usage.

## Overview

These notebooks provide hands-on examples of all amplifierd API endpoints, organized by feature area. They're designed for experienced developers who want to understand and integrate with the amplifierd daemon.

## Prerequisites

### 1. Install Dependencies

```bash
pip install requests jupyter
```

### 2. Start Amplifierd Daemon

From the amplifier-dev workspace (required for runtime):

```bash
cd /data/repos/msft/amplifier/amplifier-dev
python -m amplifierd
```

The daemon runs on `http://127.0.0.1:8420` by default.

### 3. Launch Jupyter

```bash
cd /path/to/amplifierd
jupyter notebook notebooks/
```

## Notebook Series

### 01 - Getting Started
**File**: `01-getting-started.ipynb`

Introduction to amplifierd API:
- Health and status checks
- API configuration
- Error handling patterns
- Connection testing

**Start here** if you're new to the API.

### 02 - Sessions & Messages
**File**: `02-sessions-and-messages.ipynb`

Session management for LLM interactions:
- Creating and listing sessions
- Sending and retrieving messages
- Session lifecycle management
- Transcript handling

**Focus**: Conversational workflow orchestration

### 03 - Profile Management
**File**: `03-profile-management.ipynb`

Profile discovery and activation:
- **Phase 1 (Read)**: List, get, and explore profiles
- **Phase 2 (Write)**: Activate and deactivate profiles

**Focus**: Configuring LLM providers, tools, and hooks

### 04 - Collection Management
**File**: `04-collection-management.ipynb`

Collection discovery and mounting:
- **Phase 1 (Read)**: List and explore collections
- **Phase 2 (Write)**: Mount and unmount collections

**Focus**: Managing reusable configuration packages

### 05 - Module Management
**File**: `05-module-management.ipynb`

Module discovery and source configuration:
- **Phase 1 (Read)**: Discover all module types
- **Phase 2 (Write)**: Configure module sources with scoped overrides

**Focus**: Advanced module resolution and development workflows

## Learning Path

### For Quick Start
1. `01-getting-started.ipynb` - Verify connectivity
2. `02-sessions-and-messages.ipynb` - Basic functionality
3. Pick relevant notebooks based on your needs

### For Complete Understanding
Work through all notebooks in order (01 → 05).

### For Specific Tasks
- **Managing LLM configurations?** → `03-profile-management.ipynb`
- **Adding shared modules?** → `04-collection-management.ipynb`
- **Custom module development?** → `05-module-management.ipynb`

## API Coverage

### Complete Endpoint Reference

| Category | Read Endpoints (Phase 1) | Write Endpoints (Phase 2) |
|----------|-------------------------|---------------------------|
| **Status** | 3 endpoints | - |
| **Sessions** | 2 GET | 2 POST, 1 DELETE |
| **Messages** | 1 GET | 1 POST |
| **Profiles** | 3 GET | 1 POST, 1 DELETE |
| **Collections** | 2 GET | 1 POST, 1 DELETE |
| **Modules** | 7 GET | 1 POST, 1 PUT, 1 DELETE |

**Total**: 19 endpoints across all operations

## Features Demonstrated

### Phase 1 (Read Operations)
- ✓ Resource discovery (profiles, collections, modules)
- ✓ Detailed information retrieval
- ✓ Source tracking and type filtering
- ✓ Session and message management

### Phase 2 (Write Operations)
- ✓ Profile activation
- ✓ Collection mounting/unmounting
- ✓ Module source configuration
- ✓ Scoped configuration management (user/project/local)

## Safety Notes

**Configuration-modifying examples are commented out** to prevent accidental changes. Uncomment them when you're ready to modify your configuration.

Write operations modify these files:
- `~/.amplifier/settings.yaml` (user scope)
- `.amplifier/settings.yaml` (project scope)
- `.amplifier/settings.local.yaml` (local scope)
- `~/.amplifier/collections.lock` (collection registry)

**Recommendation**: Test write operations in a development environment first.

## Code Patterns

All notebooks follow consistent patterns:

### Request Pattern
```python
response = requests.get(f"{API_BASE}/endpoint")
data = print_response(response, "OPERATION NAME")
```

### Error Handling Pattern
```python
if response.ok:
    print("✓ Success")
elif response.status_code == 404:
    print("✗ Not found")
else:
    print(f"✗ Error: {response.status_code}")
```

### Workflow Pattern
```python
def workflow_example():
    # 1. Discovery
    # 2. Selection
    # 3. Operation
    # 4. Verification
```

## Philosophy Alignment

These notebooks demonstrate amplifierd's ruthless simplicity:
- Direct API calls (no unnecessary wrappers)
- Simple error handling (HTTP status codes)
- Clear examples (no over-abstraction)
- Practical workflows (real-world usage)

## Troubleshooting

### Connection Refused
```bash
# Verify daemon is running
ps aux | grep amplifierd

# Start daemon if not running
python -m amplifierd
```

### Import Errors
```bash
# Daemon requires amplifier-dev workspace
cd /data/repos/msft/amplifier/amplifier-dev
python -m amplifierd
```

### 404 Errors
- Check resource exists using list endpoints first
- Verify identifiers match exactly (case-sensitive)
- Some resources may not exist in fresh installations

## Additional Resources

- **Implementation docs**: `../PHASE1_IMPLEMENTATION.md`, `../PHASE2_IMPLEMENTATION.md`
- **Service layer**: `../amplifierd/services/README.md`
- **Tests**: `../tests/daemon/` - Additional examples
- **Philosophy**: `../ai_context/IMPLEMENTATION_PHILOSOPHY.md`

## Contributing

Found issues or have suggestions?
- Update notebooks directly
- Add new examples
- Report bugs via issues
- Follow ruthless simplicity philosophy

---

**Happy exploring!** Start with `01-getting-started.ipynb` and work your way through the series.
