#!/usr/bin/env python3
"""Cut on MEANING. I name the first and last words; this finds where they are.

10 Sept. Kamay, after reviewing all 40: "its ridiculous how many of the videos
still end when kevin's mouth is still open or you can tell he is about to say
something... some of the video start on for example 'and that it..' like what is?
what was he talking about."

He is right and the fault is architectural. Every previous attempt picked
boundaries by PROXY - punctuation, then silence gaps, then gap length. None of
them consult meaning, so clips opened on "Because", "or bad things", "was afraid
of water" and closed on "You may not." and "There is a slight...".

So the proxy is gone. A human reads the transcript, decides the exact sentence a
clip opens and closes on, and this module's only job is to locate those words in
the audio precisely. Word timings come from short local chunks, measured on
6 Sept as accurate to ~0.04s.
"""
import difflib
import json, os, re, subprocess, sys
sys.path.insert(0, os.path.expanduser("~/Kamay"))
import vsc_clip

LEAD  = 0.18
TAIL  = 0.60
# Where Kevin FINISHES the closing word, and the words around it, as the last locate()
# measured them (absolute seconds). The caption pass re-times the clip on its own and
# drifts at the tail; these are what the cut was decided on.
LAST_SPEECH_END = None
LAST_NEXT_WORD = None
LAST_WORDS = []


def norm(t):
    return re.sub(r"[^a-z0-9']", "", t.lower())


def words_in(src, a, b, tag, S):
    w = vsc_clip.word_times(src, a, b, tag, S)
    for x in w:
        x["a"] += a
        x["b"] += a
        x["n"] = norm(x["t"])
    return w


def _near(a, b):
    """Two transcribed words that are the same word. 'NeXT'/'next', 'Steven'/'Stephen'."""
    if a == b:
        return True
    if min(len(a), len(b)) < 4:
        return False
    return difflib.SequenceMatcher(a=a, b=b).ratio() >= 0.8


def _find(words, phrase, prefer_last=False):
    """Where this sentence starts. EXACT first, then loosely - never only exactly.

    30 Sept 2026: five clips failed three builds in a row with "missing opening|
    missing closing", and every one of those sentences was plainly there in the
    video. The comparison was letter-perfect, so one word the server heard
    differently from the Mac - where the plan was written - made a whole clip
    unlocatable. It is the same failure that had already silently skipped the
    caption corrections, in a second place: a correction that is 80% the same run
    of words, in the right part of the video, is the run that was meant.
    Exact wins when it exists, so nothing that already resolves can move.
    """
    toks = [norm(t) for t in phrase.split() if norm(t)]
    if not toks:
        return None
    for loose in (False, True):
        hits = []
        for i in range(len(words) - len(toks) + 1):
            got = [words[i + k]["n"] for k in range(len(toks))]
            if not loose:
                if got == toks:
                    hits.append(i)
                continue
            same = sum(1 for a, b in zip(got, toks) if _near(a, b))
            # one word may be heard differently, never two, and never in a phrase so
            # short that "one wrong" is most of it
            if same == len(toks) or (len(toks) >= 4 and same >= len(toks) - 1):
                hits.append(i)
        if hits:
            if loose:
                print(f"      opening/closing matched loosely: {phrase!r}", flush=True)
            return hits[-1] if prefer_last else hits[0]
    return None


def locate(src, base, S, region, first_words, last_words, tag, dur=None):
    """Exact in/out for the clip that OPENS on first_words and CLOSES on last_words.

    The region is a HINT, not a boundary. 27 Sept 2026: Kevin publishes the same
    interview on Rumble as well as to the VSC platform, and the published cut is
    trimmed differently - the episode that runs 1090s in both was found to sit at
    different offsets. A plan that only searched a 50-second window around its
    region would fail against the other version of its own source, which is the one
    thing standing between the factory and never needing a file from the Mac again.
    So when the words are not in the window, the whole video is searched. The
    sentences identify the clip; the region only says where to look first.
    """
    global LAST_SPEECH_END, LAST_NEXT_WORD, LAST_WORDS
    LAST_SPEECH_END, LAST_NEXT_WORD, LAST_WORDS = None, None, []   # never the previous clip's
    a0, b0 = max(0.0, region[0] - 22), region[1] + 28
    w = words_in(src, a0, b0, tag, S)
    i = _find(w, first_words)
    j = _find(w, last_words, prefer_last=True)
    if (i is None or j is None) and dur and dur > b0 + 1:
        w = words_in(src, 0.0, dur, tag + "_all", S)
        i = _find(w, first_words)
        j = _find(w, last_words, prefer_last=True)
    if i is None or j is None:
        return None, ("missing opening" if i is None else "") + ("|missing closing" if j is None else "")
    j_end = j + len([t for t in last_words.split() if norm(t)]) - 1
    if j_end <= i:
        return None, "closing lands before opening"
    start = w[i]["a"] - LEAD
    end = w[j_end]["b"]
    LAST_SPEECH_END, LAST_WORDS = round(end, 3), w[i:j_end + 1]
    nxt = w[j_end + 1]["a"] if j_end + 1 < len(w) else end + 2.0
    LAST_NEXT_WORD = round(nxt, 3) if j_end + 1 < len(w) else None
    # NEVER INTO THE NEXT WORD. 2 Oct 2026, Kamay: YOUR-BIGGEST-DISASTER ended on "one
    # of the" - "it." ends at 27.68 and "One" starts at 27.68, and a tail of at least
    # 0.18s was added anyway. The tail is a share of a REAL gap, or nothing.
    end = end + (min(TAIL, (nxt - end) * 0.6) if nxt > end else 0.0)
    return (round(max(0.0, start), 3), round(end, 3)), "ok"
