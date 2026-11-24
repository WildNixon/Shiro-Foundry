#!/usr/bin/env python3
"""Shiro Foundry: the project profile every tool reads.

A project that runs a foundry keeps one small file, `.foundry/foundry.toml`, in its main checkout. It names the
project, the crew, the paths and the limits; every tool (office.py, rq.py, board.py, journal.py, flow.py, ...)
reads it through this module, and falls back to DEFAULTS for whatever the file leaves out. A project with no
profile at all still works on the defaults.

    python foundry_profile.py show [KEY]     the profile in force as JSON (KEY: one dotted key, e.g. paths.office)
    python foundry_profile.py where          the checkout, the main checkout and the profile file in use
    python foundry_profile.py selftest

In code:

    import foundry_profile as fp
    P = fp.load(__file__)            # the checkout this script lies in
    P.get("limits.usage_stop")       # a dotted key, defaults filled in
    P.path("office")                 # paths.office as an absolute Path under the MAIN checkout
    P.local("state")                 # paths.state under THIS checkout (a worktree's own copy)
    P.py                             # the interpreter to name in briefs and help text
    P.badge_prefix, P.crew, P.project
    P.skill("employee")              # the skill name a brief tells a hire to load

Environment overrides (tests and odd layouts): FOUNDRY_ROOT (the checkout), FOUNDRY_MAIN (the main checkout),
FOUNDRY_PROFILE (the toml file), and FOUNDRY_<SECTION>_<KEY> for any scalar key, e.g. FOUNDRY_PATHS_OFFICE.
Standard library only; Python 3.11 or newer (tomllib).
"""

import copy
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

VERSION = "0.2.0"

DEFAULTS = {
    "project": "",                 # the project's name as people say it; empty: the main checkout's folder name
    "crew": "",                    # a short lower-case name for this crew (journal carry); empty: from project
    "badge_prefix": "FB1",         # the first word of every badge line
    "main_branch": "main",
    "commands": {
        "python": "",              # the interpreter briefs and help text name; empty: the one running the tool
        "test": "",                # the project's own test command; every builder's brief names it
    },
    "paths": {                     # relative to the checkout unless absolute
        "tools": "scripts/foundry",
        "office": "out/foundry",   # the crew office: git-ignored, shared by every worktree
        "state": "docs/progress/state.json",
        "map": "docs/progress-map.html",
        "roadmap": "docs/ROADMAP.md",
        "flow": "docs/flow",       # the road graph asset and the plan files (checked in)
        "flow_out": "out/flow",    # built pages (git-ignored)
        "reviews": "docs/reviews",
        "research": "docs/research",
        "handoff": "docs/handoff",
        "decisions": "docs/decisions",
        "gym": "gym",              # series/, prereg/, contracts/, charts/, grades/, lanes/ live under it
        "rules": ".foundry/rules.md",
    },
    "skills": {
        "founder": "foundry-founder",
        "manager": "foundry-manager",
        "employee": "foundry-employee",
        "flow": "foundry-flow",
        "bench": "foundry-bench",
        "gym": "gym",
    },
    "slots": {                     # the rota a new state.json starts with; state.json's rota.slots wins once set
        "day": "06:00",
        "swing": "14:00",
        "night": "22:00",
        "round_every": "2h",
        "review_window_min": 90,
    },
    "limits": {
        "usage_stop": 80,          # percent of the plan's weekly usage at which the manager stops and asks
        "crew_max": 4,             # the headcount the starter shift gets; after that each shift names its own
        "stale_min": 45,           # an employee silent this long reads STALE
        "overdue_min": 15,         # this far past its finish reads OVERDUE
        "manager_stale_min": 120,
    },
    "resource": {                  # the one shared thing the crew queues for (a VM, a GPU, a device); name "" = none
        "name": "",
        "seats": ["main"],         # how many jobs it takes at once, each by name
        "seat_env": "FOUNDRY_SEAT",  # the variable a queued command reads its seat from
        "seats_env": "FOUNDRY_SEATS",  # every seat held, for a whole-resource job
        "prepare": "",             # a command line run in the seat before each job ("" = none)
        "exclusive": "",           # a regex: jobs whose text matches never hold seats at the same time
        "status": "",              # a command that prints the resource's own health (disk, memory)
        "default_max": "30m",
        "shell": "",               # the shell a queued command line runs in; empty: bash on PATH, else sh
        "enforce_max": False,      # true: a `run` job still going at its --max plus max_grace is ended (exit 124)
        "max_grace": "2m",
    },
    "measure": {                   # how "done" is decided: the gym
        "done_means": "the milestone's gym lane says PASS",
        "lane_pattern": r"\bG(?:X\d+[a-z]?|L\d+|\d+)\b",
        "counted": "",             # the command of a counted run, with <lane>
        "dev": "",                 # the command of a dev (uncounted) run
        "sweep": "",               # the command that runs every lane, if the project has one
        "grader_owned": ["gym/prereg", "gym/lanes", "gym/run.py", "gym/gym_kit.py"],
        "records": ["gym/series", "gym/charts", "gym/grades"],
        "selftest": "",            # the gym's own selftest command
        "grader_no_read": [],      # paths a grader never opens (the builder's code)
        "handin_check": "",        # a command office.py handin runs when a branch changes handin_check_paths
        "handin_check_paths": [],  # globs
        "handin_check_timeout_s": 900,
        "vendored_paths": [],      # globs a badge should not own without saying so
        "unit_manifests": [],      # lanes_for.py: globs of the build units' manifest files
        "not_built": ["tests/", "benches/", "examples/", "*.md"],  # lanes_for.py: paths that move no lane
        "sweep_skip": [],          # sweep.py: globs left out of its "did the tree move" check
        "no_verdict_exits": [2, 3],  # sweep.py: exit codes of the counted command that mean "no verdict"
    },
    "roadmap": {                   # the shape of ROADMAP.md's tables (the foundry-founder skill: references/roadmap-format.md)
        "requirement_id": r"[A-Z0-9]+-\d+",
        "tiers": ["P0", "P1", "P2"],
        "stage_id": r"R\d",
        "milestone_id": r"M\d+",
        "decision_id": r"D\d+",
        "goal": "1.0",
        "late_stages": [],         # named stages between the numbered ones and the goal, in order (e.g. ["Beta"])
        "block_id": r"[QP]\d+[a-z]?",  # how a push block's title opens on the map
    },
    "board": {
        "phases_title": "Phases",  # the heading over state.phases
        "absolute_commands": False,  # true: the map prints tool commands with absolute paths
    },
    "git": {
        "push": False,             # the crew never pushes unless the founder's profile says so
        "merge": "cherry-pick by commit",
        "worktrees": ".claude/worktrees",
        "branch_prefix": "claude/",
    },
    "titles": {},                  # extra hire cards: name -> {like, role, kinds, does, may_write, hands_in, independent}
    "models": {},                  # role or title -> model id; empty: the session's own
    "flagged": {},                 # title -> {"model": ..., "trailer": ...}: work that gets a heavy review
    "crews": {},                   # other crews that work this way: name -> {"lessons": "<path to their outbox>"}
    "hooks": {
        "protect": ["docs/flow/road.graph.json", "docs/flow/road.edits.jsonl"],
        "protect_reason": "",      # text that replaces the hook's refusal message
    },
}


def _run_git(args, cwd):
    try:
        r = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return ""
    return r.stdout.strip() if r.returncode == 0 else ""


def checkout(start=None):
    """The checkout a script or a folder lies in: FOUNDRY_ROOT, else the nearest parent holding .foundry or .git."""
    env = os.environ.get("FOUNDRY_ROOT")
    if env:
        return Path(env).resolve()
    p = Path(start if start is not None else os.getcwd()).resolve()
    if p.is_file():
        p = p.parent
    for d in (p, *p.parents):
        if (d / ".foundry").is_dir() or (d / ".git").exists():
            return d
    return p


def main_checkout(root=None):
    """The main checkout of the repository `root` belongs to (a worktree's parent repo); `root` itself without git."""
    env = os.environ.get("FOUNDRY_MAIN")
    if env:
        return Path(env).resolve()
    root = Path(root) if root is not None else checkout()
    common = _run_git(["rev-parse", "--path-format=absolute", "--git-common-dir"], root)
    if common and Path(common).name == ".git":
        return Path(common).parent
    return root


def _merge(base, over):
    for k, v in over.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _merge(base[k], v)
        else:
            base[k] = v
    return base


def _shape_problems(doc, like=None, pre=""):
    """Keys of a profile whose value is not the kind the defaults have (a table written as a string, a list as a
    number). A wrong kind would otherwise surface as a traceback deep in some tool."""
    like = DEFAULTS if like is None else like
    out = []
    for k, v in doc.items():
        if k not in like:
            continue
        want = like[k]
        if isinstance(want, dict):
            if not isinstance(v, dict):
                out.append(f"`{pre}{k}` must be a table ([{pre}{k}]), not {type(v).__name__}")
            elif want:
                out.extend(_shape_problems(v, want, f"{pre}{k}."))
        elif isinstance(want, list):
            if not isinstance(v, list):
                out.append(f"`{pre}{k}` must be a list, not {type(v).__name__}")
        elif isinstance(want, bool):
            if not isinstance(v, bool):
                out.append(f"`{pre}{k}` must be true or false, not {type(v).__name__}")
        elif isinstance(want, (int, float)):
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                out.append(f"`{pre}{k}` must be a number, not {type(v).__name__}")
        elif isinstance(want, str):
            if not isinstance(v, str):
                out.append(f"`{pre}{k}` must be text in quotes, not {type(v).__name__}")
    return out


def _coerce(text, like):
    if isinstance(like, bool):
        return text.strip().lower() in ("1", "true", "yes", "on")
    if isinstance(like, int):
        try:
            return int(text)
        except ValueError:
            return like
    if isinstance(like, list):
        return [t.strip() for t in text.split(",") if t.strip()]
    return text


def _env_overrides(data):
    for sec, val in list(data.items()):
        if isinstance(val, dict):
            for k, like in list(val.items()):
                if isinstance(like, dict):
                    continue
                e = os.environ.get(f"FOUNDRY_{sec}_{k}".upper())
                if e is not None:
                    val[k] = _coerce(e, like)
        else:
            e = os.environ.get(f"FOUNDRY_{sec}".upper())
            if e is not None and sec not in ("root", "main", "profile"):
                data[sec] = _coerce(e, val)
    return data


class Profile:
    def __init__(self, data, root, main, file):
        self.data = data
        self.root = Path(root)      # this checkout (a worktree, or the main checkout itself)
        self.main = Path(main)      # the main checkout: the office and the live state are here
        self.file = file            # the toml read, or None when the defaults stand alone
        self.problems = []          # what was wrong with the file, for `where` and the tools' doctor lines

    def get(self, key, default=None):
        cur = self.data
        for part in key.split("."):
            if not isinstance(cur, dict) or part not in cur:
                return default
            cur = cur[part]
        return cur

    def _resolve(self, base, name):
        v = self.get(f"paths.{name}")
        if v is None:
            raise KeyError(f"the profile has no paths.{name}")
        p = Path(v)
        return p if p.is_absolute() else base / p

    def path(self, name):
        """paths.<name> under the main checkout (the office, the live state, the built pages)."""
        return self._resolve(self.main, name)

    def local(self, name):
        """paths.<name> under this checkout (a worktree's own copy of a tracked file)."""
        return self._resolve(self.root, name)

    def rel(self, name):
        """paths.<name> as written, with forward slashes, for git pathspecs and printed commands."""
        return str(self.get(f"paths.{name}")).replace("\\", "/")

    def gym(self, *parts, local=True):
        return (self.local("gym") if local else self.path("gym")).joinpath(*parts)

    @property
    def project(self):
        return self.get("project") or self.main.name

    @property
    def crew(self):
        c = self.get("crew") or self.project
        return "".join(ch if ch.isalnum() else "-" for ch in c.lower()).strip("-") or "crew"

    @property
    def badge_prefix(self):
        return str(self.get("badge_prefix") or "FB1").upper()

    @property
    def py(self):
        """The interpreter as a brief should print it (quoted when it has a space)."""
        p = self.get("commands.python") or sys.executable or "python"
        p = str(p).replace("\\", "/")
        return f'"{p}"' if " " in p else p

    def tool(self, name):
        """A tool's command line as a brief should print it: the interpreter plus the tool's absolute path."""
        t = (self.path("tools") / name)
        s = str(t).replace("\\", "/")
        return f'{self.py} "{s}"' if " " in s else f"{self.py} {s}"

    def skill(self, level):
        return self.get(f"skills.{level}") or f"foundry-{level}"

    def has_resource(self):
        return bool(self.get("resource.name"))

    def slots(self):
        """The default rota as state.json writes it: [{"id": "day", "start": "06:00"}, ...] in clock order."""
        out = [{"id": k, "start": v} for k, v in (self.get("slots") or {}).items()
               if isinstance(v, str) and len(v) == 5 and v[2] == ":"]
        return sorted(out, key=lambda s: s["start"])


def load(start=None, strict=True):
    """The profile for the checkout `start` lies in (a script's __file__, a folder, or the working directory).

    A profile file that exists and cannot be read is never replaced by the defaults in silence: a tool running on
    the defaults would look for the office in another folder, lose the shared resource and with it the counted-run
    freeze, and forget which files only a grader may change. So load() says what is wrong on stderr and exits 2.
    strict=False returns the defaults with the trouble listed in `.problems` (for `where`, `founder.py doctor` and
    the hooks, which must go on)."""
    root = checkout(start)
    main = main_checkout(root)
    data = copy.deepcopy(DEFAULTS)
    file, problems = None, []
    env = os.environ.get("FOUNDRY_PROFILE")
    candidates = [Path(env)] if env else [root / ".foundry" / "foundry.toml", main / ".foundry" / "foundry.toml"]
    if env and not Path(env).is_file():  # a mistyped name must not mean "the defaults"
        problems.append(f"{env}: FOUNDRY_PROFILE names no file")
    for c in candidates:
        if c.is_file():
            try:
                with open(c, "rb") as f:
                    doc = tomllib.load(f)
                wrong = _shape_problems(doc)
                if wrong:
                    problems.extend(f"{c}: {w}" for w in wrong)
                else:
                    _merge(data, doc)
                    file = c
            except UnicodeDecodeError as e:  # saved as UTF-16 by an editor or a shell redirect
                problems.append(f"{c}: not UTF-8 text ({e.reason} at byte {e.start}); save it as UTF-8")
            except (OSError, ValueError, RecursionError) as e:  # TOMLDecodeError is a ValueError
                problems.append(f"{c}: {e}")
            break
    _env_overrides(data)
    p = Profile(data, root, main, file)
    p.problems = problems
    if problems and strict:
        for line in problems:
            print(f"foundry: the profile cannot be read: {line}", file=sys.stderr)
        print("foundry: fix the file (`foundry_profile.py where` checks it); nothing was done", file=sys.stderr)
        raise SystemExit(2)
    return p


def selftest():
    import tempfile
    ok, bad = 0, []

    def check(name, cond):
        nonlocal ok
        if cond:
            ok += 1
        else:
            bad.append(name)

    saved = {k: os.environ.pop(k) for k in list(os.environ) if k.startswith("FOUNDRY_")}
    try:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "my proj"
            (root / ".foundry").mkdir(parents=True)
            (root / "scripts" / "foundry").mkdir(parents=True)
            p = load(root)
            check("defaults without a file", p.file is None and p.badge_prefix == "FB1")
            check("project from the folder", p.project == "my proj" and p.crew == "my-proj")
            check("office under main", p.path("office") == p.main / "out" / "foundry")
            (root / ".foundry" / "foundry.toml").write_text(
                'project = "Kestrel"\nbadge_prefix = "kb1"\n[paths]\noffice = "out/crew"\n'
                '[resource]\nname = "dev VM"\nseats = ["a", "b"]\n[crews.other]\nlessons = "x.jsonl"\n',
                encoding="utf-8")
            p = load(root / "scripts" / "foundry")
            check("found from a subfolder", p.root == root.resolve())
            check("file values", p.project == "Kestrel" and p.badge_prefix == "KB1" and p.rel("office") == "out/crew")
            check("untouched defaults stay", p.rel("state") == "docs/progress/state.json" and p.get("limits.usage_stop") == 80)
            check("resource", p.has_resource() and p.get("resource.seats") == ["a", "b"])
            check("crews table", p.get("crews.other.lessons") == "x.jsonl")
            check("slots in order", [s["id"] for s in p.slots()] == ["day", "swing", "night"])
            check("tool line quotes a spaced path", p.tool("office.py").endswith('office.py"'))
            check("missing key", p.get("nope.nothing", 7) == 7)
            os.environ["FOUNDRY_PATHS_OFFICE"] = str(Path(td) / "office")
            os.environ["FOUNDRY_LIMITS_USAGE_STOP"] = "95"
            os.environ["FOUNDRY_RESOURCE_SEATS"] = "a, b"
            p = load(root)
            check("env path", p.path("office") == Path(td) / "office")
            check("env int and list", p.get("limits.usage_stop") == 95 and p.get("resource.seats") == ["a", "b"])
            for k in ("FOUNDRY_PATHS_OFFICE", "FOUNDRY_LIMITS_USAGE_STOP", "FOUNDRY_RESOURCE_SEATS"):
                os.environ.pop(k)
            (root / ".foundry" / "foundry.toml").write_text("project = [broken", encoding="utf-8")
            p = load(root, strict=False)
            check("a broken file is reported, defaults stand", p.problems and p.badge_prefix == "FB1")
            import contextlib, io
            code = None
            with contextlib.redirect_stderr(io.StringIO()) as err:
                try:
                    load(root)
                except SystemExit as e:
                    code = e.code
            check("a broken file stops a tool: exit 2, the reason on stderr",
                  code == 2 and "cannot be read" in err.getvalue())
            (root / ".foundry" / "foundry.toml").write_bytes('project = "x"\n'.encode("utf-16"))
            p = load(root, strict=False)
            check("a file that is not UTF-8 is a problem, not a traceback", any("not UTF-8" in x for x in p.problems))
            (root / ".foundry" / "foundry.toml").write_text('paths = "x"\n[resource]\nseats = "a"\n[limits]\nusage_stop = "80"\n',
                                                            encoding="utf-8")
            p = load(root, strict=False)
            check("wrong kinds are named, the defaults stand",
                  len(p.problems) == 3 and p.rel("office") == "out/foundry" and p.get("limits.usage_stop") == 80)
            (root / ".foundry" / "foundry.toml").write_text('project = "ok"\n[titles.x]\nlike = "fixer"\n[models]\nbuilder = "m"\n',
                                                            encoding="utf-8")
            p = load(root, strict=False)
            check("free tables (titles, models) take any keys", not p.problems and p.get("titles.x.like") == "fixer")
            os.environ["FOUNDRY_PROFILE"] = str(root / "nope.toml")
            p = load(root, strict=False)
            check("FOUNDRY_PROFILE naming no file is a problem", any("names no file" in x for x in p.problems))
            os.environ.pop("FOUNDRY_PROFILE")
            check("defaults were not mutated", DEFAULTS["paths"]["office"] == "out/foundry" and DEFAULTS["badge_prefix"] == "FB1")
    finally:
        os.environ.update(saved)
    for b in bad:
        print("FAIL", b)
    print(f"foundry_profile selftest: {ok} ok, {len(bad)} failed")
    return 1 if bad else 0


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "show"
    if cmd == "selftest":
        return selftest()
    p = load(strict=False)
    if cmd == "where":
        print(f"checkout       {p.root}")
        print(f"main checkout  {p.main}")
        print(f"profile        {p.file or 'none (defaults)'}")
        for line in p.problems:
            print(f"PROBLEM        {line}")
        return 1 if p.problems else 0
    if cmd == "show":
        v = p.get(argv[2]) if len(argv) > 2 else p.data
        print(json.dumps(v, indent=1, ensure_ascii=False))
        for line in p.problems:  # what is printed above is then the defaults, not the file
            print(f"PROBLEM the profile cannot be read, so these are the defaults: {line}", file=sys.stderr)
        return 1 if p.problems else 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
