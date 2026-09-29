#!/usr/bin/env python3
"""Find a VSC assignment on Rumble so nobody has to upload 1.4GB from a laptop.

27 Sept 2026. Kamay: "rumble does have ALL and even MORE episodes of the KT show
Limitless. its there you just have to look for it."

He was right and my first look was weak. Searching by TITLE fails because Kevin
publishes the same interview under a different name: the VSC source "Why Millionaires
Love PROBLEMS" is on Rumble as "Your Success Starts On Your Worst Day: What Every
Millionaire Knows". Rumble's own search does not even return his channel for that
phrase.

DURATION is the identifier. That episode runs 1090s on Rumble and the VSC original
runs 1090.5s, and exactly ONE of the 632 catalogued episodes is within two seconds of
it. Across the whole catalogue 351 durations are unique, so a duration plus a height
and a date window identifies an episode far better than its title does.

The catalogue itself is kt-machine's (public, refreshed by its own workflow), so this
costs nothing and stays current.

    python3 cloud/rumble_match.py                 # match every plan that needs it
    python3 cloud/rumble_match.py <key> <seconds> # tell it the duration you measured
"""
import json, os, re, sys, urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CATALOG = ("https://raw.githubusercontent.com/kamaycampos/kt-machine/main/"
           "factory/rumble_catalog.json")
TOL = 2.5          # seconds. A published cut is the same edit; it does not drift.
MIN_H = 1080       # the gate that exists because 18 clips went out blurry


def catalog():
    return json.loads(urllib.request.urlopen(CATALOG, timeout=60).read())


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def match(cat, duration=None, title=None):
    """(url, entry, why) for the one episode this is, or (None, None, reason)."""
    ok = {u: e for u, e in cat.items() if e.get("height", 0) >= MIN_H and not e.get("short")}
    if duration:
        near = [(u, e) for u, e in ok.items() if abs(e.get("dur", 0) - duration) <= TOL]
        if len(near) == 1:
            return near[0][0], near[0][1], f"duration {duration:.1f}s matched one episode"
        if len(near) > 1:
            # more than one at that length: the title breaks the tie, loosely
            if title:
                t = norm(title)
                best = [(u, e) for u, e in near if norm(e["title"])[:18] in t or t[:18] in norm(e["title"])]
                if len(best) == 1:
                    return best[0][0], best[0][1], "duration and title agreed"
            return None, None, f"{len(near)} episodes are within {TOL}s of {duration:.1f}s - " \
                               f"say which: {[e['title'][:40] for _u, e in near]}"
        return None, None, f"nothing within {TOL}s of {duration:.1f}s. The published cut may be " \
                           f"trimmed, or the catalogue may be stale - refresh it in kt-machine."
    if title:
        t = norm(title)
        hits = [(u, e) for u, e in ok.items() if norm(e["title"])[:20] in t or t[:20] in norm(e["title"])]
        if len(hits) == 1:
            return hits[0][0], hits[0][1], "title matched one episode"
        return None, None, (f"{len(hits)} title matches. Titles differ between the VSC platform "
                            f"and Rumble - measure the duration and pass it instead.")
    return None, None, "no duration and no title to go on"


def main():
    cat = catalog()
    print(f"{len(cat)} episodes in the catalogue", flush=True)
    key = sys.argv[1] if len(sys.argv) > 1 else None
    dur = float(sys.argv[2]) if len(sys.argv) > 2 else None
    import glob
    for f in sorted(glob.glob(os.path.join(HERE, "plans", "*.json"))):
        p = json.load(open(f))
        if key and p["key"] != key:
            continue
        if p.get("rumble") and not dur:
            print(f"  {p['key']}: already on Rumble -> {p['rumble']}"); continue
        u, e, why = match(cat, dur or p.get("duration"), p.get("title") or p.get("source"))
        if not u:
            print(f"  {p['key']}: NOT MATCHED - {why}"); continue
        p["rumble"], p["duration"], p["height"] = u, e["dur"], e["height"]
        p["rumble_title"] = e["title"]
        json.dump(p, open(f, "w"), indent=1)
        print(f"  {p['key']}: {why}\n      {e['height']}p {e['dur']}s  {e['title']}\n      {u}")
    print("MATCHDONE")


if __name__ == "__main__":
    main()
