#!/usr/bin/env python3
"""LISTEN to the edges of the RENDERED clips: what whisper hears in the first and last
seconds of the file that is delivered, not of the source.

3 Oct 2026. Kamay, watching the delivered batch, found what every level-and-silence
measurement had passed: FALL-DOWN-SEVEN-TIMES and THE-TEAM-THATS-LOSING ended on Kevin's
next words, REACT-OR-RESPOND cut "pro|blem", and NOT-AFFECTED-BY-ANYTHING opened on
"...people" with the caption reading SUCCESSFUL PEOPLE. A silence detector can say there
is sound; only a listener can say which word it is. So the file itself is transcribed,
at both ends, and its first and last heard words are set beside the plan's.

    python cloud/edges.py delivered          # the newest file of every delivered clip
    python cloud/edges.py NAME_51s.mp4 ...   # these release files
    python cloud/edges.py plancheck <key>    # every planned cut, heard on the SOURCE first
"""
import glob, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.environ.get("GITHUB_REPOSITORY", "kamaycampos/vsc-factory")
WH = os.path.expanduser("~/Kamay/whisper.cpp/build/bin/whisper-cli")
MD = os.path.expanduser("~/Kamay/whisper.cpp/models/ggml-small.en.bin")
EDGE = 3.0
norm = lambda t: re.sub(r"[^a-z0-9']", "", t.lower())


def sh(*a):
    return subprocess.run(a, capture_output=True, text=True)


def assets():
    r = sh("gh", "release", "view", "clips", "-R", REPO, "--json", "assets")
    return json.loads(r.stdout)["assets"]


def newest(names):
    out = {}
    for a in assets():
        m = re.match(r"(.+)_\d+s\.mp4$", a["name"])
        if m and m.group(1) in names and (m.group(1) not in out or a["updatedAt"] > out[m.group(1)]["updatedAt"]):
            out[m.group(1)] = a
    return [out[n]["name"] for n in names if n in out]


def heard(wav, tag):
    """Words whisper hears, with times: -ml 1 -sow, as the factory's own timing pass."""
    r = sh(WH, "-m", MD, "-f", wav, "-ml", "1", "-sow", "-bs", "5", "-bo", "5", "-oj", "-of", f"/tmp/edge_{tag}")
    if r.returncode or not os.path.exists(f"/tmp/edge_{tag}.json"):
        return None
    w = []
    for s in json.load(open(f"/tmp/edge_{tag}.json"))["transcription"]:
        t = s["text"].strip()
        if t and not re.match(r"^[\[\(].*[\]\)]$", t):
            w.append((s["offsets"]["from"] / 1000.0, s["offsets"]["to"] / 1000.0, t))
    return w


def same_start(got, cap):
    """Is the first word heard the first caption word, whole?

    12 Oct 2026: FIRED-FROM-HIS-OWN-COMPANY opens on "Steve" over clean silence, whisper
    heard "Steven" (its known name bias - CLAUDE.md, "Steve Jobs (not Steven)") and the
    clip was failed. A word cut at the START of a clip is heard SHORTER or different,
    never with letters added, so a heard word that begins with the caption word and runs
    at most two letters longer is the whole word. Only the opening gets this: at the end,
    a longer word ("problem" heard as "problems") is speech running past the close."""
    # ...and its SPELLING: run 38316915072 heard "Stephen" for the same clip. A clipped
    # word has lost its first sound, so the same first three letters at full length or
    # longer is the whole word ("teve" for "steve" still fails).
    # ...and a NAME whisper spells its own way (30 Oct, they_re_not_hiding): "Elizondo" on
    # screen, "Alessandro" heard. Same consonants in the same order (z~s, c~k, doubles
    # collapsed) and the same kind of first letter, so a word that lost its first sound
    # ("lizondo") still fails.
    return got == cap or (bool(cap) and len(cap) >= 4 and (
        (got.startswith(cap) and len(got) - len(cap) <= 2)
        or (got[:3] == cap[:3] and len(cap) <= len(got) <= len(cap) + 3)
        or (len(cap) >= 5 and (got[0] in VOWELS) == (cap[0] in VOWELS)
            and (got[0] in VOWELS or got[0] == cap[0])
            and len(skeleton(cap)) >= 3 and skeleton(got).startswith(skeleton(cap)))))


VOWELS = "aeiouy"


def skeleton(w):
    """The consonants of a word as whisper hears them: 'alessandro' and 'elizondo' -> 'lsnd...'."""
    w = re.sub(r"[^a-z]", "", w).replace("z", "s").replace("c", "k").replace("ph", "f")
    return re.sub(r"(.)\1+", r"\1", re.sub(f"[{VOWELS}]", "", w))


def check(p, caps=None, plan_clip=None, work="/tmp/edges"):
    """What whisper hears at the two ends of the file at p, against its own captions.

    The words that matter are the ones ON SCREEN: the first caption's first word must be
    the first word heard, whole, and the last caption's last word the last one heard,
    with nothing after it. (The plan's words are reported too; the opening may begin up
    to six words earlier, at the start of the sentence - see vsc_v2_render's head check.)"""
    os.makedirs(work, exist_ok=True)
    dur = float(sh("ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p).stdout or 0)
    sh("ffmpeg", "-y", "-loglevel", "error", "-i", p, "-t", f"{EDGE}", "-ar", "16000", "-ac", "1", f"{work}/h.wav")
    sh("ffmpeg", "-y", "-loglevel", "error", "-ss", f"{max(0.0, dur - EDGE - 0.6):.3f}", "-i", p,
       "-ar", "16000", "-ac", "1", f"{work}/t.wav")
    h, t = heard(f"{work}/h.wav", "h"), heard(f"{work}/t.wav", "t")
    # the first / last REAL word: a caption token that is only punctuation ("--", an
    # opening quote) normed to "" and failed PRAYING-FROM-DESPERATION (13 Oct)
    toks = [t for t in (norm(x) for c in (caps or []) for x in c[2].split()) if t]
    cap_first = toks[0] if toks else None
    cap_last = toks[-1] if toks else None
    # ...and on the listening side too: HUNDREDS-OF-CREDIBLE-WITNESSES (30 Oct) was heard
    # "- Alessandro", and the "-" was taken as its first word
    h = [x for x in (h or []) if norm(x[2])] or h
    t = [x for x in (t or []) if norm(x[2])] or t
    got_first = norm(h[0][2]) if h else None
    got_last = norm(t[-1][2]) if t else None
    c = plan_clip or {}
    return {"first_heard": h[:4] if h else h, "last_heard": t[-5:] if t else t,
            "caption_first": cap_first, "caption_last": cap_last,
            "plan_first": norm((c.get("open") or " ").split()[0]),
            "plan_last": norm((c.get("close") or " ").split()[-1]),
            "first_ok": got_first is not None and same_start(got_first, cap_first),
            "last_ok": got_last is not None and got_last == cap_last}


def main(args):
    plan = {c["name"]: c for f in glob.glob(os.path.join(HERE, "plans", "*.json"))
            for c in json.load(open(f))["clips"]}
    if args == ["delivered"]:
        d = json.load(open(os.path.join(HERE, "cloud", "delivered.json")))
        files = newest([n for k, v in d.items() if not k.startswith("_") for n in v])
    else:
        files = args
    os.makedirs("/tmp/edges", exist_ok=True)
    report = []
    for f in files:
        name = re.sub(r"_\d+s\.mp4$", "", f)
        p = os.path.join("/tmp/edges", f)
        for g in (f, f[:-4] + "__caps.json"):
            if not os.path.exists(os.path.join("/tmp/edges", g)):
                sh("gh", "release", "download", "clips", "-R", REPO, "-p", g, "-D", "/tmp/edges", "--clobber")
        cj = p[:-4] + "__caps.json"
        caps = json.load(open(cj)) if os.path.exists(cj) else None
        row = dict(file=f, **check(p, caps, plan.get(name)))
        report.append(row)
        print(f"{'OK ' if row['first_ok'] else '?? '}{'OK ' if row['last_ok'] else '?? '}{f}")
        print(f"     first 3s: {' '.join(f'{a:.2f}:{w}' for a, b, w in (row['first_heard'] or [])[:6])}"
              f"   (caption '{row['caption_first']}', plan '{row['plan_first']}')")
        print(f"     last  3s: {' '.join(f'{a:.2f}-{b:.2f}:{w}' for a, b, w in (row['last_heard'] or [])[-6:])}"
              f"   (caption '{row['caption_last']}', plan '{row['plan_last']}')", flush=True)
    json.dump(report, open("/tmp/edges/edges.json", "w"), indent=1)


def probe(key, spans):
    """THE SOURCE'S OWN SOUND at chosen moments: real silences and the words heard, in
    source seconds. 3 Oct 2026: the closes chosen from word times alone ended on
    "infomer-" and before "Vince Lombardi"; a boundary is chosen from this instead.
        python cloud/edges.py probe millionaires_problems 515:533 944:948"""
    sys.path.insert(0, os.path.expanduser("~/Kamay"))
    sys.path.insert(0, HERE)
    from cloud.source import fetch, plans
    import vsc_v2_render as V
    src = fetch([p for p in plans() if p["key"] == key][0])
    for s in spans:
        t0, t1 = (float(x) for x in s.split(":"))
        runs = []
        for c in range(int(t0), int(t1) + 1, 2):
            runs += V.quiet_runs(src, c + 1.0, before=1.2, length=2.6)
        runs = sorted({(round(a, 2), round(b, 2)) for a, b in runs if b > t0 and a < t1})
        sh("ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t0:.3f}", "-to", f"{t1:.3f}", "-i", src,
           "-ar", "16000", "-ac", "1", "/tmp/probe.wav")
        w = heard("/tmp/probe.wav", "p") or []
        print(f"=== {t0:.1f}-{t1:.1f}")
        print("  silences >= 60 ms: " + "  ".join(f"{a:.2f}-{b:.2f}({b - a:.2f})" for a, b in runs))
        print("  words: " + " ".join(f"{t0 + a:.2f}:{x}" for a, b, x in w), flush=True)
        if t1 - t0 <= 3.0:          # a short span: its level every 20 ms, to see dips under a music bed
            import numpy as np
            raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", "/tmp/probe.wav", "-f", "s16le", "-"],
                                 capture_output=True).stdout
            x = np.frombuffer(raw, dtype=np.int16).astype(float)
            db = [20 * np.log10(np.sqrt(np.mean(x[i:i + 320] ** 2)) + 1e-9) for i in range(0, len(x) - 320, 320)]
            print("  dB/20ms: " + " ".join(f"{t0 + k * 0.02:.2f}:{d:.0f}" for k, d in enumerate(db)), flush=True)


def plancheck(key, names=()):
    """HEAR EVERY PLANNED CUT ON THE SOURCE, BEFORE ANYTHING IS RENDERED.

        python cloud/edges.py plancheck <key> [CLIP ...]     (edges workflow: "plancheck <key>")
        python cloud/edges.py plancheck <key> CLIP@612.4:690.1   (a trial cut, before it goes in the plan)

    31 Oct 2026, they_re_not_hiding: three of nine hand cuts FAILED edge listening after a
    full build round - EVERY-CULTURE-SAW-THEM ended as "...the same." with "thing" cut, and
    two more for reasons the source could have shown. Edge listening hears the first EDGE s
    and the last EDGE + 0.6 s of the FILE; this cuts exactly those stretches out of the
    source at the plan's start_at / end_at and hears them the same way, so a cut that will
    fail is known in minutes, not after a build. First word heard vs the plan's open (whole,
    names spelt whisper's way allowed), last word heard vs the plan's close (exact).
    Exit 1 when any cut fails - fix the times from the words it prints, then push."""
    sys.path.insert(0, os.path.expanduser("~/Kamay"))
    sys.path.insert(0, HERE)
    from cloud.source import fetch, plans
    plan = [p for p in plans() if p["key"] == key][0]
    src = fetch(plan)
    # CLIP@start:end hears a TRIAL cut instead of the plan's - try a time before writing it in
    trial = {n.split("@")[0]: [float(x) for x in n.split("@")[1].split(":")] for n in names if "@" in n}
    names = [n.split("@")[0] for n in names]
    out, bad = [], 0
    for c in plan["clips"]:
        if names and c["name"] not in names:
            continue
        if c["name"] in trial:
            c = dict(c, start_at=trial[c["name"]][0], end_at=trial[c["name"]][1])
        if c.get("start_at") is None or c.get("end_at") is None:
            print(f"  --  {c['name']}: no start_at / end_at - the renderer finds the cut, nothing to hear")
            continue
        a, b = float(c["start_at"]), float(c["end_at"])
        sh("ffmpeg", "-y", "-loglevel", "error", "-ss", f"{a:.3f}", "-t", f"{min(EDGE, b - a):.3f}", "-i", src,
           "-ar", "16000", "-ac", "1", "/tmp/pc_h.wav")
        t0 = max(a, b - EDGE - 0.6)
        sh("ffmpeg", "-y", "-loglevel", "error", "-ss", f"{t0:.3f}", "-t", f"{b - t0:.3f}", "-i", src,
           "-ar", "16000", "-ac", "1", "/tmp/pc_t.wav")
        h = [x for x in (heard("/tmp/pc_h.wav", "pch") or []) if norm(x[2])]
        t = [x for x in (heard("/tmp/pc_t.wav", "pct") or []) if norm(x[2])]
        want_first = next((w for w in (norm(x) for x in c["open"].split()) if w), "")
        want_last = next((w for w in (norm(x) for x in reversed(c["close"].split())) if w), "")
        got_first = norm(h[0][2]) if h else ""
        got_last = norm(t[-1][2]) if t else ""
        ok_first = same_start(got_first.replace("'", ""), want_first.replace("'", ""))
        ok_last = got_last.replace("'", "") == want_last.replace("'", "")
        bad += not (ok_first and ok_last)
        heard_h = " ".join(x[2] for x in h[:5])
        heard_t = " ".join(x[2] for x in t[-5:])
        print(f"  {'OK  ' if ok_first and ok_last else 'FAIL'} {c['name']}: "
              f"opens [{heard_h}]{'' if ok_first else f' - plan opens on {want_first!r}'} | "
              f"ends [{heard_t}]{'' if ok_last else f' - plan closes on {want_last!r}'}", flush=True)
        out.append({"clip": c["name"], "start_at": a, "end_at": b, "first_ok": ok_first, "last_ok": ok_last,
                    "first_heard": heard_h, "last_heard": heard_t})
    os.makedirs("/tmp/edges", exist_ok=True)
    json.dump(out, open("/tmp/edges/edges.json", "w"), indent=1)
    print(f"PLANCHECK {key}: {len(out) - bad}/{len(out)} cuts heard as planned")
    if bad:
        sys.exit(1)


if __name__ == "__main__":
    if sys.argv[1:2] == ["plancheck"]:
        plancheck(sys.argv[2], sys.argv[3:])
    elif sys.argv[1:2] == ["probe"]:
        probe(sys.argv[2], sys.argv[3:])
    else:
        main(sys.argv[1:] or ["delivered"])
