# Amplifier Tools Guide

**Comprehensive guide for understanding and working with Amplifier tools**

---

## Table of Contents

1. [What Are Tools?](#what-are-tools)
2. [How Tools Work](#how-tools-work)
3. [Available Tools](#available-tools)
4. [Tool Contract](#tool-contract)
5. [Configuration](#configuration)
6. [Security and Safety](#security-and-safety)
7. [Best Practices](#best-practices)
8. [Creating Custom Tools](#creating-custom-tools)
9. [Troubleshooting](#troubleshooting)
10. [Reference](#reference)

---

## What Are Tools?

**Tools** are capabilities that extend what an Amplifier agent can do. They enable the LLM to interact with external systems, read files, execute commands, search the web, and perform other actions beyond text generation.

### Key Characteristics

- **LLM-callable**: Declared in a format LLMs can use (schema)
- **Safe execution**: Sandboxed and validated
- **Configurable**: Paths, permissions, behavior customizable
- **Composable**: Multiple tools work together
- **Observable**: Execution tracked via hooks

### Philosophy

Tools embody the "capabilities" principle:
- **Mechanism for action**: Tools are how agents interact with the world
- **Kernel manages**: Loading, validation, execution
- **Modules provide**: Implementation of specific capabilities
- **Safety first**: Security and validation built-in

Think of it as: **Tools are the agent's hands.**

---

## How Tools Work

### The Lifecycle

```
┌─────────────────────┐
│  1. Tool Mounted    │  Module mounts tool with schema
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  2. Schema Provided │  LLM knows tool exists and how to use it
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  3. LLM Decides     │  LLM generates tool_use
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  4. Orchestrator    │  Orchestrator extracts tool call
│     Extracts        │
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  5. Validation      │  Check params against schema
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  6. Tool Executes   │  Tool implementation runs
└──────────┬──────────┘
           │
┌──────────▼──────────┐
│  7. Result Returned │  Output returned to LLM
└─────────────────────┘
```

### Integration with Session

```python
# Tools mounted automatically from mount plan
mount_plan = {
    "session": {
        "orchestrator": "loop-streaming",
        "context": "context-simple"
    },
    "tools": [
        {
            "module": "tool-filesystem",
            "source": "git+https://...",
            "config": {
                "allowed_write_paths": ["."]
            }
        },
        {
            "module": "tool-bash",
            "source": "git+https://..."
        }
    ]
}

async with AmplifierSession(config=mount_plan) as session:
    # LLM can now use read_file, write_file, execute_bash
    response = await session.execute("Read test.txt and count the lines")
    # Behind the scenes:
    # 1. LLM: tool_use(read_file, file_path="test.txt")
    # 2. Tool executes: returns contents
    # 3. LLM: counts lines, responds "The file has 42 lines"
```

---

## Available Tools

### tool-filesystem

**File reading, writing, and editing.**

**Tools provided:**
- `read_file`: Read file contents with line numbers
- `write_file`: Write/overwrite files
- `edit_file`: Exact string replacements

**Configuration:**
```yaml
tools:
  - module: tool-filesystem
    source: git+https://github.com/microsoft/amplifier-module-tool-filesystem@main
    config:
      # Read operations (permissive by default)
      allowed_read_paths: null  # null = allow all reads

      # Write/Edit operations (restrictive by default)
      allowed_write_paths: ["."]  # Current dir + subdirs only

      require_approval: false  # Require human approval for writes
```

**Philosophy:**
- Reads are low-risk (consuming data) → permissive
- Writes are high-risk (modifying state) → restrictive

**Example usage:**
```python
response = await session.execute("Read config.yaml and change port to 8080")

# LLM will:
# 1. read_file(file_path="config.yaml")
# 2. edit_file(file_path="config.yaml", old_string="port: 3000", new_string="port: 8080")
```

---

### tool-bash

**Execute shell commands safely.**

**Tools provided:**
- `execute_bash`: Run bash commands with sandboxing

**Configuration:**
```yaml
tools:
  - module: tool-bash
    source: git+https://github.com/microsoft/amplifier-module-tool-bash@main
    config:
      allow_dangerous: false    # Prevent rm, dd, mkfs, etc.
      timeout: 60               # Command timeout (seconds)
      working_directory: "."    # Default working directory
      require_approval: true    # Require human approval
```

**Safety features:**
- Command whitelisting/blacklisting
- Timeout enforcement
- Working directory restrictions
- Output size limits

**Example usage:**
```python
response = await session.execute("Run tests and show me the results")

# LLM will:
# execute_bash(command="pytest tests/")
```

---

### tool-web

**Fetch and parse web content.**

**Tools provided:**
- `fetch_url`: Download and extract text from URLs

**Configuration:**
```yaml
tools:
  - module: tool-web
    source: git+https://github.com/microsoft/amplifier-module-tool-web@main
    config:
      allowed_domains: null     # null = allow all domains
      blocked_domains: []       # Explicitly block domains
      timeout: 30               # Request timeout
      max_content_length: 1MB   # Limit download size
```

**Example usage:**
```python
response = await session.execute("Fetch the latest news from example.com")

# LLM will:
# fetch_url(url="https://example.com/news")
```

---

### tool-search

**Search code and files using grep/ripgrep.**

**Tools provided:**
- `grep`: Search for patterns in files
- `rg`: Fast ripgrep-based search

**Configuration:**
```yaml
tools:
  - module: tool-search
    source: git+https://github.com/microsoft/amplifier-module-tool-search@main
    config:
      allowed_paths: ["."]      # Limit search scope
      max_results: 100          # Limit result count
```

**Example usage:**
```python
response = await session.execute("Find all functions named 'process' in the codebase")

# LLM will:
# grep(pattern="def process", paths=["."])
```

---

### tool-task

**Spawn sub-agents for delegation.**

**Tools provided:**
- `spawn_task`: Create child session with agent configuration

**Configuration:**
```yaml
tools:
  - module: tool-task
    source: git+https://github.com/microsoft/amplifier-module-tool-task@main
    config:
      max_concurrent: 3         # Max parallel sub-agents
      timeout: 600              # Sub-agent timeout
```

**Requires agents section:**
```yaml
agents:
  bug-hunter:
    description: "Debugging specialist"
    providers:
      - module: provider-anthropic
        config:
          model: claude-opus-4-1  # Stronger model for sub-agent
    tools:
      - module: tool-filesystem
      # Note: no tool-task (prevent recursive delegation)
    system:
      instruction: "You are a debugging specialist..."
```

**Example usage:**
```python
response = await session.execute("Investigate the crash in auth.py using bug-hunter agent")

# LLM will:
# spawn_task(agent_name="bug-hunter", task="Investigate crash in auth.py")
```

---

### tool-todo

**Manage todo lists for task tracking.**

**Tools provided:**
- `update_todos`: Add, update, remove todos

**Configuration:**
```yaml
tools:
  - module: tool-todo
    source: git+https://github.com/microsoft/amplifier-module-tool-todo@main
    config:
      storage_path: .amplifier/todos
```

**Example usage:**
```python
response = await session.execute("Add a todo to implement caching")

# LLM will:
# update_todos(todos=[{"content": "Implement caching", "status": "pending"}])
```

---

### Comparison Matrix

| Tool | Category | Safety Level | Typical Use |
|------|----------|--------------|-------------|
| **tool-filesystem** | File I/O | Medium (configurable) | Read/write files |
| **tool-bash** | Execution | High risk | Run commands |
| **tool-web** | Network | Low risk | Fetch URLs |
| **tool-search** | Search | Low risk | Find code |
| **tool-task** | Delegation | Medium | Spawn sub-agents |
| **tool-todo** | State | Low risk | Track tasks |

---

## Tool Contract

### Mount Function

Every tool module must implement:

```python
async def mount(coordinator, config: dict):
    """
    Mount tool(s) with coordinator.

    Args:
        coordinator: The session coordinator
        config: Configuration from mount plan

    Returns:
        Optional cleanup function
    """
    # Register tool(s)
    coordinator.register_tool(
        name="my_tool",
        description="Tool description for LLM",
        parameters={
            "type": "object",
            "properties": {
                "param1": {"type": "string", "description": "First param"}
            },
            "required": ["param1"]
        },
        function=my_tool_implementation
    )

    # Optional: return cleanup function
    async def cleanup():
        # Clean up resources
        pass

    return cleanup
```

### Tool Implementation

```python
async def my_tool_implementation(param1: str, param2: int = 10) -> str:
    """
    Tool implementation.

    Args:
        param1: Required parameter
        param2: Optional parameter with default

    Returns:
        Tool result as string (returned to LLM)

    Raises:
        ValueError: If parameters invalid
        RuntimeError: If execution fails
    """
    # Validate inputs
    if not param1:
        raise ValueError("param1 is required")

    # Execute tool logic
    result = do_something(param1, param2)

    # Return result
    return f"Operation completed: {result}"
```

### Tool Schema

Tools use JSON Schema for parameter validation:

```python
{
    "type": "object",
    "properties": {
        "file_path": {
            "type": "string",
            "description": "Absolute path to the file"
        },
        "offset": {
            "type": "integer",
            "description": "Line number to start reading (optional)",
            "minimum": 1
        },
        "limit": {
            "type": "integer",
            "description": "Number of lines to read (optional)",
            "minimum": 1,
            "maximum": 10000
        }
    },
    "required": ["file_path"]
}
```

### Entry Point

```toml
# pyproject.toml
[project.entry-points."amplifier.modules"]
tool-mytool = "amplifier_module_tool_mytool:mount"
```

---

## Configuration

### Mount Plan Configuration

```python
{
    "tools": [
        {
            "module": "tool-filesystem",
            "source": "git+https://github.com/microsoft/amplifier-module-tool-filesystem@main",
            "config": {
                "allowed_write_paths": ["."],
                "require_approval": false
            }
        },
        {
            "module": "tool-bash",
            "source": "git+https://github.com/microsoft/amplifier-module-tool-bash@main",
            "config": {
                "allow_dangerous": false,
                "timeout": 60,
                "require_approval": true
            }
        }
    ]
}
```

### Profile Configuration

```yaml
# profiles/dev.md
---
tools:
  - module: tool-filesystem
    source: git+https://...
    config:
      allowed_write_paths: ["."]
      require_approval: false  # Dev: no approval needed

  - module: tool-bash
    source: git+https://...
    config:
      allow_dangerous: false  # Never allow dangerous commands
      require_approval: true   # Always approve bash
---
```

---

## Security and Safety

### Path Validation (tool-filesystem)

**Read operations:**
```yaml
config:
  allowed_read_paths: null  # Allow all (default)
  # Or restrict:
  allowed_read_paths: ["/app/data", "/tmp"]
```

**Write operations:**
```yaml
config:
  allowed_write_paths: ["."]  # Current directory only (default)
  # Or expand:
  allowed_write_paths: [".", "/app/uploads"]
```

**Path traversal protection:**
- All paths resolved to absolute before checking
- Subdirectory traversal allowed (current dir + children)
- Parent directory traversal blocked (`../` attacks prevented)

---

### Command Safety (tool-bash)

**Dangerous command blocking:**
```yaml
config:
  allow_dangerous: false  # Block rm, dd, mkfs, etc.
```

**Blocked commands** (when `allow_dangerous: false`):
- `rm -rf` (recursive delete)
- `dd` (disk operations)
- `mkfs` (format filesystem)
- `:(){ :|:& };:` (fork bomb)
- And more...

**Timeout enforcement:**
```yaml
config:
  timeout: 60  # Kill after 60 seconds
```

---

### Approval Requirements

**For high-risk operations:**
```yaml
config:
  require_approval: true  # Human must approve
```

**How it works:**
1. LLM requests tool execution
2. Orchestrator pauses
3. Hook emits `tool:approval:requested` event
4. Human reviews and approves/rejects
5. Execution continues or aborts

**Approval hook (hooks-approval):**
```yaml
hooks:
  - module: hooks-approval
    source: git+https://...
    config:
      auto_approve: false  # Manual approval
      timeout: 300         # Wait up to 5 min
```

---

### Network Safety (tool-web)

**Domain filtering:**
```yaml
config:
  allowed_domains: ["example.com", "trusted.org"]
  # Or block specific domains:
  blocked_domains: ["malicious.com"]
```

**Content limits:**
```yaml
config:
  max_content_length: 1048576  # 1MB limit
  timeout: 30                   # Request timeout
```

---

## Best Practices

### 1. Principle of Least Privilege

**Grant minimal permissions needed:**

```yaml
# Bad: Allow all
tools:
  - module: tool-filesystem
    config:
      allowed_write_paths: ["/"]  # Too permissive!

# Good: Restrict to project
tools:
  - module: tool-filesystem
    config:
      allowed_write_paths: ["."]  # Current project only
```

### 2. Separate Development and Production

**Development (permissive):**
```yaml
tools:
  - module: tool-bash
    config:
      allow_dangerous: false
      require_approval: false  # Trust agent in dev
```

**Production (restrictive):**
```yaml
tools:
  - module: tool-bash
    config:
      allow_dangerous: false
      require_approval: true   # Always approve in prod
```

### 3. Use Appropriate Tools

**Don't use bash for file operations:**
```yaml
# Bad: Using bash for file ops
tools:
  - module: tool-bash

# Agent does:
# execute_bash(command="cat file.txt")

# Good: Use dedicated file tool
tools:
  - module: tool-filesystem

# Agent does:
# read_file(file_path="file.txt")
```

**Why?** Dedicated tools have:
- Better error handling
- Cleaner output (line numbers, formatting)
- Safer validation
- More LLM-friendly APIs

### 4. Compose Tools Effectively

**Enable complementary tools:**
```yaml
tools:
  - module: tool-search       # Find code
  - module: tool-filesystem   # Read/edit files
  - module: tool-bash         # Run tests

# Agent workflow:
# 1. grep(pattern="def authenticate")  # Find auth code
# 2. read_file(file_path="auth.py")    # Read implementation
# 3. edit_file(old="...", new="...")   # Fix bug
# 4. execute_bash(command="pytest")    # Verify fix
```

### 5. Monitor Tool Usage

**Enable logging:**
```yaml
hooks:
  - module: hooks-logging
    config:
      level: INFO  # Log all tool calls

# Logs show:
# tool:invoked: read_file(file_path="/data/config.yaml")
# tool:completed: read_file ✓
```

**Track metrics:**
- Tool call frequency
- Success/failure rates
- Execution times
- Error patterns

---

## Creating Custom Tools

### Step 1: Define Tool Schema

```python
# amplifier_module_tool_mytool/__init__.py

async def mount(coordinator, config):
    """Mount custom tool."""

    # Define tool schema
    coordinator.register_tool(
        name="my_custom_tool",
        description="Does something useful for the LLM",
        parameters={
            "type": "object",
            "properties": {
                "input_text": {
                    "type": "string",
                    "description": "Text to process"
                },
                "mode": {
                    "type": "string",
                    "enum": ["fast", "accurate"],
                    "description": "Processing mode"
                }
            },
            "required": ["input_text"]
        },
        function=my_custom_tool_impl
    )
```

### Step 2: Implement Tool Logic

```python
async def my_custom_tool_impl(input_text: str, mode: str = "fast") -> str:
    """
    Tool implementation.

    Args:
        input_text: Text to process
        mode: Processing mode

    Returns:
        Processed result
    """
    # Validate
    if not input_text:
        raise ValueError("input_text cannot be empty")

    if mode not in ["fast", "accurate"]:
        raise ValueError(f"Invalid mode: {mode}")

    # Execute
    if mode == "fast":
        result = fast_process(input_text)
    else:
        result = accurate_process(input_text)

    # Return
    return f"Processed: {result}"
```

### Step 3: Add Configuration

```python
async def mount(coordinator, config):
    # Extract config
    max_length = config.get("max_length", 1000)
    allow_html = config.get("allow_html", False)

    # Use in tool
    async def my_custom_tool_impl(input_text: str, mode: str = "fast") -> str:
        if len(input_text) > max_length:
            raise ValueError(f"Input too long (max: {max_length})")

        if not allow_html and "<" in input_text:
            raise ValueError("HTML not allowed")

        # ... rest of implementation
```

### Step 4: Package as Module

```toml
# pyproject.toml
[project]
name = "amplifier-module-tool-mytool"
version = "1.0.0"

dependencies = [
    "amplifier-core>=1.0.0"
]

[project.entry-points."amplifier.modules"]
tool-mytool = "amplifier_module_tool_mytool:mount"
```

### Step 5: Use in Profile

```yaml
tools:
  - module: tool-mytool
    source: git+https://github.com/org/amplifier-module-tool-mytool@main
    config:
      max_length: 5000
      allow_html: true
```

---

## Troubleshooting

### Issue: Tool Not Found

**Error:** `Tool 'my_tool' not found`

**Causes:**
1. Tool module not mounted
2. Wrong tool name in LLM call
3. Module failed to register tool

**Solutions:**

1. **Verify module mounted:**
   ```yaml
   tools:
     - module: tool-mytool  # Must be in mount plan
       source: git+https://...
   ```

2. **Check tool registration:**
   ```python
   # In module's mount():
   coordinator.register_tool(
       name="my_tool",  # This name must match LLM call
       ...
   )
   ```

3. **Enable debug logging:**
   ```yaml
   hooks:
     - module: hooks-logging
       config:
         level: DEBUG  # See tool registration
   ```

---

### Issue: Permission Denied

**Error:** `Permission denied: /path/to/file`

**Causes:**
1. Path outside allowed_write_paths
2. Path traversal blocked
3. File permissions

**Solutions:**

1. **Check allowed paths:**
   ```yaml
   tools:
     - module: tool-filesystem
       config:
         allowed_write_paths: ["."]  # Expand if needed
   ```

2. **Use absolute paths:**
   ```python
   # Resolve to absolute before calling
   from pathlib import Path
   abs_path = Path("relative/path").resolve()
   ```

3. **Check file permissions:**
   ```bash
   ls -la /path/to/file
   chmod 644 /path/to/file  # If needed
   ```

---

### Issue: Tool Execution Timeout

**Error:** `Tool execution timeout after 60s`

**Causes:**
1. Tool operation too slow
2. Timeout too short
3. Hung process

**Solutions:**

1. **Increase timeout:**
   ```yaml
   tools:
     - module: tool-bash
       config:
         timeout: 300  # 5 minutes
   ```

2. **Optimize tool:**
   - Cache expensive operations
   - Reduce I/O
   - Parallelize within tool

3. **Check for hangs:**
   - Test tool directly (not via LLM)
   - Add logging within tool implementation

---

### Issue: Invalid Tool Parameters

**Error:** `Invalid parameters for tool 'read_file'`

**Causes:**
1. LLM provided wrong types
2. Missing required parameters
3. Schema mismatch

**Solutions:**

1. **Check LLM call:**
   ```yaml
   hooks:
     - module: hooks-logging
       config:
         level: DEBUG  # See exact parameters
   ```

2. **Improve tool description:**
   ```python
   coordinator.register_tool(
       name="read_file",
       description="Read file contents. file_path MUST be absolute path.",  # Clear!
       parameters={...}
   )
   ```

3. **Add validation:**
   ```python
   async def read_file_impl(file_path: str) -> str:
       if not Path(file_path).is_absolute():
           raise ValueError("file_path must be absolute")
   ```

---

## Reference

### File Locations

| Tool | Path |
|------|------|
| tool-filesystem | `amplifier-dev/amplifier-module-tool-filesystem/` |
| tool-bash | `amplifier-dev/amplifier-module-tool-bash/` |
| tool-web | `amplifier-dev/amplifier-module-tool-web/` |
| tool-search | `amplifier-dev/amplifier-module-tool-search/` |
| tool-task | `amplifier-dev/amplifier-module-tool-task/` |
| tool-todo | `amplifier-dev/amplifier-module-tool-todo/` |

### Key Concepts

| Concept | Description |
|---------|-------------|
| **Tool** | LLM-callable capability |
| **Schema** | JSON Schema defining parameters |
| **Tool call** | LLM requesting tool execution |
| **Tool result** | Output returned to LLM |
| **Approval** | Human review before execution |

### Related Guides

- [**Mount Plans Guide**](./mounts.md) - How tools are loaded
- [**Orchestrators Guide**](./orchestrators.md) - How orchestrators execute tools
- [**Hooks Guide**](./hooks.md) - Observing tool execution
- [**Development Guide**](./development.md) - Creating custom tools

---

## Quick Reference

### Choosing Tools

```
Need file operations?
    └─ tool-filesystem (read, write, edit)

Need command execution?
    └─ tool-bash (with safety checks!)

Need web access?
    └─ tool-web (fetch URLs)

Need code search?
    └─ tool-search (grep, ripgrep)

Need sub-agents?
    └─ tool-task (delegation)

Need task tracking?
    └─ tool-todo (todo lists)
```

### Configuration Template

```yaml
tools:
  - module: tool-filesystem
    source: git+https://github.com/microsoft/amplifier-module-tool-filesystem@main
    config:
      allowed_read_paths: null    # null = all, or ["path1", "path2"]
      allowed_write_paths: ["."]  # Current dir + subdirs
      require_approval: false

  - module: tool-bash
    source: git+https://github.com/microsoft/amplifier-module-tool-bash@main
    config:
      allow_dangerous: false      # Block rm, dd, etc.
      timeout: 60                 # Seconds
      require_approval: true      # Always approve

  - module: tool-web
    source: git+https://github.com/microsoft/amplifier-module-tool-web@main
    config:
      allowed_domains: null       # null = all
      blocked_domains: []
      timeout: 30
```

---

**Tools are the agent's hands. Choose wisely, configure safely, and trust the validation.**
