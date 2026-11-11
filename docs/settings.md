# Native harness settings

Agent Home manages **Home-local native configuration**, not a parallel settings
database. Codex, maintained Pi, Claude Code and OpenCode remain responsible for
loading configuration, authentication, permissions, sessions and model behavior.

Install the optional TOML editor from a source checkout to manage Codex settings:

```sh
python -m pip install '.[settings]'
```

Ordinary commands and the JSON-backed runtimes do not import that editor.

## Inspect and locate a setting

```sh
soulsteads settings catalog --runtime codex --version 0.157.1
soulsteads settings inspect --home /path/to/home --runtime codex
soulsteads settings get --home /path/to/home --runtime codex --key @model
soulsteads settings get --home /path/to/home --runtime codex --key /sandbox_mode
```

The catalog separates its own `catalog_revision` from a caller-supplied observed
harness version. Supplying `--version` does not run the harness or certify every
setting for that version. Known fields receive conservative shape checks;
advanced native fields are not a complete versioned schema validation.

Common aliases are deliberately limited:

- All four runtimes: `@model`.
- Codex: `@provider` maps to `model_provider`; `@reasoning` maps to
  `model_reasoning_effort`.
- Pi: `@provider` maps to `defaultProvider`; `@reasoning` maps to
  `defaultThinkingLevel`.
- Claude and OpenCode provider/reasoning mechanisms do not have a fabricated
  shared alias. Use their documented native fields.

Known Codex token-budget fields such as `model_auto_compact_token_limit` and
`tool_output_token_limit` are numeric settings, not credential fields. Their
documented shapes are checked without exempting arbitrary token-named values.

Advanced keys use nonempty JSON Pointer object paths, even for TOML:
`/model_providers/application/base_url`, `/hooks`, or `/permission/bash`.
Escape a literal `~` as `~0` and `/` as `~1`. Set arrays as complete values;
array-index editing and replacing the entire root are not supported.

### Native documents

- Codex: `.codex/config.toml`.
- Pi: `.pi/settings.json`; optional MCP-extension data in `.pi/mcp.json`.
- Claude: `.claude/settings.json`; project/Home MCP servers in `.mcp.json`.
- OpenCode: `opencode.json` or an existing `opencode.jsonc`. Ambiguous simultaneous
  JSON and JSONC files are refused rather than choosing an edit target silently.

`soulsteads commit` includes the supported OpenCode JSONC document in its narrow
Home-file allowlist. Managed projection refresh (`config --sync`) does not yet
support JSONC: it refuses before changing configuration rather than creating a
conflicting `opencode.json`. The settings editor still supports JSONC preview,
apply, import/export and unset. Switching back to managed refresh requires an
explicit conversion to one valid JSON document; no automatic format migration
is performed.

Pi MCP configuration requires a compatible separately installed extension. It is
not advertised as built-in Pi functionality.

JSONC edits retain comments and untouched text where possible. Codex edits use a
TOML-aware editor and retain Soulsteads' managed block. Ordinary JSON is rendered
as JSON. Duplicate keys, non-finite numbers, unsupported native value types and
unsafe or oversized files are refused instead of silently changing meaning.

### Read-only external layers

```sh
soulsteads settings inspect --home /path/to/home --runtime claude \
  --user-dir /path/to/native-user-home --project /path/to/project
```

`--user-dir` is the **native user's home directory**, not a settings-file path.
For example, Pi user settings are found at `.pi/agent/settings.json` beneath it;
OpenCode uses `.config/opencode/`. Claude project-local settings are also
reported. External documents are read-only and are not copied into the Home.
Project mode does not treat Home model/provider settings as an active layer.

The report includes files, static values, active scope and provenance. `source`
identifies a contributing layer; `sources` records multiple contributors for
combined values. This is a **static inspection, not a claim of runtime-effective
configuration**. Environment variables, CLI overrides, trust, remote settings,
enterprise policy, native discovery and harness-version differences can change
what the running harness uses. Credential stores are not part of this inventory.

## Preview, apply and unset

Changes preview by default. Review the native before/after documents and the
reported limitations before applying. Commit the current Home first if you need
a Git rollback point; settings changes do not create a commit automatically.

```sh
soulsteads settings set --home /path/to/home --runtime codex \
  --key @model --value '"example-model"' --plan-file model-plan.json
soulsteads settings apply --home /path/to/home --plan-file model-plan.json

soulsteads settings set --home /path/to/home --runtime pi \
  --key @reasoning --value '"high"' --apply
soulsteads settings unset --home /path/to/home --runtime pi --key @reasoning
```

`--value` is JSON, including the quotation marks around a string. Use `unset`
rather than JSON `null` to remove a TOML setting. `unset` also previews unless
`--apply` is supplied.

For an ordered batch, `settings plan --changes-file changes.json` reads a bounded
JSON file. Alternatively, `--changes` accepts an inline JSON array:

```json
[
  {"op": "set", "path": "@model", "value": "example-model"},
  {"op": "set", "path": "/sandbox_mode", "value": "read-only"}
]
```

Supply the same `--home` and `--runtime` options and optionally `--plan-file`.
Only `set` and `unset` operations are accepted. Unknown native fields remain the
operator's responsibility to validate against the installed harness.

Saved plans are JSON receipts bound to the Home, manifest and native source
snapshots. Applying revalidates those snapshots, rebuilds the proposed changes
and refuses stale or altered receipts. Plans and profiles are published as
private mode-0600 files without overwriting an existing output. Native documents
are limited to 1 MiB; plan/profile transfers are limited to 8 MiB.

Writes use the existing checked-directory, lock and publication helpers. A batch
that touches multiple native files is **not a cross-file atomic transaction**.
If publication is interrupted after one file, inspect the actual Home and make a
new plan; do not blindly replay a stale receipt.

## MCP, advanced fields and credential references

Unrelated native MCP connections, hooks, permissions, plugins, provider options
and other advanced values can be edited through native paths. For example,
Claude `/mcpServers/application` is routed to `.mcp.json`, not incorrectly placed
in `.claude/settings.json`. The manager does not execute commands or install MCP
extensions while editing.

Soulsteads-owned identity fields, canonical skill wiring and its Hindsight
connection are protected. Use the corresponding identity, skills or Hindsight
workflow to change them. Read access and write protection are separate: managed
configuration can still be inspected.

Never put a real credential in `--value`, a changes file, a profile or a plan.
The manager rejects recognized literal credentials and suspicious credential
arguments, redacts sensitive inspection values and never resolves references.
This is not a general-purpose secret scanner: do not assume arbitrary shell
commands or arbitrary strings are safe to export.

Native reference forms differ:

- OpenCode: `{env:APPLICATION_TOKEN}` and native file references where supported.
- Claude MCP fields: `${APPLICATION_TOKEN}` where native expansion is supported;
  Claude's settings `env` values are not treated as interpolated secret storage.
- Codex: `env_key`, `bearer_token_env_var` and `env_http_headers` hold environment
  variable **names**, not secret values. `${TOKEN}` is not invented as a Codex
  interpolation mechanism.
- Pi extension reference support depends on the installed extension. Do not
  assume a shell-style reference is a built-in Pi setting.

Configure the real credential through the harness's approved native credential
mechanism or secret store. The manager does not copy authentication state.

## Export and import

```sh
soulsteads settings export --home /path/to/home --runtime opencode \
  --output settings-profile.json
soulsteads settings import --home /path/to/other-home --runtime opencode \
  --profile settings-profile.json --plan-file import-plan.json
soulsteads settings apply --home /path/to/other-home --plan-file import-plan.json
```

Exports contain Home-local portable settings, retained native secret references
and explicit omissions. Managed wiring and credential-bearing values are not
portable. Import previews by default and reuses the normal validation and apply
path. Redaction placeholders are not configuration values and are refused.
Profiles are runtime-specific; there is no claim of automatic translation from
one harness's settings or permission semantics into another's.
MCP imports update individual portable server entries and preserve destination
Hindsight wiring and unrelated servers. Other imported object values replace
the corresponding property; review their preview rather than assuming a deep
merge of every native object.

## Separate projects

`run --project` carries Home identity and skill guidance through native per-run
inputs without moving native authentication/session directories or writing the
project's configuration. It deliberately does **not** copy Home model/provider,
MCP or permission policy into the project. See [runtimes](runtimes.md) and
[native acceptance](native-acceptance.md) for mechanisms, versioned evidence and
limits. Start a fresh native session after settings changes unless you have
separately qualified that harness's live-reload behavior.

Codex/Claude project mode additionally requires explicit `--allow-context-in-argv`
because its native inline inputs expose private Home text in process arguments.
Other local users or process monitors may read those arguments. Do not enable
this on a host where that exposure is unacceptable; Home-root launches remain
available without it. Dry-run output redacts the private inline text.
