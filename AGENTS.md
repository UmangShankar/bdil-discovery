# Clip quality requirements

The user requires stronger payoffs and clean, complete endings for all future
clips. Apply these requirements to automatic candidates AND editorial jobs in
`v4_test/`, including custom scripts that call the cutter directly.

- Choose a specific resolution, reveal, punchline, comparison result or useful
  insight that answers the clip's opening. Hype or an unanswered question alone
  is not a payoff. Record `payoff_review` with `setup`, `resolution`,
  `why_it_resolves`, and `reviewed_by` in each new clip's metadata.
- Finish the complete spoken thought. Never cut on "but", "and", "because",
  "so", another dangling connector, an unfinished phrase, or a partial word.
  Punctuation in automatic captions does not establish a safe cut.
- Prefer extending to a clean sentence/word boundary that retains the payoff.
  If the configured duration cannot accommodate it, choose a different complete
  ending/window. Never truncate a sentence merely to hit a duration target.
- Do not add source padding into the next sentence. Check every spoken edit
  boundary in a multi-excerpt cut, retaining the speaker's meaning and stance.
- Before uploading any speech clip, run `v4_quality.audit_export()` on the FINAL
  rendered MP4 and save its result as `ending_audit`. Require `passed=true`.
  This catches next-sentence words that may have leaked beyond planned captions.
  If it fails, fix/re-cut and re-audit; do not just remove a bad word from captions
  or add silent padding to hide an incomplete thought.
- Review the final seconds for the actual resolution and an audible clean cut.
  ASR word timing is estimated and is not a claim of frame/sample accuracy.
- For a genuinely non-speech clip, document a visual `payoff_review` from the
  actual sequence and inspect the final frames. Mark speech auditing not
  applicable with that reason; never invent a spoken transcript or an ASR pass.
- Do not alter existing published videos unless the user explicitly requests it.

Keep OAuth files and production rendering/upload configuration unchanged. Use
only authorized credentials; never print or commit credential contents. Preserve
unrelated work, including pre-existing working-tree changes.
