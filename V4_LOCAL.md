# V4 local-first hook ranking (experimental)

This is **opt-in** and does not modify V3, the Mac cutter, Google Sheets,
uploading or public publishing. Zero OpenAI API calls.

Uses existing V3 caption parsing and fixed transcript windows. If a local video
is provided, FFmpeg adds per-window audio peaks; optional `opencv-python` adds
motion intensity. These features help detect action, but are **not** semantic
understanding or frame-accurate scene/payoff verification.

Run from the discovery repository:

```bash
python -m unittest v4_tests.py
python v4_local.py --vtt /path/to/source.en-orig.vtt --duration 674 --limit 5 --out candidates.json
python v4_local.py --vtt /path/to/source.en-orig.vtt --duration 674 --video /path/to/source.mp4 --out candidates.json
```

Requires `ffmpeg` on PATH for audio; install `opencv-python` optionally for
video frame sampling. With no local video it still runs using the Python standard
library, the existing `smart_hooks.py` and transcript evidence. No video is
downloaded automatically. Outputs JSON with top five start/end/hook/captions,
scoring evidence, and verification coverage. Generated hooks are excerpts and
should be reviewed before publishing; quality is not guaranteed.

**Comparison / rollout gate:** run V3 and V4 against the *same* VTT/video,
review whether each proposed clip actually contains a visual payoff and
whether cuts are clean. Do not enable Sheet writes or replace the live
Mac pipeline until that test passes. Recording all five in Sheet columns H–K
needs an explicit multi-row/multi-clip data contract; current single-row
H–K cannot safely represent five clips in four cells.
