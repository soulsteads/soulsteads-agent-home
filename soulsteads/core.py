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
from pathlib import Path
from typing import Final


class HomeError(Exception):
    """Raised when an agent home cannot be safely operated on."""


_NAME: Final = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_PERSONA_FILES: Final = ("USER.md", "SOUL.md", "AGENTS.md", "MEMORY.md")
_SECRET_NAMES: Final = {".env", "credentials", "credential", "secrets", "secret"}


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
    environment = os.environ.copy()
    for key in list(environment):
        if key.startswith("GIT_"):
            environment.pop(key)
    result = subprocess.run(
        ["git", "-C", str(home), "-c", "core.hooksPath=/dev/null", *args],
        text=True,
        capture_output=True,
        check=False,
        env=environment,
    )
    if check and result.returncode:
        raise HomeError(result.stderr.strip() or "Git command failed")
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


def _allowed_path(path: str) -> bool:
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
            "workspace/.gitkeep",
            ".mcp.json",
            ".pi/mcp.json",
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


def commit(home: Path, message: str | None = None) -> str:
    """Explicitly commit only the narrow, safe identity allowlist."""
    home = Path(home)
    _validate_home(home)
    if message is not None and (not isinstance(message, str) or not message.strip()):
        _error("commit message must not be empty")
    _assert_regular_tree(home, home_links=True)
    staged = _git(home, "diff", "--cached", "--name-only", "-z").stdout.split("\0")[:-1]
    if any(not _allowed_path(path) for path in staged):
        _error("index contains unsafe paths")
    candidates = _git(
        home, "ls-files", "--cached", "--others", "--exclude-standard", "-z"
    ).stdout.split("\0")[:-1]
    paths = sorted({path for path in candidates if _allowed_path(path)})
    if not paths:
        _error("no safe agent files to commit")
    _git(home, "add", "-A", "--", *paths)
    staged = _git(home, "diff", "--cached", "--name-only", "-z").stdout.split("\0")[:-1]
    if not staged or any(not _allowed_path(path) for path in staged):
        _error("index contains unsafe paths")
    if message is None:
        noun = "file" if len(staged) == 1 else "files"
        message = f"Update agent home ({len(staged)} {noun})"
    _git(home, "commit", "-m", message)
    return _git(home, "rev-parse", "HEAD").stdout.strip()


def history(home: Path) -> str:
    home = Path(home)
    _validate_home(home)
    return _git(home, "log", "--format=%H %s").stdout


def revert(home: Path, revision: str) -> str:
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
    changed = _git(home, "diff", "--name-only", "-z", revision, "HEAD").stdout.split(
        "\0"
    )[:-1]
    if any(
        not _allowed_path(name) and name != "workspace/.gitkeep" for name in changed
    ):
        _error("historical tree contains unsafe paths")
    if not changed:
        _error("revision is already checked out")
    patch = _git(home, "diff", "--binary", revision, "HEAD").stdout
    applied = subprocess.run(
        [
            "git",
            "-C",
            str(home),
            "-c",
            "core.hooksPath=/dev/null",
            "apply",
            "--reverse",
            "--index",
        ],
        input=patch,
        text=True,
        capture_output=True,
        check=False,
        env={k: v for k, v in os.environ.items() if not k.startswith("GIT_")},
    )
    if applied.returncode:
        raise HomeError(f"cannot restore revision: {applied.stderr.strip()}")
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
    from .runtimes import RUNTIMES, digest, render_all
    from .templates import DOCUMENTS

    if runtime not in RUNTIMES:
        _error("unsupported runtime")
    rendered = render_all(DOCUMENTS)
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
            "managed_files": {p: digest(text) for p, text in rendered.items()},
        }
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
