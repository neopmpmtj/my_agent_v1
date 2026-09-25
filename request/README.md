# request — standalone LLM catalog + single-turn CLI

Portable Django app: drop into another project (install the app, run migrations, set `OPENAI_API_KEY`).

## Two catalogs

- **DB** — every text model from OpenAI `models.list` (extras are inactive until added to the JSON).
- **JSON** — the active stack (`llm_ask` only uses these). Prices and `endpoint_kind` live here.

## Add a model (automated)

OpenAI has no official prices API. `model_add` fetches [LiteLLM `model_prices_and_context_window.json`](https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json), converts per-token costs to USD per 1M, writes [`catalog/openai_models.json`](catalog/openai_models.json), then runs `model_sync`.

```bash
python manage.py model_list --all --json
python manage.py model_add --model gpt-5-mini --json
python manage.py llm_ask --prompt "..." --model gpt-5-mini --json
```

If LiteLLM has no row, pass `--input-cost-per-1m` and `--output-cost-per-1m`. Optional: `--endpoint-kind`, `--default`.

`llm_ask` is stateless: one prompt in, one reply out.

## ChatGPT subscription (OAuth)

Plus/Go is not Platform API credit. `auth_login --provider openai` runs the Codex PKCE flow (same public client id as Codex CLI: `app_EMoamEEZ73f0CkXaXp7hrann`) and stores tokens in gitignored `.auth/openai.json`. `llm_ask --auth auto` uses that session for models marked `supports_codex_oauth` (currently `gpt-5.6-terra`) against `https://chatgpt.com/backend-api/codex/responses`. Other models keep using `OPENAI_API_KEY`. `--provider` is required later for Anthropic; v1 implements openai only.

This Codex backend is unofficial for third-party clients and can change. Do not scrape chatgpt.com as a website API. No `auth_logout` in v1 (delete `.auth/openai.json` to drop the session).

## Commands

```bash
python manage.py model_sync --json
python manage.py model_list --json
python manage.py model_list --all --json
python manage.py model_show --model gpt-4o-mini --json
python manage.py model_add --model gpt-5-mini --json
python manage.py model_remove --model gpt-5-mini --json
python manage.py auth_login --provider openai --json
python manage.py auth_status --provider openai --json
python manage.py llm_ask --prompt "why is the sky blue?" --model gpt-5.6-terra --json
python manage.py llm_ask --prompt "why is the sky blue?" --model gpt-4o-mini --auth api_key --json
```
