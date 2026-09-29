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
import json, os, re, subprocess, sys
sys.path.insert(0, os.path.expanduser("~/Kamay"))
import vsc_clip

LEAD  = 0.18
TAIL  = 0.60


def norm(t):
    return re.sub(r"[^a-z0-9']", "", t.lower())


def words_in(src, a, b, tag, S):
    w = vsc_clip.word_times(src, a, b, tag, S)
    for x in w:
        x["a"] += a
        x["b"] += a
        x["n"] = norm(x["t"])
    return w


def _find(words, phrase, prefer_last=False):
    toks = [norm(t) for t in phrase.split() if norm(t)]
    hits = []
    for i in range(len(words) - len(toks) + 1):
        if [words[i + k]["n"] for k in range(len(toks))] == toks:
            hits.append(i)
    if not hits:
        return None
    return hits[-1] if prefer_last else hits[0]


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
    nxt = w[j_end + 1]["a"] if j_end + 1 < len(w) else end + 2.0
    end = end + min(TAIL, max(0.18, (nxt - end) * 0.75))   # never bleed into the next word
    return (round(max(0.0, start), 3), round(end, 3)), "ok"
