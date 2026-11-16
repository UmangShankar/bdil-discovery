"""Sync approved backlog from Google Sheets to local cutter and return private upload links.

Pull: python pull_backlog.py --client-secret ../clipper/client_secret.json --out ../clipper/backlog.csv
Push: python pull_backlog.py --push --client-secret ../clipper/client_secret.json --out ../clipper/backlog.csv
Credentials remain on Mac. P0 gate is fail-closed.
"""
import argparse
import csv
from pathlib import Path
import gspread
from gspread.utils import rowcol_to_a1
from p0_gate import gate_rows, sync_changes

SHEET_ID = "1Oh4ginalP3ZMirlElEQ2ADyMu-PifJRBeVTrMkbqJEE"
HERE = Path(__file__).resolve().parent
TOKENS = Path("~/BadDayInLeonida").expanduser()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="backlog.csv", type=Path)
    ap.add_argument("--push", action="store_true")
    ap.add_argument("--sheet", default=SHEET_ID)
    ap.add_argument("--client-secret", default=HERE / "client_secret.json", type=Path)
    args = ap.parse_args()
    scope = "spreadsheets" if args.push else "spreadsheets.readonly"
    gc = gspread.oauth(credentials_filename=str(args.client_secret),
                      authorized_user_filename=str(TOKENS / ("sheets_rw_token.json" if args.push else "sheets_token.json")),
                      scopes=[f"https://www.googleapis.com/auth/{scope}"])
    ws = gc.open_by_key(args.sheet).worksheet("backlog")
    rows = ws.get_all_values()
    if not rows:
        raise SystemExit("No backlog found; refusing to run cutter")
    if not args.push:
        try:
            safe, held = gate_rows(rows)
        except ValueError as exc:
            raise SystemExit(f"SAFETY: {exc}. Run discovery to refresh Sheet schema first.")
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(safe)
        for reason in held:
            print("HOLD:", reason)
        h = safe[0]
        todo = sum(r[h.index("status")] == "to-cut" for r in safe[1:])
        print(f"{len(rows)-1} rows saved, {todo} approved to-cut, {len(held)} held")
        return
    if not args.out.exists():
        raise SystemExit(f"Local backlog missing: {args.out}")
    with args.out.open(newline="", encoding="utf-8") as f:
        local = {r["id"]: r for r in csv.DictReader(f)}
    try:
        updates = sync_changes(rows, local)
    except ValueError as exc:
        raise SystemExit(f"SYNC ERROR: {exc}")
    if updates:
        header = rows[0]
        # Write source URLs and clip files before changing status to uploaded.
        payload = [{"range": rowcol_to_a1(line, header.index(col) + 1),
                    "values": [[value]]} for line, col, value in updates]
        ws.batch_update(payload, value_input_option="RAW")
        for line, col, value in updates:
            print(f"Sheet row {line}: {col} -> {value[:100]}")
    print(f"{len(updates)} cell update(s) written to the Sheet")

if __name__ == "__main__":
    main()
