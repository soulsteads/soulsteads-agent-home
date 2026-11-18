"""Opt-in, read-only probe of installed harness versions.

Runs ``<binary> --version`` for each harness and compares the strictly parsed
result with the versions recorded in docs/native-acceptance.md. A match is not
live qualification, and every error maps to a non-qualified status.
"""

import os
import re
import selectors
import shutil
import signal
import subprocess
import time
from pathlib import Path

TIMEOUT_SECONDS = 5.0
MAX_OUTPUT_BYTES = 4096

# Qualified versions as recorded in docs/native-acceptance.md (see the sources
# listed in docs/runtimes.md). Nothing here is invented: a runtime without a
# record reports "no qualified version recorded".
QUALIFIED_VERSIONS = {
    "pi": ("1.4.0",),
    "opencode": ("1.19.5",),
    "codex": ("0.157.1", "0.169.0"),
    "claude": ("2.1.270", "2.1.318", "2.1.325"),
}
# Bare executable names, resolved on PATH exactly as Home's launcher does.
BINARIES = {"pi": "pi", "opencode": "opencode", "codex": "codex", "claude": "claude"}
VERSION_ARGV = ("--version",)

STATUSES = (
    "qualified",
    "newer-unqualified",
    "older-unqualified",
    "unparseable",
    "not-installed",
    "probe-failed/timeout",
    "probe-skipped",
)

_VERSION = re.compile(
    rb"(?<![0-9A-Za-z.+-])v?([0-9]{1,6})\.([0-9]{1,6})\.([0-9]{1,6})(?![0-9A-Za-z+-]|\.[0-9])"
)
# Only non-secret variables needed to locate and start a binary are inherited.
_ENV_KEYS = ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "USER", "LOGNAME")


def _tuple(text):
    return tuple(int(part) for part in text.split("."))


def parse_version(output):
    """Return one strict dotted version, or None when absent or ambiguous."""
    found = {m.groups() for m in _VERSION.finditer(output)}
    if len(found) != 1:
        return None
    return ".".join(part.decode("ascii") for part in next(iter(found)))


def compare(version, qualified):
    """Classify a parsed version against the qualified versions."""
    if version in qualified:
        return "qualified"
    if _tuple(version) > max(_tuple(item) for item in qualified):
        return "newer-unqualified"
    return "older-unqualified"


_MANAGERS = ("mise", "asdf", "volta", "pyenv", "nodenv", "rbenv")
_NEUTRAL_CWD = "/"
_SCRIPT_PEEK_BYTES = 256


def _has_parts(parts, *run):
    n = len(run)
    return any(tuple(parts[i : i + n]) == run for i in range(len(parts) - n + 1))


def _classify_one(path):
    parts = Path(path).parts
    name = parts[-1] if parts else ""
    if _has_parts(parts, "mise", "shims") or _has_parts(parts, "mise", "command-wrappers"):
        return "mise"
    if name == "mise":  # a shim symlink resolves to the mise binary itself
        return "mise"
    if _has_parts(parts, ".asdf", "shims"):
        return "asdf"
    if _has_parts(parts, ".volta", "bin") or name in ("volta", "volta-shim"):
        return "volta"
    if _has_parts(parts, ".pyenv", "shims"):
        return "pyenv"
    if "shims" in parts[:-1]:  # nodenv/rbenv-style; any other */shims/* path
        return "shim"
    return None


def _script_manager(path):
    """Manager named on a script's first (shebang) line, else None."""
    try:
        with open(path, "rb") as handle:
            first = handle.read(_SCRIPT_PEEK_BYTES).split(b"\n", 1)[0]
    except OSError:
        return None
    if not first.startswith(b"#!"):
        return None
    for token in first[2:].decode("utf-8", "replace").split():
        if os.path.basename(token) in _MANAGERS:
            return os.path.basename(token)
    return None


def detect_wrapper(path):
    """Name the version manager behind a resolved path, or None.

    Rules: the path or its symlink target is under mise shims/command-wrappers,
    asdf/volta/pyenv shim directories or any other ``*/shims/*`` directory, is
    a symlink to a ``mise`` or volta binary, or is a script whose shebang line
    names a known manager. Unknown wrapper schemes cannot be detected.
    """
    try:
        real = os.path.realpath(path)
    except (OSError, ValueError):
        real = path
    return _classify_one(path) or _classify_one(real) or _script_manager(real)


def _resolve_mise_shim(name):
    """Read-only ``mise which <name>``; return a trusted real binary or None."""
    mise = shutil.which("mise")
    if mise is None or detect_wrapper(mise) not in ("mise", None):
        return None
    if _has_parts(Path(mise).parts, "mise", "shims"):
        return None
    outcome, out, _ = _run_raw(mise, ("which", name))
    if outcome != "ok":
        return None
    try:
        text = out.decode("utf-8").strip()
    except UnicodeDecodeError:
        return None
    if not text or "\n" in text or "\0" in text or not os.path.isabs(text):
        return None
    if not (os.path.isfile(text) and os.access(text, os.X_OK)):
        return None
    if detect_wrapper(text) is not None:
        return None
    return text


def _run(path):
    """Run the version command; return (outcome, output bytes)."""
    outcome, out, err = _run_raw(path, VERSION_ARGV)
    return outcome, out + b"\n" + err


def _run_raw(path, argv_tail):
    """Run ``path`` with argv_tail safely; return (outcome, stdout, stderr)."""
    env = {key: os.environ[key] for key in _ENV_KEYS if key in os.environ}
    env["NO_COLOR"] = "1"
    # Version-manager shims (for example mise) may otherwise download and install
    # a missing tool while answering; the probe must stay read-only.
    env["MISE_AUTO_INSTALL"] = "0"
    env["MISE_NOT_FOUND_AUTO_INSTALL"] = "0"
    env["MISE_EXEC_AUTO_INSTALL"] = "0"
    try:
        process = subprocess.Popen(
            [path, *argv_tail],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            cwd=_NEUTRAL_CWD,
            shell=False,
            close_fds=True,
            start_new_session=True,
        )
    except (OSError, ValueError):
        return "failed", b"", b""

    def kill():
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except OSError:
            try:
                process.kill()
            except OSError:
                pass

    chunks = {process.stdout: b"", process.stderr: b""}
    outcome = "ok"
    deadline = time.monotonic() + TIMEOUT_SECONDS
    selector = selectors.DefaultSelector()
    try:
        for stream in chunks:
            selector.register(stream, selectors.EVENT_READ)
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                outcome = "timeout"
                break
            for key, _ in selector.select(remaining):
                data = os.read(key.fd, MAX_OUTPUT_BYTES + 1)
                if not data:
                    selector.unregister(key.fileobj)
                    continue
                chunks[key.fileobj] += data
                if len(chunks[key.fileobj]) > MAX_OUTPUT_BYTES:
                    outcome = "too-large"
            if outcome == "too-large":
                break
        if outcome == "ok":
            try:
                process.wait(timeout=max(deadline - time.monotonic(), 0.01))
            except subprocess.TimeoutExpired:
                outcome = "timeout"
    except OSError:
        outcome = "failed"
    finally:
        selector.close()
        if outcome != "ok" or process.poll() is None:
            kill()
        try:
            process.wait(timeout=2)
        except (subprocess.TimeoutExpired, OSError):
            pass
        for stream in (process.stdout, process.stderr):
            try:
                stream.close()
            except OSError:
                pass
    if outcome == "ok" and process.returncode != 0:
        outcome = "nonzero"
    return outcome, chunks[process.stdout], chunks[process.stderr]


def _skipped(result, reason):
    result["status"] = "probe-skipped"
    result["reason"] = reason
    return result


def probe_runtime(runtime):
    """Return a content-free, fail-closed result for one harness."""
    qualified = QUALIFIED_VERSIONS.get(runtime, ())
    result = {
        "runtime": runtime,
        "binary": BINARIES[runtime],
        "status": "probe-failed/timeout",
        "installed_version": None,
        "qualified_versions": list(qualified),
        "note": "A version match is not live qualification.",
    }
    path = shutil.which(BINARIES[runtime])
    if path is None:
        result["status"] = "not-installed"
        return result
    manager = detect_wrapper(path)
    if manager is not None:
        if manager == "mise":
            resolved = _resolve_mise_shim(os.path.basename(path))
            if resolved is None:
                return _skipped(result, "unresolved-mise-shim")
            result["resolved_via"] = "mise which"
            path = resolved
        else:
            return _skipped(result, f"wrapper:{manager}")
    outcome, output = _run(path)
    if outcome in ("timeout", "nonzero", "failed"):
        result["reason"] = {
            "timeout": "timeout",
            "nonzero": "non-zero-exit",
            "failed": "exec-error",
        }[outcome]
        return result
    version = None if outcome == "too-large" else parse_version(output)
    if version is None:
        result["status"] = "unparseable"
        return result
    result["installed_version"] = version
    if not qualified:
        result["status"] = "unparseable"
        result["reason"] = "no qualified version recorded"
        return result
    result["status"] = compare(version, qualified)
    return result


def probe_all(runtimes):
    runtimes = [name for name in runtimes if name in BINARIES]
    return {
        "scope": "opt-in-read-only-version-probe",
        "command": "<binary> --version",
        "results": [probe_runtime(name) for name in runtimes],
    }
