# Native-file publication contract

Native sync holds the cooperative lock on the initially opened Home and retains
that root descriptor through admission and publication. Bounded configuration
content reads are relative to that descriptor, so replacing the pathname cannot
redirect canonical/manifest content reads or writes to a different Home. The
pathname is also rechecked against the retained root identity before publication
boundaries.

Each output is recorded with the exact intended UTF-8 bytes and the published
file identity. Sync rechecks all admitted inputs, all previously published
outputs, destination parents, and the root after every file publication and at
the final success boundary. The manifest remains the last publication. Any
failure after a publication is reported as partial; no rollback is claimed.
Fresh native-projection publication applies the same retained-root and
previous-output checks; it does not make the surrounding creation lifecycle atomic.

These checks protect against pathname rebinding and detect observed changes;
they do not sandbox a hostile same-UID process able to race mutable Git/tree
metadata or mutate a file in the final interval between checks and syscalls.
External editors must remain quiescent during publication. The cooperative
lock serializes cooperating Soulsteads configuration writers only.

## Mechanism and platform

- Ordinary configuration publication requires POSIX no-follow directory
  descriptors, hardlink publication and `flock`. Missing lock support is an
  actionable error, not an unlocked fallback. Linux is exercised locally; the
  repository CI also targets macOS. Native Windows publication is unqualified.
- A persistent, private, single-link lock inode lives in `.git/`. It is never
  unlinked after release. Unsafe existing locks are rejected, not repaired.
- An admitted absent destination uses atomic no-clobber `link` from a staged
  private file, followed by removal of the staging name. A late entry is
  preserved and produces an error. There is no overwrite-capable fallback.
- Existing leaves use a checked replacement under the cooperative lock. Checks
  and replacement are not atomic compare-and-swap. Unrelated native settings
  are preserved by preflight merging only within this quiescent-editor contract.
- Files and containing directories are fsynced. Published identity/type checks
  precede content reads. A failed stage is removed only when its inode is owned
  by the operation. Earlier successful outputs are checked again before success.
- The manifest is last, not a transaction commit marker. A crash or error may
  leave native files and ownership metadata out of step; inspect the reported
  applied/remaining paths, preserve custom edits, then explicitly reconcile.
  No automatic rollback or crash-atomic whole-Home guarantee is provided.

## Producer and consumer boundaries

- `core.create` uses the shared checked publisher for fresh native projections
  and the manifest. Canonical-file initialization and Git initialization remain
  non-concurrent lifecycle operations; ordinary creation is not an atomic outer
  directory publication and must not be read or externally edited mid-creation.
- Runtime-only `core.configure` uses retained-root admission and the same file
  publisher without refreshing native projections. The clean-tree requirement
  remains; runtime selection does not erase another adapter's custom settings.
- `native_config.sync` handles explicit refresh and Hindsight add/update/remove
  through one pure native-file plan followed by checked publication.
- Import finalization refreshes imported identity through that same path before
  the existing Linux-only, no-replace outer-directory publication. Private
  reference copying and outer import lifecycle retain their own existing checks.
- Verification reads without repair; native harnesses are independent consumers
  and must be stopped during updates if they require a consistent file set.
- Git commit/restore and skill installation retain their separate non-concurrent
  lifecycle contracts. The configuration lock does not govern arbitrary Git,
  runtime, editor, or same-UID processes, and path-based Git/tree validation is
  not hardened into a general filesystem sandbox by this change.
