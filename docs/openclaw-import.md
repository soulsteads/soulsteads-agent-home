# Import an OpenClaw workspace

Copy portable files from one explicitly chosen local OpenClaw workspace into a **new private** Agent Home. If OpenClaw has multiple agents, identify the intended agent's workspace yourself first. Home does not read `openclaw.json`, resolve an agent ID, or follow configured paths. See [OpenClaw's workspace guide](https://docs.openclaw.ai/concepts/agent-workspace).

```sh
soulsteads import-openclaw helper \
  --workspace /path/to/authorized-workspace \
  --runtime opencode --path "$HOME/agents/helper"
```

Inspection is the default. It reports selected files and skills, fixed categories left behind, and no activation claim. It does not print document bodies or source paths. Names can still be private metadata. Review the actual source content before applying: imported documents and skills will be tracked in the **new Home's local Git history**, and the importer cannot tell whether a document contains a secret or source-specific instructions.

- `SOUL.md`, `AGENTS.md`, and `USER.md` are selected when present. The importer wraps `AGENTS.md` with Home instructions and preserves the original in the ignored private receipt directory.
- Add `--include-memory` to select the root `MEMORY.md`. It becomes a local Home document, not a Hindsight upload. `IDENTITY.md` and daily memory logs stay behind.
- Add `--skill example-skill`, repeating the flag for each skill you want from `skills/<name>/`. No skills are selected automatically. The directory and frontmatter names must match. Portable frontmatter is normalized; the Markdown body and supporting files are copied without being executed. OpenClaw-specific metadata, nested skills, hidden entries, credential paths, and links are refused rather than silently bypassed. Skill import uses the same optional PyYAML dependency as the Hermes importer: `python3 -m pip install 'soulsteads[hermes]'` in an isolated tool environment. A document-only import does not need it.
- Other skill roots, models, provider credentials, MCP servers, plugins, permissions, sessions, messaging bindings, schedules, and external memory stay with the source. This command does not verify feature parity or run either agent.

Repeat the inspected command with `--apply` to create the Home. Apply reads the source again, so keep the selected files unchanged between inspection and apply. Application needs Linux `renameat2`, refuses an existing destination, and never overwrites the source. Provenance is stored under `.runtime/openclaw/` (ignored by Git). Run `soulsteads verify /path/to/new-home` and review native instructions, skills, permissions, and authentication before starting a session. A live handoff is a separate operation.
