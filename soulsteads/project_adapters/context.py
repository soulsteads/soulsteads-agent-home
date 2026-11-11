"""Bounded, checked Home resources for native per-run prompt inputs."""

import os
import stat
from pathlib import Path

from .. import core, native_config
from ..hermes_import import _open_dir


def require_private_argv_consent(allowed):
    if allowed is not True:
        raise core.HomeError(
            "project context would expose private Home identity, memory and skills in process argv; "
            "explicitly opt in with --allow-context-in-argv only if local process-argument visibility is acceptable"
        )


def collect_context(home: Path):
    """Read identity, operating instructions and skill text without credential/state reads."""
    home = Path(home).absolute()
    core.load(home)
    root_fd, chain = _open_dir(home)
    snapshot = native_config._NativeSnapshot()
    try:

        def required(relative):
            text = snapshot.read(home / relative)
            if text is None:
                raise core.HomeError("required Home context resource is missing")
            return text

        sections = [
            "Home identity context:\n" + required(".pi/APPEND_SYSTEM.md"),
            "Home AGENTS.md instructions:\n" + required("AGENTS.md"),
        ]
        names = []
        skills = home / "skills"
        try:
            skills_fd, _skills_chain = _open_dir(skills)
        except FileNotFoundError:
            skills_fd = -1
        if skills_fd >= 0:
            try:
                before = os.fstat(skills_fd)
                entries = sorted(os.listdir(skills_fd))
                for name in entries:
                    info = os.stat(name, dir_fd=skills_fd, follow_symlinks=False)
                    if stat.S_ISLNK(info.st_mode):
                        raise core.HomeError(
                            "Home skill directories must not be symbolic links"
                        )
                    if not stat.S_ISDIR(info.st_mode):
                        continue
                    if info.st_uid != os.getuid() or info.st_mode & 0o022:
                        raise core.HomeError("unsafe Home skill directory")
                    text = snapshot.read(skills / name / "SKILL.md")
                    if text is not None:
                        names.append(name)
                        sections.append(
                            f"Home skill {name} (resource root: {skills / name}):\n{text}"
                        )
                after = os.fstat(skills_fd)
                if native_config._identity(before) != native_config._identity(
                    after
                ) or entries != sorted(os.listdir(skills_fd)):
                    raise core.HomeError("Home skill inventory changed during planning")
            finally:
                os.close(skills_fd)
        snapshot.verify()
        native_config._verify_root(home, chain)
        return "\n\n".join(sections), names
    finally:
        snapshot.close()
        os.close(root_fd)


def checked_inline_argument(argument: str):
    """Refuse oversize native arguments rather than truncating identity or skills."""
    if len(os.fsencode(argument)) > 96 * 1024:
        raise core.HomeError(
            "Home context exceeds the native inline input limit; reduce Home context or skills"
        )
    return argument
