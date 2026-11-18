"""Canonical settings with explicit capability checks and native edit ownership."""
import copy
import re

from . import core, settings


def translate(config, runtime):
    if not isinstance(config, dict) or set(config) - {"model", "provider", "mcp", "permission"}:
        raise core.HomeError("shared settings accept only model, provider, mcp, permission")
    result = {}
    def put(surface, key, value):
        result.setdefault(surface, {})[key] = value
    for key in ("model", "provider", "permission"):
        if key in config and (not isinstance(config[key], str) or not config[key].strip()):
            raise core.HomeError(f"shared {key} must be a nonempty string")
    if runtime == "soulsteads":
        from . import native_harness

        native_harness.translate(config)  # explicit unsupported/invalid mappings fail here
        settings._secret_check(config, runtime=runtime)
        return {}
    if "model" in config:
        put("main", "model", config["model"])
    if "provider" in config:
        if runtime == "codex":
            put("main", "model_provider", config["provider"])
        elif runtime == "pi":
            put("main", "defaultProvider", config["provider"])
        elif runtime == "opencode" and "model" in config:
            put("main", "model", config["provider"] + "/" + config["model"])
        else:
            raise core.HomeError(f"shared provider is unsupported for {runtime}; use native settings")
    if runtime == "pi" and "model" in config:
        result["main"]["defaultModel"] = result["main"].pop("model")
    if "permission" in config:
        # Native permission semantics differ; never weaken or guess a mapping.
        if runtime != "codex" or config["permission"] != "read-only":
            raise core.HomeError(f"shared permission supports only codex read-only; use native permissions for {runtime}")
        put("main", "sandbox_mode", "read-only")
        put("main", "approval_policy", "never")
    servers = config.get("mcp", {})
    if not isinstance(servers, dict):
        raise core.HomeError("shared mcp must be an object of named stdio servers")
    if servers and runtime == "pi":
        raise core.HomeError("shared MCP is unsupported for pi; configure a native extension")
    for name, server in servers.items():
        if not isinstance(name, str) or re.fullmatch(r"[A-Za-z0-9_-]{1,64}", name) is None or not isinstance(server, dict) or set(server) - {"command", "args"}:
            raise core.HomeError("shared MCP accepts named command/args objects only")
        if not isinstance(server.get("command"), str) or not server["command"] or not isinstance(server.get("args", []), list) or not all(isinstance(x, str) for x in server.get("args", [])):
            raise core.HomeError("shared MCP requires a command string and string args")
        if runtime == "opencode":
            put("mcp", name, {"type": "local", "command": [server["command"], *server.get("args", [])], "enabled": True})
        else:
            put("mcp", name, {"command": server["command"], "args": server.get("args", [])})
    settings._secret_check(config, runtime=runtime)
    return result


def plan(home, manifest, writes, snapshot):
    """Merge only owned keys, preserving unowned native fields and formatting."""
    runtime = manifest["runtime"]
    if runtime == "soulsteads":
        # Projected key-by-key with its own ownership record in native_harness.plan.
        return copy.deepcopy(manifest.get("shared_owned", {}))
    desired = translate(manifest.get("shared_settings", {}), runtime)
    ownership = copy.deepcopy(manifest.get("shared_owned", {}))
    if not isinstance(ownership, dict):
        raise core.HomeError("invalid shared ownership metadata")
    owned = ownership.get(runtime, {})
    if not isinstance(owned, dict) or set(owned) - {"main", "mcp"}:
        raise core.HomeError("invalid shared ownership metadata")
    spec = settings._runtime(runtime)
    missing = object()
    for surface in sorted(set(desired) | set(owned)):
        relative = spec.get("mcp_file", spec["file"]) if surface == "mcp" else spec["file"]
        fmt = "json" if relative == spec.get("mcp_file") else spec["format"]
        raw = writes.get(relative, snapshot.read(home / relative))
        data = settings._parse(raw, fmt)
        prefix = (spec["mcp"],) if surface == "mcp" else ()
        previous = owned.get(surface, {})
        wanted = desired.get(surface, {})
        if not isinstance(previous, dict):
            raise core.HomeError("invalid shared ownership metadata")
        changes = []
        for key in sorted(set(previous) | set(wanted)):
            path = (*prefix, key)
            # Hindsight belongs to the dedicated memory adapter, never both.
            if surface == "mcp" and key == "hindsight":
                raise core.HomeError("configure Hindsight with --hindsight-url, not shared MCP")
            current = settings._resolved(data, path, missing)
            if key in previous and current != previous[key]:
                raise core.HomeError(f"native edit conflicts with shared setting {surface}.{key}; preserve and reconcile it explicitly")
            if key not in previous and current is not missing:
                # Equal native values remain user-owned rather than being silently adopted.
                if current == wanted.get(key, missing):
                    continue
                raise core.HomeError(f"existing native setting conflicts with shared setting {surface}.{key}")
            if key in wanted:
                settings._validate_value(runtime, path, wanted[key])
                changes.append(("set", path, wanted[key], None))
            else:
                changes.append(("unset", path, None, None))
        rendered = settings._render(fmt, raw, changes) if changes else raw
        if rendered != snapshot.read(home / relative):
            writes[relative] = rendered
        new_owned = {key: copy.deepcopy(wanted[key]) for key in wanted
                     if key in previous or settings._resolved(data, (*prefix, key), missing) is missing}
        ownership.setdefault(runtime, {})[surface] = new_owned
    return ownership


def codex_overrides(manifest):
    """Apply explicit canonical intent for a Home-managed Codex invocation.

    Project trust controls project-file loading in Codex. Passing user-configured
    canonical settings as native CLI overrides avoids granting project trust or
    changing global configuration. Native-only settings still obey native trust.
    Identity text is not copied into arguments here.
    """
    if manifest['runtime'] != 'codex' or not manifest.get('shared_settings'):
        return []
    from .native_config import _codex_feature_value
    desired = translate(manifest['shared_settings'], 'codex')
    result = []
    for key, value in desired.get('main', {}).items():
        result.extend(['--config', key + '=' + _codex_feature_value(value)])
    for name, server in desired.get('mcp', {}).items():
        for key, value in server.items():
            path = 'mcp_servers.' + name + '.' + key
            result.extend(['--config', path + '=' + _codex_feature_value(value)])
    return result
