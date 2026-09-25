# my_agent_v1 — Agent instructions

Django 5. Settings in `conf/`. Domain logic lives in **`request/services.py`**. Agents and humans run the same **management commands**.

**Read [`docs/handoff.md`](docs/handoff.md) first** — session snapshot (done / not done / next).  
**Read [`docs/project-plan.md`](docs/project-plan.md)** — durable backlog.  
**Read [`request/README.md`](request/README.md)** — catalog + CLI for the standalone `request` app.

## Architecture

```text
Human / agent  →  management commands  →  request/services.py  →  models.py
views / API (optional)  ────────────────────────────────┘
```

- Business logic in `services.py`, not views, API handlers, or CLI
- Prefer new capabilities as commands first (`<entity>_<action>`, `--json` on list/show)
- Minimize scope — focused diffs; match existing patterns

## Agent CLI

Run from repo root with `.venv/bin/python manage.py …`.

| Command | Purpose |
|---------|---------|
| `model_sync` | Merge [`request/catalog/openai_models.json`](request/catalog/openai_models.json) with OpenAI `models.list` into the DB. Manual only (not on every ask). |
| `model_list` | List catalogued models. `--json` includes `endpoint_kinds_in_catalog`. Use `--all` to see inactive API ids. |
| `model_show --model <id>` | One model row plus CLI defaults. |
| `model_add --model <id>` | Look up prices (LiteLLM JSON), write the curated file, then `model_sync` so the model is active for `llm_ask`. Optional `--input-cost-per-1m` / `--output-cost-per-1m` / `--endpoint-kind` / `--default`. |
| `model_remove --model <id>` | Remove from `openai_models.json`, deactivate for `llm_ask`, then `model_sync`. Cannot remove the only curated model; removing default promotes the next row. |
| `auth_login --provider openai` | Browser PKCE ChatGPT/Codex OAuth. Tokens in gitignored `.auth/openai.json`. Other providers fail until implemented. |
| `auth_status --provider openai` | Logged in / expired / plan. Never prints tokens. |
| `llm_ask --prompt "..."` | Stateless single turn: one prompt in, one reply out. `--model`, `--max-output-tokens`, `--temperature`, `--system`, `--auth auto\|oauth\|api_key`. |

Conventions: list/show support `--json`; writes use explicit flags; errors on stderr (or `{ok: false, error}` with `--json`); non-zero exit on failure.

Pricing comes from LiteLLM’s public table (not an official OpenAI prices API). `model_add` writes JSON then syncs. Override with `--input-cost-per-1m` / `--output-cost-per-1m` if lookup misses.

Examples:

```bash
.venv/bin/python manage.py model_sync --json
.venv/bin/python manage.py model_list --all --json
.venv/bin/python manage.py model_add --model gpt-5-mini --json
.venv/bin/python manage.py auth_login --provider openai --json
.venv/bin/python manage.py llm_ask --prompt "why is the sky blue?" --model gpt-5.6-terra --json
```

## Do

- Read `docs/handoff.md` and `docs/project-plan.md` before large changes
- When you notice new plans not in the backlog, ask: "Should I add this to `docs/project-plan.md`?"
- Use `.venv/bin/python` for `manage.py` and tests (or activate the venv first)
- Put secrets in root `.env` only; OAuth tokens in gitignored `.auth/`; use `.env.example` as the committed template
- End substantive sessions with `/session-handoff` or skill `session-handoff`

## Do not

- Commit `.env`, `.auth/`, API keys, or `db.sqlite3`
- Store conversation history in v1 (`llm_ask` is stateless)
- Edit `.cursor/plans/` unless the user asks
- Use emoji in logs or prints

## Commands

```bash
source .venv/bin/activate
cp .env.example .env   # if .env missing
.venv/bin/python manage.py migrate
.venv/bin/python manage.py model_sync --json
.venv/bin/python manage.py auth_login --provider openai --json
.venv/bin/python manage.py llm_ask --prompt "why is the sky blue?" --json
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

**Done:** Django scaffold; LLM catalog; `model_add` / `model_remove`; stateless `llm_ask`; ChatGPT/Codex OAuth.

**Not done:** Anthropic; multi-turn / tool loops; DRF; persisting Q&A.

**Next:** `auth_login` or API-key `llm_ask`; use `model_remove` to demote models from the stack.
