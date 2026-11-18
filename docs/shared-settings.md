# Canonical shared settings

Home stores explicit portable intent in `soulsteads.json` as `shared_settings`.
Use `soulsteads config ./helper --shared-json '<JSON object>'` to replace it.
The command refreshes native files transactionally; changing the selected
harness and every actual Home-managed launch also refresh the selected harness.
Dry-run previews do not publish changes. Identity, skills, Hindsight and learning
retain their dedicated adapters and commands.

| Canonical field | Codex | OpenCode | Pi | Claude Code |
| --- | --- | --- | --- | --- |
| `model` | `model` | `model` | `defaultModel` | `model` |
| `provider` | `model_provider` | `provider/model` (requires model) | `defaultProvider` | Explicitly unsupported |
| `mcp` | `mcp_servers` stdio | `mcp` local | Explicitly unsupported | `.mcp.json` stdio |
| `permission` | Explicit `read-only` only: `sandbox_mode=read-only`, `approval_policy=never` | Unsupported | Unsupported | Unsupported |

Omitting permission never adds a permission override. Other permission semantics
must be configured natively; Home does not guess equivalence. Provider definitions,
credentials, environment expansion, remote MCP authentication and advanced options
remain native. A provider name does not create its credentials or authorize spend.
Hindsight uses `--hindsight-url`, not a shared server named `hindsight`.

Example (generic values; use an installed server and native provider):

```sh
python3 -m pip install 'soulsteads[settings]'
soulsteads config ./helper --shared-json '{"model":"example-model","mcp":{"local-proof":{"command":"example-mcp","args":["--stdio"]}}}'
soulsteads commit ./helper -m 'Configure shared model and MCP'
soulsteads run ./helper -- exec --ephemeral 'Use the configured proof tool.'
```

MCP names must contain only ASCII letters, digits, underscores or hyphens, up to
64 characters. Only a command and string arguments are accepted. Literal secrets
are refused by the settings secret check; do not put credentials in this object.
Use native credential facilities. The optional `settings` extra supplies TOML
editing for Codex; unsupported formats fail before publication.

## Ownership and recovery

Home owns only values it introduced or previously owned. An equal pre-existing
native value remains user-owned. Unrelated native fields and TOML comments remain
intact. Editing an owned native value creates an explicit conflict; Home refuses
before publishing the manifest, identity or settings. Inspect the diff and
reconcile the canonical and native values deliberately. Home does not silently
adopt conflicting native edits. Switching harnesses preserves other harnesses'
files and ownership records.

To remove shared intent, use `--shared-json '{}'`; only owned native values are
removed. Commit coherent changes with `soulsteads commit`, and recover using
`soulsteads revert ./helper REVISION`. Restore creates a new commit and preserves
history. Restart the native session after configuration changes. No command here
changes global runtime configuration or authentication.

## Native loading and qualification

Codex project-file loading depends on native project trust. Home does not grant
trust. For Home-managed Codex launches, explicit shared intent is passed as native
`--config` arguments as well as written to the Home's native file. For `exec`/`e`
placed immediately after Home's `--`, overrides follow the subcommand because
Codex 0.162.1 uses a separate parser there. Later user-provided native flags retain
native precedence. Direct Codex launches still depend on native project trust for
project settings, and native-only Home fields are not copied into these flags.
Project-mode identity text remains subject to explicit argv consent and dry-run
redaction. Do not put secret values in model/provider/MCP command arguments.

Actual Codex 0.162.1 sessions have loaded Home identity, discovered an installed
skill, executed its bundled Python script, and called an actual stdio MCP tool
using canonical model/provider/MCP settings. The harmless tool truthfully declares
MCP `readOnlyHint`; a tool requiring approval can be refused under native
`approval_policy=never`. Actual OpenCode 1.19.5 sessions using a local compatible
model have loaded Home identity and an installed skill and executed its script.
These observations do not qualify every provider, MCP transport, permission mode,
Pi translation, project mode, resume or compaction. Schema and unit checks
for other mappings are not real-session qualification.

Claude Code 2.1.325 has exercised Home-root settings, skill loading, a named
project MCP server with explicit native consent, and separate clean-exit
continuation. That does not qualify crash recovery, live settings reload,
compaction, or all project MCP transports. Named-server consent is not global
approval. Maintained Pi 1.4.0 has exercised loading and changed-setting
consumption; its two-session task did not complete. See the
[native compatibility limits](native-acceptance.md).
