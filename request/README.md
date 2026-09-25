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

## Commands

```bash
python manage.py model_sync --json
python manage.py model_list --json
python manage.py model_list --all --json
python manage.py model_show --model gpt-4o-mini --json
python manage.py model_add --model gpt-5-mini --json
python manage.py llm_ask --prompt "why is the sky blue?" --model gpt-4o-mini --json
```
