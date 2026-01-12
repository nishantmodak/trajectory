"""Filters for removing noise from session transcripts."""

from .models import ToolCall

# Short confirmations that don't add signal
NOISE_PHRASES = frozenset([
    "yes", "no", "ok", "okay", "sure", "thanks", "thank you",
    "y", "n", "yep", "nope", "got it", "sounds good", "go ahead",
    "do it", "proceed", "continue", "next", "done", "good"
])

# Git commands to filter from code-focused analysis
GIT_COMMANDS = [
    "git ", "git push", "git commit", "git add", "git checkout",
    "git rebase", "git fetch", "git status", "git diff", "git log",
    "git merge", "git pull", "git reset", "git stash", "git branch"
]

# Package manager commands to filter
PROCESS_COMMANDS = [
    "yarn ", "npm ", "pnpm ", "pip ", "brew ", "cargo ",
    "go mod", "bundle ", "composer "
]


def is_noise_message(text: str) -> bool:
    """Check if a user message is noise (confirmation, short response, system message)."""
    if not text:
        return True

    text_lower = text.lower().strip()

    # Skip very short confirmations
    if len(text_lower) < 20 and text_lower in NOISE_PHRASES:
        return True

    # Skip system/task notifications
    if text_lower.startswith(("<task-notification", "<command-")):
        return True

    return False


def is_system_noise(text: str) -> bool:
    """Check if text is system-generated noise (for intent extraction)."""
    if not text:
        return True

    return (
        text.startswith("<command-") or
        text.startswith("<task-") or
        text.startswith("Base directory for this skill") or
        text.startswith("# ") or
        len(text.strip()) < 10
    )


def is_code_relevant_tool(tool_call: ToolCall) -> bool:
    """Check if a tool call is relevant to code decisions (not git/process)."""
    if tool_call.name in ("Edit", "Write"):
        return True

    if tool_call.name == "Bash":
        cmd = tool_call.input.get("command", "").lower()

        # Filter out git commands
        for git_cmd in GIT_COMMANDS:
            if cmd.startswith(git_cmd):
                return False

        # Filter out package manager commands
        for proc_cmd in PROCESS_COMMANDS:
            if cmd.startswith(proc_cmd):
                return False

        return True

    if tool_call.name in ("Grep", "Glob", "Read"):
        return True

    return False
