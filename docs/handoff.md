> **Last updated:** 2026-09-25 17:35 WEST (Europe/Lisbon)
> Replace with the current date and time whenever you edit this file.

# Session handoff

## Done

- Django 5 scaffold: `conf/` settings (decouple + `.env`), `request` app, pytest + pytest-django, `.cursor/` rules/skills/commands.
- Agent CLI pattern: management commands → `request/services.py` → models. `--json` on list/show/writes that need machine output.
- Hybrid catalog: curated [`request/catalog/openai_models.json`](../request/catalog/openai_models.json) is the **active stack** (prices, `endpoint_kind`). `model_sync` merges OpenAI `models.list` into `LLMModel`; extra API ids are **inactive**.
- Stateless `llm_ask`: one prompt in, one reply out; `--model` among active rows; `--auth auto|oauth|api_key`.
- `model_add` / **`model_remove`**: promote or demote models on the JSON stack, then `model_sync`. Remove refuses the only curated row; removing default promotes the next entry.
- ChatGPT/Codex OAuth: `auth_login` / `auth_status` (`--provider openai`), `.auth/openai.json`, `supports_codex_oauth` on `gpt-5.6-terra`.

## Decisions

- No official OpenAI prices API; `model_sync` still needs `OPENAI_API_KEY` for `models.list`.
- JSON catalog lives inside `request` for portability.
- `llm_ask` does not store Q&A. DRF optional later.
- ChatGPT subscription via Codex backend; API key fallback. Auth `--provider` openai-only until Anthropic.
- No `auth_logout` in v1 (delete `.auth/openai.json` to drop OAuth).

## Not done

- Anthropic; multi-turn / `agent_run`; DRF; persisting conversations; device-code login; `auth_logout`.

## Next

- `auth_login --provider openai` then `llm_ask --model gpt-5.6-terra --json`, or API-key `llm_ask` on `gpt-4o-mini`.
- Trim stack with `model_remove --model <id> --json` when experimenting.

## Commands

```bash
source .venv/bin/activate
.venv/bin/python manage.py migrate
.venv/bin/python manage.py model_sync --json
.venv/bin/python manage.py model_add --model gpt-5-mini --json
.venv/bin/python manage.py model_remove --model gpt-5-mini --json
.venv/bin/python manage.py auth_login --provider openai --json
.venv/bin/python manage.py llm_ask --prompt "why is the sky blue?" --model gpt-4o-mini --json
pytest
```
