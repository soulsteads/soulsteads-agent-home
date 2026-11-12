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
versions do not identify your installed version. `verify` adds capabilities and
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

Every `--learning scoped-apply` selection requires its complete target list;
other modes reject targets. A bare `--sync` retains the stored mode and scope.
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

This is a skill-learning instruction convention. Scope is checked when compiling
configuration, but Soulsteads does not mediate the harness's later file writes.
Native permissions and approvals remain authoritative. The policy excludes
supporting scripts, identity/config changes, permissions, credentials, plugins,
schedules, installations, commits and external actions. It grants no memory-write
or Hindsight-retention authority. Curated facts, service-owned memory and temporary
handoffs remain separate. No lifecycle hook or background learner is installed.

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

Native wiring:

- **Claude:** owned `UserPromptSubmit` and `Stop` callback groups in project
  `.claude/settings.json`. Unrelated callback groups and settings are preserved.
- **Codex:** project `.codex/hooks.json` with the same command events and owned
  `features.hooks = true` while enabled. Project trust and exact hook-definition
  review remain native; no trust is granted by Soulsteads.
- **OpenCode:** `.opencode/plugins/soulsteads-memory.js` uses the **v1 plugin API**:
  `chat.message`, additive `experimental.chat.system.transform`, and `session.idle`.
  The SDK's assistant `parentID` must match the captured user message. OpenCode v2
  uses a different plugin API and is not supported for this automation mapping.
- **Pi:** `.pi/extensions/soulsteads-memory.ts` uses `before_agent_start`,
  `agent_end`, and final `agent_settled` to exclude aborted runs. These surfaces
  were checked against maintained **1.5.2 source**; historical 1.4.0 identity/project
  loader receipts do not qualify this new lifecycle integration.

The adapters invoke `soulsteads memory-hook`, so the installed CLI must be on the
harness's PATH. No required launcher, daemon, installer, npm package, runtime
permission change or global config is added. Generated extension files stay
owned and reproducible when disabled; their manifest guard disarms them. Owned
command registrations are removed, preserving other groups. Stop and restart
native sessions after changes, review generated code and use native trust/approval
flows. Only **Home-root sessions** are supported for automatic memory. Pi's separate
project selector does not forward the Home extension or MCP connection.

Recall sends the captured prompt to the configured per-bank MCP `recall` tool
with low search budget and a 1,000-token request budget. Returned reference text is
bounded to 6,000 characters and explicitly marked as untrusted data. Command hooks
return native `additionalContext`; Pi adds a hidden native custom message, and
OpenCode appends to the existing system context. No built-in prompt is replaced.

Retention captures a prompt only when enabled, then submits it and a completed
assistant reply to the same bank's `retain` tool. It never opens `transcript_path`,
reads Git history, or sends tool/reasoning/image attachments. Text is bounded to
32 KiB per speaker; oversized or missing text is skipped. Native template/skill
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
  [optional maintained coding-agent integration](https://github.com/vectorize-io/hindsight/tree/main/hindsight-integrations/coding-agents).
