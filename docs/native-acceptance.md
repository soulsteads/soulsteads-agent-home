# Native acceptance and release limits

Agent Home prepares native files. It does not run an agent loop, enforce prompt
instructions as permissions, grant trust, or certify model behavior. These checks
use synthetic data and isolated native state. No real agent migration or live
Hindsight bank is part of acceptance.

## Versioned native evidence

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

`run --project` is supported only for the qualified maintained Pi version above.
The selector passes native `--append-system-prompt` paths for Home identity and
Home AGENTS, and native `--skill` paths for canonical Home skills. The project is
the process cwd. Authentication, native state, model/provider settings and MCP
selection stay with the harness; Home MCP configuration is **not** carried into
project mode. The installed binary version is not automatically probed.

Clean, isolated B/C fixtures demonstrated all of these conditions:

- Home A SOUL/USER/MEMORY/AGENTS and both skill-description canaries loaded.
- The corresponding B/C project AGENTS loaded through native discovery.
- A sibling Home D private canary was absent, with no real user-home resource paths.
- B/C contained only their original AGENTS file after loading; no Home files,
  links, native configuration, or authentication files were copied into them.

These are native resource-loading tests, not a sandbox or model-behavior test.
Global/project native resources can still apply during normal use.

Other project selectors are deliberately unqualified in this release:

- OpenCode explicit custom configuration carried Home identity and project rules,
  including a project-config instruction addition. The attempted combination did
  not discover Home skills and modified the disposable project inventory. It did
  not meet the untouched-project acceptance gate.
- Claude 2.1.270 predates current documented native AGENTS support. Newer
  additional-directory mechanisms need their own precedence/trust qualification.
- Codex additive overrides alone did not establish complete Home operating-guidance
  and canonical-skill selection. Moving `CODEX_HOME` into the definition would also
  move runtime/authentication state, so that is not an accepted workaround.

Do not infer that these mechanisms can never work. They are not accepted adapters
here. Home-root invocation remains available for all four qualified versions.

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
live bank, and no automatic ingestion, recall injection, or retention is enabled.

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
