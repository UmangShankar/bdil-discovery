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
