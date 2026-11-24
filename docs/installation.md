# Install, use and recover a standalone Home

This path needs Python 3.11 or newer with `venv` and `pip`, Git, and a separately
installed and authenticated native Codex CLI on `PATH`. On distributions that
split Python packaging, install their public Python venv/pip packages first.
Codex and its model account are operator prerequisites: Home does not install
Codex, supply credentials, choose an account, or require a particular proxy or
private model route. Use Codex's supported login/provider setup and project trust
controls. Keep its native permissions in force.

No other Soulsteads product, Hermes, memory service, private script, or developer
checkout is needed. The `settings` extra below supplies public `tomlkit` for
Codex TOML edits. Ordinary Home commands have no Python runtime dependencies;
Hermes import separately requires the `hermes` extra.

## Install an exact artifact

Obtain the reviewed source archive or wheel and its SHA-256 from your distributor.
If no wheel is provided, build one from the source archive. A source checkout or
a passing local install does not establish a hosted package or CI result.

Use a fresh directory outside any Git repository; do not unpack a private Git
history into it. These commands use standard Python tools:

```sh
mkdir -p "$HOME/home-preview/source"
cd "$HOME/home-preview"
# Set SOURCE_ARCHIVE to the supplied, hash-checked source tar file.
tar -xf "$SOURCE_ARCHIVE" -C source
# The build directory must contain pyproject.toml. If the archive has a wrapper
# directory, use ./source/<directory> in place of ./source on the next line.
python3 -m venv .venv
.venv/bin/python -m pip wheel --no-deps --wheel-dir dist ./source
.venv/bin/python -m pip install './dist/soulsteads-0.3.0-py3-none-any.whl[settings]'
export PATH="$PWD/.venv/bin:$PATH"
soulsteads --help
```

Building requires access to public build dependencies (`setuptools>=68`); installing
`[settings]` also downloads `tomlkit>=0.12,<1` unless already supplied locally.
For a supplied wheel, omit extraction/build and install the exact wheel path with
`[settings]` instead. A wheel installation does not require Git history or the
source directory. Git is still needed to create and version Homes.

## First useful work

Create a new canonical Home. Set the model to one your existing Codex account
supports; the name below is a placeholder, not a required model:

```sh
soulsteads create packer --runtime codex --path "$PWD/packer" --no-skills
soulsteads config ./packer --shared-json '{"model":"YOUR_SUPPORTED_CODEX_MODEL"}'
```

Edit `packer/SOUL.md` and `packer/USER.md` with your agent identity and project.
Install a reviewed local skill directory containing `SKILL.md` and its referenced
files with `soulsteads skill install ./packer /path/to/skill`. Installation copies
files locally and executes nothing. Place task input in `packer/workspace/`.

```sh
soulsteads config ./packer --sync
soulsteads verify ./packer
soulsteads commit ./packer -m 'Reviewed working baseline'
soulsteads log ./packer
soulsteads run ./packer --dry-run
soulsteads run ./packer
```

Complete Codex's explicit trust step for the Home itself, not just its workspace.
Without trust, native project configuration may be ignored even when skills are
listed. Ask Codex to read the installed skill and its reference, compute an output
from the input, write it under `workspace/`, and read it back. Inspect the artifact
yourself. A successful offline `verify` alone does not prove native task success.

For an explicitly selected project, use `run ./packer --project /absolute/project
--allow-context-in-argv`. This consent exposes Home identity/skill text in process
arguments; dry-run redacts it. Native project settings retain their own scope.
The rehearsal selected the Home's own `workspace/` and used `exec --ephemeral`
for one fresh task. Home-root interactive launch remains the simpler entry point.

## Recover one bad tracked Codex configuration

Stop native sessions before editing/restoring. Record the baseline commit ID
from `soulsteads log`. If a later edit leaves `.codex/config.toml` malformed,
`verify` reports a structural failure and `config --sync` names the native
configuration conflict; neither reports a parser line number. Sync does not
silently replace the damaged file. Review the diff. If retaining the failed configuration
in local history is appropriate and it contains no secrets:

```sh
soulsteads verify ./packer
soulsteads config ./packer --sync
soulsteads commit ./packer -m 'Record failed local configuration before recovery'
soulsteads revert ./packer BASELINE_COMMIT_ID
soulsteads verify ./packer
soulsteads log ./packer
soulsteads run ./packer
```

The first two commands are expected to report the malformed configuration.
Replace `BASELINE_COMMIT_ID` with the reviewed hexadecimal ancestor ID.
Restore requires a clean tracked tree and creates a new commit; it preserves
history, ignored workspace output and untracked files. Operator-owned native
settings present in the baseline return with that snapshot. Changes made after
the baseline are not merged into the restored configuration. Start a fresh native
process to load it. Restoring a revision that is already checked out, with no
diff against HEAD, is refused with "revision is already checked out" and changes
nothing. Git restore does not restore ignored native sessions or
credential state, and is not a memory-service rollback.

## Qualified scope

The documented recovery path covers tracked Home files. Check compatibility
with the exact versions of Python and the native runtime you install. The source
workflow declares Ubuntu/macOS and Python 3.11/3.13; other combinations may differ.

Home retains its Apache-2.0 license and NOTICE. Native Codex and optional
third-party dependencies have their own licenses and terms. The built wheel
includes Home's LICENSE and NOTICE; this rehearsal is not an audit of every
native dependency or hosted service.

Hindsight is optional. This install and recovery path does not require a memory
service and does not test one. See [native compatibility and release limits](native-acceptance.md)
for the separately scoped memory behavior.
