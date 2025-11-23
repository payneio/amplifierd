# Amplifier profiles

Persistent issue tracking for Amplifier sessions with dependency management and priority-based scheduling.

## What This Provides

- **issue_manager tool** - Create, list, update, and close issues with dependencies
- **issue-aware profile** - Pre-configured session with issue management enabled
- **Local storage** - Issues stored in `.amplifier/issues/` as JSONL files

## Installation

First, install Amplifier:

```bash
uv tool install git+https://github.com/microsoft/amplifier@next
```

Then add this collection:

```bash
amplifier collection add git+https://github.com/payneio/payne-amplifier@main#subdirectory=max_payne_collection
```

## Usage

### Quick Start

Run Amplifier with the issue-aware profile:

```bash
amplifier run --profile max-payne-collection:issue-aware
```

Then interact with issues:

```
You: "Create an issue to implement user authentication"
Assistant: [Creates issue with the issue_manager tool]

You: "What can I work on?"
Assistant: [Lists ready issues with get_ready operation]

You: "Work on issue <id>"
Assistant: [Updates status to in_progress and begins work]
```

### Manual Configuration

Add the tool to your own profile:

```yaml
tools:
  - module: tool-issue
    source: git+https://github.com/payneio/payne-amplifier@main#subdirectory=max_payne_collection/modules/tool-issue
    config:
      data_dir: .amplifier/issues
      actor: assistant
```

## Data Storage

Issues are stored locally in your project:

```
<project-root>/
└── .amplifier/
    └── issues/
        ├── issues.jsonl          # Issue records
        ├── dependencies.jsonl    # Issue relationships
        └── events.jsonl          # Change history
```

## Issue Operations

The issue_manager tool supports:

- **create** - New issue with priority and type
- **list** - Filter by status, priority, assignee
- **get** - Show issue details
- **update** - Change status, priority, blocking notes
- **close** - Mark complete with reason
- **get_ready** - Find work with no blockers
- **get_blocked** - See blocked issues
- **add_dep** - Link issues with dependencies
- **remove_dep** - Remove dependency links

## Issue States

- **open** - Created, not yet started
- **in_progress** - Actively being worked on
- **blocked** - Waiting on dependencies
- **closed** - Completed

## Priorities

- **0** - Critical
- **1** - High
- **2** - Normal (default)
- **3** - Low
- **4** - Deferred

## License

MIT License - See LICENSE file for details
