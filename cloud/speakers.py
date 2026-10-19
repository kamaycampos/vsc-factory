#!/usr/bin/env python3
"""Who is talking, stretch by stretch: Kevin or the guest.

    python cloud/speakers.py map <source.mp4> <words.json> <out.json>
    python cloud/speakers.py ref <out.npy> <kevin-only clip> [...]

18 Oct 2026, Naomi (GIN), for the interview episodes: "we want clips that focus on
Kevin talking (it can be talking with John but we don't want clips focusing only on
John)". The transcript the planner reads could not show who speaks - every word looked
like Kevin's. This is that missing column. prep publishes `speakers-<key>.json`;
autoplan tags the guest's lines in the transcript and refuses a clip where Kevin
carries less than KEVIN_MIN of the speech.

How: every stretch of speech (words without a 0.35 s gap, at most 6 s) gets a
voiceprint (vsc_frame._Voices, the numpy Resemblyzer encoder speaker_turns already
uses). Two voices are found by 2-means seeded with Kevin's own voiceprint
(assets/kevin_voice.npy, made with `ref` from 13 delivered clips where only Kevin
speaks) and the stretch least like him. A stretch too short to judge is "?", and the
words between take their neighbours' voice. An episode where the second voice holds
under 5 % of the speech is solo: everything is Kevin.

Output: {"v": 1, "guest_share": f, "spans": [[a, b, "K"|"G"|"?"], ...]} (source s).
"""
import json, os, subprocess, sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.join(os.path.dirname(HERE), "assets", "kevin_voice.npy")
FF = os.path.expanduser("~/Kamay/bin/ffmpeg")
if not os.path.exists(FF):
    FF = "ffmpeg"
SR = 16000
GAP = 0.35           # a new stretch after a pause this long - turns change in pauses
LONG = 6.0           # ... or once a stretch is this long
JUDGE = 1.0          # under this much sound a voiceprint is a guess
MARGIN = 0.03        # a stretch nearer neither voice by this much is "?"
SOLO = 0.05          # second voice under this share of the speech = a solo episode
ISLAND = 3.0         # a shorter run between two runs of the other voice is a misread
APART = 0.05         # the two voices must differ by this much in likeness to Kevin's reference


def trusted(m):
    """Can this map tell Kevin from the guest? (19 Oct 2026, Hollywood Insider: Kevin and
    John Denney on the same mics in one room came out 0.83 / 0.82 against Kevin's studio
    voice - one man to the encoder. John's own lines matched Kevin's in-room voice at
    0.86-0.92, Kevin's 0.91-0.93, and the map called Kevin's 12-minute solo opening the
    guest's.) An untrusted map is never used to judge a clip."""
    if not m.get("guest_share"):
        return False
    return (m.get("kevin_vs_ref", 0) - m.get("guest_vs_ref", 0)) >= APART


def pcm(src):
    raw = subprocess.run([FF, "-v", "error", "-i", src, "-vn", "-ac", "1", "-ar", str(SR),
                          "-f", "s16le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0


def encoder():
    sys.path.insert(0, os.path.expanduser("~/Kamay"))
    import vsc_frame
    if not os.path.exists(vsc_frame.VOICE):
        raise FileNotFoundError(vsc_frame.VOICE)
    return vsc_frame._Voices(vsc_frame.VOICE)


def stretches(words):
    out, cur = [], []
    for w in words:
        if cur and (w["a"] - cur[-1]["b"] >= GAP or w["b"] - cur[0]["a"] > LONG):
            out.append((cur[0]["a"], cur[-1]["b"]))
            cur = []
        cur.append(w)
    if cur:
        out.append((cur[0]["a"], cur[-1]["b"]))
    return out


def speaker_map(src, words):
    words = sorted(words, key=lambda w: w["a"])
    st = stretches(words)
    x, enc = pcm(src), encoder()
    kref = np.load(REF).astype(np.float32)
    vec = [enc.embed(x[int(a * SR):int(b * SR)]) if b - a >= JUDGE else None for a, b in st]
    idx = [i for i, v in enumerate(vec) if v is not None]
    if len(idx) < 4:
        return {"v": 1, "guest_share": 0.0, "spans": [[a, b, "K"] for a, b in st]}
    V = np.stack([vec[i] for i in idx])
    dur = np.array([st[i][1] - st[i][0] for i in idx])
    # 2-means, Kevin's centroid seeded with his reference voice
    cK, cG = kref, V[int(np.argmin(V @ kref))]
    for _ in range(8):
        lab = (V @ cG > V @ cK).astype(int)              # 1 = guest
        if lab.sum() == 0 or lab.sum() == len(lab):
            break
        cK = (V[lab == 0] * dur[lab == 0, None]).sum(0)
        cG = (V[lab == 1] * dur[lab == 1, None]).sum(0)
        cK, cG = cK / np.linalg.norm(cK), cG / np.linalg.norm(cG)
    if cG @ kref > cK @ kref:                           # the clusters came out swapped
        cK, cG = cG, cK
    d = V @ cG - V @ cK
    share = float(dur[d > 0].sum() / dur.sum())
    lab = {}
    for i, di in zip(idx, d):
        lab[i] = "?" if abs(di) < MARGIN else ("G" if di > 0 else "K")
    if share < SOLO:
        lab = {i: "K" for i in range(len(st))}
        share = 0.0
    # a stretch too short (or too close) to judge takes the voice around it, if both
    # sides agree; otherwise it stays "?"
    for i in range(len(st)):
        if lab.get(i, "?") != "?":
            continue
        p = next((lab[j] for j in range(i - 1, -1, -1) if lab.get(j, "?") != "?"), None)
        n = next((lab[j] for j in range(i + 1, len(st)) if lab.get(j, "?") != "?"), None)
        lab[i] = p if p == n and p else ("?" if share else "K")
    spans = []
    for i, (a, b) in enumerate(st):
        if spans and spans[-1][2] == lab[i] and a - spans[-1][1] < 2.0:
            spans[-1][1] = round(b, 2)
        else:
            spans.append([round(a, 2), round(b, 2), lab[i]])
    # AN ISLAND IS A MISREAD. Tested on Kevin + another narrator + Kevin (18 Oct): one
    # 2.6 s stretch inside the other man's 42 s was called Kevin. A run under ISLAND
    # with the same other voice on both sides joins them (a real "Right." from the
    # guest inside Kevin's answer is lost too - too short to matter to the share).
    i = 1
    while i < len(spans) - 1:
        p, c, n = spans[i - 1], spans[i], spans[i + 1]
        if p[2] == n[2] != c[2] and c[1] - c[0] < ISLAND:
            p[1] = n[1]
            del spans[i:i + 2]
            i = max(1, i - 1)
        else:
            i += 1
    return {"v": 1, "guest_share": round(share, 3), "apart": round(float(cK @ kref - cG @ kref), 3),
            "kevin_vs_ref": round(float(cK @ kref), 3), "guest_vs_ref": round(float(cG @ kref), 3),
            "spans": spans}


def who(spans, t):
    """The voice at source second t ("K", "G" or "?")."""
    for a, b, s in spans:
        if a - 0.05 <= t <= b + 0.05:
            return s
    return "?"


def make_ref(out, clips):
    enc = encoder()
    vs = []
    for c in clips:
        x = pcm(c)
        for k in range(0, len(x) - 8 * SR, 8 * SR):      # 8 s pieces, all of each clip
            vs.append(enc.embed(x[k:k + 8 * SR]))
    v = np.mean(vs, 0)
    v /= np.linalg.norm(v)
    sims = np.array(vs) @ v
    print(f"{len(vs)} pieces from {len(clips)} clips; each vs the mean: "
          f"min {sims.min():.3f} median {np.median(sims):.3f}")
    np.save(out, v.astype(np.float32))


if __name__ == "__main__":
    if sys.argv[1] == "ref":
        make_ref(sys.argv[2], sys.argv[3:])
    else:
        _, _, src, wj, out = sys.argv
        m = speaker_map(src, json.load(open(wj)))
        json.dump(m, open(out, "w"))
        g = sum(b - a for a, b, s in m["spans"] if s == "G")
        print(f"guest share {m['guest_share']:.0%}, {len(m['spans'])} turns, "
              f"{g:.0f} s guest; Kevin {m.get('kevin_vs_ref')} / guest {m.get('guest_vs_ref')} vs ref")
