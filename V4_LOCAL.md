# V4 local discovery and review

V4 is opt-in and uses no paid APIs or OpenAI key. V3, the cutter, OAuth,
uploads, scheduling and production Sheets are unchanged. **Do not replace V3 yet.**
See `V4_VALIDATION.md` for measured results and remaining rollout criteria.

From `discovery/`, with FFmpeg/FFprobe on PATH and the existing virtualenv:

```bash
.venv/bin/python v4_local.py --video v4_test/primary_360.mp4 --vtt v4_test/test_video.en-orig.vtt --source-url 'https://www.youtube.com/watch?v=eDK9ko0HbBc' --out v4_test/run/candidates.json --previews v4_test/run/previews --evidence-cache v4_test/primary-evidence.json
```

Use a new preview directory on subsequent runs: existing media is never overwritten.
Install Python dependencies with `pip install -r requirements-v4.txt` if setting up
a new environment. FFmpeg is a separate executable. OpenCV is optional: missing,
failed or incomplete OpenCV decoding falls back to FFmpeg grayscale 160x90 sampling
at 1fps. Source codecs must be decodable by the installed FFmpeg. Large AV1 sources
can remain slow because decoding compressed interframes still requires work;
prefer a low-resolution copy of the same source, verifying FFprobe duration.
The supplied 4K source and downloaded 360p version both measure 901.474 seconds.

`--duration` is only needed for transcript-only operation; local media duration
always comes from FFprobe. Missing captions produce zero clips unless optional
`--whisper-model small --transcript-cache path.json` is requested. This uses
`faster-whisper` with `local_files_only=True`; a model must already be cached
or available at a local path. No model download or cloud inference occurs.
Long, sparse and low-confidence ASR segments are discarded.

JSON schema version 1 contains zero to five `candidates`, source identity, media
duration, per-stage status/errors/counts, processing time, zero API cost, and
`rejected` windows with reasons. Candidate objects include rank, hook, start/end,
duration, captions, category, component/overall scores, confidence, coverage,
selection reason, attributed transcript payoff, and review flags. `rank()` remains
a list-returning adapter; `select()` retains the single-hook interface.

Complete sentence groups of 12–30s are enumerated before content scoring. The
rules require a reaction with a resolved event or a specific linked educational
payoff, reject ads/speculation/dependent openings, and remove overlap and near
identical text. Fixed score weights total 100: hook 22, story 18, payoff 24,
relevance 10, audio onset 4, motion 4, boundaries 8, retention 6, originality 4.
Minimum score is 65, hook 55/100, payoff 70/100. Extra sentences earn no reward.
Unknown originality receives a documented neutral prior. Diversity is a selection
gate, not a claim of corpus-wide originality. Scores are heuristics, not calibrated
probabilities or predicted view counts.

Audio RMS onsets, motion differences and 1fps scene-cut proposals are independently
observable. Scene proposals are exposed in each candidate's evidence; they do not
move cuts through spoken sentences. Transcript windows provide sentence-level
boundaries, including word-share estimates from the existing VTT parser. Scene
precision is approximately +/-1 second, and true cuts may be missed. Audio/motion
peaks do not establish screams, explosions or interesting gameplay. Coverage means
successful measurements, not semantic accuracy. Missing evidence never increases
the score, and lowers confidence. All generated candidates require content review.

For a reviewed candidate, document `reviewed_by`, set `semantic_verified=true`
and `review_required=false` in a separate reviewed report after checking footage,
audio, title agreement and cuts. Full evidence coverage is also required for
handoff. Those fields are attestations and must not be toggled automatically by a
production job. The delivered local render review is engineering inspection of
sampled frames and independent ASR, not a claim of independent fact-checking.

```bash
.venv/bin/python v4_handoff.py reviewed-candidates.json --video source.mp4 --cutter ../clipper/clip.py --caption-model small --render v4_test/staging/render.mp4 --thumbnail thumbnail.jpg --short-title 'My GTA Clip'
```

The adapter calls the existing cutter's cut/ASS/render functions, retains exact
selected times, and never calls uploading or backlog mutation. Optional cached
Whisper adds word-timed karaoke through the existing caption renderer. Without
that flag it renders the hook and retains transcript text in JSON. Rendering is
validated before an atomic final-file creation; existing output is never replaced.
The reviewed report must include a complete `payoff_review`. The CLI requires a
portrait thumbnail and short title, then creates a dated delivery package after
the intermediate render passes its ending checks.

**Delivery packages (required):** every finished clip is delivered in
`packages/short-video-title_YYYY-MM-DD/`. The date is the current Europe/London
date; `--date` can specify an explicit client date. Another save with the same
title/date creates `_v2`, `_v3`, etc. Earlier packages are never overwritten.

Every package contains a finished `video.mp4`, a **1080x1920 (9:16) thumbnail**,
`UPLOAD-DETAILS.txt` with title/description/tags/keywords and prepared settings,
portable `metadata.json`, `README.txt`, `payoff-review.json`, `ending-audit.json`,
and a `manifest.json` with file hashes. Caption ASS and thumbnail prompt files are
included when available. A missing/landscape thumbnail, missing payoff review,
failed ending audit, or mismatched video prevents a completed package. Generate
and review the thumbnail as part of every clip task, not as a later optional job.

To package an already-rendered clip:

```bash
.venv/bin/python v4_package.py --video staging/video.mp4 --thumbnail staging/thumbnail.jpg --metadata staging/metadata.json --short-title 'My GTA Clip'
```

Optional flags: `--root`, `--date YYYY-MM-DD`, `--captions`, `--thumbnail-prompt`.
`build_package()` and `validate_package()` provide the same contract to editorial
scripts. Working files can remain in `v4_test/`; the readable dated package is
the final deliverable. Packaging does not upload or change publication settings.

**Ending/payoff gate (2026-11-17):** trailing connectors and dependent phrases
are rejected even if automatic captions add a full stop (for example, `but.`).
Unanswered final questions, promised-later answers, ellipses and generic hype
alone do not count as a payoff. Window padding stops before the next speech cue,
including an incomplete following cue that never became a full sentence.

The reviewed speech renderer now runs `v4_quality.audit_export()` on the actual
finished MP4 before creating the final output. It uses cached local Whisper,
checks the real final sentence/word, and holds exports whose last word touches
the cut. Missing audit evidence fails closed. This final speech audit needs a
locally available Whisper model even when karaoke captions are disabled. Estimated
ASR timing does not replace checking the audible ending and the actual resolution.
If ASR omits punctuation, the export can pass only when its actual final words
match the reviewed complete payoff's lexical suffix and have sufficient clearance
before the cut. An extra sentence after that payoff, a different ending, or a
dangling connector still holds the export. Punctuation is never added merely to
make a failed ending pass.

Longer speech over music can be wrongly discarded as "no speech" for an entire
ASR segment. If recognition stops over eight seconds before the end of a clip
longer than 20 seconds, the ending audit independently decodes and transcribes
the final 16 seconds. This focused pass disables voice-activity rejection, uses
no target-text prompt, and requires confident terminal words, a matching reviewed
payoff and clean timing clearance. It can reject an earlier apparent pass if the
actual tail is incomplete. The report records the audited window and the initial
result; it does not claim that this focused pass verifies the entire transcript.

All future editorial jobs must also follow `AGENTS.md`: record an explicit
`payoff_review` (setup, resolution, why it resolves the opening, reviewer), check
every spoken edit boundary, and save a passing final `ending_audit` before upload.
Non-speech clips need a documented visual payoff review instead of an invented
speech-audit pass. Extend/reselect a complete thought; never hard-truncate to a
duration target, hide a word only in captions, or use silence to mask a fragment.
Existing published clips are not modified by these checks.

The Sheet planner is **dry-run only**, requires no credentials and performs no
network requests:

```bash
.venv/bin/python v4_sheets.py --snapshot v4_test/sheet-snapshot.json --reports v4_test/benchmark-final.json v4_test/benchmark-second-whisper.json --dry-run --out v4_test/sheets-dry-run.json
```

Snapshot shape: `{spreadsheet_id, sheet_name, headers, rows:[{row_number,values}],
candidate_ids:[]}`. Reports are matched by exact source URL and linked by backlog
`id`. The planner resolves named headers and supports the live Date Added column:
as inspected on 2026-11-16, `url` is H and `hook/start/end/captions` are I–L
(previously G and H–K). Multiple clips become proposed child rows in
`v4_candidates`; only one top reviewed clip may fill empty legacy cells. Manual
values and completed statuses are preserved. Child IDs deduplicate repeated runs.
The planner does not create the table or apply writes. A future writer must
re-read headers, IDs, status, values, formulas, validation and existing child IDs
immediately before writing, using RAW values to avoid formula interpretation.

```bash
.venv/bin/python -m unittest v4_package_tests v4_quality_tests v4_tests v4_integration_tests v3_tests discover_tests p0_tests
```
