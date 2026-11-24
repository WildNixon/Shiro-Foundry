#!/usr/bin/env python3
"""Shiro Foundry: the founder's own tool.

    python founder.py init [--project NAME] [--resource NAME] [--gym]
                                 found a project: write the starter profile (.foundry/foundry.toml), the rules
                                 file, a starter roadmap, the state (through board.py init) and the git-ignore
                                 lines for the office and the built pages. --gym also scaffolds a starter gym
                                 (gym_init.py init). Never overwrites: a file that exists is kept and named
    python founder.py doctor [--selftest]
                                 is the foundry installed and whole: the interpreter, the profile, every tool,
                                 every skill, the office ignored by git, the state, the roadmap, the hooks.
                                 --selftest also runs each tool's selftest. Exit 1 when a PROBLEM line printed
    python founder.py audit [--json]
                                 the roadmap audit in one read: requirements nobody works toward, the queue's
                                 gaps, decisions that gate what is queued, failures with no plan, usage against
                                 the stop, and what flow.py and board.py found. Writes nothing
    python founder.py push new NAME [--title TEXT] [--by FDR-1]
                                 a push plan's starter file under paths.handoff, with the usage budget, the
                                 shared resource's seats and the open decisions filled in from the state
    python founder.py selftest

The founder writes what the manager runs (the roadmap, the profile, the queue of shifts, the decision register);
this tool only scaffolds and reads. The roadmap's own checks are flow.py selftest's, the state's are board.py
check's; audit gathers them and adds the ones that sit between the two files.
Standard library only.
"""

import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import foundry_profile as fp  # noqa: E402

TOOLS = ("foundry_profile.py", "founder.py", "office.py", "rq.py", "board.py", "journal.py", "flow.py",
         "flow_graph.py", "flow_page.py", "plan_flow.py", "lanes_for.py", "sweep.py", "gym_init.py")
SELFTESTS = ("foundry_profile.py", "founder.py", "office.py", "rq.py", "board.py", "journal.py", "plan_flow.py",
             "sweep.py")
SKILLS = ("founder", "manager", "employee", "flow", "bench", "gym")
MET = ("PASS", "Decided")
STARTER_BANNER = ("<!-- STARTER: every row below is an example of the shape the tools read. "
                  "Replace all of it with this project's own goal, stages, milestones and requirements. -->\n\n")


def now():
    env = os.environ.get("FOUNDRY_NOW")
    t = dt.datetime.fromtimestamp(float(env)) if env else dt.datetime.now()
    return t.astimezone()


def stamp(t=None):
    t = t or now()
    s = t.strftime("%Y-%m-%dT%H:%M%z")
    return s[:-2] + ":" + s[-2:]


def templates():
    for d in (HERE / "templates", HERE.parent / "profile"):
        if d.is_dir():
            return d
    return None


def run(args, cwd, timeout=300):
    try:
        r = subprocess.run(args, cwd=str(cwd), capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
        return r.returncode, (r.stdout or ""), (r.stderr or "")
    except (OSError, subprocess.SubprocessError) as e:
        return 127, "", str(e)


def git(root, *args):
    return run(["git", "-C", str(root), *args], root, timeout=30)


def ignored(root, rel):
    """True/False when git can say whether `rel` is ignored; None outside a repository."""
    code, _, err = git(root, "check-ignore", "-q", rel.rstrip("/") + "/x")
    if code in (0, 1):
        return code == 0
    return None


def read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


# ---------------------------------------------------------------------------------------------------------- init

def set_toml_value(text, section, key, value):
    """Set one `key = "..."` line in a template: top level when section is None, else inside [section]."""
    lines, cur, done = text.split("\n"), None, False
    for i, line in enumerate(lines):
        m = re.match(r"\s*\[([^\]]+)\]", line)
        if m and not line.lstrip().startswith("#"):
            cur = m.group(1)
            continue
        if cur == section and re.match(rf"{re.escape(key)}\s*=", line):
            tail = re.search(r"\s+#.*$", line)
            lines[i] = f'{key} = {json.dumps(value)}' + (tail.group(0) if tail else "")
            done = True
            break
    return "\n".join(lines), done


def cmd_init(argv):
    P = fp.load(strict=False)
    root = P.main
    project = opt(argv, "--project") or P.project
    resource = opt(argv, "--resource")
    tdir = templates()
    out = []

    def write(path, text, what):
        if path.exists():
            out.append(f"kept    {path.relative_to(root)} (it exists)")
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        out.append(f"wrote   {path.relative_to(root)}: {what}")
        return True

    prof = (tdir / "foundry.example.toml").read_text(encoding="utf-8") if tdir and (tdir / "foundry.example.toml").is_file() \
        else 'project = ""\ncrew = ""\n\n[resource]\nname = ""\n'
    prof, _ = set_toml_value(prof, None, "project", project)
    crew = "".join(ch if ch.isalnum() else "-" for ch in project.lower()).strip("-") or "crew"
    prof, _ = set_toml_value(prof, None, "crew", crew)
    if resource:
        prof, _ = set_toml_value(prof, "resource", "name", resource)
    write(root / ".foundry" / "foundry.toml", prof, "the profile; fill in the limits with the user")

    rules = (tdir / "rules.example.md").read_text(encoding="utf-8") if tdir and (tdir / "rules.example.md").is_file() \
        else "# This project's rules and lessons\n\n## Always\n\n## The host\n"
    write(root / ".foundry" / "rules.md", rules, "the rules file; replace each bracketed line or delete it")

    P = fp.load(root)  # the profile just written
    road = (tdir / "ROADMAP.example.md").read_text(encoding="utf-8") if tdir and (tdir / "ROADMAP.example.md").is_file() \
        else f"# {project}: roadmap\n\n## Goal\n\n(One paragraph the user agrees with, then the checks that say it is reached.)\n"
    write(P.path("roadmap"), STARTER_BANNER + road, "a starter roadmap in the shape the tools read")

    gi = root / ".gitignore"
    have = gi.read_text(encoding="utf-8") if gi.is_file() else ""
    add = []
    # the office, the built pages, and the folder the crew's worktrees live in: an untracked worktree folder would
    # make the main checkout read as dirty to every counted run
    for rel in (P.rel("office"), P.rel("flow_out"), str(P.get("git.worktrees") or ""),
                "out/sweeps",                            # sweep.py's --out folders must be git-ignored
                "out/gym" if "--gym" in argv else ""):  # the gym runner's run folders
        rel = rel.replace("\\", "/").strip("/")
        if not rel or Path(rel).is_absolute():
            continue
        if ignored(root, rel) is not True and f"/{rel}/" not in have.split():
            add.append(f"/{rel}/")
    if add:
        with open(gi, "a", encoding="utf-8", newline="\n") as f:
            head = "# Shiro Foundry: the crew office, built pages, run folders and crew worktrees\n"
            f.write(("" if have.endswith("\n") or not have else "\n") + ("" if "# Shiro Foundry:" in have else head)
                    + "\n".join(add) + "\n")
        out.append(f"added   .gitignore: {', '.join(add)}")

    board = HERE / "board.py"
    if P.path("state").exists():
        out.append(f"kept    {P.rel('state')} (it exists)")
    elif board.is_file():
        code, so, se = run([sys.executable, str(board), "init"], root)
        first = (so.strip().splitlines() or se.strip().splitlines() or [""])[0].strip()
        out.append((f"wrote   {P.rel('state')}: the starter state (board.py init)" if code == 0
                    else f"PROBLEM {P.rel('state')} (board.py init): {first}"))
    else:
        out.append("PROBLEM board.py is not beside founder.py: the state was not written")

    if "--gym" in argv:  # the smallest gym the tools can read, for the first grader to start from
        gi_tool = HERE / "gym_init.py"
        if gi_tool.is_file():
            code, so, se = run([sys.executable, str(gi_tool), "init"], root)
            for line in (so or se).strip().splitlines():
                out.append(("        " if code == 0 else "PROBLEM ") + line.strip())
        else:
            out.append("PROBLEM gym_init.py is not beside founder.py: the gym was not scaffolded")

    for line in out:
        print(line)
    print("\nNext: `founder.py doctor`, then the goal and the requirements with the user (/foundry-founder found).")
    return 1 if any(l.startswith("PROBLEM") for l in out) else 0


# -------------------------------------------------------------------------------------------------------- doctor

def cmd_doctor(argv):
    P = fp.load(strict=False)
    root, lines = P.main, []

    def say(kind, text):
        lines.append((kind, text))

    v = sys.version_info
    say("ok" if v >= (3, 11) else "PROBLEM", f"python {v.major}.{v.minor}.{v.micro} ({sys.executable})"
        + ("" if v >= (3, 11) else ": 3.11 or newer is needed (tomllib)"))
    if P.file:
        say("ok", f"profile {P.file}")
    elif not P.problems:
        say("note", "no .foundry/foundry.toml: the defaults are in force (`founder.py init` writes one)")
    for prob in P.problems:
        say("PROBLEM", f"profile does not parse: {prob}")
    tools = P.path("tools")
    here_is_tools = tools.resolve() == HERE
    if not here_is_tools:
        say("note", f"this founder.py runs from {HERE}, not from paths.tools ({tools}): briefs will name paths.tools")
    missing = 0
    for t in TOOLS:
        if not (HERE / t).is_file():
            say("PROBLEM", f"tool missing beside founder.py: {t}")
            missing += 1
        elif not here_is_tools and not (tools / t).is_file():
            say("PROBLEM", f"tool missing in paths.tools: {t} (run install.py for this project)")
            missing += 1
    if not missing:
        say("ok", f"tools: all {len(TOOLS)} present in {P.rel('tools')}")
    home = Path(os.environ.get("FOUNDRY_HOME") or Path.home()) / ".claude" / "skills"
    for level in SKILLS:
        name = P.skill(level)
        where = [d for d in (root / ".claude" / "skills", home) if (d / name / "SKILL.md").is_file()]
        if where:
            say("ok", f"skill {name} ({'project' if where[0] != home else 'user'})")
        else:
            say("PROBLEM", f"skill {name} is not installed (looked in {root / '.claude' / 'skills'} and {home})")
    for name in ("office", "flow_out"):
        rel = P.rel(name)
        ig = None if Path(rel).is_absolute() else ignored(root, rel)
        if ig is False:
            say("PROBLEM", f"paths.{name} ({rel}) is not git-ignored: every punch or build would dirty the tree")
        elif ig is None and not Path(rel).is_absolute():
            say("note", f"not a git repository here: cannot check that {rel} is ignored")
        else:
            say("ok", f"paths.{name} ({rel}) is outside git's view")
    wt = str(P.get("git.worktrees") or "").replace("\\", "/").strip("/")
    if wt and not Path(wt).is_absolute() and ignored(root, wt) is False:
        say("PROBLEM", f"git.worktrees ({wt}) is not git-ignored: the first crew worktree would make the main checkout "
                       "read as dirty to a counted run (add it to .gitignore)")
    say("ok" if P.path("state").is_file() else "PROBLEM",
        f"state {P.rel('state')}" + ("" if P.path("state").is_file() else " is missing (`board.py init`)"))
    if P.path("state").is_file() and read_json(P.path("state")) is None:
        say("PROBLEM", f"state {P.rel('state')} is not valid JSON")
    if P.path("roadmap").is_file():
        text = P.path("roadmap").read_text(encoding="utf-8", errors="replace")
        say("note" if text.startswith("<!-- STARTER") else "ok",
            f"roadmap {P.rel('roadmap')}" + (" is still the starter: the founder has not written it" if text.startswith("<!-- STARTER") else ""))
    else:
        say("PROBLEM", f"roadmap {P.rel('roadmap')} is missing")
    if not P.path("rules").is_file():
        say("note", f"no rules file ({P.rel('rules')}): briefs will name none")
    if P.has_resource():
        say("ok", f"shared resource: {P.get('resource.name')} ({len(P.get('resource.seats') or [])} seat(s))")
        if not P.get("measure.counted"):
            say("note", "measure.counted is empty: the manager has no pinned counted-run command to queue")
    else:
        say("note", "no shared resource named: rq.py and the queue's freeze are off")
    hooks, settings = root / ".claude" / "hooks", root / ".claude" / "settings.json"
    stext = settings.read_text(encoding="utf-8", errors="replace") if settings.is_file() else ""
    for h in ("graph_readonly.py", "no_python_stdin.py"):
        if (hooks / h).is_file() and h in stext:
            say("ok", f"hook {h} installed")
        elif (hooks / h).is_file():
            say("note", f"hook {h} is in .claude/hooks but .claude/settings.json does not run it")
        else:
            say("note", f"hook {h} not installed" + (": the road graph's files are protected only by the rule"
                                                      if h.startswith("graph") else " (only needed where the shell hangs on python stdin)"))
    try:
        import segno  # noqa: F401
        say("ok", "segno is installed: badges get QR plates")
    except ImportError:
        say("note", "segno is not installed: badges work, their QR plates are not drawn (`pip install segno`)")
    if "--selftest" in argv:
        for t in SELFTESTS:
            if (HERE / t).is_file():
                code, so, se = run([sys.executable, str(HERE / t), "selftest"], HERE, timeout=900)
                last = ((so.strip().splitlines() or [""])[-1] or (se.strip().splitlines() or [""])[-1])[:160]
                say("ok" if code == 0 else "PROBLEM", f"selftest {t}: {last}")
    for kind, text in lines:
        print(f"{kind:<8}{text}")
    bad = sum(1 for k, _ in lines if k == "PROBLEM")
    print(f"\ndoctor: {bad} problem(s), {sum(1 for k, _ in lines if k == 'note')} note(s)")
    return 1 if bad else 0


# --------------------------------------------------------------------------------------------------------- audit

def roadmap_rows(P, text):
    """Requirement rows as the board reads them: | ID | tier | status | ... ."""
    rid, tiers = P.get("roadmap.requirement_id"), P.get("roadmap.tiers") or ["P0", "P1", "P2"]
    tier = "|".join(re.escape(t) for t in tiers)
    row = re.compile(rf"^\| ({rid}) \| ({tier})(?:→(?:{tier})\*)? \| (PASS|Part|Planned|Decided|Open) \|([^\n]*)$", re.M)
    return [{"id": m.group(1), "tier": m.group(2), "status": m.group(3), "rest": m.group(4), "at": m.start()}
            for m in row.finditer(text)]


def audit(P, at=None):
    at = at or now()
    out = {"at": stamp(at), "problems": [], "findings": {}, "not_read": []}
    F = out["findings"]
    road = P.path("roadmap")
    text = road.read_text(encoding="utf-8", errors="replace") if road.is_file() else ""
    if not text:
        out["not_read"].append(f"{P.rel('roadmap')}: missing")
    elif text.startswith("<!-- STARTER"):
        out["problems"].append(f"{P.rel('roadmap')} is still the starter: nothing in it is this project's")
    rows = roadmap_rows(P, text) if text else []
    tiers = P.get("roadmap.tiers") or ["P0"]
    top = tiers[0]
    mid = re.compile(rf"\b{P.get('roadmap.milestone_id')}\b")
    if rows:
        by_tier = {}
        for r in rows:
            t = by_tier.setdefault(r["tier"], {"met": 0, "total": 0})
            t["total"] += 1
            t["met"] += r["status"] in MET
        F["distance"] = by_tier
        # A requirement is worked toward when a milestone id stands in its own row, or its id is named elsewhere
        # in the roadmap (a milestone's Closes line, a stage's exit).
        orphans = []
        for r in rows:
            if r["tier"] != top or r["status"] in MET:
                continue
            elsewhere = len(re.findall(rf"(?<![A-Z0-9-]){re.escape(r['id'])}(?![0-9])", text)) > 1
            if not mid.search(r["rest"]) and not elsewhere:
                orphans.append(r["id"])
        F["top_tier_no_milestone"] = orphans
        seen = {}
        for r in rows:
            seen.setdefault(r["id"], 0)
            seen[r["id"]] += 1
        F["duplicate_ids"] = sorted(i for i, n in seen.items() if n > 1)
    state = read_json(P.path("state"))
    if state is None:
        out["not_read"].append(f"{P.rel('state')}: missing or not valid JSON")
        state = {}
    shift, queue = state.get("shift") or {}, state.get("queue") or []
    gaps = []
    for s in [shift, *queue]:
        if not s:
            continue
        sid = s.get("id") or "(no id)"
        if not s.get("milestone"):
            gaps.append(f"{sid}: names no milestone")
        if not s.get("blocks"):
            gaps.append(f"{sid}: has no blocks")
        elif s.get("milestone") and not any(b.get("checkpoint") for b in s["blocks"]):
            gaps.append(f"{sid}: no block carries a checkpoint, so nothing in it runs the counted gym")
        if "crew_max" not in s:
            gaps.append(f"{sid}: no crew_max (the profile's default applies)")
    F["queue_gaps"] = gaps
    F["queued_shifts"] = len(queue)
    if text and rows and not queue and any(r["tier"] == top and r["status"] not in MET for r in rows):
        out["problems"].append(f"the queue is empty and {top} requirements are still open: plan the next shifts")
    planned = {str(s.get("milestone")) for s in [shift, *queue] if s and s.get("milestone")}
    gating, old = [], []
    for d in state.get("decisions") or []:
        if d.get("status") != "open":
            continue
        nb = str(d.get("needed_before") or "")
        if nb and nb in planned:
            gating.append(f"{d.get('id')}: {d.get('question', '')[:90]} (needed before {nb}, which is queued)")
        try:
            asked = dt.datetime.fromisoformat(str(d.get("asked")))
            if asked.tzinfo is None:
                asked = asked.astimezone()
            if (at - asked).days >= 7:
                old.append(f"{d.get('id')}: open {(at - asked).days} days")
        except ValueError:
            pass
    F["decisions_gating_the_queue"] = gating
    F["decisions_open_a_week"] = old
    F["decisions_open"] = sum(1 for d in state.get("decisions") or [] if d.get("status") == "open")
    noplan = [f.get("id") for f in state.get("failures") or []
              if f.get("status") == "open" or (f.get("status") == "planned" and not (f.get("plan") and f.get("owner")))]
    F["failures_without_a_plan"] = noplan
    # a manager who finds the roadmap wrong writes <handoff>/<date>-proposal-<topic>.md; each is the founder's to answer
    hd = P.path("handoff")
    F["roadmap_proposals"] = sorted(f.name for f in hd.glob("*-proposal-*.md")) if hd.is_dir() else []
    usage = state.get("usage") or {}
    pts = usage.get("points") or []
    if pts:
        last = pts[-1]
        stop = usage.get("stop", P.get("limits.usage_stop"))
        F["usage"] = {"weekly": last.get("weekly"), "stop": stop, "at": last.get("at"), "reset": usage.get("reset")}
        try:
            if float(last.get("weekly")) >= float(stop):
                out["problems"].append(f"usage {last.get('weekly')}% is at or past the stop ({stop}%)")
        except (TypeError, ValueError):
            pass
    for label, key in (("gating decisions", "decisions_gating_the_queue"), (f"{top} requirements with no milestone", "top_tier_no_milestone"),
                       ("duplicate requirement ids", "duplicate_ids"), ("failures without a plan", "failures_without_a_plan")):
        if F.get(key):
            out["problems"].append(f"{len(F[key])} {label}")
    return out


def cmd_audit(argv):
    P = fp.load()
    a = audit(P)
    tools = {}
    for t, args in (("flow.py", ["selftest"]), ("flow.py", ["brief"]), ("board.py", ["brief", "--keys", "warnings"])):
        if (HERE / t).is_file():
            code, so, se = run([sys.executable, str(HERE / t), *args], P.main)
            tools[f"{t} {' '.join(args)}"] = {"exit": code, "out": so.strip(), "err": se.strip()[-400:]}
    if "--json" in argv:
        a["tools"] = tools
        print(json.dumps(a, indent=1, ensure_ascii=False))
        return 1 if a["problems"] else 0
    print(f"Founder's audit of {P.project}, {a['at']}\n")
    F = a["findings"]
    if F.get("distance"):
        print("Distance to the goal: " + "; ".join(f"{t} {v['met']}/{v['total']} met" for t, v in sorted(F["distance"].items())))
    if F.get("usage"):
        u = F["usage"]
        print(f"Usage: {u['weekly']}% of a {u['stop']}% stop (read {u['at']}; reset {u.get('reset') or 'not recorded'})")
    print(f"Queue: {F.get('queued_shifts', 0)} shift(s) behind the current one; open decisions: {F.get('decisions_open', 0)}")
    for title, key in (("Top-tier requirements no milestone names", "top_tier_no_milestone"),
                       ("Requirement ids used twice", "duplicate_ids"),
                       ("The queue's gaps", "queue_gaps"),
                       ("Open decisions that gate something queued", "decisions_gating_the_queue"),
                       ("Decisions open a week or more", "decisions_open_a_week"),
                       ("Failures with no plan or owner", "failures_without_a_plan"),
                       (f"Roadmap proposals from managers, in {P.rel('handoff')} (read each; say in the audit what became of it)",
                        "roadmap_proposals")):
        items = F.get(key) or []
        if items:
            print(f"\n{title} ({len(items)}):")
            for i in items[:40]:
                print(f"  - {i}")
            if len(items) > 40:
                print(f"  ... and {len(items) - 40} more")
    for name, r in tools.items():
        body = r["out"] or r["err"]
        lines = body.splitlines()[-12:]
        try:  # a brief is JSON: print what it found, not its whole body
            doc = json.loads(r["out"])
            if isinstance(doc, dict) and isinstance(doc.get("findings"), list):
                lines = [f"[{f.get('kind', '')}] {f.get('head', '')}: {f.get('text', '')}" for f in doc["findings"]]
            elif isinstance(doc, dict) and isinstance(doc.get("warnings"), list):
                lines = [f"! {w}" for w in doc["warnings"]] or ["no warnings"]
        except ValueError:
            pass
        print(f"\n{name} (exit {r['exit']}):")
        for line in lines:
            print(f"  {line[:300]}")
    for n in a["not_read"]:
        print(f"\nNOT READ  {n}")
    print()
    for p in a["problems"]:
        print(f"PROBLEM   {p}")
    print(f"audit: {len(a['problems'])} problem(s). Findings are not a re-cut: each change is a decision for the user.")
    return 1 if a["problems"] else 0


# ---------------------------------------------------------------------------------------------------------- push

PUSH = """# {title}: draft

Written {at} by {by} on the user's "<the words that asked for this push>".
Nothing here is queued until the user approves it; record the approval below in their own words, with the time.

## Window

- **Start:** <date time>
- **Freeze:** <date time>. A counted sweep of every lane follows.
- **Close:** <date time>{reset}
- **Slots:** <n> ({slots})
- **Usage:** {usage}
- **The shared resource:** {resource}

## Blocks

1. **Q1, <title>** (<slots>). <What it does.>
   - Done when: <a lane's verdict on a counted run / a merged commit with its review / a report on the main branch>.

## Left out, and why

- <milestone>: waits on D<n> / carried / not in this budget.

## The user's calls before the first block

1. Settings: the usage stop ({stop}% now), the headcount ({crew_max} now), heavy work pre-approved or not, the model for each title.
{decisions}

## Carried in

{failures}

## Approval

- <time>: "<the user's own words>"
"""


def cmd_push(argv):
    if len(argv) < 2 or argv[0] != "new":
        print("usage: founder.py push new NAME [--title TEXT] [--by FDR-1]")
        return 2
    P = fp.load()
    name = re.sub(r"[^a-z0-9-]+", "-", argv[1].lower()).strip("-")
    if not name:
        print("refused: the push needs a name (letters, digits, dashes)")
        return 2
    t = now()
    path = P.path("handoff") / f"{t:%Y-%m-%d}-{name}-draft.md"
    if path.exists():
        print(f"refused: {path} exists")
        return 2
    state = read_json(P.path("state")) or {}
    usage = state.get("usage") or {}
    pts = usage.get("points") or []
    stop = usage.get("stop", P.get("limits.usage_stop"))
    if pts:
        u = f"{pts[-1].get('weekly')}% of the week used at {pts[-1].get('at')}; the stop is {stop}%, so the budget is about " \
            f"{max(0, round(float(stop) - float(pts[-1].get('weekly') or 0)))} points. Last push's rate: <points per slot>."
    else:
        u = f"not recorded yet (`board.py usage <percent>`); the stop is {stop}%."
    seats = P.get("resource.seats") or []
    res = (f"{P.get('resource.name')}, {len(seats)} seat(s) ({', '.join(seats)}); at most <n> builders need it at once"
           if P.has_resource() else "none named in the profile: every block is host work")
    opens = [d for d in state.get("decisions") or [] if d.get("status") == "open"]
    dec = "\n".join(f"{i}. {d.get('id')}: {d.get('question', '')}"
                    + (f" (recommended: {d['recommend']})" if d.get("recommend") else "")
                    + (f" Needed before {d['needed_before']}." if d.get("needed_before") else "")
                    for i, d in enumerate(opens, 2)) or "2. (no open decisions in the register)"
    fails = [f for f in state.get("failures") or [] if f.get("status") in ("open", "planned")]
    fl = "\n".join(f"- {f.get('id')} ({f.get('status')}): {str(f.get('what', ''))[:110]}" for f in fails[:30]) \
        or "- (no open failures)"
    if len(fails) > 30:
        fl += f"\n- ... and {len(fails) - 30} more (`board.py brief --keys failures`)"
    text = PUSH.format(title=opt(argv, "--title") or name, at=stamp(t), by=opt(argv, "--by") or "<your badge id>",
                       reset=f", ahead of the usage reset at {usage['reset']}" if usage.get("reset") else "",
                       slots=", ".join(s["id"] for s in P.slots()) or "the rota's slots", usage=u, resource=res,
                       stop=stop, crew_max=(state.get("shift") or {}).get("crew_max", P.get("limits.crew_max")),
                       decisions=dec, failures=fl)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(f"wrote {path}")
    print("Fill in the window and the blocks, bring it to the user, and queue it only on their words.")
    return 0


# ------------------------------------------------------------------------------------------------------ selftest

def opt(argv, name):
    if name in argv:
        i = argv.index(name)
        if i + 1 < len(argv):
            return argv[i + 1]
    for a in argv:
        if a.startswith(name + "="):
            return a.split("=", 1)[1]
    return None


def selftest():
    import contextlib
    import io
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
            root = Path(td) / "proj"
            root.mkdir()
            os.environ.update(FOUNDRY_ROOT=str(root), FOUNDRY_MAIN=str(root), FOUNDRY_HOME=str(Path(td) / "home"),
                              FOUNDRY_NOW="1795000000")
            text, done = set_toml_value('project = "x"   # name\n[resource]\nname = ""  # none\n', "resource", "name", "GPU 0")
            check("set_toml_value in a section keeps the comment", done and 'name = "GPU 0"  # none' in text)
            text, done = set_toml_value(text, None, "project", 'A "B"')
            check("set_toml_value top level, quoted", done and 'project = "A \\"B\\""   # name' in text)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = cmd_init(["--project", "Test Proj", "--resource", "the rig"])
            P = fp.load(root)
            check("init wrote a profile that parses", P.file is not None and not P.problems and P.project == "Test Proj")
            check("init named the resource and the crew", P.get("resource.name") == "the rig" and P.crew == "test-proj")
            check("init wrote rules and a starter roadmap", (root / ".foundry" / "rules.md").is_file()
                  and P.path("roadmap").read_text(encoding="utf-8").startswith("<!-- STARTER"))
            check("init exit follows board.py's presence", rc == (0 if (HERE / "board.py").is_file() else 1))
            before = (root / ".foundry" / "foundry.toml").read_text(encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()) as b2:
                cmd_init(["--project", "Other"])
            check("init never overwrites", (root / ".foundry" / "foundry.toml").read_text(encoding="utf-8") == before
                  and "kept" in b2.getvalue())

            road = ("# R\n\n| ID | Tier | Status | Lane |\n|---|---|---|---|\n"
                    "| APP-01 | P0 | PASS | G1 |\n| APP-02 | P0 | Planned | M2 |\n| APP-03 | P0 | Open | |\n"
                    "| APP-04 | P1 | Open | |\n| APP-05 | P0 | Part | |\n\n### M3\nCloses: APP-05\n")
            P.path("roadmap").write_text(road, encoding="utf-8")
            state = {"shift": {"id": "s1", "milestone": "M2", "crew_max": 3, "blocks": [{"title": "b"}]},
                     "queue": [{"id": "s2", "blocks": []}],
                     "decisions": [{"id": "D1", "status": "open", "question": "ship without it?", "needed_before": "M2",
                                    "asked": "2026-11-01T10:00-06:00"},
                                   {"id": "D2", "status": "answered", "question": "x", "needed_before": "M2"}],
                     "failures": [{"id": "F001", "status": "open"}, {"id": "F002", "status": "planned", "plan": "p", "owner": "o"},
                                  {"id": "F003", "status": "planned", "plan": "p"}],
                     "usage": {"stop": 80, "reset": "2026-11-24T01:00-06:00", "points": [{"at": "t", "weekly": 85}]}}
            P.path("state").parent.mkdir(parents=True, exist_ok=True)
            P.path("state").write_text(json.dumps(state), encoding="utf-8")
            a = audit(P)
            F = a["findings"]
            check("audit distance by tier", F["distance"] == {"P0": {"met": 1, "total": 4}, "P1": {"met": 0, "total": 1}})
            check("audit: a top-tier row with no milestone", F["top_tier_no_milestone"] == ["APP-03"])
            check("audit: the queue's gaps", any("s2: names no milestone" in g for g in F["queue_gaps"])
                  and any("s1: no block carries a checkpoint" in g for g in F["queue_gaps"]))
            check("audit: a decision gating the queue, and its age", len(F["decisions_gating_the_queue"]) == 1
                  and F["decisions_open_a_week"] and F["decisions_open"] == 1)
            check("audit: failures without a plan", F["failures_without_a_plan"] == ["F001", "F003"])
            check("audit: usage past the stop is a problem", any("past the stop" in p for p in a["problems"]))
            P.path("roadmap").unlink()
            check("audit without a roadmap reads on", any("missing" in n for n in audit(P)["not_read"]))

            with contextlib.redirect_stdout(io.StringIO()) as b3:
                rc = cmd_push(["new", "Push One", "--by", "FDR-1"])
            drafts = list(P.path("handoff").glob("*-push-one-draft.md"))
            body = drafts[0].read_text(encoding="utf-8") if drafts else ""
            check("push new writes a draft", rc == 0 and len(drafts) == 1 and "FDR-1" in body)
            check("push draft carries usage, the resource, decisions and failures",
                  "85% of the week" in body and "the rig" in body and "D1: ship without it?" in body and "F001" in body
                  and "D2" not in body)
            with contextlib.redirect_stdout(io.StringIO()):
                check("push new refuses to overwrite", cmd_push(["new", "Push One"]) == 2)

            with contextlib.redirect_stdout(io.StringIO()) as b4:
                rc = cmd_doctor([])
            d = b4.getvalue()
            check("doctor names missing skills as problems", rc == 1 and "skill foundry-manager is not installed" in d)
            check("doctor sees the starter state of things", "roadmap" in d and "shared resource: the rig" in d)
            for level in SKILLS:
                sk = root / ".claude" / "skills" / P.skill(level)
                sk.mkdir(parents=True)
                (sk / "SKILL.md").write_text("x", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()) as b5:
                cmd_doctor([])
            check("doctor finds project skills", "skill foundry-manager (project)" in b5.getvalue())
    finally:
        for k in [k for k in os.environ if k.startswith("FOUNDRY_")]:
            os.environ.pop(k)
        os.environ.update(saved)
    for b in bad:
        print("FAIL", b)
    print(f"founder selftest: {ok} ok, {len(bad)} failed")
    return 1 if bad else 0


def main(argv):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # a console may default to a legacy code page
    cmd = argv[1] if len(argv) > 1 else ""
    rest = argv[2:]
    if cmd in ("", "-h", "--help", "help"):
        print(__doc__)
        return 0 if cmd else 2
    if "-h" in rest or "--help" in rest:
        print(__doc__)
        return 0
    if cmd == "selftest":
        return selftest()
    if cmd == "init":
        return cmd_init(rest)
    if cmd == "doctor":
        return cmd_doctor(rest)
    if cmd == "audit":
        return cmd_audit(rest)
    if cmd == "push":
        return cmd_push(rest)
    print(f"unknown command {cmd!r}\n")
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
