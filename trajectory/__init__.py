"""Trajectory - Generate decision logs from Claude Code sessions.

Trajectory parses Claude Code session logs and generates structured
decision documents for PR review, capturing intent, changes, and reasoning.

Basic usage:
    from trajectory import parse_session, render_decision_log

    data = parse_session(Path("~/.claude/projects/.../session.jsonl"))
    output = render_decision_log(data)
    print(output)

With AI analysis:
    from trajectory import parse_session, analyze_session, render_decision_log

    data = parse_session(session_path)
    analysis = analyze_session(data)  # Requires ANTHROPIC_API_KEY
    output = render_decision_log(data, analysis, audit=True)
"""

__version__ = "0.2.0"

from .models import (
    SessionData,
    AnalysisResult,
    FileChange,
    ToolCall,
    ConversationTurn,
)
from .parser import (
    parse_session,
    find_latest_session,
    list_sessions,
    build_transcript,
)
from .analyzer import analyze_session, analyze_session_for_flow
from .renderer import render_decision_log, render_flow_diagram
from .cli import main

__all__ = [
    # Models
    "SessionData",
    "AnalysisResult",
    "FileChange",
    "ToolCall",
    "ConversationTurn",
    # Parser
    "parse_session",
    "find_latest_session",
    "list_sessions",
    "build_transcript",
    # Analyzer
    "analyze_session",
    "analyze_session_for_flow",
    # Renderer
    "render_decision_log",
    "render_flow_diagram",
    # CLI
    "main",
]
