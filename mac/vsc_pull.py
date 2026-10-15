#!/usr/bin/env python3
"""Bring finished clips down from the cloud into the VSC folder, by itself.

Kamay, 29 Sept 2026: "can i shut the mac off right now and the clips will get to the
VSC file still?" Until now, no - the factory publishes to a GitHub release and somebody
had to fetch them. This is that somebody.

It runs whenever the Mac is awake, asks whether the release holds a clip the folder does
not, and pulls only those. Cheap when there is nothing new (one API call), silent when
it has nothing to say, and it never deletes anything - a clip already in the folder is
left exactly as it is.
"""
import json, os, re, subprocess, sys, time

GH = os.path.expanduser("~/Kamay/bin/gh")
REPO = "kamaycampos/vsc-factory"
# clips land HERE, are read here, and only then move into the folder Kamay opens.
# Before 30 Sept the pull put them straight into Clips/ and the checking happened
# afterwards in a chat - so a broken clip and a finished clip looked the same to him.
# 10 Oct 2026: moved OFF the Desktop. macOS blocks a launchd job from ~/Desktop, and
# iCloud syncs it, so for a week nothing was delivered and downloads failed with
# "resource deadlock avoided". ~/Desktop/VSC/Clips is now a shortcut to ~/VSC/Clips,
# so Kamay opens the same place he always did.
DEST = os.path.expanduser("~/VSC/.incoming")
HERE = os.path.dirname(os.path.abspath(__file__))
GATE = os.path.join(HERE, "vsc_gate.py")
DELIVERED = os.path.expanduser("~/VSC/Clips")
# names already dealt with on the Desktop (old cuts, the batch GIN has) - never re-fetched
HANDLED = os.path.expanduser("~/VSC/.handled.txt")
LOG = os.path.expanduser("~/Kamay/logs/vsc_pull.log")


def sh(*a):
    return subprocess.run(list(a), capture_output=True, text=True)


def note(msg):
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a") as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M')}  {msg}\n")


def main():
    # A folder this job cannot read looks EMPTY, and every file in it "missing" - that is
    # how the gate delivered nothing for a week while the pull re-fetched the same files.
    try:
        os.listdir(os.path.dirname(DELIVERED))
    except PermissionError:
        note(f"macOS is blocking this job from {os.path.dirname(DELIVERED)} - nothing pulled")
        return 1
    # A NEW ASSIGNMENT'S SOURCE (12 Oct 2026): Rumble refuses the cloud, not this Mac.
    # vsc_source.py fetches and uploads it when the cloud could not - detached, with its
    # own lock, so a 30-minute download never holds up clips arriving here.
    subprocess.Popen([sys.executable, os.path.join(HERE, "vsc_source.py")],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True)
    r = sh(GH, "release", "view", "clips", "-R", REPO, "--json", "assets")
    if r.returncode:
        note(f"could not reach the release: {r.stderr.strip()[-120:]}")
        return 1
    assets = [a for a in json.loads(r.stdout).get("assets", [])
              if a["name"].endswith((".mp4", "__caps.json"))]
    # ONLY THE NEWEST CUT OF EACH CLIP. The release keeps every length a clip was ever
    # built at (BANNED-FOR-LIFE_53s, _54s, _55s, _65s). 10 Oct 2026: 66 files sat in the
    # holding area for 13 real clips, and each re-cut was pulled as if it were new.
    newest = {}
    for a in assets:
        if a["name"].endswith(".mp4"):
            clip = re.sub(r"_\d+s\.mp4$", "", a["name"])
            if clip not in newest or a.get("updatedAt", "") > newest[clip].get("updatedAt", ""):
                newest[clip] = a
    keep = {a["name"] for a in newest.values()}
    keep |= {n[:-4] + "__caps.json" for n in list(keep)}
    assets = [a for a in assets if a["name"] in keep]
    # A file set aside (.superseded, FINAL_23_for_GIN ...) has been dealt with; it must
    # never come back into the holding area.
    handled = set()
    if os.path.exists(HANDLED):
        handled.update(x.strip() for x in open(HANDLED) if x.strip())
    for root, _, files in os.walk(os.path.dirname(DELIVERED)):
        if root.startswith((DEST, DELIVERED)):
            continue
        handled.update(files)
    os.makedirs(DEST, exist_ok=True)
    # A CLIP WITH THE RIGHT NAME IS NOT THE RIGHT CLIP. 30 Sept 2026: eleven clips were
    # rebuilt in the cloud with 22 caption corrections in them, this pulled nothing
    # because the folder already held files with those names, and the old broken cuts
    # sat there looking finished. Same name, different file, is exactly the case that
    # matters - so what is published is compared to what is on disk by SIZE and by age,
    # and a published file that differs replaces the local one.
    want = []
    for a in assets:
        p = os.path.join(DEST, a["name"])
        here = [os.path.join(d, a["name"]) for d in (DEST, DELIVERED, os.path.join(DELIVERED, "_needs_work"),
                                                      os.path.join(DELIVERED, ".caps"),
                                                      os.path.join(DELIVERED, "_needs_work", ".caps"))]
        here = [q for q in here if os.path.exists(q)]
        # ALREADY JUDGED IF ANY COPY IS THIS FILE (13 Oct 2026). A rebuild the gate held
        # back sits in _needs_work while the older good cut stays in Clips; comparing only
        # the Clips copy re-downloaded FIRED-FROM-HIS-OWN-COMPANY every 15 minutes, and the
        # gate held it back again every time.
        same = [q for q in here if a.get("size") == os.path.getsize(q)]
        if same:
            p = same[0]
        elif here:
            p = here[0]
        if not os.path.exists(p):
            if a["name"] not in handled:
                want.append(a["name"])
            continue
        if a.get("size") and a["size"] != os.path.getsize(p):
            want.append(a["name"])
            note(f"replacing {a['name']}: published file is a different size")
            continue
        up = a.get("updatedAt") or ""
        if up:
            try:
                t = time.mktime(time.strptime(up[:19], "%Y-%m-%dT%H:%M:%S")) - time.timezone
                if t > os.path.getmtime(p) + 60:
                    want.append(a["name"])
                    note(f"replacing {a['name']}: published file is newer")
            except ValueError:
                pass
    if not want:
        return 0
    got = 0
    for a in want:
        d = sh(GH, "release", "download", "clips", "-R", REPO, "-p", a, "-D", DEST, "--clobber")
        if d.returncode == 0 and os.path.exists(os.path.join(DEST, a)):
            got += 1
        else:
            note(f"failed to fetch {a}: {d.stderr.strip()[-120:]}")
    # VERIFY WHAT LANDED. A downloaded file that will not open is worse than a missing
    # one, because it looks finished. Anything unreadable is removed and reported.
    bad = []
    for a in [x for x in want if x.endswith(".mp4")]:
        p = os.path.join(DEST, a)
        if not os.path.exists(p):
            continue
        o = sh(os.path.expanduser("~/Kamay/bin/ffmpeg"), "-nostdin", "-i", p).stderr
        if "Duration:" not in o or "1080x1920" not in o:
            os.remove(p); bad.append(a)
    note(f"pulled {got} file(s)" + (f"; discarded {len(bad)} that would not open: {bad}" if bad else ""))
    print(f"pulled {got} new file(s) into {DEST}")
    # the gate checks corrections against the LOCAL plans; on 10 Oct they were a week
    # stale and the newest batch had no plan at all, so its corrections went unchecked
    sh("git", "-C", os.path.expanduser("~/vsc-factory"), "pull", "-q", "--ff-only")
    # the cloud's verdict per clip (edge listening the Mac cannot redo) - see vsc_gate
    sh(GH, "release", "download", "clips", "-R", REPO, "-p", "verdicts.json",
       "-O", os.path.expanduser("~/VSC/.verdicts.json"), "--clobber")
    g = subprocess.run([sys.executable, GATE], capture_output=True, text=True)
    print(g.stdout.strip() or g.stderr.strip()[-400:])
    note(g.stdout.strip().splitlines()[-1] if g.stdout.strip() else "the gate did not run")
    # SAY SO when clips arrive (12 Oct 2026): "without me needing to do anything" - the
    # folder fills by itself, and the Mac tells him it did instead of him checking.
    n = sum(1 for x in g.stdout.splitlines() if x.strip().startswith("DELIVERED"))
    h = sum(1 for x in g.stdout.splitlines() if x.strip().startswith("HELD BACK"))
    if n or h:
        msg = (f"{n} new clip(s) ready in Desktop > VSC > Clips" if n else "") + \
              (f"{'; ' if n else ''}{h} held back in _needs_work" if h else "")
        sh("osascript", "-e", f'display notification "{msg}" with title "VSC clips" sound name "Glass"')
    return 0


if __name__ == "__main__":
    sys.exit(main())
