#!/usr/bin/env python3
"""Tests for tools/plan_flow.py: `python tests/test_plan_flow.py`. A plan started by `new` must hold no problem
and build a page; every plan in the tree must hold no problem; a plan with a mistake must be told so; and the
commands must refuse what they cannot do. Everything is written under a scratch folder, never the tree."""
import contextlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

for _k in [k for k in os.environ if k.startswith("FOUNDRY_")]:
    os.environ.pop(_k)
_OFFICE = tempfile.mkdtemp(prefix="planflow-office-")  # no badge here: the real office is never asked
os.environ["FOUNDRY_PATHS_OFFICE"] = str(Path(_OFFICE) / "none")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import plan_flow  # noqa: E402

FAILS = []
PLAN = '''[meta]
title = "Scratch"
buys = ["one gain"]
[[section]]
title = "More"
text = "a paragraph"
[[stage]]
id = "S1"
title = "one"
[[stage]]
id = "S2"
title = "two"
[[step]]
id = "A1"
stage = "S1"
title = "first"
state = "new"
effort = "S"
confidence = "estimate"
[[step]]
id = "A2"
stage = "S2"
title = "second"
state = "have"
effort = "M"
confidence = "read"
needs = ["A1"]
[[decision]]
id = "Q1"
title = "q"
gates = ["S2"]
[[lane]]
id = "L1"
of = "S2"
title = "lane"
checks = ["a control"]
'''


def check(name, cond, got=None):
    if not cond:
        FAILS.append(name)
        print(f"FAIL {name}" + (f": {got!r}" if got is not None else ""))


def call(root, *argv):
    """(exit code, stdout, stderr) of one plan_flow command on a scratch root."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = plan_flow.main(list(argv), root)
    return code, out.getvalue(), err.getvalue()


def top_names(js):
    """The names a script declares at the start of a line: const/let/var declarators and functions. The page script
    is one closure of three pieces, so a name two pieces declare stops the whole page (no node on this host to ask)."""
    names = []
    for line in js.splitlines():
        m = re.match(r"(?:const|let|var)\s+(.*)", line)
        if m:
            depth, quote, part, parts = 0, "", "", []
            for ch in m[1]:
                if quote:
                    quote = "" if ch == quote else quote
                elif ch in "'\"`":
                    quote = ch
                elif ch in "([{":
                    depth += 1
                elif ch in ")]}":
                    depth -= 1
                elif ch == "," and depth == 0:
                    parts.append(part)
                    part = ""
                    continue
                elif ch == ";" and depth == 0:
                    break
                part += ch
            names += [n[1] for n in (re.match(r"\s*([A-Za-z_$][\w$]*)\s*(?:=|$)", p) for p in parts + [part]) if n]
        m = re.match(r"function\s+([A-Za-z_$][\w$]*)", line)
        if m:
            names.append(m[1])
    return names


def has(bad, word):
    return any(word in line for line in bad)


def main():
    for name in plan_flow.plan_names(plan_flow.HERE):
        bad = plan_flow.chart(name)["model"](plan_flow.HERE)[2]
        check(f"the tree's plan '{name}' has no problem", not bad, bad)

    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        check("list on an empty tree says how to start", "new NAME" in call(root, "list")[1])
        code, out, _ = call(root, "selftest")
        check("selftest with no plan checks the template and passes", code == 0 and "the template" in out and "0 problems" in out, out)
        check("build with no plan fails", call(root, "build", f"--out={root / 'page'}")[0] == 1)
        check("new needs a title", call(root, "new", "demo")[0] == 2)
        check("new refuses a taken name", call(root, "new", "os", "--title=x")[0] == 2)
        check("new refuses a name that is not a slug", call(root, "new", "../x", "--title=x")[0] == 2)
        code, out, _ = call(root, "new", "demo", '--title=A "quoted" plan', "--question=Why?")
        path = root / "docs" / "flow" / "demo.plan.toml"
        check("new writes the plan", code == 0 and path.is_file(), out)
        check("new never overwrites", call(root, "new", "demo", "--title=other")[0] == 1 and 'A \\"quoted\\" plan' in path.read_text(encoding="utf-8"))
        code, out, _ = call(root, "selftest", "demo")
        check("a new plan passes its selftest", code == 0 and "0 problems" in out, out)
        code, out, _ = call(root, "list")
        check("list names the plan and its title", code == 0 and 'demo' in out and 'A "quoted" plan' in out, out)
        code, out, _ = call(root, "build", "demo", f"--out={root / 'page'}")
        page = root / "page" / "demo.html"
        check("build writes the page and the graph", code == 0 and page.is_file() and (root / "page" / "demo.graph.json").is_file(), out)
        check("the page names its plan file and its command", "docs/flow/demo.plan.toml" in page.read_text(encoding="utf-8") and "plan_flow.py show demo" in page.read_text(encoding="utf-8"))
        check("build writes nothing beside --out", not (root / "out").exists())

        path.write_text(PLAN, encoding="utf-8", newline="\n")
        nodes, edges, bad, meta = plan_flow.chart("demo")["model"](root)
        check("a full plan has no problem", not bad, bad)
        check("the stages are chained", any(e["a"] == "S1" and e["b"] == "S2" and e["kind"] == "then" for e in edges))
        check("a decision gates its stage", any(e["a"] == "Q1" and e["b"] == "S2" and e["kind"] == "gate" for e in edges))
        check("a lane closes its stage", any(e["a"] == "S2" and e["b"] == "L1" and e["kind"] == "sub" for e in edges))
        check("the first panel's sections are read", [s["title"] for s in meta["sections"]] == ["What it buys", "More"], meta["sections"])
        check("trace up finds what comes first", plan_flow.traced(edges, "A2", True) == ["A1"], plan_flow.traced(edges, "A2", True))
        check("trace down finds what follows", plan_flow.traced(edges, "S1", False) == ["S2", "L1"], plan_flow.traced(edges, "S1", False))
        code, out, _ = call(root, "trace", "demo", "A2", "--up")
        check("trace prints one line a way", code == 0 and out.strip() == "before A2 (1): A1", out)
        code, out, _ = call(root, "show", "demo", "Q1")
        check("show prints a node with its links", code == 0 and "decision Q1" in out and "goes out: S2" in out, out)
        check("show of an unknown id fails", call(root, "show", "demo", "ZZ")[0] == 2)
        check("an unknown plan fails", call(root, "show", "nope", "A1")[0] == 2)
        check("an unknown command fails", call(root, "paint", "demo")[0] == 2)
        check("edges prints every link", call(root, "edges", "demo")[1].count("->") == len(edges))

        for name, text, word in (
                ("a table with no id", PLAN + '[[step]]\nstage = "S1"\n', "has no id"),
                ("needs that is not a list", PLAN.replace('needs = ["A1"]', 'needs = "A1"'), "must be a list"),
                ("an unknown need", PLAN.replace('needs = ["A1"]', 'needs = ["ZZ"]'), "not a step"),
                ("a gate on no stage", PLAN.replace('gates = ["S2"]', 'gates = ["S9"]'), "not a stage"),
                ("a lane of no stage", PLAN.replace('of = "S2"', 'of = "S9"'), "is not a stage"),
                ("a roadmap row that is not there", PLAN.replace('gates = ["S2"]', 'gates = ["S2"]\nroadmap = "D99"'), "no D99 row"),
                ("an anchor whose file is gone", PLAN.replace('needs = ["A1"]', 'needs = ["A1"]\nanchor = ["no/such/file", "x"]'), "is gone"),
                ("a plan with no stage", '[meta]\ntitle = "t"\n', "no stage"),
                ("a plan that is not TOML", "[[stage", "not TOML")):
            path.write_text(text, encoding="utf-8", newline="\n")
            bad = plan_flow.chart("demo")["model"](root)[2]
            check(f"{name} is reported", has(bad, word), bad)
        check("a selftest with a problem exits 1", call(root, "selftest", "demo")[0] == 1)
        check("a selftest of every plan exits 1 when one fails", call(root, "selftest")[0] == 1)

        # the main checkout takes a new plan or a page from the manager's badge only
        real = plan_flow.flow.main_root
        plan_flow.flow.main_root = lambda: root
        try:
            path.unlink()
            code, _, err = call(root, "new", "demo", "--title=x")
            check("new in the main checkout needs the manager's badge", code == 2 and "--by" in err and not path.exists(), err)
            code, _, err = call(root, "new", "demo", "--title=x", "--by=not a badge line")
            check("new in the main checkout refuses a line that is no badge", code == 2 and not path.exists(), err)
            path.write_text(PLAN, encoding="utf-8", newline="\n")
            code, _, err = call(root, "build", "demo")
            check("build into the main checkout's out/ needs the badge", code == 2 and "--out" in err and not (root / "out").exists(), err)
            code, _, err = call(root, "build", "demo", f"--out={root / 'out' / 'flow'}")
            check("an --out that points into the main checkout needs the badge too", code == 2 and not (root / "out").exists(), err)
            code, _, err = call(root, "build", "demo", f"--out={root / 'docs' / 'pages'}")
            check("an --out anywhere in the main checkout needs the badge", code == 2 and not (root / "docs" / "pages").exists(), err)
            with tempfile.TemporaryDirectory() as other:
                check("build with an --out outside the main checkout is anyone's", call(root, "build", "demo", f"--out={Path(other) / 'page'}")[0] == 0)
            check("reading in the main checkout is anyone's", call(root, "show", "demo", "A1")[0] == 0 and call(root, "selftest", "demo")[0] == 0)
            check("in_main: the checkout, a file in it, a folder not made yet", all(plan_flow.in_main(p) for p in (root, path, root / "a" / "b")))
            check("in_main: a folder beside it is not", not plan_flow.in_main(root.parent / "elsewhere"))

            # the manager's badge passes the first gate; the freeze is the second
            real_manager, real_frozen = plan_flow.flow_graph.manager, plan_flow.frozen
            plan_flow.flow_graph.manager = lambda by, office_dir=None: None
            try:
                path.unlink()
                office = root / "office"  # a scratch crew office: the real reader on real files, no stub
                real_frozen_fn = plan_flow.frozen
                plan_flow.frozen = lambda: real_frozen_fn(office)
                now = time.time()
                office.mkdir()
                (office / "rq.queue.json").write_text(json.dumps([{"id": "MGR-1-sweep", "job": "the sweep", "prio": 0, "at": now, "beat": now}]), encoding="utf-8")
                check("a project with no shared resource has no freeze", plan_flow.frozen() == ([], []), plan_flow.frozen())
                (office / "rq.queue.json").unlink()
                office.rmdir()
                os.environ["FOUNDRY_RESOURCE_NAME"] = "the test rig"  # from here on the project has a queue to freeze on

                def queue(*entries):
                    (office / "rq.queue.json").write_text(json.dumps([dict(e, at=now, beat=now) for e in entries]), encoding="utf-8")

                def new_refused(word):
                    code, _, err = call(root, "new", "demo", "--title=x")
                    return code == 2 and word in err and not path.exists(), err

                check("no crew office folder: new is refused", *new_refused("could not be read"))
                office.mkdir()
                check("an office with no queue file is a clear queue", plan_flow.frozen() == ([], []), plan_flow.frozen())
                (office / "rq.queue.json").write_text("{not json", encoding="utf-8")
                check("a mangled queue file: new is refused", *new_refused("could not be read"))
                (office / "rq.queue.json").write_text('{"a": 1}', encoding="utf-8")
                check("a queue file that is not a list: new is refused", *new_refused("could not be read"))
                (office / "rq.lock").mkdir()
                queue()
                check("a held seat whose lock names nobody: new is refused", *new_refused("could not be read"))
                (office / "rq.lock").rmdir()
                queue({"id": "MGR-1-counted-G1", "job": "counted G1", "prio": 0, "all": True})
                check("a counted run in the queue: new is refused, badge or not", *new_refused("MGR-1-counted-G1"))
                code, _, err = call(root, "build", "no-such-plan", f"--out={root / 'docs' / 'pages'}")
                check("a build into the main checkout's tracked folders is refused during a freeze", code == 2 and "freeze" in err, err)
                queue({"id": "EMP-9", "job": "a run", "prio": 0, "all": True})
                check("a prio-0 job under a plain id is a counted run too", *new_refused("EMP-9 (prio 0)"))
                queue({"id": "MGR-1-sweep", "job": "the sweep", "prio": 1})
                path.write_text(PLAN, encoding="utf-8", newline="\n")
                code, out, err = call(root, "build", "demo")
                check("the manager's build into out/ goes on during a freeze", code == 0 and (root / "out" / "flow" / "demo.html").is_file(), err)
                path.unlink()
                queue({"id": "MGR-1-ci", "job": "ci on main", "prio": 1, "all": True})
                code, _, err = call(root, "new", "demo", "--title=x")
                check("a whole-resource job under a plain id gets a note, and the write goes on", code == 0 and "MGR-1-ci" in err and "COUNTED?" in err and path.is_file(), err)
                path.unlink()
                queue({"id": "EMP-3", "job": "dev run 4", "prio": 5, "all": True}, {"id": "EMP-4", "job": "unit tests", "prio": 5})
                code, _, err = call(root, "new", "demo", "--title=x")
                check("a dev run and a one-seat job are no freeze and no note", code == 0 and not err and path.is_file(), err)

                # a link left at the page's name is replaced, never written through
                elsewhere = root / "elsewhere.html"
                elsewhere.write_text("not a page", encoding="utf-8")
                page = root / "out" / "flow" / "demo.html"
                page.unlink()
                try:
                    os.link(elsewhere, page)
                except OSError:
                    page = None
                if page:
                    path.write_text(PLAN, encoding="utf-8", newline="\n")
                    code, _, err = call(root, "build", "demo")
                    check("a build replaces a hardlink at the page's name", code == 0 and elsewhere.read_text(encoding="utf-8") == "not a page" and "<script>" in page.read_text(encoding="utf-8"), err)
                check("a build leaves no temp file", not list((root / "out" / "flow").glob("*.tmp")))
            finally:
                plan_flow.flow_graph.manager, plan_flow.frozen = real_manager, real_frozen
                os.environ.pop("FOUNDRY_RESOURCE_NAME", None)

            # a chart with facts of its own (a project's reader) registers in CHARTS and is reached by its name
            path.write_text(PLAN, encoding="utf-8", newline="\n")
            rel = plan_flow.PLANS / "demo.plan.toml"
            plan_flow.CHARTS["demo"] = {"name": "demo", "plan": rel, "render": plan_flow.render,
                                        "model": lambda r: plan_flow.build_model(r, r / rel, "demo", bad=["a fact of its own is off"], then="its own order")}
            try:
                code, out, _ = call(root, "selftest", "demo")
                check("a registered chart's own facts reach the selftest", code == 1 and "PROBLEM a fact of its own is off" in out, out)
                check("a registered chart's own words reach the links", "its own order" in call(root, "edges", "demo")[1])
            finally:
                plan_flow.CHARTS.clear()
            check("without the registered chart the plan is clean again", call(root, "selftest", "demo")[0] == 0)
        finally:
            plan_flow.flow.main_root = real

    # in_main by git's own answer: a worktree under the main checkout's folder is its own checkout
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.invalid", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.invalid",
               GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    with tempfile.TemporaryDirectory() as d:
        repo = Path(d) / "repo"
        wt = repo / ".claude" / "worktrees" / "w"

        def git(*args):
            return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, env=env).returncode

        repo.mkdir()
        ok = git("init", "-q") == 0 and git("commit", "-q", "--allow-empty", "-m", "one") == 0 and git("worktree", "add", "-q", "-b", "w", str(wt)) == 0
        check("the scratch repository and its worktree were made", ok)
        if ok:
            real = plan_flow.flow.main_root
            plan_flow.flow.main_root = lambda: repo
            try:
                check("git: the main checkout and a folder in it are in main", plan_flow.in_main(repo) and plan_flow.in_main(repo / "out" / "flow"))
                check("git: a worktree under the main checkout's folder is not", not plan_flow.in_main(wt) and not plan_flow.in_main(wt / "out" / "flow"))
                check("git: a folder outside is not", not plan_flow.in_main(Path(d) / "other"))
                unc = "\\\\localhost\\" + str(repo).replace(":", "$", 1)
                if os.name == "nt" and os.path.isdir(unc):
                    check("the main checkout by its UNC name is still the main checkout", plan_flow.in_main(unc + "\\out\\x") and plan_flow.under(unc + "\\out\\x", repo / "out"), unc)
                    check("the worktree by its UNC name is still not", not plan_flow.in_main(unc + "\\.claude\\worktrees\\w\\out"))
            finally:
                plan_flow.flow.main_root = real
            git("worktree", "remove", "--force", str(wt))

    shared, mine = top_names(plan_flow.flow_page.js("")), top_names(plan_flow.P_JS)
    check("the name scan reads the shared script", {"W", "esc", "row", "S"} <= set(shared), shared)
    check("the name scan reads the plan profile", {"PINS", "P", "WORDS", "asks"} <= set(mine), mine)
    check("the plan profile declares no name the shared page script has", not set(shared) & set(mine), sorted(set(shared) & set(mine)))
    check("the scan would catch a clash", "W" in top_names(plan_flow.P_JS.replace("WORDS", "W")))
    check("the profile declares no name twice", len(mine) == len(set(mine)), mine)
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "docs" / "flow").mkdir(parents=True)
        (root / "docs" / "flow" / "demo.plan.toml").write_text(PLAN.replace('id = "A1"', 'id = "A\\"1"', 1).replace('needs = ["A1"]', 'needs = ["A\\"1"]'), encoding="utf-8", newline="\n")
        code, out, _ = call(root, "build", "demo", f"--out={root / 'page'}")
        html = (root / "page" / "demo.html").read_text(encoding="utf-8") if code == 0 else ""
        check("the page holds one script", html.count("<script>") == 1, html.count("<script>"))
        check("a quote in a step's id stays inside its attribute", 'placeholder="Find a node (A&quot;1,' in html, re.findall(r'placeholder="[^>]*', html))

    print(f"plan flow tests: {'FAIL ' + str(len(FAILS)) if FAILS else 'ok'}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
