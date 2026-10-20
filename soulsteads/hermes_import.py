"""Explicit local Hermes imports; no source execution or live ownership transfer."""

from __future__ import annotations

import ctypes
import errno
import json
import os
import re
import secrets
import shutil
import stat
from pathlib import Path

from . import core

MAX_FILE = 2 * 1024 * 1024
MAX_TOTAL = 64 * 1024 * 1024
MAX_ENTRIES = 10000
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")


class ImportErrorSafe(core.HomeError):
    """An importer error that never includes source content or parser excerpts."""


def require_yaml():
    try:
        import yaml
    except ImportError:
        raise ImportErrorSafe(
            "Hermes import requires PyYAML; install 'soulsteads[hermes]'"
        ) from None
    return yaml


def _yaml(raw):
    yaml = require_yaml()

    class StrictLoader(yaml.SafeLoader):
        pass

    def mapping(loader, node):
        result = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node)
            if not isinstance(key, str) or key in result:
                raise ImportErrorSafe("invalid or duplicate YAML mapping key")
            result[key] = loader.construct_object(value_node)
        return result

    StrictLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping
    )
    try:
        depth = 0
        for count, event in enumerate(yaml.parse(raw), 1):
            if count > 20000 or isinstance(event, yaml.events.AliasEvent):
                raise ImportErrorSafe(
                    "YAML aliases or excessive nodes are not supported"
                )
            if isinstance(
                event, (yaml.events.MappingStartEvent, yaml.events.SequenceStartEvent)
            ):
                depth += 1
            elif isinstance(
                event, (yaml.events.MappingEndEvent, yaml.events.SequenceEndEvent)
            ):
                depth -= 1
            if depth > 40:
                raise ImportErrorSafe("YAML nesting exceeds import limit")
        value = yaml.load(raw, Loader=StrictLoader)
        if value is None:
            value = {}
        if not isinstance(value, dict):
            raise ImportErrorSafe("YAML must be a mapping")
        return value
    except (yaml.YAMLError, UnicodeError, ValueError, TypeError, RecursionError):
        raise ImportErrorSafe("invalid YAML; source details suppressed") from None


def _identity(info):
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_uid,
        info.st_nlink,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def _absolute(path):
    path = Path(path).expanduser()
    if ".." in path.parts:
        raise ImportErrorSafe("parent traversal is not allowed")
    return path.absolute()


def _open_dir(path):
    """Walk all lexical ancestors without following directory links."""
    path = _absolute(path)
    fd = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    chain = []
    try:
        for part in path.parts[1:]:
            new = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = new
            info = os.fstat(fd)
            sticky = info.st_uid == 0 and info.st_mode & stat.S_ISVTX
            if info.st_uid not in (0, os.getuid()) or (
                info.st_mode & 0o022 and not sticky
            ):
                raise ImportErrorSafe(
                    "unsafe source or destination directory permissions"
                )
            chain.append((info.st_dev, info.st_ino, info.st_mode, info.st_uid))
        return fd, chain
    except BaseException:
        os.close(fd)
        raise


class Snapshot:
    """Bounded source bytes plus file, absence, and ancestor identity checks."""

    def __init__(self):
        self.files = {}
        self.dirs = {}
        self.absent = set()
        self.total = 0

    def directory(self, path):
        path = _absolute(path)
        fd, chain = _open_dir(path)
        try:
            record = (chain, _identity(os.fstat(fd)))
            if self.dirs.setdefault(path, record) != record:
                raise ImportErrorSafe("source directory changed")
        finally:
            os.close(fd)

    def read(self, path):
        path = _absolute(path)
        if path in self.files:
            return self.files[path][0]
        # Record every absent optional path without following any existing ancestor.
        ancestor = path.parent
        missing = []
        while True:
            try:
                fd, _ = _open_dir(ancestor)
                os.close(fd)
                self.directory(ancestor)
                break
            except FileNotFoundError:
                missing.append(ancestor)
                ancestor = ancestor.parent
        if missing:
            self.absent.add(missing[-1])
            return None
        fd, _ = _open_dir(path.parent)
        try:
            try:
                before = os.stat(path.name, dir_fd=fd, follow_symlinks=False)
            except FileNotFoundError:
                self.absent.add(path)
                return None
            if (
                not stat.S_ISREG(before.st_mode)
                or before.st_uid != os.getuid()
                or before.st_nlink != 1
                or before.st_size > MAX_FILE
            ):
                raise ImportErrorSafe(
                    "unsafe source file type, ownership, links or size"
                )
            child = os.open(
                path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd
            )
            try:
                if _identity(os.fstat(child)) != _identity(before):
                    raise ImportErrorSafe("source changed during read")
                data = bytearray()
                while len(data) <= MAX_FILE:
                    chunk = os.read(child, min(65536, MAX_FILE + 1 - len(data)))
                    if not chunk:
                        break
                    data.extend(chunk)
                if (
                    len(data) != before.st_size
                    or _identity(os.fstat(child)) != _identity(before)
                    or _identity(os.stat(path.name, dir_fd=fd, follow_symlinks=False))
                    != _identity(before)
                ):
                    raise ImportErrorSafe("source changed during read")
            finally:
                os.close(child)
        finally:
            os.close(fd)
        self.total += len(data)
        if self.total > MAX_TOTAL or len(self.files) >= MAX_ENTRIES:
            raise ImportErrorSafe("aggregate import limit exceeded")
        self.files[path] = (bytes(data), _identity(before))
        return bytes(data)

    def verify(self):
        for path, (chain, info) in self.dirs.items():
            fd, current = _open_dir(path)
            try:
                if chain != current or _identity(os.fstat(fd)) != info:
                    raise ImportErrorSafe(
                        "source directory binding or inventory changed"
                    )
            finally:
                os.close(fd)
        for path in self.absent:
            fd, _ = _open_dir(path.parent)
            try:
                try:
                    os.stat(path.name, dir_fd=fd, follow_symlinks=False)
                except FileNotFoundError:
                    continue
                raise ImportErrorSafe("source appeared during import")
            finally:
                os.close(fd)
        for path, (_, expected) in self.files.items():
            fd, _ = _open_dir(path.parent)
            try:
                if (
                    _identity(os.stat(path.name, dir_fd=fd, follow_symlinks=False))
                    != expected
                ):
                    raise ImportErrorSafe("source file changed during import")
            finally:
                os.close(fd)


def _names(value):
    if value is None:
        return set()
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ImportErrorSafe("invalid disabled-skills list")
    return {item.strip() for item in value if item.strip()}


def _skills(selected, config, snap, platform, unsupported):
    settings = config.get("skills") or {}
    if not isinstance(settings, dict):
        raise ImportErrorSafe("skills settings must be a mapping")
    overrides = settings.get("platform_disabled") or {}
    if not isinstance(overrides, dict):
        raise ImportErrorSafe("platform skill settings must be a mapping")
    disabled = _names(settings.get("disabled")) | _names(overrides.get(platform))
    disabled.discard("hermes-agent")
    for key in settings:
        if key not in {"disabled", "platform_disabled"} and settings[key]:
            unsupported.append(
                "additional Hermes skill discovery/settings require manual review"
            )
    root = selected / "skills"
    # An absent catalogue is recorded so a late tree cannot silently change selection.
    try:
        snap.directory(root)
    except FileNotFoundError:
        snap.read(root / "SKILL.md")
        return {}
    pending, paths, count = [root], [], 0
    excluded = {
        ".git",
        ".archive",
        "archive",
        "__pycache__",
        "node_modules",
        ".venv",
        "venv",
    }
    while pending:
        directory = pending.pop()
        snap.directory(directory)
        fd, _ = _open_dir(directory)
        try:
            for name in sorted(os.listdir(fd)):
                count += 1
                if count > MAX_ENTRIES:
                    raise ImportErrorSafe("skill inventory exceeds import limit")
                if name in excluded:
                    continue
                if name == "_org":
                    unsupported.append(
                        "organization skill discovery requires manual review"
                    )
                    continue
                info = os.stat(name, dir_fd=fd, follow_symlinks=False)
                item = directory / name
                if stat.S_ISDIR(info.st_mode):
                    pending.append(item)
                elif stat.S_ISREG(info.st_mode):
                    paths.append(item)
                else:
                    raise ImportErrorSafe("skill tree contains links or special files")
        finally:
            os.close(fd)
    owners, enabled = {}, {}
    support = {"references", "assets", "templates", "scripts"}
    import sys

    for path in sorted(paths):
        if path.name != "SKILL.md" or any(
            part in support for part in path.relative_to(root).parts[:-1]
        ):
            continue
        raw = snap.read(path)
        match = re.match(
            rb"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|$)", raw, re.DOTALL
        )
        if not match:
            raise ImportErrorSafe("skill requires YAML frontmatter")
        metadata = _yaml(match.group(1))
        name = metadata.get("name")
        description = metadata.get("description")
        if (
            not isinstance(name, str)
            or not SLUG.fullmatch(name)
            or not isinstance(description, str)
            or not description.strip()
        ):
            raise ImportErrorSafe("skill requires a slug name and nonempty description")
        if name in owners.values():
            raise ImportErrorSafe("duplicate canonical skill name")
        owners[path.parent] = name
        platforms = metadata.get("platforms") or []
        if isinstance(platforms, str):
            platforms = [platforms]
        if not isinstance(platforms, list) or any(
            not isinstance(x, str) for x in platforms
        ):
            raise ImportErrorSafe("invalid skill platform metadata")
        aliases = {"macos": "darwin", "windows": "win32"}
        host_match = not platforms or any(
            sys.platform.startswith(aliases.get(x.lower(), x.lower()))
            for x in platforms
        )
        if metadata.get("environments"):
            unsupported.append("environment-conditioned skills require manual review")
            continue
        if name not in disabled and host_match:
            enabled[name] = path.parent
    result = {}
    for path in sorted(paths):
        candidates = [owner for owner in owners if path.is_relative_to(owner)]
        if not candidates:
            continue
        owner = max(candidates, key=lambda item: len(item.parts))
        name = owners[owner]
        if enabled.get(name) != owner:
            continue
        relative = path.relative_to(owner)
        if any(part.startswith(".git") for part in relative.parts) or core._secret_path(
            relative
        ):
            raise ImportErrorSafe(
                "selected skill contains forbidden metadata or credential paths"
            )
        raw = snap.read(path)
        result[Path(name) / relative] = (
            raw,
            0o700 if snap.files[_absolute(path)][1][2] & 0o111 else 0o600,
        )
    return result


def _plan(
    name,
    source,
    profile,
    runtime,
    *,
    workspace=None,
    platform="cli",
    include_secrets=False,
):
    from .runtimes import RUNTIMES

    if not SLUG.fullmatch(name or ""):
        raise ImportErrorSafe("name must be a lowercase hyphenated slug")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", profile or ""):
        raise ImportErrorSafe("profile must be a valid Hermes profile identifier")
    if runtime not in RUNTIMES or not SLUG.fullmatch(platform or ""):
        raise ImportErrorSafe("unsupported runtime or platform name")
    require_yaml()
    source = _absolute(source)
    selected = source if profile == "default" else source / "profiles" / profile
    snap = Snapshot()
    snap.directory(selected)
    config_raw = snap.read(selected / "config.yaml")
    config = _yaml(config_raw or b"{}")
    documents = {}
    workspace = _absolute(workspace) if workspace is not None else None
    if workspace:
        snap.directory(workspace)
    for filename in ("SOUL.md", "AGENTS.md", "USER.md", "MEMORY.md"):
        raw = snap.read(selected / filename)
        if raw is None and workspace and filename != "MEMORY.md":
            raw = snap.read(workspace / filename)
        if filename in ("USER.md", "MEMORY.md"):
            memory = snap.read(selected / "memories" / filename)
            if memory is not None:
                raw = memory
        if raw is not None:
            raw.decode("utf-8")
            documents[filename] = raw
    private = {}
    if "AGENTS.md" in documents:
        private["AGENTS.md"] = documents["AGENTS.md"]
    if config_raw is not None:
        private["config.yaml"] = config_raw
    if include_secrets:
        raw = snap.read(selected / ".env")
        if raw is not None:
            private[".env"] = raw
    unsupported = []
    if any(
        value not in (None, {}, [], "", False)
        for key, value in config.items()
        if key != "skills"
    ):
        unsupported.append(
            "Hermes runtime, model, tools, permissions and service settings require manual review"
        )
    skills = _skills(selected, config, snap, platform, unsupported)
    report = {
        "name": name,
        "profile": profile,
        "runtime": runtime,
        "platform": platform,
        "files": sorted(documents),
        "skills": sorted({item.parts[0] for item in skills}),
        "unsupported": sorted(set(unsupported)),
        "private_files": sorted(private),
        "activation_ready": False,
        "status": "inspected",
    }
    snap.verify()
    return snap, selected, workspace, documents, skills, private, report


def inspect_source(name, source, profile="default", runtime="opencode", **options):
    try:
        return _plan(name, source, profile, runtime, **options)[-1]
    except (OSError, UnicodeError):
        raise ImportErrorSafe(
            "cannot safely inspect Hermes source; details suppressed"
        ) from None


def _mkdir_parent(path):
    missing = []
    current = path
    while not current.exists() and not current.is_symlink():
        missing.append(current)
        current = current.parent
    fd, _ = _open_dir(current)
    try:
        for directory in reversed(missing):
            os.mkdir(directory.name, mode=0o700, dir_fd=fd)
            new = os.open(
                directory.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd
            )
            os.close(fd)
            fd = new
    finally:
        os.close(fd)
    return _open_dir(path)


def _publish(stage_fd, parent_fd, destination):
    """No-replace directory publication. Never fall back to overwrite-capable rename."""
    libc = ctypes.CDLL(None, use_errno=True)
    rename = getattr(libc, "renameat2", None)
    if rename is None:
        raise ImportErrorSafe(
            "atomic no-replace import publication requires Linux renameat2"
        )
    rename.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    rename.restype = ctypes.c_int
    if rename(stage_fd, b"home", parent_fd, os.fsencode(destination), 1):
        code = ctypes.get_errno()
        if code == errno.EEXIST:
            raise ImportErrorSafe("destination already exists; nothing was overwritten")
        raise ImportErrorSafe(
            "atomic import publication failed; nothing was overwritten"
        )


def import_profile(
    name,
    source,
    profile="default",
    runtime="opencode",
    *,
    path=None,
    base=None,
    allow_partial=False,
    **options,
):
    stage = None
    parent_fd = None
    published = False
    stage_identity = None
    try:
        snap, selected, workspace, documents, skills, private, report = _plan(
            name, source, profile, runtime, **options
        )
        if report["unsupported"] and not allow_partial:
            raise ImportErrorSafe(
                "manual configuration required; inspect first, then acknowledge with --allow-partial"
            )
        target = _absolute(
            path
            if path is not None
            else (
                Path(base) if base is not None else Path.home() / ".soulsteads/agents"
            )
            / name
        )
        for root in (_absolute(source), selected, workspace):
            if root and (
                target == root or root in target.parents or target in root.parents
            ):
                raise ImportErrorSafe("source and destination must not overlap")
        if target.exists() or target.is_symlink():
            raise ImportErrorSafe("destination already exists")
        core._check_not_nested_git(target.parent)
        parent_fd, chain = _mkdir_parent(target.parent)
        stage = ".hermes-import-" + secrets.token_hex(16)
        os.mkdir(stage, mode=0o700, dir_fd=parent_fd)
        info = os.stat(stage, dir_fd=parent_fd, follow_symlinks=False)
        stage_identity = (info.st_dev, info.st_ino)
        stage_path = target.parent / stage
        home = core.create(name, runtime, path=stage_path / "home", with_skills=False)
        for filename, raw in documents.items():
            content = raw.decode("utf-8")
            if filename == "AGENTS.md":
                private["AGENTS.md"] = raw
                content = (
                    "# Imported Home instructions\n\nAt session start, read SOUL.md, USER.md, and MEMORY.md in this home.\n\n"
                    "---\n\n" + content
                )
            # Preserve source bytes exactly except for the explicitly wrapped AGENTS.md.
            (home / filename).write_bytes(content.encode("utf-8"))
            (home / filename).chmod(0o600)
        for relative, (raw, mode) in skills.items():
            destination = home / "skills" / relative
            missing = []
            parent = destination.parent
            while not parent.exists():
                missing.append(parent)
                parent = parent.parent
            for directory in reversed(missing):
                directory.mkdir(mode=0o700)
            with destination.open("xb") as stream:
                os.fchmod(stream.fileno(), mode)
                stream.write(raw)
        private_root = home / ".runtime" / "hermes"
        (home / ".runtime").mkdir(mode=0o700)
        private_root.mkdir(mode=0o700)
        for filename, raw in private.items():
            (private_root / filename).write_bytes(raw)
            (private_root / filename).chmod(0o600)
        report.update(status="imported")
        private_receipt = {
            **report,
            "source_path": str(selected),
            "destination_path": str(target),
        }
        receipt = private_root / "IMPORT-RECEIPT.json"
        receipt.write_text(
            json.dumps(private_receipt, indent=2) + "\n", encoding="utf-8"
        )
        receipt.chmod(0o600)
        if core._git(home, "status", "--porcelain").stdout:
            core.commit(home, "Import Hermes agent definition")
        snap.verify()
        fresh, current = _open_dir(target.parent)
        try:
            if chain != current or os.fstat(fresh).st_ino != os.fstat(parent_fd).st_ino:
                raise ImportErrorSafe("destination parent changed")
        finally:
            os.close(fresh)
        # Move the completed home into the stage's sibling namespace atomically.
        stage_fd = os.open(stage, os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
        try:
            expected = os.stat("home", dir_fd=stage_fd, follow_symlinks=False)
            _publish(stage_fd, parent_fd, target.name)
            published = True
            os.fsync(stage_fd)
            os.fsync(parent_fd)
            fresh, current = _open_dir(target.parent)
            try:
                actual = os.stat(target.name, dir_fd=fresh, follow_symlinks=False)
                if chain != current or (actual.st_dev, actual.st_ino) != (
                    expected.st_dev,
                    expected.st_ino,
                ):
                    raise ImportErrorSafe("published destination binding changed")
            finally:
                os.close(fresh)
            core.load(target)
            snap.verify()
        finally:
            os.close(stage_fd)
        return report
    except ImportErrorSafe:
        if published:
            raise ImportErrorSafe(
                "import was published but final verification failed; inspect destination before retrying"
            ) from None
        raise
    except (OSError, UnicodeError):
        if published:
            raise ImportErrorSafe(
                "import was published but final verification failed; inspect destination before retrying"
            ) from None
        raise ImportErrorSafe(
            "cannot safely import Hermes source; details suppressed"
        ) from None
    finally:
        if parent_fd is not None:
            try:
                if stage_identity is not None and stage is not None:
                    info = os.stat(stage, dir_fd=parent_fd, follow_symlinks=False)
                    if (info.st_dev, info.st_ino) == stage_identity and stat.S_ISDIR(
                        info.st_mode
                    ):
                        shutil.rmtree(stage, dir_fd=parent_fd)
            finally:
                os.close(parent_fd)
