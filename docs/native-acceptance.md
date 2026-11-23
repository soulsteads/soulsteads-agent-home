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

## Reviewed skill edits in external harnesses

A Linux rehearsal used a disposable Home with learning set to `propose` and a
synthetic skill containing a unique shipment code. Pi 1.6.0 read the original
code in a model turn. The installed Home CLI previewed and applied one change.
A fresh Codex 0.171.0 session returned the revised code with a local model.
A separate Codex session ran `soulsteads skill review .` with the skill name
inside its read-only sandbox and returned the same review ID as an independent
operator preview. The second proposal left the skill untouched.

OpenCode 2.4.0 and Claude Code 2.1.330 each returned the revised code in a
fresh session with the skill file explicitly referenced. Requests to the local
Qwen2.5-1.5B-Instruct model included both the Home learning policy and the new
skill body. OpenCode also called its native `skill` tool for the correct skill;
the completed tool result contained the revised body. A separate OpenCode run
without the explicit reference timed out. On a command-recall question, the
small model in Claude Code suggested an invalid `--review-id` flag. Preview
takes no ID; only apply takes `--apply REVIEW_ID`.

To repeat the check, install the candidate CLI, create a disposable Home and
install a synthetic skill with a unique response in its body. Ask Pi for the
response using `/skill:NAME`. Follow the [skill review example](runtimes.md#review-one-skill-change-across-harnesses)
to change it, then ask a fresh harness for the response without putting the
answer in the question. For a read-only sandbox, start in the Home root and
use `.` as the Home argument. Compare an in-session preview with the same JSON
run by the operator. Supply a separate model endpoint or normal harness account
for each live test.
