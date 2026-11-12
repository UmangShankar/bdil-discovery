"""Run on the Mac before clip.py: downloads the Sheet's backlog tab to backlog.csv.

Usage: python pull_backlog.py --key ~/BadDayInLeonida/service-account.json --out backlog.csv
"""
import argparse, csv, json
from pathlib import Path
import gspread

SHEET_ID = "1Oh4ginalP3ZMirlElEQ2ADyMu-PifJRBeVTrMkbqJEE"

ap = argparse.ArgumentParser()
ap.add_argument("--key", required=True, type=Path)
ap.add_argument("--out", default="backlog.csv", type=Path)
ap.add_argument("--sheet", default=SHEET_ID)
a = ap.parse_args()
ws = gspread.service_account(filename=str(a.key.expanduser())).open_by_key(a.sheet).worksheet("backlog")
rows = ws.get_all_values()
with a.out.open("w", newline="", encoding="utf-8") as f:
    csv.writer(f).writerows(rows)
todo = sum(1 for r in rows[1:] if r and r[0] == "to-cut")
print(f"{len(rows) - 1} rows saved to {a.out}, {todo} marked to-cut")
