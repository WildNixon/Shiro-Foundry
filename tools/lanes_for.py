#!/usr/bin/env python3
"""Which gym lanes a change can move.

    lanes_for.py <git range>            lanes whose inputs the range touches, one per line, with the matching rule
                                        as a trailing comment
    lanes_for.py --files a b c          the same for a list of repo paths
    lanes_for.py <range> --explain      per lane, every touched path that matched and why; then the touched paths
                                        no lane watches
    lanes_for.py <range> --skip GLOB    leave the touched paths matching GLOB out (may repeat); a sweep skips
                                        grader notes this way
    lanes_for.py check                  the project's own table: every lane in the gym's run.py has an entry and the
                                        other way round, every group and unit a lane names exists; prints the units
                                        no lane reads
    lanes_for.py selftest               this tool's rules, on a scratch tree in a temp folder

A range is anything `git diff --name-only` takes (`a..b`, `a...b`), or one commit, which means its diff against its
first parent (so a merge shows what it brought in). Exit 0 with no output when no lane is touched; 2 on a usage or git
error. A project with no gym folder or no table yet selects no lane (one line on stderr, exit 0).

The table is lane-inputs.toml in the gym folder (paths.gym in the profile):

    [always]                      paths that can change every lane (a lock file, the gym's shared code)
    paths = ["requirements.lock", "gym/gym_kit.py"]
    [broad]                       what `broad = true` lanes react to
    paths = ["src/", "tests/"]
    [units.core]                  a unit: a folder that is built as one thing, and the units it needs
    dir = "src/core"
    needs = ["util"]
    [groups.harness]              inputs several lanes share
    paths = ["tools/harness/"]
    units = ["core"]
    [lanes.G1]
    paths = ["gym/lanes/g1.py", "gym/prereg/G1.md"]     prefixes (a folder ends in "/") or globs ("*" crosses "/")
    units = ["app"]               the lane reacts to these units and to every unit they need
    uses = ["harness"]
    broad = true                  only when the lane's inputs cannot be told from the code

Inside a unit, the files measure.not_built names (default: tests/, benches/, examples/ and *.md) are not built into
what a lane runs and select nothing through a unit or a broad rule. A unit with `own_paths = false` stands for its
needs only: lanes list its files one by one. measure.unit_manifests in the profile (globs, default none) names TOML
manifests to read units from as well: the folder of each is a unit named by its [package] name, needing the units
its [dependencies] and [build-dependencies] name (an optional one is followed unless the edge into the unit sets
default-features = false).

It is the manager's tool for the merge gate and a short sweep, not a grader's: this script reads the gym's run.py
as text for the lane names and never imports anything under the gym folder. Standard library only.
"""

import fnmatch
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import foundry_profile as fp  # noqa: E402

P = fp.load(__file__)
ROOT = P.root
GYM = P.local("gym")
TABLE_NAME = "lane-inputs.toml"
DEP_TABLES = ("dependencies", "build-dependencies")
NOT_BUILT = ["tests/", "benches/", "examples/", "*.md"]  # inside a unit; measure.not_built overrides


def lane_names(gym=None):
    """The lane names in run.py's LANES, read as text, in their order; none when the gym has no run.py yet."""
    run_py = (gym or GYM) / "run.py"
    if not run_py.is_file():
        return []
    text = run_py.read_text(encoding="utf-8")
    m = re.search(r"^LANES\s*=\s*\{(.*?)\}", text, re.S | re.M)
    if not m:
        raise SystemExit("lanes_for: cannot find LANES in %s" % run_py)
    return re.findall(r'"([A-Za-z0-9]+)"\s*:', m.group(1))


def units_of(root, table, manifests=()):
    """{unit: (repo dir or None, {needed unit: (optional?, follow its optional needs?)}, own paths?)} from the
    table's [units] and from the manifests the profile names."""
    raw = {}
    for pattern in manifests:
        for mf in sorted(root.glob(pattern)):
            if not mf.is_file():
                continue
            try:
                data = tomllib.loads(mf.read_text(encoding="utf-8"))
            except (OSError, tomllib.TOMLDecodeError):
                continue
            name = (data.get("package") or {}).get("name")
            if not name:
                continue
            deps = {}
            tables = [data.get(t) or {} for t in DEP_TABLES]
            for target in (data.get("target") or {}).values():
                tables.extend(target.get(t) or {} for t in DEP_TABLES)
            for tab in tables:
                for key, spec in tab.items():
                    spec = spec if isinstance(spec, dict) else {}
                    pkg = spec.get("package", key)
                    deps[pkg] = (bool(spec.get("optional")), spec.get("default-features", True))
            raw[name] = [mf.parent.relative_to(root).as_posix(), deps, True]
    for name, spec in (table.get("units") or {}).items():
        cur = raw.setdefault(name, [None, {}, True])
        if spec.get("dir"):
            cur[0] = str(spec["dir"]).replace("\\", "/").strip("/")
        for n in spec.get("needs", []):
            cur[1].setdefault(n, (False, True))
        if "own_paths" in spec:
            cur[2] = bool(spec["own_paths"])
    return {name: (d, {p: v for p, v in deps.items() if p in raw}, own) for name, (d, deps, own) in raw.items()}


def unit_closure(names, units):
    """{unit: how it was reached} for the named units and the units they need. An optional need is followed unless
    the edge into the unit said not to follow its defaults."""
    via_of, visited = {}, set()
    todo = [(n, None, True) for n in names]
    while todo:
        name, via, defaults = todo.pop(0)
        if name not in units or (name, defaults) in visited:
            continue
        visited.add((name, defaults))
        via_of.setdefault(name, via)
        for dep, (optional, dep_defaults) in units[name][1].items():
            if optional and not defaults:
                continue
            todo.append((dep, via or name, dep_defaults))
    return via_of


def path_match(path, pattern):
    if any(c in pattern for c in "*?["):
        return fnmatch.fnmatchcase(path, pattern) or fnmatch.fnmatchcase(path, pattern.rstrip("/") + "/*")
    if pattern.endswith("/"):
        return path.startswith(pattern)
    return path == pattern or path.startswith(pattern + "/")


def table_file(gym=None):
    return (gym or GYM) / TABLE_NAME


def load(root=None, gym=None, manifests=None):
    root, gym = root or ROOT, gym or GYM
    if manifests is None:
        manifests = P.get("measure.unit_manifests", []) or []
    table = tomllib.loads(table_file(gym).read_text(encoding="utf-8"))
    units = units_of(root, table, manifests)
    groups = table.get("groups") or {}
    rules = {}  # lane -> [(kind, pattern, label)]
    problems = []
    for name, (d, _, own) in units.items():
        if own and not d:
            problems.append("unit %s has no dir" % name)
    for lane, spec in (table.get("lanes") or {}).items():
        # Rule order is the order a file's label is chosen in: the lane's own paths and units before its groups'.
        rs = [("always", p, "always") for p in (table.get("always") or {}).get("paths", [])]
        rs += [("path", p, "path") for p in spec.get("paths", [])]
        sources = [("", list(spec.get("units", [])))]
        for g in spec.get("uses", []):
            if g not in groups:
                problems.append("%s uses unknown group %s" % (lane, g))
                continue
            rs += [("path", p, "group %s" % g) for p in groups[g].get("paths", [])]
            sources.append(("%s: " % g, groups[g].get("units", [])))
        for prefix, names in sources:
            for n in names:
                if n not in units:
                    problems.append("%s names unknown unit %s" % (lane, n))
            for c, via in sorted(unit_closure(names, units).items()):
                if not units[c][2] or not units[c][0]:
                    continue  # its own files are listed one by one (a group's or each lane's paths)
                label = "%sunit %s%s" % (prefix, c, " (via %s)" % via if via else "")
                rs.append(("unit", units[c][0] + "/", label))
        if spec.get("broad"):
            rs += [("broad", p, "broad") for p in (table.get("broad") or {}).get("paths", [])]
        rules[lane] = rs
    return rules, units, problems


def not_built(path, unit_dirs, patterns):
    """True for a file inside a unit that is not built into what a lane runs (its tests, its notes)."""
    home = max((d for d in unit_dirs if path.startswith(d + "/")), key=len, default=None)
    if home is None:
        return False
    rest = path[len(home) + 1:]
    return any(rest.startswith(p) if p.endswith("/") else fnmatch.fnmatchcase(rest, p) for p in patterns)


def match(files, rules, units=None, patterns=None):
    """{lane: [(path, label)]} for the lanes some file touches."""
    if patterns is None:
        patterns = P.get("measure.not_built", NOT_BUILT) or []
    dirs = [d for d, _, _ in (units or {}).values() if d]
    skip = {f for f in files if not_built(f, dirs, patterns)}
    hits = {}
    for lane, rs in rules.items():
        for f in files:
            for kind, pat, label in rs:
                if kind in ("unit", "broad") and f in skip:
                    continue
                if path_match(f, pat):
                    hits.setdefault(lane, []).append((f, label))
                    break
    return hits


def changed_files(rng, root=None, env=None):
    # --no-renames: with rename detection (diff.renames in a user's config) a moved file shows only its new path,
    # so a file moved out of a watched folder would select no lane
    if ".." in rng:
        args = ["git", "diff", "--name-only", "--no-renames", rng]
    else:
        args = ["git", "diff", "--name-only", "--no-renames", rng + "^1", rng]
    try:
        p = subprocess.run(args, cwd=root or ROOT, capture_output=True, text=True, env=env)
    except OSError as e:
        raise SystemExit("lanes_for: cannot run git: %s" % e)
    if p.returncode != 0:
        raise SystemExit("lanes_for: %s failed: %s" % (" ".join(args), p.stderr.strip()))
    return [l.strip() for l in p.stdout.splitlines() if l.strip()]


def order(lanes, gym=None):
    known = lane_names(gym)
    return sorted(lanes, key=lambda l: (known.index(l) if l in known else len(known), l))


def report(files, rules, units=None, explain=False, out=None, gym=None, patterns=None):
    out = out or sys.stdout
    hits = match(files, rules, units, patterns)
    for lane in order(hits, gym):
        labels = []
        for _, label in hits[lane]:
            if label not in labels:
                labels.append(label)
        more = " (+%d more)" % (len(labels) - 2) if len(labels) > 2 else ""
        print("%-5s # %s%s" % (lane, "; ".join(labels[:2]), more), file=out)
        if explain:
            for f, label in hits[lane]:
                print("        %s  <- %s" % (f, label), file=out)
    if explain:
        watched = {f for h in hits.values() for f, _ in h}
        loose = [f for f in files if f not in watched]
        if loose:
            print("# watched by no lane:", file=out)
            for f in loose:
                print("        %s" % f, file=out)
    return hits


def check_table(root=None, gym=None, manifests=None, out=None):
    """The table against the gym: the fails as a list, the summary lines printed."""
    out = out or sys.stdout
    gym = gym or GYM
    rules, units, problems = load(root, gym, manifests)
    fails = ["table: " + p for p in problems]
    names = lane_names(gym)
    if (gym / "run.py").is_file():
        for lane in names:
            if lane not in rules:
                fails.append("run.py lane %s has no entry in %s" % (lane, TABLE_NAME))
        for lane in rules:
            if lane not in names:
                fails.append("%s has %s, which is not in run.py's LANES" % (TABLE_NAME, lane))
        print("lanes in run.py: %d; in the table: %d" % (len(names), len(rules)), file=out)
    else:
        print("no run.py in the gym folder yet: the lane names are not compared; in the table: %d" % len(rules), file=out)
    always = (tomllib.loads(table_file(gym).read_text(encoding="utf-8")).get("always") or {}).get("paths", [])
    for p in always:
        if not any(c in p for c in "*?[") and sorted(match([p.rstrip("/") + ("/x" if p.endswith("/") else "")], rules, units)) != sorted(rules):
            fails.append("the always path %s does not select every lane" % p)
    reached = set()
    for rs in rules.values():
        reached |= {lab.split("unit ", 1)[1].split()[0] for k, _, lab in rs if k == "unit"}
    unwatched = sorted(c for c in units if c not in reached and units[c][2])
    print("units no lane reads: %s" % (" ".join(unwatched) or "none"), file=out)
    return fails


def check():
    if not table_file().is_file():
        print("lanes_for: no %s in %s yet; nothing to check" % (TABLE_NAME, GYM), file=sys.stderr)
        return 0
    fails = check_table()
    for f in fails:
        print("FAIL: " + f)
    print("lanes_for check: %s" % ("ok" if not fails else "FAILED"))
    return 1 if fails else 0


SELFTEST_TABLE = """\
version = 1
[always]
paths = ["requirements.lock", "gym/gym_kit.py", "gym/tools/"]
[broad]
paths = ["src/", "tools/", "requirements.lock"]
[units.util]
dir = "src/util"
[units.core]
dir = "src/core"
needs = ["util"]
[units.app]
dir = "src/app"
needs = ["core"]
[units.paint]
dir = "src/paint"
[units.spare]
dir = "src/spare"
[units.harness]
dir = "tools/harness"
needs = ["core"]
own_paths = false
[groups.harness]
paths = ["tools/harness/main.py", "tools/harness/run_*.py"]
units = ["harness"]
[lanes.G1]
paths = ["gym/lanes/g1.py", "gym/prereg/G1.md", "data/g1/"]
units = ["app"]
[lanes.G2]
paths = ["gym/lanes/g2.py"]
uses = ["harness"]
[lanes.G3]
paths = ["gym/lanes/g3.py"]
units = ["util", "plug"]
[lanes.G10]
paths = ["gym/lanes/g10.py"]
broad = true
"""


def remove_tree(path):
    """Remove a temp folder and all in it. A file that is read-only (git's objects on Windows) is made writable and
    tried once more; what still cannot go is left, never an error."""
    import shutil

    def retry(func, p, _exc):
        try:
            os.chmod(p, 0o700)
            func(p)
        except OSError:
            pass

    if sys.version_info >= (3, 12):  # onexc came with 3.12, where onerror is deprecated
        shutil.rmtree(path, onexc=retry)
    else:
        shutil.rmtree(path, onerror=retry)


def selftest():
    """This tool's rules on a scratch tree; nothing of the project is read, and nothing is written outside the temp
    folder."""
    import io
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="foundry-lanes-selftest-")).resolve()  # its real name, so paths compare
    ok, fails = 0, []

    def expect(what, cond, detail=""):
        nonlocal ok
        if cond:
            ok += 1
        else:
            fails.append("%s: %s" % (what, detail))
    try:
        root, gym = tmp / "repo", tmp / "repo" / "gym"
        gym.mkdir(parents=True)
        (gym / TABLE_NAME).write_text(SELFTEST_TABLE, encoding="utf-8")
        (gym / "run.py").write_text('import x\nLANES = {\n    "G1": 1,\n    "G2": 2,\n    "G10": 3,\n    "G3": 4,\n}\n', encoding="utf-8")
        plug = root / "plugins" / "plug"
        plug.mkdir(parents=True)
        (plug / "unit.toml").write_text('[package]\nname = "plug"\n[dependencies]\nextra = { path = "../extra", optional = true }\n'
                                        'paint = { path = "x", default-features = false }\nelsewhere = "1"\n', encoding="utf-8")
        (root / "plugins" / "extra").mkdir()
        (root / "plugins" / "extra" / "unit.toml").write_text('[package]\nname = "extra"\n', encoding="utf-8")
        man = ["plugins/*/unit.toml"]
        pats = list(NOT_BUILT)
        rules, units, problems = load(root, gym, man)
        sel = lambda *files: order(match(list(files), rules, units, pats), gym)  # noqa: E731

        expect("the table loads without problems", not problems, problems)
        expect("lane names come from run.py as text, in its order", lane_names(gym) == ["G1", "G2", "G10", "G3"], lane_names(gym))
        expect("a lane's own path selects it", sel("gym/lanes/g1.py") == ["G1"], sel("gym/lanes/g1.py"))
        expect("a folder prefix selects by any file under it", sel("data/g1/a/b.bin") == ["G1"], sel("data/g1/a/b.bin"))
        expect("a unit's file selects the lanes that name the unit, and the broad lane",
               sel("src/app/main.py") == ["G1", "G10"], sel("src/app/main.py"))
        expect("a needed unit's file selects every lane that reaches it (G1 via app, G2 via its group)",
               sel("src/core/x.py") == ["G1", "G2", "G10"], sel("src/core/x.py"))
        expect("a unit needed two steps away is reached", sel("src/util/u.py") == ["G1", "G2", "G10", "G3"], sel("src/util/u.py"))
        expect("a unit in no lane selects only the broad lane", sel("src/spare/p.py") == ["G10"], sel("src/spare/p.py"))
        expect("a unit's tests/ file and its notes select nothing, the broad lane included",
               sel("src/core/tests/t.py", "src/app/README.md", "src/util/examples/e.py") == [],
               sel("src/core/tests/t.py", "src/app/README.md", "src/util/examples/e.py"))
        expect("a path rule still selects a file the not-built rule covers",
               order(match(["gym/prereg/G1.md"], rules, units, pats), gym) == ["G1"])
        expect("a unit with own_paths = false gives no folder rule: only its listed files select its lanes",
               sel("tools/harness/other.py") == ["G10"] and sel("tools/harness/main.py") == ["G2", "G10"]
               and sel("tools/harness/run_g2.py") == ["G2", "G10"], (sel("tools/harness/other.py"), sel("tools/harness/main.py")))
        expect("an always path selects every lane", sel("requirements.lock") == ["G1", "G2", "G10", "G3"]
               and sel("gym/tools/png.py") == ["G1", "G2", "G10", "G3"], sel("requirements.lock"))
        expect("a docs-only change selects no lane", sel("docs/ROADMAP.md", "README.md", "docs/research/note.md") == [])
        expect("a unit read from a manifest is a unit; its optional need is followed from a lane that names it",
               sel("plugins/plug/a.py") == ["G3"] and sel("plugins/extra/a.py") == ["G3"],
               (sel("plugins/plug/a.py"), sel("plugins/extra/a.py")))
        expect("an edge with default-features = false is followed, but not that unit's optional needs",
               "paint" in unit_closure(["plug"], units) and "elsewhere" not in units, unit_closure(["plug"], units))
        deep = {"a": ("a", {"b": (False, False)}, True), "b": ("b", {"c": (True, True)}, True), "c": ("c", {}, True)}
        expect("an optional need behind a no-defaults edge is not followed; from the unit itself it is",
               sorted(unit_closure(["a"], deep)) == ["a", "b"] and sorted(unit_closure(["b"], deep)) == ["b", "c"])
        expect("without the manifests the lane names an unknown unit, and the table check says so",
               any("G3 names unknown unit plug" in p for p in load(root, gym, [])[2]), load(root, gym, [])[2])

        buf = io.StringIO()
        report(["src/core/x.py", "docs/a.md"], rules, units, explain=True, out=buf, gym=gym, patterns=pats)
        text = buf.getvalue()
        expect("the report prints a lane per line with its rule, in run.py's order, and --explain the loose paths",
               text.splitlines()[0].startswith("G1    # unit core (via app)") and "G2    # harness: unit core (via harness)" in text
               and "G10   # broad" in text and "# watched by no lane:\n        docs/a.md" in text
               and text.index("G2 ") < text.index("G10"), text)

        buf = io.StringIO()
        cf = check_table(root, gym, man, out=buf)
        expect("check passes on the scratch table and lists the units no lane reads",
               not cf and "lanes in run.py: 4; in the table: 4" in buf.getvalue()
               and "units no lane reads: spare" in buf.getvalue(), (cf, buf.getvalue()))
        (gym / "run.py").write_text('LANES = {"G1": 1, "G2": 2, "G10": 3, "G4": 5}\n', encoding="utf-8")
        cf = check_table(root, gym, man, out=io.StringIO())
        expect("check fails for a lane in run.py with no entry, and for an entry that is not a lane",
               any("lane G4 has no entry" in f for f in cf) and any("has G3, which is not" in f for f in cf), cf)
        (gym / "run.py").unlink()
        expect("with no run.py yet, lanes are ordered by name and nothing crashes",
               lane_names(gym) == [] and sel("requirements.lock") == ["G1", "G10", "G2", "G3"], sel("requirements.lock"))
        expect("path_match: a prefix, an exact file, a glob, and a near miss",
               path_match("a/b/c.py", "a/b/") and path_match("a/b", "a/b") and path_match("a/b/c.py", "a/b")
               and path_match("a/x/c.py", "a/*/c.py") and not path_match("a/bc.py", "a/b"))

        # a range and one commit, through git, in a scratch repository (identity by environment, no config written)
        genv = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        genv.update(GIT_AUTHOR_NAME="selftest", GIT_AUTHOR_EMAIL="selftest@example.invalid", GIT_COMMITTER_NAME="selftest",
                    GIT_COMMITTER_EMAIL="selftest@example.invalid", GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")

        def git(*args):
            return subprocess.run(["git", "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false", *args], cwd=root,
                                  capture_output=True, text=True, env=genv)
        try:
            have_git = git("init", "-q", "-b", "main").returncode == 0
        except OSError:
            have_git = False
        if not have_git:
            print("  skip the git cases: git is not on the PATH")
        else:
            for f in ("src/app/main.py", "src/paint/p.py", "docs/a.md"):
                (root / f).parent.mkdir(parents=True, exist_ok=True)
                (root / f).write_text("1\n", encoding="utf-8")
            git("add", "-A")
            git("commit", "-q", "-m", "base")
            (root / "src/app/main.py").write_text("2\n", encoding="utf-8")
            git("commit", "-q", "-am", "app")
            (root / "docs/a.md").write_text("2\n", encoding="utf-8")
            git("commit", "-q", "-am", "docs")
            git("mv", "src/app/main.py", "src/paint/main.py")
            git("commit", "-q", "-m", "move")
            one = changed_files("HEAD~2", root, genv)
            expect("one commit means its diff against its first parent", one == ["src/app/main.py"], one)
            expect("a docs-only commit selects no lane", sel(*changed_files("HEAD~1", root, genv)) == [])
            rng = changed_files("HEAD~3..HEAD~1", root, genv)
            expect("a range lists every path it touches", sorted(rng) == ["docs/a.md", "src/app/main.py"], rng)
            moved = changed_files("HEAD", root, genv)
            expect("a moved file shows both its old and its new path, so the lane it left is selected",
                   sorted(moved) == ["src/app/main.py", "src/paint/main.py"] and "G1" in sel(*moved), moved)
            try:
                changed_files("no-such-rev", root, genv)
                expect("a bad range is a clear error", False, "no SystemExit")
            except SystemExit as e:
                expect("a bad range is a clear error", "failed" in str(e), e)
    finally:
        remove_tree(tmp)
    expect("the selftest leaves no temp folder behind", not tmp.exists(), tmp)
    for f in fails:
        print("FAIL: " + f)
    print("lanes_for selftest: %d ok, %d failed" % (ok, len(fails)))
    return 1 if fails else 0


def main(argv):
    if argv[:1] and argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    if argv[:1] == ["selftest"]:
        return selftest()
    if argv[:1] == ["check"]:
        return check()
    explain = "--explain" in argv
    argv = [a for a in argv if a != "--explain"]
    skip = []
    while "--skip" in argv:
        i = argv.index("--skip")
        if i + 1 >= len(argv):
            print("lanes_for: --skip needs a glob", file=sys.stderr)
            return 2
        skip.append(argv[i + 1])
        del argv[i:i + 2]
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 2
    if argv[0] == "--files":
        files = [a.replace("\\", "/") for a in argv[1:]]
        files = [f[2:] if f.startswith("./") else f for f in files]
    elif len(argv) == 1:
        files = changed_files(argv[0])
    else:
        print(__doc__)
        return 2
    if not table_file().is_file():
        print("lanes_for: no %s in %s yet; no lane is selected" % (TABLE_NAME, GYM), file=sys.stderr)
        return 0
    files = [f for f in files if not any(fnmatch.fnmatchcase(f, g) for g in skip)]
    rules, units, problems = load()
    for p in problems:
        print("lanes_for: table: %s" % p, file=sys.stderr)
    report(files, rules, units, explain)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
