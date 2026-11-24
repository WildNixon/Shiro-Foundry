#!/usr/bin/env python3
"""The gym's runner.

    python gym/run.py list                 the lanes, one per line: name, file, title
    python gym/run.py selftest             gym_kit's selftest, this runner's own, then every lane's
    python gym/run.py dev <lane>           an uncounted run: collects, grades dry; nothing is published
    python gym/run.py counted <lane>       a counted run: one point in gym/series/<lane>.json, a grade, a chart

A run gets an id (YYYYMMDD-HHMMSS-xxxx) and a folder, out/gym/<lane>/<run id>/ (GYM_OUT names another base). The
runner writes manifest.json there, the lane's collect() writes the artifacts its contract lists, and the lane's
grade() reads that folder and nothing else. A dev run leaves dry-grade.json in the folder. A counted run leaves
grade.json there and publishes: one point in the lane's series, gym/grades/<lane>-<run id>.md and
gym/charts/<lane>.html.

A counted run is refused (exit 2, nothing written) when: the checkout is not a git checkout, or `git status` shows
any change, tracked or not (the run samples the tree, so it must be the commit it names); the lane has no
gym/prereg/<lane>.json; the prereg is still a template; or the prereg pins no contract, a contract whose path
leaves the checkout (an absolute path elsewhere, or one with `..` that resolves outside), or a contract whose
file does not have the pinned sha256.

The verdict word is the lane's. The runner never chooses one: a lane that returns no word from gym_kit.WORDS is
refused and nothing is published. It changes one only when nothing shows that a counted run sampled the commit
it names. Then the runner publishes the run as VOID with the reason, whatever the lane said (the lane's own word
is kept in the point and the grade as lane_verdict):
    - the tree is not clean after the collect (the manifest's tree_clean_after is false);
    - git cannot say whether it is (tree_clean_after is null): git answered before the run, so something in the
      run stopped it;
    - HEAD, or HEAD's reflog, is not what it was before the collect (head_moved): the collect committed, reset or
      checked out, so a clean tree afterwards says nothing.
The runner asks git with GIT_DIR, GIT_WORK_TREE and GIT_INDEX_FILE taken out of the environment, so a collect
that sets one of them does not point these checks at another repository.

Exit code:
    0   PASS, or a passing selftest, or `list`
    1   any other verdict word (MARGINAL, FAIL, MEASURING, STARVED, VOID, SATURATED), or a failing selftest
    2   a refusal (nothing was published), or a command line the runner does not know
    3   the runner failed: an error that is no refusal, with its traceback on stderr, or a lane (or code it
        calls) that ended the process with sys.exit, whatever code it gave. There is no verdict; a caller must
        not read this as a FAIL, and a lane's sys.exit(0) is never the PASS code.
    130 interrupted (Ctrl+C). There is no verdict.

What a lane file gives the runner (see lanes/, and the README):
    LANE, TITLE, GRADER_VERSION        its name as LANES spells it, one line on what it proves, the grader's version
    collect(run_dir, root, mode)       make the artifacts in run_dir; returns facts for the manifest
    grade(run_dir)                     a dict with "verdict", "n" and "why" at least
    selftest()                         0 when every verdict word and every control was reached, else 1
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import gym_kit  # noqa: E402

# Lane name -> its file under lanes/, without ".py". Keep one lane per line: other tools read the names here as text.
LANES = {
    "G1": "g1_example",
}

RUN_ID = re.compile(r"20\d{6}-\d{6}-[0-9a-f]{4}")


class Refused(Exception):
    """The runner's own refusal. A lane may raise its own class with gym_refused = True."""
    gym_refused = True


GIT_REDIRECTS = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE")  # each points git at something other than `root`


def _git(root, *args):
    """git's answer about the checkout `root`, or None. Asked without the variables that would turn the question
    to another repository, work tree or index: a collect may have set one in this process."""
    env = {k: v for k, v in os.environ.items() if k not in GIT_REDIRECTS}
    try:
        r = subprocess.run(["git", "-C", root, *args], capture_output=True, text=True, timeout=60, env=env)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


def find_root(gym=HERE):
    """The checkout the gym lies in (git's answer), else the gym folder's parent."""
    top = _git(gym, "rev-parse", "--show-toplevel")
    return os.path.normpath(top.strip()) if top and top.strip() else os.path.dirname(gym)


def out_base(root):
    return os.environ.get("GYM_OUT") or os.path.join(root, "out", "gym")


def new_run_id(now=None):
    return time.strftime("%Y%m%d-%H%M%S", time.localtime(now)) + "-" + os.urandom(2).hex()


def load_lane(lane, gym=HERE, lanes=None):
    lanes = LANES if lanes is None else lanes
    if lane not in lanes:
        raise Refused("unknown lane %s; known: %s" % (lane, ", ".join(lanes) or "none"))
    if not isinstance(lanes[lane], str):
        return lanes[lane]  # the selftest's stub
    path = os.path.join(gym, "lanes", lanes[lane] + ".py")
    if not os.path.isfile(path):
        raise Refused("lane %s names %s, which is not there" % (lane, path))
    spec = importlib.util.spec_from_file_location("gym_lane_" + lanes[lane], path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def write_json(path, obj):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, indent=1, sort_keys=True, default=str)
        fh.write("\n")
    os.replace(tmp, path)


def tree_changes(root):
    """The lines of `git status --porcelain` (untracked files too), or None outside a git checkout."""
    out = _git(root, "status", "--porcelain", "--untracked-files=all")
    return None if out is None else [line for line in out.splitlines() if line.strip()]


def file_shas(path):
    """Every hash a pin may hold for this file: the sha256 of its bytes, and of its bytes with CRLF read as LF."""
    with open(path, "rb") as fh:
        body = fh.read()
    return {hashlib.sha256(body).hexdigest(), hashlib.sha256(body.replace(b"\r\n", b"\n")).hexdigest()}


def inside(path, root):
    """Whether a path resolves to a place inside the folder `root` (links and `..` followed, case as the system reads it)."""
    try:
        p, r = os.path.normcase(os.path.realpath(path)), os.path.normcase(os.path.realpath(root))
        return p != r and os.path.commonpath([p, r]) == r
    except (OSError, ValueError):  # another drive, or a path the system cannot read
        return False


def head_state(root):
    """(HEAD's commit, a line for HEAD's reflog: its length and its newest entry), each None when git cannot say."""
    commit = (_git(root, "rev-parse", "HEAD") or "").strip() or None
    count, tip = _git(root, "rev-list", "--walk-reflogs", "--count", "HEAD"), _git(root, "reflog", "-n", "1", "--format=%H %gs", "HEAD")
    return commit, (None if count is None or tip is None else "%s %s" % (count.strip(), tip.strip()))


def unsound(manifest):
    """Why a counted run cannot be said to have sampled the commit it names, or None: what the manifest holds of
    the tree and of HEAD after the collect."""
    clean = manifest.get("tree_clean_after")
    if clean is False:
        changed = [str(c).strip() for c in manifest.get("tree_changes_after") or []]
        names = ("; ".join(changed[:5]) + ("; ..." if len(changed) > 5 else "")) or "git status shows changes"
        return "the tree was not clean after the collect (%s)" % names
    if clean is not True:
        return ("git could not say whether the tree was clean after the collect, though it could before the run "
                "(did the collect change git's environment or the repository?)")
    if manifest.get("head_moved"):
        return "HEAD moved during the collect (%s)" % manifest["head_moved"]
    return None


def void_if_unsound(result, manifest):
    """The lane's result, or that result as VOID when the run cannot be said to have sampled the commit it names
    (unsound), whatever the lane says. The one case where the runner changes a verdict word."""
    reason = unsound(manifest)
    if reason is None:
        return result
    why = ("%s, so the run did not sample the commit it names; the lane said %s (%s)"
           % (reason, result.get("verdict"), result.get("why")))
    return dict(result, verdict="VOID", why=why, lane_verdict=result.get("verdict"))


def prereg_refusal(lane, gym, root):
    """Why this lane may not run counted, or None. Returns (reason, prereg doc)."""
    path = os.path.join(gym, "prereg", lane + ".json")
    if not os.path.isfile(path):
        return "lane %s has no prereg (%s): an independent grader writes it before any counted data" % (lane, path), None
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError) as e:
        return "%s is not JSON (%s)" % (path, e), None
    if not isinstance(doc, dict):
        return "%s is not a JSON object" % path, None
    if str(doc.get("status") or "").strip().upper().startswith("TEMPLATE"):
        return ("%s is still a template: the grader fills it, sets \"status\" to \"registered\" and commits it "
                "before the first counted run" % path), doc
    c = doc.get("contract") if isinstance(doc.get("contract"), dict) else {}
    rel, sha = str(c.get("path") or "").strip(), str(c.get("sha256") or "").strip().lower()
    if not rel or not sha:
        return ("%s pins no contract: set contract.path and contract.sha256 to the builder's contract as the "
                "grader read it" % path), doc
    cfile = os.path.join(root, rel)
    if not inside(cfile, root):
        return ("%s pins %s, which is not a file inside this checkout (%s): contract.path is a path under the "
                "checkout, with no `..` that leaves it" % (path, rel, root)), doc
    if not os.path.isfile(cfile):
        return "%s pins %s, which is not in this checkout" % (path, rel), doc
    if sha not in file_shas(cfile):
        return ("%s pins %s at sha256 %s, and the file here is another text: the grader reads the change and "
                "pins it again, by a dated amendment" % (path, rel, sha[:12])), doc
    return None, doc


def word_of(result):
    """The lane's verdict word, or a Refused: the runner never supplies one."""
    word = result.get("verdict") if isinstance(result, dict) else None
    if word not in gym_kit.WORDS:
        raise Refused("the lane returned no verdict word (%r); known words: %s. Nothing is published"
                      % (word, ", ".join(gym_kit.WORDS)))
    return word


def start_run(lane, mod, mode, root, out):
    run_id = new_run_id()
    run_dir = os.path.join(out, lane, run_id)
    os.makedirs(run_dir)
    commit, reflog = head_state(root)
    manifest = {"run_id": run_id, "lane": lane, "mode": mode, "started": time.time(),
                "grader": getattr(mod, "GRADER_VERSION", ""), "commit": commit}
    write_json(os.path.join(run_dir, "manifest.json"), manifest)
    manifest["collect"] = mod.collect(run_dir, root, mode)
    commit_after, reflog_after = head_state(root)
    if commit_after != commit:
        manifest["commit_after"] = commit_after
        manifest["head_moved"] = "from %s to %s" % ((commit or "nothing")[:12], (commit_after or "nothing git can name")[:12])
    elif reflog_after != reflog:
        manifest["head_moved"] = "it names the same commit, but its reflog changed: a commit, a reset or a checkout was made in between"
    changes = tree_changes(root)
    manifest["tree_clean_after"] = None if changes is None else not changes
    if changes:
        manifest["tree_changes_after"] = changes[:50]
    manifest["ended"] = time.time()
    write_json(os.path.join(run_dir, "manifest.json"), manifest)
    return run_id, run_dir, manifest


def dev(lane, gym=HERE, root=None, out=None, lanes=None):
    root = root or find_root(gym)
    mod = load_lane(lane, gym, lanes)
    run_id, run_dir, _ = start_run(lane, mod, "dev", root, out or out_base(root))
    result = mod.grade(run_dir)
    word = word_of(result)
    doc = dict(result, dry=True, run_id=run_id, run_dir=run_dir)
    write_json(os.path.join(run_dir, "dry-grade.json"), doc)
    print("%s dev %s: %s (n=%s) %s" % (lane, run_id, word, result.get("n"), result.get("why")))
    print("dry grade (not published): %s" % os.path.join(run_dir, "dry-grade.json"))
    return 0 if word == "PASS" else 1


def publish(lane, mod, result, run_id, run_dir, manifest, prereg, gym, root):
    """One point in the lane's series, the grade and the chart. The series file is what the board reads."""
    meta = {"lane": lane, "grader": getattr(mod, "GRADER_VERSION", ""), "prereg": prereg.get("prereg_id", "")}
    spath = os.path.join(gym, "series", lane + ".json")
    if os.path.isfile(spath):
        try:
            with open(spath, encoding="utf-8") as fh:
                empty = not (json.load(fh).get("points") or [])
        except (OSError, ValueError, AttributeError):
            empty = False
        if empty:  # a series with no point holds no evidence: it takes this grader's meta
            os.remove(spath)
    series = gym_kit.Series(spath, meta=meta)
    try:
        shown = os.path.relpath(run_dir, root).replace("\\", "/")
    except ValueError:
        shown = run_dir
    point = {"run_id": run_id, "verdict": result["verdict"], "n": result.get("n"), "why": result.get("why"),
             "headline": result.get("headline"), "commit": manifest.get("commit"), "run_dir": shown}
    if result.get("lane_verdict"):  # the runner made this run VOID (void_if_unsound); what the lane said is kept
        point["lane_verdict"] = result["lane_verdict"]
    series.append(point)
    grade_path = os.path.join(gym, "grades", "%s-%s.md" % (lane, run_id))
    os.makedirs(os.path.dirname(grade_path), exist_ok=True)
    text = mod.honest_grade(result, run_dir) if hasattr(mod, "honest_grade") else "\n".join([
        "# %s honest grade: %s" % (lane, run_id), "",
        "1. **Verdict: %s.** %s" % (result["verdict"], result.get("why", "")),
        "2. **Headline:** %s (n=%s)." % (result.get("headline"), result.get("n")),
        "3. **Evidence:** run `%s`; series `%s`." % (shown, os.path.relpath(spath, root).replace("\\", "/")), ""])
    with open(grade_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text if text.endswith("\n") else text + "\n")
    pts = series.points
    heads = [p.get("headline") if isinstance(p.get("headline"), (int, float)) else None for p in pts]
    if any(h is not None for h in heads):
        gym_kit.write_chart(
            os.path.join(gym, "charts", lane + ".html"), "%s: %s" % (lane, getattr(mod, "TITLE", "")),
            [str(p.get("run_id", ""))[4:13] for p in pts], [{"label": "headline", "data": heads}],
            before=result.get("bar") if isinstance(result.get("bar"), (int, float)) else None,
            kpis={"Verdict": (result["verdict"], run_id), "n": result.get("n"), "Counted runs": len(pts)},
            notes=["Each point is one counted run. The dashed line is the pre-registered bar."],
            subtitle="Prereg %s, grader %s" % (meta["prereg"], meta["grader"]))
    return spath, grade_path


def counted(lane, gym=HERE, root=None, out=None, lanes=None):
    root = root or find_root(gym)
    mod = load_lane(lane, gym, lanes)
    why, prereg = prereg_refusal(lane, gym, root)
    if why:
        raise Refused(why)
    changes = tree_changes(root)
    if changes is None:
        raise Refused("a counted run needs a git checkout (%s is not one): the run names the commit it sampled" % root)
    if changes:
        raise Refused("the tree is not clean (%s%s): commit or remove every change, tracked or not, then run again"
                      % ("; ".join(c.strip() for c in changes[:5]), "; ..." if len(changes) > 5 else ""))
    run_id, run_dir, manifest = start_run(lane, mod, "counted", root, out or out_base(root))
    result = mod.grade(run_dir)
    word_of(result)  # a lane with no verdict word is refused before anything else is decided
    result = void_if_unsound(result, manifest)
    word = word_of(result)
    write_json(os.path.join(run_dir, "grade.json"), dict(result, run_id=run_id))
    spath, grade_path = publish(lane, mod, result, run_id, run_dir, manifest, prereg, gym, root)
    print("%s %s: %s (n=%s) %s" % (lane, run_id, word, result.get("n"), result.get("why")))
    print("series: %s\nhonest grade: %s" % (spath, grade_path))
    print("commit the records (series, grades, charts) before the next counted run")
    return 0 if word == "PASS" else 1


def _selftest():
    """The runner's own checks, on a stub lane in a temp folder."""
    checks = []

    def ok(cond, what):
        checks.append(bool(cond))
        print(("  ok   " if cond else "  FAIL ") + what)

    class Stub:
        LANE, TITLE, GRADER_VERSION = "ZZ", "a stub", "zz-v1"
        word = "PASS"

        @staticmethod
        def collect(run_dir, root, mode):
            with open(os.path.join(run_dir, "artifact.txt"), "w", encoding="utf-8") as fh:
                fh.write("1\n")
            return {"stub": True}

        @classmethod
        def grade(cls, run_dir):
            return {"verdict": cls.word, "n": 3, "why": "stub", "headline": 1.0}

    def quiet(fn, *a, **kw):
        stdout, stderr = sys.stdout, sys.stderr
        sys.stdout = sys.stderr = open(os.devnull, "w")
        try:
            return fn(*a, **kw)
        except Refused as e:
            return "refused: %s" % e
        finally:
            sys.stdout.close()
            sys.stdout, sys.stderr = stdout, stderr

    tmp = os.path.realpath(tempfile.mkdtemp(prefix="gymrun-"))  # its real name, so path comparisons hold
    other = os.path.realpath(tempfile.mkdtemp(prefix="gymrun-other-"))
    try:
        gym, out, lanes = os.path.join(tmp, "gym"), os.path.join(tmp, "out"), {"ZZ": Stub}
        os.makedirs(gym)
        ok(RUN_ID.fullmatch(new_run_id()) and new_run_id(0)[:15] != new_run_id(86400)[:15], "a run id reads YYYYMMDD-HHMMSS-xxxx, by its time")
        rc = quiet(dev, "ZZ", gym, tmp, out, lanes)
        runs = os.listdir(os.path.join(out, "ZZ"))
        files = sorted(os.listdir(os.path.join(out, "ZZ", runs[0]))) if runs else []
        ok(rc == 0 and len(runs) == 1 and RUN_ID.fullmatch(runs[0]) and files == ["artifact.txt", "dry-grade.json", "manifest.json"],
           "dev: PASS exits 0; the run folder holds the artifacts, the manifest and the dry grade")
        ok(not os.path.exists(os.path.join(gym, "series")), "dev publishes nothing: no series, grade or chart")
        Stub.word = "FAIL"
        ok(quiet(dev, "ZZ", gym, tmp, out, lanes) == 1, "dev: a word other than PASS exits 1")
        Stub.word = "GOOD"
        ok(str(quiet(dev, "ZZ", gym, tmp, out, lanes)).startswith("refused: the lane returned no verdict word"),
           "a lane that returns no verdict word is refused: the runner supplies none")
        Stub.word = "PASS"
        ok(str(quiet(dev, "NOPE", gym, tmp, out, lanes)).startswith("refused: unknown lane"), "an unknown lane is refused")
        ok("has no prereg" in str(quiet(counted, "ZZ", gym, tmp, out, lanes)), "counted: no prereg is refused")
        os.makedirs(os.path.join(gym, "prereg"))
        pre = os.path.join(gym, "prereg", "ZZ.json")
        write_json(pre, {"status": "TEMPLATE: not registered", "prereg_id": "ZZ-v1"})
        ok("still a template" in str(quiet(counted, "ZZ", gym, tmp, out, lanes)), "counted: a template prereg is refused")
        write_json(pre, {"status": "registered", "prereg_id": "ZZ-v1", "contract": {"path": "", "sha256": ""}})
        ok("pins no contract" in str(quiet(counted, "ZZ", gym, tmp, out, lanes)), "counted: a prereg with no contract pin is refused")
        con = os.path.join(tmp, "contract.md")
        with open(con, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("# the contract\n")
        write_json(pre, {"status": "registered", "prereg_id": "ZZ-v1", "contract": {"path": "contract.md", "sha256": "0" * 64}})
        ok("another text" in str(quiet(counted, "ZZ", gym, tmp, out, lanes)), "counted: a stale contract pin is refused")
        write_json(pre, {"status": "registered", "prereg_id": "ZZ-v1",
                         "contract": {"path": "contract.md", "sha256": sorted(file_shas(con))[0]}})
        why, _ = prereg_refusal("ZZ", gym, tmp)
        ok(why is None, "a registered prereg whose pin matches the contract passes the prereg gate")
        # a pin whose path leaves the checkout is refused, however it is spelled, though the sha256 matches
        away = os.path.join(other, "contract.md")
        shutil.copyfile(con, away)
        spellings = [away, os.path.join("gym", "..", "..", os.path.basename(other), "contract.md")]
        try:
            spellings.append(os.path.relpath(away, tmp))
        except ValueError:
            pass
        whys = []
        for spelled in spellings:
            write_json(pre, {"status": "registered", "prereg_id": "ZZ-v1",
                             "contract": {"path": spelled, "sha256": sorted(file_shas(con))[0]}})
            whys.append(prereg_refusal("ZZ", gym, tmp)[0] or "")
        ok(all("not a file inside this checkout" in w for w in whys),
           "counted: a contract path that leaves the checkout (absolute, or by ..) is refused")
        write_json(pre, {"status": "registered", "prereg_id": "ZZ-v1",
                         "contract": {"path": os.path.join("gym", "..", "contract.md"), "sha256": sorted(file_shas(con))[0]}})
        ok(prereg_refusal("ZZ", gym, tmp)[0] is None, "a contract path with .. that stays inside the checkout passes")
        write_json(pre, {"status": "registered", "prereg_id": "ZZ-v1",
                         "contract": {"path": "contract.md", "sha256": sorted(file_shas(con))[0]}})
        # the tree not clean after the collect: the runner makes the run VOID, whatever the lane said
        said = {"verdict": "PASS", "n": 3, "why": "stub", "headline": 1.0}
        v = void_if_unsound(said, {"tree_clean_after": False, "tree_changes_after": ["?? stray.txt"]})
        ok(v["verdict"] == "VOID" and v["lane_verdict"] == "PASS" and "stray.txt" in v["why"] and "PASS" in v["why"]
           and said["verdict"] == "PASS", "a run whose tree is not clean after the collect is VOID, with the reason and the lane's word")
        ok(void_if_unsound(said, {"tree_clean_after": True}) is said, "a clean tree and a HEAD that did not move leave the lane's result as it is")
        v1, v2 = void_if_unsound(said, {"tree_clean_after": None}), void_if_unsound(said, {})
        ok(v1["verdict"] == "VOID" and v1["lane_verdict"] == "PASS" and "git could not say" in v1["why"] and v2["verdict"] == "VOID",
           "a counted run after which git cannot say whether the tree is clean is VOID, not clean")
        v = void_if_unsound(said, {"tree_clean_after": True, "head_moved": "from aaaa to bbbb"})
        ok(v["verdict"] == "VOID" and v["lane_verdict"] == "PASS" and "HEAD moved during the collect (from aaaa to bbbb)" in v["why"],
           "a counted run whose collect moved HEAD is VOID, though the tree is clean after it")
        # the same through git itself, when there is one: a collect that commits, and one that commits and resets back
        repo = os.path.join(tmp, "repo")
        genv = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        genv.update(GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.invalid", GIT_COMMITTER_NAME="t",
                    GIT_COMMITTER_EMAIL="t@example.invalid", GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")

        def g(*args):
            try:
                return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True, timeout=60, env=genv).returncode == 0
            except (OSError, subprocess.SubprocessError):
                return False

        os.makedirs(repo)
        if g("init", "-q") and g("commit", "-q", "--allow-empty", "-m", "one"):
            class Commits(Stub):
                steps = (("commit", "-q", "--allow-empty", "-m", "two"),)

                @classmethod
                def collect(cls, run_dir, root, mode):
                    for step in cls.steps:
                        g(*step)
                    return {}

            run_out = os.path.join(tmp, "out-repo")
            m1 = quiet(start_run, "ZZ", Commits, "counted", repo, run_out)[2]
            Commits.steps = (("commit", "-q", "--allow-empty", "-m", "three"), ("reset", "-q", "--hard", "HEAD~1"))
            m2 = quiet(start_run, "ZZ", Commits, "counted", repo, run_out)[2]
            m3 = quiet(start_run, "ZZ", Stub, "counted", repo, run_out)[2]
            ok(m1["tree_clean_after"] is True and "from " in m1.get("head_moved", "") and unsound(m1),
               "a collect that commits: the tree is clean, HEAD moved, the run is unsound")
            ok(m2["tree_clean_after"] is True and "reflog" in m2.get("head_moved", "") and unsound(m2),
               "a collect that commits and resets back: the same commit, another reflog, the run is unsound")
            ok(m3["tree_clean_after"] is True and "head_moved" not in m3 and unsound(m3) is None,
               "a collect that leaves git alone: clean, HEAD where it was, sound")
            # a collect that leaves GIT_DIR set in this process does not blind the checks after it
            had = {k: os.environ.get(k) for k in GIT_REDIRECTS}

            class Redirects(Stub):
                @staticmethod
                def collect(run_dir, root, mode):
                    os.environ["GIT_DIR"] = os.path.join(root, "no-such-git-dir")
                    with open(os.path.join(root, "stray.txt"), "w", encoding="utf-8") as fh:
                        fh.write("x\n")
                    return {}

            try:
                m4 = quiet(start_run, "ZZ", Redirects, "counted", repo, run_out)[2]
            finally:
                for k, v in had.items():
                    if v is None:
                        os.environ.pop(k, None)
                    else:
                        os.environ[k] = v
            ok(m4["tree_clean_after"] is False and any("stray.txt" in c for c in m4.get("tree_changes_after", [])),
               "a collect that sets GIT_DIR and leaves a file: the runner still sees the file (it asks git without GIT_DIR)")
        else:
            print("  skip the git cases: git could not make a scratch repository here")

        class Exits(Stub):
            code = 0

            @classmethod
            def collect(cls, run_dir, root, mode):
                raise SystemExit(cls.code)

        class Interrupted(Stub):
            @staticmethod
            def collect(run_dir, root, mode):
                raise KeyboardInterrupt()

        class Broken(Stub):
            @staticmethod
            def collect(run_dir, root, mode):
                raise RuntimeError("the collect broke")

        real, real_out = dict(LANES), os.environ.get("GYM_OUT")
        LANES.clear()
        LANES["ZZ"] = Broken
        os.environ["GYM_OUT"] = out  # main() takes no folder: its run folder goes under the temp folder too
        try:
            rc3 = quiet(main, ["dev", "ZZ"])
            rc2 = quiet(main, ["dev", "NOPE"])
            LANES["ZZ"] = Exits
            rc_exit0 = quiet(main, ["dev", "ZZ"])
            Exits.code = 7
            rc_exit7 = quiet(main, ["dev", "ZZ"])
            Exits.code = None
            rc_exit_none = quiet(main, ["dev", "ZZ"])
            LANES["ZZ"] = Interrupted
            rc_int = quiet(main, ["dev", "ZZ"])
        finally:
            LANES.clear()
            LANES.update(real)
            if real_out is None:
                os.environ.pop("GYM_OUT", None)
            else:
                os.environ["GYM_OUT"] = real_out
        ok(rc3 == 3 and rc2 == 2, "an error that is no refusal exits 3 (the runner failed; no verdict); a refusal exits 2")
        ok((rc_exit0, rc_exit7, rc_exit_none) == (3, 3, 3), "a lane that calls sys.exit, with 0, 7 or nothing, exits 3: never the PASS code")
        ok(rc_int == 130, "an interrupt exits 130, not a verdict's code")
        ok("git checkout" in str(quiet(counted, "ZZ", gym, tmp, out, lanes)) or "not clean" in str(quiet(counted, "ZZ", gym, tmp, out, lanes)),
           "counted: outside a clean git checkout is refused")
        ok(not os.path.exists(os.path.join(gym, "series")), "every refusal published nothing")
        run_dir = os.path.join(out, "ZZ", "20300101-000000-abcd")
        os.makedirs(run_dir)
        result = {"verdict": "FAIL", "n": 3, "why": "stub", "headline": 0.5, "bar": 0.9}
        spath, gpath = publish("ZZ", Stub, result, "20300101-000000-abcd", run_dir, {"commit": "c0ffee"}, {"prereg_id": "ZZ-v1"}, gym, tmp)
        with open(spath, encoding="utf-8") as fh:
            doc = json.load(fh)
        p = doc["points"][0]
        ok(doc["meta"] == {"lane": "ZZ", "grader": "zz-v1", "prereg": "ZZ-v1"} and p["run_id"] == "20300101-000000-abcd"
           and p["verdict"] == "FAIL" and p["n"] == 3 and isinstance(p["ts"], float),
           "publish: the series holds meta and one point with run_id, verdict, n and an epoch ts")
        ok(os.path.isfile(gpath) and os.path.isfile(os.path.join(gym, "charts", "ZZ.html")), "publish: the grade and the chart are written")
        write_json(spath, {"meta": {"lane": "ZZ", "grader": "older", "prereg": ""}, "points": []})
        publish("ZZ", Stub, result, "20300101-000001-abcd", run_dir, {}, {"prereg_id": "ZZ-v1"}, gym, tmp)
        try:
            publish("ZZ", type("Other", (Stub,), {"GRADER_VERSION": "zz-v2"}), result, "20300101-000002-abcd", run_dir, {}, {"prereg_id": "ZZ-v1"}, gym, tmp)
            ok(False, "a series with points refuses another grader version")
        except ValueError:
            ok(True, "an empty series takes the grader's meta; one with points refuses another grader version")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        shutil.rmtree(other, ignore_errors=True)
    n = sum(checks)
    print("run.py selftest: %d/%d ok" % (n, len(checks)))
    return 0 if n == len(checks) else 1


def main(argv):
    try:
        if argv == ["list"]:
            for lane, name in LANES.items():
                try:
                    title = getattr(load_lane(lane), "TITLE", "")
                except Refused as e:
                    title = "(%s)" % e
                print("%-6s %-24s %s" % (lane, name, title))
            return 0
        if argv == ["selftest"]:
            rc = gym_kit._selftest()
            print("run.py:")
            rc |= _selftest()
            for lane in LANES:
                print("lane %s:" % lane)
                rc |= load_lane(lane).selftest()
            print("gym selftest: %s" % ("ok" if rc == 0 else "FAILED"))
            return rc
        if len(argv) == 2 and argv[0] == "dev":
            return dev(argv[1])
        if len(argv) == 2 and argv[0] == "counted":
            return counted(argv[1])
    except Exception as e:  # noqa: BLE001 - a refusal exits 2; any other error is the runner's failure, exit 3
        if getattr(e, "gym_refused", False) is True:
            print("refused: %s" % e, file=sys.stderr)
            return 2
        traceback.print_exc()
        print("the runner failed; no verdict (%s: %s). Exit 3 is not a verdict word: nothing here says PASS or FAIL"
              % (type(e).__name__, e), file=sys.stderr)
        return 3
    except SystemExit as e:  # a lane, or code it calls, ended the process: its code must not pass for a verdict's
        traceback.print_exc()
        print("the runner failed; no verdict (the lane, or code it calls, called sys.exit(%r)). Exit 3 is not a verdict "
              "word: nothing here says PASS or FAIL" % (e.code,), file=sys.stderr)
        return 3
    except KeyboardInterrupt:
        print("interrupted; no verdict", file=sys.stderr)
        return 130
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
