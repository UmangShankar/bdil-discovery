"""Install V3 automatic AI hook selection from GitHub discovery into local clipper.

Run: python install_v3.py --target ../clipper
No secrets or videos are copied. Installation makes backups and fails closed.
"""
import argparse
import ast
import re
import shutil
from pathlib import Path

def replace_once(src,old,new,label):
    if src.count(old)!=1:
        raise RuntimeError(f"Unsupported local clip.py at {label}: {src.count(old)} anchors; no files changed")
    return src.replace(old,new,1)

def install(folder):
    folder=Path(folder).expanduser().resolve()
    path=folder/"clip.py"
    cfgpath=folder/"config.yaml"
    before=path.read_text(encoding="utf-8")
    cfg=cfgpath.read_text(encoding="utf-8")
    if "AI moment selection v3" in before:
        print("Already installed v3; no changes made")
        return
    after=before
    if "import os\n" not in after:
        after=replace_once(after,"import json\n","import json\nimport os\n","imports")
    old='    if start is not None:\n        end = end if end is not None else start + CFG["max_clip_sec"]'
    new='''    # AI moment selection v3: transcript-grounded hook + payoff-aware boundaries.
    ai_choice = None
    if start is None and url:
        from smart_hooks import select
        ai_choice = select(url, info, WORK)
        if not ai_choice:
            print("  No suitable transcript-grounded clip; leave it for human review")
            return []
        start, end = ai_choice["start"], ai_choice["end"]
        hook = hook or ai_choice["hook"]
    if start is not None:
        end = end if end is not None else start + CFG["max_clip_sec"]'''
    after=replace_once(after,old,new,"auto moment selection")
    after=replace_once(after,'        meta["file"] = out.name',
        '''        meta["hook"] = hook or ""
        meta["start"] = s
        meta["end"] = e
        if ai_choice:
            meta["ai_selection"] = ai_choice
        meta["file"] = out.name''',"persist selection metadata")
    oldgate='''        if not (r.get("hook") or "").strip():
            print(f"  HOLD (needs a specific hook): {r.get('title')}")
            continue
'''
    if oldgate in after:
        after=after.replace(oldgate,"",1)
    oldcall='        try:\n            res = make_clip(r["url"]'
    newcall='''        if not (r.get("start") or "").strip() and not os.getenv("OPENAI_API_KEY"):
            print(f"  HOLD (AI key missing; needs OPENAI_API_KEY or start/end): {r.get('title')}")
            continue
        try:
            res = make_clip(r["url"]'''
    # Avoid duplicate hold if a prior installer partially modified code.
    if 'AI key missing; needs OPENAI_API_KEY' not in after:
        after=replace_once(after,oldcall,newcall,"AI credential guard")
    oldmeta='            r["clip_file"] = "; ".join(x["file"] for x in res)'
    newmeta='''            if res:
                r["hook"] = r.get("hook") or res[0].get("hook", "")
                r["start"] = str(res[0].get("start", ""))
                r["end"] = str(res[0].get("end", ""))
            r["clip_file"] = "; ".join(x["file"] for x in res)'''
    if newmeta not in after:
        after=replace_once(after,oldmeta,newmeta,"backlog generated hook/point sync")
    if not re.search(r"(?m)^max_clip_sec:\\s*22\\s*$",cfg):
        raise RuntimeError("Expected max_clip_sec: 22, refusing to change unknown config")
    cfg=re.sub(r"(?m)^(max_clip_sec:\\s*)22(?=\\s*$)",r"\\g<1>30",cfg,count=1)
    ast.parse(after)
    src=Path(__file__).with_name("smart_hooks.py")
    if not src.is_file():
        raise RuntimeError("smart_hooks.py missing beside installer")
    if not (folder/"clip.py.pre-v3.bak").exists():
        shutil.copy2(path,folder/"clip.py.pre-v3.bak")
    if not (folder/"config.yaml.pre-v3.bak").exists():
        shutil.copy2(cfgpath,folder/"config.yaml.pre-v3.bak")
    shutil.copy2(src,folder/"smart_hooks.py")
    path.write_text(after,encoding="utf-8")
    cfgpath.write_text(cfg,encoding="utf-8")
    print("Installed v3 into",folder)
    print("Manual --start/--end remains supported; automated clips target 12-30 seconds")

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--target",type=Path,required=True)
    install(parser.parse_args().target)
