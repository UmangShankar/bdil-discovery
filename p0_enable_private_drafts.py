"""One-time local v2 clipper patch: private drafts no longer require rights approval.

Run: python p0_enable_private_drafts.py --target ../clipper
Does not access OAuth secrets, download videos or upload anything.
"""
import argparse
import ast
import shutil
from pathlib import Path

OLD = '''        if r.get("rights", "").strip().lower() != "allowlisted":
            print(f"  HOLD (rights not verified): {r.get('title')}")
            continue
'''
NEW = '''        # P0: rights are advisory for PRIVATE drafts. Public publishing remains manual.
'''
def main(folder):
    f = folder / "clip.py"
    s = f.read_text(encoding="utf-8")
    if OLD not in s:
        if NEW in s:
            print("Already patched:", f)
            return
        raise SystemExit("Unexpected clip.py version: rights block not found; no changes made")
    if '"privacyStatus": "private"' not in s:
        raise SystemExit("Uploader does not appear private by default; refusing patch")
    out = s.replace(OLD, NEW, 1)
    ast.parse(out)
    backup = folder / "clip.py.pre-p0-drafts.bak"
    if not backup.exists():
        shutil.copy2(f, backup)
    f.write_text(out, encoding="utf-8")
    print("Private draft gate updated:", f)
    print("Backup:", backup)

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--target", required=True, type=Path)
    args = p.parse_args()
    main(args.target.expanduser().resolve())
