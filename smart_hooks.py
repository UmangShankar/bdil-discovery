"""Transcript-grounded automatic hooks for private GTA Shorts drafts."""
import argparse
import html
import json
import os
import re
from pathlib import Path

import requests

TIME = re.compile(r"(\d\d:\d\d:\d\d[.,]\d+)\s+-->\s+(\d\d:\d\d:\d\d[.,]\d+)")
TAG = re.compile(r"<[^>]+>")

def sec(v):
    h, m, s = v.replace(",", ".").split(":")
    return 3600*int(h) + 60*int(m) + float(s)

def parse_vtt(content):
    """Convert YouTube's rolling captions into non-overlapping speech cues.

    Auto-VTT repeats the previous line and inserts 10-ms hold frames.
    The timestamp line can also contain alignment settings; these aren't
    narration. Extract genuinely new words and preserve their cue timing.
    """
    cues, previous_words = [], []
    for part in re.split(r"\n\s*\n", content.replace("\r\n", "\n")):
        lines = part.strip().splitlines()
        index = next((i for i, line in enumerate(lines) if TIME.search(line)), None)
        if index is None:
            continue
        match = TIME.search(lines[index])
        a, b = sec(match[1]), sec(match[2])
        if b - a < 0.12:
            continue
        speech = html.unescape(TAG.sub("", " ".join(lines[index + 1:])))
        words = re.sub(r"\s+", " ", speech).strip().split()
        if not words:
            continue
        overlap = 0
        for n in range(1, min(len(words), len(previous_words)) + 1):
            if [w.lower() for w in previous_words[-n:]] == [w.lower() for w in words[:n]]:
                overlap = n
        fresh = words[overlap:]
        if fresh:
            cues.append({"start": round(a, 2), "end": round(b, 2), "text": " ".join(fresh)})
        previous_words = words
    return cues

def fetch_vtt(url, work):
    import yt_dlp
    folder=Path(work)/"transcripts"
    folder.mkdir(parents=True,exist_ok=True)
    name=re.sub(r"[^a-zA-Z0-9_-]","_",url.split("v=")[-1].split("&")[0])[:72]
    files=sorted(folder.glob(name+".en*.vtt"))
    if files:
        return files[0]
    opts={"quiet":True,"skip_download":True,"writesubtitles":True,
          "writeautomaticsub":True,"subtitleslangs":["en-orig"],
          "subtitlesformat":"vtt","outtmpl":str(folder/name)+".%(ext)s"}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
    except Exception as exc:
        print("  Subtitle retrieval problem:",str(exc)[:160])
    files=sorted(folder.glob(name+".en*.vtt"))
    return files[0] if files else None

def validate(candidate,cues,duration):
    """Reject invalid edits; align payoff against timestamps if model cue ID drifts."""
    if not isinstance(candidate, dict) or candidate.get("skip"):
        return None
    try:
        a, b = float(candidate["start"]), float(candidate["end"])
        hook = str(candidate["hook"]).strip()
    except (KeyError, TypeError, ValueError):
        print("  Validation: missing start, end or hook")
        return None
    if not (0 <= a < b <= duration and 12 <= b-a <= 30):
        print(f"  Validation: invalid clip duration/bounds ({a:.2f}-{b:.2f})")
        return None
    if not (12 <= len(hook) <= 85) or "\n" in hook:
        print("  Validation: invalid hook length or formatting")
        return None
    if not cues:
        return None
    inside = [(i, cue) for i, cue in enumerate(cues)
              if a <= cue["start"] and cue["end"] <= b + .75]
    if not inside:
        print("  Validation: no timed captions inside proposed window")
        return None
    # Model index is a hint, not an authority: verify the actual timed payoff.
    try:
        i = int(candidate["payoff_cue"])
    except (KeyError, TypeError, ValueError):
        i = -1
    if not (0 <= i < len(cues) and a <= cues[i]["start"] < b
            and cues[i]["end"] <= b + .75 and b - cues[i]["end"] <= 3):
        i = inside[-1][0]
    payoff = cues[i]
    if b - payoff["end"] > 3 or payoff["end"] > b + .75:
        print("  Validation: payoff not close to clip ending")
        return None
    if not re.search(r"[.!?][\"']?$", payoff["text"]):
        print("  Validation: clip doesn't end at a sentence boundary")
        return None
    return {"start": round(a, 2), "end": round(b, 2), "hook": hook,
            "payoff_cue": i, "payoff": payoff["text"],
            "reason": str(candidate.get("reason", ""))[:220]}

def propose(cues,duration,title):
    sample=" ".join(x["text"] for x in cues[:150])
    letters=[c for c in sample if c.isalpha()]
    if len(cues)<8 or not letters or sum(c.isascii() for c in letters)/len(letters)<.92:
        print("  No suitable English subtitle track")
        return None
    key=os.getenv("OPENAI_API_KEY","").strip()
    if not key:
        print("  OPENAI_API_KEY is missing; use manual timestamps or configure API key")
        return None
    transcript="\n".join(f"{i}|{x['start']:.2f}-{x['end']:.2f}|{x['text']}" for i,x in enumerate(cues))
    if len(transcript)>90000:
        print("  Transcript too large for reliable automatic selection")
        return None
    instruction=("Select ONE compelling self-contained GTA video moment of 12-30 seconds, "
       "using ONLY timestamped captions, not imagined video frames. Require setup, change and payoff. "
       "Keep entire payoff sentence, with 0.3 seconds breathing room, no mid-sentence cuts. "
       "Reject ad reads, empty hype, spoilers, unsupported confirmed-feature claims. "
       "Speculative content must use speculative hook language. If no suitable moment, return "
       "{\"skip\":true}. Otherwise respond with JSON fields start, end, hook, payoff_cue "
       "(zero-based index of the transcript cue with the payoff), reason. "
       "IMPORTANT: The selected final payoff cue must end in a full stop, "
       "question mark or exclamation mark, and end must equal that cue's "
       "end timestamp plus approximately 0.3 seconds. Avoid cut-off sentences. "
       f"Title: {title}; duration: {duration}\nTranscript:\n{transcript}")
    try:
        r=requests.post("https://api.openai.com/v1/chat/completions",timeout=100,
            headers={"Authorization":"Bearer "+key},
            json={"model":os.getenv("BDIL_AI_MODEL","gpt-4o-mini"),
                  "response_format":{"type":"json_object"},
                  "messages":[{"role":"system","content":"Return only valid JSON. Ground every claim in the transcript."},
                              {"role":"user","content":instruction}]})
        r.raise_for_status()
        result=json.loads(r.json()["choices"][0]["message"]["content"])
        chosen=validate(result,cues,duration)
        if not chosen:
            print("  AI candidate failed payoff/duration checks; skipping")
        return chosen
    except (ValueError,KeyError,requests.RequestException) as exc:
        print("  AI request failed:",str(exc)[:180])
        return None

def select(url,info,work):
    path=fetch_vtt(url,work)
    if not path:
        print("  No English subtitles; no AI clip selected")
        return None
    cues=parse_vtt(path.read_text(encoding="utf-8-sig"))
    result=propose(cues,float(info.get("duration") or 0),info.get("title",""))
    if result:
        print(f"  AI selected {result['start']}-{result['end']}: {result['hook']}")
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--vtt",type=Path,required=True)
    p.add_argument("--duration",type=float,required=True)
    p.add_argument("--title",default="GTA 6 video")
    args=p.parse_args()
    result=propose(parse_vtt(args.vtt.read_text(encoding="utf-8-sig")),args.duration,args.title)
    print(json.dumps(result or {"skip":True},indent=2))
