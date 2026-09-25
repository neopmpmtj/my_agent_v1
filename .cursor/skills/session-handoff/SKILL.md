---
name: session-handoff
description: >-
  End-of-session documentation sync. Updates docs/handoff.md, docs/project-plan.md
  status, and AGENTS.md session block. Use when the user says session handoff,
  wrap up, end session, update living docs, or before stopping work.
disable-model-invocation: true
---

# Session handoff

Sync **living documents** at end of session so the next chat can start from `docs/handoff.md` and `docs/project-plan.md` without re-briefing.

| Living file | Rhythm |
|-------------|--------|
| `docs/handoff.md` | Session snapshot — refresh fully each handoff |
| `docs/project-plan.md` | Long-running backlog — append on request; tick status each handoff |

## When to run

- User says: "session handoff", "wrap up", "update living docs", "we're done for today"
- Before ending a coding session with meaningful changes

## Do not

- Commit or push unless explicitly requested
- Invent work that was not done — derive "landed" from conversation + `git diff`
- Edit `.cursor/plans/` unless the user asked
- Add items to `docs/project-plan.md` unless the user asked or confirmed during the session

## Workflow

### 1. Gather session facts

- Scan conversation for completed work, decisions, and explicit "next" task
- Run `git status` and `git diff` (or review unstaged changes)
- Run tests if the project has them: `pytest` or `.venv/bin/python manage.py test`

### 2. Update living documents

**Timestamp format** (required at top of `docs/handoff.md`):

```markdown
> **Last updated:** YYYY-MM-DD HH:MM TZ (Europe/Lisbon)
> Replace with the current date and time whenever you edit this file.
```

| File | Update |
|------|--------|
| `docs/handoff.md` | **Primary.** Refresh the **Last updated** block. **Done**, **Not done**, **Next** sections. Commands block if changed. |
| `docs/project-plan.md` | Mark completed items (`[x]`), keep pending visible (`[ ]`). Append new items only when the user asked or confirmed during the session. |
| `AGENTS.md` | Session block: **Done**, **Not done**, **Next** (concise bullets). |

### 3. Reply to user

Short summary:

1. **Landed** — 3–6 bullets
2. **Next session** — one line
3. **Docs touched** — file list
4. **Tests** — count or "not run"
