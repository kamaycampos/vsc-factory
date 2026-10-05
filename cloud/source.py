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
    """The plan's source video, on disk, ready to cut. Tried in order, never fatal
    until every route is exhausted.

    1. THE CACHED COPY in this repo's `sources` release. Encrypted, because this
       repository is public and a public repository must never re-host someone's video.
       Fast, in the same datacentre, and cannot be refused.
    2. RUMBLE, which is how the file is OBTAINED the first time. Cloudflare turns
       requests away sometimes, so this poses as Chrome and retries. Prep - and only
       prep, which runs alone before any shard exists - then caches it encrypted so
       nothing ever depends on Rumble twice.
    3. FRAME.IO, if a token and an asset id are configured.

    Written as one straight line of fallbacks after three separate bugs lived in the
    tangle this used to be: an upload that silently matched nothing, a download that
    was never moved to where the pipeline looks, and a release failure that raised
    before the Rumble fallback it was supposed to fall back to.
    """
    name = plan["source"]
    dest = os.path.join(SRC, f"{plan['prefix']} {plan['key']}.mp4")
    os.makedirs(SRC, exist_ok=True)

    def usable():
        return os.path.exists(dest) and height(dest) >= 1000

    if usable():
        return dest

    # 1. the cached copy (one file, or <name>.part00, .part01... for one over 2 GiB)
    r = sh("gh", "release", "download", "sources", "-R", REPO, "-p", name, "-D", "/tmp",
           "--clobber")
    got = os.path.join("/tmp", name)
    if r.returncode != 0 and name.endswith(".enc"):
        sh("gh", "release", "download", "sources", "-R", REPO, "-p", name + ".part*", "-D", "/tmp",
           "--clobber")
        parts = sorted(os.path.join("/tmp", f) for f in os.listdir("/tmp") if f.startswith(name + ".part"))
        if parts:
            j = subprocess.run("cat " + " ".join(f'"{x}"' for x in parts) + f' > "{got}"', shell=True)
            for x in parts:
                os.remove(x)
            r = j
    if r.returncode == 0 and os.path.exists(got):
        if name.endswith(".enc"):
            sh("openssl", "enc", "-d", "-aes-256-cbc", "-pbkdf2", "-pass", "env:VSC_KEY",
               "-in", got, "-out", dest)
            os.remove(got)
        else:
            os.replace(got, dest)
        if usable():
            print(f"  source from the cache ({height(dest)}p)", flush=True)
            return dest
        # a truncated or wrongly-keyed file looks present to everything but a decoder
        print("  the cached copy is unreadable - discarding it", flush=True)
        os.path.exists(dest) and os.remove(dest)

    # 2. Rumble
    if plan.get("rumble"):
        import time
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "-U",
                        "yt-dlp[default,curl-cffi]", "curl_cffi"], capture_output=True)
        for attempt in range(6):
            sh(sys.executable, "-m", "yt_dlp", "--no-warnings", "-q", "--impersonate",
               "chrome", "-N", "8", "-f", "bv*[height<=2160]+ba/b[height<=2160]",
               "--merge-output-format", "mp4", "-o", dest, plan["rumble"])
            if usable():
                print(f"  fetched from Rumble ({height(dest)}p): "
                      f"{plan.get('rumble_title', '')}", flush=True)
                if os.environ.get("SOURCE_MAY_CACHE") == "1":
                    # OVER 2 GiB GOES UP IN PARTS (5 Oct 2026): GitHub refuses a release
                    # asset of 2 GiB or more, and every shard downloads the source from
                    # here. Same scheme as kt-machine's rumble_stock.py; the download
                    # above joins the parts byte for byte.
                    enc = os.path.join("/tmp", name)
                    sh("gh", "release", "create", "sources", "-R", REPO, "-t", "sources",
                       "-n", "Source videos, encrypted. This repository is public.")
                    part = 1900 * 1024 * 1024
                    if os.path.getsize(dest) < part - 1024 * 1024:
                        sh("openssl", "enc", "-aes-256-cbc", "-pbkdf2", "-salt",
                           "-pass", "env:VSC_KEY", "-in", dest, "-out", enc)
                        files = [enc]
                    else:
                        subprocess.run(f'openssl enc -aes-256-cbc -pbkdf2 -salt -pass env:VSC_KEY '
                                       f'-in "{dest}" | split -b {part} -d -a 2 - "{enc}.part"',
                                       shell=True, check=True)
                        files = sorted(os.path.join("/tmp", f) for f in os.listdir("/tmp")
                                       if f.startswith(name + ".part"))
                    u = None
                    for f in files:
                        u = sh("gh", "release", "upload", "sources", f, "--clobber", "-R", REPO)
                        os.remove(f)
                        if u.returncode:
                            break
                    print("  cached, encrypted, to the sources release" if not u.returncode
                          else f"  could not cache it: {u.stderr[-120:]}", flush=True)
                return dest
            time.sleep(12 * (attempt + 1))
        print("  Rumble refused every attempt", flush=True)

    # 3. Frame.io
    if os.environ.get("FRAMEIO_TOKEN") and plan.get("frameio_asset"):
        import urllib.request
        req = urllib.request.Request(
            f"https://api.frame.io/v2/assets/{plan['frameio_asset']}",
            headers={"Authorization": "Bearer " + os.environ["FRAMEIO_TOKEN"]})
        a = json.load(urllib.request.urlopen(req))
        if a.get("original"):
            urllib.request.urlretrieve(a["original"], dest)
            if usable():
                return dest

    raise SystemExit(
        f"no source for {plan['key']}: nothing cached, "
        f"{'Rumble refused' if plan.get('rumble') else 'no Rumble URL'}, "
        f"and no Frame.io fallback configured.")


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
