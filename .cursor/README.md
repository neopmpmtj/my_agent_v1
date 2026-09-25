# Cursor project configuration

Project-level Cursor settings live here. User-global config remains in `~/.cursor/`.

| Path | Purpose |
|------|---------|
| [`rules/`](rules/) | Persistent AI rules (`.mdc` files with YAML frontmatter) |
| [`skills/`](skills/) | Project Agent Skills (`skill-name/SKILL.md`) |
| [`agents/`](agents/) | Custom subagent definitions (`.md` files) |
| [`commands/`](commands/) | Slash commands (`.md` files) |
| [`hooks/`](hooks/) | Hook scripts referenced by `hooks.json` |
| [`hooks.json`](hooks.json) | Hook event configuration |
| [`cli.json`](cli.json) | Optional CLI overrides for this project |
| [`plans/`](plans/) | Saved agent plans (do not edit unless the user asks) |

## Quick start

- **Rule**: add `rules/my-rule.mdc` — see [Cursor rules docs](https://cursor.com/docs/context/rules)
- **Skill**: add `skills/my-skill/SKILL.md`
- **Agent**: add `agents/my-agent.md`
- **Command**: add `commands/my-command.md`
- **Hook**: add a script under `hooks/` and register it in `hooks.json`

Starter rules: [`rules/core.mdc`](rules/core.mdc) and [`rules/django-python.mdc`](rules/django-python.mdc).

[`AGENTS.md`](../AGENTS.md) at the project root provides agent instructions.

Commit this folder to share conventions with the team.
