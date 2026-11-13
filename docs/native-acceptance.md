# Native acceptance and release limits

Agent Home prepares native files. It does not run an agent loop, enforce prompt
instructions as permissions, grant trust, or certify model behavior. These checks
use synthetic data and isolated native state. No real agent migration or live
Hindsight bank is part of acceptance.

## Versioned native evidence

The native receipts below predate the configurable `LEARNING.md` policy.
Learning modes, scope checks, projections and capability reporting have source
and disposable-Home test coverage. The new policy content has not been separately
qualified in native sessions, and no model-following or enforced edit-scope claim
is made. `capabilities` identifies the historical loader versions separately from
the unprobed installed version; see the [matrix](runtimes.md#capability-matrix).

The current qualification work distinguishes source tests, native resource loading,
request construction, and completed model behavior. Source/wheel test receipts and
the exact reviewed candidate are recorded with the feature PR; this document does
not replace those receipts.

- **OpenCode `opencode-ai@1.19.4`:** generated Home-root `opencode.json` references
  loaded SOUL, USER, MEMORY, AGENTS and both canonical skill descriptions into a
  captured native system message. A loopback HTTP 400 ended the substantive
  request; the fixture returned only a canned session title to reach that request.
  There was no model conversation. Earlier 2.1.3 receipts are historical, not a
  new acceptance run of that version.
- **Claude Code 2.1.270:** generated `CLAUDE.md` imports and skill aliases loaded
  the same Home canaries into its native request. Claude represents imported
  project instructions in native reminder content; Agent Home did not inject a
  user prompt. The loopback returned HTTP 400. This is loader/request evidence,
  not instruction-following evidence.
- **Codex CLI 0.157.1:** native `debug prompt-input` loaded generated additive
  developer instructions, Home AGENTS and both skill descriptions with explicit
  trust in disposable native state. The untrusted case omitted identity canaries;
  skill discovery still occurred. No provider request was made. Agent Home does
  not grant project trust or replace the built-in system prompt.
- **Maintained Pi `@earendil-works/pi-coding-agent@1.4.0`:** the actual native CLI
  argument parser and resource loader consumed the generated projection and
  skills. Home-root identity loading followed native project trust: it was absent
  when trust was refused and present when granted in the fixture. A separate
  Home/project test passed for B and C, as described below. Executable name alone
  does not establish maintained-package compatibility.

No completed model task, resumed session, compaction, or live config reload is
accepted by these tests. Start a fresh session after refresh unless you separately
qualify the harness's reload behavior.

## Home versus project

Explicit `run --project` adapters are available for all four harnesses. They
select Home identity/AGENTS/skill guidance without copying Home model/provider,
MCP or permission configuration into the project. Native credentials, sessions,
trust and approval settings stay with the harness. The installed version is not
automatically certified by the adapter.

Current separate-project evidence:

- **Codex CLI 0.157.1:** a real native HTTP request contained Home
  SOUL/USER/MEMORY/AGENTS, both canonical skill-description canaries, and the
  separate project's AGENTS canary. The adapter used per-run
  `developer_instructions`; skills were prompt content, not native skill
  registration. `CODEX_HOME` and filesystem permission scope were not expanded.
- **Claude Code 2.1.318:** a real native HTTP request contained the same Home
  canaries and the separate project's CLAUDE.md canary. Home skill content came
  from `--append-system-prompt`, not Claude-native slash-skill registration.
- **OpenCode 1.19.5:** a real native HTTP request contained the same Home canaries
  and the separate project's AGENTS canary using the production inline-resource
  adapter. Existing native inline settings are merged rather than replaced.
- **Maintained Pi 1.4.0:** the earlier actual native parser/resource-loader
  qualification remains applicable to its unchanged adapter. B/C project fixtures
  loaded Home identity, AGENTS and both skill descriptions plus native project
  instructions; a sibling Home's private canary was absent.

Codex/Claude qualification explicitly opts into argv transport using synthetic
public canaries. Real project launches require `--allow-context-in-argv` because
other local users or process monitors may read command-line text; without that
consent, these adapters fail closed before loading private context. Their dry-run
output redacts the context. Pi/OpenCode use file references rather than embedding
the private Home text in process arguments.

The Codex, Claude and OpenCode requests went only to a loopback HTTP fixture,
which deliberately returned HTTP 400. No successful model response or tool
execution was simulated. Each separate project retained exactly its original
files. These are request-construction/resource-selection checks, not evidence of
instruction following, resumed sessions, live reload, or every harness version.

`python scripts/qualify_project_context.py --help` describes the opt-in native
request fixture. It uses fresh synthetic native state and no real credentials;
its report identifies retained synthetic files for inspection. The normal test
suite does not invoke a provider or require native executables.

Codex and Claude inline context is bounded and refused when too large rather
than truncated. Home references outside a project remain subject to native
filesystem permissions. Native-global and project resources can still apply;
these inputs are not a security sandbox or an automatic trust grant.

## Optional memory

The CLI prepares environment-variable credential references in native MCP files;
no credential value is copied into them. Offline verification checks variable
presence, not validity, approval, server availability, or bank authorization.
Missing credentials and unqualified connectivity remain explicit findings.

A synthetic loopback test using Pi's native `@earendil-works/pi-mcp@1.4.0` client
performed initialization, tool discovery, explicit recall, explicitly scoped
synthetic retain, exact-bank readback, and wrong-bank rejection. The controller
reran that probe independently. The server was a protocol fixture, **not a live
Hindsight deployment**. It does not establish native tool approval, Hindsight
persistence/authorization, or end-to-end configuration/credential expansion for
all four harnesses. Live memory remains unqualified. No ordinary test touches a
live bank. Automatic recall/retention is now separately opt-in; these older native
receipts do not qualify its execution.

New automatic-memory tests exercise the actual Python helper against a synthetic
HTTP MCP server, including initialization/session headers, JSON/SSE recall,
prompt/reply retention, duplicate suppression, redirects, bounds and sanitized
failures. Generated Pi/OpenCode code is executed against fake lifecycle APIs with
a stub helper, including cancelled runs and tool-output filtering. Configuration
tests cover opt-in/out, unrelated hook preservation, owned-hook conflicts and
concurrent flag updates. These are protocol/adapter fixtures, not native harness,
model, or live Hindsight acceptance. Pi's new adapter references 1.5.2 lifecycle
source, and OpenCode automation targets the v1 plugin API only.

## Reproduce the opt-in OpenCode/Claude check

Install the qualified native packages yourself; the script does not install or
upgrade anything. Supply explicit executable paths and exact version strings:

```sh
PYTHONPYCACHEPREFIX=/path/to/private-cache python3 scripts/qualify_native.py \
  --opencode-path /path/to/opencode --opencode-version 1.19.4 \
  --claude-path /path/to/claude --claude-version '2.1.270 (Claude Code)' \
  --home-root-only --evidence /path/to/private-evidence.json
```

The script generates disposable Homes using the real CLI library and rebuilds
the native subprocess environment with fake credentials. Omit `--home-root-only`
only for the exploratory OpenCode project checks; unmet project acceptance returns
nonzero and is not a release success. Evidence contains synthetic request bodies,
not credentials. Ordinary unit tests never invoke native runtimes.

## Existing-Home migration

No live Home is migrated by installing this release.

1. Stop the Home's native sessions. Back up the complete Home in approved private
   storage; ignored private runtime state is not covered by Git history.
2. Run `soulsteads verify /path/to/home` for a read-only preview of stale or missing
   adapters. For a rehearsal, use an isolated private copy, not the live Home.
3. Run `soulsteads config /path/to/home --sync` explicitly. Keep external editors
   quiescent and obey the [publication contract](publication-contract.md).
4. Inspect `git -C /path/to/home diff` locally. Resolve managed conflicts manually;
   there is no force option. Commit only the reviewed, authorized change.
5. Start the selected native harness and complete its own project-trust and MCP
   approval steps. Confirm identity/skills without changing permission policy.
6. If necessary, restore a reviewed tracked snapshot with `soulsteads revert` as a
   new commit. Do not reset history. Recover ignored runtime/private state from the
   private backup only under separate explicit authority.

A partial-publication error is not a rollback. Review its applied/remaining paths
before retrying. Git restore and skill installation are separate non-concurrent
lifecycle operations; the publication lock is not a lock for arbitrary editors or
all Git/native processes.
