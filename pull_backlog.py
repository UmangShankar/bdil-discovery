"""Sync the backlog between the Google Sheet and the Mac.

  pull (before clip.py):  python pull_backlog.py --out backlog.csv
  push (after clip.py):   python pull_backlog.py --push --out backlog.csv

Pull downloads the Sheet's "backlog" tab to backlog.csv (read-only access).
Push writes status changes that clip.py made locally (in-progress, clipped, uploaded,
skipped) back to the Sheet, matched by id, so the same row is never cut twice.
It only moves a row forward; it never overwrites hooks or notes.

Signs in as you with client_secret.json (no service-account key). Each mode keeps its
own sign-in token; the first run of each opens a browser once.
"""
import argparse, csv
from pathlib import Path
import gspread
from gspread.utils import rowcol_to_a1

SHEET_ID = "1Oh4ginalP3ZMirlElEQ2ADyMu-PifJRBeVTrMkbqJEE"
HERE = Path(__file__).resolve().parent
TOKENS = Path("~/BadDayInLeonida").expanduser()
ORDER = {"": 0, "ready": 1, "to-cut": 2, "in-progress": 3, "clipped": 4, "uploaded": 5}
FINAL = {"skipped", "expired", "filtered"}

ap = argparse.ArgumentParser()
ap.add_argument("--out", default="backlog.csv", type=Path)
ap.add_argument("--push", action="store_true", help="write local status changes back to the Sheet")
ap.add_argument("--sheet", default=SHEET_ID)
ap.add_argument("--client-secret", default=HERE / "client_secret.json", type=Path)
a = ap.parse_args()

scope = "spreadsheets" if a.push else "spreadsheets.readonly"
gc = gspread.oauth(credentials_filename=str(a.client_secret),
                   authorized_user_filename=str(TOKENS / ("sheets_rw_token.json" if a.push else "sheets_token.json")),
                   scopes=[f"https://www.googleapis.com/auth/{scope}"])
ws = gc.open_by_key(a.sheet).worksheet("backlog")
rows = ws.get_all_values()

if not a.push:
    with a.out.open("w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)
    todo = sum(1 for r in rows[1:] if r and r[0] == "to-cut")
    print(f"{len(rows) - 1} rows saved to {a.out}, {todo} marked to-cut")
    raise SystemExit

head = rows[0]
si, ii = head.index("status"), head.index("id")
sheet_pos = {r[ii]: (n, r[si]) for n, r in enumerate(rows[1:], start=2) if len(r) > ii}
with a.out.open(newline="", encoding="utf-8") as f:
    local = {r["id"]: r.get("status", "") for r in csv.DictReader(f)}

updates = []
for rid, new in local.items():
    if rid not in sheet_pos:
        continue
    row_no, old = sheet_pos[rid]
    forward = new in FINAL or ORDER.get(new, -1) > ORDER.get(old, 99)
    if new and new != old and old not in FINAL and forward:
        updates.append({"range": rowcol_to_a1(row_no, si + 1), "values": [[new]]})
        print(f"{rid}: {old or '-'} -> {new}")
if updates:
    ws.batch_update(updates, value_input_option="RAW")
print(f"{len(updates)} status change(s) written to the Sheet")
