"""Render session analysis to markdown."""

from typing import Optional

from .models import SessionData, AnalysisResult
from .filters import is_system_noise


def render_decision_log(
    data: SessionData,
    analysis: Optional[AnalysisResult] = None,
    audit: bool = False
) -> str:
    """Render session data to markdown decision log.

    Default output (15-second skim):
        - Intent
        - Decisions (1-2)

    Audit output (full provenance):
        - Intent
        - Decisions (all, with provenance)
        - Changed files
        - Rejected alternatives
        - Assumptions
        - Deferred items

    Args:
        data: Parsed session data.
        analysis: Optional AI analysis results.
        audit: If True, include full provenance and all sections.

    Returns:
        Markdown formatted decision log.
    """
    lines = []

    # Header - branch name or generic title
    if data.git_branch:
        lines.append(f"# {data.git_branch}")
    else:
        lines.append("# Decision Log")
    lines.append("")

    # Intent
    _render_intent(lines, data, analysis)

    # Decisions (the main content)
    if analysis and analysis.decisions:
        _render_decisions(lines, analysis, audit)

    # Everything below is audit-only
    if audit:
        # Changed files
        _render_changes(lines, data)

        # Rejected alternatives
        if analysis and analysis.rejected:
            _render_rejected(lines, analysis)

        # Assumptions
        if analysis and analysis.assumptions:
            _render_assumptions(lines, analysis)

        # Deferred items
        if analysis and analysis.deferred:
            _render_deferred(lines, analysis)

    # Footer
    _render_footer(lines, data, audit)

    return "\n".join(lines)


def _render_intent(lines: list, data: SessionData, analysis: Optional[AnalysisResult]) -> None:
    """Render the intent section."""
    if analysis and analysis.intent:
        lines.append(f"> {analysis.intent}")
    elif data.user_prompts:
        # Find first real user prompt (skip system noise)
        primary = None
        for prompt in data.user_prompts:
            text = prompt["text"]
            if not is_system_noise(text):
                primary = text
                break

        if not primary:
            primary = data.user_prompts[0]["text"]

        if len(primary) > 200:
            primary = primary[:200] + "..."
        lines.append(f"> {primary}")

    lines.append("")


def _render_decisions(lines: list, analysis: AnalysisResult, audit: bool) -> None:
    """Render the decisions section."""
    lines.append("**Decisions:**")
    max_decisions = len(analysis.decisions) if audit else 2

    for item in analysis.decisions[:max_decisions]:
        if isinstance(item, dict):
            decision = item.get("decision", "")
            reasoning = item.get("reasoning", "")
            provenance = item.get("provenance", "")
            context = item.get("context", "")

            if audit:
                lines.append(f"- {decision}")
                if reasoning:
                    lines.append(f"  {reasoning}")
                if provenance or context:
                    badge_parts = []
                    if provenance:
                        badge_parts.append(f"`[{provenance}]`")
                    if context:
                        badge_parts.append(f"_{context}_")
                    lines.append(f"  {' '.join(badge_parts)}")
            else:
                lines.append(f"- {decision}")
        else:
            lines.append(f"- {item}")

    if not audit and len(analysis.decisions) > 2:
        remaining = len(analysis.decisions) - 2
        lines.append(f"  ... +{remaining} more (--audit)")

    lines.append("")


def _render_changes(lines: list, data: SessionData) -> None:
    """Render the files changed section (audit only)."""
    if not data.file_changes:
        return

    files_changed = {}
    for change in data.file_changes:
        rel_path = _relativize_path(change.file_path, data.project_path)
        if rel_path not in files_changed:
            files_changed[rel_path] = {"edits": 0, "created": False}
        if change.change_type == "create":
            files_changed[rel_path]["created"] = True
        else:
            files_changed[rel_path]["edits"] += 1

    lines.append("**Changed:**")
    for file_path, info in files_changed.items():
        if info["created"]:
            lines.append(f"  `{file_path}` (new)")
        else:
            lines.append(f"  `{file_path}`")

    lines.append("")


def _render_rejected(lines: list, analysis: AnalysisResult) -> None:
    """Render rejected alternatives section."""
    lines.append("**Rejected:**")
    for item in analysis.rejected:
        if isinstance(item, dict):
            alternative = item.get("alternative", "")
            reason = item.get("reason", "")
            context = item.get("context", "")
            lines.append(f"- {alternative}")
            if reason:
                lines.append(f"  {reason}")
            if context:
                lines.append(f"  _{context}_")
        else:
            lines.append(f"- {item}")
    lines.append("")


def _render_assumptions(lines: list, analysis: AnalysisResult) -> None:
    """Render assumptions section."""
    lines.append("**Assumptions:**")
    for item in analysis.assumptions:
        if isinstance(item, dict):
            assumption = item.get("assumption", "")
            provenance = item.get("provenance", "")
            context = item.get("context", "")
            line = f"- {assumption}"
            if provenance:
                line += f" `[{provenance}]`"
            if context:
                line += f" _{context}_"
            lines.append(line)
        else:
            lines.append(f"- {item}")
    lines.append("")


def _render_deferred(lines: list, analysis: AnalysisResult) -> None:
    """Render deferred items section."""
    lines.append("**Deferred:**")
    for item in analysis.deferred:
        if isinstance(item, dict):
            deferred_item = item.get("item", "")
            context = item.get("context", "")
            line = f"- {deferred_item}"
            if context:
                line += f" _{context}_"
            lines.append(line)
        else:
            lines.append(f"- {item}")
    lines.append("")


def _render_footer(lines: list, data: SessionData, audit: bool) -> None:
    """Render the footer with session reference."""
    lines.append("---")
    if audit:
        lines.append(f"_Session: {data.session_id}_")
    else:
        lines.append(f"_Session: {data.session_id[:8]}_")


def _relativize_path(file_path: str, project_path: str) -> str:
    """Make file path relative to project."""
    if project_path and file_path.startswith(project_path):
        return file_path[len(project_path):].lstrip("/")
    return file_path


def render_flow_diagram(
    data: SessionData,
    analysis: Optional[AnalysisResult] = None
) -> str:
    """Render session as ASCII decision flow diagram.

    Shows the flow of the session as a visual timeline:
    - Intent
    - Decisions (DIRECTIVE/CHOICE/IMPLEMENT)
    - Output (files changed)
    - Rejected alternatives
    - Deferred items

    Args:
        data: Parsed session data.
        analysis: Optional AI analysis results.

    Returns:
        ASCII flow diagram.
    """
    # Box width constants
    W = 40  # inner width
    lines = []

    # Header
    if data.git_branch:
        lines.append(f"╔══ {data.git_branch} ══╗")
    else:
        lines.append("╔══ Session Flow ══╗")
    lines.append("")

    # Intent at the top
    if analysis and analysis.intent:
        intent = analysis.intent
        if len(intent) > W - 2:
            intent = intent[:W - 5] + "..."
        lines.append(f"  ┌─ INTENT {'─' * (W - 10)}┐")
        lines.append(f"  │ {intent:<{W - 2}} │")
        lines.append(f"  └{'─' * W}┘")
        lines.append(f"{' ' * 20}│")
        lines.append(f"{' ' * 20}▼")

    # Map type to label
    type_labels = {
        "directive": "DIRECTIVE",
        "explicit": "DIRECTIVE",  # backwards compat
        "choice": "CHOICE",
        "chosen": "CHOICE",  # backwards compat
        "implement": "IMPLEMENT",
        "inferred": "IMPLEMENT",  # backwards compat
    }

    # Decisions flow
    if analysis and analysis.decisions:
        for i, item in enumerate(analysis.decisions):
            is_last = (i == len(analysis.decisions) - 1)

            if isinstance(item, dict):
                decision = item.get("decision", "")
                dec_type = item.get("type", item.get("provenance", ""))
                label = type_labels.get(dec_type, "DECISION")

                # Truncate
                if len(decision) > W - 2:
                    decision = decision[:W - 5] + "..."

                # Draw decision box
                header = f"─ {label} "
                lines.append(f"  ┌{header}{'─' * (W - len(header))}┐")
                lines.append(f"  │ {decision:<{W - 2}} │")
                lines.append(f"  └{'─' * W}┘")
            else:
                decision = str(item)
                if len(decision) > W - 2:
                    decision = decision[:W - 5] + "..."
                lines.append(f"  ┌─ DECISION {'─' * (W - 11)}┐")
                lines.append(f"  │ {decision:<{W - 2}} │")
                lines.append(f"  └{'─' * W}┘")

            if not is_last:
                lines.append(f"{' ' * 20}│")
                lines.append(f"{' ' * 20}▼")

    # Files changed (output)
    if data.file_changes:
        lines.append(f"{' ' * 20}│")
        lines.append(f"{' ' * 20}▼")
        lines.append(f"  ┌─ OUTPUT {'─' * (W - 9)}┐")

        files_changed = {}
        for change in data.file_changes:
            rel_path = _relativize_path(change.file_path, data.project_path)
            # Just use filename
            filename = rel_path.split("/")[-1]
            if filename not in files_changed:
                files_changed[filename] = {"edits": 0, "created": False}
            if change.change_type == "create":
                files_changed[filename]["created"] = True
            else:
                files_changed[filename]["edits"] += 1

        for filename, info in list(files_changed.items())[:4]:
            label = "(new)" if info["created"] else f"({info['edits']} edit{'s' if info['edits'] > 1 else ''})"
            display = f"{filename} {label}"
            if len(display) > W - 2:
                display = display[:W - 5] + "..."
            lines.append(f"  │ {display:<{W - 2}} │")

        if len(files_changed) > 4:
            remaining = len(files_changed) - 4
            lines.append(f"  │ +{remaining} more files{' ' * (W - 14 - len(str(remaining)))} │")

        lines.append(f"  └{'─' * W}┘")

    # Rejected alternatives
    if analysis and analysis.rejected:
        lines.append("")
        lines.append(f"  ╳─ REJECTED {'─' * (W - 12)}╳")
        for item in analysis.rejected:
            if isinstance(item, dict):
                alt = item.get("alternative", "")
                if len(alt) > W - 2:
                    alt = alt[:W - 5] + "..."
                lines.append(f"  ╳ {alt:<{W - 2}} ╳")
            else:
                text = str(item)
                if len(text) > W - 2:
                    text = text[:W - 5] + "..."
                lines.append(f"  ╳ {text:<{W - 2}} ╳")
        lines.append(f"  ╳{'─' * W}╳")

    # Deferred (pushed aside)
    if analysis and analysis.deferred:
        lines.append("")
        lines.append(f"  ──▷ DEFERRED {'─' * (W - 13)}▷")
        for item in analysis.deferred:
            if isinstance(item, dict):
                deferred_item = item.get("item", "")
                if len(deferred_item) > W - 4:
                    deferred_item = deferred_item[:W - 7] + "..."
                lines.append(f"    ▷ {deferred_item:<{W - 4}} ▷")
            else:
                text = str(item)
                if len(text) > W - 4:
                    text = text[:W - 7] + "..."
                lines.append(f"    ▷ {text:<{W - 4}} ▷")
        lines.append(f"  ──▷{'─' * (W - 2)}▷")

    # Footer
    lines.append("")
    lines.append(f"╚══ Session: {data.session_id[:8]} ══╝")

    return "\n".join(lines)
