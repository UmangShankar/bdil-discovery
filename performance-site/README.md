# Clip Intelligence: hosted performance dashboard

Private, multi-channel dashboard with daily manual updates, a daily-views line chart, title-based topic analysis, and YouTube/TikTok content CSV imports. The code starts with one empty profile and **does not include anyone's analytics or Site identity**. This is separate from the V4 clipping pipeline.

## ChatGPT Sites deployment

1. Open this repository in a ChatGPT coding workspace with the Sites capability and ask it to create a **new private Site from `performance-site/`**. The supplied `.openai/hosting.json` declares the `DB` database binding but intentionally does not identify a Site.
2. The Sites workflow creates a new Site, provisions D1, applies the checked-in Drizzle migration in `drizzle/`, builds, and deploys the app. Hosted database records are keyed to the signed-in ChatGPT user; API endpoints reject requests without identity. Do not copy another person's Site project ID, credentials or database.
3. Open your Site, select or add a channel, and import the platform exports. Use **+ Daily update** to enter that day's figures. You must save a change to initialise the database. Entries are keyed by channel, platform and date; saving an existing date asks before replacing entered fields.

Sites capability, authentication, D1 provisioning and publication depend on the user's ChatGPT workspace and supported Sites workflow. A GitHub clone alone does not provision or deploy a ChatGPT Site. Do not expose a publicly accessible deployment without adding appropriate access controls.

## Developer preview

The Site uses Node 22.13+, npm, Vinext and Cloudflare D1. From this directory:

```bash
npm ci
npm run db:generate
npm run build
node --import ./scripts/sites-env.mjs ./node_modules/wrangler/bin/wrangler.js d1 execute DB --local --config dist/server/wrangler.json --persist-to .wrangler/state --file drizzle/0000_windy_golden_guardian.sql
npm start
```

Open the local URL printed by Wrangler. The local database is separate from the hosted Site; local preview authentication depends on the Sites development configuration and does not prove the hosted sign-in flow. If local sign-in is unavailable, use the supported Sites preview rather than bypassing authentication. The checked-in migration is already generated; rerun `db:generate` only after editing the schema, and do not modify applied migrations.

## Importing and data semantics

- **YouTube:** unzip the Studio export and select `Table data.csv`, then provide the exact report start and end dates. Re-imports update matching video IDs in the selected channel. Report-period figures are not automatically lifetime or 24-hour values.
- **TikTok:** unzip the content export and select `Content.csv`. Enter the year used by its month/day dates. A file spanning a year boundary is rejected. Re-imports update matching video IDs and retain dated TikTok observations.
- **Daily updates:** supply daily changes, not cumulative totals. The line chart displays daily views for the selected platform (Overview defaults to TikTok). There is no automatic platform connection or daily fetch.
- **Migration from the older local dashboard:** export its JSON backup, then choose **Merge dashboard backup**. This merges matching post IDs and platform video IDs. The dashboard's initial empty profile is separate; select or add the appropriate profile after import. Inspect results before making further changes. The prior browser's data is not automatically copied.
- Back up regularly using **Export backup**. Keep exported analytics and platform credentials out of Git.

## Analysis limitations

Topics are approximate keyword matches against titles, not video understanding; edit topic labels in **Show imported posts**. Medians are descriptive, include videos of different ages and potentially different formats, and can be affected by low sample sizes. YouTube metrics from different report periods should not be mixed as a controlled comparison. TikTok imported post totals and YouTube report-period views have different meanings and are shown separately. The dashboard does not yet infer the best posting time, calculate a unique weekly returning-viewer north star, import TikTok account overview/follower/viewer CSVs, or automatically generate a causal growth strategy. The daily chart does not fill missing days.
