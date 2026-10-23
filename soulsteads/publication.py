"""Checked, descriptor-relative publication primitives for Soulsteads writers.

Cooperative writers lock a persistent inode in the home's ignored .git directory.
External editors must be quiescent: checking an existing leaf before replace is
not compare-and-swap and cannot exclude a same-UID writer in the final interval.
"""

import errno
import os
import secrets
import stat
from contextlib import contextmanager

from .core import HomeError

try:
    import fcntl
except ImportError:
    fcntl = None


class PublicationError(HomeError):
    """Publication failed; published indicates whether destination was changed."""

    def __init__(self, message, *, published):
        super().__init__(message)
        self.published = published


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


@contextmanager
def cooperative_lock(root_fd):
    """Serialize Soulsteads publishers using a persistent private lock inode."""
    if fcntl is None or os.name != "posix":
        raise HomeError("native publication requires POSIX descriptor and lock support")
    git_fd = os.open(
        ".git", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root_fd
    )
    lock_fd = -1
    try:
        lock_fd = os.open(
            "soulsteads-publication.lock",
            os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK,
            0o600,
            dir_fd=git_fd,
        )
        opened = os.fstat(lock_fd)
        path_info = os.stat(
            "soulsteads-publication.lock", dir_fd=git_fd, follow_symlinks=False
        )
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_uid != os.getuid()
            or opened.st_nlink != 1
            or stat.S_IMODE(opened.st_mode) != 0o600
            or _identity(opened) != _identity(path_info)
        ):
            raise HomeError("unsafe cooperative publication lock")
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        after_wait = os.fstat(lock_fd)
        path_after_wait = os.stat(
            "soulsteads-publication.lock", dir_fd=git_fd, follow_symlinks=False
        )
        if _identity(after_wait) != _identity(path_after_wait) or _identity(
            after_wait
        ) != _identity(opened):
            raise HomeError("cooperative publication lock changed while waiting")
        yield
    except OSError as exc:
        raise HomeError("cannot acquire cooperative publication lock") from exc
    finally:
        if lock_fd >= 0:
            os.close(lock_fd)
        os.close(git_fd)


def publish_file(parent_fd, name, text, *, expected=None):
    """Stage/fsync bytes, then atomically create absent or replace checked leaf."""
    data = text.encode("utf-8")
    temporary = f".{name}.{secrets.token_hex(16)}.tmp"
    descriptor = -1
    staged_inode = None
    destination_changed = False
    try:
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=parent_fd,
        )
        created = os.fstat(descriptor)
        staged_inode = (created.st_dev, created.st_ino)
        os.fchmod(descriptor, 0o600)
        offset = 0
        while offset < len(data):
            offset += os.write(descriptor, data[offset:])
        os.fsync(descriptor)
        staged = os.fstat(descriptor)
        staged_identity = _identity(staged)
        staged_inode = (staged.st_dev, staged.st_ino)
        if (
            not stat.S_ISREG(staged.st_mode)
            or staged.st_uid != os.getuid()
            or staged.st_nlink != 1
            or staged.st_size != len(data)
        ):
            raise HomeError("unsafe staged native file")
        os.close(descriptor)
        descriptor = -1
        if (
            _identity(os.stat(temporary, dir_fd=parent_fd, follow_symlinks=False))
            != staged_identity
        ):
            raise HomeError("staged native file changed before publication")
        if expected is None:
            os.link(
                temporary,
                name,
                src_dir_fd=parent_fd,
                dst_dir_fd=parent_fd,
                follow_symlinks=False,
            )
            destination_changed = True
            os.unlink(temporary, dir_fd=parent_fd)
        else:
            current = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
            if (
                _identity(current) != expected
                or not stat.S_ISREG(current.st_mode)
                or current.st_nlink != 1
            ):
                raise HomeError("native destination changed after preflight")
            os.replace(temporary, name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
            destination_changed = True
        os.fsync(parent_fd)
        published = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        if (
            (published.st_dev, published.st_ino) != staged_inode
            or published.st_uid != os.getuid()
            or not stat.S_ISREG(published.st_mode)
            or published.st_nlink != 1
            or published.st_size != len(data)
        ):
            raise HomeError(
                "published native file metadata mismatch "
                f"(uid={published.st_uid}, regular={stat.S_ISREG(published.st_mode)}, "
                f"links={published.st_nlink}, size={published.st_size}, expected={len(data)})"
            )
        check_fd = os.open(
            name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent_fd
        )
        try:
            check_info = os.fstat(check_fd)
            if _identity(check_info) != _identity(published):
                raise HomeError("published native file changed")
            output = bytearray()
            while len(output) <= len(data):
                chunk = os.read(check_fd, min(65536, len(data) + 1 - len(output)))
                if not chunk:
                    break
                output.extend(chunk)
            if bytes(output) != data or _identity(os.fstat(check_fd)) != _identity(
                published
            ):
                raise HomeError("published native file content mismatch")
        finally:
            os.close(check_fd)
        return published
    except HomeError as exc:
        if destination_changed:
            raise PublicationError(str(exc), published=True) from exc
        raise
    except OSError as exc:
        if destination_changed:
            raise PublicationError(
                f"native publication failed after destination change: {name}",
                published=True,
            ) from exc
        if exc.errno == errno.EEXIST:
            raise HomeError(
                f"native destination appeared during publication: {name}"
            ) from exc
        raise
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            candidate = os.stat(temporary, dir_fd=parent_fd, follow_symlinks=False)
            if staged_inode == (candidate.st_dev, candidate.st_ino):
                os.unlink(temporary, dir_fd=parent_fd)
        except FileNotFoundError:
            pass


def publish_fresh(root, files):
    """Checked publication for a fresh staging home; caller owns outer rename."""
    from pathlib import Path

    from .hermes_import import _open_dir

    root = Path(root).absolute()
    root_fd, root_chain = _open_dir(root)
    applied = []
    outputs = {}
    ordered = list(files.items())

    def verify_outputs():
        rebound, chain = _open_dir(root)
        try:
            if chain != root_chain:
                raise HomeError("fresh native home root changed")
        finally:
            os.close(rebound)
        for relative, (expected, identity) in outputs.items():
            parts = Path(relative).parts
            parent = os.dup(root_fd)
            try:
                for part in parts[:-1]:
                    child = os.open(
                        part,
                        os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                        dir_fd=parent,
                    )
                    os.close(parent)
                    parent = child
                fd = os.open(
                    parts[-1],
                    os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                    dir_fd=parent,
                )
                try:
                    info = os.fstat(fd)
                    if _identity(info) != identity:
                        raise HomeError("published fresh native output changed")
                    data = bytearray()
                    while len(data) <= len(expected):
                        chunk = os.read(fd, min(65536, len(expected) + 1 - len(data)))
                        if not chunk:
                            break
                        data.extend(chunk)
                    if (
                        bytes(data) != expected
                        or _identity(os.fstat(fd)) != identity
                        or _identity(
                            os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)
                        )
                        != identity
                    ):
                        raise HomeError("published fresh native output changed")
                finally:
                    os.close(fd)
            finally:
                os.close(parent)

    try:
        with cooperative_lock(root_fd):
            verify_outputs()
            for index, (relative, text) in enumerate(ordered):
                path = Path(relative)
                parts = path.parts
                if path.is_absolute() or not parts or ".." in parts:
                    raise HomeError("invalid native destination")
                parent_fd = os.dup(root_fd)
                try:
                    for part in parts[:-1]:
                        try:
                            child_fd = os.open(
                                part,
                                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                dir_fd=parent_fd,
                            )
                        except FileNotFoundError:
                            os.mkdir(part, mode=0o700, dir_fd=parent_fd)
                            child_fd = os.open(
                                part,
                                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                dir_fd=parent_fd,
                            )
                        os.close(parent_fd)
                        parent_fd = child_fd
                    result = publish_file(parent_fd, parts[-1], text, expected=None)
                    outputs[relative] = (text.encode("utf-8"), _identity(result))
                    applied.append(relative)
                    verify_outputs()
                except Exception as exc:
                    if applied:
                        remaining = [name for name, _ in ordered if name not in applied]
                        raise HomeError(
                            "fresh native publication partially applied; "
                            f"applied={applied!r}; remaining={remaining!r}; "
                            "discard the staging home before exposing it"
                        ) from exc
                    raise
                finally:
                    os.close(parent_fd)
            verify_outputs()
            os.fsync(root_fd)
    finally:
        os.close(root_fd)
