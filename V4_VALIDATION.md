# V4 validation — 2026-11-16

**NO-GO for replacing V3. GO for opt-in local discovery and reviewed renders.**

Implemented: automatic FFmpeg fallback, sparse grayscale motion/cut proposals,
independent observable audio/video/scene/transcript stages, audio-onset rather than
volume scoring, optional cached offline Whisper, sentence-based candidate
enumeration, linked explanatory payoffs, speculation/history-metaphor/ad filters,
meaningful quality gates, fixed score normalization, rejection diagnostics,
non-overlap/text diversity, stable JSON, validated previews, reviewed cutter
handoff and a credential-free multi-candidate Sheets dry-run planner.

The starting feature branch was `feature/v4-local-first-hook-ranking` at
`93c52d4`; its 36 tests passed. Actual-media tests exposed missing fallback and
quality gates that the original suite did not cover. Existing untracked `.venv/`,
`candidates.json`, and `v4_test/` assets were retained. Protected directories and
production code/configuration were not modified. No credential contents were read.

Automated validation command:

```
.venv/bin/python -m unittest v4_tests v4_integration_tests v3_tests discover_tests p0_tests
```

61 tests pass, including actual H.264, VP9 and AV1 decode, forced OpenCV failure,
corrupt/missing media, missing subtitles, silence/steady tone, transcript semantic
regressions, incomplete payoff, overlap/duplicate removal, zero candidates,
NaN/infinite/out-of-duration timestamps, JSON, source-duration precedence,
review gates, child-table multiplicity/idempotency/manual preservation, and
shifted Sheet headers. Local log: `v4_test/test-results.txt`.

| Real source | Duration | Result | Evidence | Uncached wall time | API cost |
| --- | ---: | --- | --- | ---: | ---: |
| eDK9ko0HbBc, provided 4K AV1 / same-source 360p AV1 | 901.474s | 1 educational review candidate; 1,194 windows rejected | 1,802 audio measurements; 901 sampled frames; 138 coarse scene proposals; 619 parsed VTT cues | Initial complete 360p pass with previews: 16.593s | $0 |
| iQy-GH_JXJ8, downloaded 360p AV1 | 465.854s | 0 candidates | 931 audio measurements; 466 sampled frames; 51 coarse scene proposals; no YouTube subtitles | Media-only initial pass: 13.401s; initial local Whisper + media pass: 24.875s | $0 |

Machine-readable current measurements: `v4_benchmarks.json`. Full local candidate
and rejection reports are in `v4_test/benchmark-final.json` and
`v4_test/benchmark-second-whisper.json`. Later cached runs are faster and are not
substituted for uncached performance claims. The second source's local Whisper
initially returned three segments; the strengthened ASR filter retained one short
line and dropped two implausibly sparse long segments. There is no complete
12–30s story/payoff. Sampled footage resembles a gameplay montage; authenticity as
released GTA 6 gameplay is unverified. No clip or title is inferred from activity.

The original V4 on the primary file selected **658.16–678.00 (54.34)**, including
“the pandemic hit,” and **386.09–406.28 (42.44)**, historical Euphoria commentary
with an unrelated ending. Both got maximum audio activity and no motion evidence.
The revised rules reject those exact excerpts as clips. Valuable historical
mechanics insights remain allowed; history itself is not a rejection criterion.

Best inspected moment: **02:11.760–02:24.430 (12.670s)**, **79.78/100**,
category `mechanics_comparison`. Opening: “In older GTA, people mostly came in a
few sizes because bodies shared the same animations.” Payoff: the narrator
attributes animation/body adaptation and varied heights to Nelson. The title is
an extracted opening excerpt. Independent cached Whisper recovered both complete
sentences from the preview; sampled frames show the GTA 5/6 comparison and
characters of different heights. This verifies the content of the excerpt, not
the underlying claim about Rockstar's implementation. Confidence 0.75, evidence
coverage 1.0; the generated report still requires review.

Local artifacts:

- `v4_test/previews-final/candidate-01.mp4`: 360p-source review preview.
- `v4_test/previews-original/candidate-01.mp4`: original 4K AV1-source preview; FFprobe 12.683333s.
- `v4_test/contact-primary.jpg`, `v4_test/contact-second.jpg`: inspected contact sheets.
- `v4_test/preview-asr-check.json`: independent audio check.
- `v4_test/reviewed-for-local-render.json`: documented engineering inspection, local-render scope only.
- `v4_test/cutter-integration.mp4`: original-source existing-cutter render, hook only.
- `v4_test/cutter-captions.mp4`: existing-cutter render with local word-timed captions, H.264/AAC, 1080x1920, 12.700s.
- `v4_test/cutter-caption-check.jpg`: inspected captioned render frame.

The full original 4K scan was stopped after excessive processing time; the
same-duration 360p source completed full timeline analysis. The original source
was independently decoded over the actual selected section, previewed, and passed
through the existing cutter. Full original-resolution scan performance is not a
passed acceptance criterion. Downscaling output does not eliminate AV1 interframe
decoding cost; low-resolution sources are the practical input.

The connected canonical Sheet was read through the authorized connector. During
this session another process/user inserted **Date Added**, changed the grid from
26 to 27 columns and reordered rows. Current names put status at B, URL at H and
clip fields at I–L. The planner resolves header names, hashes the schema for write
preconditions and uses source IDs rather than treating row numbers as permanent.
The latest bounded live snapshot's one `to-cut` record matches the second benchmark
with zero eligible clips: dry run proposes **0 child rows, 0 legacy patches, 1 held
source**. The primary benchmark is a completed record and is untouched. Unverified
candidates and manual edits are held by regression tests. No Sheet writes were
made; no candidate table was created. Live writing remains deliberately
unimplemented until verified clip quality and concurrency-safe writing are ready.

Remaining rollout criteria:

- Broader real gameplay/funny/discovery benchmark with positive, inspected
  outcomes. The two-video benchmark proves conservative rejection and one
  educational selection, not reliable autonomous retention ranking.
- Better semantic story/topic/claim assessment. Regex heuristics still miss
  valid moments and can accept weak narration; audio/motion do not classify
  explosions/reactions or distinguish music from speech.
- Word/frame alignment of source boundaries and higher-resolution scene-boundary
  refinement. The inspected clip is complete by ASR and source cues, but timing
  decimals are source estimates, not a frame-accuracy guarantee.
- Calibrated ranking/confidence and genuine originality measurement. Current
  scores are explainable heuristics and originality uses a neutral prior.
- A tested live Sheet writer with fresh precondition checks; current deliverable
  is the safe offline planner and verified live schema inspection.
- Full 4K scan performance remains unresolved; successful full-timeline analysis
  used the low-resolution version of the same source.

No merge, public/private upload, automatic publishing, credential changes, or V3
replacement occurred. Work remains on PR #1:
https://github.com/UmangShankar/bdil-discovery/pull/1
