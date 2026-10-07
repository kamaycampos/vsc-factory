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
    word in the transcript, and cloud/check_plan.py must pass. One repair round with
    the problems listed; if it still fails, the stub stays a stub and the run says why.
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
    """TRANSCRIPT_<prefix key>.txt, as prep publishes it to the prep release."""
    name = f"TRANSCRIPT_{(p['prefix'] + ' ' + p['key'])[:40]}.txt"
    os.makedirs("/tmp/autoplan", exist_ok=True)
    subprocess.run(["gh", "release", "download", "prep", "-R", REPO, "-p", name,
                    "-D", "/tmp/autoplan", "--clobber"], capture_output=True)
    f = os.path.join("/tmp/autoplan", name)
    return open(f).read() if os.path.exists(f) else None


def problems(p, clips, text):
    """Everything code can check. Empty list = keep it."""
    out = []
    if not clips:
        return ["no clips"]
    words = norm(text)
    for c in clips:
        for k in ("open", "close"):
            if norm(c[k]) not in words:
                out.append(f"{c['name']}: {k} \"{c[k]}\" is not in the transcript word for word")
        if len(c["region"]) != 2 or c["region"][0] >= c["region"][1]:
            out.append(f"{c['name']}: region must be [start, end] with start < end")
        elif c["region"][1] > float(p.get("duration") or 1e9) + 1:
            out.append(f"{c['name']}: region ends after the episode does")
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
    for attempt in (1, 2):
        with client.beta.messages.stream(
            model=MODEL, max_tokens=64000, system=system, messages=messages,
            output_config={"effort": "high",
                           "format": {"type": "json_schema", "schema": SCHEMA}},
            betas=["server-side-fallback-2026-07-01"], fallbacks="default",
        ) as stream:
            r = stream.get_final_message()
        if r.stop_reason == "refusal":
            print(f"::error::{p['key']}: the model declined ({getattr(r, 'stop_details', None)})")
            return None
        if r.stop_reason == "max_tokens":
            print(f"::error::{p['key']}: the answer was cut off at max_tokens")
            return None
        text_out = next((b.text for b in r.content if b.type == "text"), "")
        clips = clean(json.loads(text_out)["clips"])
        bad = problems(p, clips, text)
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


def main():
    stubs = [(f, json.load(open(f))) for f in sorted(glob.glob(os.path.join(ROOT, "plans", "*.json")))]
    stubs = [(f, p) for f, p in stubs if not p.get("clips") and p.get("autoplan", True)]
    if not stubs:
        print("no stub plans - nothing to choose")
        return
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("::warning::A new batch is waiting for its clips, but the ANTHROPIC_API_KEY "
              "secret is not set. See CLAUDE.md -> Autopilot.")
        return
    import anthropic
    client = anthropic.Anthropic()
    planned = []
    for f, p in stubs:
        text = transcript(p)
        if not text:
            print(f"::warning::{p['key']}: no transcript in the prep release yet")
            continue
        print(f"{p['key']}: choosing clips with {MODEL}")
        clips = plan_one(client, p, text)
        if not clips:
            print(f"::error::{p['key']}: no batch passed the checks - the stub stays as it was")
            continue
        p["clips"] = clips
        json.dump(p, open(f, "w"), indent=1)
        planned.append(p["key"])
        for c in clips:
            print(f"   {c['name']:34} {c['region'][1] - c['region'][0]:5.0f}s  {' / '.join(c['hook'])}")
    if planned and os.environ.get("GITHUB_OUTPUT"):
        open(os.environ["GITHUB_OUTPUT"], "a").write(f"planned=1\nkeys={' '.join(planned)}\n")
    print("AUTOPLANNED: " + (" ".join(planned) or "none"))


if __name__ == "__main__":
    main()
