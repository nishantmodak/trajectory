"""Analyze sessions using Claude API to extract decisions."""

import json
import os
import re
import sys
from typing import Optional

from .models import SessionData, AnalysisResult
from .parser import build_transcript

# Analysis prompt template
ANALYSIS_PROMPT = '''Analyze this coding session and extract CODE DECISIONS for a PR review.

{files_summary}

Transcript (filtered to code-relevant discussion):
{transcript}

Respond in this exact JSON format:
{{
  "intent": "What feature/fix/change was being implemented (1-2 sentences, focus on the WHAT and WHY)",
  "decisions": [
    {{
      "decision": "What was decided",
      "reasoning": "Why this choice was made",
      "provenance": "explicit|chosen|inferred",
      "context": "Readable summary of how this decision came about"
    }}
  ],
  "rejected": [
    {{
      "alternative": "What was considered but not chosen",
      "reason": "Why it was rejected",
      "provenance": "explicit|chosen",
      "context": "Summary of the discussion"
    }}
  ],
  "assumptions": [
    {{
      "assumption": "What was taken for granted",
      "provenance": "explicit|inferred",
      "context": "How this assumption surfaced"
    }}
  ],
  "deferred": [
    {{
      "item": "What was explicitly pushed to later",
      "provenance": "explicit",
      "context": "Summary of why it was deferred"
    }}
  ]
}}

CONTEXT FIELD - Make it readable for someone reviewing later:
- For [chosen]: "Selected from options: X / Y / Z" - list what the alternatives were
- For [explicit]: "User requested X because Y" - capture the why
- For [inferred]: "Based on pattern in codebase" or "Implied by file structure"
- NOT verbatim quotes. Summarize so it's understandable without the transcript.

RULES:
- "decisions": Only actual choices made. Must have evidence in conversation or code.
- "rejected": Only alternatives that were ACTUALLY discussed and not chosen.
- "assumptions": Things taken for granted. Can be inferred from context.
- "deferred": Only things EXPLICITLY marked as "later", "out of scope", "not now".

PROVENANCE:
- "explicit": User directly stated this
- "chosen": User selected from options assistant presented
- "inferred": Deduced from code/context (NOT allowed for rejected/deferred)

NO INTERPRETATION. Only record what happened. Do not add risks, suggestions, or code review comments.

Aim for 3-6 decisions, 0-2 rejected (only if actually discussed), 1-3 assumptions, 0-2 deferred (only if explicit).'''


def analyze_session(data: SessionData, model: str = "claude-sonnet-4-20250514") -> Optional[AnalysisResult]:
    """Use Claude API to analyze the session and extract decisions.

    Args:
        data: Parsed session data.
        model: Claude model to use for analysis.

    Returns:
        AnalysisResult with extracted decisions, or None on error.

    Requires:
        ANTHROPIC_API_KEY environment variable.
    """
    try:
        import anthropic
    except ImportError:
        print("Error: anthropic package not installed. Run: pip install anthropic", file=sys.stderr)
        return None

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY environment variable not set", file=sys.stderr)
        return None

    client = anthropic.Anthropic(api_key=api_key)

    # Build context
    transcript = build_transcript(data, code_focused=True)
    files_summary = _build_files_summary(data)

    prompt = ANALYSIS_PROMPT.format(
        files_summary=files_summary,
        transcript=transcript
    )

    try:
        print("Analyzing session with Claude...", file=sys.stderr)
        response = client.messages.create(
            model=model,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = response.content[0].text
        return _parse_analysis_response(response_text)

    except Exception as e:
        print(f"Error during analysis: {e}", file=sys.stderr)
        return None


def _build_files_summary(data: SessionData) -> str:
    """Build a summary of files changed in the session."""
    if not data.file_changes:
        return ""

    files_changed = {}
    for change in data.file_changes:
        rel_path = _relativize_path(change.file_path, data.project_path)
        if rel_path not in files_changed:
            files_changed[rel_path] = {"edits": 0, "created": False}
        if change.change_type == "create":
            files_changed[rel_path]["created"] = True
        else:
            files_changed[rel_path]["edits"] += 1

    files_list = []
    for path, info in files_changed.items():
        if info["created"]:
            files_list.append(f"- {path} (created)")
        else:
            files_list.append(f"- {path} ({info['edits']} edits)")

    return "Files changed:\n" + "\n".join(files_list)


def _relativize_path(file_path: str, project_path: str) -> str:
    """Make file path relative to project."""
    if project_path and file_path.startswith(project_path):
        return file_path[len(project_path):].lstrip("/")
    return file_path


# Flow-specific analysis prompt
FLOW_ANALYSIS_PROMPT = '''Analyze this coding session to create a DECISION FLOW visualization.

{files_summary}

Transcript:
{transcript}

Extract the decision sequence as a FLOW. Respond in this exact JSON format:
{{
  "intent": "What user wanted to accomplish (max 35 chars)",
  "decisions": [
    {{
      "decision": "Short statement (max 35 chars)",
      "type": "directive|choice|implement",
      "context": "For choice: list options. For directive: why (optional)"
    }}
  ],
  "rejected": [
    {{
      "alternative": "What was not chosen (max 35 chars)"
    }}
  ],
  "deferred": [
    {{
      "item": "What was pushed to later (max 30 chars)"
    }}
  ]
}}

DECISION TYPES:
- "directive": User explicitly requested this action
- "choice": User selected from options presented
- "implement": Action taken based on context/inference

RULES:
- Keep text SHORT (max 35 chars) - these render in narrow ASCII boxes
- Sequence order: how the session actually progressed
- Focus on the chain: Intent → Decisions → Output
- Skip git/process decisions, focus on code decisions
- Aim for 2-4 decisions, 0-2 rejected, 0-1 deferred
- NO assumptions section needed'''


def analyze_session_for_flow(data: SessionData, model: str = "claude-sonnet-4-20250514") -> Optional[AnalysisResult]:
    """Use Claude API to analyze the session specifically for flow visualization.

    Uses a different prompt optimized for sequential decision flow.

    Args:
        data: Parsed session data.
        model: Claude model to use for analysis.

    Returns:
        AnalysisResult with extracted decisions, or None on error.

    Requires:
        ANTHROPIC_API_KEY environment variable.
    """
    try:
        import anthropic
    except ImportError:
        print("Error: anthropic package not installed. Run: pip install anthropic", file=sys.stderr)
        return None

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY environment variable not set", file=sys.stderr)
        return None

    client = anthropic.Anthropic(api_key=api_key)

    # Build context
    transcript = build_transcript(data, code_focused=True)
    files_summary = _build_files_summary(data)

    prompt = FLOW_ANALYSIS_PROMPT.format(
        files_summary=files_summary,
        transcript=transcript
    )

    try:
        print("Analyzing session for flow visualization...", file=sys.stderr)
        response = client.messages.create(
            model=model,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = response.content[0].text
        return _parse_analysis_response(response_text)

    except Exception as e:
        print(f"Error during flow analysis: {e}", file=sys.stderr)
        return None


def _parse_analysis_response(response_text: str) -> Optional[AnalysisResult]:
    """Parse the JSON response from Claude."""
    json_match = re.search(r'\{[\s\S]*\}', response_text)
    if not json_match:
        return None

    try:
        result = json.loads(json_match.group())
        return AnalysisResult(
            intent=result.get("intent", ""),
            decisions=result.get("decisions", []),
            rejected=result.get("rejected", []),
            assumptions=result.get("assumptions", []),
            deferred=result.get("deferred", [])
        )
    except json.JSONDecodeError:
        return None
