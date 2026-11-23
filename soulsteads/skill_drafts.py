"""Review and publish a body-only change to one existing Home skill."""

from contextlib import contextmanager, nullcontext
import difflib
import hashlib
import json
import os
import re
import stat

from . import core
from .hermes_import import SLUG, _absolute, _identity, _open_dir
from .native_config import _NativeSnapshot, _open_relative_dir, _read, _verify_root
from .publication import cooperative_lock, publish_file

_SKILL_LIMIT = 128 * 1024
# JSON escaping can expand a byte to six characters, for two skill versions.
_DRAFT_LIMIT = 2 * 1024 * 1024
_STORE = (".runtime", "skill-drafts")
_HEADER = re.compile(r"\A---[ \t]*\r?\n.*?\r?\n---[ \t]*\r?\n", re.S)


def _hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _encode(record):
    return json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"


def _target(home, skill):
    if not isinstance(skill, str) or len(skill) > 64 or not SLUG.fullmatch(skill):
        raise core.HomeError("skill name must be a lowercase slug of at most 64 characters")
    return home / "skills" / skill / "SKILL.md"


def _validate(record):
    if (
        not isinstance(record, dict)
        or record.keys() != {"version", "skill", "reason", "base", "candidate"}
        or type(record["version"]) is not int
        or record["version"] != 1
    ):
        raise core.HomeError("invalid skill draft format")
    reason = record["reason"]
    if (
        not isinstance(reason, str) or not reason.strip()
        or len(reason) > 512 or not reason.isprintable()
    ):
        raise core.HomeError("skill draft needs a one-line reason of up to 512 characters")
    headers = []
    for text in (record["base"], record["candidate"]):
        if not isinstance(text, str) or "\x00" in text or len(text.encode("utf-8")) > _SKILL_LIMIT:
            raise core.HomeError("invalid or oversized skill draft text")
        header = _HEADER.match(text)
        if not header or not text[header.end():].strip():
            raise core.HomeError("skill must have frontmatter and a nonempty body")
        headers.append(header.group())
    if headers[0] != headers[1]:
        raise core.HomeError("skill draft must preserve frontmatter exactly")
    if record["base"] == record["candidate"]:
        raise core.HomeError("skill draft makes no change")


@contextmanager
def _home(path, *, write=False):
    home = _absolute(path)
    fd, chain = _open_dir(home)
    try:
        with cooperative_lock(fd) if write else nullcontext():
            _verify_root(home, chain)
            core._validate_home(home, reader=_read)
            _verify_root(home, chain)
            yield home, fd, chain
    finally:
        os.close(fd)


@contextmanager
def _store(fd, *, create=False):
    """Open private draft storage without chmod or symlink traversal."""
    try:
        runtime = _open_relative_dir(fd, _STORE[:1], create=create)
        try:
            _check_private_dir(runtime)
            drafts = _open_relative_dir(runtime, _STORE[1:], create=create)
            try:
                _check_private_dir(drafts)
                if create:
                    os.fsync(runtime)
                    os.fsync(fd)
                yield drafts
            finally:
                os.close(drafts)
        finally:
            os.close(runtime)
    except FileNotFoundError as exc:
        raise core.HomeError("skill draft storage not found or changed") from exc


def _check_private_dir(fd):
    info = os.fstat(fd)
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise core.HomeError("skill draft storage must be owner-only")


def _draft_text(home, fd, draft_id, snapshot):
    leaf = home.joinpath(*_STORE, draft_id + ".json")
    raw = _read(leaf, snapshot, max_bytes=_DRAFT_LIMIT)
    directory = os.fstat(fd)
    chain = snapshot.chains[leaf]
    if not chain or chain[-1][:2] != (directory.st_dev, directory.st_ino):
        raise core.HomeError("skill draft storage changed")
    if raw is not None and (
        stat.S_IMODE(snapshot.states[leaf][2]) != 0o600 or _hash(raw) != draft_id
    ):
        raise core.HomeError("skill draft changed or is not private")
    return leaf, raw


def _read_draft(home, fd, draft_id, snapshot):
    _, raw = _draft_text(home, fd, draft_id, snapshot)
    if raw is None:
        raise core.HomeError("skill draft not found")
    try:
        record = json.loads(raw)
        if _encode(record) != raw:
            raise core.HomeError("invalid canonical skill draft")
        _validate(record)
        _target(home, record["skill"])
    except (ValueError, RecursionError) as exc:
        raise core.HomeError("invalid skill draft") from exc
    return record


def _read_skill(target, snapshot):
    text = _read(target, snapshot, max_bytes=_SKILL_LIMIT)
    if text is None:
        raise core.HomeError("skill draft requires an existing canonical SKILL.md")
    if snapshot.states[target][2] & 0o111:
        raise core.HomeError("skill draft target must not be executable")
    return text


def _publish(home, chain, leaf, text, snapshot, *, limit):
    parent, binding = _open_dir(leaf.parent)
    try:
        if binding != snapshot.chains[leaf]:
            raise core.HomeError("skill draft destination changed during review")
        snapshot.verify_bounded()
        _verify_root(home, chain)
        published = publish_file(parent, leaf.name, text, expected=snapshot.states[leaf])
        try:
            checked = _NativeSnapshot()
            actual = _read(leaf, checked, max_bytes=limit)
            if (
                actual != text or checked.states[leaf] != _identity(published)
                or checked.chains[leaf] != binding
            ):
                raise core.HomeError("published skill draft output changed")
            _verify_root(home, chain)
        except (OSError, core.HomeError) as exc:
            raise core.HomeError(
                "skill draft write occurred but could not be verified; inspect before retrying"
            ) from exc
    finally:
        os.close(parent)


class _DraftSnapshot(_NativeSnapshot):
    def verify_bounded(self):
        for path, state in self.states.items():
            current = _NativeSnapshot()
            limit = _SKILL_LIMIT if path.name == "SKILL.md" else _DRAFT_LIMIT
            _read(path, current, max_bytes=limit)
            if (
                current.states[path] != state or current.chains[path] != self.chains[path]
                or current.hashes[path] != self.hashes[path]
            ):
                raise core.HomeError("skill draft input changed during review")


def propose(path, skill, candidate_path, reason):
    """Save exact review bytes without changing the active skill."""
    _target(_absolute(path), skill)
    candidate = _read(_absolute(candidate_path), max_bytes=_SKILL_LIMIT)
    if candidate is None:
        raise core.HomeError("skill draft candidate file not found")
    with _home(path, write=True) as (home, fd, chain):
        snapshot = _DraftSnapshot()
        base = _read_skill(_target(home, skill), snapshot)
        record = {
            "version": 1, "skill": skill, "base": base,
            "candidate": candidate, "reason": reason,
        }
        _validate(record)
        text = _encode(record)
        draft_id = _hash(text)
        with _store(fd, create=True) as store:
            leaf, existing = _draft_text(home, store, draft_id, snapshot)
            if existing is None:
                _publish(home, chain, leaf, text, snapshot, limit=_DRAFT_LIMIT)
            else:
                snapshot.verify_bounded()
                _verify_root(home, chain)
        return {"id": draft_id, "status": "proposed", **_summary(record)}


def _check_id(draft_id):
    if not isinstance(draft_id, str) or not re.fullmatch(r"[0-9a-f]{64}", draft_id):
        raise core.HomeError("invalid skill draft ID")


def _summary(record):
    return {
        "skill": record["skill"],
        "base_sha256": _hash(record["base"]),
        "candidate_sha256": _hash(record["candidate"]),
    }


def show(path, draft_id):
    """Display just the private diff and reason; never create draft storage."""
    _check_id(draft_id)
    with _home(path) as (home, fd, chain), _store(fd) as store:
        snapshot = _DraftSnapshot()
        record = _read_draft(home, store, draft_id, snapshot)
        target = _target(home, record["skill"]).relative_to(home)
        lines = difflib.unified_diff(
            record["base"].splitlines(keepends=True),
            record["candidate"].splitlines(keepends=True),
            fromfile=f"a/{target}", tofile=f"b/{target}",
        )
        diff = "".join(
            line if line.endswith("\n") else line + "\n\\ No newline at end of file\n"
            for line in lines
        )
        snapshot.verify_bounded()
        _verify_root(home, chain)
        return {"id": draft_id, **_summary(record), "reason": record["reason"], "diff": diff}


def _change(path, draft_id, *, undo):
    _check_id(draft_id)
    with _home(path, write=True) as (home, fd, chain), _store(fd) as store:
        snapshot = _DraftSnapshot()
        record = _read_draft(home, store, draft_id, snapshot)
        target = _target(home, record["skill"])
        before, after = record["base"], record["candidate"]
        if undo:
            before, after = after, before
        if _read_skill(target, snapshot) != before:
            raise core.HomeError("stale skill draft: current skill does not match the expected bytes")
        _publish(home, chain, target, after, snapshot, limit=_SKILL_LIMIT)
        return {
            "id": draft_id, "skill": record["skill"],
            "status": "undone" if undo else "applied", "sha256": _hash(after),
        }


def apply(path, draft_id):
    """Approve and publish the exact reviewed draft."""
    return _change(path, draft_id, undo=False)


def undo(path, draft_id):
    """Restore only the captured preimage, leaving Git history and index alone."""
    return _change(path, draft_id, undo=True)
