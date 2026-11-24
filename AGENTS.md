# Default workflow: accepted V4

V4 is accepted and is the default for all future clipping work as of
2026-11-24. The user reviewed and used it for a week and explicitly closed
the rollout. Use `v4.py` / the V4 modules for new jobs; V3 is historical and
must not be selected or invoked as an implicit fallback. The existing cutter's
cut/ASS/render helpers are still the V4 rendering backend.

Use `v4.py prepare URL` (or `--file VIDEO --vtt CAPTIONS`) to prepare a source.
Review its footage and choose complete moments; zero automatic candidates may
still require V4 editorial selection, including visual/non-speech sequences.
Apply the quality and delivery requirements below to every editorial job.
Do not reopen accepted rollout limitations as blockers or ask the user to
re-approve V4. New improvements are separate follow-up work when requested.
Only upload/publish when requested; preserve the user's chosen visibility.
See `V4_RELEASE.md` and `active_pipeline.json` for the accepted operating scope.

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

## Delivery package standard

- Every future clip's upload title must contain the exact text `GTA VI`.
  Every future thumbnail must visibly include `GTA VI`; include it in the image
  prompt and check the generated cover before packaging. This applies to
  automatic candidates and custom editorial packages. Do not revise existing
  packages or uploads unless the user requests it.
- Every finished clip gets its own delivery folder in `discovery/packages/`,
  named `short-video-title_YYYY-MM-DD`. Use the current user-facing date in
  Europe/London, not the video's source publication date or a YouTube ID.
- Every new save/revision creates a new folder. On a same-title/same-date
  collision use `_v2`, `_v3`, etc. Never overwrite or silently reuse a package.
- A 9:16 thumbnail is mandatory for EVERY finished package. Generate/review it
  as part of the clip task; save the upload-ready cover at 1080x1920. A landscape
  image alone does not satisfy this requirement. If the cover is not ready, the
  delivery package is incomplete; do not leave it as an optional follow-up.
- Final package contents: `video.mp4`, `thumbnail.jpg` (or PNG), `metadata.json`,
  `UPLOAD-DETAILS.txt`, `README.txt`, `payoff-review.json`, `ending-audit.json`,
  and `manifest.json`. Include caption ASS and image-generation prompt when
  available. Metadata and the manifest use package-relative asset paths.
- Use `v4_package.build_package()` or its CLI so missing thumbnails, wrong
  dimensions, incomplete payoff reviews and failed ending audits block delivery.
  Custom editorial scripts must also finish with this packaging step.
- Give the user the readable dated package folder and links to its video,
  portrait thumbnail and upload details. Working files may stay in `v4_test/`;
  do not present an ID-named working folder as the final delivery package.

Keep OAuth files and production rendering/upload configuration unchanged. Use
only authorized credentials; never print or commit credential contents. Preserve
unrelated work, including pre-existing working-tree changes.
