# Native harness configuration

Agent Home prepares files. The selected harness owns the agent loop, sessions,
tools, permissions, approvals and integrations. There is no Soulsteads prompt
interceptor, memory daemon or required launcher. Global harness configuration and
authentication remain active; a Home is not a sandbox.

## Direct launch and refresh

New Homes contain native files for all four harnesses. `--runtime` selects only the
launch default; changing it does not remove another harness's configuration.

```sh
soulsteads create helper --runtime opencode
cd ~/.soulsteads/agents/helper
opencode                  # or pi, codex, claude
```

Start from the Home root so its project configuration and instructions are found.
The `workspace/` output convention does not change the process working directory
or grant filesystem access. Starting in another unrelated repository does not
implicitly carry this Home's identity. Project access and trust belong to the
harness; Agent Home never grants trust or changes approval/sandbox policy.

The qualified exception is maintained Pi 1.4.0:
`soulsteads run helper --project /path/to/project`. Native Pi flags select Home
identity/operating guidance and canonical skills while project instructions load
from the project cwd. Home MCP/provider configuration is not forwarded. Other
project selectors are rejected in this release. See [current native acceptance](native-acceptance.md)
for package identity, tested trust boundaries, and unsupported combinations.

After editing canonical identity or curated memory, refresh before a new session:

```sh
soulsteads config helper --sync
soulsteads verify helper
soulsteads commit helper -m "Update agent identity and native projections"
```

`--sync` also upgrades existing Homes without changing their canonical Markdown.
It accepts uncommitted edits, preflights every native file, and preserves unrelated
JSON fields, additional OpenCode instruction paths, and TOML outside the marked
Codex block. JSON formatting can change when managed fields change. Conflicting
owned edits are refused rather than overwritten. Resolve them manually; there is
no force-overwrite option. Review the diff and use normal Home Git history for
rollback. Publication is atomic per file, not a multi-file filesystem transaction;
an I/O failure can leave a partial refresh. Inspect before retrying.
The [publication contract](publication-contract.md) requires external editors and
native readers to be quiescent. A persistent cooperative lock does not exclude
arbitrary editors, turn check-plus-replace into compare-and-swap, or make all
configuration files one transaction.
Identity inputs and generated native files are bounded to 1 MiB each; excessive
content is rejected, never silently truncated. Curate large memory files first.

Pi and Codex need generated snapshots because they do not have the same Markdown
include mechanism. Their projections contain the current SOUL.md, USER.md and
MEMORY.md text. `managed_files` hashes in `soulsteads.json` identify generated
content, not a security boundary. OpenCode and Claude read the canonical files
through native includes. Sync does not reload an active session: start a new one,
or use a harness's documented reload facility. Resume/compaction behavior must be
qualified separately; old sessions are not portable between harnesses.

## Instructions and skills

- **OpenCode:** root `opencode.json` includes `SOUL.md`, `USER.md` and `MEMORY.md`
  with its native `instructions` list; `AGENTS.md` is discovered normally.
- **Claude Code:** `CLAUDE.md` imports `AGENTS.md`, `SOUL.md`, `USER.md`, and
  `MEMORY.md`. `.claude/settings.json` is a project customization point.
- **Pi:** `.pi/APPEND_SYSTEM.md` appends the generated identity without replacing
  the built-in system prompt. Pi discovers `AGENTS.md`; `.pi/settings.json` stays
  a customization point. Project configuration requires native trust. The
  launcher no longer sends identity files as initial user-message attachments.
- **Codex:** `.codex/config.toml` adds generated `developer_instructions`. It does
  not set `model_instructions_file` or replace built-in instructions. Native
  `AGENTS.md` discovery supplies workspace guidance. Untrusted projects skip
  project configuration, so inspect trust through Codex rather than assuming the
  file was applied. Do not edit inside the managed TOML block.

`skills/` is the single editable Agent Skills tree. Two fixed relative links expose
it natively: `.agents/skills -> ../skills` (OpenCode, Pi, Codex) and
`.claude/skills -> ../skills` (Claude Code; also recognized by some other harnesses).
These are the only managed links allowed. Native Windows symlink behavior is not
qualified. Harness versions may warn about duplicate discovery.

Fresh Homes include original `starter` and `skill-maintenance` procedures unless
created with `--no-skills`. Skill maintenance is executed by the harness's own file
and shell tools. It proposes improvements after useful corrections, applies only
explicitly authorized or preapproved skill edits, validates them, and commits only
with authority. It does not install plugins, run a background learner, or expand
permissions. Existing/imported skills are not silently replaced with starters.

## Explicit Hindsight tools

Configure a pre-existing, authorized Hindsight bank through native HTTP MCP:

```sh
soulsteads config helper \
  --hindsight-url https://memory.example/mcp/helper/ \
  --hindsight-token-env HINDSIGHT_API_TOKEN
```

Supply the token to the harness through your approved secret/environment mechanism.
Agent Home stores only its environment-variable **name** and never copies the
credential into configuration or contacts the endpoint. The offline verifier
checks whether the variable is nonempty, without reporting its value; this does
not validate the credential. `HINDSIGHT_API_TOKEN` is the default reference.
URLs must be HTTPS, with a per-bank `/mcp/<bank>/` path and no userinfo, query or
fragment; HTTP is allowed only on localhost/loopback. The URL chooses a bank, not
an authorization boundary: the server must enforce the caller's permissions.

Native output:

- OpenCode: `mcp.hindsight` in `opencode.json`, remote transport, explicit bearer
  header using `{env:NAME}`; automatic OAuth discovery is disabled for this entry.
- Claude Code: project `.mcp.json`, HTTP server and `${NAME}` header expansion.
- Pi: project `.pi/mcp.json`, HTTP server and `${NAME}` header expansion.
- Codex: `mcp_servers.hindsight` URL and `bearer_token_env_var` in the managed TOML
  block.

The harness owns MCP connection, tool discovery, approval and invocation. Project
MCP configuration may require native approval. This feature does not change global
servers, install Hindsight packages, start a service, auto-retain conversations,
ingest Git history, or claim automatic recall. A native plugin/hook integration
would be a separate opt-in feature with its own version and lifecycle tests.

```sh
soulsteads config helper --no-hindsight
```

Removal affects owned project entries only and preserves unrelated MCP servers.
It does not delete bank data, revoke credentials, disconnect a running session, or
remove a global server. Inspect native configuration precedence if a global
`hindsight` server remains. Root MEMORY.md stays distinct from external Hindsight
and each harness's built-in automatic memory.

## Verification boundaries

`soulsteads verify` checks basic syntax, native projection freshness, private
storage, skill metadata, and safe aliases without launching a harness or fixing
files. It reports each adapter's paths and loading mechanism, required native
trust/reload actions, and an **unverified** runtime version; it does not probe or
install a harness. Configured memory always retains a separate qualification
finding. A missing credential is actionable, but a present variable is not proof
of valid authorization, server availability, correct bank, or native approval.
`needs-review` is not activation proof. Generated files cannot guarantee that a
model follows instructions or chooses a skill.

Tests use disposable Homes and real local Git. Native qualification must record
exact client versions and separate config/schema reads from real model generation,
MCP connectivity, instruction following, resume and compaction. No paid model calls
or private-agent imports are required for the ordinary test suite. Runtime APIs
and configuration schemas change; qualify a new release before claiming parity.

Current versioned acceptance and its limits are recorded in
[native acceptance](native-acceptance.md). The following earlier investigation
receipts are retained as historical context, not acceptance of a newer candidate.
That native configuration qualification used OpenCode 1.19.4 and 2.1.3, Pi
`@earendil-works/pi-coding-agent` 1.4.0, Codex CLI 0.157.1 and Claude Code 2.1.270:

- OpenCode `debug config` accepted the project instructions and Hindsight config;
  `debug skill` discovered both Home starter skills. A native `run` request sent
  to a loopback fixture contained the SOUL/USER canaries, AGENTS.md and both
  skills. The fixture intentionally returned HTTP 400; no real model ran.
- Pi's actual resource loader loaded SOUL/USER canaries from APPEND_SYSTEM.md and
  discovered both skills; its native MCP validator accepted the server entry.
- Codex's app-server `config/read` returned both canaries in effective developer
  instructions; `mcp get hindsight --json` recognized the project MCP entry. Its
  `debug prompt-input` dump included both canaries, AGENTS.md and both starter
  skills in model-visible input, without invoking a provider (MCP disabled only
  for that read-only prompt dump).
- OpenCode v2.1.3 `debug config` also accepted the same Home configuration and
  translated its MCP entry to the native server map. A native `run --standalone`
  request to the same kind of HTTP 400 fixture included both identity canaries,
  AGENTS.md and both skills. `debug skill` is not a supported v2 command; the
  request capture, not that failed command, establishes discovery in this check.
- Claude `mcp get hindsight` recognized project scope and reported pending approval.
  A native `claude -p` request captured by an isolated loopback fixture contained
  the SOUL/USER canaries, AGENTS.md and both skills through the shared aliases.
  The fixture intentionally returned HTTP 400; this proves request construction,
  not model generation. The plugin-component validator does not follow the alias
  directory, so it must not be used as evidence that ordinary skill loading fails.

All native checks used disposable homes and synthetic data without real provider
calls or live Hindsight access. The deprecated `@mariozechner/pi-coding-agent` 0.73.1
does not provide the current native MCP surface; do not infer support from its
`pi` executable name. Skill execution, session lifecycle and older client versions
are not qualified here.

## First-party references

- OpenCode: [config](https://opencode.ai/docs/config/),
  [rules](https://opencode.ai/docs/rules/), [skills](https://opencode.ai/docs/skills/),
  [MCP](https://opencode.ai/docs/mcp-servers/).
- Pi: [configuration](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/configuration.md),
  [skills](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/skills.md),
  [MCP](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/mcp.md).
- Codex: [configuration](https://developers.openai.com/codex/config-reference/),
  [AGENTS.md](https://developers.openai.com/codex/guides/agents-md/),
  [skills](https://developers.openai.com/codex/skills/),
  [MCP](https://developers.openai.com/codex/mcp/).
- Claude: [memory/imports](https://code.claude.com/docs/en/memory),
  [settings](https://code.claude.com/docs/en/settings),
  [skills](https://code.claude.com/docs/en/skills), [MCP](https://code.claude.com/docs/en/mcp).
- Hindsight: [MCP server](https://github.com/vectorize-io/hindsight/blob/main/hindsight-docs/docs/developer/mcp-server.md),
  [optional maintained coding-agent integration](https://github.com/vectorize-io/hindsight/tree/main/hindsight-integrations/coding-agents).
