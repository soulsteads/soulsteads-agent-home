"""Offline structural checks; never launch a runtime or contact integrations."""

import json
import os
import re
import stat
import tomllib
from pathlib import Path

from . import core
from .hermes_import import Snapshot, _absolute
from .runtimes import RUNTIMES, SKILL_LINKS, render


def _json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def constant(value):
        raise ValueError("nonstandard JSON constant")

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


def verify_home(home):
    """Return content-free findings; success is not runtime or privacy certification."""
    findings = []

    def add(identifier, status, consequence, next_action):
        findings.append(
            {
                "id": identifier,
                "status": status,
                "consequence": consequence,
                "next_action": next_action,
            }
        )

    try:
        if os.name != "posix":
            raise ValueError("offline verification requires POSIX file safety")
        home = _absolute(Path(home))
        snap = Snapshot()
        snap.directory(home)
        snap.directory(home / ".git")
        manifest = _json(snap.read(home / "soulsteads.json") or b"null")
        if (
            not isinstance(manifest, dict)
            or type(manifest.get("schema_version")) is not int
            or manifest["schema_version"] != 1
            or not isinstance(manifest.get("name"), str)
            or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", manifest["name"])
            or manifest.get("runtime") not in RUNTIMES
        ):
            raise ValueError("invalid manifest")
        runtime = manifest["runtime"]
        for filename in core._PERSONA_FILES:
            raw = snap.read(home / filename)
            if raw is None:
                add(
                    "identity-files",
                    "failed",
                    "A required identity file is missing.",
                    "Restore the required Home documents.",
                )
                break
            raw.decode("utf-8")
        else:
            add(
                "identity-files",
                "passed",
                "Required identity files are readable.",
                "Confirm actual instruction loading in a separately authorized runtime test.",
            )
        for filename in render(runtime):
            raw = snap.read(home / filename)
            if raw is None:
                add(
                    "runtime-config",
                    "failed",
                    "A runtime configuration file is missing.",
                    "Review the selected adapter and restore its configuration.",
                )
                break
            if filename.endswith(".json"):
                if not isinstance(_json(raw), dict):
                    raise ValueError("runtime config must be an object")
            elif filename.endswith(".toml"):
                tomllib.loads(raw.decode("utf-8"))
            else:
                raw.decode("utf-8")
        else:
            add(
                "runtime-config",
                "passed",
                "Adapter files have valid basic syntax.",
                "Native configuration semantics, dependencies and credentials remain unverified.",
            )
        aliases = {}
        for relative, target in SKILL_LINKS.items():
            alias = home / relative
            snap.directory(alias.parent)
            info = alias.lstat()
            if not stat.S_ISLNK(info.st_mode) or os.readlink(alias) != target:
                raise ValueError("unsafe skill alias")
            aliases[alias] = (
                info.st_dev,
                info.st_ino,
                info.st_mtime_ns,
                info.st_ctime_ns,
            )
        snap.directory(home / "skills")
        for entry in (home / "skills").iterdir():
            if entry.is_dir():
                snap.directory(entry)
                if snap.read(entry / "SKILL.md") is None:
                    raise ValueError("skill directory lacks metadata")
        pending = [home / "skills"]
        inventory_count = 0
        portability = False
        metadata_unverified = False
        while pending:
            directory = pending.pop()
            snap.directory(directory)
            for entry in directory.iterdir():
                inventory_count += 1
                if inventory_count > 10000:
                    raise ValueError("excessive skill inventory")
                info = entry.lstat()
                if stat.S_ISDIR(info.st_mode):
                    if len(entry.relative_to(home).parts) > 32:
                        raise ValueError("excessive skill nesting")
                    pending.append(entry)
                else:
                    raw = snap.read(entry)
                    if entry.name != "SKILL.md":
                        continue
                    from .hermes_import import ImportErrorSafe, require_yaml

                    try:
                        require_yaml()
                    except ImportErrorSafe:
                        metadata_unverified = True
                    else:
                        from .skill_conversion import convert_skill

                        convert_skill(raw, entry.parent.name)
                    text = raw.decode("utf-8")
                    portability |= bool(
                        re.search(
                            r"\b(skill_view|skill_manage|execute_code|hindsight_recall|"
                            r"hindsight_retain|hindsight_reflect|session_search)\b",
                            text,
                        )
                    )
        add(
            "skill-metadata",
            "needs-review" if metadata_unverified else "passed",
            "Skill metadata parsing requires the optional Hermes extra."
            if metadata_unverified
            else "Local skill documents passed metadata validation.",
            "Install soulsteads[hermes] to validate YAML skill metadata; no scripts are executed."
            if metadata_unverified
            else "Confirm skill discovery with the native runtime separately.",
        )
        if portability:
            add(
                "skill-portability",
                "needs-review",
                "Some skill text mentions tools that may be Hermes-specific.",
                "Review native tool equivalents; this heuristic is not an exhaustive dependency audit.",
            )
        receipt_raw = snap.read(home / ".runtime/hermes/IMPORT-RECEIPT.json")
        if receipt_raw is not None:
            receipt = _json(receipt_raw)
            if (
                not isinstance(receipt, dict)
                or receipt.get("status") != "imported"
                or not isinstance(receipt.get("unsupported"), list)
                or not all(isinstance(value, str) for value in receipt["unsupported"])
            ):
                raise ValueError("invalid import receipt")
            add(
                "migration-follow-up",
                "needs-review" if receipt["unsupported"] else "passed",
                "The import receipt records manual migration work."
                if receipt["unsupported"]
                else "No manual work was listed in the original import receipt.",
                "Review the private receipt; it is historical evidence, not proof of current integration health.",
            )
        snap.read(home / ".gitignore")
        snap.read(home / ".git/index")
        snap.read(home / ".git/config")
        tracked = core._git(
            home, "-c", "core.fsmonitor=false", "ls-files", "-z"
        ).stdout.split("\0")[:-1]
        unsafe = any(
            core._secret_path(Path(path)) or Path(path).parts[0] == ".runtime"
            for path in tracked
        )
        probes = (
            ".env",
            ".env.local",
            "auth.json",
            "credentials",
            "secrets",
            ".runtime/",
            ".runtime/hermes/config.yaml",
            ".runtime/hermes/IMPORT-RECEIPT.json",
            ".runtime/hermes/.env",
            ".runtime/hermes/hindsight/config.json",
        )
        ignored = all(
            core._git(
                home,
                "-c",
                "core.fsmonitor=false",
                "check-ignore",
                "--no-index",
                "-q",
                "--",
                probe,
                check=False,
            ).returncode
            == 0
            for probe in probes
        )
        untracked = core._git(
            home,
            "-c",
            "core.fsmonitor=false",
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
        ).stdout.split("\0")[:-1]
        unsafe |= any(
            core._secret_path(Path(path)) or Path(path).parts[0] == ".runtime"
            for path in untracked
        )
        add(
            "private-storage",
            "failed" if unsafe or not ignored else "passed",
            "Private paths must be ignored and absent from the Git index.",
            "Review Git tracking locally; this is not a secret-content scan or history audit.",
        )
        snap.verify()
        for alias, identity in aliases.items():
            info = alias.lstat()
            if (
                info.st_dev,
                info.st_ino,
                info.st_mtime_ns,
                info.st_ctime_ns,
            ) != identity or os.readlink(alias) != SKILL_LINKS[
                alias.relative_to(home).as_posix()
            ]:
                raise ValueError("skill alias changed")
    except (
        OSError,
        ValueError,
        core.HomeError,
        UnicodeError,
        TypeError,
        RecursionError,
    ):
        add(
            "home-safety",
            "failed",
            "Home structure could not be safely verified.",
            "Review file types, permissions, size limits and configuration locally.",
        )
    return {
        "schema_version": 1,
        "scope": "offline-structural",
        "status": (
            "failed"
            if any(f["status"] == "failed" for f in findings)
            else "needs-review"
            if any(f["status"] == "needs-review" for f in findings)
            else "passed"
        ),
        "activation_ready": False,
        "findings": findings,
        "not_verified": [
            "runtime-execution",
            "model-access",
            "external-memory",
            "mcp-connectivity",
            "permissions-equivalence",
            "secret-content",
        ],
    }
