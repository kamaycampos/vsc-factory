#!/usr/bin/env python3
"""Every real pause in a source, measured once, the way the renderer measures one.

    python cloud/pauses.py <source.mp4> <out.json>

13 Oct 2026, why_your_prayers_fail: 13 of 15 clips came back "no pause before the
open" or "no pause after the close". The planner chose its opening and closing words
from a transcript that cannot show silence, and the renderer then looked for a pause
that was not there. This is the missing map: the stretches of the episode that are
QUIET by vsc_v2_render.quiet_runs' rule - at least 35 dB under the speech around them
and in the bottom of the local range - lasting >= 0.15 s. autoplan marks them in the
transcript it hands the planner and refuses an open or close that is not on one.

Output: {"v": 3, "dur": seconds, "pauses": [[start, end], ...],
         "cuts": [[start, end, depth_db], ...]}  (cuts: see cut_points and bed_cuts)
"""
import json, os, subprocess, sys

import numpy as np

FF = os.path.expanduser("~/Kamay/bin/ffmpeg")
if not os.path.exists(FF):
    FF = "ffmpeg"
STEP = 0.01          # 10 ms frames, as quiet_runs
WIN = 2.6            # the window quiet_runs judges "the speech around it" over
MIN = 0.15           # a real pause (vsc_v2_render._longest)


def db_frames(src):
    raw = subprocess.run([FF, "-v", "error", "-i", src, "-vn", "-ar", "16000", "-ac", "1",
                          "-f", "s16le", "-"], capture_output=True, check=True).stdout
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    st = 160
    n = len(x) // st
    x = x[:n * st].reshape(n, st)
    return 20 * np.log10(np.sqrt((x ** 2).mean(axis=1) + 1e-9) + 1e-9)


def pause_map(src):
    db = db_frames(src)
    n, w = len(db), int(WIN / STEP)
    # quiet_runs' threshold, judged over a 2.6 s window around each frame (sampled every
    # 0.2 s and held - the percentiles move slowly and this keeps a 30-min file to seconds)
    hop = 20
    q = np.zeros(n, dtype=bool)
    for c in range(0, n, hop):
        a, b = max(0, c - w // 2), min(n, c + w // 2)
        lo, hi = np.percentile(db[a:b], 15), np.percentile(db[a:b], 90)
        thr = min(lo + (hi - lo) * 0.40, hi - 35.0)
        q[c:c + hop] = db[c:c + hop] <= thr
    out, k = [], 0
    while k < n:
        if q[k]:
            j = k
            while j < n and q[j]:
                j += 1
            if (j - k) * STEP >= MIN:
                out.append([round(k * STEP, 2), round(j * STEP, 2)])
            k = j
        else:
            k += 1
    cuts = cut_points(db)
    # a bed gap is added only where no measured cut already lies, so every v2 cut stays
    cuts += [r for r in bed_cuts(db) if not any(o[1] > r[0] and o[0] < r[1] for o in cuts)]
    return {"v": 3, "dur": round(n * STEP, 2), "pauses": out, "cuts": sorted(cuts)}


def cut_points(db):
    """Breath gaps a clip can be cut in, measured against the voice around them.

    15 Oct 2026, why_your_prayers_fail: Kevin talks almost without stopping, and the
    rule above found a pause at only 40 of 261 sentence ends - so the planner could
    place 8 clips in 27 minutes. Measured by hand, most sentence ends still carry a
    breath: 0.3-0.6 s that drops 40-50 dB under his voice. Cut there with an exact
    start_at / end_at and whisper hears a whole first and last word with nothing after
    (all 8 hand cuts that day, listened to on the source before they were built).
    A cut point: >= 0.15 s at 30 dB under the loud end of the voice within 1.3 s,
    dipping to 38 dB under - or >= 0.12 s of near-silence (55 dB under)."""
    n, out, k = len(db), [], 0
    hop, w = 20, int(1.3 / STEP)
    hi = np.empty(n)
    for c in range(0, n, hop):
        hi[c:c + hop] = np.percentile(db[max(0, c - w):min(n, c + w)], 90)
    q = db <= hi - 30
    while k < n:
        if q[k]:
            j = k
            while j < n and q[j]:
                j += 1
            depth = float((db[k:j] - hi[k:j]).min())
            L = (j - k) * STEP
            if (L >= 0.15 and depth <= -38) or (L >= 0.12 and depth <= -55):
                out.append([round(k * STEP, 2), round(j * STEP, 2), round(depth)])
            k = j
        else:
            k += 1
    return out


def bed_cuts(db):
    """Breath gaps UNDER A MUSIC BED, measured against the bed itself.

    29 Oct 2026, they_re_not_hiding: 6 cut points in 27 minutes, and autoplan turned
    20 of 21 good clips away ("not after a pause"). A bed runs under the whole episode:
    the quietest 5 % of it sits at 39 dB against 62-65 dB of voice (your_purpose_is_a:
    17.6 dB), so no gap can drop the 38 dB cut_points needs - 0 of its 248 sentence ends
    did. The gaps are there: the quietest 0.15 s of a sentence end sits a median 1.7 dB
    above the floor. Where the floor never drops 35 dB under the voice (5th vs 90th
    percentile within 8 s), a cut point is >= 0.15 s within 3 dB of that floor, touching
    it (1 dB), and 15 dB under the voice within 1.3 s. 93 of the 248 sentence ends get
    one; 12 % of these gaps sit inside a short whisper word, as 15 % of the v2 rule's did
    on your_purpose_is_a (whisper's times, not the gaps). Edge listening judges the file."""
    n, out, k = len(db), [], 0
    hop, w, fw = 20, int(1.3 / STEP), int(8.0 / STEP)
    hi, fl, top = np.empty(n), np.empty(n), np.empty(n)
    for c in range(0, n, hop):
        hi[c:c + hop] = np.percentile(db[max(0, c - w):min(n, c + w)], 90)
        s = db[max(0, c - fw):min(n, c + fw)]
        fl[c:c + hop], top[c:c + hop] = np.percentile(s, 5), np.percentile(s, 90)
    q = (top - fl < 35) & (db <= fl + 3) & (db <= hi - 15)
    while k < n:
        if q[k]:
            j = k
            while j < n and q[j]:
                j += 1
            if (j - k) * STEP >= 0.15 and (db[k:j] - fl[k:j]).min() <= 1.0:
                out.append([round(k * STEP, 2), round(j * STEP, 2), round(float((db[k:j] - hi[k:j]).min()))])
            k = j
        else:
            k += 1
    return out


if __name__ == "__main__":
    m = pause_map(sys.argv[1])
    json.dump(m, open(sys.argv[2], "w"))
    print(f"{len(m['pauses'])} pauses, {len(m['cuts'])} cut points over {m['dur']:.0f} s")
