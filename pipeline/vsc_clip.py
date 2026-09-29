#!/usr/bin/env python3
"""One VSC clip end to end: snap the edges, time the words, render.

RULE ZERO (Kamay, 6 Sept, quoting the brief - "the most important thing than
anything else"): start and end at a NATURAL point, contain a complete thought,
never cut Kevin off halfway through a word, never end mid-sentence. So the in and
out points are snapped to whisper's own sentence segments and then padded a
fraction of a second outward, because a boundary that is exact to the millisecond
still clips the attack of the first consonant.
"""
import json, math, os, subprocess, sys, glob, re
sys.path.insert(0, os.path.expanduser("~/Kamay"))
import vsc_render, vsc_edges

WORK   = os.path.expanduser("~/Desktop/VSC/.work")
OUT    = os.path.expanduser("~/Desktop/VSC/Clips")
FFMPEG = os.path.expanduser("~/Kamay/bin/ffmpeg")
WHISPER= os.path.expanduser("~/Kamay/whisper.cpp/build/bin/whisper-cli")
MODEL  = os.path.expanduser("~/Kamay/whisper.cpp/models/ggml-small.en.bin")
LEAD, TRAIL = 0.20, 0.35
POST_ROLL = 0.75     # breathing room AFTER his real last word, measured not guessed
PROBE     = 1.6      # look this far past the snapped end to find where he truly stops     # never clip the first consonant or the last breath
CAP_MAX = 20                 # ceiling, not a target - his own captions run 8-15

FILLER = re.compile(r"^(um|uh|erm|ah|mm|hmm)[,.!?]?$", re.I)


def segments(base):
    """Sentence boundaries, used only to decide where to cut ~12s chunks.

    27 Sept 2026: prep took 30 minutes in the cloud and it was not the 4K face
    sampling (measured: 68s for a whole 18-minute video). It was transcribing the
    same audio TWICE - a whole-file pass whose only purpose was this function, plus
    the chunked word pass. Everything this returns that anybody uses is `marks`, the
    segment start times. The chunked pass already knows where sentences end, more
    accurately than the whole-file pass does, so the second transcription is dropped
    and the boundaries are derived from the words.
    """
    p = os.path.join(WORK, base + ".json")
    if os.path.exists(p):
        j = json.load(open(p))
        return [(s["offsets"]["from"] / 1000, s["offsets"]["to"] / 1000, s["text"].strip())
                for s in j["transcription"]]
    w = json.load(open(os.path.join(WORK, base + ".words.json")))
    out, start, said = [], None, []
    for x in w:
        if start is None:
            start = x["a"]
        said.append(x["t"])
        if x["t"].rstrip().endswith((".", "!", "?")):
            out.append((start, x["b"], " ".join(said))); start, said = None, []
    if said:
        out.append((start, w[-1]["b"], " ".join(said)))
    return out


SENT_END = re.compile(r"[.!?][\"')\]]*$")
LEADIN   = 0.16      # start a touch before the first consonant
TAILOUT  = 0.55      # let the last word land before the picture goes


def _allowed(iv, t0, t1, dur):
    """The stretch of Kevin, uninterrupted, that this clip must live inside."""
    walls = sorted(iv)
    lo, hi = 0.0, dur
    for a, b in walls:
        if b <= t0: lo = max(lo, b)
        if a >= t1: hi = min(hi, a); break
        if a < t1 and b > t0:            # the window straddles a question
            if t1 - b > a - t0: lo = max(lo, b)
            else:               hi = min(hi, a)
    return lo, hi


MAX_LEN = 118.0     # Naomi's ceiling is 120s
DRIFT   = 9.0       # a boundary further than this from the intended one is not this clip


def snap_audio(spans, iv, S, t0, t1, dur, fine=None):
    """Boundaries taken from SILENCE, not from the transcript.

    6 Sept, Kamay, after watching all 19: "almost every single clip ends either
    when KT is still talking or when the interviewer is asking a question and
    some of them starts mid sentence. this is unacceptable."

    Measured, he was right: MIND-LIKE-GLASS began 15.5s into unbroken speech and
    most ends sat 0.6-0.8s PAST a gap, i.e. already inside the next sentence. The
    cause was trusting the transcript's full stops - and that transcript was
    already known to be wrong about where sentences end.

    So a clip may only begin where a silence ENDS and end where a silence BEGINS.
    Among nearby candidates, prefer a long pause (a sentence break breathes longer
    than a mid-thought one) and text that actually terminates.
    """
    lo, hi = _allowed(iv, t0, t1, dur)
    ends_txt = [x[1] for x in S if SENT_END.search(x[2])]

    def terminal_near(t, tol=1.2):
        """A sentence ENDS at t."""
        return 1.0 if any(abs(e - t) <= tol for e in ends_txt) else 0.0

    def terminal_before(t, tol=1.4):
        """The previous sentence finished just before t, so t begins a new one.
        Without this, starts landed on a mid-sentence breath - NO-BUTTONS-LEFT
        opened on "so I have no more buttons that can push"."""
        return 1.0 if any(-0.2 <= (t - e) <= tol for e in ends_txt) else 0.0

    starts, finishes = [], []
    for i, (a, b) in enumerate(spans):
        gap_before = a - spans[i-1][1] if i else 9.9
        gap_after  = spans[i+1][0] - b if i + 1 < len(spans) else 9.9
        if lo - 0.01 <= a <= hi:
            starts.append((a, gap_before))
        if lo <= b <= hi + 0.01:
            finishes.append((b, gap_after, gap_after))
    def best(cands, target, want_terminal):
        out, sc = None, -1e9
        for t, gap, *_ in cands:
            if abs(t - target) > DRIFT: continue
            s_ = min(gap, 2.0) * 1.0 - abs(t - target) * 0.15
            s_ += (terminal_near(t) if want_terminal else terminal_before(t)) * 1.6
            if s_ > sc: sc, out = s_, t
        return out

    def collect(sp):
        st, fi = [], []
        for i, (aa, bb) in enumerate(sp):
            gb = aa - sp[i-1][1] if i else 9.9
            ga = sp[i+1][0] - bb if i + 1 < len(sp) else 9.9
            if lo - 0.01 <= aa <= hi: st.append((aa, gb))
            if lo <= bb <= hi + 0.01: fi.append((bb, ga, ga))
        return st, fi

    if (not starts or not finishes) and fine:
        # No confident pause anywhere in the window - Kevin can run 100s+ without
        # one. Fall back to finer gaps, but ONLY where the transcript agrees a
        # sentence ends there. Two weak signals that concur beat one strong guess.
        fs, ff = collect(fine)
        starts   = starts   or [c for c in fs if terminal_before(c[0])] or fs
        finishes = finishes or [c for c in ff if terminal_near(c[0])] or ff
        if not starts or not finishes:
            return None

    a = best(starts, t0, False)
    if a is None: a = min(starts, key=lambda c: abs(c[0]-t0))[0]
    usable = [c for c in finishes if a + 15 < c[0] <= a + MAX_LEN]
    b = best(usable, t1, True)
    if b is None:
        if not usable: return None
        b = min(usable, key=lambda c: abs(c[0]-t1))[0]
    gap_after = next((g for t, g, *_ in finishes if abs(t - b) < 1e-6), TAILOUT)
    tail = min(TAILOUT, max(0.12, gap_after * 0.7))   # never run into the next sentence
    return round(max(lo, a - LEADIN), 3), round(min(hi, b + tail), 3)


CHUNK = 12.0        # seconds. Accuracy AND timing both degrade on long windows.


def word_times(src, t0, t1, tag, S):
    """Real word text and timings, transcribed in SHORT chunks.

    6 Sept, Kamay: Kevin says "My top people in the Brotherhood" and the caption
    read "I taught people in the brotherhood", and separately the captions ran
    behind his voice. Both are the same fault. Measured on this very line:

        full 18-min file  -> "I taught people in the brotherhood"   WRONG
        71-second window  -> "brotherhood, it was, they knew..."    WRONG
        10-second window  -> "My top people in the Brotherhood"     RIGHT

    Whisper degrades on long audio, in the words AND in the timestamps, which is
    why the last caption was still on screen a second after he had stopped
    talking. So cut the window into ~12s chunks at sentence boundaries (never
    mid-word) and transcribe each on its own.
    """
    marks = [x[0] for x in S if t0 < x[0] < t1]
    bounds, last = [t0], t0
    for m in marks:
        if m - last >= CHUNK:
            bounds.append(m); last = m
    bounds.append(t1)
    if len(bounds) > 2 and bounds[-1] - bounds[-2] < 2.0:
        bounds.pop(-2)

    words = []
    for i, (a, b) in enumerate(zip(bounds, bounds[1:])):
        wav = f"/tmp/vsc_{tag}_{i}.wav"
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-ss", str(a), "-to", str(b),
                        "-i", src, "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", wav], check=True)
        subprocess.run([WHISPER, "-m", MODEL, "-f", wav, "-ml", "1", "-sow",
                        "-bs", "5", "-bo", "5", "-oj", "-of", f"/tmp/vsc_{tag}_{i}"],
                       capture_output=True)
        j = json.load(open(f"/tmp/vsc_{tag}_{i}.json"))
        off = a - t0
        span = b - a
        for seg in j["transcription"]:
            t = seg["text"].strip()
            if not t or FILLER.match(t):
                continue
            wa = seg["offsets"]["from"]/1000.0
            wb = seg["offsets"]["to"]/1000.0
            if wa > span + 0.05:            # whisper padding past the chunk - discard
                continue
            wb = min(wb, span)              # a final word stretched into silence
            words.append({"t": t, "a": round(off + wa, 3), "b": round(off + max(wb, wa + 0.12), 3)})
        os.remove(wav); os.remove(f"/tmp/vsc_{tag}_{i}.json")
    return words


WEAK_END = {"and","or","but","the","a","an","to","of","in","on","at","for","with",
            "that","that's","this","is","was","are","were","be","been","it","its",
            "your","you","my","his","her","their","so","if","because","when","as",
            "i","we","they","he","she","not","no","do","does","did","can","will"}


def bursts(words):
    """Short caption bursts that break on MEANING, timed to real speech.

    Reverted from one-word captions 6 Sept at Kamay's request. Each burst starts
    on its first word and ends on its last, both from chunked whisper timings, so
    a burst is on screen for exactly as long as those words are spoken.
    """
    out, cur = [], []
    for w in words:
        cand = (" ".join(x["t"] for x in cur) + " " + w["t"]).strip()
        if cur and len(cand) > CAP_MAX:
            out.append(cur); cur = [w]
        else:
            cur.append(w)
            if re.search(r"[.!?,;:]$", w["t"]):
                out.append(cur); cur = []
    if cur: out.append(cur)
    # never end a burst on a weak word - it reads as an unfinished thought
    for i in range(len(out) - 1):
        while (len(out[i]) > 1
               and re.sub(r"[^\w']", "", out[i][-1]["t"]).lower() in WEAK_END
               and not re.search(r"[.!?]$", out[i][-1]["t"])):
            out[i + 1].insert(0, out[i].pop())
    out = [b for b in out if b]
    res = []
    for i, b in enumerate(out):
        a_, b_ = b[0]["a"], b[-1]["b"]
        if i + 1 < len(out):                 # hold to the next burst, but never
            b_ = min(out[i + 1][0]["a"], b_ + 0.30)   # through a real pause
        res.append({"text": " ".join(x["t"] for x in b).strip(" ,"),
                    "a": round(a_, 3), "b": round(max(b_, a_ + 0.25), 3)})
    return [r for r in res if r["text"]]


def snap_text(src, tag, t0, t1, lo, hi, S):
    """Last resort when the audio has NO pause to cut on.

    Some answers are edited so tightly there is not a single 0.18s gap: 146s
    unbroken in "Every Millionaire", 60s in "If You Want". There is no acoustic
    boundary to find, so fall back to word timings transcribed LOCALLY in short
    chunks - measured 6 Sept as accurate to ~0.04s, unlike the full-file pass
    that caused this whole mess.
    """
    a0, b0 = max(lo, t0 - 14), min(hi, t1 + 14)
    w = word_times(src, a0, b0, tag + "tx", S)
    if not w:
        return None
    starts = [w[0]] + [w[i] for i in range(1, len(w))
                       if re.search(r"[.!?]$", w[i-1]["t"])]
    ends = [x for x in w if re.search(r"[.!?]$", x["t"])]
    if not starts or not ends:
        return None
    a = min(starts, key=lambda x: abs(a0 + x["a"] - t0))
    a = a0 + a["a"]
    cand = [x for x in ends if a0 + x["b"] > a + 15 and a0 + x["b"] <= a + MAX_LEN]
    if not cand:
        return None
    b = a0 + min(cand, key=lambda x: abs(a0 + x["b"] - t1))["b"]
    return round(max(lo, a - LEADIN), 3), round(min(hi, b + 0.45), 3)


def make(src, base, name, t0, t1, hook, iv=(), ads=()):
    S = segments(base)
    ed = vsc_edges.analyse(src, base)
    walls = list(iv) + list(ads)
    got = snap_audio(ed["spans"], walls, S, t0, t1, ed["dur"], ed.get("fine"))
    if got is None:
        lo, hi = _allowed(walls, t0, t1, ed["dur"])
        got = snap_text(src, re.sub(r"\W+", "", name)[:16], t0, t1, lo, hi, S)
    if got is None:
        raise RuntimeError(f"{name}: no valid boundary in range")
    a, b = got
    tag = re.sub(r"\W+", "", name)[:20]
    words = [w for w in word_times(src, a, b, tag, S) if w["a"] < (b - a)]
    caps = bursts(words)
    dest = os.path.join(OUT, f"{name}_{int(round(b-a))}s.mp4")
    fj = os.path.join(WORK, base + ".frame.json")
    shots = vsc_render.build(src, fj, a, b, hook, caps, dest)
    edge = verify_edges(dest)
    print(f"{name}: {a:.2f}-{b:.2f} ({b-a:.1f}s) | {len(shots)} shots | "
          f"{len(words)} words -> {len(caps)} captions | {edge} -> {os.path.basename(dest)}", flush=True)
    return dest


def verify_edges(path, head_win=0.10, tail_win=0.35):
    """Read the RENDERED file back and assert it opens and closes in silence.

    The whole failure on 6 Sept was trusting a transcript instead of checking the
    artifact. So the artifact gets checked: measure the clip's own speech level,
    then confirm the first and last fraction of a second sit far below it.
    """
    import wave, numpy as np
    tmp = "/tmp/vsc_verify.wav"
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", path,
                    "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", tmp], check=True)
    w = wave.open(tmp); x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    w.close(); os.remove(tmp)
    x = x.astype(np.float32)
    h, t = int(16000 * head_win), int(16000 * tail_win)
    if len(x) < (h + t) * 3: return "too short to check"
    body = float(np.sqrt(np.mean(x[h:-t] ** 2)) + 1e-9)
    head = float(np.sqrt(np.mean(x[:h] ** 2)) + 1e-9)
    tailv = float(np.sqrt(np.mean(x[-t:] ** 2)) + 1e-9)
    hdb = 20 * math.log10(head / body); tdb = 20 * math.log10(tailv / body)
    # The TAIL is the one Kamay caught - a clip must never end while he talks.
    # The head only has to prove we did not cut into a syllable.
    ok = "OK" if (tdb < -12 and hdb < -6) else ("TAIL WARN" if tdb >= -12 else "head warn")
    return f"edges {hdb:+.0f}/{tdb:+.0f}dB {ok}"
