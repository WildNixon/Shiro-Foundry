#!/usr/bin/env python3
"""The hand-in wall between builder and grader: office.py handin sends back a badge that is not a grader's whose
commits change a path under the profile's measure.grader_owned, and lets a grader's through. The wall looks at the
branch's tree as well as at each commit's own list (a `git merge -s ours` that keeps an old bar, a commit left out
of --commits), and a run's records (measure.records) are the manager's or a grader's to commit.

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
COUNT = [0]


def check(name, cond, detail=""):
    COUNT[0] += 1
    print(("ok   " if cond else "FAIL ") + name + ("" if cond else f"\n     {detail}"))
    if not cond:
        FAILS.append(name)


def main():
    tmp = Path(tempfile.mkdtemp(prefix="office-wall-")).resolve()
    repo, office = tmp / "repo", tmp / "office"
    (repo / ".foundry").mkdir(parents=True)
    (repo / ".foundry" / "foundry.toml").write_text('project = "Wall"\n', encoding="utf-8")
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("FOUNDRY_") and k not in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR",
                                                         "GIT_PREFIX")}
    env.update(GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.invalid", GIT_COMMITTER_NAME="t",
               GIT_COMMITTER_EMAIL="t@example.invalid", FOUNDRY_ROOT=str(repo), FOUNDRY_MAIN=str(repo),
               FOUNDRY_PATHS_OFFICE=str(office), PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
    sys.path.insert(0, str(TOOLS))
    for k in [k for k in os.environ if k.startswith("FOUNDRY_") or k in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE")]:
        os.environ.pop(k)
    os.environ.update({k: env[k] for k in ("FOUNDRY_ROOT", "FOUNDRY_MAIN", "FOUNDRY_PATHS_OFFICE", "GIT_AUTHOR_NAME",
                                           "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL")})
    import office as officemod

    def git(*a, stdin=None):
        return subprocess.run(["git", "-C", str(repo), *a], env=env, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", input=stdin)

    def put(rel, text):
        f = repo / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(text, encoding="utf-8", newline="\n")

    def commit(msg):
        git("add", "-A")
        r = git("commit", "-q", "-m", msg)
        assert r.returncode == 0, r.stdout + r.stderr
        return git("rev-parse", "HEAD").stdout.strip()

    def branch(name, at="main"):
        r = git("switch", "-q", "-c", name, at)
        assert r.returncode == 0, r.stdout + r.stderr

    def wall(bad):
        return [b for b in bad if "measure.grader_owned" in b]

    def records(bad):
        return [b for b in bad if "a run's records" in b]

    git("init", "-q", "-b", "main", ".")
    put("src/a.txt", "a\n")
    put("gym/prereg/G1.json", '{"bar": 1}\n')
    put("gym/series/G1.json", '{"points": []}\n')
    first = commit("base")

    office.mkdir(parents=True, exist_ok=True)
    c = officemod.crew(office)
    builder = {"id": "EMP-01", "role": "BUILDER", "files": "src/, gym/"}
    grader = {"id": "EMP-02", "role": "GRADER", "files": "gym/, src/"}
    scout = {"id": "EMP-03", "role": "SCOUT", "files": "src/"}
    manager = {"id": "MGR-1", "role": "MANAGER", "files": "gym/, src/"}

    # the wall, by a commit's own list
    branch("work")
    put("gym/prereg/G1.json", '{"bar": 0}\n')
    put("src/a.txt", "b\n")
    commit("work")
    bad, _, facts = officemod.handin_checks(builder, repo, "main", [], c)
    check("a builder whose commits change the measure's files is sent back",
          any("gym/prereg/G1.json (in a commit)" in b for b in wall(bad)), str(bad))
    check("the changed files were read", "gym/prereg/G1.json" in facts.get("files", []), str(facts))
    bad, _, _ = officemod.handin_checks(grader, repo, "main", [], c)
    check("a grader's commit of the same file passes the wall", not wall(bad), str(bad))
    branch("clean")
    put("src/b.txt", "c\n")
    commit("clean")
    bad, _, _ = officemod.handin_checks(scout, repo, "main", [], c)
    check("a branch that leaves the measure alone is not sent back for it", not wall(bad) and not records(bad), str(bad))

    # M3: the grader raises the bar on main; the builder's `git merge -s ours main` keeps the old bar, and no commit
    # of the builder's lists the prereg
    branch("ours")
    put("src/c.txt", "c\n")
    commit("the builder's work")
    branch("behind", "ours")  # the same work with no merge: behind main once the bar is raised, nothing more
    git("switch", "-q", "main")
    put("gym/prereg/G1.json", '{"bar": 2}\n')
    commit("the grader raises the bar")
    git("switch", "-q", "ours")
    r = git("merge", "-q", "-s", "ours", "main", "-m", "merge main, keeping ours")
    assert r.returncode == 0, r.stdout + r.stderr
    per_commit = []
    for sha in git("rev-list", "main..HEAD").stdout.split():
        per_commit += git("show", "--no-renames", "--name-only", "--format=", sha).stdout.split()
    two_dot = git("diff", "--no-renames", "--name-only", "main", "HEAD").stdout.split()
    check("the scenario holds: no commit of the branch lists the prereg, and the branch's tree differs from main in it",
          "gym/prereg/G1.json" not in per_commit and "gym/prereg/G1.json" in two_dot, f"{per_commit} {two_dot}")
    ours = {"id": "EMP-04", "role": "BUILDER", "files": "src/"}
    bad, _, facts = officemod.handin_checks(ours, repo, "main", [], c)
    check("a merge -s ours that keeps the old bar is sent back, naming the path and that the tree differs from the base",
          any("gym/prereg/G1.json (the branch's tree differs from main)" in b and "merge -s ours" in b for b in wall(bad))
          and "gym/prereg/G1.json" not in facts.get("files", []), f"{bad} {facts}")
    bad, _, _ = officemod.handin_checks({**ours, "role": "GRADER"}, repo, "main", [], c)
    check("the same merge by a grader passes the wall", not wall(bad), str(bad))
    git("switch", "-q", "main")
    put("src/later.txt", "later\n")
    commit("main moves on")
    git("switch", "-q", "ours")
    bad, _, _ = officemod.handin_checks(ours, repo, "main", [], c)
    check("the kept old bar is still found after main moves on",
          any("gym/prereg/G1.json (the branch's tree differs from main)" in b for b in wall(bad)), str(bad))
    git("switch", "-q", "behind")
    bad, _, facts = officemod.handin_checks(ours, repo, "main", [], c)
    two_dot = git("diff", "--no-renames", "--name-only", "main", "HEAD").stdout.split()
    check("a branch that is only behind main, where the grader raised the bar after the fork, is not sent back for it",
          not wall(bad) and facts.get("files") == ["src/c.txt"] and "gym/prereg/G1.json" in two_dot, f"{bad} {facts} {two_dot}")

    # --commits a,b names only some commits: the one left out still counts, by the branch's tree
    branch("two")
    put("src/d.txt", "d\n")
    named = commit("named in --commits")
    put("gym/prereg/G1.json", '{"bar": 0.5}\n')
    put("gym/series/G1.json", '{"points": ["PASS"]}\n')
    flow = officemod.prof().rel("flow").strip("/")
    put(flow + "/road.json", "{}\n")
    commit("left out of --commits")
    bad, _, facts = officemod.handin_checks({"id": "EMP-05", "role": "BUILDER", "files": "src/"}, repo, "main", [named], c)
    check("with --commits naming one commit, a walled path in a commit left out is sent back as the tree differing",
          facts.get("files") == ["src/d.txt"]
          and any("gym/prereg/G1.json (the branch's tree differs from main)" in b for b in wall(bad))
          and any("gym/series/G1.json (the branch's tree differs from main)" in b for b in records(bad))
          and any("road graph" in b and flow + "/road.json (the branch's tree differs from main)" in b for b in bad),
          f"{bad} {facts}")

    # M4: a run's records are committed by the manager or a grader, never by the badge that built what is measured
    branch("recs")
    put("gym/series/G1.json", '{"points": ["PASS"]}\n')
    commit("a PASS point added by hand")
    for who in (builder, scout, {"id": "EMP-06", "role": "REVIEWER", "files": "gym/"}):
        bad, _, _ = officemod.handin_checks(who, repo, "main", [], c)
        check(f"a {who['role'].lower()}'s commit that changes a run's records is sent back",
              any("gym/series/G1.json (in a commit)" in b and "committed by whoever queued the counted run" in b
                  for b in records(bad)), str(bad))
    for who in (manager, grader):
        bad, _, _ = officemod.handin_checks(who, repo, "main", [], c)
        check(f"a {who['role'].lower()}'s commit of a run's records passes", not records(bad), str(bad))

    # H1: --base names another branch than main. The builder lowers the bar on `low`, cuts `low2` from it and does
    # the real work there: against `low` (or HEAD~1, or HEAD) no commit and no tree difference shows the prereg
    branch("low")
    put("gym/prereg/G1.json", '{"bar": 0.1}\n')
    put("gym/series/G1.json", '{"points": ["PASS", "PASS"]}\n')
    put(flow + "/road.json", '{"n": 1}\n')
    commit("the bar lowered on the branch the work is cut from")
    branch("low2", "low")
    put("src/e.txt", "e\n")
    commit("the real work")
    h1 = {"id": "EMP-08", "role": "BUILDER", "files": "src/"}
    for b_ in ("low", "HEAD~1", "HEAD"):
        bad, warn, facts = officemod.handin_checks(h1, repo, b_, [], c)
        check(f"with --base {b_} the walls still stand against main: the prereg, the records and the road graph are sent back",
              "gym/prereg/G1.json" not in facts.get("files", [])
              and any("gym/prereg/G1.json (in a commit)" in x for x in wall(bad))
              and any("gym/series/G1.json (in a commit)" in x for x in records(bad))
              and any("road graph" in x and flow + "/road.json (in a commit)" in x for x in bad)
              and any(f"--base is {b_}, not the main branch main" in w and f"both {b_} and main" in w for w in warn),
              f"{bad} {warn} {facts}")
    bad, warn, _ = officemod.handin_checks(h1, repo, "main", [], c)
    check("with the main branch as the base no warning speaks of --base", not any("--base is" in w for w in warn), str(warn))
    git("switch", "-q", "clean")
    bad, warn, _ = officemod.handin_checks(scout, repo, "HEAD~1", [], c)
    check("a clean branch handed in with another --base is READY for the walls, with the warning naming both",
          not wall(bad) and not records(bad) and any("--base is HEAD~1, not the main branch main" in w for w in warn), f"{bad} {warn}")
    real_main = officemod.main_branch
    officemod.main_branch = lambda: "trunk"
    try:
        bad, _, _ = officemod.handin_checks(scout, repo, "main", [], c)
        bad_m, warn_m, _ = officemod.handin_checks(manager, repo, "main", [], c)
    finally:
        officemod.main_branch = real_main
    check("where the main branch does not exist the walls cannot be checked: a PROBLEM for a badge that is not the manager's",
          any("cannot check the walls: no trunk here" in x for x in bad)
          and not any("cannot check the walls" in x for x in bad_m) and any("no trunk here" in w for w in warn_m),
          f"{bad} {bad_m} {warn_m}")

    # L7: a name git prints quoted (a quote in it) is read by its own bytes, so it is behind the wall too
    branch("quoted")
    blob = git("hash-object", "-w", "--stdin", stdin="{}\n").stdout.strip()
    odd = 'gym/prereg/a"b.json'
    # core.protectNTFS off for this one command: on Windows git otherwise refuses the name before it is ever stored
    r = git("-c", "core.protectNTFS=false", "update-index", "--add", "--cacheinfo", f"100644,{blob},{odd}")
    r2 = git("commit", "-q", "-m", "a prereg whose name holds a quote")
    plain = git("show", "--name-only", "--format=", "HEAD").stdout.strip()
    if r.returncode == 0 and r2.returncode == 0 and plain.startswith('"'):
        bad, _, facts = officemod.handin_checks({"id": "EMP-09", "role": "BUILDER", "files": "gym/"}, repo, "main", [], c)
        check("a walled path whose name git prints quoted is sent back by its real name",
              odd in facts.get("files", []) and any(odd + " (in a commit)" in x for x in wall(bad)), f"{bad} {facts}")
    else:
        check("the quoted-name scenario could be built", False, f"{r.stderr} {r2.stderr} {plain}")
    git("switch", "-q", "-f", "main")

    # the wall on a file system that does not tell Gym/Prereg from gym/prereg
    (tmp / "CaseProbe").write_text("x", encoding="utf-8")
    insensitive = (tmp / "caseprobe").exists()
    branch("case")
    blob = git("hash-object", "-w", "--stdin", stdin="{}\n").stdout.strip()
    r = git("-c", "core.ignorecase=false", "update-index", "--add", "--cacheinfo", f"100644,{blob},Gym/Prereg/x.json")
    r2 = git("commit", "-q", "-m", "another spelling of the prereg folder")
    listed = git("show", "--name-only", "--format=", "HEAD").stdout.split()
    if r.returncode == 0 and r2.returncode == 0 and listed == ["Gym/Prereg/x.json"]:
        bad, _, _ = officemod.handin_checks({"id": "EMP-07", "role": "BUILDER", "files": "Gym/, gym/"}, repo, "main", [], c)
        hit = any("Gym/Prereg/x.json" in b for b in wall(bad))
        check("Gym/Prereg/x is behind the wall where the file system folds case"
              if insensitive else "Gym/Prereg/x is another folder where the file system tells case apart",
              hit == insensitive, f"insensitive={insensitive} {bad}")
    else:
        check("the case scenario could be built", False, f"{r.stderr} {r2.stderr} {listed}")
    fold = officemod.path_fold(repo)
    check("path_fold folds case only where the checkout's file system does",
          (fold("Gym/Prereg/X") == fold("gym/prereg/x")) == insensitive and fold("a/b") == "a/b", fold("Gym/Prereg/X"))
    git("reset", "-q", "--hard")
    check("the test wrote no identity into the repo's git config",
          git("config", "--local", "--get", "user.name").stdout.strip() == "" and first != "", "user.name is set")

    def _writable(func, path, _exc):  # git writes its objects read-only, which some systems will not delete
        try:
            os.chmod(path, 0o700)
            func(path)
        except OSError:
            pass

    if not FAILS:
        shutil.rmtree(tmp, **({"onexc": _writable} if sys.version_info >= (3, 12) else {"onerror": _writable}))
    print(f"office wall test: {COUNT[0] - len(FAILS)} ok, {len(FAILS)} failed" + (f" (scratch kept: {tmp})" if FAILS else ""))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
