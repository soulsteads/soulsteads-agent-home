"""Private, per-launch copies of admitted native instruction/skill resources.

The mutable Home is an input, never a later native read target. The temporary
namespace belongs to the launcher; this does not defend against a same-UID
actor that can manipulate the launcher's private files or process itself.
"""

import os
import stat
import tempfile
from pathlib import Path

from .. import core, native_config
from ..hermes_import import MAX_ENTRIES, Snapshot, _open_dir


class ResourceLaunch(dict):
    """JSON-compatible plan owning resources until close or context exit.

    Keep this object alive through the native process and close it afterwards.
    Serializing/copying the mapping does not transfer resource ownership.
    """

    def __init__(self, plan, temporary):
        super().__init__(plan)
        self._temporary = temporary

    def close(self):
        self._temporary.cleanup()

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()


def copy_resources(home, project):
    """Return (temporary owner, root, skill names), cleaning failed preparations."""
    home, project = Path(home).absolute(), Path(project).resolve()
    core.load(home)
    parent = Path(tempfile.gettempdir()).resolve()
    if parent.is_relative_to(home) or parent.is_relative_to(project):
        raise core.HomeError(
            "launch temporary storage must be outside Home and project"
        )
    temporary = tempfile.TemporaryDirectory(prefix="soulsteads-context-", dir=parent)
    root = Path(temporary.name).resolve()
    try:
        if root.is_relative_to(home) or root.is_relative_to(project):
            raise core.HomeError(
                "launch temporary storage must be outside Home and project"
            )
        descriptor, _chain = _open_dir(root)
        os.close(descriptor)
        snapshot = Snapshot()
        count = 0

        def copy_file(source, destination):
            data = snapshot.read(source)
            if data is None:
                raise core.HomeError("required Home context resource is missing")
            if len(data) > native_config.MAX_FILE_BYTES:
                raise core.HomeError("Home context resource exceeds the size limit")
            if snapshot.files[source][1][2] & 0o022:
                raise core.HomeError(
                    "Home context files must not be group/other writable"
                )
            if source.name in {"APPEND_SYSTEM.md", "AGENTS.md", "SKILL.md"}:
                data.decode("utf-8")
            destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            mode = 0o700 if snapshot.files[source][1][2] & 0o111 else 0o600
            with destination.open("xb") as output:
                output.write(data)
            destination.chmod(mode)

        def entries(directory):
            nonlocal count
            snapshot.directory(directory)
            fd, _chain = _open_dir(directory)
            try:
                names = []
                with os.scandir(fd) as scan:
                    for entry in scan:
                        count += 1
                        if count > MAX_ENTRIES:
                            raise core.HomeError(
                                "Home skill inventory exceeds the entry limit"
                            )
                        names.append(entry.name)
                result = [
                    (name, os.stat(name, dir_fd=fd, follow_symlinks=False))
                    for name in sorted(names)
                ]
            finally:
                os.close(fd)
            snapshot.directory(directory)
            return result

        def copy_tree(source, destination):
            if len(source.relative_to(home / "skills").parts) > 32:
                raise core.HomeError("Home skill tree exceeds the depth limit")
            destination.mkdir(mode=0o700)
            for name, info in entries(source):
                src, dst = source / name, destination / name
                if stat.S_ISDIR(info.st_mode):
                    copy_tree(src, dst)
                elif stat.S_ISREG(info.st_mode):
                    copy_file(src, dst)
                else:
                    raise core.HomeError(
                        "Home skill resources must be real directories or regular files"
                    )

        copy_file(home / ".pi/APPEND_SYSTEM.md", root / ".pi/APPEND_SYSTEM.md")
        copy_file(home / "AGENTS.md", root / "AGENTS.md")
        skills = home / "skills"
        names = []
        (root / "skills").mkdir(mode=0o700)
        for name, info in entries(skills):
            if stat.S_ISLNK(info.st_mode):
                raise core.HomeError(
                    "Home skill directories must not be symbolic links"
                )
            if not stat.S_ISDIR(info.st_mode):
                continue
            # Match the existing selector: directories without SKILL.md are not skills.
            if snapshot.read(skills / name / "SKILL.md") is not None:
                copy_tree(skills / name, root / "skills" / name)
                names.append(name)
        snapshot.verify()
        return temporary, root, names
    except BaseException:
        temporary.cleanup()
        raise
