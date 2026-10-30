#!/usr/bin/env python3
"""Choose the clips for every stub plan - one Claude call, checked by code.

    python cloud/autoplan.py

5 Oct 2026. A VSC batch used to be planned by hand inside an Opus chat that grew to
672K tokens and burned most of a week's limit. The KT and AR accounts plan without
anyone watching. This is the VSC version, built to be safe as well as cheap:

  - ONE request, no tools. Claude reads the rules, the delivered batch and the
    transcript, and answers with JSON in a fixed schema. It cannot run commands, edit
    files or push - it only returns data.
  - CODE DECIDES what is kept: every opening and closing line must be found word for
    word in the transcript, the renderer's own search (first open, last close, in the
    region +/- 22-28 s) is replayed on the transcript so the length of SPEECH is checked,
    not the region, and cloud/check_plan.py must pass. Two repair rounds with the
    problems listed; if it still fails, the stub stays a stub and the run goes RED.
  - Only plans/<key>.json is ever written; the workflow commits plans/ and nothing else.

Needs the ANTHROPIC_API_KEY repository secret (pay per use: roughly $0.20-0.60 a batch
on Claude Opus 5.5). Without it, this step prints what is missing and changes nothing.
Model override: the VSC_PLANNER_MODEL repository variable.
"""
import glob
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import check_plan  # noqa: E402

REPO = os.environ.get("GITHUB_REPOSITORY", "kamaycampos/vsc-factory")
MODEL = os.environ.get("VSC_PLANNER_MODEL") or "claude-opus-5-5"
ATTEMPTS = 4        # the first answer, then up to three repair rounds with the problems listed
MIN_KEEP = 6        # after the last round, keep the clips that pass if at least this many do
PER_MIN = 0.45      # whole teachings a minute of episode holds (PLANNING.md step 3: 27 min -> 12)

SCHEMA = {
    "type": "object",
    "properties": {
        "clips": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "region": {"type": "array", "items": {"type": "number"}},
                    "open": {"type": "string"},
                    "close": {"type": "string"},
                    "hook": {"type": "array", "items": {"type": "string"}},
                    "short_ok": {"type": "string"},
                },
                "required": ["name", "region", "open", "close", "hook", "short_ok"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["clips"],
    "additionalProperties": False,
}


def norm(s):
    return re.sub(r"[^a-z0-9 ]", "", re.sub(r"\s+", " ", str(s).lower())).strip()


def rules():
    """'The rules' from CLAUDE.md - the reviewers' hard rules, in one place."""
    md = open(os.path.join(ROOT, "CLAUDE.md")).read()
    m = re.search(r"## The rules.*?(?=\n## )", md, re.S)
    return m.group(0) if m else md


def example():
    """The delivered, reviewer-approved batch: the shape and the standard."""
    # finished projects live in plans/done/ (15 Oct 2026): out of every build, still the example
    p = json.load(open(os.path.join(ROOT, "plans", "done", "millionaires_problems.json")))
    keep = ("name", "region", "open", "close", "hook", "short_ok")
    return json.dumps([{k: c[k] for k in keep if k in c} for c in p["clips"]], indent=1)


def transcript(p):
    """TRANSCRIPT_<prefix key>.txt, as prep publishes it to the prep release.

    GitHub rewrites an asset's name on upload - spaces (and most punctuation) become
    dots - so the name prep uploads is never the name that comes back. Run 48 (7 Oct)
    asked for "TRANSCRIPT_Why Millionaires millionaires_full.txt", found nothing, planned
    nothing and went green. Match on letters and digits only, then fetch by the stored name.
    """
    want = f"TRANSCRIPT_{(p['prefix'] + ' ' + p['key'])[:40]}.txt"
    key = re.sub(r"[^a-z0-9]", "", want.lower())
    r = subprocess.run(["gh", "release", "view", "prep", "-R", REPO, "--json", "assets"],
                       capture_output=True, text=True)
    if r.returncode:
        print(f"::warning::could not list the prep release: {r.stderr.strip()[:200]}")
        return None
    names = [a["name"] for a in json.loads(r.stdout).get("assets", [])]
    name = next((n for n in names if re.sub(r"[^a-z0-9]", "", n.lower()) == key), None)
    if not name:
        return None
    os.makedirs("/tmp/autoplan", exist_ok=True)
    subprocess.run(["gh", "release", "download", "prep", "-R", REPO, "-p", name,
                    "-D", "/tmp/autoplan", "--clobber"], capture_output=True)
    f = os.path.join("/tmp/autoplan", name)
    return open(f).read() if os.path.exists(f) else None


LINE = re.compile(r"^\[(\d+):(\d+(?:\.\d+)?)(?: [A-Z+]+)?\]\s*(.*)$", re.M)   # [mm:ss.ss GUEST]


def timed_words(text):
    """[(t, word)] from the [mm:ss.ss] transcript. A line only says when it STARTS, so
    each word's time is interpolated to the next line's start - a few seconds out at
    worst, which is all the checks below need."""
    lines = [(int(m[1]) * 60 + float(m[2]), m[3]) for m in LINE.finditer(text)]
    out = []
    for k, (t0, s) in enumerate(lines):
        ws = [w for w in (norm(x) for x in s.split()) if w]
        t1 = lines[k + 1][0] if k + 1 < len(lines) else t0 + 0.4 * len(ws)
        out += [(t0 + (t1 - t0) * i / max(1, len(ws)), w) for i, w in enumerate(ws)]
    return out


def where(tw, phrase):
    """[(start, end)] of every place the phrase is spoken."""
    p = [w for w in (norm(x) for x in phrase.split()) if w]
    if not p:
        return []
    n, ws = len(p), [w for _, w in tw]
    return [(tw[i][0], tw[i + n - 1][0]) for i in range(len(ws) - n + 1) if ws[i:i + n] == p]


def mmss(t):
    return f"{int(t // 60):02d}:{t % 60:04.1f}"


def searched(c, tw):
    """Every place the open / close words are spoken where the renderer looks for them."""
    a0, b0 = max(0.0, c["region"][0] - 22), c["region"][1] + 28
    return ([x for x in where(tw, c["open"]) if a0 <= x[0] <= b0],
            [x for x in where(tw, c["close"]) if a0 <= x[1] <= b0])


def located(c, tw):
    """What the renderer will cut, found the way pipeline/vsc_pick.locate finds it:
    in region-22 .. region+28 s, the FIRST place the opening is spoken and the LAST place
    the closing is. The region is only where it looks - the WORDS set the clip's length.
    The delivered batch padded its regions by 5-24 s, so a clip of 27 s of speech passed
    the 40 s minimum on a 40 s region. Measured here, it cannot."""
    o, e = searched(c, tw)
    out, n = [], c["name"]
    if not o:
        out.append(f"{n}: the opening is not spoken inside your region (+/- the 22-28 s the "
                   "renderer searches) - fix the region or the open")
    if not e:
        out.append(f"{n}: the closing is not spoken inside your region (+/- the 22-28 s the "
                   "renderer searches) - fix the region or the close")
    if out:
        return out
    if len(o) > 1:
        out.append(f"{n}: the open words are spoken {len(o)} times where the renderer looks ("
                   + ", ".join(mmss(x[0]) for x in o) + ") and it takes the FIRST - choose "
                   "opening words that occur only where the clip starts")
    if len(e) > 1:
        out.append(f"{n}: the close words are spoken {len(e)} times where the renderer looks ("
                   + ", ".join(mmss(x[1]) for x in e) + ") and it takes the LAST - choose "
                   "closing words that occur only where the teaching lands")
    t0, t1 = o[0][0], e[-1][1]
    span = t1 - t0
    if span <= 0:
        out.append(f"{n}: the closing is spoken before the opening")
    elif span > check_plan.MAX_LEN - 1:
        out.append(f"{n}: from the open to the close words is ~{span:.0f} s of speech "
                   f"({mmss(t0)}-{mmss(t1)}) - over the {check_plan.MAX_LEN:.0f} s ceiling; split "
                   "it where a second complete idea begins")
    elif span < check_plan.MIN_LEN - 2 and not c.get("short_ok"):
        out.append(f"{n}: from the open to the close words is only ~{span:.0f} s of speech "
                   f"({mmss(t0)}-{mmss(t1)}) - the region does not set the length, the words "
                   "do. Keep the whole teaching (setup, proof, landing), or if it truly is "
                   "complete, say why in short_ok")
    return out


# ----------------------------------------------------------------- THE PAUSES (13 Oct 2026)
# why_your_prayers_fail: 13 of 15 clips came back "no pause before the open" or "no pause
# after the close", and two could not be rendered at all ("missing closing"). The planner
# chose its words from a transcript that cannot show silence, and they were checked against
# that transcript - while the renderer searches the WORD-TIMING pass and cuts in the SOUND.
# So the planner now reads a transcript whose every line break IS a real pause (prep's
# pauses-<key>.json, measured by quiet_runs' rule), and its words are checked the way the
# renderer finds them: in the word stream, loosely, inside region -22/+28 s, with a pause
# before the open and after the close. Calibrated on that batch: these rules called 22 of
# the renderer's 26 edge verdicts, and were stricter on the rest.
PAUSE = None                 # (words, pauses) for the plan being chosen, when prep made them
# WHO IS TALKING (18 Oct 2026, Naomi, for the interview episodes): "we want clips that
# focus on Kevin talking (it can be talking with John but we don't want clips focusing
# only on John)". prep's speakers-<key>.json gives every word a voice ("K", "G", "?");
# the guest's lines are tagged in the transcript and a clip must give Kevin KEVIN_MIN of
# its speech and close on his words. SPEAKERS is False for a solo episode or no map.
SPEAKERS = False
KEVIN_MIN = 0.60
CUTS = False                 # True when those are measured cut points: clips get start_at/end_at
OPEN_GAP, CLOSE_GAP = 0.15, 0.20


def gap_before(pauses, t):
    """The longest pause pause_before() would take for a first word starting at t."""
    return max((b - a for a, b in pauses if a <= t + 0.15 and t - 0.6 <= b <= t + 2.5), default=0.0)


def gap_after(pauses, t):
    """The longest pause pause_after() would take after a last word ending at t."""
    return max((b - a for a, b in pauses if b >= t - 0.25 and t - 1.0 <= a <= t + 0.5), default=0.0)


def cut_near(pauses, t, back=0.8, ahead=0.25):
    """The longest gap overlapping [t - back, t + ahead]: the one a word starting at t
    sits right after (as measured by hand on 15 Oct)."""
    c = [r for r in pauses if r[1] >= t - back and r[0] <= t + ahead]
    return max(c, key=lambda r: r[1] - r[0]) if c else None


def prep_data(p):
    """(words, pauses) from the prep release, or None - then only the old checks run."""
    global CUTS, OPEN_GAP, CLOSE_GAP
    CUTS, OPEN_GAP, CLOSE_GAP = False, 0.15, 0.20      # per plan: an older v1 map keeps the old rule
    d = "/tmp/autoplan/prep"
    os.makedirs(d, exist_ok=True)
    for pat in (f"prep-{p['key']}.tar.gz", f"pauses-{p['key']}.json", f"speakers-{p['key']}.json"):
        subprocess.run(["gh", "release", "download", "prep", "-R", REPO, "-p", pat, "-D", d,
                        "--clobber"], capture_output=True)
    try:
        import tarfile
        with tarfile.open(os.path.join(d, f"prep-{p['key']}.tar.gz")) as t:
            m = next(m for m in t.getmembers() if m.name.endswith(f"{p['key']}.words.json"))
            words = json.load(t.extractfile(m))
        pm = json.load(open(os.path.join(d, f"pauses-{p['key']}.json")))
        # v2 maps carry measured cut points (cloud/pauses.cut_points, 15 Oct 2026): many
        # more places a clip can start and end, each cut with an exact start_at / end_at
        CUTS = bool(pm.get("cuts"))
        pauses = [r[:2] for r in pm["cuts"]] if CUTS else pm["pauses"]
        if CUTS:
            OPEN_GAP, CLOSE_GAP = 0.12, 0.15
    except Exception as e:
        print(f"::warning::{p['key']}: no pause map ({type(e).__name__}) - planning without it")
        return None
    for w in words:
        w["n"] = re.sub(r"[^a-z0-9']", "", w["t"].lower())
    global SPEAKERS
    SPEAKERS = False
    try:
        from speakers import who, trusted          # cloud/ is on sys.path (HERE)
        sm = json.load(open(os.path.join(d, f"speakers-{p['key']}.json")))
        for w in words:
            w["s"] = who(sm["spans"], (w["a"] + w["b"]) / 2)
        SPEAKERS = trusted(sm)
        print(f"  speaker map: the guest holds {sm['guest_share']:.0%} of the speech"
              + ("" if SPEAKERS else " - NOT TRUSTED (the voices do not separate, or a solo "
                 "episode): no tags, the planner judges who speaks from the words"))
        if sm["guest_share"] and not SPEAKERS:
            print(f"::warning::{p['key']}: the speaker map cannot tell Kevin from the guest "
                  f"({sm.get('kevin_vs_ref')} / {sm.get('guest_vs_ref')} vs his reference) - "
                  "Kevin focus is the planner's judgment; check every clip's speaker")
    except Exception as e:
        print(f"::warning::{p['key']}: no speaker map ({type(e).__name__}) - cannot check "
              "that clips focus on Kevin")
    return words, pauses


def paused_transcript(words, pauses):
    """The words, one line per stretch of speech: a new line starts only after a pause the
    renderer can cut in (>= CLOSE_GAP after the last word, >= OPEN_GAP before the next)."""
    lines, cur = [], []
    for k, w in enumerate(words):
        cur.append(w)
        nxt = words[k + 1] if k + 1 < len(words) else None
        if nxt is None or (gap_after(pauses, w["b"]) >= CLOSE_GAP
                           and gap_before(pauses, nxt["a"]) >= OPEN_GAP):
            a = cur[0]["a"]
            tag = voice_tag(cur) if SPEAKERS else ""
            lines.append(f"[{int(a // 60):02d}:{a % 60:05.2f}{tag}] " + " ".join(x["t"] for x in cur))
            cur = []
    return "\n".join(lines)


def _near(a, b):
    import difflib
    return a == b or (min(len(a), len(b)) >= 4 and difflib.SequenceMatcher(a=a, b=b).ratio() >= 0.8)


def _find(ws, phrase, last=False):
    """pipeline/vsc_pick._find: exact first, then one word heard differently."""
    toks = [t for t in (re.sub(r"[^a-z0-9']", "", x.lower()) for x in phrase.split()) if t]
    if not toks:
        return None
    for loose in (False, True):
        hits = []
        for i in range(len(ws) - len(toks) + 1):
            got = [ws[i + k]["n"] for k in range(len(toks))]
            same = sum(1 for a, b in zip(got, toks) if (_near(a, b) if loose else a == b))
            if same == len(toks) or (loose and len(toks) >= 4 and same >= len(toks) - 1):
                hits.append(i)
        if hits:
            return hits[-1] if last else hits[0]
    return None


def voice_tag(ws):
    """" GUEST" when the guest says most of a line, " KEVIN+GUEST" when both say a fair
    part of it, "" for Kevin's own lines (the rest of the transcript)."""
    k = sum(w["b"] - w["a"] for w in ws if w.get("s") == "K")
    g = sum(w["b"] - w["a"] for w in ws if w.get("s") == "G")
    if g > k:
        return " GUEST" if k < 0.3 * (k + g) else " GUEST+KEVIN"
    return " KEVIN+GUEST" if g >= 0.3 * (k + g) else ""


def kevin_focus(c, ws):
    """GIN wants Kevin's clips: he carries KEVIN_MIN of the speech and lands the close."""
    k = sum(w["b"] - w["a"] for w in ws if w.get("s") == "K")
    g = sum(w["b"] - w["a"] for w in ws if w.get("s") == "G")
    out = []
    if k + g > 0 and k / (k + g) < KEVIN_MIN:
        out.append(f"{c['name']}: Kevin speaks only {k / (k + g):.0%} of it - the guest carries "
                   "this clip. GIN wants clips that focus on KEVIN (the guest may ask and react). "
                   "Choose a stretch where Kevin teaches, or drop it")
    tail = [w for w in ws[-6:] if w.get("s") in ("K", "G")]
    if tail and sum(1 for w in tail if w["s"] == "G") > len(tail) / 2:
        out.append(f"{c['name']}: it closes on the GUEST's words - end where KEVIN lands the teaching")
    return out


def at_pauses(c):
    """What the RENDERER will find for this clip, judged on the word stream and the pause
    map. Empty = it opens and closes in silence and both ends can be located."""
    words, pauses = PAUSE
    n = c["name"]
    a0, b0 = max(0.0, c["region"][0] - 22), c["region"][1] + 28
    ws = [w for w in words if a0 <= w["a"] <= b0]
    i, j = _find(ws, c["open"]), _find(ws, c["close"], last=True)
    out = []
    if i is None:
        out.append(f"{n}: the renderer cannot find the open \"{c['open']}\" in the word stream "
                   "near your region - copy it exactly from the start of a line")
    if j is None:
        out.append(f"{n}: the renderer cannot find the close \"{c['close']}\" in the word stream "
                   "near your region - copy it exactly from the end of a line")
    if out:
        return out
    je = j + len([t for t in c["close"].split() if re.sub(r"[^a-z0-9']", "", t.lower())]) - 1
    t0, t1 = ws[i]["a"], ws[min(je, len(ws) - 1)]["b"]
    rs = re_ = None
    if CUTS and not out:
        # THE EXACT CUT, from the gap itself - whisper's word times run up to half a
        # second early, so the renderer is told where the silence is (start_at / end_at)
        # and its edge listening checks the result. Same placement as the 8 hand cuts of
        # 15 Oct: start up to 0.25 s before the voice, end 0.15 s into the gap.
        nxt = ws[je + 1]["a"] if je + 1 < len(ws) else t1 + 0.5
        lw = ws[min(je, len(ws) - 1)]
        rs, re_ = cut_near(pauses, t0), cut_near(pauses, nxt)
        # A LONG LAST WORD IS SEARCHED FIRST (30 Oct 2026, they_re_not_hiding): whisper ran
        # "experience." 613.83-623.94 over the interviewer's whole question, so the "next
        # word" sat 10 s on and the gap beside it would have put his question in the clip.
        # The gap is the longest inside the word's first 2 s; none there = no clean close.
        if lw["b"] - lw["a"] > 0.8:
            inside = [r for r in pauses if lw["a"] + 0.15 <= r[0] < min(lw["b"], lw["a"] + 2.0)
                      and r[1] - r[0] >= CLOSE_GAP]
            re_ = max(inside, key=lambda r: r[1] - r[0]) if inside else (re_ if lw["b"] - lw["a"] <= 2.0 else None)
        # THE END GAP IS THE ONE BEFORE THE NEXT WORD, never the one after it (28 Oct 2026):
        # THE-CHRISTMAS-CRASH closed "...seeking anything" and the longest gap in reach was
        # the pause AFTER "because" (378.82-379.69), so end_at kept "because" - the first
        # word of "because you have it all", the landing. A gap may end at most 0.5 s past
        # the next word's start (whisper's times run early), no later.
        if re_ and re_[1] > nxt + 0.5 and lw["b"] - lw["a"] <= 0.8:
            re_ = cut_near([r for r in pauses if r[1] <= nxt + 0.5], nxt)
        # ...and the start gap is the one AFTER the word before the open: DHARMA-IS-DUTY's
        # longest gap in reach (179.80-180.24) sat before the interviewer's "Is it?", so the
        # clip would have opened on his question.
        # (A gap that ends before the previous word even starts has a word between it and
        # the open; FOCUS-ONLY-ON-TODAY's gap overlaps whisper's late "loose." and is right.)
        if rs and i > 0 and rs[1] <= ws[i - 1]["a"] + 0.05:
            rs = cut_near([r for r in pauses if r[1] > ws[i - 1]["a"] + 0.05], t0)
        # (WHISPER SWALLOWS THE PAUSE INTO A LONG LAST WORD, CLAUDE.md: "all." ran
        # 380.41-382.48 and held the gap at 380.67 - the long-word search above finds it.)
        if rs:
            c["start_at"] = round(max(rs[0], rs[1] - 0.25), 2)
        if re_:
            c["end_at"] = round(re_[0] + min(0.15, (re_[1] - re_[0]) / 2), 2)
    open_ok = (rs is not None and rs[1] - rs[0] >= OPEN_GAP) if CUTS else gap_before(pauses, t0) >= OPEN_GAP
    close_ok = (re_ is not None and re_[1] - re_[0] >= CLOSE_GAP) if CUTS else gap_after(pauses, t1) >= CLOSE_GAP
    if not open_ok:
        out.append(f"{n}: the open \"{c['open']}\" ({mmss(t0)}) is not after a pause - Kevin is "
                   "still talking into it. Start on the FIRST words of a transcript line")
    if not close_ok:
        out.append(f"{n}: the close \"{c['close']}\" ({mmss(t1)}) runs straight into his next words "
                   "- end on the LAST words of a transcript line, where the teaching lands")
    if SPEAKERS:
        out += kevin_focus(c, ws[i:je + 1])
    span = t1 - t0
    if span > check_plan.MAX_LEN - 1:
        out.append(f"{n}: {span:.0f} s of speech from open to close - over the "
                   f"{check_plan.MAX_LEN:.0f} s ceiling")
    elif span < check_plan.FLOOR:
        out.append(f"{n}: only {span:.0f} s of speech from open to close - under GIN's "
                   f"{check_plan.FLOOR:.0f} s floor")
    elif span < check_plan.MIN_LEN and not c.get("short_ok"):
        out.append(f"{n}: only {span:.0f} s of speech from open to close - keep the whole teaching, "
                   "or say in short_ok why it is complete")
    return out


def target(p):
    """How many whole teachings the episode holds, at least (PLANNING.md step 3)."""
    return max(MIN_KEEP, round(float(p.get("duration") or 0) / 60 * PER_MIN))


def uncut(clips, tw, dur, least=150.0):
    """[(start, end)] stretches of at least `least` seconds that no clip covers."""
    spans = []
    for c in clips:
        o, e = searched(c, tw)
        if o and e:
            spans.append((o[0][0], e[-1][1]))
    out, t = [], 0.0
    for a, b in sorted(spans) + [(dur, dur)]:
        if a - t >= least:
            out.append((t, a))
        t = max(t, b)
    return out


def problems(p, clips, text):
    """Everything code can check. Empty list = keep it. A "BATCH:" problem is about the
    whole batch (too few clips): it goes back to the planner, but never sinks the clips
    that pass at the end."""
    out = []
    if not clips:
        return ["no clips"]
    # NEVER SHRINK A BATCH (Kamay, 30 Oct 2026: "8 clips are to less"). they_re_not_hiding
    # came out 9 clips from a 27-min episode with 15 minutes uncut: fragments were dropped
    # instead of re-cut as whole teachings. The planner hears the count and the uncut
    # stretches until the batch is full.
    want, dur = target(p), float(p.get("duration") or 0)
    if len(clips) < want:
        holes = uncut(clips, timed_words(text), dur)
        out.append(f"BATCH: only {len(clips)} clips - a {dur / 60:.0f}-minute episode holds at least "
                   f"{want} whole teachings (PLANNING.md step 3). Add the missing ones. Never fix a "
                   "problem by dropping or merging a clip: move its open or close to the nearest clean "
                   "line, or extend it to the lesson it is missing."
                   + (" No clip covers " + ", ".join(f"{mmss(a)}-{mmss(b)}" for a, b in holes)
                      + " - cut every whole teaching there (skip only intro chatter and the ad wall)."
                      if holes else ""))
    # The [mm:ss.ss] stamps come out first: left in, a phrase that runs across two
    # transcript lines would have a timestamp in the middle of it and never match.
    words = norm(LINE.sub(r"\3", text))
    tw = timed_words(text)
    for c in clips:
        found = True
        for k in ("open", "close"):
            if norm(c[k]) not in words:
                found = False
                out.append(f"{c['name']}: {k} \"{c[k]}\" is not in the transcript word for word")
        if len(c["region"]) != 2 or c["region"][0] >= c["region"][1]:
            out.append(f"{c['name']}: region must be [start, end] with start < end")
            continue
        if c["region"][1] > float(p.get("duration") or 1e9) + 1:
            out.append(f"{c['name']}: region ends after the episode does")
        if found:
            out += located(c, tw)
            if PAUSE:
                out += at_pauses(c)
    # Names are unique across every plan: the clips release and built.json are keyed by
    # name, so a redo reusing a delivered name would overwrite the file GIN already has.
    taken = {}
    for f in glob.glob(os.path.join(ROOT, "plans", "*.json")) + glob.glob(os.path.join(ROOT, "plans", "done", "*.json")):
        o = json.load(open(f))
        if o.get("key") != p.get("key"):
            taken.update({c["name"]: o["key"] for c in o.get("clips", [])})
    for c in clips:
        if c["name"] in taken:
            out.append(f"{c['name']}: that name is already used by plans/{taken[c['name']]}.json - choose a new one")
    trial = dict(p, clips=clips)
    os.makedirs("/tmp/autoplan", exist_ok=True)
    path = "/tmp/autoplan/_trial.json"
    json.dump(trial, open(path, "w"))
    errs, _warns = check_plan.check(path, {})
    return out + errs


def clean(raw):
    clips = []
    for c in raw:
        c = dict(c)
        c["name"] = re.sub(r"[^A-Z0-9]+", "-", c["name"].upper()).strip("-")
        c["hook"] = [h.strip().upper() for h in c["hook"]][:2]
        c["region"] = [round(float(x), 1) for x in c["region"]]
        if not c.get("short_ok", "").strip():
            c.pop("short_ok", None)
        c["fixes"] = []
        clips.append(c)
    return clips


def thin_punctuation(text, window=300.0, floor=4.0):
    """[(start, end, stops per minute)] for every 5-minute stretch under `floor`.

    RULES #2: a cutter cannot find a sentence boundary the transcript does not contain,
    and whisper drifts on long files - the second half of KT's 7 Oct transcript came back
    with almost no full stops. Reported on the run page so a thin stretch is visible
    before anyone wonders why its clips open mid-thought."""
    lines = [(int(m[1]) * 60 + float(m[2]), m[3]) for m in LINE.finditer(text)]
    if not lines:
        return []
    out, t, end = [], 0.0, lines[-1][0]
    while t < end:
        seg = " ".join(s for a, s in lines if t <= a < t + window)
        mins = min(window, end - t) / 60
        if mins >= 1 and seg.strip():
            rate = len(re.findall(r"[.!?](?:\s|$)", seg)) / mins
            if rate < floor:
                out.append((t, min(t + window, end), rate))
        t += window
    return out


def plan_one(client, p, text):
    system = (open(os.path.join(ROOT, "PLANNING.md")).read() + "\n\n" + rules() +
              "\n\n## The delivered, reviewer-approved batch (shape and standard)\n" + example())
    if p.get("redo_of"):
        f = os.path.join(ROOT, "plans", p["redo_of"] + ".json")
        old = json.load(open(f if os.path.exists(f) else os.path.join(ROOT, "plans", "done", p["redo_of"] + ".json")))
        system += (
            f"\n\n## THIS IS A REDO of {p['redo_of']} - the SAME episode as the batch above\n"
            "Kamay, 5 Oct: that batch came out 30-82 s and CUT THE TEACHING. It was planned while "
            "the renderer died on clips over ~62 s, so long teachings were split into pieces; the "
            "renderer is fixed. Re-cut the episode: every clip runs from the start of the thought "
            f"to where the teaching lands - setup, proof and landing - never over {check_plan.MAX_LEN:.0f} s. "
            "Where one lesson was split across several clips above, make it ONE clip. Keep "
            "different tellings of a lesson only when each is complete on its own. Every clip "
            "needs a NEW name, different from every name above.\n"
            f"Notes on this episode: {old.get('note', '')}")
    user = (f"Episode: \"{p.get('title') or p['key']}\", {p.get('duration', '?')} seconds long.\n"
            + ("Transcript: every line is one stretch of speech, and EVERY LINE BREAK IS A REAL "
               "PAUSE in the sound - the only places a clip can be cut cleanly. Each line starts "
               "at [mm:ss.ss] source time. `open` = the first words of a line; `close` = the last "
               "words of a line.\n"
               + ("Lines tagged GUEST (or GUEST+KEVIN / KEVIN+GUEST) are spoken by the guest "
                  "(mostly / partly); untagged lines are Kevin's. Clips must FOCUS ON KEVIN: "
                  f"he speaks at least {KEVIN_MIN:.0%} of every clip and its close is his.\n"
                  if SPEAKERS else "") + "\n" if PAUSE else
               "Transcript (each line starts at [mm:ss.ss] source time):\n\n") + text)
    messages = [{"role": "user", "content": user}]
    import anthropic
    for attempt in range(1, ATTEMPTS + 1):
        try:
            # cache_control: a repair round re-reads the brief and the transcript from the
            # cache (a tenth of the price) instead of paying for them again.
            with client.beta.messages.stream(
                model=MODEL, max_tokens=64000, system=system, messages=messages,
                output_config={"effort": "high",
                               "format": {"type": "json_schema", "schema": SCHEMA}},
                cache_control={"type": "ephemeral"},
                betas=["server-side-fallback-2026-07-01"], fallbacks="default",
            ) as stream:
                r = stream.get_final_message()
        except anthropic.APIError as e:
            # The SDK has already retried 429 / 5xx / dropped connections twice.
            print(f"::error::{p['key']}: the Claude API failed: {type(e).__name__}: {str(e)[:300]}")
            return None
        if r.stop_reason == "refusal":
            print(f"::error::{p['key']}: the model declined ({getattr(r, 'stop_details', None)})")
            return None
        if r.stop_reason == "max_tokens":
            print(f"::error::{p['key']}: the answer was cut off at max_tokens")
            return None
        text_out = "".join(b.text for b in r.content if b.type == "text")
        try:
            clips = clean(json.loads(text_out)["clips"])
            bad = problems(p, clips, text)
        except (ValueError, KeyError, TypeError, IndexError, AttributeError) as e:
            clips, bad = [], [f"the answer was not the JSON batch asked for ({e})"]
        print(f"  attempt {attempt}: {len(clips)} clips, {len(bad)} problem(s) "
              f"[{r.usage.input_tokens} in / {r.usage.output_tokens} out]")
        if not bad or (attempt == ATTEMPTS and all(b.startswith("BATCH:") for b in bad)):
            if bad:
                print(f"::warning::{p['key']}: UNDER TARGET - {len(clips)} clips, the episode holds "
                      f"at least {target(p)}. {bad[0]}")
                summary([f"**{p['key']}: UNDER TARGET** - {len(clips)} of at least {target(p)} clips. "
                         "Cut the uncut stretches as whole teachings before it goes to GIN."])
            return clips
        for b in bad:
            print("    - " + b)
        # Append-only: the model's own turn goes back unchanged, then the problems.
        messages += [{"role": "assistant", "content": r.content},
                     {"role": "user", "content": "Code checked your batch and found these problems. "
                      "Return the whole corrected batch:\n- " + "\n- ".join(bad)}]
    # KEEP WHAT PASSED (13 Oct 2026). One clip the planner could not get onto a pause used
    # to throw away the whole batch, and the episode waited for a person. The clips that
    # pass every check are kept when there are enough of them; the rest are named here.
    if clips:
        names = {c["name"] for c in clips}
        failing = {b.split(":")[0] for b in bad if b.split(":")[0] in names}
        general = [b for b in bad if b.split(":")[0] not in names and not b.startswith("BATCH:")]
        keep = [c for c in clips if c["name"] not in failing]
        if (not general and len(keep) >= MIN_KEEP
                and not [b for b in problems(p, keep, text) if not b.startswith("BATCH:")]):
            print(f"::warning::{p['key']}: kept {len(keep)} clips that pass; dropped "
                  f"{', '.join(sorted(failing))} - they could not be put on a clean pause")
            if len(keep) < target(p):
                summary([f"**{p['key']}: UNDER TARGET** - kept {len(keep)} of at least {target(p)} "
                         f"clips; {', '.join(sorted(failing))} could not be put on a clean pause. "
                         "Re-cut them as whole teachings before it goes to GIN."])
            return keep
    return None


def summary(lines):
    """The run page shows what was chosen - readable from the GitHub app on a phone."""
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        open(os.environ["GITHUB_STEP_SUMMARY"], "a").write("\n".join(lines) + "\n\n")


def main():
    stubs = [(f, json.load(open(f))) for f in sorted(glob.glob(os.path.join(ROOT, "plans", "*.json")))]
    stubs = [(f, p) for f, p in stubs if not p.get("clips") and p.get("autoplan", True)]
    if not stubs:
        print("no stub plans - nothing to choose")
        return
    planned, waiting = [], []
    out = os.environ.get("GITHUB_OUTPUT")

    def done():
        # Written even when nothing was planned: the workflow saves what WAS planned,
        # then fails the run while any batch is still waiting. Run 48 (7 Oct) planned
        # nothing, said so in one log line, and went green with zero clips.
        if out:
            open(out, "a").write(f"planned={1 if planned else 0}\nkeys={' '.join(planned)}\n"
                                 f"waiting={' '.join(waiting)}\n")
        print("AUTOPLANNED: " + (" ".join(planned) or "none"))
        if waiting:
            print("STILL WAITING FOR CLIPS: " + " ".join(waiting))

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("::error::A new batch is waiting for its clips, but the ANTHROPIC_API_KEY "
              "secret is not set. See CLAUDE.md -> Autopilot.")
        waiting += [p["key"] for _, p in stubs]
        return done()
    import anthropic
    client = anthropic.Anthropic()
    for f, p in stubs:
        text = transcript(p)
        if not text:
            print(f"::error::{p['key']}: no transcript for it in the prep release")
            waiting.append(p["key"])
            continue
        global PAUSE
        PAUSE = prep_data(p)
        if PAUSE:
            # the planner reads, and is checked against, the transcript whose line breaks
            # are the pauses the renderer can cut in
            text = paused_transcript(*PAUSE)
            print(f"  pause map: {len(PAUSE[1])} pauses, {text.count(chr(10)) + 1} lines of speech")
            if len(PAUSE[1]) < p.get("duration", 0) / 60:
                # they_re_not_hiding, 29 Oct 2026: 6 cut points in 27 min was a music bed the
                # map could not see through, not an episode without pauses (CLAUDE.md)
                print(f"::warning::{p['key']}: under one cut point a minute - check the pause map")
        thin = thin_punctuation(text)
        for a, b, rate in thin:
            print(f"::warning::{p['key']}: {mmss(a)}-{mmss(b)} has {rate:.1f} full stops a "
                  "minute (under 4) - whisper drifted; cuts there need a careful look")
        if thin:
            summary([f"**{p['key']}: thin punctuation** in " + ", ".join(
                f"{mmss(a)}-{mmss(b)} ({r:.1f}/min)" for a, b, r in thin)])
        print(f"{p['key']}: choosing clips with {MODEL}")
        clips = plan_one(client, p, text)
        if not clips:
            print(f"::error::{p['key']}: no batch passed the checks - the stub stays as it was")
            waiting.append(p["key"])
            continue
        p["clips"] = clips
        json.dump(p, open(f, "w"), indent=1)
        planned.append(p["key"])
        tw = timed_words(text)
        rows = [f"### {p['key']}: {len(clips)} clips chosen", "",
                "| clip | source | speech | hook |", "|---|---|---|---|"]
        for c in clips:
            o, e = searched(c, tw)
            t0, t1 = o[0][0], e[-1][1]
            print(f"   {c['name']:34} {mmss(t0)}-{mmss(t1)} ~{t1 - t0:3.0f}s  {' / '.join(c['hook'])}")
            rows.append(f"| {c['name']} | {mmss(t0)}-{mmss(t1)} | ~{t1 - t0:.0f} s | {' / '.join(c['hook'])} |")
        summary(rows)
    done()


if __name__ == "__main__":
    main()
