#!/usr/bin/env python3
"""Clear a finished project out of the three releases (Kamay, 15 Oct: "always delete stuff
that is confirmed not needed anymore").

    python cloud/retire.py <key> [<key> ...] [--keep-source <key> ...] [--dry-run]

Only a plan already in plans/done/ can be retired. Deleted: every cut of its clips (all
lengths, video and caption file) and of the names in cloud/dropped.json from `clips`; its
pause map, speaker map, prep archive and transcript from `prep`; its encrypted source
from `sources`, unless --keep-source names it (keep it while GIN may still ask for a
re-cut: a source Rumble refuses the runners costs a long Mac upload to bring back).
25 Oct 2026: a cloud session may not delete release files; this runs as a workflow.
"""
import json, os, re, subprocess, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.environ.get("GITHUB_REPOSITORY", "kamaycampos/vsc-factory")
letters = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())


def gh(*a):
    r = subprocess.run(["gh", "api", *a], capture_output=True, text=True)
    if r.returncode:
        raise SystemExit(f"gh api {' '.join(a)}: {r.stderr.strip()}")
    return r.stdout


def assets(tag):
    rid = json.loads(gh(f"repos/{REPO}/releases/tags/{tag}"))["id"]
    out = []
    for line in gh("--paginate", f"repos/{REPO}/releases/{rid}/assets?per_page=100",
                   "--jq", ".[] | [.id, .name, .size] | @tsv").splitlines():
        i, n, s = line.split("\t")
        out.append((int(i), n, int(s)))
    return out


def main(argv):
    dry = "--dry-run" in argv
    argv = [a for a in argv if a != "--dry-run"]
    keep = set()
    if "--keep-source" in argv:
        k = argv.index("--keep-source")
        keep = set(argv[k + 1:])
        argv = argv[:k]
    plans = []
    for key in argv:
        f = os.path.join(HERE, "plans", "done", f"{key}.json")
        if not os.path.exists(f):
            raise SystemExit(f"{key}: not in plans/done/ - only a finished project is retired")
        plans.append(json.load(open(f)))
    try:
        dropped = set(json.load(open(os.path.join(HERE, "cloud", "dropped.json")))["names"])
    except FileNotFoundError:
        dropped = set()
    names = dropped | {c["name"] for p in plans for c in p["clips"]}
    clip_of = lambda n: re.sub(r"_\d+s(\.mp4|__caps\.json|__head\.json|__tail\.json)$", "", n)
    gone = []
    for i, n, s in assets("clips"):
        if clip_of(n) != n and clip_of(n) in names:
            gone.append(("clips", i, n, s))
    for i, n, s in assets("prep"):
        for p in plans:
            if p["key"] in n or (n.startswith("TRANSCRIPT_") and letters(p["prefix"]) in letters(n)):
                gone.append(("prep", i, n, s))
                break
    for i, n, s in assets("sources"):
        for p in plans:
            if n.startswith(p["key"] + ".mp4") and p["key"] not in keep:
                gone.append(("sources", i, n, s))
    for tag, i, n, s in gone:
        print(f"{'would delete' if dry else 'delete'}  {tag:8s} {s / 1e6:9.1f} MB  {n}", flush=True)
        if not dry:
            gh("-X", "DELETE", f"repos/{REPO}/releases/assets/{i}")
    print(f"\n{len(gone)} file(s), {sum(g[3] for g in gone) / 1e9:.2f} GB"
          + (" (dry run - nothing deleted)" if dry else " deleted")
          + (f"; source kept for: {' '.join(sorted(keep))}" if keep else ""))


if __name__ == "__main__":
    main(sys.argv[1:])
