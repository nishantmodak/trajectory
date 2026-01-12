"""Data models for trajectory session analysis."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FileChange:
    """Represents a file modification during a session."""
    file_path: str
    change_type: str  # "edit" or "create"
    old_content: Optional[str] = None
    new_content: Optional[str] = None


@dataclass
class ToolCall:
    """Represents a tool invocation during a session."""
    name: str
    input: dict
    timestamp: str


@dataclass
class ConversationTurn:
    """A single turn in the conversation."""
    role: str  # "user" or "assistant"
    text: str
    timestamp: str
    tool_calls: list = field(default_factory=list)


@dataclass
class SessionData:
    """Parsed data from a Claude Code session."""
    session_id: str
    project_path: str
    git_branch: str
    user_prompts: list = field(default_factory=list)
    assistant_responses: list = field(default_factory=list)
    conversation: list = field(default_factory=list)
    tool_calls: list = field(default_factory=list)
    file_changes: list = field(default_factory=list)
    start_time: Optional[str] = None
    end_time: Optional[str] = None


@dataclass
class AnalysisResult:
    """Structured analysis of a coding session.

    Contains only factual records of what happened:
    - decisions: Choices that were made
    - rejected: Alternatives discussed but not chosen
    - assumptions: What was taken for granted
    - deferred: Things explicitly pushed to later
    """
    intent: str
    decisions: list
    rejected: list
    assumptions: list
    deferred: list
