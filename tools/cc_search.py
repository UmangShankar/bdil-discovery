"""One-off: find Creative Commons (CC BY) GTA V videos with chaos/fail moments.
Writes tools/cc_results.md. Licence is re-checked per video via videos.list status.license."""
import os, re, requests
from datetime import datetime, timezone
YT = "https://www.googleapis.com/youtube/v3"
key = os.environ["YOUTUBE_API_KEY"]
QUERIES = ["gta 5 funny moments", "gta 5 fails", "gta v ragdoll physics", "gta 5 police chase funny",
           "gta 5 chaos", "gta 5 euphoria ragdoll", "gta v funny gameplay"]
def dur(s):
    m = re.match(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", s or "")
    d, h, mi, se = (int(x or 0) for x in m.groups()); return d*86400+h*3600+mi*60+se
ids = []
for q in QUERIES:
    r = requests.get(f"{YT}/search", timeout=30, params={"key": key, "part": "id", "type": "video", "q": q,
        "videoLicense": "creativeCommon", "order": "viewCount", "maxResults": 25, "relevanceLanguage": "en"})
    r.raise_for_status(); ids += [i["id"]["videoId"] for i in r.json()["items"]]
ids = list(dict.fromkeys(ids)); rows = []
for i in range(0, len(ids), 50):
    r = requests.get(f"{YT}/videos", timeout=30, params={"key": key, "part": "snippet,statistics,contentDetails,status",
        "id": ",".join(ids[i:i+50])}); r.raise_for_status()
    for v in r.json()["items"]:
        if v["status"].get("license") != "creativeCommon": continue
        sn = v["snippet"]; d = dur(v["contentDetails"]["duration"])
        if d < 60 or not re.search(r"gta\s*(v|5)\b|grand theft auto (v|5)", sn["title"], re.I): continue
        rows.append((int(v["statistics"].get("viewCount", 0)), v["id"], sn["title"], sn["channelTitle"],
                     sn["channelId"], sn["publishedAt"][:10], d, v["status"].get("embeddable")))
rows.sort(reverse=True)
out = [f"# CC BY GTA V candidates ({datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC)", "",
       "| # | Views | Title | Channel | Published | Length | URL |", "|---|---|---|---|---|---|---|"]
for n, (vw, vid, t, ch, cid, pub, d, emb) in enumerate(rows[:40], 1):
    out.append(f"| {n} | {vw:,} | {t.replace('|','/')[:80]} | {ch.replace('|','/')} | {pub} | {d//60}:{d%60:02d} | https://www.youtube.com/watch?v={vid} |")
open("tools/cc_results.md", "w").write("\n".join(out) + "\n"); print("\n".join(out))
