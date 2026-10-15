#!/usr/bin/env python3
"""Nothing reaches ~/Desktop/VSC/Clips unless it is deliverable.

Kamay, 30 Sept 2026: "i dont want to AGAIN go into the VSC file and found BS clips."
Until now the pull dropped whatever the cloud published straight into the folder, and
the checking happened afterwards, in a chat, by me. So a broken clip and a finished
clip looked exactly the same to the person opening the folder.

This inverts it. Clips land in a holding area first and are read there. Only a clip
that passes goes into Clips/. Everything else goes to Clips/_needs_work/ with a
plain-English note beside it saying what is wrong. If the folder has a clip in it,
that clip can be submitted - that is the whole contract.

Three things are checked, all on the FINISHED file, never on a promise:
  1. it opens, it is 1080x1920, it has sound
  2. kt_qc - captions on the sound, nothing drawn over anything, clean opening and
     ending, and the damage patterns transcription actually makes
  3. every correction the plan asked for is actually in the captions. This is the one
     that was missing on 30 Sept, when 22 corrections were written, none were applied,
     and every layer reported success.
"""
import glob, hashlib, json, os, re, subprocess, sys, urllib.request

sys.path.insert(0, os.path.expanduser("~/Kamay"))


def live_engine():
    """The SAME kt_qc the cloud judged the clip with, not a hand-copied one.

    12 Oct 2026: the cloud pulls kt-machine/shared live at every build, but this gate
    imported ~/Kamay/kt_qc.py, a copy made by hand on 10 Oct - and the local kt-machine
    checkout was 70 commits behind. A fix to the shared gate would have passed a clip in
    the cloud and held it back here. Fetched each run into ~/VSC/.engine, kept only if
    its sha1 matches the shared MANIFEST; offline, the last good copy (or ~/Kamay's) is used.
    """
    eng = os.path.expanduser("~/VSC/.engine")
    raw = "https://raw.githubusercontent.com/kamaycampos/kt-machine/main/shared"
    try:
        os.makedirs(eng, exist_ok=True)
        man = json.load(urllib.request.urlopen(f"{raw}/MANIFEST.json", timeout=20))["files"]
        body = urllib.request.urlopen(f"{raw}/kt_qc.py", timeout=20).read()
        if hashlib.sha1(body).hexdigest() == man.get("kt_qc.py"):
            open(os.path.join(eng, "kt_qc.py"), "wb").write(body)
    except Exception:
        pass
    if os.path.exists(os.path.join(eng, "kt_qc.py")):
        sys.path.insert(0, eng)


live_engine()
# Off the Desktop since 10 Oct 2026 (see vsc_pull.py). ~/Desktop/VSC/Clips points here.
DEST = os.path.expanduser("~/VSC/Clips")
HOLD = os.path.expanduser("~/VSC/.incoming")
BAD = os.path.join(DEST, "_needs_work")
FFMPEG = os.path.expanduser("~/Kamay/bin/ffmpeg")
PLANS = [os.path.expanduser("~/vsc-factory/plans")]


def plan_for(name):
    for d in PLANS:
        for f in glob.glob(os.path.join(d, "*.json")):
            for c in json.load(open(f))["clips"]:
                if c["name"] == name:
                    return c
    return None


def corrections_present(name, caps_text):
    """Did the words the plan asked for actually end up on screen?

    Compared loosely on purpose - the renderer breaks captions into lines, so a
    correction spanning a line break is there without being one string.
    """
    c = plan_for(name)
    if not c:
        return []
    flat = re.sub(r"\s+", " ", caps_text)
    missing = []
    for fix in c.get("fixes", []):
        right = re.sub(r"\s+", " ", fix[2]).strip()
        wrong = re.sub(r"\s+", " ", fix[1]).strip()
        if not right or right in flat:
            continue
        # A correction's JOB is to keep the wrong words off the screen. If they are not
        # there, it has been done - by this correction, or by a later one that rewrote
        # the same stretch. 30 Sept 2026: JOBS-WAS-FIRED read perfectly and was held
        # back anyway, because an earlier correction had been superseded by mine and
        # its exact replacement text no longer appeared.
        if wrong and wrong not in flat:
            continue
        missing.append(right)
    return missing


def check(mp4):
    """(ok, [reasons]) for one finished clip."""
    why = []
    o = subprocess.run([FFMPEG, "-nostdin", "-i", mp4], capture_output=True, text=True).stderr
    if "Duration:" not in o:
        return False, ["the file will not open"]
    if "1080x1920" not in o:
        why.append("not 1080x1920 - phones will letterbox it")
    if "Audio:" not in o:
        why.append("no sound track")
    caps = mp4[:-4] + "__caps.json"
    if not os.path.exists(caps):
        why.append("no caption file beside it, so the words cannot be read")
    else:
        text = " ".join(x[2] for x in json.load(open(caps)))
        name = re.sub(r"_\d+s\.mp4$", "", os.path.basename(mp4))
        miss = corrections_present(name, text)
        if miss:
            why.append(f"{len(miss)} correction(s) the plan asked for are NOT on screen: "
                       + "; ".join(repr(m[:44]) for m in miss[:3]))
    try:
        import kt_qc
        v, reasons = kt_qc.check(mp4)
        if v == "fail":
            why += list(reasons)
    except Exception as e:
        why.append(f"the quality gate could not run: {e}")
    why += cloud_sound_faults(mp4)
    return not why, why


# What only the cloud can judge: it LISTENS to the first and last seconds of the file.
# Text faults are not taken from it - the same live kt_qc re-judges those above.
SOUND = ("first word heard", "last word heard", "opening:", "no pause after the close")


def cloud_sound_faults(mp4):
    """12 Oct 2026: FIRED-FROM-HIS-OWN-COMPANY was a cloud FAIL ("first word heard is not
    'steve'") and this gate delivered it, because the verdict never came down with the
    file. (That one was whisper's name bias, fixed in edges.py - but a real cut opening
    would have walked into the folder the same way.) The verdict is matched to the exact
    file name, so an old verdict never judges a rebuilt clip."""
    try:
        v = json.load(open(os.path.expanduser("~/VSC/.verdicts.json")))
    except Exception:
        return []
    name = re.sub(r"_\d+s\.mp4$", "", os.path.basename(mp4))
    e = v.get(name) or {}
    if e.get("file") != os.path.basename(mp4) or e.get("verdict") != "fail":
        return []
    return [f"cloud listening: {w.strip('; ')}" for w in e.get("why", [])
            if any(s in w for s in SOUND)]


def main():
    os.makedirs(DEST, exist_ok=True)
    os.makedirs(HOLD, exist_ok=True)
    moved, held = [], []
    for mp4 in sorted(glob.glob(os.path.join(HOLD, "*.mp4"))):
        # STILL ARRIVING. A clip whose caption file has not landed yet is not a bad
        # clip, it is an unfinished download - judging it would file a good clip under
        # _needs_work and nothing would ever look at it again.
        if not os.path.exists(mp4[:-4] + "__caps.json"):
            print(f"  still arriving, left alone  {os.path.basename(mp4)}")
            continue
        ok, why = check(mp4)
        base = os.path.basename(mp4)
        dest = DEST if ok else BAD
        os.makedirs(dest, exist_ok=True)
        for g in (mp4, mp4[:-4] + "__caps.json"):
            if os.path.exists(g):
                os.replace(g, os.path.join(dest, os.path.basename(g)))
        if ok:
            moved.append(base)
            # a clip that is good now must not be shadowed by an old rejected copy
            old = os.path.join(BAD, base)
            if os.path.exists(old):
                os.remove(old)
            # ONE CUT PER CLIP IN THE FOLDER (15 Oct 2026). A re-cut arrives under a new
            # length (HEAVEN-IS-NOT-A-PLACE_21s -> _45s) and the old file stayed beside it,
            # so the folder held two versions of one clip and either could be submitted.
            # Older cuts - delivered or held back - go to the Trash (Kamay, 15 Oct: "always
            # delete stuff that is confirmed not needed"); emptying it stays his call.
            clip = re.sub(r"_\d+s\.mp4$", "", base)
            arch = os.path.expanduser("~/.Trash/VSC-replaced")
            for d in (DEST, BAD):
                for f in glob.glob(os.path.join(d, clip + "_*")):
                    fb = os.path.basename(f)
                    if re.fullmatch(re.escape(clip) + r"_\d+s(\.mp4|__caps\.json|__WHY\.txt)", fb) \
                            and not fb.startswith(base[:-4]):
                        try:
                            os.makedirs(arch, exist_ok=True)
                            os.replace(f, os.path.join(arch, fb))
                        except OSError:
                            # macOS may keep a background job out of the Trash; then the
                            # old cut waits in ~/VSC/.replaced (never pulled again: vsc_pull
                            # treats every file under ~/VSC outside Clips as handled)
                            rep = os.path.expanduser("~/VSC/.replaced")
                            os.makedirs(rep, exist_ok=True)
                            os.replace(f, os.path.join(rep, fb))
        else:
            held.append((base, why))
            open(os.path.join(BAD, base[:-4] + "__WHY.txt"), "w").write(
                base + "\n\n" + "\n".join("- " + w for w in why) + "\n")
    for b in moved:
        print(f"  DELIVERED  {b}")
    for b, why in held:
        print(f"  HELD BACK  {b}\n             " + "\n             ".join(why))
    print(f"\n{len(moved)} clip(s) in the VSC folder, {len(held)} held back"
          + (f" in {BAD}" if held else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
