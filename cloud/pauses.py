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

Output: {"v": 1, "dur": seconds, "pauses": [[start, end], ...]}.
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
    return {"v": 1, "dur": round(n * STEP, 2), "pauses": out}


if __name__ == "__main__":
    m = pause_map(sys.argv[1])
    json.dump(m, open(sys.argv[2], "w"))
    print(f"{len(m['pauses'])} pauses over {m['dur']:.0f} s")
