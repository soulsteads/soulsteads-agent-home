# Agent credential vault

Use the optional vault to keep provider API keys and integration credentials out
of your Git-tracked Agent Home. Agent Home stores them in the current Linux
user's default [Secret Service](https://specifications.freedesktop.org/secret-service/latest/)
keyring. It doesn't create a Home file or fall back to plaintext.

## Set up and use

Install the `vault` extra from the source checkout (`uv tool install '.[vault]'`
or `python -m pip install '.[vault]'` in your virtual environment). You need a
trusted D-Bus user session and an existing, persistent, unlocked default keyring
(such as GNOME Keyring). Set up and unlock the keyring using your OS tools;
Soulsteads does not create an account, set up a daemon, or unlock a collection.
Ordinary commands and unbound launches don't require this extra.

With an existing Home named `helper`:

```sh
soulsteads vault set helper application
soulsteads vault list helper
soulsteads run helper --credential APPLICATION_TOKEN=application --dry-run
soulsteads run helper --credential APPLICATION_TOKEN=application
```

- `set` prompts without echo. For automation, `set ... --stdin` reads redirected
  input as exact UTF-8 text (including any final newline). Values must be
  nonempty, at most 16 KiB, and contain no NUL bytes. Never pass a value in a
  command argument or paste it into shell history. Alias names are lowercase
  slugs beginning with a letter; `list` outputs a JSON array of names, not values.
- `--credential ENV=ALIAS` is explicit for each launch. Repeat it for other
  variables, and put the options **before** any `--` introducing native arguments.
  Use the environment variable the native provider or extension expects. Do not
  put vault bindings in tracked files: the vault does not resolve settings or
  substitute values into generated configuration. Existing environment variables,
  duplicate destinations, and reserved launcher variables are rejected. Native
  configuration and state selectors, such as `CODEX_HOME`, `CLAUDE_CONFIG_DIR`,
  `PI_CODING_AGENT_DIR`, and `OPENCODE_CONFIG`, are reserved even when unset.
- Dry runs display only the destination variable names and never open the
  keyring. Real launches fail before starting the harness if a requested
  credential is missing or the keyring is unavailable. Running a native harness
  directly does not open the vault.

Run `vault set` again to replace an entry. Run
`vault delete helper application` to remove it from the keyring. Neither action
changes credentials already in running processes or revokes them at the provider;
rotate or revoke them there and restart affected processes as needed.

## Store a login

Use `--login` to store a username and password together under one alias. The
three prompts do not echo input. Leave the URL blank to omit it.

```sh
soulsteads vault set helper service --login
soulsteads run helper \
  --credential APP_LOGIN_USER=service.username \
  --credential APP_LOGIN_PASS=service.password \
  --credential APP_LOGIN_SITE=service.url
```

Map only the fields your runtime needs. Omit the `url` mapping if the entry
doesn't have a URL. A missing field stops the launch; a login alias by itself
never passes the whole record. The URL is stored as text: Agent Home neither
opens it nor verifies that it matches the destination the runtime connects to.

For automation, `vault set helper service --login --stdin` accepts a UTF-8 JSON
object from redirected input. It requires nonempty strings named `username` and
`password` and accepts one optional nonempty `url` string. Omit the key rather
than using an empty string or `null`. Input and the encoded login record are
each limited to 16 KiB. Supply the JSON through a trusted pipe rather than
putting values in command arguments, shell history, or a tracked file.

Setting an existing alias replaces the entire entry; omitting the URL removes
the previous URL. `vault list` still shows aliases only. Single-value entries
such as API keys still use `set` without `--login` and bindings without a field.

## Security and portability limits

- Scope is by absolute Home path in the selected user's default keyring, not by
  agent name or Git identity. A copy or move to another path does not carry
  credentials; enroll them there separately. Remove old entries before discarding
  a Home, and don't reuse a path for an unrelated agent until its old entries
  are removed. A replacement Home at the same path uses the same namespace.
  Vault contents aren't included in settings exports, Home backups or Git
  restore. Back up the keyring using the OS provider's supported procedure.
- The backend provides storage protection; this is not a sandbox between agents
  running under one OS account. Alias labels and lookup attributes are keyring
  metadata, not secret fields. Do not place sensitive values in aliases. Trust
  the user session, keyring provider and processes that can use that keyring.
- The launched harness, its tools and descendants can read the variables you
  give them. They can disclose those values in logs, tool output, or network
  requests. Only grant credentials to trusted Homes, projects, and runtimes;
  prefer provider-scoped, least-privilege credentials. Native sign-in and
  session storage remain the harness's responsibility.
- Other platforms and headless services without a usable Secret Service session
  are not supported by this vault. Continue using native authentication or
  your deployment's established secret-injection mechanism there.
