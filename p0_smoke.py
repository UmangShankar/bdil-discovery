"""Offline production smoke test against the Mac's actual v2 clip.py.

No network, video rendering or YouTube upload is performed. The real backlog
orchestration is exercised with a stubbed clip maker and a temporary CSV.
"""
import argparse
import csv
import importlib.util
import tempfile
from pathlib import Path

from p0_gate import approval_error, sync_changes

FIELDS = ["id", "status", "url", "rights", "hook", "flags", "rights_evidence",
          "rights_approved_by", "rights_approved_at", "youtube", "clip_file"]

def check(clipper: Path):
    script = clipper / "clip.py"
    if not script.is_file():
        raise SystemExit(f"Can't find clipper: {script}")
    source = script.read_text(encoding="utf-8")
    if '"privacyStatus": "private"' not in source:
        raise SystemExit("FAIL: uploader is not clearly configured for private uploads")
    if "r.get(\"rights\"" not in source or "allowlisted" not in source:
        raise SystemExit("FAIL: clipper is missing the v2 rights gate")
    spec = importlib.util.spec_from_file_location("bdil_mac_clipper", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    approved = dict.fromkeys(FIELDS, "")
    approved.update(id="yt:p0-test", status="to-cut",
        url="https://www.youtube.com/watch?v=example", rights="allowlisted",
        hook="NPCs fight back!", rights_evidence="https://example.org/creator-consent",
        rights_approved_by="operator", rights_approved_at="2026-11-16")
    if approval_error(approved):
        raise SystemExit("FAIL: approved sample was rejected by the rights gate")
    with tempfile.TemporaryDirectory(prefix="bdil-p0-") as d:
        path = Path(d) / "backlog.csv"
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            w.writerow(approved)
        original = module.make_clip
        try:
            def fake_make_clip(url, file, start, end, hook, title, do_upload, publish_at):
                assert do_upload is True
                assert publish_at is None, "P0 must not schedule public publication"
                assert hook == "NPCs fight back!"
                return [{"file": "p0-dry-run.mp4",
                         "youtube": "https://youtube.com/shorts/P0dryrun"}]
            module.make_clip = fake_make_clip
            module.run_backlog(path, True)
        finally:
            module.make_clip = original
        with path.open(newline="", encoding="utf-8") as f:
            result = list(csv.DictReader(f))[0]
        if result["status"] != "uploaded":
            raise SystemExit("FAIL: clipper did not mark successful private upload as uploaded")
        if result["youtube"] != "https://youtube.com/shorts/P0dryrun":
            raise SystemExit("FAIL: clipper did not save returned private video URL")
        if result["clip_file"] != "p0-dry-run.mp4":
            raise SystemExit("FAIL: clipper did not save the clip filename")
        remote = [FIELDS, [approved.get(c, "") for c in FIELDS]]
        changes = sync_changes(remote, {result["id"]: result})
        if (2, "status", "uploaded") not in changes or not any(x[1] == "youtube" for x in changes):
            raise SystemExit("FAIL: Sheets return-sync could not reconcile upload")
    print("PASS: approved row -> clipper batch -> private upload metadata -> Google Sheets status/link")
    print("NOTE: This was an OFFLINE simulation. No YouTube video was uploaded.")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--clipper", type=Path, default=Path("~/BadDayInLeonida/clipper").expanduser())
    args = p.parse_args()
    check(args.clipper.expanduser().resolve())
