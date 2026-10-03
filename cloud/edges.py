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
    cap_first = norm(caps[0][2].split()[0]) if caps else None
    cap_last = norm(caps[-1][2].split()[-1]) if caps else None
    got_first = norm(h[0][2]) if h else None
    got_last = norm(t[-1][2]) if t else None
    c = plan_clip or {}
    return {"first_heard": h[:4] if h else h, "last_heard": t[-5:] if t else t,
            "caption_first": cap_first, "caption_last": cap_last,
            "plan_first": norm((c.get("open") or " ").split()[0]),
            "plan_last": norm((c.get("close") or " ").split()[-1]),
            "first_ok": got_first is not None and got_first == cap_first,
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


if __name__ == "__main__":
    if sys.argv[1:2] == ["probe"]:
        probe(sys.argv[2], sys.argv[3:])
    else:
        main(sys.argv[1:] or ["delivered"])
