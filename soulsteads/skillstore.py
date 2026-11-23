"""Send Home skill corrections to a configured Skillstore installation."""

import hashlib
import ipaddress
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from . import core, native_config, publication
from .skill_review import open_skill, skill_body

VERSION = re.compile(r"[0-9][0-9A-Za-z.+-]{0,127}")
ACTOR = re.compile(r"[0-9A-Za-z_.@-]{1,100}")
TOKEN_ENV = re.compile(r"[A-Za-z_][A-Za-z_0-9]{0,127}")


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _path(target):
    return target.home / ".runtime" / f"skillstore-{target.relative.parent.name}.json"


def _binding(target):
    path = _path(target)
    raw = target.snapshot.read(path)
    if raw is None:
        return None
    directory = _state_directory(target)
    os.close(directory)
    if target.snapshot.states[path][2] & 0o077:
        raise core.HomeError("expected an owner-only Skillstore binding file")
    try:
        binding = json.loads(raw)
        if (
            set(binding)
            != {
                "store",
                "actor",
                "token_env",
                "versions",
                "auto_submit",
            }
            or not isinstance(binding["versions"], dict)
            or type(binding["auto_submit"]) is not bool
        ):
            raise ValueError
        _validate_binding(
            target, binding["store"], binding["actor"], binding["token_env"]
        )
        return binding if binding["versions"] else None
    except (TypeError, ValueError):
        raise core.HomeError("invalid private Skillstore binding") from None


def _validate_binding(target, store, actor, token_env):
    if not ACTOR.fullmatch(actor) or (
        token_env is not None and not TOKEN_ENV.fullmatch(token_env)
    ):
        raise ValueError("invalid Skillstore contributor or token variable name")
    if store.startswith(("http://", "https://")):
        url = urlsplit(store)
        try:
            loopback = ipaddress.ip_address(url.hostname or "").is_loopback
        except ValueError:
            loopback = url.hostname == "localhost"
        if (
            not token_env
            or not url.hostname
            or url.username is not None
            or url.password is not None
            or url.query
            or url.fragment
            or (url.scheme == "http" and not loopback)
        ):
            raise ValueError(
                "remote Skillstore needs a token variable and HTTPS or loopback HTTP"
            )
    else:
        path = Path(store)
        if (
            token_env is not None
            or not path.is_absolute()
            or ".." in path.parts
            or path.is_relative_to(target.home)
        ):
            raise ValueError(
                "use an absolute local Skillstore path outside the Home without a token"
            )


def _command(binding, *args):
    executable = shutil.which("skillstore")
    if not executable:
        raise core.HomeError("install the Skillstore CLI and put it on PATH")
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("SKILLSTORE_")
    }
    if binding["token_env"]:
        token = os.environ.get(binding["token_env"])
        if not token:
            raise core.HomeError(
                "configured Skillstore contributor token is unavailable"
            )
        env["SKILLSTORE_TOKEN"] = token
    try:
        result = subprocess.run(
            [
                executable,
                "--store",
                binding["store"],
                "--kind",
                "agent",
                "--actor",
                binding["actor"],
                *args,
            ],
            env=env,
            capture_output=True,
            check=False,
            timeout=45,
        )
    except subprocess.TimeoutExpired:
        raise core.HomeError(
            "Skillstore timed out; check the registry before retrying"
        ) from None
    if result.returncode:
        raise core.HomeError(
            f"Skillstore {args[0]} failed; check the registry, permissions and version"
        )
    try:
        return json.loads(result.stdout)
    except (ValueError, UnicodeError):
        raise core.HomeError("Skillstore returned invalid JSON") from None


def _release(binding, name, version):
    if not VERSION.fullmatch(version):
        raise ValueError("provide an exact Skillstore version")
    release = _command(binding, "inspect", name, "--version", version)
    try:
        valid = (
            release["name"] == name
            and release["version"] == version
            and release["status"] in {"reviewed", "withdrawn"}
            and release["review"]["digest_reviewed"] == release["digest"]
            and _package_digest(release["files"]) == release["digest"]
        )
    except (KeyError, TypeError, AttributeError):
        valid = False
    if not valid:
        raise core.HomeError(
            "expected a reviewed Skillstore release with a matching manifest"
        )
    return release


def _stage(binding, name, version, scratch):
    release = _release(binding, name, version)
    if release["status"] != "reviewed":
        raise core.HomeError("Skillstore release is withdrawn")
    receipt = _command(
        binding, "install", name, "--version", version, "--target", str(scratch)
    )
    if (receipt["digest"], receipt["name"], receipt["version"]) != (
        release["digest"],
        name,
        version,
    ):
        raise core.HomeError("Skillstore release changed during staging")
    directory = scratch / name
    text = native_config._read(directory / "SKILL.md")
    if (
        text is None
        or release["files"]["SKILL.md"]["mode"] != "644"
        or release["files"]["SKILL.md"]["sha256"] != _sha(text)
    ):
        raise core.HomeError("expected a reviewed non-executable SKILL.md")
    return directory, text, release


def _state_directory(target, *, create=False):
    directory = native_config._open_relative_dir(
        target.root_fd, (".runtime",), create=create
    )
    metadata = os.fstat(directory)
    if metadata.st_uid != os.getuid() or metadata.st_mode & 0o077:
        os.close(directory)
        raise core.HomeError("expected an owner-only .runtime directory")
    return directory


def _remember(target, binding):
    directory = _state_directory(target, create=True)
    try:
        path = _path(target)
        publication.publish_file(
            directory,
            path.name,
            json.dumps(binding, indent=2, sort_keys=True) + "\n",
            expected=target.snapshot.states[path],
        )
    finally:
        os.close(directory)


def _matched_version(target, binding):
    current_hash = _sha(target.original)
    found = binding["versions"].get(current_hash)
    if found is None:
        raise core.HomeError(
            "local SKILL.md differs from the bound releases; review it before continuing"
        )
    return found


def _package_digest(files):
    # Skillstore's format hashes the sorted path, mode, and content digest.
    data = "".join(
        f"{entry['mode']} {entry['sha256']} {path}\n"
        for path, entry in sorted(files.items())
    )
    return "sha256:" + _sha(data)


def bind(home, name, version, *, store, actor, token_env, auto_submit):
    with open_skill(home, name) as target:
        previous = _binding(target)
        if store is None:
            if previous is None:
                return {"status": "unbound", "skill": name}
            with publication.cooperative_lock(target.root_fd):
                target.verify()
                _remember(target, {**previous, "versions": {}})
            return {"status": "unbound", "skill": name}
        _validate_binding(target, store, actor, token_env)
        wanted = {
            "store": store,
            "actor": actor,
            "token_env": token_env,
            "versions": previous["versions"]
            if previous and previous["store"] == store
            else {},
            "auto_submit": auto_submit,
        }
        with tempfile.TemporaryDirectory(prefix="soulsteads-skillstore-") as work:
            _, text, release = _stage(wanted, name, version, Path(work) / "base")
        if target.original != text:
            raise core.HomeError(
                "local SKILL.md must match the selected reviewed release before binding"
            )
        wanted["versions"][_sha(text)] = {
            "version": version,
            "digest": release["digest"],
        }
        with publication.cooperative_lock(target.root_fd):
            target.verify()
            _remember(target, wanted)
        return {
            "status": "bound",
            "skill": name,
            "auto_submit": auto_submit,
            "version": version,
            "digest": release["digest"],
        }


def learn(home, name, proposal):
    with open_skill(home, name) as target:
        policy = target.manifest.get("learning")
        if not policy or policy["mode"] == "off":
            raise core.HomeError("enable a Home learning mode to use skill learn")
        updated, report = target.plan(proposal)
        binding = _binding(target)
        if binding is None:
            return report
        if not binding["auto_submit"]:
            return {**report, "status": "registry-preview"}
        selected = _matched_version(target, binding)
        with tempfile.TemporaryDirectory(prefix="soulsteads-skillstore-") as work:
            staged, text, release = _stage(
                binding, name, selected["version"], Path(work) / "base"
            )
            if target.original != text or selected["digest"] != release["digest"]:
                raise core.HomeError(
                    "bound Skillstore release no longer matches the Home"
                )
            (staged / "SKILL.md").write_bytes(updated.encode("utf-8"))
            digest = _package_digest(
                {
                    **release["files"],
                    "SKILL.md": {"mode": "644", "sha256": _sha(updated)},
                }
            )
            with publication.cooperative_lock(target.root_fd):
                target.verify()
                existing = _command(binding, "proposals", "--name", name)
                prior = next(
                    (
                        item
                        for item in existing
                        if item["digest"] == digest
                        and item["base_version"] == selected["version"]
                    ),
                    None,
                )
                result = prior or _command(
                    binding,
                    "propose",
                    name,
                    str(staged),
                    "--base-version",
                    selected["version"],
                    f"--rationale={proposal['reason'].strip()}",
                )
            if result["digest"] != digest:
                raise core.HomeError("Skillstore returned a different proposal digest")
        return {
            **report,
            "status": "submitted" if prior is None else "already-submitted",
            "proposal_id": result["id"],
            "proposal_status": result["status"],
            "base_version": selected["version"],
            "digest": digest,
        }


def adopt(home, name, version, *, apply=None):
    with open_skill(home, name) as target:
        binding = _binding(target)
        if binding is None:
            raise core.HomeError("bind this Home skill to a Skillstore release first")
        selected = _matched_version(target, binding)
        if selected["version"] == version:
            raise core.HomeError("this Home already uses that reviewed version")
        original = target.original
        base = _release(binding, name, selected["version"])
        if (
            selected["digest"] != base["digest"]
            or _sha(original) != base["files"]["SKILL.md"]["sha256"]
        ):
            raise core.HomeError("bound Skillstore release no longer matches the Home")
        with tempfile.TemporaryDirectory(prefix="soulsteads-skillstore-") as work:
            _, updated, release = _stage(binding, name, version, Path(work) / "update")
        if {
            p
            for p in base["files"].keys() | release["files"].keys()
            if base["files"].get(p) != release["files"].get(p)
        } != {"SKILL.md"}:
            raise core.HomeError(
                "Home adoption requires a release that changes only SKILL.md"
            )
        # Reuse the local review contract to preserve metadata and bind the exact bytes.
        before, after = skill_body(original), skill_body(updated)
        candidate, report = target.plan(
            {
                "reason": f"Adopt reviewed Skillstore {name}@{version} ({release['digest']})",
                "before": before,
                "after": after,
            }
        )
        if candidate != updated:
            raise core.HomeError("Home adoption requires unchanged skill frontmatter")
        if apply is not None:
            if apply != report["review_id"]:
                raise ValueError(
                    "review ID differs; preview the reviewed version again"
                )
            with publication.cooperative_lock(target.root_fd):
                target.verify()
                # Record both valid versions first. The active file hash selects
                # the actual version even if publication is interrupted.
                binding["versions"][_sha(updated)] = {
                    "version": version,
                    "digest": release["digest"],
                }
                _remember(target, binding)
                target.publish(updated)
            report["status"] = "applied"
        return {
            **report,
            "previous_version": selected["version"],
            "version": version,
            "digest": release["digest"],
        }
