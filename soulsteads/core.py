"""Safe local agent-home operations using only the Python standard library."""

from __future__ import annotations

import json
import os
import re
import secrets
import shutil
import stat
import subprocess
from collections.abc import Callable
from contextlib import ExitStack
from pathlib import Path
from typing import Final


class HomeError(Exception):
    """Raised when an agent home cannot be safely operated on."""


_NAME: Final = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_PERSONA_FILES: Final = ("USER.md", "SOUL.md", "AGENTS.md", "MEMORY.md")
_SECRET_NAMES: Final = {".env", "credentials", "credential", "secrets", "secret"}
_MAX_WORKSPACE_FILE: Final = 64 * 1024 * 1024
_WorkspaceFile = tuple[list[tuple[int, int, int, int]], os.stat_result | None, int | None]


def _error(message: str) -> None:
    raise HomeError(message)


def _private_dir(path: Path) -> None:
    path.mkdir(mode=0o700)
    path.chmod(0o700)


def _write_private(path: Path, text: str) -> None:
    """Atomically initialize canonical private files, not native configuration."""
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(16)}.tmp")
    descriptor = -1
    temporary_created = False
    try:
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
        )
        temporary_created = True
        os.fchmod(descriptor, 0o600)
        data = text.encode("utf-8")
        written = 0
        while written < len(data):
            written += os.write(descriptor, data[written:])
        os.fsync(descriptor)
        os.close(descriptor)
        descriptor = -1
        os.replace(temporary, path)
        temporary_created = False
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if temporary_created:
            temporary.unlink(missing_ok=True)


def _render(runtime: str) -> dict[str, str]:
    """Obtain runtime files lazily so the core remains independently importable."""
    from soulsteads.runtimes import render

    rendered = render(runtime)
    if not isinstance(rendered, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in rendered.items()
    ):
        _error("runtime renderer returned invalid files")
    return rendered


def _git(
    home: Path, *args: str, check: bool = True
) -> subprocess.CompletedProcess[str]:
    result = _git_bytes(home, *args, check=check)
    return subprocess.CompletedProcess(
        result.args, result.returncode, os.fsdecode(result.stdout), os.fsdecode(result.stderr)
    )


def _git_bytes(
    home: Path, *args: str, check: bool = True, input: bytes | None = None
) -> subprocess.CompletedProcess[bytes]:
    environment = {
        key: value for key, value in os.environ.items() if not key.startswith("GIT_")
    }
    result = subprocess.run(
        ["git", "-C", str(home), "-c", "core.hooksPath=/dev/null", *args],
        input=input,
        capture_output=True,
        check=False,
        env=environment,
    )
    if check and result.returncode:
        raise HomeError(os.fsdecode(result.stderr).strip() or "Git command failed")
    return result


def _check_name(name: str) -> None:
    if not isinstance(name, str) or not _NAME.fullmatch(name):
        _error("name must be a single lowercase slug")


def _check_safe_ancestors(path: Path) -> None:
    for ancestor in (path, *path.parents):
        if ancestor.exists() and ancestor.is_symlink():
            _error(f"symlinked path is not allowed: {ancestor}")


def _check_not_nested_git(path: Path) -> None:
    for ancestor in (path, *path.parents):
        if (ancestor / ".git").exists():
            _error("agent home cannot be created inside an existing Git repository")


def _safe_relative(relative: str) -> Path:
    candidate = Path(relative)
    if (
        candidate.is_absolute()
        or ".." in candidate.parts
        or "." in candidate.parts
        or not candidate.parts
    ):
        _error("unsafe runtime file path")
    return candidate


def _assert_regular_tree(root: Path, home_links: bool = False) -> None:
    """Reject symlinks and special files below a home before Git may see them."""
    for entry in root.rglob("*"):
        if entry.is_symlink():
            from .runtimes import SKILL_LINKS

            relative = entry.relative_to(root).as_posix()
            if (
                home_links
                and relative in SKILL_LINKS
                and os.readlink(entry) == SKILL_LINKS[relative]
                and not (root / "skills").is_symlink()
                and (root / "skills").is_dir()
            ):
                continue
            _error(f"symlink is not allowed: {entry}")
        mode = entry.lstat().st_mode
        if not (stat.S_ISREG(mode) or stat.S_ISDIR(mode)):
            _error(f"special file is not allowed: {entry}")


def _validate_home(
    home: Path, *, reader: Callable[[Path], str | None] | None = None
) -> dict:
    home = Path(home)
    if home.is_symlink() or not home.is_dir():
        _error("home must be a non-symlink directory")
    _check_safe_ancestors(home)
    if not (home / ".git").is_dir() or (home / ".git").is_symlink():
        _error("home must be a standalone Git repository")
    _check_not_nested_git(home.parent)
    parent_git = _git(
        home, "rev-parse", "--show-superproject-working-tree", check=False
    ).stdout.strip()
    if parent_git:
        _error("nested Git repositories are not agent homes")
    _assert_regular_tree(home, home_links=True)
    manifest = home / "soulsteads.json"
    if manifest.is_symlink() or not manifest.is_file():
        _error("missing manifest")
    try:
        text = (
            reader(manifest)
            if reader is not None
            else manifest.read_text(encoding="utf-8")
        )
        if text is None:
            raise HomeError("missing manifest")
        value = json.loads(text)
    except (OSError, json.JSONDecodeError) as exc:
        raise HomeError("invalid manifest") from exc
    from .runtimes import RUNTIMES

    if (
        not isinstance(value, dict)
        or type(value.get("schema_version")) is not int
        or value.get("schema_version") != 1
        or not isinstance(value.get("name"), str)
        or not _NAME.fullmatch(value["name"])
        or value.get("runtime") not in RUNTIMES
    ):
        _error("unsupported manifest schema")
    from .learning import validate as validate_learning

    validate_learning(value.get("learning"))
    from .memory_automation import effective_policy, validate as validate_automation

    validate_automation(value.get("hindsight_automation"), value.get("hindsight"))
    effective_policy(value.get("hindsight_policy", {}))
    return value


def load(home: Path) -> dict:
    """Return a validated agent manifest; never treats arbitrary directories as homes."""
    return _validate_home(Path(home))


def _secret_path(path: Path) -> bool:
    return any(
        part.lower().startswith(".env")
        or part.lower().split(".")[0] in _SECRET_NAMES
        or part.lower() in {"auth.json", "id_rsa", "id_ed25519"}
        or part.lower().endswith((".pem", ".key", ".p12", ".pfx"))
        for part in path.parts
    )


def _workspace_file_path(path: str) -> bool:
    """Recognize a canonical, non-private workspace path, without filesystem I/O."""
    if not isinstance(path, str) or not path.startswith("workspace/"):
        return False
    parts = path.split("/")
    return (
        not any(part in {"", ".", ".."} for part in parts)
        and not any(ord(char) < 32 or ord(char) == 127 or char == "\\" for char in path)
        and not _secret_path(Path(path))
        and not any(
            part.lower().startswith(("credentials", "secrets"))
            or part.lower() in {
                ".git", ".gitmodules", ".gitattributes", ".runtime", ".cache",
                "sessions", ".claude", ".codex", ".opencode", ".pi", ".agents",
            }
            for part in parts[1:]
        )
    )


def _allowed_path(path: str) -> bool:
    if path.startswith("workspace/"):
        return False
    candidate = _safe_relative(path)
    if _secret_path(candidate):
        return False
    try:
        from soulsteads.runtimes import RUNTIMES

        runtime_paths = {key for runtime in RUNTIMES for key in _render(runtime)}
    except (ImportError, ValueError):
        runtime_paths = set()
    from .runtimes import SKILL_LINKS

    return (
        str(candidate)
        in {
            *_PERSONA_FILES,
            "soulsteads.json",
            ".gitignore",

            ".mcp.json",
            ".pi/mcp.json",
            "LEARNING.md",
            ".codex/hooks.json",
            ".opencode/plugins/soulsteads-memory.js",
            ".pi/extensions/soulsteads-memory.ts",
            "opencode.jsonc",
            *runtime_paths,
            *SKILL_LINKS,
        }
        or candidate.parts[0] == "skills"

    )


def _assert_clean(home: Path) -> None:
    status = _git(home, "status", "--porcelain", "--untracked-files=all").stdout
    if status:
        _error("home has dirty or untracked changes")


def _assert_no_worktree_hardlinks(home: Path) -> None:
    """Keep Git patch application from modifying an externally linked worktree file."""
    for entry in home.rglob("*"):
        if entry.relative_to(home).parts[0] == ".git":
            continue
        metadata = entry.lstat()
        if stat.S_ISREG(metadata.st_mode) and metadata.st_nlink != 1:
            _error(f"hardlinked worktree file is not allowed: {entry}")


def _open_workspace_file(home: Path, path: str, lifetime: ExitStack) -> _WorkspaceFile:
    """Bind the lexical Home-to-leaf chain, including a tracked deletion's absence."""
    from .hermes_import import _open_dir
    from .publication import _identity

    parts = path.split("/")
    try:
        with ExitStack() as dirs:
            directory, chain = _open_dir(home)
            dirs.callback(os.close, directory)
            for part in parts[:-1]:
                try:
                    directory = os.open(
                        part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory
                    )
                except FileNotFoundError:
                    return chain, None, None
                dirs.callback(os.close, directory)
                info = os.fstat(directory)
                chain.append((info.st_dev, info.st_ino, info.st_mode, info.st_uid))
                try:
                    os.stat(".git", dir_fd=directory, follow_symlinks=False)
                except FileNotFoundError:
                    pass
                else:
                    _error("workspace selection crosses a nested Git repository")
            leaf = parts[-1]
            try:
                info = os.stat(leaf, dir_fd=directory, follow_symlinks=False)
            except FileNotFoundError:
                return chain, None, None
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                _error("workspace selection must be a regular single-link file")
            if info.st_size > _MAX_WORKSPACE_FILE:
                _error("workspace file exceeds the 64 MiB limit")
            fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
            lifetime.callback(os.close, fd)
            if _identity(os.fstat(fd)) != _identity(info):
                _error("workspace selection changed while opening")
            return chain, info, fd
    except OSError as exc:
        raise HomeError("cannot safely open workspace selection") from exc


def _read_workspace_file(fd: int, info: os.stat_result) -> bytes:
    from .publication import _identity

    # A bounded read protects against growth after the pre-open size check.
    with os.fdopen(os.dup(fd), "rb") as source:
        data = source.read(info.st_size + 1)
    if len(data) != info.st_size or _identity(os.fstat(fd)) != _identity(info):
        _error("workspace selection changed while reading")
    return data


def _verify_workspace_files(home: Path, files: dict[str, _WorkspaceFile]) -> None:
    from .publication import _identity

    for path, (chain, info, fd) in files.items():
        try:
            with ExitStack() as binding:
                current_chain, current, _ = _open_workspace_file(home, path, binding)
                if current_chain == chain:
                    if info is None and current is None:
                        continue
                    if (
                        info is not None
                        and current is not None
                        and fd is not None
                        and _identity(info) == _identity(current) == _identity(os.fstat(fd))
                    ):
                        continue
        except HomeError as exc:
            raise HomeError("workspace selection changed before commit") from exc
        _error("workspace selection changed before commit")


def _staged_names(home: Path) -> list[str]:
    return _git(
        home, "diff", "--cached", "--no-renames", "--ignore-submodules=none",
        "--name-only", "-z",
    ).stdout.split("\0")[:-1]


def commit(
    home: Path,
    message: str | None = None,
    *,
    workspace_files: tuple[str, ...] | list[str] = (),
) -> str:
    """Commit the identity allowlist and any workspace files selected for this commit."""
    home = Path(home)
    _validate_home(home)
    if message is not None and (not isinstance(message, str) or not message.strip()):
        _error("commit message must not be empty")
    selected = set(workspace_files)
    if any(not _workspace_file_path(path) for path in selected):
        _error("workspace selection must be a non-private Home-relative file path")
    with ExitStack() as lifetime:
        files = {path: _open_workspace_file(home, path, lifetime) for path in sorted(selected)}
        return _commit_selected(home, message, files)


def _commit_selected(home: Path, message: str | None, files: dict[str, _WorkspaceFile]) -> str:
    selected = files.keys()
    tracked: set[str] = set()
    if selected:
        tracked = set(_git(
            home, "ls-tree", "-rz", "--name-only", "HEAD", "--", "workspace/"
        ).stdout.split("\0")[:-1])
    exists = {path for path, (_, info, _) in files.items() if info is not None}
    if selected - exists - tracked:
        _error("workspace selection does not name an existing or tracked file")

    def allowed(path: str) -> bool:
        return path in selected or _allowed_path(path)

    if any(not allowed(path) for path in _staged_names(home)):
        _error("index contains unsafe paths")
    candidates = _git(
        home, "ls-files", "--cached", "--others", "--exclude-standard", "-z"
    ).stdout.split("\0")[:-1]
    if exists and any(
        path.startswith(file + "/") or file.startswith(path + "/")
        for file in exists for path in tracked
    ):
        _error("workspace selection would replace a tracked file or directory; record deletions first")
    paths = sorted({path for path in candidates if _allowed_path(path)})
    if not paths and not selected:
        _error("no safe agent files to commit")
    index_records = []
    zero = ""
    if selected - exists:
        zero = "0" * len(_git(home, "rev-parse", "HEAD").stdout.strip())
    for path, (_, info, fd) in files.items():
        if info is None:
            mode, oid = "0", zero
        else:
            # Hash admitted bytes, not a pathname Git would reopen or filter.
            assert fd is not None
            mode = "100755" if info.st_mode & stat.S_IXUSR else "100644"
            oid = _git_bytes(
                home, "hash-object", "-w", "--stdin", input=_read_workspace_file(fd, info)
            ).stdout.decode("ascii").strip()
        index_records.append(os.fsencode(f"{mode} {oid}\t{path}\0"))
    _verify_workspace_files(home, files)
    if paths:
        _git(home, "--literal-pathspecs", "add", "-A", "--", *paths)
    if index_records:
        _verify_workspace_files(home, files)
        _git_bytes(home, "update-index", "-z", "--index-info", input=b"".join(index_records))
    staged = _staged_names(home)
    if not staged or any(not allowed(path) for path in staged):
        _error("index contains unsafe paths")
    if message is None:
        noun = "file" if len(staged) == 1 else "files"
        message = f"Update agent home ({len(staged)} {noun})"
    _verify_workspace_files(home, files)
    _git(home, "commit", "-m", message)
    return _git(home, "rev-parse", "HEAD").stdout.strip()


def history(home: Path) -> str:
    home = Path(home)
    _validate_home(home)
    return _git(home, "log", "--format=%H %s").stdout


def revert(home: Path, revision: str) -> str:
    """Restore the managed Home snapshot without writing into the workspace."""
    home = Path(home)
    _validate_home(home)
    if not isinstance(revision, str) or not re.fullmatch(
        r"[0-9a-fA-F]{7,40}", revision
    ):
        _error("revision must be a hexadecimal commit id")
    _assert_clean(home)
    _assert_no_worktree_hardlinks(home)
    if _git(
        home, "merge-base", "--is-ancestor", revision, "HEAD", check=False
    ).returncode:
        _error("revision must be an ancestor")
    tree = _git(home, "ls-tree", "-rz", revision).stdout.split("\0")[:-1]
    for entry in tree:
        mode, _, remainder = entry.partition(" ")
        _, _, name = remainder.partition("\t")
        if name == "workspace" or name.startswith("workspace/"):
            continue
        from .runtimes import SKILL_LINKS

        if mode == "120000":
            if (
                name not in SKILL_LINKS
                or _git(home, "show", f"{revision}:{name}").stdout != SKILL_LINKS[name]
            ):
                _error("historical tree contains unsafe symlinks")
        elif mode not in ("100644", "100755"):
            _error("historical tree contains unsupported file modes")
        if not _allowed_path(name):
            _error("historical tree contains unsafe paths")
    # Exclude workspace paths from the actual patch, not just the preflight list.
    managed = ("--", ".", ":(top,exclude)workspace")
    changed = _git(
        home, "diff", "--no-renames", "--ignore-submodules=none", "--name-only", "-z",
        revision, "HEAD", *managed,
    ).stdout.split("\0")[:-1]
    if any(not _allowed_path(name) for name in changed):
        _error("historical tree contains unsafe paths")
    if not changed:
        _error("no managed Home changes to restore; that snapshot is already checked out")
    patch = _git_bytes(
        home, "diff", "--binary", "--no-renames", "--no-ext-diff", "--no-textconv",
        revision, "HEAD", *managed,
    ).stdout
    applied = _git_bytes(home, "apply", "--reverse", "--index", input=patch, check=False)
    if applied.returncode:
        raise HomeError(f"cannot restore revision: {os.fsdecode(applied.stderr).strip()}")
    _git(home, "commit", "-m", f"Restore {revision}")
    return _git(home, "rev-parse", "HEAD").stdout.strip()


def configure(home: Path, runtime: str) -> None:
    """Change runtime selection through the checked manifest publication path."""
    from .native_config import configure_runtime

    configure_runtime(home, runtime)


def install_skill(home: Path, source: Path) -> Path:
    home = Path(home)
    _validate_home(home)
    source = Path(source)
    if source.is_symlink() or not source.is_dir():
        _error("skill source must be a local non-symlink directory")
    _check_safe_ancestors(source)
    _assert_regular_tree(source)
    skill_file = source / "SKILL.md"
    if not skill_file.is_file() or skill_file.is_symlink():
        _error("skill source requires SKILL.md")
    text = skill_file.read_text(encoding="utf-8")
    frontmatter = re.match(r"\A---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not frontmatter:
        _error("SKILL.md requires YAML frontmatter")
    fields = dict(
        re.findall(
            r"^([A-Za-z][\w-]*):\s*(.+?)\s*$", frontmatter.group(1), re.MULTILINE
        )
    )
    name = fields.get("name", "")
    if not _NAME.fullmatch(name) or not fields.get("description", "").strip():
        _error("skill frontmatter requires slug name and description")
    for entry in source.rglob("*"):
        relative = entry.relative_to(source)
        if any(part.startswith(".git") for part in relative.parts) or _secret_path(
            relative
        ):
            _error("skill source contains forbidden path")
    destination = home / "skills" / name
    if destination.exists() or destination.is_symlink():
        _error("skill already exists")
    shutil.copytree(source, destination, copy_function=shutil.copy2)
    for entry in destination.rglob("*"):
        if entry.is_file():
            entry.chmod(0o700 if entry.stat().st_mode & stat.S_IXUSR else 0o600)
        elif entry.is_dir():
            entry.chmod(0o700)
    destination.chmod(0o700)
    return destination


def create(
    name: str,
    runtime: str,
    path: Path | None = None,
    base: Path | None = None,
    with_skills: bool = True,
    *,
    learning: dict | None = None,
) -> Path:
    """Create a fresh standalone, private, generated agent Git repository."""
    _check_name(name)
    if not isinstance(runtime, str) or not runtime:
        _error("runtime must be a nonempty string")
    target = (
        Path(path)
        if path is not None
        else (
            Path(base) if base is not None else Path.home() / ".soulsteads" / "agents"
        )
        / name
    )
    if target.exists() or target.is_symlink():
        _error("refusing to adopt or overwrite an existing path")
    _check_safe_ancestors(target.parent)
    _check_not_nested_git(target.parent)
    from .runtimes import RUNTIMES, digest, render, render_all
    from .templates import DOCUMENTS

    if runtime not in RUNTIMES:
        _error("unsupported runtime")
    from .learning import validate as validate_learning

    if learning is None:
        learning = {"mode": "off", "skills": []}
    validate_learning(learning)
    available = {"starter", "skill-maintenance"} if with_skills else set()
    if any(name not in available for name in learning["skills"]):
        _error("learning scope requires existing local skill files")
    rendered = render_all(DOCUMENTS, learning=learning)
    native_owned = None
    if runtime == "soulsteads":
        from . import native_harness

        rendered.update(render("soulsteads", DOCUMENTS, learning=learning))
        text, native_owned = native_harness.plan(
            {"name": name}, None, "LEARNING.md" in rendered
        )
        rendered[native_harness.FILE] = text
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    _private_dir(target)
    try:
        from .templates import DOCUMENTS, SKILL_MAINTENANCE, STARTER

        for filename, content in DOCUMENTS.items():
            _write_private(target / filename, content)
        _write_private(
            target / ".gitignore",
            ".env\n.env.*\ncredentials*\nsecrets*\n*.key\n*.pem\nauth.json\nworkspace/*\n!workspace/.gitkeep\n.runtime/\n.cache/\nsessions/\n.claude/settings.local.json\n.claude/projects/\n.pi/sessions/\n.codex/sessions/\n.opencode/node_modules/\n",
        )
        workspace = target / "workspace"
        _private_dir(workspace)
        _write_private(workspace / ".gitkeep", "")
        skills = target / "skills"
        _private_dir(skills)
        _write_private(skills / ".gitkeep", "")
        from .runtimes import SKILL_LINKS

        for relative, link in SKILL_LINKS.items():
            alias = target / relative
            alias.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            alias.symlink_to(link, target_is_directory=True)
        if with_skills:
            for skill_name, content in (
                ("starter", STARTER),
                ("skill-maintenance", SKILL_MAINTENANCE),
            ):
                starter = skills / skill_name
                _private_dir(starter)
                _write_private(starter / "SKILL.md", content)
        # Git inherits the caller's umask; create its root privately so newly
        # created and imported Homes satisfy the verifier without target repair.
        _private_dir(target / ".git")
        _git(target, "init", "--quiet")
        _git(target, "config", "user.name", "Soulsteads")
        _git(target, "config", "user.email", "soulsteads@localhost")
        manifest = {
            "schema_version": 1,
            "name": name,
            "runtime": runtime,
            "learning": learning,
            "managed_files": {p: digest(text) for p, text in rendered.items()},
        }
        if native_owned is not None:
            from . import native_harness

            manifest["shared_owned"] = {"soulsteads": native_owned}
            manifest["managed_files"][native_harness.FILE] = native_harness.digest_owned(native_owned)
        from .publication import publish_fresh

        publish_fresh(
            target,
            {
                **rendered,
                "soulsteads.json": json.dumps(manifest, indent=2) + "\n",
            },
        )
        _git(target, "add", "--", ".")
        _git(target, "commit", "--quiet", "-m", "Initialize agent home")
    except Exception:
        shutil.rmtree(target, ignore_errors=True)
        raise
    return target
