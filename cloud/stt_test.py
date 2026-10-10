#!/usr/bin/env python3
"""Which speech-to-text should the master transcript use? Measured on OUR audio.

    python cloud/stt_test.py run <engine> <wav> <out.json>
    python cloud/stt_test.py score <key> <hyp dir> [--correct]

9 Oct 2026. Vendor accuracy claims conflict, so every candidate transcribes the same
whole episode (millionaires_problems, 18:10) and is scored against what GIN's reviewers
actually signed off: the burned captions of the delivered clips (`<clip>__caps.json` in
the clips release - small.en output WITH the plan's human `fixes` already applied).

Scores, per engine, summed over every delivered clip:
  - WER  - word error rate against those captions (case and punctuation ignored);
  - names - each name in kt_master.NAMES that the captions contain, right or wrong
            (NeXT must keep its capitals);
  - timing - spread of caption-start differences (ms) once each clip's offset is
            removed: how tightly the engine's word times follow the approved ones;
  - runtime, and the same scores again after the one Claude correction call.

BIAS, stated up front: the reference IS small.en plus the errors reviewers caught. Any
small.en error they missed counts as RIGHT for small.en and WRONG for everyone else, so
small.en's WER is flattered. A better engine has to beat that handicap.

Nothing here prints Kevin's words: the report holds numbers and name tallies only.
"""
import difflib
import json
import os
import re
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.environ.get("KT_SHARED", "/tmp/kt_shared"))
REPO = os.environ.get("GITHUB_REPOSITORY", "kamaycampos/vsc-factory")

ENGINES = {
    "small": "whisper:" + os.path.expanduser("~/wcache/ggml-small.en.bin"),
    "turbo": "whisper:" + os.path.expanduser("~/wturbo/ggml-large-v3-turbo.bin"),
    "turbo-names": "whisper+names:" + os.path.expanduser("~/wturbo/ggml-large-v3-turbo.bin"),
    "large": "whisper:" + os.path.expanduser("~/wlarge/ggml-large-v3.bin"),
}
FILLER = {"um", "uh", "erm", "ah", "mm", "hmm"}


def toks(text):
    t = text.replace("%", " percent").replace("$", " ").replace("&", " and ")
    t = re.sub(r"[—–\-/]", " ", t)
    return [w for w in (re.sub(r"[^a-z0-9']", "", x.lower()).strip("'") for x in t.split())
            if w and w not in FILLER]


def raw_toks(text):
    t = re.sub(r"[—–\-/]", " ", text)
    return [w for w in (re.sub(r"[^A-Za-z0-9'.]", "", x).strip(".'") for x in t.split())
            if w and w.lower() not in FILLER]


def run(engine, wav, out):
    import kt_master
    t0 = time.time()
    words = kt_master.collapse_stutters(kt_master.transcribe(wav, ENGINES[engine]))
    took = round(time.time() - t0, 1)
    json.dump({"engine": engine, "seconds": took, "words": words}, open(out, "w"))
    print(f"{engine}: {len(words)} words in {took}s")


# ------------------------------------------------------------------- the reference
def reference(key):
    """{clip: {"region": [s, e], "bursts": [[a, b, text], ...]}} for every delivered clip."""
    plan = json.load(open(os.path.join(ROOT, "plans", key + ".json")))
    delivered = set(json.load(open(os.path.join(HERE, "delivered.json"))).get(key, []))
    rel = json.load(urllib.request.urlopen(f"https://api.github.com/repos/{REPO}/releases/tags/clips"))
    newest = {}
    for a in rel["assets"]:
        m = re.match(r"(.+)_(\d+)s__caps\.json$", a["name"])
        if m and m.group(1) in delivered:
            if m.group(1) not in newest or a["updated_at"] > newest[m.group(1)]["updated_at"]:
                newest[m.group(1)] = a
    out = {}
    for c in plan["clips"]:
        a = newest.get(c["name"])
        if a:
            out[c["name"]] = {"region": c["region"],
                              "bursts": json.load(urllib.request.urlopen(a["browser_download_url"]))}
    return out


# ------------------------------------------------------------------------- scoring
def lev(a, b):
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def score_clip(ref, words):
    """(errors, ref words, name hits, name total, [timing deltas]) for one clip."""
    r0, r1 = ref["region"]
    win = [w for w in words if r0 - 25 <= w[0] <= r1 + 35]
    # every reference word, with the start of the caption burst it opens (or None)
    rw, rraw, rstart = [], [], []
    for a, b, text in ref["bursts"]:
        t, rt = toks(text), raw_toks(text)
        for k, w in enumerate(t):
            rw.append(w)
            rstart.append(a if k == 0 else None)
        rraw += rt if len(rt) == len(t) else [None] * len(t)
    hw = []
    for a, b, w in win:
        for x in toks(w):
            hw.append((x, a, raw_toks(w)))
    hn = [x[0] for x in hw]
    sm = difflib.SequenceMatcher(a=rw, b=hn, autojunk=False)
    blocks = [m for m in sm.get_matching_blocks() if m.size >= 3]
    if not blocks:
        return len(rw), len(rw), 0, 0, []
    lo = max(0, blocks[0].b - blocks[0].a)
    hi = min(len(hn), blocks[-1].b + blocks[-1].size + (len(rw) - blocks[-1].a - blocks[-1].size))
    hyp = hn[lo:hi]
    err = lev(rw, hyp)
    # alignment for names and timing
    sm = difflib.SequenceMatcher(a=rw, b=hyp, autojunk=False)
    same = {}
    for m in sm.get_matching_blocks():
        for k in range(m.size):
            same[m.a + k] = lo + m.b + k
    deltas = [hw[same[i]][1] - rstart[i] for i in range(len(rw)) if rstart[i] is not None and i in same]
    if deltas:
        med = sorted(deltas)[len(deltas) // 2]
        deltas = [abs(d - med) for d in deltas]
    import kt_master
    hit = tot = 0
    for name in kt_master.NAMES:
        nt = toks(name)
        if not nt:
            continue
        for i in range(len(rw) - len(nt) + 1):
            if rw[i:i + len(nt)] != nt:
                continue
            tot += 1
            ok = all(i + k in same for k in range(len(nt)))
            # a name whose spelling IS its capitals (NeXT) must come back with them
            for k, part in enumerate(name.split()):
                if ok and k < len(nt) and re.search(r"[a-z][A-Z]", part):
                    ok = part in hw[same[i + k]][2]
            hit += ok
    return err, len(rw), hit, tot, deltas


def score(key, hypdir, do_correct=False):
    ref = reference(key)
    print(f"reference: {len(ref)} delivered clips, "
          f"{sum(len(toks(' '.join(b[2] for b in r['bursts']))) for r in ref.values())} words")
    plan = json.load(open(os.path.join(ROOT, "plans", key + ".json")))
    rows = []
    hyps = []
    for f in sorted(os.listdir(hypdir)):
        if f.endswith(".json"):
            hyps.append(json.load(open(os.path.join(hypdir, f))))
    if do_correct:
        import kt_master
        for h in list(hyps):
            w, taken, rejected, usage = kt_master.correct([tuple(x) for x in h["words"]],
                                                         context=plan.get("note", ""))
            if usage:
                hyps.append({"engine": h["engine"] + "+claude", "seconds": h["seconds"],
                             "words": w, "edits": len(taken), "refused": len(rejected),
                             "claude_usd": usage["usd"]})
                print(f"  {h['engine']}+claude: {len(taken)} edits taken, {len(rejected)} refused, "
                      f"${usage['usd']}", flush=True)
                for e in rejected[:15]:                       # reasons only, never the words
                    print(f"    refused: {e['rejected']}", flush=True)
    for h in hyps:
        E = N = H = T = 0
        D = []
        for name, r in ref.items():
            e, n, hit, tot, d = score_clip(r, h["words"])
            E += e; N += n; H += hit; T += tot; D += d
        D.sort()
        cost = h.get("claude_usd", 0)          # whisper.cpp on a free runner costs nothing
        rows.append({"engine": h["engine"], "wer": round(100 * E / max(1, N), 2), "errors": E, "words": N,
                     "names": f"{H}/{T}", "timing_ms_median": round(1000 * D[len(D) // 2]) if D else None,
                     "timing_ms_p90": round(1000 * D[int(len(D) * 0.9)]) if D else None,
                     "runtime_s": h["seconds"], "usd_per_episode": round(cost, 3),
                     "edits": h.get("edits"), "refused": h.get("refused")})
    rows.sort(key=lambda r: r["wer"])
    md = ["| engine | WER % | errors/words | names right | timing spread median / p90 ms | runtime s | $ / episode | Claude edits (refused) |",
          "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        ed = "" if r["edits"] is None else f"{r['edits']} ({r['refused']})"
        md.append(f"| {r['engine']} | {r['wer']} | {r['errors']}/{r['words']} | {r['names']} | "
                  f"{r['timing_ms_median']} / {r['timing_ms_p90']} | {r['runtime_s']} | "
                  f"{r['usd_per_episode']} | {ed} |")
    os.makedirs("/tmp/report", exist_ok=True)
    open("/tmp/report/report.md", "w").write("\n".join(md) + "\n")
    json.dump(rows, open("/tmp/report/report.json", "w"), indent=1)
    print("\n".join(md))


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[0] == "run":
        run(a[1], a[2], a[3])
    elif a[0] == "score":
        score(a[1], a[2], "--correct" in a)
