# Amplifierd API Notebooks

Interactive Jupyter notebooks demonstrating amplifierd HTTP API usage.

## Overview

These notebooks provide hands-on examples of all amplifierd API endpoints, organized by feature area. They're designed for experienced developers who want to understand and integrate with the amplifierd daemon.

**Architecture**: Amplifierd uses a collection-based resource management system:
- **Collections**: Git repositories or local directories containing profiles, agents, context, and tools
- **Registry**: `collections.yaml` tracks collection metadata, sources, and assets
- **Compilation**: Profiles are compiled on-demand with full asset resolution
- **Discovery**: Auto-discovery scans registry and compiles profiles with dependencies

### Directory Structure

```
$AMPLIFIERD_HOME/
├── cache/
│   ├── git/{commit-hash}/           # Git repo caches
│   └── fsspec/http/                 # HTTP URL caches
├── share/
│   ├── collections.yaml             # Collection registry
│   └── profiles/{collection}/{profile}/
│       ├── {profile}.md             # Manifest (preserves original)
│       ├── orchestrator/            # Orchestrator module
│       ├── agents/                  # Agent files
│       ├── context/                 # Context directory
│       ├── tools/                   # Tool modules
│       ├── hooks/                   # Hook modules
│       └── providers/               # Provider modules
└── state/
    └── active_profile.txt           # Active profile name
```

**Key Points:**
- **Git subdirectory support**: Collections can reference subdirectories using `#subdirectory=path`
- **Schema v2 only**: All profiles use schema_version 2 format
- **Auto-compilation**: Profiles compiled automatically with full asset resolution
- **Manifest preservation**: Original `.md` manifests preserved alongside compiled assets
- **No extends support**: Profiles are self-contained after compilation

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
- **Read Operations**: List and get compiled profiles with full asset resolution
- **Write Operations**: Activate and deactivate profiles
- **Profile Format**: Schema v2 only (schema_version: 2)
- **Discovery**: Auto-discovery compiles profiles from registry on demand
- **Compilation**: Full asset resolution with module copying
- **Activation**: Stored in plain text file (`active_profile.txt`)

**Focus**: Configuring LLM providers, tools, hooks, and compiled profiles

### 04 - Collection Management
**File**: `04-collection-management.ipynb`

Collection registry and synchronization:
- **Read Operations**: List collections from registry (`collections.yaml`)
- **Write Operations**: Sync registry (discover collections and profiles)
- **Collection Sources**: Git repositories or local directories
- **Git Subdirectories**: Support for `#subdirectory=path` syntax
- **Registry Format**: YAML with metadata, sources, and asset tracking
- **Auto-Discovery**: Automatic profile compilation during sync

**Focus**: Managing collection registry and profile discovery

### 05 - Module Management
**File**: `05-module-management.ipynb`

Module discovery and resolution:
- **Read Operations**: List modules from compiled profiles
- **Module Resolution**: Follow refs to source collections
- **Module Types**: orchestrator, agents, context, tools, hooks, providers
- **Discovery**: Modules compiled into profile directories during profile compilation
- **Metadata**: Module information from source collection manifests
- **Namespace**: Collection-qualified references (e.g., `@foundation/context/shared`)

**Focus**: Understanding module resolution and compiled profile structure

### 06 - Mount Plan Generation
**File**: `06-mount-plan-generation.ipynb`

Mount plan generation from cached profiles:
- **Generate Plans**: Convert profiles into structured mount plans
- **Mount Types**: EmbeddedMount (agents/context) vs ReferencedMount (providers/tools/hooks)
- **Module IDs**: Convention `{profile}.{type}.{name}` for unique identification
- **Organization**: Automatic grouping by module type
- **Settings**: Apply settings overrides during generation
- **Format Versioning**: Plans include formatVersion for compatibility

**Focus**: Understanding mount plan structure and generation

### 07 - Session Lifecycle
**File**: `07-session-lifecycle.ipynb`

Enhanced session management with mount plan integration:
- **Session Creation**: Automatic mount plan generation on session creation
- **Lifecycle States**: CREATED → ACTIVE → COMPLETED/FAILED/TERMINATED
- **Message Management**: Append messages to transcript, retrieve conversation history
- **Session Queries**: Filter by status, profile, date range
- **State Persistence**: Atomic updates with session.json, transcript.jsonl
- **Error Handling**: Fail sessions with error details, terminate sessions
- **Cleanup**: Age-based cleanup with status protection

**Focus**: Complete session lifecycle with mount plans and transcripts

### 08 - Amplified Directories
**File**: `08-amplified-directories.ipynb`

Multi-directory context management:
- **Directory Management**: Create, list, update, delete amplified directories
- **Profile Inheritance**: Child directories inherit `default_profile` from parent
- **Session Integration**: Sessions tied to specific amplified directories
- **Root Auto-Amplification**: Root directory auto-amplified on daemon startup
- **Metadata Schema**: Required `default_profile` + optional user fields
- **Security**: Path validation prevents directory traversal attacks

**Focus**: Managing multiple working directory contexts with independent settings

## Learning Path

### For Quick Start
1. `01-getting-started.ipynb` - Verify connectivity
2. `02-sessions-and-messages.ipynb` - Basic functionality
3. Pick relevant notebooks based on your needs

### For Complete Understanding
Work through all notebooks in order (01 → 08).

### For Specific Tasks
- **Managing LLM configurations?** → `03-profile-management.ipynb`
- **Adding shared modules?** → `04-collection-management.ipynb`
- **Understanding module structure?** → `05-module-management.ipynb`
- **Generating mount plans?** → `06-mount-plan-generation.ipynb`
- **Managing session lifecycle?** → `07-session-lifecycle.ipynb`
- **Working with multiple projects?** → `08-amplified-directories.ipynb`

## API Coverage

### Complete Endpoint Reference

| Category | Read Endpoints | Write Endpoints |
|----------|----------------|-----------------|
| **Status** | 3 endpoints | - |
| **Sessions** | 4 GET | 6 POST, 1 DELETE |
| **Messages** | 1 GET | 1 POST |
| **Profiles** | 3 GET | 1 POST, 1 DELETE |
| **Collections** | 2 GET | 1 POST, 1 DELETE |
| **Modules** | 7 GET | - |
| **Mount Plans** | 1 GET | 1 POST |
| **Amplified Directories** | 2 GET | 1 POST, 1 PATCH, 1 DELETE |

**Total**: 35+ endpoints across all operations

## Features Demonstrated

### Read Operations
- ✓ Resource discovery (profiles, collections, modules)
- ✓ Detailed information retrieval
- ✓ Source tracking and type filtering
- ✓ Session and message management

### Write Operations
- ✓ Profile activation
- ✓ Collection mounting/unmounting

## Safety Notes

**Configuration-modifying examples are commented out** to prevent accidental changes. Uncomment them when you're ready to modify your configuration.

Write operations modify:
- `~/.amplifier/amplifierd/active_profile.txt` - Active profile name
- `~/.amplifier/collections/` - Collection directories (mount/unmount)

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

### Missing Refs During Compilation
- Verify collection is registered in `collections.yaml`
- Check ref syntax matches `@collection/module_type/module_name`
- Ensure source collection contains referenced module
- Run collection sync to refresh registry

### Schema v1 Profiles Rejected
- All profiles must use `schema_version: 2`
- No support for legacy schema v1 profiles
- Update profile manifests to schema v2 format

### Subdirectory Not Found
- Verify Git URL includes `#subdirectory=path` fragment
- Check subdirectory path exists in repository
- Ensure path is relative to repository root

### Cache Location Issues
- Git repos cached in `$AMPLIFIERD_HOME/cache/git/{commit-hash}/`
- HTTP URLs cached in `$AMPLIFIERD_HOME/cache/fsspec/http/`
- Clear cache by removing cache directories

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
