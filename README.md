# trajectory

[![PyPI version](https://badge.fury.io/py/trajectory-ai.svg)](https://pypi.org/project/trajectory-ai/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Capture the *why* behind AI-generated code.

When you use Claude Code to write code, trajectory captures your coding session — decisions made, alternatives rejected, the full conversation. Share the reasoning, not just the diff.

## Install

```bash
pip install trajectory-ai
```

`ANTHROPIC_API_KEY` required for `gen` command (decision summaries).

## Usage

```bash
cd your-project
trajectory gen
```

Creates `trajectory.md`:

```markdown
# feat/add-user-auth

> Implement JWT authentication for the API

**Decisions:**
- Use RS256 for token signing
- Store refresh tokens in httpOnly cookies
  ... +3 more (--audit)

---
_Session: a1b2c3d4_
```

## Commands

```bash
trajectory gen                 # generate trajectory.md (decision summary)
trajectory gen --copy          # generate + copy to clipboard
trajectory gen --flow          # ASCII flow diagram
trajectory gen --audit         # full provenance details
trajectory transcript          # full conversation to stdout
trajectory transcript --copy   # copy transcript to clipboard
trajectory gen -s 17c072d8     # use specific session
trajectory list                # show available sessions
```

## Flow Diagram

```bash
trajectory gen --flow
```

```
╔══ feat/add-user-auth ══╗

  ┌─ INTENT ────────────────────────────┐
  │ Add JWT auth to the API             │
  └─────────────────────────────────────┘
                    │
                    ▼
  ┌─ DIRECTIVE ─────────────────────────┐
  │ Use RS256 for token signing         │
  └─────────────────────────────────────┘
                    │
                    ▼
  ┌─ IMPLEMENT ─────────────────────────┐
  │ Add refresh token rotation          │
  └─────────────────────────────────────┘
                    │
                    ▼
  ┌─ OUTPUT ────────────────────────────┐
  │ jwt.ts (new)                        │
  │ auth.ts (3 edits)                   │
  └─────────────────────────────────────┘

  ╳─ REJECTED ──────────────────────────╳
  ╳ Session-based auth with Redis       ╳
  ╳─────────────────────────────────────╳

╚══ Session: a1b2c3d4 ══╝
```

## Full Transcript

```bash
trajectory transcript
```

```markdown
# Session: a1b2c3d4

**Project:** `/path/to/project`
**Branch:** `feat/add-user-auth`
**Started:** 2026-01-12 10:30

---

## User

Add JWT authentication to the API

---

## Assistant

I'll help you implement JWT authentication...

`[Read]` src/auth.ts
`[Edit]` src/auth.ts
`[Bash]` `npm install jsonwebtoken`

---

## User

Use RS256 instead of HS256

---
...
```

No API key needed — just formats your local session logs.

## Full Provenance (--audit)

```markdown
**Decisions:**
- Use RS256 for token signing
  Better security for production environments
  `[chosen]` _Selected from: RS256 / HS256 / ES256_

**Rejected:**
- Session-based auth with Redis
  _More infrastructure overhead_

**Assumptions:**
- API consumed by first-party clients only `[inferred]`

**Deferred:**
- Rate limiting _Explicitly marked for v2_
```

| Label | Meaning |
|-------|---------|
| `[explicit]` | User directly stated |
| `[chosen]` | User selected from options |
| `[inferred]` | Deduced from context |

## How It Works

1. Claude Code saves session logs to `~/.claude/projects/`
2. Trajectory reads the JSONL (conversation, tool calls, file edits)
3. For `gen`: Uses Claude API to extract structured decisions
4. For `transcript`: Formats raw conversation (no API needed)

## Requirements

- Python 3.9+
- Claude Code
- `ANTHROPIC_API_KEY` (for `gen` command only)

## License

MIT
