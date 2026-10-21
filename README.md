<p align="center">
  <img src="assets/banner.svg" alt="Soulsteads Agent Home" width="720" />
</p>

<p align="center">
  <strong>Your agent. Your files. No BS.</strong><br/>
  A portable home for your coding agent’s identity, instructions, memory, and skills.
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache%202.0-blue" alt="License: Apache 2.0" /></a>
  <img src="https://img.shields.io/badge/python-3.11%2B-informational?logo=python" alt="Python 3.11 or newer" />
  <img src="https://img.shields.io/badge/storage-local%20Git-38bdf8" alt="Storage: local Git" />
</p>

<p align="center">
  <a href="#get-started">Get started</a> ·
  <a href="#import-from-hermes">Import from Hermes</a> ·
  <a href="docs/runtimes.md">Runtime guide</a> ·
  <a href="#know-before-you-start">Safety and privacy</a>
</p>

---

## Why Agent Home?

Give your agent a home you can read, edit, and version—not another service to run.
The small `soulsteads` CLI keeps its identity, instructions, local memory, skills,
and project-level runtime configuration together in a local Git repository.

- **Your files, on your machine.** Plain Markdown and local configuration, not a hosted account.
- **Choose your runtime.** OpenCode, pi, Claude Code, or Codex. Install and authenticate it separately.
- **Keep a history.** Commit changes and restore earlier tracked contents without rewriting history.
- **Start small.** Python 3.11+ and Git; ordinary CLI commands have no runtime Python dependencies.
- **Bring selected Hermes files.** Inspect a profile before importing with the optional `hermes` extra.

Agent Home manages the home—not models, gateways, scheduled jobs, or chat accounts.
It does not install your runtime or change its global configuration.

## Get started

Install the CLI, create a home, and preview its launch command:

```sh
uv tool install git+https://github.com/soulsteads/soulsteads-agent-home.git
soulsteads create helper --runtime opencode
soulsteads run helper --dry-run
```

Choose `pi`, `claude`, or `codex` instead if that is the runtime you use.
Once your runtime is installed and authenticated, launch it with `soulsteads run helper`.

### Other installation options

```sh
uv tool install .
# Or, from the repository URL:
uv tool install git+https://github.com/soulsteads/soulsteads-agent-home.git
# Alternatively:
pipx install .
```

## Create an agent

```sh
soulsteads create helper --runtime opencode
soulsteads create researcher --runtime pi --path ~/agents/researcher
soulsteads create reviewer --runtime claude --no-skills
soulsteads create builder --runtime codex
```

The default destination is `~/.soulsteads/agents/<name>`.
Use `--agents-dir /another/parent` **before** the subcommand to change this parent.
Creation refuses existing destinations and locations inside another Git repository.
It never imports existing personal agent files or reads credentials.

### What’s in a home?

Each home has:

- `USER.md`: a blank user profile to fill in yourself.
- `SOUL.md`: a generic, editable identity and behavior starter.
- `AGENTS.md`: instructions to read the identity, user, and memory files.
- `MEMORY.md`: an initially empty durable-memory document.
- `workspace/`: scratch space for work, excluded from tracking except its placeholder.
- `skills/`: portable `SKILL.md` folders, with an optional original starter skill.
- `soulsteads.json`: name, runtime, and manifest schema version.
- Project-local runtime configuration and an initial local Git commit.

New homes are private (`0700` directories, `0600` generated files; executable
files in installed skills retain owner-only execute permission). No Git remote is added.
Generated home commits use a repository-local `Soulsteads <soulsteads@localhost>`
identity, never modify your global Git configuration, and do not run Git hooks.
This identity is configurable through normal repo-local Git commands.

## Import from Hermes

Install the optional importer, then inspect an explicitly selected source profile:

```sh
uv tool install '.[hermes]'
soulsteads import-hermes helper --source "$HOME/.hermes" --profile helper \
  --runtime opencode --path "$HOME/agents/helper"
```

Inspection is read-only. Add `--apply` only after reviewing its report; a fresh
private Home is created without starting a runtime or transferring live messaging
ownership. Supported identity files, memory, and enabled local skills are imported;
nonportable settings and unsupported discovery are reported, not silently
translated. Incomplete imports require `--allow-partial` acknowledgement.

The source configuration (which may contain secrets) and receipt remain in ignored
private storage. Separate credential files are excluded by default; an explicit
`--include-secrets` copies only
the selected profile's `.env` as an inactive private reference, never OAuth login
or live credential pools. Identity/skills may enter the new Home's local Git
history, so inspect them for secrets before applying or sharing.

See the [Hermes import guide](docs/hermes-import.md) for source selection, workspace
instructions, skill filters, safety checks, and the separate activation boundary.
Inspect its compatibility findings before applying, then run
`soulsteads verify /path/to/new-home` for offline structural checks. Verification
never launches an agent and does not establish that migration is activation-ready.

---

## Configure and launch

```sh
soulsteads config helper
soulsteads config helper --runtime codex
soulsteads run helper --dry-run
soulsteads run helper -- --help
soulsteads run ~/agents/researcher
```

An agent argument is a name under the default parent or a path. Use `./helper`
for a relative path instead of a registered name. Runtimes launch **from the home
root**, so project instructions and configuration are discoverable. Ask the agent
to keep task outputs in `workspace/` when appropriate. This is not a sandbox.
Runtime arguments after `--` are passed verbatim without a shell.

Configuration changes require a clean tracked tree and preserve your Markdown.
Customized runtime configuration is not silently overwritten. Commit changes
before switching runtimes; inspect and commit the new configuration afterward.
Global models, authentication, MCP servers, permissions, and runtime defaults are
not changed. This CLI does not install or isolate runtime binaries, and the
runtime can still load its own global configuration.

See [runtime adapters and upstream references](https://github.com/soulsteads/soulsteads-agent-home/blob/main/docs/runtimes.md).

## Track and restore

```sh
soulsteads commit helper  # Automatically generate a local commit message
# Or supply your own:
soulsteads commit helper -m "Personalize the agent"
soulsteads log helper
soulsteads revert helper <commit-id>
```

Omit `-m` to generate a message such as `Update agent home (2 files)` from the
number of changed files selected for the commit. This needs no AI service or
network access and does not copy file contents or filenames into the message.
Explicit messages are preserved; an explicitly blank message is rejected.
No changes means no new commit. The same safe-file allowlist applies in both modes.

Restore accepts a hexadecimal commit ID from this home's ancestor history and
creates a **new commit** with the old tracked contents. It does not reset history,
delete untracked files, or run `git clean`. A dirty tree is refused. Ignored
workspace output, `.env`, and runtime session/cache files stay untouched.

Tracking is intentionally limited to agent identity/configuration and skills.
This is not a secret scanner: **never put secrets in tracked Markdown, skills, or
runtime config**. Ignoring `.env` does not encrypt it. This CLI does not push or
publish your generated agent repository.

## Install a skill

```sh
soulsteads skill install helper /path/to/my-skill
soulsteads commit helper -m "Install my-skill"
```

The source must be a local directory with `SKILL.md` YAML frontmatter containing
`name` and `description`. The first version supports simple scalar frontmatter;
use a lowercase hyphenated skill name and a one-line description. Links, special
files, hidden repository metadata, secret-named files, collisions, and path
traversal are rejected. No code is executed and no network fetch is performed.
Inspect third-party instructions yourself before installing: a skill can direct
an agent to perform harmful actions even when its files contain no executable code.

## Optional: reach your agent from chat

[Soulsteads Agent Messaging](https://github.com/soulsteads/soulsteads-agent-messaging)
is a separate project that connects coding agents to chat apps, so you can send
requests and receive replies without staying at a terminal. Agent Home focuses
on the agent's portable identity, instructions, memory, skills, and configuration;
Agent Messaging provides the chat connection.

The projects are independent: neither requires the other. You can use Agent Home
with your chosen runtime directly, or use Agent Messaging without an Agent Home.
If you choose to use both, follow Agent Messaging's setup guide for its supported
configuration; installing Agent Home does not install or configure messaging,
transfer credentials, or start a messaging service.

---

## Know before you start

> [!CAUTION]
> **Agent Home is not a sandbox or a secret scanner.** Your runtime keeps its
> machine permissions and may load its own global configuration. Review imported
> files and third-party skills before running an agent or sharing a home.

- **Keep secrets out of Git.** Ignored private files are not encrypted; tracked Markdown and skills may contain sensitive information.
- **Import is not activation.** Hermes sessions, schedules, messaging ownership, and external services are not automatically transferred into a running agent.
- **Restore is scoped.** Only tracked Home contents are restored; ignored workspace output and runtime state stay untouched.
- **Chat is optional.** Agent Messaging is independent and needs its own setup and credentials.

## More documentation

- [Hermes import guide](docs/hermes-import.md): source selection, supported files, safety checks, and activation limits.
- [Runtime adapters](docs/runtimes.md): configuration details and upstream references.
- [Agent Messaging](https://github.com/soulsteads/soulsteads-agent-messaging): connect an agent to chat, separately.

## Development

```sh
PYTHONPYCACHEPREFIX=/tmp/soulsteads-pycache python3 -m unittest discover -s tests -v
uvx ruff check soulsteads tests
uv build --out-dir /tmp/soulsteads-dist
```

Tests create disposable homes and real local Git repositories. They do not invoke
paid model calls, copy private agents, or mutate user-level runtime configuration.

## License

Licensed under the [Apache License, Version 2.0](LICENSE).
See [NOTICE](NOTICE) for copyright attribution.
