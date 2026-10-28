#!/usr/bin/env python3
"""READ EVERY CAPTION LINE - in the cloud, after every build. 28 Oct 2026.

Kamay, 28 Oct: "we have been trying this system for months ... and still the system
cannot run from start to end in one go?" The one step every batch still waited on a
person for was the caption read (Naomi's rule: read every caption line before
submission). This is that read.

For every clip of an active plan that is built from its plan entry as it stands, and
not yet read, ONE Claude call (all of a batch's clips together) reads the captions the
SERVER burned in (`<file>__caps.json`, the only text a fix can match) beside prep's
transcript of the same stretch. It answers in a fixed schema: `fixes` (wrong words ->
right words) and `look` (what text cannot fix: a mid-thought end, someone else talking).

Code keeps a fix only if it can apply exactly as the renderer will apply it:
  - the wrong words are in that clip's captions, within 4 s of the time given,
  - it overlaps no other new fix, and no text an earlier fix produced (fixes stack),
  - it changes something, and stays a correction (at most 12 words), not a rewrite.
Kept fixes go into the plan; the workflow commits it and starts a fresh run, which
rebuilds only those clips. That run CONFIRMS each fix in the new captions (no model
call): every `right` must be on screen, or the clip is a LOOK.

capread.json (clips release), per clip:
  A LOOK a person has answered is cleared by the clip's plan field "look_ok": "<why>"
  (not part of the fingerprint, so it rebuilds nothing).
  {"fp": plan fingerprint read, "file": file confirmed or null, "status": "read" |
   "fixing", "fixes": [...applied], "look": [...]}
The Mac gate passes a clip only when status is "read", file is that exact file and
look is empty.

    python cloud/capread.py            # what the workflow runs
    python cloud/capread.py --dry      # read and validate, change nothing
"""
import glob, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
REPO = os.environ.get("GITHUB_REPOSITORY", "kamaycampos/vsc-factory")
MODEL = os.environ.get("VSC_CAPREAD_MODEL") or "claude-opus-5-5"
WORK = "/tmp/capread"
NEAR = 4.0          # seconds between the time the reader gives and where the words are
MAX_WORDS = 12      # a correction, not a rewrite

SCHEMA = {
    "type": "object",
    "properties": {
        "clips": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "fixes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "t": {"type": "number"},
                                "wrong": {"type": "string"},
                                "right": {"type": "string"},
                                "why": {"type": "string"},
                            },
                            "required": ["t", "wrong", "right", "why"],
                            "additionalProperties": False,
                        },
                    },
                    "look": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["name", "fixes", "look"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["clips"],
    "additionalProperties": False,
}

BRIEF = """You are the caption reader for GIN's VSC clips of Kevin Trudeau. A reviewer
(Naomi) reads every caption line before a clip is submitted; you are that read. The
captions below are EXACTLY what is burned into each clip, one line per caption, with the
second it appears. Beside them is a second, independent transcript of the same stretch
(prep's whole-file pass) - where the two disagree, one of them misheard Kevin.

Return, per clip:
- `fixes`: every caption error. `wrong` is copied LETTER FOR LETTER from the captions
  (it may run across two consecutive caption lines), `t` is the second of the caption
  line where `wrong` starts, `right` is what Kevin said, `why` is a few words.
  Fix: misheard words (use the other transcript and the meaning), names (Steve Jobs,
  NeXT, New York Times bestseller list, Carnegie Deli, American Memory Institute, the
  Possibility Thinker's Creed, Dharma), a full stop or capital in the middle of a
  sentence ("missing. on the inside" -> "missing on the inside"; "Nothing outside. of
  yourself" -> "Nothing outside of yourself"), a sentence that starts lower-case, a
  missing full stop between two sentences, [BLANK_AUDIO] or words nobody said
  ("Sorry.", "Thank you."). Where Kevin misspeaks and the meaning is obvious, write
  what he meant.
  Keep Kevin's own words and style: never paraphrase, never tidy his grammar, never
  shorten. Include one or two correct neighbouring words in `wrong` and `right` when
  that makes the match unique, but keep `wrong` short (at most 12 words). Never two
  fixes over the same words.
- `look`: problems text cannot fix, for a person to decide: the clip opens or ends
  mid-thought, the teaching does not land, someone other than Kevin carries it (a
  guest's question or reaction is fine), no lesson at all. Empty when there is none.
  Do not put caption errors here - fix them.

Most clips need few or no fixes. Do not invent problems; an empty answer is right for
clean captions.

The reviewers' rules, for context:
"""


def sh(*a):
    return subprocess.run(list(a), capture_output=True, text=True)


def norm(t):
    """pipeline/vsc_v2caps.norm - the comparison fix_text makes."""
    return re.sub(r"[^a-z0-9']", "", t.lower())


def release_json(name):
    d = sh("gh", "release", "download", "clips", "-R", REPO, "-p", name, "-D", WORK, "--clobber")
    try:
        return json.load(open(os.path.join(WORK, name))) if d.returncode == 0 else {}
    except Exception:
        return {}


def caps(file):
    """The burned captions of one clip file: [[t0, t1, text], ...]."""
    cj = file[:-4] + "__caps.json"
    d = sh("gh", "release", "download", "clips", "-R", REPO, "-p", cj, "-D", WORK, "--clobber")
    try:
        return json.load(open(os.path.join(WORK, cj))) if d.returncode == 0 else None
    except Exception:
        return None


def stream(cap):
    """The captions as one word stream: (normalised word, line start, line index)."""
    out = []
    for k, (t0, _t1, text) in enumerate(cap):
        for w in text.split():
            if norm(w):
                out.append((norm(w), t0, k))
    return out


def spans(ws, phrase):
    toks = [norm(w) for w in phrase.split() if norm(w)]
    n = len(toks)
    return [(i, i + n) for i in range(len(ws) - n + 1) if n and [w[0] for w in ws[i:i + n]] == toks]


def protected(ws, old_fixes):
    """Word indices an earlier fix produced - a new fix over them stacks (CLAUDE.md)."""
    got = set()
    for f in old_fixes:
        hits = [s for s in spans(ws, f[2]) if abs(ws[s[0]][1] - f[0]) <= 12.0]
        if hits:
            s = min(hits, key=lambda s: abs(ws[s[0]][1] - f[0]))
            got |= set(range(*s))
    return got


def validate(clip, cap, fixes):
    """(kept fixes as plan entries, rejected with reasons)."""
    ws = stream(cap)
    taken = protected(ws, clip.get("fixes", []))
    kept, bad = [], []
    for f in fixes:
        wrong, right, t = f["wrong"].strip(), f["right"].strip(), float(f["t"])
        why = None
        if not wrong or not right:
            why = "empty wrong or right"
        elif wrong == right:
            why = "changes nothing"
        elif len(wrong.split()) > MAX_WORDS or len(right.split()) > MAX_WORDS + 3:
            why = "too long for a correction"
        else:
            hits = [s for s in spans(ws, wrong) if abs(ws[s[0]][1] - t) <= NEAR]
            if not hits:
                why = f"'{wrong}' is not in the captions near {t:.1f}s"
            else:
                s = min(hits, key=lambda s: abs(ws[s[0]][1] - t))
                if taken & set(range(*s)):
                    why = "overlaps another fix"
                else:
                    taken |= set(range(*s))
                    kept.append([round(ws[s[0]][1], 2), wrong, right])
        if why:
            bad.append(f"{clip['name']}: {why} ({f['wrong']!r} -> {f['right']!r})")
    return kept, bad


def confirm(entry, cap):
    """Every applied fix's words are on screen in the rebuilt file."""
    ws = stream(cap)
    miss = []
    for f in entry.get("fixes", []):
        if not any(abs(ws[s[0]][1] - f[0]) <= 12.0 for s in spans(ws, f[2])):
            miss.append(f"caption fix not on screen: '{f[2]}' (was '{f[1]}') near {f[0]:.0f}s")
    return miss


def region_text(tx, c):
    """prep's transcript lines over this clip's stretch (each line '[mm:ss.ss] ...')."""
    a, b = c.get("start_at", c["region"][0]) - 3, c.get("end_at", c["region"][1]) + 3
    out = []
    for line in tx.splitlines():
        m = re.match(r"\[(\d+):(\d+(?:\.\d+)?)", line)
        if m and a - 30 <= int(m.group(1)) * 60 + float(m.group(2)) <= b:
            out.append(line)
    return "\n".join(out)


def ask(p, todo, tx):
    import anthropic
    from autoplan import rules
    client = anthropic.Anthropic()
    parts = [f"Episode: \"{p.get('title') or p['key']}\"\n"]
    for c, cap in todo:
        lines = "\n".join(f"[{t0:6.2f}] {text}" for t0, _t1, text in cap)
        parts.append(f"=== CLIP {c['name']} - hook: {' / '.join(c.get('hook', []))}\n"
                     f"Burned captions (second in the clip, text):\n{lines}\n\n"
                     f"Other transcript of this stretch (source time; starts a little "
                     f"before the clip and ends a little after it):\n{region_text(tx, c)}\n")
    with client.beta.messages.stream(
        model=MODEL, max_tokens=32000, system=BRIEF + rules(),
        messages=[{"role": "user", "content": "\n".join(parts)}],
        output_config={"effort": "high", "format": {"type": "json_schema", "schema": SCHEMA}},
        betas=["server-side-fallback-2026-07-01"], fallbacks="default",
    ) as s:
        r = s.get_final_message()
    if r.stop_reason in ("refusal", "max_tokens"):
        raise RuntimeError(f"the reader stopped: {r.stop_reason}")
    print(f"  read {len(todo)} clip(s) [{r.usage.input_tokens} in / {r.usage.output_tokens} out]")
    return {x["name"]: x for x in json.loads("".join(b.text for b in r.content if b.type == "text"))["clips"]}


def main(dry=False):
    from shard import fingerprint
    from autoplan import transcript
    os.makedirs(WORK, exist_ok=True)
    built, verdicts, done = release_json("built.json"), release_json("verdicts.json"), release_json("capread.json")
    try:
        delivered = json.load(open(os.path.join(HERE, "delivered.json")))
    except Exception:
        delivered = {}
    changed, summary = [], []
    for f in sorted(glob.glob(os.path.join(ROOT, "plans", "*.json"))):
        p = json.load(open(f))
        locked = set(delivered.get(p["key"], []))
        todo = []
        for c in p["clips"]:
            n, fp = c["name"], fingerprint(c)
            file = (verdicts.get(n) or {}).get("file")
            if n in locked or built.get(n) != fp or not file:
                continue                    # delivered, not built from this entry, or no file
            e = done.get(n)
            if e and e.get("fp") == fp and e.get("file") == file:
                continue                    # read and confirmed
            cap = caps(file)
            if cap is None:
                summary.append(f"{n}: no caption file for {file} - not read")
                continue
            if e and e.get("fp") == fp and e.get("status") == "fixing":
                # rebuilt with the fixes this step wrote: confirm, no second model call
                miss = confirm(e, cap)
                look = ([] if c.get("look_ok") else e.get("look", [])) + miss
                done[n] = dict(e, file=file, status="read", look=look)
                summary.append(f"{n}: {len(e.get('fixes', []))} fix(es) confirmed on screen"
                               + (f" - LOOK: {'; '.join(miss)}" if miss else ""))
                continue
            todo.append((c, cap, file, fp))
        if not todo:
            continue
        try:
            ans = ask(p, [(c, cap) for c, cap, _f, _fp in todo], transcript(p) or "")
        except Exception as ex:
            print(f"::error::{p['key']}: the caption read failed: {type(ex).__name__}: {str(ex)[:300]}")
            summary.append(f"{p['key']}: caption read FAILED - clips stay unread")
            continue
        for c, cap, file, fp in todo:
            a = ans.get(c["name"], {"fixes": [], "look": ["the reader returned nothing for this clip"]})
            # THE LAST CAPTION ENDS THE SENTENCE (28 Oct 2026). A clip ends where the
            # teaching lands - a finished sentence - but the caption pass, cut off at the
            # clip's end, dropped the stop ("But duty is simple"), and kt_qc failed
            # DHARMA-IS-DUTY and THE-CHRISTMAS-CRASH as "ends mid-thought". Code, not the
            # model: first, so a model fix over the same words is the one rejected.
            last = cap[-1][2].strip() if cap else ""
            if last and not re.search(r"[.?!][\"')]*$", last):
                a["fixes"] = [{"t": cap[-1][0], "wrong": last, "right": last.rstrip(",;:-") + ".",
                               "why": "the clip ends a sentence"}] + a.get("fixes", [])
            kept, bad = validate(c, cap, a.get("fixes", []))
            for b in bad:
                print(f"    rejected - {b}")
            look = a.get("look", [])
            if c.get("look_ok") and look:
                # A PERSON ANSWERED THIS LOOK in the plan ("look_ok": "<why>"); it is kept
                # in capread.json for the record and no longer holds the clip
                print(f"    {c['name']}: LOOK answered by look_ok ({c['look_ok']}): {'; '.join(look)}")
                look = []
            if kept:
                c["fixes"] = c.get("fixes", []) + kept
                done[c["name"]] = {"fp": fingerprint(c), "file": None, "status": "fixing",
                                   "fixes": kept, "look": look}
                changed.append(p["key"])
            else:
                done[c["name"]] = {"fp": fp, "file": file, "status": "read", "fixes": [], "look": look}
            summary.append(f"{c['name']}: {len(kept)} fix(es)"
                           + "".join(f"\n    - '{k[1]}' -> '{k[2]}'" for k in kept)
                           + (f"\n    LOOK: {'; '.join(look)}" if look else "")
                           + (f"\n    ({len(bad)} rejected)" if bad else ""))
        if p["key"] in changed and not dry:
            json.dump(p, open(f, "w"), indent=1)
    print("\n".join(summary) or "every built clip's captions are already read")
    if dry:
        return
    json.dump(done, open(os.path.join(WORK, "capread.json"), "w"), indent=1, sort_keys=True)
    u = sh("gh", "release", "upload", "clips", os.path.join(WORK, "capread.json"), "--clobber", "-R", REPO)
    if u.returncode:
        print(f"::error::could not publish capread.json: {u.stderr[-200:]}")
    gh = os.environ.get("GITHUB_OUTPUT")
    if gh:
        open(gh, "a").write(f"fixed={'1' if changed else ''}\nkeys={' '.join(sorted(set(changed)))}\n")
    s = os.environ.get("GITHUB_STEP_SUMMARY")
    if s:
        open(s, "a").write("### Caption read\n```\n" + ("\n".join(summary) or "nothing to read") + "\n```\n")


if __name__ == "__main__":
    main(dry="--dry" in sys.argv)
