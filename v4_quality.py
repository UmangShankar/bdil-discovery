"""Fail-closed ending checks shared by automatic and editorial V4 clips.

These are conservative language/timing checks, not semantic understanding.
The final export still needs a documented review of its actual resolution.
"""
import math
import re


TRAILING_WORDS = {
    'and', 'but', 'or', 'because', 'so', 'if', 'when', 'while', 'unless',
    'until', 'although', 'whereas', 'since', 'which', 'with',
    'without', 'to', 'from', 'than', 'then', 'also', 'however', 'therefore',
    'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
    'have', 'has', 'had', 'can', 'could', 'would', 'should', 'will', 'may',
    'might', 'must', "that's", "it's", "there's", "here's",
}
TRAILING_PHRASE = re.compile(
    r"\b(such as|for example|which means|that means|that's why|this is why|here's why|and then|"
    r"in order to|as well as|going to|there is|there are|kind of|sort of|"
    r"because of|as a result of|in front of|due to|as if|even if|rather than|so that)\W*$", re.I)
UNRESOLVED = re.compile(
    r"\b(to be continued|hold that thought|wait for it|we(?:'ll| will) find out|"
    r"let(?:'s| us) see what happens|we(?:'ll| will) see|find out next time|"
    r"what happens next|something is about to happen|the real answer comes later)\b", re.I)
HYPE_ONLY = re.compile(
    r"^(?:oh\s+)?(?:wow|no way|crazy|insane|unbelievable|that(?:'s| is| was) (?:crazy|insane|wild|amazing)|"
    r"i can(?:not|'t) believe (?:it|that)|you won't believe (?:it|that)|"
    r"i (?:guess|don't know)|who knows)\W*$", re.I)


def sentences(text):
    text = re.sub(r'\[[^\]]*\]', '', str(text)).strip()
    return [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]


def ending_reasons(text, require_punctuation=True):
    """Punctuation alone cannot make '...but.' a complete ending."""
    cleaned = re.sub(r'\[[^\]]*\]', '', str(text)).strip().replace('\u2019', "'")
    words = re.findall(r"[a-z]+(?:'[a-z]+)?", cleaned.lower())
    reasons = []
    if not words:
        return ['no spoken ending to verify']
    if words[-1] in TRAILING_WORDS or TRAILING_PHRASE.search(cleaned):
        reasons.append('unfinished connective or dependent phrase at cut')
    if re.search(r'(?:\.{2,}|\u2026|[-\u2013\u2014])\s*[\"\u201d\u2019\']?$', cleaned):
        reasons.append('trailing ellipsis or interrupted sentence')
    elif require_punctuation and not re.search(r'[.!?][\"\u201d\u2019\']?$', cleaned):
        reasons.append('no complete sentence ending')
    return reasons


def payoff_reasons(text, require_punctuation=True):
    """Reject a dangling hook, promised answer or hype-only final sentence."""
    parts = sentences(text)
    if not parts:
        return ['no identifiable payoff']
    final = parts[-1]
    reasons = ending_reasons(final, require_punctuation=require_punctuation)
    if re.search(r'\?[!?]*[\"\u201d\u2019\']?$', final):
        reasons.append('ending asks a question instead of resolving it')
    if UNRESOLVED.search(final):
        reasons.append('payoff deferred beyond the clip')
    if HYPE_ONLY.fullmatch(final.replace('\u2019', "'")):
        reasons.append('generic reaction without a specific final resolution')
    return reasons


def audit_words(words, duration, payoff=None, min_tail=.12):
    """Inspect actual exported speech, including leaked next-sentence words.

    Tail clearance is a conservative risk gate using estimated ASR word timing;
    it is not a guarantee of sample-accurate alignment.
    """
    reasons = []
    valid = []
    for w in words:
        try:
            a, b = float(w['start']), float(w['end'])
            text = w['word'].strip()
        except (KeyError, TypeError, ValueError, AttributeError):
            reasons.append('invalid exported word timing')
            continue
        if not (math.isfinite(a) and math.isfinite(b) and 0 <= a <= b <= duration + .05):
            reasons.append('exported word lies outside media duration')
            continue
        if text:
            valid.append({'start': a, 'end': b, 'word': text})
    if not valid:
        reasons.append('no exported speech could be verified')
        return {'passed': False, 'reasons': list(dict.fromkeys(reasons)), 'method': 'local ASR word timing'}
    if any(b['start'] < a['start'] for a, b in zip(valid, valid[1:])):
        reasons.append('exported word timings are out of order')
    actual = ' '.join(w['word'] for w in valid)
    # ASR often drops punctuation from a genuinely complete sentence. Only
    # reconcile that omission when the exported audio ends in the reviewed
    # payoff's exact lexical suffix; never invent a full stop to pass a cut.
    reasons.extend(payoff_reasons(actual, require_punctuation=False))
    matched_payoff = False
    if payoff is not None:
        reasons.extend(payoff_reasons(payoff))
        def tokens(text):
            return re.findall(r"[a-z]+(?:'[a-z]+)?", str(text).lower().replace('\u2019', "'"))
        expected = tokens(sentences(payoff)[-1]) if sentences(payoff) else []
        observed = tokens(actual)
        suffix = ''.join(expected[-min(4, len(expected)):])
        matched_payoff = bool(suffix) and ''.join(observed[-10:]).endswith(suffix)
        if not matched_payoff:
            reasons.append('export does not end on the reviewed payoff; re-check the cut')
    elif ending_reasons(actual):
        reasons.append('unpunctuated export ending needs a matching reviewed payoff')
    clearance = duration - valid[-1]['end']
    if clearance < min_tail:
        reasons.append('final spoken word touches cut; extend to a clean boundary and re-audit')
    return {'passed': not reasons, 'reasons': list(dict.fromkeys(reasons)),
            'actual_transcript': actual, 'actual_final_sentence': sentences(actual)[-1],
            'last_word': valid[-1]['word'], 'last_word_end': valid[-1]['end'],
            'reviewed_payoff_suffix_matched': matched_payoff,
            'tail_clearance': round(clearance, 3), 'method': 'local ASR word timing',
            'limitation': 'Semantic payoff and audible cut cleanliness still need content review'}


def audit_export(video, payoff=None, model='small'):
    """Run on the final rendered MP4, not just its planned captions."""
    from v4_media import probe
    from v4_transcript import words
    try:
        duration = probe(video)['duration']
        return audit_words(words(video, model), duration, payoff)
    except (ImportError, OSError, RuntimeError, ValueError) as exc:
        return {'passed': False, 'reasons': ['export ending audit unavailable: ' + type(exc).__name__],
                'method': 'local ASR word timing'}
