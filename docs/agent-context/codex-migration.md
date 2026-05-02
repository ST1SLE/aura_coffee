# Codex Migration Notes

Date: 2026-04-29

Aura Coffee is the pilot project for the Claude Code CLI to Codex CLI migration.

## Current State

- Root and module-level `AGENTS.md` files already existed before the migration and remain the primary project instructions.
- `CLAUDE.md` remains as a Claude-specific onboarding file. Codex should prefer `AGENTS.md`.
- `.claude/settings.local.json` remains local Claude state and is not migrated into tracked Codex files.
- The legacy `grace:*` workflow names in root `AGENTS.md` are now covered for Codex by the repo-scoped `aura-grace` skill.

## Codex Files Added

- `.codex/config.toml`: repo-safe Codex defaults only.
- `.agents/skills/aura-grace/SKILL.md`: Codex-native GRACE workflow instructions for planning, implementation, verification, refactor, refresh, debugging, review, and architecture Q&A.
- `docs/agent-context/codex-migration.md`: this migration note.

## Global Codex Dependencies

The user-level migration installed these global skills under `/home/p3tal/.agents/skills`:

- `plan-task`
- `review-changes`
- `run-tests`
- `explain-codebase`
- `update-kb`

Aura Coffee also relies on the global `/home/p3tal/.codex/AGENTS.md` working defaults.

## Deferred

- Do not migrate `.claude/settings.local.json` permission entries verbatim. Codex approval and sandboxing are handled by Codex config.
- Do not import Claude task history, todos, or file-history into this repo.
- Review the original Grace marketplace/plugin separately if a packaged Codex plugin is needed later.
- Recreate notification/snapshot hooks only if they are still useful under Codex.
