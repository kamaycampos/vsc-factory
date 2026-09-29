#!/usr/bin/env python3
"""The expensive work that every clip of one video shares - done ONCE.

Three things cost minutes per video and nothing per clip: the whole-file
transcription, the chunked word timings, and finding Kevin shot by shot. Doing them
inside each build shard would repeat an 18-minute transcription nine times over.
They are built here and published as prep-<key>.tar.gz, so the shards just unpack
them and start rendering.

Also writes TRANSCRIPT.txt - the timestamped read a human (or a planning routine)
uses to CHOOSE the clips, which is the one step no machine does.
"""
import os, subprocess, sys, tarfile

sys.path.insert(0, os.path.expanduser("~/Kamay"))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from cloud.source import fetch, plans, sh                                # noqa: E402

WORK = os.path.expanduser("~/Desktop/VSC/.work")
REPO = os.environ.get("GITHUB_REPOSITORY", "kamaycampos/vsc-machine")


def build(plan):
    """A plan with no clips yet is a STUB: it exists so the cloud will fetch the
    episode and transcribe it, and the transcript comes back for a human to choose the
    clips from. That is the whole loop with the Mac shut - name the assignment, match
    it to Rumble, read the transcript it publishes, write the clips, push."""
    import vsc_week
    src = fetch(plan)
    base = os.path.splitext(os.path.basename(src))[0]
    tar = f"/tmp/prep-{plan['key']}.tar.gz"
    got = sh("gh", "release", "download", "prep", "-R", REPO,
             "-p", os.path.basename(tar), "-D", "/tmp", "--clobber")
    if got.returncode == 0:
        with tarfile.open(tar) as t:
            t.extractall(WORK)
        print(f"  prep reused from the release for {plan['key']}", flush=True)
        return
    vsc_week.ensure_transcript(src, base)                 # transcript + words + shots
    keep = [f for f in os.listdir(WORK) if f.startswith(base) or f.startswith("TRANSCRIPT")]
    with tarfile.open(tar, "w:gz") as t:
        for f in keep:
            t.add(os.path.join(WORK, f), arcname=f)
    sh("gh", "release", "create", "prep", "-R", REPO, "-t", "prep", "-n",
       "Transcripts, word timings and shot maps, one bundle per source.")
    up = sh("gh", "release", "upload", "prep", tar, "--clobber", "-R", REPO)
    # THE TRANSCRIPT GOES UP ON ITS OWN. It is the one thing a person needs back from
    # this stage - the whole loop is: name the episode, read the transcript it
    # publishes, mark the moments. Buried inside a tarball it is not "automatic", it is
    # homework.
    for t in [f for f in os.listdir(WORK) if f.startswith("TRANSCRIPT")]:
        sh("gh", "release", "upload", "prep", os.path.join(WORK, t), "--clobber", "-R", REPO)
        print(f"  transcript published: {t}", flush=True)
    print(f"  prep built and published ({len(keep)} files){'' if not up.returncode else ' - UPLOAD FAILED'}",
          flush=True)


if __name__ == "__main__":
    key = sys.argv[1] if len(sys.argv) > 1 else None
    for p in plans():
        if key and p["key"] != key:
            continue
        build(p)
    print("PREPOK")
