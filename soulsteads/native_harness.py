"""Optional first-party Soulsteads native harness projection.

The harness owns runtime, session and tool decisions. Home owns only a small set
of keys in ``soulsteads-harness.toml`` (listed per key in the manifest under
``shared_owned.soulsteads``); every other key and comment is operator-owned.
Contract: harness README "Configuration reference" (accepted 686248c).
"""

import copy
import json
import re
import tomllib

from . import core

NAME = "soulsteads"
FILE = "soulsteads-harness.toml"
STATE = ".runtime/soulsteads-harness"
MAX_INSTRUCTION_BYTES = 64 * 1024  # [agent] instructions_files limit
SERVER_NAME = re.compile(r"[a-z0-9-]{1,24}")
MAX_AGENT_ID = 64  # [agent] id is [a-z0-9_-]{1,64}
READ_ONLY_TOOLS = ["read_file", "list_dir", "search_files"]
# Scoped file tools only: no run_command, no MCP grant, no directory beyond workspace/.
WORKSPACE_WRITE_TOOLS = ["read_file", "write_file", "edit_file", "list_dir", "search_files"]
PERMISSION_TOOLS = {"read-only": READ_ONLY_TOOLS, "workspace-write": WORKSPACE_WRITE_TOOLS}
HEADER = (
    "# Soulsteads Home projection for the native harness. Home owns only the keys\n"
    "# recorded in soulsteads.json (shared_owned.soulsteads); add any other native\n"
    "# settings (provider endpoint, limits, approvals, commands) freely.\n\n"
)


def translate(config):
    """Canonical shared settings -> (dotted main keys, MCP entries). Fails closed."""
    main, mcp = {}, {}
    if "provider" in config:
        raise core.HomeError(
            "shared provider is unsupported for soulsteads; the native harness has one "
            "openai-compat provider whose endpoint is operator-owned (set provider.base_url_env natively)"
        )
    if "model" in config:
        main["provider.model"] = config["model"]
    if "permission" in config:
        if config["permission"] not in PERMISSION_TOOLS:
            raise core.HomeError(
                "shared permission supports only read-only and workspace-write for soulsteads; "
                "use native grants (shell commands and network are native-only)"
            )
        main["grants.workspace"] = "workspace"
        main["grants.tools"] = list(PERMISSION_TOOLS[config["permission"]])
    servers = config.get("mcp", {})
    if not isinstance(servers, dict):
        raise core.HomeError("shared mcp must be an object of named stdio servers")
    for name, server in servers.items():
        if (
            not isinstance(name, str)
            or not isinstance(server, dict)
            or set(server) - {"command", "args"}
            or not isinstance(server.get("command"), str)
            or not server["command"]
            or not isinstance(server.get("args", []), list)
            or not all(isinstance(x, str) for x in server.get("args", []))
        ):
            raise core.HomeError("shared MCP requires a command string and string args")
        if SERVER_NAME.fullmatch(name) is None:
            raise core.HomeError(
                "shared MCP name is not valid for soulsteads (lowercase letters, digits, hyphen; max 24)"
            )
        # Ask-gated: the operator approves each call (run --approve-ask / chat tty); never allow.
        mcp[name] = {
            "transport": "stdio",
            "command": server["command"],
            "args": list(server.get("args", [])),
            "default_approval": "ask",
        }
    return main, mcp


def projection(manifest, learning_present):
    from . import shared

    if len(manifest["name"]) > MAX_AGENT_ID or re.fullmatch(r"[a-z0-9_-]+", manifest["name"]) is None:
        raise core.HomeError(
            f"Home name is not a valid native agent id (1-{MAX_AGENT_ID} chars of [a-z0-9_-]); "
            "choose a shorter name or another harness"
        )
    files = ["AGENTS.md", "SOUL.md", "USER.md", "MEMORY.md"]
    if learning_present:
        files.append("LEARNING.md")
    main = {
        "agent.id": manifest["name"],
        "agent.instructions_files": files,
        "skills.roots": ["skills"],
    }
    config = manifest.get("shared_settings") or {}
    shared.translate(config, NAME)  # validation and secret checks in one place
    extra_main, mcp = translate(config)
    main.update(extra_main)
    return main, mcp


def _value(value):
    if isinstance(value, list):
        return "[" + ", ".join(_value(item) for item in value) + "]"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    raise core.HomeError("unsupported native value")


def baseline(main, mcp):
    tables = {}
    for key, value in main.items():
        table, leaf = key.split(".", 1)
        tables.setdefault(table, []).append((leaf, value))
    out = HEADER
    for table in ("agent", "provider", "grants", "skills"):
        if table in tables:
            out += f"[{table}]\n" + "".join(
                f"{leaf} = {_value(value)}\n" for leaf, value in tables[table]
            ) + "\n"
    for name, entry in mcp.items():
        out += "[[mcp_servers]]\n" + f"name = {_value(name)}\n"
        out += "".join(f"{k} = {_value(v)}\n" for k, v in entry.items()) + "\n"
    return out.rstrip("\n") + "\n"


def _lookup(parsed, dotted):
    node = parsed
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return _MISSING
        node = node[part]
    return node


_MISSING = object()


def digest_owned(owned):
    from .runtimes import digest

    return digest(json.dumps(owned, sort_keys=True, separators=(",", ":")))


def _merge(current, wanted_main, wanted_mcp, previous):
    try:
        parsed = tomllib.loads(current)
    except tomllib.TOMLDecodeError as exc:
        raise core.HomeError("native harness config is not valid TOML") from exc
    prev_main = previous.get("main", {})
    prev_mcp = previous.get("mcp", {})
    new_main, edits_main = {}, []
    for key in sorted(set(prev_main) | set(wanted_main)):
        cur = _lookup(parsed, key)
        if key in prev_main:
            if cur != prev_main[key]:
                raise core.HomeError(
                    f"native edit conflicts with shared setting {key}; preserve and reconcile it explicitly"
                )
        elif cur is not _MISSING:
            if cur == wanted_main.get(key, _MISSING):
                continue  # equal operator value stays operator-owned
            raise core.HomeError(
                f"existing native setting conflicts with shared setting {key}"
            )
        if key in wanted_main:
            new_main[key] = copy.deepcopy(wanted_main[key])
            if cur != wanted_main[key]:
                edits_main.append(("set", key, wanted_main[key]))
        else:
            edits_main.append(("unset", key, None))
    servers = parsed.get("mcp_servers", [])
    if not isinstance(servers, list):
        raise core.HomeError("native MCP servers must be an array of tables")
    current_servers = {}
    for server in servers:
        if not isinstance(server, dict) or not isinstance(server.get("name"), str):
            raise core.HomeError("native MCP server must have a string name")
        name = server["name"]
        if name in current_servers:
            raise core.HomeError(f"duplicate MCP server name {name}")
        current_servers[name] = server
    new_mcp, edits_mcp = {}, []
    for name in sorted(set(prev_mcp) | set(wanted_mcp)):
        cur = current_servers.get(name)
        bare = None if cur is None else {k: v for k, v in cur.items() if k != "name"}
        if name in prev_mcp:
            if bare != prev_mcp[name]:
                raise core.HomeError(
                    f"native edit conflicts with shared MCP server {name}; preserve and reconcile it explicitly"
                )
        elif cur is not None:
            if bare == wanted_mcp.get(name):
                continue
            raise core.HomeError(
                f"existing native MCP server {name} conflicts with shared setting"
            )
        if name in wanted_mcp:
            new_mcp[name] = copy.deepcopy(wanted_mcp[name])
            if bare != wanted_mcp[name]:
                edits_mcp.append(("set", name, wanted_mcp[name]))
        else:
            edits_mcp.append(("unset", name, None))
    owned = {"main": new_main, "mcp": new_mcp}
    if not edits_main and not edits_mcp:
        return current, owned
    try:
        import tomlkit
    except ImportError as exc:
        raise core.HomeError(
            "editing an existing native harness config requires the optional 'settings' extra"
        ) from exc
    doc = tomlkit.parse(current)
    for op, key, value in edits_main:
        parts = key.split(".")
        node = doc
        if op == "set":
            for part in parts[:-1]:
                if part not in node:
                    node[part] = tomlkit.table()
                node = node[part]
            node[parts[-1]] = value
        else:
            chain = [doc]
            for part in parts[:-1]:
                chain.append(chain[-1][part])
            chain[-1].pop(parts[-1], None)
            for depth in range(len(parts) - 1, 0, -1):
                if len(chain[depth]) == 0:
                    chain[depth - 1].pop(parts[depth - 1], None)
    for op, name, entry in edits_mcp:
        aot = doc.get("mcp_servers")
        index = next(
            (i for i, s in enumerate(aot or []) if s.get("name") == name), None
        )
        if op == "set":
            table = tomlkit.table()
            table["name"] = name
            for k, v in entry.items():
                table[k] = v
            if aot is None:
                aot = tomlkit.aot()
                doc["mcp_servers"] = aot
            if index is None:
                aot.append(table)
            else:
                aot[index] = table
        elif index is not None:
            del aot[index]
            if len(aot) == 0:
                del doc["mcp_servers"]
    return tomlkit.dumps(doc), owned


def plan(manifest, current, learning_present):
    """Return (text, owned). Raises HomeError on conflict; never overwrites unowned keys."""
    main, mcp = projection(manifest, learning_present)
    previous = (manifest.get("shared_owned") or {}).get(NAME, {})
    if not isinstance(previous, dict) or set(previous) - {"main", "mcp"}:
        raise core.HomeError("invalid shared ownership metadata")
    if current is None:
        return baseline(main, mcp), {"main": main, "mcp": mcp}
    return _merge(current, main, mcp, previous)


def launch_argv(home, extra, *, create=True):
    """Explicit config and state paths: never the harness's global default home."""
    import os
    import subprocess
    from pathlib import Path

    home = Path(home)
    state = home / STATE
    ignored = subprocess.run(
        ["git", "-C", str(home), "check-ignore", "-q", STATE + "/x"], check=False
    ).returncode == 0
    if not ignored:
        raise core.HomeError(f"{STATE}/ must be Git-ignored in the Home before running the native harness")
    if create:
        state.mkdir(mode=0o700, parents=True, exist_ok=True)
    binary = os.environ.get("SOULSTEADS_HARNESS_BIN") or "soulsteads-harness"
    return [binary, "--config", str(home / FILE), "--home", str(state), *extra]
