#!/usr/bin/env python3
"""Start a VSC batch from one line: the assignment's title and its length.

    python cloud/new_batch.py "<title GIN gave it>" <duration: 18:10 or 1090> [rumble url]

5 Oct 2026, Kamay: "once they give us the video ... just give it to the factory and
the factory automatically starts working ... when I come back I want to find the
clips ready." This is the "give it" half. It writes a STUB plan (no clips yet),
finds the same episode on Rumble by duration (rumble_match), and the vsc workflow
does the rest: prep transcribes it, autoplan.py chooses the clips, build renders.
Run by the vsc-new workflow (a form in the GitHub app), or by hand.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)


def seconds(s):
    s = str(s).strip()
    if ":" in s:
        parts = [float(x) for x in s.split(":")]
        return sum(v * 60 ** i for i, v in enumerate(reversed(parts)))
    return float(s)


def slug(title):
    words = re.findall(r"[a-z0-9]+", title.lower())
    return "_".join(words[:4]) or "batch"


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    title, dur = sys.argv[1].strip(), seconds(sys.argv[2])
    rumble = sys.argv[3].strip() if len(sys.argv) > 3 and sys.argv[3].strip() else None
    key = slug(title)
    path = os.path.join(ROOT, "plans", f"{key}.json")
    if os.path.exists(path):
        sys.exit(f"plans/{key}.json already exists - this assignment is already in the factory")
    plan = {"key": key, "prefix": " ".join(title.split()[:3])[:30], "title": title,
            "source": f"{key}.mp4.enc", "duration": dur, "autoplan": True,
            "note": "Started by vsc-new. Clips are chosen by cloud/autoplan.py from the "
                    "transcript prep publishes; rules in CLAUDE.md and PLANNING.md.",
            "clips": []}
    if rumble:
        plan["rumble"] = rumble
    else:
        import rumble_match as M
        u, e, why = M.match(M.catalog(), dur, title)
        if u:
            plan.update(rumble=u, duration=e["dur"], height=e["height"], rumble_title=e["title"])
        print(f"Rumble: {why}")
    # ONE EPISODE, ONE PLAN. GIN titles differ from Rumble's, so a second title for the
    # same interview would otherwise start a second batch of the same clips.
    import glob
    for f in glob.glob(os.path.join(ROOT, "plans", "*.json")):
        o = json.load(open(f))
        if plan.get("rumble") and o.get("rumble") == plan["rumble"]:
            sys.exit(f"this episode is already in the factory as plans/{os.path.basename(f)} "
                     f"({o.get('title') or o['key']})")
    json.dump(plan, open(path, "w"), indent=1)
    print(f"wrote plans/{key}.json" + ("" if plan.get("rumble") else
          " - NO SOURCE FOUND: add the Rumble URL, or upload <key>.mp4.enc to the sources release"))
    gh = os.environ.get("GITHUB_OUTPUT")
    if gh:
        open(gh, "a").write(f"key={key}\nsource={'yes' if plan.get('rumble') else 'no'}\n")


if __name__ == "__main__":
    main()
