# Soulsteads

A small `soulsteads` CLI for creating and maintaining a portable agent home.
Choose OpenCode, pi, Claude Code, or Codex; keep the agent's identity,
instructions, memory, skills, and runtime configuration in a local Git repository.

Python 3.11+ and Git are required. Ordinary commands have no runtime Python
dependencies. Direct Hermes import uses the optional `hermes` extra (PyYAML).
Install and authenticate your chosen agent runtime separately.

## Install

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
soulsteads commit helper -m "Personalize the agent"
soulsteads log helper
soulsteads revert helper <commit-id>
```

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
