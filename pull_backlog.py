"""Run on the Mac before clip.py: downloads the Sheet's backlog tab to backlog.csv.

Signs in as you (no service-account key needed), using the same client_secret.json
as the uploader. The first run opens a browser once; the sign-in is then cached.

Usage: python pull_backlog.py --out backlog.csv
"""
import argparse, csv
from pathlib import Path
import gspread

SHEET_ID = "1Oh4ginalP3ZMirlElEQ2ADyMu-PifJRBeVTrMkbqJEE"
HERE = Path(__file__).resolve().parent

ap = argparse.ArgumentParser()
ap.add_argument("--out", default="backlog.csv", type=Path)
ap.add_argument("--sheet", default=SHEET_ID)
ap.add_argument("--client-secret", default=HERE / "client_secret.json", type=Path)
ap.add_argument("--token", default=Path("~/BadDayInLeonida/sheets_token.json").expanduser(), type=Path)
a = ap.parse_args()
gc = gspread.oauth(credentials_filename=str(a.client_secret), authorized_user_filename=str(a.token),
                   scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
rows = gc.open_by_key(a.sheet).worksheet("backlog").get_all_values()
with a.out.open("w", newline="", encoding="utf-8") as f:
    csv.writer(f).writerows(rows)
todo = sum(1 for r in rows[1:] if r and r[0] == "to-cut")
print(f"{len(rows) - 1} rows saved to {a.out}, {todo} marked to-cut")
