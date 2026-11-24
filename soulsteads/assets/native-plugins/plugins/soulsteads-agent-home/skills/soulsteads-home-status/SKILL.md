---
name: soulsteads-home-status
description: Check an explicitly selected Soulsteads Agent Home without changing it.
disable-model-invocation: true
---

# Soulsteads Home status

Run this procedure only when the user asks to check a Soulsteads Agent Home.

1. Require one explicitly selected Home name or absolute Home path. If none was
   given, ask. Do not infer it from this project's working directory, discover
   other Homes, or substitute a different Home if verification fails.
2. Refuse input starting with `-`. Run `soulsteads verify --no-credential-check "$home"`
   to skip the Home-selected credential presence check.
   Pass the selection as a single literal argument, never as shell code.
   Follow the harness's normal permission prompts.
   If the CLI is missing or execution is denied, report that rather than
   installing it or replacing the check with direct filesystem reads.
3. Summarize the top-level verification status and any failed checks or
   suggested next steps. Do not paste raw diagnostics, private paths, or
   configuration values. An offline check does not prove that the current
   session loaded this Home or that a model is reachable.

Do not add other options, read identity or memory files directly, change
settings, start a harness, or repair anything as part of this check.
