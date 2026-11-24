#!/usr/bin/env python3
"""The hand-in wall between builder and grader: office.py handin sends back a badge that is not a grader's whose
commits change a path under the profile's measure.grader_owned, and lets a grader's through.

    python tests/office_wall_test.py

Runs in a scratch git repository in a temp folder; writes no git config (the identity comes from the environment).
"""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent / "tools"
FAILS = []


def check(name, cond, detail=""):
    print(("ok   " if cond else "FAIL ") + name + ("" if cond else f"\n     {detail}"))
    if not cond:
        FAILS.append(name)


def main():
    tmp = Path(tempfile.mkdtemp(prefix="office-wall-"))
    repo, office = tmp / "repo", tmp / "office"
    (repo / ".foundry").mkdir(parents=True)
    (repo / ".foundry" / "foundry.toml").write_text('project = "Wall"\n', encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if not k.startswith("FOUNDRY_")}
    env.update(GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.invalid", GIT_COMMITTER_NAME="t",
               GIT_COMMITTER_EMAIL="t@example.invalid", FOUNDRY_ROOT=str(repo), FOUNDRY_MAIN=str(repo),
               FOUNDRY_PATHS_OFFICE=str(office), PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
    sys.path.insert(0, str(TOOLS))
    os.environ.update({k: env[k] for k in ("FOUNDRY_ROOT", "FOUNDRY_MAIN", "FOUNDRY_PATHS_OFFICE")})
    import office as officemod

    def git(*a):
        return subprocess.run(["git", "-C", str(repo), *a], env=env, capture_output=True, text=True)

    git("init", "-q", "-b", "main", ".")
    (repo / "src").mkdir()
    (repo / "src" / "a.txt").write_text("a\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "base")
    git("switch", "-q", "-c", "work")
    (repo / "gym" / "prereg").mkdir(parents=True)
    (repo / "gym" / "prereg" / "G1.json").write_text("{}\n", encoding="utf-8")
    (repo / "src" / "a.txt").write_text("b\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "work")

    office.mkdir(parents=True, exist_ok=True)
    c = officemod.crew(office)
    builder = {"id": "EMP-01", "role": "BUILDER", "files": "src/, gym/"}
    bad, _, facts = officemod.handin_checks(builder, repo, "main", [], c)
    check("a builder whose commits change the measure's files is sent back",
          any("measure.grader_owned" in b and "gym/prereg/G1.json" in b for b in bad), str(bad))
    check("the changed files were read", "gym/prereg/G1.json" in facts.get("files", []), str(facts))
    grader = {"id": "EMP-02", "role": "GRADER", "files": "gym/prereg/G1.json, src/"}
    bad, _, _ = officemod.handin_checks(grader, repo, "main", [], c)
    check("a grader's commit of the same file passes the wall", not any("measure.grader_owned" in b for b in bad), str(bad))
    scout = {"id": "EMP-03", "role": "SCOUT", "files": "src/"}
    git("switch", "-q", "main")
    git("switch", "-q", "-c", "clean")
    (repo / "src" / "b.txt").write_text("c\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "clean")
    bad, _, _ = officemod.handin_checks(scout, repo, "main", [], c)
    check("a branch that leaves the measure alone is not sent back for it", not any("measure.grader_owned" in b for b in bad), str(bad))

    def _writable(func, path, _exc):
        os.chmod(path, 0o700)
        func(path)

    if not FAILS:
        shutil.rmtree(tmp, onerror=_writable)
    print(f"office wall test: {4 - len(FAILS)} ok, {len(FAILS)} failed" + (f" (scratch kept: {tmp})" if FAILS else ""))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
