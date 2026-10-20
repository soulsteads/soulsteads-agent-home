# Development guide

This is the public Soulsteads CLI, not a personal agent home.
Never copy private USER.md, SOUL.md, MEMORY.md, credentials, runtime sessions, or
personal skill content into this repository. Write generic examples from scratch.

- Python 3.11+, standard library for ordinary CLI operations; keep the CLI small and portable.
- Hermes imports use the optional `hermes` extra (PyYAML). Import it lazily; ordinary
  commands must keep working without it. Never implement a partial YAML parser.
- Run `PYTHONPYCACHEPREFIX=/tmp/soulsteads-pycache python3 -m unittest discover -s tests -v`.
- Use disposable temporary homes for all lifecycle tests; never test on a real agent.
- Git operations must stay within the selected standalone home and preserve history.
- Restore must create a new commit, never reset history or clean untracked files.
- Do not weaken runtime permissions or write global runtime configuration.
- Verify upstream configuration fields before changing runtime adapters; cite them in docs/runtimes.md.
- Skill installation is local-only, does not execute anything, and rejects unsafe trees.
