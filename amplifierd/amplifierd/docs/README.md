# Amplifierd Documentation

**Profile management daemon for Amplifier**

---

## What is amplifierd?

Amplifierd is a daemon that manages **profiles** - reusable session configurations for the Amplifier AI agent system. Think of profiles as templates that define which AI models, tools, agents, and settings to use for different workflows.

Instead of configuring each session manually, you define a profile once and reuse it across sessions.

**Example use cases:**
- "coding" profile: Code-focused agents, development tools, code review workflows
- "research" profile: Research agents, web search, knowledge synthesis tools
- "writing" profile: Writing assistants, style guides, grammar tools

---

## Quick Start

**1. Understand the system** (5 min):
```
Profile (what you want)
    ↓ (transformation)
Mount Plan (what amplifier-core needs)
    ↓ (initialization)
Session (running instance)
```

**2. See a real example**:
```yaml
# profiles/foundation/base.md
---
session:
  orchestrator:
    module: loop-streaming
  context:
    module: context-simple
providers:
- module: provider-anthropic
tools:
- module: tool-web
agents:
  code-expert: https://example.com/agents/code-expert.md
---
```

**3. Use a profile**:
```bash
# Start daemon
amplifierd start

# Create session with profile
curl -X POST http://localhost:8000/api/v1/sessions \
  -d '{"profile_name": "foundation/base"}'

# Execute prompt
curl -X POST http://localhost:8000/api/v1/sessions/{id}/execute \
  -d '{"content": "Hello!"}'
```

---

## Documentation Structure

### Learn the Concepts (Start Here)

**15-minute introduction:**
1. [Overview](01-concepts/overview.md) - The big picture
2. [Profiles](01-concepts/profiles.md) - Profile structure and syntax
3. [Mount Plans](01-concepts/mount-plans.md) - Runtime format

### Advanced Topics

**Deep technical details:**
- [Profile Lifecycle](04-advanced/profile-lifecycle.md) - Complete transformation flow

---

## Core Concepts at a Glance

**Profile**: User-facing configuration template
- Written in markdown with YAML frontmatter
- References external modules (git URLs)
- Named as `collection/profile` (e.g., `foundation/base`)

**Collection**: Group of related profiles
- Defined in `.amplifierd/share/collections.yaml`
- Can be local or from git repositories
- Example: `foundation` collection with `base`, `dev`, `production` profiles

**Mount Plan**: Runtime configuration dict
- Generated from profiles
- Contains module IDs + profile hints
- What amplifier-core uses to initialize sessions

**Module**: Executable component
- orchestrator: Controls execution loop
- context: Manages conversation context
- providers: LLM providers (Anthropic, OpenAI, etc.)
- tools: Capabilities (web, filesystem, etc.)
- hooks: Lifecycle extensions
- agents: AI personas (embedded as content)

---

## The Flow: Profile → Session

```
1. collections.yaml → Collection sources (git repos)
   └─ Cached to: .amplifierd/cache/git/{hash}/

2. Collection → Profile specs (profile.md files)
   └─ Compiled to: .amplifierd/share/profiles/{collection}/{profile}/

3. Profile → Mount Plan (dict with module IDs)
   └─ Saved to: .amplifierd/state/sessions/{id}/mount_plan.json

4. Mount Plan → AmplifierSession (running instance)
   └─ Modules loaded via DaemonModuleSourceResolver
```

---

## Real Example: foundation/base

**Profile location:**
```
registry/profiles/foundation/base.md
```

**Compiled to:**
```
.amplifierd/share/profiles/foundation/base/
├── orchestrator/loop-streaming/
├── context/context-simple/
├── providers/provider-anthropic/
├── tools/tool-web/
├── hooks/hooks-logging/
└── agents/code-expert.md
```

**Mount plan generated:**
```json
{
  "session": {
    "orchestrator": {
      "module": "loop-streaming",
      "source": "foundation/base",
      "config": {...}
    }
  },
  "providers": [...],
  "agents": {...}
}
```

**Session created:**
```
AmplifierSession(config=mount_plan)
  ↓ (resolver translates "foundation/base" → filesystem path)
Modules loaded and session ready!
```

---

## Getting Help

**Common questions:**
- "What's a profile?" → [profiles.md](01-concepts/profiles.md)
- "How do mount plans work?" → [mount-plans.md](01-concepts/mount-plans.md)
- "Where are things cached?" → [profile-lifecycle.md](04-advanced/profile-lifecycle.md)

**Troubleshooting:**
- Profile not found → Check cache: `.amplifierd/share/profiles/`
- Module not loading → Check compilation logs
- Session fails → Verify mount plan format

---

## Philosophy

This documentation follows amplifierd's implementation philosophy:
- **Ruthless simplicity**: Explain only what's essential
- **Show, don't tell**: Real examples > abstract descriptions
- **Progressive disclosure**: Start simple, add depth as needed
- **Clear contracts**: Specify inputs, outputs, and transformations

---

**Ready to learn more?** Start with [01-concepts/overview.md](01-concepts/overview.md)
