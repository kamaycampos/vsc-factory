#!/usr/bin/env python3
"""ONE COMMAND for a new week of VSC clips.  python3 ~/Kamay/vsc_week.py

Everything that can be decided by a machine, in the order that survived Kamay's
review of weeks 1 and 2. What CANNOT be automated is step 2, and it is the step
that decides whether the clips are any good: a human reads the transcript and
names the exact sentence each clip OPENS and CLOSES on, plus its one-idea hook.
Six rounds of automatic edge-picking were rejected because every proxy measured
acoustics and none consulted meaning.

    1. Put the sources in ~/Desktop/VSC/Source  (Frame.io "Original", 1080p+)
    2. Add each clip to ~/Kamay/vsc_cuts.py CUTS:
         ("NAME", (region_from, region_to), "opening words", "closing words",
          "ONE IDEA HOOK")                      # or ["TWO", "LINES"]
    3. Run this. It does the rest and prints what it could not verify.

Per clip: find the exact in/out from those words -> read the words and build the
captions -> pin every caption to the sound by IDENTITY -> render -> check the
finished file. Nothing is believed because a call returned success; every stage is
read back off the artifact.
"""
import glob, json, os, re, subprocess, sys
sys.path.insert(0, os.path.expanduser("~/Kamay"))
import vsc_clip, vsc_pick, vsc_v2caps, vsc_v2_time, vsc_v2_render, vsc_v2_onscreen   # noqa: E402
from vsc_cuts import CUTS, END_OVERRIDE, VIS_OVERRIDE                                # noqa: E402

SRC = os.path.expanduser("~/Desktop/VSC/Source")
OUT = os.path.expanduser("~/Desktop/VSC/Clips")
WORK = os.path.expanduser("~/Desktop/VSC/.work")
FF = os.path.expanduser("~/Kamay/bin/ffmpeg")


def source_is_hd(src):
    """18 clips once went out blurry from 640x360 sources. Output size proves nothing.

    NEVER WAIT FOREVER ON A FILE. 29 Sept 2026: this call hung with no output and no
    CPU, and it looked like the pipeline was slow. It was not - Kamay's Desktop is
    synced to iCloud Drive, the 1.4GB source had been evicted to the cloud, and every
    read of it blocked while iCloud tried to fetch it back. Even `ls` on the folder
    hung for five minutes. A probe that can block forever turns a storage problem into
    a mystery, so it gets a timeout and says plainly what it thinks is wrong.
    """
    try:
        o = subprocess.run([FF, "-nostdin", "-i", src], capture_output=True,
                           text=True, timeout=120).stderr
    except subprocess.TimeoutExpired:
        raise SystemExit(
            f"cannot read {os.path.basename(src)} - 120s and no answer.\n"
            f"If this file lives under ~/Desktop or ~/Documents it is synced to iCloud "
            f"and has probably been evicted; reading it waits on a download that may "
            f"never finish. Keep sources outside iCloud, or build in the cloud.")
    m = re.search(r", (\d{3,5})x(\d{3,5})", o)
    return (int(m.group(2)) if m else 0), (int(m.group(1)) if m else 0)


def ensure_transcript(src, base):
    """The whole-file transcription and the readable transcript, built once.

    Two different things are needed and both were being made by hand, which is how
    week 2 hit a missing file: `<base>.json` (whole-file whisper JSON - what
    vsc_clip.segments reads to know who is speaking and where sentences fall) and
    TRANSCRIPT.txt, the timestamped read for CHOOSING the clips. Normal mode may be
    prompted - it is only the `-ml 1 -sow` timing pass a prompt would wreck.
    """
    import vsc_edges, vsc_words
    # NO WHOLE-FILE TRANSCRIPTION. It cost a full extra pass over the audio and its
    # only consumer was vsc_clip.segments(), which now derives sentence boundaries
    # from the chunked word pass instead. Halves prep.
    j = os.path.join(WORK, base + ".json")
    if False:
        wav = "/tmp/vsc_whole.wav"
        subprocess.run([FF, "-y", "-loglevel", "error", "-i", src, "-ar", "16000", "-ac", "1",
                        "-c:a", "pcm_s16le", wav], check=True)
        print("  transcribing the whole file (once)...", flush=True)
        subprocess.run([os.path.expanduser("~/Kamay/whisper.cpp/build/bin/whisper-cli"),
                        "-m", os.path.expanduser("~/Kamay/whisper.cpp/models/ggml-small.en.bin"),
                        "-f", wav, "-bs", "5", "--prompt", vsc_v2caps.PUNCT,
                        "-oj", "-of", os.path.join(WORK, base)], capture_output=True)
    dur = vsc_edges.analyse(src, base)["dur"]
    # WHERE KEVIN IS, shot by shot - the renderer needs it to keep him in a 9:16
    # frame. vsc_frame writes it next to the source; the renderer reads it from
    # .work, and nothing built it, which is the second missing file this week.
    fj = os.path.join(WORK, base + ".frame.json")
    if not os.path.exists(fj):
        print("  finding Kevin shot by shot (a few minutes, once)...", flush=True)
        subprocess.run(["python3", os.path.expanduser("~/Kamay/vsc_frame.py"), src], check=True)
        beside = os.path.splitext(src)[0] + ".frame.json"
        if os.path.exists(beside):
            os.replace(beside, fj)
    words = vsc_words.build(src, base, dur)
    out = os.path.join(WORK, "TRANSCRIPT_" + base[:40] + ".txt")
    if not os.path.exists(out):
        line, start, lines = [], None, []
        for x in words:
            if start is None:
                start = x["a"]
            line.append(x["t"])
            if x["t"].rstrip().endswith((".", "!", "?")) and len(" ".join(line)) > 90:
                lines.append(f"[{int(start//60):02d}:{start%60:05.2f}] " + " ".join(line))
                line, start = [], None
        if line:
            lines.append(f"[{int(start//60):02d}:{start%60:05.2f}] " + " ".join(line))
        open(out, "w").write("\n".join(lines))
        print(f"  transcript for choosing clips: {out}", flush=True)
    return dur


def check_only():
    """Can every clip's opening and closing words actually be FOUND? Ask the locator.

    27 Sept: a pre-flight that searched the whole-file word cache passed all 18 clips,
    and then 4 of them failed to locate during the run. The locator does not use that
    cache - it transcribes its own short window, and the two passes disagree on
    individual words. A check is only worth anything if it asks the same code that
    will do the work. Run this before a build: it is slow (one local read per clip)
    and it is the truth.
    """
    for prefix, clips in CUTS.items():
        hit = glob.glob(os.path.join(SRC, prefix + "*.mp4"))
        if not hit:
            continue
        src = hit[0]
        base = os.path.splitext(os.path.basename(src))[0]
        dur = ensure_transcript(src, base)
        S = vsc_clip.segments(base)
        print(f"\n##### {prefix}", flush=True)
        for name, region, first, last, hook in clips:
            got, why = vsc_pick.locate(src, base, S, region, first, last,
                                       re.sub(r"\W+", "", name)[:18], dur=dur)
            if got:
                print(f"  ok  {name:28} {got[0]:8.2f} - {got[1]:8.2f}  ({got[1]-got[0]:5.1f}s)", flush=True)
            else:
                print(f"  !!  {name:28} {why}", flush=True)
    print("CHECKDONE")


def _match_prefix(plan, clip):
    """Which source this plan's clips are cut from: the prefix already in CUTS whose
    video is in the folder, matched on the plan key or on the source file it names."""
    want = (plan.get("source") or plan.get("key") or "").lower().replace("_", " ")
    for pre in CUTS:
        if pre.lower() in want or want.split()[0:1] and want.split()[0] in pre.lower():
            if glob.glob(os.path.join(SRC, pre + "*.mp4")):
                return pre
    for pre in CUTS:                       # one source in the folder and one plan: it
        if glob.glob(os.path.join(SRC, pre + "*.mp4")):   # is that one
            return pre
    return None


def main(only=None):
    os.makedirs(WORK, exist_ok=True); os.makedirs(OUT, exist_ok=True)
    abp = os.path.join(WORK, "v2_ab.json")
    ab = json.load(open(abp)) if os.path.exists(abp) else {}
    fixes = json.load(open(os.path.join(WORK, "v2_fixes.json"))) if os.path.exists(
        os.path.join(WORK, "v2_fixes.json")) else {}
    # every clip's corrections, read from the plans themselves
    plan_fixes = {}
    # WHERE THE PLANS ARE, FROM THE SERVER'S POINT OF VIEW. setup.sh copies this file
    # into ~/Kamay so the pipeline runs unchanged, which means __file__ is no longer
    # inside the checkout - looking for "../plans" found ~/plans, which does not exist,
    # so every caption correction was silently skipped and the clips shipped uncorrected
    # while everything reported success. The checkout is named explicitly.
    _plandirs = [os.environ.get("GITHUB_WORKSPACE", "") + "/plans",
                 os.environ.get("VSC_PLANS", ""),
                 os.path.expanduser("~/vsc-factory/plans"),
                 os.path.expanduser("~/Desktop/VSC/vsc-machine/plans"),
                 os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "plans")]
    _plandirs = [d for d in _plandirs if d and os.path.isdir(d)]
    # A CLIP IN THE PLAN IS A CLIP THAT GETS BUILT. Until 30 Sept the plan carried only
    # the corrections and the cuts lived in vsc_cuts.py, so two clips written into the
    # plan were counted as missing by the sharder and the verifier, sent to a server,
    # and then silently skipped by the builder: "0 made, 0 could not be located".
    # Nothing was wrong with them; nothing was looking for them. Plan entries are merged
    # into CUTS here, and vsc_cuts.py stays the place a cut can be overridden by hand.
    for _f in sorted(sum([glob.glob(os.path.join(_d, "*.json")) for _d in _plandirs], [])):
        try:
            _p = json.load(open(_f))
            _known = {n for cl in CUTS.values() for n, *_r in cl}
            for _c in _p.get("clips", []):
                if _c.get("fixes"):
                    plan_fixes[_c["name"]] = _c["fixes"]
                if not _c.get("open") or not _c.get("close"):
                    continue
                # THE PLAN WINS. 30 Sept 2026: ten clips were re-cut in the plan to end
                # where the teaching lands, the build ran, and every one of them came
                # out on its OLD cut - "MORE-PROBLEMS-THAN-YOU 27.49 - 130.19" in the
                # log, the 102-second version, because a name already in vsc_cuts.py
                # was left alone. The plan is what is read, reviewed and corrected, so
                # a plan entry REPLACES the hand-written cut of the same name rather
                # than being skipped by it.
                if _c["name"] in _known:
                    for _pre2, _cl2 in CUTS.items():
                        _cl2[:] = [t for t in _cl2 if t[0] != _c["name"]]
                _pre = _p.get("prefix") or _match_prefix(_p, _c)
                if not _pre:
                    print(f"  !! {_c['name']} is in a plan with no source to cut it from",
                          flush=True)
                    continue
                CUTS.setdefault(_pre, []).append(
                    (_c["name"], tuple(_c["region"]), _c["open"], _c["close"],
                     _c.get("hook") or ["", ""]))
                print(f"  + {_c['name']} taken from the plan", flush=True)
        except Exception as _e:
            print(f"  !! could not read {os.path.basename(_f)}: {_e}", flush=True)
    done, failed = [], []
    for prefix, clips in CUTS.items():
        hit = glob.glob(os.path.join(SRC, prefix + "*.mp4"))
        if not hit:
            continue                                  # that week's source is gone; skip quietly
        src = hit[0]
        base = os.path.splitext(os.path.basename(src))[0]
        h, w = source_is_hd(src)
        if h < 1000:
            print(f"!! {prefix}: source is only {w}x{h}. Download the Frame.io ORIGINAL "
                  f"- a small source cannot be rescued by the render.", flush=True)
            continue
        print(f"\n##### {prefix}   {w}x{h}", flush=True)
        dur = ensure_transcript(src, base)
        S = vsc_clip.segments(base)
        for name, region, first, last, hook in clips:
            if only and name not in only:
                continue
            if glob.glob(os.path.join(OUT, name + "_*.mp4")) and name in ab:
                print(f"  -- {name}: already made", flush=True); continue
            tag = re.sub(r"\W+", "", name)[:18]
            got, why = vsc_pick.locate(src, base, S, region, first, last, tag, dur=dur)
            if not got:
                print(f"  !! {name}: {why} - check the words against the transcript", flush=True)
                failed.append((name, why)); continue
            a, b = got
            if name in END_OVERRIDE:
                b = END_OVERRIDE[name]
            # WHERE HE FINISHES THE CLOSING WORD, as the locator measured it. 1 Oct 2026:
            # YOUR-BIGGEST-DISASTER was located 0.00-27.90 and MORE-PROBLEMS-THAN-YOU
            # 94.70-133.59 - both right - and both shipped short ("It doesn't end",
            # "not people without"), because the renderer trimmed to the caption pass's
            # idea of the close, which drifts up to 2.8s at the tail, and then heard
            # Kevin still saying the close as "speech after the close".
            said = vsc_pick.LAST_SPEECH_END
            said = None if said is None else round(min(said, b), 3)
            close_words = [(round(x["a"] - a, 3), round(x["b"] - a, 3), x["t"])
                           for x in vsc_pick.LAST_WORDS if x["b"] <= b + 0.05]
            ab[name] = {"a": a, "b": b, "src": os.path.basename(src),
                        "vis_end": VIS_OVERRIDE.get(name), "speech_end": said,
                        "close_words": close_words[-20:],
                        "next_word": vsc_pick.LAST_NEXT_WORD}
            json.dump(ab, open(abp, "w"), indent=1)
            print(f"  {name:30} {a:8.2f} - {b:8.2f}  ({b - a:5.1f}s)", flush=True)
            # CORRECTIONS COME WITH THE PLAN. 29 Sept: the cloud rebuilt this batch
            # without the caption fixes, because they lived in a file on the Mac, and
            # every clip regressed - "best settle list", "Stephen Jobs", "Foul
            # bankruptcy", a line of TV footage spliced into a story. A correction that
            # is not versioned beside the plan is a correction that gets lost.
            clip_fixes = list(fixes.get(name, [])) + plan_fixes.get(name, [])
            print(f"      {len(clip_fixes)} caption correction(s) for this clip", flush=True)
            vsc_v2caps.build(name, a, b, src, last, clip_fixes)
            vsc_v2_time.retime(name, src, a, b)
            vsc_v2_render.HOOKS[name] = hook
            vsc_v2_render.OUT = OUT
            vsc_v2_render.main([name])
            done.append(name)
    print("\n=== READ THE FINISHED FILES ===", flush=True)
    for name in done:
        f = glob.glob(os.path.join(OUT, name + "_*.mp4"))
        if not f:
            print(f"  !! {name}: nothing was written"); failed.append((name, "no file")); continue
        r = vsc_v2_onscreen.check(f[0])
        caps = [tuple(x) for x in json.load(open(f[0][:-4] + "__caps.json"))]
        ov = sum(1 for i in range(len(caps) - 1) if caps[i][1] > caps[i + 1][0] + 0.001)
        hit, miss, _m = r if r else (0, 0, [])
        flag = "" if (hit >= 10 and not ov) else "   <-- LOOK"
        print(f"  {name:30} {hit:2d}/{hit + miss:2d} moments right, {ov} overlaps{flag}", flush=True)
    print(f"\n{len(done)} made, {len(failed)} could not be located: {failed}")
    print("STILL YOURS TO DO: read every caption line, and watch the first 3 seconds "
          "and the last 2 of each clip.")
    print("VSCWEEKDONE")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--check"]:
        check_only()
    else:
        main(sys.argv[1:] or None)
