#!/usr/bin/env python3
"""Build an episode's MASTER transcript on the server (kt-machine shared/kt_master.py).

    python cloud/master.py <key> <engine> [<second engine>] [--no-correct]

Engines: small | turbo | turbo-names | large - free whisper.cpp only (see
cloud/stt_test.py). The whole episode is transcribed once, corrected by one Claude
call (when ANTHROPIC_API_KEY is set), then the plan's `master_fixes` - human
corrections in SOURCE seconds, written once per episode - are applied. The file goes
where kt_master.cut() looks; a copy encrypted with VSC_KEY goes to /tmp/master_out.

Only used when MASTER_TRANSCRIPT=1 (opt-in, default off).
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, os.path.expanduser("~/Kamay"))
from cloud.source import fetch, plans          # noqa: E402
from cloud.stt_test import ENGINES             # noqa: E402
import kt_master                               # noqa: E402


def main(key, engine, correct=True, second=None):
    plan = [p for p in plans() if p["key"] == key][0]
    src = fetch(plan)
    ctx = plan.get("rumble_title") or plan.get("prefix", "")
    ctx = f"'{ctx}'. {plan.get('note', '')}"
    m = kt_master.build(src, ENGINES[engine], correct, ctx, plan.get("master_fixes", []),
                        second=ENGINES.get(second) if second else None)
    for e in m["edits"]:
        print(f"    EDIT {e['at']:7.1f}s  {e['wrong']!r} -> {e['right']!r}  ({e['why']})")
    for e in m["rejected"]:
        print(f"    REFUSED  {e['wrong']!r} -> {e['right']!r}: {e['rejected']}")
    os.makedirs("/tmp/master_out", exist_ok=True)
    p = kt_master.path_for(src)
    subprocess.run(["openssl", "enc", "-aes-256-cbc", "-pbkdf2", "-salt", "-pass", "env:VSC_KEY",
                    "-in", p, "-out", f"/tmp/master_out/{key}.master.json.enc"], check=True)
    json.dump({k: m[k] for k in ("engine", "seconds", "usage")} |
              {"edits": len(m["edits"]), "refused": len(m["rejected"])},
              open("/tmp/master_out/summary.json", "w"), indent=1)


if __name__ == "__main__":
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    main(a[0], a[1], "--no-correct" not in sys.argv, a[2] if len(a) > 2 else None)
