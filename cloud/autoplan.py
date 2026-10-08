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
ATTEMPTS = 3        # the first answer, then up to two repair rounds with the problems listed

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
    p = json.load(open(os.path.join(ROOT, "plans", "millionaires_problems.json")))
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


LINE = re.compile(r"^\[(\d+):(\d+(?:\.\d+)?)\]\s*(.*)$", re.M)


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


def problems(p, clips, text):
    """Everything code can check. Empty list = keep it."""
    out = []
    if not clips:
        return ["no clips"]
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
    # Names are unique across every plan: the clips release and built.json are keyed by
    # name, so a redo reusing a delivered name would overwrite the file GIN already has.
    taken = {}
    for f in glob.glob(os.path.join(ROOT, "plans", "*.json")):
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


def plan_one(client, p, text):
    system = (open(os.path.join(ROOT, "PLANNING.md")).read() + "\n\n" + rules() +
              "\n\n## The delivered, reviewer-approved batch (shape and standard)\n" + example())
    if p.get("redo_of"):
        old = json.load(open(os.path.join(ROOT, "plans", p["redo_of"] + ".json")))
        system += (
            f"\n\n## THIS IS A REDO of {p['redo_of']} - the SAME episode as the batch above\n"
            "Kamay, 5 Oct: that batch came out 30-82 s and CUT THE TEACHING. It was planned while "
            "the renderer died on clips over ~62 s, so long teachings were split into pieces; the "
            "renderer is fixed. Re-cut the episode: every clip runs from the start of the thought "
            "to where the teaching lands - setup, proof and landing - usually 45-110 s, never over "
            "118. Where one lesson was split across several clips above, make it ONE clip. Keep "
            "different tellings of a lesson only when each is complete on its own. Every clip "
            "needs a NEW name, different from every name above.\n"
            f"Notes on this episode: {old.get('note', '')}")
    user = (f"Episode: \"{p.get('title') or p['key']}\", {p.get('duration', '?')} seconds long.\n"
            f"Transcript (each line starts at [mm:ss.ss] source time):\n\n{text}")
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
        if not bad:
            return clips
        for b in bad:
            print("    - " + b)
        # Append-only: the model's own turn goes back unchanged, then the problems.
        messages += [{"role": "assistant", "content": r.content},
                     {"role": "user", "content": "Code checked your batch and found these problems. "
                      "Return the whole corrected batch:\n- " + "\n- ".join(bad)}]
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
