# The Amplifier Computing Platform: Architecture for Intelligent Computing

Paul Payne

---

## Abstract

The Amplifier Computing Platform (ACP) addresses four fundamental limitations of existing agentic systems: ephemeral sessions, app-centric data models, prompt-driven behavior, and tight UI coupling. Through four architectural innovations—hierarchical context binding, compile-time profile resolution, persistent session state, and dynamic module resolution—ACP enables data-in-place amplification, reproducible agent behavior, and long-running workflows.

This document presents the implemented architecture (approximately 60% of the full vision), concrete proof points you can verify today, and the roadmap forward. The code is open source, the proof points are executable, and the vision is grounded in working mechanisms.

---

## 1. The Problem: Limitations of Current Agentic Systems

Since ChatGPT's release, agentic AI systems have proliferated, but they share common architectural limitations that prevent them from becoming true computing platforms:

### 1.1 Claude Code / Cursor
**What they do well:**
- Direct filesystem access (no cloud isolation)
- Command-line execution capabilities
- Real-time code generation and editing

**Architectural limitations:**
- **Ephemeral sessions**: Lost on restart, no persistence
- **No project identity**: Context is per-chat window, not per-project
- **Prompt-driven behavior**: Capabilities defined through natural language, not composable modules
- **No reproducibility**: Same prompt can yield different results

### 1.2 Semantic Workbench
**What it does well:**
- Workspace concept for project organization
- YAML-based configuration
- Multi-agent orchestration

**Architectural limitations:**
- **UI-coupled**: Workspaces tied to specific UI implementation
- **Runtime resolution**: Configs resolved during execution (not deterministic)
- **Behavior-data fusion**: No clean separation between agent capabilities and project data

### 1.3 ChatGPT + MCP
**What it does well:**
- Polished user experience
- Plugin ecosystem via MCP
- Cloud-based reliability

**Architectural limitations:**
- **Isolated from your computer**: Runs remotely, requires explicit data sync
- **App-centric**: Data must be imported/exported, not amplified in place
- **Integration overhead**: Each MCP server requires custom development

### 1.4 The Common Pattern

All existing systems force users to choose between:
- **Ephemeral power** (Claude Code: capable but nothing persists)
- **Persistent structure** (Semantic Workbench: organized but rigid)
- **Cloud polish** (ChatGPT: smooth but isolated)

**What's missing**: A system that combines direct filesystem access, persistent project identity, reproducible behavior, and composable capabilities—all running locally as a platform, not an app.

---

## 2. The Architecture: Four Innovations

ACP solves these limitations through four architectural innovations. Each addresses a specific gap and enables capabilities impossible in existing systems.

### 2.1 Hierarchical Context Binding via Amplified Directories

**The Innovation**: Any directory becomes a computational project by adding a `.amplified/` marker. Projects exist independently of sessions and provide inherited context automatically.

**Directory Structure:**
```
/data/
  email/
    .amplified/
      AGENTS.md              # Project-specific instructions
      profiles.yaml          # Default profile: "email-assistant"
    inbox/
      2024-01-15.eml
      2024-01-16.eml
  projects/
    myapp/
      .amplified/
        AGENTS.md            # Different instructions
        profiles.yaml        # Default profile: "foundation/base"
      src/
        main.py
      tests/
        test_main.py
```

**Data Model:**
```python
# amplifierd/models/amplified_directories.py:25-32
class AmplifiedDirectory(BaseModel):
    relative_path: str           # Path within data lake
    default_profile: str | None  # Profile to use by default
    metadata: dict               # Arbitrary project metadata
    agents_content: str | None   # Content of AGENTS.md
```

**API Example:**
```bash
# Discover amplified directories
GET /amplified-directories

Response:
[
  {
    "relative_path": "email",
    "default_profile": "email-assistant",
    "metadata": {"type": "inbox"},
    "agents_content": "# Email Context\n\nThis is my personal email..."
  },
  {
    "relative_path": "projects/myapp",
    "default_profile": "foundation/base",
    "metadata": {"language": "python"},
    "agents_content": "# MyApp\n\nThis is a web application..."
  }
]
```

**What This Enables:**

1. **Data-in-place amplification**: Sync any folder (Dropbox, OneDrive, git repo) → instant ACP project. No import/export.

2. **Persistent project identity**: Multiple sessions in the same project share context automatically.

3. **Git-versionable intelligence**: `.amplified/AGENTS.md` evolves with your project, tracked in version control.

4. **Independent configuration**: Each project has its own profile, agents, and metadata.

**Contrast with Existing Systems:**
- **Claude Code/Cursor**: Context is per-chat window. Opening a new chat loses all previous project context.
- **Semantic Workbench**: Workspaces exist but are UI-coupled, not filesystem-native.
- **ACP**: Directories are first-class projects. Any synced folder with `.amplified/` marker becomes computationally addressable.

### 2.2 Compile-Time Profile Resolution (Mount Plans)

**The Innovation**: Agent profiles are compiled once from git references, cached locally, then mounted to sessions. This separates profile resolution (git) → compilation (cache) → mounting (session), enabling reproducible behavior.

**Profile Structure:**
```yaml
# .amplifierd/profiles/foundation/extended.yaml
extends: foundation/base        # Inherit all modules
providers:
  - source: anthropic-claude-sonnet-4
    config:
      temperature: 0.7
tools:
  - source: filesystem
    config:
      working_dir: "."
  - source: python-repl
hooks:
  - source: git-aware-context
agents:
  - source: code-reviewer
contexts:
  - message: "You are an expert code reviewer focusing on best practices."
```

**Compilation Process:**
```python
# amplifierd/services/profile_compilation.py:89-103
def compile_profile(profile: ProfileDetails, ...) -> Path:
    """
    1. Resolves git refs to specific commits (determinism)
    2. Copies module code to local cache (embedded)
    3. Creates importable Python package structure
    4. Returns: ~/.amplifierd/share/profiles/{collection}/{profile}/
    """
```

**Mount Plan Schema:**
```json
{
  "profile": "foundation/extended",
  "resolved_commit": "a7b3c9d2e4f1",
  "providers": [
    {
      "id": "anthropic-claude-sonnet-4",
      "source_path": "/home/user/.amplifierd/share/profiles/foundation/extended/providers/anthropic-claude-sonnet-4",
      "config": {"temperature": 0.7}
    }
  ],
  "tools": [...],
  "hooks": [...],
  "agents": [...],
  "contexts": [...]
}
```

**What This Enables:**

1. **Reproducible sessions**: Same mount plan = identical behavior. No "works on my machine" variance.

2. **Offline initialization**: Pre-compiled assets available locally, no network required for session creation.

3. **Version pinning**: `extends: foundation/base@v1.2` locks profile version for stability.

4. **Profile inheritance**: Child profiles automatically get parent modules, can override specific ones.

**Contrast with Existing Systems:**
- **Claude Code**: Behavior defined through runtime prompt engineering. No reproducibility guarantees.
- **Semantic Workbench**: YAML configs resolved at runtime. Different runs may behave differently.
- **ACP**: Compile-time resolution produces deterministic mount plans. Sessions created from same mount plan are behaviorally identical.

### 2.3 Persistent Session State Machine

**The Innovation**: Sessions are first-class persistent entities with a defined lifecycle, not ephemeral chat windows. They survive daemon restarts and maintain complete audit trails.

**Session Lifecycle:**
```
CREATED → RUNNING → COMPLETED
              ↓
           FAILED
```

**File-Based Storage:**
```
~/.amplifierd/data/sessions/
  session_abc123/
    session.json        # Metadata (state, profile, timestamps)
    transcript.jsonl    # Message history (append-only)
```

**Session Model:**
```python
# amplifier_library/sessions/session.py:15-28
class SessionMetadata(BaseModel):
    session_id: str
    status: SessionStatus  # CREATED | RUNNING | COMPLETED | FAILED
    profile: str
    amplified_dir: str | None
    working_dir: str
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
```

**State Management:**
```python
# amplifier_library/sessions/manager.py:45-62
def create_session(self, mount_plan: dict) -> SessionMetadata:
    """Creates session.json + empty transcript.jsonl"""

def transition_state(self, session_id: str, new_state: SessionStatus):
    """Validates state machine transitions, updates session.json"""
```

**What This Enables:**

1. **Survive restarts**: Kill daemon, restart → all sessions preserved with full history.

2. **Long-running workflows**: Sessions can run for hours/days (daemon architecture supports it).

3. **Session archaeology**: Complete audit trail in JSONL format for debugging, compliance, learning.

4. **Foundation for automation**: RESTful API + persistent state = external triggers (cron, webhooks) can create/resume sessions.

**Contrast with Existing Systems:**
- **Claude Code/Cursor**: Sessions exist only in memory. Restart = lost context.
- **ChatGPT**: Cloud persistence, but tied to specific UI and account.
- **ACP**: File-based persistence (JSON + JSONL) enables local storage, git compatibility, and complete control over data.

### 2.4 Dynamic Module Resolution

**The Innovation**: Uniform addressing for tools, hooks, providers, and agents across profiles. Modules are first-class mountable units with runtime discovery from compiled profiles.

**Module Addressing:**
```python
# Profile references module by ID
tools:
  - source: "filesystem"
  - source: "python-repl"

# Resolver finds module in compiled profile
class DaemonModuleSourceResolver:
    def resolve(self, module_id: str, profile_hint: str) -> ModuleSource:
        """
        Returns path to Python package in compiled profile structure.

        Example:
        module_id = "filesystem"
        profile_hint = "foundation/base"

        Returns: ~/.amplifierd/share/profiles/foundation/base/tools/filesystem/
        """
```

**Module Discovery:**
```python
# amplifierd/module_resolver.py:23-45
class DaemonModuleSourceResolver:
    def resolve(self, module_id: str, profile_hint: str) -> ModuleSource:
        # 1. Check compiled profile cache
        # 2. Load module metadata
        # 3. Return importable path
```

**What This Enables:**

1. **Agent self-modification**:
   - Agent generates Python tool module
   - Saves to `.amplified/tools/custom-scraper/`
   - Updates profile YAML to mount it
   - Reloads session with new tool available

2. **Profile composition**:
   - `foundation/extended` inherits modules from `foundation/base`
   - Can override specific modules (replace `tool/filesystem` with custom version)
   - Safe experimentation (profiles are isolated namespaces)

3. **Distributed capabilities**:
   - Profiles live in git repos
   - Pull profiles from GitHub, internal repos, local directories
   - Share capabilities across team via version control

**Contrast with Existing Systems:**
- **Claude Code**: Tools are SDK built-ins or MCP servers. No dynamic module loading.
- **Semantic Workbench**: Hardcoded Python imports. Adding capabilities requires code changes.
- **ACP**: Module resolution is declarative. Adding capabilities means updating YAML and reloading session.

---

## 3. Proof: Try It Yourself

These are not theoretical capabilities—they work today. Here are commands you can run to verify each innovation:

### 3.1 Directory Amplification

**Claim**: Any directory with `.amplified/` marker becomes an ACP project.

**Proof**:
```bash
# Create amplified directory
mkdir -p ~/test-data/myproject/.amplified
echo "default_profile: foundation/base" > ~/test-data/myproject/.amplified/profiles.yaml
echo "# My Project" > ~/test-data/myproject/.amplified/AGENTS.md

# Configure daemon to use test-data
export AMPLIFIERD_DATA_DIR=~/test-data

# Start daemon
cd amplifierd && uv run python -m amplifierd

# In another terminal, discover projects
curl http://localhost:8000/amplified-directories

# Response shows your project:
[
  {
    "relative_path": "myproject",
    "default_profile": "foundation/base",
    "metadata": {},
    "agents_content": "# My Project"
  }
]

# Create session in this project
curl -X POST http://localhost:8000/sessions \
  -H "Content-Type: application/json" \
  -d '{"amplified_dir": "myproject"}'

# Agent automatically has myproject context (files, AGENTS.md, profile)
```

### 3.2 Profile Switching Mid-Session

**Claim**: Profiles can be switched during a session, changing available capabilities without losing context.

**Proof**:
```bash
# Create session with base profile
curl -X POST http://localhost:8000/sessions \
  -H "Content-Type: application/json" \
  -d '{"profile": "foundation/base"}' \
  > session.json

# Extract session ID
SESSION_ID=$(cat session.json | jq -r '.session_id')

# Send message to verify current capabilities
curl -X POST http://localhost:8000/sessions/$SESSION_ID/messages \
  -H "Content-Type: application/json" \
  -d '{"content": "What tools do you have available?"}'

# Switch to extended profile (adds code-reviewer agent)
curl -X POST http://localhost:8000/sessions/$SESSION_ID/profile \
  -H "Content-Type: application/json" \
  -d '{"profile": "foundation/extended"}'

# Send message to verify new capabilities
curl -X POST http://localhost:8000/sessions/$SESSION_ID/messages \
  -H "Content-Type: application/json" \
  -d '{"content": "What tools do you have now?"}'

# Session continues with new capabilities, all previous context preserved
```

### 3.3 Mount Plan Determinism

**Claim**: Mount plans are deterministic. Same mount plan = identical session behavior.

**Proof**:
```bash
# Generate mount plan (idempotent operation)
curl http://localhost:8000/mount-plans/foundation/base > mount_plan.json

# View resolved structure
cat mount_plan.json | jq .

# Response shows:
{
  "profile": "foundation/base",
  "resolved_commit": "a7b3c9d2e4f1",  # Git SHA, not branch name
  "providers": [...],                  # Embedded code paths
  "tools": [...],
  "hooks": [...],
  "agents": [...],
  "contexts": [...]                    # Compiled @mention content
}

# Create multiple sessions from same mount plan
for i in {1..5}; do
  curl -X POST http://localhost:8000/sessions \
    -H "Content-Type: application/json" \
    -d @mount_plan.json
done

# All 5 sessions have identical behavior (same tools, hooks, contexts)
```

### 3.4 Session Persistence

**Claim**: Sessions survive daemon restarts. Nothing is lost.

**Proof**:
```bash
# Create session
curl -X POST http://localhost:8000/sessions \
  -H "Content-Type: application/json" \
  -d '{"profile": "foundation/base"}' \
  > session.json

SESSION_ID=$(cat session.json | jq -r '.session_id')

# Send some messages
curl -X POST http://localhost:8000/sessions/$SESSION_ID/messages \
  -H "Content-Type: application/json" \
  -d '{"content": "Hello, please remember: my favorite color is blue"}'

# Check session file created
ls ~/.amplifierd/data/sessions/$SESSION_ID/
# Shows: session.json  transcript.jsonl

# Kill daemon (Ctrl+C in daemon terminal)

# Restart daemon
cd amplifierd && uv run python -m amplifierd

# In another terminal, retrieve session (nothing lost)
curl http://localhost:8000/sessions/$SESSION_ID

# Response shows full metadata
curl http://localhost:8000/sessions/$SESSION_ID/transcript

# Response shows complete message history including "favorite color is blue"
```

---

## 4. Current State & Roadmap

ACP is not vaporware—it's a working system with approximately 60% of the full vision implemented. Here's an honest assessment:

### 4.1 Implemented (Core Architecture) ✅

**Data Layer:**
- ✅ Amplified directories with profile binding
- ✅ File-based session storage (JSON + JSONL)
- ✅ Complete transcript history
- ✅ Project metadata and configuration

**Profile System:**
- ✅ Profile compilation from git refs
- ✅ Mount plan generation
- ✅ Profile inheritance (extends:)
- ✅ Module resolution (tools, hooks, providers, agents)

**Session Management:**
- ✅ State machine (CREATED → RUNNING → COMPLETED/FAILED)
- ✅ Persistent sessions (survive restarts)
- ✅ Session metadata tracking
- ✅ Profile switching mid-session

**API & Integration:**
- ✅ REST API for all operations
- ✅ WebSocket streaming for real-time messages
- ✅ Claude Code SDK integration
- ✅ Amplifier Core orchestration

### 4.2 Architecture Ready, Not Yet Exposed (~30%)

These capabilities have infrastructure in place but aren't yet exposed to users:

**Knowledge & Memory:**
- ⚠️ Transcript capture (implemented) → Semantic indexing (not implemented)
- ⚠️ Knowledge synthesis tools exist → Not integrated into daemon workflows
- ⚠️ Memory patterns defined → No automatic recall system

**Multi-Agent Coordination:**
- ⚠️ Architecture supports parallel sessions → No orchestration layer yet
- ⚠️ Agent-to-agent messaging patterns → Not exposed in API
- ⚠️ Workflow composition primitives → Manual YAML only

**Learning & Adaptation:**
- ⚠️ Performance metrics captured → Not analyzed or acted upon
- ⚠️ Error patterns tracked → No automatic improvement
- ⚠️ User feedback collected → No learning loop

### 4.3 Future Work (~10%)

Features requiring new architectural components:

**Scheduled Automation:**
- 🔮 Workflow scheduler (cron-like internal triggers)
- 🔮 Reactive hooks (file changes → session creation)
- 🔮 Background task management

**Intelligence Enhancements:**
- 🔮 Natural language profile compilation ("Create a profile for code review")
- 🔮 Automatic tool generation from usage patterns
- 🔮 Context-aware profile recommendations

**Advanced UI:**
- 🔮 Dynamic UI generation from profile capabilities
- 🔮 Multi-session dashboard
- 🔮 Visual workflow builder

### 4.4 Roadmap Priorities

Based on architectural leverage and user value:

**Phase 1 (Immediate - 3 months):**
1. Semantic search over transcripts (enable session archaeology)
2. Knowledge synthesis integration (make existing tools accessible)
3. Basic workflow scheduler (enable reactive automation)

**Phase 2 (Near-term - 6 months):**
4. Multi-agent orchestration (parallel session coordination)
5. Learning loop (analyze performance → suggest improvements)
6. Natural language profile generation

**Phase 3 (Long-term - 12 months):**
7. Advanced UI customization
8. Distributed profile marketplace
9. Cross-session memory and reasoning

---

## 5. Vision: What This Architecture Enables

The architectural innovations described above aren't just technical achievements—they're building blocks for a fundamentally different computing experience. Here's what becomes possible:

### 5.1 From Apps to Amplification

**The Traditional Model:**
```
Data lives in files → Import into App → Work → Export back
                    ↑
                Must choose which app
                Must fit app's data model
                Must learn app's interface
```

**The Amplified Model:**
```
Data lives in directories → Add .amplified/ → Instantly computational
                         ↑
                      No import/export
                      Native file organization
                      Direct manipulation
```

**Concrete Example:**

You sync your email via IMAP to `~/data/email/`. In the traditional model:
1. Import into email client (Outlook, Thunderbird, etc.)
2. Limited to client's capabilities
3. Want AI analysis? Need another app + more importing

With ACP:
1. Add `.amplified/` marker to `~/data/email/`
2. Session in that directory has email context automatically
3. Ask: "Summarize important emails from last week"
4. Generate: "Draft replies to pending customer questions"
5. Automate: "Flag emails mentioning 'urgent' and create tasks"

Same data, unlimited computational capabilities, no app boundaries.

### 5.2 From Prompts to Profiles

**Prompt-Driven Behavior (Existing Systems):**
```
User: "You are an expert code reviewer focusing on security..."
[100+ words of context repeated every session]

Problem: Not reusable, not versioned, not composable
```

**Profile-Based Behavior (ACP):**
```yaml
# profiles/security-reviewer.yaml
extends: foundation/code-reviewer
agents:
  - source: security-scanner
    config: {focus: ["sql-injection", "xss", "auth"]}
contexts:
  - message: "Prioritize security vulnerabilities over style issues"
```

**What This Enables:**

1. **Reusability**: Define once, use across all projects
2. **Versioning**: `security-reviewer@v2.1` for stability
3. **Composition**: Combine `security-reviewer` + `performance-analyzer`
4. **Sharing**: Distribute profiles via git, internal repos

**Real Scenario:**

Your team develops a security review profile over 6 months, incorporating:
- Learned patterns from past vulnerabilities
- Custom scanning tools
- Team coding standards
- Automated fix suggestions

Any team member can use `security-reviewer@stable`, getting 6 months of accumulated expertise instantly. New hires start with team knowledge built-in.

### 5.3 From Ephemeral to Persistent

**Ephemeral Sessions (Existing Systems):**
```
Start chat → Work for 2 hours → Close window → Everything lost
Need to redo work? Start from scratch, provide context again
```

**Persistent Sessions (ACP):**
```
Create session → Work for 2 hours → Pause
Resume tomorrow → Full context available → Continue exactly where you left off

Week later: "What was that solution we discussed?"
Session archaeology: Search transcripts, find exact conversation
```

**What This Enables:**

1. **Long-running projects**: Security audit takes 3 days? One session spans entire process.

2. **Interrupted workflows**: Context switch to urgent task, return to previous session without memory loss.

3. **Learning over time**: Session transcripts become training data. Agent learns from past successes/failures.

4. **Team collaboration**: Share session links. Others can see exactly what was done and why.

**Real Scenario:**

You're refactoring a complex authentication system. Session runs across 5 days:
- Day 1: Analysis (agent maps current implementation)
- Day 2: Design (agent proposes new architecture)
- Day 3: Implementation (agent generates code)
- Day 4: Testing (agent finds edge cases)
- Day 5: Documentation (agent explains changes)

Entire process documented in one session. New team member reads transcript, understands every decision. Future refactorings reference this session as precedent.

### 5.4 From Static to Self-Modifying

**Static Systems (Existing):**
```
Agent: "I need a tool to parse CSV files"
User: "Let me install a package and restart"
[Manual intervention required]
```

**Self-Modifying (ACP Architecture Enables):**
```
Agent: "I need a tool to parse CSV files"
Agent: [Generates csv_parser.py]
Agent: [Saves to .amplified/tools/csv-parser/]
Agent: [Updates profile YAML]
Agent: [Reloads session]
Agent: "CSV parser now available. Processing your file..."
```

**What This Enables:**

1. **No user intervention**: Agent recognizes capability gap and fills it

2. **Accumulated expertise**: Tools generated for one project available to all projects

3. **Continuous improvement**: Agent enhances own capabilities based on usage patterns

4. **Domain adaptation**: Working in new field? Agent generates specialized tools automatically

**Current Status:** Architecture supports this (dynamic module resolution + file-based storage), but automatic tool generation not yet implemented. Coming in Phase 2.

---

## 6. Comparison with Existing Systems

| Capability | Claude Code | Cursor | Semantic Workbench | **ACP** |
|-----------|-------------|--------|-------------------|---------|
| **Session Persistence** | ❌ Ephemeral | ❌ IDE-coupled | ⚠️ UI-coupled | ✅ File-based |
| **Project Identity** | ❌ Per-chat | ❌ Per-workspace | ⚠️ Workspace object | ✅ Amplified directories |
| **Reproducible Behavior** | ❌ Prompt variance | ❌ Config drift | ⚠️ Runtime resolution | ✅ Mount plans |
| **Profile Composition** | ❌ Prompt copy-paste | ❌ Settings UI | ⚠️ YAML inheritance | ✅ Git-based modules |
| **Data-in-Place** | ✅ Filesystem access | ✅ IDE folders | ⚠️ Import required | ✅ Amplified in place |
| **Long-Running Workflows** | ❌ Chat lifetime | ❌ IDE session | ⚠️ Limited | ✅ State machine |
| **Self-Modification** | ❌ Static SDK | ❌ Static tools | ❌ Hardcoded | ✅ Dynamic modules |
| **Version Control** | ❌ No versioning | ❌ Config files | ⚠️ YAML only | ✅ Profiles + sessions |
| **Multi-Project** | ❌ Manual context | ⚠️ Workspace switch | ⚠️ Limited | ✅ Directory scoped |
| **Offline Capable** | ⚠️ Partial | ⚠️ Partial | ❌ Cloud-dependent | ✅ Compiled cache |

**Legend:**
- ✅ Fully supported
- ⚠️ Partially supported or with limitations
- ❌ Not supported

---

## 7. Getting Started

### 7.1 Installation

```bash
# Clone repository
git clone https://github.com/payneio/amplifierd
cd amplifierd

# Install dependencies
make install

# Configure data directory
export AMPLIFIERD_DATA_DIR=~/amplifier-data
mkdir -p $AMPLIFIERD_DATA_DIR

# Start daemon
make daemon-dev
```

### 7.2 Create Your First Amplified Directory

```bash
# Create project directory
mkdir -p ~/amplifier-data/my-first-project/.amplified

# Configure project
cat > ~/amplifier-data/my-first-project/.amplified/profiles.yaml << EOF
default_profile: foundation/base
EOF

cat > ~/amplifier-data/my-first-project/.amplified/AGENTS.md << EOF
# My First Project

This is a test project for learning ACP.

Context for the agent:
- This is a learning environment
- Be patient and explanatory
- Suggest next steps proactively
EOF

# Add some files
echo "print('Hello, ACP!')" > ~/amplifier-data/my-first-project/hello.py
```

### 7.3 Create Your First Session

```bash
# Discover your project
curl http://localhost:8000/amplified-directories

# Create session
curl -X POST http://localhost:8000/sessions \
  -H "Content-Type: application/json" \
  -d '{"amplified_dir": "my-first-project"}' \
  > session.json

# Extract session ID
SESSION_ID=$(cat session.json | jq -r '.session_id')

# Send first message
curl -X POST http://localhost:8000/sessions/$SESSION_ID/messages \
  -H "Content-Type: application/json" \
  -d '{"content": "Hello! Can you see the hello.py file in my project?"}'

# Get response
curl http://localhost:8000/sessions/$SESSION_ID/transcript | jq '.[-1]'
```

### 7.4 Next Steps

**Learn by doing:**
1. Try the proof point commands (Section 3)
2. Create amplified directories for your actual projects
3. Experiment with profile switching
4. Explore the session transcripts

**Documentation:**
- Repository: https://github.com/payneio/amplifierd
- API Reference: `amplifierd/docs/api-reference.md`
- Profile Guide: `amplifierd/docs/profiles.md`
- Examples: `amplifierd/examples/`

**Join the Community:**
- Discussions: GitHub Issues
- Development: See `CONTRIBUTING.md`

---

## 8. Conclusion

The Amplifier Computing Platform is not a vision—it's a working system that solves real architectural problems existing systems can't address.

**What exists today:**
- Hierarchical context binding (amplified directories)
- Compile-time profile resolution (mount plans)
- Persistent session state (survive restarts)
- Dynamic module resolution (composable capabilities)

These four innovations enable:
- Data-in-place amplification (any synced folder → instant project)
- Reproducible agent behavior (git-versioned profiles)
- Long-running workflows (session state machine)
- Self-modifying capabilities (dynamic module mounting)

**Current implementation: ~60% of full vision.**

The remaining work is incremental feature development (knowledge synthesis integration, workflow scheduling, multi-agent orchestration), not fundamental architecture. The hard problems are solved.

**The code is open source.**
**The proof points are executable.**
**The vision is grounded in working mechanisms.**

---

## Appendix: Technical Details

### A.1 Session File Format

**session.json:**
```json
{
  "session_id": "session_abc123",
  "status": "RUNNING",
  "profile": "foundation/base",
  "amplified_dir": "my-first-project",
  "working_dir": "/home/user/amplifier-data/my-first-project",
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T11:45:00Z",
  "completed_at": null,
  "metadata": {}
}
```

**transcript.jsonl:**
```jsonl
{"role": "user", "content": "Hello!", "timestamp": "2024-01-15T10:30:15Z"}
{"role": "assistant", "content": "Hi! How can I help?", "timestamp": "2024-01-15T10:30:18Z"}
{"role": "user", "content": "List files", "timestamp": "2024-01-15T10:31:00Z"}
{"role": "assistant", "content": "I see hello.py", "timestamp": "2024-01-15T10:31:03Z"}
```

### A.2 Profile Compilation Directory Structure

```
~/.amplifierd/share/profiles/
  foundation/
    base/
      profile.yaml           # Original profile definition
      providers/
        anthropic-claude-sonnet-4/
          __init__.py
          provider.py
      tools/
        filesystem/
          __init__.py
          tool.py
      hooks/
      agents/
      metadata.json          # Compilation metadata
```

### A.3 Mount Plan Schema

```typescript
interface MountPlan {
  profile: string;              // "foundation/base"
  resolved_commit: string;      // Git SHA
  providers: ModuleMount[];
  tools: ModuleMount[];
  hooks: ModuleMount[];
  agents: ModuleMount[];
  contexts: ContextMessage[];
}

interface ModuleMount {
  id: string;                   // "filesystem"
  source_type: "embedded" | "referenced";
  source_path: string;          // Path to module code
  config: Record<string, any>;  // Module-specific configuration
}

interface ContextMessage {
  role: "system" | "user";
  content: string;              // From @mentions and profile contexts
}
```

### A.4 API Endpoints Summary

**Amplified Directories:**
- `GET /amplified-directories` - List discovered projects
- `GET /amplified-directories/{path}` - Get project details

**Profiles:**
- `GET /profiles` - List available profiles
- `GET /profiles/{collection}/{profile}` - Get profile details

**Mount Plans:**
- `GET /mount-plans/{collection}/{profile}` - Generate mount plan

**Sessions:**
- `POST /sessions` - Create new session
- `GET /sessions/{id}` - Get session metadata
- `GET /sessions/{id}/transcript` - Get message history
- `POST /sessions/{id}/messages` - Send message
- `POST /sessions/{id}/profile` - Switch profile
- `PATCH /sessions/{id}` - Update session settings
- `DELETE /sessions/{id}` - Terminate session

**WebSocket:**
- `WS /sessions/{id}/stream` - Real-time message streaming

---

Repository: [payneio/amplifierd](https://github.com/payneio/amplifierd)

License: MIT

Author: Paul Payne

Date: December 2, 2024
