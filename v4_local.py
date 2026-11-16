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
AD = re.compile(r"\b(sponsor|subscribe|subscription|like and subscribe|drop a like|thank you.*watching|use my code|discount code|patreon|merch|giveaway)\b", re.I)
# A subject (NPC/police/traffic) is not evidence of an event. Reactions alone
# are not evidence either: a usable transcript-only clip needs an occurrence.
OBSERVED_EVENT = re.compile(
    r"\b(crash(?:ed|es|ing)?|explod(?:ed|es|ing)|explosion|"
    r"glitch(?:ed|es|ing)?|ragdoll(?:ed)?|arrest(?:ed|s|ing)?|"
    r"bust(?:ed|s)?|collid(?:ed|es|ing)|wreck(?:ed|s)?|"
    r"fell|fall(?:s|ing)?|flew|launched|hit|hits|"
    r"killed|escaped|chased|shot|shoot(?:s|ing)?|"
    r"caught|stole|steal(?:s|ing)?)\b", re.I)
# This filter is deliberately conservative for transcript-only discovery.
# Gameplay predictions and trailer breakdowns are not observed gaming events.
SPECULATION = re.compile(
    r"\b(going to|will be|would be|might|could be|we expect|"
    r"we won't|trailer|rockstar will|rockstar is going to|"
    r"release date|prediction|rumou?r|theory|I.d bet|never confirmed|reportedly|former.*developer says)\b", re.I)

HISTORICAL_CONTEXT = re.compile(
    r"\b(since 2008|since 20\d\d|years? later|back in 20\d\d|"
    r"pandemic|full production|rockstar's own engine|the first game|"
    r"reportedly|red dead redemption cleaned up)\b", re.I)
DIRECT_EVENT = re.compile(
    r"\b(crash(?:ed|es|ing)?|explod(?:ed|es|ing)|explosion|"
    r"glitch(?:ed|es|ing)?|ragdoll(?:ed)?|arrest(?:ed|s|ing)?|"
    r"collid(?:ed|es|ing)|wreck(?:ed|s)?|fell|flew|launched|"
    r"killed|escaped|chased|shot|shoot(?:s|ing)?|caught|stole)\b", re.I)

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
    from v4_media import audio
    times,values,stage = audio(video)
    return (times,values) if stage['status']=='ok' else ([],[])


def motion_activity(video, interval=1.):
    from v4_media import frames
    times,values,_,stage = frames(video,interval)
    return (times,values) if stage['status']=='ok' else ([],[])


def ffmpeg_motion_activity(video, interval=1.0):
    """Compatibility with the concurrently added explicit FFmpeg adapter."""
    from v4_media import frames
    times,values,_,stage = frames(video,interval,force_ffmpeg=True)
    return (times,values) if stage['status']=='ok' else ([],[])


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

# Semantic rules propose review candidates; they cannot recognize depicted events.
GAME = re.compile(r"\b(gta|grand theft auto|rockstar|npc|euphoria|vice city|red dead|ammunition)\b", re.I)
REACTION = re.compile(r"\b(wait|what just happened|oh no|wow|insane|can't believe|help)\b", re.I)
OUTCOME = re.compile(r"\b(escaped|exploded|crashed|caught|dead|won|lost|back to|turned out|finally|instead|because|means|so that|that's why)\b", re.I)
INSIGHT = re.compile(r"\b(because|instead of|compared|unlike|means|that's why|times more|more than|fewer than|difference|first game|on the fly|so people|so you|only when)\b", re.I)
HISTORICAL = re.compile(r"\b(pandemic|court|bail|hospital|hacked|royalties|settlement|rerated)\b", re.I)
FRAGMENT = re.compile(r"^(and|but|so|then|they|it|his|her|this time|that dog|in his words)\b", re.I)


def sentence_windows(cues, duration):
    """Enumerate complete sentence groups, retaining source cue timestamps.

    VTT mid-cue splits are estimates from the existing parser, not word alignment.
    No duration-based shortlist is applied before content scoring.
    """
    sentences, pending = [], []
    previous_end = -1.
    for c in cues:
        try:
            a, b = float(c['start']), float(c['end'])
            text = re.sub(r'\[.*?\]', '', c['text']).strip()
        except (KeyError, TypeError, ValueError):
            continue
        if not (math.isfinite(a) and math.isfinite(b) and 0 <= a < b <= duration):
            continue
        if a < previous_end - .05:
            continue
        previous_end = b
        if not text:
            continue
        pending.append({'start':a, 'end':b, 'text':text})
        if re.search(r'[.!?]["\']?$', text):
            sentences.append({'start':pending[0]['start'], 'end':b,
                              'text':' '.join(x['text'] for x in pending)})
            pending = []
    windows = []
    for i, first in enumerate(sentences):
        for j in range(i, len(sentences)):
            last = sentences[j]
            end = min(duration, last['end']+.25)
            if end-first['start'] > 30:
                break
            if end-first['start'] < 12:
                continue
            group = sentences[i:j+1]
            if len(group) < 2 or any(y['start']-x['end'] > 2 for x,y in zip(group, group[1:])):
                continue
            windows.append({'start':first['start'], 'end':end,
                            'excerpt':' '.join(x['text'] for x in group),
                            'opening':first['text'], 'payoff':last['text'],
                            'sentences':len(group)})
    return windows


TOPICS = [
    re.compile(r'\b(npcs?|pedestrians?|crowds?|bodies|body|sizes?|heights?|animations?|characters?)\b', re.I),
    re.compile(r'\b(physics|euphoria|stumble|falling|ragdoll)\b', re.I),
    re.compile(r'\b(engine|table tennis|technology)\b', re.I),
    re.compile(r'\b(developers?|studios?|production|development|years|crunch|contractors?|jobs)\b', re.I),
    re.compile(r'\b(cops?|police|gun|shotgun|ammunition|crime|alarm)\b', re.I),
    re.compile(r'\b(houses?|rooms?|lives|photos|table)\b', re.I),
    re.compile(r'\b(online|expansions?|money|bookings|billion|million)\b', re.I),
]


def discover(cues, duration, video=None, limit=5, media=None):
    import time
    from v4_media import analyse
    started = time.monotonic()
    media = analyse(video) if media is None else media
    if 'probe' in media:
        duration = media['probe']['duration']
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError('duration must be finite and positive')
    limit = max(0, min(5, int(limit)))
    stages = {k:media[k] for k in ('audio','motion','scene')}
    stages['transcript'] = {'status':'ok' if cues else 'unavailable', 'cues':len(cues)}
    coverage = sum(stages[k]['status']=='ok' for k in stages)/4
    results, rejected = [], []
    for w in sentence_windows(cues, duration):
        text, opening, ending = w['excerpt'], w['opening'], w['payoff']
        reasons = []
        reaction = bool(REACTION.search(opening))
        occurrence = bool(DIRECT_EVENT.search(text)) and not (HISTORICAL.search(text) or HISTORICAL_CONTEXT.search(text))
        insight = bool(INSIGHT.search(ending)) and bool(GAME.search(text))
        comparison = bool(re.search(r'\d',text) and INSIGHT.search(text) and GAME.search(text))
        topic_link = any(t.search(opening) and t.search(ending) for t in TOPICS)
        educational = (insight or (comparison and bool(re.search(r'\d',ending)))) and topic_link
        strong_opening = bool(QUESTION.search(opening) or INSIGHT.search(opening)
                              or re.search(r'\b(older|first|different|secret|hidden|never)\b',opening,re.I))
        if educational and not strong_opening:
            reasons.append('educational opening lacks a specific curiosity gap')
        action = reaction and occurrence and bool(OUTCOME.search(ending) or OBSERVED_EVENT.search(ending))
        if AD.search(text): reasons.append('promotion/outro')
        if SPECULATION.search(text): reasons.append('speculation or trailer commentary')
        if FRAGMENT.search(opening) or re.match(r"^(you (?:won't|would|will)|here|[0-9]+ times)\b",opening,re.I): reasons.append('dependent opening')
        if not (action or educational): reasons.append('no grounded event-resolution or educational insight')
        if len(opening.split()) < 5 and not reaction: reasons.append('opening lacks context')
        if reasons:
            rejected.append({'start':w['start'], 'end':w['end'], 'reasons':reasons, 'excerpt':text})
            continue
        hook = .85 if reaction or QUESTION.search(opening) else .72 if INSIGHT.search(opening) else .55
        story = .75  # complete linked sentences; extra narration earns no reward
        payoff = .9 if action else .85 if insight else .72
        relevance = .9 if GAME.search(text) else .55
        audio = normalized_activity(media['audio_values'],media['audio_times'],w['start'],w['end']) if stages['audio']['status']=='ok' else 0.
        motion = normalized_activity(media['motion_values'],media['motion_times'],w['start'],w['end']) if stages['motion']['status']=='ok' else 0.
        # Fixed denominator: unavailable evidence never inflates the score.
        retention = (hook+story+payoff)/3
        score = 22*hook+18*story+24*payoff+10*relevance+4*audio+4*motion+8*.8+6*retention+4*.5
        if score < 65 or hook < .55 or payoff < .7:
            rejected.append({'start':w['start'],'end':w['end'],'reasons':['quality threshold'], 'score':round(score,2)})
            continue
        results.append({'start':round(w['start'],3),'end':round(w['end'],3),
            'duration':round(w['end']-w['start'],3),'hook':make_hook({**w,'excerpt':opening}),
            'captions':text,'category':'gameplay_action' if action else 'mechanics_comparison' if comparison else 'news_explainer',
            'score':round(score,2),'overall_score':round(score,2),
            'hook_score':round(hook*100,2),'story_score':round(story*100,2),'payoff_score':round(payoff*100,2),
            'audience_relevance_score':round(relevance*100,2),'retention_score':round(retention*100,2),
            'audio_score':round(audio*100,2),'video_score':round(motion*100,2),
            'boundary_score':80,'originality_score':50,
            'diversity':'non-overlap plus transcript Jaccard <=0.65',
            'payoff':ending,'actual_payoff':ending,
            'confidence':round(.4+.35*coverage,3),'verification_coverage':coverage,
            'verification': ('transcript-only' if not any(stages[k]['status']=='ok' for k in ('audio','motion')) else 'transcript') + ('+audio' if stages['audio']['status']=='ok' else '') + ('+motion' if stages['motion']['status']=='ok' else ''),
            'review_required':True,'semantic_verified':False,
            'reason_for_selection':'Transcript reaction with resolved event' if action else 'Transcript contains a specific explanatory or comparative payoff',
            'evidence':{'hook':hook,'story':story,'payoff':payoff,'audio':audio,'motion':motion,
                        'boundaries':'complete transcript sentences; cue timing estimate',
                        'scene_transition_proposals':[t for t in media['scene_times'] if w['start'] <= t < w['end']],
                        'originality':.5, 'originality_note':'unknown; neutral prior, no corpus comparison'},
            'limitations':['No local semantic vision model; footage/title agreement requires review',
                           'Caption timing is not frame/word aligned']})
    chosen = []
    def words(p):
        return set(re.findall(r"[a-z]+",p['captions'].lower()))-STOP
    for candidate in sorted(results,key=lambda x:(-x['score'],x['duration'],x['start'])):
        duplicate = any(max(candidate['start'],p['start']) < min(candidate['end'],p['end']) or
                        len(words(candidate)&words(p))/max(1,len(words(candidate)|words(p))) > .65 for p in chosen)
        if duplicate or len(chosen)>=limit:
            rejected.append({'start':candidate['start'],'end':candidate['end'],
                             'reasons':['overlap/duplicate' if duplicate else 'rank limit']})
        else:
            chosen.append({**candidate,'rank':len(chosen)+1})
    return {'schema_version':1,'engine':'v4-local','duration':duration,'candidates':chosen,
            'rejected':rejected,'window_count':len(sentence_windows(cues,duration)),
            'no_candidates_reason':None if chosen else ('no complete 12-30s multi-sentence windows' if not results and not rejected else 'all candidates rejected or limit is zero'),
            'stages':stages,'api_cost_usd':0,
            'processing_seconds':round(time.monotonic()-started,3),
            'limitations':['Heuristic ranking; candidate acceptance means selected for review, not publication approval']}


def rank(cues, duration, video=None, limit=5):
    return discover(cues,duration,video,limit)['candidates']


def select(url, info, work, video=None):
    from smart_hooks import fetch_vtt
    path=fetch_vtt(url,work)
    if path is None:
        return None
    picks=rank(parse_vtt(path.read_text(encoding='utf-8-sig')),float(info.get('duration') or 0),video,1)
    return picks[0] if picks else None


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vtt',type=Path)
    parser.add_argument('--duration',type=float,help='Required only without media; media duration uses FFprobe')
    parser.add_argument('--video',type=Path)
    parser.add_argument('--limit',type=int,default=5)
    parser.add_argument('--out',type=Path,default=Path('candidates.json'))
    parser.add_argument('--previews',type=Path)
    parser.add_argument('--source-url',default='')
    parser.add_argument('--whisper-model',help='Optional local/cached faster-whisper model; no model downloads')
    parser.add_argument('--transcript-cache',type=Path)
    parser.add_argument('--evidence-cache',type=Path,help='Reusable media measurements, checked against media size/mtime')
    args=parser.parse_args()
    import time
    run_started=time.monotonic()
    from v4_media import probe
    try:
        duration = probe(args.video)['duration'] if args.video else args.duration
        if duration is None:
            parser.error('--video or --duration required')
        cues = parse_vtt(args.vtt.read_text(encoding='utf-8-sig')) if args.vtt and args.vtt.is_file() else []
        transcript_stage = None
        signature = {'path':str(args.video.resolve()),'size':args.video.stat().st_size,
                     'mtime_ns':args.video.stat().st_mtime_ns,'analysis_version':2} if args.video else None
        if not cues and args.whisper_model and args.video:
            from v4_transcript import transcribe
            transcript_signature = {'source':signature,'model':args.whisper_model,'filter_version':2}
            cached_transcript = json.loads(args.transcript_cache.read_text()) if args.transcript_cache and args.transcript_cache.is_file() else {}
            if cached_transcript.get('signature') == transcript_signature:
                cues,transcript_stage = cached_transcript['cues'],cached_transcript['stage']
            else:
                try:
                    cues,transcript_stage = transcribe(args.video,args.whisper_model)
                except (ImportError,OSError,RuntimeError,ValueError) as exc:
                    transcript_stage = {'status':'failed','method':'faster-whisper','reason':str(exc)[:300]}
                if args.transcript_cache:
                    args.transcript_cache.parent.mkdir(parents=True,exist_ok=True)
                    args.transcript_cache.write_text(json.dumps({'signature':transcript_signature,'cues':cues,'stage':transcript_stage}))
        media = None
        if args.evidence_cache and args.evidence_cache.is_file():
            cached = json.loads(args.evidence_cache.read_text())
            if cached.get('source') == signature:
                media = cached['media']
        if media is None:
            from v4_media import analyse
            media = analyse(args.video)
            if args.evidence_cache:
                args.evidence_cache.parent.mkdir(parents=True,exist_ok=True)
                args.evidence_cache.write_text(json.dumps({'source':signature,'media':media},allow_nan=False))
        output = discover(cues,duration,args.video,args.limit,media=media)
        if transcript_stage:
            output['stages']['transcript']=transcript_stage
        output['source_url'] = args.source_url
        output['source_video'] = str(args.video.resolve()) if args.video else None
        if args.previews and args.video:
            from v4_handoff import previews
            output['previews'] = previews(args.video,output['candidates'],args.previews,duration)
        output['processing_seconds']=round(time.monotonic()-run_started,3)
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(json.dumps(output,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')
        print(json.dumps({k:output[k] for k in ('engine','duration','stages','processing_seconds','api_cost_usd')}))
        print(f"{len(output['candidates'])} review candidates; {len(output['rejected'])} rejected; {args.out}")
    except (ValueError,OSError,subprocess.SubprocessError) as exc:
        parser.exit(2,f'V4 failed: {exc}\n')

if __name__=='__main__':
    main()
