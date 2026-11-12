"""Bad Day In Leonida: clip discovery.

Pulls fresh GTA 6 moments from YouTube, Twitch and Reddit, scores them against
config.yaml and merges them into a rolling backlog (backlog.csv, plus a Google
Sheet if configured). Writes digest.md with the top picks and backlog health.
"""
import argparse
import csv
import json
import math
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parent
NOW = datetime.now(timezone.utc)
YT = "https://www.googleapis.com/youtube/v3"
TW = "https://api.twitch.tv/helix"
UA = "BadDayInLeonida-discovery/1.0 (by u/BadDayInLeonida)"
VIDEO_DOMAINS = ("v.redd.it", "youtube.com", "youtu.be", "twitch.tv", "streamable.com", "medal.tv")

# Columns the cutter (clip.py) reads: status, url, hook, start, end, captions.
FIELDS = ["status", "tier", "score", "source", "title", "creator", "url", "hook", "start", "end",
          "captions", "views", "views_per_h", "age_h", "brand_hits", "flags", "rights",
          "published_at", "first_seen", "id", "notes"]
USER_FIELDS = ["status", "hook", "start", "end", "captions", "notes"]   # never overwritten by a run
DONE = {"clipped", "skipped", "expired", "uploaded", "filtered"}
WARNINGS = []


def log(msg):
    print(msg, file=sys.stderr)


def parse_ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def age_hours(dt):
    return max((NOW - dt).total_seconds() / 3600, 0.25)


def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def log_score(value, target):
    if not value or value <= 0 or target <= 0:
        return 0.0
    return clamp(math.log10(1 + value) / math.log10(1 + target))


def chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def yt_duration(s):
    m = re.match(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", s or "")
    if not m:
        return 0
    d, h, mi, se = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + se


# ---------------------------------------------------------------- sources

def fetch_youtube(scfg):
    key = os.getenv("YOUTUBE_API_KEY")
    if not key:
        log("youtube: skipped (no YOUTUBE_API_KEY)")
        return []
    after = iso(NOW - timedelta(hours=scfg["lookback_hours"]))
    ids = []
    for q in scfg["queries"]:
        r = requests.get(f"{YT}/search", timeout=30, params={
            "key": key, "part": "id", "type": "video", "q": q, "order": "viewCount",
            "publishedAfter": after, "maxResults": scfg.get("max_results_per_query", 25),
            "relevanceLanguage": "en"})
        r.raise_for_status()
        ids += [i["id"]["videoId"] for i in r.json().get("items", []) if i["id"].get("videoId")]
    ids = list(dict.fromkeys(ids))
    videos = []
    for batch in chunks(ids, 50):
        r = requests.get(f"{YT}/videos", timeout=30, params={
            "key": key, "part": "snippet,statistics,contentDetails", "id": ",".join(batch)})
        r.raise_for_status()
        videos += r.json().get("items", [])
    subs = {}
    chan_ids = list({v["snippet"]["channelId"] for v in videos})
    for batch in chunks(chan_ids, 50):
        r = requests.get(f"{YT}/channels", timeout=30, params={
            "key": key, "part": "statistics", "id": ",".join(batch)})
        r.raise_for_status()
        for c in r.json().get("items", []):
            subs[c["id"]] = int(c["statistics"].get("subscriberCount", 0) or 0)
    out = []
    for v in videos:
        sn, st = v["snippet"], v.get("statistics", {})
        if sn.get("liveBroadcastContent") in ("live", "upcoming"):
            continue
        dur = yt_duration(v["contentDetails"].get("duration"))
        if dur < scfg.get("min_duration_s", 180):
            continue
        views = int(st.get("viewCount", 0) or 0)
        if views < scfg["min_views"]:
            continue
        likes, comments = int(st.get("likeCount", 0) or 0), int(st.get("commentCount", 0) or 0)
        s = subs.get(sn["channelId"], 0)
        out.append(dict(
            id=f"yt:{v['id']}", source="youtube", title=sn["title"], creator=sn["channelTitle"],
            creator_id=sn["channelId"], url=f"https://www.youtube.com/watch?v={v['id']}",
            published=parse_ts(sn["publishedAt"]), views=views,
            engagement=(likes + 3 * comments) / views if views else 0,
            outlier=views / max(s, 1000) if s else None,
            text=f"{sn['title']} {sn.get('description', '')[:500]} {' '.join(sn.get('tags', []))}",
            lookback=scfg["lookback_hours"], velocity_target=scfg["velocity_target"]))
    log(f"youtube: {len(ids)} found, {len(out)} passed source minimums")
    return out


def fetch_twitch(scfg):
    cid, secret = os.getenv("TWITCH_CLIENT_ID"), os.getenv("TWITCH_CLIENT_SECRET")
    if not (cid and secret):
        log("twitch: skipped (no TWITCH_CLIENT_ID/SECRET)")
        return []
    tok = requests.post("https://id.twitch.tv/oauth2/token", timeout=30, data={
        "client_id": cid, "client_secret": secret, "grant_type": "client_credentials"})
    tok.raise_for_status()
    h = {"Client-Id": cid, "Authorization": f"Bearer {tok.json()['access_token']}"}
    g = requests.get(f"{TW}/games", headers=h, timeout=30, params={"name": scfg["game_name"]})
    g.raise_for_status()
    games = g.json().get("data", [])
    if not games:
        log(f"twitch: category '{scfg['game_name']}' not found yet")
        return []
    r = requests.get(f"{TW}/clips", headers=h, timeout=30, params={
        "game_id": games[0]["id"], "first": 100,
        "started_at": iso(NOW - timedelta(hours=scfg["lookback_hours"])), "ended_at": iso(NOW)})
    r.raise_for_status()
    out = []
    for c in r.json().get("data", []):
        if c["view_count"] < scfg["min_views"]:
            continue
        out.append(dict(
            id=f"tw:{c['id']}", source="twitch", title=c["title"], creator=c["broadcaster_name"],
            creator_id=c["broadcaster_id"], url=c["url"], published=parse_ts(c["created_at"]),
            views=c["view_count"], engagement=None, outlier=None,
            text=f"{c['title']} gta 6", lookback=scfg["lookback_hours"],
            velocity_target=scfg["velocity_target"]))
    log(f"twitch: {len(out)} clips passed")
    return out


def reddit_session():
    """Reddit blocks anonymous requests from datacentre IPs (GitHub Actions gets 403).
    With REDDIT_CLIENT_ID/SECRET set, use an app-only OAuth token on oauth.reddit.com."""
    cid, secret = os.getenv("REDDIT_CLIENT_ID"), os.getenv("REDDIT_CLIENT_SECRET")
    if not (cid and secret):
        return "https://www.reddit.com", {"User-Agent": UA}
    tok = requests.post("https://www.reddit.com/api/v1/access_token", timeout=30, auth=(cid, secret),
                        data={"grant_type": "client_credentials"}, headers={"User-Agent": UA})
    tok.raise_for_status()
    return "https://oauth.reddit.com", {"User-Agent": UA, "Authorization": f"Bearer {tok.json()['access_token']}"}


def fetch_reddit(scfg):
    out = []
    base, headers = reddit_session()
    for sub in scfg["subreddits"]:
        try:
            r = requests.get(f"{base}/r/{sub}/top", timeout=30,
                             headers=headers, params={"t": "day", "limit": 50, "raw_json": 1})
            r.raise_for_status()
        except requests.RequestException as e:
            log(f"reddit r/{sub}: failed ({e})")
            WARNINGS.append(f"reddit r/{sub}: {type(e).__name__} {getattr(e.response, 'status_code', '')}".strip())
            continue
        for ch in r.json().get("data", {}).get("children", []):
            p = ch["data"]
            is_video = p.get("is_video") or any(d in (p.get("url") or "") for d in VIDEO_DOMAINS)
            if not is_video or p.get("ups", 0) < scfg["min_upvotes"]:
                continue
            out.append(dict(
                id=f"rd:{p['id']}", source="reddit", title=p["title"], creator=f"u/{p.get('author')}",
                creator_id=p.get("author"), url=f"https://www.reddit.com{p['permalink']}",
                published=datetime.fromtimestamp(p["created_utc"], timezone.utc), views=p["ups"],
                engagement=p.get("num_comments", 0) / max(p["ups"], 1), outlier=None,
                text=f"{p['title']} {p.get('link_flair_text') or ''} r/{sub}",
                lookback=scfg["lookback_hours"], velocity_target=scfg["velocity_target"]))
    log(f"reddit: {len(out)} video posts passed")
    return out


# ---------------------------------------------------------------- scoring

def score(cands, cfg):
    sc = cfg["scoring"]
    w = sc["weights"]
    game = re.compile(cfg["game_pattern"], re.I)
    excl = re.compile(cfg["exclude_pattern"], re.I)
    allow = {c.lower() for c in cfg["rights"]["allowlist_creators"]}
    block = {c.lower() for c in cfg["rights"]["blocklist_creators"]}
    out = []
    for c in cands:
        text = c["text"]
        if not game.search(c["title"]) and c["source"] != "twitch":
            continue  # tags/descriptions are spammed with #gta6, so the title must say it
        if excl.search(c["title"]) or c["creator"].lower() in block:
            continue
        age = age_hours(c["published"])
        if age > c["lookback"]:
            continue
        low = c["title"].lower()
        hits = sorted({k for k in cfg["brand_keywords"] if re.search(rf"\b{re.escape(k)}\b", low)})
        vph = c["views"] / age
        parts = {
            "velocity": log_score(vph, c["velocity_target"]),
            "outlier": clamp(math.log10(1 + c["outlier"]) / math.log10(11)) if c["outlier"] is not None
            else log_score(vph, c["velocity_target"]),
            "engagement": clamp(c["engagement"] / 0.08) if c["engagement"] is not None else 0.5,
            "brand": clamp(len(hits) / sc["brand_full_hits"]),
            "freshness": clamp(1 - age / c["lookback"]),
            "rights": 1.0 if c["creator"].lower() in allow else 0.3,
        }
        total = round(sum(parts[k] * w[k] for k in w))
        if total < sc["tier_b"]:
            continue
        flags = []
        if any(re.search(rf"\b{re.escape(k)}\b", low) for k in cfg["spoiler_keywords"]):
            flags.append("SPOILER")
        out.append(dict(
            id=c["id"], source=c["source"], title=c["title"], creator=c["creator"], url=c["url"],
            views=c["views"], views_per_h=round(vph), age_h=round(age, 1), brand_hits=", ".join(hits),
            flags=" ".join(flags), rights="allowlisted" if c["creator"].lower() in allow else "check",
            published_at=iso(c["published"]), score=total,
            tier="A" if total >= sc["tier_a"] else "B"))
    return out


# ---------------------------------------------------------------- backlog

def load_csv(path):
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as f:
        return {r["id"]: {k: r.get(k, "") for k in FIELDS} for r in csv.DictReader(f)}


def save_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=FIELDS)
        wr.writeheader()
        wr.writerows(rows)


def merge(backlog, scored, cfg):
    added = 0
    for s in scored:
        row = backlog.get(s["id"])
        if row is None:
            row = {k: "" for k in FIELDS}
            row.update(status="ready", first_seen=iso(NOW))
            backlog[s["id"]] = row
            added += 1
        if row["status"] in DONE:
            continue
        for k, v in s.items():
            if k not in USER_FIELDS:
                row[k] = str(v)
    game = re.compile(cfg["game_pattern"], re.I)
    excl = re.compile(cfg["exclude_pattern"], re.I)
    block = {c.lower() for c in cfg["rights"]["blocklist_creators"]}
    for row in backlog.values():  # rules changed since a row was added? drop it from the queue
        if row["status"] == "ready" and (excl.search(row["title"]) or row["creator"].lower() in block
                                         or (row["source"] != "twitch" and not game.search(row["title"]))):
            row["status"] = "filtered"
    exp = cfg["backlog"]["expire_hours"]
    for row in backlog.values():
        if row["status"] == "ready" and row.get("first_seen"):
            if (NOW - parse_ts(row["first_seen"])).total_seconds() / 3600 > exp:
                row["status"] = "expired"
    return added


def ordered(backlog):
    rank = {"to-cut": 0, "in-progress": 1, "ready": 2}
    return sorted(backlog.values(), key=lambda r: (rank.get(r["status"], 9), -int(r["score"] or 0)))


def health(rows, cfg):
    need = cfg["backlog"]["shorts_per_day"] * cfg["backlog"]["days_of_cover"]
    ready = [r for r in rows if r["status"] in ("ready", "to-cut") and "SPOILER" not in r["flags"]]
    n = len(ready)
    state = "HEALTHY" if n >= need else ("LOW" if n >= cfg["backlog"]["shorts_per_day"] else "EMPTY")
    return state, ready, need


# ---------------------------------------------------------------- google sheet

SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]


def sheet_handle():
    """Keyless by default: in GitHub Actions, google-github-actions/auth (Workload Identity
    Federation) sets GOOGLE_APPLICATION_CREDENTIALS. A JSON key still works if one is given."""
    sid = os.getenv("GOOGLE_SHEET_ID")
    sa = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not sid or not (sa or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")):
        return None
    import gspread
    if sa:
        gc = gspread.service_account_from_dict(json.loads(sa))
    else:
        import google.auth
        creds, _ = google.auth.default(scopes=SCOPES)
        gc = gspread.authorize(creds)
    sh = gc.open_by_key(sid)
    try:
        return sh.worksheet("backlog")
    except gspread.WorksheetNotFound:
        return sh.add_worksheet("backlog", rows=1000, cols=len(FIELDS))


def pull_sheet_edits(ws, backlog):
    """Your edits in the Sheet (status, hook, start, end, captions, notes) win over the CSV."""
    for r in ws.get_all_records(expected_headers=[]):
        rid = str(r.get("id", ""))
        if rid in backlog:
            for k in USER_FIELDS:
                if k in r and str(r[k]) != "":
                    backlog[rid][k] = str(r[k])


def push_sheet(ws, rows, digest_text):
    ws.clear()
    ws.update([FIELDS] + [[r.get(k, "") for k in FIELDS] for r in rows], value_input_option="RAW")
    ws.freeze(rows=1)
    sh = ws.spreadsheet
    try:
        dg = sh.worksheet("digest")
    except Exception:
        dg = sh.add_worksheet("digest", rows=60, cols=1)
    dg.clear()
    dg.update([[line] for line in digest_text.splitlines()], value_input_option="RAW")


# ---------------------------------------------------------------- digest

def digest(rows, cfg, added, counts):
    state, ready, need = health(rows, cfg)
    a = sum(1 for r in ready if r["tier"] == "A")
    days = len(ready) / cfg["backlog"]["shorts_per_day"]
    lines = [f"# Bad Day In Leonida: discovery digest, {NOW.strftime('%a %d %b %Y %H:%M')} UTC", ""]
    if NOW < datetime(2026, 11, 19, tzinfo=timezone.utc):
        lines += ["_Pre-launch: GTA 6 is out on 19 Nov. Expect a thin feed until then._", ""]
    lines += [
        f"**Backlog: {state}** | {len(ready)} ready ({a} tier A) = {days:.1f} days of cover "
        f"(target {need}) | {added} new this run",
        "", "Sources this run: " + (", ".join(f"{k} {v}" for k, v in counts.items()) or "none"), "",
        "| # | Status | Tier | Score | Source | Title | Creator | Views/h | Flags |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for i, r in enumerate(ready[:15], 1):
        title = r["title"][:70].replace("|", "/")
        lines.append(f"| {i} | {r['status']} | {r['tier']} | {r['score']} | {r['source']} | "
                     f"[{title}]({r['url']}) | {r['creator'].replace('|', '/')} | {r['views_per_h']} | {r['flags']} |")
    if not ready:
        lines.append("| - | - | - | - | - | nothing ready | - | - | - |")
    lines += ["", "Rights column says `check` until the creator is on the allowlist. "
              "Confirm permission before you publish."]
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=ROOT / "config.yaml", type=Path)
    ap.add_argument("--backlog", default=ROOT / "backlog.csv", type=Path)
    ap.add_argument("--digest", default=ROOT / "digest.md", type=Path)
    args = ap.parse_args()
    cfg = yaml.safe_load(args.config.read_text())

    fetchers = {"youtube": fetch_youtube, "twitch": fetch_twitch, "reddit": fetch_reddit}
    cands, counts, errors = [], {}, []
    for name, fn in fetchers.items():
        scfg = cfg["sources"].get(name, {})
        if not scfg.get("enabled"):
            continue
        try:
            got = fn(scfg)
        except requests.RequestException as e:
            log(f"{name}: failed ({e})")
            errors.append(name)
            got = []
        cands += got
        counts[name] = len(got)

    scored = score(cands, cfg)
    backlog = load_csv(args.backlog)
    ws = None
    try:
        ws = sheet_handle()
        if ws:
            pull_sheet_edits(ws, backlog)
    except Exception as e:  # the sheet is optional; never block the run
        log(f"sheets: read failed ({e})")
    added = merge(backlog, scored, cfg)
    rows = ordered(backlog)
    save_csv(args.backlog, rows)
    text = digest(rows, cfg, added, counts)
    if errors or WARNINGS:
        text += "\nSource problems this run: " + "; ".join(errors + WARNINGS) + "\n"
    if ws:
        try:
            push_sheet(ws, rows, text)
        except Exception as e:
            log(f"sheets: write failed ({e})")
    args.digest.write_text(text, encoding="utf-8")
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write(text)
    print(text)


if __name__ == "__main__":
    main()
