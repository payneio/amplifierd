"""Execution trace persistence hook for tracking session activity.

Persists execution traces to JSONL files for historical analysis and debugging.
Each turn (user message + assistant response cycle) is recorded with:
- Tool calls (timing, arguments, results)
- Thinking blocks
- Sub-agent invocations
- Status and errors
"""

import json
import logging
from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from amplifier_core.hooks import HookResult

logger = logging.getLogger(__name__)


class ExecutionTraceHook:
    """Persists execution trace to JSONL file.

    Tracks complete execution cycles including:
    - User messages and assistant responses
    - Tool invocations with timing and results
    - Thinking blocks with timestamps
    - Sub-agent calls (Task tool invocations)
    - Errors and status information

    File Format:
        - One JSON object per line (JSONL)
        - Each line represents one complete turn
        - Atomic writes via temp file + rename

    Example:
        hook = ExecutionTraceHook(session_dir)
        # Hook is registered with StreamingHookRegistry
        # Events automatically tracked during execution
    """

    def __init__(self: "ExecutionTraceHook", session_dir: Path) -> None:
        """Initialize execution trace hook.

        Args:
            session_dir: Path to session directory for storing trace file
        """
        self.session_dir = session_dir
        self.trace_file = session_dir / "execution_trace.jsonl"
        self.current_turn: dict[str, Any] | None = None

        logger.debug(f"Initialized ExecutionTraceHook for {session_dir}")

    async def on_assistant_message_start(self: "ExecutionTraceHook", event: str, data: dict[str, Any]) -> HookResult:
        """Start new turn tracking.

        Args:
            event: Hook event name
            data: Hook data containing user_message and context

        Returns:
            HookResult with continue action
        """
        self.current_turn = {
            "turn_id": str(uuid4()),
            "user_message": data.get("user_message", ""),
            "status": "active",
            "start_time": datetime.now(UTC).isoformat(),
            "tools": [],
            "thinking": [],
        }
        logger.info(f"Turn started: {self.current_turn['turn_id']}")
        return HookResult(action="continue")

    async def on_tool_pre(self: "ExecutionTraceHook", event: str, data: dict[str, Any]) -> HookResult:
        """Record tool invocation start.

        Args:
            event: Hook event name
            data: Hook data with tool_name, tool_input, parallel_group_id

        Returns:
            HookResult with continue action
        """
        if self.current_turn is None:
            logger.warning("Received tool:pre without active turn")
            return HookResult(action="continue")

        # Detect sub-agent calls (Task tool with subagent_type)
        tool_name = data.get("tool_name", "")
        tool_input = data.get("tool_input", {})
        parallel_group_id = data.get("parallel_group_id", "")
        is_sub_agent = tool_name == "Task"
        sub_agent_name = tool_input.get("subagent_type") if is_sub_agent else None

        tool = {
            "name": tool_name,
            "parallel_group_id": parallel_group_id,
            "status": "starting",
            "start_time": datetime.now(UTC).isoformat(),
            "arguments": tool_input,
            "is_sub_agent": is_sub_agent,
            "sub_agent_name": sub_agent_name,
        }
        self.current_turn["tools"].append(tool)
        logger.info(f"Tool added: {tool_name} (parallel_group_id={parallel_group_id}, sub-agent={is_sub_agent})")
        return HookResult(action="continue")

    async def on_tool_post(self: "ExecutionTraceHook", event: str, data: dict[str, Any]) -> HookResult:
        """Record tool completion.

        Args:
            event: Hook event name
            data: Hook data with tool_name, parallel_group_id, result, is_error

        Returns:
            HookResult with continue action
        """
        if self.current_turn is None:
            logger.warning("Received tool:post without active turn")
            return HookResult(action="continue")

        # Find matching tool by tool_name + parallel_group_id
        tool_name = data.get("tool_name", "")
        parallel_group_id = data.get("parallel_group_id", "")

        logger.info(f"Attempting to match tool: {tool_name} (parallel_group_id={parallel_group_id})")

        tool = next(
            (
                t
                for t in self.current_turn["tools"]
                if t.get("name") == tool_name
                and t.get("parallel_group_id") == parallel_group_id
                and t.get("status") in ["starting", "running"]
            ),
            None,
        )

        if tool is None:
            tool_list = [
                f"{t.get('name')}:{t.get('parallel_group_id')}:{t.get('status')}" for t in self.current_turn["tools"]
            ]
            logger.warning(
                f"No matching tool found for {tool_name} (parallel_group_id={parallel_group_id}). "
                f"Current tools: {tool_list}"
            )
            return HookResult(action="continue")

        # Update tool status and timing
        end_time = datetime.now(UTC)
        start_time = datetime.fromisoformat(tool["start_time"])
        duration_ms = (end_time - start_time).total_seconds() * 1000

        is_error = data.get("is_error", False)
        tool_result = data.get("result", data.get("tool_result", ""))

        tool["status"] = "error" if is_error else "completed"
        tool["end_time"] = end_time.isoformat()
        tool["duration_ms"] = round(duration_ms, 2)

        # Truncate large results (keep first 1000 chars)
        result_str = str(tool_result)
        tool["result"] = result_str[:1000]
        if len(result_str) > 1000:
            tool["result"] += "... (truncated)"

        if is_error:
            tool["error"] = result_str[:1000]

        logger.info(f"Tool matched and updated: {tool['name']} ({duration_ms:.2f}ms, status={tool['status']})")
        return HookResult(action="continue")

    async def on_thinking_delta(self: "ExecutionTraceHook", event: str, data: dict[str, Any]) -> HookResult:
        """Record thinking block content.

        Args:
            event: Hook event name
            data: Hook data with delta content

        Returns:
            HookResult with continue action
        """
        if self.current_turn is None:
            logger.warning("Received thinking:delta without active turn")
            return HookResult(action="continue")

        thinking = {
            "id": str(uuid4()),
            "content": data.get("delta", ""),
            "timestamp": datetime.now(UTC).isoformat(),
        }
        self.current_turn["thinking"].append(thinking)
        logger.debug("Recorded thinking delta")
        return HookResult(action="continue")

    async def on_assistant_message_complete(self: "ExecutionTraceHook", event: str, data: dict[str, Any]) -> HookResult:
        """Save completed turn to file.

        Uses atomic write (temp file + rename) to prevent corruption.

        Args:
            event: Hook event name
            data: Hook data for message completion

        Returns:
            HookResult with continue action
        """
        if self.current_turn is None:
            logger.warning("Received assistant_message_complete without active turn")
            return HookResult(action="continue")

        # Mark turn as complete with timing
        end_time = datetime.now(UTC)
        start_time = datetime.fromisoformat(self.current_turn["start_time"])
        duration_ms = (end_time - start_time).total_seconds() * 1000

        self.current_turn["status"] = "completed"
        self.current_turn["end_time"] = end_time.isoformat()
        self.current_turn["duration_ms"] = round(duration_ms, 2)

        # Count completed tools
        completed_tools = sum(1 for t in self.current_turn["tools"] if t.get("status") == "completed")
        total_tools = len(self.current_turn["tools"])

        logger.info(
            f"Turn completing: {self.current_turn['turn_id']} "
            f"({duration_ms:.2f}ms, {completed_tools}/{total_tools} tools completed)"
        )

        # Atomic write: temp file + rename
        try:
            temp_file = self.trace_file.with_suffix(".tmp")

            # Append to temp file
            with open(temp_file, "a", encoding="utf-8") as f:
                json.dump(self.current_turn, f, ensure_ascii=False)
                f.write("\n")
                f.flush()

            # Atomic rename
            temp_file.replace(self.trace_file)

            logger.info(f"Turn saved to {self.trace_file}: {self.current_turn['turn_id']}")

        except Exception as e:
            logger.error(f"Failed to save execution trace: {e}")

        finally:
            # Clear current turn
            self.current_turn = None

        return HookResult(action="continue")
