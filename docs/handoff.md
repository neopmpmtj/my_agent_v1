> **Last updated:** 2026-09-25 08:42 WEST (Europe/Lisbon)
> Replace with the current date and time whenever you edit this file.

# Session handoff

## Done

- Django 5 scaffold: `conf/` settings (decouple + `.env`), `request` app, pytest + pytest-django, `.cursor/` rules/skills/commands.
- Agent CLI pattern: management commands → `request/services.py` → models. `--json` on list/show/writes that need machine output.
- Hybrid catalog: curated [`request/catalog/openai_models.json`](../request/catalog/openai_models.json) is the **active stack** (prices, `endpoint_kind`). `model_sync` merges OpenAI `models.list` into `LLMModel`; extra API ids are **inactive**.
- Stateless `llm_ask`: one prompt in, one reply out; `--model` among active rows.
- `model_add --model <id>`: LiteLLM public price table → write JSON → `model_sync`. Optional `--input-cost-per-1m` / `--output-cost-per-1m` / `--endpoint-kind` / `--default`.

## Decisions

- No official OpenAI prices API; `model_sync` still needs `OPENAI_API_KEY` for `models.list`.
- JSON (not YAML) lives inside the `request` app so the unit stays portable.
- `llm_ask` does not store Q&A. DRF is optional later.

## Not done

- Multi-turn / tool loops (`agent_run`); persisting conversations; DRF HTTP API.

## Next

- Browse inventory (`model_list --all`), `model_add` the ids you want, then `llm_ask --model <id>`.
- Next feature: ChatGPT subscription OAuth for inference (see `docs/project-plan.md`).

## Commands

```bash
source .venv/bin/activate
.venv/bin/python manage.py migrate
.venv/bin/python manage.py model_sync --json
.venv/bin/python manage.py model_list --all --json
.venv/bin/python manage.py model_add --model gpt-5-mini --json
.venv/bin/python manage.py llm_ask --prompt "why is the sky blue?" --json
pytest
```
