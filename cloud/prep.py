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


def unpack(tar, src):
    """Put each file back where it was made: .work, or beside the source video."""
    srcdir = os.path.dirname(src)
    os.makedirs(WORK, exist_ok=True)
    with tarfile.open(tar) as t:
        for m in t.getmembers():
            if not m.isfile():
                continue
            where, _, name = m.name.partition("/")
            if not name:                      # older bundles: everything was .work
                where, name = "work", m.name
            d = srcdir if where == "source" else WORK
            f = t.extractfile(m)
            with open(os.path.join(d, os.path.basename(name)), "wb") as out:
                out.write(f.read())


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
        unpack(tar, src)
        print(f"  prep reused from the release for {plan['key']}", flush=True)
        return
    vsc_week.ensure_transcript(src, base)                 # transcript + words + shots
    # THE SHOT MAP IS NOT IN .work. It is written next to the source file, and prep
    # only ever packed .work - so the one genuinely expensive artifact, face-tracking
    # 1090 seconds of video, was never shared and every shard redid it. Both places go
    # in the bundle now, each tagged with where it belongs.
    srcdir = os.path.dirname(src)
    keep = [("work", WORK, f) for f in os.listdir(WORK)
            if f.startswith(base) or f.startswith("TRANSCRIPT")]
    keep += [("source", srcdir, f) for f in os.listdir(srcdir)
             if f.startswith(base) and f.endswith(".json")]
    with tarfile.open(tar, "w:gz") as t:
        for where, d, f in keep:
            t.add(os.path.join(d, f), arcname=f"{where}/{f}")
    print("  prep bundle holds: " + ", ".join(f"{w}/{f}" for w, _, f in keep), flush=True)
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
