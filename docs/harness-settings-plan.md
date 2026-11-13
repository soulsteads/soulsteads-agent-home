# Harness settings management implementation plan

Base: public `main` at `f8552ac747a140281bdfd4c0efd6c6ac74c03775`.
Branch: `feat/harness-settings-management`.

## Contract

Native configuration remains authoritative. Ordinary commands keep working with the standard library. A lazily imported `settings` extra may supply maintained format-preserving TOML editing. No global configuration writes, credential-store reads, automatic permission broadening, new services, or executable configuration evaluation. Preserve existing Home publication guards, unrelated keys, comments, untracked files, and Git history. Managed identity/Hindsight fields are not generic settings-editor targets.

## Implementation areas

1. Native settings engine: version-qualified catalog, strict JSON/JSONC/TOML parsing, format-preserving edits, origin/precedence inspection, redacted output, validated preview/apply/unset, portable profile import/export, stale-plan and filesystem safety.
2. CLI and documentation: discover, inspect, get, set/unset, preview/apply, export/import; common model/provider/reasoning aliases only when semantically valid; native JSON Pointer access for advanced settings. User/global and project layers are read-only. Explain observed configuration versus runtime-effective configuration.
3. Project launch: qualify Codex, Claude Code, OpenCode, and Pi identity/skill adapters using current upstream interfaces. Keep credentials and sessions native. Any Home-settings overlay must be explicit and version/capability checked; do not silently change existing Pi behavior.
4. Acceptance: parser and format round-trips, validation and secrets, precedence and unknown overrides, managed ownership, missing/unsafe files, symlink and stale-plan refusal, CLI lifecycle, isolated native resource/request construction, regression suite, independent security/spec review.

## Engine API shared with CLI

New module `soulsteads.settings` exposes JSON-serializable functions:

- `catalog(runtime, *, version=None)`
- `inspect_settings(home, runtime, *, project=None, user_dir=None, version=None)`
- `get_setting(home, runtime, key, *, project=None, user_dir=None, version=None)`
- `plan_changes(home, runtime, changes, *, version=None)`
- `apply_plan(home, plan)`
- `export_profile(home, runtime)`
- `plan_import(home, runtime, profile, *, version=None)`

Changes are a list of `{op: set|unset, path: JSON-Pointer-or-@alias, value: JSON-value}` (unset omits value). Generic edits are Home-local only. Plans are untrusted inputs and must be revalidated and reproduced before publication; they must not grant arbitrary paths or bypass managed fields. Diagnostics/diffs/exports never reveal credential literals. `HomeError` is the user-facing exception family. CLI and engine writers may coordinate additions, but must update this contract and tests together.

A catalog distinguishes known validated fields from unrecognized native fields; lack of schema coverage is not proof of unsupported native functionality. Inspection reports only resolutions justified by supplied layers and marks unknown CLI/environment/trust/policy effects explicitly.

## Ownership

- Engine writer: new settings engine/catalog/format modules, their new tests, and optional dependency metadata only.
- CLI writer: `soulsteads/cli.py`, new CLI tests, `docs/settings.md`, README settings documentation only.
- Project writer: `soulsteads/launch.py`, project-specific adapter modules, existing/new project tests, qualification scripts, `docs/native-acceptance.md` and project-launch sections of `docs/runtimes.md` only.
- Parent: integration, this plan, independent review, delivery and cleanup. No delegate commits, pushes, edits another writer's files, or creates another worktree.

## Evidence and disposable outputs

All disposable environments, package downloads, generated images and native qualification fixtures belong under an explicitly selected task-owned scratch directory. Preserve test/review evidence; remove inactive regenerable outputs after verification and reference checks. Preserve pre-existing untracked artifacts.

Environment failures must be distinguished from candidate regressions. Do not weaken storage guards, silently alter shared permissions, or claim blocked lifecycle tests passed.
