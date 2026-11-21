# Native compatibility and release limits

Agent Home prepares native configuration. The harness owns trust, permissions,
tools, sessions, and model execution. `verify` checks files and reports known
compatibility limits; it does not run the harness or prove that it will load a
setting. See the [runtime guide](runtimes.md) and [install and recovery guide](installation.md).

## Home versus project

Home-root launch uses native resource discovery. Bounded checks have exercised
loading or request construction in OpenCode, Claude Code, Codex, and maintained
Pi. Separate-project launch uses [per-run native inputs](runtimes.md#separate-project-launch).
Codex and Claude require explicit consent to expose Home context in process
arguments. Dry-run redaction does not prevent that exposure during real launch.
None of these paths is a filesystem sandbox.

Prior native checks include completed Codex and Claude tasks and clean-exit
continuation for specific versions. They do not establish live reload, crash
recovery across harnesses, or behavior with every model. Pi checks observed
native loading and changed settings, not a completed two-session task. Start a
fresh session after changing configuration.

## Optional memory

Home writes credential-variable references, not credential values. `verify`
checks variable presence offline; it does not test connectivity, MCP approval,
or authorization. Bounded checks with Codex 0.169.0 and Hindsight 1.2.1 exercised
explicit retain/readback, fresh-session recall after restart, and denial by a
separately scoped service. They do not qualify automatic callbacks, other
harnesses, or per-bank credential isolation. See the
[per-principal isolation guide](runtimes.md#per-principal-memory-isolation-with-hindsight-121).

## Messaging and the optional native harness

The [Messaging integration](runtimes.md#launch-through-messaging) uses a
separately installed backend. In the qualified Matrix path, follow-up text
queues in memory rather than steering the current turn. Cancellation can discard
pending text; it does not undo completed writes or prove that the provider has
stopped. Restart does not restore the queue. These checks do not qualify other
connectors or harness versions.

## Reproduce the opt-in OpenCode/Claude loader check

Supply explicitly installed test binaries and exact version strings. The probe
uses disposable Homes, synthetic credentials and a local error endpoint. It does
not qualify inference or a live account.

```sh
PYTHONPYCACHEPREFIX=/path/to/private-cache python3 scripts/qualify_native.py \
  --opencode-path /path/to/opencode --opencode-version 1.19.4 \
  --claude-path /path/to/claude --claude-version '2.1.270 (Claude Code)' \
  --home-root-only --evidence /path/to/private-evidence.json
```

## Existing-Home migration

Installing the CLI does not migrate a live Home.

1. Stop native sessions and back up the entire Home privately. Git does not
   cover ignored runtime state, credentials, or sessions.
2. Run `soulsteads verify /path/to/home` to inspect the current state. Rehearse
   against a disposable copy before changing an existing Home.
3. Run `soulsteads config /path/to/home --sync` explicitly with other editors
   and writers stopped. See the [publication contract](publication-contract.md).
4. Inspect the local Git diff, resolve conflicts without force, and commit the
   reviewed change. Start a fresh native process and complete its normal trust
   and MCP approval steps.
5. To recover tracked files, run `soulsteads revert /path/to/home REVISION`
   with the reviewed prior commit ID. Restore creates a new commit, not a reset.
   Recover ignored state separately from the private backup.

A partial-publication error is not a rollback. Inspect applied and remaining
paths before retrying. The publication lock is not a lock for arbitrary
editors or all Git and native processes.

## Witnessed migration-readiness checks

The import readiness report is a portable-file plan plus a manual acceptance list,
not a runtime result. Preview and import leave every runtime check at `not_run`.
The separate `soulsteads verify` report is offline-structural; its overall
`passed` status covers only local structural checks and cannot promote a readiness
check. `passed` for a runtime check requires direct evidence from the target
runtime; use `failed` only for an observed failure. Static configuration, file
presence, mocked tests, a successful import, or a network/permission setting cannot
establish provider identity, route ownership, tool availability, or isolation.

Run these checks only in a disposable, private target environment with synthetic
content. Keep detailed evidence private and outside the public report.

1. **Identity and instructions:** Start the native runtime with a synthetic profile.
   Confirm that it loaded the intended identity and instructions, not merely that
   the files were copied. Use a harmless synthetic marker and compare the runtime's
   observed context with the expected marker.
2. **Workspace:** Select a disposable workspace containing a distinct synthetic
   instruction marker. Confirm that the native runtime uses that workspace and does
   not silently fall back to another one.
3. **Skills:** Confirm that each selected skill is discoverable by the native
   runtime, then run only a harmless, deterministic synthetic check. File presence
   alone does not pass this check.
4. **Required tool/MCP dependency:** If a required tool or MCP server is selected,
   invoke each required tool/MCP dependency with a harmless, bounded operation in
   a private test environment and observe the actual result and authorization
   boundary. Do not use a live write, account, or external destination.
5. **Provider identity and fallback:** Observe the provider identity for a harmless
   synthetic request. If fallback is required, trigger a controlled provider
   failure before any output, then observe which fallback provider/model answers
   and confirm no earlier output was emitted. Skip this check only when fallback
   is not required; a configured fallback name is not evidence of correctness.
6. **Chat ownership and routing:** Verify account ownership and the intended route
   with a private test account and destination. Confirm one synthetic message reaches
   only that destination. Do not connect a live messaging channel as part of import.
7. **Permissions and network boundary:** Exercise one intended allow and one intended
   deny case in an isolated environment, observing the actual operation and result.
   A static policy file or local network availability is not a pass.
8. **Hindsight scope:** Only if external memory is selected, write a non-sensitive
   synthetic marker to a fresh isolated scope and retrieve it from a new session in
   that same scope. Then query it from a separate synthetic scope and confirm the
   request is denied or returns no data. Remove the synthetic test store afterward.
   Do not use actual bank data, personal records, or retention history.

Portable identity/instructions, workspace files, and skills are distinct from
native sessions, OAuth, messaging connections, schedules, Vault entries, Hermes
transcript history, and Hindsight records. Those items are deliberately not
transferred. This checklist does not establish a private migration proof until a
reviewer witnesses the named target-runtime checks.
