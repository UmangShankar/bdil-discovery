# Clip Intelligence

A local, reusable dashboard for clipping brands. Each profile groups a brand's YouTube and TikTok posts. It does not modify the clipping pipeline, connect accounts, import platform CSV files, or fetch metrics automatically.

## Start

From the discovery repository on your Mac:

```bash
cd ~/BadDayInLeonida/discovery
python3 -m http.server 8765 --directory dashboard
```

Open http://localhost:8765 in the same browser each time. Press Ctrl-C in Terminal to stop. Bad Day in Leonida starts as an empty profile; no performance numbers are invented. Add more profiles with **+ Channel**.

## Use

1. Add each published YouTube or TikTok post with **+ Add post**. Assign the same content ID to matching edits and the correct format, topic and hook. Record the UK local posting time.
2. Enter available views at 24 hours and 7 days as snapshots, plus lifetime views and capture date. Edit the post as figures become available. Old lifetime totals are not 24-hour figures. Leave unknown fields blank. Add average watch time, interactions and follower gains when available.
3. Filter by platform and format. Topic, hook and posting-time comparisons show median 24-hour views separately by platform and format, with sample size. Treat results as hypotheses, especially with small samples. Long videos and Shorts are different groups. Posting time is not proof of causation.
4. Export a JSON backup regularly and before changing browsers or clearing data. **Import backup replaces all local dashboard data**, after confirmation. The dashboard stores data in browser local storage, not in this repository and not across devices. Do not commit backups containing private analytics to the public repository.

Platform definitions differ. The combined lifetime total is upload plays, not unique viewers. Historic figures and snapshot timing are manually supplied, so verify accuracy in Studio. Posts are not automatically cross-matched: shared content IDs are displayed for manual comparison. API integration, analytics CSV imports, time-series history, paired-comparison analytics and automated recommendations are possible later extensions.
