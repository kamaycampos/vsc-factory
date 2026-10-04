#!/usr/bin/env python3
"""Render one VSC clip: per-shot reframing + style B hook + word-synced captions.

THE REFRAME. Kamay, 6 Sept: "cut right when the frame ends and position the next
frame and make it look as continuous as possible." That is the design. The crop
changes ONLY on a cut that already exists in the source, so the viewer's eye is
already accepting a jump and the reposition rides along invisibly. Inside a shot
the camera is locked off, so a crop that followed the face would wobble on a
still picture - which is the thing that reads as amateur.

Measured on video 1: Kevin's face moves across 1127px of the 3840 frame while
the crop window is only 1140px wide. A single fixed crop puts him OUT of frame
at the extremes. This is not a polish step.

STYLE B (chosen 6 Sept over Montserrat Black): DIN Condensed Bold, hook in the
upper third, last line yellow, gone at 3s. Condensed fits 138px inside the 780px
safe width where Montserrat fits 76px - nearly double, and the high position
leaves his face clear.
"""
import json, os, shutil, subprocess, sys
from PIL import ImageFont

HOME   = os.path.expanduser("~/Kamay")
FFMPEG = os.path.join(HOME, "bin/ffmpeg")
FONT   = "/System/Library/Fonts/Supplemental/DIN Condensed Bold.ttf"
W, H   = 1080, 1920
SAFE_W = 780            # phones crop ~10% off each side of a 9:16 clip
YELLOW = "#FFE500"
HOOK_SECS = 4.5          # 16 Sept 2026, Kamay: hooks "fade away too fast, an average viewer
                         # cannot keep up". 3.0s left ~2.7s at full opacity - not enough to
                         # read a two-line hook while watching a face. Applies to KT, Yaren, VSC.
HOOK_Y    = 165         # upper third - style B
CAP_Y     = 1450        # low enough to clear the hook, high enough to clear platform UI
CAP_SIZE  = 104      # one word at a time can carry far more size than a phrase
CAP_FLOOR = 62       # long words shrink to fit the safe width, but never below this
SHADOW = ":shadowx=0:shadowy=7:shadowcolor=black@0.80:borderw=3:bordercolor=black@0.45"
BAND_LIMIT   = 1.00     # band ONLY when the face is wider than the whole frame
BAND_TARGET  = 0.95     # when we must band, how much of the widened crop the face fills
WIDE_BELOW   = 0.45     # below this he is small in frame - crop in instead
CROPIN_TARGET= 0.58     # face share after cropping into a wide shot
_UNUSED      = 0.50     # face share of frame width. 0.72 and 0.55 both clipped his crown.
CW_MAX = 2100
MAX_UPSCALE = 1.45      # how far a wide shot may be blown up before it softens
FACE_Y = 0.45           # face centre height - leaves headroom above the head


def esc(t):
    return (t.replace("\\", r"\\\\").replace(":", r"\:").replace("'", r"’")
             .replace("%", r"\%"))


def fit(lines, size, font=FONT, floor=40):
    while size > floor:
        f = ImageFont.truetype(font, size)
        if all((f.getbbox(l)[2] - f.getbbox(l)[0]) <= SAFE_W for l in lines):
            return size
        size -= 2
    return floor


def source_size(src):
    out = subprocess.run([FFMPEG, "-i", src], capture_output=True, text=True).stderr
    for line in out.splitlines():
        if "Video:" in line:
            for tok in line.split(","):
                tok = tok.strip().split(" ")[0]
                if "x" in tok:
                    a, _, b = tok.partition("x")
                    if a.isdigit() and b.isdigit():
                        return int(a), int(b)
    raise SystemExit("cannot read size")


def crop_for(shot, sw, sh):
    """Full bleed FIRST. Bands only when his face physically cannot fit.

    6 Sept, Kamay: "it is not to my liking to be honest. i want these videos to
    be of the highest quality." He was right and the measurement showed why -
    the old face-share target put blurred bands on 93% of the runtime. At pure
    full bleed his face fills 0.68 of the frame at the median, which is simply a
    good close-up. Bands are only actually FORCED when the face is wider than
    the whole 9:16 window, and that is 2.9% of this video.

    Three cases now:
      wide shot   -> crop IN to a true 9:16 window and scale up. No bands.
      normal      -> pure full bleed. No bands.
      extreme CU  -> widen; bands, because there is no width left to give.
    """
    cw_full = int(round(sh * 9 / 16)) // 2 * 2
    face_px = shot["fw"] * sw
    share = face_px / cw_full

    if share > BAND_LIMIT:                       # face wider than the frame - must back off
        cw = int(min(face_px / BAND_TARGET, CW_MAX, sw)) // 2 * 2
        x = max(0, min(int(round(shot["cx"] * sw - cw / 2)), sw - cw)) // 2 * 2
        return cw, sh, x, 0, True

    if share < WIDE_BELOW:                       # he is small in frame - crop in, still no bands
        cw = int(max(face_px / CROPIN_TARGET, cw_full / MAX_UPSCALE)) // 2 * 2
        ch = int(round(cw * 16 / 9)) // 2 * 2
        if ch > sh or cw > cw_full:
            cw, ch = cw_full, sh
        x = max(0, min(int(round(shot["cx"] * sw - cw / 2)), sw - cw)) // 2 * 2
        y = max(0, min(int(round(shot["cy"] * sh - ch * FACE_Y)), sh - ch)) // 2 * 2
        return cw, ch, x, y, False

    ch = sh                                      # pure full bleed
    x = max(0, min(int(round(shot["cx"] * sw - cw_full / 2)), sw - cw_full)) // 2 * 2
    return cw_full, ch, x, 0, False


def shots_in(segments, t0, t1):
    out = []
    for s in segments:
        a, b = max(s["start"], t0), min(s["end"], t1)
        if b - a >= 0.20:
            out.append({**s, "start": a, "end": b})
    if not out:                                   # clip sits inside one shot
        s = min(segments, key=lambda s: abs(s["start"] - t0))
        return [{**s, "start": t0, "end": t1}]
    # A sub-second fragment at either end would flash a different crop for a few
    # frames, which is exactly the jump the per-shot design exists to avoid.
    MIN = 0.6
    merged = [out[0]]
    for s in out[1:]:
        if s["end"] - s["start"] < MIN:
            merged[-1]["end"] = s["end"]          # absorb into the shot before it
        else:
            merged.append(s)
    while len(merged) > 1 and merged[0]["end"] - merged[0]["start"] < MIN:
        merged[1]["start"] = merged[0]["start"]; merged.pop(0)
    return merged


def apply_overrides(shots, t0, ovs):
    """Carve per-clip corrections into the shot list. Times in `ovs` are CLIP-relative.

    18 Sept, from the Frame.io review. Two framings the automatic crop got wrong:
      PAPER-TIGER 0:32 "can you re-crop so his face isn't cut off?" - the crop
        switched a second BEFORE the real cut, then Kevin leans ~1000px across a
        1140px window. {"cx"} fixes the early switch; {"pan"} follows his face.
      WHY-WAIT-LAUGH-NOW 0:07 "crop out so we can see the whole words" - a title
        card was cropped like a face. {"fit"} shows the full frame width.
    """
    if not ovs:
        return shots
    cuts = sorted({t0 + o["t0"] for o in ovs} | {t0 + o["t1"] for o in ovs})
    out = []
    for s in shots:
        pts = [s["start"]] + [c for c in cuts if s["start"] < c < s["end"]] + [s["end"]]
        for p, q in zip(pts, pts[1:]):
            if q - p < 0.02:
                continue
            seg = dict(s); seg["start"], seg["end"] = p, q
            mid = (p + q) / 2 - t0
            for o in ovs:
                if o["t0"] <= mid < o["t1"]:
                    seg.update({k: v for k, v in o.items() if k not in ("t0", "t1")})
            out.append(seg)
    return out


def _pan_expr(keys, sw, cw):
    """Piecewise-linear crop x over segment-local time t, clamped inside the frame."""
    px = [(t, max(0, min(sw - cw, cx * sw - cw / 2))) for t, cx in keys]
    expr = f"{px[-1][1]:.1f}"
    for (ta, xa), (tb, xb) in reversed(list(zip(px, px[1:]))):
        expr = f"if(lt(t,{tb:.3f}),{xa:.1f}+({xb - xa:.1f})*(t-{ta:.3f})/{tb - ta:.3f},{expr})"
    return f"if(lt(t,{px[0][0]:.3f}),{px[0][1]:.1f},{expr})"


def build(src, framejson, t0, t1, hook, words, out, speech_end=None, vis_end=None, overrides=None,
          fade_out_by=None, fade_in=0.0):
    sw, sh = source_size(src)
    segs = json.load(open(framejson))["segments"]
    shots = apply_overrides(shots_in(segs, t0, t1), t0, overrides)
    parts, labels = [], []
    for i, s in enumerate(shots):
        trim = f"[0:v]trim=start={s['start']:.3f}:end={s['end']:.3f},setpts=PTS-STARTPTS,"
        if s.get("freeze_at") is not None:
            # hold ONE clean frame of Kevin over a card sliver (see card_spans' caller)
            cw, ch, x, y, _b = crop_for(s, sw, sh)
            fz = s["freeze_at"]
            parts.append(f"[0:v]trim=start={fz:.3f}:end={fz + 0.04:.3f},setpts=PTS-STARTPTS,"
                         f"crop={cw}:{ch}:{x}:{y},scale={W}:{H}:flags=lanczos,setsar=1,fps=30,"
                         f"tpad=stop_mode=clone:stop_duration={s['end'] - s['start']:.3f},"
                         f"trim=duration={s['end'] - s['start']:.3f}[v{i}];")
            labels.append(f"[v{i}]"); continue
        if s.get("lift"):
            # THE EPISODE FADES IN FROM BLACK while Kevin is already speaking (YOUR-
            # BIGGEST-DISASTER opens on the episode's first words). Starting later
            # would cut "Most"; the picture is lifted to full level instead.
            # the SAME window as the normal path (crop_for): a different crop here made the
            # picture jump in framing and level the moment the lift ended (3 Oct)
            g = s["lift"]
            cw, ch, x, y, _b = crop_for(s, sw, sh)
            parts.append(trim + f"crop={cw}:{ch}:{x}:{y},"
                         f"scale={W}:{H}:flags=lanczos,format=yuv420p,"
                         # video black is 16, not 0: lift ABOVE black, or black turns grey
                         f"geq=lum='clip(16+(lum(X,Y)-16)*({g}),16,235)':cb='clip(128+(cb(X,Y)-128)*({g}),16,240)'"
                         f":cr='clip(128+(cr(X,Y)-128)*({g}),16,240)',setsar=1,fps=30[v{i}];")
            labels.append(f"[v{i}]"); continue
        if s.get("fit"):
            # fit_w: show only the central band that holds the text, so it reads larger
            fw_ = int(s.get("fit_w", sw)) // 2 * 2
            pre = f"crop={fw_}:{sh}:{(sw - fw_) // 2}:0," if fw_ < sw else ""
            parts.append(trim + pre + f"scale={W}:-2:flags=lanczos,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=black,"
                         f"setsar=1,fps=30[v{i}];")
            labels.append(f"[v{i}]"); continue
        if s.get("pan"):
            cwp = int(round(sh * 9 / 16)) // 2 * 2
            off = s["start"] - t0
            keys = [(tt - off, cx) for tt, cx in s["pan"]]
            parts.append(trim + f"crop={cwp}:{sh}:'{_pan_expr(keys, sw, cwp)}':0,"
                         f"scale={W}:{H}:flags=lanczos,setsar=1,fps=30[v{i}];")
            labels.append(f"[v{i}]"); continue
        cw, ch, x, y, blur = crop_for(s, sw, sh)
        head = (f"[0:v]trim=start={s['start']:.3f}:end={s['end']:.3f},setpts=PTS-STARTPTS,"
                f"crop={cw}:{ch}:{x}:{y}")
        if blur:
            parts.append(
                head + f",split=2[bg{i}][fg{i}];"
                f"[bg{i}]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
                f"boxblur=40:2,eq=brightness=-0.14[bb{i}];"
                f"[fg{i}]scale={W}:-2[ff{i}];"
                f"[bb{i}][ff{i}]overlay=(W-w)/2:(H-h)/2,setsar=1,fps=30[v{i}];")
        else:
            parts.append(head + f",scale={W}:{H}:flags=lanczos,setsar=1,fps=30[v{i}];")
        labels.append(f"[v{i}]")
    graph = "".join(parts) + "".join(labels) + f"concat=n={len(shots)}:v=1:a=0[vcc];"
    _head = len(graph)        # everything after this works on the 9:16 picture (see the render below)
    # 12 Sept, Kamay: "when kevin is done butttt there is another scene coming and
    # you can see that". Every check I had was audio - a shot change at the tail is
    # invisible to all of them. If the source cuts to a new scene inside the last
    # moment of the clip, freeze on the LAST FRAME OF HIS SHOT and let the audio
    # finish over it. The viewer never sees the next scene.
    if vis_end is not None and vis_end < (t1 - t0) - 0.05:
        graph += (f"[vcc]trim=start=0:end={vis_end:.3f},setpts=PTS-STARTPTS,"
                  f"tpad=stop_mode=clone:stop_duration={(t1 - t0) - vis_end + 0.10:.3f}[vc];")
    else:
        graph += "[vcc]null[vc];"

    draws = []
    hl = [l for l in hook if l.strip()][:3]
    hs = fit([l.upper() for l in hl], 150)
    step = int(hs * 1.20)
    for i, l in enumerate(hl):
        col = YELLOW if i == len(hl) - 1 and len(hl) > 1 else "white"
        draws.append(f"drawtext=fontfile='{FONT}':text='{esc(l.upper())}':fontsize={hs}"
                     f":fontcolor={col}{SHADOW}:x=(w-tw)/2:y={HOOK_Y + i*step}"
                     f":enable='lt(t,{HOOK_SECS})'")
    # 10 Sept, Kamay: "sometimes the captions change in size like first its
    # smaller and as the video goes it becomes bigger." That was each burst being
    # sized on its own. ONE size per clip, fitted to the longest burst - the
    # brief asks for captions to be consistent, and shifting type reads as a bug.
    ws = fit([w_["text"].upper() for w_ in words] or [""], CAP_SIZE, floor=CAP_FLOOR)
    for w_ in words:
        draws.append(f"drawtext=fontfile='{FONT}':text='{esc(w_['text'].upper())}':fontsize={ws}"
                     f":fontcolor=white{SHADOW}:x=(w-tw)/2:y={CAP_Y}"
                     f":enable='gte(t,{w_['a']:.3f})*lt(t,{w_['b']:.3f})'")
    # 10 Sept, Kamay: "so many of the videos still end when kevin's mouth is
    # still open or you can tell he is about to say something." The WORDS end
    # correctly - verified by transcribing the rendered files - but the picture
    # stops the instant he finishes, freezing him mid-expression. So hold the
    # last frame briefly and fade it out. The clip lands instead of stopping.
    # The fade must begin AFTER his last word, not a fixed distance from the end
    # of the trim. 10 Sept, Kamay: "as it is fading kevin is still talking."
    _d = t1 - t0
    _spend = _d if speech_end is None else min(max(speech_end, 0.0), _d)
    _hold = 0.55
    _tot = _d + _hold
    _vstart = min(_spend + 0.18, _tot - 0.40)
    _outro = (f"tpad=stop_mode=clone:stop_duration={_hold},"
              f"fade=t=out:st={_vstart:.3f}:d={max(0.35, _tot - _vstart):.3f}")
    graph += ("[vc]" + ",".join(draws) + f",{_outro}[vo];") if draws else f"[vc]{_outro}[vo];"
    # A clip that has to end inside unbroken speech (some answers are edited with
    # no pause at all - 146s straight in "Every Millionaire") would otherwise stop
    # dead on a live waveform. It still ends on a COMPLETE sentence; the fade just
    # stops it sounding chopped.
    # Anchored to where he actually STOPS, not to the end of the trim - those
    # differ by the tail, and when the tail was short the fade ate his last word.
    _astart = min(_spend + 0.08, _tot - 0.30)
    _afade = f"afade=t=out:st={_astart:.3f}:d={max(0.30, _tot - _astart):.3f}"
    # NO PAUSE TO END IN (2 Oct 2026): Kevin runs the close straight into his next
    # sentence. The sound is faded to nothing BY the cut, over 0.15s, so the clip
    # neither stops dead on a live waveform nor lets the next word start.
    if fade_out_by is not None:
        _fe = min(max(fade_out_by, 0.2), _d)
        _afade = f"afade=t=out:st={_fe - 0.15:.3f}:d=0.15"
    if fade_in:
        _afade = f"afade=t=in:st=0:d={fade_in:.3f}," + _afade
    graph += (f"[0:a]atrim=start={t0:.3f}:end={t1:.3f},asetpts=PTS-STARTPTS,"
              f"apad=pad_dur={_hold},{_afade}[ao]")

    # SEEK TO THE CLIP, DO NOT DECODE THE WHOLE FILE. Every shot in the graph is a
    # separate trim branch off the same decoded input, so ffmpeg buffers frames for all
    # of them at once - on an 18-minute source that is gigabytes of held frames, and on
    # 30 Sept 2026 it killed the runner VM outright on every clip over a minute:
    # "the runner has received a shutdown signal" at six minutes, three attempts each,
    # on THE-450-MILLION-BREAKUP, MORE-PROBLEMS-THAN-YOU and BANNED-FOR-LIFE.
    # -ss before -i seeks instead of decoding, and -copyts keeps the timestamps
    # ABSOLUTE so every trim value in the graph still means what it says.
    # ONE THREAD PER FILTER. ffmpeg spawns a thread per core per filter and each holds
    # its own frame buffers, so on a 4-core runner a graph with a hundred filters in it
    # multiplies its memory by four. That is what kept killing the VM on the clips with
    # the most shots in them - THE-450-MILLION-BREAKUP is only 60 seconds long and died
    # as reliably as the 128-second one, which is about graph size, not duration.
    base = ["-threads", "2", "-filter_complex_threads", "1",
            "-filter_complex", graph, "-map", "[vo]", "-map", "[ao]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "19",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k",
            "-movflags", "+faststart", out, "-loglevel", "error"]
    seek = max(0.0, t0 - 4.0)
    # EACH SHOT ITS OWN PROCESS, THEN ONE PASS OVER THE 9:16 PICTURE. 3 Oct 2026, run 42:
    # NO-SUCH-THING-AS-ADVERSITY (70.8 s) and BANNED-FOR-LIFE (66.5 s) were killed by
    # the runner mid-render on all three attempts - every shot is a trim branch off ONE
    # decoded 4K stream, and the frames of the shots not yet reached queue up in memory,
    # which is what has held every clip under ~60 s. Rendered one shot per ffmpeg, each
    # holds only its own 4K frames; the join, captions and fades then run on 1080x1920.
    if len(shots) > 1 and os.environ.get("VSC_ONE_PASS") != "1":
        import re as _re, tempfile as _tf
        tmp = _tf.mkdtemp(prefix="vsc_shots_")
        segs_ok = True
        for i, p in enumerate(parts):
            starts = [float(x) for x in _re.findall(r"trim=start=([0-9.]+)", p)]
            ss = max(0.0, min(starts) - 4.0) if starts else seek
            seg = os.path.join(tmp, f"s{i:03d}.mkv")
            rr = subprocess.run([FFMPEG, "-y", "-copyts", "-ss", f"{ss:.3f}", "-i", src,
                                 "-threads", "2", "-filter_complex_threads", "1",
                                 "-filter_complex", p.rstrip(";"), "-map", f"[v{i}]",
                                 "-c:v", "libx264", "-preset", "fast", "-crf", "12",
                                 "-pix_fmt", "yuv420p", seg, "-loglevel", "error"])
            if rr.returncode or not os.path.exists(seg):
                segs_ok = False
                break
        if segs_ok:
            g2 = "".join(f"[{i + 1}:v]" for i in range(len(parts))) + \
                 f"concat=n={len(parts)}:v=1:a=0[vcc];" + graph[_head:]
            ins = [FFMPEG, "-y", "-copyts", "-ss", f"{seek:.3f}", "-i", src]
            for i in range(len(parts)):
                ins += ["-i", os.path.join(tmp, f"s{i:03d}.mkv")]
            b2 = list(base)
            b2[b2.index("-filter_complex") + 1] = g2
            r2 = subprocess.run(ins + b2)
            shutil.rmtree(tmp, ignore_errors=True)
            if r2.returncode == 0:
                return shots
            print(f"      shot-by-shot render failed ({r2.returncode}); one pass", flush=True)
        else:
            shutil.rmtree(tmp, ignore_errors=True)
            print("      a shot failed to render on its own; one pass", flush=True)
    cmd = [FFMPEG, "-y", "-copyts", "-ss", f"{seek:.3f}", "-i", src] + base
    r = subprocess.run(cmd)
    if r.returncode:
        # never let the seek be the reason a clip does not exist
        print(f"      seeking render failed ({r.returncode}); reading from the top",
              flush=True)
        subprocess.run([FFMPEG, "-y", "-i", src] + base, check=True)
    return shots
