# Project plan

Durable backlog. Append items when the user confirms; tick on session-handoff.

- [x] Django bootstrap with `conf/`, `request`, `.env`, pytest (completed 2026-09-25)
- [x] Agent CLI: `model_sync`, `model_list`, `model_show`, `llm_ask` (`--json` on list/show) (completed 2026-09-25)
- [x] Hybrid OpenAI catalog: `request/catalog/openai_models.json` + `models.list` (completed 2026-09-25)
- [x] Single-turn OpenAI completion via `request/services.py` (`complete_single_turn`) (completed 2026-09-25)
- [x] `model_add`: LiteLLM price lookup → `openai_models.json` → sync (completed 2026-09-25)
- [x] ChatGPT **subscription** inference: `auth_login` / `auth_status` (`--provider openai`), tokens in `.auth/openai.json`, `llm_ask --auth auto|oauth|api_key` via Codex Responses backend with API key fallback (completed 2026-09-25)
- [ ] Anthropic (later): Claude API key plus optional Claude CLI / subscription auth. Same `--provider` shape as OpenAI OAuth; do not implement until this item is started.
- [ ] Optional: Django REST framework on `request` (only if HTTP clients need it)
- [ ] v2: agent tool loops (`agent_run`), multi-turn storage
