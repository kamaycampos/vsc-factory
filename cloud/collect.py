#!/usr/bin/env python3
"""Gather every shard's clips into one release Kamay can download in one go.

The clips do not get posted anywhere: they go to GIN's Frame.io for Cali and Naomi
to review, and that upload is his. So the factory's last job is to put the finished
batch somewhere a phone or a laptop can fetch it, with the per-clip check results
beside it, and to say plainly which clips the machine is not sure about.
"""
import glob, json, os, subprocess, sys

REPO = os.environ.get("GITHUB_REPOSITORY", "kamaycampos/vsc-machine")
IN = sys.argv[1] if len(sys.argv) > 1 else "/tmp/shards"


def sh(*a):
    return subprocess.run(list(a), capture_output=True, text=True)


def main():
    mp4 = sorted(glob.glob(os.path.join(IN, "**", "*.mp4"), recursive=True))
    rep = []
    for f in glob.glob(os.path.join(IN, "**", "report-*.json"), recursive=True):
        rep += json.load(open(f))
    # (before the early return: a round can end with cuts not found and no file)
    # WHICH CUTS COULD NOT BE FOUND, and with what plan and locator (28 Oct 2026):
    # shard.py does not retry them unchanged. A clip that rendered later drops out.
    ul = {}
    d = sh("gh", "release", "download", "clips", "-R", REPO, "-p", "unlocated.json",
           "-D", "/tmp/ul", "--clobber")
    if d.returncode == 0:
        try:
            ul = json.load(open("/tmp/ul/unlocated.json"))
        except Exception:
            ul = {}
    for r in rep:
        if r.get("unlocated"):
            ul[r["clip"]] = r["unlocated"]
        elif r.get("file"):
            ul.pop(r["clip"], None)
    os.makedirs("/tmp/ul", exist_ok=True)
    json.dump(ul, open("/tmp/ul/unlocated.json", "w"), indent=1, sort_keys=True)
    sh("gh", "release", "upload", "clips", "/tmp/ul/unlocated.json", "--clobber", "-R", REPO)
    if not mp4:
        # NOT A FAILURE. Every clip in the plans is already built, which is the normal
        # state between assignments - the Monday run has nothing to do. A machine that
        # reports red when there is no work trains everyone to ignore red.
        print("nothing new to build: every clip in the plans is already made")
        print("COLLECTOK")
        return
    sh("gh", "release", "create", "clips", "-R", REPO, "-t", "clips",
       "-n", "Finished VSC clips. Download, watch, then upload to Frame.io.")
    bad = [r for r in rep if not r.get("ok")]
    body = ["# VSC clips", "",
            f"{len(mp4)} clips in this batch. Built in the cloud; the Mac was not involved.", ""]
    body += ["| clip | verdict | word on screen | what the check found |", "|---|---|---|---|"]
    for r in sorted(rep, key=lambda r: (r.get("ok", False), r["clip"])):
        w = r.get("why") or []
        w = [w] if isinstance(w, str) else w      # "nothing was rendered" is one string, not 20 letters
        body.append(f"| {r['clip']} | **{r.get('verdict','?')}** | {r.get('moments','-')} | "
                    f"{'; '.join(w) or '-'} |")
    if bad:
        body += ["", "**Read the captions of the ones marked LOOK before they go to Frame.io.**"]
    body += ["", "Still a human's job: read every caption line, and watch the first 3 "
             "seconds and the last 2 of each clip."]
    for f in mp4 + sorted(glob.glob(os.path.join(IN, "**", "*__caps.json"), recursive=True)):
        u = sh("gh", "release", "upload", "clips", f, "--clobber", "-R", REPO)
        if u.returncode:
            print(f"  UPLOAD FAILED {os.path.basename(f)}: {u.stderr[-120:]}", flush=True)
    # WHICH PLAN EACH PUBLISHED CLIP CAME FROM. Without this, "already built" means
    # only that a file with that name exists, and a corrected plan rebuilds nothing.
    built = {}
    d = sh("gh", "release", "download", "clips", "-R", REPO, "-p", "built.json",
           "-D", "/tmp/bj", "--clobber")
    if d.returncode == 0:
        try:
            built = json.load(open("/tmp/bj/built.json"))
        except Exception:
            built = {}
    # EVERY CLIP THAT RENDERED IS BUILT FROM ITS PLAN, whatever its verdict. 12 Oct 2026:
    # only a PASS was recorded, so a LOOK or FAIL clip was rebuilt in rounds 2 and 3 of
    # every run and again by every later run - TWO-WRONG-BELIEFS and FIRED-FROM-HIS-OWN-
    # COMPANY were rendered six times on 12 Oct, each time to the same verdict, ~35 runner
    # minutes a round. Re-rendering the same plan cannot change a verdict; changing the
    # plan (a fix, a new cut) changes the fingerprint, and that rebuilds it. A clip that
    # rendered NOTHING has no file and stays unrecorded, so the retry rounds still catch it.
    for r in rep:
        if r.get("plan") and r.get("file"):
            built[r["clip"]] = r["plan"]
    os.makedirs("/tmp/bj", exist_ok=True)
    json.dump(built, open("/tmp/bj/built.json", "w"), indent=1, sort_keys=True)
    u = sh("gh", "release", "upload", "clips", "/tmp/bj/built.json", "--clobber", "-R", REPO)
    if u.returncode:
        print(f"  could not record which plan these were built from: {u.stderr[-120:]}", flush=True)
    # THE VERDICT TRAVELS WITH THE CLIP (12 Oct 2026). The Mac gate decides what reaches
    # the folder Kamay submits from, and it cannot listen to the edges - only the cloud
    # does. FIRED-FROM-HIS-OWN-COMPANY was a cloud FAIL and the Mac delivered it anyway,
    # because nothing carried the verdict down. Keyed by clip, with the exact file name,
    # so an older verdict never judges a newer file.
    verdicts = {}
    d = sh("gh", "release", "download", "clips", "-R", REPO, "-p", "verdicts.json",
           "-D", "/tmp/bj", "--clobber")
    if d.returncode == 0:
        try:
            verdicts = json.load(open("/tmp/bj/verdicts.json"))
        except Exception:
            verdicts = {}
    for r in rep:
        if r.get("file"):
            w = r.get("why") or []
            verdicts[r["clip"]] = {"file": r["file"], "verdict": r.get("verdict"),
                                   "why": [w] if isinstance(w, str) else list(w)}
    json.dump(verdicts, open("/tmp/bj/verdicts.json", "w"), indent=1, sort_keys=True)
    sh("gh", "release", "upload", "clips", "/tmp/bj/verdicts.json", "--clobber", "-R", REPO)
    open("/tmp/notes.md", "w").write("\n".join(body))
    sh("gh", "release", "edit", "clips", "-R", REPO, "-F", "/tmp/notes.md")
    print("\n".join(body))
    print(f"\nhttps://github.com/{REPO}/releases/tag/clips")
    print("COLLECTOK")


if __name__ == "__main__":
    main()
