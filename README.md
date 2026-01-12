# trajectory

Capture the *why* behind AI-generated code.

When you use Claude Code to write code, trajectory generates a decision log — what was decided, what was rejected, what was assumed. Attach it to your PR so reviewers see the reasoning, not just the diff.

## Install

```bash
pip install trajectory
```

Requires `ANTHROPIC_API_KEY` environment variable.

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
trajectory gen                 # generate trajectory.md
trajectory gen --copy          # generate + copy to clipboard
trajectory gen --flow          # ASCII flow diagram
trajectory gen --audit         # full provenance details
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
3. Uses Claude API to extract structured decisions
4. Generates clean markdown for your PR

## Requirements

- Python 3.9+
- Claude Code
- `ANTHROPIC_API_KEY`

## License

MIT
