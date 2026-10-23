"""Offline publication of native files; no execution, model calls or global writes."""

import hashlib
import json
import os
import re
import stat
import tomllib
from pathlib import Path
from urllib.parse import urlsplit

from . import core
from .hermes_import import _identity, _open_dir
from .runtimes import CODEX_BEGIN, CODEX_END, IDENTITY_FILES, digest, render_all

MAX_FILE_BYTES = 1024 * 1024


def _read(path, snapshot=None):
    """Read one bounded regular file through a no-follow directory descriptor."""
    path = Path(path)
    key = path.absolute()
    try:
        if snapshot is not None and snapshot.root_fd is not None:
            relative = path.relative_to(snapshot.home)
            directory = _open_relative_dir(snapshot.root_fd, relative.parts[:-1])
            chain = snapshot.root_chain
        else:
            directory, chain = _open_dir(path.parent)
    except FileNotFoundError:
        if snapshot is not None:
            snapshot.record(key, None, None, None)
        return None
    except OSError as exc:
        raise core.HomeError("unsafe native configuration path") from exc
    descriptor = -1
    try:
        try:
            before = os.stat(path.name, dir_fd=directory, follow_symlinks=False)
        except FileNotFoundError:
            if snapshot is not None and snapshot.root_fd is None:
                rebound, current_chain = _open_dir(path.parent)
                try:
                    if current_chain != chain:
                        raise core.HomeError(
                            "native configuration parent changed during read"
                        )
                finally:
                    os.close(rebound)
            if snapshot is not None:
                snapshot.record(key, None, chain, None)
            return None
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_uid != os.getuid()
            or before.st_nlink != 1
            or before.st_size > MAX_FILE_BYTES
        ):
            raise core.HomeError("unsafe native configuration file")
        descriptor = os.open(
            path.name,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
            dir_fd=directory,
        )
        if _identity(os.fstat(descriptor)) != _identity(before):
            raise core.HomeError("native configuration changed during read")
        data = bytearray()
        while len(data) <= MAX_FILE_BYTES:
            chunk = os.read(descriptor, min(65536, MAX_FILE_BYTES + 1 - len(data)))
            if not chunk:
                break
            data.extend(chunk)
        if (
            len(data) != before.st_size
            or _identity(os.fstat(descriptor)) != _identity(before)
            or _identity(os.stat(path.name, dir_fd=directory, follow_symlinks=False))
            != _identity(before)
        ):
            raise core.HomeError("native configuration changed during read")
        if snapshot is None or snapshot.root_fd is None:
            rebound, current_chain = _open_dir(path.parent)
            try:
                if current_chain != chain:
                    raise core.HomeError(
                        "native configuration parent changed during read"
                    )
            finally:
                os.close(rebound)
        try:
            result = data.decode("utf-8")
        except UnicodeError as exc:
            raise core.HomeError("native configuration is not valid UTF-8") from exc
        if snapshot is not None:
            snapshot.record(
                key, _identity(before), chain, hashlib.sha256(data).digest()
            )
        return result
    except OSError as exc:
        raise core.HomeError("unsafe or changing native configuration file") from exc
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        os.close(directory)


class _NativeSnapshot:
    """Stable input identities; directory checks exclude mutable mtime metadata."""

    def __init__(self, home=None, root_fd=None, root_chain=None):
        self.states = {}
        self.chains = {}
        self.hashes = {}
        self.home = Path(home).absolute() if home is not None else None
        self.root_fd = os.dup(root_fd) if root_fd is not None else None
        self.root_chain = root_chain

    def close(self):
        if self.root_fd is not None:
            os.close(self.root_fd)
            self.root_fd = None

    def record(self, path, identity, chain, content_hash):
        if path in self.states and (
            self.states[path] != identity
            or self.chains[path] != chain
            or self.hashes[path] != content_hash
        ):
            raise core.HomeError("native input changed during planning")
        self.states[path] = identity
        self.chains[path] = chain
        self.hashes[path] = content_hash

    def read(self, path):
        return _read(path, self)

    def verify(self, excluded=()):
        excluded = set(excluded)
        for path, expected in self.states.items():
            if path in excluded:
                continue
            current = _NativeSnapshot(self.home, self.root_fd, self.root_chain)
            try:
                current.read(path)
            finally:
                current.close()
            if (
                current.states[path] != expected
                or current.hashes[path] != self.hashes[path]
                or (
                    self.chains[path] is not None
                    and current.chains[path] != self.chains[path]
                )
            ):
                raise core.HomeError("native input changed during sync")


def _json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def constant(value):
        raise ValueError("nonstandard JSON constant")

    value = json.loads(text, object_pairs_hook=pairs, parse_constant=constant)
    if not isinstance(value, dict):
        raise TypeError("native JSON must be an object")
    return value


def _merge_json(current, desired, previous=None, *, managed=False):
    """Three-way merge of owned settings; unrelated user keys stay authoritative."""
    previous = previous or {}
    result = dict(current)
    for key in previous.keys() - desired.keys():
        if key not in current:
            continue
        if key == "hindsight" and current[key] != previous[key]:
            raise ValueError("customized Hindsight server cannot be removed")
        if isinstance(previous[key], dict) and isinstance(current[key], dict):
            remaining = _merge_json(current[key], {}, previous[key], managed=managed)
            if remaining:
                result[key] = remaining
            else:
                del result[key]
        elif current[key] == previous[key]:
            del result[key]
        else:
            raise ValueError("customized setting cannot be removed")
    for key, value in desired.items():
        if key not in current:
            if managed and key in previous:
                raise ValueError("managed setting cannot be removed")
            result[key] = value
        elif isinstance(value, dict) and isinstance(current[key], dict):
            old = previous.get(key, {})
            result[key] = _merge_json(
                current[key],
                value,
                old if isinstance(old, dict) else {},
                managed=managed,
            )
        elif key == "instructions" and isinstance(current[key], list):
            if not all(isinstance(item, str) for item in current[key]):
                raise ValueError("invalid instructions list")
            old_items = previous.get(key, [])
            if managed and any(item not in current[key] for item in old_items):
                raise ValueError("managed instructions cannot be removed")
            result[key] = list(current[key])
            for item in value:
                if item not in result[key]:
                    result[key].append(item)
        elif current[key] == value or (
            key in previous and current[key] == previous[key]
        ):
            result[key] = value
        else:
            raise ValueError("conflicting native setting")
    return result


def validate_hindsight(value):
    if value is None:
        return
    if not isinstance(value, dict) or set(value) != {"url", "token_env"}:
        raise core.HomeError("invalid Hindsight configuration")
    url, token_env = value["url"], value["token_env"]
    if not isinstance(url, str) or not isinstance(token_env, str):
        raise core.HomeError("invalid Hindsight configuration")
    try:
        parsed = urlsplit(url)
        port = parsed.port
    except ValueError:
        raise core.HomeError("invalid Hindsight URL; details suppressed") from None
    if (
        parsed.scheme not in ("https", "http")
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or any(c.isspace() or ord(c) < 32 for c in url)
        or not re.fullmatch(r"(?:/[^/]+)*/mcp/[^/]+/", parsed.path)
        or (
            parsed.scheme == "http"
            and parsed.hostname not in ("localhost", "127.0.0.1", "::1")
        )
        or (port is not None and not 1 <= port <= 65535)
        or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", token_env)
    ):
        raise core.HomeError(
            "Hindsight needs a credential-free HTTPS per-bank /mcp/<bank>/ URL and a token environment-variable name (HTTP is allowed only on loopback)"
        )


def _codex(current, desired, expected):
    if current is None:
        result = desired
    elif current.startswith(CODEX_BEGIN):
        if current.count(CODEX_BEGIN) != 1 or current.count(CODEX_END) != 1:
            raise ValueError("invalid managed Codex block")
        end = current.index(CODEX_END) + len(CODEX_END)
        old = current[:end]
        if digest(old) != expected and old != desired:
            raise ValueError("customized managed Codex block")
        result = desired + current[end:]
    else:
        parsed = tomllib.loads(current)
        if (
            "developer_instructions" in parsed
            or CODEX_BEGIN in current
            or CODEX_END in current
        ):
            raise ValueError("existing Codex instructions require manual review")
        result = desired + "\n" + current
    tomllib.loads(result)
    return result


def configure_runtime(home, runtime):
    """Update only the manifest runtime through the checked publisher."""
    from . import publication
    from .runtimes import RUNTIMES

    home = Path(home).expanduser().absolute()
    if ".." in home.parts:
        raise core.HomeError("parent traversal is not allowed")
    try:
        root_fd, root_chain = _open_dir(home)
    except OSError as exc:
        raise core.HomeError("unsafe native home path") from exc
    try:
        with publication.cooperative_lock(root_fd):
            _verify_root(home, root_chain)
            snapshot = _NativeSnapshot(home, root_fd, root_chain)
            try:
                manifest = core._validate_home(home, reader=snapshot.read)
                core._assert_clean(home)
                if runtime not in RUNTIMES:
                    raise core.HomeError("unsupported runtime")
                manifest["runtime"] = runtime
                data = json.dumps(manifest, indent=2) + "\n"
                relative = "soulsteads.json"
                _verify_root(home, root_chain)
                snapshot.verify()
                parent_fds, parent_chains = _prepare_parents(
                    root_fd, home, root_chain, (relative,)
                )
                published = False
                try:
                    _verify_for_publish(
                        home,
                        root_chain,
                        snapshot,
                        parent_fds,
                        parent_chains,
                        (relative,),
                        {},
                    )
                    stat_result = publication.publish_file(
                        parent_fds[()],
                        relative,
                        data,
                        expected=snapshot.states[_path_key(home, relative)],
                    )
                    published = True
                    outputs = {
                        _path_key(home, relative): (
                            data.encode(),
                            _identity(stat_result),
                        )
                    }
                    _verify_for_publish(
                        home,
                        root_chain,
                        snapshot,
                        parent_fds,
                        parent_chains,
                        (relative,),
                        outputs,
                    )
                except (core.HomeError, OSError) as exc:
                    if published or getattr(exc, "published", False):
                        raise core.HomeError(
                            "native publication partially applied; applied=['soulsteads.json']; remaining=[]; "
                            "review the retained Home manifest before retrying"
                        ) from exc
                    raise
                finally:
                    for descriptor in parent_fds.values():
                        os.close(descriptor)
            finally:
                snapshot.close()
    finally:
        os.close(root_fd)


UNSET = object()


def plan(home, manifest, *, hindsight=UNSET, read=None):
    """Preflight every file before publication. Returns files and ownership hashes."""
    home = Path(home)
    read = read or _read
    documents = {name: read(home / name) for name in IDENTITY_FILES}
    if any(value is None for value in documents.values()):
        raise core.HomeError("required identity file is missing")
    previous_hindsight = manifest.get("hindsight")
    if hindsight is UNSET:
        hindsight = previous_hindsight
    validate_hindsight(previous_hindsight)
    validate_hindsight(hindsight)
    previous = render_all(documents, previous_hindsight)
    generated = render_all(documents, hindsight)
    managed = manifest.get("managed_files", {})
    if not isinstance(managed, dict) or any(
        not isinstance(path, str)
        or not isinstance(value, str)
        or len(value) != 64
        or any(c not in "0123456789abcdef" for c in value)
        for path, value in managed.items()
    ):
        raise core.HomeError("invalid native ownership metadata")
    writes = {}
    for relative in dict.fromkeys([*generated, *previous]):
        desired = generated.get(relative, "{}\n")
        try:
            current = read(home / relative)
            if relative.endswith(".json"):
                value = _merge_json(
                    _json(current or "{}"),
                    _json(desired),
                    _json(previous.get(relative, "{}")),
                    managed=relative in managed and current is not None,
                )
                # Preserve original formatting when no settings changed.
                result = (
                    current
                    if current is not None and _json(current) == value
                    else json.dumps(value, indent=2) + "\n"
                )
            elif relative.endswith(".toml"):
                result = _codex(current, desired, managed.get(relative))
            else:
                if (
                    current is not None
                    and current != desired
                    and digest(current) != managed.get(relative)
                ):
                    raise ValueError("customized generated file")
                result = desired
            if len(result.encode("utf-8")) > MAX_FILE_BYTES:
                raise ValueError("generated file is too large")
            if current != result:
                writes[relative] = result
        except (ValueError, TypeError, KeyError, RecursionError) as exc:
            raise core.HomeError(
                f"native configuration conflict: {relative}; preserve your edits and review locally"
            ) from exc
    return writes, {path: digest(text) for path, text in generated.items()}


def _relative_parts(relative):
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise core.HomeError("invalid native destination")
    return path.parts


def _open_relative_dir(root_fd, parts, *, create=False):
    descriptor = os.dup(root_fd)
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    try:
        for part in parts:
            try:
                child = os.open(part, flags, dir_fd=descriptor)
            except FileNotFoundError:
                if not create:
                    raise
                try:
                    os.mkdir(part, mode=0o700, dir_fd=descriptor)
                except FileExistsError:
                    pass
                child = os.open(part, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _path_key(home, relative):
    return (home / relative).absolute()


def _check_leaf(parent_fd, name, expected):
    try:
        current = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        if expected is None:
            return
        raise core.HomeError("native destination disappeared") from None
    if (
        expected is None
        or not stat.S_ISREG(current.st_mode)
        or current.st_uid != os.getuid()
        or current.st_nlink != 1
        or _identity(current) != expected
    ):
        raise core.HomeError("native destination changed after preflight")


def _preflight_destinations(root_fd, home, snapshot, relatives):
    for relative in relatives:
        parts = _relative_parts(relative)
        expected = snapshot.states.get(_path_key(home, relative), ...)
        if expected is ...:
            raise core.HomeError("native destination was not admitted")
        try:
            parent_fd = _open_relative_dir(root_fd, parts[:-1])
        except FileNotFoundError:
            if expected is not None:
                raise core.HomeError("native destination parent disappeared") from None
            continue
        except OSError as exc:
            raise core.HomeError("unsafe native destination parent") from exc
        try:
            _check_leaf(parent_fd, parts[-1], expected)
        finally:
            os.close(parent_fd)


def _prepare_parents(root_fd, home, root_chain, relatives):
    parent_parts = {_relative_parts(relative)[:-1] for relative in relatives}
    descriptors = {}
    chains = {}
    try:
        for parts in sorted(parent_parts):
            descriptor = _open_relative_dir(root_fd, parts, create=True)
            path = home.joinpath(*parts)
            try:
                rebound, chain = _open_dir(path)
                try:
                    if not parts and chain != root_chain:
                        raise core.HomeError("native home root changed")
                    info = os.fstat(descriptor)
                    if not chain or chain[-1] != (
                        info.st_dev,
                        info.st_ino,
                        info.st_mode,
                        info.st_uid,
                    ):
                        raise core.HomeError("native destination parent changed")
                finally:
                    os.close(rebound)
            except BaseException:
                os.close(descriptor)
                raise
            descriptors[parts] = descriptor
            chains[parts] = chain
        return descriptors, chains
    except BaseException:
        for descriptor in descriptors.values():
            os.close(descriptor)
        raise


def _verify_root(home, expected):
    descriptor, chain = _open_dir(home)
    try:
        if chain != expected:
            raise core.HomeError("native home root changed")
    finally:
        os.close(descriptor)


def _verify_for_publish(
    home, root_chain, snapshot, parent_fds, parent_chains, relatives, published
):
    _verify_root(home, root_chain)
    snapshot.verify(published)
    for parts, expected_chain in parent_chains.items():
        descriptor, chain = _open_dir(home.joinpath(*parts))
        try:
            retained = os.fstat(parent_fds[parts])
            if (
                chain != expected_chain
                or not chain
                or chain[-1]
                != (
                    retained.st_dev,
                    retained.st_ino,
                    retained.st_mode,
                    retained.st_uid,
                )
            ):
                raise core.HomeError("native destination parent changed")
        finally:
            os.close(descriptor)
    for relative in relatives:
        key = _path_key(home, relative)
        parts = _relative_parts(relative)
        if key in published:
            expected_bytes, expected_identity = published[key]
            fd = os.open(
                parts[-1],
                os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                dir_fd=parent_fds[parts[:-1]],
            )
            try:
                info = os.fstat(fd)
                if _identity(info) != expected_identity:
                    raise core.HomeError("published native output changed during sync")
                data = bytearray()
                while len(data) <= len(expected_bytes):
                    chunk = os.read(fd, min(65536, len(expected_bytes) + 1 - len(data)))
                    if not chunk:
                        break
                    data.extend(chunk)
                if (
                    _identity(info) != expected_identity
                    or bytes(data) != expected_bytes
                    or _identity(os.fstat(fd)) != expected_identity
                    or _identity(
                        os.stat(
                            parts[-1],
                            dir_fd=parent_fds[parts[:-1]],
                            follow_symlinks=False,
                        )
                    )
                    != expected_identity
                ):
                    raise core.HomeError("published native output changed during sync")
            finally:
                os.close(fd)
        else:
            _check_leaf(parent_fds[parts[:-1]], parts[-1], snapshot.states[key])


def sync(home, runtime=None, *, hindsight=UNSET):
    """Refresh native projections through the cooperative publication lock."""
    from . import publication

    home = Path(home).expanduser()
    if ".." in home.parts:
        raise core.HomeError("parent traversal is not allowed")
    home = home.absolute()
    root_fd, root_chain = _open_dir(home)
    try:
        with publication.cooperative_lock(root_fd):
            return _sync_locked(
                home,
                runtime,
                hindsight=hindsight,
                root_fd=root_fd,
                root_chain=root_chain,
            )
    finally:
        os.close(root_fd)


def _sync_locked(home, runtime=None, *, hindsight=UNSET, root_fd=None, root_chain=None):
    """Plan and publish native projections while caller holds home lock."""
    from . import publication
    from .runtimes import RUNTIMES

    home = Path(home).expanduser()
    if ".." in home.parts:
        raise core.HomeError("parent traversal is not allowed")
    home = home.absolute()
    if root_fd is None or root_chain is None:
        raise core.HomeError("native sync requires the retained locked home root")
    parent_fds = {}
    snapshot = _NativeSnapshot(home, root_fd, root_chain)
    try:
        _verify_root(home, root_chain)
        manifest = core._validate_home(home, reader=snapshot.read)
        _verify_root(home, root_chain)
        if runtime is not None:
            if runtime not in RUNTIMES:
                raise core.HomeError("unsupported runtime")
            manifest["runtime"] = runtime
        writes, managed = plan(home, manifest, hindsight=hindsight, read=snapshot.read)
        if hindsight is not UNSET:
            if hindsight is None:
                manifest.pop("hindsight", None)
            else:
                manifest["hindsight"] = hindsight
        manifest["managed_files"] = managed
        manifest_text = json.dumps(manifest, indent=2) + "\n"
        if snapshot.read(home / "soulsteads.json") != manifest_text:
            publications = dict(writes)
            publications["soulsteads.json"] = manifest_text
        else:
            publications = dict(writes)
        relatives = tuple(publications)
        if not relatives:
            _verify_root(home, root_chain)
            snapshot.verify()
            return sorted(writes)

        _preflight_destinations(root_fd, home, snapshot, relatives)
        _verify_root(home, root_chain)
        snapshot.verify()
        parent_fds, parent_chains = _prepare_parents(
            root_fd, home, root_chain, relatives
        )
        published = {}
        applied = []
        ordered = list(publications.items())
        for index, (relative, text) in enumerate(ordered):
            try:
                _verify_for_publish(
                    home,
                    root_chain,
                    snapshot,
                    parent_fds,
                    parent_chains,
                    relatives,
                    published,
                )
                parts = _relative_parts(relative)
                result = publication.publish_file(
                    parent_fds[parts[:-1]],
                    parts[-1],
                    text,
                    expected=snapshot.states[_path_key(home, relative)],
                )
                published[_path_key(home, relative)] = (
                    text.encode("utf-8"),
                    _identity(result),
                )
                applied.append(relative)
                _verify_for_publish(
                    home,
                    root_chain,
                    snapshot,
                    parent_fds,
                    parent_chains,
                    relatives,
                    published,
                )
            except Exception as exc:
                if getattr(exc, "published", False):
                    try:
                        current = os.stat(
                            _relative_parts(relative)[-1],
                            dir_fd=parent_fds[_relative_parts(relative)[:-1]],
                            follow_symlinks=False,
                        )
                        published[_path_key(home, relative)] = (
                            text.encode("utf-8"),
                            _identity(current),
                        )
                    except OSError:
                        pass
                    if relative not in applied:
                        applied.append(relative)
                remaining = [path for path, _ in ordered if path not in applied]
                if applied:
                    raise core.HomeError(
                        "native publication partially applied; "
                        f"applied={applied!r}; remaining={remaining!r}; "
                        "reconcile by reviewing these paths and rerunning config --sync"
                    ) from exc
                raise
        try:
            _verify_for_publish(
                home,
                root_chain,
                snapshot,
                parent_fds,
                parent_chains,
                relatives,
                published,
            )
        except (core.HomeError, OSError) as exc:
            raise core.HomeError(
                "native publication partially applied; "
                f"applied={applied!r}; remaining=[]; "
                "reconcile by reviewing these paths and rerunning config --sync"
            ) from exc
        return sorted(writes)
    except OSError as exc:
        raise core.HomeError("native configuration path changed during sync") from exc
    finally:
        for descriptor in parent_fds.values():
            os.close(descriptor)
        snapshot.close()
