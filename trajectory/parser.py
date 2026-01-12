"""Parse Claude Code session logs."""

import json
import os
from pathlib import Path
from typing import Optional

from .models import SessionData, FileChange, ToolCall, ConversationTurn
from .filters import is_noise_message, is_code_relevant_tool


def get_claude_projects_dir() -> Path:
    """Get the Claude Code projects directory."""
    return Path.home() / ".claude" / "projects"


def get_project_hash(cwd: str) -> str:
    """Convert a filesystem path to Claude's project hash format."""
    return cwd.replace("/", "-").lstrip("-")


def find_latest_session(project_path: Optional[str] = None) -> Optional[Path]:
    """Find the most recent session file for a project.

    Args:
        project_path: Filesystem path to the project. Defaults to cwd.

    Returns:
        Path to the session JSONL file, or None if not found.
    """
    projects_dir = get_claude_projects_dir()

    if project_path:
        project_hash = get_project_hash(project_path)
    else:
        project_hash = get_project_hash(os.getcwd())

    project_dir = projects_dir / project_hash

    if not project_dir.exists():
        # Try to find a matching project directory
        for p in projects_dir.iterdir():
            if project_hash in p.name or p.name in project_hash:
                project_dir = p
                break

    if not project_dir.exists():
        return None

    # Find all session files and return the most recent
    sessions = list(project_dir.glob("*.jsonl"))
    if not sessions:
        return None

    sessions.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    return sessions[0]


def resolve_session(session_id: str, project_path: Optional[str] = None) -> Optional[Path]:
    """Resolve a session ID to its full path.

    Args:
        session_id: Full or partial session ID (e.g., "17c072d8" or full UUID).
        project_path: Filesystem path to the project. Defaults to cwd.

    Returns:
        Path to the session JSONL file, or None if not found.
    """
    projects_dir = get_claude_projects_dir()
    project_path = project_path or os.getcwd()
    project_hash = get_project_hash(project_path)

    # Find matching project directory
    project_dir = None
    for p in projects_dir.iterdir():
        if project_hash in p.name or p.name in project_hash:
            project_dir = p
            break

    if not project_dir or not project_dir.exists():
        return None

    # Find session file matching the ID
    for session_file in project_dir.glob("*.jsonl"):
        if session_file.stem.startswith(session_id) or session_id in session_file.stem:
            return session_file

    return None


def list_sessions(project_path: Optional[str] = None, limit: int = 20) -> list:
    """List available sessions for a project.

    Returns:
        List of dicts with session_id, modified, size_kb.
    """
    projects_dir = get_claude_projects_dir()
    project_path = project_path or os.getcwd()
    project_hash = get_project_hash(project_path)

    # Find matching project directory
    project_dir = None
    for p in projects_dir.iterdir():
        if project_hash in p.name or p.name in project_hash:
            project_dir = p
            break

    if not project_dir or not project_dir.exists():
        return []

    sessions = sorted(
        project_dir.glob("*.jsonl"),
        key=lambda x: x.stat().st_mtime,
        reverse=True
    )

    result = []
    for s in sessions[:limit]:
        stat = s.stat()
        result.append({
            "session_id": s.stem,
            "path": s,
            "modified": stat.st_mtime,
            "size_kb": stat.st_size / 1024
        })

    return result


def parse_session(session_path: Path) -> SessionData:
    """Parse a session JSONL file and extract structured data.

    Args:
        session_path: Path to the .jsonl session file.

    Returns:
        SessionData with parsed conversation, tool calls, and file changes.
    """
    session_id = session_path.stem

    data = SessionData(
        session_id=session_id,
        project_path="",
        git_branch=""
    )

    with open(session_path, "r") as f:
        for line in f:
            if not line.strip():
                continue

            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            _process_entry(entry, data)

    return data


def _process_entry(entry: dict, data: SessionData) -> None:
    """Process a single JSONL entry and update SessionData."""
    # Extract metadata
    if "cwd" in entry and not data.project_path:
        data.project_path = entry["cwd"]
    if "gitBranch" in entry and entry["gitBranch"]:
        data.git_branch = entry["gitBranch"]

    # Track timestamps
    if "timestamp" in entry:
        if not data.start_time:
            data.start_time = entry["timestamp"]
        data.end_time = entry["timestamp"]

    # Process user messages
    if entry.get("type") == "user":
        _process_user_message(entry, data)

    # Process assistant messages
    if entry.get("type") == "assistant":
        _process_assistant_message(entry, data)


def _process_user_message(entry: dict, data: SessionData) -> None:
    """Extract user prompts from a message entry."""
    message = entry.get("message", {})
    content = message.get("content", [])
    timestamp = entry.get("timestamp", "")

    text_parts = []
    if isinstance(content, str):
        text_parts.append(content.strip())
    elif isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block.get("text", "").strip())

    combined_text = "\n".join(t for t in text_parts if t)
    if combined_text and len(combined_text) > 5:
        data.user_prompts.append({
            "text": combined_text,
            "timestamp": timestamp
        })
        data.conversation.append(ConversationTurn(
            role="user",
            text=combined_text,
            timestamp=timestamp
        ))


def _process_assistant_message(entry: dict, data: SessionData) -> None:
    """Extract assistant responses and tool calls from a message entry."""
    message = entry.get("message", {})
    content = message.get("content", [])
    timestamp = entry.get("timestamp", "")

    if not isinstance(content, list):
        return

    text_parts = []
    turn_tool_calls = []

    for block in content:
        if not isinstance(block, dict):
            continue

        # Extract text responses
        if block.get("type") == "text":
            text = block.get("text", "").strip()
            if text:
                text_parts.append(text)

        # Extract tool calls
        if block.get("type") == "tool_use":
            tool_call = _process_tool_call(block, timestamp, data)
            if tool_call:
                turn_tool_calls.append(tool_call)

    combined_text = "\n".join(text_parts)
    if combined_text or turn_tool_calls:
        data.assistant_responses.append({
            "text": combined_text,
            "tool_calls": turn_tool_calls,
            "timestamp": timestamp
        })
        data.conversation.append(ConversationTurn(
            role="assistant",
            text=combined_text,
            timestamp=timestamp,
            tool_calls=turn_tool_calls
        ))


def _process_tool_call(block: dict, timestamp: str, data: SessionData) -> Optional[ToolCall]:
    """Process a tool_use block and track file changes."""
    tool_name = block.get("name", "")
    tool_input = block.get("input", {})

    tool_call = ToolCall(
        name=tool_name,
        input=tool_input,
        timestamp=timestamp
    )
    data.tool_calls.append(tool_call)

    # Track file changes
    if tool_name == "Edit":
        data.file_changes.append(FileChange(
            file_path=tool_input.get("file_path", ""),
            change_type="edit",
            old_content=tool_input.get("old_string", ""),
            new_content=tool_input.get("new_string", "")
        ))
    elif tool_name == "Write":
        data.file_changes.append(FileChange(
            file_path=tool_input.get("file_path", ""),
            change_type="create",
            new_content=tool_input.get("content", "")
        ))

    return tool_call


def build_transcript(data: SessionData, max_length: int = 50000, code_focused: bool = True) -> str:
    """Build a readable transcript of the conversation for analysis.

    Args:
        data: Parsed session data.
        max_length: Maximum transcript length in characters.
        code_focused: If True, filter out noise and non-code-related content.

    Returns:
        Formatted transcript string.
    """
    lines = []
    total_len = 0

    for turn in data.conversation:
        # Filter noise messages in code-focused mode
        if code_focused and turn.role == "user" and is_noise_message(turn.text):
            continue

        prefix = "USER: " if turn.role == "user" else "ASSISTANT: "
        text = turn.text[:2000] if turn.text else ""

        # Include tool calls summary for assistant turns
        if turn.role == "assistant" and turn.tool_calls:
            if code_focused:
                relevant_tools = [tc for tc in turn.tool_calls if is_code_relevant_tool(tc)]
            else:
                relevant_tools = turn.tool_calls

            if relevant_tools:
                tool_summary = ", ".join(
                    f"{tc.name}({list(tc.input.keys())[0] if tc.input else ''})"
                    for tc in relevant_tools[:5]
                )
                if len(relevant_tools) > 5:
                    tool_summary += f", ... +{len(relevant_tools) - 5} more"
                if text:
                    text = f"{text}\n[Tools: {tool_summary}]"
                else:
                    text = f"[Tools: {tool_summary}]"
            elif not text:
                continue

        if text:
            entry = f"{prefix}{text}\n"
            if total_len + len(entry) > max_length:
                lines.append("... [transcript truncated] ...")
                break
            lines.append(entry)
            total_len += len(entry)

    return "\n".join(lines)
