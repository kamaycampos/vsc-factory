#!/usr/bin/env python3
"""Split the pending clips into shards of two, one server each.

Two per shard is what the KT factory settled on: a shard that is too big holds the
whole batch hostage to its slowest clip, and one clip per server wastes a minute of
setup for every two minutes of work. Clips already finished are not re-shared.
"""
import glob, hashlib, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.environ.get("GITHUB_REPOSITORY", "kamaycampos/vsc-machine")
RULES = "head-tail-2026-10-02c"      # see fingerprint()
PER = 2
SHARD_SECONDS = 95      # a shard's total clip length; one long clip gets a server alone


def fingerprint(clip):
    """What this clip was built FROM: its cut, its hook and its corrections.

    30 Sept 2026: 22 caption corrections and two cut boundaries were written into the
    plan, pushed, built - and the factory built nothing, because a clip with that name
    was already in the release and "already built" meant nothing more than that. A
    whole day's clips were the uncorrected ones, and the run was green. A clip is only
    already built if it was built from the plan entry that is in the repository NOW.
    """
    # ...and the RULES it was built by. 2 Oct 2026: the end-of-clip rule changed and
    # every clip built under the old one could carry Kevin's next words, but no plan
    # entry changed, so nothing would have been rebuilt. Bump RULES when a change to
    # the factory means every clip must be made again.
    return hashlib.sha1((json.dumps(clip, sort_keys=True) + RULES).encode()).hexdigest()[:12]


def already_built():
    r = subprocess.run(["gh", "release", "view", "clips", "-R", REPO, "--json", "assets"],
                       capture_output=True, text=True)
    if r.returncode:
        return set(), {}
    try:
        have = {re.sub(r"_\d+s\.mp4$", "", a["name"])
                for a in json.loads(r.stdout).get("assets", []) if a["name"].endswith(".mp4")}
    except Exception:
        return set(), {}
    built = {}
    if any(a["name"] == "built.json" for a in json.loads(r.stdout).get("assets", [])):
        d = subprocess.run(["gh", "release", "download", "clips", "-R", REPO, "-p",
                            "built.json", "-D", "/tmp/bj", "--clobber"],
                           capture_output=True, text=True)
        if d.returncode == 0:
            try:
                built = json.load(open("/tmp/bj/built.json"))
            except Exception:
                built = {}
    return have, built


def main():
    # ONLY lets one clip be rebuilt on demand - how the cloud output was first proved
    # identical to the Mac's, and how a single bad clip gets redone without a batch.
    only = [x for x in os.environ.get("ONLY", "").split() if x]
    done, built = already_built()
    # DELIVERED CLIPS ARE FINISHED. 3 Oct 2026: four of the 23 delivered to GIN carried a
    # FAIL "listen" verdict, so collect never recorded their fingerprint, and Monday's
    # scheduled build would have rebuilt them under new shared framing - a different
    # file in the release from the one on Frame.io. Only `only` can rebuild one now.
    try:
        delivered = json.load(open(os.path.join(HERE, "cloud", "delivered.json")))
    except Exception:
        delivered = {}
    out, stale = [], []
    for f in sorted(glob.glob(os.path.join(HERE, "plans", "*.json"))):
        p = json.load(open(f))
        todo = []
        locked = set(delivered.get(p["key"], []))
        for c in p["clips"]:
            if only and c["name"] not in only:
                continue
            if only:                          # named on demand: rebuilt, built or not
                todo.append(c["name"]); continue
            if c["name"] in locked:
                continue
            if c["name"] not in done:
                todo.append(c["name"]); continue
            if built.get(c["name"]) != fingerprint(c):
                todo.append(c["name"]); stale.append(c["name"])
        if stale:
            print("the plan changed since these were built, so they are built again: "
                  + ", ".join(stale), file=sys.stderr)
        # PACK BY LENGTH, NOT BY COUNT. 30 Sept 2026: MORE-PROBLEMS-THAN-YOU (122s) and
        # BANNED-FOR-LIFE (128s) were killed mid-render three runs in a row, and each one
        # took its shard-mate down with it - YOUR-BIGGEST-DISASTER is 32 seconds long and
        # failed three times without anything being wrong with it. The two longest clips
        # in the batch are the two that never survived; everything at 73s and under did.
        # So length decides who shares a server, and a clip over the budget gets one alone.
        span = {c["name"]: c["region"][1] - c["region"][0] for c in p["clips"]}
        group, total = [], 0.0
        for n in todo:
            if group and (len(group) >= PER or total + span.get(n, 40) > SHARD_SECONDS):
                out.append({"key": p["key"], "shard": str(len(out)), "names": " ".join(group)})
                group, total = [], 0.0
            group.append(n)
            total += span.get(n, 40)
        if group:
            out.append({"key": p["key"], "shard": str(len(out)), "names": " ".join(group)})
    print(f"{len(out)} shards, {sum(len(s['names'].split()) for s in out)} clips to build",
          file=sys.stderr)
    gh = os.environ.get("GITHUB_OUTPUT")
    if gh:
        with open(gh, "a") as fh:
            fh.write(f"matrix={json.dumps(out)}\ncount={len(out)}\n")
    print(json.dumps(out))


if __name__ == "__main__":
    main()
