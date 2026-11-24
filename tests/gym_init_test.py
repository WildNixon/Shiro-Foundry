#!/usr/bin/env python3
"""Tests for tools/gym_init.py and the gym it starts: `python tests/gym_init_test.py`.

A scratch project in a temp folder gets a gym from `init`; the gym's own selftest, a dev run and two counted runs
go through its run.py; and lanes_for.py, board.py and flow.py read the result as they would in a real project.
Every command runs as its own process with FOUNDRY_ROOT and FOUNDRY_MAIN on the scratch project and a git identity
given by environment variables. Nothing is written outside the temp folder.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TOOLS = REPO / "tools"
PY = sys.executable
FAILS = []
WORDS = ("PASS", "MARGINAL", "FAIL", "MEASURING", "STARVED", "VOID", "SATURATED")
RUN_ID = re.compile(r"20\d{6}-\d{6}-[0-9a-f]{4}")


def check(name, cond, got=None):
    if not cond:
        FAILS.append(name)
        print(f"FAIL {name}" + (f": {str(got)[-900:]}" if got is not None else ""))


class Project:
    """A scratch project: a git repository with the example roadmap and out/ ignored."""

    def __init__(self, base, name="proj", **more_env):
        self.root = base / name
        self.root.mkdir()
        env = {k: v for k, v in os.environ.items() if not k.startswith(("FOUNDRY_", "GIT_", "GYM_"))}
        self.office = base / f"office-{name}"  # the crew office, named outside the project so its tree stays clean
        env.update(FOUNDRY_ROOT=str(self.root), FOUNDRY_MAIN=str(self.root), FOUNDRY_PATHS_OFFICE=str(self.office),
                   PYTHONDONTWRITEBYTECODE="1",
                   GIT_AUTHOR_NAME="gym-test", GIT_AUTHOR_EMAIL="gym-test@example.invalid", GIT_COMMITTER_NAME="gym-test",
                   GIT_COMMITTER_EMAIL="gym-test@example.invalid", GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        scratch = base / "tmp"  # the kit's selftest keeps its temp files: they stay inside this test's folder
        scratch.mkdir(exist_ok=True)
        env.update(TMP=str(scratch), TEMP=str(scratch), TMPDIR=str(scratch))
        env.update(more_env)
        self.env = env
        (self.root / ".gitignore").write_text("out/\n", encoding="utf-8", newline="\n")
        (self.root / "docs").mkdir()
        shutil.copy(REPO / "profile" / "ROADMAP.example.md", self.root / "docs" / "ROADMAP.md")
        self.git_ok = self.git("init", "-q", "-b", "main")[0] == 0
        self.commit("base")

    def run(self, *args):
        """(exit code, stdout + stderr) of one command in the project's folder."""
        try:
            r = subprocess.run([str(a) for a in args], cwd=str(self.root), env=self.env, capture_output=True, text=True,
                               encoding="utf-8", errors="replace", timeout=600)
        except OSError as e:
            return 127, str(e)
        return r.returncode, (r.stdout or "") + (r.stderr or "")

    def git(self, *args):
        return self.run("git", "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false", *args)

    def commit(self, message):
        self.git("add", "-A")
        return self.git("commit", "-q", "-m", message)[0] == 0

    def tool(self, name, *args, **more_env):
        if not more_env:
            return self.run(PY, TOOLS / name, *args)
        kept, self.env = self.env, {**self.env, **more_env}
        try:
            return self.run(PY, TOOLS / name, *args)
        finally:
            self.env = kept

    def freeze(self, on=True, queue=None):
        """Set or lift the manager's freeze in the scratch office (the file office.py's freeze_facts reads), or
        leave a queue of jobs waiting for the shared resource. With neither, the office folder is removed."""
        shutil.rmtree(self.office, ignore_errors=True)
        if not on and queue is None:
            return
        self.office.mkdir()
        now = time.time()
        if on:
            (self.office / "freeze.json").write_text(json.dumps({"by": "MGR-1", "why": "counted run of G1", "at": now}), encoding="utf-8")
        if queue is not None:
            (self.office / "rq.queue.json").write_text(json.dumps([dict(e, at=now, beat=now) for e in queue]), encoding="utf-8")

    def gym(self, *args, folder="gym"):
        return self.run(PY, self.root / folder / "run.py", *args)


def series(p, lane="G1", folder="gym"):
    return json.loads((p.root / folder / "series" / f"{lane}.json").read_text(encoding="utf-8"))


def main():
    # the kit beside the templates is the gym skill's own
    kit, tkit = REPO / "skills" / "gym" / "scripts" / "gym_kit.py", REPO / "profile" / "gym" / "gym_kit.py"
    check("the template's gym_kit.py is the gym skill's, byte for byte", kit.read_bytes() == tkit.read_bytes())

    with tempfile.TemporaryDirectory(prefix="foundry-gym-test-") as td:
        base = Path(td).resolve()  # the folder's real name (macOS /var, a Windows 8.3 name), so paths compare
        p = Project(base)
        check("the scratch repository was made", p.git_ok and p.git("rev-parse", "HEAD")[0] == 0)
        gym = p.root / "gym"

        code, out = p.tool("board.py", "check")
        check("before init the board says there is no gym yet", "no gym yet" in out, out)
        code, out = p.tool("gym_init.py", "check")
        check("check with no gym exits 1 and says how to start", code == 1 and "init" in out, out)
        code, out = p.tool("gym_init.py", "lane", "add", "G2")
        check("lane add with no gym is refused", code == 2 and "init" in out and not gym.exists(), out)
        code, out = p.tool("gym_init.py", "init", "--lane", "Q1")
        check("init refuses a lane name the profile's pattern does not read", code == 2 and "lane_pattern" in out and not gym.exists(), out)

        # a freeze of the main checkout: init writes tracked files, so it is refused (exit 3); check only reads
        p.freeze()
        code, out = p.tool("gym_init.py", "init")
        check("init during the manager's freeze is refused: exit 3, one line naming who froze, why, and how to see it",
              code == 3 and not gym.exists() and "MGR-1" in out and "counted run of G1" in out and "freeze show" in out
              and len(out.strip().splitlines()) == 1, (code, out))
        code, out = p.tool("gym_init.py", "check")
        check("check is never refused by a freeze", code == 1 and "no gym yet" in out, (code, out))
        (p.office / "freeze.json").write_text("{not json", encoding="utf-8")
        code, out = p.tool("gym_init.py", "init")
        check("a freeze file that cannot be read is a freeze", code == 3 and not gym.exists() and "freeze" in out, (code, out))
        p.freeze(on=False, queue=[{"id": "MGR-1-sweep", "job": "the sweep", "prio": 0}])
        code, out = p.tool("gym_init.py", "init", FOUNDRY_RESOURCE_NAME="the test rig")
        check("init while a sweep waits for the shared resource is refused, and names it",
              code == 3 and not gym.exists() and "MGR-1-sweep" in out, (code, out))
        p.freeze(on=False, queue=[{"id": "MGR-1-counted-G1", "job": "counted G1", "prio": 0, "all": True}])
        code, out = p.tool("gym_init.py", "init", FOUNDRY_RESOURCE_NAME="the test rig")
        check("init while a counted run is in the queue is refused, and names it",
              code == 3 and not gym.exists() and "MGR-1-counted-G1" in out, (code, out))
        (p.office / "rq.queue.json").write_text("{not json", encoding="utf-8")
        code, out = p.tool("gym_init.py", "init", FOUNDRY_RESOURCE_NAME="the test rig")
        check("a queue that cannot be read cannot rule a freeze out: refused", code == 3 and not gym.exists() and "could not be read" in out, (code, out))
        p.freeze()
        wt = base / "wt"
        if p.git("worktree", "add", "-q", "-b", "wt", str(wt))[0] == 0:
            code, out = p.tool("gym_init.py", "init", FOUNDRY_ROOT=str(wt))
            check("a worktree is not the main checkout: init there goes on during the freeze",
                  code == 0 and (wt / "gym" / "run.py").is_file() and not gym.exists(), (code, out))
            p.git("worktree", "remove", "--force", str(wt))
            p.git("branch", "-D", "wt")
        else:
            check("the scratch worktree was made", False)
        p.freeze(on=False)

        code, out = p.tool("gym_init.py", "init")
        wrote = ["run.py", "gym_kit.py", "lane-inputs.toml", "README.md", "lanes/g1_example.py", "prereg/G1.json",
                 "contracts/G1-artifacts.md", "series/G1.json"]
        check("init writes the gym", code == 0 and all((gym / f).is_file() for f in wrote), out)
        check("init names every file it wrote", all(f"wrote gym/{f}" in out for f in wrote), out)
        check("init prints the profile lines to set", all(f"{k} = " in out for k in ("counted", "dev", "selftest")) and "gym/run.py counted <lane>" in out, out)
        measure = [line.strip() for line in out.splitlines() if re.match(r"\s+(counted|dev|selftest) = ", line)]
        check("the profile lines name plain `python`, not this host's interpreter path",
              measure == ["counted = 'python gym/run.py counted <lane>'", "dev = 'python gym/run.py dev <lane>'",
                          "selftest = 'python gym/run.py selftest'"], measure)
        text = (gym / "gym_kit.py").read_text(encoding="utf-8")
        check("the gym's gym_kit.py says where it came from, and is the skill's below the header",
              text.startswith("# Copied by") and "scripts/gym_kit.py" in text.splitlines()[0]
              and text.endswith(kit.read_text(encoding="utf-8")), text[:200])
        pre = json.loads((gym / "prereg" / "G1.json").read_text(encoding="utf-8"))
        check("the prereg is a template: not registered, no bar, no pin, a comment on how to pin",
              pre["status"].startswith("TEMPLATE") and pre["bars"][0]["threshold"] is None and pre["min_n"]["units"] is None
              and pre["contract"]["path"] == "" and pre["contract"]["sha256"] == "" and "sha256" in pre["contract"]["comment"], pre)
        check("the prereg template has every field the kit's template names",
              all(k in pre for k in ("prereg_id", "written_at", "written_before", "supersedes", "question", "unit_of_inference",
                                     "statistic", "estimator", "min_n", "bars", "controls", "decision_rule", "amendments")), sorted(pre))
        check("the contract template is a draft with the sections a builder fills",
              all(h in (gym / "contracts" / "G1-artifacts.md").read_text(encoding="utf-8")
                  for h in ("DRAFT", "## What is under test", "## The command", "## The artifacts", "## What a unit is", "## Amendments")))
        check("the example lane imports nothing of the project and has a selftest block",
              re.search(r'^if __name__ == "__main__":', (gym / "lanes" / "g1_example.py").read_text(encoding="utf-8"), re.M)
              and not re.search(r"^\s*(?:import|from)\s+(?!__future__|json|os|random|statistics|subprocess|sys|gym_kit)\w",
                                (gym / "lanes" / "g1_example.py").read_text(encoding="utf-8"), re.M))

        (gym / "README.md").write_text("mine\n", encoding="utf-8", newline="\n")
        (gym / "prereg" / "G1.json").unlink()
        code, out = p.tool("gym_init.py", "init")
        check("a second init keeps what is there, names it, and writes only what is missing",
              code == 0 and (gym / "README.md").read_text(encoding="utf-8") == "mine\n" and "kept  gym/README.md" in out
              and "wrote gym/prereg/G1.json" in out and "kept  gym/run.py" in out, out)
        (gym / "README.md").unlink()
        code, out = p.tool("gym_init.py", "init")
        check("init puts back a missing file", code == 0 and "wrote gym/README.md" in out and "The gym" in (gym / "README.md").read_text(encoding="utf-8"), out)
        code, out = p.tool("gym_init.py", "init")
        check("an init with nothing to write says so", code == 0 and "nothing written" in out and "wrote" not in out.replace("nothing written", ""), out)

        # the gym runs as it was written
        code, out = p.gym("selftest")
        check("the new gym's selftest passes", code == 0 and out.strip().endswith("gym selftest: ok") and "\n  FAIL " not in out, out)
        code, out = p.run(PY, gym / "lanes" / "g1_example.py")
        check("the lane file run alone runs its selftest", code == 0 and "want PASS" in out and "want VOID" in out, out)
        code, out = p.gym("list")
        check("run.py list names the lane", code == 0 and out.split()[:2] == ["G1", "g1_example"], out)
        code, out = p.gym("dev", "G1")
        runs = sorted((p.root / "out" / "gym" / "G1").iterdir()) if (p.root / "out" / "gym" / "G1").is_dir() else []
        check("a dev run writes a run folder whose id the board's pattern reads", len(runs) == 1 and RUN_ID.fullmatch(runs[0].name), out)
        dry = json.loads((runs[0] / "dry-grade.json").read_text(encoding="utf-8")) if runs else {}
        check("the dev run leaves a dry grade with the lane's word (MEASURING: the template registers no bar)",
              code == 1 and dry.get("dry") is True and dry.get("verdict") == "MEASURING" and dry.get("n") == 40
              and (runs[0] / "manifest.json").is_file() and (runs[0] / "samples.jsonl").is_file(), (code, out, dry))
        check("a dev run publishes nothing", series(p)["points"] == [] and not (gym / "grades").exists() and not (gym / "charts").exists())
        code, out = p.gym("dev", "G9")
        check("an unknown lane is refused", code == 2 and "unknown lane" in out, out)
        code, out = p.gym("nonsense")
        check("an unknown command prints the help and exits 2", code == 2 and "run.py counted <lane>" in out, out)

        # the Foundry's tools read it
        code, out = p.tool("lanes_for.py", "check")
        check("lanes_for.py check passes on the new gym", code == 0 and "lanes in run.py: 1; in the table: 1" in out and "lanes_for check: ok" in out, out)
        code, out = p.tool("lanes_for.py", "--files", "gym/lanes/g1_example.py")
        check("lanes_for.py selects the lane by its own file", code == 0 and out.startswith("G1"), out)
        code, out = p.tool("lanes_for.py", "--files", "gym/gym_kit.py")
        check("lanes_for.py selects the lane by an always path", code == 0 and out.startswith("G1"), out)
        code, out = p.tool("gym_init.py", "check")
        check("gym_init check passes, with the template as a note", code == 0 and "0 problem(s)" in out and "still a template" in out, out)
        code, out = p.tool("board.py", "check")
        check("the board no longer says there is no gym", "no gym yet" not in out and "progress map" in out, out)
        check("the board reads the gym's lane (its prereg, and no run yet)", "G1 has a prereg" in out and "G1 ran at" not in out, out)
        page = (p.root / "docs" / "progress-map.html").read_text(encoding="utf-8")
        check("the map lists the lane with no run yet", "1 lane with no run yet" in page and ">G1<" in page, re.findall(r"[^>]*no run yet[^<]*", page))

        # counted: refused until the prereg is registered and pins the contract, and the tree is clean
        (p.root / "docs" / "progress-map.html").unlink()
        check("the gym is committed", p.commit("the gym"))
        code, out = p.gym("counted", "G1")
        check("a counted run on the template prereg is refused", code == 2 and "still a template" in out, out)
        contract = gym / "contracts" / "G1-artifacts.md"
        contract.write_text(contract.read_text(encoding="utf-8").replace(" (DRAFT: a template, not yet a contract)", ""), encoding="utf-8", newline="\n")
        pre = json.loads((gym / "prereg" / "G1.json").read_text(encoding="utf-8"))
        pre.update(status="registered", prereg_id="G1-v1-medians-beat-the-mean", written_at="2030-01-10T09:00:00+00:00",
                   written_by="EMP-02", written_before="gym/series/G1.json held no point", question="Are the answers the medians?")
        pre["min_n"]["units"] = 20
        pre["bars"][0]["threshold"] = 90
        (gym / "prereg" / "G1.json").write_text(json.dumps(pre, indent=1) + "\n", encoding="utf-8", newline="\n")
        code, out = p.gym("counted", "G1")
        check("a counted run on a prereg that pins no contract is refused", code == 2 and "pins no contract" in out, out)
        pre["contract"].update(path="gym/contracts/G1-artifacts.md", sha256="0" * 64)
        (gym / "prereg" / "G1.json").write_text(json.dumps(pre, indent=1) + "\n", encoding="utf-8", newline="\n")
        code, out = p.gym("counted", "G1")
        check("a counted run on a stale pin is refused", code == 2 and "another text" in out, out)
        code, out = p.tool("gym_init.py", "check")
        check("gym_init check reports the stale pin", code == 1 and "PROBLEM G1: its prereg pins no version of gym/contracts/G1-artifacts.md" in out, out)
        code, out = p.tool("board.py", "check", "--no-build")
        check("the board reports the same stale pin", "G1's prereg pins no version of gym/contracts/G1-artifacts.md" in out, out)
        pre["contract"]["sha256"] = hashlib.sha256(contract.read_bytes()).hexdigest()
        (gym / "prereg" / "G1.json").write_text(json.dumps(pre, indent=1) + "\n", encoding="utf-8", newline="\n")
        code, out = p.tool("gym_init.py", "check")
        check("gym_init check passes on the registered, pinned prereg", code == 0 and "still a template" not in out and "draft" not in out, out)
        code, out = p.gym("counted", "G1")
        check("a counted run on a dirty tree is refused, and names what changed", code == 2 and "not clean" in out and "G1.json" in out, out)
        check("no refusal wrote a point", series(p)["points"] == [])
        check("the registered prereg is committed", p.commit("G1: contract, prereg"))

        # counted on the lane's stand-in: the lane says VOID, and the series, the board and the checks carry that word
        code, out = p.gym("counted", "G1")
        s = series(p)
        pt = s["points"][-1] if s["points"] else {}
        check("a counted run on the stand-in is VOID (exit 1), n 0", code == 1 and pt.get("verdict") == "VOID" and pt.get("n") == 0 and "VOID" in out, out)
        check("the series holds meta and the point in the shape the board and flow.py read",
              s["meta"] == {"lane": "G1", "grader": "g1-v1", "prereg": "G1-v1-medians-beat-the-mean"} and len(s["points"]) == 1
              and RUN_ID.fullmatch(pt.get("run_id", "")) and isinstance(pt.get("ts"), float) and pt.get("why")
              and re.fullmatch(r"[0-9a-f]{40}", pt.get("commit") or "") and pt.get("run_dir") == f"out/gym/G1/{pt.get('run_id')}", s)
        check("the counted run wrote its grade file, named for the run, and the run folder's grade.json",
              (gym / "grades" / f"G1-{pt.get('run_id')}.md").is_file() and (p.root / pt.get("run_dir", "x") / "grade.json").is_file())
        code, out = p.tool("board.py", "check")
        check("the board shows the lane's verdict from the series: VOID",
              f"G1 VOID, run {pt.get('run_id')}" in out and f"G1's latest run is VOID ({pt.get('run_id')})" in out, out)
        page = (p.root / "docs" / "progress-map.html").read_text(encoding="utf-8")
        check("the map shows the VOID run", pt.get("run_id", "x") in page and "0 lanes with no run yet" in page)
        code, out = p.gym("counted", "G1")
        check("the records of a counted run must be committed before the next one", code == 2 and "not clean" in out, out)
        (p.root / "docs" / "progress-map.html").unlink()
        p.commit("G1: a VOID run's records")

        # the contract's command in place of the stand-in: a PASS, read by the board and by flow.py
        (p.root / "tools").mkdir()
        (p.root / "tools" / "emit.py").write_text(
            "import json, os, random, statistics\n"
            "rng = random.Random(7)\n"
            "with open(os.path.join(os.environ['GYM_RUN_DIR'], 'samples.jsonl'), 'w', encoding='utf-8') as fh:\n"
            "    for i in range(60):\n"
            "        v = [rng.randrange(1, 500) for _ in range(7)]\n"
            "        fh.write(json.dumps({'id': i, 'values': v, 'answer': statistics.median(v)}) + '\\n')\n", encoding="utf-8", newline="\n")
        lane = gym / "lanes" / "g1_example.py"
        text = lane.read_text(encoding="utf-8")
        check("the lane has its COLLECT line", "\nCOLLECT = []\n" in text)
        lane.write_text(text.replace("\nCOLLECT = []\n", f"\nCOLLECT = {json.dumps([PY, 'tools/emit.py'])}\n"), encoding="utf-8", newline="\n")
        p.commit("G1: the contract's command")
        code, out = p.gym("counted", "G1")
        s = series(p)
        pt = s["points"][-1]
        check("a counted run on the contract's command passes (exit 0)", code == 0 and pt["verdict"] == "PASS" and pt["n"] == 60 and pt["headline"] == 100.0, out)
        check("the series keeps both runs, oldest first", [x["verdict"] for x in s["points"]] == ["VOID", "PASS"] and s["points"][0]["ts"] < pt["ts"])
        check("the chart is written", (gym / "charts" / "G1.html").is_file())
        code, out = p.tool("board.py", "check")
        page = (p.root / "docs" / "progress-map.html").read_text(encoding="utf-8")
        # read from the map page and from lines the board prints whatever the minute is: its "G1 ran at ... (PASS)"
        # warning depends on the minute the state was last updated, so it is not asserted on
        check("the board shows the lane's verdict from the series: PASS",
              re.search(r'Lanes PASS on their latest run</div><div class="v">1 / 1<', page) and "G1 VOID" not in out
              and "latest run is" not in out and "PASS rows on a lane not passing now: 0" in out,
              (out, re.findall(r"Lanes PASS on their latest run.{0,60}", page)))
        check("the map shows the run", pt["run_id"] in page and "0 lanes with no run yet" in page, re.findall(r"[^>]*no run yet[^<]*", page))
        code, out = p.tool("flow.py", "build", f"--root={p.root}", f"--out={base / 'flowpage'}")
        blob = re.search(r'<script type="application/json" id="gdata">(.*?)</script>', (base / "flowpage" / "workflow.html").read_text(encoding="utf-8"), re.S) \
            if (base / "flowpage" / "workflow.html").is_file() else None
        m1 = next((n for n in json.loads(blob[1].replace("<\\/", "</"))["nodes"] if n["id"] == "M1"), {}) if blob else {}
        check("flow.py reads the same run for the milestone's lane", m1.get("lane") == "G1" and m1.get("verdict") == ["PASS", pt["run_id"], 60] and m1.get("runs") == 2, (out, m1))
        code, out = p.tool("gym_init.py", "check")
        check("gym_init check passes with the series in place", code == 0 and "0 problem(s)" in out, out)
        (p.root / "docs" / "progress-map.html").unlink()
        p.commit("G1: a PASS run's records")

        # a collect that leaves a file in the tree: the runner publishes the run as VOID, whatever the lane says
        emit = p.root / "tools" / "emit.py"
        kept_emit = emit.read_text(encoding="utf-8")
        emit.write_text(kept_emit + "with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stray.txt'), 'w', encoding='utf-8') as fh:\n"
                        "    fh.write('left behind')\n", encoding="utf-8", newline="\n")
        p.commit("the command leaves a file in the tree")
        code, out = p.gym("counted", "G1")
        pt = series(p)["points"][-1]
        check("a counted run whose tree is not clean after the collect is VOID by the runner's own rule (exit 1): the point names the file and keeps the lane's word",
              code == 1 and pt["verdict"] == "VOID" and pt.get("lane_verdict") in WORDS and "stray.txt" in pt["why"]
              and "VOID" in out and len(series(p)["points"]) == 3, (code, out, pt))
        man = json.loads((p.root / pt["run_dir"] / "manifest.json").read_text(encoding="utf-8"))
        grade = json.loads((p.root / pt["run_dir"] / "grade.json").read_text(encoding="utf-8"))
        check("the manifest names what changed, and the run's grade.json is VOID too",
              man["tree_clean_after"] is False and any("stray.txt" in c for c in man["tree_changes_after"]) and grade["verdict"] == "VOID", (man, grade))
        (p.root / "tools" / "stray.txt").unlink()
        emit.write_text(kept_emit, encoding="utf-8", newline="\n")
        p.commit("G1: a VOID run's records; the command as it was")

        # a collect that commits: the tree is clean after it and the lane says PASS, but HEAD is not the commit the run names
        emit.write_text(kept_emit + "import subprocess\n"
                        "subprocess.run(['git', 'commit', '-q', '--allow-empty', '-m', 'made by the collect'],\n"
                        "               cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))), check=True)\n", encoding="utf-8", newline="\n")
        p.commit("the command commits")
        n_before = len(series(p)["points"])
        code, out = p.gym("counted", "G1")
        pt = series(p)["points"][-1]
        man = json.loads((p.root / pt["run_dir"] / "manifest.json").read_text(encoding="utf-8"))
        check("a counted run whose collect commits is VOID (exit 1) though the tree is clean and the lane said PASS",
              code == 1 and len(series(p)["points"]) == n_before + 1 and pt["verdict"] == "VOID" and pt.get("lane_verdict") == "PASS"
              and "HEAD moved during the collect" in pt["why"] and man["tree_clean_after"] is True and man.get("commit_after")
              and man["commit_after"] != man["commit"] and pt["commit"] == man["commit"], (code, out, pt, man))
        emit.write_text(kept_emit, encoding="utf-8", newline="\n")
        p.commit("G1: a VOID run's records; the command as it was")

        # a collect that leaves GIT_DIR set and a file in the tree: the runner still asks git about this checkout
        kept_lane = lane.read_text(encoding="utf-8")
        main_block = '\nif __name__ == "__main__":'
        check("the lane file has the block the next cases write before", main_block in kept_lane and "\nimport os\n" in kept_lane)
        redirect = ("\n_collect = collect\n\n\ndef collect(run_dir, root, mode):\n    facts = _collect(run_dir, root, mode)\n"
                    "    os.environ[\"GIT_DIR\"] = os.path.join(root, \"no-such-git-dir\")\n"
                    "    with open(os.path.join(root, \"stray2.txt\"), \"w\", encoding=\"utf-8\") as fh:\n"
                    "        fh.write(\"left behind\")\n    return facts\n\n")
        lane.write_text(kept_lane.replace(main_block, redirect + main_block, 1), encoding="utf-8", newline="\n")
        p.commit("the lane's collect sets GIT_DIR and leaves a file")
        code, out = p.gym("counted", "G1")
        pt = series(p)["points"][-1]
        check("a counted run whose collect sets GIT_DIR and leaves a file is VOID, and names the file",
              code == 1 and pt["verdict"] == "VOID" and pt.get("lane_verdict") in WORDS and "stray2.txt" in pt["why"], (code, out, pt))
        (p.root / "stray2.txt").unlink()
        lane.write_text(kept_lane, encoding="utf-8", newline="\n")
        p.commit("G1: a VOID run's records; the lane as it was")

        # a lane that ends the process with sys.exit(0): never the PASS code, and nothing is published
        lane.write_text(kept_lane.replace(main_block, "\ndef grade(run_dir):\n    sys.exit(0)\n\n" + main_block, 1), encoding="utf-8", newline="\n")
        p.commit("the lane's grade exits")
        n_before = len(series(p)["points"])
        code, out = p.gym("counted", "G1")
        check("a lane that calls sys.exit(0) makes the counted run exit 3 (no verdict), not 0, and publishes nothing",
              code == 3 and "the runner failed; no verdict" in out and "sys.exit(0)" in out and len(series(p)["points"]) == n_before
              and not p.git("status", "--porcelain")[1].strip(), (code, out))
        code, out = p.gym("dev", "G1")
        check("and a dev run of it exits 3 too", code == 3 and "no verdict" in out, (code, out))
        lane.write_text(kept_lane, encoding="utf-8", newline="\n")
        p.commit("the lane as it was")

        # one more lane; a freeze holds it too
        before = (gym / "run.py").read_bytes()
        p.freeze()
        code, out = p.tool("gym_init.py", "lane", "add", "G2", "--title", 'Second "quoted" lane')
        check("lane add during the manager's freeze is refused (exit 3) and writes nothing",
              code == 3 and "MGR-1" in out and (gym / "run.py").read_bytes() == before and not (gym / "prereg" / "G2.json").exists(), (code, out))
        code, out = p.tool("gym_init.py", "check")
        check("check runs during the freeze", code == 0 and "0 problem(s)" in out, (code, out))
        p.freeze(on=False)
        code, out = p.tool("gym_init.py", "lane", "add", "G2", "--title", 'Second "quoted" lane')
        new = ["lanes/g2_second_quoted_lane.py", "prereg/G2.json", "contracts/G2-artifacts.md", "series/G2.json"]
        check("lane add writes the lane's files", code == 0 and all((gym / f).is_file() for f in new), out)
        check("lane add leaves the first lane's files alone", "G1" not in out.replace("G1.", ""), out)
        check("the new prereg and contract carry the lane and the title",
              json.loads((gym / "prereg" / "G2.json").read_text(encoding="utf-8"))["title"] == 'Second "quoted" lane'
              and json.loads((gym / "prereg" / "G2.json").read_text(encoding="utf-8"))["lane"] == "G2"
              and (gym / "contracts" / "G2-artifacts.md").read_text(encoding="utf-8").startswith('# G2 artifacts: Second "quoted" lane (DRAFT'))
        code, out = p.gym("list")
        check("run.py list names both lanes, in order", code == 0 and [line.split()[0] for line in out.splitlines()] == ["G1", "G2"]
              and 'Second "quoted" lane' in out, out)
        code, out = p.tool("lanes_for.py", "check")
        check("lanes_for.py check passes with two lanes", code == 0 and "lanes in run.py: 2; in the table: 2" in out, out)
        code, out = p.tool("gym_init.py", "check")
        check("gym_init check passes with two lanes", code == 0 and "2 lane(s) (G1, G2)" in out, out)
        code, out = p.gym("selftest")
        check("the gym's selftest passes with two lanes", code == 0 and "lane G2:" in out and out.strip().endswith("gym selftest: ok"), out)
        code, out = p.gym("dev", "G2")
        check("the new lane runs a dev run", code == 1 and "G2 dev" in out and "MEASURING" in out, out)
        before = (gym / "run.py").read_text(encoding="utf-8")
        code, out = p.tool("gym_init.py", "lane", "add", "G2", "--title", "other")
        check("adding the same lane again changes nothing", code == 0 and (gym / "run.py").read_text(encoding="utf-8") == before
              and "wrote" not in out and "edited" not in out, out)
        code, out = p.tool("gym_init.py", "lane", "add", "bad-name")
        check("lane add refuses a name that is not a lane's", code == 2, out)

        # check finds what the tools would trip on
        (gym / "prereg" / "G2.json").unlink()
        code, out = p.tool("gym_init.py", "check")
        check("check: a lane with no prereg", code == 1 and "PROBLEM G2: no prereg" in out, out)
        p.tool("gym_init.py", "lane", "add", "G2")
        table = gym / "lane-inputs.toml"
        kept = table.read_text(encoding="utf-8")
        table.write_text(kept.replace("[lanes.G2]", "[lanes.G3]"), encoding="utf-8", newline="\n")
        code, out = p.tool("gym_init.py", "check")
        check("check: the table and run.py disagree, both ways", code == 1 and "has no [lanes.G2]" in out and "[lanes.G3], which is not in run.py" in out, out)
        table.write_text(kept, encoding="utf-8", newline="\n")
        lane2 = gym / "lanes" / "g2_second_quoted_lane.py"
        body = lane2.read_text(encoding="utf-8")
        lane2.write_text(body.replace('if __name__ == "__main__":\n    sys.exit(selftest())\n', ""), encoding="utf-8", newline="\n")
        code, out = p.tool("gym_init.py", "check")
        check("check: a lane file with no selftest block", code == 1 and "no `if __name__" in out, out)
        lane2.write_text(body, encoding="utf-8", newline="\n")
        ser = gym / "series" / "G2.json"
        ser.write_text(json.dumps({"meta": {}, "points": [{"run_id": "run-7", "verdict": "PASS"}, {"run_id": "20300110-113607-0a1f", "verdict": "GOOD"}]}), encoding="utf-8")
        code, out = p.tool("gym_init.py", "check")
        check("check: a series point with no run id the board reads, and one with no verdict word",
              code == 1 and "point 1 has no run id" in out and "has no verdict word" in out, out)
        ser.write_text('{"meta": {"lane": "G2"}, "points": []}\n', encoding="utf-8")
        contract.write_text(contract.read_text(encoding="utf-8") + "\nA line added after the pin.\n", encoding="utf-8", newline="\n")
        code, out = p.tool("gym_init.py", "check")
        check("check: a contract changed after its pin", code == 1 and "pins no version" in out and out.count("PROBLEM") == 1, out)

        # another first lane, and a gym folder the profile names elsewhere
        q = Project(base, "other", FOUNDRY_PATHS_GYM="measure/gym")
        code, out = q.tool("gym_init.py", "init", "--lane", "G7", "--title", "Starts in under a second", FOUNDRY_COMMANDS_PYTHON="py -3.12")
        g2 = q.root / "measure" / "gym"
        measure = [line.strip() for line in out.splitlines() if re.match(r"\s+(counted|dev|selftest) = ", line)]
        check("with commands.python set in the profile, the profile lines name that interpreter",
              measure == ["counted = 'py -3.12 measure/gym/run.py counted <lane>'", "dev = 'py -3.12 measure/gym/run.py dev <lane>'",
                          "selftest = 'py -3.12 measure/gym/run.py selftest'"], measure)
        check("init --lane names the example for that lane, under the profile's gym folder",
              code == 0 and all((g2 / f).is_file() for f in ("run.py", "lanes/g7_example.py", "prereg/G7.json", "contracts/G7-artifacts.md", "series/G7.json"))
              and not (g2 / "prereg" / "G1.json").exists() and not (q.root / "gym").exists(), out)
        every = "".join(f.read_text(encoding="utf-8") for f in g2.rglob("*") if f.is_file() and f.name != "gym_kit.py")
        check("no template name is left in that gym", not re.search(r"\bG1\b|g1_example|g1-v1", every), re.findall(r".{30}(?:\bG1\b|g1_example|g1-v1).{20}", every)[:4])
        check("its files name the profile's gym folder", "measure/gym/lanes/g7_example.py" in (g2 / "lane-inputs.toml").read_text(encoding="utf-8")
              and "python measure/gym/run.py" in (g2 / "README.md").read_text(encoding="utf-8")
              and 'TITLE = "Starts in under a second"' in (g2 / "lanes" / "g7_example.py").read_text(encoding="utf-8"))
        code, out = q.gym("selftest", folder="measure/gym")
        check("that gym's selftest passes", code == 0 and "lane G7:" in out and out.strip().endswith("gym selftest: ok"), out)
        code, out = q.tool("lanes_for.py", "check")
        check("lanes_for.py check passes there", code == 0 and "lanes_for check: ok" in out, out)
        code, out = q.tool("gym_init.py", "check")
        check("gym_init check passes there", code == 0 and "1 lane(s) (G7)" in out, out)
        code, out = q.gym("dev", "G7", folder="measure/gym")
        check("a dev run there writes under out/gym/G7", code == 1 and len(list((q.root / "out" / "gym" / "G7").iterdir())) == 1, out)

        # lane add on a LANES whose last entry has no comma and a comment after it: the comma goes before the comment
        run7 = g2 / "run.py"
        text7 = run7.read_text(encoding="utf-8")
        check("that run.py has the line the next case rewrites", '    "G7": "g7_example",\n' in text7)
        run7.write_text(text7.replace('    "G7": "g7_example",\n', '    "G7": "g7_example"  # the first lane: it has no comma\n'),
                        encoding="utf-8", newline="\n")
        code, out = q.tool("gym_init.py", "lane", "add", "G8", "--title", "Eighth")
        text8 = run7.read_text(encoding="utf-8")
        check("lane add puts the comma before the comment, and run.py still compiles",
              code == 0 and '"G7": "g7_example",  # the first lane: it has no comma\n    "G8": "g8_eighth",\n' in text8, (code, out, text8[text8.find("LANES"):][:300]))
        code, out = q.gym("list", folder="measure/gym")
        check("run.py list names both lanes after that edit", code == 0 and [line.split()[0] for line in out.splitlines()] == ["G7", "G8"], (code, out))
        # an edit whose result would not compile is not written
        broken = text8 + "\ndef (:\n"
        run7.write_text(broken, encoding="utf-8", newline="\n")
        code, out = q.tool("gym_init.py", "lane", "add", "G9", "--title", "Ninth")
        check("lane add refuses to write a run.py that would not compile, and leaves it as it was",
              code == 1 and "would not compile" in out and run7.read_text(encoding="utf-8") == broken and not (g2 / "run.py.tmp").exists(), (code, out))
        run7.write_text(text8, encoding="utf-8", newline="\n")

        # an error in a lane is the runner's failure (exit 3), not a verdict (exit 1)
        lane7 = g2 / "lanes" / "g7_example.py"
        body7 = lane7.read_text(encoding="utf-8")
        lane7.write_text(body7.replace('if __name__ == "__main__":', 'def grade(run_dir):\n    raise RuntimeError("the grader broke")\n\n\nif __name__ == "__main__":'),
                         encoding="utf-8", newline="\n")
        code, out = q.gym("dev", "G7", folder="measure/gym")
        check("an unhandled error exits 3 with its traceback and says there is no verdict",
              code == 3 and "Traceback" in out and "the grader broke" in out and "the runner failed; no verdict" in out, (code, out))
        lane7.write_text(body7, encoding="utf-8", newline="\n")

    print(f"gym init tests: {'FAIL ' + str(len(FAILS)) if FAILS else 'ok'}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
