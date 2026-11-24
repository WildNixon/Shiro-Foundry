#!/usr/bin/env python3
"""Shiro Foundry progress map: where the project is, kept by hand and checked against the gym.

    python board.py          build the map (paths.map) from the state (paths.state) and the gym's series
    python board.py init     write a starter state.json when none exists (refuses to overwrite), then build
    python board.py check    build, then print the shift-start summary and every warning
                             (check --no-build writes nothing: the form an employee uses)
    python board.py open     build, then open the map in the browser
    python board.py promote  when every block of the shift is done or skipped: move queue[0] into
                             "shift" and its blockers into "blockers", write state.json, rebuild
    python board.py brief    one compact JSON for the manager skill (Now, the rota slot, the shift,
                             the next block, the crew, what needs attention, the last day's runs, the shared
                             resource's seats, usage, open checkpoints, failures and decisions, warnings);
                             writes nothing. Long texts are cut; `brief --full` prints everything whole;
                             `brief --keys crew,resource` only those keys. Warnings come first; exit 1 =
                             warnings present
    python board.py note --by MGR-1 "text"     add a note at the top of state.notes, rebuild
    python board.py fail --what "text" [--lane L --run-id R --verdict V --plan P --owner O --from R12,R13]
                             file the next F<nnn> in state.failures, rebuild
    python board.py rr --kind review --by "TMP-1 x" --topic "text" [--report P --commit C
                             --finding "a | b" --action "a | b"]   file the next RR<nnn>, rebuild
    python board.py usage 12 [--stop 80] [--reset 2030-01-07T01:00-06:00]
                             record the week's usage (percent) for the usage chart, rebuild
    python board.py block 3 done [--note "text"]   set block 3 of the current shift, rebuild
    python board.py decide ask --by FDR-1 --question "text" [--options "a | b"] [--recommend "a"]
                             [--needed-before M12] [--brief docs/decisions/D7-x.md]
                             file the next D<n> in state.decisions (a question only the user answers), rebuild
    python board.py decide answer D7 --words "the user's own words"    record the answer (empty words are refused)
    python board.py decide withdraw D7 --note "text"                   the question no longer needs an answer
    python board.py decide list [--open]       the register, newest first; writes nothing
    python board.py pending  the edits held while a counted run was in the resource queue; writes nothing
    python board.py stamp    the time now, as state.json writes it (use it instead of calling `date`
                             from a script, so every stamp has the same form and zone)
    python board.py selftest pure checks on made-up inputs (the tree check's record files, stale roadmap
                             run ids, a project with no state, gym or roadmap, init, the decisions register);
                             reads and writes nothing outside a temp folder

While a counted sweep or a single counted run holds or waits for the shared resource (a queue id <badge>-sweep,
or <badge>-counted[-<lane>]), nothing in the main checkout may change: a counted run samples the tree, and a
change under it, tracked or not, voids the run. So in the main checkout, during either: build and check print
but do not rewrite the map, init and promote are refused, and note, usage, block, fail, rr and decide are
checked, then held in the office's pending-state.jsonl and applied with their own times by the next writing
command run in the main checkout after the run (exit 0: held). A run in a worktree neither holds nor applies:
the held edits are the main checkout's. A counted run whose hold is past its own limit is probably dead (the
host restarted): edits are still held, but they exit 4 and say DEAD?, until the manager frees the lock with
rq.py force-release. A project with no shared resource (resource.name empty) has no queue, so nothing is held.

The hand-edited part is the state (Now, the shift plan, the queue of later shifts, blockers, the block log,
milestone and phase statuses, the rota, gym checkpoints, failures, notes, the research-and-review results each
rota slot's window produces, and the decisions that wait on the user).
Lane facts (verdict, n, run id, date) are read from the gym's series files and never typed in; the crew (who
is on the clock, their job, % and approximate finish) is read from the crew office (office.py); the road to
the goal (each requirement's status, the release stages) is read from the tables of the roadmap. The builder
warns when they disagree, so a stale map announces itself. A project with no gym folder, no roadmap or no
state yet still gets a map and a brief: each missing input is one line under Needs attention.
Every path, name and limit comes from the project profile (foundry_profile.py). Standard library only (the
badge plates are drawn by office.py); no network; only the state and the map are written.
"""

import contextlib
import datetime as dt
import hashlib
import html
import io
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import foundry_profile as fp  # noqa: E402

P = fp.load(__file__)

import office  # noqa: E402  the crew office (badges, the time clock), next to this script

TOP_ROLES = tuple(getattr(office, "TOP", ("MANAGER",)))  # the founder and the manager: outside the headcount
ROOT = P.root
# FOUNDRY_PATHS_STATE and FOUNDRY_PATHS_MAP move the two written files (the guard test's scratch copies)
STATE = P.local("state")
OUT = P.local("map")
SERIES = P.gym("series")
PREREG = P.gym("prereg")
CONTRACTS = P.gym("contracts")
CHARTS = P.gym("charts")
GRADES = P.gym("grades")
ROADMAP = P.local("roadmap")
GYM = P.local("gym")
# the same places as the project writes them, for messages, git pathspecs and the page's text
STATE_REL, MAP_REL, ROADMAP_REL, GYM_REL = P.rel("state"), P.rel("map"), P.rel("roadmap"), P.rel("gym").rstrip("/")
BOARD, OFFICE, RQ = P.tool("board.py"), P.tool("office.py"), P.tool("rq.py")  # command lines, as printed
PROJECT = P.project
GOAL = str(P.get("roadmap.goal") or "the goal")          # the road to <goal>
TIERS = tuple(P.get("roadmap.tiers") or ("P0", "P1", "P2"))
TOP = TIERS[0]                                            # the tier the goal is made of
RES = P.get("resource.name") or "the shared resource"    # the one thing the crew queues for
USAGE_STOP = P.get("limits.usage_stop", 80)
PHASES_TITLE = P.get("board.phases_title", "Phases")     # the heading over state.phases, when a project has them

STALE_AFTER_H = 36  # a state older than this at shift start gets a warning
# The map's own files: edited after the block's last commit, so they never count as "dirty",
# and a commit that touches only them may sit on top of the hash Now names.
MAP_FILES = {STATE_REL, MAP_REL}
# paths whose commits do not move Now's tree: reports and notes, and a counted run's records
RECORD_PREFIXES = tuple(str(p).replace("\\", "/").rstrip("/") + "/"
                        for p in [P.rel("reviews"), P.rel("research"), P.rel("handoff"),
                                  *(P.get("measure.records") or [])])
# a grader's or builder's notes beside a contract (<gym>/contracts/G7-grader-notes.md) are records too;
# the contract itself and its amendments are not
RECORD_NOTES = re.compile(rf"^{re.escape(GYM_REL)}/contracts/[^/]+-notes\.md$")


def is_record(path):
    """True for a file whose commit does not move Now's tree: the map's own files, reports, notes, run records."""
    return path in MAP_FILES or path.startswith(RECORD_PREFIXES) or bool(RECORD_NOTES.match(path))

# status word -> (css class, glyph, label); status colours never carry meaning alone
STATUS = {
    "done": ("s-done", "✓", "done"),
    "in-progress": ("s-now", "▶", "in progress"),
    "next": ("s-next", "▷", "next"),
    "queued": ("s-next", "▷", "queued"),
    "planned": ("s-plan", "○", "planned"),
    "blocked": ("s-bad", "✕", "blocked"),
    "paused": ("s-plan", "‖", "paused"),
    "pending": ("s-plan", "○", "pending"),
    "partial": ("s-warn", "◐", "partial"),
    "skipped": ("s-plan", "–", "skipped"),
    "open": ("s-warn", "!", "open"),        # failures: open, planned, fixed, dropped; decisions: open
    "fixed": ("s-done", "✓", "fixed"),
    "dropped": ("s-plan", "–", "dropped"),
    "answered": ("s-done", "✓", "answered"),    # decisions: open, answered, withdrawn
    "withdrawn": ("s-plan", "–", "withdrawn"),
    "review": ("s-next", "◎", "review"),    # research_review kinds
    "research": ("s-now", "◇", "research"),
}
VERDICT = {
    "PASS": ("s-done", "✓"),
    "MARGINAL": ("s-warn", "~"),
    "MEASURING": ("s-warn", "…"),
    "SATURATED": ("s-warn", "↑"),
    "STARVED": ("s-warn", "○"),
    "FAIL": ("s-bad", "✕"),
    "VOID": ("s-bad", "∅"),
}
# a badge's status word (office.py) -> (css class, glyph, label)
CREW = {
    "UP": ("s-done", "✓", "up"),
    "STALE": ("s-warn", "◐", "stale"),
    "OVERDUE": ("s-bad", "✕", "overdue"),
    "HIRED": ("s-next", "▷", "hired, not in"),
    "OUT": ("s-plan", "–", "out"),
    "REVOKED": ("s-plan", "–", "revoked"),
}
NOT_PASSING = ("FAIL", "VOID", "MARGINAL", "STARVED")  # a lane's latest run in one of these needs a failure entry
BLOCK_STATUSES = ("done", "partial", "skipped", "in-progress", "pending", "blocked", "paused")  # what `block` may set
# the edit commands' options: each command takes only its own, anything else is refused (and nothing written)
EDIT_OPTS = {"note": ("by",), "usage": ("stop", "reset"), "block": ("note",),
             "fail": ("what", "lane", "run-id", "verdict", "plan", "owner", "status", "from"),
             "rr": ("kind", "by", "topic", "report", "commit", "finding", "action", "slot", "date"),
             "decide": ("by", "question", "options", "recommend", "needed-before", "brief", "words", "note")}
EDITS = tuple(EDIT_OPTS)  # the state edits a command line makes, held during a counted run like note
FAIL_STATUSES = ("open", "planned", "fixed", "dropped")
DECISION_STATUSES = ("open", "answered", "withdrawn")
# rq.py's rules, copied (the map reads its files, never imports it): a waiter silent this long has left the
# queue, and one older than RQ_AGE ranks at prio 2
RQ_STALE, RQ_AGE, RQ_MAX = 120, 90 * 60, 1800
# The roadmap's tables (their shape comes from the profile's roadmap section): a requirement row is
# "| ID | P0 | Status | ..." (or "P0→P1*" where it proposes a change), a release stage row is
# "| **R0 Boots** | theme | exit IDs | ...", the IDs as "HW-01–06, FS-02, GFX-01 (basic)"
REQ_ID = P.get("roadmap.requirement_id") or r"[A-Z0-9]+-\d+"
STAGE_ID = P.get("roadmap.stage_id") or r"R\d"
_TIER = "|".join(re.escape(t) for t in TIERS)
REQ_STATUSES = ("PASS", "Part", "Planned", "Decided", "Open")
REQ_MET = ("PASS", "Decided")  # met: a lane passed it, or, for a decision, its record exists
REQ_ROW = re.compile(rf"^\| ((?:{REQ_ID})) \| ((?:{_TIER}))(?:→((?:{_TIER}))\*)? \| ({'|'.join(REQ_STATUSES)}) \|", re.M)
STAGE_ROW = re.compile(rf"^\| \*\*((?:{STAGE_ID})) ([^*]+)\*\* \| ([^|]*) \| ([^|]*) \|", re.M)
# a PASS row with its Where and note cells, for the stale-PASS check; a lane is named by measure.lane_pattern
PASS_ROW = re.compile(rf"^\| ((?:{REQ_ID})) \| ((?:{_TIER}))(?:→((?:{_TIER}))\*)? \| PASS \| ([^|\n]*) \|([^\n]*)$", re.M)
LANE_NAME = re.compile(P.get("measure.lane_pattern") or r"\bG\d+\b")


def lane_names(text):
    """Every lane name in a text, in order (whatever groups the profile's pattern has)."""
    return [m.group(0) for m in LANE_NAME.finditer(text)]


def esc(s):
    return html.escape(str(s if s is not None else ""), quote=True)


def chip(status):
    cls, glyph, label = STATUS.get(status, ("s-plan", "?", status))
    return f'<span class="chip {cls}"><span aria-hidden="true">{glyph}</span> {esc(label)}</span>'


def verdict_chip(verdict):
    if not verdict:
        return '<span class="chip s-plan"><span aria-hidden="true">○</span> no run</span>'
    cls, glyph = VERDICT.get(verdict, ("s-warn", "?"))
    return f'<span class="chip {cls}"><span aria-hidden="true">{glyph}</span> {esc(verdict)}</span>'


def lane_key(name):
    m = re.match(r"([A-Z]+)(\d*)([a-z]*)", name)
    return (m.group(1), int(m.group(2) or 0), m.group(3)) if m else (name, 0, "")


def git(*args):
    try:
        return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=20).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def git_facts():
    head = git("rev-parse", "--short", "HEAD") or "?"
    branch = git("rev-parse", "--abbrev-ref", "HEAD") or "?"
    # git() strips the output, so the first line may have lost its leading status column: split, don't slice
    dirty = [l for l in git("status", "--porcelain", "--untracked-files=no").splitlines()
             if l.strip() and l.split(maxsplit=1)[-1].strip('"') not in MAP_FILES]
    last = git("log", "-1", "--date=format:%Y-%m-%d %H:%M", "--format=%ad\t%s")
    last_date, _, last_subject = last.partition("\t")
    return {"head": head, "branch": branch, "dirty": dirty, "last_date": last_date, "last_subject": last_subject}


def local_dt(ts):
    return dt.datetime.fromtimestamp(ts).astimezone()


def parse_updated(s):
    d = dt.datetime.fromisoformat(s)
    return d if d.tzinfo else d.astimezone()


def parse_or_none(s):
    """parse_updated, or None for a missing or hand-mangled time."""
    try:
        return parse_updated(s) if isinstance(s, str) else None
    except ValueError:
        return None


def number(v):
    """A finite int or float from state.json, or None (a string, a bool, null, inf or nan is not a number here)."""
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) else None


def usage_points(usage):
    """The usage points that parse, as (epoch seconds, weekly percent, the point), and the indexes of those that do not:
    only the `usage` command writes points, but a hand edit must not break the build."""
    good, bad = [], []
    for i, p in enumerate((usage or {}).get("points") or []):
        when = parse_or_none(p.get("at")) if isinstance(p, dict) else None
        v = number(p.get("weekly")) if isinstance(p, dict) else None
        if when is None or v is None:
            bad.append(i)
        else:
            good.append((when.timestamp(), float(v), p))
    return good, bad


def counted_checkout():
    """True in the checkout a counted sweep counts and the held edits belong to: the main checkout. FOUNDRY_SWEEP_GUARD
    is the guard test's switch: 1 says yes, 0 says no, whatever the checkout. Never export it in a shell or set it
    in a session: 0 in the main checkout turns the guard off during a sweep, and 1 in a worktree takes main's held
    edits into that worktree's state.json. Only the guard test sets it, for its own child runs."""
    env = os.environ.get("FOUNDRY_SWEEP_GUARD")
    if env in ("0", "1"):
        return env == "1"
    return P.main.resolve() == ROOT.resolve()


def worktree_write_refusal(cmd, root, main, targets):
    """A linked worktree's board.py writes its own copies of the state and the map (ROOT is the script's checkout),
    and a later commit on that branch would carry an older map into main. So a writing command there (build, check,
    open, init, promote, note, fail, rr, usage, block, decide) is refused when it would write inside that worktree:
    only the crew office's checkout, the main one, writes the map. A target moved outside the worktree
    (FOUNDRY_PATHS_STATE, FOUNDRY_PATHS_MAP: a scratch copy) is not refused. The reason text, or None to go on."""
    root, main = Path(root).resolve(), Path(main).resolve()
    if root == main:
        return None
    inside = []
    for t in targets:
        try:
            inside.append(Path(t).resolve().relative_to(root).as_posix())
        except ValueError:
            continue
    if not inside:
        return None
    return (f"this is a linked worktree ({root.as_posix()}), not the main checkout ({main.as_posix()}): "
            f"board.py {cmd} would write {' and '.join(inside)} here, and a later commit could carry them. "
            "Only the main checkout's board.py writes the map. An employee reports with office.py progress or office.py fail "
            f"(the main checkout's: {OFFICE}, which writes only the crew office); here, board.py check --no-build "
            "reads and writes nothing")


def write_targets(cmd, state, out):
    """The files a writing command writes, for worktree_write_refusal: build, check and open render only the map
    (OUT; their apply_pending replays held edits into STATE only in the main checkout, never in a worktree), so a
    worktree run with FOUNDRY_PATHS_MAP on a scratch file is not refused. init, promote and the edit forms write
    state.json too. Only when not counted_checkout(): a worktree run with FOUNDRY_SWEEP_GUARD=1 (whose apply_pending
    would move the office's held edits into the worktree's state.json) still counts state.json and stays refused."""
    return (out,) if cmd in ("build", "check", "open") and not counted_checkout() else (state, out)


def has_resource():
    """True when the profile names a shared resource the crew queues for (resource.name)."""
    return P.has_resource()


def queue_facts():
    """The resource queue as the office reads it (office.vm_facts: holds and waiters), or None when the project has
    no shared resource or the office has no folder yet."""
    if not has_resource():
        return None
    d = office.office_dir()
    return office.vm_facts(d, office.now_ts()) if d.exists() else None


def sweep_hold():
    """The counted sweeps holding or waiting for the shared resource (office.sweeps_of's records), in the main
    checkout; [] anywhere else, and [] in a project with no shared resource (no queue, so nothing to wait out)."""
    try:
        if not counted_checkout():
            return []
        q = queue_facts()
        return office.sweeps_of(q, office.now_ts()) if q else []
    except Exception as e:
        # the guard never stops the map from being read, but a guard that could not look must say so
        print(f"board.py: the counted-sweep guard could not read the resource queue ({type(e).__name__}: {e}); "
              "writing as if no sweep is queued", file=sys.stderr)
        return []


def dev_hold():
    """The whole-resource jobs under a plain id that are dev runs by their text (office.dev_uncounted): named in one
    line, not flagged as maybe counted."""
    try:
        q = queue_facts()
        return office.dev_uncounted(q) if q else []
    except Exception:
        return []


def unmarked_hold():
    """Prio-0 or whole-resource jobs under a plain id (office.unmarked_counted), maybe a counted run the guard cannot
    see. Read in any checkout; [] when the office cannot be read."""
    try:
        q = queue_facts()
        return office.unmarked_counted(q) if q else []
    except Exception:
        return []


def pending_file():
    return office.office_dir() / "pending-state.jsonl"


def read_pending():
    try:
        return [json.loads(l) for l in pending_file().read_text(encoding="utf-8").splitlines() if l.strip()]
    except (OSError, ValueError):
        return []


def write_pending(held):
    f = pending_file()
    if not held:
        f.unlink(missing_ok=True)
        return
    tmp = f.with_suffix(".tmp")
    tmp.write_text("".join(json.dumps(h, ensure_ascii=False) + "\n" for h in held), encoding="utf-8", newline="\n")
    os.replace(tmp, f)


def hold_edit(argv, now):
    with office.locked(office.office_dir()):
        write_pending(read_pending() + [{"at": now.isoformat(timespec="seconds"), "argv": argv}])


def apply_pending():
    """Replays the held edits in order, each with the time it was made, in the main checkout only (anywhere else
    they would land in the wrong state.json and be lost). Under the office lock, so two writers never replay the
    same lines; a line that does not apply stays in the file, marked, for the manager to settle by hand."""
    if not counted_checkout() or not pending_file().exists():
        return 0
    try:
        with office.locked(office.office_dir()):
            held = read_pending()
            done, left = 0, []
            for h in held:
                if h.get("failed"):
                    left.append(h)
                    continue
                try:
                    rc = edit_state(list(h["argv"]), at=parse_updated(h["at"]))
                except (Exception, SystemExit) as e:  # one bad line must not lose the others
                    rc = f"{type(e).__name__}: {e}"
                if rc == 0:
                    done += 1
                else:
                    left.append({**h, "failed": str(rc)})
                    print(f"  ! a held edit did not apply ({rc}) and stays in {pending_file().name}: {h}")
            write_pending(left)
    except office.Refused as e:
        print(f"  ! the held edits were not applied this time: {e}")
        return 0
    fresh = sum(1 for h in held if not h.get("failed"))
    if fresh:
        print(f"applied {done} of {fresh} edit(s) held during a counted sweep")
    if left:
        print(f"  ! {len(left)} held edit(s) did not apply: make them by hand, then delete {pending_file().as_posix()}")
    return done


def lanes_of(f):
    """The lanes a failure entry names: "G18", or several as "G10, G17"."""
    return [x for x in re.split(r"[,\s]+", str(f.get("lane") or "")) if x]


def out_name():
    """The map's path as printed: relative to the checkout, or whole when FOUNDRY_PATHS_MAP moved it elsewhere."""
    try:
        return OUT.relative_to(ROOT).as_posix()
    except ValueError:
        return OUT.as_posix()


STATE_SHAPES = {"notes": ("at", "by", "text"), "log": ("date", "title"), "decisions": ("id", "question", "status")}
SHAPE_HINT = {"notes": "`board.py note --by` builds a note", "log": "a log entry is typed by hand",
              "decisions": "`board.py decide ask` builds a decision"}


def check_shape(state):
    """A `notes` item is {at, by, text}, a `log` item {date, title} and a `decisions` item {id, question, status}; a
    bare string or a missing key saves fine and then crashes the map's render after the commit, so write_state
    refuses it."""
    for key, need in STATE_SHAPES.items():
        items = state.get(key)
        if items is None:
            continue
        if not isinstance(items, list):
            raise ValueError(f"state.{key} must be a list, not {type(items).__name__}")
        for i, x in enumerate(items):
            miss = [k for k in need if not isinstance(x, dict) or k not in x]
            if miss:
                raise ValueError(f"state.{key}[{i}] must be an object with {', '.join(need)} "
                                 f"(missing {', '.join(miss)}): {str(x)[:80]!r}; {SHAPE_HINT[key]}")


def write_state(state, path=None):
    """state.json in its own format, written whole or not at all: a temporary file beside it, then a replace. A note
    or log entry of the wrong shape is refused (ValueError) before anything is written."""
    check_shape(state)
    path = path or STATE
    try:
        fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    except OSError:  # a transient open failure passes on one retry
        time.sleep(0.2)
        fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(state, indent=1, ensure_ascii=False) + "\n")
        if path.exists():
            os.chmod(tmp, path.stat().st_mode)  # mkstemp's file is private; keep the old file's mode
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def starter_state(now=None):
    """What `init` writes, and what a project with no state yet is drawn from: Now, an empty shift, the profile's
    rota slots, limits and usage stop, and every list empty."""
    now = now or dt.datetime.now().astimezone()
    return {
        "updated": now.isoformat(timespec="minutes"),
        "now": {"headline": f"{PROJECT}: no shift planned yet.",
                "position": "The state was just started; the manager writes the first shift plan.", "tree": "",
                "plan_file": f"{STATE_REL} (the shift's blocks)"},
        "shift": {"id": "start", "title": "No shift planned yet", "when": "not started",
                  "crew_max": P.get("limits.crew_max", 4), "heavy_ok": False, "before_start": [], "blocks": []},
        "queue": [], "blockers": [], "log": [],
        "milestones": [], "lanes": {},
        "rota": {"slots": default_slots(), "days": []},
        "checkpoints": [], "failures": [], "notes": [], "research_review": [],
        "usage": {"stop": USAGE_STOP, "points": []},
        "decisions": [],
    }


def default_slots():
    """The rota a state with no rota.slots is read by: the profile's, else the office's own."""
    return P.slots() or list(getattr(office, "DEFAULT_SLOTS", []))


def normalize(state, now=None):
    """A state someone typed by hand may lack `now`, `updated` or `shift`; the page and the brief read them, so the
    gaps are filled in memory (never written) and the map still builds."""
    now = now or dt.datetime.now().astimezone()
    if not isinstance(state.get("now"), dict):
        state["now"] = {}
    for k in ("headline", "position", "tree"):
        state["now"].setdefault(k, "")
    if parse_or_none(state.get("updated")) is None:
        state["updated"] = now.isoformat(timespec="minutes")
    if not isinstance(state.get("shift"), dict):
        state["shift"] = {}
    return state


def read_state(required=False, fill=True):
    """(state, True) from the state file, or (a starter state, False) when there is none yet. `required` (the edit
    commands) and a file that is not JSON end the run with one plain line, never a traceback. fill=False (the edit
    commands, which write the state back) leaves a hand-typed state's gaps as they are."""
    try:
        text = STATE.read_text(encoding="utf-8")
    except OSError:
        if required:
            raise SystemExit(f"no state yet ({STATE.as_posix()}): run board.py init first")
        return normalize(starter_state()), False
    try:
        state = json.loads(text)
        if not isinstance(state, dict):
            raise ValueError("the top level is not an object")
    except ValueError as e:
        raise SystemExit(f"{STATE.as_posix()} is not a state the map can read ({e}); fix it by hand (git diff shows "
                         "the last edit)")
    return (normalize(state) if fill else state), True


def missing_inputs():
    """One sentence per input the project does not have yet, for Needs attention: the map and the brief are built
    without it, and each line says who writes it."""
    out = []
    if not STATE.is_file():
        out.append(f"no state yet: run founder.py init, or board.py init (it writes {STATE_REL})")
    if not ROADMAP.is_file():
        out.append(f"no roadmap yet: the founder writes {ROADMAP_REL}")
    if not GYM.is_dir():
        out.append(f"no gym yet: the first grader sets up {GYM_REL}/ with the gym skill (lanes, preregs, series); lane checks are skipped")
    return out


def open_decisions(state):
    """The decisions that still wait on the user, as the register keeps them (newest first)."""
    return [d for d in state.get("decisions") or [] if isinstance(d, dict) and d.get("status", "open") == "open"]


def read_roadmap():
    """The road to the goal from the roadmap: {id: (priority, status)}, the priority being the proposed one where
    the roadmap proposes a change, and the release stages, each with its exit IDs, met count and status."""
    try:
        text = ROADMAP.read_text(encoding="utf-8")
    except OSError:
        return {}, []
    reqs = {m[1]: (m[3] or m[2], m[4]) for m in REQ_ROW.finditer(text)}
    stages = []
    for m in STAGE_ROW.finditer(text):
        ids = []
        for prefix, a, b in re.findall(r"([A-Z0-9]+)-(\d+)(?:–(\d+))?", re.sub(r"\([^)]*\)", "", m[4])):
            ids += [f"{prefix}-{n:0{len(a)}d}" for n in range(int(a), int(b or a) + 1)]
        sts = [reqs.get(i, (None, None))[1] for i in ids]
        met = sum(1 for s in sts if s in REQ_MET)
        status = ("done" if ids and met == len(ids) else
                  "partial" if any(s in REQ_MET or s == "Part" for s in sts) else "planned")
        stages.append({"id": m[1], "title": m[2].strip(), "theme": m[3].strip(), "ids": ids, "met": met,
                       "counts": Counter(s or "missing" for s in sts), "status": status})
    return reqs, stages


def pass_lanes(lanes):
    """The roadmap's PASS rows joined to their lanes' newest counted verdicts (a PASS typed in the roadmap is not a
    lane passing now). A row's lanes are the known lane names (the series, state.lanes) in its Where and note cells. Returns
    (stale, unnamed): stale rows name a lane whose newest run is not PASS, as {"id", "p", "lanes", "stale": [{"lane",
    "verdict", "run_id"}]}; unnamed rows name no known lane, as {"id", "p"}."""
    try:
        text = ROADMAP.read_text(encoding="utf-8")
    except OSError:
        return [], []
    stale, unnamed = [], []
    for m in PASS_ROW.finditer(text):
        rid, p = m[1], m[3] or m[2]
        named = []
        for x in lane_names(m[4] + " " + m[5]):
            if x in lanes and x not in named:
                named.append(x)
        if not named:
            unnamed.append({"id": rid, "p": p})
            continue
        bad = [{"lane": x, "verdict": lanes[x]["verdict"] or "no run", "run_id": lanes[x]["run_id"]}
               for x in named if lanes[x]["verdict"] != "PASS"]
        if bad:
            stale.append({"id": rid, "p": p, "lanes": named, "stale": bad})
    return stale, unnamed


RUN_ID = re.compile(r"\b(20\d{6}-\d{6}(?:-[0-9a-f]{4})?)\b")


def series_runs():
    """{lane: [(run id, verdict), oldest first]} from the gym's series."""
    out = {}
    for f in sorted(SERIES.glob("*.json")):
        try:
            pts = json.loads(f.read_text(encoding="utf-8")).get("points", [])
        except (OSError, ValueError):
            continue
        out[f.stem] = [(p["run_id"], p.get("verdict")) for p in pts if p.get("run_id")]
    return out


# a VOID or STARVED run decided nothing, so it never supersedes the decided run a roadmap row quotes
UNDECIDED = ("VOID", "STARVED")


def roadmap_stale_runs(text, runs):
    """Rows of the roadmap that quote a lane's old counted run and not its newest decided one (a stage row that
    still says FAIL after the lane's counted PASS). `runs` is series_runs(): per lane, (run id, verdict) pairs oldest
    first (a bare id counts as decided). A table row is stale for lane L when it names L, quotes at least one run id
    of L's series (a quoted id matches a series id it is a prefix of), and does not name L's newest decided point
    (a VOID or STARVED point after it changes nothing). The newest counts as named when the row quotes it
    in full or by prefix, or by its four-hex suffix alone as a word ("fixed: G8 PASS 0854"); "run X,
    latest Y" is not stale. Returns [{"row", "lane", "quoted", "newest"}]."""
    stale = []
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        quoted = RUN_ID.findall(line)
        if not quoted:
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        row = re.sub(r"[*]", "", cells[0]) if cells else "?"
        named = set(lane_names(line))
        for lane in sorted(named & set(runs)):
            pts = [p if isinstance(p, (tuple, list)) else (p, None) for p in runs[lane]]
            ids = [r for r, _ in pts]
            decided = [r for r, v in pts if v not in UNDECIDED]
            if not decided:
                continue
            newest = decided[-1]
            mine = [q for q in quoted if any(r.startswith(q) for r in ids)]
            if not mine or any(newest.startswith(q) for q in mine):
                continue
            suffix = re.search(r"-([0-9a-f]{4})$", newest)
            if suffix and re.search(rf"(?<![0-9a-f-]){suffix[1]}(?![0-9a-f])", line):
                continue
            stale.append({"row": row, "lane": lane, "quoted": mine, "newest": newest})
    return stale


def roadmap_runs_warning(text, runs):
    """consistency()'s roadmap step: one warning sentence for the rows that quote an old run, or None."""
    old_runs = roadmap_stale_runs(text, runs)
    if not old_runs:
        return None
    shown = "; ".join(f"{s['row']} quotes {s['lane']} {s['quoted'][-1]}, newest decided {s['newest']}" for s in old_runs[:4])
    return (f"{len(old_runs)} row(s) of {ROADMAP_REL} quote a lane's older counted run and not its newest decided one "
            f"({shown}{'; …' if len(old_runs) > 4 else ''}). Update each row's verdict and run id, quoting the newest "
            "run id in full (a VOID or STARVED run never replaces a decided one).")


def stale_text(row):
    """'APP-03 is marked PASS on G2, whose latest run 20300110-113607-0121 is VOID'."""
    on = ", ".join(row["lanes"])
    if len(row["lanes"]) == 1 and row["stale"][0]["run_id"]:
        s = row["stale"][0]
        return f"{row['id']} is marked PASS on {on}, whose latest run {s['run_id']} is {s['verdict']}"
    why = "; ".join(f"{s['lane']}'s latest run {s['run_id']} is {s['verdict']}" if s["run_id"] else f"{s['lane']} has no run"
                    for s in row["stale"])
    return f"{row['id']} is marked PASS on {on}: {why}"


def read_lanes(state):
    """One record per lane, from the gym's series plus the files that exist for lanes with no run yet. A project
    with no gym folder has only the lanes its state names; a series file that is not JSON is skipped."""
    lanes = {}
    for f in sorted(SERIES.glob("*.json")):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            pts = d.get("points", [])
        except (OSError, ValueError, AttributeError):
            continue
        last = pts[-1] if pts else None
        first_pass = next((p for p in pts if p.get("verdict") == "PASS" and p.get("ts")), None)
        lanes[f.stem] = {
            "lane": f.stem,
            "grader": d.get("meta", {}).get("grader", ""),
            "runs": len(pts),
            "counts": Counter(p.get("verdict") for p in pts),
            "verdict": last.get("verdict") if last else None,
            "prev": pts[-2].get("verdict") if len(pts) > 1 else None,
            "n": last.get("n") if last else None,
            "run_id": last.get("run_id") if last else None,
            "when": local_dt(last["ts"]) if last and last.get("ts") else None,
            "first_pass": first_pass["ts"] if first_pass else None,
            "history": [(p.get("verdict"), p.get("run_id"), p.get("n"), p.get("ts")) for p in pts[-12:]],
        }
    for name in state.get("lanes", {}):
        lanes.setdefault(name, {"lane": name, "grader": "", "runs": 0, "counts": Counter(),
                                "verdict": None, "prev": None, "n": None, "run_id": None, "when": None,
                                "first_pass": None, "history": []})
    for name, rec in lanes.items():
        rec["checkpoint"] = state.get("lanes", {}).get(name, "")
        base = re.sub(r"[a-z]+$", "", name)
        rec["prereg"] = next((p for p in (PREREG / f"{name}.json", PREREG / f"{base}.json") if p.exists()), None)
        contract = CONTRACTS / f"{name}-artifacts.md"
        rec["contract"] = contract if contract.exists() else None
        rec["draft"] = bool(contract.exists() and "DRAFT" in contract.read_text(encoding="utf-8").splitlines()[0])
        chart = CHARTS / f"{name}.html"
        rec["chart"] = chart if chart.exists() else None
        rec["grade"] = None
        if rec["run_id"]:
            hits = sorted(GRADES.glob(f"*{rec['run_id']}.md"))
            hits = [h for h in hits if len(hits) == 1 or f"-{name}-" in h.name]
            rec["grade"] = hits[0] if hits else None
    return dict(sorted(lanes.items(), key=lambda kv: lane_key(kv[0])))


def read_crew(state, now):
    """The crew office (office.py's folder in the main checkout) at build time; empty until a badge is issued."""
    ts = now.timestamp()
    crew = {"dir": "", "manager": None, "badges": [], "reports": [], "events": [], "error": "",
            "slot": office.slot_at((state.get("rota") or {}).get("slots"), ts)}
    try:
        d = office.office_dir()
        if (d / "roster.json").exists():
            crew.update(office.crew(d, ts))
            crew["events"] = [e for e in office.read_events(d) if e["at"] <= ts]
        crew["dir"] = d.as_posix()
    except Exception as e:  # the map still builds when the office cannot be read, whatever is wrong with its files
        crew["error"] = f"{type(e).__name__}: {e}"
    for b in crew["badges"]:
        try:
            p = Path(b["plate"])
            b["svg"] = p.read_text(encoding="utf-8") if p.exists() else ""
        except Exception:
            b["svg"] = ""
    return crew


def default_seat():
    """The seat whose files carry no suffix (rq.lock, rq.last): the first one the profile names."""
    return str((P.get("resource.seats") or ["main"])[0])


def read_resource(crew, now):
    """The shared resource's seats from the crew office's queue files (rq.seats, rq.lock[.<seat>]/hold.json,
    rq.queue.json, rq.last[.<seat>]): who holds each seat, since when and for how long, and who waits.
    Local files only; nothing is asked of the resource. Empty when the project has no shared resource or the office
    has no queue. The files are read by rq.py's rules (its seats, holder and live waiters), so the map and the queue
    agree, and no file, however mangled, stops the build."""
    d = Path(crew["dir"]) if crew.get("dir") else None
    res = {"seats": [], "queue": []}
    if not has_resource() or not d or not d.exists():
        return res
    try:
        # rq.py's seats: one seat per line, blanks and `#` lines skipped; a missing or empty file means the profile's
        names = [l.strip() for l in (d / "rq.seats").read_bytes().decode("utf-8", "replace").splitlines()
                 if l.strip() and not l.startswith("#")]
    except Exception:
        names = None
    if names is None and not any((d / f).exists() for f in ("rq.last", "rq.lock", "rq.queue.json")):
        return res  # an office with no queue at all
    names = names or [str(s) for s in (P.get("resource.seats") or ["main"])]
    ts = now.timestamp()
    for seat in names:
        suffix = "" if seat == default_seat() else "." + seat
        rec = {"seat": seat, "hold": None, "last": ""}
        try:
            rec["hold"] = read_hold(d / ("rq.lock" + suffix), ts)
        except Exception:
            pass
        try:
            rec["last"] = ((d / ("rq.last" + suffix)).read_bytes().decode("utf-8", "replace").strip().splitlines() or [""])[0]
        except Exception:
            pass
        res["seats"].append(rec)
    try:
        q = json.loads((d / "rq.queue.json").read_bytes().decode("utf-8", "replace"))
        res["queue"] = live_waiters(q if isinstance(q, list) else [], ts)
    except Exception:
        pass
    return res


def read_hold(lk, ts):
    """rq.py's holder: a seat is held while its lock dir exists. hold.json says by whom, since when and for how long;
    without it (an old-style or half-written hold) the holder file names it, else "unknown", since the dir's mtime."""
    if not lk.is_dir():
        return None
    h = {}
    try:
        j = json.loads((lk / "hold.json").read_bytes().decode("utf-8", "replace"))
        h = j if isinstance(j, dict) else {}
    except Exception:
        pass
    who = h.get("id")
    if not isinstance(who, str) or not who.strip():
        try:
            who = (lk / "holder").read_bytes().decode("utf-8", "replace").strip() or "unknown"
        except Exception:
            who = "unknown"
    since = number(h.get("since"))
    if since is None:
        since = lk.stat().st_mtime
    mx = number(h.get("max"))
    mx = int(mx) if mx and mx > 0 else RQ_MAX
    return {"id": who, "job": str(h.get("job") or ""), "since": since, "max": mx, "all": bool(h.get("all")),
            "overdue": ts - since > mx}


def live_waiters(q, ts):
    """rq.py's live waiters: those still polling, in queue order (prio, then first come), a long wait ranking at
    prio 2. Entries without numeric at, beat and prio are not waiters rq.py could have written; they are left out."""
    out = []
    for e in q:
        if not isinstance(e, dict) or any(number(e.get(k)) is None for k in ("at", "beat", "prio")):
            continue
        if ts - e["beat"] > RQ_STALE:
            continue
        prio = 2 if ts - e["at"] > RQ_AGE and e["prio"] > 2 else e["prio"]
        out.append(dict(e, prio=prio, id=str(e.get("id", "?")), job=str(e.get("job") or "")))
    return sorted(out, key=lambda e: (e["prio"], e["at"]))


def recent_runs(lanes, now, hours=24):
    """Lanes whose latest graded run is younger than `hours`, oldest first: a sweep reads as one row per lane."""
    cut = now - dt.timedelta(hours=hours)
    return sorted((l for l in lanes.values() if l["when"] and l["when"] >= cut), key=lambda l: l["when"])


def failure_for(state, rec):
    """The failures entry that covers a lane's latest run, or None: one naming the run id, else one naming the lane
    with no run id that is still open, planned or dropped. A fixed entry with no run id was about an earlier run,
    so it does not cover a new failing one. An entry naming several lanes ("G10, G17") covers each of them."""
    mine = [f for f in state.get("failures", []) if rec["lane"] in lanes_of(f)]
    exact = [f for f in mine if rec["run_id"] and f.get("run_id") == rec["run_id"]]
    loose = [f for f in mine if not f.get("run_id") and f.get("status", "open") != "fixed"]
    return (exact or loose or [None])[-1]


def attention(state, lanes, crew, res, now):
    """What the manager acts on next, most pressing first, as (css class, group, sentence, anchor). The warnings
    box says where the map disagrees with the tree; this list says what the project itself is waiting for."""
    out = []
    for line in missing_inputs():
        out.append(("s-next", "setup", line, "keeping"))
    for d in open_decisions(state):
        before = f" (needed before {d['needed_before']})" if d.get("needed_before") else ""
        out.append(("s-next", "the user", f"{d.get('id', '?')} waits on the user{before}: {d.get('question', '')}",
                    "decisions"))
    for b in state.get("blockers", []):
        if waits_on_user(b):
            out.append(("s-next", "the user", b.get("what", ""), "blockers"))
    week_ago, old = now - dt.timedelta(days=7), []
    for l in lanes.values():
        if l["verdict"] not in NOT_PASSING:
            continue
        f = failure_for(state, l)
        if f and f.get("status") == "dropped":
            continue  # decided not to pursue
        filed = f"{f['id']} {f.get('status', 'open')}" if f else "no failure entry"
        if f and l["when"] and l["when"] < week_ago:
            old.append(f"{l['lane']} {l['verdict']} ({filed})")  # long known: one line for all of them, below
            continue
        was = f" (was {l['prev']})" if l["prev"] and l["prev"] != l["verdict"] else ""
        owner = f", owner {(f.get('owner') or 'none')[:60]}" if f else ""
        out.append(("s-bad" if not f or f.get("status", "open") == "open" else "s-warn", "lane",
                    f"{l['lane']} {l['verdict']}{was}, run {l['run_id']}: {filed}{owner}", "runs"))
    if old:
        out.append(("s-plan", "lane", f"{len(old)} lane(s) not passing for over a week: " + ", ".join(old), "lanes"))
    unplanned = [f for f in state.get("failures", []) if f.get("status", "open") == "open" and not f.get("plan")]
    if unplanned:
        out.append(("s-warn", "failures", f"{len(unplanned)} open failure(s) have no plan yet: "
                    + ", ".join(f.get("id", "?") for f in unplanned[:12]) + (" …" if len(unplanned) > 12 else ""), "failures"))
    for b in crew["badges"]:
        if b["role"] in TOP_ROLES:
            continue
        if b["status"] in ("STALE", "OVERDUE"):
            out.append(("s-bad" if b["status"] == "OVERDUE" else "s-warn", "crew",
                        f"{b['id']} {b['name']} is {b.get('status_text') or b['status']}; chase it or clock it out", "crew"))
        elif (b["status"] == "HIRED" and b.get("kind") == "SESSION" and not b.get("session")
              and now.timestamp() - b["issued"] > 900):
            # a session badge nobody assigned a session to counts toward crew_max and never clocks in
            out.append(("s-bad", "crew", f"{b['id']} hired at {local_dt(b['issued']):%H:%M}, no session: assign a bench "
                        "or clock it out", "crew"))
        elif b["status"] == "HIRED" and now.timestamp() - b["issued"] > 900:
            out.append(("s-next", "crew", f"{b['id']} {b['name']} was hired at {local_dt(b['issued']):%H:%M} and has not "
                        "clocked in; start its session or clock it out", "crew"))
    for rec in res["seats"]:
        h = rec["hold"]
        if h and h["overdue"]:
            out.append(("s-bad", "resource", f"seat {rec['seat']} is held by {h['id']} past its {h['max'] // 60} min "
                        f"(since {local_dt(h['since']):%H:%M})", "resource"))
    u = (state.get("usage") or {})
    pts, _ = usage_points(u)
    stop = usage_stop(u)
    if pts and stop is not None and pts[-1][1] >= stop:
        out.append(("s-bad", "usage", f"weekly usage {pts[-1][1]:g}% is at or past the stop at {stop:g}%; "
                    "ask the user before new work", "usage"))
    return out


def usage_stop(usage):
    """The usage stop in force: the one the state records, else the profile's limits.usage_stop."""
    stop = number((usage or {}).get("stop"))
    return stop if stop is not None else number(USAGE_STOP)


def waits_on_user(b):
    """A blocker the user must clear: its owner names the user as a word ("the user", "User"; not "app-user builder"),
    or it has no owner and its text says it waits on the user."""
    word = re.compile(r"(?<![\w-])user(?![\w-])", re.I)
    owner = b.get("owner")
    if owner:
        return bool(word.search(str(owner)))
    return bool(re.search(r"(?<![\w-])the user(?![\w-])", str(b.get("what") or ""), re.I))


def crew_intervals(crew, now):
    """(badge id, start, end) of every stretch an employee was on the clock, from the in and out punches."""
    roles = {b["id"]: b["role"] for b in crew["badges"]}
    open_, out = {}, []
    for e in crew["events"]:
        if roles.get(e["id"], "MANAGER") in TOP_ROLES:
            continue
        if e["ev"] == "in":
            open_[e["id"]] = e["at"]
        elif e["ev"] == "out" and e["id"] in open_:
            out.append((e["id"], open_.pop(e["id"]), e["at"]))
    return out + [(i, a, now.timestamp()) for i, a in open_.items()]


def untriaged(state, crew):
    """Failure reports from the crew (office.py fail, R<seq>) that no state.failures entry names in its "from"
    (one report id, or a list of them when one failure files several reports)."""
    filed = set()
    for f in state.get("failures", []):
        fr = f.get("from")
        filed.update(fr if isinstance(fr, list) else [fr] if fr else [])
    return [r for r in crew["reports"] if f"R{r['seq']}" not in filed]


ENDS_NEXT_DAY_MAX_S = 4 * 3600  # a next-morning `ends` reads up to this far past the slot's end


def read_ends(sid, s0, s1, text):
    """A rota `ends` ("HH:MM", local, 00:00-23:59) for the slot `sid` that ran s0..s1, as (epoch seconds,
    None), or (None, why it is refused), or (None, None) when there is none. The end is the HH:MM on the slot's start
    date when that is after the start. An HH:MM at or before the start reads as the next day only for a slot that
    crosses midnight (a night slot's "07:30"), and only up to the slot's length or ENDS_NEXT_DAY_MAX_S past its end,
    whichever is less; any other end before the start is a typo, refused, and the check warns. So is an
    `ends` that is not a time ("24:00", "7:3", "07:30pm"). The time is built on the calendar date and then
    made local, so a next-morning end keeps its wall-clock time across a DST change."""
    raw = str(text or "").strip()
    if not raw:
        return None, None
    m = re.match(r"^([01]?\d|2[0-3]):([0-5]\d)$", raw)
    if not m:
        return None, (f"`ends` {text!r} for the {sid} slot of {local_dt(s0):%Y-%m-%d} is not a time HH:MM "
                      "(00:00-23:59); it is ignored.")
    start = local_dt(s0)
    hm = dt.time(int(m.group(1)), int(m.group(2)))
    t = dt.datetime.combine(start.date(), hm).astimezone()
    if t.timestamp() > s0:
        return t.timestamp(), None
    crosses = local_dt(s1).date() > start.date()
    t = dt.datetime.combine(start.date() + dt.timedelta(days=1), hm).astimezone()
    late = min(s1 - s0, ENDS_NEXT_DAY_MAX_S)
    if crosses and t.timestamp() - s1 <= late:
        return t.timestamp(), None
    why = (f"`ends` {text} for the {sid} slot of {start:%Y-%m-%d} is at or before the slot's start ({start:%H:%M}), "
           + (f"and more than {late // 3600:g} h past the slot's end ({local_dt(s1):%H:%M}); " if crosses
              else "and the slot does not cross midnight; ")
           + "it is ignored. Write an end after the slot's start"
           + (f" (or the next morning, until {local_dt(s1 + late):%H:%M}, for this slot)." if crosses else "."))
    return None, why


def user_end_why(state, b):
    """The end the user set for a manager's slot, as (epoch seconds, None), (None, why it is refused) or
    (None, None). It is `ends` in the rota.days entry of the badge's own slot as it clocked in, keyed (like every
    rota entry) by the date the slot started, so a night manager who clocks in after midnight reads the night that
    began the evening before, and a manager appointed and clocked in just before its slot starts reads
    that slot (office.badge_slot). read_ends says how an end before the start reads."""
    try:
        slots = (state.get("rota") or {}).get("slots")
        own = office.badge_slot(slots, b)
        if own is None:
            return None, None  # the badge's slot is not the one it clocked in during, nor the next: no entry to read
        sid, s0, s1 = own
        day = f"{local_dt(s0):%Y-%m-%d}"
        entry = next((e for e in (state.get("rota") or {}).get("days", [])
                      if isinstance(e, dict) and e.get("date") == day), {}).get(sid) or {}
        return read_ends(sid, s0, s1, entry.get("ends") if isinstance(entry, dict) else None)
    except (AttributeError, KeyError, TypeError, ValueError):
        return None, None


def user_end(state, b):
    """The user's end for the manager's slot as epoch seconds, or None (see user_end_why)."""
    return user_end_why(state, b)[0]


def rota_names_manager(state, slot, s0, bid):
    """True when the rota.days entry of the slot now (keyed by the date it started) names `bid` as its manager,
    as the first word of its `manager` text: a manager re-badged before the boundary whose badge reads the slot that
    ended is still this slot's manager when the rota says so."""
    try:
        day = f"{local_dt(s0):%Y-%m-%d}"
        entry = next((e for e in (state.get("rota") or {}).get("days", [])
                      if isinstance(e, dict) and e.get("date") == day), {}).get(slot) or {}
        words = str(entry.get("manager") or "").split()
        return bool(words) and words[0] == bid
    except (AttributeError, TypeError, ValueError):
        return False


def stale_contract_pins(prereg_dir=None, root=None):
    """Lanes whose contract file in this checkout has a sha256 (and git blob) that no pin in the lane's
    prereg names, as warning sentences. A merge that brings a contract amendment leaves the counted lane's pin stale
    until its grader re-pins. A prereg with no contract path, or whose contract is not in this checkout (a lane on an
    unmerged branch), is skipped. A prereg's contract path is relative to the checkout (`root`)."""
    prereg_dir = Path(prereg_dir or PREREG)
    root = Path(root or ROOT)
    out = []
    for p in sorted(prereg_dir.glob("*.json"), key=lambda p: lane_key(p.stem)):
        try:
            text = p.read_text(encoding="utf-8")
            c = json.loads(text).get("contract")
            path = c.get("path") if isinstance(c, dict) else None
            f = root / path if path else None
            if not f or not f.is_file():
                continue
            body = f.read_bytes()
        except (OSError, ValueError, AttributeError):
            continue
        sha = hashlib.sha256(body).hexdigest()
        blob = hashlib.sha1(b"blob %d\0" % len(body) + body).hexdigest()
        if sha not in text and blob not in text:
            out.append(f"{p.stem}'s prereg pins no version of {path} as it is in this checkout (sha256 {sha[:12]}); "
                       f"a contract change came in without the grader's re-pin: no counted {p.stem} until it is re-pinned.")
    return out


def ends_typos(state, now):
    """Every rota.days `ends` from the last two days that read_ends refuses, as warning sentences. A days
    entry that is not an object with a YYYY-MM-DD date is skipped with its own warning, never stopping the scan or the
    check."""
    out = []
    rota = state.get("rota") or {}
    slots = rota.get("slots") if isinstance(rota, dict) else None
    days = rota.get("days", []) if isinstance(rota, dict) else []
    for i, e in enumerate(days if isinstance(days, list) else []):
        try:
            if not isinstance(e, dict):
                out.append(f"The rota's days entry {i + 1} is not an object ({str(e)[:40]!r}); it is skipped.")
                continue
            date = dt.date.fromisoformat(str(e.get("date")))
        except ValueError:
            out.append(f"The rota's days entry {i + 1} has a bad date ({str(e.get('date'))[:20]!r}); it is skipped.")
            continue
        for sid, v in e.items():
            if not isinstance(v, dict) or not v.get("ends"):
                continue
            try:
                start = next((x["start"] for x in (slots or default_slots()) if x["id"] == sid), None)
                if not start:
                    continue
                t0 = dt.datetime.fromisoformat(f"{date.isoformat()}T{start}:00").astimezone()
                if (now - t0).total_seconds() > 2 * 86400:
                    continue
                _, s0, s1 = office.slot_at(slots, t0.timestamp())
                _, why = read_ends(sid, s0, s1, v.get("ends"))
            except (AttributeError, KeyError, TypeError, ValueError):
                continue
            if why:
                out.append("The rota's " + why)
    return out


def consistency(state, lanes, facts, now, crew):
    """Everything that makes the map untrustworthy, as plain sentences."""
    warn = []
    updated = parse_or_none(state.get("updated")) or now
    age_h = (now - updated).total_seconds() / 3600
    if age_h > STALE_AFTER_H:
        warn.append(f"The state is {age_h / 24:.1f} days old (updated {state['updated']}); update it before trusting Now.")
    for rec in lanes.values():
        if rec["when"] and rec["when"] > updated:
            warn.append(f"{rec['lane']} ran at {rec['when']:%Y-%m-%d %H:%M} ({rec['verdict']}), after the state's last update.")
    for group in ("milestones", "phases"):
        for item in state.get(group, []):
            lane = lanes.get(item.get("lane", ""))
            v = lane["verdict"] if lane else None
            if item.get("status") == "done" and v != "PASS":
                warn.append(f"{item.get('id')} is marked done but its lane {item.get('lane')} has {v or 'no run'}.")
            if item.get("status") != "done" and v == "PASS" and group == "milestones":
                warn.append(f"{item.get('id')} is not marked done but {item['lane']} is PASS; update the status or say why.")
    blocks = state.get("shift", {}).get("blocks", [])
    queue = state.get("queue", [])
    if blocks and all(b.get("status") in ("done", "skipped") for b in blocks):
        if queue:
            warn.append(f"The shift is complete; promote the next queued shift ({BOARD} promote): "
                        f"{queue[0].get('title', '')[:70]}")
        else:
            warn.append("Every block of the shift plan is done or skipped and nothing is queued; write the next shift plan.")
    for b in blocks:
        if b.get("status") == "in-progress":
            warn.append(f"Block {b.get('time')} is marked in progress: it is running now, or the last block did not end with an update.")
    # the queue: what a promote would move into the shift must already have the shift's shape
    for i, q in enumerate(queue, 2):
        if not q.get("id") or not q.get("title") or not q.get("blocks"):
            warn.append(f"Queued shift {i} lacks an id, a title or blocks.")
        if q.get("crew_max") is None:
            warn.append(f"Queued shift {q.get('id', i)} has no crew_max; the manager sets the headcount per shift.")
        for b in q.get("blocks", []):
            if any(b.get(k) is None for k in ("time", "title", "done_when")):
                warn.append(f"Queued shift {q.get('id', i)}: a block lacks time, title or done_when.")
            if b.get("status", "pending") != "pending":
                warn.append(f"Queued shift {q.get('id', i)}: block {b.get('time')} is {b.get('status')}, not pending.")
    ids = [x for x in [state.get("shift", {}).get("id")] + [q.get("id") for q in queue] if x]
    for dup in sorted({x for x in ids if ids.count(x) > 1}):
        warn.append(f"The shift id {dup} is used more than once.")
    m = re.search(r"\b[0-9a-f]{7,}\b", str((state.get("now") or {}).get("tree") or ""))
    if m and facts["head"] != "?" and not facts["head"].startswith(m.group(0)) and not m.group(0).startswith(facts["head"]):
        # commits on top that touch only records (the map's own files, reports and notes, a counted run's series,
        # charts and grades) are the routine, not a surprise: Now's tree names the last code commit, and the
        # warning names what changed
        between = [f.strip() for f in git("diff", "--name-only", f"{m.group(0)}..HEAD").splitlines() if f.strip()]
        known = bool(git("cat-file", "-t", m.group(0)))
        code = [f for f in between if not is_record(f)]
        if not known or code:
            warn.append(f"Now says the tree is at {m.group(0)} but HEAD is {facts['head']}; something was committed after the last update"
                        + (f" ({', '.join(code[:3])}{', …' if len(code) > 3 else ''})." if code else "."))
    if facts["dirty"]:
        warn.append(f"The tree is dirty ({len(facts['dirty'])} tracked files changed); look at git status first.")
    # every lane with a prereg has a row; the failures list covers every lane whose latest run did not pass
    known_lanes = set(state.get("lanes", {}))
    known_lanes |= {re.sub(r"[a-z]+$", "", x) for x in known_lanes}
    for p in sorted(PREREG.glob("*.json"), key=lambda p: lane_key(p.stem)):
        if p.stem not in known_lanes:
            warn.append(f"{p.stem} has a prereg but no row in state.lanes; add it with its checkpoint.")
    for rec in lanes.values():
        if rec["verdict"] in NOT_PASSING and not failure_for(state, rec):
            warn.append(f"{rec['lane']}'s latest run is {rec['verdict']} ({rec['run_id']}) and no failure entry names it "
                        "(a fixed entry with no run id does not cover a new run).")
    # gym checkpoints: a milestone in the shift has one, each has a prereg and a grader who is not its builder
    shift = state.get("shift", {})
    cps = state.get("checkpoints", [])
    ms = shift.get("milestone")
    if ms and not any(cp.get("milestone") == ms for cp in cps):
        warn.append(f"The shift's milestone {ms} has no gym checkpoint; the manager sets one (lane, builder, grader).")
    if ms and blocks and not any(b.get("checkpoint") for b in blocks):
        warn.append(f"No block of the shift carries the checkpoint (the counted gym run of {ms}'s lane).")
    for cp in cps:
        lane = lanes.get(cp.get("lane", ""))
        if not lane or not lane["prereg"]:
            warn.append(f"Checkpoint {cp.get('lane')} ({cp.get('milestone')}) has no prereg yet; its grader writes it before any data.")
        if not cp.get("grader"):
            warn.append(f"Checkpoint {cp.get('lane')} has no grader; hire an independent GRADER session for it.")
        elif cp.get("grader") == cp.get("builder"):
            warn.append(f"Checkpoint {cp.get('lane')}: the grader is its builder ({cp.get('grader')}); a grader is independent.")
    # the crew: one manager, inside its slot; the headcount; nobody silent or late; every report triaged
    on = [b for b in crew["badges"] if b["on"]]
    mgrs = [b for b in on if b["role"] == "MANAGER"]
    slot, s0, _ = crew["slot"]
    if len(mgrs) > 1:
        warn.append(f"{len(mgrs)} managers are on the clock ({', '.join(b['id'] for b in mgrs)}); there is one manager.")
    if not mgrs and any(b["role"] not in TOP_ROLES for b in on):
        warn.append(f"Employees are on the clock and no manager is; the manager clocks in (/{P.skill('manager')}).")
    for b in mgrs:
        if b.get("slot") != slot and b["in_at"] < s0 and not rota_names_manager(state, slot, s0, b["id"]):
            end, _ = user_end_why(state, b)  # a refused end is warned by ends_typos below, and reads as none
            if end and now.timestamp() < end:
                pass  # the user's own end for this manager's slot (rota ends): it is still on the clock
            elif end:
                warn.append(f"The manager {b['id']} ran past the user's end for its {b.get('slot')} slot "
                            f"({local_dt(end):%H:%M}); hand off (office.py end-shift, the log entry, clock out).")
            else:
                warn.append(f"The manager {b['id']} clocked in for the {b.get('slot')} slot, which ended at "
                            f"{local_dt(s0):%H:%M}; hand off (office.py end-shift, the log entry, clock out) before the {slot} slot's work. "
                            "If the user set a later end, write it as `ends` in the slot's rota.days entry.")
        if b["status"] == "STALE":
            warn.append(f"The manager {b['id']} has not been heard from since {local_dt(b['heard']):%H:%M}.")
    warn.extend(ends_typos(state, now))
    if mgrs and crew.get("dir"):
        try:
            import journal
            warn.extend(journal.warnings(Path(crew["dir"]), state, now.timestamp()))
        except Exception as exc:
            warn.append(f"NOTE: journal.py could not be loaded ({type(exc).__name__}: {exc}); run {P.tool('journal.py')} due.")
    warn.extend(stale_contract_pins())
    if shift.get("crew_max") is None:
        warn.append(f"The shift {shift.get('id')} has no crew_max; the manager sets the headcount per shift.")
    elif len(office.headcount(crew)) > int(shift["crew_max"]):
        warn.append(f"{len(office.headcount(crew))} employees hold badges on a shift whose crew_max is {shift['crew_max']}.")
    for b in crew["badges"]:
        if b["role"] not in TOP_ROLES and b["status"] in ("STALE", "OVERDUE"):
            why = (f"not heard from since {local_dt(b['heard']):%H:%M}" if b["status"] == "STALE"
                   else f"past its approximate finish {local_dt(b['eta']):%H:%M}")
            warn.append(f"{b['id']} {b['name']} is {b.get('status_text') or b['status']}: {why}; the manager chases it or clocks it out.")
    if crew["error"]:
        warn.append(f"The crew office could not be read ({crew['error']}).")
    unmarked = unmarked_hold()
    if unmarked:
        warn.append(f"{', '.join(unmarked)} holds or waits for {RES} at prio 0 or for every seat under a plain id, which the "
                    "counted-run guard cannot see: if it is a counted run, change nothing in the main checkout until it ends "
                    "(queue the next one as <badge>-counted-<lane>).")
    _, bad = usage_points(state.get("usage"))
    if bad:
        warn.append(f"state.usage.points has {len(bad)} point(s) the map cannot read (index {', '.join(map(str, bad))}: "
                    "`at` must be an ISO time, `weekly` a number); they are left off the chart. Fix or remove them.")
    new = untriaged(state, crew)
    if new:
        warn.append(f"{len(new)} failure report(s) from the crew are not triaged ({', '.join('R' + str(r['seq']) for r in new)}); "
                    "file each in state.failures with a plan and an owner.")
    # every slot since rota.rr_since runs its research-and-review window and files what it found
    rota = state.get("rota") or {}
    w = rr_window(rota, slot, s0)
    since = rota.get("rr_since")
    if w and since and s0 >= dt.datetime.fromisoformat(since).timestamp() and now.timestamp() > w[1]:
        day = f"{local_dt(s0):%Y-%m-%d}"
        if not any(r.get("date") == day and r.get("slot") == slot for r in state.get("research_review", [])):
            warn.append(f"The {slot} slot's research-and-review window ({local_dt(w[0]):%H:%M}–{local_dt(w[1]):%H:%M}) "
                        "has ended and research_review has no entry for it; file the reports, or a note saying why not.")
    # the decisions register: every entry has an id of its own and a status the map knows
    dec_ids = [str(d.get("id")) for d in state.get("decisions") or [] if isinstance(d, dict)]
    for dup in sorted({x for x in dec_ids if dec_ids.count(x) > 1}):
        warn.append(f"The decision id {dup} is used more than once in state.decisions.")
    for d in state.get("decisions") or []:
        if isinstance(d, dict) and d.get("status", "open") not in DECISION_STATUSES:
            warn.append(f"Decision {d.get('id')} has the status {d.get('status')!r}; it is one of {', '.join(DECISION_STATUSES)}.")
        if isinstance(d, dict) and d.get("status") == "answered" and not str(d.get("answer") or "").strip():
            warn.append(f"Decision {d.get('id')} is marked answered with no answer; record the user's own words "
                        f"(board.py decide answer {d.get('id')} --words ...), or set it back to open.")
    # the road to the goal: the roadmap's tables parse, and every release stage's exit ID has a requirement row
    # (a project with no roadmap yet has one line under Needs attention, not a warning)
    reqs, stages = read_roadmap()
    if ROADMAP.is_file() and (not reqs or not stages):
        warn.append(f"{ROADMAP_REL} has no requirement rows or release stages the map can read; Road to {GOAL} is empty.")
    for st in stages:
        missing = [i for i in st["ids"] if i not in reqs]
        if missing:
            warn.append(f"Release stage {st['id']} names {', '.join(missing)}, which no requirement row of {ROADMAP_REL} has.")
    # a PASS row counts as met as typed; say when the lane it names does not pass now, or when it names none
    stale, unnamed = pass_lanes(lanes)
    for row in stale:
        warn.append(stale_text(row) + f"; the row counts as met as typed. Rerun the lane, or mark the row Part in {ROADMAP_REL}.")
    # a row quoting a lane's old counted run and not its newest has gone stale since that run
    try:
        old_runs = roadmap_runs_warning(ROADMAP.read_text(encoding="utf-8"), series_runs())
    except OSError:
        old_runs = None
    if old_runs:
        warn.append(old_runs)
    if unnamed:
        warn.append(f"{len(unnamed)} PASS row(s) of {ROADMAP_REL} name no lane, so the map cannot check them "
                    f"({', '.join(r['id'] for r in unnamed)}): PASS with no lane named; name the lane and run in the row.")
    return warn


def rr_window(rota, slot_id, s0):
    """A slot's research-and-review window (rota.slots[].rr, "22:15–23:45") as epoch seconds inside the slot that starts at s0."""
    sl = next((x for x in rota.get("slots") or [] if x.get("id") == slot_id), None)
    m = re.match(r"\s*(\d{1,2}):(\d{2})\s*[–-]\s*(\d{1,2}):(\d{2})", (sl or {}).get("rr", ""))
    if not m:
        return None
    base = local_dt(s0).replace(hour=0, minute=0, second=0, microsecond=0)
    a = base + dt.timedelta(hours=int(m.group(1)), minutes=int(m.group(2)))
    if a.timestamp() < s0:  # a night slot's window after midnight
        a += dt.timedelta(days=1)
    b = base + dt.timedelta(hours=int(m.group(3)), minutes=int(m.group(4)))
    while b <= a:
        b += dt.timedelta(days=1)
    return a.timestamp(), b.timestamp()


CSS = """
:root{
  --bg:#f7f7f5; --surface:#ffffff; --surface-2:#f0efeb; --text:#1d1d1b; --text-2:#55554f; --text-3:#85847d;
  --border:rgba(0,0,0,.12); --border-2:rgba(0,0,0,.22);
  --good:#0f6e56; --good-bg:#e1f5ee; --good-bd:#5dcaa5;
  --danger:#a32d2d; --danger-bg:#fcebeb; --danger-bd:#e39a9a;
  --warn:#854f0b; --warn-bg:#faeeda; --warn-bd:#e2bb7a;
  --accent:#185fa5; --accent-bg:#e6f1fb; --accent-bd:#8fbce8;
  --radius:8px;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --bg:#161615; --surface:#1f1f1d; --surface-2:#2a2a28; --text:#ecebe6; --text-2:#b9b8b1; --text-3:#8d8c86;
    --border:rgba(255,255,255,.12); --border-2:rgba(255,255,255,.24);
    --good:#9fe1cb; --good-bg:#08392f; --good-bd:#1d9e75;
    --danger:#f09595; --danger-bg:#4a1717; --danger-bd:#9b3b3b;
    --warn:#fac775; --warn-bg:#412402; --warn-bd:#8a5a16;
    --accent:#85b7eb; --accent-bg:#0c2c4f; --accent-bd:#2f6ca8;
  }
}
:root[data-theme="dark"]{
  --bg:#161615; --surface:#1f1f1d; --surface-2:#2a2a28; --text:#ecebe6; --text-2:#b9b8b1; --text-3:#8d8c86;
  --border:rgba(255,255,255,.12); --border-2:rgba(255,255,255,.24);
  --good:#9fe1cb; --good-bg:#08392f; --good-bd:#1d9e75;
  --danger:#f09595; --danger-bg:#4a1717; --danger-bd:#9b3b3b;
  --warn:#fac775; --warn-bg:#412402; --warn-bd:#8a5a16;
  --accent:#85b7eb; --accent-bg:#0c2c4f; --accent-bd:#2f6ca8;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--text);font:16px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:1040px;margin:0 auto;padding:32px 16px 64px}
h1{font-size:28px;font-weight:600;margin:0 0 4px;letter-spacing:-.01em}
h2{font-size:20px;font-weight:600;margin:44px 0 6px}
h3{font-size:15px;font-weight:600;margin:0 0 4px}
p{margin:0 0 12px}
.lede{color:var(--text-2);margin:0 0 4px;max-width:72ch}
.meta{color:var(--text-3);font-size:13px}
.sub{color:var(--text-2);font-size:14px;margin:0 0 16px;max-width:76ch}
code{font:13px/1.5 ui-monospace,Consolas,"Cascadia Mono",monospace;background:var(--surface-2);padding:1px 5px;border-radius:5px}
pre{font:13px/1.5 ui-monospace,Consolas,"Cascadia Mono",monospace;background:var(--surface-2);padding:10px 12px;border-radius:var(--radius);overflow-x:auto;margin:6px 0 10px}
pre code{background:none;padding:0}
a{color:var(--accent)}
.chip{display:inline-block;font-size:12px;line-height:1.5;padding:1px 8px;border-radius:var(--radius);white-space:nowrap;vertical-align:1px;border:1px solid transparent}
.s-done{background:var(--good-bg);color:var(--good);border-color:var(--good-bd)}
.s-now{background:var(--accent);color:#fff;border-color:var(--accent)}
.s-next{background:var(--accent-bg);color:var(--accent);border-color:var(--accent-bd)}
.s-plan{background:var(--surface-2);color:var(--text-2);border-color:var(--border)}
.s-bad{background:var(--danger-bg);color:var(--danger);border-color:var(--danger-bd)}
.s-warn{background:var(--warn-bg);color:var(--warn);border-color:var(--warn-bd)}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,180px),1fr));gap:12px;margin:20px 0 16px}
.stat{background:var(--surface-2);border-radius:var(--radius);padding:12px 14px}
.stat .k{font-size:13px;color:var(--text-2)} .stat .v{font-size:26px;font-weight:600;line-height:1.2} .stat .d{font-size:13px;color:var(--text-3)}
.card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:14px 16px;min-width:0}
.card p{font-size:14px;color:var(--text-2);margin:0 0 6px}
.card ul,.card ol{margin:6px 0 0;padding-left:20px;font-size:14px;color:var(--text-2)}
.card li{margin:0 0 4px}
.band{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr));gap:12px}
.alert{border:1px solid var(--warn-bd);background:var(--warn-bg);color:var(--warn);border-radius:12px;padding:12px 16px;margin:16px 0}
.alert ul{margin:4px 0 0;padding-left:20px;font-size:14px}
.ok{border:1px solid var(--good-bd);background:var(--good-bg);color:var(--good);border-radius:12px;padding:10px 16px;margin:16px 0;font-size:14px}
.check{list-style:none;padding:0;margin:0}
.check li{display:grid;grid-template-columns:22px minmax(0,1fr);gap:8px;padding:7px 0;border-top:1px solid var(--border);font-size:14px;color:var(--text-2)}
.check li:first-child{border-top:0}
.check .box{display:inline-block;width:16px;height:16px;border:1.5px solid var(--border-2);border-radius:4px;margin-top:4px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,150px),1fr));gap:10px}
.node{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:10px 12px;min-width:0;border-top-width:4px}
.node.s-done{border-top-color:var(--good-bd);background:var(--surface);color:var(--text)}
.node.s-now{border-top-color:var(--accent);background:var(--surface);color:var(--text)}
.node.s-next{border-top-color:var(--accent-bd);background:var(--surface);color:var(--text)}
.node.s-plan{border-top-color:var(--border-2);background:var(--surface);color:var(--text)}
.node.s-bad{border-top-color:var(--danger-bd);background:var(--surface);color:var(--text)}
.node.s-warn{border-top-color:var(--warn-bd);background:var(--surface);color:var(--text)}
.node .id{font-weight:600;font-size:15px}
.node .t{font-size:13px;color:var(--text-2);margin:2px 0 6px;line-height:1.35}
.node .f{font-size:12px;color:var(--text-3);margin-top:6px;line-height:1.4}
.tablewrap{overflow-x:auto;border:1px solid var(--border);border-radius:12px;background:var(--surface)}
table{border-collapse:collapse;width:100%;font-size:14px;min-width:640px}
th,td{text-align:left;padding:8px 12px;border-top:1px solid var(--border);vertical-align:top}
thead th{border-top:0;font-weight:600;background:var(--surface-2)}
td{color:var(--text-2)} td:first-child{color:var(--text);white-space:nowrap}
tr.up td{background:var(--accent-bg)}
.num{text-align:right;white-space:nowrap}
.log{border-top:1px solid var(--border);padding:14px 0;overflow-wrap:anywhere}
.log h3{display:flex;flex-wrap:wrap;gap:8px;align-items:baseline}
.log .when{color:var(--text-3);font-weight:400;font-size:13px}
.log .cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,260px),1fr));gap:4px 20px}
.log ul{margin:4px 0 6px;padding-left:20px;font-size:14px;color:var(--text-2)}
.log .k{font-size:12px;color:var(--text-3);text-transform:uppercase;letter-spacing:.04em}
.log p{font-size:14px;color:var(--text-2);margin:4px 0 0}
.note{font-size:13px;color:var(--text-3);margin-top:10px}
.two{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr));gap:12px}
.cvwrap{overflow-x:auto}
.cv{display:block;width:100%;min-width:720px;height:auto}
.cv .gl{stroke:var(--border);stroke-width:1}
.cv .ax{fill:var(--text-3);font-size:13px}
.cv .lbl{fill:var(--text-2);font-size:14px;font-weight:600}
.cv .ln{fill:none;stroke:var(--accent);stroke-width:2;stroke-linejoin:round}
.cv .dot{fill:var(--accent);stroke:var(--surface);stroke-width:2}
.cv .hit{fill:transparent}
.cv g:hover .dot{stroke:var(--text)}
.seg{display:flex;gap:2px;height:26px;margin:8px 0}
.seg .sg{display:flex;align-items:center;justify-content:center;min-width:8px;font-size:12px;border:1px solid;overflow:hidden}
.seg .sg:first-child{border-radius:4px 0 0 4px} .seg .sg:last-child{border-radius:0 4px 4px 0}
.hist{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,230px),1fr));gap:4px 16px;margin-top:8px}
.hrow{display:flex;gap:8px;align-items:center;font-size:13px;min-width:0}
.hrow .hl{flex:0 0 44px;color:var(--text);font-weight:600}
.hsq{display:flex;gap:2px;flex-wrap:wrap}
.sq{display:inline-flex;width:16px;height:16px;align-items:center;justify-content:center;font-size:10px;border:1px solid;border-radius:4px}
.rota{position:relative;height:30px;margin:10px 0 2px;background:var(--surface-2);border-radius:6px}
.rs{position:absolute;top:0;bottom:0;display:flex;align-items:center;justify-content:center;font-size:12px;border:1px solid var(--border-2);border-radius:6px;overflow:hidden;color:var(--text-2);background:var(--surface);white-space:nowrap}
.rs.cur{background:var(--accent-bg);border-color:var(--accent);color:var(--accent);font-weight:600}
.rs.past{background:var(--surface-2);border-color:var(--border)}
.rs.next{border-style:dashed}
.rnow{position:absolute;top:-5px;bottom:-5px;width:2px;margin-left:-1px;background:var(--text);border-radius:1px}
.raxis{position:relative;height:18px;font-size:11px;color:var(--text-3);margin-bottom:6px}
.raxis span{position:absolute;transform:translateX(-50%)}
.raxis span:first-child{transform:none} .raxis span:last-child{transform:translateX(-100%)}
.badges{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,320px),1fr));gap:12px}
.badge{display:grid;grid-template-columns:88px minmax(0,1fr);gap:12px;background:var(--surface);border:1px solid var(--border);border-left-width:4px;border-radius:12px;padding:12px;min-width:0}
.badge.mgr{border-left-color:var(--accent)}
.badge h3{margin:0 0 4px;overflow-wrap:anywhere}
.badge p{font-size:14px;color:var(--text-2);margin:4px 0 0;overflow-wrap:anywhere}
.plate svg{display:block;width:88px;height:88px;border-radius:4px}
.bar{height:8px;background:var(--surface-2);border-radius:4px;overflow:hidden;margin:8px 0 2px}
.bar span{display:block;height:100%;background:var(--accent);border-radius:4px}
.card .notes{list-style:none;padding:0;margin:0}
.card .notes li{margin:0;padding:8px 0;border-top:1px solid var(--border);font-size:14px;color:var(--text-2)}
.card .notes li:first-child{border-top:0}
td ul.tl{margin:0;padding-left:18px} td ul.tl li{margin:0 0 4px}
.wide{margin-top:12px}
.toc{display:flex;flex-wrap:wrap;gap:4px 14px;font-size:13px;margin:12px 0 0;padding:8px 0;border-top:1px solid var(--border);border-bottom:1px solid var(--border)}
.toc a{text-decoration:none} .toc a:hover{text-decoration:underline}
.attn{border-left:4px solid var(--accent);margin:0 0 16px}
.card .attnl{list-style:none;padding:0;margin:6px 0 0}
.card .attnl li{padding:5px 0;border-top:1px solid var(--border);overflow-wrap:anywhere}
.card .attnl li:first-child{border-top:0}
.attnl a{color:var(--text-2);text-decoration:none} .attnl a:hover{text-decoration:underline}
.card .vml{list-style:none;padding:0;margin:6px 0 0} .card .vml li{margin:0 0 10px;overflow-wrap:anywhere}
details.fold{margin-top:10px}
details.fold>summary{cursor:pointer;font-size:14px;color:var(--accent);padding:6px 0}
details.fold[open]>summary{margin-bottom:8px}
.cv.usg{min-width:0}
.cv .stopl{stroke:var(--danger-bd);stroke-width:1.5;stroke-dasharray:5 4}
@media (max-width:640px){ h1{font-size:24px} }
"""


def block_minutes(b):
    m = re.match(r"\s*(\d{1,2}):(\d{2})\s*[–-]\s*(\d{1,2}):(\d{2})", b.get("time", ""))
    if not m:
        return 60
    return (int(m[3]) * 60 + int(m[4]) - int(m[1]) * 60 - int(m[2])) % 1440 or 60


def shift_bar(blocks):
    """This shift's blocks as one bar, each segment as long as its planned time, filled by its status."""
    if not blocks:
        return '<p class="meta">No shift plan.</p>'
    segs, mins = [], Counter()
    for b in blocks:
        st = b.get("status", "pending")
        cls, glyph, label = STATUS.get(st, STATUS["pending"])
        m = block_minutes(b)
        mins[st] += m
        segs.append(f'<span class="sg {cls}" style="flex:{m}" title="{esc(b.get("time", ""))} · {esc(label)} · '
                    f'{esc(b.get("title", "")[:140])}"><span aria-hidden="true">{glyph}</span></span>')
    done = sum(1 for b in blocks if b.get("status") in ("done", "skipped"))
    total = sum(mins.values())
    legend = " ".join(f"{chip(st)} {m / 60:.1f} h" for st, m in mins.items())
    return (f'<div class="seg" role="img" aria-label="{done} of {len(blocks)} blocks done or skipped">{"".join(segs)}</div>'
            f'<p class="meta">{done} of {len(blocks)} blocks done or skipped · {(mins["done"] + mins["skipped"]) / 60:.1f} of {total / 60:.1f} planned hours</p>'
            f'<p class="meta">{legend}</p>')


def svg_passes(lanes, now):
    """Gym lanes with a first PASS, cumulative over time: one step line, a dot per lane carrying its tooltip."""
    pts = sorted((l["first_pass"], l["lane"], l) for l in lanes.values() if l["first_pass"])
    if not pts:
        return '<p class="meta">No lane has a PASS yet.</p>'
    W, H, L, R, T, B = 960, 240, 40, 84, 12, 28
    day0 = local_dt(pts[0][0]).replace(hour=0, minute=0, second=0, microsecond=0)
    days = (now.date() - day0.date()).days + 1
    t0, t1 = day0.timestamp(), (day0 + dt.timedelta(days=days)).timestamp()
    ymax = max(5, -(-len(pts) // 5) * 5)

    def x(t):
        return L + (t - t0) / (t1 - t0) * (W - L - R)

    def y(v):
        return T + (1 - v / ymax) * (H - T - B)

    g = [f'<line class="gl" x1="{L}" x2="{W - R}" y1="{y(v):.1f}" y2="{y(v):.1f}"/>'
         f'<text class="ax" x="{L - 6}" y="{y(v) + 4:.1f}" text-anchor="end">{v}</text>' for v in range(0, ymax + 1, 5)]
    for i in range(0, days + 1, max(1, -(-days // 8))):
        t = day0 + dt.timedelta(days=i)
        g.append(f'<text class="ax" x="{x(t.timestamp()):.1f}" y="{H - 8}" text-anchor="middle">{t:%m-%d}</text>')
    path, dots = [f"M{x(t0):.1f},{y(0):.1f}"], []
    for i, (ts, name, l) in enumerate(pts, 1):
        path.append(f"H{x(ts):.1f}V{y(i):.1f}")
        tip = f"{name} first PASS {local_dt(ts):%Y-%m-%d %H:%M}" + (f" · {l['checkpoint']}" if l["checkpoint"] else "")
        dots.append(f'<g><title>{esc(tip)}</title><circle class="hit" cx="{x(ts):.1f}" cy="{y(i):.1f}" r="9"/>'
                    f'<circle class="dot" cx="{x(ts):.1f}" cy="{y(i):.1f}" r="4"/></g>')
    nx = x(now.timestamp())
    path.append(f"H{nx:.1f}")
    return (f'<div class="cvwrap"><svg class="cv" viewBox="0 0 {W} {H}" role="img" '
            f'aria-label="{len(pts)} lanes have passed, the first on {local_dt(pts[0][0]):%Y-%m-%d}">'
            + "".join(g) + f'<path class="ln" d="{"".join(path)}"/>' + "".join(dots)
            + f'<text class="lbl" x="{nx + 6:.1f}" y="{y(len(pts)) + 4:.1f}">{len(pts)} lanes</text></svg></div>')


def lane_history(lanes):
    """The last twelve verdicts of every lane, oldest first, each a square with its glyph and a tooltip."""
    rows = []
    for l in lanes.values():
        sq = []
        for v, run_id, n, ts in l["history"]:
            cls, glyph = VERDICT.get(v, ("s-warn", "?"))
            when = f" · {local_dt(ts):%Y-%m-%d %H:%M}" if ts else ""
            sq.append(f'<span class="sq {cls}" title="{esc(l["lane"])} {esc(v)}{f" n={n}" if n is not None else ""} · '
                      f'{esc(run_id or "")}{when}"><span aria-hidden="true">{glyph}</span></span>')
        rows.append(f'<div class="hrow"><span class="hl">{esc(l["lane"])}</span>'
                    f'<span class="hsq">{"".join(sq) or "<span class=meta>no run</span>"}</span></div>')
    key = " ".join(f'<span class="sq {VERDICT[v][0]}" aria-hidden="true">{VERDICT[v][1]}</span> {v.lower()}'
                   for v in ("PASS", "MARGINAL", "FAIL", "VOID"))
    return f'<div class="hist">{"".join(rows)}</div><p class="meta" style="margin-top:8px">{key}</p>'


def rota_today(state, crew, now):
    """Today's 24 hours as the rota's slots: which shift each ran, its manager, crew-hours, and a now marker."""
    rota = state.get("rota") or {}
    slots = sorted(rota.get("slots") or default_slots(), key=lambda s: s["start"])
    days = {e.get("date"): e for e in rota.get("days", []) if isinstance(e, dict)}
    day0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day1 = day0 + dt.timedelta(days=1)

    def at(s):
        h, m = map(int, s["start"].split(":"))
        return day0 + dt.timedelta(hours=h, minutes=m)

    # before the first start, the last slot of yesterday is still running
    segs = [(day0, at(slots[0]), slots[-1]["id"], (day0 - dt.timedelta(days=1)).date())]
    segs += [(at(s), at(slots[i + 1]) if i + 1 < len(slots) else day1, s["id"], day0.date()) for i, s in enumerate(slots)]
    ivals = crew_intervals(crew, now)
    bar, items = [], []
    for s, e, sid, date in segs:
        if e <= s:
            continue
        entry = (days.get(date.isoformat()) or {}).get(sid) or {}
        hours = sum(max(0.0, min(e.timestamp(), b) - max(s.timestamp(), a)) for _, a, b in ivals) / 3600
        state_ = "cur" if s <= now < e else "past" if e <= now else "next"
        span = f"{s:%H:%M}–{'24:00' if e == day1 else f'{e:%H:%M}'}"
        what = entry.get("shift") or "no shift on the rota"
        rr = next((x.get("rr") for x in slots if x["id"] == sid), None)
        left, width = (s - day0).total_seconds() / 864, (e - s).total_seconds() / 864
        bar.append(f'<div class="rs {state_}" style="left:calc({left:.3f}% + 1px);width:calc({width:.3f}% - 2px)" '
                   f'title="{esc(sid)} {span} · {esc(what)}"><span>{esc(sid)}</span></div>')
        since = f" (from {date:%m-%d})" if date != day0.date() else ""
        items.append(f'<li><strong>{esc(sid)}</strong> {span}{since}{" · <strong>now</strong>" if state_ == "cur" else ""} · '
                     f'{esc(what)} · manager {esc(entry.get("manager") or "—")} · crew {hours:.1f} h'
                     + (f' · research and review {esc(rr)}' if rr else "")
                     + (f' · <span class="meta">{esc(entry["note"])}</span>' if entry.get("note") else "") + "</li>")
    nowp = (now - day0).total_seconds() / 864
    axis = "".join(f'<span style="left:{h / 24 * 100:.3f}%">{h:02d}</span>' for h in (0, 6, 12, 18, 24))
    return (f'<div class="rota" role="img" aria-label="today\'s rota; now {now:%H:%M}">{"".join(bar)}'
            f'<div class="rnow" style="left:{nowp:.3f}%" title="now {now:%H:%M}"></div></div>'
            f'<div class="raxis">{axis}</div><ul>{"".join(items)}</ul>')


def crew_chip(status):
    cls, glyph, label = CREW.get(status, ("s-plan", "?", status.lower()))
    return f'<span class="chip {cls}"><span aria-hidden="true">{glyph}</span> {esc(label)}</span>'


def hhmm_rel(ts, now):
    d = local_dt(ts)
    when = f"{d:%H:%M}" if d.date() == now.date() else f"{d:%m-%d %H:%M}"
    m = round((ts - now.timestamp()) / 60)
    rel = f"in {m} min" if 0 <= m < 90 else f"in {m / 60:.1f} h" if m >= 90 else f"{-m} min late" if m > -90 else f"{-m / 60:.1f} h late"
    return f"{when} ({rel})"


def crew_html(state, crew, now):
    """A badge tile per agent on the clock (the manager first), then who clocked out in this slot."""
    if not crew["badges"]:
        return (f'<div class="card"><p>No badge has been issued yet. The manager (<code>/{esc(P.skill("manager"))}</code>) appoints '
                f'itself and hires the crew with <code>{esc(OFFICE)}</code>; each employee clocks in with its badge line.</p>'
                f'<p class="meta">Crew office: {esc(crew["dir"] or P.rel("office"))}</p></div>')
    slot, s0, _ = crew["slot"]
    live = sorted((b for b in crew["badges"] if b["on"] or b["status"] == "HIRED"),
                  key=lambda b: (b["role"] not in TOP_ROLES, b["id"]))
    tiles = []
    for b in live:
        facts_ = []
        if b["in_at"] and b["on"]:
            facts_.append(f"in {local_dt(b['in_at']):%H:%M}")
        if b["heard"]:
            facts_.append(f"heard {local_dt(b['heard']):%H:%M}")
        if b.get("session"):
            facts_.append(f"session {b['session']}")
        for k, label in (("lane", "lane"), ("vmdir", "seat")):
            if b.get(k):
                facts_.append(f"{label} {b[k]}")
        finish = (f"finish ~{hhmm_rel(b['eta'], now)}" if b["eta"] else
                  f"issued {local_dt(b['issued']):%H:%M}, not clocked in")
        bar = (f'<div class="bar" role="img" aria-label="{b["pct"]}% done"><span style="width:{b["pct"]}%"></span></div>'
               f'<p class="meta">{b["pct"]}% · {esc(finish)}</p>') if b["role"] not in TOP_ROLES else \
              f'<p class="meta">{esc(b.get("shift", ""))} · {esc(b.get("slot", ""))} slot</p>'
        tiles.append(
            f'<div class="badge{" mgr" if b["role"] in TOP_ROLES else ""}"><div class="plate">{b["svg"]}</div><div>'
            f'<h3>{esc(b["id"])} · {esc(b["name"])}</h3>'
            f'<div>{crew_chip(b["status"])} <span class="meta">{esc(b["role"].lower())} · {esc(b["kind"].lower())}</span></div>'
            f'<p>{esc(b.get("job", ""))}</p>{bar}'
            f'<p class="meta">{esc(" · ".join(facts_))}</p>'
            + (f'<p class="meta">“{esc(b["note"])}”</p>' if b["note"] else "") + "</div></div>")
    gone = [b for b in crew["badges"] if b["status"] == "OUT" and (b["out_at"] or 0) >= s0]
    rows = "".join(f"<tr><td>{esc(b['id'])}</td><td>{esc(b['name'])}</td><td>{esc(b['role'].lower())}</td>"
                   f"<td>{esc(b['result'] or '')}</td><td>{local_dt(b['out_at']):%H:%M}</td><td class=\"num\">{b['hours']:.1f}</td>"
                   f"<td>{esc(b['note'])}</td></tr>" for b in gone)
    out_tbl = ('<h3 style="margin-top:16px">Clocked out this slot</h3><div class="tablewrap"><table><thead><tr><th>Badge</th>'
               '<th>Name</th><th>Role</th><th>Result</th><th>Out</th><th class="num">Hours</th><th>Note</th></tr></thead>'
               f'<tbody>{rows}</tbody></table></div>') if gone else ""
    return (f'<div class="badges">{"".join(tiles) or "<div class=card><p>Nobody is on the clock.</p></div>"}</div>{out_tbl}'
            f'<p class="note">Crew office {esc(crew["dir"])}; {slot} slot. A badge is its QR plate; the line it holds is the punch card.</p>')


def fold(items, keep, more):
    """The first `keep` items as they are, the rest inside a closed <details> whose summary is `more` (with the count)."""
    if len(items) <= keep:
        return "".join(items), ""
    return "".join(items[:keep]), (f'<details class="fold"><summary>{esc(more.format(n=len(items) - keep))}</summary>'
                                   f'{"".join(items[keep:])}</details>')


def attention_html(items):
    if not items:
        return '<div class="ok">✓ Nothing is waiting on the manager or the user.</div>'
    rows = "".join(f'<li><span class="chip {cls}">{esc(group)}</span> <a href="#{anchor}">{esc(text)}</a></li>'
                   for cls, group, text, anchor in items)
    return f'<div class="card attn"><h3>Needs attention ({len(items)})</h3><ul class="attnl">{rows}</ul></div>'


def resource_html(res, now):
    """One line per seat of the shared resource: free, or who holds it, for how long of its limit; then the waiters."""
    if not res["seats"]:
        return '<p class="meta">No resource queue in the crew office.</p>'
    rows = []
    for rec in res["seats"]:
        h = rec["hold"]
        if not h:
            rows.append(f'<li><strong>{esc(rec["seat"])}</strong> <span class="chip s-done">free</span>'
                        + (f'<br><span class="meta">last: {esc(rec["last"][:200])}</span>' if rec["last"] else "") + "</li>")
            continue
        age = max(0, now.timestamp() - h["since"])
        pct = min(100, round(age / h["max"] * 100))
        rows.append(f'<li><strong>{esc(rec["seat"])}</strong> '
                    f'<span class="chip {"s-bad" if h["overdue"] else "s-now"}">{"overdue" if h["overdue"] else "held"}</span> '
                    f'{esc(h["id"])}{" · every seat" if h["all"] else ""} · since {local_dt(h["since"]):%H:%M} · '
                    f'{int(age) // 60} of {h["max"] // 60} min'
                    f'<div class="bar" role="img" aria-label="{pct}% of the hold used"><span style="width:{pct}%"></span></div>'
                    f'<span class="meta">{esc(h["job"][:220])}</span></li>')
    q = "".join(f'<li>{esc(e.get("id", "?"))} · prio {esc(e.get("prio", "?"))} · {esc(str(e.get("job", ""))[:160])}</li>'
                for e in res["queue"])
    return (f'<ul class="vml">{"".join(rows)}</ul>'
            f'<p class="meta">{len(res["queue"])} waiting in the queue</p>' + (f"<ul>{q}</ul>" if q else ""))


def decisions_html(state):
    """The decisions register as a table: the open ones (they wait on the user) first, the rest folded."""
    decs = [d for d in state.get("decisions") or [] if isinstance(d, dict)]
    head = ('<thead><tr><th>Id</th><th>Status</th><th>Asked</th><th>Question</th><th>Options</th><th>Needed before</th>'
            '<th>Answer</th><th>Brief</th></tr></thead>')

    def row(d):
        opts = "".join(f"<li>{esc(o)}</li>" for o in d.get("options") or [])
        rec = f'<br><span class="meta">Recommended: {esc(d["recommend"])}</span>' if d.get("recommend") else ""
        answer = esc(d.get("answer") or "")
        if d.get("answered"):
            answer += f'<br><span class="meta">{esc(d["answered"])}</span>'
        if d.get("status") == "withdrawn":
            answer = (f'<span class="meta">withdrawn{" " + esc(d["withdrawn"]) if d.get("withdrawn") else ""}'
                      f'{": " + esc(d["note"]) if d.get("note") else ""}</span>')
        brief_ = f'<a href="{page_rel(ROOT / d["brief"])}">brief</a>' if d.get("brief") else "—"
        return (f"<tr><td>{esc(d.get('id'))}</td><td>{chip(d.get('status', 'open'))}</td>"
                f"<td style=\"white-space:nowrap\">{esc(str(d.get('asked', ''))[:16].replace('T', ' '))}<br>"
                f"<span class=\"meta\">{esc(d.get('by', ''))}</span></td><td>{esc(d.get('question', ''))}</td>"
                f"<td>{f'<ul class=tl>{opts}</ul>' if opts else '—'}{rec}</td><td>{esc(d.get('needed_before') or '—')}</td>"
                f"<td>{answer or '—'}</td><td>{brief_}</td></tr>")

    open_rows = "".join(row(d) for d in decs if d.get("status", "open") == "open")
    closed = [row(d) for d in decs if d.get("status", "open") != "open"]
    more = (f'<details class="fold"><summary>{len(closed)} answered or withdrawn</summary><div class="tablewrap"><table>'
            f'{head}<tbody>{"".join(closed)}</tbody></table></div></details>') if closed else ""
    return (f'<div class="tablewrap"><table>\n{head}\n<tbody>'
            + (open_rows or '<tr><td colspan="8">Nothing waits on the user.</td></tr>') + f'</tbody>\n</table></div>\n{more}')


def page_rel(p):
    """A file's link as the map writes it: relative to the map's own folder (whole when it cannot be)."""
    if not p:
        return ""
    try:
        return esc(Path(os.path.relpath(p, OUT.parent)).as_posix())
    except ValueError:
        return esc(Path(p).as_posix())


def runs_html(state, lanes, now):
    """The lanes graded in the last 24 hours as a table: a sweep, or a day's counted runs, at a glance."""
    recent = recent_runs(lanes, now)
    if not recent:
        return '<p class="meta">No lane was graded in the last 24 hours.</p>'
    counts = Counter(l["verdict"] for l in recent)
    rows = []
    for l in recent:
        f = failure_for(state, l) if l["verdict"] in NOT_PASSING else None
        change = (f'<span class="chip s-bad">was {esc(l["prev"])}</span>' if l["prev"] == "PASS" and l["verdict"] != "PASS"
                  else f'<span class="chip s-done">was {esc(l["prev"])}</span>' if l["verdict"] == "PASS" and l["prev"] not in (None, "PASS")
                  else '<span class="meta">same</span>' if l["prev"] else '<span class="meta">first run</span>')
        filed = (f'{esc(f["id"])} {chip(f.get("status", "open"))}' if f else
                 '<span class="chip s-bad">not filed</span>' if l["verdict"] in NOT_PASSING else "—")
        rows.append(f'<tr><td>{esc(l["lane"])}</td><td>{verdict_chip(l["verdict"])}</td>'
                    f'<td class="num">{esc(l["n"]) if l["n"] is not None else "—"}</td><td>{change}</td>'
                    f'<td>{l["when"]:%H:%M}<br><span class="meta">{esc(l["run_id"] or "")}</span></td><td>{filed}</td></tr>')
    head = " · ".join(f"{c} {v}" for v, c in counts.most_common())
    return (f'<p>{len(recent)} lane{"s" if len(recent) != 1 else ""} graded since {recent[0]["when"]:%m-%d %H:%M}: {esc(head)}</p>'
            '<div class="tablewrap"><table><thead><tr><th>Lane</th><th>Latest</th><th class="num">n</th><th>Against the run before</th>'
            f'<th>Graded</th><th>Failure entry</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>')


def usage_svg(usage, now):
    """The week's usage points as a line against the stop line; the points are typed in by the manager's rounds."""
    pts = [(t, v) for t, v, _ in usage_points(usage)[0]]
    if not pts:
        return ('<p class="meta">No usage point recorded. The manager records one each round: '
                f'<code>{esc(BOARD)} usage 12</code></p>')
    W, H, L, R, T, B = 460, 150, 34, 12, 8, 22
    reset = parse_or_none(usage.get("reset"))
    # the chart ends at the reset, or now and the last point once a reset has passed without a new --reset
    t1 = max(reset.timestamp() if reset else 0, now.timestamp(), pts[-1][0])
    t0 = t1 - 7 * 86400
    pts = [p for p in pts if p[0] >= t0] or pts[-1:]  # one week before the chart's end; the latest point always shows
    t0 = min(t0, pts[0][0])
    stop = usage_stop(usage)

    def x(t):
        return L + (t - t0) / max(1.0, t1 - t0) * (W - L - R)

    def y(v):
        return T + (1 - min(100.0, v) / 100) * (H - T - B)

    g = [f'<line class="gl" x1="{L}" x2="{W - R}" y1="{y(v):.1f}" y2="{y(v):.1f}"/>'
         f'<text class="ax" x="{L - 6}" y="{y(v) + 4:.1f}" text-anchor="end">{v}</text>' for v in (0, 50, 100)]
    if stop is not None:
        g.append(f'<line class="stopl" x1="{L}" x2="{W - R}" y1="{y(stop):.1f}" y2="{y(stop):.1f}"><title>stop at {stop}%</title></line>')
    path = "M" + " L".join(f"{x(t):.1f},{y(v):.1f}" for t, v in pts)
    lt, lv = pts[-1]
    return (f'<div class="cvwrap"><svg class="cv usg" viewBox="0 0 {W} {H}" role="img" aria-label="weekly usage {lv:g}% at '
            f'{local_dt(lt):%m-%d %H:%M}">' + "".join(g) + f'<path class="ln" d="{path}"/>'
            f'<circle class="dot" cx="{x(lt):.1f}" cy="{y(lv):.1f}" r="4"/>'
            f'<text class="ax" x="{L}" y="{H - 6}">{local_dt(t0):%m-%d}</text>'
            f'<text class="ax" x="{W - R}" y="{H - 6}" text-anchor="end">{local_dt(t1):%m-%d %H:%M}</text></svg></div>'
            f'<p class="meta">{lv:g}% at {local_dt(lt):%m-%d %H:%M}'
            + (f' · stop at {stop:g}%' if stop is not None else "")
            + ((f' · resets {local_dt(reset.timestamp()):%a %m-%d %H:%M}' if reset.timestamp() > now.timestamp() else
                f' · the reset {local_dt(reset.timestamp()):%a %m-%d %H:%M} has passed; record the next one with --reset')
               if reset else "")
            + "</p>")


def render(state, lanes, facts, warns, now, crew):
    S = state
    res = read_resource(crew, now)
    attn = attention(S, lanes, crew, res, now)
    usage = S.get("usage") or {}
    u_stop = usage_stop(usage)
    u_last = (usage_points(usage)[0] or [(0, 0, None)])[-1][2]  # the last point that parses
    milestones, phases = S.get("milestones") or [], S.get("phases") or []
    m_done = sum(1 for m in milestones if m.get("status") == "done")
    p_done = sum(1 for p in phases if p.get("status") == "done")
    ran = [l for l in lanes.values() if l["verdict"]]
    l_pass = sum(1 for l in ran if l["verdict"] == "PASS")
    nxt = next((m for m in milestones if m.get("status") in ("in-progress", "next")), None)
    shift = S.get("shift", {})
    blocks = shift.get("blocks", [])
    up = next((i for i, b in enumerate(blocks) if b.get("status") in ("pending", "in-progress", "partial")), None)
    reqs, stages = read_roadmap()
    by_p = {p: Counter(s for q, s in reqs.values() if q == p) for p in TIERS}
    p0_met = sum(by_p[TOP][s] for s in REQ_MET)
    stale, unnamed = pass_lanes(lanes)
    p0_stale = sum(1 for r in stale if r["p"] == TOP)
    slots_n = len((S.get("rota") or {}).get("slots") or default_slots())
    span = (lambda xs: f"{esc(xs[0].get('id'))} to {esc(xs[-1].get('id'))}" if len(xs) > 1 else
            esc(xs[0].get("id")) if xs else "none yet")
    roadmap_link = f'<a href="{page_rel(ROADMAP)}">{esc(ROADMAP_REL)}</a>'
    phases_stat = (f'<div class="stat"><div class="k">{esc(PHASES_TITLE)}</div><div class="v">{p_done} / {len(phases)}</div>'
                   f'<div class="d">{span(phases)}</div></div>') if phases else ""
    resource_card = (f'<div class="card" id="resource"><h3>{esc(RES)}: seats</h3><p>Who holds each seat of the shared '
                     f'resource, from the crew office\'s queue files at build time.</p>{resource_html(res, now)}</div>'
                     ) if has_resource() else ""
    stale_html = ""
    if stale or unnamed:
        stale_html = ('<div class="card" style="margin-bottom:12px"><h3>PASS rows to recheck '
                      f'<span class="chip s-warn"><span aria-hidden="true">!</span> not lane-backed now</span></h3><p>A PASS in {esc(ROADMAP_REL)} counts as met as typed; these rows name a lane '
                      'whose newest counted run is not PASS, or name no lane at all.</p><ul>'
                      + "".join(f"<li>{esc(stale_text(r))} ({esc(r['p'])})</li>" for r in stale)
                      + "".join(f"<li>{esc(r['id'])} ({esc(r['p'])}) is marked PASS with no lane named</li>" for r in unnamed)
                      + "</ul></div>")

    def fact_line(lane_name):
        l = lanes.get(lane_name)
        if not l or not l["verdict"]:
            bits = []
            if l and l["contract"]:
                bits.append("contract draft" if l["draft"] else "contract")
            if l and l["prereg"]:
                bits.append("prereg")
            return f"{esc(lane_name)} · " + (", ".join(bits) if bits else "no lane yet")
        n = f" n={l['n']}" if l["n"] is not None else ""
        when = f" · {l['when']:%Y-%m-%d}" if l["when"] else ""
        return f"{esc(lane_name)} {esc(l['verdict'])}{n}{when}"

    def nodes(items, with_ms=False):
        out = []
        for it in items:
            cls = STATUS.get(it["status"], STATUS["planned"])[0]
            sub = f"<div class=\"t\">{esc(it['title'])}</div>"
            ms = f" · {esc(it['milestone'])}" if with_ms and it.get("milestone") else ""
            facts_ = fact_line(it["lane"]) if it.get("lane") else "no lane yet"
            note = f"<div class=\"f\">{esc(it['note'])}</div>" if it.get("note") else ""
            out.append(f'<div class="node {cls}"><div class="id">{esc(it["id"])}{ms} {chip(it["status"])}</div>{sub}'
                       f'<div class="f">{facts_}</div>{note}</div>')
        return "\n".join(out)

    rel = page_rel

    lane_rows = []
    for l in lanes.values():
        counts = ", ".join(f"{v} {c}" for v, c in sorted(l["counts"].items(), key=lambda kv: -kv[1])) or "—"
        links = []
        if l["grade"]:
            links.append(f'<a href="{rel(l["grade"])}">grade</a>')
        if l["chart"]:
            links.append(f'<a href="{rel(l["chart"])}">chart</a>')
        if l["prereg"]:
            links.append(f'<a href="{rel(l["prereg"])}">prereg</a>')
        if l["contract"]:
            links.append(f'<a href="{rel(l["contract"])}">contract{" (draft)" if l["draft"] else ""}</a>')
        when = f"{l['when']:%Y-%m-%d %H:%M}" if l["when"] else "—"
        n = esc(l["n"]) if l["n"] is not None else "—"
        lane_rows.append(f"<tr><td>{esc(l['lane'])}</td><td>{esc(l['checkpoint'])}</td><td>{verdict_chip(l['verdict'])}</td>"
                         f"<td class=\"num\">{n}</td><td>{when}<br><span class=\"meta\">{esc(l['run_id'] or '')}</span></td>"
                         f"<td class=\"num\">{l['runs']}</td><td>{esc(counts)}</td><td>{' · '.join(links) or '—'}</td></tr>")

    def block_table(blocks_, up_):
        rows = []
        for i, b in enumerate(blocks_):
            st = b.get("status", "pending")
            row_cls = ' class="up"' if i == up_ else ""
            label = chip(st) + (' <span class="chip s-next"><span aria-hidden="true">→</span> up next</span>' if i == up_ and st == "pending" else "")
            rows.append(f"<tr{row_cls}><td>{esc(b.get('time',''))}</td><td>{esc(b.get('title',''))}</td>"
                        f"<td>{esc(b.get('done_when',''))}</td><td>{label}</td></tr>")
        return ('<div class="tablewrap"><table>\n<thead><tr><th>Time</th><th>Block</th><th>Done when</th><th>Status</th></tr></thead>\n'
                f'<tbody>{"".join(rows)}</tbody>\n</table></div>')

    queue = S.get("queue", [])
    queue_html = []
    for i, q in enumerate(queue, 2):
        before = "".join(f"<li>{esc(x)}</li>" for x in q.get("before_start", []))
        qb = "".join(f"<li><strong>{esc(b['what'])}</strong>" +
                     (f"<br><span class=\"meta\">Owner: {esc(b['owner'])}</span>" if b.get("owner") else "") + "</li>"
                     for b in q.get("blockers", []))
        queue_html.append(f'<div class="card" style="margin-bottom:12px"><h3>Shift {i} · {esc(q.get("title", ""))}</h3>'
                          f'<p class="meta">{esc(q.get("when", ""))} · id {esc(q.get("id", ""))}</p>'
                          f'<h3>Before the first block</h3><ul>{before or "<li>—</li>"}</ul>'
                          f'<div style="margin:10px 0">{block_table(q.get("blocks", []), None)}</div>'
                          f'<h3>Blockers of this shift</h3><ul>{qb or "<li>None recorded.</li>"}</ul></div>')

    warn_html = ("<div class=\"alert\"><strong>Before trusting this map:</strong><ul>" +
                 "".join(f"<li>{esc(w)}</li>" for w in warns) + "</ul></div>") if warns else \
        "<div class=\"ok\">✓ The state agrees with the gym series and the git tree at build time.</div>"

    log_html = []
    for e in S.get("log", []):
        def ul(items):
            return "<ul>" + "".join(f"<li>{esc(x)}</li>" for x in items) + "</ul>" if items else "<p>—</p>"
        when = esc(e.get("date", "")) + (f" {esc(e['time'])}" if e.get("time") else "") + \
            (f" · {esc(e['slot'])} slot" if e.get("slot") else "")
        log_html.append(
            f'<div class="log"><h3>{esc(e.get("title",""))} <span class="when">{when}</span></h3>'
            f'<div class="cols"><div><div class="k">Done</div>{ul(e.get("done"))}</div>'
            f'<div><div class="k">Not done</div>{ul(e.get("not_done"))}</div>'
            f'<div><div class="k">Verdicts</div>{ul(e.get("verdicts"))}<div class="k">Commits</div>'
            f'<p>{esc(", ".join(e.get("commits", [])) or "—")}</p>'
            + (f'<div class="k">Crew</div>{ul(e["crew"])}' if e.get("crew") else "") + '</div></div>'
            f'<p><span class="k">Next</span> {esc(e.get("next",""))}</p></div>')

    def files_of(l):
        links = []
        if l and l["contract"]:
            links.append(f'<a href="{rel(l["contract"])}">contract{" (draft)" if l["draft"] else ""}</a>')
        if l and l["prereg"]:
            links.append(f'<a href="{rel(l["prereg"])}">prereg</a>')
        if l and l["grade"]:
            links.append(f'<a href="{rel(l["grade"])}">grade</a>')
        return " · ".join(links) or "—"

    cp_rows = "".join(
        f"<tr><td>{esc(cp.get('lane'))}</td><td>{esc(cp.get('milestone'))}</td><td>{esc(cp.get('shift', ''))}</td>"
        f"<td>{esc(cp.get('builder', ''))}</td><td>{esc(cp.get('grader', '')) or '<span class=meta>none yet</span>'}</td>"
        f"<td>{verdict_chip(lanes[cp['lane']]['verdict'] if cp.get('lane') in lanes else None)}</td>"
        f"<td>{files_of(lanes.get(cp.get('lane', '')))}</td><td>{esc(cp.get('note', ''))}</td></tr>"
        for cp in S.get("checkpoints", []))
    order = {"open": 0, "planned": 1, "fixed": 2, "dropped": 3}

    def fail_row(f):
        return (
            f"<tr><td>{esc(f.get('id'))}</td><td>{chip(f.get('status', 'open'))}</td><td style=\"white-space:nowrap\">{esc(f.get('at', ''))}</td>"
            f"<td>{esc(f.get('lane') or '—')}{(' ' + verdict_chip(f['verdict'])) if f.get('verdict') else ''}"
            f"{('<br><span class=meta>' + esc(f['run_id']) + '</span>') if f.get('run_id') else ''}</td>"
            f"<td>{esc(f.get('what', ''))}</td><td>{esc(f.get('plan', ''))}</td><td>{esc(f.get('owner', ''))}</td></tr>")

    fails_sorted = sorted(S.get("failures", []), key=lambda f: (order.get(f.get("status", "open"), 9), f.get("id", "")))
    fail_head = ('<thead><tr><th>Id</th><th>Status</th><th>When</th><th>Lane / run</th><th>What</th><th>Plan</th>'
                 '<th>Owner</th></tr></thead>')
    fail_rows = "".join(fail_row(f) for f in fails_sorted if f.get("status", "open") in ("open", "planned"))
    closed = [fail_row(f) for f in fails_sorted if f.get("status", "open") not in ("open", "planned")]
    fail_closed = (f'<details class="fold"><summary>{len(closed)} fixed or dropped</summary><div class="tablewrap"><table>'
                   f'{fail_head}<tbody>{"".join(closed)}</tbody></table></div></details>') if closed else ""
    new_reports = "".join(
        f"<li><strong>R{r['seq']}</strong> by {esc(r['id'])} at {local_dt(r['at']):%m-%d %H:%M}: {esc(r.get('what', ''))}"
        + (f" · {esc(r['lane'])}" if r.get("lane") else "") + (f" {verdict_chip(r['verdict'])}" if r.get("verdict") else "")
        + (f"<br><span class=\"meta\">Proposed plan: {esc(r['plan'])}</span>" if r.get("plan") else "") + "</li>"
        for r in untriaged(S, crew))
    open_fails = sum(1 for f in S.get("failures", []) if f.get("status", "open") in ("open", "planned"))
    note_items = [f'<li><span class="meta">{esc(n.get("at", ""))} · {esc(n.get("by", ""))}</span><br>{esc(n.get("text", ""))}</li>'
                  for n in S.get("notes", [])]
    notes = "".join(note_items[:6])
    notes_more = (f'<details class="fold"><summary>{len(note_items) - 6} older notes</summary><ul class="notes">'
                  f'{"".join(note_items[6:])}</ul></details>') if len(note_items) > 6 else ""
    log_top, log_more = fold(log_html, 3, "{n} older block log entries")

    def bullets(xs):
        return f'<ul class="tl">{"".join(f"<li>{esc(x)}</li>" for x in xs)}</ul>' if xs else "—"

    def rr_row(r):
        report = f'<a href="{rel(ROOT / r["report"])}">report</a>' if r.get("report") else "—"
        commit = f'<br><span class="meta">{esc(r["commit"])}</span>' if r.get("commit") else ""
        return (f"<tr><td>{esc(r.get('id'))}</td><td style=\"white-space:nowrap\">{esc(r.get('date', ''))}<br>"
                f"<span class=\"meta\">{esc(r.get('slot', ''))}</span></td><td>{chip(r.get('kind', 'review'))}</td>"
                f"<td>{esc(r.get('by', ''))}</td><td>{esc(r.get('topic', ''))}</td><td>{bullets(r.get('findings', []))}</td>"
                f"<td>{bullets(r.get('actions', []))}</td><td>{report}{commit}</td></tr>")

    # state.research_review is kept oldest first or newest first by different managers: show the highest id first
    rr_sorted = sorted(S.get("research_review", []), key=lambda r: lane_key(str(r.get("id", ""))), reverse=True)
    rr_head = ('<thead><tr><th>Id</th><th>When</th><th>Kind</th><th>By</th><th>Topic</th><th>Findings</th>'
               '<th>What it changed</th><th>Report</th></tr></thead>')
    rr_rows = "".join(rr_row(r) for r in rr_sorted[:8])
    rr_more = (f'<details class="fold"><summary>{len(rr_sorted) - 8} older entries</summary><div class="tablewrap"><table>'
               f'{rr_head}<tbody>{"".join(rr_row(r) for r in rr_sorted[8:])}</tbody></table></div></details>') if len(rr_sorted) > 8 else ""
    nav = " ".join(f'<a href="#{a}">{t}</a>' for a, t in (
        ("status", "Status"), ("runs", "Runs"), ("crew", "Crew"), ("notes", "Notes"), ("decisions", "Decisions"),
        ("research", "Research and review"),
        ("checkpoints", "Checkpoints"), ("failures", "Failures"), ("shift", "This shift"), ("queue", "Next shifts"),
        ("blockers", "Blockers"), ("release", esc(f"Road to {GOAL}")), ("milestones", "Milestones"), ("lanes", "Lanes"),
        ("log", "Log")))
    on_clock = [b for b in crew["badges"] if b["on"] and b["role"] not in TOP_ROLES]
    mgr_on = next((b for b in crew["badges"] if b["on"] and b["role"] == "MANAGER"), None)

    blockers = "".join(
        f"<li><strong>{esc(b['what'])}</strong>" +
        (f"<br><span class=\"meta\">Owner: {esc(b['owner'])}</span>" if b.get("owner") else "") +
        (f"<br><span class=\"meta\">Fallback: {esc(b['fallback'])}</span>" if b.get("fallback") else "") +
        (f"<br><span class=\"meta\">Shift: {esc(b['shift'])}</span>" if b.get("shift") else "") + "</li>"
        for b in S.get("blockers", []))

    side = "".join(
        f'<div class="card"><h3>{esc(t["id"])} · {esc(t["title"])} {chip(t["status"])}</h3>'
        f'<p>{esc(t.get("note",""))}</p><p class="meta">{" · ".join(fact_line(x) for x in t.get("lanes", []))}</p></div>'
        for t in S.get("side_tracks", []))

    def stage_counts(st):
        rest = [f"{st['counts'][s]} {s.lower()}" for s in (*REQ_STATUSES, "missing") if s not in REQ_MET and st["counts"][s]]
        return f"{st['met']} of {len(st['ids'])} met" + "".join(f" · {x}" for x in rest)

    stage_nodes = "\n".join(
        f'<div class="node {STATUS[st["status"]][0]}"><div class="id">{esc(st["id"])} {chip(st["status"])}</div>'
        f'<div class="t">{esc(st["title"])}</div><div class="f">{esc(stage_counts(st))}</div>'
        f'<div class="f">{esc(st["theme"])}</div></div>'
        for st in stages)
    req_rows = "".join(
        f"<tr><td>{esc(p)}</td>" + "".join(f'<td class="num">{by_p[p][s]}</td>' for s in REQ_STATUSES)
        + f'<td class="num">{sum(by_p[p].values())}</td></tr>'
        for p in TIERS)

    dirty = f"dirty, {len(facts['dirty'])} tracked files changed" if facts["dirty"] else "clean"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(PROJECT)} progress map</title>
<meta name="description" content="Where {esc(PROJECT)} is: milestones with their gym verdicts, the road to {esc(GOAL)}, the current block, the current shift's plan, the shifts queued after it, blockers, decisions and the block log.">
<style>{CSS}</style>
</head>
<body>
<main>
<h1>{esc(PROJECT)} progress map</h1>
<p class="lede">{esc(S["now"]["headline"])}</p>
<p class="meta">State updated {esc(S["updated"])} · built {now:%Y-%m-%d %H:%M} from {esc(facts["branch"])} {esc(facts["head"])} ({dirty}) · last commit {esc(facts["last_date"])} “{esc(facts["last_subject"])}”</p>

<nav class="toc" aria-label="Sections">{nav}</nav>

{warn_html}
{attention_html(attn)}

<div class="stats">
  <div class="stat"><div class="k">Weekly usage</div><div class="v">{f'{u_last["weekly"]:g}%' if u_last else "—"}</div><div class="d">{(f"stop at {u_stop:g}% · ") if u_stop is not None else ""}{("recorded " + esc(str(u_last.get("at", ""))[5:16].replace("T", " "))) if u_last else "no point recorded"}</div></div>
  <div class="stat"><div class="k">Milestones PASS</div><div class="v">{m_done} / {len(milestones)}</div><div class="d">{span(milestones)}{", gym-gated" if milestones else ""}</div></div>
  {phases_stat}
  <div class="stat"><div class="k">Lanes PASS on their latest run</div><div class="v">{l_pass} / {len(ran)}</div><div class="d">{len(lanes) - len(ran)} lane{"s" if len(lanes) - len(ran) != 1 else ""} with no run yet</div></div>
  <div class="stat"><div class="k">Next milestone</div><div class="v">{esc(nxt.get("id")) if nxt else "—"}</div><div class="d">{esc(nxt.get("title", "")) if nxt else ""}{(" · " + esc(nxt["lane"])) if nxt and nxt.get("lane") else ""}</div></div>
  <div class="stat"><div class="k">Crew on the clock</div><div class="v">{len(on_clock)} / {esc(shift.get("crew_max", "—"))}</div><div class="d">{esc(crew["slot"][0])} slot · manager {esc(mgr_on["id"]) if mgr_on else "none"}</div></div>
  <div class="stat"><div class="k">Open failures</div><div class="v">{open_fails}</div><div class="d">{len(untriaged(S, crew))} reported, not triaged</div></div>
  <div class="stat"><div class="k">Decisions open</div><div class="v">{len(open_decisions(S))}</div><div class="d">they wait on the user · <a href="#decisions">Decisions</a></div></div>
  <div class="stat"><div class="k">{esc(GOAL)} {esc(TOP)}s met</div><div class="v">{p0_met} / {sum(by_p[TOP].values())}</div><div class="d">{by_p[TOP]["Part"]} part-way{f" · {p0_stale} on a lane not passing now" if p0_stale else ""} · <a href="#release">Road to {esc(GOAL)}</a></div></div>
</div>

<div class="band">
  <div class="card"><h3>Where we are</h3><p>{esc(S["now"]["position"])}</p><p class="meta">Tree: {esc(S["now"]["tree"])}</p></div>
  <div class="card"><h3>Next block</h3><p>{esc(blocks[up].get("time", "")) + " · " + esc(blocks[up].get("title", "")) if up is not None else (f"No pending block; promote the next queued shift ({esc(BOARD)} promote)." if queue else "No pending block; write the next shift plan.")}</p>{f'<p class="meta">Done when: {esc(blocks[up].get("done_when", ""))}</p>' if up is not None else ""}<p class="meta">Plan file: {esc(S["now"].get("plan_file", ""))}</p></div>
</div>

<h2 id="status">Status</h2>
<p class="sub">Drawn at build time from the shift plan, the rota, the crew office and the gym's series ({esc(GYM_REL)}/series). Hover a mark for its facts.</p>
<div class="two">
  <div class="card"><h3>This shift's blocks</h3><p>{esc(shift.get("id", ""))}{(" · " + esc(shift["milestone"])) if shift.get("milestone") else ""} · crew_max {esc(shift.get("crew_max", "—"))} · heavy work {"pre-approved" if shift.get("heavy_ok") else "asks first"}</p>{shift_bar(blocks)}</div>
  <div class="card"><h3>Today's rota</h3><p>{slots_n} slot{"s" if slots_n != 1 else ""} a day; each names the shift it runs and its manager.</p>{rota_today(S, crew, now)}</div>
</div>
<div class="two" style="margin-top:12px">
  {resource_card}
  <div class="card" id="usage"><h3>Weekly usage</h3><p>Recorded by the manager's rounds; the line is the stop the user set.</p>{usage_svg(usage, now)}</div>
</div>
<div class="card wide" id="runs"><h3>Runs in the last 24 hours</h3>{runs_html(S, lanes, now)}</div>
<div class="card wide"><h3>Gym lanes passed, cumulative</h3><p>Each step is a lane's first PASS.</p>{svg_passes(lanes, now)}</div>
<div class="card wide"><h3>Lane run history</h3><p>The last twelve graded runs per lane, oldest first.</p>{lane_history(lanes) if lanes else '<p class="meta">No lane yet.</p>'}</div>

<h2 id="crew">Crew on the clock</h2>
<p class="sub">One manager; every other agent is an employee with a badge. Each tile is read from the time clock: the job, the last progress post, the approximate finish. STALE means silent for {esc(P.get("limits.stale_min", 45))} min, OVERDUE {esc(P.get("limits.overdue_min", 15))} min past the finish.</p>
{crew_html(S, crew, now)}

<h2 id="notes">Notes</h2>
<div class="card"><ul class="notes">{notes or "<li>None.</li>"}</ul>{notes_more}</div>

<h2 id="decisions">Decisions</h2>
<p class="sub">Questions only the user answers. The founder or the manager files one with its options and a recommendation (<code>board.py decide ask</code>); the answer is recorded in the user's own words (<code>board.py decide answer</code>). Open ones wait on the user and are listed under Needs attention. Newest first.</p>
{decisions_html(S)}

<h2 id="research">Research and review</h2>
<p class="sub">Every rota slot has a research-and-review window (Today's rota shows it). New hires work it: a reviewer reads the last slot's commits, a researcher answers the coming blocks' open questions. Each writes a report under {esc(P.rel("reviews"))} or {esc(P.rel("research"))}; the manager files it here with what it changed (a failure entry, a block, a note). Newest first.</p>
<div class="tablewrap"><table>
{rr_head}
<tbody>{rr_rows or '<tr><td colspan="8">Nothing filed yet.</td></tr>'}</tbody>
</table></div>
{rr_more}

<h2 id="checkpoints">Gym checkpoints</h2>
<p class="sub">Set by the manager. A milestone is done only when its lane says PASS; the grader is its own session, never the builder, and writes the prereg before any data.</p>
<div class="tablewrap"><table>
<thead><tr><th>Lane</th><th>Milestone</th><th>Shift</th><th>Builder</th><th>Grader</th><th>Latest</th><th>Files</th><th>Note</th></tr></thead>
<tbody>{cp_rows or '<tr><td colspan="8">No checkpoint set.</td></tr>'}</tbody>
</table></div>

<h2 id="failures">Failures and action plans</h2>
<p class="sub">Open and planned first. The crew reports with <code>office.py fail</code>; the manager files each report here with a plan and an owner.</p>
<div class="tablewrap"><table>
{fail_head}
<tbody>{fail_rows or '<tr><td colspan="7">None open or planned.</td></tr>'}</tbody>
</table></div>
{fail_closed}
{f'<div class="card" style="margin-top:12px"><h3>Reported by the crew, not yet triaged</h3><ul>{new_reports}</ul></div>' if new_reports else ""}

<h2 id="shift-start">Before a shift</h2>
<p class="sub">Read this map, then walk the list. Nothing heavy starts before the user has answered what the list asks of them.</p>
<div class="card"><ol class="check">
{"".join(f'<li><span class="box" aria-hidden="true"></span><span>{esc(c)}</span></li>' for c in S.get("checklist", [])) or "<li><span></span><span>No checklist yet (state.checklist).</span></li>"}
</ol></div>

<h2 id="shift">This shift: {esc(shift.get("title", ""))}</h2>
<p class="sub">{esc(shift.get("when", ""))}. Mark a block done, partial or skipped at its end, add a log entry, rebuild this map, commit.</p>
<div class="card" style="margin-bottom:12px"><h3>Before the first block</h3><ul>{"".join(f"<li>{esc(x)}</li>" for x in shift.get("before_start", [])) or "<li>—</li>"}</ul></div>
{block_table(blocks, up)}

<h2 id="queue">Next shifts</h2>
<p class="sub">In order, each planned block by block. When every block of This shift is done or skipped, <code>{esc(BOARD)} promote</code> moves the first one up and its blockers into Blockers; the standing blockers stay.</p>
{"".join(queue_html) or '<div class="card"><p>Nothing queued; write the next shift plan into queue.</p></div>'}

<h2 id="blockers">Blockers and open questions</h2>
<div class="card"><ul>{blockers or "<li>None recorded.</li>"}</ul></div>

<h2 id="release">Road to {esc(GOAL)}</h2>
<p class="sub">The end goal: {esc(PROJECT)} {esc(GOAL)} is every {esc(TOP)} requirement of {roadmap_link} met. Read from the roadmap's tables at build time. A requirement is met when a gym lane passed it, or, for a decision, when its record exists. The release stages say what must be true; the milestones below are the work.</p>
{stale_html}<div class="grid">{stage_nodes or f'<div class="card"><p>{esc(ROADMAP_REL)} has no release stages the map can read{"" if ROADMAP.is_file() else " (no roadmap yet: the founder writes it)"}.</p></div>'}</div>
<div class="tablewrap" style="margin-top:12px"><table>
<thead><tr><th>Priority</th>{"".join(f'<th class="num">{s}</th>' for s in REQ_STATUSES)}<th class="num">Total</th></tr></thead>
<tbody>{req_rows}</tbody>
</table></div>

<h2 id="milestones">Milestone track</h2>
<p class="sub">Each milestone is done only when its lane says PASS; the verdict under each card comes from the gym's series, not from this file.</p>
<div class="grid">{nodes(milestones) or '<div class="card"><p>No milestone yet (state.milestones).</p></div>'}</div>
{f'<h2 id="phases">{esc(PHASES_TITLE)}</h2><div class="grid">{nodes(phases, with_ms=True)}</div>' if phases else ""}

<h2 id="side">Side tracks</h2>
<div class="band">{side or '<div class="card"><p>None.</p></div>'}</div>

<h2 id="lanes">Gym lanes</h2>
<p class="sub">Read from {esc(GYM_REL)}/series/*.json at build time. Runs counts every graded run, VOIDs included.</p>
<div class="tablewrap"><table>
<thead><tr><th>Lane</th><th>Checkpoint</th><th>Latest</th><th class="num">n</th><th>Last run</th><th class="num">Runs</th><th>History</th><th>Files</th></tr></thead>
<tbody>{"".join(lane_rows) or '<tr><td colspan="8">No lane yet.</td></tr>'}</tbody>
</table></div>

<h2 id="log">Block log</h2>
<p class="sub">Newest first. One entry per block; what was done, what was not, which verdicts were earned, and what comes next.</p>
{log_top or '<div class="card"><p>No block logged yet.</p></div>'}
{log_more}

<h2 id="rules">Standing rules</h2>
<div class="card"><ul>{"".join(f"<li>{esc(r)}</li>" for r in S.get("rules", [])) or "<li>None recorded (state.rules).</li>"}</ul></div>

<h2 id="keeping">How this map is kept</h2>
<div class="two">
  <div class="card"><h3>End of a block</h3>
    <ol>
      <li>In <code>{esc(STATE_REL)}</code>: set the block's <code>status</code> (done, partial, skipped), add a <code>log</code> entry at the top (done, not done, verdicts, commits, next), update <code>now</code> (position, tree hash), and any milestone or phase status that changed.</li>
      <li>Rebuild and read the warnings box:</li>
    </ol>
    <pre><code>{esc(BOARD)} check</code></pre>
    <ol start="3">
      <li>Commit <code>{esc(STATE_REL)}</code> and <code>{esc(MAP_REL)}</code> with the block's last commit.</li>
      <li>When the last block is done or skipped: <code>board.py promote</code> moves the first queued shift into <code>shift</code> and its blockers into <code>blockers</code> (the standing ones stay); then set its <code>when</code>, update <code>now</code>, rebuild, commit. A new shift plan is appended to <code>queue</code>, never written over <code>shift</code>.</li>
    </ol>
  </div>
  <div class="card"><h3>Start of a shift</h3>
    <ol>
      <li>Run the check; it rebuilds the map and prints Now, the next block, the queue and every warning:</li>
    </ol>
    <pre><code>{esc(BOARD)} check</code></pre>
    <ol start="2">
      <li>Open <code>{esc(MAP_REL)}</code> (or <code>board.py open</code>) and walk the checklist above; the Next shifts section is the order of what follows.</li>
      <li>A warning means the map and the tree disagree: fix the state first, then start.</li>
    </ol>
  </div>
  <div class="card"><h3>The crew</h3>
    <ol>
      <li>One manager per slot: you type <code>/{esc(P.skill("manager"))}</code>; it appoints itself (<code>office.py appoint</code>, refused while another manager is fresh), clocks in, runs the check and reads the rota.</li>
      <li>It hires up to the shift's <code>crew_max</code> (<code>office.py hire</code>): sessions for real jobs, subagents for quick ones; each brief carries the badge line, and each employee loads <code>{esc(P.skill("employee"))}</code> and clocks in with it.</li>
      <li>Employees post progress, report failures and clock out; the manager files the reports under Failures, keeps the checkpoints, ends the slot with <code>office.py end-shift</code> and the log entry's <code>crew</code>.</li>
    </ol>
    <pre><code>{esc(OFFICE)} roster</code></pre>
  </div>
</div>
<p class="note">Lane facts come from the gym's series, the crew from the time clock in the crew office ({esc(P.rel("office"))}), and the road to {esc(GOAL)} from the tables of {esc(ROADMAP_REL)}; milestone statuses, the shift plan, the queue, the rota, checkpoints, failures, notes, decisions, research and review, and the log are kept in the state, by the manager only. The builder never edits the gym.</p>
</main>
</body>
</html>
"""


def build(write=True):
    """Reads everything and (unless write is False) writes the map. A project with no state yet is drawn from a
    starter state held in memory; nothing but the map is written."""
    state, _ = read_state()
    lanes = read_lanes(state)
    facts = git_facts()
    now = dt.datetime.now().astimezone()
    crew = read_crew(state, now)
    warns = consistency(state, lanes, facts, now, crew)
    if write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(render(state, lanes, facts, warns, now, crew), encoding="utf-8", newline='\n')
    return state, lanes, facts, warns, now, crew


def init_state():
    """`init`: writes the starter state when the project has none. An existing state is never overwritten (exit 3)."""
    if STATE.exists():
        print(f"refused: {STATE.as_posix()} exists; init never overwrites a state. Edit it with the edit commands "
              "(note, block, fail, rr, usage, decide), or by hand.")
        return 3
    STATE.parent.mkdir(parents=True, exist_ok=True)
    write_state(starter_state())
    print(f"wrote {STATE.as_posix()}: Now, an empty shift (crew_max {P.get('limits.crew_max', 4)}), the rota's slots "
          f"({', '.join(s['id'] + ' ' + s['start'] for s in default_slots())}), usage stop {USAGE_STOP}%. "
          "Next: milestones and lanes, the first shift plan in queue, then board.py promote.")
    return 0


def promote():
    """Moves the first queued shift into "shift" once every block of the current one is done or skipped."""
    state, _ = read_state(required=True)
    queue = state.get("queue", [])
    blocks = state.get("shift", {}).get("blocks", [])
    if not queue:
        print("nothing queued; write the next shift plan into queue")
        return 2
    if blocks and not all(b.get("status") in ("done", "skipped") for b in blocks):
        print("the current shift still has pending blocks; mark them done or skipped first")
        return 2
    old_id = state.get("shift", {}).get("id")
    nxt = queue.pop(0)
    new_blockers = [dict(b, shift=nxt["id"]) for b in nxt.pop("blockers", [])]
    state["shift"] = {"id": nxt["id"], "title": nxt["title"],
                      "when": nxt.get("when", "not started; it starts on the user's call"),
                      "plan_file": f"{STATE_REL} (these blocks)",
                      **{k: nxt[k] for k in ("milestone", "crew_max", "heavy_ok") if k in nxt},
                      "before_start": nxt.get("before_start", []), "blocks": nxt["blocks"]}
    # the finished shift's own blockers go with it; the standing ones (untagged) stay
    state["blockers"] = new_blockers + [b for b in state.get("blockers", []) if b.get("shift") != old_id]
    state["queue"] = queue
    state["updated"] = dt.datetime.now().astimezone().isoformat(timespec="minutes")
    write_state(state)
    print(f"promoted {nxt['id']}; {len(queue)} shift(s) still queued. Edit now.headline, now.position and the shift's when, then commit.")
    return 0


def check(state, lanes, facts, warns, now, crew, rebuilt=True):
    S = state
    blocks = S.get("shift", {}).get("blocks", [])
    up = next((b for b in blocks if b.get("status") in ("pending", "in-progress", "partial")), None)
    age_h = (now - (parse_or_none(S.get("updated")) or now)).total_seconds() / 3600
    print(f"{PROJECT} progress map, shift-start check at {now:%Y-%m-%d %H:%M}")
    print(f"  state updated {S['updated']} ({age_h:.0f} h ago)")
    print(f"  tree {facts['branch']} {facts['head']} {'dirty' if facts['dirty'] else 'clean'}; last commit {facts['last_date']} \"{facts['last_subject']}\"")
    print(f"  now: {S['now']['headline']}")
    print(f"       {S['now']['position']}")
    print(f"  shift: {S.get('shift', {}).get('title', '')}")
    if up:
        print(f"  next block: {up.get('time')} {up.get('title')}\n       done when: {up.get('done_when')}")
    elif S.get("queue"):
        print(f"  next block: none pending; promote the next queued shift ({BOARD} promote)")
    else:
        print("  next block: none pending; write the next shift plan")
    if S.get("shift", {}).get("before_start"):
        print("  before the first block:")
        for x in S["shift"]["before_start"]:
            print(f"    - {x}")
    queue = S.get("queue", [])
    print(f"  queue: {len(queue)} shift(s) after this one")
    for i, q in enumerate(queue, 2):
        print(f"    {i}. {q.get('id')}: {q.get('title', '')[:90]} ({q.get('when', '')})")
    print(f"  blockers: {len(S.get('blockers', []))}")
    for b in S.get("blockers", []):
        print(f"    - {b.get('what', '')}")
    decs = open_decisions(S)
    print(f"  decisions open: {len(decs)}")
    for d in decs:
        print(f"    {d.get('id')} {str(d.get('question', ''))[:100]}"
              + (f" (needed before {d['needed_before']})" if d.get("needed_before") else ""))
    shift = S.get("shift", {})
    slot, s0, s1 = crew["slot"]
    entry = next((e for e in (S.get("rota") or {}).get("days", [])
                  if isinstance(e, dict) and e.get("date") == f"{local_dt(s0):%Y-%m-%d}"), {}).get(slot) or {}
    print(f"  rota: {slot} slot {local_dt(s0):%H:%M}-{local_dt(s1):%H:%M}; on the rota: {entry.get('shift') or 'nothing'}"
          f"; crew_max {shift.get('crew_max', 'not set')}; heavy work {'pre-approved' if shift.get('heavy_ok') else 'asks first'}")
    on = [b for b in crew["badges"] if b["on"] or b["status"] == "HIRED"]
    print(f"  crew ({len(on)}; {OFFICE} roster for the full list):")
    for b in sorted(on, key=lambda b: (b["role"] not in TOP_ROLES, b["id"])):
        eta = f", finish ~{local_dt(b['eta']):%H:%M}" if b["eta"] and b["role"] not in TOP_ROLES else ""
        print(f"    {b['id']} {b['name']} {b['role'].lower()}: {b.get('status_text') or b['status']} {b['pct']}%{eta}; {b.get('job', '')[:80]}")
    print(f"  checkpoints: {len(S.get('checkpoints', []))}")
    for cp in S.get("checkpoints", []):
        l = lanes.get(cp.get("lane", ""))
        print(f"    {cp.get('lane')} for {cp.get('milestone')}: latest {(l or {}).get('verdict') or 'no run'}; "
              f"prereg {'yes' if l and l['prereg'] else 'no'}; builder {cp.get('builder', '?')}; grader {cp.get('grader') or 'none'}")
    fails = [f for f in S.get("failures", []) if f.get("status", "open") in ("open", "planned")]
    print(f"  failures open or planned: {len(fails)}; reported, not triaged: {len(untriaged(S, crew))}")
    for f in fails:
        print(f"    {f.get('id')} [{f.get('status', 'open')}] {f.get('what', '')[:90]}")
    reqs, stages = read_roadmap()
    p0 = Counter(s for q, s in reqs.values() if q == TOP)
    if ROADMAP.is_file():
        print(f"  road to {GOAL} ({ROADMAP_REL}): {TOP} met {sum(p0[s] for s in REQ_MET)} of {sum(p0.values())}, "
              f"{p0['Part']} part-way, {p0['Planned']} planned, {p0['Open']} open; "
              + ", ".join(f"{st['id']} {st['met']}/{len(st['ids'])}" for st in stages))
        stale, unnamed = pass_lanes(lanes)
        print(f"    PASS rows on a lane not passing now: {len(stale)} ({sum(1 for r in stale if r['p'] == TOP)} {TOP}); "
              f"PASS with no lane named: {len(unnamed)}")
    else:
        print(f"  road to {GOAL}: no roadmap yet ({ROADMAP_REL})")
    print("  checklist:")
    for i, c in enumerate(S.get("checklist", []), 1):
        print(f"    {i}. {c}")
    attn = attention(S, lanes, crew, read_resource(crew, now), now)
    print(f"  needs attention: {len(attn)}")
    dev = dev_hold()
    if dev:
        print(f"  dev, not counted: {', '.join(dev)}")
    for _, group, text, _ in attn:
        print(f"    [{group}] {text[:200]}")
    if warns:
        print(f"  WARNINGS ({len(warns)}):")
        for w in warns:
            print(f"    ! {w}")
    else:
        print("  warnings: none; the state agrees with the gym series and the git tree")
    print(f"  map: {out_name()} ({'rebuilt' if rebuilt else 'not rebuilt'})")
    return 1 if warns else 0


def edit_state(argv, at=None, write=True):
    """The manager's routine state edits, so a round needs no scratch script. Each one sets `updated` to now and
    keeps the file's format; the caller rebuilds (main does). Only the manager runs these.
        note --by MGR-1 "text"                  a note at the top of state.notes
        usage 12 [--stop 80] [--reset <iso>]    a weekly-usage point (percent) in state.usage.points
        block <n> <status> [--note "text"]      block n (1-based) of the current shift: done, partial, skipped, ...
        fail --what "text" [--lane G2 --run-id R --verdict VOID --plan P --owner O --status S --from R12,R13]
                                                the next F<nnn> at the end of state.failures, where new ones go
        rr --kind review|research --by "TMP-1 x" --topic T [--report P --commit C --finding "a | b" --action "a | b"
           --slot day --date 2030-01-02]        the next RR<nnn> at the top of state.research_review
        decide ask --by FDR-1 --question T [--options "a | b" --recommend T --needed-before M12 --brief PATH]
                                                the next D<n> at the top of state.decisions, open
        decide answer D7 --words "the user's own words"    D7 is answered (empty words are refused)
        decide withdraw D7 --note T             D7 no longer needs an answer
    Each command takes only its own options; any other is refused and nothing is written. A bare `--` ends the
    options, so a text may start with `--`: note --by MGR-1 -- "--force was wrong".
    `at` replays a held edit at the time it was made; write=False checks the command and writes nothing.
    """
    cmd, args = argv[0], list(argv[1:])
    usage_line = {"decide": 'usage: board.py decide ask --by <badge id> --question "text" [--options "a | b"] '
                            '[--recommend "text"] [--needed-before M12] [--brief <path>] | decide answer D<n> --words '
                            '"the user\'s own words" | decide withdraw D<n> --note "text" | decide list [--open]',
                  "note": 'usage: board.py note --by <badge id> [--] "text"',
                  "usage": "usage: board.py usage <weekly percent 0-100> [--stop <percent 0-100>] "
                           "[--reset <ISO time of the weekly reset>]",
                  "block": 'usage: board.py block <n> <status> [--note "text"]; statuses: ' + ", ".join(BLOCK_STATUSES),
                  "fail": 'usage: board.py fail --what "text" [--lane L] [--run-id R] [--verdict V] [--plan P] [--owner O] '
                          "[--status " + "|".join(FAIL_STATUSES) + "] [--from R12,R13]",
                  "rr": 'usage: board.py rr --kind review|research --by "<badge> <name>" --topic "text" [--report <path>] '
                        '[--commit <sha>] [--finding "a | b"] [--action "a | b"] [--slot <slot id>] [--date YYYY-MM-DD]'}[cmd]
    opts, pos = {}, []
    while args:
        a = args.pop(0)
        if a == "--":
            pos += args  # everything after a bare -- is text
            break
        if a.startswith("--"):
            if a[2:] not in EDIT_OPTS[cmd]:
                print(f"{cmd} takes no option {a}; " + usage_line)
                return 2
            if not args or (cmd in ("fail", "rr", "decide") and args[0].startswith("--")):
                # `fail --what --plan x` would file "--plan" as the failure
                print(f"{a} needs a value" + (" (a value may not start with --)" if args else ""))
                return 2
            opts[a[2:]] = args.pop(0)
        else:
            pos.append(a)
    state, _ = read_state(required=True, fill=False)
    now = at or dt.datetime.now().astimezone()
    if cmd == "decide":
        decs = state.setdefault("decisions", [])
        if not isinstance(decs, list):
            print("state.decisions is not a list; fix it by hand first")
            return 2
        verb = pos[0] if pos else ""
        took = {"ask": ("by", "question", "options", "recommend", "needed-before", "brief"), "answer": ("words",),
                "withdraw": ("note",)}.get(verb)
        if took is None or any(k not in took for k in opts):
            print(usage_line)
            return 2
        if verb == "ask":
            if len(pos) != 1 or not str(opts.get("by") or "").strip() or not str(opts.get("question") or "").strip():
                print(usage_line)
                return 2
            nums = [int(m.group(1)) for d in decs for m in [re.fullmatch(r"D(\d+)", str((d or {}).get("id", "")))] if m]
            did = f"D{(max(nums) if nums else 0) + 1}"
            decs.insert(0, {"id": did, "asked": now.isoformat(timespec="minutes"), "by": opts["by"].strip(),
                            "question": opts["question"].strip(),
                            "options": [x.strip() for x in str(opts.get("options") or "").split("|") if x.strip()],
                            "recommend": str(opts.get("recommend") or "").strip(),
                            "needed_before": str(opts.get("needed-before") or "").strip(), "status": "open",
                            "answer": "", "answered": "", "brief": str(opts.get("brief") or "").strip()})
            said = f"{did} filed (open; it waits on the user)"
        else:
            d = next((x for x in decs if isinstance(x, dict) and x.get("id") == (pos[1] if len(pos) == 2 else None)), None)
            if len(pos) != 2 or not re.fullmatch(r"D\d+", pos[1]):
                print(usage_line)
                return 2
            if d is None:
                print(f"no decision {pos[1]} in state.decisions (board.py decide list)")
                return 2
            if d.get("status", "open") != "open":
                print(f"{pos[1]} is already {d.get('status')}; only an open decision is answered or withdrawn "
                      "(ask a new one if the question came back)")
                return 2
            if verb == "answer":
                words = str(opts.get("words") or "").strip()
                if not words:
                    print(f"refused: decide answer needs the user's own words (--words \"...\"); an empty answer is "
                          f"not an answer, and {pos[1]} stays open")
                    return 2
                d.update(status="answered", answer=words, answered=now.isoformat(timespec="minutes"))
                said = f"{pos[1]} answered"
            else:
                why = str(opts.get("note") or "").strip()
                if not why:
                    print(f"refused: decide withdraw needs --note saying why {pos[1]} no longer needs an answer")
                    return 2
                d.update(status="withdrawn", note=why, withdrawn=now.isoformat(timespec="minutes"))
                said = f"{pos[1]} withdrawn"
    elif cmd == "note":
        if len(pos) != 1 or not opts.get("by"):
            print(usage_line)
            return 2
        state.setdefault("notes", []).insert(0, {"at": now.isoformat(timespec="minutes"), "by": opts["by"], "text": pos[0]})
        said = f"note by {opts['by']} added"
    elif cmd == "usage":
        try:
            if len(pos) != 1:
                raise ValueError("one percent")
            pct = float(pos[0])
            stop = float(opts["stop"]) if "stop" in opts else None
            reset = parse_updated(opts["reset"]) if "reset" in opts else None
            # inf, nan and out-of-range percents are typos; nan would also write invalid JSON
            if not all(math.isfinite(v) and 0 <= v <= 100 for v in (pct, stop if stop is not None else 0)):
                raise ValueError("a percent is 0 to 100")
        except ValueError:
            print(usage_line)
            return 2
        u = state.setdefault("usage", {"stop": USAGE_STOP, "points": []})
        if reset is not None:
            old = parse_or_none(u.get("reset"))
            # compare instants, not spellings: only a later reset starts a new week (and a new line of points)
            if old is not None and reset < old:
                print(f"--reset {opts['reset']} is earlier than the recorded reset {u['reset']}; a new week's reset is "
                      "later. " + usage_line)
                return 2
            if old is None or reset > old:
                u["reset"], u["points"] = opts["reset"], []  # a new week starts a new line
        if stop is not None:
            u["stop"] = int(stop) if stop == int(stop) else stop
        u.setdefault("points", []).append({"at": now.isoformat(timespec="minutes"), "weekly": int(pct) if pct == int(pct) else pct})
        said = f"usage {pct:g}% recorded ({len(u['points'])} point(s) this week)"
    elif cmd in ("fail", "rr"):
        if pos:
            print(usage_line)
            return 2
        split = lambda s: [x.strip() for x in str(s or "").split("|") if x.strip()]

        def next_id(items, prefix):
            nums = [int(m.group(1)) for x in items for m in [re.fullmatch(prefix + r"(\d+)", str(x.get("id", "")))] if m]
            return f"{prefix}{(max(nums) if nums else 0) + 1:03d}"
        if cmd == "fail":
            st = opts.get("status") or ("planned" if opts.get("plan") and opts.get("owner") else "open")
            if not opts.get("what") or st not in FAIL_STATUSES:
                print(usage_line)
                return 2
            froms = [x for x in re.split(r"[,\s]+", opts.get("from", "")) if x]
            if any(not re.fullmatch(r"R\d+", x) for x in froms):
                print("--from takes report ids R<seq>, comma-separated; " + usage_line)
                return 2
            fs = state.setdefault("failures", [])
            fid = next_id(fs, "F")
            fs.append({"id": fid, "at": f"{now:%Y-%m-%d}", "lane": opts.get("lane") or None,
                          "run_id": opts.get("run-id") or None, "verdict": opts.get("verdict") or None,
                          "what": opts["what"], "plan": opts.get("plan", ""), "owner": opts.get("owner", ""), "status": st,
                          **({"from": froms[0] if len(froms) == 1 else froms} if froms else {}),
                          "shift": state.get("shift", {}).get("id")})
            said = f"{fid} filed ({st})"
        else:
            if opts.get("kind") not in ("review", "research") or not opts.get("by") or not opts.get("topic"):
                print(usage_line)
                return 2
            slot_id, s0, _ = office.slot_at((state.get("rota") or {}).get("slots"), now.timestamp())
            rs = state.setdefault("research_review", [])
            rid = next_id(rs, "RR")
            rs.insert(0, {"id": rid, "date": opts.get("date") or f"{local_dt(s0):%Y-%m-%d}", "slot": opts.get("slot") or slot_id,
                          "kind": opts["kind"], "by": opts["by"], "topic": opts["topic"],
                          "findings": split(opts.get("finding")), "actions": split(opts.get("action")),
                          "report": opts.get("report", ""), "commit": opts.get("commit", "")})
            said = f"{rid} filed ({opts['kind']}, {rs[0]['slot']} {rs[0]['date']})"
    else:
        blocks = state.get("shift", {}).get("blocks", [])
        if (len(pos) != 2 or not re.fullmatch(r"[0-9]+", pos[0]) or not 1 <= int(pos[0]) <= len(blocks)
                or pos[1] not in BLOCK_STATUSES):
            print(usage_line.replace("<n>", f"<1-{len(blocks)}>"))
            return 2
        b = blocks[int(pos[0]) - 1]
        b["status"] = pos[1]
        if opts.get("note"):
            b["note"] = (b["note"] + "; " if b.get("note") else "") + f"{now:%H:%M %m-%d} {opts['note']}"
        said = f"block {pos[0]} ({b.get('time', '')}) is {pos[1]}"
    if not write:
        print(said + " (checked, not written)")
        return 0
    was = parse_or_none(state.get("updated"))
    if at is None or was is None or was < now:
        state["updated"] = now.isoformat(timespec="seconds")
    write_state(state)
    print(said)
    return 0


def brief(state, lanes, facts, warns, now, crew, full=False, keys=None):
    """One compact JSON for the manager skill: what a shift-start or block-end decision needs, and nothing else.
    Long texts are cut and passed checkpoints are counted, not listed; `brief --full` prints them whole.
    The warnings come first, so a reader that cuts long output still sees them; `--keys a,b` prints
    only those keys (warnings always). Exit 1 means only "warnings present", not a failure. A project with no shared
    resource has no `resource` key and none of the queue's counted-run keys."""
    S = state
    res = read_resource(crew, now)

    def cut(s, n):
        s = str(s or "")
        return s if full or len(s) <= n else s[:n] + "…"
    shift = S.get("shift", {})
    blocks = shift.get("blocks", [])
    up = next((b for b in blocks if b.get("status") in ("pending", "in-progress", "partial")), None)
    slot, s0, s1 = crew["slot"]
    day = f"{local_dt(s0):%Y-%m-%d}"
    entry = next((e for e in (S.get("rota") or {}).get("days", [])
                  if isinstance(e, dict) and e.get("date") == day), {}).get(slot)

    def t(ts):
        return local_dt(ts).isoformat(timespec="minutes") if ts else None

    rrw = rr_window(S.get("rota") or {}, slot, s0)
    reqs, stages = read_roadmap()
    out = {
        "warnings": warns,
        "at": now.isoformat(timespec="minutes"),
        "tree": {"branch": facts["branch"], "head": facts["head"], "dirty": len(facts["dirty"])},
        "now": S["now"],
        "slot": {"id": slot, "start": t(s0), "end": t(s1), "rota": entry},
        "shift": {k: shift.get(k) for k in ("id", "title", "milestone", "crew_max", "heavy_ok", "when")},
        "blocks": [{"time": b.get("time"), "status": b.get("status"), "checkpoint": b.get("checkpoint"),
                    "title": b.get("title", "")[:160]} for b in blocks],
        "next_block": up and {k: up.get(k) for k in ("time", "title", "done_when", "checkpoint")},
        "queue": [{"id": q.get("id"), "title": q.get("title", "")[:120], "crew_max": q.get("crew_max")} for q in S.get("queue", [])],
        "crew": [{"id": b["id"], "name": b["name"], "role": b["role"], "kind": b["kind"], "status": b["status"],
                  "pct": b["pct"], "eta": t(b["eta"]), "heard": t(b["heard"]), "session": b.get("session"),
                  "lane": b.get("lane"), "job": b.get("job", ""),
                  # what its job is doing in the resource queue (the office reports it under `vm`)
                  **({"resource": b.get("vm")} if has_resource() else {})}
                 for b in crew["badges"] if b["on"] or b["status"] == "HIRED"],
        "attention": [f"[{group}] {text}" for _, group, text, _ in attention(S, lanes, crew, res, now)],
        "recent_runs": [{"lane": l["lane"], "verdict": l["verdict"], "n": l["n"], "prev": l["prev"], "run_id": l["run_id"],
                         "at": l["when"].isoformat(timespec="minutes"),
                         "failure": (failure_for(S, l) or {}).get("id") if l["verdict"] in NOT_PASSING else None}
                        for l in recent_runs(lanes, now)],
        # the shared resource's seats, then who waits (only in a project that has one)
        "resource": [{"seat": r["seat"], "held_by": r["hold"] and r["hold"]["id"], "since": r["hold"] and t(r["hold"]["since"]),
                      "max_min": r["hold"] and r["hold"]["max"] // 60, "overdue": bool(r["hold"] and r["hold"]["overdue"])}
                     for r in res["seats"]] + ([{"queue": [e.get("id") for e in res["queue"]]}] if res["queue"] else []),
        "usage": {"stop": usage_stop(S.get("usage")),
                  **{k: v for k, v in (S.get("usage") or {}).items() if k != "points"},
                  "last": ((S.get("usage") or {}).get("points") or [None])[-1]},
        # a passed checkpoint of an earlier shift is history: counted here, listed by --full
        "checkpoints": [{**cp, **({"note": cut(cp["note"], 240)} if "note" in cp else {}),
                         "verdict": (lanes.get(cp.get("lane", "")) or {}).get("verdict"),
                         "prereg": bool((lanes.get(cp.get("lane", "")) or {}).get("prereg"))}
                        for cp in S.get("checkpoints", [])
                        if full or cp.get("shift") == shift.get("id")
                        or (lanes.get(cp.get("lane", "")) or {}).get("verdict") != "PASS"],
        "checkpoints_passed_earlier": sum(1 for cp in S.get("checkpoints", []) if cp.get("shift") != shift.get("id")
                                          and (lanes.get(cp.get("lane", "")) or {}).get("verdict") == "PASS"),
        # one line each: "F211 planned G21 (owner) what"; the plan and the full text are in --full and on the map
        "failures_open": [f if full else
                          f"{f.get('id')} {f.get('status', 'open')} {f.get('lane') or '-'} ({cut(f.get('owner'), 40)}) {cut(f.get('what'), 100)}"
                          for f in S.get("failures", []) if f.get("status", "open") in ("open", "planned")],
        "untriaged": [{k: r.get(k) for k in ("seq", "id", "what", "lane", "run_id", "verdict", "plan")} for r in untriaged(S, crew)],
        # the six highest ids, as the map sorts them: state.research_review is kept in either order
        "research_review": {"window": rrw and [t(rrw[0]), t(rrw[1])],
                            "recent": [{k: r.get(k) for k in ("id", "date", "slot", "kind", "topic")}
                                       for r in sorted(S.get("research_review", []), key=lambda r: lane_key(str(r.get("id", ""))),
                                                       reverse=True)[:6]]},
        "blockers": [b.get("what", "")[:200] for b in S.get("blockers", [])],
        # the questions that wait on the user, newest first; the options and the brief are in --full and on the map
        "decisions_open": [d if full else
                           {"id": d.get("id"), "asked": d.get("asked"), "by": d.get("by"), "question": cut(d.get("question"), 200),
                            "recommend": cut(d.get("recommend"), 120), "needed_before": d.get("needed_before") or None}
                           for d in open_decisions(S)],
        # `p0` counts the goal's own tier (roadmap.tiers[0], named in `tier`)
        "release": {"goal": GOAL, "tier": TOP, "roadmap": ROADMAP.is_file(),
                    "p0": dict(Counter(s for q, s in reqs.values() if q == TOP)),
                    "stages": [{"id": st["id"], "title": st["title"], "met": st["met"], "of": len(st["ids"]),
                                "status": st["status"]} for st in stages],
                    # PASS rows whose named lane's newest counted run is not PASS (they still count in p0 as typed)
                    "stale_pass": [{"id": r["id"], "p": r["p"], "lanes": r["lanes"],
                                    "not_passing": [f"{s['lane']} {s['verdict']} {s['run_id'] or ''}".strip() for s in r["stale"]]}
                                   for r in pass_lanes(lanes)[0]]},
        # a counted sweep in the resource queue: change nothing in the main checkout until it ends
        "counted_sweep": [r["text"] for r in sweep_hold()],
        # a prio-0 or whole-resource job under a plain id: maybe a counted run the guard cannot see
        "counted_unmarked": unmarked_hold(),
        # whole-resource jobs whose text says dev: not counted, so no freeze
        "dev_not_counted": dev_hold(),
        "held_edits": len(read_pending()),
    }
    if not has_resource():
        for k in ("resource", "counted_sweep", "counted_unmarked", "dev_not_counted"):
            out.pop(k, None)
    if keys is not None:
        unknown = [k for k in keys if k not in out]
        out = {k: v for k, v in out.items() if k == "warnings" or k in keys}
        if unknown:
            out["unknown_keys"] = unknown
    print(json.dumps(out, indent=1, ensure_ascii=False))
    return 1 if warns else 0


def decide_list(args):
    """`decide list [--open]`: the register as lines, newest first; reads only."""
    if any(a != "--open" for a in args):
        print("usage: board.py decide list [--open]")
        return 2
    state, _ = read_state()
    decs = [d for d in state.get("decisions") or [] if isinstance(d, dict)]
    shown = open_decisions(state) if "--open" in args else decs
    print(f"{len(shown)} decision(s)" + (" open" if "--open" in args else f", {len(open_decisions(state))} open"))
    for d in shown:
        tail = (f" -> {d.get('answer')}" if d.get("status") == "answered" else
                f" (withdrawn: {d.get('note', '')})" if d.get("status") == "withdrawn" else
                (f" [recommended: {d['recommend']}]" if d.get("recommend") else "")
                + (f" [needed before {d['needed_before']}]" if d.get("needed_before") else ""))
        print(f"  {d.get('id')} {d.get('status', 'open')} {str(d.get('asked', ''))[:16]} {d.get('by', '')}: "
              f"{d.get('question', '')}{tail}")
    return 0


def selftest():
    """Checks on made-up inputs: nothing in the checkout is read or written (the cases that need files make them in
    a temp folder, with the module's paths swapped for it and restored)."""
    import inspect
    import shutil
    ok, bad = [], []

    def expect(what, cond, detail=""):
        (ok if cond else bad).append(what + ("" if cond else f": {detail}"))

    def quiet(fn, *a, **kw):
        """(return value, printed text) of a call whose prints are not the selftest's."""
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = fn(*a, **kw)
        return rc, buf.getvalue()

    g = globals()
    # the fixtures name lanes G1, G2 ...: read them by that shape whatever the project's own lane pattern is
    lane_was = g["LANE_NAME"]
    g["LANE_NAME"] = re.compile(r"\bG\d+[a-z]?\b")

    # a commit of grader notes, reviews, research or run records does not move Now's tree
    notes_only = [f"{GYM_REL}/contracts/G7-grader-notes.md", f"{GYM_REL}/contracts/G20-grader-notes.md",
                  *(p + "2030-01-11-day.md" for p in RECORD_PREFIXES), STATE_REL, MAP_REL]
    expect("a notes-and-records-only commit does not move the tree", not [f for f in notes_only if not is_record(f)],
           str([f for f in notes_only if not is_record(f)]))
    for f in ("tools/office.py", "src/app/main.rs", f"{GYM_REL}/contracts/G7-artifacts.md",
              f"{GYM_REL}/contracts/sub/G7-grader-notes.md", f"{GYM_REL}/lanes/g7.py", "README.md"):
        expect(f"{f} still moves the tree", not is_record(f))

    # a roadmap row quoting a lane's old counted run and not its newest is stale
    runs = {"G1": ["20300103-004533-48ac", "20300110-115716-d005", "20300111-135643-0854"],
            "G2": ["20300102-173859-3440", "20300111-162107-5818"]}
    text = "\n".join([
        "| **R1 Desktop** | shell | APP-01 | M3 done (G1 FAIL n=30, 20300110-115716-d005) | Part |",
        "| APP-02 | P0 | PASS | M3 | G1 PASS n=34, 20300111-135643-0854 |",
        "| FILE-01 | P0 | Part | M4 | G2 PASS n=732, run 20300102-173859-3440, latest 20300111-162107 |",
        "| FILE-03 | P0 | Part | M4 | G2 newest counted VOID: 20300102-173859-3440 |",
        "| SET-01 | P0 | Part | M5 | G3 MEASURING 20300110-165310 |",
        "Prose naming G1 20300103-004533-48ac is not a row.",
        "| UPD-01 | P0 | Part | M2 | quotes 20300110-115716-d005 and names no lane |"])
    got = roadmap_stale_runs(text, runs)
    rows = sorted((s["row"], s["lane"]) for s in got)
    expect("a row quoting only an older run is flagged, with the lane's newest",
           rows == [("FILE-03", "G2"), ("R1 Desktop", "G1")]
           and all(s["newest"] == runs[s["lane"]][-1] for s in got), str(got))
    expect("a row quoting the newest (also by prefix, 'run X, latest Y') is not flagged",
           not any(r in ("APP-02", "FILE-01") for r, _ in rows), str(rows))
    expect("a lane with no series, prose and a row naming no lane are not flagged",
           not any(r in ("SET-01", "UPD-01") for r, _ in rows), str(rows))

    # a VOID or STARVED point newer than the PASS a row quotes supersedes nothing; a row quoting only the VOID still
    # names an old run once a decided one follows it
    vruns = {"G2": [("20300102-173859-3440", "VOID"), ("20300111-162107-5818", "PASS"),
                    ("20300112-010000-a323", "VOID"), ("20300112-020000-4a4f", "STARVED")]}
    vtext = "\n".join(["| FILE-01 | P0 | PASS | M4 | G2's counted PASS 20300111-162107-5818, not the VOIDs a323/4a4f |",
                       "| FILE-03 | P0 | Part | M4 | G2 VOID 20300102-173859-3440 |"])
    got = roadmap_stale_runs(vtext, vruns)
    expect("a row quoting the PASS is not flagged when newer VOID/STARVED points follow it",
           [s["row"] for s in got] == ["FILE-03"] and got[0]["newest"] == "20300111-162107-5818", str(got))

    # the newest named by its four-hex suffix alone ("fixed: G1 PASS 0854") is named; a suffix inside another word
    # or id is not
    l2 = roadmap_stale_runs("\n".join([
        "| X-01 | P0 | PASS | M3 | G1 FAIL 20300110-115716-d005 (its failure entry), fixed: G1 PASS 0854 |",
        "| X-02 | P0 | Part | M3 | G1 FAIL 20300110-115716-d005, commit 0854abc |"]), runs)
    expect("a history row naming the newest by its four-hex suffix is not flagged; a sha starting with it is",
           [s["row"] for s in l2] == ["X-02"], str(l2))

    # a manager re-badged before its slot with `appoint --slot day` (its badge keeps slot_start, the day slot's
    # start) reads the day entry's `ends`; the same badge without slot_start reads none
    three = [{"id": "day", "start": "06:00"}, {"id": "swing", "start": "14:00"}, {"id": "night", "start": "22:00"}]
    d0 = dt.datetime(2030, 1, 12, 6, 0).astimezone()
    at = lambda hh, mm: d0.replace(hour=hh, minute=mm).timestamp()
    rb = {"id": "MGR-7", "role": "MANAGER", "slot": "day", "issued": at(5, 32), "in_at": at(5, 33),
          "slot_start": d0.timestamp()}
    ends_st = {"rota": {"slots": three, "days": [{"date": "2030-01-12", "day": {"ends": "15:17"}}]}}
    expect("user_end: a --slot day badge clocked in at 05:33 reads the day entry's ends 15:17",
           user_end(ends_st, rb) == at(15, 17), user_end(ends_st, rb))
    expect("user_end: the same badge without slot_start reads no end",
           user_end(ends_st, {**rb, "slot_start": None}) is None)
    expect("user_end: a slot_start more than an hour after the issue is not honoured",
           user_end(ends_st, {**rb, "issued": at(4, 50), "in_at": at(4, 51)}) is None)

    # the record and stale-run checks through consistency() itself, on a fixture roadmap, series and git (module
    # paths swapped for a temp dir and restored; nothing in the checkout is read)
    swapped = ("ROOT", "STATE", "OUT", "GYM", "ROADMAP", "SERIES", "PREREG", "CONTRACTS", "CHARTS", "GRADES", "git",
               "unmarked_hold", "sweep_hold", "dev_hold", "read_pending", "read_crew", "has_resource")
    keep = {k: g[k] for k in swapped}
    tmp = Path(tempfile.mkdtemp(prefix="board-selftest-"))
    try:
        (tmp / "series").mkdir()
        (tmp / "prereg").mkdir()
        (tmp / "series" / "G1.json").write_text(json.dumps({"points": [
            {"run_id": "20300110-115716-d005", "verdict": "FAIL"}, {"run_id": "20300111-135643-0854", "verdict": "PASS"},
            {"run_id": "20300112-000000-beef", "verdict": "VOID"}]}), encoding="utf-8")
        g["ROOT"] = tmp
        g["SERIES"], g["PREREG"], g["ROADMAP"] = tmp / "series", tmp / "prereg", tmp / "ROADMAP.md"
        g["unmarked_hold"] = lambda: []
        between = {"files": []}

        def fake_git(*args):
            if args[:1] == ("diff",):
                return "\n".join(between["files"])
            return "commit" if args[:2] == ("cat-file", "-t") else ""
        g["git"] = fake_git
        now = dt.datetime.now().astimezone()
        st = {"updated": now.isoformat(), "now": {"tree": "abc1234"}, "shift": {"id": "t", "crew_max": 1, "blocks": []},
              "queue": [], "lanes": {}}
        facts = {"head": "def5678", "dirty": []}
        crew = {"badges": [], "slot": ("night", now.timestamp() - 60, now.timestamp() + 3600), "error": None, "reports": []}

        def warns(roadmap, files):
            g["ROADMAP"].write_text(roadmap, encoding="utf-8")
            between["files"] = files
            return consistency(st, {}, facts, now, crew)
        tree = lambda w: [x for x in w if x.startswith("Now says the tree")]
        road = lambda w: [x for x in w if "older counted run" in x]
        w = warns("| R1 | x | APP-01 | G1 FAIL 20300110-115716-d005 |\n", [f"{GYM_REL}/contracts/G7-grader-notes.md"])
        expect("consistency(): a notes-only commit on top of Now's tree gives no tree warning", not tree(w), str(tree(w)))
        expect("consistency(): a roadmap row quoting an older run than the newest decided one warns",
               len(road(w)) == 1 and "20300111-135643-0854" in road(w)[0], str(w))
        w = warns("| R1 | x | APP-01 | G1 PASS 20300111-135643-0854 |\n", ["tools/office.py", RECORD_PREFIXES[-1] + "G1.json"])
        expect("consistency(): a code commit still moves the tree", len(tree(w)) == 1 and "tools/office.py" in tree(w)[0], str(w))
        expect("consistency(): a row quoting the PASS before a newer VOID does not warn", not road(w), str(road(w)))

        # a contract whose file no pin in the prereg names warns; a re-pin in an amendment clears it
        (tmp / "gym" / "contracts").mkdir(parents=True)
        g["PREREG"] = tmp / "gym" / "prereg"
        g["PREREG"].mkdir()
        cf = tmp / "gym" / "contracts" / "G77-artifacts.md"
        cf.write_bytes(b"# G77 contract\n")
        pin = hashlib.sha256(cf.read_bytes()).hexdigest()
        pre = {"contract": {"path": "gym/contracts/G77-artifacts.md", "sha256": pin}}
        (g["PREREG"] / "G77.json").write_text(json.dumps(pre), encoding="utf-8")
        (g["PREREG"] / "G78.json").write_text(json.dumps({"contract": {"path": "gym/contracts/G78-artifacts.md"}}),
                                              encoding="utf-8")
        pinw = lambda w: [x for x in w if "re-pinned" in x]
        w = warns("", [])
        expect("consistency(): a contract matching its prereg pin gives no pin warning; a contract not in the checkout "
               "is skipped", not pinw(w), str(pinw(w)))
        cf.write_bytes(b"# G77 contract\n\n## Amendment 1\n")
        w = warns("", [])
        expect("consistency(): a contract changed after its pin warns",
               len(pinw(w)) == 1 and "G77's prereg" in pinw(w)[0] and "no counted G77" in pinw(w)[0], str(w))
        body = cf.read_bytes()
        blob = hashlib.sha1(b"blob %d\0" % len(body) + body).hexdigest()
        (g["PREREG"] / "G77.json").write_text(json.dumps({**pre, "amendments": [{"contract_blob": blob}]}), encoding="utf-8")
        expect("consistency(): a re-pin by git blob in an amendment clears the pin warning", not pinw(warns("", [])))

        # a manager whose badge names the slot that ended reads no slot warning when the rota names it
        today = f"{local_dt(now.timestamp() - 60):%Y-%m-%d}"
        crew["badges"] = [{"id": "MGR-9", "role": "MANAGER", "on": True, "slot": "swing", "status": "UP",
                           "in_at": now.timestamp() - 3600, "heard": now.timestamp() - 60}]
        slotw = lambda w: [x for x in w if "clocked in for the swing slot" in x]
        w = warns("", [])
        expect("consistency(): a manager past its badge's slot warns while the rota does not name it", len(slotw(w)) == 1, str(w))
        st["rota"] = {"days": [{"date": today, "night": {"manager": "MGR-9 re-badged before the slot"}}]}
        expect("consistency(): no slot warning when the slot's rota.days entry names the manager",
               not slotw(warns("", [])), str(warns("", [])))
        st["rota"] = {"days": [{"date": today, "night": {"manager": "MGR-8 day; MGR-9 relieved"}}]}
        expect("consistency(): a rota entry naming the manager only later in its text does not count",
               len(slotw(warns("", []))) == 1)

        # a project with no state, no gym folder and no roadmap still gets a page and a brief: one line each under
        # Needs attention, no traceback, nothing written but the map
        proj = tmp / "empty project"
        proj.mkdir()
        g["ROOT"] = proj
        g["STATE"], g["OUT"] = proj / "docs" / "progress" / "state.json", proj / "docs" / "progress-map.html"
        g["GYM"], g["ROADMAP"] = proj / "gym", proj / "docs" / "ROADMAP.md"
        for k in ("SERIES", "PREREG", "CONTRACTS", "CHARTS", "GRADES"):
            g[k] = proj / "gym" / k.lower()
        g["git"] = lambda *args: ""
        g["sweep_hold"] = g["dev_hold"] = g["read_pending"] = lambda: []
        g["read_crew"] = lambda state, now: {"dir": "", "manager": None, "badges": [], "reports": [], "events": [],
                                             "error": "", "slot": office.slot_at((state.get("rota") or {}).get("slots"),
                                                                                 now.timestamp())}
        g["has_resource"] = lambda: False
        try:
            result, said = quiet(build)
            page, err = g["OUT"].read_text(encoding="utf-8"), None
        except Exception as e:  # the point of the case: no input's absence may raise
            result, page, err = None, "", f"{type(e).__name__}: {e}"
        expect("no state, gym or roadmap: build writes the map and raises nothing", err is None and "<h1>" in page, err)
        needs = page[page.find("Needs attention"):page.find('<div class="stats">')]
        expect("... with one line each under Needs attention (no state, no roadmap, no gym)",
               all(x in needs for x in ("no state yet", "no roadmap yet: the founder writes", "no gym yet")), needs[:400])
        expect("... and nothing but the map was written (no state.json appeared)",
               not g["STATE"].exists() and sorted(p.name for p in proj.rglob("*") if p.is_file()) == ["progress-map.html"],
               str(sorted(p.name for p in proj.rglob("*"))))
        expect("... the page has the project's name, a Decisions section, and no resource card without a resource",
               f"<title>{esc(PROJECT)} progress map</title>" in page and 'id="decisions"' in page
               and 'id="resource"' not in page, page[:300])
        try:
            rc, said = quiet(brief, *build(write=False))
            j, err = json.loads(said), None
        except Exception as e:
            rc, j, err = None, {}, f"{type(e).__name__}: {e}"
        expect("no state, gym or roadmap: brief prints JSON with the three setup lines under attention",
               err is None and len([a for a in j.get("attention", []) if a.startswith("[setup] no ")]) == 3, err or j.get("attention"))
        expect("... brief has decisions_open (empty), no resource and no queue keys without a resource",
               j.get("decisions_open") == [] and not {"resource", "counted_sweep", "counted_unmarked", "dev_not_counted"} & set(j)
               and j.get("release", {}).get("roadmap") is False, sorted(j))
        expect("... and a missing roadmap or gym is not a warning", not [w for w in j.get("warnings", [])
               if "ROADMAP" in w or "roadmap" in w or "gym" in w], j.get("warnings"))
        rc, said = quiet(check, *build(write=False), rebuilt=False)
        expect("no state, gym or roadmap: check prints its summary", "no roadmap yet" in said and "needs attention: 3" in said, said[-400:])
        g["has_resource"] = lambda: True
        rc, said = quiet(brief, *build(write=False))
        j = json.loads(said)
        expect("with a resource in the profile and no queue yet, brief has an empty resource list and the queue keys",
               j.get("resource") == [] and j.get("counted_sweep") == [] and "dev_not_counted" in j, sorted(j))
        page_r = render(*build(write=False))
        expect("... and the page has the resource card, headed by its name, saying seats",
               'id="resource"' in page_r and f"{esc(RES)}: seats" in page_r and "No resource queue in the crew office" in page_r)
        g["has_resource"] = lambda: False

        # an edit command with no state says so in one line
        try:
            quiet(edit_state, ["note", "--by", "MGR-1", "x"])
            said = "no exit"
        except SystemExit as e:
            said = str(e)
        expect("an edit with no state yet ends with one line naming init", "run board.py init first" in said, said)

        # init: writes the starter state once, never over an existing one
        rc, said = quiet(init_state)
        st0 = json.loads(g["STATE"].read_text(encoding="utf-8")) if g["STATE"].exists() else {}
        expect("init writes a starter state (exit 0)", rc == 0 and bool(st0), said)
        expect("init: Now, an empty shift with the profile's crew_max, heavy_ok false",
               all(k in st0.get("now", {}) for k in ("headline", "position", "tree"))
               and st0.get("shift", {}).get("blocks") == [] and st0["shift"].get("crew_max") == P.get("limits.crew_max", 4)
               and st0["shift"].get("heavy_ok") is False, st0.get("shift"))
        expect("init: the profile's rota slots, the usage stop, and every list empty",
               st0.get("rota", {}).get("slots") == default_slots() and st0.get("usage") == {"stop": USAGE_STOP, "points": []}
               and all(st0.get(k) == [] for k in ("queue", "blockers", "log", "checkpoints", "failures", "notes",
                                                  "research_review", "decisions")), st0)
        before = g["STATE"].read_bytes()
        rc, said = quiet(init_state)
        expect("init refuses to overwrite an existing state (exit 3, the file untouched)",
               rc == 3 and "refused" in said and g["STATE"].read_bytes() == before, said)
        result, said = quiet(build)
        expect("after init the state line is gone from Needs attention and the fresh state gives no warning",
               "no state yet" not in g["OUT"].read_text(encoding="utf-8") and result[3] == [], result[3])
        g["STATE"].write_text("{}", encoding="utf-8")
        try:
            result, said = quiet(build)
            err = None
        except Exception as e:
            err = f"{type(e).__name__}: {e}"
        expect("an empty state ({}) still builds a page and a brief", err is None and quiet(brief, *build(write=False))[0] in (0, 1), err)
        expect("... and its gaps were filled in memory only", g["STATE"].read_text(encoding="utf-8") == "{}")
        g["STATE"].write_bytes(before)

        # the decisions register
        ask = ["decide", "ask", "--by", "FDR-1", "--question", "Ship the importer in M12 or after?", "--options",
               "in M12 | after M12", "--recommend", "after M12", "--needed-before", "M12", "--brief", "docs/decisions/D1-importer.md"]
        rc, said = quiet(edit_state, ask, write=False)
        expect("decide ask with write=False checks and writes nothing", rc == 0 and "checked, not written" in said
               and g["STATE"].read_bytes() == before, said)
        rc, said = quiet(edit_state, ask)
        decs = json.loads(g["STATE"].read_text(encoding="utf-8")).get("decisions", [])
        expect("decide ask files D1, open, with every field of the register",
               rc == 0 and "D1 filed" in said and len(decs) == 1 and decs[0]["id"] == "D1" and decs[0]["status"] == "open"
               and decs[0]["by"] == "FDR-1" and decs[0]["options"] == ["in M12", "after M12"]
               and decs[0]["recommend"] == "after M12" and decs[0]["needed_before"] == "M12" and decs[0]["answer"] == ""
               and decs[0]["answered"] == "" and decs[0]["brief"] == "docs/decisions/D1-importer.md"
               and parse_or_none(decs[0]["asked"]) is not None, decs)
        rc, said = quiet(edit_state, ["decide", "ask", "--by", "MGR-2", "--question", "Second question?"])
        decs = json.loads(g["STATE"].read_text(encoding="utf-8"))["decisions"]
        expect("the next ask is D2, newest first", rc == 0 and [d["id"] for d in decs] == ["D2", "D1"], decs)
        for what, argv in (("ask with no question", ["decide", "ask", "--by", "FDR-1"]),
                           ("ask with no --by", ["decide", "ask", "--question", "q"]),
                           ("answer with empty words", ["decide", "answer", "D1", "--words", "   "]),
                           ("answer with no --words", ["decide", "answer", "D1"]),
                           ("answer to an unknown id", ["decide", "answer", "D9", "--words", "yes"]),
                           ("an option of another form (answer --question)", ["decide", "answer", "D1", "--question", "q"]),
                           ("an option decide does not have", ["decide", "answer", "D1", "--lane", "G1"]),
                           ("withdraw with no note", ["decide", "withdraw", "D2"]),
                           ("an unknown form", ["decide", "close", "D1"])):
            was = g["STATE"].read_bytes()
            rc, said = quiet(edit_state, argv)
            expect(f"decide: {what} is refused (exit 2) and nothing is written", rc == 2 and g["STATE"].read_bytes() == was, said)
        S1 = read_state()[0]
        attn = [t for _, grp, t, _ in attention(S1, {}, g["read_crew"](S1, now), {"seats": [], "queue": []}, now) if grp == "the user"]
        expect("an open decision is under Needs attention as 'waits on the user', with what needs it",
               any(t.startswith("D1 waits on the user (needed before M12): Ship the importer") for t in attn)
               and any(t.startswith("D2 waits on the user: Second question?") for t in attn), attn)
        rc, said = quiet(brief, *build(write=False))
        j = json.loads(said)
        expect("brief lists the open decisions in decisions_open, newest first",
               [d["id"] for d in j["decisions_open"]] == ["D2", "D1"] and j["decisions_open"][1]["needed_before"] == "M12",
               j.get("decisions_open"))
        rc, said = quiet(edit_state, ["decide", "answer", "D1", "--words", "After M12. Keep M12 small."])
        decs = {d["id"]: d for d in json.loads(g["STATE"].read_text(encoding="utf-8"))["decisions"]}
        expect("decide answer records the user's own words and the time",
               rc == 0 and decs["D1"]["status"] == "answered" and decs["D1"]["answer"] == "After M12. Keep M12 small."
               and parse_or_none(decs["D1"]["answered"]) is not None, decs["D1"])
        rc, said = quiet(edit_state, ["decide", "answer", "D1", "--words", "again"])
        expect("an answered decision is not answered twice", rc == 2 and "already answered" in said, said)
        rc, said = quiet(edit_state, ["decide", "withdraw", "D2", "--note", "the importer was dropped"])
        decs = {d["id"]: d for d in json.loads(g["STATE"].read_text(encoding="utf-8"))["decisions"]}
        expect("decide withdraw closes the question with its note",
               rc == 0 and decs["D2"]["status"] == "withdrawn" and decs["D2"]["note"] == "the importer was dropped", decs["D2"])
        rc, said = quiet(edit_state, ["decide", "ask", "--by", "FDR-1", "--question", "Third?"])
        rc, said = quiet(decide_list, [])
        expect("decide list prints the register newest first, with the answer and the open count",
               rc == 0 and said.splitlines()[0] == "3 decision(s), 1 open" and [l.split()[0] for l in said.splitlines()[1:]]
               == ["D3", "D2", "D1"] and "-> After M12. Keep M12 small." in said, said)
        rc, said = quiet(decide_list, ["--open"])
        expect("decide list --open prints only the open ones", rc == 0 and "D3 open" in said and "D1" not in said and "D2" not in said, said)
        expect("decide list refuses anything but --open", quiet(decide_list, ["--all"])[0] == 2)
        result, said = quiet(build)
        page = g["OUT"].read_text(encoding="utf-8")
        sect = page[page.find('<h2 id="decisions">'):page.find('<h2 id="research">')]
        expect("the page's Decisions section shows the open question, and folds the answered and withdrawn ones",
               "Third?" in sect and "2 answered or withdrawn" in sect and "After M12. Keep M12 small." in sect
               and "D3 waits on the user: Third?" in page, sect[:300])
        expect("the register's ids and statuses give no warning", not [w for w in result[3] if "ecision" in w], result[3])
        S2 = read_state()[0]
        S2["decisions"].append({"id": "D3", "question": "dup", "status": "maybe"})
        w = consistency(S2, {}, {"head": "?", "dirty": []}, now, g["read_crew"](S2, now))
        expect("a decision id used twice and a status the map does not know both warn",
               any("D3 is used more than once" in x for x in w) and any("'maybe'" in x for x in w), w)
        try:
            write_state({"decisions": ["D4"]}, tmp / "bad.json")
            err = None
        except ValueError as e:
            err = str(e)
        expect("write_state refuses a decision that is not an object, and writes nothing",
               err is not None and "state.decisions[0]" in err and not (tmp / "bad.json").exists(), err)
        expect("decide is held during a counted run like note (it is one of the edits)", "decide" in EDITS and "note" in EDITS)
        expect("the selftest's project folder holds only its state and its map",
               sorted(p.name for p in proj.rglob("*") if p.is_file()) == ["progress-map.html", "state.json"],
               str(sorted(p.name for p in proj.rglob("*"))))
    finally:
        g.update(keep)
        shutil.rmtree(tmp, ignore_errors=True)

    # a linked worktree's writing command is refused when it would write the map's files inside that worktree
    wt, mc = Path("/x/main/.claude/worktrees/agent-1"), Path("/x/main")
    in_wt = (wt / "docs" / "progress" / "state.json", wt / "docs" / "progress-map.html")
    why = worktree_write_refusal("fail", wt, mc, in_wt)
    expect("a worktree's board.py fail that would write its own state.json and map is refused, both named",
           bool(why) and "docs/progress/state.json and docs/progress-map.html" in why and "office.py fail" in why, why)
    expect("the main checkout writes its map", worktree_write_refusal("note", mc, mc,
           (mc / "docs" / "progress" / "state.json", mc / "docs" / "progress-map.html")) is None)
    expect("a worktree run whose targets are scratch copies outside it (the guard test's) is not refused",
           worktree_write_refusal("build", wt, mc, (Path("/tmp/s/state.json"), Path("/tmp/s/map.html"))) is None)
    why = worktree_write_refusal("build", wt, mc, (Path("/tmp/s/state.json"), wt / "docs" / "progress-map.html"))
    expect("one target inside the worktree is enough to refuse, and only it is named",
           bool(why) and "would write docs/progress-map.html here" in why, why)

    # build, check and open write only the map, so their worktree run with only FOUNDRY_PATHS_MAP moved to scratch is
    # not refused, and a refusal names the map alone; init, promote and the edit forms still name both
    st_wt, scratch_out = wt / "docs" / "progress" / "state.json", Path("/tmp/s/map.html")
    guard_was = os.environ.get("FOUNDRY_SWEEP_GUARD")
    os.environ["FOUNDRY_SWEEP_GUARD"] = "1"  # a counted checkout's build replays held edits into STATE
    why = worktree_write_refusal("build", wt, mc, write_targets("build", st_wt, scratch_out))
    expect("with FOUNDRY_SWEEP_GUARD=1 a worktree's board.py build counts state.json and stays refused",
           bool(why) and "would write docs/progress/state.json here" in why, why)
    os.environ["FOUNDRY_SWEEP_GUARD"] = "0"  # the cases below are a worktree's, wherever the selftest runs
    for c in ("build", "check", "open"):
        expect(f"a worktree's board.py {c} with only the map moved to scratch is not refused",
               worktree_write_refusal(c, wt, mc, write_targets(c, st_wt, scratch_out)) is None,
               str(write_targets(c, st_wt, scratch_out)))
    why = worktree_write_refusal("build", wt, mc, write_targets("build", st_wt, wt / "docs" / "progress-map.html"))
    expect("a worktree's board.py build refusal names only the map, not state.json",
           bool(why) and "would write docs/progress-map.html here" in why and "state.json" not in why.split("here")[0], why)
    for c in ("note", "fail", "promote", "init", "decide"):
        why = worktree_write_refusal(c, wt, mc, write_targets(c, st_wt, scratch_out))
        expect(f"a worktree's board.py {c} still writes state.json, so it stays refused with the map moved",
               bool(why) and "would write docs/progress/state.json here" in why, why)
    if guard_was is None:
        os.environ.pop("FOUNDRY_SWEEP_GUARD", None)
    else:
        os.environ["FOUNDRY_SWEEP_GUARD"] = guard_was
    g["LANE_NAME"] = lane_was

    # every case runs before the ok/FAIL lines print, so a failing one is named
    src = inspect.getsource(selftest)
    tail = src[src.rfind("for w in ok:"):]
    expect("no selftest case sits after the ok/FAIL print loops (a failure there would print no FAIL line)",
           "expect(" not in tail, tail[:200])

    for w in ok:
        print(f"  ok   {w}")
    for w in bad:
        print(f"  FAIL {w}")
    print(f"board selftest: {len(ok)} ok, {len(bad)} failed")
    return 1 if bad else 0


def main(argv):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # a console may default to a legacy code page
    cmd = argv[1] if len(argv) > 1 else "build"
    if cmd == "selftest":
        return selftest()
    if cmd not in ("build", "init", "check", "open", "promote", "brief", "pending", "stamp") + EDITS:
        print(__doc__)
        return 2
    if cmd == "brief":
        keys = next((x.split("=", 1)[1] for x in argv[2:] if x.startswith("--keys=")), None)
        if "--keys" in argv[2:]:
            i = argv.index("--keys", 2)
            keys = argv[i + 1] if i + 1 < len(argv) else ""
        return brief(*build(write=False), full="--full" in argv[2:],
                     keys=[k.strip() for k in keys.split(",") if k.strip()] if keys is not None else None)
    if cmd == "stamp":
        print(dt.datetime.now().astimezone().isoformat(timespec="minutes"))
        return 0
    if cmd == "decide" and argv[2:3] == ["list"]:
        return decide_list(argv[3:])  # reads only
    if cmd == "check" and "--no-build" in argv[2:]:
        # an employee comparing warnings must not rebuild the map (in the main checkout that dirties the tree a
        # counted run samples). Read-only: no held edit is applied, nothing is written.
        print("the map was NOT rebuilt: check --no-build reads only")
        return check(*build(write=False), rebuilt=False)
    sweeps = sweep_hold()
    if cmd == "pending":
        held = read_pending()
        print(f"{len(held)} edit(s) held" + (f"; counted sweep in the resource queue: {', '.join(r['text'] for r in sweeps)}" if sweeps else
                                             "; no counted sweep: the next build, check, note, usage or block run in "
                                             "the main checkout applies them"))
        for h in held:
            print(f"  {h.get('at')}  {' '.join(map(str, h.get('argv', [])))}" + (f"   FAILED: {h['failed']}" if h.get("failed") else ""))
        return 0
    why_wt = worktree_write_refusal(cmd, ROOT, P.main, write_targets(cmd, STATE, OUT))
    if why_wt:
        print(f"refused: {why_wt}")
        return 3
    if sweeps:
        dead = all(r["dead"] for r in sweeps)
        why = (f"a counted sweep is in the resource queue ({', '.join(r['text'] for r in sweeps)}): nothing in this "
               "checkout may change until it ends"
               + (f"; it looks DEAD (did the host restart?): check {RQ} status, and if no sweep is running, the manager "
                  f"frees its seats with {RQ} force-release" if dead else ""))
        if cmd in ("promote", "init"):
            print(f"refused: {why}")
            return 3
        if cmd in EDITS:
            rc = edit_state(argv[1:], write=False)
            if rc:
                return rc
            try:
                hold_edit(argv[1:], dt.datetime.now().astimezone())
            except office.Refused as e:
                print(f"NOT held and not written: {e}. {why}. Run the command again.")
                return 5
            print(f"held, not written: {why}. It is applied with this time by the next writing command run in the main "
                  "checkout after the sweep (board.py pending lists what is held).")
            return 4 if dead else 0
        result = build(write=False)
        print(f"the map was NOT rebuilt: {why}")
        if cmd == "check":
            return check(*result, rebuilt=False)
        for w in result[3]:
            print(f"  ! {w}")
        return 0
    apply_pending()
    rc = (init_state() if cmd == "init" else promote() if cmd == "promote" else
          edit_state(argv[1:]) if cmd in EDITS else 0)
    if rc and cmd in EDITS + ("init",):
        return rc
    result = build()
    if cmd in ("build", "init", "promote") + EDITS:
        print(f"wrote {out_name()}; {len(result[3])} warning(s)")
        for w in result[3]:
            print(f"  ! {w}")
        return rc
    if cmd == "check":
        return check(*result)
    import webbrowser
    webbrowser.open(OUT.as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
