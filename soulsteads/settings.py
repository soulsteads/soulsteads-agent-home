"""Native settings with observed provenance and checked Home-local publication.

Plans are validation receipts, not authorization tokens. No harness is executed,
no credential store is opened, and no project or global configuration is written.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import re
from contextlib import contextmanager, nullcontext
from pathlib import Path

from . import core
from . import native_config as native
from .hermes_import import _open_dir
from .publication import _identity, cooperative_lock, publish_file
from .settings_catalog import (
    ALIASES,
    CATALOG_REVISION,
    NON_SECRET_FIELDS,
    OWNED_IDENTITY,
    REASONING,
    catalog,
    runtime_spec,
)
from .settings_formats import (
    delete_jsonc,
    delete_toml,
    parse_jsonc,
    parse_toml,
    update_jsonc,
    update_toml,
)

_SECRET_KEY = re.compile(
    r"api.?key|token|secret|password|credential|authorization|private.?key|^auth$",
    re.IGNORECASE,
)
_ENV_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_CREDENTIAL_FLAG = re.compile(
    r"--(?:api[-_]?key|(?:access|refresh|bearer|auth)[-_]?token|client[-_]?secret|token|password|passwd|secret|credentials?|authorization)",
    re.IGNORECASE,
)
_MISSING = object()
_PLAN_FORMAT = "soulsteads-settings-plan-v1"
_MANIFEST = "soulsteads.json"


def _runtime(runtime, version=None):
    return runtime_spec(runtime, version)


def _plain(value, depth=0):
    if depth > 64:
        raise core.HomeError("native settings nesting exceeds the depth limit")
    if isinstance(value, dict):
        return {str(k): _plain(v, depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v, depth + 1) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        raise core.HomeError(
            "non-finite native values cannot be represented in a settings plan"
        )
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise core.HomeError(
        "this native value type is not representable in a portable JSON settings profile"
    )


def _parse(text, fmt):
    if text is None:
        return {}
    if fmt == "toml":
        value = _plain(parse_toml(text))
    else:
        if fmt == "json":
            try:
                json.loads(text)
            except (ValueError, RecursionError) as exc:
                raise core.HomeError("native settings require strict JSON") from exc
        value = _plain(parse_jsonc(text))
    if not isinstance(value, dict):
        raise core.HomeError("native settings root must be an object")
    return value


@contextmanager
def _snapshot(home, *, writing=False):
    home = Path(home).expanduser().absolute()
    root_fd, chain = _open_dir(home)
    snap = native._NativeSnapshot(home, root_fd, chain)
    try:
        core._validate_home(home, reader=snap.read)
        with cooperative_lock(root_fd) if writing else nullcontext():
            core._validate_home(home, reader=snap.read)
            snap.verify()
            yield home, root_fd, chain, snap
            native._verify_root(home, chain)
    finally:
        snap.close()
        os.close(root_fd)


def _digest(text, identity):
    return {
        "sha256": hashlib.sha256((text or "").encode("utf-8")).hexdigest(),
        "identity": list(identity) if identity is not None else None,
    }


def _documents(home, runtime, snap):
    spec = _runtime(runtime)
    candidates = [spec["file"]]
    if runtime == "opencode":
        candidates.append("opencode.jsonc")
    if "mcp_file" in spec:
        candidates.append(spec["mcp_file"])
    texts, data = {}, {}
    for relative in candidates:
        texts[relative] = snap.read(home / relative)
        fmt = "json" if relative == spec.get("mcp_file") else spec["format"]
        data[relative] = _parse(texts[relative], fmt)
    primary = (
        "opencode.jsonc"
        if runtime == "opencode" and texts.get("opencode.jsonc") is not None
        else spec["file"]
    )
    ambiguous = runtime == "opencode" and all(
        texts.get(p) is not None for p in ("opencode.json", "opencode.jsonc")
    )
    return spec, primary, texts, data, ambiguous


def _combined(runtime, primary, data):
    result = copy.deepcopy(data[primary])
    spec = _runtime(runtime)
    if "mcp_file" in spec:
        auxiliary = data[spec["mcp_file"]]
        if spec["mcp"] in auxiliary:
            if spec["mcp"] in result:
                raise core.HomeError(
                    "MCP settings are duplicated in primary and auxiliary native documents"
                )
            result[spec["mcp"]] = copy.deepcopy(auxiliary[spec["mcp"]])
    return result


def _route(runtime, primary, path):
    spec = _runtime(runtime)
    return (
        spec["mcp_file"] if path[0] == spec["mcp"] and "mcp_file" in spec else primary
    )


def _reference(value, runtime=None):
    if not isinstance(value, str):
        return False
    stripped = value.removeprefix("Bearer ")
    patterns = {
        "opencode": r"\{env:[A-Za-z_][A-Za-z0-9_]*\}",
        "claude": r"\$\{[A-Za-z_][A-Za-z0-9_]*\}",
        "pi": r"\$\{[A-Za-z_][A-Za-z0-9_]*\}",
        "codex": r"(?!)",
    }
    if runtime is not None:
        return bool(re.fullmatch(patterns[runtime], stripped))
    return any(
        re.fullmatch(pattern, stripped) for pattern in patterns.values()
    ) or bool(re.fullmatch(r"env:[A-Za-z_][A-Za-z0-9_]*", stripped))


def _env_field(path, runtime):
    if runtime != "codex":
        return False
    return (
        len(path) == 3
        and (
            path[0] == "model_providers"
            and path[2] == "env_key"
            or path[0] == "mcp_servers"
            and path[2] == "bearer_token_env_var"
        )
        or len(path) == 4
        and path[0] in {"model_providers", "mcp_servers"}
        and path[2] == "env_http_headers"
    )


def _secret_check(value, path=(), runtime=None):
    key = path[-1] if path else ""
    definition = NON_SECRET_FIELDS.get(runtime or "", {}).get(tuple(path))
    if definition is not None:
        if definition["type"] == "integer":
            valid = (
                isinstance(value, int)
                and not isinstance(value, bool)
                and definition["minimum"] <= value <= definition["maximum"]
            )
        else:
            valid = isinstance(value, str) and value in definition["enum"]
        if not valid:
            raise core.HomeError("invalid value for a known non-credential setting")
        return
    if isinstance(value, str) and value.startswith("[REDACTED"):
        raise core.HomeError(
            "redacted placeholders are not native configuration values"
        )
    if _env_field(path, runtime):
        if not isinstance(value, str) or not _ENV_NAME.fullmatch(value):
            raise core.HomeError(
                "credential environment references must be variable names, not values"
            )
        return
    if _SECRET_KEY.search(key):
        if isinstance(value, bool) or value is None:
            return
        if _reference(value, runtime) and not (
            runtime == "claude" and path[:1] == ("env",)
        ):
            return
        raise core.HomeError(
            "credential values must be native environment references, never literals"
        )
    if isinstance(value, dict):
        for child, item in value.items():
            if not isinstance(child, str):
                raise core.HomeError("native settings object keys must be strings")
            _secret_check(item, path + (child,), runtime)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            if (
                isinstance(item, str)
                and _CREDENTIAL_FLAG.fullmatch(item)
                and (
                    index + 1 >= len(value) or not _reference(value[index + 1], runtime)
                )
            ):
                raise core.HomeError(
                    "credential-bearing arguments require native environment references"
                )
            _secret_check(item, path, runtime)
    elif isinstance(value, str) and not _reference(value, runtime):
        patterns = (
            r"(?i)https?://[^/@ ]+@",
            r"(?i)\bBearer\s+\S+",
            rf"(?i){_CREDENTIAL_FLAG.pattern}(?:=|\s+)\S+",
            r"(?i)(?:api[_-]?key|access[_-]?token|password|secret|[?&]token)\s*[:=]\s*[^ ,;]+",
        )
        if any(re.search(pattern, value) for pattern in patterns):
            raise core.HomeError("credential-bearing value is not accepted")


def _redact(value, path=(), runtime=None):
    if isinstance(value, dict):
        if path and _SECRET_KEY.search(path[-1]):
            try:
                _secret_check(value, path, runtime)
            except core.HomeError:
                return "[REDACTED]"
        return {k: _redact(v, path + (str(k),), runtime) for k, v in value.items()}
    if isinstance(value, list):
        try:
            _secret_check(value, path, runtime)
        except core.HomeError:
            return "[REDACTED]"
        return [_redact(item, path, runtime) for item in value]
    try:
        _secret_check(value, path, runtime)
    except core.HomeError:
        return "[REDACTED]"
    return value


def _pointer(key, runtime):
    if not isinstance(key, str):
        raise core.HomeError("settings path must be a string")
    if key.startswith("@"):
        if key[1:] not in ALIASES[runtime]:
            raise core.HomeError(f"unsupported {runtime} settings alias")
        return ALIASES[runtime][key[1:]]
    if not key.startswith("/") or len(key) > 2048:
        raise core.HomeError("settings path must be an alias or bounded JSON Pointer")
    parts = key[1:].split("/")
    if len(parts) > 32 or any(not p or re.search(r"~(?![01])", p) for p in parts):
        raise core.HomeError("malformed or excessive JSON Pointer")
    return tuple(p.replace("~1", "/").replace("~0", "~") for p in parts)


def _encoded(path):
    return "/" + "/".join(p.replace("~", "~0").replace("/", "~1") for p in path)


def _resolved(doc, path, default=None):
    node = doc
    for part in path:
        if isinstance(node, dict) and part in node:
            node = node[part]
        elif isinstance(node, list) and part.isdigit() and int(part) < len(node):
            node = node[int(part)]
        else:
            return default
    return node


def _validate_value(runtime, path, value):
    _secret_check(value, path, runtime)
    if runtime == "codex":

        def no_null(item):
            if item is None:
                raise core.HomeError("TOML has no null value; use unset instead")
            if isinstance(item, dict):
                for child in item.values():
                    no_null(child)
            elif isinstance(item, list):
                for child in item:
                    no_null(child)

        no_null(value)
    for alias, native_path in ALIASES[runtime].items():
        if path != native_path:
            continue
        if not isinstance(value, str) or not value.strip():
            raise core.HomeError(f"{alias} must be a non-empty native string")
        if alias == "reasoning" and value not in REASONING[runtime]:
            raise core.HomeError("unsupported reasoning effort")
    if (
        runtime == "codex"
        and path == ("sandbox_mode",)
        and (
            not isinstance(value, str)
            or value not in {"read-only", "workspace-write", "danger-full-access"}
        )
    ):
        raise core.HomeError("unsupported Codex sandbox_mode")
    if (
        runtime == "codex"
        and path == ("approval_policy",)
        and (
            not isinstance(value, str)
            or value not in {"untrusted", "on-request", "on-failure", "never"}
        )
    ):
        raise core.HomeError("unsupported Codex approval_policy")


def _change(change, runtime):
    if not isinstance(change, dict) or change.get("op") not in {"set", "unset"}:
        raise core.HomeError("change must have op=set|unset")
    expected = {"op", "path", "value"} if change["op"] == "set" else {"op", "path"}
    if set(change) != expected:
        raise core.HomeError("change contains missing or unexpected fields")
    path = _pointer(change["path"], runtime)
    spec = _runtime(runtime)
    if path[0] in OWNED_IDENTITY[runtime] or path[:2] == (spec["mcp"], "hindsight"):
        raise core.HomeError(
            "Soulsteads-owned identity and Hindsight must use their dedicated configuration workflow"
        )
    value = change.get("value")
    if change["op"] == "set":
        try:
            value = _plain(value)
            json.dumps(value, allow_nan=False)
        except (ValueError, TypeError, RecursionError) as exc:
            raise core.HomeError(
                "settings values must be bounded finite JSON values"
            ) from exc
        _validate_value(runtime, path, value)
    return (
        change["op"],
        path,
        value,
        change["path"][1:] if change["path"].startswith("@") else None,
    )


def _edit_semantic(doc, op, path, value):
    node = doc
    for part in path[:-1]:
        if not isinstance(node, dict):
            raise core.HomeError(
                "replace native arrays as a whole; pointer parent must be an object"
            )
        if part not in node:
            if op == "unset":
                return
            node[part] = {}
        node = node[part]
    if not isinstance(node, dict):
        raise core.HomeError(
            "replace native arrays as a whole; pointer parent must be an object"
        )
    if op == "set":
        node[path[-1]] = copy.deepcopy(value)
    else:
        node.pop(path[-1], None)


def _canonical(value):
    try:
        return native._canonical_json(value)
    except (TypeError, ValueError, RecursionError) as exc:
        raise core.HomeError("invalid native structural comparison value") from exc


def _same(left, right):
    """Compare JSON semantics without Python's bool/int equality aliases."""
    if left is _MISSING or right is _MISSING:
        return left is right
    return _canonical(left) == _canonical(right)


def _preserve_owned(runtime, before, after):
    for key in OWNED_IDENTITY[runtime]:
        if not _same(before.get(key, _MISSING), after.get(key, _MISSING)):
            raise core.HomeError("managed identity changed")
    path = (_runtime(runtime)["mcp"], "hindsight")
    if not _same(_resolved(before, path, _MISSING), _resolved(after, path, _MISSING)):
        raise core.HomeError("managed Hindsight connection changed")


def _render(fmt, text, changes):
    working = text if text is not None else ("" if fmt == "toml" else "{}\n")
    managed = ""
    if fmt == "toml":
        from .runtimes import CODEX_BEGIN, CODEX_END

        if working.startswith(CODEX_BEGIN):
            end = working.find(CODEX_END)
            if end < 0:
                raise core.HomeError("unterminated managed Codex block")
            end += len(CODEX_END)
            managed, working = working[:end], working[end:]
    for op, path, value, _alias in changes:
        if op == "unset":
            working = (
                delete_toml(working, [path])
                if fmt == "toml"
                else delete_jsonc(working, path)
            )
            continue
        current = _parse(working, fmt)
        prefix, node = (), current
        for index, part in enumerate(path):
            if not isinstance(node, dict):
                raise core.HomeError("replace native arrays as a whole")
            prefix += (part,)
            if part not in node:
                subtree = copy.deepcopy(value)
                for child in reversed(path[index + 1 :]):
                    subtree = {child: subtree}
                path, value = prefix, subtree
                break
            node = node[part]
        working = (
            update_toml(working, [(path, value)])
            if fmt == "toml"
            else update_jsonc(working, [(path, value)])
        )
    return managed + working


def _make_plan(home, runtime, changes, version, chain, snap):
    spec, primary, texts, data, ambiguous = _documents(home, runtime, snap)
    if ambiguous:
        raise core.HomeError(
            "both opencode.json and opencode.jsonc exist; select one native config before editing"
        )
    if not isinstance(changes, list) or len(changes) > 256:
        raise core.HomeError("changes must be a list of at most 256 operations")
    parsed = [_change(change, runtime) for change in changes]
    proposed = copy.deepcopy(data)
    grouped = {}
    for change in parsed:
        relative = _route(runtime, primary, change[1])
        grouped.setdefault(relative, []).append(change)
        _edit_semantic(proposed[relative], *change[:3])
    before = _combined(runtime, primary, data)
    after = _combined(runtime, primary, proposed)
    _preserve_owned(runtime, before, after)
    writes = {}
    for relative, edits in grouped.items():
        fmt = "json" if relative == spec.get("mcp_file") else spec["format"]
        rendered = _render(fmt, texts[relative], edits)
        if not _same(_parse(rendered, fmt), proposed[relative]):
            raise core.HomeError("native rendering did not reproduce the preview")
        if len(rendered.encode("utf-8")) > native.MAX_FILE_BYTES:
            raise core.HomeError("native settings output exceeds the size limit")
        if rendered != texts[relative]:
            writes[relative] = rendered
    expected = {
        relative: _digest(text, snap.states[(home / relative).absolute()])
        for relative, text in texts.items()
    }
    expected[_MANIFEST] = _digest(
        snap.read(home / _MANIFEST), snap.states[(home / _MANIFEST).absolute()]
    )
    snap.verify()
    plan = {
        "format": _PLAN_FORMAT,
        "runtime": runtime,
        "catalog_revision": CATALOG_REVISION,
        "observed_version": version,
        "home_anchor": list(chain[-1]),
        "expected": expected,
        "changes": [
            {
                "op": op,
                "path": _encoded(path),
                **({"value": value} if op == "set" else {}),
            }
            for op, path, value, _alias in parsed
        ],
        "before": _redact(before, runtime=runtime),
        "after": _redact(after, runtime=runtime),
        "targets": sorted(writes),
        "preview": True,
        "would_change": bool(writes),
        "risks": [
            "Native tools, execution, or permission behavior changes; review before applying."
        ]
        if any(
            p[1][0]
            in {
                spec["mcp"],
                "hooks",
                "permission",
                "permissions",
                "sandbox_mode",
                "approval_policy",
                "tools",
            }
            for p in parsed
        )
        else [],
    }
    return plan, writes


def plan_changes(home, runtime, changes, *, version=None):
    _runtime(runtime, version)
    with _snapshot(home) as (normalized_home, _fd, chain, snap):
        home = normalized_home
        return _make_plan(home, runtime, changes, version, chain, snap)[0]


def apply_plan(home, plan):
    if (
        not isinstance(plan, dict)
        or plan.get("format") != _PLAN_FORMAT
        or plan.get("preview") is not True
    ):
        raise core.HomeError("invalid settings plan")
    runtime, version = plan.get("runtime"), plan.get("observed_version")
    _runtime(runtime, version)
    with _snapshot(home, writing=True) as (normalized_home, root_fd, chain, snap):
        home = normalized_home
        reproduced, writes = _make_plan(
            home, runtime, plan.get("changes"), version, chain, snap
        )
        if not _same(reproduced, plan):
            raise core.HomeError(
                "stale or modified settings plan; create and review a new preview"
            )
        relatives = tuple(sorted(writes))
        native._preflight_destinations(root_fd, home, snap, relatives)
        parents, chains = native._prepare_parents(root_fd, home, chain, relatives)
        published = {}
        try:
            for relative in relatives:
                native._verify_for_publish(
                    home, chain, snap, parents, chains, relatives, published
                )
                parts = Path(relative).parts
                info = publish_file(
                    parents[parts[:-1]],
                    parts[-1],
                    writes[relative],
                    expected=snap.states[(home / relative).absolute()],
                )
                published[(home / relative).absolute()] = (
                    writes[relative].encode("utf-8"),
                    _identity(info),
                )
                native._verify_for_publish(
                    home, chain, snap, parents, chains, relatives, published
                )
            snap.verify(published)
        except (core.HomeError, OSError) as exc:
            if published or getattr(exc, "published", False):
                raise core.HomeError(
                    "settings publication may be partial; inspect native files before retrying"
                ) from exc
            raise
        finally:
            for descriptor in parents.values():
                os.close(descriptor)
    return {
        "runtime": runtime,
        "applied": True,
        "changed": list(relatives),
        "preview": False,
    }


def _merge(left, right, *, arrays=False, trace=None, source=None, prefix=()):
    """Resolve values and, optionally, track the layers that actually survive."""
    result = copy.deepcopy(left)

    def record(value, path):
        assert trace is not None and source is not None
        trace[path] = [source]
        if isinstance(value, dict):
            for key, child in value.items():
                record(child, path + (key,))

    def forget(value, path):
        assert trace is not None
        trace.pop(path, None)
        if isinstance(value, dict):
            for key, child in value.items():
                forget(child, path + (key,))

    for key, value in right.items():
        path = prefix + (key,)
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(
                result[key],
                value,
                arrays=arrays,
                trace=trace,
                source=source,
                prefix=path,
            )
        elif arrays and isinstance(value, list) and isinstance(result.get(key), list):
            previous_keys = {_canonical(item) for item in result[key]}
            added = [item for item in value if _canonical(item) not in previous_keys]
            result[key] = result[key] + added
            if trace is not None and added:
                assert source is not None
                trace[path] = sorted({*trace.get(path, []), source})
        else:
            if trace is not None:
                # Replacing a container also discards all its former origins.
                forget(result.get(key, _MISSING), path)
            result[key] = copy.deepcopy(value)
            if trace is not None:
                record(value, path)
        if trace is not None and isinstance(result[key], dict) and result[key]:
            trace[path] = sorted(
                {
                    layer
                    for child in result[key]
                    for layer in trace.get(path + (child,), [])
                }
            )
    return result


def _external_files(runtime, root, name):
    if name == "user":
        files = {
            "codex": [(".codex/config.toml", "toml")],
            "pi": [(".pi/agent/settings.json", "json")],
            "claude": [(".claude/settings.json", "json")],
            "opencode": [
                (".config/opencode/opencode.json", "jsonc"),
                (".config/opencode/opencode.jsonc", "jsonc"),
            ],
        }
    else:
        spec = _runtime(runtime)
        files = {runtime: [(spec["file"], spec["format"])]}
        if runtime == "opencode":
            files[runtime].append(("opencode.jsonc", "jsonc"))
        if runtime == "claude":
            files[runtime].append((".claude/settings.local.json", "json"))
        if "mcp_file" in spec:
            files[runtime].append((spec["mcp_file"], "json"))
    return [
        (
            root / relative,
            fmt,
            "project-local"
            if relative.endswith("settings.local.json")
            else name + "-mcp"
            if relative.endswith("mcp.json")
            else name,
        )
        for relative, fmt in files[runtime]
    ]


def inspect_settings(home, runtime, *, project=None, user_dir=None, version=None):
    _runtime(runtime, version)
    with _snapshot(home) as (normalized_home, _fd, _chain, snap):
        home = normalized_home
        _spec, primary, texts, data, ambiguous = _documents(home, runtime, snap)
        external_snap = native._NativeSnapshot()
        own = _combined(runtime, primary, data)
        layers = []
        resolved = {}
        active_scope = "project" if project is not None else "home"
        trace = {}

        def admit(name, path, values, present, active, writable):
            nonlocal resolved
            layers.append(
                {
                    "name": name,
                    "path": str(path),
                    "present": present,
                    "active": active,
                    "writable": writable,
                    "values": _redact(values, runtime=runtime),
                }
            )
            if active and present:
                resolved = _merge(
                    resolved,
                    values,
                    arrays=runtime in {"claude", "opencode"},
                    trace=trace,
                    source=len(layers) - 1,
                )

        if user_dir is not None:
            for path, fmt, name in _external_files(
                runtime, Path(user_dir).expanduser().absolute(), "user"
            ):
                text = external_snap.read(path)
                admit(name, path, _parse(text, fmt), text is not None, True, False)
        admit("home", home / primary, data[primary], True, active_scope == "home", True)
        if "mcp_file" in _spec:
            auxiliary = _spec["mcp_file"]
            admit(
                "home-mcp",
                home / auxiliary,
                data[auxiliary],
                texts[auxiliary] is not None,
                active_scope == "home",
                True,
            )
        if active_scope == "home" and runtime == "claude":
            path = home / ".claude/settings.local.json"
            text = snap.read(path)
            admit(
                "home-local", path, _parse(text, "json"), text is not None, True, False
            )
        if project is not None:
            for path, fmt, name in _external_files(
                runtime, Path(project).expanduser().absolute(), "project"
            ):
                text = external_snap.read(path)
                admit(name, path, _parse(text, fmt), text is not None, True, False)
        contributors = {
            _encoded(path): list(
                dict.fromkeys(layers[index]["name"] for index in indices)
            )
            for path, indices in trace.items()
        }
        origins = {path: names[-1] for path, names in contributors.items() if names}
        snap.verify()
        external_snap.verify()
        external_snap.close()
        diagnostics = [
            "Static observed files only: CLI/environment, trust, profiles, remote defaults and managed policy may change runtime results.",
            "Credential screening is heuristic; arbitrary executable strings cannot be proven secret-free.",
            "User inputs are HOME-like roots; XDG overrides, parent-directory discovery and remote config are not inferred.",
        ]
        if runtime == "codex" and project is not None:
            diagnostics.append(
                "Codex project trust is unknown; project-file resolution is conditional, not runtime-effective."
            )
        if ambiguous:
            diagnostics.append(
                "Both OpenCode JSON and JSONC files exist; home resolution is ambiguous and editing is refused."
            )
        fields = []
        for field in catalog(runtime)["fields"]:
            path = tuple(field["path"])
            value = _resolved(resolved, path, _MISSING)
            classification = "not-configured"
            if value is not _MISSING:
                try:
                    _validate_value(runtime, path, value)
                    classification = "shape-valid"
                except core.HomeError:
                    classification = "invalid-known-field"
            fields.append({"path": list(path), "classification": classification})
        return {
            "runtime": runtime,
            "catalog": catalog(runtime, version=version),
            "layers": layers,
            "home_values": _redact(own, runtime=runtime),
            "effective": _redact(resolved, runtime=runtime),
            "effective_status": "conditional static resolution of supplied files, not native runtime-effective configuration",
            "runtime_effective": False,
            "active_scope": active_scope,
            "origins": origins,
            "contributors": contributors,
            "origin_semantics": "Surviving layers from the actual static merge; replaced values discard earlier origins.",
            "field_classification": fields,
            "diagnostics": diagnostics,
        }


def get_setting(home, runtime, key, *, project=None, user_dir=None, version=None):
    _runtime(runtime, version)
    path = _pointer(key, runtime)
    report = inspect_settings(
        home, runtime, project=project, user_dir=user_dir, version=version
    )
    value = _resolved(report["effective"], path, _MISSING)
    source = report["origins"].get(_encoded(path))
    if source is None and path[0] in report["effective"]:
        source = report["origins"].get(_encoded(path[:1]))
    sources = report["contributors"].get(_encoded(path), [])
    if value is _MISSING:
        source = None
    elif isinstance(value, (dict, list)) and len(sources) > 1:
        source = "merged"
    return {
        "runtime": runtime,
        "key": key,
        "path": list(path),
        "present": value is not _MISSING,
        "value": None if value is _MISSING else value,
        "source": source,
        "sources": sources,
        "runtime_effective": False,
    }


def export_profile(home, runtime):
    _runtime(runtime)
    omissions = []
    spec = _runtime(runtime)
    with _snapshot(home) as (normalized_home, _fd, _chain, snap):
        home = normalized_home
        _, primary, _, data, ambiguous = _documents(home, runtime, snap)
        if ambiguous:
            raise core.HomeError(
                "ambiguous OpenCode documents cannot be exported as one profile"
            )
        values = _combined(runtime, primary, data)

        def clean(value, path=()):
            if (
                len(path) == 1
                and path[0] in OWNED_IDENTITY[runtime]
                or path == (spec["mcp"], "hindsight")
            ):
                omissions.append(
                    {"path": _encoded(path), "reason": "Soulsteads-owned field"}
                )
                return _MISSING
            if isinstance(value, dict) and not (path and _SECRET_KEY.search(path[-1])):
                result = {}
                for key, item in value.items():
                    child = clean(item, path + (key,))
                    if child is not _MISSING:
                        result[key] = child
                return result
            try:
                _secret_check(value, path, runtime)
            except core.HomeError:
                omissions.append(
                    {
                        "path": _encoded(path),
                        "reason": "credential-like or nonportable value",
                    }
                )
                return _MISSING
            return copy.deepcopy(value)

        exported = clean(values)
        snap.verify()
    return {
        "format": "soulsteads-settings-v1",
        "runtime": runtime,
        "catalog_revision": CATALOG_REVISION,
        "settings": exported,
        "omissions": omissions,
        "limits": [
            "Review before sharing: arbitrary command strings are not proven secret-free."
        ],
    }


def plan_import(home, runtime, profile, *, version=None):
    _runtime(runtime, version)
    if (
        not isinstance(profile, dict)
        or profile.get("format") != "soulsteads-settings-v1"
        or profile.get("runtime") != runtime
    ):
        raise core.HomeError("unsupported native settings profile")
    if not _same(profile.get("catalog_revision"), CATALOG_REVISION) or not isinstance(
        profile.get("settings"), dict
    ):
        raise core.HomeError("unsupported settings profile revision or value shape")
    values = _plain(profile["settings"])
    if not isinstance(values, dict):
        raise core.HomeError("settings profile values must be an object")
    _secret_check(values, runtime=runtime)
    changes = []
    mcp_root = runtime_spec(runtime)["mcp"]
    for key, value in values.items():
        if key == mcp_root:
            if not isinstance(value, dict):
                raise core.HomeError("profile MCP settings must be an object")
            # Export omits owned Hindsight wiring. Import only the explicitly
            # portable entries; never replace the destination's whole MCP map.
            for name, server in value.items():
                changes.append(
                    {"op": "set", "path": _encoded((key, name)), "value": server}
                )
        else:
            changes.append({"op": "set", "path": _encoded((key,)), "value": value})
    return plan_changes(home, runtime, changes, version=version)
