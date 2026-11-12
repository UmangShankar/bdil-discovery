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

On the Mac, `python pull_backlog.py --out backlog.csv` signs in as you with client_secret.json.
Test: Actions > Clip discovery > Run workflow.
