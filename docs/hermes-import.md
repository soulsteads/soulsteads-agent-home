# Import a Hermes agent

Import an explicitly selected local Hermes profile into a **new, private**
Soulsteads agent home. Inspection is read-only by default. Applying an import
creates files and local Git history; it does not run the agent, install a service,
authenticate a provider, or move a messaging connection.

Inspection uses POSIX file-safety checks. **Applying imports currently requires
Linux with `renameat2`** for atomic no-overwrite publication; unsupported platforms
refuse rather than fall back to a replacement rename.

Use the source owner's account and an authorized source directory. Do not import
somebody else's profile merely because you can read it. All examples below are
generic placeholders. Never copy a real profile into this public source checkout.

## Install the optional importer

Ordinary Soulsteads commands need only Python's standard library. Hermes uses
YAML, so direct import also needs the maintained PyYAML parser:

```sh
uv tool install 'soulsteads[hermes] @ git+https://github.com/soulsteads/soulsteads-agent-home.git'
# From this source checkout instead:
uv tool install '.[hermes]'
```

Use an isolated tool environment, not a system-wide Python installation. The
importer reports an actionable error if its optional dependency is missing;
other commands do not require it. Do not substitute a hand-written YAML parser.

## Inspect first

Choose the destination name, a supported target runtime, and the source Hermes
home. `--source` is the **parent Hermes home**, not its `profiles/<name>` directory:

```sh
soulsteads import-hermes helper \
  --source "$HOME/.hermes" --profile helper \
  --runtime opencode --path "$HOME/agents/helper"
```

`--profile default` selects the source directory itself. A named profile selects
`SOURCE/profiles/PROFILE`. The command does not use Hermes's active-profile
selection or inherit a different profile silently. Source identifiers are matched
exactly, including supported underscores; the new Home name remains a lowercase
hyphenated slug. To import a separately located
Hermes home, pass that directory as `--source` and select `--profile default`.

Review the JSON report locally. It describes selected files/skills, omissions,
blockers, and required manual work without printing file contents, secret values,
or memory bodies. Absolute source/destination paths remain in the ignored private
receipt, not in the public JSON report. Agent and skill names can still be sensitive
metadata; redact reports before sharing them.

The importer reads only the explicitly selected source and any explicitly supplied
workspace. It does not execute Hermes, plugins, skill scripts, or instructions
found in those files. It does not copy a workspace, Vault, session database,
conversation history, or scheduler state recursively.

### Workspace instructions

If identity instructions live in a workspace rather than the profile, explicitly
supply that workspace:

```sh
soulsteads import-hermes helper \
  --source "$HOME/.hermes" --profile helper --runtime claude \
  --workspace /path/to/authorized-workspace --path "$HOME/agents/helper"
```

Profile-root files take precedence over workspace fallbacks; `memories/USER.md`
and `memories/MEMORY.md` take precedence for those two documents. Missing documents
retain generic Home templates. Imported `AGENTS.md` is prefixed with the Home
identity-file reading instruction; its exact original bytes are also preserved
privately in `.runtime/hermes/AGENTS.md`. Other imported core documents keep their
original bytes.

The importer does not follow `terminal.cwd` automatically. A configured path is
not permission to inspect an unrelated workspace. Only supported root identity
files are considered from an explicit workspace, not its projects or Vaults.

### Skill selection

Selection uses the local profile skill catalogue and the requested source
platform's filters. Use `--platform matrix` or `--platform mattermost` when
importing that surface instead of the default `cli` selection.

- Global `skills.disabled` and the selected `skills.platform_disabled` are combined.
- Hermes's essential `hermes-agent` exception remains eligible.
- Selected skills are converted to standard [Agent Skills](https://agentskills.io/specification)
  frontmatter. Names must be lowercase hyphenated identifiers of at most 64
  characters; descriptions must be nonempty and at most 1024 characters. Hermes
  discovery fields are consumed for selection, then removed from the output.
  Supported license, compatibility, and string-valued metadata are retained;
  Hermes-specific metadata is removed.
- Disabled nested skills must not reappear as assets of an enabled parent.
- Unsupported discovery tiers, including external or conditional sources, are
  reported rather than silently treated as a complete effective catalogue.
- Markdown bodies and supporting assets keep their original bytes; only SKILL.md
  frontmatter changes. The shared `.agents/skills` and `.claude/skills` aliases
  expose the converted catalogue to all four supported harnesses.
- Imported Home instructions explain native skill loading and native-tool
  equivalents for Hermes skill/file/terminal tool references. This is guidance,
  not a rewrite of arbitrary script or tool APIs.
- Skill scripts are copied as files only; no script or installation hook runs.

This is file-format compatibility, not proof that a skill works in the selected
runtime. Instructions can refer to Hermes-only tools and policies. Review them
before running the imported agent. Runtime-global skills can still be discovered;
a local catalogue is not a cross-runtime authorization sandbox.

## Hindsight integration: pending setup choice

The importer detects `memory.provider: hindsight` and profile-local
`hindsight/config.json`. It preserves that JSON unchanged under ignored private
`.runtime/hermes/hindsight/config.json`, where keys and endpoint/bank details do
not enter Git or public reports. Malformed JSON and duplicate keys are refused;
source changes and optional-file appearance remain part of snapshot verification.
The importer does not inspect shared `~/.hindsight` state or the ambient process
environment.

**Automatic native Hindsight setup is not implemented in this candidate.** The
report identifies it as required manual work rather than claiming memory is ready.
`--allow-partial` acknowledges this omission; it does not install or enable hooks.

The maintained [Hindsight coding-agents integration](https://github.com/vectorize-io/hindsight/tree/main/hindsight-integrations/coding-agents)
supports the target harnesses, but adds a JavaScript dependency and hooks that can
retain conversations and inject memory. Its general installer also changes
user-global harness settings. A scoped importer integration must preserve the
source profile's supported memory behavior without running that global installer
or enabling additional ingestion. Bank access alone through MCP is a narrower
alternative; it does not preserve automatic memory behavior. That choice remains
an owner decision before implementation. No Hindsight server or memory bank is
contacted or modified during import.

## Apply only after review

Repeat the inspected command with `--apply` to create the destination. Existing
destinations are refused; imports never merge into another Home or overwrite it.
Use a new path for another attempt and preserve earlier candidates for review.

```sh
soulsteads import-hermes helper \
  --source "$HOME/.hermes" --profile helper \
  --runtime opencode --path "$HOME/agents/helper" --apply
```

Hermes-specific settings do not necessarily have equivalent meanings in OpenCode,
pi, Claude Code, or Codex. When the report requires manual configuration, review
it and add `--allow-partial` only if you accept the listed omissions:

```sh
soulsteads import-hermes helper \
  --source "$HOME/.hermes" --profile helper \
  --runtime opencode --path "$HOME/agents/helper" --allow-partial --apply
```

Acknowledging an incomplete import does not bypass malformed YAML, unsafe file
checks, duplicate skill IDs, or destination protections. The importer does not
translate unknown permissions into permissive runtime defaults. Generated runtime
configuration follows the existing [adapter contract](runtimes.md), without
changing global model, authentication, MCP, trust, or tool-permission settings.

### Credentials and private reference material

The source `config.yaml` is preserved for manual review under the new Home's
ignored `.runtime/hermes/` directory. It can contain credentials and must remain
private. The import report/receipt belongs there too, not in tracked agent files.

By default, the importer does not copy `.env`. If explicitly authorized, add
`--include-secrets` to copy only the selected profile's `.env` into private,
ignored `.runtime/hermes/.env`. That reference copy is **not automatically loaded**
by the launcher. Configure supported native credentials separately; never paste
real values into chat or commit them to Git.

OAuth `auth.json`, refresh tokens, runtime credential pools, and ambient gateway
environment variables are not transferred. Do not copy a live refresh token into
a second application that may refresh it concurrently.

The imported Home has private directories/files, local Git history, and no added
remote. Identity, memory, and skills are normal Home files and may be locally
tracked. This tool is **not a secret scanner**: secrets embedded in Markdown or
skill content can therefore enter local history. Inspect the source and report
before applying, and never publish an imported Home without a separate privacy
review. Ignoring a file does not encrypt it.

## Verify before running or connecting Messaging

1. Inspect the imported Home and private receipt; account for every omission.
2. Check which identity, instructions, memory, and skills the target runtime
   actually loads. Importing files does not establish semantic compatibility.
3. Configure and verify model/provider access, MCP, memory services, permissions,
   and approvals through supported target-runtime mechanisms.
4. Use `soulsteads config /path/to/new-home` and
   `soulsteads run /path/to/new-home --dry-run` to inspect the selected runtime
   without launching it. These are local structural checks, not generation tests.
5. Launch only when authorized. A separate Messaging setup must reconcile allowed
   users/rooms/channels and preserve one live owner for each platform identity.

The importer never stops Hermes or starts a competing connector. Cron jobs,
remote-memory banks, bridge state, and conversation history retain their existing
owners. Importing an agent definition does not make its old conversations native
sessions in another harness. Retain the original profile and existing consumers
as rollback until a separately authorized handoff is verified.

## Safety and verification limits

Unsafe YAML, links, special files, ambiguous selections, excessive input, and
existing destinations are refused. Errors are sanitized rather than echoing
source configuration. Do not disable these checks to import an unreviewed tree.

Automated tests use disposable synthetic profiles. They exercise inspection,
application, source preservation, selection, private storage, local Git, and
failure boundaries. They do not establish live Hermes-to-Messaging migration,
provider authentication, or runtime behavior with private agents.

Hermes references:
[profiles](https://hermes-agent.nousresearch.com/docs/user-guide/profiles),
[skills](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills),
and [configuration](https://hermes-agent.nousresearch.com/docs/user-guide/configuration).
