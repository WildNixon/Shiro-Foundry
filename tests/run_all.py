#!/usr/bin/env python3
"""Run every selftest and test file in the repository, one after another.

    python tests/run_all.py [--keep-going]

Each tool's `selftest` and each file under tests/ and hooks/test_*.py runs in its own process with the same
interpreter. Every one works in temp folders only. Exit 1 when any failed.
"""

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SELFTESTS = ["foundry_profile.py", "founder.py", "office.py", "rq.py", "board.py", "journal.py", "plan_flow.py",
             "lanes_for.py", "sweep.py"]


def main(argv):
    if hasattr(sys.stdout, "reconfigure"):  # a failing test's tail may hold any character
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    runs = [(f"tools/{t} selftest", [str(ROOT / "tools" / t), "selftest"]) for t in SELFTESTS if (ROOT / "tools" / t).is_file()]
    if (ROOT / "tools" / "flow.py").is_file():
        runs.append(("tools/flow.py selftest --logic", [str(ROOT / "tools" / "flow.py"), "selftest", "--logic"]))
    for h in ("no_python_stdin.py", "graph_readonly.py"):
        if (ROOT / "hooks" / h).is_file():
            runs.append((f"hooks/{h} selftest", [str(ROOT / "hooks" / h), "selftest"]))
    for f in sorted((ROOT / "tests").glob("*.py")):
        if f.name != "run_all.py":
            runs.append((f"tests/{f.name}", [str(f)]))
    for f in sorted((ROOT / "hooks").glob("test_*.py")):
        runs.append((f"hooks/{f.name}", [str(f)]))
    env = {k: v for k, v in os.environ.items() if not k.startswith("FOUNDRY_")}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    failed = []
    for name, args in runs:
        t0 = time.time()
        try:
            r = subprocess.run([sys.executable, *args], cwd=str(ROOT), env=env, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=1800)
            code, out = r.returncode, (r.stdout or "") + (r.stderr or "")
            summary = (r.stdout or "").strip().splitlines()  # the count line is the last of stdout
        except subprocess.TimeoutExpired:
            code, out = 124, "timed out after 30 minutes"
            summary = []
        last = (summary or out.strip().splitlines() or ["(no output)"])[-1][:150]
        print(f"{'ok  ' if code == 0 else 'FAIL'} {name:<34} {time.time() - t0:6.1f}s  {last}", flush=True)
        if code != 0:
            failed.append(name)
            print("\n".join("     " + line for line in out.strip().splitlines()[-25:]))
            if "--keep-going" not in argv:
                break
    print(f"\n{len(runs) - len(failed)} of {len(runs)} passed" + (f"; failed: {', '.join(failed)}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
