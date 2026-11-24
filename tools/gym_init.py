#!/usr/bin/env python3
"""Start a gym: the smallest one the Foundry's tools can read, for the project's first grader to build on.

    gym_init.py init [--lane G1] [--title "what the lane proves"]
                                    writes the gym folder (paths.gym): run.py, gym_kit.py, lane-inputs.toml, README.md,
                                    one example lane with its prereg template and contract template, and an empty
                                    series file. A file that is already there is kept and named, never overwritten.
    gym_init.py lane add G2 [--title "what the lane proves"]
                                    one more lane in a gym that has a run.py: its lane file, prereg template,
                                    contract template, empty series file, its line in run.py's LANES and its entry
                                    in lane-inputs.toml
    gym_init.py check               reads the gym as the tools will and prints what is wrong; exit 1 on any problem

`init` and `lane add` write tracked files, so in the main checkout they are refused (exit 3, one line naming the
freeze) while the manager's freeze is on or a counted run or sweep holds or waits for the shared resource: a
counted run checks that the tree is clean, and a new file would stop it. `office.py freeze show` shows the freeze.
In a worktree, and in a project with no crew office yet, nothing is frozen. `check` only reads and always runs.

Exit code: 0 done; 1 `check` found a problem, or `lane add` could not finish an edit; 2 a refusal of the request
itself (a lane name the profile does not read, no gym to add to, no templates); 3 refused during a freeze.

What `init` writes runs as it is: `run.py selftest` passes and `run.py dev <lane>` grades the example lane's own
stand-in. It is a start, not a gym that decides anything: the prereg is a template (run.py refuses a counted run
on it), the contract is a draft, and the example lane grades a toy task. The builder writes the contract; an
independent grader then writes the prereg and the lane from it, before any counted data. The gym skill has the
method, and the gym's README the order of work.

`check` looks at: the lane names in run.py (read as text, as lanes_for.py reads them) against measure.lane_pattern;
each lane's file (with a selftest block), prereg and contract; a prereg that pins a contract against the sha256
of that file as it is in this checkout; lane-inputs.toml against run.py, both ways; what `run.py list` prints;
and each series file's shape. A prereg that is still a template is a note, not a problem.

It works on the checkout this script lies in (FOUNDRY_ROOT names another) and writes only under that checkout's
gym folder. The templates are the files under templates/gym beside this script (profile/gym in the Foundry's own
repository). It commits nothing. Standard library only.
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import foundry_profile as fp  # noqa: E402

P = fp.load(__file__)
HERE = Path(__file__).resolve().parent
GYM = P.local("gym")
GYM_REL = P.rel("gym").strip("/")
LANE_PATTERN = P.get("measure.lane_pattern") or r"\bG\d+\b"
T_LANE, T_MODULE, T_GRADER = "G1", "g1_example", "g1-v1"   # how the templates spell their one lane
T_TITLE = "Example: the answers are the medians, and beat the mean"
RUN_ID = re.compile(r"20\d{6}-\d{6}(?:-[0-9a-f]{4})?")     # a run id as the board reads it
WORDS = ("PASS", "MARGINAL", "FAIL", "MEASURING", "STARVED", "VOID", "SATURATED")
LANES_BLOCK = re.compile(r"^LANES\s*=\s*\{(.*?)\}", re.S | re.M)  # run.py's table, as lanes_for.py finds it


class Refused(Exception):
    pass


class Frozen(Refused):
    """The main checkout is frozen: nothing tracked is written (exit 3)."""


def hold_for_freeze(what):
    """Raise Frozen when `what` may not write tracked files into this checkout now: flow_graph.freeze_refusal, the
    one reader of the freeze that plan_flow.py and the graph's edits go by."""
    try:
        import flow_graph
    except Exception as e:  # noqa: BLE001 - the tools are installed together; without it nothing can be ruled out
        raise Frozen(f"{what}: flow_graph.py beside this tool could not be loaded ({type(e).__name__}: {e}), so a "
                     "freeze of the main checkout cannot be ruled out; nothing written")
    why = flow_graph.freeze_refusal(what, P.root)
    if why:
        raise Frozen(why)


def templates():
    for d in (HERE / "templates" / "gym", HERE.parent / "profile" / "gym"):
        if (d / "run.py").is_file():
            return d
    raise Refused(f"the gym templates are missing: neither {HERE / 'templates' / 'gym'} nor "
                  f"{HERE.parent / 'profile' / 'gym'} holds a run.py (install the Foundry again)")


def valid_lane(lane):
    if not re.fullmatch(r"[A-Za-z0-9]+", lane or ""):
        return f"a lane's name is letters and digits only; got '{lane}'"
    try:
        if not re.fullmatch(LANE_PATTERN, lane):
            return (f"'{lane}' does not match the profile's measure.lane_pattern ({LANE_PATTERN}): the board would "
                    "not read it as a lane. Pick a name that matches, or change the pattern first")
    except re.error as e:
        return f"the profile's measure.lane_pattern is not a regular expression ({e})"
    return None


def slug(title):
    s = re.sub(r"[^a-z0-9]+", "_", (title or "").lower()).strip("_")[:24].strip("_")
    return s or "lane"


def fill(text, lane, module, title, kind):
    """A template's text for one lane: the lane's name, its file's name, its title and the gym folder's path."""
    text = text.replace(T_MODULE, module).replace(T_GRADER, lane.lower() + "-v1")
    text = re.sub(rf"\b{T_LANE}\b", lane, text)
    if title:
        quoted = json.dumps(title, ensure_ascii=False)[1:-1] if kind in ("py", "json") else title
        text = text.replace(T_TITLE, quoted)
    if GYM_REL != "gym":
        text = re.sub(r"(?<![\w/.-])gym/", GYM_REL + "/", text)
    return text


def kit_text(src):
    """gym_kit.py as the gym gets it: the skill's file, under a header that says where it came from."""
    body = src.read_text(encoding="utf-8")
    sha = hashlib.sha256(body.replace("\r\n", "\n").encode("utf-8")).hexdigest()
    head = ("# Copied by the Foundry's gym_init.py from the gym skill's scripts/gym_kit.py\n"
            f"# (sha256 {sha} before this header). It is the gym's own copy from here on: a grader may change it,\n"
            "# and a change is a change to every lane (lane-inputs.toml lists it under [always]).\n")
    return head + body


def empty_series(lane):
    return json.dumps({"meta": {"lane": lane}, "points": []}, indent=1) + "\n"


def put(path, text, done):
    """Write a new file; one that is already there is kept. `done` collects ("wrote" | "kept", path)."""
    if path.exists():
        done.append(("kept", path))
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    done.append(("wrote", path))
    return True


def shown(path):
    try:
        return path.resolve().relative_to(P.root.resolve()).as_posix()
    except ValueError:
        return str(path)


def lane_parts(src, lane, module, title):
    """(path under the gym, text) for the three files one lane adds, and its empty series file."""
    read = lambda rel: (src / rel).read_text(encoding="utf-8")  # noqa: E731
    return [
        (f"lanes/{module}.py", fill(read(f"lanes/{T_MODULE}.py"), lane, module, title, "py")),
        (f"prereg/{lane}.json", fill(read(f"prereg/{T_LANE}.json"), lane, module, title, "json")),
        (f"contracts/{lane}-artifacts.md", fill(read(f"contracts/{T_LANE}-artifacts.md"), lane, module, title, "md")),
        (f"series/{lane}.json", empty_series(lane)),
    ]


def report(done):
    for what, path in done:
        print(f"{what:<6}{shown(path)}" + (" (already there; not changed)" if what == "kept" else ""))


def run_line(rest):
    return f"{P.py} {GYM_REL}/run.py {rest}"


def profile_line(rest):
    """A command line for the profile's [measure] table, which is committed: the profile's own commands.python
    when it names one, else plain `python`, never this host's interpreter path."""
    py = str(P.get("commands.python") or "").strip() or "python"  # the profile's value as it is written there
    return f"{py} {GYM_REL}/run.py {rest}"


def ignored_note():
    """One line when the run folders would not be git-ignored (a counted run needs a clean tree)."""
    try:
        r = subprocess.run(["git", "-C", str(P.root), "check-ignore", "-q", "out/gym/x"], capture_output=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode == 1:
        return ("note: out/ is not git-ignored here. A run's folder is out/gym/<lane>/<run id>/, and a counted run "
                "needs a clean tree: add `out/` to .gitignore.")
    return None


def init(lane, title):
    why = valid_lane(lane)
    if why:
        raise Refused(why)
    src = templates()
    hold_for_freeze("gym_init init")
    module = f"{lane.lower()}_example"
    done = []
    for rel in ("run.py", "lane-inputs.toml", "README.md"):
        put(GYM / rel, fill((src / rel).read_text(encoding="utf-8"), lane, module, "", rel.rsplit(".", 1)[-1]), done)
    put(GYM / "gym_kit.py", kit_text(src / "gym_kit.py"), done)
    for rel, text in lane_parts(src, lane, module, title):
        put(GYM / rel, text, done)
    report(done)
    kept = [p for w, p in done if w == "kept"]
    if len(kept) == len(done):
        print(f"nothing written: every file is already there. `{P.tool('gym_init.py')} check` reads the gym.")
        return 0
    if kept:
        print(f"{len(kept)} file(s) were already there and were kept: run `{P.tool('gym_init.py')} check` to see "
              "whether the gym still agrees with itself.")
    print("\nNext:")
    print(f"  {run_line('selftest')}")
    print(f"  {run_line('dev ' + lane)}")
    print(f"  {P.tool('gym_init.py')} check")
    print("Then the builder writes the contract, and an independent grader the prereg and the lane "
          f"({GYM_REL}/README.md has the order of work).")
    print("\nProfile lines to set under [measure] in .foundry/foundry.toml:")
    print(f"  counted = '{profile_line('counted <lane>')}'")
    print(f"  dev = '{profile_line('dev <lane>')}'")
    print(f"  selftest = '{profile_line('selftest')}'")
    note = ignored_note()
    if note:
        print("\n" + note)
    return 0


def lane_names(text):
    """The lane names in run.py's LANES, read as text (lanes_for.py's rule), or None when there is no LANES."""
    m = LANES_BLOCK.search(text)
    return None if not m else re.findall(r'"([A-Za-z0-9]+)"\s*:', m.group(1))


def lane_files(lane):
    """The lane's files as office.py finds them: lanes/<lane>_*.py or lanes/<lane>.py, lower case."""
    d = GYM / "lanes"
    return sorted(list(d.glob(f"{lane.lower()}_*.py")) + list(d.glob(f"{lane.lower()}.py"))) if d.is_dir() else []


def code_end(line):
    """Where the code of one line ends: the index of its comment's `#` (one outside every quoted string), else the
    line's length."""
    quote, i = "", 0
    while i < len(line):
        ch = line[i]
        if quote:
            if ch == "\\":
                i += 1
            elif ch == quote:
                quote = ""
        elif ch in "\"'":
            quote = ch
        elif ch == "#":
            return i
        i += 1
    return len(line)


def with_comma(body):
    """The body of LANES with a comma after its last entry when that has none. The comma goes right after the
    entry's code: before a comment that follows it on its line, never inside the comment."""
    lines = body.split("\n")
    for i in range(len(lines) - 1, -1, -1):
        code = lines[i][:code_end(lines[i])].rstrip()
        if code:
            if not code.endswith(","):
                lines[i] = code + "," + lines[i][len(code):]
            break
    return "\n".join(lines)


def add_to_run_py(lane, module):
    """Add the lane's line to run.py's LANES. Returns a problem text, or None."""
    path = GYM / "run.py"
    with open(path, encoding="utf-8", newline="") as fh:
        text = fh.read()
    m = LANES_BLOCK.search(text)
    line = f'"{lane}": "{module}",'
    if not m:
        return f"{shown(path)} has no LANES table this tool can read: add the lane there by hand ({line})"
    body = m.group(1)
    code = "\n".join(ln[:code_end(ln)] for ln in body.split("\n"))  # a comment's own colons and quotes are not read
    if re.search(r":\s*[^\s\"',#]", code):  # a value that is not a quoted file name: a runner with its own shape
        return (f"{shown(path)}'s LANES does not map names to file names, so this tool leaves it alone: add "
                f"{lane} there by hand")
    eol = "\r\n" if "\r\n" in text else "\n"
    new_body = with_comma(body.rstrip()) + f"{eol}    {line}{eol}"
    text = text[:m.start(1)] + new_body + text[m.end(1):]
    try:  # never leave a run.py that does not compile: every tool that reads the gym would stop on it
        compile(text, str(path), "exec", dont_inherit=True)
    except (SyntaxError, ValueError) as e:
        return (f"{shown(path)} would not compile with {lane}'s line added to LANES ({type(e).__name__}: {e}); it was "
                f"left as it is: add the lane there by hand ({line})")
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    tmp.replace(path)
    return None


def add_to_table(lane, module):
    """Append the lane's entry to lane-inputs.toml. Returns a problem text, or None."""
    path = GYM / "lane-inputs.toml"
    entry = (f"\n[lanes.{lane}]\npaths = [\"{GYM_REL}/lanes/{module}.py\", \"{GYM_REL}/prereg/{lane}.json\", "
             f"\"{GYM_REL}/contracts/{lane}-artifacts.md\"]\n")
    if not path.is_file():
        return f"{shown(path)} is missing: `init` writes one; then add{entry}"
    with open(path, encoding="utf-8", newline="") as fh:
        text = fh.read()
    try:
        tomllib.loads(text + entry)
    except tomllib.TOMLDecodeError as e:
        return f"{shown(path)} would not be TOML with the lane's entry added ({e}): add it by hand:{entry}"
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text + ("" if text.endswith("\n") else "\n") + (entry.replace("\n", "\r\n") if "\r\n" in text else entry))
    return None


def lane_add(lane, title):
    why = valid_lane(lane)
    if why:
        raise Refused(why)
    run_py = GYM / "run.py"
    if not run_py.is_file():
        raise Refused(f"there is no {shown(run_py)} yet: start the gym with `{P.tool('gym_init.py')} init --lane {lane}`")
    src = templates()
    hold_for_freeze("gym_init lane add")
    names = lane_names(run_py.read_text(encoding="utf-8")) or []
    have = lane_files(lane)
    module = have[0].stem if have else f"{lane.lower()}_{slug(title)}"
    done, problems, changed = [], [], []
    for rel, text in lane_parts(src, lane, module, title):
        if rel.startswith("lanes/") and have:
            done.append(("kept", have[0]))
            continue
        put(GYM / rel, text, done)
    report(done)
    if lane in names:
        print(f"kept  {shown(run_py)}: LANES already names {lane}")
    else:
        why = add_to_run_py(lane, module)
        problems += [why] if why else []
        changed += [] if why else [f"{shown(run_py)}: LANES now names {lane}"]
    table = GYM / "lane-inputs.toml"
    try:
        in_table = lane in (tomllib.loads(table.read_text(encoding="utf-8")).get("lanes") or {})
    except (OSError, tomllib.TOMLDecodeError):
        in_table = False
    if in_table:
        print(f"kept  {shown(table)}: it already has [lanes.{lane}]")
    else:
        why = add_to_table(lane, module)
        problems += [why] if why else []
        changed += [] if why else [f"{shown(table)}: [lanes.{lane}] added (list there every path the lane's result depends on)"]
    for line in changed:
        print("edited " + line)
    for line in problems:
        print("PROBLEM " + line)
    if not problems:
        print(f"\nNext: {run_line('selftest')}, then {P.tool('gym_init.py')} check")
    return 1 if problems else 0


def pin_problem(lane, prereg_path, doc, text):
    """What is wrong with the prereg's contract pin, as (problems, notes)."""
    c = doc.get("contract") if isinstance(doc.get("contract"), dict) else None
    path = str(c.get("path") or "").strip() if c else ""
    if not path:
        return [], [f"{lane}: its prereg pins no contract yet (contract.path is empty)"]
    f = P.root / path
    if not f.is_file():
        return [f"{lane}: its prereg pins {path}, which is not in this checkout"], []
    body = f.read_bytes()
    sha = hashlib.sha256(body).hexdigest()
    blob = hashlib.sha1(b"blob %d\0" % len(body) + body).hexdigest()
    lf = hashlib.sha256(body.replace(b"\r\n", b"\n")).hexdigest()
    if sha in text or blob in text:
        return [], []
    if lf in text:
        return [], [f"{lane}: its prereg pins {path} by the sha256 of its text with LF line ends; the file here has "
                    "CRLF, and the board compares the bytes as they are"]
    return [f"{lane}: its prereg pins no version of {path} as it is in this checkout (sha256 {sha[:12]}): the "
            "grader reads the change and pins it again, by a dated amendment; no counted run until then"], []


def check():
    """The gym as the tools read it. Prints PROBLEM and note lines; returns the exit code."""
    problems, notes = [], []
    run_py = GYM / "run.py"
    if not GYM.is_dir():
        print(f"gym_init check: there is no gym yet ({shown(GYM)}/): `{P.tool('gym_init.py')} init` starts one")
        return 1
    names = None
    if not run_py.is_file():
        problems.append(f"{shown(run_py)} is missing: nothing can run a lane")
    else:
        names = lane_names(run_py.read_text(encoding="utf-8"))
        if names is None:
            problems.append(f"{shown(run_py)} has no `LANES = {{...}}` table: lanes_for.py reads the lane names there as text")
    names = names or []
    if run_py.is_file() and not names:
        problems.append(f"{shown(run_py)}'s LANES names no lane")
    for lane in names:
        why = valid_lane(lane)
        if why:
            problems.append(f"{lane}: {why}")
        files = lane_files(lane)
        if not files:
            problems.append(f"{lane}: no lane file ({GYM_REL}/lanes/{lane.lower()}_*.py or {lane.lower()}.py)")
        for f in files:
            if not re.search(r"^if __name__ == [\"']__main__[\"']\s*:", f.read_text(encoding="utf-8", errors="replace"), re.M):
                problems.append(f"{lane}: {shown(f)} has no `if __name__ == \"__main__\":` block, so running it alone "
                                "runs no selftest and still exits 0")
        base = re.sub(r"[a-z]+$", "", lane)
        prereg = next((p for p in (GYM / "prereg" / f"{lane}.json", GYM / "prereg" / f"{base}.json") if p.is_file()), None)
        if prereg is None:
            problems.append(f"{lane}: no prereg ({GYM_REL}/prereg/{lane}.json)")
        else:
            text = prereg.read_text(encoding="utf-8", errors="replace")
            try:
                doc = json.loads(text)
            except ValueError as e:
                doc = None
                problems.append(f"{lane}: {shown(prereg)} is not JSON ({e})")
            if doc is not None and not isinstance(doc, dict):
                problems.append(f"{lane}: {shown(prereg)} is not a JSON object")
            elif doc is not None:
                if str(doc.get("status") or "").strip().upper().startswith("TEMPLATE"):
                    notes.append(f"{lane}: its prereg is still a template (not registered): no counted run until the grader fills it")
                else:
                    for key in ("prereg_id", "written_at", "written_before"):
                        if not doc.get(key) or "<" in str(doc.get(key)):
                            problems.append(f"{lane}: its prereg is not a template any more and has no {key}")
                p2, n2 = pin_problem(lane, prereg, doc, text)
                problems += p2
                notes += n2
        contract = GYM / "contracts" / f"{lane}-artifacts.md"
        if not contract.is_file():
            problems.append(f"{lane}: no contract ({GYM_REL}/contracts/{lane}-artifacts.md)")
        elif "DRAFT" in (contract.read_text(encoding="utf-8", errors="replace").splitlines() or [""])[0]:
            notes.append(f"{lane}: its contract is still a draft")

    table = GYM / "lane-inputs.toml"
    if not table.is_file():
        problems.append(f"{shown(table)} is missing: lanes_for.py selects no lane without it")
    else:
        try:
            doc = tomllib.loads(table.read_text(encoding="utf-8"))
            rules = doc.get("lanes") or {}
            for lane in names:
                if lane not in rules:
                    problems.append(f"{shown(table)} has no [lanes.{lane}], a lane in run.py")
            for lane in rules:
                if lane not in names and run_py.is_file():
                    problems.append(f"{shown(table)} has [lanes.{lane}], which is not in run.py's LANES")
            for lane, spec in rules.items():
                for p in spec.get("paths", []) if isinstance(spec, dict) else []:
                    if not any(c in p for c in "*?[") and not (P.root / p).exists():
                        notes.append(f"{shown(table)}: {lane} lists {p}, which is not there")
        except tomllib.TOMLDecodeError as e:
            problems.append(f"{shown(table)} is not TOML ({e})")

    if run_py.is_file() and names:
        try:
            r = subprocess.run([sys.executable, str(run_py), "list"], capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=120, cwd=str(P.root))
            listed = [line.split()[0] for line in r.stdout.splitlines() if line.strip()]
            if r.returncode != 0:
                last = ((r.stderr or r.stdout).strip().splitlines() or ["no output"])[-1]
                problems.append(f"`run.py list` exited {r.returncode}: {last}")
            elif listed != names:
                problems.append(f"`run.py list` prints {', '.join(listed) or 'no lane'}; LANES read as text names {', '.join(names)}")
        except (OSError, subprocess.SubprocessError) as e:
            problems.append(f"`run.py list` could not be run ({type(e).__name__}: {e})")

    series = GYM / "series"
    for f in sorted(series.glob("*.json")) if series.is_dir() else []:
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
            pts = doc.get("points")
            if not isinstance(pts, list):
                raise ValueError("no points list")
        except (OSError, ValueError, AttributeError) as e:
            problems.append(f"{shown(f)} is not a series the board can read ({e})")
            continue
        if names and f.stem not in names:
            notes.append(f"{shown(f)} is the series of {f.stem}, which is not in run.py's LANES")
        for i, p in enumerate(pts):
            if not isinstance(p, dict) or not RUN_ID.fullmatch(str(p.get("run_id") or "")):
                problems.append(f"{shown(f)}: point {i + 1} has no run id the board reads (YYYYMMDD-HHMMSS-xxxx)")
            elif p.get("verdict") not in WORDS:
                problems.append(f"{shown(f)}: point {i + 1} ({p['run_id']}) has no verdict word")
            elif not isinstance(p.get("ts"), (int, float)):
                problems.append(f"{shown(f)}: point {i + 1} ({p['run_id']}) has no epoch ts, so the chart pages skip it")

    for line in problems:
        print("PROBLEM " + line)
    for line in notes:
        print("note    " + line)
    print(f"gym_init check: {len(names)} lane(s) ({', '.join(names) or 'none'}), {len(problems)} problem(s), {len(notes)} note(s)")
    return 1 if problems else 0


def main(argv):
    ap = argparse.ArgumentParser(prog="gym_init.py", description="Start a gym the Foundry's tools can read, add a lane to it, or check it.")
    sub = ap.add_subparsers(dest="cmd")
    a = sub.add_parser("init", help="write the smallest gym; a file that exists is kept")
    a.add_argument("--lane", default=T_LANE, help="the first lane's name (default G1)")
    a.add_argument("--title", default="", help="one line on what the lane proves")
    b = sub.add_parser("lane", help="lane add NAME: one more lane")
    b.add_argument("verb", choices=("add",))
    b.add_argument("name")
    b.add_argument("--title", default="", help="one line on what the lane proves")
    sub.add_parser("check", help="read the gym as the tools will; exit 1 on a problem")
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return 0 if argv else 2
    args = ap.parse_args(argv)
    title = " ".join(str(getattr(args, "title", "") or "").split())
    try:
        if args.cmd == "init":
            return init(args.lane, title)
        if args.cmd == "lane":
            return lane_add(args.name, title)
        if args.cmd == "check":
            return check()
    except Frozen as e:
        print(f"refused: {e}", file=sys.stderr)
        return 3
    except Refused as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    print(__doc__)
    return 2


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main(sys.argv[1:]))
