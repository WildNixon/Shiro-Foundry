#!/usr/bin/env python3
"""Tests for the road graph asset (tools/flow_graph.py, run as `flow.py graph`): who may edit, what a link may
join, the signed edit log, and that flow.py's model reads its links from the asset once it is seeded.

  python tests/test_flow_graph.py

Everything runs in a scratch folder with a scratch crew office (FOUNDRY_PATHS_OFFICE) and a scratch profile
(FOUNDRY_PROFILE, which names one late stage, Beta), so the real office, roster and graph are never touched and
no git config is written. FOUNDRY_ROOT and FOUNDRY_MAIN name the scratch project, so nothing walks up into a
repository the temp folder may lie in; the git identity comes from the environment.
"""
import json
import os
import subprocess
import sys
import shutil
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent / "tools"
FLOW = HERE / "flow.py"

ROADMAP = """# Fixture

| Stage | Theme | Exit | Milestones | Now |
|---|---|---|---|---|
| **R0 Boots** | boots | BOOT-01 | M1 | x |
| **R1 Core** | core | SYS-01 | M2 | x |
| **Beta** | beta | All P0 | none | x |
| **1.0 RC → GA** | ga | every P0 PASS | none | x |

| Milestone | Theme | Closes | Why here |
|---|---|---|---|
| M1 | Boot | BOOT-01 | First |
| M2 | Core | SYS-01 | Needs M1. Needs D1 |
| M3 | Apps | APP-01 | After M2 |

| ID | P | Status | Where | Note |
|---|---|---|---|---|
| BOOT-01 | P0 | Open | M1 | n |
| SYS-01 | P0 | Open | M2 | n |
| APP-01 | P0 | Open | M3 | n |

| # | Decision | Where it stands | Owner | Needed before |
|---|---|---|---|---|
| D1 | Thing | Open: x | the user | M2 |
| D2 | Other | Open: y | the user | M3 (APP-01) |
"""
STATE = {"milestones": [{"id": f"M{i}", "title": t, "status": "planned"} for i, t in ((1, "Boot"), (2, "Core"), (3, "Apps"))],
         "failures": [], "usage": {},
         "shift": {"blocks": [{"title": "Q1: M1 boot", "status": "pending"}, {"title": "Q2: M2 core", "status": "pending"}]}}

FAILS = []


def check(name, cond, detail=""):
    if not cond:
        FAILS.append(name)
        print("FAIL", name, detail)


def main():
    tmp = Path(tempfile.mkdtemp(prefix="flowgraph-")).resolve()  # its real name (macOS /var, a Windows 8.3 name)
    root, off = tmp / "root", tmp / "office"
    (root / "docs" / "progress").mkdir(parents=True)
    off.mkdir()
    (root / "docs" / "ROADMAP.md").write_text(ROADMAP, encoding="utf-8")
    (root / "docs" / "progress" / "state.json").write_text(json.dumps(STATE), encoding="utf-8")
    for k in [k for k in os.environ if k.startswith("FOUNDRY_")]:
        os.environ.pop(k)
    (tmp / "foundry.toml").write_text('project = "Fixture"\n[roadmap]\nlate_stages = ["Beta"]\n', encoding="utf-8")
    os.environ["FOUNDRY_PROFILE"] = str(tmp / "foundry.toml")
    os.environ["FOUNDRY_PATHS_OFFICE"] = str(off)
    os.environ["FOUNDRY_ROOT"] = os.environ["FOUNDRY_MAIN"] = str(root)
    sys.path.insert(0, str(HERE))
    import office
    key = office.load_key(off)

    def badge(bid, role):
        line = office.make_line(key, {"ID": bid, "NAME": "TEST", "ROLE": role, "KIND": "SESSION", "SHIFT": "T1", "SLOT": "DAY", "ISSUED": "1"})
        return {"id": bid, "line": line, "role": role, "name": "TEST"}

    mgr, emp, old = badge("MGR-1", "MANAGER"), badge("EMP-1", "BUILDER"), badge("MGR-0", "MANAGER")
    fdr, fake = badge("FDR-1", "FOUNDER"), badge("EMP-2", "FOUNDER")
    roster = {"v": 1, "manager": "MGR-1", "founder": "FDR-1", "badges": {b["id"]: b for b in (mgr, emp, old, fdr, fake)}}
    office.write_roster(off, roster)
    asset, log = root / "docs" / "flow" / "road.graph.json", root / "docs" / "flow" / "road.edits.jsonl"

    def run(*args, by=None, at=None, **more_env):
        cmd = [sys.executable, str(FLOW), f"--root={at or root}", *args] + (["--by", by] if by else [])
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", env={**os.environ, **more_env})
        return r.returncode, r.stdout + r.stderr

    def edges():
        return {f"{e['from']}>{e['to']}": e for e in json.loads(asset.read_text(encoding="utf-8"))["edges"]}

    G = ("graph",)
    rc, out = run(*G, "verify")
    check("verify before the seed is ok", rc == 0 and "no graph asset yet" in out, out)
    rc, out = run(*G, "seed", by=emp["line"])
    check("a crew badge cannot seed", rc == 3 and "may read the graph but not edit" in out and not asset.exists(), out)
    rc, out = run(*G, "seed")
    check("no badge cannot seed", rc == 3 and "needs the manager's badge" in out, out)
    rc, out = run(*G, "seed", by=mgr["line"][:-1] + ("A" if mgr["line"][-1] != "A" else "B"))
    check("a changed badge line cannot seed", rc == 3 and "signature does not match" in out, out)
    rc, out = run(*G, "seed", by=old["line"])
    check("a manager badge that is not the roster's manager cannot seed", rc == 3 and "only the manager" in out, out)
    rc, out = run(*G, "seed", by=mgr["line"])
    check("the manager seeds", rc == 0 and asset.exists() and log.exists(), out)
    e = edges()
    check("the seed carries the prose links", set(e) == {"M1>M2", "M2>M3", "D1>M2", "D2>M3", "R0>Beta", "R1>Beta", "Beta>1.0"}, str(sorted(e)))
    check("a seeded link is unconfirmed", all(x.get("seeded") for x in e.values()))
    check("a partial gate keeps its IDs", e["D2>M3"].get("ids") == ["APP-01"] and e["D2>M3"]["in"] == "gate")
    check("pins follow the types", (e["M1>M2"]["out"], e["M1>M2"]["in"]) == ("done", "after") and e["R0>Beta"]["out"] == "reached")
    rc, out = run(*G, "seed", by=mgr["line"])
    check("a second seed is refused", rc == 3 and "already seeded" in out, out)
    rc, out = run(*G, "verify")
    check("verify after the seed", rc == 0 and "graph ok" in out and "signatures not checked" not in out, out)

    for name, a, b, word in (("a loop", "M3", "M1", "loop"), ("decision to decision", "D1", "D2", "no link runs from a decision to a decision"),
                             ("a derived link", "M1", "R0", "Closes column"), ("an unknown node", "M1", "M77", "not a node"),
                             ("a lane", "M1", "G5", "not a node"), ("itself", "M1", "M1", "itself")):
        before = asset.read_bytes()
        rc, out = run(*G, "link", a, b, by=mgr["line"])
        check(f"link refused: {name}", rc == 3 and word in out and asset.read_bytes() == before, out)
    rc, out = run(*G, "link", "M1", "M3", "--ids", "APP-01", by=mgr["line"])
    check("--ids only on a decision's link", rc == 3 and "--ids narrows a decision" in out, out)
    rc, out = run(*G, "link", "M1", "M3", "--why", "needs the boot path", by=mgr["line"])
    check("the manager links", rc == 0 and "M1>M3" in edges() and not edges()["M1>M3"].get("seeded"), out)
    rc, out = run(*G, "link", "M1", "M3", "--why", "needs the boot path", by=mgr["line"])
    check("the same link twice is refused", rc == 3 and "already linked" in out, out)
    rc, out = run(*G, "link", "M1", "M2", by=emp["line"])
    check("a crew badge cannot link", rc == 3 and "may read the graph" in out, out)
    rc, out = run(*G, "confirm", "M1", "M2", "--why", "M2 boots from M1's image", by=mgr["line"])
    check("confirm clears seeded", rc == 0 and "seeded" not in edges()["M1>M2"] and edges()["M1>M2"]["why"].startswith("M2 boots"), out)
    rc, out = run(*G, "confirm", "M1", "M2", "--why", "M2 boots from M1's image", by=mgr["line"])
    check("confirm twice is refused", rc == 3, out)
    rc, out = run(*G, "link", "Q1", "Q2", by=mgr["line"])
    check("push blocks link by the map's shift", rc == 0 and edges()["Q1>Q2"]["out"] == "then", out)
    rc, out = run(*G, "link", "Q1", "M1", by=mgr["line"])
    check("a block runs a milestone", rc == 0 and (edges()["Q1>M1"]["out"], edges()["Q1>M1"]["in"]) == ("runs", "push"), out)
    rc, out = run(*G, "link", "Q9", "M1", by=mgr["line"])
    check("a block not in the shift is refused", rc == 3 and "not a node" in out, out)

    # the page's data: authored links with their pins, derived links marked, nothing drawn twice
    rc, out = run(f"--out={tmp / 'out'}", "build")
    page = (tmp / "out" / "workflow.html").read_text(encoding="utf-8") if (tmp / "out" / "workflow.html").is_file() else ""
    check("the page is named after the project and its goal", "<title>Fixture workflow</title>" in page and "the road to 1.0</h1>" in page, page[:300])
    check("build writes the page and graph.json", rc == 0 and (tmp / "out" / "graph.json").is_file() and 'id="gdata"' in (tmp / "out" / "workflow.html").read_text(encoding="utf-8"), out[-600:])
    if (tmp / "out" / "graph.json").is_file():
        gd = json.loads((tmp / "out" / "graph.json").read_text(encoding="utf-8"))
        ge = {f"{e['a']}>{e['b']}": e for e in gd["edges"]}
        types = {n["id"]: n["type"] for n in gd["nodes"]}
        check("graph.json: the asset is named and sound", gd["meta"]["asset"] and gd["meta"]["ok"], str(gd["meta"]))
        check("graph.json: the late stages and the first tier come from the profile", gd["meta"]["late"] == ["Beta", "1.0"] and gd["meta"]["tier"] == "P0", str(gd["meta"]))
        check("graph.json: node types", (types.get("M1"), types.get("D1"), types.get("R0"), types.get("Q1")) == ("milestone", "decision", "stage", "block"), str(types))
        check("graph.json: a confirmed link is firm, a seeded one is soft", ge["M1>M2"]["soft"] is False and ge["M2>M3"]["soft"] is True)
        check("graph.json: a partial gate is its own kind", ge["D2>M3"]["kind"] == "pgate" and ge["D1>M2"]["kind"] == "gate")
        check("graph.json: a feed is read at build", ge["M1>R0"]["kind"] == "feed" and ge["M1>R0"].get("derived") and ge["M1>R0"]["ids"] == ["BOOT-01"])
        check("graph.json: authored block links are not drawn twice", len(gd["edges"]) == len(ge) and not ge["Q1>Q2"].get("derived") and not ge["Q1>M1"].get("derived"))
        check("graph.json: a block's title still names its milestone", ge.get("Q2>M2", {}).get("derived") is True, str(sorted(ge)))
        check("graph.json: every link's ends are nodes", all(e["a"] in types and e["b"] in types for e in gd["edges"]))

    rc, out = run(*G, "node", "add", "M9", "--note", "later", by=mgr["line"])
    nodes = json.loads(asset.read_text(encoding="utf-8"))["nodes"]
    check("node add", rc == 0 and nodes.get("M9") == {"type": "milestone", "note": "later"}, out)
    rc, out = run(*G, "node", "add", "XYZ", by=mgr["line"])
    check("node add needs a type it can tell", rc == 3 and "--type" in out, out)
    rc, out = run(*G, "node", "rm", "M2", by=mgr["line"])
    check("node rm refused while linked", rc == 3 and "still has links" in out, out)
    rc, out = run(*G, "node", "rm", "M9", by=mgr["line"])
    check("node rm", rc == 0 and "M9" not in json.loads(asset.read_text(encoding="utf-8"))["nodes"], out)
    rc, out = run(*G, "undo", by=mgr["line"])
    check("undo puts the node back", rc == 0 and "M9" in json.loads(asset.read_text(encoding="utf-8"))["nodes"], out)
    rc, out = run(*G, "undo", by=mgr["line"])
    check("undo again takes it away", rc == 0 and "M9" not in json.loads(asset.read_text(encoding="utf-8"))["nodes"], out)
    rc, out = run(*G, "undo", by=emp["line"])
    check("a crew badge cannot undo", rc == 3, out)

    # the founder's badge edits like the manager's; the role alone, under a crew id, does not
    rc, out = run(*G, "node", "add", "M7", "--note", "the founder's", by=fake["line"])
    check("a FOUNDER role under a crew id is refused", rc == 3 and "may read the graph but not edit" in out, out)
    rc, out = run(*G, "node", "add", "M7", "--note", "the founder's", by=fdr["line"])
    check("the founder's badge edits", rc == 0 and "by FDR-1" in out and "M7" in json.loads(asset.read_text(encoding="utf-8"))["nodes"], out)
    rc, out = run(*G, "node", "rm", "M7", by=fdr["line"])
    check("the founder's badge removes its node", rc == 0, out)
    rc, out = run(*G, "verify")
    check("the founder's edits are signed like the manager's", rc == 0 and "graph ok" in out and "by FDR-1" in out, out)

    # a freeze of the main checkout holds every edit, the manager's too; reading goes on
    now = time.time()
    (off / "freeze.json").write_text(json.dumps({"by": "MGR-1", "why": "counted run of G1", "at": now}), encoding="utf-8")
    before = asset.read_bytes(), log.read_bytes()
    for name, args in (("link", ("link", "M2", "M3", "--why", "x")), ("unlink", ("unlink", "M1", "M2")), ("confirm", ("confirm", "M2", "M3")),
                       ("node add", ("node", "add", "M8")), ("node set", ("node", "set", "M1", "--note", "n")), ("node rm", ("node", "rm", "M3")),
                       ("undo", ("undo",)), ("seed", ("seed",))):
        rc, out = run(*G, *args, by=mgr["line"])
        check(f"graph {name} during the manager's freeze is refused: exit 3, who froze, why, and how to see it",
              rc == 3 and "MGR-1" in out and "counted run of G1" in out and "freeze show" in out
              and len(out.strip().splitlines()) == 1 and (asset.read_bytes(), log.read_bytes()) == before, out)
    rc, out = run(*G, "node", "add", "M8", by=fdr["line"])
    check("the founder's badge is held by the freeze too", rc == 3 and "freeze" in out, out)
    rc, out = run(*G, "node", "add", "M8", by=emp["line"])
    check("a crew badge is refused for its badge first, freeze or not", rc == 3 and "may read the graph but not edit" in out, out)
    for args in (("show",), ("show", "M3"), ("trace", "M3"), ("verify",)):
        rc, out = run(*G, *args)
        check(f"graph {' '.join(args)} is never refused by a freeze", rc == 0 and "freeze" not in out, out)
    (off / "freeze.json").write_text("{not json", encoding="utf-8")
    rc, out = run(*G, "node", "add", "M8", by=mgr["line"])
    check("a freeze file that cannot be read is a freeze", rc == 3 and "freeze" in out and (asset.read_bytes(), log.read_bytes()) == before, out)
    (off / "freeze.json").unlink()
    rig = {"FOUNDRY_RESOURCE_NAME": "the test rig"}
    for qid in ("MGR-1-sweep", "MGR-1-counted-G1"):
        (off / "rq.queue.json").write_text(json.dumps([{"id": qid, "job": "counted", "prio": 0, "all": True, "at": now, "beat": now}]), encoding="utf-8")
        rc, out = run(*G, "node", "add", "M8", by=mgr["line"], **rig)
        check(f"an edit while {qid} is in the queue is refused, and names it",
              rc == 3 and qid in out and "rq.py" in out and (asset.read_bytes(), log.read_bytes()) == before, out)
    (off / "rq.queue.json").write_text("{not json", encoding="utf-8")
    rc, out = run(*G, "node", "add", "M8", by=mgr["line"], **rig)
    check("a queue that cannot be read cannot rule a freeze out: the edit is refused", rc == 3 and "could not be read" in out, out)
    (off / "rq.queue.json").write_text(json.dumps([{"id": "EMP-4", "job": "unit tests", "prio": 5, "at": now, "beat": now}]), encoding="utf-8")
    rc, out = run(*G, "node", "add", "M8", by=mgr["line"], **rig)
    check("a plain job in the queue is no freeze: the edit goes on", rc == 0 and "M8" in json.loads(asset.read_text(encoding="utf-8"))["nodes"], out)
    (off / "rq.queue.json").unlink()
    rc, out = run(*G, "node", "rm", "M8", by=mgr["line"])
    check("with the freeze lifted and the queue clear the manager edits again", rc == 0, out)
    # a checkout that is not the main one (a worktree) is not frozen: the freeze holds the main checkout only
    (off / "freeze.json").write_text(json.dumps({"by": "MGR-1", "why": "counted run of G1", "at": now}), encoding="utf-8")
    side = tmp / "side"
    shutil.copytree(root, side)
    rc, out = run(*G, "node", "add", "M8", by=mgr["line"])
    check("the main checkout is held", rc == 3, out)
    rc, out = run(*G, "node", "add", "M8", by=mgr["line"], at=side, FOUNDRY_ROOT=str(side))
    check("a checkout that is not the main one is not frozen", rc == 0 and "M8" in json.loads(
        (side / "docs" / "flow" / "road.graph.json").read_text(encoding="utf-8"))["nodes"], out)
    (off / "freeze.json").unlink()

    # reading is open: no badge
    rc, out = run(*G, "show", "M3")
    check("show a node", rc == 0 and "in pins: after, gate, push" in out and "M1.done → M3.after" in out and "UNCONFIRMED" in out, out)
    rc, out = run(*G, "trace", "M3", "--up")
    check("trace up", rc == 0 and all(x in out for x in ("M2.done → M3.after", "M1.done → M2.after", "D1.decides → M2.gate")) and "waiting on" not in out, out)
    rc, out = run(*G, "trace", "M1", "--down")
    check("trace down", rc == 0 and "M2.done → M3.after" in out and "Beta" not in out, out)

    # flow.py's model reads the asset, and keeps the prose only as a note
    rc, out = run("edges")
    check("edges reads the asset", rc == 0 and any(l.startswith("M3") and "after M2,M1" in l.replace("M1,M2", "M2,M1") for l in out.splitlines()), out)
    check("edges says the graph is ok", "GRAPH graph ok" in out, out)
    rc, _ = run(*G, "unlink", "M2", "M3", by=mgr["line"])
    rc2, out = run("edges")
    m3 = next(l for l in out.splitlines() if l.startswith("M3"))
    check("an unlinked dependency leaves the model", rc == 0 and "after M1 " in m3, m3)
    check("the prose that lost its link is a note", "NOTE ROADMAP.md's prose names M2 before M3" in out, out)
    rc, _ = run(*G, "unlink", "D1", "M2", by=mgr["line"])
    rc2, out = run("edges")
    check("an unlinked gate leaves the model", rc == 0 and any(l.startswith("D1") and l.rstrip().endswith("-> -") for l in out.splitlines()), out)

    # drift: the roadmap gains a milestone the graph does not know
    (root / "docs" / "ROADMAP.md").write_text(ROADMAP.replace("| M3 | Apps", "| M4 | New | APP-01 | After M3 |\n| M3 | Apps"), encoding="utf-8")
    rc, out = run("edges")
    check("a new milestone without a node is flagged", "WARN M4 is a milestone" in out and "graph node add M4" in out, out)
    (root / "docs" / "ROADMAP.md").write_text(ROADMAP, encoding="utf-8")

    # a new manager: the old line stops working
    roster["manager"] = "MGR-0"
    office.write_roster(off, roster)
    rc, out = run(*G, "node", "add", "M9", by=mgr["line"])
    check("the manager before is refused", rc == 3 and "only the manager" in out, out)
    rc, out = run(*G, "node", "add", "M9", by=old["line"])
    check("the manager now edits", rc == 0, out)
    roster["badges"]["MGR-0"]["revoked"] = 1700000000
    office.write_roster(off, roster)
    rc, out = run(*G, "node", "rm", "M9", by=old["line"])
    check("a revoked badge is refused", rc == 3 and "revoked" in out, out)
    roster["badges"]["MGR-0"].pop("revoked")
    roster["manager"] = "MGR-1"
    office.write_roster(off, roster)

    # a hand edit shows
    good_asset, good_log = asset.read_text(encoding="utf-8"), log.read_text(encoding="utf-8")
    asset.write_text(good_asset.replace('"needs the boot path"', '"because"'), encoding="utf-8")
    rc, out = run(*G, "verify")
    check("a hand edit of the asset is TAMPERED", rc == 1 and "TAMPERED" in out and "changed outside flow.py graph" in out, out)
    rc, out = run(*G, "node", "add", "M8", by=mgr["line"])
    check("no edit lands on a tampered asset", rc == 3 and "does not match its edit log" in out, out)
    rc, out = run("edges")
    check("the model flags a tampered asset", "WARN TAMPERED" in out, out)
    asset.write_text(good_asset.replace("\n", "\r\n"), encoding="utf-8", newline="")
    rc, out = run(*G, "verify")
    check("line endings alone are not a change", rc == 0, out)
    asset.write_text(good_asset, encoding="utf-8", newline="\n")
    log.write_text(good_log.replace('"by": "MGR-1"', '"by": "MGR-7"', 1), encoding="utf-8", newline="\n")
    rc, out = run(*G, "verify")
    check("a hand edit of the log is TAMPERED", rc == 1 and "TAMPERED" in out, out)
    lines = good_log.splitlines()
    log.write_text("\n".join(lines[:1] + lines[2:]) + "\n", encoding="utf-8", newline="\n")
    rc, out = run(*G, "verify")
    check("a dropped log entry is TAMPERED", rc == 1 and "TAMPERED" in out, out)
    log.write_text(good_log, encoding="utf-8", newline="\n")
    rc, out = run(*G, "verify")
    check("restored files verify", rc == 0, out)
    log.unlink()
    rc, out = run(*G, "verify")
    check("an asset with no log is not ok", rc == 1 and "no edit log" in out, out)

    # hand-in: a crew branch that changes the graph is sent back; the manager's is not (identity by env, no git config)
    repo = tmp / "repo"
    repo.mkdir()
    genv = {**{k: v for k, v in os.environ.items() if not k.startswith("GIT_")},
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid", "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@example.invalid", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}

    def git(*args):
        return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, env=genv)

    git("init", "-q", "-b", "main")
    (repo / "a.txt").write_text("a\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "base")
    git("checkout", "-q", "-b", "job")
    (repo / "docs" / "flow").mkdir(parents=True)
    (repo / "docs" / "flow" / "road.graph.json").write_text("{}\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "a hand edit")
    c = office.crew(off, 1700000000.0)
    bad, _, _ = office.handin_checks({"id": "EMP-1", "role": "BUILDER", "files": ""}, repo, "main", [], c)
    check("hand-in sends back a crew branch that changes the graph", any("only the manager edits it" in b for b in bad), str(bad))
    bad, _, _ = office.handin_checks({"id": "MGR-1", "role": "MANAGER", "files": ""}, repo, "main", [], c)
    check("hand-in lets the manager's graph commit through", not any("only the manager edits it" in b for b in bad), str(bad))

    if FAILS:  # keep the scratch folder only when a failure needs reading
        print(f"flow graph tests: {len(FAILS)} failed (scratch kept: {tmp})")
        return 1

    def _writable(func, path, _exc):  # git marks its objects read-only on Windows
        os.chmod(path, 0o700)
        func(path)

    # onexc from Python 3.12 (onerror is deprecated there); onerror before it
    shutil.rmtree(tmp, **({"onexc": _writable} if sys.version_info >= (3, 12) else {"onerror": _writable}))
    print("flow graph tests: all ok")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
