# Project plan

Durable backlog. Append items when the user confirms; tick on session-handoff.

- [x] Django bootstrap with `conf/`, `request`, `.env`, pytest (completed 2026-09-25)
- [x] Agent CLI: `model_sync`, `model_list`, `model_show`, `llm_ask` (`--json` on list/show) (completed 2026-09-25)
- [x] Hybrid OpenAI catalog: `request/catalog/openai_models.json` + `models.list` (completed 2026-09-25)
- [x] Single-turn OpenAI completion via `request/services.py` (`complete_single_turn`) (completed 2026-09-25)
- [x] `model_add`: LiteLLM price lookup → `openai_models.json` → sync (completed 2026-09-25)
- [ ] ChatGPT **subscription** inference (next session): Plus/Go is **not** Platform API credit. Official path used by Codex CLI, OpenClaw, and Pi is **ChatGPT/Codex OAuth** (`codex login` / `openclaw models auth login --provider openai`), billed against the ChatGPT plan quota, not `OPENAI_API_KEY`. Keep the API key as fallback. Investigate wiring `llm_ask` to that OAuth/Codex route (or wrapping Codex) vs staying on `api.openai.com`. Do **not** scrape chatgpt.com as a fake API.
- [ ] Optional: Django REST framework on `request` (only if HTTP clients need it)
- [ ] v2: agent tool loops (`agent_run`), multi-turn storage
