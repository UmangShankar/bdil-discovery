# Bad Day In Leonida: clip discovery

## Default: accepted V4

V4 is finalized for our reviewed clipping workflow as of **24 November 2026**,
following the user's week of review and use. All future clip jobs use V4.
See [V4_RELEASE.md](V4_RELEASE.md) for the closeout and [V4_LOCAL.md](V4_LOCAL.md)
for the commands. The earlier V3 rollout instructions below are historical.

```bash
cd ~/BadDayInLeonida/discovery
.venv/bin/python install_v4.py --target ../clipper --daily ../run_daily.sh
.venv/bin/python v4.py prepare 'YOUTUBE_URL'
# Or: .venv/bin/python v4.py prepare --file VIDEO.mp4 --vtt CAPTIONS.vtt
```

Review the footage/candidates, render with the V4 quality checks, generate a
portrait cover and package with `v4.py package`. Both the upload title and visible
thumbnail text must include **GTA VI**. Verify with `v4.py verify PACKAGE_FOLDER`.
Upload only when requested; retain the requested visibility and thumbnail checks.

The installed daily launcher pulls the selected backlog and prepares V4 review
jobs, reusing unchanged prepared sources. It does not use the old V3 auto-upload
path, overwrite editorial selections, or mark unrendered jobs clipped/uploaded.

## Source discovery

Runs 4x a day on GitHub Actions. Finds GTA 6 moments on YouTube, Twitch and Reddit,
scores them (see config.yaml), and keeps a rolling backlog in `backlog.csv`, the
Google Sheet ("backlog" and "digest" tabs) and `digest.md`.

Morning: in the Sheet, set `status` to `to-cut` and write a `hook` (optional `start`/`end`
in seconds or mm:ss). Your edits are never overwritten. Statuses: ready, to-cut,
in-progress, clipped, uploaded, skipped, expired.

Settings > Secrets and variables > Actions:
- Secrets: YOUTUBE_API_KEY, TWITCH_CLIENT_ID, TWITCH_CLIENT_SECRET
- Variables: GOOGLE_SHEET_ID, WIF_PROVIDER, SERVICE_ACCOUNT
Google sign-in is keyless (Workload Identity Federation), so no service-account key file is needed.

## Daily V4 source preparation on the Mac
```
~/BadDayInLeonida/run_daily.sh
```
Jobs are saved in `discovery/v4_test/jobs/` for V4 review and rendering. The
source-discovery GitHub Action still maintains the source backlog; it does not
perform semantic clipping or publishing.

## Historical V2/V3 rollout notes

The remaining sections document earlier releases. Do not run their installers
or daily auto-upload commands for normal work; the accepted default is V4.

## V2 quality / rights policy

Discovery now pre-filters for GTA VI moment-oriented English-language titles
and rejects explainers, trailers, mods and unrelated content. This is **only
metadata screening**, not AI viewing or proof the footage is a good Short.

P0 update: rights notes are optional for private drafts. An English hook is still
required for backlog processing. Rights and source usage must be reviewed
before any public release; credit alone does not establish usage rights.

## Upgrade the local cutter to v2

From `~/BadDayInLeonida/discovery` after `git pull origin main`:

```bash
python upgrade_clipper.py --target ../clipper
python -m py_compile ../clipper/clip.py
```

The upgrade modifies only `../clipper/clip.py` and `../clipper/config.yaml`;
the original versions are backed up locally as `.pre-v2.bak`. It never
reads or copies YouTube `token.json`, OAuth `client_secret.json`, or videos.
Do not commit your local clipper directory or secrets to GitHub.

Changes: auto-pick up to one strong event window (22 seconds, 2.5 seconds
lead-in), skip sources without an unusually distinct peak, and require a human-supplied `hook` for backlog processing. Run the P0
private-draft patch below to make the old rights gate optional.
Direct one-off renders still work, but direct upload is blocked. Backlog
`--upload` continues to upload **private**, not public. The detection
remains heuristic, not video understanding or guaranteed high retention.

First smoke test with a local sample without uploading:

```bash
cd ~/BadDayInLeonida/clipper
source .venv/bin/activate  # if your clipper environment has one
python clip.py --file /absolute/path/to/sample.mp4 --start 10 --end 25 --hook "Example hook"
```

Do not run the upgrade twice: it is deliberately fail-closed if the original
code has already been replaced.


## P0: optional rights notes for PRIVATE draft production

The P0 backlog handoff now accepts any `status=to-cut` source with a valid
`url` and an editorial `hook` (excluding spoiler-flagged content). Rights
fields `rights`, `rights_evidence`, `rights_approved_by` and
`rights_approved_at` can be completed if available, **but are optional for
PRIVATE drafts**. Rights `check` does not prevent private clipping. This
does not grant permission to publish copyrighted material publicly.
Final public release remains your manual decision after checking rights.

The private upload pipeline returns `status=uploaded`, `youtube` URL
and `clip_file` to the Sheet. Discovery preserves these fields across
sweeps. The uploader continues using `privacyStatus=private`.

### One-time P0 rollout on your Mac

```bash
cd ~/BadDayInLeonida/discovery
git pull origin main
python p0_enable_private_drafts.py --target ../clipper
python -m py_compile ../clipper/clip.py
python -m unittest discover_tests.py p0_tests.py
python p0_smoke.py --clipper ../clipper
```

Next run GitHub Actions > **Clip discovery** > **Run workflow** to add the new
tracking columns to the live Sheet. The offline smoke test must pass before
you rely on batch processing; it does not upload a real video.

### Daily private draft run (manual until P1)

```bash
cd ~/BadDayInLeonida/clipper
git -C ~/BadDayInLeonida/discovery pull -q
python ~/BadDayInLeonida/discovery/pull_backlog.py --client-secret client_secret.json --out backlog.csv
python clip.py --backlog backlog.csv --upload
python ~/BadDayInLeonida/discovery/pull_backlog.py --push --client-secret client_secret.json --out backlog.csv
```

No automatic public publishing. This batch still needs a real integration
test using one selected Sheet row to validate Mac OAuth, clip rendering and
the private YouTube URL/status returning to the Sheet. Manual uploads
outside backlog do not get reconciled automatically.

## V3: install AI-generated hooks without any ZIP download

```bash
cd ~/BadDayInLeonida/discovery
git pull origin main
python install_v3.py --target ../clipper
python -m py_compile ../clipper/clip.py ../clipper/smart_hooks.py
python -m unittest discover_tests.py p0_tests.py v3_tests.py
```

Automatic moment selection requires an OpenAI API key supplied as
`OPENAI_API_KEY`. This key must not be committed to Git. For a private
editorial test with an existing transcript:

```bash
cd ~/BadDayInLeonida/clipper
python smart_hooks.py --vtt hazard_npcs.en-orig.vtt --duration 674 --title 'GTA 6 NPCs'
```

A `to-cut` Sheet row may now have an empty `hook`, `start`, and
`end`. V3 attempts to find a complete English-language 12-30-second
moment via YouTube captions and AI. If the source has no usable English
captions, no API key, or no validated payoff, it will not invent a clip.
Manual `--start`/`--end` remains available. The AI has not analysed
video frames, and captions alone cannot verify scene quality.
Rights annotations are optional for *private drafts*; public release
still requires your separate rights and quality review.
