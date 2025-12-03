# Amplified Context - @Mention Resolution Design

**Date**: 2025-12-01
**Status**: Design Specification
**Philosophy**: Ruthless Simplicity

---

## Executive Summary

Two complementary features for session context:

1. **AGENTS.md Inclusion**: Automatically include `.amplified/AGENTS.md` in session context
2. **@Mention Resolution**: Resolve `@mention` references in profiles and AGENTS.md

**Core Design**: Only 2 @mention types, no shortcuts, no collections integration, minimal surface area.

---

## The Two @Mention Types

### 1. `@<context-key>:<path>` - Profile Context References

References content from a profile's `context` dictionary.

**Structure**:
- `context-key` matches a key in profile's `context: {...}` section
- `path` is relative to the resolved context directory
- Uses existing `RefResolutionService` to resolve the context ref

**Example**:

Profile definition:
```yaml
---
context:
  coding-standards: "git+https://github.com/org/standards@main"
  design-docs: "fsspec://s3/bucket/design"
---

Follow these patterns: @coding-standards:STYLE.md
See architecture: @design-docs:ARCHITECTURE.md
```

Resolution:
1. Extract `context-key` = "coding-standards", `path` = "STYLE.md"
2. Look up "coding-standards" in profile's `context` dict → "git+https://github.com/org/standards@main"
3. Use `RefResolutionService.resolve_ref()` to get cached directory
4. Read `{cached_dir}/STYLE.md`
5. Replace @mention with file contents

### 2. `@<path>` - Relative to Amplified Directory

Resolves relative to the amplified directory (session's initial CWD).

**Structure**:
- Path is relative to `amplified_dir` (NOT `.amplified/`)
- Standard relative path syntax: `./`, `../`, or direct paths

**Examples**:

```markdown
# .amplified/AGENTS.md

Reference coding style: @docs/CODING_STYLE.md
Check conventions: @docs/CONVENTIONS.md
See sibling project: @../shared-lib/IMPLEMENTATION.md
```

Resolution:
1. Strip `@` prefix → "docs/CODING_STYLE.md"
2. Resolve relative to `amplified_dir` → `{amplified_dir}/docs/CODING_STYLE.md`
3. Validate path stays within `amplified_dir` boundaries (security)
4. Read file contents
5. Replace @mention with contents

---

## Why Only Two Types?

**Ruthless Simplicity**:
- No collection resolution needed (profiles already handle that in `context`)
- No shortcuts (`@user:`, `@project:`, `@~/`)
- Clear use case for each type
- Minimal surface area

**Natural Fit with amplifierd**:
- Profiles already have `context` dictionary
- Sessions already track `amplified_dir`
- Reuses existing `RefResolutionService`

**Less Code, Less Bugs**:
- No `CollectionResolver` integration
- No home directory references
- Simpler testing
- Easier to maintain

---

## Resolution Algorithm

### Core Architecture

**Based on amplifier-app-cli's proven implementation** with key features:
- **Recursive resolution**: Follows @mentions in loaded files
- **Cycle detection**: Prevents infinite loops via visited paths set
- **Content deduplication**: Same content = one message crediting all paths
- **Queue-based processing**: Processes nested mentions systematically

### Resolution Method

```python
def _resolve_mention(self, mention: str, relative_to: Path) -> Path | None:
    """Resolve @mention to file path.

    Two types:
    1. @context-key:path - Profile context reference (pre-compiled)
    2. @path - Relative to amplified_dir

    Args:
        mention: The @mention string (e.g., "@coding-standards:STYLE.md")
        relative_to: Base path for relative resolution

    Returns:
        Resolved Path if found, None otherwise
    """

    # Type 1: @context-key:path (has colon separator)
    if ":" in mention[1:]:
        context_key, path = mention[1:].split(":", 1)

        # CRITICAL: Contexts are PRE-COMPILED during profile compilation
        # They're already copied to: {compiled_profile_dir}/contexts/{context_key}/
        context_dir = self.compiled_profile_dir / "contexts" / context_key

        if not context_dir.exists():
            logger.warning(f"Context '{context_key}' not found at {context_dir}")
            return None

        # Resolve path within pre-compiled context
        file_path = context_dir / path
        return file_path if file_path.exists() else None

    # Type 2: @path (relative to amplified_dir)
    path = mention.lstrip("@")
    resolved = (self.amplified_dir / path).resolve()

    # Security: Ensure path stays within amplified_dir
    try:
        resolved.relative_to(self.amplified_dir.resolve())
    except ValueError:
        logger.warning(f"Path traversal blocked: {mention}")
        return None

    return resolved if resolved.exists() else None
```

### Recursive Loading with Deduplication

```python
def load_mentions(
    self,
    text: str,
    relative_to: Path | None = None
) -> list[Message]:
    """Load @mentions recursively with cycle detection and deduplication.

    Returns list of Message objects (role="developer") for context injection.
    """
    deduplicator = ContentDeduplicator()
    visited_paths: set[Path] = set()
    path_to_mention: dict[Path, str] = {}  # Track original @mention
    to_process: list[str] = parse_mentions(text)

    while to_process:  # RECURSIVE processing
        mention = to_process.pop(0)
        path = self._resolve_mention(mention, relative_to)

        if path is None or path.resolve() in visited_paths:
            continue  # Skip missing or already visited

        visited_paths.add(path.resolve())
        path_to_mention[path.resolve()] = mention

        # Load content
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        # Deduplicate by content hash
        deduplicator.add_file(path.resolve(), content)

        # Parse nested mentions and add to queue
        nested_mentions = parse_mentions(content)
        for nested in nested_mentions:
            if nested not in to_process:
                to_process.append(nested)  # Process in next iteration

    # Create Message objects from deduplicated content
    return self._create_messages(
        deduplicator.get_unique_files(),
        path_to_mention
    )

def _create_messages(
    self,
    context_files: list[ContextFile],
    path_to_mention: dict[Path, str]
) -> list[Message]:
    """Create Message objects from loaded context files.

    Each file becomes a separate Message object with role="developer".
    """
    messages = []
    for ctx_file in context_files:
        # Format: "@mention → /absolute/path" for each source
        path_displays = []
        for p in ctx_file.paths:
            original_mention = path_to_mention.get(p)
            if original_mention:
                path_displays.append(f"{original_mention} → {p}")
            else:
                path_displays.append(str(p))

        paths_str = ", ".join(path_displays)
        content = f"[Context from {paths_str}]\n\n{ctx_file.content}"
        messages.append(Message(role="developer", content=content))

    return messages
```

### Data Structures

```python
@dataclass
class ContextFile:
    """Represents a unique file loaded from @mentions."""
    content: str              # File content
    paths: list[Path]         # All paths with this content
    hash: str                 # SHA-256 hash for deduplication

class ContentDeduplicator:
    """Deduplicates file content by hash, tracking all source paths."""

    def add_file(self, path: Path, content: str) -> None:
        """Add file to deduplicator. Same content = same hash."""
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        if content_hash not in self._content_by_hash:
            self._content_by_hash[content_hash] = content
            self._paths_by_hash[content_hash] = []

        if path not in self._paths_by_hash[content_hash]:
            self._paths_by_hash[content_hash].append(path)

    def get_unique_files(self) -> list[ContextFile]:
        """Return deduplicated files with all source paths."""
        return [
            ContextFile(
                content=content,
                paths=self._paths_by_hash[content_hash],
                hash=content_hash
            )
            for content_hash, content in self._content_by_hash.items()
        ]
```

**Key Design Points**:
- **Recursive processing**: Queue-based while loop handles nested mentions
- **Cycle detection**: `visited_paths` set prevents infinite loops
- **Content deduplication**: Hash-based, tracks all source paths
- **Message per file**: Each unique content becomes separate Message object
- **Graceful degradation**: Missing files silently skipped (no exception)
- **Context location**: Pre-compiled at `{compiled_profile_dir}/contexts/{context-key}/`

---

## MentionLoader Service

**Location**: `amplifierd/services/mention_loader.py`

**Adapted from amplifier-app-cli's proven implementation**

**Interface**:

```python
class MentionLoader:
    """Loads files referenced by @mentions with deduplication and cycle detection.

    Features:
    - Recursive loading (follows @mentions in loaded files)
    - Cycle detection (prevents infinite loops)
    - Content deduplication (same content = one copy, all paths credited)
    - Silent skip on missing files
    """

    def __init__(
        self,
        compiled_profile_dir: Path,
        amplified_dir: Path
    ):
        """Initialize loader.

        Args:
            compiled_profile_dir: Path to compiled profile (contains contexts/)
            amplified_dir: Amplified directory path (session's initial CWD)
        """
        self.compiled_profile_dir = compiled_profile_dir
        self.amplified_dir = amplified_dir

    def load_mentions(
        self,
        text: str,
        relative_to: Path | None = None
    ) -> list[Message]:
        """Load all @mentioned files recursively with cycle detection.

        Args:
            text: Text containing @mentions
            relative_to: Base path for relative mentions (optional)

        Returns:
            List of Message objects with role="developer" containing loaded context

        Side Effects:
            - Logs warnings for unresolvable mentions
            - Silently skips missing files (no exception)
        """
        # Implementation shown in Resolution Algorithm section above

    def _resolve_mention(
        self,
        mention: str,
        relative_to: Path
    ) -> Path | None:
        """Resolve @mention to file path.

        Two types:
        1. @context-key:path - Profile context reference (pre-compiled)
        2. @path - Relative to amplified_dir

        Args:
            mention: The @mention string (e.g., "@coding-standards:STYLE.md")
            relative_to: Base path for relative resolution

        Returns:
            Resolved Path if found, None otherwise
        """
        # Implementation shown in Resolution Algorithm section above

    def _create_messages(
        self,
        context_files: list[ContextFile],
        path_to_mention: dict[Path, str]
    ) -> list[Message]:
        """Create Message objects from loaded context files.

        Each file becomes a separate Message object with role="developer".

        Args:
            context_files: List of deduplicated context files
            path_to_mention: Mapping of resolved paths to original @mention strings

        Returns:
            List of Message objects
        """
        # Implementation shown in Resolution Algorithm section above
```

**Supporting Classes**:

```python
@dataclass
class ContextFile:
    """Represents a unique file loaded from @mentions."""
    content: str              # File content
    paths: list[Path]         # All paths with this content
    hash: str                 # SHA-256 hash for deduplication

class ContentDeduplicator:
    """Deduplicates file content by hash, tracking all source paths."""

    def add_file(self, path: Path, content: str) -> None:
        """Add file to deduplicator."""

    def get_unique_files(self) -> list[ContextFile]:
        """Return deduplicated files with all source paths."""

    def get_known_hashes(self) -> set[str]:
        """Return hashes currently tracked (for session-wide deduplication)."""
```

**Dependencies**:
- `pathlib.Path` (stdlib)
- `hashlib` (stdlib)
- `logging` (stdlib)
- `amplifier_core.message_models.Message` (existing)

**No dependencies on**:
- ❌ `RefResolutionService` (contexts pre-compiled, not needed at runtime)
- ❌ `CollectionResolver` (not needed)
- ❌ Home directory expansion (not needed)
- ❌ Complex path search (not needed)

**Key Differences from Old Design**:
- Returns `list[Message]` instead of string replacement
- Recursive resolution with cycle detection
- Content deduplication via hash
- Uses pre-compiled context directories (not git cache)

---

## Integration Points

### MountPlanService Changes

**New Method**:

```python
def _load_context_messages(
    self,
    profile_id: str,
    amplified_dir: Path
) -> list[Message]:
    """Load and resolve context files as Message objects.

    Args:
        profile_id: Profile ID (collection/profile)
        amplified_dir: Absolute path to amplified directory

    Returns:
        List of Message objects with role="developer" containing context
    """
    messages: list[Message] = []

    # Get compiled profile directory
    collection_id, profile_name = profile_id.split("/")
    compiled_profile_dir = (
        self.share_dir / "profiles" / collection_id / profile_name
    )

    # Create mention loader
    mention_loader = MentionLoader(
        compiled_profile_dir=compiled_profile_dir,
        amplified_dir=amplified_dir
    )

    # Load profile instruction (markdown body)
    profile = self.profile_service.get_profile(profile_id)
    if profile.instruction:
        instruction_messages = mention_loader.load_mentions(
            profile.instruction,
            relative_to=amplified_dir
        )
        messages.extend(instruction_messages)

    # Load .amplified/AGENTS.md if exists
    agents_md = amplified_dir / ".amplified" / "AGENTS.md"
    if agents_md.exists():
        content = agents_md.read_text()
        agents_messages = mention_loader.load_mentions(
            content,
            relative_to=amplified_dir
        )
        messages.extend(agents_messages)

    return messages
```

**Updated generate_mount_plan**:

```python
def generate_mount_plan(
    self,
    profile_id: str,
    amplified_dir: Path  # NEW: required for AGENTS.md and @path resolution
) -> dict[str, Any]:
    """Generate mount plan with resolved context messages."""

    # ... existing code to build mount plan ...

    # NEW: Load context messages with @mention resolution
    context_messages = self._load_context_messages(profile_id, amplified_dir)

    # NEW: Add to mount plan if any messages were loaded
    if context_messages:
        # Convert Message objects to dicts for JSON serialization
        mount_plan["context_messages"] = [
            {
                "role": msg.role,
                "content": msg.content
            }
            for msg in context_messages
        ]

    return mount_plan
```

### Session Router Changes

**Pass amplified_dir to generate_mount_plan**:

```python
# In POST /sessions endpoint
amplified_dir_path = (data_dir / amplified_dir).resolve()

mount_plan = mount_plan_service.generate_mount_plan(
    profile_id=profile_name,
    amplified_dir=amplified_dir_path  # NEW
)
```

### Mount Plan Schema

**New Optional Field**:

```python
mount_plan = {
    "session": {...},
    "providers": [...],
    "tools": [...],
    "hooks": [...],
    "agents": {...},
    "context_messages": [  # NEW - optional
        {
            "role": "developer",
            "content": "[Context from @coding-standards:STYLE.md → /path/to/file]\n\n{file content}"
        },
        {
            "role": "developer",
            "content": "[Context from @docs/CONVENTIONS.md → /path/to/file]\n\n{file content}"
        }
    ]
}
```

**Message Format**:
- Each loaded file becomes a separate message
- `role="developer"` for all context messages
- Content format: `[Context from @mention → /path]\n\n{content}`
- Deduplicated: Same content = one message with multiple paths credited

**Backward Compatibility**: Old mount plans without `context_messages` continue to work.

---

## Security Model

### Path Traversal Prevention

**For @context-key:path**:
- Context directory is pre-compiled and secured during profile compilation
- Path within context is trusted (already copied to `contexts/{context_key}/`)
- No runtime resolution needed (no RefResolutionService calls)

**For @path**:
- MUST validate resolved path stays within `amplified_dir`
- Block attempts like `@../../../etc/passwd`
- Log warning and return original @mention on violation

```python
# Security check for @path type
resolved = (amplified_dir / path).resolve()

try:
    # Ensure resolved path is within amplified_dir
    resolved.relative_to(amplified_dir.resolve())
except ValueError:
    logger.warning(f"Path traversal blocked: {mention}")
    return mention  # Return original, don't expose path
```

### Resource Limits

**File Size Limit**:
```python
MAX_MENTION_FILE_SIZE = 1_000_000  # 1MB

content = file_path.read_text()
if len(content) > MAX_MENTION_FILE_SIZE:
    logger.warning(f"File too large: {file_path} ({len(content)} bytes)")
    return mention  # Skip large files
```

**Mention Count Limit**:
```python
MAX_MENTIONS_PER_FILE = 50

mentions = extract_mentions(text)
if len(mentions) > MAX_MENTIONS_PER_FILE:
    logger.warning(f"Too many @mentions: {len(mentions)}")
    mentions = mentions[:MAX_MENTIONS_PER_FILE]
```

---

## Error Handling

**Principle**: Never fail session creation due to @mention errors.

**Strategies**:

1. **Missing context key**: Log warning, return original @mention
2. **Failed ref resolution**: Log warning, return original @mention
3. **Missing file**: Log warning, return original @mention
4. **Path traversal**: Log warning, return original @mention
5. **File too large**: Log warning, return original @mention

**Example**:
```python
try:
    context_files = self._load_context_files(profile_id, amplified_dir)
except Exception as e:
    logger.warning(f"Failed to load context files: {e}")
    context_files = {}  # Empty, session creation continues

# Session is created successfully even if @mentions failed
```

**Result**: Session always created, users see original @mention text where resolution failed.

---

## Usage Examples

### Example 1: Profile with Context References

**Profile Definition** (`registry/profiles/foundation/base.md`):

```yaml
---
context:
  coding-standards: "git+https://github.com/org/standards@main"
  api-docs: "fsspec://s3/docs-bucket/api"
---

# Foundation Profile

Follow these coding patterns: @coding-standards:PATTERNS.md

See API guidelines: @api-docs:REST_GUIDELINES.md

Reference error handling: @coding-standards:ERRORS.md
```

**Resolution**:
1. `@coding-standards:PATTERNS.md` → Clone git repo → Read `PATTERNS.md`
2. `@api-docs:REST_GUIDELINES.md` → Fetch from S3 → Read `REST_GUIDELINES.md`
3. `@coding-standards:ERRORS.md` → Use cached git repo → Read `ERRORS.md`

### Example 2: AGENTS.md with Project References

**AGENTS.md** (`.amplified/AGENTS.md`):

```markdown
# Project Agent Instructions

## Coding Style

Follow our coding style: @docs/CODING_STYLE.md

## Team Conventions

Reference conventions: @docs/CONVENTIONS.md

## Shared Implementation

Check shared implementation: @../shared-lib/IMPLEMENTATION.md
```

**Resolution** (assuming `amplified_dir` = `/data/repos/myproject`):
1. `@docs/CODING_STYLE.md` → `/data/repos/myproject/docs/CODING_STYLE.md`
2. `@docs/CONVENTIONS.md` → `/data/repos/myproject/docs/CONVENTIONS.md`
3. `@../shared-lib/IMPLEMENTATION.md` → `/data/repos/shared-lib/IMPLEMENTATION.md`

### Example 3: Mixed Usage

**Profile**:
```yaml
---
context:
  standards: "git+https://github.com/company/standards@v2"
---

Follow standard patterns: @standards:STYLE.md
But override with project specifics: [resolved at session time from AGENTS.md]
```

**AGENTS.md**:
```markdown
Project-specific overrides: @docs/PROJECT_OVERRIDES.md
```

**Result**: Profile context provides standards, AGENTS.md provides project customization.

---

## Testing Strategy

### Unit Tests for MentionLoader

**Test Type 1: Profile Context References**:
```python
def test_load_context_reference():
    """Test @context-key:path resolution from pre-compiled context."""
    # Setup pre-compiled context
    context_dir = compiled_profile_dir / "contexts" / "docs"
    context_dir.mkdir(parents=True)
    (context_dir / "README.md").write_text("# Documentation")

    loader = MentionLoader(compiled_profile_dir, amplified_dir)

    text = "See: @docs:README.md"
    messages = loader.load_mentions(text)

    assert len(messages) == 1
    assert messages[0].role == "developer"
    assert "# Documentation" in messages[0].content
    assert "@docs:README.md" in messages[0].content  # Path tracking

def test_missing_context_key():
    """Test graceful handling of missing context key."""
    loader = MentionLoader(compiled_profile_dir, amplified_dir)

    text = "See: @missing:file.md"
    messages = loader.load_mentions(text)

    assert len(messages) == 0  # Silently skipped
```

**Test Type 2: Relative Path References**:
```python
def test_load_relative_path():
    """Test @path resolution relative to amplified_dir."""
    # Create test file
    (amplified_dir / "docs" / "STYLE.md").write_text("# Style Guide")

    loader = MentionLoader(compiled_profile_dir, amplified_dir)

    text = "Follow: @docs/STYLE.md"
    messages = loader.load_mentions(text)

    assert len(messages) == 1
    assert "# Style Guide" in messages[0].content

def test_path_traversal_blocked():
    """Test security: block path traversal."""
    loader = MentionLoader(compiled_profile_dir, amplified_dir)

    text = "See: @../../../etc/passwd"
    messages = loader.load_mentions(text)

    assert len(messages) == 0  # Blocked, no messages
```

**Test Type 3: Recursive Resolution**:
```python
def test_recursive_mention_loading():
    """Test recursive @mention resolution."""
    # Create file chain: A -> B -> C
    (amplified_dir / "a.md").write_text("File A\n@b.md")
    (amplified_dir / "b.md").write_text("File B\n@c.md")
    (amplified_dir / "c.md").write_text("File C")

    loader = MentionLoader(compiled_profile_dir, amplified_dir)

    messages = loader.load_mentions("Start: @a.md")

    # Should load all three files
    assert len(messages) == 3
    contents = [msg.content for msg in messages]
    assert any("File A" in c for c in contents)
    assert any("File B" in c for c in contents)
    assert any("File C" in c for c in contents)

def test_cycle_detection():
    """Test cycle detection prevents infinite loops."""
    # Create cycle: A -> B -> A
    (amplified_dir / "a.md").write_text("File A\n@b.md")
    (amplified_dir / "b.md").write_text("File B\n@a.md")

    loader = MentionLoader(compiled_profile_dir, amplified_dir)

    messages = loader.load_mentions("Start: @a.md")

    # Should load each file only once
    assert len(messages) == 2
```

**Test Type 4: Content Deduplication**:
```python
def test_content_deduplication():
    """Test same content from multiple paths = one message."""
    # Create two files with identical content
    (amplified_dir / "docs/v1.md").write_text("# Same Content")
    (amplified_dir / "docs/v2.md").write_text("# Same Content")

    loader = MentionLoader(compiled_profile_dir, amplified_dir)

    text = "See: @docs/v1.md and @docs/v2.md"
    messages = loader.load_mentions(text)

    # Should be deduplicated to one message
    assert len(messages) == 1
    # But both paths should be credited
    assert "v1.md" in messages[0].content
    assert "v2.md" in messages[0].content

def test_missing_file_graceful():
    """Test graceful skip on missing file."""
    loader = MentionLoader(compiled_profile_dir, amplified_dir)

    text = "See: @missing/file.md"
    messages = loader.load_mentions(text)

    assert len(messages) == 0  # Silently skipped, no exception
```

### Integration Tests

**Test Profile Instruction Resolution**:
```python
def test_profile_instruction_with_mentions():
    """Test profile instruction @mention resolution returns Messages."""
    # Setup pre-compiled context
    context_dir = compiled_profile_dir / "contexts" / "docs"
    context_dir.mkdir(parents=True)
    (context_dir / "STYLE.md").write_text("# Style Guide")

    # Setup profile with context reference
    profile = create_test_profile(
        context={"docs": "git+https://example.com/docs@main"},
        instruction="Follow: @docs:STYLE.md"
    )

    # Generate mount plan
    mount_plan = mount_plan_service.generate_mount_plan(
        profile_id="test/profile",
        amplified_dir=test_amplified_dir
    )

    # Verify resolution
    assert "context_messages" in mount_plan
    assert len(mount_plan["context_messages"]) == 1
    msg = mount_plan["context_messages"][0]
    assert msg["role"] == "developer"
    assert "# Style Guide" in msg["content"]
    assert "@docs:STYLE.md" in msg["content"]  # Path tracking
```

**Test AGENTS.md Resolution**:
```python
def test_agents_md_with_mentions():
    """Test AGENTS.md @mention resolution returns Messages."""
    # Create AGENTS.md with @mentions
    agents_md = test_amplified_dir / ".amplified" / "AGENTS.md"
    agents_md.write_text("Follow: @docs/STYLE.md")

    # Create referenced file
    (test_amplified_dir / "docs" / "STYLE.md").write_text("# Style")

    # Generate mount plan
    mount_plan = mount_plan_service.generate_mount_plan(
        profile_id="test/profile",
        amplified_dir=test_amplified_dir
    )

    # Verify resolution
    assert "context_messages" in mount_plan
    messages = mount_plan["context_messages"]
    assert any("# Style" in msg["content"] for msg in messages)
```

**Test Recursive Resolution in Integration**:
```python
def test_recursive_mentions_in_profile():
    """Test recursive @mention resolution through profile."""
    # Create file chain
    (test_amplified_dir / "a.md").write_text("File A\n@b.md")
    (test_amplified_dir / "b.md").write_text("File B")

    # Profile references first file
    profile = create_test_profile(instruction="Start: @a.md")

    mount_plan = mount_plan_service.generate_mount_plan(
        profile_id="test/profile",
        amplified_dir=test_amplified_dir
    )

    # Should load both files
    messages = mount_plan["context_messages"]
    assert len(messages) == 2
    contents = [msg["content"] for msg in messages]
    assert any("File A" in c for c in contents)
    assert any("File B" in c for c in contents)
```

**Test Backward Compatibility**:
```python
def test_no_agents_md():
    """Test graceful handling when AGENTS.md doesn't exist."""
    mount_plan = mount_plan_service.generate_mount_plan(
        profile_id="test/profile",
        amplified_dir=test_amplified_dir
    )

    # Should succeed, just no context_messages
    assert "context_messages" not in mount_plan or \
           len(mount_plan.get("context_messages", [])) == 0
```

---

## Performance Characteristics

**Resolution Timing**:
- One-time cost at mount plan generation
- No per-message overhead
- Amortized across session lifetime

**Caching**:
- Contexts pre-compiled during profile compilation (one-time cost)
- No runtime git clones or fsspec downloads
- File reads from local filesystem only
- Resolved messages stored in mount plan (persistent)

**Typical Performance**:
- Context file reads: <10ms per file (local filesystem)
- Recursive resolution: Linear in number of files loaded
- Deduplication: Hash computation is fast (SHA-256)
- Total overhead per session: ~100-200ms for typical cases

**Optimization**: Not needed currently. If needed later:
- Cache resolved mentions at profile compilation time
- Pre-resolve common patterns
- Parallel resolution of multiple context refs

---

## Design Decisions

**Recursive Resolution** (CHANGED from original design):
- Queue-based processing follows @mentions in loaded files
- Cycle detection prevents infinite loops
- Based on amplifier-app-cli's proven implementation
- More complete than single-pass approach

**No Directory Resolution**:
- Only resolves to files, not directories
- @mention must point to a file
- Clearer semantics, simpler implementation

**No Collection Integration**:
- Collections are handled by profiles' `context` dictionary
- No direct @collection:path syntax
- Profile authors define context mappings

**No Home Directory Shortcuts**:
- No `@~/path` syntax
- No `@user:path` shortcuts
- Keep resolution local to amplified directory and profile context

---

## Migration from Old Design

**What Changed from Original Design**:
- **CRITICAL FIX**: Contexts resolved from pre-compiled `contexts/` directory (not git cache via RefResolutionService)
- **UPGRADED**: Single-pass → recursive resolution with cycle detection
- **UPGRADED**: String replacement → Message objects per file
- **ADDED**: Content deduplication via hash
- **REMOVED**: 5 @mention types → 2 types (ruthless simplicity)
- **REMOVED**: `CollectionResolver` integration (not needed)
- **REMOVED**: `@user:`, `@project:`, `@~/` shortcuts (not needed)

**What Stayed**:
- AGENTS.md automatic inclusion
- Profile instruction resolution
- Two @mention types: `@context-key:path` and `@path`
- Security model (path traversal prevention)
- Error handling approach (graceful degradation)

**Migration Path**:
- No breaking changes (new feature)
- Old profiles work unchanged
- New profiles can use @mentions
- AGENTS.md usage is opt-in

---

## Success Criteria

**Functional**:
- ✅ AGENTS.md automatically included when present
- ✅ Profile context references resolve correctly (@context-key:path)
- ✅ Relative paths resolve correctly (@path)
- ✅ Missing files don't break session creation
- ✅ Security validation prevents path traversal
- ✅ Resolved content embedded in mount plan

**Non-Functional**:
- ✅ Ruthlessly simple (2 types, minimal code)
- ✅ Reuses existing RefResolutionService
- ✅ Natural fit with amplifierd architecture
- ✅ Clear error messages
- ✅ Backward compatible
- ✅ Well-tested

---

## Implementation Checklist

### Core Implementation

- [ ] Create `amplifierd/services/mention_loader.py`
  - [ ] Implement `MentionLoader` class
  - [ ] Add `_resolve_mention()` method
    - [ ] @context-key:path resolution (pre-compiled contexts/)
    - [ ] @path resolution (relative to amplified_dir)
    - [ ] Security validation for path traversal
  - [ ] Add `load_mentions()` method
    - [ ] Queue-based recursive processing
    - [ ] Cycle detection with visited_paths set
    - [ ] Nested mention discovery
  - [ ] Add `_create_messages()` method
    - [ ] Create Message objects per unique file
    - [ ] Path tracking with original @mention
  - [ ] Add error handling and logging

- [ ] Create `amplifierd/services/mention_loader_models.py`
  - [ ] `ContextFile` dataclass
  - [ ] `ContentDeduplicator` class
    - [ ] Hash-based deduplication
    - [ ] Multi-path tracking

- [ ] Update `amplifierd/services/mount_plan_service.py`
  - [ ] Add `amplified_dir` parameter to `generate_mount_plan()`
  - [ ] Add `_load_context_messages()` method
  - [ ] Create `MentionLoader` instance
  - [ ] Load and resolve profile instruction
  - [ ] Load and resolve AGENTS.md
  - [ ] Add `context_messages` to mount plan

- [ ] Update `amplifierd/routers/sessions.py`
  - [ ] Pass `amplified_dir` to `generate_mount_plan()`

### Testing

- [ ] Unit tests for `MentionLoader`
  - [ ] Test @context-key:path resolution (pre-compiled)
  - [ ] Test @path resolution
  - [ ] Test missing context key
  - [ ] Test missing file
  - [ ] Test path traversal prevention
  - [ ] Test recursive resolution (file chains)
  - [ ] Test cycle detection
  - [ ] Test content deduplication

- [ ] Unit tests for `ContentDeduplicator`
  - [ ] Test hash-based deduplication
  - [ ] Test multi-path tracking
  - [ ] Test get_unique_files()

- [ ] Integration tests
  - [ ] Test profile instruction with @mentions
  - [ ] Test AGENTS.md with @mentions
  - [ ] Test recursive mentions in profile
  - [ ] Test mixed context + relative paths
  - [ ] Test backward compatibility

### Documentation

- [ ] Add @mention syntax guide
- [ ] Add usage examples
- [ ] Document security model
- [ ] Update API documentation

---

## Conclusion

This design provides @mention resolution with proven patterns from amplifier-app-cli:

**Just Two Types**:
1. `@context-key:path` - Profile context references (pre-compiled)
2. `@path` - Relative to amplified directory

**Key Strengths**:
- ✅ Minimal surface area (2 types, not 5)
- ✅ Recursive resolution with cycle detection
- ✅ Content deduplication via hash
- ✅ Message objects (not string replacement)
- ✅ Uses pre-compiled contexts (fast, no runtime git ops)
- ✅ Natural fit with amplifierd architecture
- ✅ Clear security model
- ✅ Graceful error handling
- ✅ Proven implementation patterns from app-cli

**Critical Corrections from Original Design**:
1. **Context resolution**: Pre-compiled `contexts/` directory (not RefResolutionService)
2. **Recursive processing**: Queue-based with cycle detection (not single-pass)
3. **Message creation**: Separate Message objects per file (not string replacement)
4. **Deduplication**: Hash-based content deduplication (not duplicate messages)

**Philosophy Alignment**:
- Ruthless simplicity over feature completeness
- Reuse proven patterns (from app-cli)
- Security by design
- Fail gracefully, never break session creation

The implementation follows the project's core philosophy while providing valuable functionality for managing session context and profile composition, based on amplifier-app-cli's proven @mention loading system.
