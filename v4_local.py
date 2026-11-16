"""V4 local-first moment ranking. No API calls, no paid models, no uploads.

Requires existing smart_hooks.py. Optional OpenCV adds motion; ffmpeg adds
audio energy. When only a VTT is supplied, reports transcript-only evidence.
"""
import argparse
import json
import math
import re
import shutil
import subprocess
from pathlib import Path

from smart_hooks import build_windows, parse_vtt

EVENTS = {
    "crash": 3, "crashed": 3, "explosion": 3, "explode": 3,
    "police": 2, "cop": 2, "cops": 2, "chase": 2, "arrest": 2,
    "npc": 1.5, "glitch": 2, "ragdoll": 3, "dead": 2,
    "what": 1, "why": 1, "how": 1, "wait": 2,
    "no": 1.5, "oh": 1, "wow": 2, "look": 1,
    "run": 1, "help": 2, "crazy": 2, "insane": 2,
}
QUESTION = re.compile(r"\?|\b(wait|what|why|how|look|watch|imagine)\b", re.I)
AD = re.compile(r"\b(sponsor|subscribe|use my code|discount code|patreon|merch|giveaway)\b", re.I)
STOP = {"the", "and", "for", "you", "that", "this", "with", "was", "are", "but", "not", "have", "from", "they", "what"}
def clamp(x):
    return max(0.0, min(1.0, float(x)))

def normalized_activity(values, seconds, start, end):
    """Average per-second measured activity with robust within-video scaling."""
    if not values:
        return 0.0
    selected = [v for t, v in zip(seconds, values) if start <= t < end]
    if not selected:
        return 0.0
    ordered = sorted(values)
    base = ordered[len(ordered)//2]
    top = ordered[min(len(ordered)-1, int(.95 * (len(ordered)-1)))]
    if top <= base + 1e-9:
        return 0.0
    return clamp((max(selected) - base) / (top - base))

def audio_activity(video, sample_rate=8000, hop=.5):
    """Decode mono PCM through ffmpeg and measure windowed RMS, in seconds."""
    if not shutil.which("ffmpeg"):
        return [], []
    import array
    cmd = ["ffmpeg", "-v", "error", "-i", str(video), "-vn",
           "-ac", "1", "-ar", str(sample_rate), "-f", "s16le", "-"]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except OSError:
        return [], []
    chunk = int(sample_rate*hop)*2
    times, levels = [], []
    try:
        index=0
        while True:
            raw=proc.stdout.read(chunk)
            if len(raw) < 2:
                break
            arr=array.array("h")
            arr.frombytes(raw[:len(raw)//2*2])
            if not arr:
                break
            rms=math.sqrt(sum(v*v for v in arr)/len(arr))/32768
            levels.append(math.log1p(rms*100))
            times.append(index*hop)
            index += 1
    finally:
        if proc.stdout:
            proc.stdout.close()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
    return times, levels

def motion_activity(video, interval=1.0):
    """Sparse grayscale frame differences, optional OpenCV dependency."""
    try:
        import cv2
    except ImportError:
        return [], []
    capture=cv2.VideoCapture(str(video))
    if not capture.isOpened():
        return [], []
    times, values=[], []
    last=None
    t=0.0
    try:
        while True:
            capture.set(cv2.CAP_PROP_POS_MSEC, t*1000)
            ok, frame=capture.read()
            if not ok:
                break
            small=cv2.resize(frame, (160, 90))
            gray=cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
            if last is not None:
                values.append(float(cv2.absdiff(last, gray).mean()))
                times.append(t)
            last=gray
            t+=interval
    finally:
        capture.release()
    return times, values

def text_signals(window):
    text=window["excerpt"]
    words=re.findall(r"[a-z']+", text.lower())
    event=sum(EVENTS.get(w, 0) for w in words)
    opening=" ".join(words[:18])
    ending=" ".join(words[-30:])
    first=clamp((int(bool(QUESTION.search(opening))) * .55 + sum(EVENTS.get(w, 0) for w in words[:15])*.07))
    payoff=clamp((sum(EVENTS.get(w, 0) for w in re.findall(r"[a-z']+", ending))*.075
                  + .2*int("!" in text[-160:] or "?" in text[-160:])))
    density=clamp(len(words)/max(1, window["end"]-window["start"])/3.4)
    event_score=clamp(event/12)
    return first, payoff, density, event_score, bool(AD.search(text))

def make_hook(window):
    """Extract an attributed excerpt rather than invent a GTA gameplay claim."""
    excerpt=re.sub(r"\s+", " ", window["excerpt"]).strip()
    sentences=re.split(r"(?<=[.!?])\s+", excerpt)
    lead=next((s for s in sentences if QUESTION.search(s) and len(s)>=12), sentences[0])
    lead=lead.strip().strip('"')
    if len(lead)>82:
        lead=lead[:79].rsplit(" ",1)[0]+"..."
    if len(lead)<12:
        lead=(excerpt[:82].rsplit(" ",1)[0]).strip()
    return lead

def rank(cues, duration, video=None, limit=5):
    """Rank non-overlapping validated VTT windows, retaining evidence/limitations."""
    windows=build_windows(cues, duration, limit=240)
    if not windows:
        return []
    at, av = audio_activity(video) if video else ([], [])
    mt, mv = motion_activity(video) if video else ([], [])
    results=[]
    for w in windows:
        hook, payoff, density, event, ad = text_signals(w)
        audio=normalized_activity(av, at, w["start"], w["end"])
        motion=normalized_activity(mv, mt, w["start"], w["end"])
        # Renormalize only available signals; absence is not evidence of low activity.
        weights={"hook":25,"payoff":20,"speech":10,"event":15,"duration":5}
        if av: weights["audio"]=15
        if mv: weights["motion"]=10
        score=(25*hook+20*payoff+10*density+15*event
               +5*clamp(1-abs((w["end"]-w["start"])-20)/20)
               + (15*audio if av else 0)+(10*motion if mv else 0))
        score=100*score/sum(weights.values())
        if ad: score*=.25
        results.append({
            "start":w["start"],"end":w["end"],"hook":make_hook(w),
            "captions":w["excerpt"],"payoff":w["payoff"],
            "score":round(score,2),"evidence":{
                "hook":round(hook,3),"payoff":round(payoff,3),
                "speech":round(density,3),"event":round(event,3),
                "audio":round(audio,3) if av else None,
                "motion":round(motion,3) if mv else None,
                "sponsor_penalty":ad
            },
            "verification":"transcript+audio+motion" if av and mv else (
                "transcript+audio" if av else "transcript+motion" if mv else "transcript-only")
        })
    # Greedy non-overlap and diversity: no identical moments in the top five.
    chosen=[]
    for candidate in sorted(results, key=lambda r:(-r["score"],r["start"])):
        overlap=any(max(0,min(candidate["end"],p["end"])-max(candidate["start"],p["start"]))>2
                    for p in chosen)
        if not overlap:
            chosen.append(candidate)
        if len(chosen)>=limit:
            break
    return chosen

def select(url, info, work, video=None):
    """Backwards-compatible single-hook adapter; caller decides whether to use."""
    from smart_hooks import fetch_vtt
    path=fetch_vtt(url,work)
    if path is None:
        return None
    cues=parse_vtt(path.read_text(encoding="utf-8-sig"))
    picks=rank(cues,float(info.get("duration") or 0),video=video,limit=1)
    return picks[0] if picks else None

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--vtt",type=Path,required=True)
    parser.add_argument("--duration",type=float,required=True)
    parser.add_argument("--video",type=Path,help="Local video path; no network download")
    parser.add_argument("--limit",type=int,default=5)
    parser.add_argument("--out",type=Path)
    args=parser.parse_args()
    if args.video and not args.video.is_file():
        parser.error("Video does not exist")
    cues=parse_vtt(args.vtt.read_text(encoding="utf-8-sig"))
    output={"engine":"v4-local","candidates":rank(cues,args.duration,args.video,max(1,args.limit))}
    rendered=json.dumps(output,indent=2,ensure_ascii=False)
    if args.out:
        args.out.write_text(rendered+"\n",encoding="utf-8")
    print(rendered)

if __name__=="__main__":
    main()
