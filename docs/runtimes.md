# Native harness configuration

Agent Home prepares files. The selected harness owns the agent loop, sessions,
tools, permissions, approvals and integrations. There is no Soulsteads prompt
interceptor, memory daemon or required launcher. Global harness configuration and
authentication remain active; a Home is not a sandbox.

## Capability matrix

Soulsteads compiles one portable definition into native files. Canonical Markdown
and `skills/` describe the agent; `soulsteads.json` selects its launch default,
optional Hindsight connection and learning policy. Native files are projections
or references, not a second editable agent definition. OpenClaw/Hermes-style
identity, memory and skill conventions do not imply full runtime parity.

| Capability | OpenCode | Pi | Codex | Claude Code |
| --- | --- | --- | --- | --- |
| SOUL/USER/curated MEMORY | Native `instructions` paths | Generated additive `APPEND_SYSTEM.md` | Generated additive `developer_instructions` | Native `CLAUDE.md` imports |
| Portable skills | Native `.agents/skills` alias | Native `.agents/skills` alias | Native `.agents/skills` alias | Native `.claude/skills` alias |
| Optional Hindsight tools | Native MCP config | Maintained Pi native MCP config | Native MCP config | Native MCP config |
| Learning modes | Model-followed policy through native instructions | Same, included in generated projection | Same, included in generated projection | Model-followed policy through native imports |
| Opt-in automatic recall/retention | V1 lifecycle plugin | Current lifecycle extension | Native command hooks | Native command hooks |
| Home identity/skills with separate project cwd | Unqualified | Qualified native resource loading, 1.4.0 only | Unqualified | Unqualified |
| Model behavior, resume and compaction | Unverified | Unverified | Unverified | Unverified |

Skill discovery does not translate Hermes-specific tools, scripts, services or
permissions. Inspect imported dependencies and report unsupported requirements.
Hindsight registration alone is config support, not live connectivity. Automatic
memory is a separate opt-in mapping described below; its adapters have synthetic
protocol and native-event fixture coverage, not full native-session qualification.
Native-loader evidence for identity/skills and its exact versions is
recorded in [native acceptance](native-acceptance.md). Configurable learning policy
has source/disposable-Home coverage only; its new content has not been separately
qualified in native sessions.

```sh
soulsteads capabilities
soulsteads capabilities --runtime pi
soulsteads verify helper
```

`capabilities` emits a versioned JSON matrix without reading an agent Home,
probing an installed runtime, or contacting a provider. Historical qualified
versions do not identify your installed version. Add `--probe-versions` (see
"Opt-in version probe" below) to also compare the installed binaries. `verify` adds capabilities and
the effective learning mode/target count to each adapter, without exposing skill
target names, document contents or connection values.

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

Use `soulsteads run helper --project /path/to/project` to explicitly select Home
identity and skill guidance in a separate repository. Home MCP/provider settings
are not forwarded. See [separate-project launch](#separate-project-launch) and
[current native acceptance](native-acceptance.md) for the per-harness mechanisms,
versioned qualification and limits.

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
and shell tools when the selected learning mode permits it. It proposes improvements
after useful corrections, applies only
explicitly authorized or preapproved skill edits, validates them, and commits only
with authority. It does not install plugins, run a background learner, or expand
permissions. Existing/imported skills are not silently replaced with starters.

## Learning configuration

New and newly imported Homes have an explicit `off` learning policy. Existing
Homes without a `learning` field retain their existing guidance, including the
older starter's proposal convention. Plain `--sync` does not opt those Homes into
a mode or rewrite their canonical instructions or skills.

```sh
soulsteads create helper --runtime pi --learning propose
soulsteads config helper --learning scoped-apply \
  --learning-skill starter --learning-skill skill-maintenance
soulsteads config helper --learning off
```

- **off:** do not initiate durable-guidance proposals or edits as a side effect
  of normal work. Explicit user requests to edit guidance are still ordinary tasks.
- **propose:** suggest one evidence-backed procedural improvement with its target,
  reason and proposed diff; wait for explicit authority before persisting it.
- **scoped-apply:** preapprove small procedural corrections only to the existing
  `skills/<name>/SKILL.md` files explicitly named by repeated `--learning-skill`.
  Preserve metadata, validate corrections, and report each applied diff and evidence.

- **auto:** [submit, approve and adopt Skillstore corrections automatically](#automatically-approve-and-adopt-skillstore-corrections)
  for the named skills.

Each `scoped-apply` or `auto` selection requires its complete target list.
The other modes reject targets. A bare `--sync` retains the stored mode and scope.
Targets must be unique local skill names, not paths or patterns, and their files
must exist. New Homes may name only the bundled skills actually being created;
install other inspected local skills first, then configure them. `--no-skills`
omits starters without overriding the learning mode. No skill is installed or
executed by selecting a policy. Missing scoped targets fail sync/verification;
select `off` or a new valid scope to remove a stale target.

The manifest stores, for example:

```json
{"learning": {"mode": "scoped-apply", "skills": ["starter"]}}
```

Soulsteads generates owned `LEARNING.md` from that setting. OpenCode adds it to
`instructions`, Claude imports it from `CLAUDE.md`, and Pi/Codex include its text
in their existing additive instruction projections. The policy selects the mode
ahead of generic starter/imported learning guidance. Existing canonical Markdown
and installed skills remain user-maintained. Edit the setting with `config`, not
the generated policy; owned-file conflicts are refused before publication.
Changes use the same [publication contract](publication-contract.md) as identity
and memory configuration. Review the diff and start a fresh native session.

The harness identifies opportunities for skill improvements during work.
In `scoped-apply` and `auto`, `soulsteads skill learn` rejects targets outside the
Home's allowlist before planning a change or contacting Skillstore, even if the
skill has a registry binding. Native permissions govern tool calls and direct
file writes.
Keep supporting scripts, identity, credentials, memory, and other runtime
configuration under their separately configured workflows. The harness must be
able to run the CLI and reach Skillstore from the session for unattended learning.

## Explicit Hindsight tools

Configure a pre-existing, authorized Hindsight bank through native HTTP MCP:

```sh
soulsteads config helper \
  --hindsight-url https://memory.example/mcp/helper/ \
  --hindsight-token-env HINDSIGHT_API_TOKEN
```

Supply the token to the harness through your approved secret/environment mechanism.
Agent Home stores only its environment-variable **name** and never copies the
credential into configuration. Config and verification do not contact the endpoint;
opted-in runtime callbacks do. The offline verifier
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
servers, install Hindsight packages, start a service, or ingest Git history.
Automatic recall and retention require the separate opt-in below.

```sh
soulsteads config helper --no-hindsight
```

Removal affects owned project entries only and preserves unrelated MCP servers.
It does not delete bank data, revoke credentials, disconnect a running session, or
remove a global server. Inspect native configuration precedence if a global
`hindsight` server remains. Root MEMORY.md stays distinct from external Hindsight
and each harness's built-in automatic memory.

### Hindsight service configuration

Service deployment remains optional and belongs to Hindsight, not Home. In the
published [`hindsight-api-slim` 1.2.1 distribution](https://pypi.org/project/hindsight-api-slim/1.2.1/),
`hindsight_api/config.py` defines
`HINDSIGHT_API_RETAIN_MAX_COMPLETION_TOKENS`,
`HINDSIGHT_API_RETAIN_CHUNK_SIZE`, `HINDSIGHT_API_LLM_MAX_RETRIES`,
`HINDSIGHT_API_RETAIN_LLM_MAX_RETRIES`, `HINDSIGHT_API_LLM_TIMEOUT`,
`HINDSIGHT_API_ENABLE_AUTO_CONSOLIDATION`, `HINDSIGHT_API_WORKER_ENABLED`,
`HINDSIGHT_API_EMBEDDINGS_OPENAI_DIMENSIONS`, and
`HINDSIGHT_API_SKIP_LLM_VERIFICATION`. These are service environment settings;
Home does not emit or change them. Inspect the owner version before use.

The preflight parsed a 2048-token retention output limit, a 1000-character chunk
size, zero configured LLM/embedding retries, disabled consolidation/worker, and
1024 embedding dimensions. The output-token limit must exceed the chunk-size
setting. The service's startup verification still makes a model call by default:
`engine/providers/openai_compatible_llm.py::verify_connection` supplies its own
retry setting. A request/time guard is needed to enforce an aggregate test budget;
per-operation configuration alone is not an aggregate cap. Skipping a previously
completed startup check does not qualify retention or recall.

In this version, `api/http.py` exposes resolved bank configuration through
`GET /v1/default/banks/{bank_id}/config`; the bare bank URL is not that GET route.
`api/mcp.py` selects single-bank tools from the URL path, while
`extensions/builtin/tenant.py::ApiKeyTenantExtension` authenticates a tenant.
That built-in authentication does not establish a bank allowlist. A bank URL or
rejected extra tool argument must not be advertised as credential-level
cross-bank authorization.

### Per-principal memory isolation with Hindsight 1.2.1

In this version, the shipped enforcement unit is the **tenant**, not the bank.
`ApiKeyTenantExtension` accepts exactly one key per service process and maps every
authenticated request to that process's `HINDSIGHT_API_DATABASE_SCHEMA`. Any
holder of that key can reach every bank in that schema. This applies to the REST
routes, the multi-bank `/mcp/` endpoint (which takes a `bank_id` argument), and
any `/mcp/<bank>/` URL. The package ships no per-key bank allowlist. A custom
`TenantExtension` or `OperationValidatorExtension` could add one, but that would be
new authorization code. Home does not provide one.

Isolate principals (for example work, personal and coding agents) using only
shipped capability:

1. Run one Hindsight service per principal. Set `HINDSIGHT_API_TENANT_EXTENSION`
   to `hindsight_api.extensions.builtin.tenant:ApiKeyTenantExtension`.
   Each service needs its own fresh key in
   `HINDSIGHT_API_TENANT_API_KEY`, and its own `HINDSIGHT_API_DATABASE_SCHEMA`.
   The services can share one PostgreSQL database.
2. Leave `HINDSIGHT_API_MCP_AUTH_TOKEN` unset and
   `HINDSIGHT_API_TENANT_MCP_AUTH_DISABLED` unset or false. The former selects
   legacy MCP authentication; the latter can bypass tenant MCP authentication.
3. Point each Home at its principal's service. Use a distinct token
   environment-variable name for each Home:

```sh
soulsteads config work-agent --hindsight-url https://work-memory.example/mcp/work/ \
  --hindsight-token-env WORK_HINDSIGHT_TOKEN --sync
soulsteads config personal-agent --hindsight-url https://personal-memory.example/mcp/personal/ \
  --hindsight-token-env PERSONAL_HINDSIGHT_TOKEN --sync
```

Each key then reaches only its own service's schema. Another principal's service
rejects it with HTTP 401. Naming another bank through the key's own service finds
only banks in that key's schema, so another principal's data reads as absent. Home
checks only that the variable is nonempty. It never stores the value and cannot
confirm that two Homes use different keys or services. The operator must keep
them distinct.

These settings were checked in the published 1.2.1 distribution linked above:
`extensions/builtin/tenant.py::ApiKeyTenantExtension` defines key/schema mapping
and the MCP auth-disable option; `extensions/loader.py::_collect_config` reads
the tenant environment variables; `config.py` defines the database schema and
legacy MCP token fields; `api/mcp.py::MCPMiddleware` selects MCP authentication.

The boundary is the key-to-service binding. Banks *within* one tenant are not
isolated from each other. In this topology, all services connect to PostgreSQL
with whatever role you configure. Separate database roles per schema are
stronger, but they were not qualified here. See the
[memory compatibility limits](native-acceptance.md#optional-memory).

## Automatic Hindsight memory

After configuring a bank, select either operation independently:

```sh
soulsteads config helper --hindsight-recall --hindsight-retain
soulsteads config helper --no-hindsight-retain
soulsteads config helper --no-hindsight-recall
```

Both default to off, including in existing Homes. The manifest stores
`"hindsight_automation": {"recall": true, "retain": true}`. Each flag changes only
its own setting under the cooperative configuration lock. `--no-hindsight` also
disables both operations. Configuration stays offline and uses the existing
checked publisher, ownership/conflict rules, and canonical Git lifecycle.

Inspect the saved policy and effective defaults without printing the endpoint,
bank name, or credential:

```sh
soulsteads config helper --hindsight-status
soulsteads config helper --hindsight-policy-json '{"recall_budget":"mid","recall_max_tokens":800}'
```

Each update merges only the specified keys into `hindsight_policy` in the Home
manifest. It does not enable either callback or change native MCP permissions.
Supported options are:

- `recall_budget`: `low` (default), `mid`, or `high`.
- `recall_max_tokens`: 1–4,000 tokens (default 1,000).
- `recall_context_chars`: 256–6,000 characters (default 6,000), including the reference wrapper.
- `turn_text_bytes`: 1–32,768 UTF-8 bytes per speaker (default 32,768).
- `request_timeout_seconds`: 1–3 seconds (default 3) for socket operations,
  capped by the remaining callback budget when each HTTP request starts.
- `callback_deadline_seconds`: 1–8 seconds (default 8) for the whole MCP
  exchange. Responses at or after the deadline are discarded, but this is a
  soft limit on how long the callback runs: an in-progress HTTP operation can
  return late. The native adapter's outer timeout is unchanged.

These are Home callback limits, not Hindsight server settings or limits on
explicit native MCP calls. Status reports whether the credential is present in
the current CLI environment; it does not test the service or native approval.

The native adapters check recall and retention separately. Recall-only sessions
do not cache completed replies, fetch session messages for retention, or invoke
retain callbacks. Retention-only sessions still capture the prompt but do not
inject recall context. With both flags off, neither prompt nor reply content is
processed by these adapters. Pi discards a cached reply if retention is disabled
before settlement; OpenCode rechecks retention after awaiting session messages
and before consuming the returned replies. These are automatic-memory controls,
not a restriction on separately invoked native MCP tools.

Native wiring:

- **Claude:** owned `UserPromptSubmit` and `Stop` callback groups in project
  `.claude/settings.json`. Unrelated callback groups and settings are preserved.
- **Codex:** project `.codex/hooks.json` with the same command events and
  `features.hooks = true` while enabled. Existing feature tables are merged without
  losing unrelated flags or comments; their flags may be written as equivalent
  root-level dotted keys. A preexisting user-owned `hooks = true` stays enabled
  when memory is disabled. An explicit user `hooks = false` is a conflict, not
  silently overridden. Project trust and exact hook-definition review remain
  native; no trust is granted by Soulsteads.
- **OpenCode:** `.opencode/plugins/soulsteads-memory.js` uses the **v1 plugin API**:
  `chat.message`, additive `experimental.chat.system.transform`, and `session.idle`.
  The SDK's assistant `parentID` must match the captured user message. OpenCode v2
  uses a different plugin API and is not supported for this automation mapping.
- **Pi:** `.pi/extensions/soulsteads-memory.ts` uses `before_agent_start`,
  `agent_end`, and final `agent_settled` to exclude aborted runs. Only a successful
  `stop` reply is eligible for retention; output-limit fragments (`length`),
  pending/deferred responses, and tool/error/aborted replies are excluded. These
  surfaces were checked against maintained **1.5.2 source**; historical 1.4.0
  identity/project loader receipts do not qualify this new lifecycle integration.

The adapters invoke `soulsteads memory-hook`, so the installed CLI must be on the
harness's PATH. No required launcher, daemon, installer, npm package, runtime
permission change or global config is added. Generated extension files stay
owned and reproducible when disabled; their manifest guard disarms them. Owned
command registrations are removed, preserving other groups. Stop and restart
native sessions after changes, review generated code and use native trust/approval
flows. Only **Home-root sessions** are supported for automatic memory. Pi's separate
project selector does not forward the Home extension or MCP connection.

Recall sends the captured prompt to the configured per-bank MCP `recall` tool
using the Home's search and token budgets. Returned reference text is bounded by
the context limit and explicitly marked as untrusted data. Command hooks
return native `additionalContext`; Pi adds a hidden native custom message, and
OpenCode appends to the existing system context. No built-in prompt is replaced.

Retention captures a prompt only when enabled, then submits it and a completed
assistant reply to the same bank's `retain` tool. It never opens `transcript_path`,
reads Git history, or sends tool/reasoning/image attachments. Text is bounded by
the per-speaker byte limit; oversized or missing text is skipped. Native template/skill
expansion can be part of the captured prompt, and secrets typed into ordinary text
are not filtered. This opt-in authorizes that prompt/reply transfer, independently
of the learning mode. Hook network calls use the environment credential directly;
native MCP tool-invocation approval does not separately gate these hook HTTP calls.

Pending prompts live in `0700` `.runtime/hindsight/` with `0600` files named by
hashed runtime/session IDs. This directory is ignored by Git. The raw prompt is
cleared before the first retention attempt; duplicate callbacks do not retry it,
even if the service timed out after receiving it. Bank changes invalidate pending
turns, and prompts older than 24 hours are ineligible. Unfinished prompts can remain
in private storage until replaced or manually removed; expiry is not disk erasure.
No competing durable `MEMORY.md` copy or background ingestion is created.

The helper implements bounded MCP initialization, JSON/SSE responses and session
headers using the Python standard library. It refuses HTTP redirects, keeps TLS
verification, uses short network deadlines, and emits content-free failure notices
with empty native hook output. Memory failure never requests a continuation or
blocks a task. Retention is best-effort, at most one attempt per captured turn;
it is not an exactly-once or durable-delivery guarantee. Concurrent prompts in one
session, session resume/compaction and cancellation timing need native qualification.

Protocol tests use only a synthetic loopback server, and JavaScript adapter tests
use fake native events and a stub helper. Actual harness activation, live Hindsight
persistence and end-to-end model use remain unverified and are reported separately
by `verify` and `capabilities`. No ordinary test accesses a real memory bank.

## Verification boundaries

`soulsteads verify` checks basic syntax, native projection freshness, private
storage, skill metadata, and safe aliases without launching a harness or fixing
files. It reports each adapter's paths and loading mechanism, required native
trust/reload actions, and an **unverified** runtime version; by default it does
not probe or install a harness (see the opt-in probe below). With Hindsight
configured, it checks whether the named environment variable is set. Use
`soulsteads verify --no-credential-check helper` to omit that check and finding
without skipping structural or memory qualification findings. A set variable
does not prove authorization, server availability, bank identity, or approval.
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

### Opt-in version probe

`soulsteads verify <agent> --probe-versions` (and `soulsteads capabilities
--probe-versions`) runs `<binary> --version` for Pi, OpenCode, Codex and Claude
and adds a `version_probe` object (per runtime for `capabilities`). Without the
flag nothing is executed and the output is byte-for-byte unchanged. The probe
never alters findings, the `verify` exit status, `runtime_version` (which stays
`unverified`), permissions or privacy settings.

Each binary reports one status:

| Status | Meaning |
| --- | --- |
| `qualified` | The parsed version equals a version recorded below. |
| `newer-unqualified` | Newer than every recorded version. |
| `older-unqualified` | Not recorded and not newer than the newest recorded version (including versions between recorded ones). |
| `unparseable` | No single strict `MAJOR.MINOR.PATCH` in the output (pre-releases, several different versions, or oversized output are refused). |
| `not-installed` | No executable of that name on `PATH`. |
| `probe-failed/timeout` | Could not execute, exited non-zero, or exceeded 5 seconds; `reason` is one of `exec-error`, `non-zero-exit`, `timeout`. |
| `probe-skipped` | Not qualified and not executed: the binary is a version-manager shim or wrapper that could not be safely resolved; `reason` is `unresolved-mise-shim` or `wrapper:<manager>` (`volta`, `asdf`, `pyenv`, `shim`, ...). |

Qualified versions come only from `docs/native-acceptance.md`: Pi 1.4.0 and
OpenCode 1.19.5 (the maintained Pi and OpenCode records); Codex CLI 0.157.1 and
0.169.0; Claude Code 2.1.270, 2.1.318 and 2.1.325. A runtime with no recorded
version would report `no qualified version recorded` and is never `qualified`.

Limits: binaries are found on `PATH` the way Home's launcher finds them, and
are executed directly (no shell, argv list, stdin closed, own process group
killed on timeout, 4 KiB cap per stream, only `PATH`, `HOME`, locale, `TMPDIR`
and user-name variables inherited, plus `NO_COLOR=1` and mise auto-install
switches set to `0`). Every process the probe starts runs from the neutral
working directory `/`, so project `mise.toml` or `.tool-versions` files cannot
select a version, and `MISE_AUTO_INSTALL`, `MISE_EXEC_AUTO_INSTALL` and
`MISE_NOT_FOUND_AUTO_INSTALL` are `0`.

Shim handling: after `PATH` lookup (no extra search paths) the path and its
symlink target are checked before anything runs. Recognised wrappers are mise
(`*/mise/shims/*`, `*/mise/command-wrappers/*`, or a symlink to `mise`), asdf
(`*/.asdf/shims/*`), volta (`*/.volta/bin/*` or a symlink to `volta`/`volta-shim`),
pyenv (`*/.pyenv/shims/*`), any other `*/shims/*` directory (nodenv/rbenv style),
and scripts whose first `#!` line names one of these managers. For a mise shim the
probe runs `mise which <name>` once (same limits, no shell) and only accepts an
absolute path to an existing, executable, non-wrapper file, which it then probes
directly (`resolved_via: "mise which"`). If that fails, or the wrapper is not
mise, nothing is executed and the status is `probe-skipped`. This cannot detect
arbitrary unknown wrappers: a binary behind a wrapper this list does not know is
still run directly, so probe only binaries you are willing to run.
The probe writes no file, reads no Home
configuration, makes no provider, model or network request, and starts no
authentication flow. Version output is untrusted: only a strictly parsed
version is printed. **A version match is not live qualification.** It does not
show that this Home's adapter, permissions, memory or models work with that
binary; any error maps to a non-qualified status, never `qualified`.

## First-party references

The configurable learning policy reuses existing native instruction surfaces;
it introduces no harness-specific learning setting. Rechecked on 2026-11-11:
OpenCode's [configuration schema](https://opencode.ai/config.json) defines
`instructions` as an array of paths/URLs; Claude's
[memory reference](https://code.claude.com/docs/en/memory.md) documents relative
`@path/to/import` expansion; maintained Pi's
[configuration source](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/configuration.md)
documents additive `APPEND_SYSTEM.md`; the official OpenAI
[configuration reference](https://developers.openai.com/codex/config-reference/)
defines `developer_instructions` as additional session developer instructions.
These field checks do not extend the historical native-session qualification to
the newly generated learning content or to newer installed client versions.

Automatic-memory fields/events were checked on 2026-11-11 against the official
OpenAI [hooks guide](https://developers.openai.com/codex/hooks/) and
[config reference](https://developers.openai.com/codex/config-reference/), Claude's
[hooks reference](https://code.claude.com/docs/en/hooks), maintained Pi's
[extension reference](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/extensions.md)
(1.5.2 source), the published OpenCode
[v1 plugin interface](https://unpkg.com/@opencode-ai/plugin@1.19.4/dist/index.d.ts)
and [SDK message types](https://unpkg.com/@opencode-ai/sdk@1.19.4/dist/v2/gen/types.gen.d.ts),
and Hindsight's [per-bank MCP/tool reference](https://github.com/vectorize-io/hindsight/blob/main/hindsight-docs/docs/developer/mcp-server.md).
Current documentation/source checks and synthetic fixtures are not installed-client
qualification. Older clients without those events cannot provide this automation.

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
  - Optional maintained coding-agent integration: [Hindsight](https://github.com/vectorize-io/hindsight/tree/main/hindsight-integrations/coding-agents).

## Separate-project launch

`soulsteads run helper --project /path/to/project` selects a separate working
repository while carrying the selected Home's identity and skill guidance.
`prepare_launch(home, runtime, project, extra=())` returns the native arguments,
child environment and project working directory; extra arguments stay literal.
For OpenCode/Pi it returns an explicit resource lease: keep the returned object
in a `with` block through native execution, or close it in `finally`. The CLI
handles that lifetime. Preview mode (`preview=True`, selected by `--dry-run`)
returns a non-executable descriptor without creating private copies. See the
[snapshot lifetime and security boundary](settings.md#separate-projects).
No adapter copies Home-wide authentication/session directories or writes
project/global config. Selected relative skill assets are copied verbatim.

**Private argv consent:** Codex and Claude place the selected Home context in
process arguments, which may be readable by other local users or process
monitors even when Home files are private. These project adapters refuse to run
unless `--allow-context-in-argv` is supplied (or `allow_context_in_argv=True` is
passed to the API). Use a Home-root launch instead if that tradeoff is not
acceptable. A private-file transport for these interactive modes is not qualified
here. Dry-run output always redacts their inline Home text.

- **Maintained Pi:** native `--append-system-prompt` paths carry the Home identity
  projection and AGENTS; `--skill` paths select private per-launch copies of
  the canonical Home skills and their relative assets.
- **Codex:** native `--cd` selects the project and a per-run
  `--config developer_instructions=...` value carries bounded Home identity,
  AGENTS and canonical SKILL.md content. This selects the Home developer-guidance
  value for that run, rather than merging arbitrary ambient developer strings.
  Identity and learning policy come from the selected Home's synchronized
  `.codex/config.toml` `developer_instructions`, not another runtime's projection.
  This is the existing upstream [Codex field](https://github.com/openai/codex/blob/rust-v0.157.1/codex-rs/core/config.schema.json),
  also read back through native 0.169.0 `config/read`; no new configuration key
  or global setting is introduced. Selected-only sync may leave other adapters
  stale, so their projections are not authoritative for a Codex launch.
  Skills are prompt content, not Codex-native slash-skill registration. Neither
  `CODEX_HOME` nor `--add-dir` is changed.
- **Claude Code:** `--append-system-prompt` carries the same bounded Home content.
  This is not Claude-native slash-skill registration; no `--add-dir` is used.
- **OpenCode:** process-local `OPENCODE_CONFIG_CONTENT` adds Home instruction
  files and skill search paths from the same private resource lease, not mutable
  Home pathnames. An existing inline configuration
  retains its unrelated model/provider/permission fields, instruction paths,
  skill paths and skill URLs. Native discovery does not prove skill activation.

Codex/Claude inline context is bounded to avoid silently dropping Home content
or exceeding command-line limits. Oversized context is refused. These mechanisms
are not filesystem sandboxes, do not grant trust, and do not change the native
approval or sandbox settings merely by selecting a project. Native-only Home
settings are not copied. Codex receives explicitly configured canonical shared
model/provider/MCP settings and any explicitly requested supported permission
through native CLI overrides; see [shared settings](shared-settings.md).

### Qualification and limits

The focused project tests exercise deterministic arguments, environment handling,
context markers, no-shell behavior and unchanged Home/project state. Independent native request
fixtures additionally exercised Codex 0.157.1, Claude Code 2.1.318 and OpenCode
1.19.5 with a separate synthetic project. Each native request included Home
SOUL/USER/MEMORY/AGENTS markers, both canonical skill-description markers and
project instructions. The project inventory stayed unchanged. Each request was
stopped by a loopback HTTP 400; no model task completed or real credential was
used. Maintained Pi 1.4.0 retains its earlier direct-Home resource-loading
qualification. The new leased handoff was separately checked with OpenCode 1.19.5
(actual loopback HTTP 400 request) and Pi 1.5.2 (actual offline resource loader):
Home source replacement after preparation did not change loaded identity, skill
or project markers; Pi also loaded a relative skill asset from the leased copy.
This does not certify inference, bank persistence, resume or compaction.

For a local check, use a disposable Home and project, inspect the redacted dry run,
and confirm what the selected native harness loads before using private content.

Official native references:

- Codex [configuration](https://developers.openai.com/codex/config-reference/)
  and [CLI](https://developers.openai.com/codex/cli/reference).
- Claude Code [CLI](https://code.claude.com/docs/en/cli-reference)
  and [skills](https://code.claude.com/docs/en/skills).
- OpenCode [configuration](https://opencode.ai/docs/config/),
  [instructions](https://opencode.ai/docs/instructions/) and
  [skills](https://opencode.ai/docs/skills/).

## Soulsteads native harness (`--runtime soulsteads`, optional)

First-party harness `soulsteads-harness` 0.1.0; fields verified against its public
configuration reference (README "Configuration reference") and
the accepted binary's `capabilities` loader. The harness, not Home, owns
runtime/session/tool decisions. Home writes `soulsteads-harness.toml` at the Home
root and records the keys it owns in `soulsteads.json` (`shared_owned.soulsteads`);
every other key/comment/table is operator-owned and preserved. An owned key edited
natively, or an existing differing native value, is a conflict: sync refuses and
changes nothing.

| Canonical | Native |
| --- | --- |
| identity, curated memory, learning policy | `agent.id`, `agent.instructions_files` = AGENTS/SOUL/USER/MEMORY[/LEARNING].md (each <= 64 KiB). Changed text on a resumed session needs `--allow-instruction-change`; start a fresh session instead. |
| skills | `skills.roots = ["skills"]` (real directory, not the `.agents/.claude` symlinks); skills grant nothing, scripts never run |
| `model` | `provider.model` |
| `permission: read-only` | `grants.workspace = "workspace"` (Home workspace only), `grants.tools = [read_file, list_dir, search_files]` |
| `permission: workspace-write` | same workspace grant, `grants.tools = [read_file, write_file, edit_file, list_dir, search_files]`; no `run_command`, shell or network; approvals stay native-owned (default `allow`; set `[grants] approval = { write_file = "ask" }` natively to gate writes) |
| stdio `mcp` | `[[mcp_servers]]` `default_approval = "ask"`; empty child environment; calls need `run --approve-ask` or the `chat` terminal |

Unsupported (explicit error, nothing written): shared `provider` (the single
openai-compat endpoint is operator-owned: add `[provider] base_url_env` natively),
any `permission` except `read-only` and `workspace-write`, Hindsight/automation, `--project` launch
(would broaden the workspace grant), MCP names outside `[a-z0-9-]{1,24}`, Home names longer than the native agent id limit (64 chars; checked before create/runtime switch, external homes unaffected).
Native-only: limits, `run_command`/`[commands]`, per-tool approval, HTTP MCP
(e.g. a Forge public MCP URL with `header_value_env`), ACP/A2A. No hooks.

`soulsteads run <agent> -- run "task"` executes
`soulsteads-harness --config <home>/soulsteads-harness.toml --home <home>/.runtime/soulsteads-harness …`
(binary: `$SOULSTEADS_HARNESS_BIN` or `soulsteads-harness` on PATH); state stays in the
Git-ignored `.runtime/`. Switching to or from an external harness is
`soulsteads config <agent> --runtime <name>`; the native file is left untouched while
another harness is selected. Editing an existing native file needs the `settings` extra.

### Launch through Messaging

Messaging's public `acp.backends.soulsteads` command/args/environment interface can
invoke the installed Home CLI. Prepare an isolated Home through `create`, install
local skills through `skill install`, and set canonical model/file permissions
through `config --shared-json`. Set `provider.base_url_env` and bounded native
limits in its generated TOML as operator-owned settings. Preserve native
approvals. Home synchronizes its owned keys again on every `run`.

For example, this backend fragment assumes an existing `/srv/agents/helper`
using runtime `soulsteads`, canonical `permission: workspace-write`, and native
`provider.base_url_env = "HARNESS_BASE_URL"`:

```json
{
  "acp": {
    "defaultBackend": "soulsteads",
    "backends": {
      "soulsteads": {
        "command": "/opt/home/bin/soulsteads",
        "args": ["run", "/srv/agents/helper", "--", "acp"],
        "agentHome": "/srv/agents/helper/workspace",
        "env": {
          "SOULSTEADS_HARNESS_BIN": "/opt/harness/bin/soulsteads-harness",
          "HARNESS_BASE_URL": "{env:HARNESS_BASE_URL}"
        }
      }
    }
  }
}
```

This is a backend fragment, not a complete connector configuration. Configure
the bridge's persistent session store and the connector's explicit sender/room
allowlists separately. Keep credentials in private configuration or environment
references. Messaging's `agentHome` here must match the generated native
workspace grant, **not the canonical Home root**: ACP validates that cwd. Home
launches from its own root and passes explicit config and ignored runtime-state
paths. The bridge owns chat bindings; the native harness owns execution/history.

Messaging's built-in `soulsteads` backend queues up to eight pending texts in an
active Matrix thread. It submits them in order after successful completion, not
as live steering. If a turn is cancelled or fails, unsubmitted texts are dropped.
The queue is not durable. Cancellation does not undo completed work or establish
that the provider stopped. See [compatibility limits](native-acceptance.md#messaging-and-the-optional-native-harness).

## Review one skill change across harnesses

In a Home with learning set to `propose` or `scoped-apply`, Pi, OpenCode,
Claude Code and Codex receive the same review command through their native
instructions. Refresh existing Homes with `soulsteads config HOME --sync` and
start a fresh native session. The CLI must be on PATH for a harness to invoke
it. An operator can also run the command directly.

For example, suppose the body of `skills/shipping/SKILL.md` contains the exact
sentence “Record the parcel weight.” From the Home directory, preview one edit:

```sh
soulsteads skill review . shipping <<'JSON'
{"reason":"The carrier requires grams.","before":"Record the parcel weight.","after":"Record the parcel weight in grams."}
JSON
```

When already in the Home root, pass `.` so the CLI uses the current directory
as its anchor. This also works in a Linux user namespace that maps system
directory owners to an unmapped UID. Named paths retain the ancestry checks.

Read the diff locally. To accept it, repeat the same command and JSON with
`--apply REVIEW_ID` after the skill name, substituting the ID from the preview.
The ID binds the Home, skill, learning policy, current file content, reason and
replacement. A changed input requires a fresh preview. The ID is a consistency
check; approval still comes from the operator or the applicable learning scope.

Only a unique passage in an existing skill body can be replaced. The frontmatter
and other files are preserved. No proposal file or Git commit is required.
To undo the edit, preview the inverse change against the current skill and review
it before applying. Use the normal Home commit command when you want a revision.
External editors must be quiescent during apply, as for native configuration
publication. A fresh harness session can load the updated canonical skill through
its native discovery path.

## Send learning proposals to Skillstore

Install the [Skillstore CLI](https://github.com/soulsteads/soulsteads-agent-skillstore#install-from-source)
on the harness's PATH. Start with an existing skill whose `SKILL.md` matches
an exact reviewed version. For a shared registry, provision an agent
contributor token separately from the reviewer's token. Set the contributor
token variable through the harness's normal environment configuration.

```sh
soulsteads config . --learning propose
soulsteads skill bind . shipping --store https://skills.example.net \
  --version 1.0.0 --actor shipping-agent --token-env SHIPPING_SKILLSTORE_TOKEN
```

Use an absolute store directory outside the Home for a local registry and omit
`--token-env`. Remote registries use HTTPS or loopback HTTP. Bindings live under
the Home's private `.runtime/` directory and store the token variable name.

In a fresh session, the native learning guidance tells the harness to call
`soulsteads skill learn . shipping` with the same JSON fields as `skill review`.
With learning enabled and an active binding, Home stages the approved registry
package, verifies the local skill body against its recorded version, and
submits the correction as a pending proposal. Supporting files come from the
reviewed registry package. Keep the proposed text and reason suitable for
sharing with the configured registry.

The command reports the proposal ID. A repeat from the same Home checks for
an existing proposal with the same base and content before submitting. For an
unbound skill, the command returns a local preview. Native shell and network
permissions govern whether the harness can run the command and reach the store.

- Use `soulsteads config . --learning off` to turn off learning for all skills
  in the Home.
- Repeat the binding with `--no-auto-submit` to keep adoption and preview
  available while disabling automatic submissions for that skill.
- Use `soulsteads skill bind . shipping --off` to return that skill to local
  review.

A Skillstore reviewer can inspect and decide the proposal from the registry CLI
or through a configured
Telegram inbox in Agent Messaging. See `docs/SKILL-REVIEWS.md` in that project.
After acceptance, preview and adopt that exact version:

```sh
soulsteads skill adopt . shipping 1.1.0
soulsteads skill adopt . shipping 1.1.0 --apply REVIEW_ID
```

Adoption updates the canonical `SKILL.md` in the selected Home and records the
version and digest. It checks for local changes to that file, preserves
frontmatter, and requires a release that differs only in `SKILL.md`.
To undo an adoption, preview and adopt the earlier reviewed version using
the same commands. This restores just the skill body. Start a fresh harness
session to load the adopted version.

### Automatically approve and adopt Skillstore corrections

Use a separate Skillstore service reviewer for the skills you want to update
automatically. The reviewer must already be in the registry's reviewer list.
For a served registry, supply a token issued to that reviewer with
`skillstore --kind service token ...`. Keep the contributor token issued to
the agent under a different identity. For a local directory registry, specify
both actors and omit the two token options. Directory mode trusts the local
OS account to declare actors.

```sh
soulsteads skill bind . shipping --store https://skills.example.net \
  --version 1.0.0 --actor shipping-agent --token-env SHIPPING_SKILLSTORE_TOKEN \
  --reviewer-actor shipping-auto --reviewer-token-env SHIPPING_REVIEWER_TOKEN
soulsteads config . --learning auto --learning-skill shipping
```

Start a fresh native session. Its learning policy calls
`soulsteads skill learn` when it finds a reusable correction for a named skill.
The command validates the edit, submits it from the contributor, approves it
with the service reviewer, and adopts the verified release in the active Home.
For a new approval it requires the latest reviewed stable base and increments
that version's patch number. The command returns the proposal ID, new release
version and digest.

An approval error reports the proposal ID when available. Retry the same
proposal to reuse its recorded state. If Skillstore already accepted it but the
Home update was interrupted, the retry verifies the accepted release and
finishes adoption. A rejected proposal stays rejected. Use `skill adopt` to
return to an earlier reviewed version.

Set `--learning propose` to return to pending proposals, or `--learning off`
to stop learning. To remove the reviewer association, repeat `skill bind` with
the active version and omit the reviewer flags. Keep the service credential
private. A harness that can read its environment can use the reviewer token
with the registry privileges that token carries. Use a dedicated registry or
service account for the skills you intend to automate.
