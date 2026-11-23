# Review changes to a local skill

Use drafts to keep a proposed improvement out of the active skill tree until you review it. This is a local, manual workflow; it does not install a learner, schedule a job, contact Skillstore, or grant the harness new permissions.

1. Copy an existing canonical `skills/<name>/SKILL.md` into a private working file outside the tracked Home. Change only the procedure, not its frontmatter. Start with one correction you expect to use again. Keep user facts in separately authorized memory and temporary task state in a handoff.
2. Save the draft with a brief reason that explains what went wrong and what the revised procedure should do differently. Do not include credentials, transcripts, or unrelated personal details.
3. Inspect the exact diff. Test the new instruction against the case that prompted it and a case that should still work. If the active skill changed after the draft was created, make a new draft against the current version rather than forcing an overwrite.
4. When satisfied, apply the exact draft and check the changed skill. Start a fresh harness session before testing native discovery. Review other working-tree changes before committing.

```sh
soulsteads skill propose helper starter /private/candidate.md \
  --reason 'The handoff omitted verification of the result.'
soulsteads skill show helper DRAFT_ID
soulsteads skill apply helper DRAFT_ID
# Optional: restore just this skill if it still contains the applied bytes.
soulsteads skill undo helper DRAFT_ID
```

Drafts are private and Git-ignored. Keep the ID returned by `propose`, which binds the reviewed bytes, target, and reason. `show` intentionally prints private review content; do not forward it without checking it. `apply` is the approval action for that exact draft. `undo` refuses to replace later edits. Neither command stages or commits anything. Pause the harness and other editors while applying or undoing a draft. This is not a filesystem permission boundary: a harness with general write tools can still edit files outside this workflow unless its own permissions prevent it.

For a Git record, commit the reviewed change separately. If you later undo it, review and commit the restoration as another change. If the draft is no longer available, Git history still contains any committed version. On a clean Home, `soulsteads revert helper PRIOR_REVISION` restores the **whole tracked snapshot** as a new commit, not just the skill. See [Agent Skillstore](https://github.com/soulsteads/soulsteads-agent-skillstore) for publishing reviewed skill versions across Homes.
