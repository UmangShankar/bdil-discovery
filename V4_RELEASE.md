# V4 accepted release — 24 November 2026

V4 is finalized for the reviewed workflow and is the default from now on.
Umang confirmed that he reviewed and used it for a week, accepted its current
capabilities, and asked to close the rollout. This decision supersedes the
16 November opt-in/no-go assessment preserved in `V4_VALIDATION.md`.

## Operating workflow

1. Prepare sources through `v4.py prepare URL`, `--file VIDEO --vtt CAPTIONS`,
   or `--backlog CSV`. This invokes V4 local discovery and saves review jobs.
   Optional `--whisper-model small` uses an already-cached local model.
2. Review source footage and choose complete hook/story/payoff moments.
   Automatic candidates are proposals. A zero-candidate result may still be
   handled through V4 editorial selection, including non-speech visual clips.
3. Render with the existing cutter helpers and V4 quality checks. The `render`
   command forwards to the reviewed-candidate handoff; custom editorial cuts
   follow the same `AGENTS.md` requirements, including every spoken boundary.
4. Generate/review a 1080x1920 portrait thumbnail. Every future title and visible
   thumbnail text must include **GTA VI**. New packages normalize upload titles
   to include it; thumbnail lettering remains an explicit visual review.
5. Package through `v4.py package ...`, then `v4.py verify PACKAGE_FOLDER`.
   Every new package records `workflow_version: v4`, uses a readable title/date
   folder and keeps captions, metadata, payoff/ending evidence and file hashes.
6. Upload only when requested, using the tested uploader and requested privacy.
   Verify the resulting video metadata, visibility and applied thumbnail.

Preparation never uploads or marks a source clipped/uploaded. Backlog preparation
is read-only and reuses existing jobs when the source and editorial request are
unchanged. The daily launcher pulls the selected backlog and prepares V4 jobs;
it does not call the old V3 auto-cut/upload path or push invented completion
statuses. Finishing and uploading a reviewed package remain separate actions.

## Entry points

```bash
cd ~/BadDayInLeonida/discovery
.venv/bin/python install_v4.py --target ../clipper --daily ../run_daily.sh
.venv/bin/python v4.py prepare 'YOUTUBE_URL'
.venv/bin/python v4.py prepare --file VIDEO.mp4 --vtt CAPTIONS.vtt
.venv/bin/python v4.py discover --help
.venv/bin/python v4.py render --help
.venv/bin/python v4.py package --help
.venv/bin/python v4.py verify packages/SHORT_TITLE_YYYY-MM-DD
```

The installed `clipper/clip.py` command delegates to V4 source preparation.
Its cut/ASS/render helper functions remain available to V4. Installation backs
up changed local files as `.pre-v4.bak` and does not touch OAuth credentials.
V2/V3 installers and documentation are historical; no implicit V3 fallback exists.

## Closeout scope

The existing final ending/payoff checks, actual export review, portrait cover,
date/revision naming and upload verification remain release requirements.
Existing packages and published videos are not retroactively changed.

Known limits are accepted and are no longer rollout blockers: heuristic ranking,
coarse scene sampling, ASR ambiguity/holds, slower high-resolution scans, and
the separate multi-candidate Sheets writer remaining a dry-run planner. This
release does not claim fully unattended semantic editing or automatic publishing.
Improvements are separate future work when requested; V4 rollout is closed.

Validation on 2026-11-24: **106 tests passed**, covering V4/legacy compatibility,
actual-media fallbacks, ending/payoff checks, packaging, new title branding,
default routing, installer idempotence and read-only backlog preparation.
CI repeats the suite without source downloads, model downloads, uploads or
credentials. The local activation is also checked through the installed cutter
entry point using existing media. See the Git history/PR for the final result.
