# Bad Day In Leonida: clip discovery

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

## Daily run on the Mac
```
cd ~/BadDayInLeonida/clipper && source .venv/bin/activate
git -C ~/BadDayInLeonida/discovery pull -q
python ~/BadDayInLeonida/discovery/pull_backlog.py --client-secret client_secret.json --out backlog.csv
python clip.py --backlog backlog.csv --upload
python ~/BadDayInLeonida/discovery/pull_backlog.py --push --client-secret client_secret.json --out backlog.csv
```
Pull before cutting; push afterwards so clipped/uploaded rows are marked in the Sheet and never cut twice.
Local test file: `python clip.py --file X.mp4 --start 0 --end 8 --hook "..." --upload` (a bare path is read as a URL).
Test: Actions > Clip discovery > Run workflow.

## V2 quality / rights policy

Discovery now pre-filters for GTA VI moment-oriented English-language titles
and rejects explainers, trailers, mods and unrelated content. This is **only
metadata screening**, not AI viewing or proof the footage is a good Short.

The Mac pull script prevents `to-cut` rows with rights other than
`allowlisted` from reaching the local cutter. A `check` row needs verified
permission; giving credit alone does not establish usage rights.
Previous uploads are unchanged. Approve and inspect footage before publishing.

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
lead-in), skip sources without an unusually distinct peak, and require both
`rights=allowlisted` and a human-supplied `hook` for backlog processing.
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

## P0: audited private-upload pipeline (16 Nov 2026)

The production handoff is now **fail-closed**. A row in the Google Sheet can
be set to `status=to-cut` only after these approval fields are completed:

- `rights=allowlisted`: creator must be on the verified creator allowlist in `config.yaml`.
  This is assigned by discovery, **not** manually by the operator.
- `rights_evidence`: a durable URL to the **actual permission / licence record** or,
  for footage you recorded and own, `owned:<specific local evidence reference>`.
  **The source-video URL or mere credit is NOT rights evidence.**
- `rights_approved_by`: person who reviewed the evidence.
- `rights_approved_at`: date of approval (ISO date recommended).
- `hook`: approved truthful English on-screen hook. Optional `start` and `end`
  may be set to preserve the setup and payoff of a specific segment.

Unapproved `to-cut` entries are downgraded to `ready` in the local copy ONLY
and the script prints the reason. No rights status is inferred from views,
creator popularity, or YouTube availability.

After a successful **private** upload, `pull_backlog.py --push` writes
`status=uploaded`, `youtube` Shorts URL and `clip_file` to the Google Sheet.
Those fields persist across discovery sweeps. A missing video URL prevents
recording uploaded status. Final status is never regressed.

### One-time rollout (Mac)

1. From `~/BadDayInLeonida/discovery`, run `git pull origin main`.
2. In GitHub Actions > Clip discovery, select **Run workflow** once, then check
   the Sheet has `rights_evidence`, `rights_approved_by`,
   `rights_approved_at`, `youtube`, `clip_file` columns.
3. Use the Python environment with `numpy`, `PyYAML`, `gspread`,
   `google-auth-oauthlib`, `google-api-python-client`, `yt-dlp`
   and the installed clipper requirements.
4. Run the offline test `python -m unittest discover_tests.py p0_tests.py` then
   `python p0_smoke.py --clipper ../clipper`.
5. Fill approval fields **only for truly permitted content**; for a first
   real integration test use your own GTA gameplay rather than a third-party
   commentary video. Verify the rendered output and the resulting private
   entry in YouTube Studio.

### Daily Mac batch (still manual until P1 scheduler)

```bash
cd ~/BadDayInLeonida/clipper
git -C ~/BadDayInLeonida/discovery pull -q
python ~/BadDayInLeonida/discovery/pull_backlog.py --client-secret client_secret.json --out backlog.csv
python clip.py --backlog backlog.csv --upload
python ~/BadDayInLeonida/discovery/pull_backlog.py --push --client-secret client_secret.json --out backlog.csv
```

Never run the batch for unapproved sources. All uploads remain **private**
and require a further, separate human decision before public publishing.

**Limits:** The offline smoke test stubs the actual YouTube upload; it does
not prove Mac OAuth, source download, caption generation or YouTube response.
One full live test with a rights-cleared backlog source is still required.
