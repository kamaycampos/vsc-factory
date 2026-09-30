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


def _why(w):
    return w if isinstance(w, str) else "; ".join(list(w)[:2])


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
        # THE GATE. Every mechanical check there is, run on the finished file: captions
        # on the sound, nothing drawn over anything, clean opening and ending, and the
        # damage patterns that transcription actually produces - repeated words,
        # scrambled phrases, stray full stops. A clip it cannot vouch for is marked, and
        # a marked clip is not something to hand a reviewer or an account.
        import kt_qc
        verdict, why = kt_qc.check(f[0])
        r = vsc_v2_onscreen.check(f[0])
        hit, miss = (r[0], r[1]) if r else (0, 0)
        report.append({"clip": name, "ok": verdict == "pass", "verdict": verdict,
                       "why": why, "moments": f"{hit}/{hit + miss}",
                       "file": os.path.basename(f[0])})
        for g in (f[0], f[0][:-4] + "__caps.json"):
            shutil.copy(g, OUT)
    json.dump(report, open(os.path.join(OUT, f"report-{key}-{os.environ.get('SHARD','x')}.json"), "w"), indent=1)
    for x in report:
        print(f"  {x.get('verdict','?').upper():5} {x['clip']:28} {x.get('moments','')} moments"
              + (f"  |  {_why(x.get('why'))}" if x.get('why') else ""), flush=True)
    print("BUILDOK")
    # A clip that produced NO FILE is a machine failure, and a machine failure has to
    # turn the job red. On 29 Sept RUN-AT-THE-PROBLEM rendered nothing, this report
    # said so, and the job still finished green - so the clip was simply absent from
    # the batch with nothing anywhere saying it was missing. The artifact is already
    # uploaded by then (the upload step runs even on failure), so nothing is lost by
    # failing here. A QC verdict of "look" is NOT this: that is a judgement for a human
    # and it stays green, named in the release notes.
    gone = [x["clip"] for x in report if x.get("why") == "nothing was rendered"]
    if gone:
        sys.exit("NOT RENDERED: " + ", ".join(gone))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
