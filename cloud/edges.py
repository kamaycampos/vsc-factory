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
        if not os.path.exists(p):
            sh("gh", "release", "download", "clips", "-R", REPO, "-p", f, "-D", "/tmp/edges", "--clobber")
        dur = float(sh("ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", p).stdout or 0)
        sh("ffmpeg", "-y", "-loglevel", "error", "-i", p, "-t", f"{EDGE}", "-ar", "16000", "-ac", "1", "/tmp/edges/h.wav")
        sh("ffmpeg", "-y", "-loglevel", "error", "-ss", f"{max(0.0, dur - EDGE - 0.6):.3f}", "-i", p,
           "-ar", "16000", "-ac", "1", "/tmp/edges/t.wav")
        h, t = heard("/tmp/edges/h.wav", "h"), heard("/tmp/edges/t.wav", "t")
        c = plan.get(name, {})
        want_first = norm((c.get("open") or " ").split()[0])
        want_last = norm((c.get("close") or " ").split()[-1])
        got_first = norm(h[0][2]) if h else None
        got_last = norm(t[-1][2]) if t else None
        row = {"file": f, "first_heard": h[:4] if h else h, "last_heard": t[-5:] if t else t,
               "plan_first": want_first, "plan_last": want_last,
               "first_ok": got_first == want_first, "last_ok": got_last == want_last}
        report.append(row)
        print(f"{'OK ' if row['first_ok'] else '?? '}{'OK ' if row['last_ok'] else '?? '}{f}")
        print(f"     first 3s: {' '.join(f'{a:.2f}:{w}' for a, b, w in (h or [])[:6])}   (plan opens '{want_first}')")
        print(f"     last  3s: {' '.join(f'{a:.2f}-{b:.2f}:{w}' for a, b, w in (t or [])[-6:])}   (plan ends '{want_last}')",
              flush=True)
    json.dump(report, open("/tmp/edges/edges.json", "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1:] or ["delivered"])
