#!/usr/bin/env python3
"""Check every plan before a single server starts. Exit 1 on any problem.

    python cloud/check_plan.py                 # every plans/*.json
    python cloud/check_plan.py plans/x.json    # one plan

WHY THIS EXISTS. 5 Oct 2026, Kamay, after the millionaires_problems batch: "the
factory was making them so the clips are not more than 60 seconds, which made many
clips so horribly short, cutting the teaching". GIN's ceiling is 120 s. The ~60 s
came from nowhere in GIN's brief: on 30 Sept the renderer died on every clip over
~62 s (one decoded 4K stream for all shots), and instead of fixing the renderer the
plan was cut to fit it - MORE-PROBLEMS 102 s became two clips, BANNED-FOR-LIFE 128 s
became three (commit d88d8f1). The renderer was fixed on 4 Oct (each shot its own
ffmpeg), so the reason is gone, and this check keeps the habit from coming back:
a teaching is never shortened to suit a machine.

It also refuses the stacked fix CLAUDE.md warns about, which was still in the plan:
a second correction written over the text a first one produced duplicates words.

Delivered clips (cloud/delivered.json) are history and are not checked - a rule
that blocks every build behind clips nobody may rebuild is not a rule, it is a jam.
"""
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

MIN_LEN = 40.0      # a whole teaching rarely fits in less; "short_ok" says why it does
MAX_LEN = 118.0     # Naomi's ceiling is 120 s (same constant as vsc_clip.MAX_LEN)
HOOK_WORDS = 10     # two short lines; GIN approved "THE DAY IT FALLS APART / IS THE DAY YOU START"

# A hook must give the viewer a reason to stay: something they get, fear, or
# recognise. A bare number is not one - "WHY IT TOOK HER 3 HOURS" (KT account,
# 5 Oct) passed every shape rule and says nothing. Warning only here: GIN's
# reviewers approve VSC hooks, and all-caps text hides the names that carry many
# of them (J.K. ROWLING, STEVE JOBS).
STAKES = re.compile(
    r"(\byou\b|\byour\b|\byou'?re\b|[$%]|\d|\bmillion|\bbillion|\brich|\bwealth|\bmoney|"
    r"\bbroke|\bpoor|\bsuccess|\bmillionaire|\bwin|\bwinners?\b|\blos[et]|\bfail|"
    r"\bfired|\bbanned|\bsued|\bprison|\bhabit|\bfear|\bpain|\bsuffer|\bproblem|"
    r"\bdisaster|\badversity|\bsecret|\blie\b|\bnever\b|\bban|\bgold|"
    r"\b(one|two|three|four|five|six|seven|eight|nine|ten|hundred|thousand)\b)", re.I)


def norm(s):
    return re.sub(r"\s+", " ", str(s)).strip().lower()


def stacked(fixes):
    """(i, j) where fix j rewrites text that fix i produced."""
    out = []
    for i, a in enumerate(fixes):
        for j in range(i + 1, len(fixes)):
            b = fixes[j]
            if abs(float(a[0]) - float(b[0])) > 20:
                continue
            ra, wb = norm(a[2]), norm(b[1])
            if ra and wb != ra and ra in wb:
                out.append((i, j))
    return out


def check(path, delivered):
    p = json.load(open(path))
    errs, warns = [], []
    for k in ("key", "prefix", "clips"):
        if k not in p:
            errs.append(f"missing '{k}'")
    locked = set(delivered.get(p.get("key"), []))
    names = [c.get("name") for c in p.get("clips", [])]
    if len(names) != len(set(names)):
        errs.append("duplicate clip names")
    for c in p.get("clips", []):
        n = c.get("name", "?")
        if n in locked:
            continue
        r = c.get("region") or [0, 0]
        span = float(r[1]) - float(r[0])
        if span > MAX_LEN:
            errs.append(f"{n}: region {span:.0f}s is over the {MAX_LEN:.0f}s ceiling - "
                        "split it into two clips that EACH carry a whole idea")
        elif span < MIN_LEN and not c.get("short_ok"):
            errs.append(f"{n}: region {span:.0f}s is under {MIN_LEN:.0f}s - is the whole "
                        "teaching (setup, proof, landing) inside it? If it truly is, add "
                        '"short_ok": "<why it is complete>"')
        for k in ("open", "close"):
            if len(str(c.get(k) or "").split()) < 3:
                errs.append(f"{n}: '{k}' must be the clip's exact first/last words (3+)")
        h = c.get("hook") or []
        if not isinstance(h, list) or len(h) != 2 or not all(str(x).strip() for x in h):
            errs.append(f"{n}: hook must be two lines")
        else:
            w = sum(len(str(x).split()) for x in h)
            if w > HOOK_WORDS:
                errs.append(f"{n}: hook is {w} words - max {HOOK_WORDS}")
            if not STAKES.search(" ".join(h)):
                warns.append(f"{n}: hook '{' / '.join(h)}' names nothing the viewer gets, "
                             "fears or recognises - is there a number, a name or a cost to lead with?")
        fx = c.get("fixes") or []
        for i, f in enumerate(fx):
            if len(f) not in (3, 4):
                errs.append(f"{n}: fix {i} must be [t, \"wrong\", \"right\"] (+ optional start times)")
            elif len(f) == 4 and (not isinstance(f[3], list) or len(f[3]) != len(str(f[2]).split())):
                errs.append(f"{n}: fix {i} needs one start time per word of \"right\"")
            # case counts: captions show it ("a Forest fire" -> "A forest fire" is a real fix)
            elif str(f[1]).split() == str(f[2]).split():
                errs.append(f"{n}: fix {i} changes nothing")
        for i, j in stacked([f for f in fx if len(f) in (3, 4)]):
            errs.append(f"{n}: fix {j} rewrites the text fix {i} produced - they stack and "
                        "duplicate words. Write ONE fix against the server's caps.json")
    return errs, warns


def main():
    paths = sys.argv[1:] or sorted(glob.glob(os.path.join(ROOT, "plans", "*.json")))
    try:
        delivered = json.load(open(os.path.join(HERE, "delivered.json")))
    except FileNotFoundError:
        delivered = {}
    bad = 0
    for path in paths:
        errs, warns = check(path, delivered)
        print(f"{os.path.basename(path)}: {'OK' if not errs else 'PROBLEMS'}")
        for e in errs:
            print("   - " + e)
        for w in warns:
            print("   ~ " + w)
        bad += bool(errs)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
