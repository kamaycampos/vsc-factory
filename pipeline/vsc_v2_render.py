#!/usr/bin/env python3
"""Render the 29 revised VSC clips into ~/Desktop/VSC/Clips_v2. Originals untouched.

18 Sept 2026, after the Frame.io review. Everything here was decided with Kamay:
hooks rewritten to ONE idea and held 5-6s (all 29 approved as written), every
caption rebuilt and read line by line (vsc_v2caps.py), two crops fixed. The in/out
points are the ones on disk, recovered by matching audio - NOT from the logs,
which were wrong for 7 clips and would have moved edges he had approved.
"""
import difflib, glob, json, os, re, subprocess, sys
sys.path.insert(0, os.path.expanduser("~/Kamay"))
import vsc_render as R                                          # noqa: E402
from vsc_cuts import CUTS                                       # noqa: E402

WORK = os.path.expanduser("~/Desktop/VSC/.work")
# THIS WEEK'S folder. It was Clips_v2 for the week-1 revision batch, and calling
# this script directly afterwards quietly wrote 9 re-rendered clips there while
# Clips still held their older versions - one batch split across two folders with
# different caption timing. The driver sets OUT explicitly; this is the default.
OUT = os.path.expanduser("~/Desktop/VSC/Clips")
FF = os.path.expanduser("~/Kamay/bin/ffmpeg")
R.HOOK_SECS = 5.5            # Cali: "just have one concept ... hold it for 5-6 seconds"

HOOKS = {
 "AN-ANCESTOR-DROWNED": "DO YOUR ANCESTORS AFFECT YOU TODAY?",
 "BREATH-OF-FIRE": "HARDSHIP IS AN ADVENTURE",
 "CONFRONT-IT-VANISHES": "FACE YOUR FEAR AND IT VANISHES",
 "DISTRACTION-ISNT-THE-POINT": "CLEAR WHAT TRIGGERS YOU",
 "DONT-TELL-ANYONE": "NEVER SHARE YOUR GOALS",
 "EVEN-PEOPLE-WHO-LOVE-YOU": "EVEN YOUR FAMILY WANTS YOU TO FAIL",
 "GET-RID-OF-YOUR-FRIENDS": "YOUR FRIENDS DECIDE YOUR INCOME",
 "HANG-AROUND-BROKE-PEOPLE": "BROKE FRIENDS KEEP YOU BROKE",
 "LEARNED-AT-THE-BOTTOM": "THE BOTTOM TEACHES YOU EVERYTHING",
 "MIND-LIKE-GLASS": "SILENCE CLEARS YOUR MIND",
 "NO-BUTTONS-LEFT": "NOTHING CAN TRIGGER ME NOW",
 "PAPER-TIGER": "YOUR FEARS ARE PAPER TIGERS",
 "PROTECT-THE-SEED": "PROTECT YOUR DREAM IN SILENCE",
 "SHARING-KILLS-THE-DREAM": "SHARING YOUR DREAM KILLS IT",
 "TEN-YEARS-STILL-BROKE": "BEING AROUND MONEY ISN'T ENOUGH",
 "THE-BOSTON-ACCENT": "YOU BECOME WHO YOU LISTEN TO",
 "THE-CHINESE-FARMER": "THERE'S NO GOOD OR BAD NEWS",
 "THE-FIVE-YOU-WATCH": "YOU EARN LIKE WHO YOU WATCH",
 "THE-GLASSES": "YOU CAN'T SEE WHAT HOLDS YOU BACK",
 "THE-MASTERMIND-EXCEPTION": "THE ONLY PEOPLE TO TELL YOUR DREAM",
 "THE-ROLLS-ROYCE": "I TOLD NO ONE FOR 4 YEARS",
 "THEY-WANT-YOU-AT-THEIR-LEVEL": "MOST PEOPLE DON'T WANT YOU TO SUCCEED",
 "THOUSAND-POUNDS-OF-ROCKS": ["WHY SUCCESS FEELS", "LIKE WALKING UPHILL"],   # Cali: "perfect. Approved."
 "TWO-WAYS-TO-CLEAR": "TWO WAYS TO CLEAR YOUR BLOCKS",
 "VIKTOR-FRANKL": "YOU CAN ALWAYS CONTROL YOUR THOUGHTS",
 "WE-PAY-TO-FEEL-BAD": "WE PAY MONEY TO FEEL SCARED",
 "WHATS-IN-MY-FEED": "YOUR FEED SHOWS HOW YOU THINK",
 "WHY-WAIT-LAUGH-NOW": "WHY WAIT TO LAUGH ABOUT IT?",
 "YOURE-A-MAGICIAN": "HOW HER FEAR OF WATER VANISHED",
}


def two_lines(hook):
    """One idea, laid out as two balanced lines so it renders large."""
    if isinstance(hook, list):
        return hook
    w = hook.split()
    if len(w) <= 2:
        return [hook]
    best = min(range(1, len(w)), key=lambda k: abs(len(" ".join(w[:k])) - len(" ".join(w[k:]))))
    return [" ".join(w[:best]), " ".join(w[best:])]


def next_onset(src, after, look=3.0):
    """First real speech after `after` in the source (quiet first, then a rise)."""
    import numpy as np
    a0 = max(0.0, after - 1.5)
    raw = subprocess.run([FF, "-y", "-loglevel", "error", "-ss", f"{a0:.3f}", "-t", f"{1.5 + look:.3f}",
                          "-i", src, "-ar", "16000", "-ac", "1", "-f", "s16le", "-"],
                         capture_output=True).stdout
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    st = 160
    if len(x) < st * 20:
        return None
    db = 20 * np.log10(np.array([np.sqrt(np.mean(x[i:i + st] ** 2) + 1e-9)
                                 for i in range(0, len(x) - st, st)]) + 1e-9)
    lo, hi = np.percentile(db, 15), np.percentile(db, 90)
    thr = lo + (hi - lo) * 0.40
    quiet = 0
    for i in range(int((after - a0) / 0.01), len(db)):
        if db[i] <= thr:
            quiet += 1
            continue
        if quiet >= 8 and all(db[k] > thr for k in range(i, min(i + 3, len(db)))):
            return a0 + i * 0.01
        quiet = 0
    return None


def quiet_runs(src, t, before=1.2, length=2.6):
    """Stretches of quiet (>= 60ms) in the sound around t, as absolute (start, end)."""
    import numpy as np
    a0 = max(0.0, t - before)
    raw = subprocess.run([FF, "-y", "-loglevel", "error", "-ss", f"{a0:.3f}", "-t", f"{length:.2f}",
                          "-i", src, "-ar", "16000", "-ac", "1", "-f", "s16le", "-"],
                         capture_output=True).stdout
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    st = 160
    if len(x) < st * 40:
        return []
    db = 20 * np.log10(np.array([np.sqrt(np.mean(x[i:i + st] ** 2) + 1e-9)
                                 for i in range(0, len(x) - st, st)]) + 1e-9)
    lo, hi = np.percentile(db, 15), np.percentile(db, 90)
    # QUIET IS QUIET, NOT "QUIETER THAN THE REST". 2 Oct 2026, run 30, measured on the
    # released files: real pauses sit at or below 15 dB against 55-70 dB of speech, but
    # where no silence is near, a threshold relative to the window alone called a 50 dB
    # dip in his voice a pause, and nine clips were cut while he was still audible.
    # A pause must also be 35 dB below the speech around it.
    q = db <= min(lo + (hi - lo) * 0.40, hi - 35.0)
    runs, k = [], 0
    while k < len(q):
        if q[k]:
            j = k
            while j < len(q) and q[j]:
                j += 1
            if j - k >= 6:
                runs.append((a0 + k * 0.01, a0 + j * 0.01))
            k = j
        else:
            k += 1
    return runs


def _nearest(runs, t):
    return min(runs, key=lambda r: 0.0 if r[0] <= t <= r[1] else min(abs(r[0] - t), abs(r[1] - t)))


def _longest(runs, lo, hi, real=0.15):
    """Of the quiet runs that overlap [lo, hi], the longest REAL one (>= `real` s), or
    None. 3 Oct 2026, run 33: FALL-DOWN-SEVEN-TIMES "ended in the pause" from +21.82 to
    +21.89 - a 70 ms gap between two words of running speech, taken because the old
    fallback accepted the longest gap of any length. That is no pause: it gets the
    fade and the FAIL that a person listens to, like every other no-pause edge."""
    big = [r for r in runs if r[1] >= lo and r[0] <= hi and r[1] - r[0] >= real]
    return max(big, key=lambda r: r[1] - r[0]) if big else None


def valley(src, t, back=0.35, ahead=0.10):
    """The quietest 30ms in [t - back, t + ahead]: where two words that run together
    are furthest apart. The cut when there is no pause to cut in."""
    import numpy as np
    a0 = max(0.0, t - back)
    raw = subprocess.run([FF, "-y", "-loglevel", "error", "-ss", f"{a0:.3f}", "-t", f"{back + ahead:.3f}",
                          "-i", src, "-ar", "16000", "-ac", "1", "-f", "s16le", "-"],
                         capture_output=True).stdout
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    st = 480
    if len(x) < st * 3:
        return None
    e = [float(np.sqrt(np.mean(x[i:i + st] ** 2))) for i in range(0, len(x) - st, 80)]
    k = int(np.argmin(e))
    return a0 + (k * 80 + st / 2) / 16000.0


def pause_after(src, said, back=0.6, ahead=0.5):
    """The silence Kevin leaves after the close, from the sound: (start, end) or None.

    Whisper's word times cannot show it - on YOUR-BIGGEST-DISASTER "it." runs 26.97-27.68
    and "One" starts at 27.68, the pause swallowed into the word before it. The
    quiet stretch nearest the end of the close is the pause between the two."""
    # THE LONGEST REAL SILENCE NEAR THE BOUNDARY, not the nearest. A gap inside the
    # close ("creates | it") is short; the pause after it - and the MUTED gaps this
    # source carries (YOUR-BIGGEST-DISASTER: digital silence 26.85-27.45 after "it
    # creates it", whisper's boundary at 27.68, "One" at 27.50) - are long.
    # ...but never a pause INSIDE the close: a silence followed by speech that ends
    # well before the close does ("end it. | It creates it.") would cut the punchline.
    return _longest([r for r in quiet_runs(src, said, before=1.4, length=2.8) if r[1] >= said - 0.25],
                    said - 1.0, said + ahead)


def pause_before(src, first, back=2.5, ahead=0.6):
    """The silence just before the plan's first word, from the sound: (start, end) or None.

    The mirror of pause_after. 2 Oct 2026, Kamay: "it starts on an off moment: a word
    or words that aren't the right start... the most important thing of all in clips
    is the FIRST 3 SECONDS." Whisper hands the first word a start that may swallow the
    pause before it, so the quiet nearest that start is where the clip begins - never
    on the tail of the sentence before."""
    # a quiet that STARTS well after the first word's start is a gap inside the opening
    # words, not the pause before them. It may END long after it: TONS-OF-DIRT-FOR-GOLD
    # (2 Oct) had 2.0s of DIGITAL SILENCE over a shot of Kevin mid-gesture before he
    # says "People" - the locator had put the word inside it, and a clip that opens on
    # a mouth moving without sound is the worst first 3 seconds there is.
    return _longest([r for r in quiet_runs(src, first, before=1.4, length=4.4) if r[0] <= first + 0.15],
                    first - ahead, first + back)


def card_spans(src, a, b, step=0.1):
    """Where the source shows a TITLE CARD or a SCREEN GRAB instead of Kevin: clip-relative
    (t0, t1) spans, to be shown in FULL instead of cropped like a face.

    3 Oct 2026, the Connector's frame review: six clips opened on the episode's 16:9
    text cards centre-cropped to 9:16 ("...ON'T STOP SUC... / CREATE IT."), and two
    ended on them or on a cropped web page. The shot map's segments run 60-130s and
    never see a 1-second card. Measured on the released frames: cards are 85-93% pure
    black (< 14), the web page 97% near-white (> 225), Kevin at most 1-2% of either."""
    import numpy as np
    w_, h_ = 160, 90
    raw = subprocess.run([FF, "-v", "error", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", src,
                          "-vf", f"fps={1 / step:.0f},scale={w_}:{h_},format=gray",
                          "-f", "rawvideo", "-"], capture_output=True).stdout
    n = len(raw) // (w_ * h_)
    dark = []
    for k in range(n):
        y = np.frombuffer(raw[k * w_ * h_:(k + 1) * w_ * h_], dtype=np.uint8).reshape(h_, w_)[15:75]
        dark.append(max((y < 14).mean(), (y > 225).mean()))
    spans, k = [], 0
    while k < n:
        if dark[k] > 0.70:
            j = k
            while j < n and dark[j] > 0.70:
                j += 1
            # A REAL CARD (>= 0.4 s) DISSOLVES in and out: grow its span through every
            # frame still partly card (THE-450-MILLION-BREAKUP, 3 Oct: 0.90 -> 0.53 -> 0.14
            # -> 0.01 over 1.8-2.2 s, and the 0.53 frame was cropped like a face). Not for
            # a short dark start - that is a fade from black, lifted elsewhere.
            if (j - k) * step >= 0.4:
                while k > 0 and dark[k - 1] > 0.05:
                    k -= 1
                while j < n and dark[j] > 0.05:
                    j += 1
            spans.append((max(0.0, k * step - step / 2), min(b - a, j * step - step / 2)))
            k = j
        else:
            k += 1
    return spans


def fade_in_lift(src, a, look=2.0, step=0.1):
    """If the picture fades up from black at the clip's start, the gain that undoes it:
    (end, expr) with expr a function of the segment's time T, or None."""
    import numpy as np
    raw = subprocess.run([FF, "-v", "error", "-ss", f"{a:.3f}", "-t", f"{look:.3f}", "-i", src,
                          "-vf", f"fps={1 / step:.0f},scale=160:90,format=gray",
                          "-f", "rawvideo", "-"], capture_output=True).stdout
    n = len(raw) // (160 * 90)
    m = [float(np.frombuffer(raw[k * 14400:(k + 1) * 14400], dtype=np.uint8)[2400:12000].mean()) for k in range(n)]
    if n < 8 or m[0] > 0.6 * max(m):
        return None
    # the level the fade ARRIVES at, in the same shot - not the brightest frame in the
    # window, which can belong to the next camera angle and over-lifts the fade
    top = max(m)
    k_end = next((k for k in range(1, n - 1) if m[k] > 0.3 * top and m[k + 1] <= m[k] * 1.03), None)
    if k_end is None:
        return None
    ref, end = m[k_end], k_end * step
    if end < 0.2:
        return None
    # 85% of the correction: a touch under is invisible, a touch over looks washed out
    pts = [(k * step, 1 + 0.85 * (min(5.0, ref / max(m[k], 1.0)) - 1)) for k in range(int(round(end / step)) + 1)]
    expr = f"{pts[-1][1]:.3f}"
    for (ta, ga), (tb, gb) in reversed(list(zip(pts, pts[1:]))):
        expr = f"if(lt(T,{tb:.2f}),{ga:.3f}+({gb - ga:.3f})*(T-{ta:.2f})/{tb - ta:.2f},{expr})"
    return end, expr


def finish_close(words, close_words, close_phrase, span, name=""):
    """THE LAST CAPTION IS THE CLOSE. Checked on what is about to be burned.

    2 Oct 2026, run 24: the picture now ran on to the end of the teaching, and on
    two clips the captions still stopped short - "It doesn't end", "not people
    without" - with Kevin saying the rest under no caption at all. The words had
    been lost somewhere between the caption pass, the corrections, the re-timing
    and the line breaks. Whatever the stage, this is the one place it can be seen
    whole: if the captions do not reach the close, the missing words are added from
    the locator's own hearing, at its times.
    """
    import vsc_v2caps
    have = [vsc_v2caps.norm(t) for w in words for t in w["text"].split()]
    miss = vsc_v2caps.missing_tail(have, [tuple(x) for x in close_words], close_phrase)
    if not miss:
        if miss is None and words:
            print(f"  !! {name}: last caption {words[-1]['text']!r} does not reach the close "
                  f"{close_phrase!r} - READ THIS ENDING", flush=True)
        return words
    texts = [m[2] for m in miss]
    # THE WORDS FROM THE PLAN, THE TIMES FROM THE LOCATOR. The plan's close is what a
    # person read Kevin say; the locator found it "loosely" on YOUR-BIGGEST-DISASTER,
    # i.e. it heard one of those words differently, and that word must not be burned.
    ptoks = close_phrase.split()
    pn = [vsc_v2caps.norm(t) for t in ptoks]
    for k in range(min(6, len(have)), 0, -1):
        hit = [p for p in range(len(pn) - k, -1, -1) if pn[p:p + k] == have[-k:] and p + k < len(pn)]
        if hit:
            rest = ptoks[hit[0] + k:]
            t0, t1 = miss[0][0], miss[-1][1]
            tot = sum(len(t) for t in rest) or 1
            miss, t = [], t0
            for tx in rest:
                d = (t1 - t0) * len(tx) / tot
                miss.append((t, t + d, tx)); t += d
            texts = list(rest)
            break
    texts[-1] = texts[-1].rstrip(",;:")
    if not texts[-1].endswith((".", "!", "?")):
        texts[-1] += "."                          # the close ends the sentence
    out = [dict(w) for w in words]
    # a lone word that ends a clause ("it," / "it.") belongs on the line it completes
    if len(texts) > 1 and texts[0].endswith((".", ",")) and len(out[-1]["text"]) + len(texts[0]) < 30:
        out[-1]["text"] += " " + texts[0]
        texts, miss = texts[1:], miss[1:]
    if out[-1]["text"].rstrip().endswith((".", "!", "?")):
        texts[0] = texts[0][:1].upper() + texts[0][1:]
    s0 = max(miss[0][0], out[-1]["a"] + 0.25)
    e0 = min(span, max(miss[-1][1] + 0.2, s0 + 0.6))
    if s0 >= span - 0.1:
        print(f"  !! {name}: no room to caption {' '.join(texts)!r} - READ THIS ENDING", flush=True)
        return words
    out[-1]["b"] = s0                             # each caption ends where the next begins
    out.append({"text": " ".join(texts), "a": round(s0, 3), "b": round(e0, 3)})
    print(f"      captions finished to the close: {' '.join(texts)!r} at +{s0:.2f}s", flush=True)
    return out


def main(only=None):
    ab = json.load(open(os.path.join(WORK, "v2_ab.json")))
    _ovp = os.path.join(WORK, "v2_overrides.json")
    ov = json.load(open(_ovp)) if os.path.exists(_ovp) else {}   # per-clip crops, if any
    pre = {n: p for p, cl in CUTS.items() for n, *_ in cl}
    os.makedirs(OUT, exist_ok=True)
    for name in sorted(ab):
        if only and name not in only:
            continue
        r = ab[name]
        a, b = r["a"], r["b"]
        src = glob.glob(os.path.expanduser(f"~/Desktop/VSC/Source/{pre[name]}*.mp4"))[0]
        fj = [x for x in glob.glob(os.path.join(WORK, "*.frame.json"))
              if os.path.basename(x).startswith(pre[name])][0]
        cap = json.load(open(os.path.join(WORK, "v2caps", name + ".json")))
        # last resort: close on the final word, never crash on a missing match
        # WHERE THE CLIP STARTS: inside the pause before the plan's first word, heard
        # in the sound. The captions were transcribed over [a_cap, b] and keep that
        # clock; they are shifted onto the clip's real start below.
        a_cap = a
        ow, pe = r.get("open_word"), r.get("prev_end")
        hz, head_note, head_bad = None, "", False
        if ow is not None and ow > 0.5:
            hz = pause_before(src, ow)
            if hz is not None:
                a = max(0.0, hz[1] - min(0.12, (hz[1] - hz[0]) * 0.4))
                head_note = f"starts in the pause before the open (+{hz[0] - a:.2f}s to +{hz[1] - a:.2f}s)"
            else:
                v = valley(src, ow, back=0.35, ahead=0.05)
                a = v if v is not None else max(ow - 0.05, (pe + 0.02) if pe is not None and pe < ow - 0.05 else ow - 0.05)
                head_bad = True
                head_note = f"NO PAUSE heard before the open - starts at the quietest point, +{(v or a) - ow:+.2f}s from the first word"
        shift = a_cap - a
        close_end = cap["close_end"] if cap.get("close_end") is not None else (
            max(w[1] for w in cap["words"]) if cap.get("words") else b - a)
        close_abs = a_cap + close_end
        close_end = close_abs - a
        # WHERE THE CLIP ENDS: on the close, and never on a word after it. 2 Oct 2026,
        # Kamay: YOUR-BIGGEST-DISASTER ended on "one of the" and WINNERS-HATE-LOSING on
        # "there is a". The caption pass's idea of the close drifts BOTH ways (+2.80s,
        # +1.95s), and both failures came from trusting it: trimmed into the close one
        # day, "extended so the last word finishes" past it the next. The locator heard
        # the close in short chunks and decides where he finishes, in both directions;
        # the next word he says - in the sound and in the word times - is a ceiling.
        said, nxt = r.get("speech_end"), r.get("next_word")
        if said is not None:
            close_abs, close_end = said, said - a
        note = ""
        # END IN THE PAUSE HE LEAVES AFTER THE CLOSE, heard in the sound. Whisper's
        # times cannot be trusted at a word boundary: on YOUR-BIGGEST-DISASTER "it."
        # runs to 27.68 and "One" starts at 27.68 - the pause swallowed whole.
        pz = pause_after(src, close_abs) if said is not None else None
        if pz is not None:
            close_abs, close_end = pz[0], pz[0] - a      # he has stopped: the fades start here
            new_b = pz[0] + min(0.12, (pz[1] - pz[0]) * 0.4)
            note = f"ends in the pause after the close (+{pz[0] - a:.2f}s to +{pz[1] - a:.2f}s)"
        elif said is not None:
            # Whisper's boundary can run LATE: on YOUR-BIGGEST-DISASTER the sound is already
            # rising into "One" 0.3s before the 27.68 whisper gives, so the real pause ends
            # before the strict window above allows. Take the latest quiet in the last
            # 0.6s of the close; failing that, the quietest instant between the words.
            # no PAUSE, but maybe a short REAL silence (>= 60 ms, 35 dB under the voice):
            # MORE-PROBLEMS-THAN-YOU, 3 Oct, dipped to 5 dB just after "problems" and
            # the quietest-point search, 0.35 s wide, missed it and cut later - into a
            # faint rise. The latest real silence in the last 0.6 s comes first.
            short = [r for r in quiet_runs(src, said) if said - 0.6 <= r[1] <= said + 0.15 and r[0] <= said + 0.1]
            v = (max(short)[0] + min(0.06, (max(short)[1] - max(short)[0]) * 0.5)) if short \
                else valley(src, said, back=0.35, ahead=0.10)
            new_b = v if v is not None else ((nxt - 0.08) if nxt is not None and nxt > said + 0.05 else said)
            close_abs, close_end = new_b, new_b - a
            note = f"no pause heard after the close - ends at the quietest point between the words ({new_b - said:+.2f}s)"
        else:
            onset = next_onset(src, close_abs)
            tail = 0.30 if onset is None else max(0.10, min(0.30, (onset - close_abs) * 0.6))
            new_b = close_abs + tail
            note = "no locator close: caption pass close"
        b = min(new_b, said + 0.60) if said is not None else new_b
        # THE TAIL CHECK. Nothing he says after the close may be in the clip: a clip
        # whose close runs straight into the next word, with no pause to end in, is a
        # FAIL for a person to hear - never a silent pass.
        # Every no-pause ending is a FAIL to be heard - not only one past the next
        # word's whisper start: BANNED-FOR-LIFE's quietest point was still 58 dB.
        tail_bad = said is not None and pz is None
        json.dump({"close": round(close_abs - a, 3), "end": round(b - a, 3),
                   "pause": None if pz is None else [round(pz[0] - a, 3), round(pz[1] - a, 3)],
                   "next_word": None if nxt is None else round(nxt - a, 3),
                   "speech_after_close": bool(tail_bad)},
                  open(os.path.join(OUT, name + "__tail.json"), "w"))
        if tail_bad:
            print(f"  !! {name}: NO PAUSE after the close - the next word may be audible", flush=True)
        span = b - a
        words = [{"text": t, "a": max(0.0, s + shift), "b": min(e + shift, span)}
                 for s, e, t in cap["bursts"] if s + shift < span and e + shift > 0.05]
        close_phrase = [c2 for p2, cl in CUTS.items() for n2, r2, f2, c2, h in cl if n2 == name]
        if close_phrase and r.get("close_words"):
            words = finish_close(words, [(x[0] + shift, x[1] + shift, x[2]) for x in r["close_words"]],
                                 close_phrase[0], span, name)
        # THE HEAD CHECK. The first word on screen is the plan's first word, and there
        # is a pause to start in. Either failing is a FAIL for a person to watch.
        import vsc_v2caps
        open_phrase = [f2 for p2, cl in CUTS.items() for n2, r2, f2, c2, h in cl if n2 == name]
        want = vsc_v2caps.norm(open_phrase[0].split()[0]) if open_phrase else ""
        got = vsc_v2caps.norm(words[0]["text"].split()[0]) if words else ""
        same = lambda g: g == want or (min(len(g), len(want)) >= 4 and
                                       difflib.SequenceMatcher(a=g, b=want).ratio() >= 0.8)
        first_ok = bool(want) and same(got)
        if want and not first_ok:
            # A CLIP MAY START AT THE BEGINNING OF THE SENTENCE THAT HOLDS THE OPEN.
            # BEAT-HARRY-POTTER: Kevin says "I said, you know, I'm gonna write that book"
            # and the plan opens on "I'm" - the clip starting on "I said" is the right
            # start. Allowed only within the first six words and with no sentence end
            # before the plan's word; anything else is a start in the wrong place.
            lead = [t for w in words[:3] for t in w["text"].split()][:6]
            for k, t in enumerate(lead):
                if same(vsc_v2caps.norm(t)):
                    first_ok = k > 0 and not any(x.rstrip().endswith((".", "!", "?")) for x in lead[:k])
                    break
        json.dump({"start": round(a, 3), "open_word": None if ow is None else round(ow - a, 3),
                   "pause": None if hz is None else [round(hz[0] - a, 3), round(hz[1] - a, 3)],
                   "first_caption_word": got, "plan_first_word": want,
                   "first_caption_at": round(words[0]["a"], 3) if words else None,
                   "bad": bool(head_bad or not first_ok),
                   "why": ("no pause before the open" if head_bad else "") +
                          ("" if first_ok else f"; first caption word {got!r} is not the plan's {want!r}")},
                  open(os.path.join(OUT, name + "__head.json"), "w"))
        if head_note or not first_ok:
            print(f"      {head_note}" + ("" if first_ok else f"  !! first caption word {got!r}, plan says {want!r}"),
                  flush=True)
        vis = r.get("vis_end")
        vis = None if vis is None else vis + shift          # clip-relative, like the captions
        if name == "VIKTOR-FRANKL":
            vis = None     # the "new scene" is another angle of Kevin, still talking
        if vis is not None and vis >= span - 0.05:
            vis = None
        for old in glob.glob(os.path.join(OUT, name + "_*.mp4")):
            os.remove(old)
        dest = os.path.join(OUT, f"{name}_{int(round(span))}s.mp4")
        hook = HOOKS.get(name) or [h for p2, cl in CUTS.items() for n2, r2, f2, c2, h in cl
                                  if n2 == name][0]
        # FRAMING THAT AUDIO CANNOT SEE: cards shown whole, a fade from black undone
        ovs = list(ov.get(name) or [])
        cards = card_spans(src, a, b)
        span_ = b - a
        for c0, c1 in cards:
            # A SLIVER of a card at the very start or end (BANNED-FOR-LIFE, 3 Oct: the
            # first 4 frames) would only flash, whole or cropped: hold Kevin's nearest
            # clean frame over it instead - 0.13 s of stillness is not seen.
            # sampled every 0.1 s, so the card may run up to one sample past what was seen
            if c1 - c0 <= 0.3 and c0 < 0.05 and fade_in_lift(src, a) is None:
                ovs.append({"t0": 0.0, "t1": round(c1 + 0.1, 3), "freeze_at": round(a + c1 + 0.15, 3)})
            elif c1 - c0 <= 0.3 and c1 > span_ - 0.05:
                ovs.append({"t0": round(max(0.0, c0 - 0.1), 3), "t1": round(span_, 3),
                            "freeze_at": round(a + c0 - 0.17, 3)})
            elif c1 - c0 >= 0.15:
                ovs.append({"t0": round(c0, 3), "t1": round(c1, 3), "fit": True})
        lift = fade_in_lift(src, a)
        # a clip that OPENS ON A CARD is dark because of the card, not a fade from black
        # (THE-FOREST-FIRE, REACT-OR-RESPOND read as fades) - the card is shown whole
        if lift is not None and cards and cards[0][0] < 0.05 and cards[0][1] - cards[0][0] > 0.4:
            lift = None
        if lift is not None:
            ovs.append({"t0": 0.0, "t1": round(lift[0], 3), "lift": lift[1]})
        if cards or lift:
            print(f"      shown whole: {[(round(x, 2), round(y, 2)) for x, y in cards]}"
                  + (f"; fade from black lifted to +{lift[0]:.2f}s" if lift else ""), flush=True)
        R.build(src, fj, a, b, two_lines(hook), words, dest,
                speech_end=min(close_end, span), vis_end=vis, overrides=ovs or None,
                fade_out_by=span if tail_bad else None, fade_in=0.08 if head_bad else 0.0)
        # exactly what was burned, for kt_sync_check
        json.dump([[w["a"], w["b"], w["text"]] for w in words],
                  open(dest[:-4] + "__caps.json", "w"))
        print(f"  {name:30} {span:6.2f}s  hook {two_lines(hook)}  {note}", flush=True)
    print("V2RENDERDONE")


if __name__ == "__main__":
    main(sys.argv[1:] or None)
