#!/usr/bin/env python3
"""Build this shard's clips and READ THE FILES BACK. One server, two clips.

Runs the same vsc_week pipeline the Mac runs - locate the cut by the sentences the
plan names, build the captions, pin them to the sound by identity, render - and then
checks the finished file rather than trusting that the calls returned success: is the
word Kevin is saying on screen at a dozen random moments, and does any caption
overlap the next. A clip that fails those is still uploaded, but it is NAMED in the
report so nobody hands it to a reviewer by accident.
"""
import glob, json, os, shutil, sys

sys.path.insert(0, os.path.expanduser("~/Kamay"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cloud.source import fetch, plans                                    # noqa: E402

OUT = "/tmp/shard_out"
CLIPS = os.path.expanduser("~/Desktop/VSC/Clips")


def main(key, names):
    import vsc_week, vsc_v2_onscreen
    plan = [p for p in plans() if p["key"] == key][0]
    fetch(plan)
    os.makedirs(OUT, exist_ok=True)
    vsc_week.main(names)
    report = []
    for name in names:
        f = glob.glob(os.path.join(CLIPS, name + "_*.mp4"))
        if not f:
            report.append({"clip": name, "ok": False, "why": "nothing was rendered"})
            continue
        r = vsc_v2_onscreen.check(f[0])
        hit, miss = (r[0], r[1]) if r else (0, 0)
        caps = [tuple(x) for x in json.load(open(f[0][:-4] + "__caps.json"))]
        ov = sum(1 for i in range(len(caps) - 1) if caps[i][1] > caps[i + 1][0] + 0.001)
        ok = bool(r) and hit >= 9 and ov == 0
        report.append({"clip": name, "ok": ok, "moments": f"{hit}/{hit + miss}",
                       "overlaps": ov, "file": os.path.basename(f[0])})
        for g in (f[0], f[0][:-4] + "__caps.json"):
            shutil.copy(g, OUT)
    json.dump(report, open(os.path.join(OUT, f"report-{key}-{os.environ.get('SHARD','x')}.json"), "w"), indent=1)
    for x in report:
        print(f"  {'ok ' if x['ok'] else 'LOOK'} {x['clip']:28} {x.get('moments','')} moments, "
              f"{x.get('overlaps','?')} overlaps", flush=True)
    print("BUILDOK")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
