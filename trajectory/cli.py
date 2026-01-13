"""Command-line interface for trajectory."""

import argparse
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from .parser import find_latest_session, list_sessions, parse_session, resolve_session
from .analyzer import analyze_session, analyze_session_for_flow
from .renderer import render_decision_log, render_flow_diagram, render_transcript


def main() -> int:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        prog="trajectory",
        description="Generate decision logs from Claude Code sessions",
        epilog="""
Examples:
  trajectory gen                 Generate trajectory.md from latest session
  trajectory gen --copy          Generate + copy to clipboard
  trajectory gen --flow          ASCII flow diagram
  trajectory gen --audit         Full provenance details
  trajectory transcript          Full conversation to stdout
  trajectory transcript --copy   Copy transcript to clipboard
  trajectory gen -s 17c072d8     Use specific session
  trajectory list                Show available sessions
  trajectory help                Show detailed help

Workflow:
  1. Use Claude Code to build something
  2. Run: trajectory gen (for PR summary) or trajectory transcript (for full conversation)

Requires ANTHROPIC_API_KEY environment variable (for gen command only).
""",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # gen command
    gen_parser = subparsers.add_parser(
        "gen",
        help="Generate decision.md"
    )
    gen_parser.add_argument(
        "-s", "--session",
        metavar="ID",
        help="Session ID or path"
    )
    gen_parser.add_argument(
        "-p", "--project",
        metavar="PATH",
        help="Project path (defaults to current directory)"
    )
    gen_parser.add_argument(
        "-o", "--output",
        metavar="FILE",
        help="Output file (default: trajectory.md)"
    )
    gen_parser.add_argument(
        "--flow",
        action="store_true",
        help="Output as ASCII flow diagram"
    )
    gen_parser.add_argument(
        "--audit",
        action="store_true",
        help="Full output with provenance"
    )
    gen_parser.add_argument(
        "--copy",
        action="store_true",
        help="Copy output to clipboard"
    )
    gen_parser.add_argument(
        "--model",
        default="claude-sonnet-4-20250514",
        help="Claude model for analysis"
    )

    # transcript command
    transcript_parser = subparsers.add_parser(
        "transcript",
        help="Output full conversation transcript"
    )
    transcript_parser.add_argument(
        "-s", "--session",
        metavar="ID",
        help="Session ID or path"
    )
    transcript_parser.add_argument(
        "-p", "--project",
        metavar="PATH",
        help="Project path (defaults to current directory)"
    )
    transcript_parser.add_argument(
        "--copy",
        action="store_true",
        help="Copy output to clipboard"
    )

    # list command
    list_parser = subparsers.add_parser(
        "list",
        help="List available sessions"
    )
    list_parser.add_argument(
        "-p", "--project",
        metavar="PATH",
        help="Project path"
    )

    # help command
    help_parser = subparsers.add_parser(
        "help",
        help="Show detailed help"
    )

    args = parser.parse_args()

    # Handle subcommands
    if args.command == "gen":
        return cmd_gen(args)
    elif args.command == "transcript":
        return cmd_transcript(args)
    elif args.command == "list":
        return cmd_list(args)
    elif args.command == "help":
        return cmd_help()
    else:
        parser.print_help()
        return 0


def cmd_gen(args) -> int:
    """Generate decision.md."""
    # Find session
    if args.session:
        if "/" in args.session or args.session.endswith(".jsonl"):
            session_path = Path(args.session)
        else:
            session_path = resolve_session(args.session, args.project)
    else:
        session_path = find_latest_session(args.project)

    if not session_path or not session_path.exists():
        print("Error: No session found", file=sys.stderr)
        print("Use 'trajectory list' to see available sessions", file=sys.stderr)
        return 1

    # Parse session
    print(f"Parsing session: {session_path.stem[:8]}", file=sys.stderr)
    data = parse_session(session_path)

    print(f"Found {len(data.user_prompts)} prompts, {len(data.file_changes)} file changes", file=sys.stderr)

    # Analyze
    if args.flow:
        print("Analyzing for flow...", file=sys.stderr)
        analysis = analyze_session_for_flow(data, model=args.model)
        output = render_flow_diagram(data, analysis)
    else:
        print("Analyzing...", file=sys.stderr)
        analysis = analyze_session(data, model=args.model)
        output = render_decision_log(data, analysis, audit=args.audit)

    if analysis:
        print(f"Extracted {len(analysis.decisions)} decisions", file=sys.stderr)

    # Handle output
    if args.copy:
        copy_to_clipboard(output)
        print("Copied to clipboard", file=sys.stderr)

    if args.flow:
        # Flow outputs to stdout
        print(output)
    else:
        # Markdown writes to file
        output_path = args.output or "trajectory.md"
        with open(output_path, "w") as f:
            f.write(output)
        print(f"Written to {output_path}", file=sys.stderr)

    return 0


def cmd_transcript(args) -> int:
    """Output full conversation transcript."""
    # Find session
    if args.session:
        if "/" in args.session or args.session.endswith(".jsonl"):
            session_path = Path(args.session)
        else:
            session_path = resolve_session(args.session, args.project)
    else:
        session_path = find_latest_session(args.project)

    if not session_path or not session_path.exists():
        print("Error: No session found", file=sys.stderr)
        print("Use 'trajectory list' to see available sessions", file=sys.stderr)
        return 1

    # Parse session
    print(f"Parsing session: {session_path.stem[:8]}", file=sys.stderr)
    data = parse_session(session_path)

    print(f"Found {len(data.conversation)} turns", file=sys.stderr)

    # Render transcript
    output = render_transcript(data)

    # Handle output
    if args.copy:
        copy_to_clipboard(output)
        print("Copied to clipboard", file=sys.stderr)

    # Always output to stdout
    print(output)

    return 0


def cmd_list(args) -> int:
    """List available sessions."""
    sessions = list_sessions(getattr(args, "project", None))

    if not sessions:
        print("No sessions found", file=sys.stderr)
        return 1

    print("Sessions:\n")
    for i, s in enumerate(sessions, 1):
        mtime = datetime.fromtimestamp(s["modified"])
        print(f"  {i}. {s['session_id'][:8]}")
        print(f"     {mtime.strftime('%Y-%m-%d %H:%M')} | {s['size_kb']:.1f}KB")

    return 0


def cmd_help() -> int:
    """Show detailed help."""
    help_text = """
TRAJECTORY - Capture the why behind AI-generated code

COMMANDS
  trajectory gen [options]        Generate trajectory.md (decision summary)
  trajectory transcript [options] Full conversation transcript to stdout
  trajectory list [options]       List available sessions
  trajectory help                 Show this help

GEN OPTIONS
  -s, --session ID     Use specific session (from 'trajectory list')
  -p, --project PATH   Project directory (default: current)
  -o, --output FILE    Output file (default: trajectory.md)
  --flow               ASCII flow diagram (outputs to stdout)
  --audit              Full output with provenance labels
  --copy               Copy output to clipboard
  --model MODEL        Claude model (default: claude-sonnet-4-20250514)

TRANSCRIPT OPTIONS
  -s, --session ID     Use specific session (from 'trajectory list')
  -p, --project PATH   Project directory (default: current)
  --copy               Copy output to clipboard

LIST OPTIONS
  -p, --project PATH   Project directory (default: current)

OUTPUT FORMATS
  gen (default)        Intent + top 2 decisions (15-second skim)
  gen --audit          All decisions with reasoning + provenance labels
  gen --flow           Visual ASCII diagram of decision flow
  transcript           Full conversation with tool call summaries

PROVENANCE LABELS (in --audit mode)
  [explicit]           User directly stated this
  [chosen]             User selected from options presented
  [inferred]           Deduced from code/context

DECISION TYPES (in --flow mode)
  DIRECTIVE            User explicitly requested this action
  CHOICE               User selected from options
  IMPLEMENT            Action taken based on context

EXAMPLES
  trajectory gen                      Generate trajectory.md
  trajectory gen --copy               Generate + copy to clipboard
  trajectory gen --audit              Full provenance details
  trajectory gen -s a8718b74          Use specific session
  trajectory gen --flow               ASCII diagram to stdout
  trajectory transcript               Full conversation to stdout
  trajectory transcript --copy        Copy transcript to clipboard
  trajectory transcript > session.md  Save transcript to file
  trajectory list                     Show available sessions

WORKFLOW
  For PR reviews:
    trajectory gen → paste trajectory.md into PR description

  For sharing/playback:
    trajectory transcript → share the full conversation

ENVIRONMENT
  ANTHROPIC_API_KEY    Required for 'gen' command. Not needed for 'transcript'.

MORE INFO
  https://github.com/nishantmodak/trajectory-ai
"""
    print(help_text)
    return 0


def copy_to_clipboard(text: str) -> None:
    """Copy text to system clipboard."""
    try:
        if platform.system() == "Darwin":
            subprocess.run(["pbcopy"], input=text.encode(), check=True)
        elif platform.system() == "Linux":
            # Try xclip first, fall back to xsel
            try:
                subprocess.run(["xclip", "-selection", "clipboard"], input=text.encode(), check=True)
            except FileNotFoundError:
                subprocess.run(["xsel", "--clipboard", "--input"], input=text.encode(), check=True)
        else:  # Windows
            subprocess.run(["clip"], input=text.encode(), check=True, shell=True)
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"Warning: Could not copy to clipboard: {e}", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
