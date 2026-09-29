#!/usr/bin/env python3
"""Put a plan's source video where the pipeline expects it, on the server.

The GIN "Classified" interviews are NOT on Rumble (checked 27 Sept against all 34
episodes the KT factory has stocked) and YouTube refuses cloud runners outright
("The page needs to be reloaded", SABR streaming). So the source arrives one of two
ways, tried in this order:

  1. the `sources` release of this PRIVATE repository - uploaded once per video,
     after which every build, re-run and later week needs no Mac at all;
  2. Frame.io, when FRAMEIO_TOKEN is set - the authoritative copy, and where GIN
     publishes the assignments in the first place.

Nothing is re-encoded and nothing is encrypted: the repository is private, which is
also what lets it hold Apple's DIN font.
"""
import json, os, subprocess, sys

K = os.path.expanduser("~/Kamay")
SRC = os.path.expanduser("~/Desktop/VSC/Source")
REPO = os.environ.get("GITHUB_REPOSITORY", "kamaycampos/vsc-machine")
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def sh(*a):
    return subprocess.run(list(a), capture_output=True, text=True)


def height(f):
    r = sh(os.path.join(K, "bin", "ffprobe"), "-v", "error", "-select_streams", "v:0",
           "-show_entries", "stream=height", "-of", "csv=p=0", f)
    try:
        return int(r.stdout.strip().split("\n")[0])
    except Exception:
        return 0


_retried = {}


def fetch(plan):
    # ASSET NAMES STAY PLAIN. The Frame.io originals are called things like
    # "Why Millionaires Love PROBLEMS [kYuMd5P4NK0]_H264.mp4", and a shell treats
    # those brackets as a glob pattern - the upload silently matched nothing twice
    # before anyone noticed. The asset is named after the plan key; the file is then
    # saved under a name starting with the plan's prefix, which is what the pipeline
    # globs for.
    name = plan["source"]
    dest = os.path.join(SRC, f"{plan['prefix']} {plan['key']}.mp4")
    if os.path.exists(dest) and height(dest) >= 1000:
        return dest
    os.makedirs(SRC, exist_ok=True)
    # RUMBLE FIRST when the plan has been matched. Kevin publishes every episode there
    # too, so nothing needs uploading from a laptop ever again. Cloudflare turns the
    # first request away sometimes, so this poses as Chrome and retries - the pattern
    # kt-machine has used daily since September.
    # THE CACHED COPY FIRST. Rumble is how the file is OBTAINED the first time; it is
    # not how it should be fetched six times a run. 29 Sept: every one of the six build
    # shards downloaded its own 1.2GB copy from Rumble because this block sat below the
    # Rumble one - slow, and three shards died (two killed outright, most likely the
    # runner filling its disk). The release copy lives in the same datacentre, cannot
    # be refused by Cloudflare, and is already the thing prep put there for exactly
    # this purpose.
    r = sh("gh", "release", "download", "sources", "-R", REPO, "-p", name, "-D", "/tmp", "--clobber")
    if r.returncode == 0 and os.path.exists(os.path.join("/tmp", name)):
        # THE CACHED SOURCE IS ENCRYPTED. This repository is public (for the unlimited
        # Actions minutes), and a public repository must never re-host someone's video.
        # Same treatment kt-machine gives its episodes: the bytes are opened at build
        # time with a secret nobody outside the machine holds.
        enc = os.path.join("/tmp", name)
        if name.endswith(".enc"):
            sh("openssl", "enc", "-d", "-aes-256-cbc", "-pbkdf2", "-pass", "env:VSC_KEY",
               "-in", enc, "-out", dest)
            os.remove(enc)
        else:
            os.replace(enc, dest)
    if r.returncode and os.environ.get("FRAMEIO_TOKEN") and plan.get("frameio_asset"):
        import urllib.request
        req = urllib.request.Request(
            f"https://api.frame.io/v2/assets/{plan['frameio_asset']}",
            headers={"Authorization": "Bearer " + os.environ["FRAMEIO_TOKEN"]})
        a = json.load(urllib.request.urlopen(req))
        url = a.get("original")
        if not url:
            raise SystemExit("Frame.io gave no original for that asset")
        urllib.request.urlretrieve(url, dest)
    elif r.returncode:
        raise SystemExit(f"no source for {name}: not in the sources release, and no "
                         f"FRAMEIO_TOKEN + frameio_asset to fall back on.\n{r.stderr[-200:]}")
    if plan.get("rumble") and not (os.path.exists(dest) and height(dest) >= 1000):
        import time
        may_cache = os.environ.get("SOURCE_MAY_CACHE") == "1"
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U",
                        "yt-dlp[default,curl-cffi]", "curl_cffi"], capture_output=True)
        for attempt in range(6):
            sh(sys.executable, "-m", "yt_dlp", "--no-warnings", "-q", "--impersonate", "chrome",
               "-N", "8", "-f", "bv*[height<=2160]+ba/b[height<=2160]",
               "--merge-output-format", "mp4", "-o", dest, plan["rumble"])
            if os.path.exists(dest) and height(dest) >= 1000:
                print(f"  fetched from Rumble ({height(dest)}p): {plan.get('rumble_title','')}",
                      flush=True)
                # KEEP IT - BUT ONLY FROM PREP. Rumble sits behind Cloudflare and
                # refuses sometimes (served this episode at 01:22, turned every attempt
                # away at 14:09), so the first successful fetch caches it in this repo's
                # own release and no later run depends on Rumble being up.
                #
                # ONLY PREP MAY WRITE IT. 28 Sept: every one of the 8 build shards runs
                # at the same time and each tried to cache the same 1.2GB asset with
                # --clobber. Clobber deletes before it uploads, so the asset kept
                # vanishing for minutes at a time - and the other shards, looking for it
                # exactly then, were told it was "not in the sources release". Six of
                # eight failed. Prep runs alone, before any shard exists, so it is the
                # only safe writer. Same rule as the posting queue: ONE writer.
                if not may_cache:
                    return dest
                cached = os.path.join("/tmp", name)
                sh("openssl", "enc", "-aes-256-cbc", "-pbkdf2", "-salt",
                   "-pass", "env:VSC_KEY", "-in", dest, "-out", cached)
                up = sh("gh", "release", "upload", "sources", cached, "--clobber", "-R", REPO)
                os.remove(cached)
                print("  cached to the sources release" if not up.returncode else
                      f"  could not cache it: {up.stderr[-120:]}", flush=True)
                return dest
            time.sleep(12 * (attempt + 1))
        print("  Rumble refused every attempt; falling back to the uploaded release", flush=True)
    # download under the ASSET's plain name, then put it at dest - forgetting this
    # rename made the gate report "source is 0p", which is exactly what a gate is for
    h = height(dest)
    # A CACHED FILE CAN BE A BAD FILE. The parallel-clobber race could leave a
    # half-written asset behind, and a truncated mp4 looks like a present file to
    # everything except a decoder. If what came out of the cache cannot be read, throw
    # it away and go back to Rumble rather than failing the whole run on it.
    if h < 1000 and plan.get("rumble") and not _retried.get(dest):
        print(f"  the cached copy is unreadable ({h}p) - discarding it and refetching",
              flush=True)
        _retried[dest] = True
        os.remove(dest)
        return fetch(plan)
    # 18 clips once went out blurry from 640x360 sources and the output size proved
    # nothing. The gate is on the SOURCE, before a single frame is rendered.
    if h < 1000:
        raise SystemExit(f"REFUSED: source is {h}p, the gate is 1080p")
    print(f"  source ready: {name}  {h}p", flush=True)
    return dest


def plans():
    import glob
    return [json.load(open(f)) for f in sorted(glob.glob(os.path.join(HERE, "plans", "*.json")))]


if __name__ == "__main__":
    key = sys.argv[1] if len(sys.argv) > 1 else None
    for p in plans():
        if key and p["key"] != key:
            continue
        fetch(p)
    print("SOURCEOK")
