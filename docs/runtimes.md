# Runtime adapters

These adapters write **project-local** configuration only. They do not install a
runtime, authenticate it, select a model, configure MCP, grant trust, or loosen
permissions. Run `soulsteads run <agent> --dry-run` to see the exact command and CWD.
Global runtime configuration remains active; an agent home is not an OS sandbox.
Linux and macOS are the current targets; native Windows symlink behavior is not
qualified.

## Shared instructions and skills

`AGENTS.md` tells the runtime to read `SOUL.md`, `USER.md`, and `MEMORY.md` at the
start of a session. These are user-editable documents, not application settings.

`skills/` is canonical. The tool creates two fixed, relative directory symlinks:

- `.agents/skills -> ../skills` for OpenCode, pi, and Codex.
- `.claude/skills -> ../skills` for Claude Code (also recognized by OpenCode).

Both aliases stay inside the same home. Only these exact links are admitted;
third-party skill trees may not contain links. Editing a canonical skill changes
what each runtime reads without duplicated skill content. Runtime versions may
warn about duplicate discovery of the same skill; the content is identical.

## OpenCode

Creates root `opencode.json`, supported alongside `opencode.jsonc` and
`.opencode/opencode.json(c)`. Uses the documented `instructions` list to load
`SOUL.md`, `USER.md`, and `MEMORY.md` in addition to discovered `AGENTS.md`.
Starts `opencode` from the home root and passes requested arguments verbatim.
No model or permission keys are set.

Sources: [configuration](https://opencode.ai/v2/docs/config),
[instructions](https://opencode.ai/v2/docs/instructions),
[skills](https://opencode.ai/v2/docs/skills).
The same root JSON/instructions approach is documented in
[the earlier docs](https://opencode.ai/docs/config/).

## pi coding agent

Creates `.pi/settings.json` as an empty project customization point. pi discovers
root `AGENTS.md` and native `.agents/skills`. The launcher also passes `@SOUL.md`,
`@USER.md`, and `@MEMORY.md` as explicit initial context-file attachments. It does
**not** pass `--approve` or relocate `PI_CODING_AGENT_DIR`: existing global auth and
settings remain available, and the user still controls project trust. Check your
installed version with `pi --help`.

Sources: [configuration](https://github.com/badlogic/pi-mono/blob/main/packages/coding-agent/docs/configuration.md),
[CLI](https://github.com/badlogic/pi-mono/blob/main/packages/coding-agent/docs/cli.md),
[skills](https://github.com/badlogic/pi-mono/blob/main/packages/coding-agent/docs/skills.md).

## Claude Code

Creates empty `.claude/settings.json` and a root `CLAUDE.md` shim importing
`@AGENTS.md`, `@SOUL.md`, `@USER.md`, and `@MEMORY.md`. These are documented Claude
Markdown imports, not invented settings fields. Starts `claude` from the home
root. The managed native skills alias points at canonical `skills/`.

Sources: [memory and imports](https://code.claude.com/docs/en/memory),
[settings](https://code.claude.com/docs/en/settings),
[skills](https://code.claude.com/docs/en/skills).

## Codex CLI

Creates a comment-only `.codex/config.toml` project customization point. Codex
natively discovers root `AGENTS.md` and `.agents/skills`; project configuration
may require a trusted directory. Starts `codex` from the home root.

Codex does **not** automatically include all three arbitrary profile documents.
The generated `AGENTS.md` explicitly instructs it to read them. This is model-led
file reading, not a native include directive; no unsupported config key is used.
Permissions, sandbox policy, approval policy, `CODEX_HOME`, and global developer
instructions are left unchanged. The root `MEMORY.md` is also distinct from any
runtime-managed automatic memory.

Sources: [project instructions](https://developers.openai.com/codex/guides/agents-md),
[skills](https://developers.openai.com/codex/skills),
[configuration](https://developers.openai.com/codex/config-basic/).

## Verification limits

Unit and subprocess tests verify generated files, JSON/TOML syntax, aliases,
launcher argument boundaries, and complete local Git workflows. Actual installed
runtime help/version smoke checks are reported separately. These checks do not
prove that an LLM followed instructions, discovered every skill, or authenticated
successfully. No paid model calls or private-agent imports are part of the suite.
