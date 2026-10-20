"""Convert Hermes skill frontmatter to portable Agent Skills metadata.

Only portable metadata is rewritten. Markdown instructions are preserved verbatim;
Hermes-specific tool APIs and cross-skill references are not translated.
"""

from __future__ import annotations

import json
import re


def _fail(message: str) -> ValueError:
    # Never include source YAML or parser diagnostics in public errors.
    return ValueError(message)


def convert_skill(raw: bytes, expected_name: str) -> bytes:
    """Return SKILL.md with canonical Agent Skills frontmatter.

    Required fields are validated against the source identity and Agent Skills
    limits. Optional license/compatibility strings and JSON-safe metadata maps are
    retained; all other Hermes or unknown fields are dropped. The Markdown body
    is unchanged. Related assets are the caller's responsibility and are copied
    without modification.
    """
    if not isinstance(raw, bytes):
        raise _fail("skill content must be bytes")
    if (
        not isinstance(expected_name, str)
        or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", expected_name)
        or len(expected_name) > 64
    ):
        raise _fail("expected skill name is not canonical")
    match = re.match(rb"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|$)", raw, re.DOTALL)
    if not match:
        raise _fail("skill requires YAML frontmatter")
    from . import hermes_import

    try:
        metadata = hermes_import._yaml(match.group(1))
    except hermes_import.ImportErrorSafe:
        # importer errors are sanitized; avoid leaking arbitrary parser errors.
        raise _fail("invalid skill frontmatter") from None
    name, description = metadata.get("name"), metadata.get("description")
    if (
        not isinstance(name, str)
        or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name)
        or len(name) > 64
        or name != expected_name
    ):
        raise _fail("skill name does not match canonical source identity")
    if (
        not isinstance(description, str)
        or not description.strip()
        or len(description) > 1024
    ):
        raise _fail("skill description is missing or exceeds 1024 characters")
    output = {"name": name, "description": description}
    for key in ("license", "compatibility"):
        value = metadata.get(key)
        if value is not None:
            if (
                not isinstance(value, str)
                or not value.strip()
                or (key == "compatibility" and len(value) > 500)
            ):
                raise _fail("invalid optional skill metadata")
            output[key] = value
    optional = metadata.get("metadata")
    if optional is not None:
        if not isinstance(optional, dict) or not all(
            isinstance(k, str) for k in optional
        ):
            raise _fail("invalid optional skill metadata")
        optional = {k: v for k, v in optional.items() if k != "hermes"}
        if not all(isinstance(value, str) for value in optional.values()):
            raise _fail("portable skill metadata values must be strings")
        output["metadata"] = optional
    lines = ["---"]
    for key in ("name", "description", "license", "compatibility"):
        if key in output:
            lines.append(f"{key}: {json.dumps(output[key], ensure_ascii=False)}")
    if "metadata" in output:
        lines.append(
            "metadata: "
            + json.dumps(output["metadata"], ensure_ascii=False, separators=(",", ":"))
        )
    lines.append("---")
    return ("\n".join(lines) + "\n").encode("utf-8") + raw[match.end() :]
