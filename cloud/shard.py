#!/usr/bin/env python3
"""Split the pending clips into shards of two, one server each.

Two per shard is what the KT factory settled on: a shard that is too big holds the
whole batch hostage to its slowest clip, and one clip per server wastes a minute of
setup for every two minutes of work. Clips already finished are not re-shared.
"""
import glob, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.environ.get("GITHUB_REPOSITORY", "kamaycampos/vsc-machine")
PER = 2


def already_built():
    r = subprocess.run(["gh", "release", "view", "clips", "-R", REPO, "--json", "assets"],
                       capture_output=True, text=True)
    if r.returncode:
        return set()
    try:
        return {re.sub(r"_\d+s\.mp4$", "", a["name"])
                for a in json.loads(r.stdout).get("assets", []) if a["name"].endswith(".mp4")}
    except Exception:
        return set()


def main():
    # ONLY lets one clip be rebuilt on demand - how the cloud output was first proved
    # identical to the Mac's, and how a single bad clip gets redone without a batch.
    only = [x for x in os.environ.get("ONLY", "").split() if x]
    done = already_built()
    out = []
    for f in sorted(glob.glob(os.path.join(HERE, "plans", "*.json"))):
        p = json.load(open(f))
        todo = [c["name"] for c in p["clips"]
                if c["name"] not in done and (not only or c["name"] in only)]
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
