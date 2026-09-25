> **Last updated:** 2026-09-25 09:24 WEST (Europe/Lisbon)
> Replace with the current date and time whenever you edit this file.

# Session handoff

## Done

- Django 5 scaffold: `conf/` settings (decouple + `.env`), `request` app, pytest + pytest-django, `.cursor/` rules/skills/commands.
- Agent CLI pattern: management commands → `request/services.py` → models. `--json` on list/show/writes that need machine output.
- Hybrid catalog: curated [`request/catalog/openai_models.json`](../request/catalog/openai_models.json) is the **active stack** (prices, `endpoint_kind`). `model_sync` merges OpenAI `models.list` into `LLMModel`; extra API ids are **inactive**.
- Stateless `llm_ask`: one prompt in, one reply out; `--model` among active rows; `--auth auto|oauth|api_key`.
- `model_add --model <id>`: LiteLLM public price table → write JSON → `model_sync`. Optional `--input-cost-per-1m` / `--output-cost-per-1m` / `--endpoint-kind` / `--default`.
- ChatGPT/Codex OAuth: `auth_login --provider openai` (PKCE, port 8765), `auth_status`. Tokens in gitignored `.auth/openai.json` with auto-refresh. `gpt-5.6-terra` has `supports_codex_oauth`. No `auth_logout` (Pi-style stay signed in).

## Decisions

- No official OpenAI prices API; `model_sync` still needs `OPENAI_API_KEY` for `models.list`.
- JSON (not YAML) lives inside the `request` app so the unit stays portable.
- `llm_ask` does not store Q&A. DRF is optional later.
- ChatGPT Plus/Go uses Codex OAuth + `chatgpt.com/backend-api/codex/responses`, not `api.openai.com`. Unofficial for third-party clients; API key remains fallback. Own token file (not `~/.codex/auth.json`). `--provider` is openai-only for now so Anthropic can slot in later.
- Auth commands take `--provider` (default openai). Other providers error with “not implemented”.

## Not done

- Anthropic (`--provider anthropic`); multi-turn / tool loops (`agent_run`); persisting conversations; DRF HTTP API; device-code login; `auth_logout`.

## Next

- Run `auth_login --provider openai`, then `llm_ask --model gpt-5.6-terra --json`.
- Later: Anthropic (see `docs/project-plan.md`).

## Commands

```bash
source .venv/bin/activate
.venv/bin/python manage.py migrate
.venv/bin/python manage.py model_sync --json
.venv/bin/python manage.py auth_login --provider openai --json
.venv/bin/python manage.py auth_status --provider openai --json
.venv/bin/python manage.py llm_ask --prompt "why is the sky blue?" --model gpt-5.6-terra --json
.venv/bin/python manage.py llm_ask --prompt "why is the sky blue?" --auth api_key --json
pytest
```
