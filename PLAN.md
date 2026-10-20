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

Automatic Hindsight setup is requested but not complete. Choose the maintained
coding-agents dependency/native hooks versus memory-bank tool access only before
adding dependencies or changing durable memory behavior. Existing global install
commands are not safe project-local import steps. Until scoped wiring is qualified,
Hindsight is an explicit reported omission, never an activation-ready claim.

## Non-goals

OAuth/refresh-token migration, native session conversion, remote-memory data,
scheduler conversion, live bridge handoff and cross-runtime permission equivalence
are not implemented by file import. External/conditional/organization skill
discovery requires explicit manual review and partial-import acknowledgement.
Source profiles and existing consumers remain unchanged. Only synthetic data
belongs in this public repository and its tests.
