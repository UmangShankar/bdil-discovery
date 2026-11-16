"""Apply v2 event-centred Shorts changes to the local cutter.

Usage from the discovery directory:
    python upgrade_clipper.py --target ../clipper
The original files are preserved as .pre-v2.bak files.
"""
import argparse
import ast
import re
import shutil
from pathlib import Path

def replace_once(source, old, new):
    if old not in source:
        raise ValueError("Unexpected clip.py version; missing: " + old[:80])
    return source.replace(old, new, 1)

def upgrade(folder):
    script, conf = folder / "clip.py", folder / "config.yaml"
    source, settings = script.read_text(), conf.read_text()
    original_window = '''def _pick_windows(segs, duration, n):
    lead, length = CFG["lead_in_sec"], CFG["max_clip_sec"]
    picks: list[tuple[float, float]] = []
    for s, e, _ in sorted(segs, key=lambda x: -x[2]):
        peak = (s + e) / 2
        start = max(0.0, peak - lead)
        end = min(duration, start + length)
        if all(end <= ps or start >= pe for ps, pe in picks):   # no overlap
            picks.append((start, end))
        if len(picks) >= n:
            break
    return sorted(picks)'''
    replacement_window = '''def _pick_windows(segs, duration, n):
    """Choose prominent peaks, without making clips just to fill a quota."""
    if not segs or duration <= 0:
        return []
    values = np.array([float(v) for _, _, v in segs], dtype=float)
    baseline = float(np.median(values))
    spread = float(np.percentile(values, 90) - baseline)
    if spread <= 1e-9:
        return []
    threshold = baseline + max(spread * 1.2, 1e-9)
    lead = float(CFG.get("lead_in_sec", 2.5))
    length = min(max(float(CFG.get("max_clip_sec", 22)), 12), 30)
    picks = []
    for s, e, power in sorted(segs, key=lambda x: -x[2]):
        if power < threshold:
            break
        peak = (s + e) / 2
        start = max(0.0, peak - lead)
        end = min(float(duration), start + length)
        if end - start < 10:
            continue
        if all(end <= ps or start >= pe for ps, pe in picks):
            picks.append((start, end))
        if len(picks) >= n:
            break
    return sorted(picks)'''
    source = replace_once(source, original_window, replacement_window)
    source = replace_once(source,
        '    results = []\n    stamp = datetime.now().strftime("%Y%m%d-%H%M")',
        '    if not windows:\n        print("No strong moment: skip this source instead of making filler.")\n        return []\n    results = []\n    stamp = datetime.now().strftime("%Y%m%d-%H%M")')
    source = replace_once(source,
        '''        if "SPOILER" in (r.get("flags") or ""):
            print(f"  skipping spoiler-flagged: {r.get('title')}")
            continue
        try:''',
        '''        if "SPOILER" in (r.get("flags") or ""):
            print(f"  skipping spoiler-flagged: {r.get('title')}")
            continue
        if r.get("rights", "").strip().lower() != "allowlisted":
            print(f"  HOLD (rights not verified): {r.get('title')}")
            continue
        if not (r.get("hook") or "").strip():
            print(f"  HOLD (needs a specific hook): {r.get('title')}")
            continue
        try:''')
    # The local cutter may have slightly different bookkeeping lines; only
    # replace the status assignment and leave the rest of the method intact.
    # No clips = skip, not a false successful "clipped" status.
    source, status_count = re.subn(
        r'(?m)^(\\s*)r\\["status"\\]\\s*=\\s*["\\']clipped["\\']\\s*$',
        lambda m: m.group(1) + 'if not res:\\n'
        + m.group(1) + '    r["status"] = "skipped"\\n'
        + m.group(1) + 'else:\\n'
        + m.group(1) + '    r["status"] = "uploaded" if do_upload else "clipped"',
        source, count=1)
    if status_count != 1:
        print("NOTE: status block differs; retained existing status logic")
    source = replace_once(source,
        '    elif a.url or a.file:\n        make_clip(',
        '    elif a.url or a.file:\n        if a.upload:\n            sys.exit("Direct upload disabled: use a rights-approved backlog row.")\n        make_clip(')
    for old, new in (("auto_clips_per_video: 2", "auto_clips_per_video: 1"),
                     ("max_clip_sec: 40", "max_clip_sec: 22"),
                     ("lead_in_sec: 12", "lead_in_sec: 2.5")):
        if old not in settings:
            raise ValueError("Unexpected config: " + old)
        settings = settings.replace(old, new, 1)
    ast.parse(source)
    shutil.copy2(script, folder / "clip.py.pre-v2.bak")
    shutil.copy2(conf, folder / "config.yaml.pre-v2.bak")
    script.write_text(source)
    conf.write_text(settings)
    print("Updated", script, "and config.yaml. Local backups saved.")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=Path, required=True)
    args = ap.parse_args()
    upgrade(args.target.expanduser().resolve())
