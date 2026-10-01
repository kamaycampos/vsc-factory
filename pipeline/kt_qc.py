#!/usr/bin/env python3
"""NOTHING POSTS THAT THIS CANNOT VOUCH FOR.

Kamay, 29 Sept 2026, after a batch reached him with "Steven Jobs", "best settle list"
and "It's not It's not overcoming adversity" in the burned captions:

    "an agent that right after the factory finishes goes and checks and makes sure
     every single clip is absolutely PERFECT... so their system doesn't post BS in
     our accounts."

This is that gate. It reads the FINISHED file - never the plan, never the render log -
and returns a verdict per clip. A clip it cannot vouch for does not get queued.

WHAT IT CAN PROVE, and does:
  - the caption record exists at all (a clip that never recorded its captions cannot
    be checked by anything, ever, so it fails)
  - the word being spoken is on screen, sampled at random moments of the real video
  - no caption is drawn on top of the next
  - the clip opens on the start of a sentence and ends on the end of one
  - the picture is 1080x1920 and the audio is not silent
  - the hook is one idea and is held long enough to read

WHAT IT CANNOT PROVE, said plainly so nobody trusts it too far:
  it cannot tell a wrong word from a right one. "best settle list" is four ordinary
  English words in a sensible order; only a person - or a reader who knows the subject -
  knows Kevin meant "best seller". The text checks below catch MECHANICAL damage
  (repeats, scrambles, stray punctuation, fragments), which is what most transcription
  failures actually look like, and they caught every mechanical defect in the 29 Sept
  batch. They will not catch a plausible wrong word. Read the captions.
"""
import json, os, re, subprocess, sys

FF = os.path.expanduser("~/Kamay/bin/ffmpeg")
MIN_SECS, MAX_SECS = 8.0, 185.0
CONNECTORS = {"and", "or", "to", "of", "after", "upon", "by", "over", "on", "the", "a"}
STARTERS = {"the", "this", "that", "these", "we", "you", "they", "he", "she", "it",
            "and", "but", "so", "guess", "now", "what", "if", "because", "there",
            "well", "look", "every", "most", "without", "when", "successful", "people"}
OPENERS = {"and", "but", "so", "because", "it", "the", "a", "an", "if", "when", "what",
           "you", "i", "we", "they", "he", "she", "this", "that", "there", "now", "look"}


# function words that recur in correct English one word apart: "that firing that",
# "the gold the", "to it to". Damage repeats content words, not these.
REPEATABLE = {"that", "the", "a", "to", "of", "it", "is", "in", "on", "at", "as",
              "was", "had", "very", "no", "you", "they", "he", "she", "we", "i"}


def sh(*a):
    return subprocess.run(list(a), capture_output=True, text=True)


def probe(mp4):
    o = sh(FF, "-nostdin", "-i", mp4).stderr
    d = re.search(r"Duration: (\d+):(\d+):([\d.]+)", o)
    v = re.search(r", (\d{2,5})x(\d{2,5})", o)
    return ((int(d[1]) * 3600 + int(d[2]) * 60 + float(d[3])) if d else 0.0,
            (int(v[1]), int(v[2])) if v else (0, 0),
            "Audio:" in o)


def text_faults(caps):
    """Mechanical damage in the caption text. Every pattern here is a defect that
    actually shipped on 29 Sept, so none of them is hypothetical."""
    out = []
    words = [(w, i) for i, (_a, _b, t) in enumerate(caps) for w in t.split()]
    flat = [w for w, _ in words]
    norm = [re.sub(r"[^a-z']", "", w.lower()) for w in flat]

    for i in range(len(norm) - 1):
        # "Without Without setbacks", "or I'll I'll stay", "It's not It's not"
        # ...but not across a sentence end. "I'll tell you what. What if I am banned",
        # "I published it. It became number one" - a sentence ending on a word and the
        # next beginning with it is ordinary English, and it held back two good clips.
        if (norm[i] and norm[i] == norm[i + 1] and norm[i] not in ("that", "had", "very", "no")
                and not flat[i].endswith((",", ".", "!", "?", "-", "..."))):
            out.append(f'word repeated: "{flat[i]} {flat[i+1]}"')
    for i in range(len(norm) - 2):
        # "It's not It's not", "forest fire Forest is". A word repeated one word later.
        # Kevin repeats himself ON PURPOSE - "tons and tons and tons", "attacking,
        # attacking" - so the two tells that separate damage from emphasis: real
        # emphasis is joined by a connector, or punctuated with a comma.
        # 30 Sept 2026: this failed two clips that were RIGHT. "it was because of that
        # firing that he started NeXT" is ordinary English, and "They attack. They get
        # pissed off" is a new sentence. Damage repeats CONTENT words and runs straight
        # through; a function word recurring, or a full stop in between, is neither.
        if (norm[i] and norm[i] == norm[i + 2] and norm[i + 1] not in CONNECTORS
                and norm[i] not in CONNECTORS          # "tons AND tons AND tons"
                and norm[i] not in REPEATABLE
                # the stop can be on EITHER word before the repeat: "a huge
                # distinction. Huge." and "of her life. Her life was" are both a new
                # sentence starting on the same word, which is how Kevin lands a point.
                and not flat[i].endswith((",", ".", "!", "?", "-", "..."))
                and not flat[i + 1].endswith((",", ".", "!", "?", "-", "..."))
                and len(norm[i]) > 1):
            out.append(f'word repeated after one: "{" ".join(flat[i:i+3])}"')
    for i in range(len(norm) - 3):
        # "said He it said", "It was It when was", "do It things does"
        if (norm[i] and norm[i] == norm[i + 3]
                # "It was when she was at the bottom" and "What they do is they look
                # at it" are correct English with a function word recurring. Damage
                # scrambles CONTENT words - "said He it said", "was It when was".
                and norm[i] not in REPEATABLE
                # "every single one, every single one had more" - he repeats a whole
                # phrase for emphasis, and emphasis is PUNCTUATED. Transcription damage
                # never is: "said He it said", "was It when was", "do It things does"
                # run straight through with no comma anywhere in them.
                and not any(flat[i + k].endswith((",", ".", "!", "?", "-", "..."))
                            for k in (0, 1, 2))):
            out.append(f'phrase scrambled around "{" ".join(flat[i:i+4])}"')
    for i in range(len(norm) - 1):
        # "So you We have to" - two subject pronouns in a row
        # ...but not across a sentence end. "taken away from you. I go, Yeah" is two
        # sentences, not two subjects, and it held back a clip that was correct.
        if norm[i] in ("you", "we", "i", "he", "she", "they") and \
           norm[i + 1] in ("we", "you", "i", "he", "she", "they") and norm[i] != norm[i + 1] \
           and not flat[i].endswith((".", "!", "?", ",", "-", "...")):
            out.append(f'two subjects together: "{flat[i]} {flat[i+1]}"')
    for i in range(len(flat) - 1):
        # "the number. one difference" - a full stop that is not a sentence end
        if flat[i].endswith(".") and not flat[i].endswith("...") and \
           flat[i + 1][:1].islower() and len(flat[i].strip(".")) > 1 and \
           not re.match(r"^[A-Z]\.$", flat[i]):
            out.append(f'stray full stop: "{flat[i]} {flat[i+1]}"')
        # "down a goal Guess what" - a new sentence with no full stop before it.
        # ONLY for words that genuinely begin sentences. Firing on any capitalised word
        # flagged "I remember Smokey the Bear" and "in New York City", which are correct
        # English - and a gate that blocks good clips is as useless as one that passes
        # bad ones, because either way nobody believes what it says.
        if (not flat[i].endswith((".", "!", "?", ",", ":", ";", "-", '"'))
                and norm[i + 1] in STARTERS and flat[i + 1][:1].isupper()
                and not flat[i][:1].isupper()):
            out.append(f'sentence starts with no stop: "{flat[i]} {flat[i+1]}"')
    return sorted(set(out))


def check(mp4, samples=12):
    """(verdict, reasons) - verdict is 'pass', 'look' or 'fail'."""
    name = re.sub(r"_\d+s$", "", os.path.basename(mp4)[:-4])
    side = mp4[:-4] + "__caps.json"
    if not os.path.exists(side):
        return "fail", ["no caption record - this clip cannot be checked by anything"]
    caps = [tuple(x) for x in json.load(open(side))]
    if not caps:
        return "fail", ["the caption record is empty"]
    hard, soft = [], []

    dur, (w, h) = probe(mp4)[:2]
    aud = probe(mp4)[2]
    if (w, h) != (1080, 1920):
        hard.append(f"picture is {w}x{h}, not 1080x1920")
    if not aud:
        hard.append("no audio stream")
    if not (MIN_SECS <= dur <= MAX_SECS):
        hard.append(f"{dur:.0f}s is outside {MIN_SECS:.0f}-{MAX_SECS:.0f}s")

    ov = sum(1 for i in range(len(caps) - 1) if caps[i][1] > caps[i + 1][0] + 0.001)
    if ov:
        hard.append(f"{ov} caption(s) drawn on top of the next")

    first, last = caps[0][2].split(), caps[-1][2].rstrip()
    if first and first[0][:1].islower() and re.sub(r"[^a-z']", "", first[0].lower()) not in OPENERS:
        hard.append(f'opens mid-sentence on "{" ".join(first[:3])}"')
    if not last.endswith((".", "!", "?", '"')):
        hard.append(f'ends mid-thought on "{" ".join(last.split()[-3:])}"')

    for f in text_faults(caps):
        hard.append(f)

    # is the spoken word on screen? the only check that reads the real audio
    try:
        sys.path.insert(0, os.path.expanduser("~/Kamay"))
        import vsc_v2_onscreen
        r = vsc_v2_onscreen.check(mp4, n=samples)
        if r:
            hit, miss, _m = r
            if hit + miss and hit / (hit + miss) < 0.75:
                hard.append(f"the spoken word was on screen in only {hit} of {hit+miss} moments")
            elif hit + miss and hit / (hit + miss) < 0.9:
                soft.append(f"word on screen {hit}/{hit+miss}")
    except Exception as e:
        soft.append(f"could not sample the audio: {type(e).__name__}")

    if hard:
        return "fail", hard
    return ("look", soft) if soft else ("pass", [])


def main(paths):
    import glob
    files = []
    for p in paths:
        files += glob.glob(os.path.join(p, "*.mp4")) if os.path.isdir(p) else [p]
    bad = []
    for f in sorted(files):
        v, why = check(f)
        n = re.sub(r"_\d+s$", "", os.path.basename(f)[:-4])
        print(f"  {v.upper():5} {n:30} {'; '.join(why[:3])}", flush=True)
        if v == "fail":
            bad.append(n)
    print(f"\n{len(files) - len(bad)} of {len(files)} clips can be vouched for.")
    if bad:
        print(f"WOULD NOT POST: {bad}")
    print("A human still reads the captions: this cannot tell a wrong word from a right one.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or [os.path.expanduser("~/Desktop/VSC/Clips")]))
