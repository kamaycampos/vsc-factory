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
        body.append(f"| {r['clip']} | **{r.get('verdict','?')}** | {r.get('moments','-')} | "
                    f"{'; '.join(r.get('why', [])) or '-'} |")
    if bad:
        body += ["", "**Read the captions of the ones marked LOOK before they go to Frame.io.**"]
    body += ["", "Still a human's job: read every caption line, and watch the first 3 "
             "seconds and the last 2 of each clip."]
    for f in mp4 + sorted(glob.glob(os.path.join(IN, "**", "*__caps.json"), recursive=True)):
        u = sh("gh", "release", "upload", "clips", f, "--clobber", "-R", REPO)
        if u.returncode:
            print(f"  UPLOAD FAILED {os.path.basename(f)}: {u.stderr[-120:]}", flush=True)
    open("/tmp/notes.md", "w").write("\n".join(body))
    sh("gh", "release", "edit", "clips", "-R", REPO, "-F", "/tmp/notes.md")
    print("\n".join(body))
    print(f"\nhttps://github.com/{REPO}/releases/tag/clips")
    print("COLLECTOK")


if __name__ == "__main__":
    main()
