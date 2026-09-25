# my_agent_v1 — Agent instructions

Django 5 chatbot scaffold. Settings in `conf/`. Domain logic lives in **`request/services.py`**. Agents and humans run the same **management commands**; add HTTP (DRF) only when something needs a network API.

**Read [`docs/handoff.md`](docs/handoff.md) first** — session snapshot (done / not done / next).  
**Read [`docs/project-plan.md`](docs/project-plan.md)** — durable backlog.

## Architecture

```text
Human / agent  →  management commands  →  request/services.py  →  models.py
views / API (optional)  ────────────────────────────────┘
```

- Business logic in `services.py`, not views, API handlers, or CLI
- Prefer new capabilities as commands first (`<entity>_<action>`, `--json` on list/show)
- Minimize scope — focused diffs; match existing patterns

## Agent CLI

Run from repo root with `.venv/bin/python manage.py …`. Document new commands below.

| Command | Purpose |
|---------|---------|
| *(none yet)* | Add rows as you implement services |

Conventions: `thing_list --json`, `thing_show <id> --json`; writes use explicit flags; errors on stderr, exit code non-zero on failure.

## Do

- Read `docs/handoff.md` and `docs/project-plan.md` before large changes
- When you notice new plans not in the backlog, ask: "Should I add this to `docs/project-plan.md`?"
- Use `.venv/bin/python` for `manage.py` and tests (or activate the venv first)
- Put secrets in root `.env` only; use `.env.example` as the committed template
- End substantive sessions with `/session-handoff` or skill `session-handoff`

## Do not

- Commit `.env`, API keys, or `db.sqlite3`
- Over-engineer before phase 2
- Edit `.cursor/plans/` unless the user asks
- Use emoji in logs or prints

## Commands

```bash
source .venv/bin/activate
cp .env.example .env   # if .env missing
.venv/bin/python manage.py migrate
.venv/bin/python manage.py runserver
pytest
```

## Cursor project config

| Path | Use |
|------|-----|
| [`.cursor/rules/`](.cursor/rules/) | Project rules (`.mdc`) |
| [`.cursor/skills/`](.cursor/skills/) | Project skills (`session-handoff`) |
| [`.cursor/agents/`](.cursor/agents/) | Custom subagents |
| [`.cursor/commands/`](.cursor/commands/) | Slash commands |
| [`.cursor/hooks/`](.cursor/hooks/) | Hook scripts + `hooks.json` |

## Session

**Done:** (initial bootstrap — update on session-handoff)

**Not done:** Management commands, OpenAI integration, conversation models; optional DRF later.

**Next:** `request/services.py` + commands (e.g. `thing_list --json`); OpenAI when ready.
