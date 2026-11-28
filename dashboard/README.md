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

## Import a YouTube Studio export

Unzip the YouTube export, select **Import YouTube CSV**, and choose `Table data.csv`. Enter the report's exact date range. The import adds videos or updates existing YouTube rows by video ID in the selected channel. Imported entries are unclassified until you set their format. Imported views and other analytics are scoped to the report period; they are not lifetime views or 24-hour snapshots. Report views appear in the post table, with their date range. Re-importing a different range replaces the prior imported report metrics for each matching video; it does not create historical snapshots. Topic, hook, format and manual snapshots are preserved. Existing dashboard rows can be matched if their URL uses the standard YouTube watch or Shorts URL. Export a dashboard backup before importing.

YouTube's date-only publish value is shown as a date, without inventing a time. Set the actual UK posting time manually if known. The first-24-hour comparisons remain empty until true snapshots are entered. The report's additional analytics are stored in the backup for future analysis; they are not yet charted. TikTok imports are not yet implemented.

## Import TikTok content

Unzip the TikTok Content export and choose **Import TikTok CSV** and `Content.csv`. Enter the year that applies to all dates in that file; TikTok's file contains month/day but no year or posting time. Files crossing a year boundary are rejected. Videos are added or updated by TikTok video ID; existing manual tags and snapshots are preserved. The import stores TikTok's total views, likes, comments and shares as captured in the export, and displays total views with the capture date. It does not treat them as 24-hour or 7-day snapshots. The title is shortened at the `DESCRIPTION` marker when adding a row. Other TikTok exports (Overview, Followers and Viewers) are not yet imported. Back up before importing.
