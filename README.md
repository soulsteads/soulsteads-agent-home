<p align="center">
  <img src="assets/banner.svg" alt="Soulsteads Agent Home" width="720" />
</p>

<p align="center">
  <strong>Your agent. Your files. No BS.</strong><br/>
  Define your agent once. Generate native configuration for your chosen harness.
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
The small `soulsteads` CLI maps one portable agent definition—identity, instructions,
memory connections, skills, and learning preferences—into native configuration for
pi, OpenCode, Codex, and Claude Code. The definition lives in a local Git repository;
your chosen harness owns execution, sessions, tools, and permissions.

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
Or `cd ~/.soulsteads/agents/helper` and run `opencode`, `pi`, `codex`, or `claude`
directly. Native configuration supplies the behavior; the Soulsteads launcher is optional.

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
- `skills/`: one portable skill tree, with optional verification and skill-maintenance starters.
- `soulsteads.json`: name, launch default, manifest version, and generated-file ownership hashes.
- Coexisting native configuration for all four harnesses and an initial local Git commit.
- `LEARNING.md`: generated learning policy, off by default in new homes.

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
soulsteads config helper --sync  # Refresh native files after canonical Markdown edits
soulsteads run helper --dry-run
soulsteads run helper -- --help
soulsteads run ~/agents/researcher
```

An agent argument is a name under the default parent or a path. Use `./helper`
for a relative path instead of a registered name. Runtimes launch **from the home
root**, so project instructions and configuration are discoverable. Ask the agent
to keep task outputs in `workspace/` when appropriate. This is not a sandbox.
Runtime arguments after `--` are passed verbatim without a shell.

Select a separate project explicitly without copying Home files:

```sh
soulsteads run helper --project /path/to/project --dry-run
soulsteads run helper --project /path/to/project
```

All four adapters carry the selected Home's identity, operating guidance and
skill context through native per-run inputs. They do not copy Home MCP/provider
settings, change permission policy, or move authentication/session state.
Codex and Claude receive skill text as bounded prompt guidance rather than
native slash-skill registration. They require explicit `--allow-context-in-argv`:
this places private Home identity and memory in process arguments that other
local users or process monitors may read. Without that consent, project launch
is refused; use a Home-root launch if this exposure is unacceptable. Dry-run
output redacts the private text even after consent. The installed version is not automatically
certified; see [native acceptance and limits](docs/native-acceptance.md).

Changing the launch default requires a clean tracked tree and never removes another
harness's files. `config --sync` accepts uncommitted canonical edits and upgrades
older Homes. It refreshes Pi's system-append file and Codex's additive developer
instructions; OpenCode and Claude use native includes. Unrelated settings are
preserved, and conflicting owned edits are refused. Inspect and commit the diff,
then start a new native session or use its supported reload mechanism.
Global models, authentication, MCP servers, permissions, and runtime defaults are
not changed. This CLI does not install or isolate runtime binaries, and the
runtime can still load its own global configuration.

See [runtime adapters and upstream references](https://github.com/soulsteads/soulsteads-agent-home/blob/main/docs/runtimes.md).

For standalone, explicitly enabled native v2 extensions, see the
[optional OpenCode v2 plugins](docs/opencode-v2-plugins.md) and the
[pinned upstream Hindsight integration](integrations/hindsight-opencode/README.md).
These do not change Home defaults or automatically configure a native profile.

### Native harness settings

Inspect native configuration and its known sources, then preview or apply
Home-local changes without creating a separate settings database:

```sh
soulsteads settings catalog --runtime codex
soulsteads settings inspect --home ./helper --runtime codex
soulsteads settings set --home ./helper --runtime codex \
  --key @model --value '"example-model"' --plan-file model-plan.json
soulsteads settings apply --home ./helper --plan-file model-plan.json
```

Codex editing requires the optional `settings` extra. The manager also supports
unset, ordered batches, advanced native fields and portable same-harness
profiles. External user/project layers are read-only, managed identity is
protected, and credentials belong in native secret storage rather than plans.
Static inspection is not a claim of runtime-effective precedence. See the
[settings guide](docs/settings.md) for formats, references and safety limits.

### Optional Hindsight memory tools

Point the Home at an existing authorized bank without copying credentials:

```sh
soulsteads config helper \
  --hindsight-url https://memory.example/mcp/helper/ \
  --hindsight-token-env HINDSIGHT_API_TOKEN
soulsteads verify helper
```

The harness reads its native project MCP configuration and the token from its
environment. Configuration and verification are offline; the token is never copied
into generated files. Native trust/approval still applies.

Opt in separately to recall at prompt submission and retention of captured prompts
with completed assistant replies:

```sh
soulsteads config helper --hindsight-recall --hindsight-retain
soulsteads config helper --no-hindsight-recall --no-hindsight-retain
```

Native command hooks (Claude/Codex), a plugin (OpenCode v1), or an extension
(Pi's current lifecycle API) call the small `soulsteads memory-hook` helper.
The helper uses the selected bank and environment credential. It excludes tool
output, transcript files and Git history, bounds requests, and lets the task
continue when memory is unavailable. Retention temporarily stores pending prompts
in private, ignored `.runtime/hindsight/` files. Start fresh sessions after changes.

Remove owned project entries and disable callbacks with
`soulsteads config helper --no-hindsight`; bank data and global servers remain
untouched. Live-bank persistence and native approval remain unqualified. See
[automatic memory](docs/runtimes.md#automatic-hindsight-memory) for versions,
limits and the distinction between hook execution and native MCP tool approvals.

### Skill improvement

Learning is **off** in new homes. Enable proposals or preapprove small procedural
corrections in explicitly named, existing skill files:

```sh
soulsteads create learner --runtime pi --learning propose
soulsteads config helper --learning scoped-apply --learning-skill starter
soulsteads config helper --learning off
```

`propose` shows suggested changes for review. `scoped-apply` covers only
`skills/<name>/SKILL.md` for each repeated `--learning-skill`; it does not authorize
supporting scripts, memory writes, identity/config changes, commits, or installation.
The generated policy loads through each harness's native instruction mechanism.
These modes are model-followed instructions; native permissions enforce access.
There is no background learner. Existing homes without a learning setting keep
their prior guidance until explicitly configured.

The optional `skill-maintenance` starter separates facts/preferences, reusable
procedures, and temporary handoffs. `--no-skills` omits both starter skills without
changing the selected learning mode. See [learning configuration](docs/runtimes.md#learning-configuration)
for refresh, scope, and qualification details.

### Inspect adapter capabilities

```sh
soulsteads capabilities
soulsteads capabilities --runtime pi
soulsteads verify helper
```

`capabilities` reports supported mappings and qualification limits without needing
a home or probing installed harnesses. `verify` also reports the home's effective
learning mode and prepared native paths. See the [capability matrix](docs/runtimes.md#capability-matrix)
for memory automation and project-selection limits.

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

## Native settings

Inspect native runtime settings with `soulsteads settings catalog`, `inspect`, and `get`. Propose edits with `set`, `unset`, `plan`, or `import`; these commands preview by default and require `--apply` to change the selected Agent Home. `apply` revalidates a saved plan and rejects stale state. User/project layers are inspection-only. Settings behavior, aliases, and validation coverage depend on runtime and version; fields outside the catalog remain native runtime territory. Credential stores are not accessed, and runtime-effective values may also depend on CLI flags, environment, trust, or policy.

See [the settings guide](docs/settings.md) for options, profiles, examples, limits, and rollback guidance.

## License

Licensed under the [Apache License, Version 2.0](LICENSE).
See [NOTICE](NOTICE) for copyright attribution.
