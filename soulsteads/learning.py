"""Portable learning policy, expressed as instructions rather than permissions."""

import re

MODES = ("off", "propose", "scoped-apply")
POLICY_FILE = "LEARNING.md"


def validate(value):
    """None preserves legacy guidance; explicit policies have a strict shape."""
    if value is None:
        return
    if (
        not isinstance(value, dict)
        or set(value) != {"mode", "skills"}
        or value["mode"] not in MODES
        or not isinstance(value["skills"], list)
        or any(
            not isinstance(name, str)
            or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name)
            for name in value["skills"]
        )
        or len(set(value["skills"])) != len(value["skills"])
        or bool(value["skills"]) != (value["mode"] == "scoped-apply")
    ):
        raise ValueError(
            "invalid learning policy: choose off, propose, or scoped-apply; "
            "scoped-apply requires unique local skill names and other modes have no targets"
        )


def render(value):
    """Compile a user-selected mode without granting native tool permissions."""
    validate(value)
    if value is None:
        return None
    text = (
        "# Learning policy\n\n"
        "Generated from soulsteads.json; change it with soulsteads config <home> "
        "--learning, then refresh before a new session.\n"
        "This policy selects the learning mode in preference to generic starter "
        "or imported learning guidance. It does not override native permissions "
        "or explicit user instructions.\n\n"
        f"Mode: {value['mode']}\n\n"
    )
    if value["mode"] == "off":
        text += (
            "Do not initiate proposals or edits to durable guidance as a side effect "
            "of ordinary work. An explicit user request to edit guidance remains "
            "an ordinary authorized task.\n"
        )
    else:
        text += (
            "After a useful correction or nontrivial task, consider one small, "
            "evidence-backed improvement to a reusable procedure. Read the relevant "
            "skill and, if available, skills/skill-maintenance/SKILL.md first.\n"
        )
        if value["mode"] == "propose":
            text += (
                "Show the target, reason and smallest proposed diff. Do not persist "
                "a learning change without explicit user authorization.\n"
            )
        else:
            text += (
                "The user has preapproved small procedural corrections only in "
                "these existing Home-relative files:\n\n"
                + "".join(f"- `skills/{name}/SKILL.md`\n" for name in value["skills"])
                + "\nResolve targets against the agent Home, never an unrelated project. "
                "Preserve skill metadata. Do not create, delete or rename skills, "
                "edit scripts or supporting files, or broaden this scope. "
                "For other targets, propose a diff and wait for explicit authority. "
                "Validate each applied correction and report its diff and evidence.\n"
            )
    return text + (
        "\nFacts and preferences belong in separately authorized curated memory or "
        "the configured memory service; temporary task state belongs in a handoff. "
        "This skill-learning policy does not authorize memory writes or automatic "
        "Hindsight retention. Never create a competing local copy of service-owned memory.\n"
        "Learning does not authorize changes to SOUL.md, USER.md, AGENTS.md, "
        "this policy, runtime configuration, permissions, credentials, plugins or schedules. "
        "It does not authorize installation, commits, publication or external actions. "
        "Native tools and approvals remain authoritative; these are model-followed "
        "instructions, not a sandbox or a background learner.\n"
    )
