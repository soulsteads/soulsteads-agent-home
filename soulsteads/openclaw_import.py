"""Import explicitly selected, portable files from an OpenClaw workspace."""

import os
from pathlib import Path
import re
import stat

from . import core
from .hermes_import import (
    ImportErrorSafe, MAX_ENTRIES, SLUG, Snapshot, _absolute, _apply_import, _open_dir, _yaml,
)
from .runtimes import RUNTIMES
from .skill_conversion import convert_skill

_PORTABLE_FIELDS = {"name", "description", "license", "compatibility", "metadata"}


def _skills(workspace, names, snapshot):
    result = {}
    count = 0
    for name in names:
        root = workspace / "skills" / name
        snapshot.directory(root)
        raw = snapshot.read(root / "SKILL.md")
        header = re.match(rb"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|$)", raw or b"", re.S)
        if not header:
            raise ImportErrorSafe("selected skill requires SKILL.md with YAML frontmatter")
        fields = _yaml(header.group(1))
        metadata = fields.get("metadata", {})
        if set(fields) - _PORTABLE_FIELDS or (
            isinstance(metadata, dict) and {"openclaw", "clawdbot", "clawdis", "hermes"} & metadata.keys()
        ):
            raise ImportErrorSafe("OpenClaw-specific skill metadata requires manual review before import")
        try:
            raw.decode("utf-8")
            portable = convert_skill(raw, name)
        except (ValueError, UnicodeError):
            raise ImportErrorSafe("invalid portable metadata or text in selected skill") from None
        pending = [root]
        while pending:
            directory = pending.pop()
            snapshot.directory(directory)
            fd, _ = _open_dir(directory)
            try:
                with os.scandir(fd) as entries:
                    for entry in entries:
                        count += 1
                        if count > MAX_ENTRIES:
                            raise ImportErrorSafe("skill inventory exceeds import limit")
                        item = directory / entry.name
                        relative = item.relative_to(root)
                        if entry.name.startswith(".") or core._secret_path(relative):
                            raise ImportErrorSafe("selected skill contains hidden or credential paths")
                        info = entry.stat(follow_symlinks=False)
                        if stat.S_ISDIR(info.st_mode):
                            pending.append(item)
                        elif stat.S_ISREG(info.st_mode):
                            if item.name == "SKILL.md" and directory != root:
                                raise ImportErrorSafe("nested skill in selected skill; import separately")
                            data = snapshot.read(item)
                            if data is None:
                                raise ImportErrorSafe("skill changed during inspection")
                            mode = 0o700 if snapshot.files[item][1][2] & 0o111 else 0o600
                            result[Path(name) / relative] = (portable if item.name == "SKILL.md" else data, mode)
                        else:
                            raise ImportErrorSafe("selected skill contains links or special files")
            finally:
                os.close(fd)
    return result


def _plan(name, workspace, runtime, *, include_memory=False, skills=()):
    if not SLUG.fullmatch(name or "") or runtime not in RUNTIMES:
        raise ImportErrorSafe("invalid Home name or runtime")
    if any(not SLUG.fullmatch(skill or "") or len(skill) > 64 for skill in skills):
        raise ImportErrorSafe("select skills by lowercase hyphenated directory name")
    if len(set(skills)) != len(skills):
        raise ImportErrorSafe("duplicate skill selection")
    workspace = _absolute(workspace)
    snapshot = Snapshot()
    snapshot.directory(workspace)
    documents = {}
    filenames = ["AGENTS.md", "SOUL.md", "USER.md"]
    if include_memory:
        filenames.append("MEMORY.md")
    for filename in filenames:
        raw = snapshot.read(workspace / filename)
        if raw is not None:
            raw.decode("utf-8")
            documents[filename] = raw
    selected = _skills(workspace, skills, snapshot)
    if not documents and not selected:
        raise ImportErrorSafe("no selected portable documents or skills in the workspace")
    report = {
        "schema_version": 1,
        "source": "openclaw-workspace",
        "name": name,
        "runtime": runtime,
        "files": sorted(documents),
        "skills": sorted(skills),
        "identity": "not-transferred",
        "curated_memory": "not-selected" if not include_memory else (
            "selected" if "MEMORY.md" in documents else "missing"
        ),
        "not_transferred": [
            "IDENTITY.md", "daily-memory", "unselected-and-external-skills", "gateway-config",
            "model-and-permissions", "mcp-and-plugins", "sessions", "schedules", "messaging",
            "credentials", "external-memory",
        ],
        "unsupported": [],
        "activation_ready": False,
        "status": "inspected",
    }
    snapshot.verify()
    return snapshot, workspace, None, documents, selected, {}, report


def inspect_workspace(name, workspace, runtime, **options):
    try:
        return _plan(name, workspace, runtime, **options)[-1]
    except (OSError, UnicodeError):
        raise ImportErrorSafe("cannot safely inspect OpenClaw workspace; details suppressed") from None


def import_workspace(name, workspace, runtime, *, path=None, base=None, **options):
    return _apply_import(
        name, runtime, "openclaw", lambda: _plan(name, workspace, runtime, **options),
        path=path, base=base, allow_partial=False, source_root=workspace,
    )
