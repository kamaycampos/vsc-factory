#!/usr/bin/env python3
"""Render the 29 revised VSC clips into ~/Desktop/VSC/Clips_v2. Originals untouched.

18 Sept 2026, after the Frame.io review. Everything here was decided with Kamay:
hooks rewritten to ONE idea and held 5-6s (all 29 approved as written), every
caption rebuilt and read line by line (vsc_v2caps.py), two crops fixed. The in/out
points are the ones on disk, recovered by matching audio - NOT from the logs,
which were wrong for 7 clips and would have moved edges he had approved.
"""
import glob, json, os, re, subprocess, sys
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
        close_end = cap["close_end"] if cap.get("close_end") is not None else (
            max(w[1] for w in cap["words"]) if cap.get("words") else b - a)
        close_abs = a + close_end
        # NEVER TRIM INTO THE CLOSE. The caption pass's close drifts at the tail (worst
        # +2.80s on YOUR-BIGGEST-DISASTER), and next_onset then hears Kevin still saying
        # the closing words and cuts them as "speech after the close" - which is how
        # "It doesn't end it, it creates it" shipped as "It doesn't end". The locator
        # measured where he finishes the close; nothing ends before that.
        said = r.get("speech_end")
        if said is not None and close_abs < said - 0.05:
            print(f"      close held to the cut: caption pass said +{close_abs - a:.2f}s, "
                  f"he finishes at +{said - a:.2f}s", flush=True)
            close_abs = said
            close_end = said - a
        onset = next_onset(src, close_abs)
        tail = 0.30 if onset is None else max(0.10, min(0.30, (onset - close_abs) * 0.6))
        note = ""
        if onset is not None and onset < b - 0.05:
            # SPEECH after the closing sentence - the defect Naomi flagged on three clips
            b, note = close_abs + tail, f"trimmed: speech after the close at +{onset - close_abs:.2f}s"
        elif close_abs > b - 0.10:
            b, note = close_abs + tail, "extended so the last word finishes"
        span = b - a
        words = [{"text": t, "a": s, "b": min(e, span)} for s, e, t in cap["bursts"] if s < span]
        close_phrase = [c2 for p2, cl in CUTS.items() for n2, r2, f2, c2, h in cl if n2 == name]
        if close_phrase and r.get("close_words"):
            words = finish_close(words, r["close_words"], close_phrase[0], span, name)
        vis = r.get("vis_end")
        if name == "VIKTOR-FRANKL":
            vis = None     # the "new scene" is another angle of Kevin, still talking
        if vis is not None and vis >= span - 0.05:
            vis = None
        for old in glob.glob(os.path.join(OUT, name + "_*.mp4")):
            os.remove(old)
        dest = os.path.join(OUT, f"{name}_{int(round(span))}s.mp4")
        hook = HOOKS.get(name) or [h for p2, cl in CUTS.items() for n2, r2, f2, c2, h in cl
                                  if n2 == name][0]
        R.build(src, fj, a, b, two_lines(hook), words, dest,
                speech_end=min(close_end, span), vis_end=vis, overrides=ov.get(name))
        # exactly what was burned, for kt_sync_check
        json.dump([[w["a"], w["b"], w["text"]] for w in words],
                  open(dest[:-4] + "__caps.json", "w"))
        print(f"  {name:30} {span:6.2f}s  hook {two_lines(hook)}  {note}", flush=True)
    print("V2RENDERDONE")


if __name__ == "__main__":
    main(sys.argv[1:] or None)
