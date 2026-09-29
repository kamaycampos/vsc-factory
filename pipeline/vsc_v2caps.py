#!/usr/bin/env python3
"""VSC Week-1 re-caption, 18 Sept 2026 - after the Frame.io review.

Reviewers (Cali / Naomi) on the submitted clips: captions did not match what
Kevin says ("death sentence", "overt acts", "O'Hare", "parkas"...), and Naomi:
"Always take the time to read all the caption again to make sure it's written
what Kevin is actually saying."

Two whisper passes, each trusted ONLY for what it is good at:
  TIMES - kt_words.words_for(): unprompted `-ml 1 -sow` over the clip. The pass
          graded against the waveform on 16 Sept. NEVER prompted - a prompt in
          this mode compressed timestamps by up to 9.5s (project-caption-drift).
  WORDS - normal-mode whisper in ~15s chunks cut at pauses. It hears words far
          better than -ml 1 (which produced "of the that we were taught"), but it
          gives no word times. Aligned onto the timed words with difflib.
Then the reviewers' explicit corrections, then kt_render.phrases_from_words for
the line breaks Kamay approved on 16 Sept.

Writes ~/Desktop/VSC/.work/v2caps/<NAME>.json : {"words": [...], "bursts": [...]}
"""
import difflib, glob, json, os, re, subprocess, sys
sys.path.insert(0, os.path.expanduser("~/Kamay"))
import kt_words, kt_render                                     # noqa: E402
from vsc_cuts import CUTS                                      # noqa: E402

FF = os.path.expanduser("~/Kamay/bin/ffmpeg")
WH = os.path.expanduser("~/Kamay/whisper.cpp/build/bin/whisper-cli")
MD = os.path.expanduser("~/Kamay/whisper.cpp/models/ggml-small.en.bin")
WORK = os.path.expanduser("~/Desktop/VSC/.work")
OUT = os.path.join(WORK, "v2caps")
# Prompting NORMAL mode is safe - it is only the -ml 1 timing pass it breaks - and
# it is what makes whisper punctuate (0% -> 75% of sentences, 14 Sept).
PUNCT = ("Hello, everyone. Today, we are going to talk about money, health, and "
         "success. It is important, isn't it?")
FILLER = re.compile(r"^(um+|uh+|erm|ah|mm+|hmm+)[,.!?]?$", re.I)


def norm(t):
    return re.sub(r"[^a-z0-9']", "", t.lower())


def _plain(src, t0, t1):
    wav = "/tmp/vsc_v2p.wav"
    subprocess.run([FF, "-y", "-loglevel", "error", "-ss", f"{t0:.3f}", "-to", f"{t1:.3f}",
                    "-i", src, "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", wav], check=True)
    subprocess.run([WH, "-m", MD, "-f", wav, "-bs", "5", "--prompt", PUNCT, "-oj",
                    "-of", "/tmp/vsc_v2p"], capture_output=True)
    try:
        j = json.load(open("/tmp/vsc_v2p.json"))
        return " ".join(x["text"] for x in j["transcription"]).split()
    except Exception:
        return []


def accurate_words(src, a, b, key):
    """[(start, end, word)] clip-relative: timed-pass TIMES carrying plain-pass WORDS."""
    timed = [w for w in kt_words.words_for(src, a, b, key) if w[2].strip()]
    if not timed:
        return []
    # chunk the plain pass at the biggest pause near every 15s, never mid-word
    bounds, last = [0.0], 0.0
    for i in range(1, len(timed)):
        if timed[i][0] - last >= 15.0:
            cands = [k for k in range(max(1, i - 6), min(len(timed), i + 6))]
            k = max(cands, key=lambda k: timed[k][0] - timed[k - 1][1])
            cut = (timed[k - 1][1] + timed[k][0]) / 2
            if cut - last > 4.0:
                bounds.append(cut); last = cut
    bounds.append(b - a)
    # ALIGN CHUNK BY CHUNK, and only trust a chunk the two passes broadly agree on.
    # 18 Sept, first test: whisper REGURGITATED THE PROMPT over a hard chunk of
    # BREATH-OF-FIRE - "We are going to talk about money." across 14 seconds where
    # Kevin says "...generating so much heat". Whole-clip alignment swallowed it.
    # So each chunk must (a) not contain prompt text and (b) match the timed pass
    # at >= 0.6, and even then only SMALL substitutions (<= 4 words) are taken:
    # the plain pass fixes a misheard word, it never rewrites a stretch.
    LEAK = ("helloeveryone", "goingtotalkaboutmoney", "healthandsuccess", "itisimportant")
    out = []
    for p, q in zip(bounds, bounds[1:]):
        tw = [w for w in timed if p <= w[0] < q]
        if not tw:
            continue
        pw = _plain(src, a + p, a + q)
        pw = [w.strip('"\u201c\u201d') for w in pw if w.strip('"\u201c\u201d')]
        joined = "".join(norm(w) for w in pw)
        tn = [norm(w[2]) for w in tw]
        pn = [norm(w) for w in pw]
        sm = difflib.SequenceMatcher(a=tn, b=pn, autojunk=False)
        if not pw or any(k in joined for k in LEAK) or sm.ratio() < 0.6:
            out += tw                                # plain pass not trustworthy here
            continue
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                for k in range(i2 - i1):
                    out.append((tw[i1 + k][0], tw[i1 + k][1], pw[j1 + k]))
            elif tag == "replace" and (i2 - i1) <= 4 and (j2 - j1) <= 4:
                ts, te = tw[i1][0], tw[i2 - 1][1]
                ws = pw[j1:j2]
                if i2 - i1 == j2 - j1:
                    for k in range(i2 - i1):
                        out.append((tw[i1 + k][0], tw[i1 + k][1], ws[k]))
                else:
                    tot = sum(len(w) for w in ws) or 1
                    t = ts
                    for w in ws:
                        d = (te - ts) * len(w) / tot
                        out.append((round(t, 3), round(t + d, 3), w)); t += d
            elif tag == "insert" and (j2 - j1) <= 2:
                ts = tw[i1 - 1][1] if i1 > 0 else tw[0][0]
                te = tw[i1][0] if i1 < len(tw) else ts + 0.3
                ws = pw[j1:j2]
                d = max(0.08, (te - ts) / len(ws))
                for k, w in enumerate(ws):
                    out.append((round(ts + k * d, 3), round(ts + (k + 1) * d, 3), w))
            else:
                out += tw[i1:i2]                     # big disagreement: keep the timed words
    out = [w for w in out if w[2].strip() and not FILLER.match(w[2].strip())]
    out.sort(key=lambda w: w[0])
    # A word straddling a chunk edge is heard by BOTH chunks ("minutes, minutes,").
    # Drop the repeat only when the two copies overlap in time - Kevin's deliberate
    # repeats ("freezing, freezing, freezing cold") are a second apart and stay.
    ded = []
    for w in out:
        if ded and norm(w[2]) == norm(ded[-1][2]) and w[0] - ded[-1][0] < 0.35:
            continue
        ded.append(w)
    return ded


def cut_after_close(words, close_phrase):
    """Drop every word after the clip's closing sentence.

    AN-ANCESTOR-DROWNED, Naomi: "cut off the end just a second earlier so that we
    don't see the caption of the next sentence starting". A fragment of the next
    sentence inside the window gets captioned. Returns (words, end_of_close) or
    (words, None) when the closing words cannot be found.
    """
    full = [norm(t) for t in close_phrase.split() if norm(t)]
    # THE TWO PASSES DO NOT ALWAYS AGREE ON EVERY WORD. The cut is located with the
    # whole-file word cache; the captions come from a separate chunked pass, and on
    # YOUR-BIGGEST-DISASTER that pass heard "it doesn't end it, creates it" - one
    # "it" short of what Kevin says, so the closing phrase was nowhere to be found
    # and the clip could not be rendered at all. A missing word must not cost the
    # clip: the tail is retried shorter, and the caller is told how it matched so the
    # caption text can be corrected.
    for drop in range(0, max(1, len(full) - 1)):
        toks = full[drop:]
        if len(toks) < 2:
            break
        got = _cut_on(words, toks)
        if got:
            return got
    return words, None


def _cut_on(words, toks):
    wn = [norm(w[2]) for w in words]
    # whisper may hyphenate or split ("counter-intention"); compare on joined letters
    target = "".join(toks)
    for i in range(len(words) - 1, -1, -1):
        acc = ""
        for j in range(i, max(-1, i - len(toks) - 3), -1):
            acc = wn[j] + acc
            if acc.endswith(target) or acc.replace("'", "") == target.replace("'", ""):
                return words[:i + 1], words[i][1]
    return None


def fix_text(words, fixes):
    """Apply reviewer corrections: [near_seconds, "wrong words", "right words", [times]].

    The optional 4th field gives the replacement words their MEASURED start times.
    Without it the span is shared out by word length, which is a guess - fine for a
    one-for-one swap ("parkers" -> "parkas"), wrong when the count changes. Kamay,
    23 Sept: Kevin says "really" three times and only two were captioned; splitting
    the old two-word span three ways would have put all three ~0.4s early.
    """
    words = list(words)
    for fix in fixes:
        near, wrong, right = fix[0], fix[1], fix[2]
        at = fix[3] if len(fix) > 3 else None
        wt = [norm(x) for x in wrong.split()]
        best = None
        for i in range(len(words) - len(wt) + 1):
            if [norm(words[i + k][2]) for k in range(len(wt))] == wt:
                d = abs(words[i][0] - near)
                if best is None or d < best[0]:
                    best = (d, i)
        if best is None or best[0] > 6.0:
            print(f"    !! fix not applied, '{wrong}' not found near {near}s", flush=True)
            continue
        i = best[1]
        rw = right.split()
        ts, te = words[i][0], words[i + len(wt) - 1][1]
        if at is not None:
            assert len(at) == len(rw), f"{len(at)} times for {len(rw)} words in '{right}'"
            new = [(round(at[k], 3), round(at[k + 1] if k + 1 < len(at) else max(te, at[k] + 0.25), 3), w)
                   for k, w in enumerate(rw)]
        else:
            tot = sum(len(w) for w in rw) or 1
            new, t = [], ts
            for w in rw:
                d = (te - ts) * len(w) / tot
                new.append((round(t, 3), round(t + d, 3), w)); t += d
        words[i:i + len(wt)] = new
    return words


def build(name, a, b, src, close_phrase, fixes=()):
    words = accurate_words(src, a, b, f"VSC2/{name}")
    # quote marks come from EITHER pass and hide sentence ends from the line breaker
    words = [(x, y, w.strip('"\u201c\u201d')) for x, y, w in words if w.strip('"\u201c\u201d')]
    # corrections FIRST: THE-CHINESE-FARMER's closing "there's just news" could not be
    # found while whisper still had it as "There is just news."
    words = fix_text(words, fixes)
    words, close_end = cut_after_close(words, close_phrase)
    bursts = kt_render.phrases_from_words(words)
    os.makedirs(OUT, exist_ok=True)
    json.dump({"words": words, "bursts": bursts, "close_end": close_end},
              open(os.path.join(OUT, name + ".json"), "w"), indent=0)
    return words, bursts, close_end


if __name__ == "__main__":
    ab = json.load(open(os.path.join(WORK, "v2_ab.json")))
    fixes = json.load(open(os.path.join(WORK, "v2_fixes.json"))) if os.path.exists(
        os.path.join(WORK, "v2_fixes.json")) else {}
    close = {n: c for p, cl in CUTS.items() for n, r, f, c, h in cl}
    pre = {n: p for p, cl in CUTS.items() for n, *_ in cl}
    only = sys.argv[1:] or sorted(ab)
    for name in only:
        r = ab[name]
        src = glob.glob(os.path.expanduser(f"~/Desktop/VSC/Source/{pre[name]}*.mp4"))[0]
        w, bu, ce = build(name, r["a"], r["b"], src, close[name], fixes.get(name, []))
        print(f"  {name:30} {len(w):4d} words -> {len(bu):3d} captions | close found at "
              f"{'%.2f' % ce if ce is not None else 'NOT FOUND'} (clip ends {r['b']-r['a']:.2f})",
              flush=True)
    print("V2CAPSDONE")


def refinish(name, close_phrase, fixes):
    """Re-apply corrections to words ALREADY transcribed - no whisper re-run.

    The first pass saved each clip's words; corrections are cheap text edits on top.
    """
    P = os.path.join(OUT, name + ".json")
    raw = P.replace(".json", ".raw.json")
    if not os.path.exists(raw):                      # keep the first transcription forever
        json.dump(json.load(open(P))["words"], open(raw, "w"))
    words = [tuple(w) for w in json.load(open(raw))]
    words = [(x, y, w.strip('"“”')) for x, y, w in words if w.strip('"“”')]
    words = fix_text(words, fixes)
    words, close_end = cut_after_close(words, close_phrase)
    bursts = kt_render.phrases_from_words(words)
    json.dump({"words": words, "bursts": bursts, "close_end": close_end}, open(P, "w"), indent=0)
    return words, bursts, close_end
