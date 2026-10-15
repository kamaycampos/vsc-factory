#!/usr/bin/env python3
"""The Mac fetches a VSC source when the cloud cannot. Started by vsc_pull every 15 min.

12 Oct 2026: "Why Your Prayers Fail" sat unbuilt for a day. Rumble's Cloudflare refuses
GitHub's runners ("Rumble refused every attempt"), so every new assignment the autopilot
starts dies in prep until someone downloads the episode on a Mac and uploads it by hand.
That someone is this script. The same Rumble URL serves this Mac 2160p.

For each plan in ~/vsc-factory/plans with a Rumble URL whose source is not on the
`sources` release, and only while NO vsc run is queued or running (a run's prep may be
caching the same file - two encryptions with different salts, mixed part by part,
decrypt to garbage):
  download (>= 1080p, checked) -> lock with VSC_KEY (~/.vsc_key) -> split into the same
  1900 MiB parts source.py joins -> upload -> check every part's size on the release ->
  start vsc.yml. A part that fails is removed with the rest of that attempt, so the
  release holds the whole file or none of it - never a part01 without its part00.

Silent when there is nothing to do. One at a time (a lock), and it never deletes
anything on the release that it did not upload in the same attempt.
"""
import fcntl, glob, json, os, re, shutil, subprocess, sys, time

GH = os.path.expanduser("~/Kamay/bin/gh")
YTDLP = os.path.expanduser("~/Kamay/bin/yt-dlp_macos")
FF = os.path.expanduser("~/Kamay/bin/ffmpeg")
KEYFILE = os.path.expanduser("~/.vsc_key")
REPO = "kamaycampos/vsc-factory"
PLANS = os.path.expanduser("~/vsc-factory/plans")
WORK = os.path.expanduser("~/VSC/.source_work")
LOCK = os.path.expanduser("~/VSC/.source.lock")
LOG = os.path.expanduser("~/Kamay/logs/vsc_source.log")
PART = 1900 * 1024 * 1024          # cloud/source.py: GitHub refuses an asset of 2 GiB+


def sh(*a, **k):
    return subprocess.run(list(a), capture_output=True, text=True, **k)


def note(msg):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M')}  {msg}\n")


def tell(msg):
    note(msg)
    sh("osascript", "-e", f'display notification "{msg}" with title "VSC source"')


def on_release():
    r = sh(GH, "release", "view", "sources", "-R", REPO, "--json", "assets")
    if r.returncode:
        return None
    return {a["name"]: a["size"] for a in json.loads(r.stdout).get("assets", [])}


def present(name, assets):
    """The whole file is there: one asset, or part00, part01 ... with no gap."""
    if name in assets:
        return True
    parts = sorted(n for n in assets if re.fullmatch(re.escape(name) + r"\.part\d\d", n))
    return bool(parts) and parts == [f"{name}.part{i:02d}" for i in range(len(parts))]


def cloud_busy():
    r = sh(GH, "run", "list", "-R", REPO, "-w", "vsc", "-L", "5", "--json", "status")
    if r.returncode:
        return True                            # cannot tell: do nothing this round
    return any(x["status"] in ("queued", "in_progress", "waiting", "pending", "requested")
               for x in json.loads(r.stdout))


def height(f):
    o = sh(FF, "-nostdin", "-i", f).stderr
    m = re.search(r"Video:.*?, (\d{3,5})x(\d{3,5})", o)
    return int(m[2]) if m else 0


def fetch(plan, assets):
    name, key = plan["source"], plan["key"]
    if plan.get("source_key", "VSC_KEY") != "VSC_KEY":
        note(f"{key}: source missing but the plan names {plan['source_key']}, "
             "which this Mac does not hold - left alone")
        return False
    free = shutil.disk_usage(os.path.expanduser("~")).free
    if free < 6 * 1024 ** 3:          # a 27-min 4K source peaks at ~5 GB (file + its encrypted parts)
        tell(f"{key}: source missing, but the Mac has only {free // 1024 ** 3} GB free - "
             "need 6 GB to fetch it")
        return False
    shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(WORK)
    src = os.path.join(WORK, f"{key}.mp4")
    tell(f"Fetching the source for {key} on the Mac (the cloud was refused)")
    env = dict(os.environ, PATH=os.path.expanduser("~/Kamay/bin") + ":" + os.environ.get("PATH", ""))
    for attempt in range(3):
        sh(YTDLP, "--no-warnings", "-q", "--impersonate", "chrome", "-N", "8",
           "-f", "bv*[height<=2160]+ba/b[height<=2160]", "--merge-output-format", "mp4",
           "-o", src, plan["rumble"], env=env)
        if os.path.exists(src) and height(src) >= 1000:
            break
        time.sleep(30 * (attempt + 1))
    h = height(src) if os.path.exists(src) else 0
    if h < 1000:
        tell(f"{key}: could not download a 1080p+ copy from Rumble (got {h or 'nothing'})")
        shutil.rmtree(WORK, ignore_errors=True)
        return False
    # lock and split in one stream: no second full-size copy on a nearly full disk
    env["VSC_KEY"] = open(KEYFILE).read().strip()
    enc = os.path.join(WORK, name)
    if os.path.getsize(src) < PART - 1024 * 1024:
        r = sh("openssl", "enc", "-aes-256-cbc", "-pbkdf2", "-salt", "-pass", "env:VSC_KEY",
               "-in", src, "-out", enc, env=env)
        files = [enc]
    else:
        r = subprocess.run(f'openssl enc -aes-256-cbc -pbkdf2 -salt -pass env:VSC_KEY -in "{src}" '
                           f'| split -b {PART} -a 2 -d - "{enc}.part"', shell=True, env=env,
                           capture_output=True, text=True)
        files = sorted(glob.glob(enc + ".part*"))
    env.pop("VSC_KEY")
    os.remove(src)
    if r.returncode or not files:
        tell(f"{key}: locking the source failed - nothing uploaded")
        shutil.rmtree(WORK, ignore_errors=True)
        return False
    sizes = {os.path.basename(f): os.path.getsize(f) for f in files}
    # 2 GB uploads take ~16 min each from here; one retry per part
    for f in files:
        for _ in range(2):
            if sh(GH, "release", "upload", "sources", f, "-R", REPO, "--clobber").returncode == 0:
                break
        os.remove(f)
    now = on_release() or {}
    wrong = [n for n, s in sizes.items() if now.get(n) != s]
    shutil.rmtree(WORK, ignore_errors=True)
    if wrong:
        for n in sizes:                          # whole file or none of it
            sh(GH, "release", "delete-asset", "sources", n, "-R", REPO, "-y")
        tell(f"{key}: upload incomplete ({', '.join(wrong)}) - removed, will retry")
        return False
    tell(f"{key}: source uploaded ({h}p, {len(sizes)} part(s))")
    return True


def main():
    os.makedirs(os.path.dirname(LOCK), exist_ok=True)
    lk = open(LOCK, "w")
    try:
        fcntl.flock(lk, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return 0                                  # a fetch is already running
    if not os.path.exists(KEYFILE):
        return 0
    sh("git", "-C", os.path.dirname(PLANS), "pull", "-q", "--ff-only")
    todo = []
    for f in sorted(glob.glob(os.path.join(PLANS, "*.json"))):
        p = json.load(open(f))
        if p.get("rumble") and p.get("source"):
            todo.append(p)
    if not todo:
        return 0
    assets = on_release()
    if assets is None:
        return 0
    todo = [p for p in todo if not present(p["source"], assets)]
    if not todo or cloud_busy():
        return 0
    # every missing source first, ONE run after (15 Oct): starting a run after the first
    # upload let its prep reach for the second source while this was still uploading it
    if sum(1 for p in todo if fetch(p, assets)):
        sh(GH, "workflow", "run", "vsc.yml", "-R", REPO, "--ref", "main")
        tell("sources uploaded - the cloud is building the new batches")
    return 0


if __name__ == "__main__":
    sys.exit(main())
