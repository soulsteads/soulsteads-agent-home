"""Review a bounded change to the body of an existing Home skill."""

import difflib
import hashlib
import json
import os
import re
from contextlib import ExitStack
from pathlib import Path

from . import core, native_config, publication
from .hermes_import import _open_dir

MAX_PROPOSAL_BYTES = 64 * 1024


def _plan(original, relative, proposal, home_identity, policy):
    if not isinstance(proposal, dict) or set(proposal) != {"reason", "before", "after"}:
        raise ValueError("proposal requires exactly reason, before and after")
    if any(not isinstance(v, str) or "\0" in v for v in proposal.values()):
        raise ValueError("proposal fields must be text without NUL")
    reason, before, after = (proposal[k] for k in ("reason", "before", "after"))
    if not reason.strip() or not before.strip() or before == after:
        raise ValueError("provide a reason and a distinct change to existing body text")

    # Preserve the original frontmatter byte for byte, including CRLF.
    header = re.match(
        r"\A---[ \t]*\r?\n.*?^---[ \t]*\r?\n", original, re.DOTALL | re.MULTILINE
    )
    if not header:
        raise ValueError("skill requires frontmatter followed by a Markdown body")
    body = original[header.end() :]
    if before not in body or body.find(before) != body.rfind(before):
        raise ValueError("before must match exactly once in the current skill body")
    updated_body = body.replace(before, after, 1)
    updated = header.group() + updated_body
    if not updated_body.strip() or len(updated.encode()) > native_config.MAX_FILE_BYTES:
        raise ValueError("updated skill is empty or too large")

    binding = [
        "skill-review-v1",
        home_identity,
        str(relative),
        policy,
        hashlib.sha256(original.encode()).hexdigest(),
        reason,
        before,
        after,
    ]
    review_id = hashlib.sha256(json.dumps(binding, sort_keys=True).encode()).hexdigest()
    report = {
        "status": "preview",
        "skill": relative.parent.name,
        "reason": reason,
        "review_id": review_id,
        "diff": list(
            difflib.unified_diff(
                original.splitlines(keepends=True),
                updated.splitlines(keepends=True),
                fromfile=str(relative),
                tofile=str(relative),
            )
        ),
    }
    return updated, report


def review(home, skill, proposal, *, apply=None):
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", skill) or len(skill) > 64:
        raise ValueError("expected a local skill name")
    at_home = Path(home) == Path(".")
    home = Path(home).absolute()
    relative = Path("skills", skill, "SKILL.md")
    with ExitStack() as stack:
        if at_home:
            # The kernel pins cwd even when ancestors are renamed. Native sandboxes
            # may map the host's root UID to nobody in those ancestor directories.
            root_fd = os.open(".", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        else:
            root_fd, _ = _open_dir(home)
        stack.callback(os.close, root_fd)
        root = os.fstat(root_fd)
        if root.st_uid != os.getuid() or root.st_mode & 0o022:
            raise core.HomeError("expected an owned Home without shared write access")
        snapshot = native_config._NativeSnapshot(home, root_fd)
        stack.callback(snapshot.close)
        manifest = core._validate_home(home, reader=snapshot.read)
        directory = root_fd
        for part in relative.parts[:-1]:
            directory = os.open(
                part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory
            )
            stack.callback(os.close, directory)
            info = os.fstat(directory)
            if info.st_uid != os.getuid() or info.st_mode & 0o022:
                raise core.HomeError("unsafe skill directory")
        original = snapshot.read(home / relative)
        if original is None:
            raise ValueError("skill does not exist in the selected Home")
        updated, report = _plan(
            original,
            relative,
            proposal,
            (root.st_dev, root.st_ino),
            manifest.get("learning"),
        )
        if apply is not None:
            if apply != report["review_id"]:
                raise ValueError(
                    "review ID differs; preview the current proposal again"
                )
            stack.enter_context(publication.cooperative_lock(root_fd))
            snapshot.verify()
            if not os.path.samestat(root, os.stat(home, follow_symlinks=False)):
                raise core.HomeError("Home changed during review")
            checked = native_config._open_relative_dir(root_fd, relative.parts[:-1])
            stack.callback(os.close, checked)
            if not os.path.samestat(os.fstat(directory), os.fstat(checked)):
                raise core.HomeError("skill directory changed during review")
            publication.publish_file(
                directory,
                relative.name,
                updated,
                expected=snapshot.states[home / relative],
            )
            report["status"] = "applied"
        return report
