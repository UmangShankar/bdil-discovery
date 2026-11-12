# Bad Day In Leonida: clip discovery

Runs 4x a day on GitHub Actions. Finds GTA 6 moments on YouTube, Twitch and Reddit,
scores them (see config.yaml), and keeps a rolling backlog in `backlog.csv`, the
Google Sheet ("backlog" and "digest" tabs) and `digest.md`.

Morning: in the Sheet, set `status` to `to-cut` and write a `hook` (optional `start`/`end`
in seconds or mm:ss). Your edits are never overwritten. Statuses: ready, to-cut,
in-progress, clipped, uploaded, skipped, expired.

Secrets (Settings > Secrets and variables > Actions): YOUTUBE_API_KEY, TWITCH_CLIENT_ID,
TWITCH_CLIENT_SECRET, GOOGLE_SHEET_ID, GOOGLE_SERVICE_ACCOUNT_JSON.
Test: Actions > Clip discovery > Run workflow.
