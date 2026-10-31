#!/usr/bin/env python3
"""Did the batch actually finish? Ask the release, not the jobs.

The 29 Sept batch ended with a green collect and four clips missing: two shards were
killed by the runner, one clip rendered nothing, and every one of those was a fact
that existed in a log nobody was going to read. A run is complete when every clip
named in the plans is published - that is the only definition worth checking, and it
is checked against the release itself, because the release is what Kamay downloads.
"""
import glob, json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.environ.get("GITHUB_REPOSITORY", "kamaycampos/vsc-factory")


def published():
    r = subprocess.run(["gh", "release", "view", "clips", "-R", REPO, "--json", "assets"],
                       capture_output=True, text=True)
    if r.returncode:
        return set()
    return {re.sub(r"_\d+s\.mp4$", "", a["name"])
            for a in json.loads(r.stdout).get("assets", []) if a["name"].endswith(".mp4")}


def held():
    """Clips plancheck held at their CURRENT plan entry (cloud/edges.py after_autoplan)."""
    sys.path.insert(0, HERE)
    from cloud.shard import fingerprint, held as on_release
    hold = on_release()
    out = set()
    for f in glob.glob(os.path.join(HERE, "plans", "*.json")):
        for c in json.load(open(f))["clips"]:
            if (hold.get(c["name"]) or {}).get("fingerprint") == fingerprint(c):
                out.add(c["name"])
    return out


def main():
    have, want, waiting = published(), [], []
    for f in sorted(glob.glob(os.path.join(HERE, "plans", "*.json"))):
        p = json.load(open(f))
        want += [c["name"] for c in p["clips"]]
        if not p["clips"]:
            waiting.append(p["key"])
    missing = [n for n in want if n not in have]
    hold = held()
    print(f"{len(want) - len(missing)}/{len(want)} clips published")
    for n in want:
        print(f"  {'ok  ' if n in have else 'HELD   ' if n in hold else 'MISSING'} {n}")
    # 7 Oct, run 48: "0/0 clips published ... BATCH COMPLETE" - a plan with no clips
    # yet is a batch nobody has made, not a finished one.
    for k in waiting:
        print(f"  WAITING  plans/{k}.json has no clips yet - autoplan did not choose them")
    if waiting and not missing:
        sys.exit(f"\nBATCH NOT MADE - {', '.join(waiting)} still has no clips. "
                 "See the autoplan job of this run for why.")
    held_now = [n for n in missing if n in hold]
    missing = [n for n in missing if n not in hold]
    if held_now and not missing:
        sys.exit(f"\nHELD BY PLANCHECK - {', '.join(held_now)}: a wrong word was heard at the cut on "
                 "the source, so they were not built. Fix start_at / end_at from a probe and push "
                 "(the autoplan run's summary page has the words heard).")
    if missing:
        sys.exit(f"\nBATCH INCOMPLETE after three attempts - {len(missing)} clip(s) never "
                 f"reached the release: {', '.join(missing)}\n"
                 "Run the workflow again; it builds only what is missing."
                 + (f"\nAlso HELD BY PLANCHECK (not built until start_at / end_at change): {', '.join(held_now)}"
                    if held_now else ""))
    print("\nEvery clip in the plans is published. BATCH COMPLETE")


if __name__ == "__main__":
    main()
