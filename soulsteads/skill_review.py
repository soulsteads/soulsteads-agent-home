"""Review a bounded change to the body of an existing Home skill."""

import difflib
import hashlib
import json
import os
import re
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
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

    body = skill_body(original)
    if before not in body or body.find(before) != body.rfind(before):
        raise ValueError("before must match exactly once in the current skill body")
    updated_body = body.replace(before, after, 1)
    updated = original[: len(original) - len(body)] + updated_body
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


def skill_body(text):
    # Keep the exact frontmatter bytes, including CRLF.
    header = re.match(
        r"\A---[ \t]*\r?\n.*?^---[ \t]*\r?\n", text, re.DOTALL | re.MULTILINE
    )
    if not header:
        raise ValueError("skill requires frontmatter followed by a Markdown body")
    return text[header.end() :]


@dataclass
class Skill:
    home: Path
    root_fd: int
    directory: int
    relative: Path
    root: os.stat_result
    snapshot: native_config._NativeSnapshot
    manifest: dict
    original: str

    def plan(self, proposal):
        return _plan(
            self.original,
            self.relative,
            proposal,
            (self.root.st_dev, self.root.st_ino),
            self.manifest.get("learning"),
        )

    def verify(self):
        self.snapshot.verify()
        if not os.path.samestat(self.root, os.stat(self.home, follow_symlinks=False)):
            raise core.HomeError("Home changed during review")
        checked = native_config._open_relative_dir(
            self.root_fd, self.relative.parts[:-1]
        )
        try:
            if not os.path.samestat(os.fstat(self.directory), os.fstat(checked)):
                raise core.HomeError("skill directory changed during review")
        finally:
            os.close(checked)

    def publish(self, updated):
        publication.publish_file(
            self.directory,
            self.relative.name,
            updated,
            expected=self.snapshot.states[self.home / self.relative],
        )


@contextmanager
def open_skill(home, skill):
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
        yield Skill(
            home, root_fd, directory, relative, root, snapshot, manifest, original
        )


def review(home, skill, proposal, *, apply=None):
    with open_skill(home, skill) as target:
        updated, report = target.plan(proposal)
        if apply is not None:
            if apply != report["review_id"]:
                raise ValueError(
                    "review ID differs; preview the current proposal again"
                )
            with publication.cooperative_lock(target.root_fd):
                target.verify()
                target.publish(updated)
            report["status"] = "applied"
        return report
