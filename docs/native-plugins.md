# Native Agent Home plugins

The opt-in `soulsteads-agent-home` package exposes one shared skill,
`soulsteads-home-status`, in Claude Code, Codex, Pi, and OpenCode v2. Use it to
check a named Home from a separate project. It verifies the Home's structure
offline without probing harness versions or checking whether its configured
credential variable is set. It does not attach, modify, or start the Home.
Use [Home-managed project launch](runtimes.md#separate-project-launch) to load
a Home's identity and skills instead.

## Locate the package

Use a checkout or installation that includes these assets. From a source
checkout, use the absolute path to `soulsteads/assets/native-plugins` as the
marketplace root. For a wheel installation, use the same Python environment
that installed `soulsteads` to locate it:

```sh
market=$(python3 -c 'from importlib.resources import files; print(files("soulsteads").joinpath("assets", "native-plugins"))')
plugin="$market/plugins/soulsteads-agent-home"
```

Put the `soulsteads` CLI from the same checkout or installation on the harness's
PATH. Without shell access, run `soulsteads verify --no-credential-check helper`
yourself instead of relaxing the harness's permissions.

## Enable in your harness

### Claude Code

Use the [native plugin directory](https://code.claude.com/docs/en/plugins/create)
for just this session:

```sh
claude --plugin-dir "$plugin"
```

Invoke `/soulsteads-agent-home:soulsteads-home-status helper`, substituting a
Home you want to inspect. Start without `--plugin-dir` to leave it unloaded.

### Codex

Add the [local marketplace and its plugin](https://developers.openai.com/codex/plugins/build)
to the selected Codex profile. This is an explicit native install; it changes
that profile's own plugin configuration, not any Agent Home files:

```sh
codex plugin marketplace add "$market"
codex plugin add soulsteads-agent-home@soulsteads-local
```

In a fresh session, select `soulsteads-agent-home:soulsteads-home-status` from
the skill picker and specify the Home, for example `helper`. Use
`codex plugin remove soulsteads-agent-home@soulsteads-local` to uninstall it.

### Pi

In the working project where you want to use it, add the
[local Pi package](https://docs.pi.dev/latest/packages):

```sh
pi install "$plugin" -l
```

With normal native project trust, start Pi and use
`/skill:soulsteads-home-status helper`. To remove the project registration, run
`pi remove "$plugin" -l`. The project references the local path, so keep the
asset directory available as long as the registration exists.

### OpenCode v2

Add the absolute plugin **directory** to the project configuration's existing
[`plugins` list](https://opencode.ai/docs/plugins/). Preserve all other entries:

```json
{
  "plugins": ["/absolute/path/to/native-plugins/plugins/soulsteads-agent-home"]
}
```

In a fresh session, explicitly ask to load the `soulsteads-home-status` skill
by name and check `helper`. The [server plugin](https://opencode.ai/docs/build/plugins/server/#skills)
registers the skill without overriding an existing entry of the same ID. It
is not advertised for automatic model selection. Remove the entry you added
and restart the project session/server to unload it. This plugin is separate
from the [optional OpenCode v2 memory and model plugins](opencode-v2-plugins.md).

## Verification limits

Native discovery was checked on Claude Code 2.1.331, Codex 0.172.0, Pi 1.6.0, and
OpenCode 2.4.1 using disposable profiles and no model calls. Discovery confirms
that each harness sees the package's skill. It does not establish live model
behavior, cross-harness session continuity, memory retention, or that the Home
being inspected supplies the current session's context.
