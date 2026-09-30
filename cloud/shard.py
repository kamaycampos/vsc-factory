#!/usr/bin/env python3
"""Split the pending clips into shards of two, one server each.

Two per shard is what the KT factory settled on: a shard that is too big holds the
whole batch hostage to its slowest clip, and one clip per server wastes a minute of
setup for every two minutes of work. Clips already finished are not re-shared.
"""
import glob, hashlib, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.environ.get("GITHUB_REPOSITORY", "kamaycampos/vsc-machine")
PER = 2


def fingerprint(clip):
    """What this clip was built FROM: its cut, its hook and its corrections.

    30 Sept 2026: 22 caption corrections and two cut boundaries were written into the
    plan, pushed, built - and the factory built nothing, because a clip with that name
    was already in the release and "already built" meant nothing more than that. A
    whole day's clips were the uncorrected ones, and the run was green. A clip is only
    already built if it was built from the plan entry that is in the repository NOW.
    """
    return hashlib.sha1(json.dumps(clip, sort_keys=True).encode()).hexdigest()[:12]


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
    out, stale = [], []
    for f in sorted(glob.glob(os.path.join(HERE, "plans", "*.json"))):
        p = json.load(open(f))
        todo = []
        for c in p["clips"]:
            if only and c["name"] not in only:
                continue
            if c["name"] not in done:
                todo.append(c["name"]); continue
            if built.get(c["name"]) != fingerprint(c):
                todo.append(c["name"]); stale.append(c["name"])
        if stale:
            print("the plan changed since these were built, so they are built again: "
                  + ", ".join(stale), file=sys.stderr)
        for i in range(0, len(todo), PER):
            out.append({"key": p["key"], "shard": str(i // PER), "names": " ".join(todo[i:i + PER])})
    print(f"{len(out)} shards, {sum(len(s['names'].split()) for s in out)} clips to build",
          file=sys.stderr)
    gh = os.environ.get("GITHUB_OUTPUT")
    if gh:
        with open(gh, "a") as fh:
            fh.write(f"matrix={json.dumps(out)}\ncount={len(out)}\n")
    print(json.dumps(out))


if __name__ == "__main__":
    main()
