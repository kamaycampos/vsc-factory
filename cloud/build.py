#!/usr/bin/env python3
"""Build this shard's clips and READ THE FILES BACK. One server, two clips.

Runs the same vsc_week pipeline the Mac runs - locate the cut by the sentences the
plan names, build the captions, pin them to the sound by identity, render - and then
checks the finished file rather than trusting that the calls returned success: is the
word Kevin is saying on screen at a dozen random moments, and does any caption
overlap the next. A clip that fails those is still uploaded, but it is NAMED in the
report so nobody hands it to a reviewer by accident.
"""
import glob, hashlib, json, os, shutil, sys, tarfile

sys.path.insert(0, os.path.expanduser("~/Kamay"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cloud.source import fetch, plans, sh                                # noqa: E402

OUT = "/tmp/shard_out"
CLIPS = os.path.expanduser("~/Desktop/VSC/Clips")
WORK = os.path.expanduser("~/Desktop/VSC/.work")


def reuse_prep(key, src):
    """Unpack what prep already worked out for this video: the transcript, the word
    timings and the shot map.

    30 Sept 2026, the reason a batch took all day. prep builds these once and publishes
    them - and no build shard ever downloaded them, so all sixteen servers re-did the
    whole-video work from scratch: face-tracking 1090 seconds, 133 shot cuts, the
    transcript. Twenty-five minutes of identical work, sixteen times over, before a
    single frame was rendered - and the long clips were then killed mid-render because
    the runner's life had already been spent. prep's own log line, "a few minutes,
    once", was describing something that was happening every time.
    """
    tar = f"/tmp/prep-{key}.tar.gz"
    got = sh("gh", "release", "download", "prep", "-R",
             os.environ.get("GITHUB_REPOSITORY", "kamaycampos/vsc-factory"),
             "-p", os.path.basename(tar), "-D", "/tmp", "--clobber")
    if got.returncode:
        print(f"  no prep bundle for {key} - this shard has to work it out itself",
              flush=True)
        return False
    import cloud.prep as prep
    prep.unpack(tar, src)
    with tarfile.open(tar) as t:
        names = [n for n in t.getnames() if "/" in n or n]
    print(f"  prep reused: {len(names)} files, no re-transcribing and no re-framing",
          flush=True)
    return True


def _why(w):
    return w if isinstance(w, str) else "; ".join(list(w)[:2])


def main(key, names):
    import vsc_week, vsc_v2_onscreen
    plan = [p for p in plans() if p["key"] == key][0]
    from cloud.shard import fingerprint    # ONE definition of "built from this"
    fp = {c["name"]: fingerprint(c) for c in plan["clips"]}
    src = fetch(plan)
    reuse_prep(key, src)
    os.makedirs(OUT, exist_ok=True)
    # ONE CLIP AT A TIME, AND COPY IT OUT THE MOMENT IT EXISTS. A shard that is killed
    # while rendering its second clip used to lose the first one too, because the copy
    # into the upload folder happened after both were built. Nothing finished is left
    # sitting where a shutdown signal can take it.
    report = []
    for name in names:
        try:
            vsc_week.main([name])
        except Exception as e:
            sys.stderr.write(f"  {name}: {type(e).__name__}: {e}\n")
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
        # SPEECH AFTER THE CLOSE IS A FAIL, never a LOOK. 2 Oct 2026: Kamay heard "one
        # of the" and "there is a" at the end of two clips the checks had passed.
        hj = os.path.join(CLIPS, name + "__head.json")
        if os.path.exists(hj) and json.load(open(hj)).get("bad"):
            verdict = "fail"
            why = list(why if isinstance(why, (list, tuple)) else [why] if why else []) + [
                "opening: " + json.load(open(hj)).get("why", "").strip("; ") +
                " - watch the first 3 seconds"]
        tj = os.path.join(CLIPS, name + "__tail.json")
        if os.path.exists(tj) and json.load(open(tj)).get("speech_after_close"):
            t = json.load(open(tj))
            verdict = "fail"
            why = list(why if isinstance(why, (list, tuple)) else [why] if why else []) + [
                f"no pause after the close: the next word starts +{t['next_word']:.2f}s, "
                f"clip ends +{t['end']:.2f}s - listen to the last second"]
        # LISTEN TO THE EDGES OF THE FILE (cloud/edges.py). 3 Oct 2026: Kamay found four
        # delivered clips whose first or last word was cut or followed by the next one,
        # every one passed by the level and silence checks above.
        try:
            from cloud.edges import check as edges
            cj = f[0][:-4] + "__caps.json"
            e = edges(f[0], json.load(open(cj)) if os.path.exists(cj) else None,
                      next((c for c in plan["clips"] if c["name"] == name), None), work=f"/tmp/edges_{name}")
            json.dump(e, open(os.path.join(OUT, name + "__edges.json"), "w"), indent=1)
            heard_ = lambda ws: " ".join(w for a_, b_, w in (ws or []))
            print(f"  EDGES {name}: first heard [{heard_(e['first_heard'])}] caption '{e['caption_first']}' | "
                  f"last heard [{heard_(e['last_heard'])}] caption '{e['caption_last']}'", flush=True)
            if not (e["first_ok"] and e["last_ok"]):
                verdict = "fail"
                why = list(why if isinstance(why, (list, tuple)) else [why] if why else []) + [
                    ("" if e["first_ok"] else f"first word heard is not '{e['caption_first']}'; ")
                    + ("" if e["last_ok"] else f"last word heard is not '{e['caption_last']}'")]
        except Exception as ex:
            print(f"  !! edge listening failed for {name}: {ex}", flush=True)
        r = vsc_v2_onscreen.check(f[0])
        hit, miss = (r[0], r[1]) if r else (0, 0)
        report.append({"clip": name, "ok": verdict == "pass", "verdict": verdict,
                       "why": why, "moments": f"{hit}/{hit + miss}",
                       "plan": fp.get(name), "file": os.path.basename(f[0])})
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
