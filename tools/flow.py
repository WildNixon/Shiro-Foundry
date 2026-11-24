#!/usr/bin/env python3
"""Workflow graphs: the road to the project's goal as a dependency graph, the pipeline every milestone moves
through, and the flow numbers a manager needs to see where work waits.

Nothing here is typed by hand. Every figure is read from what the crew already keeps up to date; each place is the
profile's (.foundry/foundry.toml, the [paths] table), named here by its default:

  docs/ROADMAP.md           stages, milestones (Closes / Why here), requirement rows, decisions (Needed before);
                            the shapes are in the foundry-founder skill (references/roadmap-format.md)
  docs/progress/state.json  milestone statuses, lanes, the shift's blocks, failures, reviews, usage
  gym/series/*.json*        counted runs and verdicts (archived series included)
  git                       when each lane's contract and prereg first appeared (any branch)
  out/foundry/              the crew office: roster, timeclock and the resource queue

  flow.py build      write workflow.html, brief.json and graph.json under paths.flow_out, print the findings
                     (the default)
  flow.py brief      print the findings as JSON (for the manager's turn)
  flow.py edges      print the graph as parsed from the roadmap, to check an edit kept its shape
  flow.py selftest   exit 1 when the roadmap no longer parses into a sound graph, or the road graph asset was
                     changed by hand or no longer names the roadmap's milestones, decisions and stages; inputs a new
                     project does not have yet (no state, office, gym series or seeded graph) are NOTE lines only.
                     selftest --logic runs just the tool's own checks, with no project read
  flow.py graph ...  the road graph asset (road.graph.json under paths.flow): show, trace and verify for anyone;
                     seed, link, unlink, confirm, node and undo for the manager's badge or the founder's
                     (flow_graph.py; graph -h)

Which milestone must come first and which decision gates what is read from the road graph asset once the manager
has seeded it; until then it is guessed from the roadmap's prose, and the page says so. The page draws it as a
canvas of typed nodes with pins (flow_page.py) and only shows: nothing on the page edits.

A project that has no roadmap yet, no road graph, no gym series or an empty office still gets a page and a brief:
each input that is missing is a "not read" line on the page and in the findings.

Plan charts share the canvas and have their own tool: plan_flow.py (a plan to judge, drawn from NAME.plan.toml
under paths.flow). A project may add its own reader that draws a "system graph" from its code onto the same
canvas (flow_page.py). The flow skill (the profile's skills.flow) says who makes, edits and reads each.

build, brief, edges and selftest only read the checkout. The outputs (workflow.html, brief.json, graph.json) live
under paths.flow_out (ignored by git), so a build never dirties the tree; --out=DIR puts them elsewhere (a
branch's build). Run it from any worktree: it reads the main checkout's live files unless --root says otherwise.
"""
import collections
import datetime as dt
import html
import json
import re
import statistics
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import foundry_profile as fp  # noqa: E402
import flow_graph  # noqa: E402  (the road graph asset and its manager-only edits)
import flow_page  # noqa: E402  (the canvas that draws it)

P = fp.load(__file__)
at = flow_graph.at  # paths.<name> under a root
ROADMAP = flow_graph.ROADMAP  # the roadmap's file name, as messages say it
GOAL, LATE = flow_graph.GOAL, flow_graph.LATE
DAY = 86400.0
WINDOW = 28  # days on the daily charts


def git(root, *args, timeout=120):
    try:
        return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def main_root():
    """The main checkout: the live roadmap, state and office are read from it."""
    return P.main


def rel(name, *more):
    """paths.<name> as the profile writes it, with forward slashes, for git and for messages."""
    return "/".join([P.rel(name).rstrip("/"), *more])


NOT_READ = []  # inputs that could not be read, or records skipped for their shape: shown on the page, never silent
ABSENT = []    # the NOT_READ lines that only say "not there yet" (a new project): the selftest notes them, no more
SKIPPED = collections.Counter()
READ_AS = collections.Counter()  # fields that were not text and were read as a default: (what, read as) -> count


def shape_notes():
    """One line per kind of record skipped, or field read as a default, for its shape."""
    return ([f"{n} {what} skipped for their shape" for what, n in sorted(SKIPPED.items())]
            + [f"{n} {what} not text, read as {as_}" for (what, as_), n in sorted(READ_AS.items())])


def load_json(path, default, optional=False):
    """The file's JSON when it has the default's type; else the default, with a line in NOT_READ."""
    path = Path(path)
    try:
        v = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        if not optional:
            absent(f"{path.name} is missing")
        return default
    except (OSError, ValueError) as e:
        NOT_READ.append(f"{path.name} could not be read ({type(e).__name__})")
        return default
    if not isinstance(v, type(default)):
        NOT_READ.append(f"{path.name} is a {type(v).__name__}, not a {type(default).__name__}")
        return default
    return v


def absent(line):
    """A not-read line for an input that is not there yet."""
    NOT_READ.append(line)
    ABSENT.append(line)


def dicts(v, what, need=()):
    """The dict entries of a list that carry the string keys in `need`; the rest are counted as skipped."""
    out = []
    for x in v if isinstance(v, list) else []:
        if isinstance(x, dict) and all(isinstance(x.get(k), str) and x.get(k) for k in need):
            out.append(x)
        else:
            SKIPPED[what] += 1
    if v is not None and not isinstance(v, list):
        SKIPPED[what + " (not a list)"] += 1
    return out


def num(v, default=None):
    # below 4.1e9: a time stamp past the year 2099 is a typo, and fromtimestamp refuses far ones on some hosts
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and 0 <= v < 4.1e9 else default


def clean_state(state):
    """state.json with every part this script reads brought to the shape it expects. A part that is absent or
    null in a file that did load is reported, so its zero on the page is never silent."""
    s = dict(state)
    if not any("state.json" in x for x in NOT_READ):
        # absent or of the wrong type; a part that is present and empty is a true zero
        for key, kind in (("milestones", list), ("failures", list), ("shift", dict), ("usage", dict)):
            if not isinstance(state.get(key), kind):
                NOT_READ.append(f"state.json holds no {key}")
    s["milestones"] = dicts(state.get("milestones"), "milestones", ("id",))
    s["phases"] = dicts(state.get("phases"), "phases", ("id",))
    for m in s["milestones"] + s["phases"]:
        if not isinstance(m.get("lane"), str):
            m["lane"] = None
        if not isinstance(m.get("title"), str):
            m["title"] = ""
        if not isinstance(m.get("status"), str):
            m["status"] = "planned"
            READ_AS[("milestone statuses", "planned")] += 1
    shift = state.get("shift") if isinstance(state.get("shift"), dict) else {}
    s["shift"] = {"blocks": [dict(b, title=str(b.get("title") or "")) for b in dicts(shift.get("blocks"), "shift blocks")]}
    s["failures"] = dicts(state.get("failures"), "failures")
    for f in s["failures"]:
        if not isinstance(f.get("status"), str):
            f["status"] = "open"
            READ_AS[("failure statuses", "open")] += 1
    s["research_review"] = [dict(r, topic=str(r.get("topic") or "")) for r in dicts(state.get("research_review"), "reviews")]
    s["usage"] = state.get("usage") if isinstance(state.get("usage"), dict) else {}
    return s


def clean_roster(roster):
    out = {}
    badges = roster.get("badges")
    for k, b in badges.items() if isinstance(badges, dict) else []:
        if isinstance(b, dict) and isinstance(b.get("id"), str):
            out[b["id"]] = dict(b, issued=num(b.get("issued"), 0.0), eta_s=num(b.get("eta_s")), job=str(b.get("job") or ""),
                                role=b.get("role") if isinstance(b.get("role"), str) else "", lane=b.get("lane") if isinstance(b.get("lane"), str) else "")
        else:
            SKIPPED["roster badges"] += 1
    if not isinstance(badges, dict) and not any("roster.json" in x for x in NOT_READ):
        NOT_READ.append("roster.json holds no badges")
    return out


def esc(s):
    return html.escape(str(s), quote=True)


def cut(s, n):
    s = " ".join(str(s).split())
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def plain(s):
    return re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", str(s)).replace("**", "").replace("`", "").strip()


def mnum(mid):
    m = re.match(r"([A-Z]+)(\d+)(.*)", mid)
    return (m[1], int(m[2]), m[3]) if m else (mid, 0, "")


# ---------------------------------------------------------------- the roadmap

# The shapes come from the profile's [roadmap] table (the foundry-founder skill's references/roadmap-format.md shows each with an example).
RID = flow_graph.rx("roadmap.requirement_id", r"[A-Z0-9]+-\d+")
TIERS = [str(t) for t in (P.get("roadmap.tiers") or ["P0", "P1", "P2"])]
TOP = TIERS[0]  # the tier the goal waits on: "left", "unmet" and the bars count this tier only
TIER = "(?:" + "|".join(re.escape(t) for t in TIERS) + ")"
MS, DEC, STAGE, LANE = flow_graph.MS, flow_graph.DEC, flow_graph.STAGE, flow_graph.LANE
STATUSES = ("PASS", "Part", "Planned", "Decided", "Open")
REQ_ROW = re.compile(r"^\| (?P<id>" + RID + r") \| (?P<p>" + TIER + r")(?:→(?P<to>" + TIER + r")\*)? \| (?P<status>"
                     + "|".join(STATUSES) + r") \| (?P<where>[^|]*) \|", re.M)
NAMED_ROW = re.compile(r"^\| \*\*(?P<name>[^*|]+)\*\* \| (?P<theme>[^|]*) \| (?P<exit>[^|]*) \|", re.M)
# one cell of a milestone or decision row: up to the next pipe that no backslash escapes (a cell may hold `\|`)
CELL = r"(?:\\.|[^|\\\n])*"
MS_ROW = re.compile(r"^\| (?P<id>" + MS + r") \| (?P<theme>" + CELL + r") \| (?P<closes>" + CELL + r") \| (?P<why>" + CELL + r") \|", re.M)
MS_BULLET = re.compile(r"^- \*\*(?P<head>" + MS + r"\b[^*]*)\*\*(?P<tail>.*)$", re.M)
DEC_ROW = re.compile(r"^\| (?P<id>" + DEC + r") \| (?P<what>" + CELL + r") \| (?P<stands>" + CELL + r") \| (?P<owner>" + CELL
                     + r") \| (?P<need>" + CELL + r") \|", re.M)
COUNT_ROW = re.compile(r"^\| \*\*(?P<p>" + TIER + r")\*\* \| " + r" \| ".join([r"(\d+)"] * 6) + r" \|", re.M)
MS_ID = re.compile(r"(?<![\w-])" + MS + r"(?!\w)")
DEC_ID = re.compile(r"(?<![\w-])" + DEC + r"(?!\w)")
LANE_OF = re.compile(r"\(lane (?P<lane>" + LANE + r")\)")
LANES_LINE = re.compile(r"^\*\*Lanes\b[^*\n]*\*\*[^\n]*", re.M)
LANE_PAIR = re.compile(r"(?<![\w-])(?P<ms>" + MS + r") (?P<lane>" + LANE + r")")
# one ID, or a run of them: 'SET-01–03'
ID_RUN = re.compile(r"(?<![\w-])(?P<id>" + RID + r")(?:[–-](?P<to>\d+))?(?!\w)")
MET = ("PASS", "Decided")


def cell(m, name):
    """One cell of a parsed row as its text: an escaped pipe is a pipe."""
    return m[name].replace("\\|", "|")


def found(rx, text):
    """Every whole match of a pattern, in order (a profile's pattern may hold groups of its own)."""
    return [m.group(0) for m in rx.finditer(text)]


def is_stage(sid):
    return sid in LATE or bool(re.fullmatch(STAGE, sid))


def stage_order(stages):
    """The stages in the order the road runs: the numbered ones, then the named late ones, the goal last."""
    return sorted([s for s in stages if s not in LATE], key=mnum) + [s for s in LATE if s in stages]


def split_id(rid):
    """('SHELL', '01') of 'SHELL-01': an ID's prefix and its number as written, or None when it does not end in
    -digits or holds no letter (a date such as 2026-01 is not an ID)."""
    m = re.fullmatch(r"(.*[A-Za-z].*)-(\d+)", rid)
    return (m[1], m[2]) if m else None


def run_of(prefix, a, b=None):
    """The IDs prefix-a to prefix-b, numbered as wide as `a` is written."""
    return [f"{prefix}-{n:0{len(a)}d}" for n in range(int(a), int(b or a) + 1)]


def ids_in(text, parens=False):
    """Requirement IDs in a cell: 'SHELL-01, 03, 04; GFX-05', 'SET-01–03', 'FILE-01 (rest)'. What stands in
    parentheses is a remark and is left out, unless parens is set."""
    out, prefix = [], None
    for tok in re.split(r"[,;]", text if parens else re.sub(r"\([^)]*\)", "", text)):
        tok = tok.strip()
        full = [(split_id(m["id"]), m["id"], m["to"]) for m in ID_RUN.finditer(tok)]
        full = [x for x in full if x[0] or (re.search(r"[A-Za-z]", x[1]) and not x[2])]
        if full:
            for parts, rid, to in full:
                if parts:
                    prefix = parts[0]
                    out += run_of(parts[0], parts[1], to)
                else:  # an ID shape of the project's own that does not end in -digits: taken as written
                    out.append(rid)
        elif prefix:
            m = re.fullmatch(r"(\d+)(?:[–-](\d+))?", tok)
            if m:
                out += run_of(prefix, m[1], m[2])
    return list(dict.fromkeys(out))


def parse_reqs(text):
    return {m["id"]: {"p": m["to"] or m["p"], "status": m["status"], "where": found(MS_ID, m["where"])}
            for m in REQ_ROW.finditer(text)}


def exit_ids(cell, reqs):
    """A stage's exit IDs. With P0 as the first tier: 'All P0 except REL-04's sign-off; PERF-01 in place' is every
    P0 but REL-04, and PERF-01; 'REL-01–05; every P0 PASS' is every P0."""
    out, drop = [], set()
    for clause in cell.split(";"):
        if re.search(r"\b(all|every) " + re.escape(TOP) + r"(?!\w)", clause, re.I):
            out += [i for i, q in reqs.items() if q["p"] == TOP]
            if "except" in clause:
                drop |= set(ids_in(clause.split("except", 1)[1]))
        else:
            out += ids_in(clause)
    return [i for i in dict.fromkeys(out) if i in reqs and i not in drop]


def shape_warnings(text, reqs):
    """Rows of the roadmap that look like table rows this script reads but did not parse, and the roadmap's own
    Count table against the rows that did."""
    w = []
    seen, got = len(list(re.finditer(r"^\| " + RID + r" \|", text, re.M))), len(list(REQ_ROW.finditer(text)))
    if seen != got:
        w.append(f"{seen - got} requirement row(s) in {ROADMAP} did not parse (an unknown status word, or a missing cell)")
    # a milestone or decision row: every line that starts like one must parse, and an id stands in one row only
    lines = text.split("\n")
    for name, start, rx, cells in (("milestone", re.compile(r"\| " + MS + r" \|"), MS_ROW, 4), ("decision", re.compile(r"\| " + DEC + r" \|"), DEC_ROW, 5)):
        first = {}
        for n, line in enumerate(lines, 1):
            if not start.match(line):
                continue
            m = rx.match(line)
            if not m:
                w.append(f"{ROADMAP} line {n}: a {name} row that did not parse (it needs {cells} cells, each closed by a pipe; "
                         f"a pipe inside a cell is written \\|): {line.strip()[:90]}")
            elif m["id"] in first:
                w.append(f"{ROADMAP} line {n}: {name} {m['id']} already has a row (line {first[m['id']]}); an id stands in one row")
            else:
                first[m["id"]] = n
    for m in COUNT_ROW.finditer(text):
        c = collections.Counter(q["status"] for q in reqs.values() if q["p"] == m["p"])
        given = [int(x) for x in m.groups()[-6:-1]]
        if [c[k] for k in STATUSES] != given:
            w.append(f"{ROADMAP}'s Count table gives {m['p']} as " + ", ".join(f"{n} {k}" for n, k in zip(given, STATUSES))
                     + "; its rows give " + ", ".join(f"{c[k]} {k}" for k in STATUSES))
    return w


def id_segments(tail):
    """The ID list after a bullet's arrow, without a closing remark such as '; the foundation for APP-01'."""
    keep = []
    for seg in tail.split(";"):
        rest = re.sub(RID + r"|\d+", "", re.sub(r"\([^)]*\)", "", seg))
        if not re.search(r"[a-z]{3,}", rest):
            keep.append(seg)
    return ids_in(";".join(keep))


# what a decision's Needed before names: a milestone or a stage, bare or with the IDs that wait in parentheses
GATE = re.compile(r"(?<![\w.-])(?P<t>" + MS + "|" + STAGE + "|" + "|".join(re.escape(x) for x in LATE)
                  + r")(?!\w)(?:'s exit)?\s*(?:\((?P<par>[^)]*)\))?")


def parse_roadmap(text):
    reqs = parse_reqs(text)
    stages = {}
    for m in NAMED_ROW.finditer(text):
        name = m["name"].strip()
        sid = name.split()[0]
        if not is_stage(sid):
            continue
        stages[sid] = {"id": sid, "title": name[len(sid):].strip(" →"), "theme": m["theme"].strip(), "exit": plain(m["exit"]),
                       "ids": exit_ids(m["exit"], reqs)}
    ms = {}
    for m in MS_ROW.finditer(text):
        if m["id"] in ms:
            continue  # a second row for the same id is a problem line (shape_warnings); the first row stands
        why = cell(m, "why").strip()
        ms[m["id"]] = {"theme": plain(cell(m, "theme")), "closes": ids_in(cell(m, "closes")), "why": plain(why),
                       "deps": [x for x in dict.fromkeys(found(MS_ID, why)) if x != m["id"]],
                       "dgates": list(dict.fromkeys(found(DEC_ID, why))), "last": why.startswith("Last")}
    lanes = {}
    for m in MS_BULLET.finditer(text):
        mid = m["head"].split()[0]
        lane = LANE_OF.search(m["head"])
        if lane:
            lanes[mid] = lane["lane"]
        if "→" in m["tail"]:
            d = ms.setdefault(mid, {"theme": "", "closes": [], "why": "", "deps": [], "dgates": [], "last": False})
            d["closes"] = list(dict.fromkeys(d["closes"] + id_segments(m["tail"].rsplit("→", 1)[1])))
    line = LANES_LINE.search(text)  # '**Lanes** (each milestone's gym lane): M1 G1, M2 G2, M3 none yet'
    for m in LANE_PAIR.finditer(line[0] if line else ""):
        lanes.setdefault(m["ms"], m["lane"])
    decisions, warns = {}, shape_warnings(text, reqs)
    for m in DEC_ROW.finditer(text):
        if m["id"] in decisions:
            continue  # as for a milestone: the first row stands, the second is a problem line
        stands, need = cell(m, "stands").strip(), cell(m, "need").strip()
        # decided only on the word itself: any other wording keeps the gate, and an unknown one is flagged
        if stands.startswith("**Decided"):
            state = "part" if "Still open" in stands else "decided"
        elif stands.startswith("**Half"):
            state = "part"
        else:
            state = "open"
            if not (stands.startswith("Open") or stands.startswith("**Adapted")):
                warns.append(f"{m['id']}'s Where it stands starts with neither Open, **Decided, **Half nor **Adapted; read as open")
        # 'M36 (UPD-06)' gates that ID alone; a bare 'M43' gates the milestone
        targets = {}
        for g in GATE.finditer(need):
            t, par = g["t"], g["par"]
            ids = [i for i in ids_in(par or "", parens=True) if i in reqs]
            targets[t] = None if (t in targets and targets[t] is None) or not ids else targets.get(t, []) + ids
        decisions[m["id"]] = {"id": m["id"], "what": plain(cell(m, "what")), "stands": plain(stands), "owner": cell(m, "owner").strip(),
                              "need": plain(need), "state": state, "targets": targets,
                              # IDs named beside the targets: 'M28 (SEC-06); the rest of SHELL-03 and SHELL-04'
                              "extra": [i for i in ids_in(GATE.sub(" ", need), parens=True) if i in reqs]}
    return reqs, stages, ms, lanes, decisions, warns


# ---------------------------------------------------------------- the model

STAGES = ["Planned", "Contract", "Build and dev runs", "Counted runs", "Passed"]
STATE_LABEL = {"done": "done", "work": "in work", "queued": "in this push", "ready": "ready to start",
               "user": "needs the user", "waits": "waits on a milestone"}


def lane_dates(root):
    """{path: first time the file appeared on any branch}."""
    out = {}
    t = None
    for line in git(root, "log", "--all", "--diff-filter=A", "--name-only", "--format=@%ct", "--",
                    rel("gym", "contracts"), rel("gym", "prereg")).splitlines():
        if line.startswith("@"):
            t = float(line[1:])
        elif line.strip() and t is not None:
            out[line.strip()] = min(t, out.get(line.strip(), t))
    return out


def series_points(root):
    """{lane: [point, oldest first]} from the gym's series, archived files included, one per run id."""
    by = collections.defaultdict(dict)
    folder = at(root, "gym") / "series"
    if not folder.is_dir():
        absent(f"{rel('gym', 'series')} is not there yet, so no counted run is read")
        return {}
    for f in sorted(folder.glob("*.json*")):
        lane = f.name.split(".json")[0]
        for p in dicts(load_json(f, {}).get("points"), f"points in {f.name}", ("run_id",)):
            if num(p.get("ts")) is not None:
                by[lane][p["run_id"]] = p
            else:
                SKIPPED[f"points in {f.name}"] += 1
    return {k: sorted(v.values(), key=lambda p: p["ts"]) for k, v in by.items()}


def timeclock(root):
    evs = []
    try:
        with open(at(root, "office") / "timeclock.jsonl", encoding="utf-8") as f:
            for line in f:
                if not line.strip():  # office.py's own reader skips blank lines too
                    continue
                try:
                    d = json.loads(line)
                except ValueError:
                    SKIPPED["timeclock lines"] += 1
                    continue
                if isinstance(d, dict) and num(d.get("at")) is not None and isinstance(d.get("id"), str):
                    evs.append(d)
                else:
                    SKIPPED["timeclock lines"] += 1
    except FileNotFoundError:
        absent("timeclock.jsonl is missing")
    except OSError:
        NOT_READ.append("timeclock.jsonl could not be read")
    return evs


def build_model(root, now):
    del NOT_READ[:]
    del ABSENT[:]
    SKIPPED.clear()
    READ_AS.clear()
    try:
        text = at(root, "roadmap").read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        text = ""
        NOT_READ.append(f"{ROADMAP} is missing ({rel('roadmap')}): no stage, milestone, requirement or decision is read")
    except OSError as e:
        text = ""
        NOT_READ.append(f"{ROADMAP} could not be read ({type(e).__name__})")
    reqs, stages, rms, rlanes, decisions, warns = parse_roadmap(text)
    # the road graph asset (flow_graph.py): once the manager has seeded it, every "must come first" and every
    # decision gate is read from it, and the roadmap's prose is only compared against it (graph_notes)
    G, gbad = flow_graph.load(root)
    gok, glines = flow_graph.verify(root)
    graph_bad = [x for x in gbad + glines if not gok or x in gbad]
    graph_notes = []
    if G is not None:
        prose = {(d, mid) for mid, r in rms.items() for d in r["deps"]} | \
                {(did, mid) for mid, r in rms.items() for did in r["dgates"]} | \
                {(did, t) for did, d in decisions.items() for t in d["targets"]}
        have = {(e["from"], e["to"]) for e in G["edges"]}
        graph_notes += [f"{ROADMAP}'s prose names {a} before {b}, and the graph has no such link" for a, b in sorted(prose - have)
                        if a in G["nodes"] and b in G["nodes"]]
        after = collections.defaultdict(list)
        for e in G["edges"]:
            after[(e["to"], e["in"])].append(e)
        for mid in set(rms) | {e["to"] for e in G["edges"] if e["in"] == "after"}:
            r = rms.setdefault(mid, {"theme": "", "closes": [], "why": "", "deps": [], "dgates": [], "last": False})
            r["deps"], r["dgates"] = [e["from"] for e in after[(mid, "after")] if flow_graph.type_of(e["from"]) == "milestone"], []
        for did, d in decisions.items():
            d["targets"] = {e["to"]: (e.get("ids") or None) for e in G["edges"] if e["from"] == did and e["out"] == "decides"}
    if "�" in text:
        NOT_READ.append(f"{ROADMAP} is not all UTF-8; the bytes that are not were replaced")
    if G is None and not gbad:
        absent("the road graph is not seeded yet, so its links are guessed from the roadmap's prose")
    state = clean_state(load_json(at(root, "state"), {}))

    # milestones: the map's list, plus a phase of the map that no milestone holds
    ms = {}
    for m in state["milestones"]:
        ms[m["id"]] = {"id": m["id"], "title": m["title"], "status": m["status"], "lane": m["lane"]}
    for p in state["phases"]:
        if not p.get("milestone") and p["id"] not in ms:
            ms[p["id"]] = {"id": p["id"], "title": p["title"],
                           "status": p["status"], "lane": p["lane"]}
    for mid in rms:
        if mid not in ms and state["milestones"]:
            warns.append(f"{mid} is in {ROADMAP}'s milestone tables but not in the map's milestones")
        if mid not in ms:
            ms[mid] = {"id": mid, "title": cut(rms[mid]["theme"], 40), "status": "planned", "lane": None}
    for mid, m in ms.items():
        r = rms.get(mid, {})
        m["lane"] = m["lane"] or rlanes.get(mid)
        held = list(r.get("closes", []))
        held += [i for i, q in reqs.items() if mid in q["where"] and i not in held]
        for i in held:
            if i not in reqs:
                warns.append(f"{mid} names {i}, which has no requirement row")
        m["ids"] = [i for i in held if i in reqs]
        m["left"] = [i for i in m["ids"] if reqs[i]["p"] == TOP and reqs[i]["status"] not in MET]
        m["deps"] = [d for d in r.get("deps", []) if d in ms]
        for d in r.get("deps", []):
            if d not in ms:
                warns.append(f"{mid}'s Why here names {d}, which is not a milestone")
        m["last"], m["why"], m["theme"] = r.get("last", False), r.get("why", ""), r.get("theme", "")
        m["done"] = m["status"] == "done"
    open_ms = {k: m for k, m in ms.items() if not m["done"]}

    # decisions that still gate something
    # A gate is partial when Needed before names the milestone with the IDs that wait ('M36 (UPD-06)'): the
    # Decisions table is the narrower word, so it holds even where the milestone's Why here names the decision.
    # Otherwise it is whole: Needed before names the milestone bare, or only its Why here names the decision.
    for d in decisions.values():
        t = d["targets"]
        d["full"] = list(dict.fromkeys([x for x in t if x in ms and t[x] is None] +
                                       [mid for mid, r in rms.items() if d["id"] in r["dgates"] and mid in ms and not t.get(mid)]))
        d["partial"] = {x: ids for x, ids in t.items() if x in ms and ids and x not in d["full"]}
        d["stage_ids"] = {x: ids or [] for x, ids in t.items() if x in stages}
        d["stages"] = list(d["stage_ids"])
        d["gates"] = d["full"] + list(d["partial"])
    open_dec = {k: d for k, d in decisions.items() if d["state"] != "decided"}
    for m in ms.values():
        m["gates"] = [d["id"] for d in open_dec.values() if m["id"] in d["full"]]
        m["pgates"] = {d["id"]: d["partial"][m["id"]] for d in open_dec.values() if m["id"] in d["partial"]}

    # depth among the open milestones, cycles guarded
    depth = {}

    def dep(mid, seen=()):
        if mid in depth:
            return depth[mid]
        if mid in seen:
            warns.append(f"dependency cycle through {mid}")
            return 0
        od = [x for x in ms[mid]["deps"] if x in open_ms]
        depth[mid] = 1 + max(dep(x, seen + (mid,)) for x in od) if od else 0
        return depth[mid]

    for mid in open_ms:
        dep(mid)
    top = max([v for k, v in depth.items() if not ms[k]["last"]], default=0)
    for mid in open_ms:
        if ms[mid]["last"]:
            depth[mid] = top + 1
    succ = collections.defaultdict(list)
    for mid, m in open_ms.items():
        for d in m["deps"]:
            if d in open_ms:
                succ[d].append(mid)

    def downstream(mid, acc=None):
        acc = acc if acc is not None else set()
        for s in succ[mid]:
            if s not in acc:
                acc.add(s)
                downstream(s, acc)
        return acc

    unmet_p0 = lambda i: i in reqs and reqs[i]["p"] == TOP and reqs[i]["status"] not in MET
    for d in open_dec.values():
        reach = set()
        for g in d["full"]:
            if g in open_ms:
                reach |= {g} | downstream(g)
        named = [i for ids in list(d["partial"].values()) + list(d["stage_ids"].values()) + [d["extra"]] for i in ids]
        d["reach"] = sorted(reach, key=mnum)
        d["p0"] = sorted({i for g in reach for i in ms[g]["left"]} | {i for i in named if unmet_p0(i)})
        d["behind"] = ", ".join(d["reach"] + [f"{k} ({', '.join(v)})" for k, v in d["partial"].items() if k in open_ms]
                                + [f"{k}'s exit" + (f" ({', '.join(v)})" if v else "") for k, v in d["stage_ids"].items()]
                                + d["extra"])

    # the pipeline: where each lane stands and when it got there
    adds = lane_dates(root)
    if not adds:
        absent(f"git gave no history for {rel('gym', 'contracts')} and {rel('gym', 'prereg')}, so every lane without a counted run shows as Planned")
    series = series_points(root)
    lanes = {}
    for lane in sorted({m["lane"] for m in ms.values() if m["lane"]}):
        pts = series.get(lane, [])
        t = [None,
             adds.get(rel("gym", "contracts", f"{lane}-artifacts.md")),
             adds.get(rel("gym", "prereg", f"{lane}.json")),
             pts[0]["ts"] if pts else None,
             next((p["ts"] for p in pts if p.get("verdict") == "PASS"), None)]
        last = None
        for i in range(1, 5):  # a stage is never entered before the one before it
            if t[i] is not None:
                t[i] = max(t[i], last) if last is not None else t[i]
                last = t[i]
        stage = max((i for i in range(1, 5) if t[i] is not None), default=0)
        lanes[lane] = {"lane": lane, "t": t, "stage": stage, "runs": len(pts),
                       "newest": (pts[-1].get("verdict"), pts[-1].get("run_id"), pts[-1].get("n")) if pts else None}

    # who is on the clock now
    roster = clean_roster(load_json(at(root, "office") / "roster.json", {}))
    evs = timeclock(root)
    last_ev = {}
    for e in evs:
        if e.get("ev") in ("in", "out"):
            last_ev[e["id"]] = e["ev"]
    live = [b for b in roster.values() if last_ev.get(b["id"]) == "in" and not b.get("revoked")
            and now - b["issued"] < 3 * DAY and b["role"] not in ("MANAGER", "FOUNDER")]

    blocks = state["shift"]["blocks"]
    fails = state["failures"]
    for mid, m in ms.items():
        L = lanes.get(m["lane"]) if m["lane"] else None
        m["stage"] = 4 if m["done"] else min(L["stage"], 3) if L else 0
        m["since"] = L["t"][m["stage"]] if L and m["stage"] else None
        pat = re.compile(r"\b(" + "|".join(re.escape(x) for x in [mid] + ([m["lane"]] if m["lane"] else [])) + r")\b")
        m["crew"] = [b["id"] for b in live if (m["lane"] and b["lane"] == m["lane"]) or pat.search(b["job"])]
        m["block"] = next((b.get("status") or "pending" for b in blocks if re.search(rf"\b{re.escape(mid)}\b", b["title"])
                           and b.get("status") != "skipped"), None)
        m["fails_open"] = sum(1 for f in fails if m["lane"] and f.get("lane") == m["lane"] and f.get("status") in ("open", "planned"))
        open_deps = [d for d in m["deps"] if d in open_ms]
        m["state"] = ("done" if m["done"] else "work" if m["stage"] or m["crew"] else "queued" if m["block"]
                      else "user" if m["gates"] else "waits" if open_deps else "ready")
        m["depth"] = depth.get(mid, 0)

    for sid, s in stages.items():
        s["counts"] = collections.Counter(reqs[i]["status"] for i in s["ids"])
        s["met"] = sum(s["counts"][x] for x in MET)
        s["feeds"] = [mid for mid, m in open_ms.items() if set(m["ids"]) & {i for i in s["ids"] if reqs[i]["status"] not in MET}]

    # first-tier requirements that nothing open holds and no open decision names: a hole in the plan
    waits_on_decision = {i for d in open_dec.values()
                         for ids in list(d["partial"].values()) + list(d["stage_ids"].values()) + [d["extra"]] for i in ids}
    orphans = [i for i, q in reqs.items() if q["p"] == TOP and q["status"] not in MET
               and not any(i in m["ids"] for m in open_ms.values()) and i not in waits_on_decision]

    return {"root": root, "now": now, "reqs": reqs, "stages": stages, "order": stage_order(stages), "ms": ms, "roadmap_ms": rms, "open_ms": open_ms,
            "decisions": decisions, "open_dec": open_dec, "lanes": lanes, "series": series, "state": state,
            "roster": roster, "evs": evs, "live": live, "warns": list(dict.fromkeys(warns)), "orphans": orphans,
            "graph": G, "graph_ok": gok, "graph_bad": graph_bad + graph_drift(G, ms, decisions, stages, state),
            "graph_notes": graph_notes, "graph_lines": glines}


def graph_drift(G, ms, decisions, stages, state):
    """Where the asset and the roadmap no longer name the same things: each is the manager's to fix with
    `flow.py graph node add|rm` or `graph unlink`."""
    if G is None:
        return []
    real = {**{k: "milestone" for k in ms}, **{k: "decision" for k in decisions}, **{k: "stage" for k in stages}}
    blocks = {m["id"] for b in state["shift"]["blocks"] for m in [re.match(r"\s*(?P<id>" + flow_graph.BLOCK + r")\b", b["title"])] if m}
    bad = [f"{k} is a {t} in {ROADMAP} or the map and has no node in the graph (graph node add {k})"
           for k, t in sorted(real.items(), key=lambda kv: mnum(kv[0])) if k not in G["nodes"]]
    bad += [f"graph node {k} ({n['type']}) is no longer in {ROADMAP} or the map (graph node rm {k})"
            for k, n in G["nodes"].items() if n["type"] != "block" and k not in real]
    for e in G["edges"]:
        for end in (e["from"], e["to"]):
            if end not in G["nodes"] and end not in blocks:
                bad.append(f"graph link {e['from']} → {e['to']} names {end}, which is not a node"
                           + (" (a push block that is no longer in the shift)" if flow_graph.type_of(end) == "block" else ""))
    loop = flow_graph.cycle(G["edges"])
    return bad + ([f"the graph has a loop: {' → '.join(loop)}"] if loop else [])


# ---------------------------------------------------------------- flow numbers

def day_of(ts):
    return dt.datetime.fromtimestamp(ts).date()


def days_back(now, n=WINDOW):
    today = day_of(now)
    return [today - dt.timedelta(days=i) for i in range(n - 1, -1, -1)]


NAMED_IN_TOPIC = re.compile(LANE + r"|(?<![\w-])" + MS + r"(?!\w)")  # the lanes and milestones a review's topic names


def flow_numbers(M):
    now, state = M["now"], M["state"]
    days = days_back(now)
    idx = {d: i for i, d in enumerate(days)}
    zero = lambda: [0.0] * len(days)
    F = {"days": days}

    # badge hours on the clock, by role
    roles = ["BUILDER", "REVIEWER", "GRADER", "SCOUT", "MANAGER"]
    hours = {r: zero() for r in roles}
    opened, spans = {}, []
    for e in M["evs"]:
        if e.get("ev") == "in":
            opened.setdefault(e["id"], e["at"])
        elif e.get("ev") == "out" and e["id"] in opened:
            spans.append((e["id"], opened.pop(e["id"]), e["at"], e.get("result")))
    for bid, t0 in opened.items():
        if now - t0 < 3 * DAY:
            spans.append((bid, t0, now, None))
    for bid, t0, t1, _ in spans:
        role = M["roster"].get(bid, {}).get("role")
        if role not in hours:
            continue
        t = t0
        while t < t1:
            d = day_of(t)
            end = min(t1, dt.datetime.combine(d + dt.timedelta(days=1), dt.time()).timestamp())
            if d in idx:
                hours[role][idx[d]] += (end - t) / 3600
            t = end
    F["hours"] = [(r.capitalize(), hours[r]) for r in roles]

    # how long a job took against the time its brief gave it
    ratio = collections.defaultdict(lambda: {"new": [], "old": []})
    for bid, t0, t1, result in spans:
        b = M["roster"].get(bid, {})
        if result is None or not b.get("eta_s") or b.get("role") in ("MANAGER", "FOUNDER"):
            continue
        age = now - t1
        if age < 14 * DAY:
            ratio[b["role"]]["new" if age < 7 * DAY else "old"].append((t1 - t0) / b["eta_s"])
    F["eta"] = {r: {k: (round(statistics.median(v), 2), len(v)) if v else None for k, v in d.items()} for r, d in ratio.items()}

    # counted runs by verdict
    verdicts = ["PASS", "MEASURING", "FAIL", "VOID"]
    runs = {v: zero() for v in verdicts}
    void7 = collections.Counter()
    runs7 = collections.Counter()
    for lane, pts in M["series"].items():
        for p in pts:
            v = p.get("verdict")
            v = v if v in verdicts else "MEASURING" if v in ("MARGINAL", "STARVED") else "FAIL" if v else None
            d = day_of(p["ts"])
            if v and d in idx:
                runs[v][idx[d]] += 1
            if v and now - p["ts"] < 7 * DAY:
                runs7[v] += 1
                if v == "VOID":
                    void7[lane] += 1
    F["runs"], F["runs7"], F["void7"] = [(v, runs[v]) for v in verdicts], runs7, void7

    # reviews by the verdict their first finding names
    kinds = ["GO", "GO-with-fixes", "NO-GO"]
    rev = {k: zero() for k in kinds}
    rev7 = {"new": collections.Counter(), "old": collections.Counter()}
    nogo_lane = collections.Counter()
    today = day_of(now)
    unsorted7 = 0
    for r in state.get("research_review", []):
        if r.get("kind") != "review":
            continue
        fnd = r.get("findings")
        first = str(fnd[0]) if isinstance(fnd, list) and fnd else ""
        # the worst verdict word in the first finding: 'f550b06e GO-with-fixes; c3812eca NO-GO' is a NO-GO
        k = "NO-GO" if re.search(r"\bNO-GO\b", first) else "GO-with-fixes" if re.search(r"\bGO[- ]with[- ]fixes\b", first) \
            else "GO" if re.search(r"(?<![-\w])GO\b", first) else None
        try:
            d = dt.date.fromisoformat(str(r.get("date"))[:10])
        except ValueError:
            continue
        if not k:
            unsorted7 += 0 <= (today - d).days < 7
            continue
        if d in idx:
            rev[k][idx[d]] += 1
        age = (today - d).days
        if age < 14:
            rev7["new" if age < 7 else "old"][k] += 1
        if age < 7 and k == "NO-GO":
            for lane in set(found(NAMED_IN_TOPIC, r["topic"])):
                nogo_lane[lane] += 1
    F["reviews"], F["rev7"], F["nogo_lane"], F["rev_unsorted7"] = [(k, rev[k]) for k in kinds], rev7, nogo_lane, unsorted7

    # failures: filed per day, by where they stand today
    fst = ["fixed", "planned", "open", "dropped"]
    filed = {s: zero() for s in fst}
    by_lane = collections.defaultdict(collections.Counter)
    for f in state.get("failures", []):
        try:
            d = dt.date.fromisoformat(str(f.get("at"))[:10])
        except ValueError:
            continue
        s = f.get("status") if f.get("status") in fst else "open"
        if d in idx:
            filed[s][idx[d]] += 1
        by_lane[str(f.get("lane") or "no lane").replace("none", "no lane")][s] += 1
    F["filed"], F["fail_lane"] = [(s, filed[s]) for s in fst], by_lane
    F["fail_now"] = collections.Counter(f.get("status") for f in state.get("failures", []))

    # who the crew waited on
    waits = collections.Counter()
    for e in M["evs"]:
        if e.get("ev") == "progress" and e.get("waiting_on") and now - e["at"] < 7 * DAY:
            waits[cut(e["waiting_on"], 28)] += 1
    F["waits"] = waits

    # the shared resource's queue now (a project with no shared resource has none)
    q = dicts(load_json(at(M["root"], "office") / "rq.queue.json", [], optional=True), "queue entries") if P.has_resource() else []
    F["rq"] = [{"id": str(w.get("id")), "job": cut(w.get("job") or "", 70), "min": round((now - num(w.get("at"), now)) / 60)} for w in q]

    # usage against the weekly stop
    u = state.get("usage", {})
    pts = []
    for p in u.get("points") if isinstance(u.get("points"), list) else []:
        try:
            w = float(p["weekly"])
            if not 0 <= w <= 1000:  # also turns away inf and nan
                raise ValueError
            pts.append((dt.datetime.fromisoformat(p["at"]).timestamp(), w))
        except (KeyError, ValueError, TypeError, OverflowError, OSError):
            SKIPPED["usage points"] += 1
    F["usage"] = None
    if len(pts) >= 2:
        recent = [p for p in pts if pts[-1][0] - p[0] <= DAY] or pts
        rate = (recent[-1][1] - recent[0][1]) / max((recent[-1][0] - recent[0][0]) / 3600, 0.01)
        stop = num(u.get("stop"), 100.0)
        try:
            reset = dt.datetime.fromisoformat(u["reset"]).timestamp()
            reset = reset if abs(reset - now) < 60 * DAY else None  # a weekly reset further off is a typo
        except (KeyError, ValueError, TypeError, OverflowError, OSError):
            reset = None
        hit = pts[-1][0] + (stop - pts[-1][1]) / rate * 3600 if rate > 0 else None
        hit = hit if hit is not None and abs(hit - now) < 60 * DAY else None  # further off is no forecast
        F["usage"] = {"now": pts[-1][1], "rate": round(rate, 2), "stop": stop, "hit": hit, "reset": reset}

    # first-tier statuses over time, from the roadmap's own history
    per_day = {}
    for line in git(M["root"], "log", "--format=%H %ct", "--", rel("roadmap")).splitlines():
        sha, _, ct = line.partition(" ")
        d = day_of(float(ct))
        per_day.setdefault(d, sha)  # newest first: the day's last commit wins
    burn_days = sorted(per_day)
    cols = ["Met", "Part", "Planned", "Open"]
    burn = []
    for d in burn_days:
        c = collections.Counter(q["status"] for q in parse_reqs(git(M["root"], "show", f"{per_day[d]}:{rel('roadmap')}")).values()
                                if q["p"] == TOP)
        burn.append((d, [c["PASS"] + c["Decided"], c["Part"], c["Planned"], c["Open"]]))
    if burn:
        full, cur, j = [], burn[0][1], 0
        d = burn[0][0]
        while d <= today:
            while j < len(burn) and burn[j][0] <= d:
                cur = burn[j][1]
                j += 1
            full.append((d, cur))
            d += dt.timedelta(days=1)
        F["burn_days"] = [d for d, _ in full]
        F["burn"] = [(c, [v[i] for _, v in full]) for i, c in enumerate(cols)]
    else:
        F["burn_days"], F["burn"] = [], []

    # how many lanes had reached each stage, day by day
    ts = [L["t"] for L in M["lanes"].values()]
    starts = [x for t in ts for x in t[1:] if x]
    if starts:
        d0 = day_of(min(starts))
        cdays = [d0 + dt.timedelta(days=i) for i in range((today - d0).days + 1)]
        cfd = []
        for k in range(1, 5):
            row = []
            for d in cdays:
                end = dt.datetime.combine(d + dt.timedelta(days=1), dt.time()).timestamp()
                row.append(sum(1 for t in ts if any(t[j] and t[j] < end for j in range(k, 5))))
            cfd.append((STAGES[k] if k < 4 else "Passed", row))
        F["cfd_days"], F["cfd"] = cdays, cfd
    else:
        F["cfd_days"], F["cfd"] = [], []
    return F


def findings(M, F):
    ms, now = M["ms"], M["now"]
    out = []

    def add(kind, head, text):
        out.append({"kind": kind, "head": head, "text": text})

    unread = NOT_READ + shape_notes()
    if unread:
        add("act", "Input not read: figures below may be short", "; ".join(unread) + ".")
    ready = sorted([m for m in M["open_ms"].values() if m["state"] == "ready"], key=lambda m: (-len(m["left"]), mnum(m["id"])))
    if ready:
        part = lambda m: " (" + f"{len(m['left'])} {TOP}" + "".join(f"; {', '.join(ids)} waits on {d}" for d, ids in m["pgates"].items()) + ")"
        add("act", "Ready to start", "No decision or open milestone holds back " + ", ".join(f"{m['id']} {m['title']}{part(m)}" for m in ready) + ".")
    decs = sorted([d for d in M["open_dec"].values() if d["p0"] or d["reach"]], key=lambda d: (-len(d["p0"]), mnum(d["id"])))
    if decs:
        add("user", "Decisions holding the most work",
            "; ".join(f"{d['id']} ({cut(d['what'], 34)}) holds {len(d['p0'])} unmet {TOP} behind {d['behind'] or 'nothing named'}"
                      for d in decs[:6]) + ".")
    slow = sorted([m for m in M["open_ms"].values() if m["stage"] and m["since"]], key=lambda m: m["since"])
    for m in slow[:3]:
        L = M["lanes"][m["lane"]]
        newest = f"; newest counted run {L['newest'][0]} n={L['newest'][2]}" if L["newest"] else ""
        add("watch", f"{m['id']} in “{STAGES[m['stage']]}” for {(now - m['since']) / DAY:.1f} days",
            f"Lane {m['lane']}{newest}; {m['fails_open']} failures open or planned on the lane; crew now: {', '.join(m['crew']) or 'nobody'}.")
    r7 = F["runs7"]
    if sum(r7.values()):
        tot = sum(r7.values())
        add("watch" if r7["VOID"] * 4 >= tot else "info", "Counted runs, last 7 days",
            f"{tot} runs: {r7['PASS']} PASS, {r7['MEASURING']} MEASURING, {r7['FAIL']} FAIL, {r7['VOID']} VOID"
            + (" (VOID by lane: " + ", ".join(f"{k} {v}" for k, v in F["void7"].most_common()) + ")" if r7["VOID"] else "") + ".")
    new, old = F["rev7"]["new"], F["rev7"]["old"]
    if sum(new.values()):
        rate = lambda c: f"{100 * c['GO'] / sum(c.values()):.0f}%" if sum(c.values()) else "n/a"
        n_all = sum(new.values()) + F["rev_unsorted7"]
        add("watch" if new["NO-GO"] * 3 >= sum(new.values()) else "info", "Reviews, last 7 days",
            f"{sum(new.values())} of {n_all} reviews name a verdict in their first finding: {new['GO']} GO, {new['GO-with-fixes']} GO-with-fixes, "
            f"{new['NO-GO']} NO-GO; clean GO rate {rate(new)} against {rate(old)} the week before"
            + (". NO-GO most on " + ", ".join(f"{k} ({v})" for k, v in F["nogo_lane"].most_common(4)) if F["nogo_lane"] else "") + ".")
    eta = [(r, d["new"]) for r, d in F["eta"].items() if d.get("new")]
    if eta:
        add("info", "Time on the clock against the brief's estimate, last 7 days",
            "Median of clocked time over the badge's estimate (under 1 is early): " + ", ".join(f"{r.lower()} ×{v[0]} (n={v[1]})" for r, v in sorted(eta)) + ".")
    if F["waits"]:
        add("info", "Who the crew waited on, last 7 days",
            ", ".join(f"{k} ({v} posts)" for k, v in F["waits"].most_common(6)) + ".")
    if F["rq"]:
        add("info", f"The queue for {P.get('resource.name')} now", "; ".join(f"{w['id']} {w['min']} min: {w['job']}" for w in F["rq"]) + ".")
    u = F["usage"]
    if u:
        fmt = lambda t: dt.datetime.fromtimestamp(t).strftime("%a %H:%M")
        late = u["hit"] and u["reset"] and u["hit"] < u["reset"]
        add("watch" if late else "info", "Usage",
            f"{u['now']:.0f}% of the week, {u['rate']:+.2f} points an hour over the last day"
            + (f"; at this rate the {u['stop']:.0f}% stop comes {fmt(u['hit'])}" if u["hit"] else "")
            + (f", the reset is {fmt(u['reset'])}" if u["reset"] else "") + ".")
    fn = F["fail_now"]
    worst = sorted(F["fail_lane"].items(), key=lambda kv: -(kv[1]["open"] + kv[1]["planned"]))[:5]
    add("info", "Failure backlog", f"{fn['open']} open and {fn['planned']} planned of {sum(fn.values())} filed"
        + ("; most on " + ", ".join(f"{k} ({c['open'] + c['planned']})" for k, c in worst) if worst else "") + ".")
    if M["orphans"]:
        add("act", f"{len(M['orphans'])} unmet {TOP} requirements that only finished milestones hold",
            ", ".join(M["orphans"]) + ". Their Where cells name no open milestone and no open decision names them, so no planned work closes them.")
    chain = []
    for mid in M["open_ms"]:
        c, cur = [mid], mid
        while True:
            nxt = [d for d in ms[cur]["deps"] if d in M["open_ms"] and d not in c]  # 'not in c': a cycle ends the walk
            if not nxt:
                break
            cur = max(nxt, key=lambda x: ms[x]["depth"])
            c.append(cur)
        chain = c if len(c) > len(chain) else chain
    if len(chain) > 1:
        add("info", "Longest chain of open milestones", " → ".join(reversed(chain)) + ". Its first link sets the earliest date for its last.")
    for w in M["warns"]:
        add("act", "Roadmap shape", w)
    return out


def tiles(M, F):
    reqs = M["reqs"]
    p0 = [q for q in reqs.values() if q["p"] == TOP]
    st = collections.Counter(m["state"] for m in M["ms"].values())
    return [(f"{TOP} met", f"{sum(1 for q in p0 if q['status'] in MET)} / {len(p0)}", f"PASS or Decided in {ROADMAP}"),
            (f"{TOP} part built", str(sum(1 for q in p0 if q["status"] == "Part")), "graded or built in part"),
            ("Milestones done", f"{st['done']} / {len(M['ms'])}", "by the map's statuses"),
            ("In work", str(st["work"]), "a contract, a lane or crew on it"),
            ("Ready to start", str(st["ready"]), "no gate, nobody on it"),
            ("Need the user", str(st["user"]), f"{len(M['open_dec'])} decisions open"),
            ("Crew on the clock", str(len(M["live"])), "badges in, the manager and the founder aside"),
            ("Failures open", str(F["fail_now"]["open"]), f"{F['fail_now']['planned']} more planned")]


# ---------------------------------------------------------------- drawing

def nice_max(v):
    if v <= 0:
        return 1, 1
    for step in (x * m for m in (1, 10, 100, 1000) for x in (1, 2, 5)):
        if v / step <= 5:
            n = int(-(-v // step))
            return step * n, step
    return v, v


def legend(names, colors):
    return '<div class="legend">' + "".join(f'<span><i style="background:var({c})"></i>{esc(n)}</span>'
                                             for n, c in zip(names, colors)) + "</div>"


def stacked(days, series, colors, unit, fmt="{:.0f}"):
    n = len(days)
    if not n:
        return '<p class="empty">No data yet.</p>'
    W, H, L, R, T, B = 560, 190, 34, 6, 8, 22
    tot = [sum(s[1][i] for s in series) for i in range(n)]
    top, step = nice_max(max(tot))
    pw, ph = W - L - R, H - T - B
    bw = pw / n
    y = lambda v: T + ph - ph * v / top
    o = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{esc(unit)} per day">']
    v = 0
    while v <= top + 1e-9:
        o.append(f'<line class="grid" x1="{L}" x2="{W - R}" y1="{y(v):.1f}" y2="{y(v):.1f}"/>'
                 f'<text class="tick" x="{L - 5}" y="{y(v) + 3:.1f}" text-anchor="end">{v:g}</text>')
        v += step
    every = max(1, n // 7)
    for i, d in enumerate(days):
        x = L + i * bw
        if (n - 1 - i) % every == 0:
            o.append(f'<text class="tick" x="{x + bw / 2:.1f}" y="{H - 6}" text-anchor="middle">{d.month}-{d.day:02d}</text>')
        if not tot[i]:
            continue
        tip = f"{d:%a %Y-%m-%d}\n" + "\n".join(f"{s[0]}: {fmt.format(s[1][i])}" for s in series if s[1][i]) + f"\nTotal: {fmt.format(tot[i])} {unit}"
        acc = 0.0
        g = [f'<g data-tip="{esc(tip)}"><rect class="hit" x="{x:.1f}" y="{T}" width="{bw:.1f}" height="{ph}"/>']
        for (name, vals), c in zip(series, colors):
            if vals[i]:
                y1, y0 = y(acc + vals[i]), y(acc)
                g.append(f'<rect x="{x + 1:.1f}" y="{y1:.1f}" width="{max(bw - 2, 1):.1f}" height="{max(y0 - y1 - 1, 0.6):.1f}" rx="1.5" style="fill:var({c})"/>')
                acc += vals[i]
        o.append("".join(g) + "</g>")
    o.append(f'<line class="axis" x1="{L}" x2="{W - R}" y1="{T + ph}" y2="{T + ph}"/></svg>')
    return legend([s[0] for s in series], colors) + "".join(o)


def lines(days, series, colors, unit):
    n = len(days)
    if n < 2:
        return '<p class="empty">No data yet.</p>'
    W, H, L, R, T, B = 560, 190, 34, 96, 8, 22
    top, step = nice_max(max(max(s[1]) for s in series))
    pw, ph = W - L - R, H - T - B
    x = lambda i: L + pw * i / (n - 1)
    y = lambda v: T + ph - ph * v / top
    o = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{esc(unit)}">']
    v = 0
    while v <= top + 1e-9:
        o.append(f'<line class="grid" x1="{L}" x2="{W - R}" y1="{y(v):.1f}" y2="{y(v):.1f}"/>'
                 f'<text class="tick" x="{L - 5}" y="{y(v) + 3:.1f}" text-anchor="end">{v:g}</text>')
        v += step
    every = max(1, n // 6)
    for i, d in enumerate(days):
        if (n - 1 - i) % every == 0:
            o.append(f'<text class="tick" x="{x(i):.1f}" y="{H - 6}" text-anchor="middle">{d.month}-{d.day:02d}</text>')
    ends = []
    for (name, vals), c in zip(series, colors):
        pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(vals))
        o.append(f'<polyline points="{pts}" style="stroke:var({c})" class="ln"/>')
        ends.append([y(vals[-1]), name, vals[-1], c])
    ends.sort()
    for i in range(1, len(ends)):  # keep the end labels apart
        ends[i][0] = max(ends[i][0], ends[i - 1][0] + 11)
    for yy, name, val, c in ends:
        o.append(f'<circle cx="{x(n - 1):.1f}" cy="{y(val):.1f}" r="3.5" style="fill:var({c})" class="dot"/>'
                 f'<text class="lbl" x="{x(n - 1) + 8:.1f}" y="{yy + 3:.1f}">{esc(name)} {val:g}</text>')
    for i, d in enumerate(days):
        tip = f"{d:%a %Y-%m-%d}\n" + "\n".join(f"{s[0]}: {s[1][i]:g}" for s in series)
        o.append(f'<rect class="hit col" data-tip="{esc(tip)}" x="{x(i) - pw / (n - 1) / 2:.1f}" y="{T}" width="{pw / (n - 1):.1f}" height="{ph}"/>')
    o.append(f'<line class="axis" x1="{L}" x2="{W - R}" y1="{T + ph}" y2="{T + ph}"/></svg>')
    return "".join(o)


def road_graph(M):
    """Open decisions, then the open milestones layered by what they wait on, then the numbered stages, then each
    named late stage in its own column, the goal last."""
    ms, reqs, stages = M["ms"], M["reqs"], M["stages"]
    order = M["order"]
    unmet = {s: {i for i in stages[s]["ids"] if reqs[i]["status"] not in MET} for s in order}

    def primary(m):
        best = max(order, key=lambda s: len(set(m["ids"]) & set(stages[s]["ids"])), default=None)
        return order.index(best) if best and set(m["ids"]) & set(stages[best]["ids"]) else len(order)

    layers = collections.defaultdict(list)
    for m in M["open_ms"].values():
        layers[m["depth"]].append(m)
    nl = max(layers, default=0) + 1
    NW, NH, GAP, COL = 164, 48, 8, 184
    rs = [s for s in order if s not in LATE]
    late = [s for s in order if s in LATE]
    tall = max([len(v) for v in layers.values()] + [len(rs), 1])
    dec = [d for d in M["open_dec"].values()]
    tall = max(tall, len(dec))
    H = tall * (NH + GAP) + 44
    pos = {}

    def place(col, ids):
        y0 = 34 + (H - 44 - len(ids) * (NH + GAP)) / 2
        for i, k in enumerate(ids):
            pos[k] = (14 + col * COL, y0 + i * (NH + GAP))

    for k in range(nl):
        place(1 + k, [m["id"] for m in sorted(layers[k], key=lambda m: (primary(m), mnum(m["id"])))])
    place(1 + nl, rs)
    for i, s in enumerate(late):
        place(2 + nl + i, [s])

    def bary(d):
        ys = [pos[g][1] for g in d["gates"] + d["stages"] if g in pos]
        return sum(ys) / len(ys) if ys else 1e9

    place(0, [d["id"] for d in sorted(dec, key=lambda d: (bary(d), mnum(d["id"])))])
    W = 14 + (2 + nl + len(late)) * COL - (COL - NW) + 14

    edges = []
    for m in M["open_ms"].values():
        for d in m["deps"]:
            if d in pos:
                edges.append((d, m["id"], "dep"))
        for s in rs:  # the late stages wait on every first-tier ID, so they are fed through the numbered stages
            if set(m["ids"]) & unmet[s] and s in pos:
                edges.append((m["id"], s, "feed"))
    for d in dec:
        for g in d["gates"] + d["stages"]:
            if g in pos:
                edges.append((d["id"], g, "gate" if g in d["full"] or g in d["stages"] else "gate pgate"))
    for s in rs:
        if late:
            edges.append((s, late[0], "dep"))
    for a, b in zip(late, late[1:]):
        edges.append((a, b, "dep"))

    o = [f'<svg id="road" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="Road to {esc(GOAL)}">',
         '<defs><marker id="ar" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto">'
         '<path d="M0,0 L8,4 L0,8 z" class="arh"/></marker></defs>']
    heads = [(0, "Open decisions")] + [(1 + k, "Open milestones" if k == 0 else "…then") for k in range(nl)] + \
            [(1 + nl, "Stages")] + [(2 + nl + i, s) for i, s in enumerate(late)]
    for col, name in heads:
        o.append(f'<text class="colh" x="{14 + col * COL}" y="16">{esc(name)}</text>')
    for a, b, kind in edges:
        (x1, y1), (x2, y2) = pos[a], pos[b]
        x1 += NW
        y1 += NH / 2
        y2 += NH / 2
        c = max(40, (x2 - x1) / 2)
        o.append(f'<path class="e {kind}" data-a="{esc(a)}" data-b="{esc(b)}" d="M{x1:.0f},{y1:.0f} C{x1 + c:.0f},{y1:.0f} {x2 - c:.0f},{y2:.0f} {x2 - 2:.0f},{y2:.0f}"'
                 + (' marker-end="url(#ar)"' if kind != "feed" else "") + "/>")

    def bar(x, y, counts, total):
        if not total:
            return ""
        out, acc, w = [], 0.0, NW - 20
        for key, cls in (("met", "--good"), ("Part", "--s1"), ("Planned", "--s1l"), ("Open", "--open")):
            v = counts.get(key, 0)
            if v:
                out.append(f'<rect x="{x + 10 + acc:.1f}" y="{y + NH - 9}" width="{max(w * v / total - 1, 1):.1f}" height="4" rx="2" style="fill:var({cls})"/>')
                acc += w * v / total
        return "".join(out)

    def node(k, cls, line1, line2, tip, bars=""):
        x, y = pos[k]
        return (f'<g class="n {cls}" data-id="{esc(k)}" data-tip="{esc(tip)}" tabindex="0"><rect class="box" x="{x}" y="{y}" width="{NW}" height="{NH}" rx="6"/>'
                f'<rect class="band" x="{x}" y="{y}" width="5" height="{NH}" rx="2"/>'
                f'<text class="t1" x="{x + 12}" y="{y + 17}">{esc(line1)}</text><text class="t2" x="{x + 12}" y="{y + 31}">{esc(line2)}</text>{bars}</g>')

    for m in M["open_ms"].values():
        if m["id"] not in pos:
            continue
        c = collections.Counter("met" if reqs[i]["status"] in MET else reqs[i]["status"] for i in m["ids"] if reqs[i]["p"] == TOP)
        why = {"user": " (" + ", ".join(m["gates"]) + ")", "waits": " (" + ", ".join(d for d in m["deps"] if d in M["open_ms"]) + ")"}.get(m["state"], "")
        flag = " ⚑" + ",".join(m["gates"]) if m["gates"] and m["state"] in ("work", "queued") else " ⚑" if m["pgates"] else ""
        tip = "\n".join(filter(None, [
            f"{m['id']} {m['title']}", m["theme"] and cut(m["theme"], 170),
            f"State: {STATE_LABEL[m['state']]}{why}", f"Pipeline: {STAGES[m['stage']]}" + (f", lane {m['lane']}" if m["lane"] else ", no lane yet"),
            "Holds: " + (", ".join(f"{i} {reqs[i]['status']}" for i in m["ids"]) or "no requirement IDs"),
            m["deps"] and "After: " + ", ".join(f"{d} ({'done' if ms[d]['done'] else 'open'})" for d in m["deps"]),
            m["gates"] and "Open decisions: " + ", ".join(m["gates"]),
            m["pgates"] and "Part waits on a decision: " + "; ".join(f"{', '.join(ids)} on {d}" for d, ids in m["pgates"].items()),
            m["crew"] and "Crew now: " + ", ".join(m["crew"]), m["why"] and "Why here: " + cut(m["why"], 170)]))
        o.append(node(m["id"], "st-" + m["state"], cut(f"{m['id']} {m['title']}", 25),
                      f"{STATE_LABEL[m['state']]}{flag} · {len(m['left'])} {TOP} left", tip, bar(*pos[m["id"]], c, sum(c.values()))))
    for d in dec:
        tip = "\n".join(filter(None, [f"{d['id']} {d['what']}", "Stands: " + cut(d["stands"], 260), "Owner: " + d["owner"],
                                      "Needed before: " + d["need"], f"Unmet {TOP} behind it: {', '.join(d['p0']) or 'none named'}"]))
        o.append(node(d["id"], "st-user dec", cut(f"{d['id']} {d['what']}", 25),
                      ("part open" if d["state"] == "part" else "open") + f" · holds {len(d['p0'])} {TOP}", tip))
    for s in order:
        if s not in pos:
            continue
        st = stages[s]
        c = dict(st["counts"])
        c["met"] = st["met"]
        left = [i for i in st["ids"] if reqs[i]["status"] not in MET]
        tip = "\n".join(filter(None, [f"{s} {st['title']}".strip() + f": {st['theme']}", f"Exit IDs met: {st['met']} of {len(st['ids'])}",
                                      "Exit, as the roadmap words it: " + cut(st["exit"], 200),
                                      left and "Not met: " + (", ".join(f"{i} {reqs[i]['status']}" for i in left) if len(left) <= 30 else
                                                              ", ".join(f"{n} {k}" for k, n in collections.Counter(reqs[i]["status"] for i in left).items())),
                                      s in rs and st["feeds"] and "Open milestones feeding it: " + ", ".join(sorted(st["feeds"], key=mnum))]))
        done = st["ids"] and st["met"] == len(st["ids"])
        o.append(node(s, "stage " + ("st-done" if done else "st-stage"), cut(f"{s} {st['title']}", 27),
                      f"{st['met']} of {len(st['ids'])} exit IDs met", tip, bar(*pos[s], c, len(st["ids"]))))
    o.append("</svg>")
    return "".join(o)


def gantt(M):
    now = M["now"]
    by_lane = collections.defaultdict(list)
    for m in M["ms"].values():
        if m["lane"] in M["lanes"]:
            by_lane[m["lane"]].append(m["id"])
    rows = [(L, by_lane[L["lane"]]) for L in M["lanes"].values() if any(L["t"][1:])]
    rows.sort(key=lambda r: min(x for x in r[0]["t"][1:] if x))
    if not rows:
        return '<p class="empty">No lane has a dated contract, prereg or run yet.</p>'
    t0 = min(min(x for x in L["t"][1:] if x) for L, _ in rows)
    W, LBL, R, RH, T = 1120, 150, 70, 17, 22
    H = T + len(rows) * RH + 8
    x = lambda t: LBL + (W - LBL - R) * (t - t0) / max(now - t0, 1)
    o = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Lane timelines">']
    d = day_of(t0)
    while d <= day_of(now):
        ts = dt.datetime.combine(d, dt.time()).timestamp()
        if ts >= t0 and (d.toordinal() % 3 == 0):
            o.append(f'<line class="grid" x1="{x(ts):.1f}" x2="{x(ts):.1f}" y1="{T - 4}" y2="{H - 4}"/>'
                     f'<text class="tick" x="{x(ts):.1f}" y="12" text-anchor="middle">{d.month}-{d.day:02d}</text>')
        d += dt.timedelta(days=1)
    cols = {1: "--s1", 2: "--s2", 3: "--s3"}
    for i, (L, mids) in enumerate(rows):
        y = T + i * RH
        marks = [(k, L["t"][k]) for k in range(1, 5) if L["t"][k]]
        done = L["stage"] == 4
        label = "/".join(sorted(mids, key=mnum)) + " " + L["lane"]
        span = lambda a, b: f"{(b - a) / DAY:.1f} d" if b - a >= DAY else f"{(b - a) / 3600:.1f} h"
        parts = []
        segs = []
        for j, (k, t) in enumerate(marks):
            end = marks[j + 1][1] if j + 1 < len(marks) else (None if done else now)
            if k == 4 or end is None:
                continue
            parts.append(f"{STAGES[k]}: {span(t, end)}" + ("" if j + 1 < len(marks) else " so far"))
            segs.append(f'<rect x="{x(t):.1f}" y="{y + 3}" width="{max(x(end) - x(t) - 1, 2):.1f}" height="{RH - 7}" rx="2" style="fill:var({cols[k]})"/>')
        tip = f"{label}\n" + "\n".join(parts) + (f"\nFirst PASS {dt.datetime.fromtimestamp(L['t'][4]):%m-%d %H:%M}" if L["t"][4] else "\nNo PASS yet")
        end_x = x(L["t"][4]) if L["t"][4] else x(now)
        o.append(f'<g data-tip="{esc(tip)}"><rect class="hit" x="0" y="{y}" width="{W}" height="{RH}"/>'
                 f'<text class="rowl" x="{LBL - 8}" y="{y + RH - 5}" text-anchor="end">{esc(label)}</text>{"".join(segs)}'
                 + (f'<circle cx="{end_x:.1f}" cy="{y + RH / 2 - 0.5:.1f}" r="4" class="pass"/>' if L["t"][4] else
                    f'<text class="lbl" x="{end_x + 6:.1f}" y="{y + RH - 5}">{(now - min(t for _, t in marks)) / DAY:.0f} d open</text>')
                 + "</g>")
    o.append("</svg>")
    return legend(["Contract, to the prereg", "Build and dev runs, to the first counted run", "Counted runs, to the first PASS", "First PASS (dot)"],
                  ["--s1", "--s2", "--s3", "--good"]) + "".join(o)


def board(M):
    now = M["now"]
    cols = []
    for k, name in enumerate(STAGES):
        mine = [m for m in M["ms"].values() if m["stage"] == k]
        if k == 4:
            recent = sorted([m for m in mine if m["lane"] in M["lanes"] and M["lanes"][m["lane"]]["t"][4]],
                            key=lambda m: -M["lanes"][m["lane"]]["t"][4])[:6]
            cards = "".join(f'<div class="card st-done"><b>{esc(m["id"])}</b> {esc(cut(m["title"], 30))}'
                            f'<small>first PASS {dt.datetime.fromtimestamp(M["lanes"][m["lane"]]["t"][4]):%m-%d}</small></div>' for m in recent)
            cards += f'<div class="more">and {len(mine) - len(recent)} earlier</div>' if len(mine) > len(recent) else ""
        else:
            order = {"work": 0, "queued": 1, "ready": 2, "user": 3, "waits": 4}
            cards = ""
            for m in sorted(mine, key=lambda m: (order.get(m["state"], 9), mnum(m["id"]))):
                bits = [STATE_LABEL[m["state"]] + (" " + ", ".join(m["gates"]) if m["gates"] else "")]
                if m["since"]:
                    bits.append(f"{(now - m['since']) / DAY:.1f} d here")
                if m["lane"]:
                    L = M["lanes"].get(m["lane"])
                    bits.append(m["lane"] + (f" {L['newest'][0]}" if L and L["newest"] else ""))
                if m["crew"]:
                    bits.append("crew " + ", ".join(m["crew"]))
                if m["fails_open"]:
                    bits.append(f"{m['fails_open']} failures open")
                cards += (f'<div class="card st-{m["state"]}"><b>{esc(m["id"])}</b> {esc(cut(m["title"], 30))}'
                          f'<small>{esc(" · ".join(bits))}</small><small>{len(m["left"])} {esc(TOP)} left</small></div>')
        cols.append(f'<div class="bcol"><h4>{esc(name)} <span>{len(mine)}</span></h4>{cards or "<div class=more>none</div>"}</div>')
    return '<div class="board">' + "".join(cols) + "</div>"


def table(M):
    now = M["now"]
    rows = []
    order = {"work": 0, "queued": 1, "ready": 2, "user": 3, "waits": 4}
    for m in sorted(M["open_ms"].values(), key=lambda m: (order.get(m["state"], 9), -len(m["left"]), mnum(m["id"]))):
        rows.append("<tr>" + "".join(f"<td>{c}</td>" for c in [
            f'<b>{esc(m["id"])}</b> {esc(m["title"])}', f'<span class="chip st-{m["state"]}">{esc(STATE_LABEL[m["state"]])}</span>',
            esc(STAGES[m["stage"]]) + (f' ({(now - m["since"]) / DAY:.1f} d)' if m["since"] else ""), esc(m["lane"] or "—"),
            str(len(m["left"])), esc(", ".join(m["gates"] + [f"{d} (only {', '.join(ids)})" for d, ids in m["pgates"].items()]) or "—"),
            esc(", ".join(f"{d}{'' if M['ms'][d]['done'] else ' (open)'}" for d in m["deps"]) or "—"),
            esc(", ".join(m["crew"]) or "—"), str(m["fails_open"] or "—")]) + "</tr>")
    return (f'<table><thead><tr><th>Milestone</th><th>State</th><th>Pipeline</th><th>Lane</th><th>{esc(TOP)} left</th><th>Open decisions</th>'
            '<th>After</th><th>Crew now</th><th>Failures open</th></tr></thead><tbody>' + "".join(rows) + "</tbody></table>")


CSS = """
:root{color-scheme:light;--page:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;--grid:#e1e0d9;--axis:#c3c2b7;
--border:rgba(11,11,11,.10);--s1:#2a78d6;--s1l:#86b6ef;--s2:#eb6834;--s3:#1baf7a;--s4:#eda100;--s5:#e87ba4;--s7:#6250d6;
--good:#0ca30c;--warn:#fab219;--serious:#ec835a;--crit:#d03b3b;--open:#c3c2b7;--tipbg:#0b0b0b;--tipink:#fcfcfb}
@media (prefers-color-scheme:dark){:root{color-scheme:dark;--page:#0d0d0d;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--grid:#2c2c2a;
--axis:#383835;--border:rgba(255,255,255,.10);--s1:#3987e5;--s1l:#1c5cab;--s2:#d95926;--s3:#199e70;--s4:#c98500;--s5:#d55181;--s7:#9085e9;
--open:#52514e;--tipbg:#f0efec;--tipink:#0b0b0b}}
*{box-sizing:border-box}body{margin:0;background:var(--page);color:var(--ink);font:14px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1340px;margin:0 auto;padding:20px 16px 60px}h1{font-size:22px;margin:0 0 2px}h2{font-size:16px;margin:30px 0 4px}
h3{font-size:13px;margin:0 0 6px}.sub{color:var(--ink2);margin:0 0 10px;max-width:90ch}.stamp{color:var(--muted);font-size:12px}
.panel{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:12px 14px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(138px,1fr));gap:8px;margin:14px 0}
.tile{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:10px 12px}
.tile b{display:block;font-size:22px;font-weight:600}.tile span{font-size:12px;color:var(--ink2)}.tile small{display:block;color:var(--muted);font-size:11px}
.find{display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:8px}
.f{background:var(--surface);border:1px solid var(--border);border-left:4px solid var(--axis);border-radius:8px;padding:8px 12px}
.f b{display:block;font-size:13px}.f p{margin:2px 0 0;color:var(--ink2);font-size:13px}.f i{font-style:normal;font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
.f.act{border-left-color:var(--s7)}.f.user{border-left-color:var(--warn)}.f.watch{border-left-color:var(--serious)}
.scroll{overflow-x:auto}svg{display:block;max-width:100%;height:auto}#road{width:100%;min-width:1040px}
.grid{stroke:var(--grid);stroke-width:1}.axis{stroke:var(--axis);stroke-width:1}.tick{fill:var(--muted);font-size:10px}
.lbl{fill:var(--ink2);font-size:10.5px}.rowl{fill:var(--ink2);font-size:10.5px}.colh{fill:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.05em}
.hit{fill:transparent}g[data-tip]:hover .hit,.hit.col:hover{fill:var(--border)}.ln{fill:none;stroke-width:2;stroke-linejoin:round}
.dot{stroke:var(--surface);stroke-width:2}.pass{fill:var(--good);stroke:var(--surface);stroke-width:2}
.e{fill:none;stroke:var(--axis);stroke-width:1.2}.e.dep{stroke:var(--ink2);stroke-width:1.6}.e.gate{stroke:var(--warn);stroke-width:1.6;stroke-dasharray:5 4}.e.pgate{stroke-width:1;stroke-dasharray:2 4}
.e.feed{opacity:.75}.arh{fill:var(--ink2)}
.n{cursor:pointer;outline:none}.n .box{fill:var(--surface);stroke:var(--border);stroke-width:1}.n .t1{font-size:11.5px;font-weight:600;fill:var(--ink)}
.n .t2{font-size:10.5px;fill:var(--ink2)}.n:focus .box,.n.hl .box{stroke:var(--ink);stroke-width:1.5}
.st-done .band{fill:var(--good)}.st-work .band{fill:var(--s1)}.st-queued .band{fill:var(--s1l)}.st-ready .band{fill:var(--s7)}
.st-user .band{fill:var(--warn)}.st-waits .band{fill:var(--open)}.st-stage .band{fill:var(--ink2)}
#road.dim .n:not(.hl),#road.dim .e:not(.hl){opacity:.13}#road .e.hl{opacity:1;stroke-width:2.2}
.legend{display:flex;flex-wrap:wrap;gap:4px 14px;font-size:12px;color:var(--ink2);margin:2px 0 6px}
.legend i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px;vertical-align:-1px}
.legend i.dash{height:0;border-top:2px dashed var(--warn);border-radius:0;width:16px;vertical-align:3px;background:none!important}
.charts{display:grid;grid-template-columns:repeat(auto-fit,minmax(380px,1fr));gap:10px}
.board{display:grid;grid-template-columns:repeat(5,minmax(170px,1fr));gap:8px;min-width:900px}
.bcol{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:8px}
.bcol h4{margin:0 0 6px;font-size:12px;color:var(--ink2);display:flex;justify-content:space-between}.bcol h4 span{color:var(--ink);font-weight:600}
.card{border:1px solid var(--border);border-left:4px solid var(--open);border-radius:6px;padding:5px 8px;margin-bottom:5px;font-size:12px}
.card small{display:block;color:var(--ink2);font-size:11px}.more{color:var(--muted);font-size:12px;padding:2px 4px}
.card.st-done{border-left-color:var(--good)}.card.st-work{border-left-color:var(--s1)}.card.st-queued{border-left-color:var(--s1l)}
.card.st-ready{border-left-color:var(--s7)}.card.st-user{border-left-color:var(--warn)}
table{border-collapse:collapse;width:100%;font-size:12.5px}th,td{text-align:left;padding:5px 8px;border-bottom:1px solid var(--grid);vertical-align:top}
th{color:var(--ink2);font-weight:600;white-space:nowrap}
.chip{display:inline-block;border-left:4px solid var(--open);padding:0 6px;white-space:nowrap}
.chip.st-work{border-color:var(--s1)}.chip.st-queued{border-color:var(--s1l)}.chip.st-ready{border-color:var(--s7)}.chip.st-user{border-color:var(--warn)}
.empty{color:var(--muted)}#tip{position:fixed;z-index:9;pointer-events:none;background:var(--tipbg);color:var(--tipink);padding:7px 10px;border-radius:6px;
font-size:12px;line-height:1.4;max-width:440px;white-space:pre-line;display:none;box-shadow:0 4px 14px rgba(0,0,0,.25)}
details{margin-top:8px}summary{cursor:pointer;color:var(--ink2)}
"""

JS = """
const tip=document.getElementById('tip');
document.addEventListener('mousemove',e=>{const t=e.target.closest('[data-tip]');if(!t){tip.style.display='none';return}
tip.textContent=t.dataset.tip;tip.style.display='block';const r=tip.getBoundingClientRect();
let x=e.clientX+14,y=e.clientY+14;if(x+r.width>innerWidth-8)x=e.clientX-r.width-14;if(y+r.height>innerHeight-8)y=Math.max(8,e.clientY-r.height-14);
tip.style.left=Math.max(8,x)+'px';tip.style.top=y+'px'});
const road=document.getElementById('road');let pin=null;
function light(id){road.querySelectorAll('.hl').forEach(n=>n.classList.remove('hl'));if(!id){road.classList.remove('dim');return}
road.classList.add('dim');const near=new Set([id]);road.querySelectorAll('.e').forEach(e=>{if(e.dataset.a===id||e.dataset.b===id){e.classList.add('hl');
near.add(e.dataset.a);near.add(e.dataset.b)}});road.querySelectorAll('.n').forEach(n=>{if(near.has(n.dataset.id))n.classList.add('hl')})}
if(road){road.querySelectorAll('.n').forEach(n=>{n.addEventListener('mouseenter',()=>{if(!pin)light(n.dataset.id)});
n.addEventListener('mouseleave',()=>{if(!pin)light(null)});n.addEventListener('focus',()=>{if(!pin)light(n.dataset.id)});
n.addEventListener('click',e=>{e.stopPropagation();pin=pin===n.dataset.id?null:n.dataset.id;light(pin)})});
road.addEventListener('click',()=>{pin=null;light(null)})}
"""


def graph_data(M):
    ctx = {"MET": MET, "STAGES": STAGES, "STATE_LABEL": STATE_LABEL, "STAGE_ORDER": M["order"], "mnum": mnum,
           "TOP": TOP, "GOAL": GOAL, "LATE": LATE, "MS": MS, "BLOCK": flow_graph.BLOCK, "ROADMAP": ROADMAP}
    guess = flow_graph.seed_from(M)[1] if M["graph"] is None else []
    return flow_page.graph_data(M, ctx, M["graph"]["edges"] if M["graph"] is not None else None, guess)


def render(M, F, finds):
    now = dt.datetime.fromtimestamp(M["now"])
    head = git(M["root"], "rev-parse", "--short", "HEAD").strip() or "an unknown commit (git gave nothing)"
    branch = git(M["root"], "rev-parse", "--abbrev-ref", "HEAD").strip() or "the checkout"
    kind_label = {"act": "act", "user": "the user", "watch": "watch", "info": "note"}
    fl = sorted(F["fail_lane"].items(), key=lambda kv: -(kv[1]["open"] + kv[1]["planned"]))[:12]
    fail_rows = "".join(f"<tr><td>{esc(k)}</td><td>{c['open']}</td><td>{c['planned']}</td><td>{c['fixed']}</td><td>{c['dropped']}</td></tr>" for k, c in fl)
    parts = [
        f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{esc(P.project)} workflow</title><style>{CSS}{flow_page.CSS}</style></head><body><main>',
        f'<h1>{esc(P.project)} workflow: the road to {esc(GOAL)}</h1>',
        f'<p class="stamp">Built {now:%a %Y-%m-%d %H:%M} from {esc(branch)} at {esc(head)} by flow.py. Read from {esc(rel("roadmap"))}, '
        f'{esc(rel("state"))}, {esc(rel("gym", "series"))}, git and the crew office ({esc(rel("office"))}); nothing on this page is typed by hand.</p>',
        '<div class="tiles">' + "".join(f'<div class="tile"><span>{esc(a)}</span><b>{esc(b)}</b><small>{esc(c)}</small></div>' for a, b, c in tiles(M, F)) + "</div>",
        '<h2>What to look at</h2><p class="sub">Computed from the graphs below, most actionable first.</p><div class="find">'
        + "".join(f'<div class="f {f["kind"]}"><i>{kind_label[f["kind"]]}</i><b>{esc(f["head"])}</b><p>{esc(f["text"])}</p></div>' for f in finds) + "</div>",
        f'<h2>Road graph: what stands between today and {esc(GOAL)}</h2>'
        '<p class="sub">Every milestone not yet done, placed after the milestones it waits on, with the open decisions that gate it on the left '
        'and the stages it feeds on the right. Each box is a typed node with named pins; a link runs from an out pin to an in pin. '
        f'The thin bar is its {esc(TOP)} requirements by status; the word in a header is the newest counted verdict of its lane.</p>',
        '<div class="legend">' + "".join(f'<span><i style="background:var({c})"></i>{esc(n)}</span>' for n, c in [
            ("in work", "--s1"), ("in this push", "--s1l"), ("ready to start", "--s7"), ("needs the user", "--warn"),
            ("waits on a milestone", "--open"), (f"{TOP} met", "--good")])
        + '<span><i class="dash"></i>decision gate</span><span><i style="background:var(--ink2);height:2px;vertical-align:3px;width:16px"></i>must come first</span></div>',
        flow_page.canvas_html(graph_data(M), road_graph(M)),
        '<h2>Pipeline: where each milestone stands</h2>'
        '<p class="sub">Every milestone moves through the same five steps. A step is reached when its evidence exists: the lane\'s contract, '
        'the grader\'s prereg, a counted run in the gym\'s series, a PASS.</p>',
        f'<div class="scroll">{board(M)}</div>',
        '<h2>Lane timelines: where the time went</h2>'
        '<p class="sub">One row per lane, from its contract to its first PASS. Long orange is build time; long green is a lane that ran counted without passing.</p>',
        f'<div class="panel">{gantt(M)}</div>',
        '<h2>Flow over time</h2><div class="charts">',
        f'<div class="panel"><h3>Lanes that reached each step (cumulative)</h3>{lines(F["cfd_days"], F["cfd"], ["--s1", "--s2", "--s3", "--good"], "lanes")}</div>',
        f'<div class="panel"><h3>{esc(TOP)} requirements by status</h3>{stacked(F["burn_days"], F["burn"], ["--good", "--s1", "--s1l", "--open"], TOP)}</div>',
        f'<div class="panel"><h3>Counted runs per day, by verdict</h3>{stacked(F["days"], F["runs"], ["--good", "--warn", "--crit", "--open"], "runs")}</div>',
        f'<div class="panel"><h3>Reviews per day, by verdict</h3>{stacked(F["days"], F["reviews"], ["--good", "--warn", "--crit"], "reviews")}</div>',
        f'<div class="panel"><h3>Badge hours on the clock per day, by role</h3>{stacked(F["days"], F["hours"], ["--s1", "--s2", "--s3", "--s4", "--s5"], "hours", "{:.1f}")}</div>',
        f'<div class="panel"><h3>Failures filed per day, by where they stand now</h3>{stacked(F["days"], F["filed"], ["--good", "--s1l", "--crit", "--open"], "failures")}</div>',
        '</div>',
        '<h2>Open milestones</h2><div class="panel scroll">' + table(M) + '</div>',
        '<details><summary>Failure backlog by lane</summary><div class="panel scroll"><table><thead><tr><th>Lane</th><th>Open</th><th>Planned</th><th>Fixed</th>'
        f'<th>Dropped</th></tr></thead><tbody>{fail_rows}</tbody></table></div></details>',
        f'<div id="tip"></div><script>{JS}</script><script>{flow_page.JS}</script></main></body></html>']
    return "".join(parts)


# ---------------------------------------------------------------- commands

FIXTURE = """
| **R0 Starts** | it starts | APP-01, 02 | M1 | x |
| **1.0** | the goal | every P0 PASS | none | x |

- **M1 start (lane G1):** done. → APP-01, 02; the base for DATA-01.

**Lanes** (each milestone's gym lane): M1 G1, M2 G2, M3 none yet.

| M1 | Start | APP-01–02 | First |
| M2 | Data | DATA-01 (the store) | Needs M1 and D2 |
| M3 | Ship | DATA-02 | Last. After M2 |

| APP-01 | P0 | PASS | M1 | n |
| APP-02 | P0 | Part | M1 | n |
| DATA-01 | P0→P1* | Planned | M2 | n |
| DATA-02 | P0 | Open | M3 | n |

| **P0** | 1 | 1 | 0 | 0 | 1 | 3 |
| **P1** | 0 | 0 | 1 | 0 | 0 | 1 |

| D1 | One | **Decided:** yes | the user | M1 |
| D2 | Two | Open: which store | the user | M2 (DATA-01); R0's exit |
"""


def logic_checks():
    """The checks that need no project: the ID lists, a small roadmap, and a build for a project that has nothing
    yet. Returns the lines that failed. It writes nothing outside a temp folder."""
    import tempfile
    bad = []

    def check(name, cond, got=None):
        if not cond:
            bad.append(f"logic: {name}" + (f" (got {got!r})" if got is not None else ""))

    if all(P.get(f"roadmap.{k}") == fp.DEFAULTS["roadmap"][k] for k in ("requirement_id", "tiers", "stage_id", "milestone_id", "decision_id")) \
            and "1.0" in LATE and re.fullmatch(LANE, "G1"):
        check("a short list", ids_in("SHELL-01, 03, 04, 06; GFX-05") == ["SHELL-01", "SHELL-03", "SHELL-04", "SHELL-06", "GFX-05"])
        check("a run and a remark", ids_in("SET-01–03, SEC-01 (rest); also FS-02") == ["SET-01", "SET-02", "SET-03", "SEC-01", "FS-02"])
        check("a date is not an ID", ids_in("FS-02 (2026-01-05); 2026-01-05") == ["FS-02"], ids_in("FS-02 (2026-01-05); 2026-01-05"))
        check("a bullet's closing remark", id_segments(" BUNDLE-01, GFX-01 (more), SEC-07; the foundation for APP-01 and GFX-02.") == ["BUNDLE-01", "GFX-01", "SEC-07"])
        check("a bullet's short list", id_segments(" SHELL-01, 03; GFX-05.") == ["SHELL-01", "SHELL-03", "GFX-05"])
        reqs, stages, ms, lanes, decisions, warns = parse_roadmap(FIXTURE)
        check("requirement rows", {k: (q["p"], q["status"]) for k, q in reqs.items()} == {
            "APP-01": ("P0", "PASS"), "APP-02": ("P0", "Part"), "DATA-01": ("P1", "Planned"), "DATA-02": ("P0", "Open")}, reqs)
        check("stage rows", stage_order(stages) == ["R0", "1.0"] and stages["R0"]["ids"] == ["APP-01", "APP-02"]
              and stages["1.0"]["ids"] == ["APP-01", "APP-02", "DATA-02"], stages)
        check("milestone rows", ms["M1"]["closes"] == ["APP-01", "APP-02"] and ms["M2"]["deps"] == ["M1"] and ms["M2"]["dgates"] == ["D2"]
              and ms["M3"]["last"] and ms["M3"]["deps"] == ["M2"], ms)
        check("lanes", lanes == {"M1": "G1", "M2": "G2"}, lanes)
        check("decisions", decisions["D1"]["state"] == "decided" and decisions["D2"]["state"] == "open"
              and decisions["D2"]["targets"] == {"M2": ["DATA-01"], "R0": None}, decisions)
        check("the Count table agrees", warns == [], warns)
        check("a wrong Count is told", any("Count table" in w for w in parse_roadmap(FIXTURE.replace("| 1 | 1 | 0 | 0 | 1 | 3 |", "| 2 | 1 | 0 | 0 | 1 | 4 |"))[5]))
        check("an unknown status word is told", any("did not parse" in w for w in parse_roadmap(FIXTURE.replace("| Open | M3 |", "| Later | M3 |"))[5]))
        # a pipe inside a cell, escaped: the row keeps its five cells, each with its own text
        piped = parse_roadmap(FIXTURE.replace("| D2 | Two | Open: which store |", "| D2 | Two \\| or three | Open: a \\| b |"))
        d2 = piped[4].get("D2", {})
        check("a decision row with an escaped pipe parses, cell by cell", piped[5] == [] and d2.get("what") == "Two | or three"
              and d2.get("stands") == "Open: a | b" and d2.get("owner") == "the user" and d2.get("targets") == {"M2": ["DATA-01"], "R0": None}, (d2, piped[5]))
        piped = parse_roadmap(FIXTURE.replace("| M2 | Data |", "| M2 | Data \\| more |"))
        check("a milestone row with an escaped pipe parses", piped[5] == [] and piped[2]["M2"]["theme"] == "Data | more"
              and piped[2]["M2"]["deps"] == ["M1"], (piped[2].get("M2"), piped[5]))
        # a row that starts like one and does not parse is a problem that names its line
        n2 = FIXTURE.split("\n").index("| D2 | Two | Open: which store | the user | M2 (DATA-01); R0's exit |") + 1
        for what, text in (("a decision row with a cell missing", FIXTURE.replace("| D2 | Two | Open: which store | the user |", "| D2 | Two | Open: which store |")),
                           ("a decision row with no closing pipe", FIXTURE.replace("R0's exit |", "R0's exit")),
                           ("a decision row with a pipe that is not escaped", FIXTURE.replace("| D2 | Two |", "| D2 | Two | or three | x | y |"))):
            got = parse_roadmap(text)
            told = [w for w in got[5] if f"line {n2}:" in w and "decision row" in w]
            check(f"{what} is told with its line" if "not escaped" not in what else f"{what} is read as the cells it makes (nothing can tell)",
                  bool(told) if "not escaped" not in what else got[4]["D2"]["what"] == "Two", got[5])
        n3 = FIXTURE.split("\n").index("| M3 | Ship | DATA-02 | Last. After M2 |") + 1
        got = parse_roadmap(FIXTURE.replace("| M3 | Ship | DATA-02 | Last. After M2 |", "| M3 | Ship | DATA-02 |"))
        check("a milestone row with a cell missing is told with its line", any(f"line {n3}:" in w and "milestone row" in w for w in got[5])
              and "M3" not in got[2], got[5])
        # the same id in two rows
        got = parse_roadmap(FIXTURE.replace("| D2 | Two |", "| D1 | Again | Open: no | the user | M2 |\n| D2 | Two |"))
        check("a decision id in two rows is told, and the first row stands",
              any("decision D1 already has a row" in w for w in got[5]) and got[4]["D1"]["state"] == "decided", got[5])
        got = parse_roadmap(FIXTURE.replace("| M3 | Ship |", "| M1 | Again | DATA-02 | Later |\n| M3 | Ship |"))
        check("a milestone id in two rows is told, and the first row stands",
              any("milestone M1 already has a row" in w for w in got[5]) and got[2]["M1"]["theme"] == "Start", got[5])
    else:
        print("NOTE the profile names its own roadmap shapes, so the fixture checks (written in the default shapes) were skipped")
    with tempfile.TemporaryDirectory(prefix="foundry-flow-selftest-") as td:
        empty = Path(td) / "empty"
        empty.mkdir()
        try:
            M = build_model(empty, dt.datetime.now().timestamp())
            F = flow_numbers(M)
            finds = findings(M, F)
            page = render(M, F, finds)
            json.dumps(brief(M, F, finds))
            check("an empty project builds a page", 'id="gdata"' in page and "</html>" in page)
            first = finds[0] if finds else {}
            check("an empty project's missing inputs are a finding", first.get("head", "").startswith("Input not read")
                  and all(w in first.get("text", "") for w in (ROADMAP, "state.json", "roster.json", "timeclock.jsonl", "series")), first)
            check("an empty project reads no graph and says so", M["graph"] is None and M["graph_ok"])
        except Exception as e:  # a traceback here is the failure this case is for
            check(f"an empty project builds without an error ({type(e).__name__}: {e})", False)
    return bad


def brief(M, F, finds):
    return {"built": dt.datetime.fromtimestamp(M["now"]).astimezone().isoformat(timespec="minutes"),
            "tiles": {a: b for a, b, _ in tiles(M, F)},
            "findings": finds,
            "milestones": {m["id"]: {"state": m["state"], "pipeline": STAGES[m["stage"]], "lane": m["lane"], "p0_left": len(m["left"]),
                                     "gates": m["gates"], "part_gates": m["pgates"], "after_open": [d for d in m["deps"] if d in M["open_ms"]], "crew": m["crew"]}
                           for m in sorted(M["open_ms"].values(), key=lambda m: mnum(m["id"]))},
            "decisions": {d["id"]: {"state": d["state"], "gates": d["full"] + d["stages"], "part_gates": d["partial"],
                                    "p0_behind": len(d["p0"])} for d in M["open_dec"].values()},
            "warnings": M["warns"] + NOT_READ + shape_notes() + M["graph_bad"],
            "graph_ok": M["graph_ok"], "graph_head": (M["graph"] or {}).get("head"), "graph_notes": M["graph_notes"]}


def main(argv):
    if "graph" in argv and not any(a in ("build", "brief", "edges", "selftest") for a in argv[:argv.index("graph")]):
        i = argv.index("graph")
        root = main_root()
        for a in argv[:i]:
            if a.startswith("--root="):
                root = Path(a.split("=", 1)[1]).resolve()
        return flow_graph.main(argv[i + 1:], root, lambda: build_model(root, dt.datetime.now().timestamp()))
    args = [a for a in argv if not a.startswith("--")]
    opts = [a for a in argv if a.startswith("--")]
    cmd = args[0] if args else "build"
    if cmd == "selftest" and opts == ["--logic"] and len(args) == 1:
        bad = logic_checks()
        for b in bad:
            print("FAIL", b)
        print(f"flow selftest (the tool's own checks, no project read): {len(bad)} problems")
        return 1 if bad else 0
    if len(args) > 1 or cmd not in ("build", "brief", "edges", "selftest") or any(not o.startswith(("--root=", "--out=")) for o in opts):
        print(__doc__)
        return 0 if "--help" in opts and not args else 2
    root = main_root()
    out_dir = None
    for a in opts:
        if a.startswith("--out="):  # a branch's build goes beside the branch, not over the main checkout's page
            out_dir = Path(a.split("=", 1)[1]).resolve()
        else:
            root = Path(a.split("=", 1)[1]).resolve()
    now = dt.datetime.now().timestamp()
    logic = logic_checks() if cmd == "selftest" else []
    M = build_model(root, now)
    if cmd == "edges":
        for m in sorted(M["ms"].values(), key=lambda m: mnum(m["id"])):
            if not m["done"]:
                gates = m["gates"] + [f"{d}({'+'.join(ids)})" for d, ids in m["pgates"].items()]
                print(f"{m['id']:5} {STATE_LABEL[m['state']]:22} lane {m['lane'] or '-':5} after {','.join(m['deps']) or '-':12} "
                      f"gates {','.join(gates) or '-':10} holds {','.join(m['ids'])}")
        for d in M["decisions"].values():
            to = d["full"] + [f"{k}({'+'.join(v)})" for k, v in d["partial"].items()] + \
                 [f"{k}({'+'.join(v)})" if v else k for k, v in d["stage_ids"].items()]
            print(f"{d['id']:4} {d['state']:8} -> {','.join(to) or '-'}")
        for s in M["stages"].values():
            print(f"{s['id']:5} {s['met']}/{len(s['ids'])} <- {','.join(sorted(s['feeds'], key=mnum)) or '-'}")
        for w in M["warns"] + NOT_READ + M["graph_bad"]:
            print("WARN", w)
        for w in M["graph_notes"]:
            print("NOTE", w)
        print("GRAPH", "; ".join(M["graph_lines"]))
        return 0
    if cmd == "selftest":
        bad = logic + list(M["warns"]) + [x for x in NOT_READ if x not in ABSENT] + shape_notes() + M["graph_bad"]
        for w in M["graph_notes"] + ABSENT:
            print("NOTE", w)
        bad += [f"stage {s} missing from {ROADMAP}" for s in LATE if s not in M["stages"]]
        bad += [f"no numbered stage row parsed from {ROADMAP}"] if not any(s not in LATE for s in M["stages"]) else []
        bad += [f"stage {s['id']} has no exit IDs" for s in M["stages"].values() if not s["ids"]]
        bad += ["no requirement rows parsed"] if not M["reqs"] else []
        bad += ["no decisions parsed"] if not M["decisions"] else []
        bad += ["no milestone table rows parsed"] if not any(r["theme"] or r["why"] for r in M["roadmap_ms"].values()) else []
        for b in bad:
            print("FAIL", b)
        print(f"flow selftest: {len(M['reqs'])} requirements, {len(M['ms'])} milestones, {len(M['decisions'])} decisions, "
              f"{len(M['stages'])} stages, {len(bad)} problems")
        return 1 if bad else 0
    F = flow_numbers(M)
    finds = findings(M, F)
    if cmd == "brief":
        print(json.dumps(brief(M, F, finds), indent=1, ensure_ascii=False))
        return 0
    out = out_dir or at(root, "flow_out")
    out.mkdir(parents=True, exist_ok=True)
    (out / "workflow.html").write_text(render(M, F, finds), encoding="utf-8")
    (out / "brief.json").write_text(json.dumps(brief(M, F, finds), indent=1, ensure_ascii=False), encoding="utf-8")
    (out / "graph.json").write_text(json.dumps(graph_data(M), indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {out / 'workflow.html'}")
    for a, b, _ in tiles(M, F):
        print(f"  {a}: {b}")
    for f in finds:
        print(f"- [{f['kind']}] {f['head']}: {f['text']}")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main(sys.argv[1:]))
