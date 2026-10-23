# Soulsteads Agent Home Native Compatibility Implementation Plan

> **For Hermes:** Use the subagent-driven-development skill to implement this plan task-by-task after implementation is authorized. Keep one writer for each source area and obtain independent specification and code-quality review.

**Goal:** Make one inspectable Agent Home reliably define an agent's identity, skills, workspace conventions and optional memory connections through configuration consumed by OpenCode, Pi, Codex and Claude Code.

**Architecture:** Agent Home maintains canonical content and prepares small native adapters. The harness owns execution, tools, permissions, sessions and compaction. Prefer native references to canonical files; generate explicitly owned projections only where necessary. There is no resident Soulsteads agent loop or prompt-interception layer.

**Tech stack:** Existing Python 3.11+ CLI and standard library, existing local Git lifecycle, Markdown/Agent Skills, native JSON/TOML configuration, optional maintained YAML support and optional MCP memory tools. No new mandatory service or framework.

**Status:** Implementation authorized on `feat/agent-home-plan`, created from fetched `origin/main` at `4cc2cb605d2ac02ded03aee8a3163de7f36b898f`. The rejected candidate is preserved separately. Implementation and qualification results are recorded below as they are verified; this is not permission to migrate live agents or merge the feature branch.

## Execution record

- Task 0: complete. Both remaining races reproduced through the CLI. The bounded spike verified absent-file no-clobber using descriptor-relative hardlink publication and retained-directory write isolation. The reviewed contract explicitly excludes arbitrary concurrent editor writes to existing files; stat/hash plus replace is not atomic compare-and-swap.
- Tasks 1–2: shared checked publication and coexisting native adapters implemented. The controller reproduced and repaired the two original races, retained-lock root rebinding, previously published output drift, unsafe published-output reads, staging cleanup and final-boundary error reporting. The source suite passes 158 tests with lint/diff checks; frozen review remains a separate gate.
- Task 3: maintained Pi 1.4.0 Home A/project B/C selection passed clean native parser/resource-loader checks with unchanged projects and no sibling/private-user-home leakage. Other project selectors are explicitly unqualified and rejected; Home-root loading is qualified for all four named versions.
- Task 4: instruction workflows implemented and source-tested (12 template/disposable-Home tests, including real skill validation and focused new-commit rollback); model behavior remains unqualified.
- Task 5: native MCP configuration and offline credential/qualification reporting implemented. Pi's native MCP client passed synthetic recall/retain/exact-bank readback and wrong-bank rejection. Live Hindsight, native approval and end-to-end tools across all harnesses remain unqualified; no ingestion or automation is enabled.
- Task 6: Home-root OpenCode/Claude request captures, Codex trust/prompt checks and Pi trust/resource checks passed without model/provider calls. Installed-wheel acceptance passed 27 checks with optional YAML absent and present, including synthetic import. See the native acceptance guide for version and evidence boundaries.
- Task 7: independent frozen review, exact remote revision/CI checks and owned-artifact cleanup govern branch delivery. The feature PR records final review/publication receipts. No main merge or live rollout is included.

See [the publication contract](docs/publication-contract.md) and [runtime guide](docs/runtimes.md) for current supported boundaries. Final release evidence belongs to the exact reviewed candidate, not the historical counts below.

---

## 1. Product outcome and boundaries

Home should answer: which agent is this, what instructions and skills apply, what may it connect to, and how does the chosen harness consume that definition?

- One Home defines one agent, not one project or one conversation.
- `SOUL.md`, `USER.md`, `AGENTS.md`, `MEMORY.md` and `skills/` remain understandable, editable sources. A generated file is not a second source of truth.
- Direct native invocation from the configured Home must work without `soulsteads run` injecting identity. The launcher remains optional convenience.
- Agent identity, target project, runtime state and external memory remain distinct. Native config selection may be necessary outside the Home; bare invocation from every arbitrary directory is not promised.
- Workspace instructions describe working conventions. Actual filesystem and tool restrictions belong to the harness/OS; never describe a directory path or prompt as a sandbox.
- Agent Messaging remains optional and independently usable. Home does not acquire transport, conversation bindings or native-session ownership.
- Forge or another memory service can own durable memory/automation. Home records supported connections, not a second copy of service-owned state.
- Native permissions, user authentication and global settings must not be weakened or silently rewritten.

**Non-goals:** universal runtime API, model-serving stack, native session conversion, automatic transcript ingestion, background learning daemon, scheduler, plugin marketplace, live profile cutover or broad repository cleanup.

## 2. Starting point: reuse rather than rebuild

Repository: https://github.com/soulsteads/soulsteads-agent-home

The investigated checkout has base `4cc2cb605d2ac02ded03aee8a3163de7f36b898f` and local branch `feat/native-harness-config`. Existing uncommitted changes include native projections, refresh/verification, optional Hindsight configuration and portable skill guidance. Preserve these changes and their rejected-candidate evidence; do not reset the checkout or start another worktree without approval.

Observed qualification of that candidate:

- Baseline: 91 tests; candidate: 131 tests passing, plus lint and installed-wheel checks. These counts are historical receipts, not future acceptance targets.
- Native identity/skill loading was exercised across all four harnesses. Some checks captured a request sent to a loopback fixture that deliberately returned HTTP 400; they were not successful model conversations.
- Native MCP registration/schema checks were exercised. Live Hindsight calls, retention, fresh/resumed model sessions and compaction behavior were not accepted.
- Two remaining write defects were independently reproduced: late-created unrelated MCP settings can be lost, and runtime selection can follow a replaced Home root and overwrite an external manifest.
- Passing aggregate tests did not establish safe publication. The earlier repairs and review receipts remain evidence, not approval of a later candidate.

Retain useful adapter work, skill templates, installed-package checks and deterministic regressions. Selectively replace the divergent configuration-publication path; do not rewrite the whole CLI.

## 3. Native compatibility contract

Record package identity, version, mechanism and observed proof per capability. Do not infer equivalence from an executable name or similar filenames.

- **OpenCode:** native `opencode.json` instruction references; native skill discovery; native MCP configuration. Qualification covered 1.19.4 and 2.1.3, whose diagnostic surfaces differ.
- **Claude Code:** native `CLAUDE.md` imports, `.claude/skills/` discovery and project `.mcp.json`; MCP approval remains a separate native step. Qualification covered 2.1.270.
- **Codex:** project `AGENTS.md`, native skills and generated additive `developer_instructions` in `.codex/config.toml`. Do not replace built-in instructions through `model_instructions_file`. Qualification covered 0.157.1 and does not bypass project trust.
- **Pi:** additive `.pi/APPEND_SYSTEM.md` projection and native skills. Maintained `@earendil-works/pi-coding-agent` 1.4.0 passed the native MCP validator; deprecated `@mariozechner/pi-coding-agent` 0.73.1 did not provide that native MCP surface. Old-package research is not the maintained-package result.

Classify each result as native reference, generated native projection, instruction-only convention, unsupported, or unverified. Also record whether it is source-tested, native-loader-tested or behaviorally exercised. Recheck current official documentation before implementation; these versioned observations are not a promise about all releases.

## 4. Ownership and update rules

- Canonical documents and skill bodies are user-maintained. Memory is reference material, not permission to replace identity, instructions or policy.
- Generated identity projections are marked and reproducible. Explicit refresh follows source edits; verification reports stale projections without repairing them.
- Native files may also contain user-owned settings. Preserve unrelated keys, servers, hooks and model/permission settings. Reject conflicting managed edits rather than silently restoring them.
- Changing the default harness must not remove other adapters or rewrite custom native files. Keep runtime selection separate from refresh intent, even when both use the same publication mechanism.
- Store credential references only. Keep secrets, native sessions, private import receipts, caches and transcripts outside the shareable Git definition.
- Prefer native includes and dedicated generated outputs over repeatedly rewriting shared configuration. Do not invent undocumented include keys or local-overlay filenames to avoid a hard problem.

## 5. Delivery sequence

### Task 0 — Pin evidence and select the publication contract

**Files:** inspect `soulsteads/core.py`, `soulsteads/native_config.py`, `soulsteads/hermes_import.py`, `soulsteads/cli.py`, `tests/test_native_security.py` and the existing importer publication tests.

1. Record the actual branch, diff, source hashes and installed tool versions. Preserve unrelated work and existing evidence.
2. Inventory every affected producer: Home creation, runtime selection, native refresh and import finalization. Trace verification and Git restore as consumers/lifecycle boundaries; do not silently expand a refactor into rewriting all Git behavior.
3. Turn the two remaining synthetic race probes into regressions through real CLI paths, not only helper calls. Observe genuine failures on the rejected implementation.
4. Run a bounded publication spike before choosing an abstraction. Reuse qualified directory-descriptor/no-follow/absent-publication primitives where appropriate.
5. State the supported concurrency/platform contract. A lock serializes cooperating Home writers; it does not stop an arbitrary editor or same-UID process. A stat/hash check followed by `os.replace` is not atomic compare-and-swap.
6. Prefer avoiding shared-file replacement. For unavoidable existing-file merges, prove the selected mechanism or explicitly narrow ownership/support and obtain review before implementation. Do not promise preservation against arbitrary concurrent writers on unsupported primitives.

**Exit gate:** a small written writer/consumer map, failing reproductions, selected mechanism, platform behavior and honest limitations. No new mandatory dependency, state contract or reduced guarantee is silently introduced.

### Task 1 — Consolidate configuration publication

**Files:** modify `soulsteads/native_config.py`, `soulsteads/core.py`, relevant `soulsteads/cli.py` routes and importer finalization; add `soulsteads/publication.py` only if the spike justifies one small shared internal module. Extend `tests/test_native_security.py`, `tests/test_native_config.py`, `tests/test_safety.py` and `tests/test_cli.py`.

1. RED: cover runtime-only selection, native refresh, Hindsight add/update/remove and import finalization through their public paths.
2. Admit the manifest, canonical sources, Home identity and destination expectations once through retained safe bindings; bound reads and reject unsupported filesystem objects.
3. Build a complete pure change plan before writes: validated relative destination, expected absence or admitted old state, intended bytes and ownership. Renderers must not choose arbitrary paths.
4. Publish using the same checked mechanism for every affected configuration mode. Preserve absence with a proven no-clobber primitive; reject late destination changes according to the reviewed contract.
5. Verify published bytes and requested root/parent bindings before success. Do not exclude an output from integrity checks merely because it was published.
6. Report partial application honestly if a multi-file update fails. Preserve source/custom settings and make reconciliation/retry explicit; do not claim whole-Home atomicity without proof.
7. GREEN: run focused regressions, then the complete suite and lint. Remove or make unreachable the unsafe fallback for these configuration paths; retaining an alternate unchecked route is not consolidation.

**Exit gate:** no outside read/write under the tested rebind cases, no lost unrelated late-created settings, no false-success content drift, and exact error/retry behavior. Independent review must accept the new contract.

### Task 2 — Finish the smallest reliable native identity release

**Files:** `soulsteads/runtimes.py`, `soulsteads/native_config.py`, `soulsteads/core.py`, `soulsteads/verification.py`, `soulsteads/hermes_import.py`, `tests/test_runtimes.py`, `tests/test_native_config.py`, `tests/test_core.py`, `tests/test_verify.py` and importer tests.

1. RED: create a Home for each launch default and prove all supported adapters coexist. Changing the default preserves the other files and unrelated settings.
2. Prove canonical SOUL/USER/MEMORY edits reach generated projections only through explicit refresh. Prove repeat refresh is a no-op and managed conflicts are actionable errors.
3. Remove identity-attachment injection from Pi launch. Keep Claude/OpenCode native references and Codex/Pi generated additive projections version-qualified.
4. Extend the existing verifier rather than adding a competing doctor: exact adapter paths, stale state, skill aliases, mechanism, required trust/reload and unsupported version status. Do not silently repair.
5. Test legacy-home upgrade and import-produced identities through the same contract. No automatic global installation or private-profile migration.

**Exit gate:** direct native loading from the Home is reliable, inspectable and independently reviewed. This is the first release-sized milestone; workspace expansion and memory automation are not prerequisites.

### Task 3 — Separate agent identity from the target project

**Files:** assess `soulsteads/cli.py`, `soulsteads/runtimes.py`, `soulsteads/verification.py`; add focused workspace tests to `tests/test_runtimes.py` and `tests/test_verify.py` before adding any public option.

1. In disposable Home A and projects B/C, investigate each harness's supported native config selection and project-instruction precedence. Do not move its authentication/session home merely to select an identity.
2. RED: launch in B and then C; agent identity remains A, the corresponding project AGENTS/rules remain effective, and a sibling Home's private canary is absent.
3. Add only native mechanisms actually demonstrated. A convenience launcher may select native flags/environment; it must not emulate the agent loop or inject missing identity as a chat message.
4. Leave B/C untouched: no personal SOUL/USER copies, overwritten project AGENTS or silent global configuration. Report unsupported combinations explicitly.

**Exit gate:** tested Home-versus-project behavior per harness. Until then advertise Home-root mode only, not universal working-directory independence.

### Task 4 — Make learning useful without inventing a learning runtime

**Files:** `soulsteads/templates.py`, `soulsteads/core.py`, `tests/test_skill_maintenance.py`, `tests/test_core.py` and `tests/test_safety.py`.

1. Keep the original portable `skill-maintenance` starter. Qualify discovery and supporting assets with native tools, not Hermes-only APIs.
2. Add small remember/correct/learn/handoff procedures only where they add distinct value. Keep facts, preferences, procedures and work checkpoints separate.
3. RED: propose by default; apply only explicitly authorized or narrowly preapproved changes. An improvement request must not silently edit SOUL, permissions, credentials, plugins or schedules.
4. Verify one correction and one reusable procedure update in a disposable Home. Show a reviewable diff and actual validation; do not measure learning by files created or tool calls made.
5. Keep learning modes off/propose/scoped-apply explicit. File-backed curated memory and service-owned projections must not become competing writers.

**Exit gate:** the harness can use and maintain a skill with clear approval and rollback. No claim of autonomous self-improvement from a template alone.

### Task 5 — Qualify optional Hindsight tools, not automatic ingestion

**Files:** `soulsteads/runtimes.py`, `soulsteads/native_config.py`, `soulsteads/verification.py`, `tests/test_hindsight_config.py` and `docs/runtimes.md`.

1. Keep the no-memory-service path usable. Require an explicit server/bank URL and credential-reference name; never copy a token into native config, source, Git or logs.
2. RED: safe add/update/remove, missing environment value, native approval pending, wrong bank, unavailable server and unrelated MCP entries remaining unchanged.
3. Use native MCP registration per qualified package/version. An old Pi without native MCP is unsupported for this slice; a reviewed maintained extension would be a separate later choice.
4. In an isolated synthetic service/bank, verify actual discovery, an explicit recall and an explicitly authorized retain, then read back the exact bank. A mock MCP fixture proves protocol behavior, not a live Hindsight deployment.
5. Keep transcript ingestion, recall injection, automatic retention, personal/work bank migration and global coding-agent installers out of scope. Later automation needs a separately accepted ownership/privacy/lifecycle plan.

**Exit gate:** explicit tools work with honest failure/approval reporting, or the capability stays marked unqualified. No live bank is touched by ordinary tests.

### Task 6 — Version-pinned native acceptance and installed-package checks

**Files:** extend tests with a small opt-in qualification harness only where needed; maintain `docs/runtimes.md` and `README.md`. Do not create a second runtime test framework.

1. For each claimed package/version, use isolated HOME/XDG/native state and private disposable fixture parents. Scope environment per subprocess rather than persistent exports.
2. Distinguish generated-file tests, real native loading, captured request construction and completed model behavior. Deliberate loopback HTTP 400 is not successful generation.
3. Capture fresh-start canaries and skill metadata. Qualify resume, compaction and config reload separately before advertising those behaviors; otherwise state the limit.
4. Test trust refusal, precedence conflicts, missing optional dependencies and direct launch without the Soulsteads launcher. Use documented native commands for the actual version, not obsolete diagnostics.
5. Build/install the wheel outside the source tree and exercise ordinary commands with optional YAML absent, then the supported YAML path separately.
6. Record helper processes. OpenCode v2 diagnostics can start a detached service even without provider calls. Stop only task-owned helpers after exact identity checks; preserve existing gateways/services.

**Exit gate:** a version/capability/evidence matrix, corresponding source and wheel identity, and no inference or lifecycle claims beyond the executed checks.

### Task 7 — Review, publish and clean one bounded milestone at a time

**Files:** documentation and focused release changes only; preserve unrelated source and existing workflows.

1. Freeze the candidate and collect independent spec and security/code review. Reproduce material findings and renew affected checks after edits.
2. Keep a bounded repair budget; reassess the design rather than continuing an unlimited sequence of narrow patches.
3. Publish only an accepted coherent slice. Verify exact remote PR head and CI; merge or live rollout requires its own applicable authority. Documentation is not permission to deploy.
4. Make an existing Home migration explicit and reversible, with backups, a dry-run/diff, supported trust actions and post-change native checks. Never test against a real profile by default.
5. Preserve source, review reports and recovery artifacts. Remove owned inactive build/dependency/cache outputs only after refreshed process/file/mount checks; verify absence and measured free-space change. Record retained paths and their cleanup conditions.

**Exit gate:** reviewed source is published only when authorized; installed/running/externally verified status stays separate. No outstanding blocker is hidden by a green aggregate count.

## 6. Verification commands and fault matrix

Existing source checks (run during authorized implementation, not as part of this plan filing):

```sh
PYTHONPYCACHEPREFIX=/tmp/soulsteads-plan-checks python3 -m unittest discover -s tests -p 'test_native_security.py' -v
PYTHONPYCACHEPREFIX=/tmp/soulsteads-plan-checks python3 -m unittest discover -s tests -p 'test_native_config.py' -v
PYTHONPYCACHEPREFIX=/tmp/soulsteads-plan-checks python3 -m unittest discover -s tests -p 'test_hindsight_config.py' -v
PYTHONPYCACHEPREFIX=/tmp/soulsteads-plan-checks python3 -m unittest discover -s tests -v
python3 -m ruff check --no-cache soulsteads tests
git diff --check
```

Expected after a completed implementation: selected regressions and full suite pass; lint/diff checks pass. Do not invent a future test count or credit fixture/import/setup failures as behavioral REDs. Record the exact test code and both failure/pass outputs.

Required fault cases:

- Missing versus existing destination, including a late-created unrelated MCP server.
- Owned-setting removal/replacement versus unrelated additions; Hindsight add/update/remove.
- Root, parent and source-leaf replacement; symlink, hardlink, special-file and changed-byte cases.
- Manifest changed during admission; source/output mutation after staging; published-content drift.
- Failure before publication, between files and after publication; explicit partial-state/retry reporting.
- Runtime-only selection and import finalization, not just the native-sync helper.
- Absent/wrong trust, unavailable memory tool, unsupported package/version and native reload boundaries.
- Project rules surviving Home selection, plus no cross-Home private canary leakage.

## 7. Decisions and release order

Recommended order: **safe configuration preparation → reliable Home-root native loading and inspection → target-project separation → reviewed learning workflows → qualified optional memory → later opt-in automation**.

The publication spike must settle filesystem concurrency/portability before implementation expands. Target-project support is advertised only per proven native mechanism. Automatic memory collection and executable extensions remain separate decisions. New dependencies, permission expansion or durable schema changes require review rather than being smuggled into a compatibility fix.

Keep the existing Home manifest reader-compatible where possible. Do not invent a new public schema or capability status enum without tracing all readers and documenting migration. Extend reports additively and retain precise unsupported/unverified outcomes.

## 8. Official references to recheck

- https://opencode.ai/docs/config/
- https://opencode.ai/docs/rules/
- https://opencode.ai/docs/skills/
- https://opencode.ai/docs/mcp-servers/
- https://code.claude.com/docs/en/memory
- https://code.claude.com/docs/en/skills
- https://code.claude.com/docs/en/mcp
- https://developers.openai.com/codex/config-reference/
- https://developers.openai.com/codex/guides/agents-md/
- https://github.com/earendil-works/pi/tree/main/packages/coding-agent/docs

These references are configuration authority, not evidence that an unexecuted feature is working.

---

## Historical Hermes import plan — retained reference

The following earlier plan is preserved verbatim as historical context. Its implementation and acceptance claims are not approval of the current native-configuration candidate.

````markdown
# Hermes import feature

## Scope and decisions

Add direct imports from an explicitly selected local Hermes home/profile into a
fresh, private Soulsteads agent home. Inspection is read-only by default;
`--apply` creates files and local Git history but never starts a runtime or
transfers live ownership. Ordinary commands remain standard-library-only. The
importer uses the approved optional `hermes` extra for maintained YAML parsing.

```sh
soulsteads import-hermes helper --source /path/to/hermes-home \
  --profile default --runtime opencode --path /path/to/new-home
```

The public Home format and existing runtime adapters remain authoritative. Reuse
ordinary Home creation and Git operations rather than importing the older private
manager's profile schema. Nonportable settings require explicit partial-import
acknowledgement, not silent translation or permission broadening.

## Implemented boundaries

- Explicit source/profile selection; no active-profile or missing-profile fallback.
- Supported identity/memory documents and enabled local skill selection.
- Standard Agent Skills conversion with native discovery aliases, unchanged body
  and supporting assets, and explicit native-tool portability guidance.
- Profile-local Hindsight configuration detection and private reference capture.
- Private ignored source configuration, import receipt, and opt-in `.env` reference.
- Metadata-only public reports; absolute provenance paths stay in the private receipt.
- Strict YAML parsing, bounded no-follow reads, source-change detection and absent
  destination publication without overwrites.
- Linux-only atomic apply; unsupported publication platforms fail closed.
- No source execution, source writes, model requests, service starts, or live handoff.

## Verification and delivery gates

Use synthetic profiles only. Exercise failing then passing tests for creation,
skill selection, identifier fidelity, publication collisions, source changes,
receipt accuracy, and private report boundaries. Run the full suite and lint.
Build the wheel and test installed commands both with and without the optional
extra, outside the source checkout. Review the final candidate independently,
then publish through a feature-branch PR and verify the remote revision.

See [the import guide](docs/hermes-import.md) for exact commands and limitations.
This plan is not authorization to import a real private profile or activate it.

## Remaining owner decision

Explicit native MCP bank tools are now the bounded setup path described above.
Automatic Hindsight migration/retention/injection remains unimplemented. A future
maintained coding-agents dependency/native-hook integration needs separate scoped
qualification before changing durable memory behavior. Global install commands
are not safe project-local import steps. Import reports keep automatic Hindsight
setup as an omission, never an activation-ready claim.

## Non-goals

OAuth/refresh-token migration, native session conversion, remote-memory data,
scheduler conversion, live bridge handoff and cross-runtime permission equivalence
are not implemented by file import. External/conditional/organization skill
discovery requires explicit manual review and partial-import acknowledgement.
Source profiles and existing consumers remain unchanged. Only synthetic data
belongs in this public repository and its tests.
````
