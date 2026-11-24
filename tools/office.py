#!/usr/bin/env python3
"""Foundry crew office: badges, the time clock and the roster for the founder, the one manager and its employees.

    office.py found --name NAME [--relieve] [--session local_...]
                                                    mint the one FOUNDER badge (id FDR-n; refused while another founder
                                                    badge is on the clock, unless --relieve). The founder is outside
                                                    the headcount and never hires: it clocks in, posts progress and
                                                    clocks out, and the roster shows it on its own line above the manager
    office.py appoint --name NAME [--relieve] [--session local_...] [--this-slot | --slot day|swing|night]
                                                    mint the one MANAGER badge (refused while another is fresh)
    office.py hire --by MGR_LINE --name N (--role R | --title T) --kind session|temp --job TEXT --eta 90m
                   [--lane G1] [--rq | --seat NAME] [--files TEXT] [--done-when TEXT] [--force-files] [--adr]
                   [--model ID [--force-model]]
                                                    --role: builder, grader, reviewer or scout;
                                                    --title: the card the badge is hired on, which sets the role
                                                    (see Titles below); refused when the title is unknown, its
                                                    profile card is broken, or the kind is not one the card allows;
                                                    --rq: the badge reaches the shared resource through rq.py run
                                                    --id <its id> (any seat); --seat: one seat of its own;
                                                    --adr: reserve the next decision-record number for it;
                                                    --model: the model the brief names, kept on the roster (for a
                                                    flagged title a model other than its own needs --force-model)
    office.py assign ID --session local_... [--by MGR_LINE] [--dry-run]
                                                    record the session that start_session returned (a manager's or a
                                                    founder's too); --by, when given, is the manager's line
    office.py amend ID --by MGR_LINE [--job TEXT] [--add-files TEXT | --set-files TEXT] [--done-when TEXT]
                   [--eta 2h] [--rq | --seat NAME]  widen, narrow or reword a badge's job; logged in the time clock
    office.py brief ID --by MGR_LINE                reprint a badge's line and its brief as the roster has it now
    office.py clock-in --badge LINE
    office.py progress --badge LINE --pct N [--eta 40m|17:50] [--note TEXT] [--waiting-on EMP-07|MGR-3-counted]
                   [--run DIR]                      --waiting-on: not STALE or OVERDUE while that badge's (or queue
                                                    id's) job holds a seat or waits in the queue;
                                                    --run: a run folder of yours, recorded by its absolute
                                                    path so a grader finds it without a relay
    office.py me --badge LINE                       your own record: the brief again, what the manager amended,
                                                    the manager on the clock, a freeze (the manager's, or a counted
                                                    run in the queue), your place in
                                                    the queue and an estimate of its start; writes nothing
    office.py status [--badge LINE]                 `me` with a badge, the roster without one
    office.py runs [--id EMP-07]                    the run folders the crew posted (newest first)
    office.py handin --badge LINE [--base main] [--commits a,b] [--file REPORT.md] [--repo DIR --by MGR_LINE]
                                                    run in your own worktree before clock-out: checks the
                                                    branch against your badge (owned files, a clean tree,
                                                    main's place, git config, the gym's pins, the project's
                                                    own hand-in check) and writes <office>/handins/<ID>.md
                                                    with the report file's text;
                                                    --repo and --by: the manager runs it for an employee
    office.py fail --badge LINE --what TEXT [--lane L] [--run-id R] [--verdict V] [--plan TEXT]
    office.py clock-out --badge LINE --result done|partial|failed|handed-off [--note TEXT] [--commits a,b]
    office.py clock-out --by MGR_LINE --id EMP-07 --result lost [--note TEXT]
    office.py roster [--json]                       who is on the clock, their job, % and approximate finish,
                                                    and the shared resource's seats: who holds each, who waits
    office.py end-shift --by MGR_LINE [--lose-temps] [--out crew.json]
                                                    the slot's crew summary; a temp still working stays on
                                                    the clock (--lose-temps clocks every temp out as lost)
    office.py freeze on --by MGR_LINE --why TEXT [--lane G1] [--max 3h]   (--max takes a unit: 30m, 3h)
    office.py freeze off --by MGR_LINE [--note TEXT] [--force]   (--force: lift a counted sweep's own freeze)
    office.py freeze show [--json]                  hold the main checkout still for a counted run, with or without
                                                    a shared resource: the roster and every `me` say FREEZE while it
                                                    is on, and past --max it reads STALE. on and off are punches in
                                                    the time clock; a second `on` is refused until `off`
    office.py round [--by MGR_LINE] [--json]        the manager's wake-up: what needs the manager, most pressing
                                                    first (usage, what waits on the user, a counted run or freeze,
                                                    reports not filed, new hand-ins, STALE or OVERDUE crew, the
                                                    journal's plan), then the crew, the seats and `first: ...`.
                                                    With --by it also posts the manager's heartbeat and marks the
                                                    listed hand-ins seen; without it, it writes nothing
    office.py handoff --by MGR_LINE [--out FILE]    write the next manager's hand-off brief as Markdown (default
                                                    <office>/briefs/handoff-<slot>-<YYYYMMDD>.md) and print its
                                                    path; three sections are left for the manager to fill by hand.
                                                    Never overwrites: a second call writes <name>-2
    office.py timers init --by MGR_LINE             write <office>/manager-timers.json when it is missing: the round,
                                                    and each slot's hand-off (40 min before its end) and start
    office.py timers show                           print the list and check its shape (exit 1: a bad entry, or no
                                                    file). The tool creates no timer: the manager creates them in
                                                    its session, and this file is the list
    office.py verify LINE | badge ID                check a line; redraw a plate
    journal.py ...                                  the shift journal (holes, failures, improvements and their
                                                    action plan), its own script on this office's badges
    office.py selftest

Exit codes: 0 done; 1 a check that found something (handin NOT READY, timers show with a bad entry or no file);
2 a command line that cannot be read, or a --files path whose folder is missing; 3 refused (the message says why).

Titles. A badge is hired on a card. The built-in cards: builder and fixer (role BUILDER, session or temp), grader
(GRADER, session only, independent), reviewer (REVIEWER, session or temp, independent), scout, triager and cleaner
(SCOUT, temp or session). A card says what the title does, what it may write and what it hands in, and the brief
prints it as "Your card (title)". --role alone hires on the role's own card. A project adds or changes a card in
the profile:

    [titles.auditor]
    like = "reviewer"                 # a built-in card to start from
    kinds = ["session"]               # and any of: role, kinds, does, may_write, hands_in, independent

Models. The brief prints `Model: <id>` when the profile's [models] names the title or the role (the title first),
or when the hire gave --model. A title with a [flagged.<title>] table (model, trailer) is built on that model, the
brief says every commit ends with the trailer, and handin makes a commit without the trailer line a PROBLEM. The
brief's push rule follows git.push: false (the default) is "no push"; true is "push only your own branch, never the
main branch".

Office files this adds: freeze.json ({"by", "why", "lane", "at", "max_s"}; absent means no freeze; other tools read
it through freeze_facts()), handins-seen.json ({"seen": {file name: its time stamp}, "at", "by"}),
manager-timers.json ({"timers": [{"name", "recurring", "every" or "at", "prompt"}]}) and briefs/handoff-*.md.

A badge is one signed line that starts with the profile's badge prefix, drawn as a QR plate (HMAC-SHA256, base32,
QR alphanumeric). Clocking in is presenting the line; every punch is appended to timeclock.jsonl and the roster is
worked out from it. Everything lives in the office folder of the main checkout (paths.office in
.foundry/foundry.toml, git-ignored), so a session in any worktree reaches the same office; FOUNDRY_PATHS_OFFICE
overrides it. The key sits next to the roster: a badge stops mix-ups and keeps an honest record, it is not
security against a session that sets out to cheat (a claim, never a credential).

Every project fact comes from the profile (foundry_profile.py): the crew's name and the other crews' lesson
files, the badge prefix, the limits, the rota's default slots, the shared resource and its seats, the gym's
folders, the hand-in check. With no [resource] name the office prints no queue lines and refuses --rq and --seat.
Standard library plus segno (for the plates only).
"""

import argparse
import base64
import contextlib
import datetime as dt
import hashlib
import hmac
import json
import os
import re
import secrets
import subprocess
import sys
import time
from pathlib import Path

if len(sys.argv) > 1 and sys.argv[1] in ("selftest", "_stress"):
    sys.dont_write_bytecode = True  # the selftest writes nothing outside its temp folder, a .pyc included
sys.path.insert(0, str(Path(__file__).resolve().parent))
import foundry_profile as fp  # noqa: E402

P = fp.load(__file__)
ROOT = P.root

def _env_key():
    return tuple(sorted((k, v) for k, v in os.environ.items() if k.startswith("FOUNDRY_") and k != "FOUNDRY_NOW"))


_PROFILES = {_env_key(): P}


def prof():
    """The profile in force now. fp.load reads the environment when it is called, and the selftest changes the
    environment mid-run, so every function asks here instead of keeping the P of import time. One load per
    distinct set of FOUNDRY_ variables."""
    key = _env_key()
    if key not in _PROFILES:
        _PROFILES.clear()
        _PROFILES[key] = fp.load(__file__)
    return _PROFILES[key]


def crew_name():
    """This crew's short name (the profile's crew; FOUNDRY_CREW overrides it)."""
    return prof().crew


def lessons():
    """{other crew: the file, or the list of files, where its lessons for this crew lie}: FOUNDRY_LESSONS (JSON)
    when set, else the profile's [crews] table (name -> {"lessons": path or list}). journal.py carry and take read it."""
    env = os.environ.get("FOUNDRY_LESSONS")
    if env:
        try:
            raw = json.loads(env)
        except ValueError:
            raw = {}
        return raw if isinstance(raw, dict) else {}
    out = {}
    for name, c in (prof().get("crews") or {}).items():
        out[str(name)] = (c.get("lessons") if isinstance(c, dict) else c) or []
    return out


CREW = crew_name()
LESSONS = lessons()

LOCK_STALE_S = 30          # a lock file older than this was left by a dead process
APPOINT_LEAD_S = 20 * 60   # a manager appointed this close before a slot starts is that slot's manager
SLOT_PICK_LEAD_S = 60 * 60  # appoint --slot names the slot now or the next one starting within this
ROLES = ("FOUNDER", "MANAGER", "BUILDER", "GRADER", "REVIEWER", "SCOUT")
TOP = ("FOUNDER", "MANAGER")  # outside the headcount, never OVERDUE, never hired
KINDS = ("SESSION", "TEMP")
RESULTS = ("done", "partial", "failed", "handed-off", "lost", "relieved")
FIELDS = ("ID", "NAME", "ROLE", "KIND", "SHIFT", "SLOT", "ISSUED")
QR_ALNUM = set("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ $%*+-./:")
_SLOTS = [{"id": "day", "start": "06:00"}, {"id": "swing", "start": "14:00"}, {"id": "night", "start": "22:00"}]


def default_slots():
    """The rota a state.json with no rota.slots is read by: the profile's [slots]."""
    return prof().slots() or _SLOTS


DEFAULT_SLOTS = default_slots()


def limit_s(name):
    """A limit of the profile's [limits], given there in minutes, as seconds: stale_min (an employee not heard from
    for this long reads STALE), manager_stale_min (a manager or founder posts at every block end; past this it reads
    STALE and can be relieved), overdue_min (past its approximate finish by this much reads OVERDUE)."""
    fallback = {"stale_min": 45, "manager_stale_min": 120, "overdue_min": 15}[name]
    try:
        return int(float(prof().get("limits." + name, fallback)) * 60)
    except (TypeError, ValueError):
        return fallback * 60


def main_branch():
    return str(prof().get("main_branch") or "main")


def badge_prefix():
    """The first word of every badge line. A plate holds QR-alphanumeric text only, so anything else is dropped."""
    p = "".join(ch for ch in prof().badge_prefix if ch in QR_ALNUM and ch not in " :")
    return p or "FB1"


try:  # optional: draws the badges' QR plates
    import segno as _segno  # noqa: F401
    HAVE_SEGNO = True
except ImportError:
    HAVE_SEGNO = False


class Refused(Exception):
    """A punch or a hire the office will not take; the message says why."""


def main_checkout():
    return prof().main


def office_dir():
    return prof().path("office")


def state_file():
    return prof().path("state")


def tool(name="office.py"):
    """A Foundry tool's command line as a brief or a refusal prints it."""
    return prof().tool(name)


def now_ts():
    env = os.environ.get("FOUNDRY_NOW")  # the selftest's injected clock
    return float(env) if env else time.time()


def local(ts):
    return dt.datetime.fromtimestamp(ts).astimezone()


def hhmm(ts, ref=None):
    if ts is None:
        return "—"
    d = local(ts)
    return f"{d:%H:%M}" if local(ref if ref is not None else now_ts()).date() == d.date() else f"{d:%m-%d %H:%M}"


def ago(seconds):
    m = int(round(seconds / 60))
    return f"{m} min" if abs(m) < 90 else f"{m / 60:.1f} h"


def token(s, n=24):
    """A free-text value as QR-alphanumeric: upper case, anything else a dash, no spaces or colons."""
    t = re.sub(r"[^0-9A-Z$%*+\-./]+", "-", str(s).upper()).strip("-")
    return re.sub(r"-{2,}", "-", t)[:n] or "NA"


def parse_dur(s, unit=False):
    """90m, 2h, 1h30m, 45 (minutes) -> seconds. With unit=True a bare number is refused, as rq.py and sweep.py
    refuse one (freeze --max); --eta alone still reads a bare number as minutes."""
    if unit and re.fullmatch(r"\s*\d+(?:\.\d+)?\s*", str(s)):
        raise Refused(f"cannot read the duration {s!r}: write a unit: 30m, 3h")
    m = re.fullmatch(r"\s*(?:(\d+(?:\.\d+)?)h)?\s*(?:(\d+)m?)?\s*", str(s))
    if not m or not (m.group(1) or m.group(2)) or (unit and m.group(2) and not str(s).strip().endswith("m")):
        raise Refused(f"cannot read the duration {s!r}; write 90m, 2h or 1h30m")
    return int(float(m.group(1) or 0) * 3600 + int(m.group(2) or 0) * 60)


def parse_eta(s, now):
    """A clock time (17:50, today or the next day) or a duration from now -> epoch seconds."""
    m = re.fullmatch(r"\s*(\d{1,2}):(\d{2})\s*", str(s))
    if not m:
        return now + parse_dur(s)
    d = local(now).replace(hour=int(m.group(1)), minute=int(m.group(2)), second=0, microsecond=0)
    if d.timestamp() < now - 3600:
        d += dt.timedelta(days=1)
    return d.timestamp()


# --- the state the manager keeps (the shift, its headcount, the rota's slots) ---

def read_state():
    f = state_file()
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def slot_at(slots, ts):
    """(slot id, start, end) of the rota slot holding ts; slots are daily start times, the last wraps past midnight."""
    slots = sorted(slots or default_slots(), key=lambda s: s["start"])
    d = local(ts)
    starts = []
    for back in (1, 0, -1):
        day = d.date() - dt.timedelta(days=back)
        for s in slots:
            h, m = map(int, s["start"].split(":"))
            starts.append((dt.datetime.combine(day, dt.time(h, m), d.tzinfo), s["id"]))
    starts.sort()
    for (t0, sid), (t1, _) in zip(starts, starts[1:]):
        if t0 <= d < t1:
            return sid, t0.timestamp(), t1.timestamp()
    return slots[0]["id"], d.timestamp(), d.timestamp()


def manager_slot(slots, ts, lead=APPOINT_LEAD_S):
    """(slot id, start, end) of the slot a manager appointed at ts is for: the slot holding ts, or the next
    slot when it starts within `lead` of ts, so a manager appointed at 13:5x for the 14:00 slot is that slot's manager
    and reads its rota entry and its end."""
    sid, s0, s1 = slot_at(slots, ts)
    if s1 > ts and s1 - ts <= lead:
        return slot_at(slots, s1)
    return sid, s0, s1


def named_slot(slots, sid, ts):
    """(slot id, start, end) of the slot `sid` holding ts, or its next start after ts (appoint --slot); None
    when the rota has no such slot."""
    if sid not in {s["id"] for s in (slots or default_slots())}:
        return None
    cur = slot_at(slots, ts)
    for _ in range(len(slots or default_slots()) + 1):
        if cur[0] == sid:
            return cur
        cur = slot_at(slots, cur[2])
    return None


def picked_slot(slots, b, ts):
    """(slot id, start, end) of the next slot a badge minted by `appoint --slot` named (its `slot_start`),
    when that slot starts within SLOT_PICK_LEAD_S after both the badge's issue and ts; otherwise None. A manager
    re-badged at 05:32 with --slot day is the day slot's manager from 05:32, for its clock-in and its hires."""
    st, sid = b.get("slot_start"), b.get("slot")
    if not st or not sid:
        return None
    if not (0 < st - ts <= SLOT_PICK_LEAD_S and 0 < st - b.get("issued", ts) <= SLOT_PICK_LEAD_S):
        return None
    got = slot_at(slots, st)
    return got if got[0] == sid else None


def hire_slot(slots, mgr, ts):
    """The slot a hire made at ts by the manager badge `mgr` (its roster record) is stamped with:
    - a badge with no slot recorded (an older format): the clock look-ahead, manager_slot (the slot holding ts, or
      the next one within APPOINT_LEAD_S);
    - the next slot a badge minted by `appoint --slot` named, in the hour before it starts (picked_slot);
    - the manager's own slot when it is the slot holding ts or the next one within APPOINT_LEAD_S (night
      crew hired at 21:5x, a --this-slot manager near the boundary);
    - otherwise the slot holding ts, so a manager whose badge names a slot that has ended (re-badged at 05:32,
      SLOT:NIGHT) hires day crew from 06:00."""
    mslot = mgr.get("slot")
    if not mslot:
        return manager_slot(slots, ts)[0]
    if picked_slot(slots, mgr, ts):
        return mslot
    here = slot_at(slots, ts)[0]
    return mslot if mslot in (here, manager_slot(slots, ts)[0]) else here


def badge_slot(slots, b, lead=APPOINT_LEAD_S):
    """(slot id, start, end) of the badge's own slot as it clocked in, or None: the slot holding its
    clock-in when that is the badge's slot; the next slot a badge minted by `appoint --slot` named, when it was issued
    and clocked in within SLOT_PICK_LEAD_S of its start; or the next slot when the badge names it and it
    starts within `lead` of the clock-in (a manager appointed and clocked in just before the boundary)."""
    sid, s0, s1 = slot_at(slots, b["in_at"])
    if not b.get("slot") or sid == b.get("slot"):
        return sid, s0, s1
    picked = picked_slot(slots, b, b["in_at"])
    if picked:
        return picked
    if s1 - b["in_at"] <= lead:
        nxt = slot_at(slots, s1)
        if nxt[0] == b.get("slot"):
            return nxt
    return None


def shift_facts(state):
    sh = state.get("shift", {})
    return sh.get("id", "none"), sh.get("crew_max")


# --- the office's files ---

@contextlib.contextmanager


def locked(d):
    d.mkdir(parents=True, exist_ok=True)
    p = d / ".lock"
    t0 = time.time()
    while True:
        try:
            fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except (FileExistsError, PermissionError):  # some systems say PermissionError while the holder is deleting it
            try:
                if time.time() - p.stat().st_mtime > LOCK_STALE_S:
                    p.unlink()
                    continue
            except (FileNotFoundError, PermissionError):
                pass
            if time.time() - t0 > 20:
                raise Refused(f"the crew office is locked ({p}); a punch is in progress, try again")
            time.sleep(0.02)
    try:
        os.write(fd, str(os.getpid()).encode())
        yield
    finally:
        os.close(fd)
        p.unlink(missing_ok=True)


def load_key(d):
    f = d / "badge_key.json"
    if not f.exists():  # written once, never replaced: a new key would void every badge out there
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps({"v": 1, "key": secrets.token_hex(32), "created": int(time.time()),
                                 "note": "crew badges; never replace"}) + "\n", encoding="utf-8")
    return bytes.fromhex(json.loads(f.read_text(encoding="utf-8"))["key"])


def read_roster(d):
    f = d / "roster.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {"v": 1, "manager": None, "badges": {}}


def write_roster(d, roster):
    tmp = d / "roster.json.tmp"
    body = json.dumps(roster, indent=1, ensure_ascii=False) + "\n"
    try:
        tmp.write_text(body, encoding="utf-8", newline="\n")
    except OSError:  # a transient open failure passes on one retry
        time.sleep(0.2)
        tmp.write_text(body, encoding="utf-8", newline="\n")
    for _ in range(50):
        try:
            os.replace(tmp, d / "roster.json")
            return
        except OSError:  # some systems will not replace a file a reader (the map's build) has open this instant
            time.sleep(0.05)
    os.replace(tmp, d / "roster.json")


def read_events(d):
    f = d / "timeclock.jsonl"
    if not f.exists():
        return []
    return [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines() if l.strip()]


def append_event(d, ev):
    """Call under the lock: numbers the event (its seq is its line number) and appends it."""
    f = d / "timeclock.jsonl"
    seq = 1 + (sum(1 for l in f.read_text(encoding="utf-8").splitlines() if l.strip()) if f.exists() else 0)
    ev = {"seq": seq, **ev}
    with open(f, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(ev, ensure_ascii=False) + "\n")
    return ev


# --- the badge line ---

def sign(key, body):
    return base64.b32encode(hmac.new(key, body.encode(), hashlib.sha256).digest()[:10]).decode()


def make_line(key, fields):
    body = badge_prefix() + " " + " ".join(f"{k}:{fields[k]}" for k in FIELDS)
    assert set(body) <= QR_ALNUM, body
    return f"{body} SIG:{sign(key, body)}"


def parse_line(line):
    line = " ".join(str(line).split())
    pre = badge_prefix() + " "
    if not line.startswith(pre):
        raise Refused(f"not a {pre.strip()} badge line")
    out = {}
    for part in line[len(pre):].split(" "):
        k, sep, v = part.partition(":")
        if not sep:
            raise Refused(f"badge line field without a colon: {part!r}")
        out[k] = v
    if any(k not in out for k in FIELDS + ("SIG",)):
        raise Refused("badge line lacks a field")
    return out, line


def verify_line(key, roster, line):
    """The badge's roster record if the line is genuine, current and not revoked; Refused otherwise."""
    fields, line = parse_line(line)
    body = line.rsplit(" SIG:", 1)[0]
    if not hmac.compare_digest(sign(key, body), fields["SIG"]):
        raise Refused(f"badge {fields['ID']}: the signature does not match (a changed or mistyped line)")
    rec = roster["badges"].get(fields["ID"])
    if not rec or rec["line"] != line:
        raise Refused(f"badge {fields['ID']} is not on the roster")
    if rec.get("revoked"):
        raise Refused(f"badge {fields['ID']} was revoked at {hhmm(rec['revoked'])}: {rec.get('revoked_why', '')}")
    return rec


def plate(d, rec):
    """The QR plate (segno: error M, alphanumeric, scale 4, border 4), black on white so it scans in dark mode.
    segno is optional: without it the badge is its signed line alone, no plate is drawn, and this returns None."""
    try:
        import segno
    except ImportError:
        return None
    qr = segno.make_qr(rec["line"], error="m", mode="alphanumeric", boost_error=False)
    (d / "badges").mkdir(parents=True, exist_ok=True)
    out = d / "badges" / f"{rec['id']}.svg"
    qr.save(str(out), kind="svg", scale=4, border=4, dark="#000", light="#fff", xmldecl=False, omitsize=True,
            title=f"{rec['id']} {rec['name']} ({rec['role'].lower()})")
    return out


# --- the resource queue (rq.py's files in the office), read by its rules ---
# The keys inside those files are the queue's own and stay as they are: a hold's or a waiter's seat is its `lane`.
# The roster record keeps a badge's seat under `vmdir` and crew() reports under `vm`, for the same reason: the
# tools that read them must not drift.

RQ_STALE_S = 120          # rq.py: a waiter that stopped polling for this long has left the queue
RQ_MAX_S = 1800           # rq.py: a hold's limit when hold.json names none


def has_resource():
    return prof().has_resource()


def res_name():
    """The shared resource as people say it (resource.name)."""
    return str(prof().get("resource.name") or "the shared resource")


def default_seat():
    """The seat a job with no seat named waits for: the first of the profile's resource.seats. Its lock is rq.lock
    and its last-holder file rq.last; another seat S uses rq.lock.S and rq.last.S."""
    s = prof().get("resource.seats") or ["main"]
    return str(s[0]) if isinstance(s, list) and s else "main"


def seat_names(d):
    """The seats: the office's rq.seats (one per line) when it is there, else the profile's resource.seats."""
    try:
        names = [l.strip() for l in (d / "rq.seats").read_text(encoding="utf-8").splitlines()
                 if l.strip() and not l.startswith("#")]
    except (OSError, ValueError):
        names = []
    if not names:
        s = prof().get("resource.seats")
        names = [str(x) for x in s] if isinstance(s, list) else []
    return names or [default_seat()]


def need_resource(flag):
    """--rq and --seat mean nothing without a shared resource."""
    if not has_resource():
        raise Refused(f"{flag}: this project names no shared resource. Name one as `[resource] name` in "
                      ".foundry/foundry.toml (and its seats), then hire again")


def rq_facts(d, now):
    """Who holds each seat and who waits, from rq.seats, rq.lock[.<seat>] and rq.queue.json. A running job is in a
    lock dir only: rq.queue.json lists the waiters. No file, however mangled, raises. With no shared resource in the
    profile there is nothing to read."""
    out = {"holds": [], "queue": [], "seats": []}
    if not has_resource():
        return out
    names, first = seat_names(d), default_seat()
    for seat in names:
        lk = d / ("rq.lock" if seat == first else "rq.lock." + seat)
        if not lk.is_dir():
            continue
        h = {}
        try:
            j = json.loads((lk / "hold.json").read_text(encoding="utf-8"))
            h = j if isinstance(j, dict) else {}
        except (OSError, ValueError):
            pass
        who = h.get("id")
        if not isinstance(who, str) or not who.strip():
            try:
                who = (lk / "holder").read_text(encoding="utf-8").strip() or "unknown"
            except (OSError, ValueError):
                who = "unknown"
        try:
            since = float(h.get("since") or lk.stat().st_mtime)
            mx = float(h.get("max") or RQ_MAX_S)
        except (OSError, TypeError, ValueError):
            since, mx = now, RQ_MAX_S
        out["holds"].append({"lane": seat, "id": who, "job": str(h.get("job") or ""), "since": since, "max": mx,
                             "all": bool(h.get("all")), "prio": h.get("prio"), "overdue": now - since > mx})
    try:
        q = json.loads((d / "rq.queue.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        q = []
    for e in q if isinstance(q, list) else []:
        try:
            if now - float(e["beat"]) <= RQ_STALE_S:
                out["queue"].append({"id": str(e["id"]), "job": str(e.get("job") or ""), "prio": e.get("prio", 5),
                                     "at": float(e["at"]), "beat": float(e["beat"]), "all": bool(e.get("all")),
                                     "max": float(e.get("max") or RQ_MAX_S),
                                     # rq.py: an entry with neither `any` nor `all` waits for one seat, the default
                                     # seat when it names none
                                     "lane": None if e.get("any") or e.get("all") else (e.get("lane") or first)})
        except (KeyError, TypeError, ValueError):
            continue
    out["queue"].sort(key=lambda e: (e["prio"], e["at"]))
    out["seats"] = names
    return out


vm_facts = rq_facts  # the name the other tools knew it by


def rq_start_estimate(rq, bid, now):
    """(time, None) when a badge's first queued job would start if every hold ahead ran to its own --max and every
    waiter ahead took its whole --max; (None, why) when no figure can be given; (None, None) when it does not wait.
    An estimate, not a bound: the queue does not enforce --max, a job at a higher priority can join ahead, jobs the
    profile's resource.exclusive names never run together, and a short job may backfill a seat ahead of a
    whole-resource waiter. Holds also often end sooner."""
    mine = lambda e: e["id"] == bid or e["id"].startswith(bid + "-")
    if not any(mine(e) for e in rq["queue"]):
        return None, None
    first = default_seat()
    free = {s: now for s in rq.get("seats") or [first]}
    over = {}  # a seat whose hold is past its own --max: nothing says when it frees
    for h in rq["holds"]:
        if now > h["since"] + h["max"]:
            over[h["lane"]] = h["id"]
        free[h["lane"]] = max(now, h["since"] + h["max"])
    for e in rq["queue"]:
        if e.get("all"):
            start = max(free.values())
            took = list(free)
        else:
            # as rq.py: a one-seat waiter takes its seat; an any-seat waiter the first to free, a seat other than
            # the default one on a tie. A seat whose hold is overdue is taken last, or a free seat would read
            # "unknown".
            seat = e.get("lane") if e.get("lane") in free else min(free, key=lambda s: (s in over, free[s], s == first))
            start, took = free[seat], [seat]
        late = [s for s in took if s in over]
        if late:  # this job, or one ahead of it, needs a seat that is overdue: no figure can be given
            return None, f"unknown: {over[late[0]]}'s hold on {late[0]} is past its own --max"
        if mine(e):
            return start, None
        for s in took:
            free[s] = start + e.get("max", RQ_MAX_S)
    return None, None


def rq_start_text(b, now):
    """The roster's and me's line for a queued job's start, or ''."""
    if b.get("vm_start_why"):
        return f"start {b['vm_start_why']}"
    if b.get("vm_start") is None:
        return ""
    if b["vm_start"] - now <= 60:
        return "next to start if the seat frees on time"
    return (f"start about {hhmm(b['vm_start'], now)} (in {ago(b['vm_start'] - now)}) if every job ahead runs to its --max "
            "and none joins ahead; an estimate, not a bound")


def rq_of(rq, bid):
    """What a badge is doing with the shared resource: (text, the time that proves it is alive) or (None, None). A
    queue id is the badge id, or the badge id and a suffix (MGR-3-sweep)."""
    mine = lambda e: e["id"] == bid or e["id"].startswith(bid + "-")
    held = [h for h in rq["holds"] if mine(h)]
    if held:
        # a hold has no heartbeat: it counts as alive until its own limit has passed
        alive = None if all(h["overdue"] for h in held) else rq["now"]
        return "holds " + ", ".join(h["lane"] for h in held), alive
    wait = [e for e in rq["queue"] if mine(e)]
    if wait:
        return f"queued (place {1 + rq['queue'].index(wait[0])} of {len(rq['queue'])})", max(e["beat"] for e in wait)
    return None, None


# A sweep of every lane is queued as <badge id>-sweep; a single counted run as <badge id>-counted[-<lane>]: both
# freeze the main checkout. Nothing else matches (a dry run's EMP-5-dry-sweep does not).
SWEEP_ID = re.compile(r"[A-Z]+-\d+-(?:sweep|counted(?:-[0-9A-Z]+)?)", re.I)


# A whole-resource job whose --job text says it is a dev run is not a counted run (a prio-0 one always may be).
# Whole words only: "not counted", "uncounted" and "(dev)", "(dev," or "(dev;" mark a dev run, as does a text that
# starts with "dev" or has "dev run". The bare word "dev" elsewhere does not: "on the dev rig", "dev-built tip" and
# "after the dev fix" are ordinary words in a counted run's text.
DEV_JOB = re.compile(r"^\s*dev\b|\bdev runs?\b|\(dev\s*[,;)]|\bnot counted\b|\buncounted\b", re.I)


def dev_command():
    """The project's dev-run command up to its <lane> (measure.dev): a job text that holds it is a dev run."""
    cmd = str(prof().get("measure.dev") or "").split("<lane>")[0].strip()
    return cmd.lower() if len(cmd) >= 3 else ""


def is_prio0(e):
    """A hand-edited queue may hold prio as the string "0"."""
    return str(e.get("prio")).strip() == "0"


def is_dev_job(e):
    """A counted run is known by its queue id (<badge>-counted[-<lane>], <badge>-sweep) or its prio 0, never by its
    --job text. The text can only mark a plain-id, prio > 0 whole-resource job as dev; a word "counted" in it does
    not undo that (a dev run's text often names the counted run it comes before). The manager's counted form is
    `--id <badge>-counted-<lane> --prio 0`, so a counted run queued by the skill is caught by id or prio."""
    if is_prio0(e):
        return False
    job = str(e.get("job") or "")
    return bool(DEV_JOB.search(job)) or bool(dev_command() and dev_command() in job.lower())


def _plain_whole(rq):
    seen = []
    for e in rq["holds"] + rq["queue"]:
        if (e.get("all") or is_prio0(e)) and not SWEEP_ID.fullmatch(e["id"]):
            seen.append(e)
    return seen


def unmarked_counted(rq):
    """A prio-0 or whole-resource job (a hold or a waiter) whose id is not <badge>-sweep or
    <badge>-counted[-<lane>] is probably a counted run the guard cannot see: the roster and the brief warn, and the
    manager freezes main by hand until it ends. A job whose text marks it a dev run is left out (dev_uncounted)."""
    out = []
    for e in _plain_whole(rq):
        if not is_dev_job(e) and e["id"] not in out:
            out.append(e["id"])
    return out


def dev_uncounted(rq):
    """The whole-resource jobs under a plain id that unmarked_counted skips because their --job text says dev (see
    DEV_JOB and dev_command), named in one short line. An id also flagged is not repeated."""
    flagged, out = set(unmarked_counted(rq)), []
    for e in _plain_whole(rq):
        if is_dev_job(e) and e["id"] not in flagged and e["id"] not in out:
            out.append(e["id"])
    return out


def sweeps_of(rq, now):
    """The counted sweeps and runs holding or waiting for the shared resource. While one is there, nothing in the
    main checkout may change, tracked or not: a counted run checks git status before it measures. One whose every
    hold is past its own limit and that no longer waits is `dead`: probably killed with its session or its host, its
    lock left behind (the manager frees it with rq.py force-release)."""
    out = {}
    for h in rq["holds"]:
        if SWEEP_ID.fullmatch(h["id"]):
            r = out.setdefault(h["id"], {"id": h["id"], "since": h["since"], "dead": True})
            r["since"] = min(r["since"], h["since"])
            r["dead"] = r["dead"] and h["overdue"]
    for e in rq["queue"]:
        if SWEEP_ID.fullmatch(e["id"]):
            out.setdefault(e["id"], {"id": e["id"], "since": e["at"], "dead": False})["dead"] = False
    return [{**r, "text": r["id"] + (f" (DEAD? its hold is past its limit, since {hhmm(r['since'], now)})" if r["dead"] else "")}
            for _, r in sorted(out.items())]


def sweep_ids(rq, now=None):
    return [r["text"] for r in sweeps_of(rq, now_ts() if now is None else now)]


# --- the roster worked out from the punches ---

def crew(d, now=None):
    """Every badge with its clock facts at `now`: on the clock or not, %, approximate finish, last heard, status, hours."""
    now = now_ts() if now is None else now
    roster = read_roster(d)
    events = [e for e in read_events(d) if e["at"] <= now]
    rq = {**rq_facts(d, now), "now": now}
    stale_s, top_stale_s, overdue_s = limit_s("stale_min"), limit_s("manager_stale_min"), limit_s("overdue_min")
    by_id = {}
    for e in events:
        by_id.setdefault(e["id"], []).append(e)
    out = []
    for bid, rec in roster["badges"].items():
        evs = by_id.get(bid, [])
        top = rec["role"] in TOP
        punches = [e for e in evs if e["ev"] in ("in", "out")]
        on = bool(punches) and punches[-1]["ev"] == "in"
        ins = [e for e in punches if e["ev"] == "in"]
        in_at = ins[-1]["at"] if ins else None
        out_ev = punches[-1] if punches and punches[-1]["ev"] == "out" else None
        hours, start = 0.0, None
        for e in punches:
            if e["ev"] == "in":
                start = e["at"]
            elif start is not None:
                hours += (e["at"] - start) / 3600
                start = None
        if start is not None:
            hours += (now - start) / 3600
        prog = [e for e in evs if e["ev"] == "progress" and (in_at is None or e["at"] >= in_at)]
        pct = 100 if out_ev and out_ev.get("result") == "done" else prog[-1].get("pct", 0) if prog else 0
        eta = next((e["eta"] for e in reversed(prog) if e.get("eta")), None)
        if eta is None and in_at is not None:
            eta = in_at + rec.get("eta_s", 0)
        heard = max((e["at"] for e in evs), default=None)
        rq_text, rq_alive = rq_of(rq, bid) if on else (None, None)
        # the last progress post's --waiting-on names whose queued job this badge waits for (a badge id or a queue
        # id); while that job holds a seat or waits in the queue, it proves this badge alive too
        wait_on = (prog[-1].get("waiting_on") if prog else None) if on else None
        w_text, w_alive = rq_of(rq, wait_on) if wait_on else (None, None)
        if w_text:
            rq_text = (rq_text + "; " if rq_text else "") + f"waits on {wait_on} ({w_text})"
            if rq_alive is None or (w_alive is not None and w_alive > rq_alive):
                rq_alive = w_alive
        # its queued or running job proves it is alive; `heard` stays its own last punch
        seen = heard
        if rq_alive is not None and heard is not None and not top:
            seen = max(heard, min(rq_alive, now))
        # a badge whose own job only waits in the queue, or that waits on a live job, is not OVERDUE: its finish
        # moves with the queue, and chasing it only asks for a new estimate. A badge holding a seat itself can still
        # be OVERDUE, and a wait ends when the waited-on hold passes its own --max.
        own_holds = bool(rq_text and rq_text.startswith("holds"))
        waiting = not own_holds and (w_alive is not None or bool(rq_text and rq_text.startswith("queued")))
        if on:
            limit = top_stale_s if top else stale_s
            status = ("STALE" if now - seen > limit else
                      "OVERDUE" if not top and eta and now > eta + overdue_s and not waiting else "UP")
        elif rec.get("revoked") and not punches:
            status = "REVOKED"
        elif out_ev:
            status = "OUT"
        else:
            status = "HIRED"  # not yet clocked in
        # OVERDUE while its own job holds a seat says so, so the manager sees the run is going
        status_text = status
        if status == "OVERDUE" and own_holds:
            mine = [h for h in rq["holds"] if h["id"] == bid or h["id"].startswith(bid + "-")]
            if mine:
                h = mine[0]
                status_text = (f"OVERDUE ({res_name()}: holds {', '.join(x['lane'] for x in mine)}, "
                               f"{int((now - h['since']) // 60)} of {int(h['max'] // 60)} min)")
        rq_start, rq_start_why = rq_start_estimate(rq, bid, now) if on else (None, None)
        out.append({**rec, "on": on, "in_at": in_at, "out_at": out_ev["at"] if out_ev else None,
                    "result": out_ev.get("result") if out_ev else None, "pct": pct, "eta": eta if on else None,
                    "heard": heard, "status": status, "status_text": status_text, "hours": round(hours, 2), "vm": rq_text,
                    "vm_start": rq_start, "vm_start_why": rq_start_why,
                    "run": next((e["run"] for e in reversed(prog) if e.get("run")), None),
                    "note": next((e.get("note") for e in reversed(evs) if e.get("note")), ""),
                    # null when no plate was drawn (no segno): never the name of a file that is not there
                    "plate": str(d / "badges" / f"{bid}.svg") if (d / "badges" / f"{bid}.svg").is_file() else None})
    return {"dir": str(d), "now": now, "founder": roster.get("founder"), "manager": roster.get("manager"), "badges": out,
            "reports": [e for e in events if e["ev"] == "fail"], "freeze": freeze_facts(d, now),
            "vm": {"holds": rq["holds"], "queue": rq["queue"], "sweeps": sweep_ids(rq, now),
                   "unmarked": unmarked_counted(rq), "dev": dev_uncounted(rq)}}


def headcount(c):
    """Employees that count against the shift's crew_max: hired and not clocked out, revoked ones aside. The founder
    and the manager are outside it."""
    return [b for b in c["badges"] if b["role"] not in TOP and b["status"] in ("HIRED", "UP", "STALE", "OVERDUE")]


# --- titles: the card a badge is hired on ---
# A title is a card: the role its badge carries, the kinds it may be hired as, whether it must be independent of
# the build, and one line each for what it does, what it may write and what it hands in. Seven are built in; a
# project adds or changes cards in the profile ([titles.<name>] with like = "<built-in>" plus any field).
# {reviews}, {research} and {grader_owned} in a card's text are filled in from the profile when it is printed.

_WRITES_OWN = "the files its badge owns, in its own worktree or on its own branch"
TITLE_CARDS = {
    "builder": {"role": "BUILDER", "kinds": ["session", "temp"], "independent": False,
                "does": "builds what the job names, with the tests that show it works",
                "may_write": _WRITES_OWN,
                "hands_in": "its commits, the tests it ran with their results, and a report through handin"},
    "fixer": {"role": "BUILDER", "kinds": ["session", "temp"], "independent": False,
              "does": "fixes one filed failure: reproduces it, fixes the cause, and shows the test that now passes",
              "may_write": _WRITES_OWN,
              "hands_in": "its commits, the failure's id, and the test that failed before and passes now"},
    "grader": {"role": "GRADER", "kinds": ["session"], "independent": True,
               "does": "grades one lane, independent of the build: writes the lane's measure before the run and reads "
                       "the verdict the grader's code prints",
               "may_write": "only the measure's files ({grader_owned})",
               "hands_in": "the pinned measure and the verdict word, quoted from the grader's output"},
    "reviewer": {"role": "REVIEWER", "kinds": ["session", "temp"], "independent": True,
                 "does": "reads a change or a plan it had no part in and says GO or NO-GO, its findings ranked by severity",
                 "may_write": "its review file only (under {reviews}/)",
                 "hands_in": "the review file: each finding with its file and line"},
    "scout": {"role": "SCOUT", "kinds": ["temp", "session"], "independent": False,
              "does": "reads and reports: research, a survey, a question answered with its sources",
              "may_write": "its report file only (under {research}/)",
              "hands_in": "the report file"},
    "triager": {"role": "SCOUT", "kinds": ["temp", "session"], "independent": False,
                "does": "sorts failure reports: reproduces each, names the cause or the next check, and drafts its "
                        "failure entry",
                "may_write": "its report file only (under {research}/)",
                "hands_in": "one entry per report: the report's id, the cause, an owner and a plan"},
    "cleaner": {"role": "SCOUT", "kinds": ["temp", "session"], "independent": False,
                "does": "cleans up at a shift's end: worktrees and branches already merged, leftovers on the shared "
                        "resource",
                "may_write": "nothing in the tree; it removes only what its brief lists",
                "hands_in": "the list of what it removed and what it left, each with the reason"},
}
CARD_TEXTS = ("does", "may_write", "hands_in")


def title_cards():
    """{title: card} in force: the built-in cards, then the profile's [titles.<name>] over them. A profile card
    starts from the built-in its `like` names (its own name when that is a built-in) and replaces any of role, kinds,
    does, may_write, hands_in, independent. A card the profile wrote wrongly keeps a `problem` text, and hire
    refuses that title with it."""
    cards = {k: {**v, "kinds": list(v["kinds"])} for k, v in TITLE_CARDS.items()}
    table = prof().get("titles") or {}
    for name, t in (table.items() if isinstance(table, dict) else []):
        name = str(name).strip().lower()
        if not isinstance(t, dict):
            cards[name] = {**cards.get(name, {}), "problem": f"[titles.{name}] is not a table"}
            continue
        like = str(t.get("like") or (name if name in TITLE_CARDS else "")).strip().lower()
        if like and like not in TITLE_CARDS:
            cards[name] = {"problem": f"[titles.{name}] like = {like!r} names no built-in card "
                                      f"({', '.join(TITLE_CARDS)})"}
            continue
        base = TITLE_CARDS.get(like)
        card = ({**base, "kinds": list(base["kinds"])} if base else
                {"role": "", "kinds": ["session", "temp"], "independent": False, "does": "", "may_write": "", "hands_in": ""})
        if like and like != name:
            card["like"] = like
        problems = []
        if "role" in t:
            card["role"] = str(t["role"]).strip().upper()
        if card["role"] not in ROLES or card["role"] in TOP:
            problems.append(f"role {card['role'] or '(none)'!r} is not one of "
                            f"{', '.join(r for r in ROLES if r not in TOP)} (give `like` or `role`)")
        if "kinds" in t:
            raw = t["kinds"] if isinstance(t["kinds"], list) else re.split(r"[,\s]+", str(t["kinds"]))
            kinds = [str(k).strip().lower() for k in raw if str(k).strip()]
            if not kinds or any(k.upper() not in KINDS for k in kinds):
                problems.append(f"kinds {t['kinds']!r}: a list of session, temp")
            else:
                card["kinds"] = kinds
        for k in CARD_TEXTS:
            if k in t:
                card[k] = str(t[k]).strip()
        if "independent" in t:
            if isinstance(t["independent"], bool):
                card["independent"] = t["independent"]
            else:
                problems.append(f"independent {t['independent']!r}: true or false")
        if problems:
            card["problem"] = f"[titles.{name}]: " + "; ".join(problems)
        cards[name] = card
    return cards


def title_of(rec):
    """A badge's title: the one it was hired on, else its role's own card (a badge from before titles)."""
    return str(rec.get("title") or rec.get("role", "")).lower()


def title_text(rec):
    """The title as the roster prints it: `fixer (builder)`, or the role alone when the title is the role's own."""
    t, role = title_of(rec), str(rec.get("role", "")).lower()
    return role if t == role else f"{t} ({role})"


def card_lines(rec):
    """The brief's "Your card (title)" block, or [] for a badge whose title has no card (the founder, the manager)."""
    title = title_of(rec)
    card = title_cards().get(title)
    if not card or card.get("problem"):
        return []
    p = prof()
    fill = {"{reviews}": p.rel("reviews").strip("/"), "{research}": p.rel("research").strip("/"),
            "{grader_owned}": ", ".join(str(x) for x in (p.get("measure.grader_owned") or [])) or "none listed"}

    def text(k):
        s = card.get(k) or "(the card does not say)"
        for a, b in fill.items():
            s = s.replace(a, b)
        return s
    head = f"Your card ({title}): role {card['role'].lower()}; hired as {' or '.join(card['kinds'])}"
    if card.get("independent"):
        head += "; independent: you had no part in what you judge, and you take no word of its author for a result"
    return [head, f"    Does: {text('does')}", f"    May write: {text('may_write')}", f"    Hands in: {text('hands_in')}"]


def flagged_of(title):
    """The profile's [flagged.<title>] ({"model": ..., "trailer": ...}) with its values as stripped text, or None.
    Work under a flagged title is built on the model named there, and every commit of it ends with the trailer, so a
    reviewer finds each one for an in-depth review."""
    f = prof().get("flagged") or {}
    t = f.get(title) if isinstance(f, dict) else None
    if not isinstance(t, dict):
        return None
    return {"model": str(t.get("model") or "").strip(), "trailer": str(t.get("trailer") or "").strip()}


def model_of(rec):
    """(model id, where it comes from) for a badge, or ('', ''): the hire's own --model, else [flagged.<title>]'s
    model, else the profile's [models] by title, then by role."""
    if rec.get("model"):
        return str(rec["model"]), "hire --model"
    title, role = title_of(rec), str(rec.get("role", ""))
    fl = flagged_of(title)
    if fl and fl["model"]:
        return fl["model"], f"[flagged.{title}]"
    models = prof().get("models") or {}
    for k in (title, role.lower(), role.upper()):
        if isinstance(models, dict) and models.get(k):
            return str(models[k]).strip(), f"[models] {k}"
    return "", ""


def model_lines(rec):
    """The brief's Model line, and the trailer line of a flagged title."""
    out = []
    model, _ = model_of(rec)
    if model:
        out.append(f"Model: {model} (the manager sets the session to it; say in your first progress note which model "
                   "you run on)")
    fl = flagged_of(title_of(rec))
    if fl and fl["trailer"]:
        out.append(f"Every commit of yours ends with the trailer: {fl['trailer']}. Your commits get an in-depth review.")
    return out


def push_text():
    """The brief's push rule, by the profile's git.push: false (the default) is no push at all."""
    v = prof().get("git.push", False)
    on = v.strip().lower() in ("1", "true", "yes", "on") if isinstance(v, str) else bool(v)
    return "push only your own branch, never the main branch" if on else "no push"


# --- the freeze: the main checkout held still for a counted run, with or without a queue ---

FREEZE_FILE = "freeze.json"
FREEZE_AT_MIN, FREEZE_AT_MAX = 946684800.0, 4102444800.0  # 2000-01-01 .. 2100-01-01 UTC: seconds, not milliseconds
FREEZE_MAX_S = 366 * 86400  # no freeze is meant to last past a year
SEEN_FILE = "handins-seen.json"
TIMERS_FILE = "manager-timers.json"


def freeze_facts(d=None, now=None):
    """The freeze the manager set with `office.py freeze on`, for every tool that must not write the main checkout
    during a counted run: {"on", "by", "why", "lane", "at", "max_s", "stale"}. The office's freeze.json is the
    state: absent means off. `stale` is True once now is past at + max_s (a freeze with no limit is never stale):
    the run it covered has probably ended and nobody lifted it. A file that cannot be read counts as a freeze in
    force, with the reason in `why`: a tool that cannot tell holds still."""
    d = office_dir() if d is None else Path(d)
    now = now_ts() if now is None else now
    off = {"on": False, "by": None, "why": "", "lane": None, "at": None, "max_s": None, "stale": False}
    f = d / FREEZE_FILE
    if not f.exists():
        return off
    try:
        j = json.loads(f.read_text(encoding="utf-8"))
        if not isinstance(j, dict):
            raise ValueError("not an object")
        at = j["at"]
        if isinstance(at, bool) or not isinstance(at, (int, float, str)):
            raise TypeError("at is not a number")
        at = float(at)
        if not FREEZE_AT_MIN <= at <= FREEZE_AT_MAX:  # nan and the infinities fail this too
            raise ValueError("at is not a time in seconds")
        local(at)  # a time this system cannot show is not a sane time
        max_s = j.get("max_s")
        if max_s is not None:
            if isinstance(max_s, bool) or not isinstance(max_s, (int, float, str)):
                raise TypeError("max_s is not a number")
            max_s = float(max_s)
            if not 0 <= max_s <= FREEZE_MAX_S:
                raise ValueError("max_s is not a sane length")
            max_s = int(max_s)
    except (OSError, ValueError, KeyError, TypeError, OverflowError, RecursionError) as e:
        return {**off, "on": True, "by": "unknown",
                "why": f"{FREEZE_FILE} cannot be read ({type(e).__name__}: {str(e)[:80]}): the manager sets it again "
                       "or lifts it"}
    return {"on": True, "by": str(j.get("by") or "unknown"), "why": str(j.get("why") or ""),
            "lane": (str(j["lane"]) if j.get("lane") else None), "at": at, "max_s": max_s,
            "stale": bool(max_s is not None and now > at + max_s)}


def freeze_text(fz, now):
    """One line for a freeze in force: who, since when, which lane, its limit, why. Never an exception: a time or
    a length that cannot be shown is said so, in every place that prints a freeze (roster, me, round, handoff)."""
    since = limit = ""
    try:
        since = f" since {hhmm(fz['at'], now)}" if fz.get("at") is not None else ""
    except (OverflowError, OSError, ValueError, TypeError):
        since = " since a time that cannot be shown"
    lane = f", lane {fz['lane']}" if fz.get("lane") else ""
    try:
        if fz.get("max_s") is not None and fz.get("at") is not None:
            limit = f", limit {ago(fz['max_s'])} (to {hhmm(fz['at'] + fz['max_s'], now)})"
    except (OverflowError, OSError, ValueError, TypeError):
        limit = ", limit cannot be shown"
    stale = " STALE? it is past its limit;" if fz.get("stale") else ""
    return f"by {fz['by']}{since}{lane}{limit}:{stale} {fz['why'] or '(no reason given)'}"


# --- the commands ---

RQ = "rq"  # a badge's seat when it reaches the shared resource through rq.py run --id <badge> (any seat; many share it)


def seat_arg(a):
    """hire's or amend's seat: --rq (through the queue) or --seat NAME; '' when neither is given."""
    rq, seat = getattr(a, "rq", False), getattr(a, "seat", None)
    if rq and seat:
        raise Refused("--rq and --seat: give one")
    if rq or seat:
        need_resource("--rq" if rq else "--seat")
    return RQ if rq else (seat or "")


def files_warnings(files, base=None):
    """A --files pattern that matches nothing and whose folder does not exist is probably a wrong path (src/core/**
    when the folder is src/app/core). A new file in an existing folder is fine."""
    base = Path(base) if base else main_checkout()
    out = []
    for pat in [p.strip() for p in re.split(r"[,;]", files or "") if p.strip()]:
        pat = pat.split(" (")[0].strip().strip("`'\"")  # "docs/x.md (new)": the path only
        # free text ("the review file only") and absolute paths are not checked
        if not pat or re.search(r"\s", pat) or "/" not in pat or pat.startswith("/") or re.match(r"^[A-Za-z]:", pat):
            continue
        fixed = []
        for part in pat.split("/"):
            if any(ch in part for ch in "*?["):
                break
            fixed.append(part)
        whole = len(fixed) == len(pat.split("/"))
        folder = base.joinpath(*fixed[:-1]) if whole else base.joinpath(*fixed)
        if folder.is_dir():
            continue  # the folder exists: a new file in it, or a pattern under it; no tree walk
        if not folder.is_dir():
            out.append(f"--files {pat!r} matches no file and {folder.relative_to(base).as_posix() or '.'}/ does not "
                       "exist in the main checkout: check the path (amend --set-files replaces the list)")
    return out


def vendored_files(base=None):
    """The repo paths of the files the profile's measure.vendored_paths names: files copied from elsewhere that are
    never edited in place. A glob is filled in from `base` (the main checkout); a folder stands for every file under
    it; a plain path is taken as written."""
    base = Path(base) if base else main_checkout()
    out = []
    globs = prof().get("measure.vendored_paths", []) or []
    for g in globs if isinstance(globs, list) else [globs]:
        g = str(g).replace("\\", "/").strip().strip("/")
        if not g or g.startswith("..") or re.match(r"^[A-Za-z]:", g):
            continue
        try:
            if any(ch in g for ch in "*?["):
                out += sorted(p.relative_to(base).as_posix() for p in base.glob(g) if p.is_file())
            elif (base / g).is_dir():
                out += sorted(p.relative_to(base).as_posix() for p in (base / g).rglob("*") if p.is_file())
            else:
                out.append(g)
        except (OSError, ValueError):
            continue
    return list(dict.fromkeys(out))


def vendored_hits(files, base=None):
    """The vendored paths a --files list covers."""
    pats, _ = owned_patterns(files)
    return [v for v in (vendored_files(base) if pats else []) if owns(pats, v)]


def vendored_warnings(files, base=None):
    """A --files list that covers a vendored file. A warning, not a refusal: the manager re-vendors on purpose now
    and then, and a broad pattern (lib/**) is fine as long as the employee is told."""
    hits = vendored_hits(files, base)
    if not hits:
        return []
    return [f"--files covers {', '.join(hits)}, vendored (measure.vendored_paths): it is not edited in place; a new "
            "version is copied in whole. Drop it from --files, or say in the job that this is a re-vendoring"]


def report_path_re():
    """A file under the profile's reviews or research folder, as a brief names it."""
    p = prof()
    return re.compile("(?:" + "|".join(re.escape(p.rel(k).strip("/")) for k in ("reviews", "research"))
                      + r")/[^\s`'\",;()<>\[\]]+")


def report_path_warnings(files, *texts):
    """A brief or done-when that names a reviews or research file which --files does not own: the employee commits
    the report the brief names and handin refuses it as outside the badge. A warning, not a refusal: the manager
    fixes --files (amend --add-files)."""
    pats, _ = owned_patterns(files)
    seen, out = set(), []
    for text in texts:
        for m in report_path_re().finditer(text or ""):
            path = m.group(0).rstrip(".:!?")
            if path.endswith("/") or path in seen:
                continue  # a folder named in passing is not a file the employee commits
            seen.add(path)
            if not owns(pats, path):
                out.append(f"the brief names {path}, which --files does not own: handin will refuse that report as "
                           "outside the badge. Add it to --files (amend --add-files), or fix the name in the brief")
    return out


HARNESS_PATHS = (".claude/settings.json", ".claude/hooks/")
HARNESS_BRIEF = ("deliver the .claude change as a patch file outside the tree, not a commit; the manager moves it to "
                 "a bench")


def harness_hits(files):
    """The harness-config paths (.claude/settings.json, .claude/hooks/) a --files list covers. Each hooks path is
    probed (a made-up probe.py, every real file under .claude/hooks/ listed now, and the file a pattern names, so
    `.claude/*/guard.py` warns). Some file systems ignore case, so patterns and probes are compared lower-cased, and
    an absolute or loose entry is read from its `/.claude/` on."""
    pats, loose = owned_patterns(files)
    pats = [p.lower() for p in pats]
    for raw in loose:  # "D:/repo/.claude/hooks/x.py", which owned_patterns keeps as free text
        low = raw.strip().strip("`'\"").replace("\\", "/").lower()
        i = low.find("/.claude/")
        if i >= 0 or low.endswith("/.claude"):
            pats.append(low[i + 1:].rstrip("/") if i >= 0 else ".claude")
    hooks = prof().root / ".claude" / "hooks"
    real = sorted(".claude/hooks/" + f.relative_to(hooks).as_posix().lower()
                  for f in (hooks.rglob("*") if hooks.is_dir() else []) if f.is_file())
    named = []
    for p in pats:  # the file a glob names, its wildcards filled in: `.claude/*/guard.py` probes hooks/guard.py
        last = re.sub(r"\[[^\]]*\]", "x", p.rsplit("/", 1)[-1]).replace("*", "probe").replace("?", "x")
        if last and last not in (".", ".."):
            named.append(".claude/hooks/" + last)
    hits = []
    for h in HARNESS_PATHS:
        probes = [h + "probe.py", *real, *named] if h.endswith("/") else [h]
        if any(owns(pats, pr) for pr in probes) or (h.endswith("/") and any(p.startswith(h) for p in pats)):
            hits.append(h.rstrip("/"))
    return hits


def harness_warnings(files, kind):
    """A TEMP badge whose --files names .claude/hooks/ or .claude/settings.json. Such a change needs the user's
    approval typed in the employee's own session, and a temp has no box the user types in. A warning, not a refusal:
    the temp may still draft the change as a patch."""
    hits = harness_hits(files) if str(kind).upper() == "TEMP" else []
    if not hits:
        return []
    return [f"--files names {', '.join(hits)} on a TEMP badge: a harness-config change needs the user's approval "
            "typed in the employee's own session, which a temp lacks. The brief tells it to " + HARNESS_BRIEF
            + "; hire a session (a bench) for the commit"]


class FilesRefused(Refused):
    """A --files pattern under a folder that does not exist (exit 2, not 3)."""
    code = 2


def refuse_bad_files(files, force):
    """hire and amend refuse a pattern whose folder is missing, unless --force-files (a folder the job creates)."""
    bad = files_warnings(files)
    if bad and not force:
        raise FilesRefused("; ".join(bad) + ". Fix the path, or pass --force-files if the job creates that folder")
    return bad


def next_id(roster, prefix):
    n = 1 + max((int(b.split("-")[1]) for b in roster["badges"] if b.startswith(prefix + "-")), default=0)
    return f"{prefix}-{n}" if prefix in ("MGR", "FDR") else f"{prefix}-{n:02d}"


def mint(d, key, roster, *, prefix, name, role, kind, state, now, slot=None, **extra):
    shift_id, _ = shift_facts(state)
    slot = slot or slot_at(state.get("rota", {}).get("slots"), now)[0]
    bid = next_id(roster, prefix)
    fields = {"ID": bid, "NAME": token(name, 20), "ROLE": role, "KIND": kind, "SHIFT": token(shift_id, 24),
              "SLOT": token(slot, 8), "ISSUED": str(int(now))}
    rec = {"id": bid, "line": make_line(key, fields), "name": name, "role": role, "kind": kind,
           "shift": shift_id, "slot": slot, "issued": now, "session": None, "revoked": None, **extra}
    roster["badges"][bid] = rec
    return rec


def manager_of(d, key, roster, line, c):
    rec = verify_line(key, roster, line)
    if rec["role"] == "FOUNDER":
        raise Refused(f"{rec['id']} is the founder's badge: the founder does not hire, assign, amend or end a shift. "
                      f"That is the manager's ({roster.get('manager') or 'none appointed'}); give --by its line")
    if rec["role"] != "MANAGER" or rec["id"] != roster.get("manager"):
        raise Refused(f"{rec['id']} is not the current manager ({roster.get('manager') or 'none appointed'})")
    me = next(b for b in c["badges"] if b["id"] == rec["id"])
    if not me["on"]:
        raise Refused(f"manager {rec['id']} is not clocked in")
    return rec


def cmd_found(a, d, now):
    """Mint the one founder badge. The founder writes the roadmap and the profile and audits the work; it is outside
    the headcount and hires no one, so its badge is only a clock: in, progress, out."""
    key = load_key(d)
    state = read_state()
    with locked(d):
        roster = read_roster(d)
        c = crew(d, now)
        old = next((b for b in c["badges"] if b["id"] == roster.get("founder")), None)
        if old and old["on"] and not a.relieve:
            raise Refused(f"{old['id']} ({old['name']}) is the founder and on the clock, heard {hhmm(old['heard'], now)}. "
                          "There is one founder: ask the user before relieving it (found --relieve).")
        if old and old["on"]:
            append_event(d, {"at": now, "id": old["id"], "ev": "out", "result": "relieved",
                             "note": f"relieved by a new founder badge ({a.name})"})
        if old:
            roster["badges"][old["id"]]["revoked"] = now
            roster["badges"][old["id"]]["revoked_why"] = f"a new founder badge was minted ({a.name})"
        rec = mint(d, key, roster, prefix="FDR", name=a.name, role="FOUNDER", kind="SESSION", state=state, now=now,
                   job="found the project: the roadmap, the profile, audits, pushes and decisions", eta_s=0, by=None)
        if a.session:
            rec["session"] = a.session
        roster["founder"] = rec["id"]
        write_roster(d, roster)
    plate(d, rec)
    cmd = tool()
    print(f"founded: {rec['id']} ({a.name}) holds the one founder badge" + (f"; {old['id']} relieved" if old and old["on"] else ""))
    print(f"badge: {rec['line']}")
    print(f"next: {cmd} clock-in --badge \"{rec['line']}\"")
    if not a.session:
        print(f"then: {cmd} assign {rec['id']} --session local_<this session's id>   (so the manager can find its founder)")
    elif cli_session_warning(a.session):
        print(cli_session_warning(a.session))
    print("the founder hires no one: appoint a manager (office.py appoint), who hires the crew")
    return 0


def cmd_appoint(a, d, now):
    key = load_key(d)
    state = read_state()
    with locked(d):
        roster = read_roster(d)
        c = crew(d, now)
        old = next((b for b in c["badges"] if b["id"] == roster.get("manager")), None)
        if old and old["on"] and old["status"] == "UP" and not a.relieve:
            raise Refused(f"{old['id']} ({old['name']}) is the manager and on the clock, heard {hhmm(old['heard'], now)}. "
                          "There is one manager: ask the user before relieving it (appoint --relieve).")
        # every refusal (the slot checks below too) comes before the old manager is clocked out or revoked.
        # A manager's finish is its slot's end; appointed just before a boundary, its slot is the next one, unless
        # --this-slot keeps the current one (re-appointing this slot's manager, whose rota `ends` then still reads)
        slots = state.get("rota", {}).get("slots")
        here = slot_at(slots, now)
        picked = {}
        if a.slot:
            # a re-badge in the last hour before a slot names that slot; its finish is that slot's end
            chosen = named_slot(slots, a.slot.lower(), now)
            if chosen is None:
                raise Refused(f"--slot {a.slot}: the rota's slots are "
                              + ", ".join(s["id"] for s in (slots or default_slots())))
            if chosen[0] != here[0] and not (chosen[1] == here[2] and here[2] - now <= SLOT_PICK_LEAD_S):
                # only the slot now, or the next one in the last hour before it starts
                raise Refused(f"--slot {a.slot}: name the slot now ({here[0]}) or, in the last "
                              f"{SLOT_PICK_LEAD_S // 60} min before it starts, the next one; the {chosen[0]} slot "
                              f"starts at {local(chosen[1]):%H:%M}")
            mslot, _, slot_end = chosen
            if chosen[0] != here[0]:
                # the badge keeps the start of the slot it named, so badge_slot and hire_slot read that slot from
                # the appointment on, not only within APPOINT_LEAD_S of its start
                picked = {"slot_start": chosen[1]}
        else:
            mslot, _, slot_end = here if a.this_slot else manager_slot(slots, now)
        if old and old["on"]:
            append_event(d, {"at": now, "id": old["id"], "ev": "out", "result": "relieved",
                             "note": f"relieved by a new appointment ({a.name})"})
        if old:
            roster["badges"][old["id"]]["revoked"] = now
            roster["badges"][old["id"]]["revoked_why"] = f"a new manager was appointed ({a.name})"
        rec = mint(d, key, roster, prefix="MGR", name=a.name, role="MANAGER", kind="SESSION", state=state, now=now, slot=mslot,
                   job="manage the slot: rota, crew, checkpoints, failures, the map", eta_s=int(slot_end - now), by=None,
                   **picked)
        if a.session:
            rec["session"] = a.session
        roster["manager"] = rec["id"]
        write_roster(d, roster)
    plate(d, rec)
    cmd = tool()
    print(f"appointed {rec['id']} ({a.name}) as the one manager" + (f"; {old['id']} relieved" if old and old["on"] else ""))
    if mslot != here[0] and not a.slot:
        print(f"note: appointed for the {mslot} slot (within {APPOINT_LEAD_S // 60} min of its start); "
              f"use --this-slot to keep the {here[0]} slot")
    print(f"badge: {rec['line']}")
    print(f"next: {cmd} clock-in --badge \"{rec['line']}\"")
    if not a.session:
        print(f"then: {cmd} assign {rec['id']} --session local_<this session's id>   (so the crew can find its manager)")
    elif cli_session_warning(a.session):
        print(cli_session_warning(a.session))
    carry = [b for b in c["badges"] if b["role"] not in TOP and b["on"]]
    if carry:
        # a brief's "message your manager" goes stale at every change of manager: tell each one
        print(f"tell the crew still on the clock that {rec['id']} is the manager now (one message each):")
        for b in carry:
            print(f"    {b['id']} {b['name']}: {b.get('session') or 'no session recorded'}")
    sweeps = c["vm"]["sweeps"]
    if sweeps:
        print(f"a counted sweep or run is in the queue of {res_name()} ({', '.join(sweeps)}): it is a background job of "
              "the session that started it. Do not stop or archive that session, and change nothing in the main "
              "checkout until it ends.")
    if c["freeze"]["on"]:
        print(f"the main checkout is frozen {freeze_text(c['freeze'], now)}. Change nothing there until the run it "
              f"covers has ended and its records are committed; then lift it: {cmd} freeze off --by \"<your line>\"")
    return 0


ADR_COUNTER = "adr-next.json"  # the last decision-record number reserved at hire, in the crew office


def adr_numbers(repo, ref=None):
    """The numbers of the decision records (NNNN-<topic>.md) under the profile's paths.decisions on `ref` (the main
    branch) and on every local branch: a draft on an unmerged branch holds its number too."""
    folder = prof().rel("decisions").strip("/")
    _, out = git(["ls-tree", "--name-only", ref or main_branch(), folder + "/"], repo)
    _, drafts = git(["log", "--branches", "--diff-filter=A", "--name-only", "--format=", "--", folder], repo)
    return sorted({int(m.group(1)) for n in (out + "\n" + drafts).splitlines()
                   if (m := re.match(r"(\d{4})-", Path(n.strip()).name))})


def reserve_adr(d, repo, now):
    """The next decision-record number past every number on the main branch and the local branches and every number
    reserved before, written to the office's one counter. The caller holds the office lock, so two hires never take
    one number."""
    f = d / ADR_COUNTER
    try:
        last = int(json.loads(f.read_text(encoding="utf-8")).get("last", 0))
    except (OSError, ValueError, AttributeError, TypeError):
        last = 0
    n = max([last, *adr_numbers(repo)]) + 1
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"last": n, "at": now}) + "\n", encoding="utf-8")
    return f"{n:04d}"


def cmd_hire(a, d, now):
    key = load_key(d)
    state = read_state()
    kind = a.kind.upper()
    cards = title_cards()
    title = (getattr(a, "title", None) or "").strip().lower()
    if title:
        # --title sets the role: the card names it
        card = cards.get(title)
        if card is None:
            raise Refused(f"title {a.title!r}: the known titles are {', '.join(sorted(cards))} (a project adds one "
                          "as [titles.<name>] with like = \"<built-in>\" in .foundry/foundry.toml)")
        if card.get("problem"):
            raise Refused(f"title {title}: its card in the profile is broken: {card['problem']}")
        role = card["role"]
        if a.role and a.role.upper() != role:
            raise Refused(f"--title {title} is a {role} card and --role says {a.role.upper()}: give --title alone, or "
                          "the title whose card has that role")
    elif a.role:
        role = a.role.upper()
        if role not in ROLES or role in TOP:
            raise Refused(f"role {a.role!r}: hire one of {', '.join(r for r in ROLES if r not in TOP)}")
        title = role.lower()  # the role's own card
        card = cards.get(title) or {}
        if card.get("problem"):
            raise Refused(f"role {a.role}: its card in the profile is broken: {card['problem']}")
    else:
        raise Refused("hire needs --role or --title")
    if kind not in KINDS:
        raise Refused(f"kind {a.kind!r}: session or temp")
    if role == "GRADER" and kind != "SESSION":
        raise Refused("a GRADER is its own session: a subagent of the manager is not independent of the build")
    if card.get("kinds") and kind.lower() not in card["kinds"]:
        raise Refused(f"title {title} is hired as {' or '.join(card['kinds'])}, not as a {kind.lower()}"
                      + (": its card says independent, and a subagent of the manager is not" if card.get("independent") else ""))
    if role == "GRADER" and not a.lane:
        raise Refused("a GRADER is hired for a lane (--lane G1)")
    model = (getattr(a, "model", None) or "").strip()
    flagged = flagged_of(title)
    if flagged is not None and not (flagged["model"] or flagged["trailer"]):
        raise Refused(f"[flagged.{title}] in the profile names neither a model nor a trailer: give it `model`, "
                      "`trailer` or both, or take the table out")
    if (flagged and flagged["model"] and model and model != flagged["model"]
            and not getattr(a, "force_model", False)):
        raise Refused(f"title {title} is flagged: its work is built on {flagged['model']} ([flagged.{title}] model), "
                      f"not {model}. Drop --model, or pass --force-model if the user said so")
    forced = refuse_bad_files(a.files, a.force_files)
    with locked(d):
        roster = read_roster(d)
        c = crew(d, now)
        mgr = manager_of(d, key, roster, a.by, c)
        shift_id, crew_max = shift_facts(state)
        if crew_max is None:
            raise Refused(f"the shift {shift_id} has no crew_max in state.json; the manager sets the headcount per shift first")
        hc = headcount(c)
        if len(hc) >= int(crew_max):
            raise Refused(f"the shift {shift_id} is at its crew_max of {crew_max} "
                          f"({', '.join(b['id'] + ' ' + b['name'] for b in hc)}); clock someone out or raise crew_max with a note")
        if role == "GRADER" and any(b.get("lane") == a.lane and b["role"] == "GRADER" for b in hc):
            raise Refused(f"lane {a.lane} already has a GRADER on this shift")
        seat = seat_arg(a)
        if seat and seat != RQ and any(b.get("vmdir") == seat for b in hc):
            raise Refused(f"the seat {seat} is held by another employee; one seat per employee "
                          "(a badge that queues through rq.py takes --rq, which many may share)")
        # the crew badge reads its hiring manager's own slot: the night manager appointed at 21:5x hires night crew,
        # a manager re-appointed with --this-slot keeps hiring for its slot near the boundary, and one appointed
        # with --slot hires for the slot it named from the appointment on; never a slot that has ended. A manager
        # badge with no slot recorded falls back to the clock look-ahead (hire_slot).
        hslot = hire_slot(state.get("rota", {}).get("slots"), mgr, now)
        adr = {"adr": reserve_adr(d, main_checkout(), now)} if a.adr else {}  # under the office lock
        rec = mint(d, key, roster, prefix="EMP" if kind == "SESSION" else "TMP", name=a.name, role=role, kind=kind,
                   state=state, now=now, slot=hslot, job=a.job, done_when=a.done_when or "", lane=a.lane or "", vmdir=seat,
                   files=a.files or "", eta_s=parse_dur(a.eta), by=mgr["id"], title=title,
                   **({"model": model} if model else {}), **adr)
        write_roster(d, roster)
    plate(d, rec)
    print(f"hired {rec['id']} {rec['name']} ({title_text(rec)}, {kind.lower()}); crew {len(hc) + 1} of {crew_max} on {shift_id}")
    m_id, m_from = model_of(rec)
    if m_id:
        print(f"  model: {m_id} ({m_from}): set the session to it before it starts"
              + ("; a temp runs on the model its Agent call names" if kind == "TEMP" else ""))
    if flagged and flagged["trailer"]:
        print(f"  flagged title: every commit ends with `{flagged['trailer']}` (handin checks it); its commits get an "
              "in-depth review")
    if rec.get("adr"):
        print(f"  ADR {rec['adr']} reserved for {rec['id']} ({(d / ADR_COUNTER).as_posix()})")
    for w in forced:
        print(f"  ! --force-files: {w}")
    for w in vendored_warnings(a.files):
        print(f"  ! vendored: {w}")
    for w in report_path_warnings(a.files, a.job, a.done_when):
        print(f"  ! report path: {w}")
    for w in harness_warnings(a.files, kind):
        print(f"  ! harness config: {w}")
    print(f"badge: {rec['line']}")
    print("\n--- brief (paste into start_session's prompt or the Agent prompt) ---")
    print(brief(rec, mgr, state))
    return 0


def manager_now_line():
    """The manager and its session as the roster has them when the brief is printed, not the id the hiring manager
    pasted at hire, which goes stale at the next change of manager."""
    try:
        roster = read_roster(office_dir())
    except (OSError, ValueError):
        roster = {}
    mid = roster.get("manager")
    m = (roster.get("badges") or {}).get(mid) if mid else None
    now = now_ts()
    when = hhmm(now)
    if not m:
        return f"Manager at {when} (this print): none appointed in the roster; check office.py roster before you message one."
    # the roster keeps the last appointed manager after it clocks out, so say its status
    try:
        status = next((b["status"] for b in crew(office_dir(), now)["badges"] if b["id"] == m["id"]), "unknown")
    except (OSError, ValueError, KeyError):
        status = "unknown"
    if status in ("OUT", "REVOKED"):
        return (f"Manager at {when} (this print, from the roster): none on the clock; the last appointed, {m['id']} "
                f"{m.get('name', '')} (session {m.get('session') or 'not recorded'}), is {status}. Check office.py roster "
                "for the manager on the clock before you message one.")
    return (f"Manager at {when} (this print, from the roster): {m['id']} {m.get('name', '')} ({status}), session "
            f"{m.get('session') or 'not recorded'}. A session id pasted above this brief may be older: check office.py roster "
            "before you message the manager.")


def branch_line():
    """The brief's one branch line."""
    p = prof()
    mb, pre = main_branch(), str(p.get("git.branch_prefix", "claude/"))
    wts = str(p.get("git.worktrees") or "").replace("\\", "/")
    return (f"Branch: if your session starts in its own worktree{' (under ' + wts + ')' if wts else ''}, work on that "
            f"branch and report its name (a new one fast-forwarded to {mb} first; a fix round keeps its branch as it "
            f"is). Otherwise (a temp or a bench in the main checkout) cut {pre}<job> from {mb}, or from the sha the "
            f"brief names, as the brief says. Never commit on {mb}. `office.py me` prints the branch you are on.")


JOURNAL_LINE = ("The journal is `journal.py add` (and `mine`) for you, nothing else: plan, carry, ready, approve and set "
                "are the manager's, and journal.py refuses them to you. Draft any plan text in your report, and the "
                "manager enters it.")
# The Foundry tools that have a selftest: a brief whose files touch one names it.
FOUNDRY_TOOLS = ("office.py", "rq.py", "board.py", "journal.py", "flow.py", "plan_flow.py", "lanes_for.py",
                 "foundry_profile.py")


def gym_rel():
    return prof().rel("gym").strip("/")


def no_selftest(path):
    """Files no selftest reads (docs, a gym contract): a brief that owns only these gets no selftest to run."""
    return bool(re.search(r"\.md$", path)) or path.startswith(gym_rel() + "/contracts/")


def lane_files(lane):
    """The lane's files, <gym>/lanes/<lane>_*.py (or <lane>.py), repo-relative; none when the gym folder is missing."""
    if not lane or not re.fullmatch(r"[A-Za-z0-9]+", lane):
        return []
    p = prof()
    lanes = p.gym("lanes")
    if not lanes.is_dir():
        return []
    return sorted(f.relative_to(p.root).as_posix() for f in
                  (list(lanes.glob(f"{lane.lower()}_*.py")) + list(lanes.glob(f"{lane.lower()}.py"))))


def lane_selftests(lane):
    """The lane files that run their own selftest when started with no argument: those with an
    `if __name__ == "__main__"` block. A file without one defines its functions and exits 0, which reads as a pass;
    its selftest runs only inside the gym's own selftest (measure.selftest)."""
    out = []
    for rel in lane_files(lane):
        try:
            text = (prof().root / rel).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if re.search(r"^if __name__ == [\"']__main__[\"']\s*:", text, re.M):
            out.append(rel)
    return out


def tools_touched(pats):
    """The Foundry tools (repo paths) a list of owned patterns covers."""
    rel = prof().rel("tools").strip("/")
    return [f"{rel}/{n}" for n in FOUNDRY_TOOLS if owns(pats, f"{rel}/{n}")]


def tests_lines(rec):
    """The brief's Tests line: the lane's own selftest, the selftest of each Foundry tool the badge's files touch, and
    the gym's selftest (measure.selftest) when a lane is named."""
    p = prof()
    pats, _ = owned_patterns(rec.get("files", ""))
    if pats and all(no_selftest(x) for x in pats):
        return ["Tests: none. Every file you own is docs or a gym contract, which no selftest reads: run none, and say "
                "so in the hand-in."]
    lane = rec.get("lane") or ""
    gym_cmd = str(p.get("measure.selftest") or "").strip() if lane else ""
    own = lane_selftests(lane)
    quiet = [f for f in lane_files(lane) if f not in own]
    steps, note = [], ""
    if own:
        steps.append("the lane's own selftest, " + ", ".join(f"`{p.py} {f}`" for f in own))
    elif quiet:  # started alone it exits 0 and prints nothing, which is no pass
        note = (f" {lane}'s lane file ({', '.join(quiet)}) has no `__main__` block, so started alone it tests nothing: "
                "its selftest runs only inside the gym's own selftest.")
    tools = tools_touched(pats)
    if tools:
        steps.append("the selftest of each crew tool you touch, " + ", ".join(f"`{p.py} {t} selftest`" for t in tools))
    if gym_cmd:
        steps.append(f"the gym's own selftest, `{gym_cmd}` (every lane's verdict selftest; if it takes over 2 minutes, "
                     "run it in the background and wait for its notice)")
    proj_cmd = str(p.get("commands.test") or "").strip()
    if proj_cmd:  # the project's own test command, named once in the profile so every brief carries it
        steps.insert(0, f"the project's tests, `{proj_cmd}`")
    head = ("Tests, run in your worktree: " + "; then ".join(steps) + "." if steps else
            "Tests, run in your worktree: the brief names no crew tool or gym selftest for these files.")
    return [head + note + " Run your job's own tests too, and name each test and its result in the hand-in. Never run "
            "`board.py check` or `board.py build` in the main checkout."]


def brief(rec, mgr, state=None):
    p = prof()
    cmd = tool()
    res = res_name()
    lines = [
        f"You are a {p.project} employee, badge {rec['id']} ({rec['name']}, {title_text(rec)}), hired by the manager {mgr['id']}.",
        f"First invoke the {p.skill('employee')} skill and follow it. Then clock in before any other work:",
        f"    {cmd} clock-in --badge \"{rec['line']}\"",
        "",
        f"Job: {rec['job']}",
    ]
    if rec.get("done_when"):
        lines.append(f"Done when: {rec['done_when']}")
    lines += card_lines(rec)
    lines += model_lines(rec)
    if rec.get("lane"):
        extra = ""
        if rec["role"] == "GRADER":
            owned = [str(x) for x in (p.get("measure.grader_owned") or [])]
            blind = [str(x) for x in (p.get("measure.grader_no_read", []) or [])]
            extra = (f" (you are its independent grader: the {p.skill('gym')} skill applies"
                     + (f"; never open {' or '.join(blind)}" if blind else "")
                     + (f"; you own only {', '.join(owned)}" if owned else "") + ")")
        lines.append(f"Lane: {rec['lane']}" + extra)
    if rec.get("files"):
        lines.append(f"Files you own: {rec['files']} (touch nothing else; git add -- <paths> only; {push_text()})")
        hits = vendored_hits(rec["files"])  # the employee reads it too
        if hits:
            lines.append(f"Vendored, never edited in place: {', '.join(hits)}. Leave it unless the job says you "
                         "re-vendor it (copy the new version in whole); ask the manager if unsure")
        if harness_warnings(rec["files"], rec.get("kind", "")):
            lines.append(f"Harness config ({', '.join(harness_hits(rec['files']))}): its change needs the user's approval "
                         f"typed in your own session, which a temp lacks: {HARNESS_BRIEF}.")
    if has_resource():
        seat_env = str(p.get("resource.seat_env") or "FOUNDRY_SEAT")
        if rec.get("vmdir") == RQ:
            lines.append(f"{res[:1].upper() + res[1:]}: through the queue only, `{tool('rq.py')} run --id {rec['id']} "
                         f"--job \"...\" --max {p.get('resource.default_max') or '30m'} -- <command>` "
                         f"(it picks the seat and sets {seat_env}); never set {seat_env} by hand")
        elif rec.get("vmdir"):
            lines.append(f"Seat: {seat_env}={rec['vmdir']} on {res} is yours alone; never two commands at once in it")
    lines.append(branch_line())
    if rec.get("adr"):
        lines.append(f"Your ADR number: {rec['adr']}, reserved for you at hire ({p.rel('decisions').strip('/')}/"
                     f"{rec['adr']}-<topic>.md). Cite other drafts by file name, never by a number they took on their "
                     "own branch.")
    lines += tests_lines(rec)
    if rec.get("role") == "GRADER" and has_resource():
        lines.append("Waiting on a queued run (the builder's dev run, the manager's counted run): post `progress "
                     "--waiting-on <its badge or queue id>` now, as soon as you wait, not later; until you do, the roster "
                     "counts you STALE.")
    lines += [
        f"Approximate time: {ago(rec['eta_s'])} from your clock-in. Post progress at each step and at least every 30 min:",
        f"    {cmd} progress --badge \"<your line>\" --pct N --eta 40m --note \"what you are on\"",
        f"Report every failure for the manager's list:  {cmd} fail --badge \"<your line>\" --what \"...\" [--lane L --run-id R --verdict V]",
        f"When the job ends:  {cmd} clock-out --badge \"<your line>\" --result done|partial|failed|handed-off --note \"...\" --commits a,b",
    ]
    if has_resource():
        lines.append(
            f"Every command on {res} goes through its queue (rq.py run), a workaround included, one job at a time "
            "under your badge: the queue refuses a second `run` under an id that waits or holds a seat, so a second "
            "job can neither replace the first's entry nor be freed by its release. Run the job in the background and "
            "end your turn: its end wakes you, and the roster shows your queue place meanwhile, so post progress when "
            "something changes, not to say you still wait. Waiting on another badge's queued job, post once with "
            "--waiting-on <that badge>.")
    lines += [
        "Post a run folder with progress --run <folder>: it lies in your worktree, not in the main checkout.",
        f"Your record at any time (this brief, amendments, the manager{', your place in the queue' if has_resource() else ''}):  "
        f"{cmd} me --badge \"<your line>\"",
        "Log a hole, a failure of the process or an improvement in the crew skill, its tools or this brief when you hit it, "
        f"not only at the end:  {tool('journal.py')} add --badge \"<your line>\" "
        "--kind hole|failure|improvement --what \"...\" --fix \"<a draft fix>\"  (no run outcome or verdict in it)",
        JOURNAL_LINE,
        f"Before you clock out, in your worktree:  {cmd} handin --badge \"<your line>\" [--file <your report>]",
        "At the end: hand in, clock out, message the manager, and stop. Never clear yourself (auto mode refuses it): "
        "the manager retitles a bench and the user /clears it.",
        "A permission or classifier refusal means stop and report it; never try another route to the same end.",
    ]
    if has_resource():
        lines.append("While a counted sweep or run is queued or running (the roster says COUNTED SWEEP or run), commit "
                     "nothing in the main checkout, not even a report: commit in your own worktree.")
    else:
        lines.append(f"While a counted run is going (you see it as FREEZE in `{cmd} me`), commit nothing in the main "
                     "checkout, not even a report: commit in your own worktree.")
    lines += [
        f"You never hire, start sessions, appoint, promote, or edit {p.rel('state')} or the map.",
        "If blocked, message the manager on the clock, not the session that started you: managers change every slot, and",
        f"    {cmd} roster      names the current one and its session.",
        manager_now_line(),
    ]
    known = [str(k) for k in ((state or {}).get("tooling_known") or []) if k]
    if known:
        lines.append("Known tooling bugs and their workarounds (state.tooling_known):")
        lines += [f"    - {k}" for k in known]
    return "\n".join(lines)


def cli_session_warning(session):
    """A warning when `session` is local_ plus this process's CLAUDE_CODE_SESSION_ID: that is the CLI's
    own id, not the desktop app's session id, so a message sent to it reaches no one. None otherwise."""
    cli = os.environ.get("CLAUDE_CODE_SESSION_ID", "").strip()
    if session and cli and session.strip() in (cli, "local_" + cli):
        return (f"warning: --session {session} is this process's CLAUDE_CODE_SESSION_ID, the CLI's id, not the app's "
                "session id; messages to it reach no one. Take the id from get_session \"self\" (its local_… id) and "
                "run office.py assign <id> --session local_… again.")
    return None


def cmd_assign(a, d, now):
    warn = cli_session_warning(a.session)
    if warn:
        print(warn)
    with locked(d):
        roster = read_roster(d)
        rec = roster["badges"].get(a.id)
        if not rec:
            raise Refused(f"no badge {a.id}")
        c = crew(d, now)
        if getattr(a, "by", None):  # optional: when given, it is the manager's line, never a founder's
            manager_of(d, load_key(d), roster, a.by, c)
        live = {b["id"]: b for b in headcount(c)}
        held = [b for b in roster["badges"].values() if b["id"] != a.id and b.get("session") == a.session]
        why = None
        for b in held:
            if b["id"] in live:
                why = f"session {a.session} already holds {b['id']} ({b['name']}); one badge per session"
            elif rec["role"] == "GRADER" and b["role"] in ("BUILDER", "MANAGER") and (b.get("lane") in ("", rec.get("lane"))):
                why = f"session {a.session} built as {b['id']}; it cannot grade lane {rec.get('lane')}"
            if why:
                break
        if a.dry_run:
            # what the session has held, so a grader's bench is picked before the hire, not after
            print(f"session {a.session} has held {len(held)} badge(s)" + (":" if held else ""))
            for b in held:
                print(f"    {b['id']} {b['name']} {b['role'].lower()}" + (f" lane {b['lane']}" if b.get("lane") else "")
                      + (" (on the clock)" if b["id"] in live else ""))
            built = sorted({b.get("lane") or "(no lane: counts for every lane)" for b in held
                            if b["role"] in ("BUILDER", "MANAGER")})
            print("built: " + (", ".join(built) if built else "nothing"))
            print(f"dry run: assign {a.id} would be " + (f"refused: {why}" if why else "taken") + "; nothing written")
            return 3 if why else 0
        if why:
            raise Refused(why)
        rec["session"] = a.session
        write_roster(d, roster)
    print(f"{a.id} is session {a.session}")
    return 0


def cmd_amend(a, d, now):
    """The manager widens or rewords a badge's job mid-shift: the roster record changes and the time clock
    keeps what it was. The event is logged under the manager's id, so it does not count as the employee being heard."""
    if not (a.job or a.add_files or a.set_files or a.done_when or a.eta or a.seat or a.rq):
        raise Refused("amend needs at least one of --job, --add-files, --set-files, --done-when, --eta, --seat, --rq")
    if a.add_files and a.set_files:
        raise Refused("--add-files widens, --set-files replaces: give one")
    forced = refuse_bad_files(a.add_files or a.set_files, a.force_files)
    key = load_key(d)
    with locked(d):
        roster = read_roster(d)
        c = crew(d, now)
        mgr = manager_of(d, key, roster, a.by, c)
        rec = roster["badges"].get(a.id)
        if not rec or rec["role"] in TOP:
            raise Refused(f"no employee badge {a.id}")
        if rec.get("revoked") or next(b for b in c["badges"] if b["id"] == a.id)["status"] in ("OUT", "REVOKED"):
            raise Refused(f"{a.id} is clocked out; hire again instead of amending")
        was = {}
        if a.job:
            was["job"], rec["job"] = rec.get("job", ""), a.job
        if a.done_when:
            was["done_when"], rec["done_when"] = rec.get("done_when", ""), a.done_when
        if a.add_files:
            was["files"] = rec.get("files", "")
            rec["files"] = ", ".join(x for x in (rec.get("files", ""), a.add_files) if x)
        if a.set_files:  # a wrong pattern is dropped, not only joined by the right one
            was["files"], rec["files"] = rec.get("files", ""), a.set_files
        if a.eta:
            was["eta_s"], rec["eta_s"] = rec.get("eta_s", 0), parse_dur(a.eta)
        seat = seat_arg(a)
        if seat:
            if seat != RQ and any(b.get("vmdir") == seat and b["id"] != a.id for b in headcount(c)):
                raise Refused(f"the seat {seat} is held by another employee; one seat per employee")
            was["vmdir"], rec["vmdir"] = rec.get("vmdir", ""), seat
        append_event(d, {"at": now, "id": mgr["id"], "ev": "amend", "for": a.id, "was": was,
                         "now": {k: rec[k] for k in was}})
        write_roster(d, roster)
    print(f"{a.id} amended by {mgr['id']}: {', '.join(was)}")
    for k in was:
        print(f"    {k}: {rec[k]}")
    for w in vendored_warnings(a.add_files or a.set_files):
        print(f"  ! vendored: {w}")
    for w in forced:
        print(f"  ! --force-files: {w}")
    if a.job or a.done_when or a.add_files or a.set_files:  # the amended brief against the amended files
        for w in report_path_warnings(rec.get("files", ""), rec.get("job", ""), rec.get("done_when", "")):
            print(f"  ! report path: {w}")
    if a.add_files or a.set_files:  # the amended files on a temp badge
        for w in harness_warnings(rec.get("files", ""), rec.get("kind", "")):
            print(f"  ! harness config: {w}")
    print(f"tell {a.id} ({rec.get('session') or 'no session recorded'}) by message: the badge line is unchanged")
    print_brief(rec, mgr)
    return 0


def print_brief(rec, mgr):
    """The badge line and the brief as `hire` printed it, from the roster record as it is now."""
    print(f"badge: {rec['line']}")
    print("\n--- brief (paste into start_session's prompt or the Agent prompt) ---")
    print(brief(rec, {"id": rec.get("by") or mgr["id"]}, read_state()))


def cmd_brief(a, d, now):
    """The manager reprints a badge's line and full brief, for a bench re-badge or a refused
    start_session, instead of rebuilding it by hand. Read-only."""
    key = load_key(d)
    roster = read_roster(d)
    mgr = manager_of(d, key, roster, a.by, crew(d, now))
    rec = roster["badges"].get(a.id)
    if not rec or rec["role"] in TOP:
        raise Refused(f"no employee badge {a.id}")
    if rec.get("revoked"):
        print(f"note: {a.id} is revoked; hire again for new work")
    print_brief(rec, mgr)
    return 0


def cmd_clock_in(a, d, now):
    key = load_key(d)
    with locked(d):
        roster = read_roster(d)
        rec = verify_line(key, roster, a.badge)
        me = next(b for b in crew(d, now)["badges"] if b["id"] == rec["id"])
        if me["on"]:
            raise Refused(f"{rec['id']} is already on the clock (in at {hhmm(me['in_at'], now)})")
        append_event(d, {"at": now, "id": rec["id"], "ev": "in"})
    print(f"{rec['id']} {rec['name']} clocked in at {hhmm(now, now)}"
          + ("" if rec["role"] == "FOUNDER" else f"; approximate finish {hhmm(now + rec.get('eta_s', 0), now)}"))
    return 0


def punch(a, d, now, ev, **fields):
    key = load_key(d)
    with locked(d):
        roster = read_roster(d)
        rec = verify_line(key, roster, a.badge)
        e = append_event(d, {"at": now, "id": rec["id"], "ev": ev, **{k: v for k, v in fields.items() if v not in (None, "", [])}})
    return rec, e


def cmd_progress(a, d, now):
    if not 0 <= a.pct <= 100:
        raise Refused("--pct is 0 to 100")
    eta = parse_eta(a.eta, now) if a.eta else None
    wait_on = (a.waiting_on or "").strip() or None
    if wait_on and not re.fullmatch(r"[A-Za-z0-9._-]+", wait_on):
        raise Refused("--waiting-on is one badge id or queue id (EMP-07, MGR-3-counted)")
    run = None
    if a.run:  # a run folder lies in its builder's worktree; the roster carries its absolute path
        p = Path(a.run).expanduser()
        p = p if p.is_absolute() else Path.cwd() / p
        if not p.is_dir():
            raise Refused(f"--run {a.run!r}: no such folder ({p.as_posix()}); give the run folder itself, from your worktree")
        run = p.resolve().as_posix()
    rec, _ = punch(a, d, now, "progress", pct=a.pct, eta=eta, note=a.note, waiting_on=wait_on, run=run)
    print(f"{rec['id']} at {a.pct}%" + (f", approximate finish {hhmm(eta, now)}" if eta else "") +
          (f"; waits on {wait_on}: not STALE or OVERDUE while its job holds a seat or waits in the queue "
           "(post again without --waiting-on when the wait ends)" if wait_on else "") +
          (f"; run folder on the roster: {run}" if run else ""))
    return 0


def git(args, cwd=None, timeout=60):
    """(exit code, stdout) of a git command; (None, '') when git itself cannot run."""
    try:
        # quotePath off: a non-ASCII path comes back as itself, not as octal escapes
        r = subprocess.run(["git", "-c", "core.quotePath=false", *args], cwd=str(cwd) if cwd else None, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None, ""
    return r.returncode, r.stdout


_FOLD = {}


def path_fold(top):
    """The function that makes two spellings of one path equal in the checkout at `top`: os.path.normcase and lower
    case where the file system does not tell Gym/Prereg from gym/prereg (found once per checkout: are the repo's
    .git and .GIT the same path?), else the path as it is. Paths here use /, as git prints them."""
    key = str(top)
    if key not in _FOLD:
        try:
            a = Path(top) / ".git"
            _FOLD[key] = bool(a.exists() and (Path(top) / ".GIT").exists() and os.path.samefile(a, Path(top) / ".GIT"))
        except OSError:
            _FOLD[key] = False
    if _FOLD[key]:
        return lambda p: os.path.normcase(str(p)).replace("\\", "/").lower()
    return lambda p: str(p)


def owned_patterns(files, base=None):
    """A badge's --files text as (patterns that can be checked, entries that cannot): free text ("the review file
    only") and absolute paths are not patterns, as in files_warnings. A bare word ("none", "tests") is free text
    too, unless `base` holds a file or folder of that name ("docs", "Makefile")."""
    pats, loose = [], []
    text = re.sub(r"\s\([^)]*\)", "", files or "")  # "docs/x.md (new, see {a,b})": the note goes first
    for raw in [p.strip() for p in re.split(r"[,;](?![^{]*\})", text) if p.strip()]:  # not inside {a,b}
        pat = raw.strip("`'\"").replace("\\", "/")
        pat = pat[2:] if pat.startswith("./") else pat
        bare = not re.search(r"[/.*]", pat)
        if (not pat or re.search(r"\s", pat) or pat.startswith("/") or re.match(r"^[A-Za-z]:", pat)
                or (bare and not (base and (Path(base) / pat).exists()))):
            loose.append(raw)
            continue
        todo = [pat]
        while todo:  # {a,b}, which fnmatch does not know, one group at a time
            p = todo.pop(0)
            m = re.search(r"\{([^{}]*)\}", p)
            if m:
                todo += [p[:m.start()] + alt.strip() + p[m.end():] for alt in m.group(1).split(",")]
            else:
                pats.append(p.rstrip("/"))
    return pats, loose


def owns(pats, path):
    """Does a list of owned patterns cover a repo path? A pattern is a file, a folder (everything under it) or a
    glob, where * and ** both cross folders, and `**/` also matches no folder at all (`.claude/**/*.json`
    owns `.claude/settings.json`)."""
    import fnmatch

    def zero_folder(p):  # the pattern with every subset of its `**/` removed
        out, todo = [], [p]
        while todo:
            q = todo.pop()
            if q in out:
                continue
            out.append(q)
            i = q.find("**/")
            while i >= 0:
                todo.append(q[:i] + q[i + 3:])
                i = q.find("**/", i + 1)
        return out

    for p0 in pats:
        for p in zero_folder(p0):
            if path == p or path.startswith(p + "/") or fnmatch.fnmatchcase(path, p.replace("**", "*")):
                return True
            if p.endswith("/**") and path.startswith(p[:-3].rstrip("/") + "/"):
                return True
    return False


# `git … config … user.name <value>` or `--unset user.name`: a write. A read (--get, --list, -l, --show-*, no value,
# or only a redirect after the key) is not. A text match cannot be sure, so a hit in a diff is a warning to read
# the line; the shared config actually holding user.* is the problem.
GIT_CONFIG_WRITE = re.compile(
    r"\bgit\b[^\n|;&]*?\bconfig\b(?:(?!--get|--list|--show|\s-l\b)[^\n|;&])*?"
    r"(?:--unset(?:-all)?[\"',\s]+[\"']?user\.(?:name|email)\b|\buser\.(?:name|email)[\"']?[\s,]+(?!\d?>)[\"'\w$])")


def git_bytes(args, cwd=None, timeout=60):
    """(exit code, stdout bytes) of a git command, for file contents hashed as they are; (None, b'') when git cannot run."""
    try:
        r = subprocess.run(["git", *args], cwd=str(cwd) if cwd else None, capture_output=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return None, b""
    return r.returncode, r.stdout


def lf_sha256(data):
    """The prereg pins' rule: sha256 of the bytes with CRLF read as LF."""
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def project_handin_check(top, changed):
    """The project's own hand-in check as (problem, warning, fact), each a text or None. The profile names it:
    measure.handin_check is a command line, run in the worktree when the branch changes a file that matches a glob in
    measure.handin_check_paths (a size audit after a change to shipped code, say). Both empty: skipped, nothing
    said. A problem when it exits non-zero; a warning that names it when it is configured and did not run."""
    p = prof()
    cmd = str(p.get("measure.handin_check", "") or "").strip()
    if not cmd:
        return None, None, None
    globs = p.get("measure.handin_check_paths", []) or []
    globs = [str(g).replace("\\", "/").strip().rstrip("/") for g in (globs if isinstance(globs, list) else [globs])
             if str(g).strip()]
    hit = [f for f in changed if owns(globs, f)]
    if not hit:
        why = ("measure.handin_check_paths names no path" if not globs else
               "no file your commits change matches measure.handin_check_paths")
        return None, (f"the project's hand-in check (`{cmd}`) was not run: {why}. If your change needs it, run it "
                      "yourself and give its result in the hand-in"), "not run"
    what = hit[0] + (f" and {len(hit) - 1} more" if len(hit) > 1 else "")
    try:
        limit = float(p.get("measure.handin_check_timeout_s", 900))
    except (TypeError, ValueError):
        limit = 900.0
    try:
        r = subprocess.run(cmd, shell=True, cwd=str(top), capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=limit)
    except subprocess.TimeoutExpired:
        return None, (f"the project's hand-in check (`{cmd}`) was not run to its end: no answer in {int(limit)} s. You "
                      f"changed {what}: run it yourself and give its result in the hand-in"), "not finished"
    except (OSError, subprocess.SubprocessError) as e:
        return None, (f"the project's hand-in check (`{cmd}`) was not run: it could not start ({type(e).__name__}). You "
                      f"changed {what}: run it yourself and give its result in the hand-in"), "not run"
    if r.returncode != 0:
        tail = " | ".join([l.strip() for l in (r.stdout + "\n" + r.stderr).splitlines() if l.strip()][-3:])[:300]
        return (f"the project's hand-in check (`{cmd}`, run because you changed {what}) exited {r.returncode}"
                + (f": {tail}" if tail else "") + ". Fix what it names and run handin again; if the brief says the "
                "manager runs it, say that in the hand-in instead"), None, f"exit {r.returncode}"
    return None, None, "passed"


def prereg_pins(doc):
    """(contract path, every sha256 it was pinned by with the latest last, the commits named for it) from one prereg's
    JSON, or None when it pins no contract. Prereg formats vary by lane; these are the keys read as holding a
    contract's sha256 or commit:
      the contract:   contract (or contract_file) .sha256/.commit, contract_history[].sha256/.commit,
                      top-level contract_sha256/contract_commit, pinned.contract_sha256[_after_aN]
      each amendment: contract_sha256/contract_commit, contract.sha256/.commit, pinned_changes.contract/.contract_commit,
                      contract_pinned.sha256/.commit/.commits, contract_amendment_adopted.commit,
                      contract_amendments_adopted[].commit
      older pins:     contract_sha256_before, replaces_contract_sha256, contract_pinned.was, pinned.contract_sha256_before_a1
    The latest pin is the last of: contract_history, the contract block, the pinned block, then each amendment in
    order; an older pin never counts as the latest."""
    if not isinstance(doc, dict):
        return None
    c = doc.get("contract") if isinstance(doc.get("contract"), dict) else doc.get("contract_file")
    if not isinstance(c, dict) or not isinstance(c.get("path"), str):
        return None
    pins, older, commits = [], [], []

    def sha(v, into):
        if isinstance(v, str) and re.fullmatch(r"[0-9a-f]{64}", v.strip()):
            into.append(v.strip())

    def cm(v):
        if isinstance(v, list):
            for x in v:
                cm(x)
        elif isinstance(v, str):
            m = re.match(r"([0-9a-f]{7,40})\b", v.strip())
            if m:
                commits.append(m.group(1))

    def blk(b, into=pins):
        if isinstance(b, dict):
            sha(b.get("sha256"), into)
            cm(b.get("commit"))
            cm(b.get("commits"))

    for h in doc.get("contract_history") or []:  # the texts read before the one the prereg pins
        blk(h)
    blk(c)
    sha(doc.get("contract_sha256"), pins)
    cm(doc.get("contract_commit"))
    pd = doc.get("pinned") if isinstance(doc.get("pinned"), dict) else {}
    sha(pd.get("contract_sha256_before_a1"), older)
    for k in sorted((k for k in pd if re.fullmatch(r"contract_sha256_after_a\d+", k)), key=lambda k: int(k.rsplit("a", 1)[1])):
        sha(pd[k], pins)
    sha(pd.get("contract_sha256"), pins)
    for am in doc.get("amendments") or []:
        if not isinstance(am, dict):
            continue
        sha(am.get("contract_sha256_before"), older)
        sha(am.get("replaces_contract_sha256"), older)
        cp = am.get("contract_pinned")
        if isinstance(cp, dict):
            sha(cp.get("was"), older)
        sha(am.get("contract_sha256"), pins)
        cm(am.get("contract_commit"))
        blk(am.get("contract"))
        blk(cp)
        pc = am.get("pinned_changes")
        if isinstance(pc, dict):
            sha(pc.get("contract"), pins)
            cm(pc.get("contract_commit"))
        ad = am.get("contract_amendment_adopted")
        cm(ad.get("commit") if isinstance(ad, dict) else None)
        for ad in am.get("contract_amendments_adopted") or []:
            cm(ad.get("commit") if isinstance(ad, dict) else None)
    latest = pins[-1:] if pins else older[-1:]
    every = [s for s in dict.fromkeys(older + pins) if s not in latest] + latest
    return c["path"].replace("\\", "/"), every, list(dict.fromkeys(commits))


def pinned_warnings(top, base, changed, head="HEAD"):
    """What a branch does to a contract or prereg that `base`'s <gym>/prereg pins: a pinned contract changed
    to text no pin holds, or to an older pin; one dropped; a commit a prereg names dropped from the branch (reset or
    rebased away); a pinned prereg's contract block or earlier amendments rewritten. Warnings, not problems: the
    manager decides. `head` is the branch tip to check (HEAD; a ref name reads another branch, read-only)."""
    out = []
    _, ls = git(["ls-tree", "--name-only", base, gym_rel() + "/prereg/"], top)
    _, mine = git(["log", "--format=%H%x09%s", f"{base}..{head}"], top)
    titles = {}  # a branch commit's title -> its short sha: a named commit rebased away has a copy with its title
    for row in mine.splitlines():
        sha_, _, title = row.partition("\t")
        titles.setdefault(title.strip(), sha_[:8])
    mine = {row.partition("\t")[0] for row in mine.splitlines() if row.strip()}
    for p in [x.strip() for x in ls.splitlines() if x.strip().endswith(".json")]:
        _, text = git(["show", f"{base}:{p}"], top)
        try:
            doc = json.loads(text)
        except ValueError:
            continue
        if not isinstance(doc, dict):
            continue
        new = None
        if p in changed:
            rc, now_text = git(["show", f"{head}:{p}"], top)
            if rc != 0:
                out.append(f"your branch removes {p}, a prereg {base} has pinned: a pin is never removed without the "
                           "manager's word")
            else:
                try:
                    new = json.loads(now_text)
                except ValueError:
                    new = None
                olds = doc.get("amendments") if isinstance(doc.get("amendments"), list) else []
                news = new.get("amendments") if isinstance(new, dict) and isinstance(new.get("amendments"), list) else []
                if not isinstance(new, dict) or new.get("contract") != doc.get("contract") or news[:len(olds)] != olds:
                    out.append(f"your branch rewrites what {base}'s {p} pinned (its contract block or an earlier "
                               "amendment): add a dated amendment instead, with the manager's word")
        pin = prereg_pins(doc)
        if not pin:
            continue
        path, pins, named = pin
        repin = (prereg_pins(new) or (None, [], []))[1] if new else []  # the branch's own prereg pinning it anew
        if path in changed and pins:
            rc, data = git_bytes(["show", f"{head}:{path}"], top)
            if rc != 0:
                out.append(f"your branch removes {path}, which {base}'s {p} pins by sha256: a pinned contract is never "
                           "removed without the manager's word")
            elif lf_sha256(data) not in (pins[-1], *repin[-1:]):
                old = lf_sha256(data) in pins
                out.append(f"your branch changes {path}, which {base}'s {p} pins by sha256 (latest {pins[-1][:12]}); "
                           + ("its text is an older pin's: was a pinned amendment dropped? " if old else
                              "its text matches no pin: ")
                           + "a pinned contract changes only by a new appended amendment, with the manager's word, and "
                           "the grader pins it again before counted data")
        for cm in named if mine else []:
            rc, hist = git(["rev-list", "--max-count=500", cm, f"^{base}"], top)
            hist = hist.split()
            if rc != 0 or not hist or hist[0] in mine or not (set(hist) & mine):
                continue  # unknown, on main already, held by the branch, or another branch's commit
            _, title = git(["log", "-1", "--format=%s", cm], top)
            copy = titles.get(title.strip())
            out.append(f"{base}'s {p} names commit {cm} for {path}, which shares your branch's history but is no "
                       "longer on it (" + (f"rebased: {copy} has its title; the prereg still names the old sha" if copy
                                           else "reset or rebased away?") +
                       "): restore it, or tell the manager before the hand-in")
    return out


def handin_checks(rec, repo, base, commits, c, report=None):
    """The pre-hand-in checks as (problems, warnings, facts). A problem is something the manager would send back;
    a warning is something the hand-in must say."""
    bad, warn, facts = [], [], {}
    rc, top = git(["rev-parse", "--show-toplevel"], repo)
    if rc != 0:
        raise Refused(f"{repo} is not a git checkout; run handin from your own worktree")
    top = Path(top.strip())
    # the main checkout is the one whose git dir is the common dir; a linked worktree's is not
    _, gd = git(["rev-parse", "--path-format=absolute", "--git-dir"], top)
    _, cd = git(["rev-parse", "--path-format=absolute", "--git-common-dir"], top)
    in_main = bool(gd.strip()) and Path(gd.strip()).resolve() == Path(cd.strip()).resolve()
    _, branch = git(["rev-parse", "--abbrev-ref", "HEAD"], top)
    _, tip = git(["rev-parse", "--short=8", "HEAD"], top)
    facts.update(worktree=top.as_posix(), branch=branch.strip(), tip=tip.strip(), in_main=in_main)
    rc, _ = git(["rev-parse", "--verify", "--quiet", base + "^{commit}"], top)
    if rc != 0:
        raise Refused(f"no base {base!r} in this repo (--base names the branch you were cut from)")
    if commits:
        shas = []
        for s in commits:
            rc, full = git(["rev-parse", "--verify", "--quiet", s + "^{commit}"], top)
            if rc != 0:
                bad.append(f"commit {s} does not exist in this repo (or the short sha is ambiguous): quote a sha from "
                           "the commit's own output")
            else:
                shas.append(full.strip())
    else:
        _, out = git(["rev-list", "--reverse", f"{base}..HEAD"], top)
        shas = out.split()
    facts["commits"] = [s[:8] for s in shas]
    if not shas and not bad:
        warn.append(f"no commit of yours on {branch.strip()} past {base}: a report-only job names its report file in the "
                    "clock-out note; a job done in the main checkout passes --commits a,b")
    pats, loose = owned_patterns(rec.get("files", ""), top)
    # the tree: every untracked file by its own path; the report passed with --file is not a
    # leftover while it is untracked (an edited tracked report is); and in the main checkout, which every employee
    # there shares, only paths this badge owns are this badge's to commit
    # every list of names is read with -z and split on NUL: git prints a name that holds a quote, a backslash or a
    # control character quoted otherwise, and a quoted name matches no wall
    _, st = git(["status", "--porcelain", "-z", "--no-renames", "--untracked-files=all"], top)
    rows = [(l[:2], l[3:]) for l in st.split("\0") if len(l) > 3]
    if report:
        try:
            rel = Path(report).resolve().relative_to(top.resolve()).as_posix()
            rows = [(code, p) for code, p in rows if not (p == rel and code == "??")]
        except ValueError:
            pass
    dirty = [p for _, p in rows]
    if in_main:
        others = [p for p in dirty if not owns(pats, p)]
        dirty = [p for p in dirty if owns(pats, p)]
        if others:
            warn.append(f"the main checkout has {len(others)} changed path(s) that are not in your files (first: "
                        f"{others[0]}): not yours to commit; tell the manager if a counted run is near")
    if dirty:
        bad.append(f"the tree is not clean ({len(dirty)} path(s), first: {dirty[0]}): commit your files or "
                   "remove the leftovers; the manager merges commits, not a working tree")
    # the files against the badge
    def names(out):
        return [f.lstrip("\n") for f in out.split("\0") if f.strip("\n")]

    def commit_files(sha_list):
        out_ = []
        for s in sha_list:
            _, out = git(["show", "--no-renames", "--name-only", "-z", "--format=", s], top)
            out_ += names(out)
        return sorted(set(out_))

    changed = commit_files(shas)
    facts["files"] = changed
    # The walls look at more than each commit's own list: a merge that kept one parent's copy (`git merge -s ours`)
    # prints nothing in `git show --name-only`, and --commits a,b names only some commits. So the branch's whole
    # difference from the base counts too: what it changed since the fork (base...HEAD) and where its tree differs
    # from the base as it is now (base HEAD). A path in the second list alone is the branch's doing only when the
    # branch's copy is not the fork point's: where the base alone moved on since the fork (the branch is behind),
    # a merge takes the base's copy and nothing is lost, so that path is not held against the badge.
    # And the walls always stand against the profile's main branch as well as the base given: --base names the
    # branch a badge was cut from (for the own-files check), and a walled change made on that branch, or a --base
    # HEAD, would otherwise pass unseen.
    mainb = main_branch()
    wall_bases = [base]
    if mainb != base:
        rc, _ = git(["rev-parse", "--verify", "--quiet", mainb + "^{commit}"], top)
        if rc == 0:
            wall_bases.append(mainb)
            warn.append(f"--base is {base}, not the main branch {mainb}: your own files were checked against {base}; the "
                        f"road graph, the measure's files and the run records were checked against both {base} and {mainb}")
        elif rec.get("role") != "MANAGER":
            bad.append(f"cannot check the walls: no {mainb} here (--base is {base}, and the road graph, the measure's "
                       f"files and the run records are always checked against the main branch {mainb}). Run handin in a "
                       "checkout of the project's own repository")
        else:
            warn.append(f"no {mainb} here: the walls were checked against {base} only")

    def blob(rev, path):
        rc, out = git(["rev-parse", "--verify", "--quiet", f"{rev}:{path}"], top)
        return out.strip() if rc == 0 else ""

    def wall_view(b):
        """One base's view: (files of the commits looked at, since-the-fork files, files only differing now, forks)."""
        if b == base:
            in_commits = changed
        else:  # the main branch: every commit past it, whatever --base or --commits named
            _, out = git(["rev-list", f"{b}..HEAD"], top)
            in_commits = sorted(set(changed) | set(commit_files(out.split())))
        since_fork, now_differs = [], []
        for into, spec in ((since_fork, [f"{b}...HEAD"]), (now_differs, [b, "HEAD"])):
            rc, out = git(["diff", "--no-renames", "--name-only", "-z", *spec], top)
            if rc == 0:
                into += names(out)
            else:
                warn.append(f"`git diff --name-only {' '.join(spec)}` did not run: the branch's tree was not checked "
                            "against the road graph, the measure's files and the run records; say so in the hand-in")
        _, mbs = git(["merge-base", "--all", b, "HEAD"], top)
        return (in_commits, sorted(set(since_fork) - set(in_commits)),
                sorted(set(now_differs) - set(since_fork) - set(in_commits)), mbs.split())

    views = [(b, wall_view(b)) for b in wall_bases]
    facts["tree_files"] = views[0][1][1]
    fold = path_fold(top)

    def named(prefixes, whole=True):
        """(the walled paths, each with where it was seen; a sentence on the tree's ones) or ([], ''). A path is
        walled when it is one of the prefixes or under it (whole=False: when it starts with one)."""
        pre = [fold(w) for w in prefixes]

        def hit(f):
            g = fold(f)
            return any((g == w or g.startswith(w + "/")) if whole else g.startswith(w) for w in pre)

        a, b, seen = [], [], set()
        for _, (in_commits, _, _, _) in views:
            for f in in_commits:
                if hit(f) and f not in seen:
                    seen.add(f)
                    a.append(f)
        for bname, (_, tree, behind_only, forks) in views:
            for f in sorted(tree + behind_only):
                if f in seen or not hit(f):
                    continue
                # a path that differs only now is the branch's doing when its copy is not every fork point's
                if f in tree or not forks or any(blob(m, f) != blob("HEAD", f) for m in forks):
                    seen.add(f)
                    b.append((f, bname))
        out = [f"{f} (in a commit)" for f in a] + [f"{f} (the branch's tree differs from {bn})" for f, bn in b]
        how = ("" if not b else f" A path marked as the tree differing is in no commit checked here: a merge that "
               f"kept one side (`git merge -s ours`) or a commit not named in --commits. `git diff --name-only "
               f"{b[0][1]} HEAD` lists it, and merging this branch would put your copy in place of {b[0][1]}'s.")
        return out, how

    def listed(hit):
        return ", ".join(hit[:6]) + (" …" if len(hit) > 6 else "")

    def prof_list(key):
        v = prof().get(key) or []
        return [str(w).replace("\\", "/").strip("/") for w in (v if isinstance(v, list) else [v]) if str(w).strip("/\\")]

    # the road graph is the manager's: flow.py graph takes the manager's badge
    road, how = named([prof().rel("flow").strip("/") + "/road."], whole=False)
    if road and rec.get("role") not in TOP:
        bad.append(f"your branch changes the road graph ({listed(road)}): only the manager edits it, through "
                   "`flow.py graph ... --by <the manager's line>`. Take the change out and ask the manager for it." + how)
    # the measure is the grader's: the wall between the one who builds and the one who grades
    if rec.get("role") != "GRADER":
        graded, how = named(prof_list("measure.grader_owned"))
        if graded:
            bad.append(f"your branch changes the measure's files ({listed(graded)}): "
                       "only a grader writes what the profile lists under measure.grader_owned. Take the change out and "
                       "send the grader a patch or a written request." + how)
    # a run's records decide what the map shows as PASS: the run writes them, whoever queued it commits them
    if rec.get("role") not in ("GRADER", "MANAGER"):
        recs, how = named(prof_list("measure.records"))
        if recs:
            bad.append(f"your branch changes a run's records ({listed(recs)}): a run's records are written by the run "
                       "and committed by whoever queued the counted run (the manager, or a grader), never by the "
                       "badge that built what is measured (measure.records in the profile). Take the change out; if a "
                       "counted run wrote them in your worktree, tell the manager, who commits them." + how)
    if pats:
        outside = [f for f in changed if not owns(pats, f)]
        if outside:
            line = (f"{len(outside)} changed file(s) outside the files your badge owns ({rec.get('files')}): "
                    + ", ".join(outside[:6]) + (" …" if len(outside) > 6 else ""))
            if loose:
                warn.append(line + f"; your badge also lists {'; '.join(loose)!r}, which cannot be checked: say in the "
                            "hand-in why each is yours")
            else:
                bad.append(line + ": take them out, or ask the manager to widen the badge (office.py amend --add-files). "
                           f"If your branch was cut from a branch other than {base}, pass --base <that branch>")
    elif changed:
        warn.append("your badge names no checkable file list, so the changed files were not checked against it")
    # main's place
    if not in_main:
        _, mb = git(["merge-base", base, "HEAD"], top)
        _, behind = git(["rev-list", "--count", f"HEAD..{base}"], top)
        facts["base"] = mb.strip()[:8]
        if behind.strip() not in ("", "0"):
            warn.append(f"{base} has {behind.strip()} commit(s) your branch lacks (you forked at {mb.strip()[:8]}): say so in "
                        "the hand-in; rebase only if the brief allows it, and never rewrite a commit already merged")
        _, cherry = git(["cherry", base, "HEAD"], top)
        dup = [l[2:10] for l in cherry.splitlines() if l.startswith("- ")]
        if dup:
            warn.append(f"{len(dup)} of your commits are already in {base} as copies ({', '.join(dup[:4])}): name only "
                        "the new ones, or the manager's merge conflicts")
    # git config: a linked worktree writes the main repo's .git/config
    for k in ("user.name", "user.email"):
        rc, v = git(["config", "--local", "--get", k], top)
        if rc == 0 and v.strip():
            bad.append(f"the repo's own git config sets {k} = {v.strip()!r}: a test or script ran `git config` in a "
                       "worktree, which rewrites every checkout's identity; tell the manager (do not unset it yourself "
                       "unless you set it), and set a scratch identity by GIT_AUTHOR_*/GIT_COMMITTER_* env instead")
    hits = []
    for s in shas:
        _, out = git(["show", "--no-renames", "--format=", "--unified=0", s], top)
        cur = ""
        for l in out.splitlines():
            if l.startswith("+++ b/"):
                cur = l[6:]
            elif (l.startswith("+") and not l.startswith("+++") and not l[1:].lstrip().startswith(("#", "//"))
                  and GIT_CONFIG_WRITE.search(l)
                  and Path(cur).name != "office.py" and not cur.endswith(".md")):
                hits.append(cur)
    if hits:
        warn.append("a commit adds what reads as a `git config user.*` write (" + ", ".join(sorted(set(hits))[:4]) + "): "
                    "if it is one, use GIT_AUTHOR_NAME/GIT_AUTHOR_EMAIL/GIT_COMMITTER_* in the command's environment "
                    "instead; if it is not, say so in the hand-in")
    warn += pinned_warnings(top, base, changed)
    # a flagged title: every commit of the badge ends with the profile's trailer, so the in-depth review finds it
    fl = flagged_of(title_of(rec))
    if fl and fl["trailer"] and shas:
        bare = []
        for s in shas:
            _, msg = git(["log", "-1", "--format=%B", s], top)
            if fl["trailer"] not in [l.strip() for l in msg.splitlines()]:
                bare.append(s[:8])
        if bare:
            bad.append(f"{len(bare)} commit(s) lack the trailer line `{fl['trailer']}` ({', '.join(bare[:6])}"
                       f"{' …' if len(bare) > 6 else ''}): the title {title_of(rec)} is flagged for an in-depth review "
                       "([flagged] in the profile), and the review finds a commit by that line. Reword each commit on "
                       "your own branch so its message ends with it (never a commit already merged)")
    # the project's own hand-in check
    hc_bad, hc_warn, hc_fact = project_handin_check(top, changed)
    if hc_fact:
        facts["handin_check"] = hc_fact
    if hc_bad:
        bad.append(hc_bad)
    if hc_warn:
        warn.append(hc_warn)
    if c["vm"]["sweeps"] or c["vm"].get("unmarked"):
        warn.append(f"a counted sweep or run is (or may be) in the queue of {res_name()}: commit nothing in the main checkout and put no "
                    "file there; the manager merges after it ends")
    fz = c.get("freeze") or {}
    if fz.get("on"):
        warn.append(f"the main checkout is frozen ({freeze_text(fz, c.get('now'))}): commit nothing there and put no "
                    "file there; the manager merges after the freeze is lifted")
    return bad, warn, facts


def keep_earlier_handin(out, mark, body):
    """when handins/<id>.md is a READY hand-in with a report other than `body`, move it to the next free
    <id>.<n>.md and return that path. A NOT READY one, or a re-run with the same report (or none), is overwritten,
    and None is returned (each fix-and-rerun must not leave another file)."""
    if not body or not out.is_file():
        return None
    old = out.read_text(encoding="utf-8", errors="replace")
    was = old.split(mark, 1)[1].strip() if mark in old else ""
    if not was or was == body.strip() or not old.split("\n", 1)[0].rstrip().endswith(": READY"):
        return None
    n = 1
    while out.with_name(f"{out.stem}.{n}.md").exists():
        n += 1
    dest = out.with_name(f"{out.stem}.{n}.md")
    for _ in range(50):
        try:
            out.replace(dest)
            return dest
        except PermissionError:  # some systems will not move a file a reader has open this instant
            time.sleep(0.05)
    out.replace(dest)
    return dest


def cmd_handin(a, d, now):
    key = load_key(d)
    roster = read_roster(d)
    rec = verify_line(key, roster, a.badge)
    c = crew(d, now)
    commits = [x.strip() for x in (a.commits or "").split(",") if x.strip()]
    # a check the manager runs for an employee (--by) is logged under the manager, as amend is, so it
    # does not count as the employee being heard
    by = manager_of(d, key, roster, a.by, c)["id"] if a.by else None
    if a.file and not Path(a.file).is_file():
        raise Refused(f"--file {a.file!r}: no such file")
    base = a.base or main_branch()
    bad, warn, facts = handin_checks(rec, Path(a.repo) if a.repo else Path.cwd(), base, commits, c, report=a.file)
    out = d / "handins" / f"{rec['id']}.md"
    mark = "## The employee's report"
    body = ""
    if a.file:
        body = Path(a.file).read_text(encoding="utf-8", errors="replace")
    elif out.is_file():  # a re-run without --file keeps the report an earlier run filed
        old = out.read_text(encoding="utf-8", errors="replace")
        body = old.split(mark, 1)[1].strip() if mark in old else ""
    verdict = "READY" if not bad else "NOT READY"
    lines = [f"# Hand-in {rec['id']} {rec['name']} ({title_text(rec)}): {verdict}",
             "",
             f"- checked {local(now):%Y-%m-%d %H:%M %Z} by `office.py handin`{' (run by ' + by + ')' if by else ''}: "
             f"{len(bad)} problem(s), {len(warn)} warning(s)",
             f"- worktree: {facts['worktree']}" + (" (the main checkout)" if facts["in_main"] else ""),
             f"- branch: {facts['branch']} at {facts['tip']}" + (f", forked from {base} at {facts['base']}" if facts.get("base") else ""),
             f"- commits ({len(facts['commits'])}): {', '.join(facts['commits']) or 'none'}",
             f"- files changed ({len(facts['files'])}): {', '.join(facts['files'][:40]) or 'none'}" + (" …" if len(facts["files"]) > 40 else ""),
             f"- job: {rec.get('job', '')}",
             f"- done when: {rec.get('done_when') or '(none given)'}"]
    if "handin_check" in facts:
        lines.append(f"- the project's hand-in check (`{prof().get('measure.handin_check')}`): {facts['handin_check']}")
    lines += [f"- PROBLEM: {x}" for x in bad] + [f"- warning: {x}" for x in warn]
    if body:
        lines += ["", mark, "", body.rstrip()]
    out.parent.mkdir(parents=True, exist_ok=True)
    kept = keep_earlier_handin(out, mark, body)  # a second round's report never overwrites the first
    out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    with locked(d):
        append_event(d, {"at": now, "id": by or rec["id"], "ev": "handin", "ok": not bad, "tip": facts["tip"],
                         "branch": facts["branch"], "problems": len(bad), "warnings": len(warn),
                         **({"for": rec["id"]} if by else {})})
    print(f"hand-in check for {rec['id']}: {verdict} ({len(bad)} problem(s), {len(warn)} warning(s))")
    print(f"  {facts['branch']} at {facts['tip']} in {facts['worktree']}; {len(facts['commits'])} commit(s), {len(facts['files'])} file(s)")
    for x in bad:
        print(f"  PROBLEM  {x}")
    for x in warn:
        print(f"  warning  {x}")
    print(f"  written: {out.as_posix()}" + ("" if a.file else "  (the report an earlier run filed is kept)" if body else
                                             "  (no --file: the check only; pass your report with --file)"))
    if kept:
        print(f"  the earlier hand-in, with another report, is kept as {kept.as_posix()}")
    print("  fix the problems and run it again; then clock out with the same commits" if bad else
          f"  then: clock-out --result … --commits {','.join(facts['commits']) or '<none>'}")
    return 1 if bad else 0


EMPTY_TREE = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


def reviews_since(rec, since, cwd=None, ref=None):
    """(the keys, [(path, keys it names)]) for the files under the profile's reviews folder that `ref` (the main
    branch) gained after `since` (a clock-in) and that name the badge's lane or a milestone (M1, by the profile's
    roadmap.milestone_id) its job or done-when names; (keys, None) when git cannot say."""
    ref = ref or main_branch()
    text = f"{rec.get('job', '')} {rec.get('done_when', '')}"
    try:
        stones = re.findall(r"\b(?:" + str(prof().get("roadmap.milestone_id") or r"M\d+") + r")\b", text)
    except re.error:
        stones = re.findall(r"\bM\d+\b", text)
    keys = sorted({k for k in [rec.get("lane") or ""] + stones if k})
    if not keys:
        return keys, []
    when = dt.datetime.fromtimestamp(since, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rc, c0 = git(["rev-list", "-1", "--first-parent", f"--before={when}", ref], cwd)
    if rc != 0:
        return keys, None
    rc, names = git(["diff", "--name-only", "--diff-filter=AM", c0.strip() or EMPTY_TREE, ref, "--",
                     prof().rel("reviews").strip("/")], cwd)
    if rc != 0:
        return keys, None
    hits = []
    for p in [x.strip() for x in names.splitlines() if x.strip()]:
        _, body = git(["show", f"{ref}:{p}"], cwd)
        named = [k for k in keys if re.search(rf"(?<![A-Za-z0-9]){re.escape(k)}(?!\d)", body)]
        if named:
            hits.append((p, named))
    return keys, hits


def cmd_me(a, d, now):
    """An employee's own record, read-only: after a clear, a compaction or a re-badge the session
    reads its brief here instead of rebuilding it from memory."""
    key = load_key(d)
    roster = read_roster(d)
    rec = verify_line(key, roster, a.badge)
    state = read_state()
    c = crew(d, now)
    me = next(b for b in c["badges"] if b["id"] == rec["id"])
    mgr = next((b for b in c["badges"] if b["id"] == c["manager"]), None)
    eta = f"finish ~{hhmm(me['eta'], now)}" if me.get("eta") else "no estimate"
    print(f"{rec['id']} {rec['name']} ({title_text(rec)}, {rec['kind'].lower()}): {me['status']} {me['pct']}% {eta}; "
          f"last heard {hhmm(me['heard'], now)}; session {rec.get('session') or 'not recorded'}")
    m_id, m_from = model_of(rec)
    if m_id:
        print(f"your model: {m_id} ({m_from})")
    if mgr:
        print(f"manager on the clock: {mgr['id']} {mgr['name']} ({mgr['status']}), session {mgr.get('session') or 'not recorded'}"
              + (f"; you were hired by {rec['by']}" if rec.get("by") and rec["by"] != mgr["id"] else ""))
    else:
        print("manager on the clock: none appointed")
    rc, top = git(["rev-parse", "--show-toplevel"])  # the branch this session is on, from its cwd
    _, br = git(["rev-parse", "--abbrev-ref", "HEAD"]) if rc == 0 else (None, "")
    print(f"your branch here: {br.strip()} in {top.strip()} (report this name)" if rc == 0
          else f"your branch here: none ({Path.cwd().as_posix()} is not a git checkout)")
    mb = main_branch()
    if rc == 0 and br.strip() == mb:  # a session in the main checkout is never told to work on the main branch
        print(f"  you are on {mb}: never commit here. Cut {prof().get('git.branch_prefix', 'claude/')}<job> (from {mb}, or "
              "the sha your brief names) in your own worktree, as the brief's branch line says")
    ins = [e["at"] for e in read_events(d) if e["ev"] == "in" and e["id"] == rec["id"]]
    if ins:  # a review that lands mid-job is read before the hand-in
        keys, hits = reviews_since(rec, ins[-1], None if rc == 0 else main_checkout())
        since = f"since your clock-in ({hhmm(ins[-1], now)})"
        if hits:
            print(f"reviews merged to {mb} {since} that name {', '.join(keys)}; read each before you hand in:")
            for p, named in hits:
                print(f"    {p} ({', '.join(named)})")
        elif hits is not None and keys:
            print(f"no review merged to {mb} {since} names {', '.join(keys)}")
    rq, res = c["vm"], res_name()
    fz = c["freeze"]
    if fz["on"]:  # the manager's own freeze, with or without a queue
        print(f"FREEZE: the main checkout is frozen {freeze_text(fz, now)}. Change nothing in the main checkout, "
              "tracked or not; commit only in your worktree")
    elif not has_resource():
        print("no freeze on the main checkout")
    if not has_resource():
        pass  # no shared resource in the profile: no queue, so no queue lines
    elif rq["sweeps"]:
        print(f"FREEZE: a counted sweep or run is in the queue of {res} ({', '.join(rq['sweeps'])}): change nothing in "
              "the main checkout, tracked or not; commit only in your worktree")
    elif rq.get("unmarked"):
        print(f"freeze? {', '.join(rq['unmarked'])} holds or waits for the whole of {res} under a plain id; if it is a "
              "counted run, the main checkout is frozen: ask the manager before any commit there")
    else:
        print(f"no counted run in the queue of {res}")
    if not has_resource():
        pass
    elif me.get("vm"):
        est = rq_start_text(me, now)
        print(f"your queued job: {me['vm']}" + (f"; {est}. Its end wakes you: end your turn instead of polling" if est else ""))
    else:
        print("your queued job: none queued or running")
    if me.get("run"):
        print(f"your last posted run folder: {me['run']}")
    amends = [e for e in read_events(d) if e["ev"] == "amend" and e.get("for") == rec["id"]]
    for e in amends:
        print(f"amended {hhmm(e['at'], now)} by {e['id']}: " + "; ".join(f"{k} was {str(v)[:80]!r}" for k, v in (e.get("was") or {}).items()))
    hi = [e for e in read_events(d) if e["ev"] == "handin" and e.get("for", e["id"]) == rec["id"]]
    if hi:
        print(f"last hand-in check: {'READY' if hi[-1].get('ok') else 'NOT READY'} at {hhmm(hi[-1]['at'], now)} ({hi[-1].get('tip')})")
    if rec["role"] == "FOUNDER":
        print(f"\na founder has no brief: the {prof().skill('founder')} skill is its guide. It hires no one; the manager does")
        return 0
    print("\n--- your brief as the roster has it now ---")
    print(brief(rec, mgr or {"id": rec.get("by") or "the manager"}, state))
    return 0


def cmd_runs(a, d, now):
    rows = [e for e in read_events(d) if e["ev"] == "progress" and e.get("run") and (not a.id or e["id"] == a.id)]
    seen, out = set(), []
    for e in reversed(rows):
        if e["run"] not in seen:
            seen.add(e["run"])
            out.append(e)
    if not out:
        print("no run folder posted" + (f" by {a.id}" if a.id else "") + " (office.py progress --run <folder>)")
        return 0
    for e in out[:25]:
        gone = "" if Path(e["run"]).is_dir() else "  (GONE)"
        print(f"{e['id']} {hhmm(e['at'], now)}  {e['run']}{gone}" + (f"  \"{e['note']}\"" if e.get("note") else ""))
    return 0


def cmd_fail(a, d, now):
    rec, e = punch(a, d, now, "fail", what=a.what, lane=a.lane, run_id=a.run_id, verdict=a.verdict, plan=a.plan)
    print(f"reported R{e['seq']} by {rec['id']}: {a.what}")
    return 0


def cmd_clock_out(a, d, now):
    if a.result not in RESULTS:
        raise Refused(f"--result is one of {', '.join(RESULTS)}")
    commits = [x.strip() for x in (a.commits or "").split(",") if x.strip()]
    key = load_key(d)
    if not a.by:
        # a sha the repo does not hold sends the manager looking for a commit that is not there. Checked before the
        # office lock is taken; git failing to run at all (None) is not the employee's error.
        ghost = [s for s in commits if git(["rev-parse", "--verify", "--quiet", s + "^{commit}"], prof().root)[0] == 1]
        if ghost:
            raise Refused(f"--commits names {', '.join(ghost)}, which this repo does not hold (or a short sha is "
                          "ambiguous: give more digits): read each sha from its commit's own output "
                          "(git log -1 --format=%h), then clock out again")
    with locked(d):
        roster = read_roster(d)
        c = crew(d, now)
        if a.by:
            mgr = manager_of(d, key, roster, a.by, c)
            if not a.id:
                raise Refused("the manager clocks someone out with --id")
            rec = roster["badges"].get(a.id)
            if not rec:
                raise Refused(f"no badge {a.id}")
            if rec["role"] == "FOUNDER":
                raise Refused(f"{a.id} is the founder's badge: the manager does not clock the founder out "
                              "(the founder clocks out itself, or `found --relieve` replaces the badge)")
            note = f"clocked out by {mgr['id']}" + (f": {a.note}" if a.note else "")
        else:
            rec = verify_line(key, roster, a.badge)
            note = a.note
        me = next(b for b in c["badges"] if b["id"] == rec["id"])
        if not me["on"] and me["status"] != "HIRED":
            raise Refused(f"{rec['id']} is not on the clock")
        append_event(d, {"at": now, "id": rec["id"], "ev": "out", "result": a.result,
                         **({"note": note} if note else {}), **({"commits": commits} if commits else {})})
    print(f"{rec['id']} {rec['name']} clocked out at {hhmm(now, now)}: {a.result} ({me['hours']:.1f} h)")
    if (not a.by and rec["role"] == "BUILDER" and a.result in ("done", "partial")
            and not any(e["ev"] == "handin" and e.get("for", e["id"]) == rec["id"] for e in read_events(d))):
        print("  note: no hand-in check on record for this badge (office.py handin, run in your worktree); the manager "
              "will run the same checks before the merge")
    return 0


def cmd_roster(a, d, now):
    state = read_state()
    c = crew(d, now)
    if a.json:
        print(json.dumps(c, indent=1, ensure_ascii=False))
        return 0
    shift_id, crew_max = shift_facts(state)
    slot, s0, s1 = slot_at(state.get("rota", {}).get("slots"), now)
    hc = headcount(c)
    print(f"Crew office {d.as_posix()} at {local(now):%Y-%m-%d %H:%M}")
    print(f"  slot {slot} {hhmm(s0, now)}-{hhmm(s1, now)}; shift {shift_id}; crew {len(hc)} of {crew_max if crew_max is not None else '(no crew_max)'}")
    fdr = next((b for b in c["badges"] if b["id"] == c.get("founder")), None)
    if fdr:  # outside the headcount, on its own line above the manager; a project may run with none
        print(f"  founder {fdr['id']} {fdr['name']}: {fdr['status']}" +
              (f", in {hhmm(fdr['in_at'], now)}, heard {hhmm(fdr['heard'], now)}, {fdr['pct']}%" if fdr["on"] else "") +
              f"; session {fdr.get('session') or 'not recorded'}" + (f"; \"{fdr['note']}\"" if fdr["on"] and fdr["note"] else ""))
    mgr = next((b for b in c["badges"] if b["id"] == c["manager"]), None)
    if mgr:
        print(f"  manager {mgr['id']} {mgr['name']}: {mgr['status']}" +
              (f", in {hhmm(mgr['in_at'], now)}, heard {hhmm(mgr['heard'], now)}" if mgr["on"] else "") +
              f"; session {mgr.get('session') or 'not recorded (office.py assign ' + mgr['id'] + ' --session local_...)'}")
        if mgr["on"]:
            print(f"      (UP means a punch inside {ago(limit_s('manager_stale_min')).replace('.0 h', ' h')}, not that the session is running: "
                  "check the session itself)")
    else:
        print("  manager: none appointed")
    rows = [b for b in c["badges"] if b["role"] not in TOP]
    on = [b for b in rows if b["on"]]
    res = res_name()
    print(f"  on the clock ({len(on)}):")
    for b in on:
        eta = f"finish ~{hhmm(b['eta'], now)} ({'in ' + ago(b['eta'] - now) if b['eta'] >= now else ago(now - b['eta']) + ' late'})" if b["eta"] else "no estimate"
        sess = f" {b['session']}" if b.get("session") else ""
        print(f"    {b['id']} {b['name']} {title_text(b)} {b['kind'].lower()}{sess}: {b.get('status_text') or b['status']} {b['pct']}% {eta}; "
              f"heard {hhmm(b['heard'], now)}" + (f"; {res}: {b['vm']}" if b.get("vm") else "") +
              (f"; \"{b['note']}\"" if b["note"] else ""))
        print(f"        job: {b.get('job', '')}")
        if rq_start_text(b, now):  # the short form: `me` prints the conditions
            print(f"        queue {rq_start_text(b, now).split(' if every job')[0]}"
                  + ("" if b.get("vm_start_why") else " (an estimate, not a bound)"))
        if b.get("run"):
            print(f"        run: {b['run']}")
    hired = [b for b in rows if b["status"] == "HIRED"]
    if hired:
        print(f"  hired, not clocked in ({len(hired)}): " + ", ".join(f"{b['id']} {b['name']} (issued {hhmm(b['issued'], now)})" for b in hired))
    done = [b for b in rows if b["status"] == "OUT" and b["out_at"] and b["out_at"] >= s0]
    if done:
        print(f"  clocked out this slot ({len(done)}):")
        for b in done:
            print(f"    {b['id']} {b['name']} {title_text(b)}: {b['result']} at {hhmm(b['out_at'], now)}, {b['hours']:.1f} h")
    rq = c["vm"]
    fz = c["freeze"]
    if fz["on"]:
        print(f"  FREEZE {freeze_text(fz, now)}. Change nothing in the main checkout, tracked or untracked, until the "
              f"manager lifts it ({tool()} freeze off)")
    if rq["holds"] or rq["queue"]:
        print(f"  {res} (a running job is a hold, not a queue entry: check here before telling anyone to re-queue):")
        for h in rq["holds"]:
            print(f"    seat {h['lane']}: {h['id']} since {hhmm(h['since'], now)} ({int((now - h['since']) // 60)} of "
                  f"{int(h['max'] // 60)} min{', OVERDUE' if h['overdue'] else ''}{', ALL SEATS' if h['all'] else ''}): {h['job']}")
        for i, e in enumerate(rq["queue"], 1):
            print(f"    waiting {i}. {e['id']} prio {e['prio']} since {hhmm(e['at'], now)}{' (every seat)' if e['all'] else ''}: {e['job']}")
    if rq["sweeps"]:
        print(f"  COUNTED SWEEP or run in the queue ({', '.join(rq['sweeps'])}): change nothing in the main checkout, "
              "tracked or untracked, until it ends and its records are committed (no commits, no report drafts, no map rebuild)")
    if rq.get("unmarked"):
        print(f"  COUNTED? {', '.join(rq['unmarked'])} holds or waits at prio 0 or for every seat under a plain id, which the "
              "guard cannot see: if it is a counted run, freeze the main checkout by hand until it ends (queue the next "
              "one as <badge>-counted-<lane>)")
    if rq.get("dev"):
        print(f"  dev, not counted: {', '.join(rq['dev'])}")
    print(f"  failure reports: {len(c['reports'])} in the time clock (R<seq>; the map shows the untriaged ones)")
    return 0


def cmd_end_shift(a, d, now):
    key = load_key(d)
    state = read_state()
    slot, s0, s1 = slot_at(state.get("rota", {}).get("slots"), now)
    if a.out and not Path(a.out).resolve().parent.is_dir():
        # checked before any event is written, so a bad --out never leaves a half-done end-shift to repeat
        raise Refused(f"--out {a.out}: its folder does not exist")
    with locked(d):
        roster = read_roster(d)
        c = crew(d, now)
        mgr = manager_of(d, key, roster, a.by, c)
        # a temp that is still UP is working (a review or research temp across the hand-off): it carries over
        temps = [b for b in c["badges"] if b["kind"] == "TEMP" and (b["on"] or b["status"] == "HIRED")
                 and (a.lose_temps or b["status"] != "UP")]
        for b in temps:
            append_event(d, {"at": now, "id": b["id"], "ev": "out", "result": "lost", "note": f"still in at {mgr['id']}'s end-shift"})
        append_event(d, {"at": now, "id": mgr["id"], "ev": "shift-end", "note": f"slot {slot}, shift {shift_facts(state)[0]}"})
    c = crew(d, now)
    worked = [b for b in c["badges"] if b["role"] not in TOP and (b["on"] or (b["out_at"] or 0) >= s0 or b["issued"] >= s0)]
    print(f"end of slot {slot} ({hhmm(s0, now)}-{hhmm(s1, now)}) by {mgr['id']}; temps clocked out: {', '.join(b['id'] for b in temps) or 'none'}")
    carry = [b for b in worked if b["on"]]
    if carry:
        print("  still on the clock (they carry over to the next slot's manager): " + ", ".join(f"{b['id']} {b['name']} {b['pct']}%" for b in carry))
    summary = [f"{b['id']} {b['name']} ({b['role'].lower()}{', ' + b['session'] if b.get('session') else ''}): "
               f"{b['result'] or ('on the clock ' + str(b['pct']) + '%')}, {b['hours']:.1f} h" for b in worked]
    print("  the log entry's crew field:")
    print(json.dumps(summary, indent=1, ensure_ascii=False))
    if a.out:
        # the hand-off script reads the crew list from this file, not from a hand copy
        Path(a.out).write_text(json.dumps(summary, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"  wrote the crew list to {a.out}")
    try:  # the shift journal's plan is ready and approved before the hand-off (journal.py)
        import journal
        line = journal.end_shift_line(d, state, now)
    except Exception as e:
        line = f"the shift journal could not be read ({type(e).__name__}: {e})"
    if line:
        print(f"  NOTE: {line}")
    print(f"then: clock {mgr['id']} out (clock-out --badge ... --result done|handed-off) after the hand-off entry is written")
    return 0


def freeze_is_sweeps(fz):
    """Was this freeze set by a counted sweep (sweep.py writes why "counted sweep" and its own id as `by`)?"""
    return bool(str(fz.get("why") or "").strip().lower().startswith("counted sweep")
                or re.search(r"-(?:sweep|counted(?:-[0-9A-Z]+)?)$", str(fz.get("by") or ""), re.I))


def cmd_freeze(a, d, now):
    """freeze on | off | show: the main checkout held still for a counted run. on and off are the manager's, and
    each is a punch in the time clock; show is anyone's and writes nothing."""
    f = d / FREEZE_FILE
    fz = freeze_facts(d, now)
    if a.action == "show":
        if getattr(a, "json", False):
            print(json.dumps(fz, indent=1, ensure_ascii=False))
        elif fz["on"]:
            print(f"FREEZE {freeze_text(fz, now)}")
            print("  change nothing in the main checkout, tracked or untracked, until the manager lifts it: "
                  f"{tool()} freeze off --by \"<the manager's line>\"")
        else:
            print(f"no freeze: the main checkout is open ({f.as_posix()} is absent)")
        return 0
    if not a.by:
        raise Refused(f"freeze {a.action} is the manager's: give --by \"<the manager's line>\"")
    key = load_key(d)
    if a.action == "on":
        why = (a.why or "").strip()
        if not why:
            raise Refused("freeze on needs --why: the run it covers, in a few words (\"counted run of G1\")")
        max_s = parse_dur(a.max, unit=True) if a.max else None
        with locked(d):
            roster = read_roster(d)
            mgr = manager_of(d, key, roster, a.by, crew(d, now))
            if fz["on"]:
                raise Refused(f"a freeze is already on ({freeze_text(fz, now)}). Lift it first (freeze off), then set "
                              "the new one")
            body = {"by": mgr["id"], "why": why, "lane": a.lane or None, "at": now, "max_s": max_s}
            f.write_text(json.dumps(body, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
            append_event(d, {"at": now, "id": mgr["id"], "ev": "freeze", "on": True, "why": why,
                             **({"lane": a.lane} if a.lane else {}), **({"max_s": max_s} if max_s is not None else {})})
        print(f"FREEZE on {freeze_text(freeze_facts(d, now), now)}")
        print("  the roster and every `me` say FREEZE from now; tell the crew on the clock (one message each) to "
              "commit only in their own worktrees")
        print(f"  lift it when the run's records are committed: {tool()} freeze off --by \"<your line>\"")
        return 0
    with locked(d):
        roster = read_roster(d)
        mgr = manager_of(d, key, roster, a.by, crew(d, now))
        if not fz["on"]:
            print("no freeze is on: nothing to lift, nothing written")
            return 0
        if freeze_is_sweeps(fz) and not getattr(a, "force", False):
            raise Refused(f"this freeze is a counted sweep's ({freeze_text(fz, now)}), and the sweep may still be "
                          f"running: see it with `{tool('sweep.py')} status`. A sweep lifts its own freeze at its end; "
                          "lifting it under a running sweep lets a commit into the checkout it measures. If the sweep "
                          "is dead, lift it with: freeze off --force")
        f.unlink(missing_ok=True)
        append_event(d, {"at": now, "id": mgr["id"], "ev": "freeze", "on": False, "was_by": fz["by"],
                         **({"held_s": int(now - fz["at"])} if fz.get("at") is not None else {}),
                         **({"note": a.note} if a.note else {})})
    held = f" after {ago(now - fz['at'])}" if fz.get("at") is not None else ""
    print(f"freeze lifted by {mgr['id']}{held} (it was set by {fz['by']}: {fz['why']}); the main checkout is open")
    return 0


def safe_state():
    """(state, what is missing): the state file as a dict, or {} and one sentence when it is absent or unreadable."""
    f = state_file()
    if not f.exists():
        return {}, (f"no state file ({f.as_posix()}): the shift, usage, decisions, blockers and failures were not "
                    f"read; `{tool('board.py')} init` writes one")
    try:
        s = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return {}, f"the state file cannot be read ({f.as_posix()}: {type(e).__name__}): nothing in it was checked"
    if not isinstance(s, dict):
        return {}, f"the state file is not an object ({f.as_posix()}): nothing in it was checked"
    return s, None


def _num(v):
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) and v == v else None


def _when(v):
    """A usage point's `at` (an ISO time, or epoch seconds) as epoch seconds, or None."""
    if _num(v) is not None:
        return float(v)
    try:
        t = dt.datetime.fromisoformat(str(v).strip().replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return (t if t.tzinfo else t.astimezone()).timestamp()


USAGE_FRESH_S = 4 * 3600  # the round asks for a new usage point when the last is older than this


def usage_facts(state, now):
    """{"stop", "last" (percent or None), "at" (epoch or None), "over", "old"} from state.usage: the last point
    against the stop the state records, else the profile's limits.usage_stop."""
    u = state.get("usage") if isinstance(state.get("usage"), dict) else {}
    stop = _num(u.get("stop"))
    if stop is None:
        stop = _num(prof().get("limits.usage_stop", 80))
    pts = []
    for p in u.get("points") or []:
        at, w = (_when(p.get("at")), _num(p.get("weekly"))) if isinstance(p, dict) else (None, None)
        if at is not None and w is not None:
            pts.append((at, w))
    at, last = pts[-1] if pts else (None, None)
    return {"stop": stop, "last": last, "at": at, "over": bool(last is not None and stop is not None and last >= stop),
            "old": bool(at is None or now - at > USAGE_FRESH_S)}


def usage_text(u, now):
    stop = _num(u.get("stop"))
    stop = "the stop is not a number" if stop is None else f"the stop is {stop:g}%"
    if _num(u.get("last")) is None:
        return f"no usage point recorded; {stop}"
    return f"{u['last']:g}% at {hhmm(u['at'], now)} ({ago(now - u['at'])} ago); {stop}"


def open_decisions(state):
    return [x for x in state.get("decisions") or [] if isinstance(x, dict) and x.get("status", "open") == "open"]


def user_blockers(state):
    """The blockers the user must clear: the owner names the user as a word, or there is no owner and the text
    says it waits on the user."""
    out = []
    for b in state.get("blockers") or []:
        if not isinstance(b, dict):
            continue
        owner = b.get("owner")
        if (re.search(r"(?<![\w-])user(?![\w-])", str(owner), re.I) if owner else
                re.search(r"(?<![\w-])the user(?![\w-])", str(b.get("what") or ""), re.I)):
            out.append(b)
    return out


def unfiled_reports(state, reports):
    """The crew's failure reports (R<seq>) that no state.failures entry names in its `from`."""
    filed = set()
    for f in state.get("failures") or []:
        fr = f.get("from") if isinstance(f, dict) else None
        filed.update(str(x) for x in (fr if isinstance(fr, list) else [fr] if fr else []))
    return [r for r in reports if f"R{r['seq']}" not in filed]


def open_failures(state):
    return [f for f in state.get("failures") or [] if isinstance(f, dict) and f.get("status", "open") in ("open", "planned")]


def new_handins(d):
    """(the hand-in files not yet marked seen, every file's stamp): a file is new until a round with --by lists it,
    and new again when a later handin rewrites it."""
    try:
        seen = json.loads((d / SEEN_FILE).read_text(encoding="utf-8")).get("seen", {})
    except (OSError, ValueError, AttributeError):
        seen = {}
    seen = seen if isinstance(seen, dict) else {}
    new, stamps = [], {}
    folder = d / "handins"
    for f in sorted(folder.glob("*.md")) if folder.is_dir() else []:
        if "." in f.stem:  # <id>.<n>.md is an earlier hand-in kept beside the live <id>.md: not a new one
            continue
        try:
            stamp = round(f.stat().st_mtime, 3)
            with open(f, encoding="utf-8", errors="replace") as fh:
                head = fh.readline().strip().lstrip("# ").strip()
        except OSError:
            continue
        stamps[f.name] = stamp
        if seen.get(f.name) != stamp:
            new.append({"file": f.name, "path": f.as_posix(), "at": stamp, "head": head})
    return new, stamps


def journal_standing(d, state, now):
    """(journal.py's facts, None), or (None, why) when the journal cannot be read: never an exception."""
    try:
        import journal
        return journal.facts(d, state, now), None
    except Exception as e:  # the journal never breaks a round or a hand-off
        return None, f"the shift journal could not be read ({type(e).__name__}: {e})"


def round_facts(d, state, missing, now):
    """What needs the manager, most pressing first, as {"needs": [{"kind", "act", "text"}], "notes", "crew",
    "seats", "first", "handins"}. `act` False marks a line that is there to be known, not acted on (a counted run or
    a freeze going as it should)."""
    c = crew(d, now)
    needs, notes = [], ([missing] if missing else [])
    cmd, board = tool(), tool("board.py")

    def need(kind, text, act=True):
        needs.append({"kind": kind, "act": act, "text": text})

    # (a) usage
    u = usage_facts(state, now)
    if u["over"]:
        need("usage", f"usage {u['last']:g}% is at or past the stop at {u['stop']:g}%: start no new work, and ask the "
                      "user whether to go on")
    if u["old"] and not missing:
        last = f"the last is {u['last']:g}% at {hhmm(u['at'], now)}" if u["last"] is not None else "none is recorded"
        need("usage", f"no usage point in the last {USAGE_FRESH_S // 3600} hours ({last}): read the plan's weekly usage "
                      f"and record it, `{board} usage <percent>`")
    # (b) what waits on the user
    for x in open_decisions(state):
        before = f" (needed before {x['needed_before']})" if x.get("needed_before") else ""
        need("decision", f"{x.get('id', '?')} waits on the user{before}: {str(x.get('question', ''))[:160]}: ask the user, "
                         "in the open, with the options")
    for b in user_blockers(state):
        need("blocker", f"a blocker waits on the user: {str(b.get('what', ''))[:160]}: ask the user")
    # (c) a counted run or a freeze
    rq = rq_facts(d, now)
    for s in sweeps_of(rq, now):
        if s["dead"]:
            need("counted", f"the counted run {s['id']} looks dead (its hold on {res_name()} is past its limit, since "
                            f"{hhmm(s['since'], now)}): check the session that started it, then free the seat with "
                            f"`{tool('rq.py')} force-release`")
        else:
            need("counted", f"the counted run {s['id']} is in the queue of {res_name()}: change nothing in the main "
                            "checkout until it ends and its records are committed", act=False)
    for bid in unmarked_counted(rq):
        need("counted", f"{bid} holds or waits for the whole of {res_name()} under a plain id: if it is a counted run, "
                        f"freeze the main checkout (`{cmd} freeze on`) until it ends")
    fz = c["freeze"]
    if fz["on"] and fz["stale"]:
        need("freeze", f"the freeze {freeze_text(fz, now)}: check the run it covers; when its records are committed, "
                       f"`{cmd} freeze off`")
    elif fz["on"]:
        need("freeze", f"a freeze is in force {freeze_text(fz, now)}: change nothing in the main checkout; lift it when "
                       f"the run's records are committed (`{cmd} freeze off`)", act=False)
    # (d) failure reports not filed
    for r in unfiled_reports(state, c["reports"]) if not missing else []:
        where = " ".join(str(r[k]) for k in ("lane", "verdict") if r.get(k))
        need("report", f"R{r['seq']} from {r['id']} is not filed ({(where + ': ') if where else ''}"
                       f"{str(r.get('what', ''))[:120]}): file it, `{board} fail --from R{r['seq']} --what \"...\"`")
    if missing and c["reports"]:
        notes.append(f"{len(c['reports'])} failure report(s) in the time clock could not be checked against the state's failures")
    # (e) new hand-ins
    new, stamps = new_handins(d)
    for h in new:
        need("handin", f"a new hand-in, {h['file']} ({h['head'] or 'no heading'}; written {hhmm(h['at'], now)}): read it "
                       f"({h['path']}), then merge its commits or send it back")
    # (f) the crew
    for b in c["badges"]:
        if b["role"] in TOP:
            continue
        who = f"{b['id']} {b['name']} ({title_text(b)})"
        sess = f"session {b['session']}" if b.get("session") else "no session recorded"
        if b["status"] in ("STALE", "OVERDUE"):
            need("crew", f"{who} is {b.get('status_text') or b['status']}, last heard {hhmm(b['heard'], now)} ({sess}): "
                         "look at its session, then message it or clock it out as lost")
        if b["kind"] == "SESSION" and not b.get("session") and b["status"] in ("HIRED", "UP", "STALE", "OVERDUE"):
            need("crew", f"{who} is a session badge with no session: start or re-badge a bench and record it, "
                         f"`{cmd} assign {b['id']} --session local_...`, or clock it out")
    # (g) the journal's plan
    jf, why = journal_standing(d, state, now)
    if why:
        notes.append(why)
    elif jf["state"] == "DUE":
        need("journal", f"the shift journal's plan is due (since {hhmm(jf['due'], now)}; {len(jf['unplanned'])} with no "
                        f"plan, {len(jf['pending'])} awaiting approval): `{tool('journal.py')} ready`, then ask the user "
                        "to approve it")
    elif jf["state"] == "READY":
        need("journal", f"the shift journal's plan waits for the user's approval ({len(jf['pending'])} entries"
                        f"{', ' + str(jf['file']) if jf.get('file') else ''}): ask the user, then record the words with "
                        f"`{tool('journal.py')} approve`")
    rows = []
    for b in headcount(c):
        eta = f"finish ~{hhmm(b['eta'], now)}" if b.get("eta") else "no estimate"
        rows.append({"id": b["id"], "name": b["name"], "title": title_of(b), "role": b["role"], "kind": b["kind"],
                     "status": b["status"], "pct": b["pct"], "eta": b.get("eta"), "heard": b.get("heard"),
                     "session": b.get("session"),
                     "text": f"{b['id']} {b['name']} {title_text(b)} {b['kind'].lower()}: "
                             f"{b.get('status_text') or b['status']} {b['pct']}% {eta}; heard {hhmm(b['heard'], now)}"
                             + (f"; {res_name()}: {b['vm']}" if b.get("vm") else "")
                             + f"; {b.get('session') or 'no session'}"})
    seats = []
    if has_resource():
        held = {h["lane"]: h for h in rq["holds"]}
        for s in rq["seats"]:
            h = held.get(s)
            seats.append({"seat": s, "id": h["id"] if h else None, "overdue": bool(h and h["overdue"]),
                          "text": (f"seat {s}: {h['id']} since {hhmm(h['since'], now)} ({int((now - h['since']) // 60)} of "
                                   f"{int(h['max'] // 60)} min{', OVERDUE' if h['overdue'] else ''}): {h['job']}") if h
                                  else f"seat {s}: free"})
        if rq["queue"]:
            seats.append({"seat": None, "id": None, "overdue": False,
                          "text": f"waiting ({len(rq['queue'])}): " + ", ".join(e["id"] for e in rq["queue"])})
    acts = [n for n in needs if n["act"]]
    first = acts[0]["text"] if acts else "nothing needs you; end the turn"
    return {"at": now, "office": d.as_posix(), "manager": c.get("manager"), "needs": needs, "notes": notes,
            "crew": rows, "seats": seats, "usage": u, "freeze": fz, "first": first,
            "handins": [h["file"] for h in new], "_stamps": stamps, "_crew": c}


def cmd_round(a, d, now):
    """The manager's wake-up in one command: what needs the manager, most pressing first, then the crew and the
    seats, then the first thing to do. Without --by it writes nothing; with --by it also posts the manager's
    heartbeat and marks the listed hand-ins seen."""
    state, missing = safe_state()
    mgr = None
    if a.by:  # checked before anything is printed, so a wrong line writes and prints nothing
        mgr = manager_of(d, load_key(d), read_roster(d), a.by, crew(d, now))
    r = round_facts(d, state, missing, now)
    stamps, c = r.pop("_stamps"), r.pop("_crew")
    wrote = None
    if mgr:
        me = next(b for b in c["badges"] if b["id"] == mgr["id"])
        acts = sum(1 for n in r["needs"] if n["act"])
        with locked(d):
            append_event(d, {"at": now, "id": mgr["id"], "ev": "progress", "pct": me["pct"],
                             "note": f"round: {acts} to act on" if acts else "round: nothing to act on"})
            if r["handins"]:
                try:
                    seen = json.loads((d / SEEN_FILE).read_text(encoding="utf-8")).get("seen", {})
                except (OSError, ValueError, AttributeError):
                    seen = {}
                seen = {k: v for k, v in (seen if isinstance(seen, dict) else {}).items() if k in stamps}
                seen.update({name: stamps[name] for name in r["handins"]})
                (d / SEEN_FILE).write_text(json.dumps({"seen": seen, "at": now, "by": mgr["id"]}, indent=1) + "\n",
                                           encoding="utf-8", newline="\n")
        wrote = {"heartbeat": mgr["id"], "handins_seen": r["handins"]}
    r["by"], r["wrote"] = (mgr["id"] if mgr else None), wrote
    if a.json:
        print(json.dumps(r, indent=1, ensure_ascii=False))
        return 0
    print(f"Round at {local(now):%Y-%m-%d %H:%M} ({d.as_posix()}); manager {r['manager'] or 'none appointed'}")
    print(f"  needs you ({len(r['needs'])}):" if r["needs"] else "  needs you: nothing")
    for i, n in enumerate(r["needs"], 1):
        print(f"    {i}. [{n['kind']}] {n['text']}" + ("" if n["act"] else "  (to know, nothing to do)"))
    for n in r["notes"]:
        print(f"  note: {n}")
    print(f"  usage: {usage_text(r['usage'], now)}")
    print(f"  crew ({len(r['crew'])}):" if r["crew"] else "  crew: nobody hired or on the clock")
    for b in r["crew"]:
        print(f"    {b['text']}")
    if r["seats"]:
        print(f"  {res_name()}:")
        for s in r["seats"]:
            print(f"    {s['text']}")
    if wrote:
        print(f"  posted {mgr['id']}'s heartbeat" + (f"; marked seen: {', '.join(r['handins'])}" if r["handins"] else ""))
    else:
        print(f"  nothing written (no --by): `{tool()} round --by \"<your line>\"` posts your heartbeat and marks the "
              "hand-ins seen")
    print(f"first: {r['first']}")
    return 0


def free_path(p):
    """`p` when no file is there, else the first of <stem>-2, <stem>-3, ... that is free: nothing is overwritten."""
    if not p.exists():
        return p
    n = 2
    while p.with_name(f"{p.stem}-{n}{p.suffix}").exists():
        n += 1
    return p.with_name(f"{p.stem}-{n}{p.suffix}")


def cmd_handoff(a, d, now):
    """Write the next manager's hand-off brief as Markdown: what the office and the state know, and three sections
    the manager fills by hand. Never overwrites: a second call writes <name>-2."""
    state, missing = safe_state()
    key = load_key(d)
    c = crew(d, now)
    mgr = manager_of(d, key, read_roster(d), a.by, c)
    slots = (state.get("rota") or {}).get("slots") if isinstance(state.get("rota"), dict) else None
    slot = mgr.get("slot") or slot_at(slots, now)[0]
    if a.out:
        out = Path(a.out).expanduser()
        out = out if out.is_absolute() else Path.cwd() / out
        if not out.parent.is_dir():
            raise Refused(f"--out {a.out}: its folder does not exist")
    else:
        out = d / "briefs" / f"handoff-{token(slot, 12).lower()}-{local(now):%Y%m%d}.md"
    fill = lambda what: [f"_Fill by hand: {what}_", "", "- "]
    L = [f"# Hand-off brief: {slot} slot, {local(now):%Y-%m-%d %H:%M}",
         "",
         f"Written by {mgr['id']} {mgr['name']} with `office.py handoff` for the next manager. The office and the state "
         "filled what they know; the three sections at the end are the manager's to write.",
         ""]
    if missing:
        L += [f"**Missing:** {missing}", ""]
    L += ["## Now", ""]
    nw = state.get("now") if isinstance(state.get("now"), dict) else {}
    shown = [(k, str(nw.get(k) or "").strip()) for k in ("headline", "position", "tree", "plan_file")]
    L += [f"- {k.replace('_', ' ')}: {v}" for k, v in shown if v] or ["- (the state has no `now`)"]
    sh = state.get("shift") if isinstance(state.get("shift"), dict) else {}
    L += ["", f"## Shift {sh.get('id', 'none')} (crew_max {sh.get('crew_max', 'not set')})", ""]
    blocks = [b for b in sh.get("blocks") or [] if isinstance(b, dict)]
    for b in blocks:
        L.append(" ".join(str(x) for x in ("-", f"[{b.get('status') or 'pending'}]", b.get("time"),
                                           b.get("title") or "(no title)") if x)
                 + (f" (checkpoint {b['checkpoint']})" if b.get("checkpoint") else "")
                 + (f"; done when: {b['done_when']}" if b.get("done_when") else ""))
    if not blocks:
        L.append("- (the shift has no blocks)")
    on = [b for b in c["badges"] if b["on"]]
    L += ["", f"## On the clock ({len(on)})", ""]
    for b in on:
        eta = hhmm(b["eta"], now) if b.get("eta") and b["role"] != "FOUNDER" else "none"
        L.append(f"- {b['id']} {b['name']}, {title_text(b)}, {b['kind'].lower()}, session {b.get('session') or 'not recorded'}: "
                 f"{b.get('job') or '(no job text)'}; {b['pct']}%, finish ~{eta}; {b.get('status_text') or b['status']}")
    if not on:
        L.append("- nobody")
    hired = [b for b in c["badges"] if b["status"] == "HIRED" and b["role"] not in TOP]
    if hired:
        L.append("- hired, not clocked in: " + ", ".join(f"{b['id']} {b['name']} ({title_text(b)})" for b in hired))
    L += ["", "Benches: ", "", "_Fill by hand: each bench session, its title as it reads now, and whether it is cleared._"]
    fails = open_failures(state)
    L += ["", f"## Open failures ({len(fails)})", ""]
    L += [f"- {f.get('id', '?')} {f.get('status', 'open')}, owner {f.get('owner') or 'none'}: {str(f.get('what', ''))[:200]}"
          for f in fails] or ["- none" if not missing else "- not read (no state)"]
    unfiled = unfiled_reports(state, c["reports"]) if not missing else []
    if unfiled:
        L.append("- reports not filed yet: " + ", ".join(f"R{r['seq']}" for r in unfiled))
    decs = open_decisions(state)
    L += ["", f"## Open decisions ({len(decs)})", ""]
    L += [f"- {x.get('id', '?')}" + (f" (needed before {x['needed_before']})" if x.get("needed_before") else "")
          + f": {str(x.get('question', ''))[:200]}" for x in decs] or ["- none" if not missing else "- not read (no state)"]
    L += ["", "## Freeze and counted runs", ""]
    fz = c["freeze"]
    frozen = [f"- FREEZE {freeze_text(fz, now)}"] if fz["on"] else []
    frozen += [f"- counted run in the queue of {res_name()}: {t}" for t in c["vm"]["sweeps"]]
    frozen += [f"- {bid} holds or waits for the whole of {res_name()} under a plain id: a counted run?" for bid in c["vm"].get("unmarked") or []]
    L += frozen or ["- none in force: the main checkout is open"]
    if frozen:
        L.append("- the session that started a counted run keeps it as a background job: do not stop or archive that "
                 "session, and change nothing in the main checkout until the run ends")
    L += ["", "## Journal", ""]
    try:
        import journal
        line = journal.end_shift_line(d, state, now) or "the shift journal's plan is approved: nothing waits"
    except Exception as e:  # the journal never breaks a hand-off
        line = f"the shift journal could not be read ({type(e).__name__}: {e})"
    L.append(f"- {line}")
    L += ["", "## Usage", "", f"- {usage_text(usage_facts(state, now), now)}" if not missing else "- not read (no state)"]
    L += ["", "## The user's words this slot (quoted, with the time)", ""]
    L += fill("every instruction, approval or refusal the user gave this slot, word for word, each with its time; the "
              "next manager acts on these and on nothing remembered")
    L += ["", "## Promised to the crew", ""]
    L += fill("what you told an employee it would get or when (a review, a merge, a seat, an answer), by badge id, so "
              "the next manager keeps it")
    L += ["", "## Background jobs this session started", ""]
    L += fill("each job still running in this session (a queued run, a watcher), what ends it, and that this session "
              "must not be stopped or archived until it has")
    with locked(d):
        out = free_path(out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
        append_event(d, {"at": now, "id": mgr["id"], "ev": "handoff", "file": out.as_posix()})
    print(out.as_posix())
    print(f"hand-off brief for the {slot} slot written by {mgr['id']}; fill its three hand-written sections and the "
          "benches line before the next manager reads it")
    if missing:
        print(f"  note: {missing}")
    return 0


def timer_slots(state):
    """The rota's slots in clock order, each with its end (the next slot's start): state.json's, else the profile's."""
    rota = state.get("rota") if isinstance(state.get("rota"), dict) else {}
    slots = [s for s in (rota.get("slots") or default_slots())
             if isinstance(s, dict) and re.fullmatch(r"\d{2}:\d{2}", str(s.get("start", ""))) and s.get("id")]
    slots = sorted(slots or _SLOTS, key=lambda s: s["start"])
    return [{"id": str(s["id"]), "start": s["start"], "end": slots[(i + 1) % len(slots)]["start"]}
            for i, s in enumerate(slots)]


HANDOFF_LEAD_MIN = 40  # the hand-off timer fires this long before a slot's end


def timers_doc(state):
    skill = prof().skill("manager")
    out = [{"name": "round", "recurring": True, "every": str(prof().get("slots.round_every", "2h") or "2h"),
            "prompt": f"/{skill} status, then the round"}]
    for s in timer_slots(state):
        h, m = map(int, s["end"].split(":"))
        t = (h * 60 + m - HANDOFF_LEAD_MIN) % (24 * 60)
        out.append({"name": f"handoff-{s['id']}", "recurring": True, "at": f"{t // 60:02d}:{t % 60:02d}",
                    "prompt": f"/{skill} shift-change"})
        out.append({"name": f"start-{s['id']}", "recurring": True, "at": s["start"], "prompt": f"/{skill} start"})
    return {"timers": out}


def timers_problems(doc):
    """What is wrong with a manager-timers.json, one sentence per bad entry; [] when its shape is right."""
    if not isinstance(doc, dict) or not isinstance(doc.get("timers"), list):
        return ["the file is not {\"timers\": [...]}"]
    bad = []
    for i, t in enumerate(doc["timers"], 1):
        if not isinstance(t, dict):
            bad.append(f"entry {i}: not an object")
            continue
        why = []
        if not isinstance(t.get("name"), str) or not t["name"].strip():
            why.append("no name")
        if not isinstance(t.get("recurring"), bool):
            why.append("recurring is not true or false")
        every, at = t.get("every"), t.get("at")
        if every is None and at is None:
            why.append("neither every nor at")
        if every is not None:
            try:
                if parse_dur(every) <= 0:
                    raise Refused("zero")
            except Refused:
                why.append(f"every {every!r} is not a duration (2h, 90m)")
        if at is not None:
            m = re.fullmatch(r"(\d{2}):(\d{2})", str(at))
            if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
                why.append(f"at {at!r} is not a clock time (HH:MM)")
        if not isinstance(t.get("prompt"), str) or not t["prompt"].strip():
            why.append("no prompt")
        if why:
            bad.append(f"entry {i} ({t.get('name') if isinstance(t.get('name'), str) and t['name'].strip() else 'unnamed'}): "
                       + ", ".join(why))
    return bad


def cmd_timers(a, d, now):
    """timers init | show: the list of the manager's timers, as a file. The tool creates no timer itself."""
    f = d / TIMERS_FILE
    said = "this tool creates no timer: the manager creates them in its session: this file is the list"
    if a.action == "init":
        if not a.by:
            raise Refused("timers init is the manager's: give --by \"<the manager's line>\"")
        state, missing = safe_state()
        with locked(d):
            mgr = manager_of(d, load_key(d), read_roster(d), a.by, crew(d, now))
            if f.exists():
                print(f"{f.as_posix()} is already there: nothing written (`{tool()} timers show` prints and checks it; "
                      "edit it by hand, or remove it and run init again)")
                return 0
            doc = timers_doc(state)
            f.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
            append_event(d, {"at": now, "id": mgr["id"], "ev": "timers", "file": f.as_posix(), "n": len(doc["timers"])})
        rota = state.get("rota") if isinstance(state.get("rota"), dict) else {}
        print(f"wrote {f.as_posix()}: {len(doc['timers'])} timers from the rota's slots ("
              + ("the state's" if rota.get("slots") else "the profile's: there is no state file" if missing
                 else "the profile's: the state names none") + ")")
        for t in doc["timers"]:
            print(f"    {t['name']}: {'every ' + t['every'] if t.get('every') else 'at ' + t['at']}, "
                  f"{'recurring' if t['recurring'] else 'once'}: {t['prompt']}")
        print(said)
        return 0
    if not f.exists():
        print(f"no {TIMERS_FILE} in the office ({f.as_posix()}): `{tool()} timers init --by \"<the manager's line>\"` "
              "writes it")
        return 1
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"{f.as_posix()} cannot be read ({type(e).__name__}: {e})")
        return 1
    bad = timers_problems(doc)
    print(f"{f.as_posix()}:")
    for t in (doc.get("timers") if isinstance(doc, dict) and isinstance(doc.get("timers"), list) else []):
        if isinstance(t, dict):
            when = f"every {t['every']}" if t.get("every") is not None else f"at {t.get('at')}"
            print(f"    {t.get('name')}: {when}, {'recurring' if t.get('recurring') is True else 'once'}: {t.get('prompt')}")
    for b in bad:
        print(f"  BAD {b}")
    print("  each entry needs: name, recurring (true or false), every (a duration) or at (HH:MM), prompt" if bad else
          f"  {len(doc['timers'])} timers, the shape is right")
    print(said)
    return 1 if bad else 0


def cmd_verify(a, d, now):
    rec = verify_line(load_key(d), read_roster(d), a.line)
    print(f"genuine: {rec['id']} {rec['name']} {rec['role'].lower()} {rec['kind'].lower()}, shift {rec['shift']}, issued {hhmm(rec['issued'], now)}")
    return 0


def cmd_badge(a, d, now):
    rec = read_roster(d)["badges"].get(a.id)
    if not rec:
        raise Refused(f"no badge {a.id}")
    out = plate(d, rec)
    print(out.as_posix() if out else "no plate drawn: segno is not installed (`pip install segno`); the line below is the badge")
    print(rec["line"])
    return 0


# --- the selftest ---

def selftest():
    """Every case runs against a scratch project in a temp folder: its own profile, checkout, office and state. The
    FOUNDRY_ variables of the caller are set aside for the run and put back at its end."""
    import tempfile
    saved = {k: os.environ.pop(k) for k in [k for k in os.environ if k.startswith("FOUNDRY_")]}
    tmp = Path(tempfile.mkdtemp(prefix="foundry-office-selftest-")).resolve()
    try:
        return _selftest(tmp)
    finally:
        for k in [k for k in os.environ if k.startswith("FOUNDRY_")]:
            os.environ.pop(k)
        os.environ.update(saved)


def _selftest(tmp):
    import shutil
    # a GIT_DIR or GIT_WORK_TREE left by a hook would point the scratch git commands at the real repo
    nogit = {k: v for k, v in os.environ.items()
             if k not in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR", "GIT_PREFIX")}
    genv = {**nogit, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}

    def put(base, rel, text):
        (base / rel).parent.mkdir(parents=True, exist_ok=True)
        (base / rel).write_text(text, encoding="utf-8")

    # the scratch project: a profile with a shared resource of two seats, a gym with four lane files, a hook, and
    # a hand-in check whose exit code the cases set through check.rc
    proj = tmp / "proj"
    put(tmp, "check.py", "import sys\nfrom pathlib import Path\nrc = Path(__file__).with_name('check.rc')\n"
                         "print('the check ran')\nsys.exit(int(rc.read_text()) if rc.exists() else 0)\n")
    check_cmd = f'"{Path(sys.executable).as_posix()}" "{(tmp / "check.py").as_posix()}"'
    prof_head = 'project = "Testbed"\nbadge_prefix = "tb1"\n'
    measure = ("[measure]\nselftest = \"python gym/run.py selftest\"\ndev = \"tools/dev-run <lane>\"\n"
               "vendored_paths = [\"gym/gym_kit.py\", \"gym/kit*.py\"]\ngrader_no_read = [\"src/\"]\n"
               f"handin_check = '{check_cmd}'\nhandin_check_paths = [\"src/app/core/**\"]\n")
    resource = "[resource]\nname = \"the rig\"\nseats = [\"main\", \"side\"]\n"
    put(proj, ".foundry/foundry.toml", prof_head + resource + measure + "[crews.other]\nlessons = \"other-carry.jsonl\"\n")
    put(tmp, "no-resource.toml", prof_head + measure)                 # the same project with no shared resource
    put(tmp, "bare.toml", prof_head + resource)                       # ... and with no hand-in check, no vendored paths
    put(tmp, "no-paths.toml", prof_head + resource + f"[measure]\nhandin_check = '{check_cmd}'\n")
    put(proj, "scripts/foundry/keep.txt", "the tools folder\n")
    put(proj, "src/app/core/lib.py", "A = 1\n")
    put(proj, "docs/readme.md", "x\n")
    put(proj, "gym/lanes/g1_boot.py", "def selftest():\n    return 0\n")
    put(proj, "gym/lanes/g10_other.py", "def selftest():\n    return 0\n")
    put(proj, "gym/lanes/g18_hardening.py", "def selftest():\n    return 0\n")
    put(proj, "gym/lanes/g24_settings.py", "def selftest():\n    return 0\n\n\nif __name__ == \"__main__\":\n    raise SystemExit(selftest())\n")
    put(proj, "gym/prereg/G8.json", "{}\n")
    put(proj, "gym/gym_kit.py", "KIT = 1\n")
    put(proj, "gym/kit2.py", "KIT = 2\n")
    put(proj, ".claude/hooks/no_python_stdin.py", "# a hook\n")
    put(proj, ".claude/skills/foundry-employee/SKILL.md", "# a skill\n")
    put(proj, "docs/decisions/0003-first.md", "x\n")
    put(proj, "docs/reviews/keep.md", "x\n")
    put(proj, "docs/research/keep.md", "x\n")
    for args in (("init", "-q", "-b", "main"), ("add", "-A"), ("commit", "-q", "-m", "the scratch project")):
        r = subprocess.run(["git", *args], cwd=proj, capture_output=True, text=True, env=genv, timeout=60)
        assert r.returncode == 0, (args, r.stdout, r.stderr)
    os.environ.update({"FOUNDRY_ROOT": str(proj), "FOUNDRY_MAIN": str(proj), "FOUNDRY_PATHS_OFFICE": str(tmp / "office"),
                       "FOUNDRY_PATHS_STATE": str(tmp / "state.json")})
    nogit.update({k: v for k, v in os.environ.items() if k.startswith("FOUNDRY_")})
    genv.update(nogit)
    ROOT, PRE, RES = prof().root, badge_prefix(), res_name()
    DEFAULT_SLOTS = default_slots()
    STALE_S, MGR_STALE_S, OVERDUE_S = limit_s("stale_min"), limit_s("manager_stale_min"), limit_s("overdue_min")
    state = {"shift": {"id": "test-shift", "crew_max": 2}, "rota": {"slots": DEFAULT_SLOTS}}
    (tmp / "state.json").write_text(json.dumps(state), encoding="utf-8")
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    t0 = 1_800_000_000.0
    ok, bad = [], []

    def run(*args, at=0.0, **more):
        r = subprocess.run([sys.executable, __file__, *args], capture_output=True, text=True, encoding="utf-8",
                           env={**env, "FOUNDRY_NOW": str(t0 + at), **more}, timeout=60, cwd=tmp)
        return r.returncode, r.stdout + r.stderr

    expect_profile = (ROOT == proj and PRE == "TB1" and office_dir() == tmp / "office" and state_file() == tmp / "state.json"
                      and has_resource() and crew_name() == "testbed" and lessons() == {"other": "other-carry.jsonl"})
    def expect(what, cond, detail=""):
        (ok if cond else bad).append(what + ("" if cond else f": {detail.strip()[:300]}"))

    expect("the selftest runs on its scratch profile: the checkout, the badge prefix, the office, the state, the crews",
           expect_profile, f"{ROOT} {PRE} {office_dir()} {state_file()} {crew_name()} {lessons()}")
    os.environ.update({"FOUNDRY_CREW": "Home Crew", "FOUNDRY_LESSONS": json.dumps({"far": ["a.jsonl", "b.jsonl"]})})
    expect("FOUNDRY_CREW and FOUNDRY_LESSONS override the profile's crew and crews",
           crew_name() == "home-crew" and lessons() == {"far": ["a.jsonl", "b.jsonl"]}, f"{crew_name()} {lessons()}")
    os.environ.pop("FOUNDRY_CREW")
    os.environ.pop("FOUNDRY_LESSONS")

    def badge_of(out):
        return next(l[len("badge: "):] for l in out.splitlines() if l.startswith("badge: "))

    rc, out = run("appoint", "--name", "mgr-a")
    mgr = badge_of(out)
    expect("appoint mints a manager", rc == 0 and "MGR-1" in mgr, out)
    rc, out = run("clock-in", "--badge", mgr, at=60)
    expect("the manager clocks in", rc == 0, out)
    rc, out = run("verify", mgr, at=61)
    expect("a genuine line verifies", rc == 0 and "genuine" in out, out)
    tampered = mgr.replace("ROLE:MANAGER", "ROLE:BUILDER")
    rc, out = run("verify", tampered, at=62)
    expect("a tampered line fails", rc != 0 and "signature" in out, out)
    rc, out = run("appoint", "--name", "mgr-b", at=120)
    expect("a second manager is refused while the first is fresh", rc != 0 and "one manager" in out, out)

    rc, out = run("hire", "--by", tampered, "--name", "b1", "--role", "builder", "--kind", "session", "--job", "x", "--eta", "60m", at=130)
    expect("hire without the manager's genuine line is refused", rc != 0, out)
    rc, out = run("hire", "--by", mgr, "--name", "builder-1", "--role", "builder", "--kind", "session",
                  "--job", "build the thing", "--eta", "60m", "--lane", "G99", "--seat", "bench-a", at=140)
    b1 = badge_of(out)
    expect("the manager hires a builder", rc == 0 and "EMP-01" in b1 and "--- brief" in out, out)
    expect("a builder's brief has no grader waiting-on line", "--waiting-on <its badge or queue id>` now" not in out, out)
    expect("the brief says the employee runs journal.py add only, never plan, carry, ready, approve or set",
           JOURNAL_LINE in out and "plan, carry, ready, approve and set are the manager's" in out, out)
    rc, out = run("hire", "--by", mgr, "--name", "grader-1", "--role", "grader", "--kind", "temp", "--job", "g", "--eta", "60m", "--lane", "G99", at=150)
    expect("a GRADER subagent is refused", rc != 0 and "independent" in out, out)
    rc, out = run("hire", "--by", mgr, "--name", "grader-1", "--role", "grader", "--kind", "session",
                  "--job", "grade G99", "--eta", "90m", "--lane", "G99", "--seat", "bench-a", at=155)
    expect("a second holder of one seat is refused", rc != 0 and "the seat bench-a is held" in out, out)
    rc, out = run("hire", "--by", mgr, "--name", "grader-1", "--role", "grader", "--kind", "session",
                  "--job", "grade G99", "--eta", "90m", "--lane", "G99", at=160)
    g1 = badge_of(out)
    expect("the manager hires a grader", rc == 0 and "EMP-02" in g1, out)
    expect("the GRADER brief says to post --waiting-on at once", "--waiting-on <its badge or queue id>` now, as soon "
           "as you wait" in out, out)
    rc, out = run("hire", "--by", mgr, "--name", "scout-1", "--role", "scout", "--kind", "temp", "--job", "s", "--eta", "10m", at=170)
    expect("hiring past crew_max is refused", rc != 0 and "crew_max" in out, out)
    n_badges = len(read_roster(Path(env["FOUNDRY_PATHS_OFFICE"]))["badges"])
    rc, out = run("hire", "--by", mgr, "--name", "scout-1", "--role", "scout", "--kind", "temp", "--job", "s", "--eta", "10m",
                  "--files", "scripts/foundry/new.py, src/no-such-x/**", at=171)
    expect("hire refuses a --files pattern whose folder does not exist (exit 2, the pattern named) and mints nothing",
           rc == 2 and "src/no-such-x/**" in out and "--force-files" in out
           and len(read_roster(Path(env["FOUNDRY_PATHS_OFFICE"]))["badges"]) == n_badges, out)

    rc, out = run("assign", "EMP-01", "--session", "local_aaa", at=180)
    expect("the builder's session is recorded", rc == 0, out)
    rc, out = run("assign", "EMP-02", "--session", "local_aaa", at=181)
    expect("the builder's session cannot take the grader badge", rc != 0, out)
    rc, out = run("assign", "EMP-02", "--session", "local_bbb", at=182)
    expect("the grader gets its own session", rc == 0, out)

    rc, out = run("clock-in", "--badge", b1, at=200)
    expect("the builder clocks in", rc == 0, out)
    rc, out = run("clock-in", "--badge", b1, at=201)
    expect("a second clock-in is refused", rc != 0 and "already" in out, out)
    rc, out = run("clock-in", "--badge", g1, at=210)
    rc, out = run("progress", "--badge", g1, "--pct", "30", "--eta", "40m", "--note", "pinning seeds", at=600)
    expect("progress revises the finish", rc == 0 and "30%" in out, out)
    rc, out = run("fail", "--badge", g1, "--what", "G99 VOID on the harness", "--lane", "G99", "--verdict", "VOID", at=700)
    expect("a failure report is numbered", rc == 0 and re.search(r"reported R\d+", out), out)

    rc, out = run("progress", "--badge", b1, "--pct", "80", at=4000)

    # the injected clock: the builder (60 min estimate, in at +200 s, last heard at +4000 s) is OVERDUE once
    # 15 min past its finish; the grader, silent for 45 min after its last post, is STALE
    c = crew(Path(env["FOUNDRY_PATHS_OFFICE"]), t0 + 200 + 3600 + OVERDUE_S + 60)
    st = {b["id"]: b["status"] for b in c["badges"]}
    expect("OVERDUE past the estimate", st["EMP-01"] == "OVERDUE", str(st))
    c = crew(Path(env["FOUNDRY_PATHS_OFFICE"]), t0 + 200 + 30 * 60)
    st = {b["id"]: b["status"] for b in c["badges"]}
    expect("UP inside the estimate", st["EMP-01"] == "UP", str(st))
    c = crew(Path(env["FOUNDRY_PATHS_OFFICE"]), t0 + 700 + STALE_S + 60)
    st = {b["id"]: b["status"] for b in c["badges"]}
    expect("STALE after 45 min of silence", st["EMP-02"] == "STALE", str(st))
    expect("the finish follows the last progress post", next(b for b in c["badges"] if b["id"] == "EMP-02")["eta"] == t0 + 600 + 40 * 60)

    # the resource queue: a grader waiting in rq.queue.json with a fresh beat is not STALE, and a running job is a hold
    d = Path(env["FOUNDRY_PATHS_OFFICE"])
    late = 700 + STALE_S + 60
    (d / "rq.queue.json").write_text(json.dumps([
        {"id": "EMP-02", "job": "dry-grade", "prio": 5, "at": t0 + 900, "beat": t0 + late - 10},
        {"id": "MGR-1-sweep", "job": "counted sweep G1", "prio": 0, "at": t0 + 950, "beat": t0 + late - 5, "all": True},
        {"id": "EMP-09", "job": "left the queue", "prio": 5, "at": t0 + 100, "beat": t0 + 200}]), encoding="utf-8")
    (d / "rq.lock").mkdir()
    (d / "rq.lock" / "holder").write_text("EMP-01\n", encoding="utf-8")
    (d / "rq.lock" / "hold.json").write_text(json.dumps({"id": "EMP-01", "job": "unit tests", "since": t0 + late - 300,
                                                          "max": 1800, "lane": "main"}), encoding="utf-8")
    c = crew(d, t0 + late)
    by = {b["id"]: b for b in c["badges"]}
    expect("a badge waiting in the queue is not STALE", by["EMP-02"]["status"] == "UP" and "queued" in by["EMP-02"]["vm"], str(by["EMP-02"]))
    expect("a badge holding a seat says so", by["EMP-01"]["vm"] == "holds main", str(by["EMP-01"].get("vm")))
    expect("a waiter that stopped polling is left out", [e["id"] for e in c["vm"]["queue"]] == ["MGR-1-sweep", "EMP-02"], str(c["vm"]["queue"]))
    expect("a queued counted sweep is named", c["vm"]["sweeps"] == ["MGR-1-sweep"], str(c["vm"]["sweeps"]))
    expect("a waiting badge keeps its own last punch as heard", by["EMP-02"]["heard"] == t0 + 700, str(by["EMP-02"]["heard"]))
    dead = {"holds": [{"lane": "main", "id": "MGR-1-sweep", "since": t0, "overdue": True},
                      {"lane": "side", "id": "EMP-5-dry-sweep", "since": t0, "overdue": False}], "queue": []}
    sw = sweeps_of(dead, t0 + late)
    expect("a sweep hold past its limit reads DEAD?, and only a badge's own sweep id counts",
           len(sw) == 1 and sw[0]["dead"] and "DEAD?" in sw[0]["text"], str(sw))
    rc, out = run("roster", at=late)
    expect("the roster shows holders, waiters and the sweep warning",
           rc == 0 and "seat main: EMP-01" in out and "waiting 1. MGR-1-sweep" in out and "COUNTED SWEEP" in out, out)
    expect("the roster asks for the manager's session", "session not recorded" in out, out)
    # the builder queued past its finish is not OVERDUE; holding a seat past it, it is
    over = 200 + 3600 + OVERDUE_S + 120
    (d / "rq.queue.json").write_text(json.dumps([
        {"id": "EMP-01", "job": "unit tests", "prio": 5, "at": t0 + over - 600, "beat": t0 + over - 5}]), encoding="utf-8")
    (d / "rq.lock" / "holder").write_text("EMP-09\n", encoding="utf-8")
    (d / "rq.lock" / "hold.json").write_text(json.dumps({"id": "EMP-09", "job": "x", "since": t0 + over - 60,
                                                          "max": 1800, "lane": "main"}), encoding="utf-8")
    by = {b["id"]: b for b in crew(d, t0 + over)["badges"]}
    expect("a badge whose job waits in the queue past its finish is not OVERDUE", by["EMP-01"]["status"] == "UP", str(by["EMP-01"]))
    # past its finish while its own job holds a seat, it is OVERDUE and says the job is running
    (d / "rq.queue.json").write_text("[]", encoding="utf-8")
    (d / "rq.lock" / "hold.json").write_text(json.dumps({"id": "EMP-01", "job": "unit tests", "since": t0 + over - 60,
                                                          "max": 1800, "lane": "main"}), encoding="utf-8")
    by = {b["id"]: b for b in crew(d, t0 + over)["badges"]}
    rc, out = run("roster", at=over)
    expect("OVERDUE while its own job holds a seat reads 'OVERDUE (<resource>: holds main, N of M min)' in crew and the roster",
           by["EMP-01"]["status"] == "OVERDUE" and by["EMP-01"]["status_text"] == f"OVERDUE ({RES}: holds main, 1 of 30 min)"
           and f"EMP-01 builder-1 builder session local_aaa: OVERDUE ({RES}: holds main, 1 of 30 min)" in out,
           str(by["EMP-01"].get("status_text")) + out)
    expect("OVERDUE with no hold keeps the plain word", next(b for b in crew(d, t0 + over)["badges"] if b["id"] == "EMP-02")
           .get("status_text") == next(b for b in crew(d, t0 + over)["badges"] if b["id"] == "EMP-02")["status"])
    (d / "rq.lock" / "hold.json").write_text(json.dumps({"id": "EMP-09", "job": "x", "since": t0 + over - 60,
                                                          "max": 1800, "lane": "main"}), encoding="utf-8")
    # the grader waits on EMP-01's job (--waiting-on), so while that job is queued it is neither STALE
    # nor OVERDUE; its last post names the wait, and the roster shows it
    rc, out = run("progress", "--badge", g1, "--pct", "40", "--eta", "10m", "--waiting-on", "EMP-01", at=over - 60)
    expect("progress takes --waiting-on", rc == 0 and "waits on EMP-01" in out, out)
    rc, out = run("progress", "--badge", g1, "--pct", "40", "--waiting-on", "EMP 01; rm", at=over - 59)
    expect("--waiting-on takes one id only", rc != 0, out)
    (d / "rq.queue.json").write_text(json.dumps([
        {"id": "EMP-01", "job": "unit tests", "prio": 5, "at": t0 + over - 600, "beat": t0 + over + STALE_S - 5}]), encoding="utf-8")
    by = {b["id"]: b for b in crew(d, t0 + over + STALE_S)["badges"]}
    expect("a badge waiting on a queued job is neither STALE nor OVERDUE",
           by["EMP-02"]["status"] == "UP" and "waits on EMP-01" in (by["EMP-02"]["vm"] or ""), str(by["EMP-02"]))
    (d / "rq.queue.json").write_text(json.dumps([
        {"id": "MGR-1-counted-G1", "job": "counted G1", "prio": 0, "at": t0 + over, "beat": t0 + over + STALE_S - 5, "all": True}]),
        encoding="utf-8")
    c = crew(d, t0 + over + STALE_S)
    expect("a single counted run (<badge>-counted-<lane>) freezes like a sweep", c["vm"]["sweeps"] == ["MGR-1-counted-G1"],
           str(c["vm"]["sweeps"]))
    rc, out = run("progress", "--badge", g1, "--pct", "40", "--eta", "10m", "--waiting-on", "MGR-1", at=over + STALE_S - 60)
    by = {b["id"]: b for b in crew(d, t0 + over + STALE_S)["badges"]}
    expect("--waiting-on a badge id covers its suffixed queue ids (MGR-1 -> MGR-1-counted-G1)",
           "waits on MGR-1" in (by["EMP-02"]["vm"] or ""), str(by["EMP-02"]))
    rc, out = run("progress", "--badge", g1, "--pct", "40", at=over + STALE_S - 59)  # the wait ends with a plain post
    by = {b["id"]: b for b in crew(d, t0 + over + 3 * STALE_S)["badges"]}
    expect("after a plain post the old wait no longer covers the badge", by["EMP-02"]["status"] == "STALE", str(by["EMP-02"]))
    # ids match case-insensitively; a prio-0 or whole-resource job under a plain id is flagged
    expect("a counted id matches in any case", bool(SWEEP_ID.fullmatch("mgr-1-counted-g23")) and not SWEEP_ID.fullmatch("EMP-5-dry-sweep"))
    um = unmarked_counted({"holds": [{"id": "MGR-3", "all": True}, {"id": "MGR-1-counted-G1", "all": True}],
                           "queue": [{"id": "EMP-3", "prio": 0, "all": False}, {"id": "EMP-4", "prio": 5, "all": False}]})
    expect("a prio-0 or all-seats job under a plain id is flagged as a possible counted run", um == ["MGR-3", "EMP-3"], str(um))
    # an all-seats job whose text says dev is not flagged, but named; a prio-0 one is always flagged
    dv = {"holds": [{"id": "EMP-18", "all": True, "prio": 5, "job": "G7 then G20 (dev runs, not counted)"}],
          "queue": [{"id": "EMP-19", "all": True, "prio": 5, "job": "Dev G23 dry grade"},
                    {"id": "EMP-7", "all": True, "prio": 5, "job": "tools/dev-run G18"},
                    {"id": "EMP-8", "all": True, "prio": 0, "job": "dev run G1"},
                    {"id": "EMP-9", "all": True, "prio": 5, "job": "G18 counted"}]}
    expect("a dev all-seats job (by its words, or by the profile's measure.dev command) is not a possible counted run; "
           "a prio-0 one is, whatever its text",
           unmarked_counted(dv) == ["EMP-8", "EMP-9"] and dev_uncounted(dv) == ["EMP-18", "EMP-19", "EMP-7"],
           f"{unmarked_counted(dv)} {dev_uncounted(dv)}")
    # whole words ("devfs", "device", "developer" are not dev); prio "0" as a string is prio 0
    must_warn = ["devfs counted G18", "device lane G21 counted run", "developer ci", "G18 counted"]
    mw = {"holds": [], "queue": [{"id": f"EMP-{20 + i}", "all": True, "prio": 5, "job": t} for i, t in enumerate(must_warn)]
          + [{"id": "EMP-30", "all": True, "prio": 5, "job": "dev runs G7, G20 (not counted)"},
             {"id": "EMP-31", "all": True, "prio": "0", "job": "dev run G1"}]}
    expect("a dev-prefixed-word or no-dev text still warns; 'dev runs ... (not counted)' is still dev",
           unmarked_counted(mw) == [f"EMP-{20 + i}" for i in range(len(must_warn))] + ["EMP-31"]
           and dev_uncounted(mw) == ["EMP-30"], f"{unmarked_counted(mw)} {dev_uncounted(mw)}")
    # the job text never makes a job counted. A dev run's text that names the counted run it precedes
    # is dev; a counted run is known by its -counted id or prio 0, whatever its text
    h19 = {"holds": [{"id": "EMP-18", "all": True, "prio": 5, "lane": "main",
                      "job": "G25 dev run 15 at the merged tip (option a, before MGR-6's counted G25; EMP-19 dry-grades)"}],
           "queue": [{"id": "EMP-60", "all": True, "prio": 5, "job": "G18 dev run; grade the counted run after"},
                     {"id": "EMP-61", "all": True, "prio": 0, "job": "dev run G1 (not counted)"},
                     {"id": "MGR-9-counted-G25", "all": True, "prio": 0, "job": "dev", "at": 0}]}
    expect("a dev text naming a counted run is dev; prio 0 and a -counted id decide, not the text",
           unmarked_counted(h19) == ["EMP-61"] and dev_uncounted(h19) == ["EMP-18", "EMP-60"]
           and sweep_ids(h19, 0) == ["MGR-9-counted-G25"], f"{unmarked_counted(h19)} {dev_uncounted(h19)} {sweep_ids(h19, 0)}")
    expect("prio stored as the string '0' counts as prio 0", is_prio0({"prio": "0"}) and not is_prio0({"prio": None}))
    # "not counted", "uncounted" and "(dev" read as dev; the bare word "dev" in a
    # counted run's text ("on the dev rig", "dev-built tip", "after the dev fix") does not, so the backstop still warns
    nd = {"holds": [], "queue": [{"id": f"EMP-{40 + i}", "all": True, "prio": 5, "job": t} for i, t in enumerate(
        ["G23 dry grade (not counted)", "uncounted G7 calibration", "G20 (dev)", "G18 Not Counted",
         "tools/ci (dev, not counted)"])]
        + [{"id": f"EMP-{50 + i}", "all": True, "prio": 5, "job": t} for i, t in enumerate(
            ["G18 rerun after the dev fix", "G24 measuring run on the dev rig", "G25 sweep, dev-built tip",
             "G23 final on main 044076c5 (fix from dev branch)", "G18 2>/dev/null rerun", "G18 counted, after a dev fix",
             "G25 sweep (dev-built tip)", "G24 measuring (dev rig, seats main+side)"])]}
    expect("'not counted', 'uncounted' and '(dev' mark a dev run; the bare word dev ('dev rig', 'dev-built', 'dev fix') "
           "and a counted text do not",
           dev_uncounted(nd) == [f"EMP-{40 + i}" for i in range(5)] and unmarked_counted(nd) == [f"EMP-{50 + i}" for i in range(8)],
           f"{unmarked_counted(nd)} {dev_uncounted(nd)}")
    # a wait covers only a badge holding no seat, and ends when the waited-on hold passes its --max
    T = over + 3 * STALE_S + 100
    (d / "rq.seats").write_text("main\nside\n", encoding="utf-8")
    (d / "rq.lock" / "hold.json").write_text(json.dumps({"id": "EMP-09", "job": "x", "since": t0 + T - 100, "max": 1800,
                                                          "lane": "main"}), encoding="utf-8")
    (d / "rq.lock.side").mkdir()
    (d / "rq.lock.side" / "hold.json").write_text(json.dumps({"id": "EMP-01", "job": "y", "since": t0 + T - 100, "max": 7200,
                                                              "lane": "side"}), encoding="utf-8")
    run("progress", "--badge", g1, "--pct", "50", "--eta", "1m", "--waiting-on", "EMP-09", at=T)
    run("progress", "--badge", b1, "--pct", "90", "--waiting-on", "EMP-09", at=T)
    by = {b["id"]: b for b in crew(d, t0 + T + 1000)["badges"]}
    expect("a waiter past its finish is UP while the waited-on hold is inside its --max", by["EMP-02"]["status"] == "UP", str(by["EMP-02"]))
    expect("a badge holding a seat itself is OVERDUE despite --waiting-on", by["EMP-01"]["status"] == "OVERDUE", str(by["EMP-01"]))
    by = {b["id"]: b for b in crew(d, t0 + T + 1800)["badges"]}
    expect("the wait ends when the waited-on hold passes its --max", by["EMP-02"]["status"] == "OVERDUE", str(by["EMP-02"]))
    shutil.rmtree(d / "rq.lock.side")
    (d / "rq.seats").unlink()
    (d / "rq.queue.json").write_text("[]", encoding="utf-8")
    shutil.rmtree(d / "rq.lock")
    c = crew(d, t0 + late)
    expect("with no queue entry the silent grader is STALE again",
           next(b for b in c["badges"] if b["id"] == "EMP-02")["status"] == "STALE")

    # amend: the manager widens a job; the time clock keeps what it was
    rc, out = run("amend", "EMP-02", "--by", mgr, "--add-files", "gym/prereg/G8.json", "--job", "grade G99 and G8", at=4100)
    expect("the manager amends a badge", rc == 0 and "gym/prereg/G8.json" in out, out)
    rc, out = run("amend", "EMP-02", "--by", g1, "--job", "x", at=4101)
    expect("only the manager amends", rc != 0, out)
    rc, out = run("amend", "EMP-02", "--by", mgr, at=4102)
    expect("an empty amend is refused", rc != 0 and "at least one" in out, out)
    ev = [e for e in read_events(d) if e["ev"] == "amend"]
    expect("the amend is logged under the manager with the old values",
           len(ev) == 1 and ev[0]["id"] == "MGR-1" and ev[0]["for"] == "EMP-02" and ev[0]["was"]["job"] == "grade G99", str(ev))
    # amend replaces a wrong file list and moves the badge onto the resource queue
    # a pattern whose folder does not exist is refused (exit 2) and changes nothing, unless --force-files
    rc, out = run("amend", "EMP-02", "--by", mgr, "--set-files", "gym/prereg/G8.json, src/no-such-part/**", "--rq", at=4104)
    rec2 = read_roster(d)["badges"]["EMP-02"]
    expect("amend --set-files with a missing folder is refused with exit 2, naming the pattern, and changes nothing",
           rc == 2 and "src/no-such-part/**" in out and "src/no-such" not in rec2["files"], out)
    rc, out = run("amend", "EMP-02", "--by", mgr, "--set-files", "gym/prereg/G8.json, src/no-such-part/**", "--rq",
                  "--force-files", at=4104)
    rec2 = read_roster(d)["badges"]["EMP-02"]
    expect("amend --set-files replaces the list and --rq puts the badge on the queue",
           rc == 0 and rec2["files"].startswith("gym/prereg/G8.json, src/") and rec2["vmdir"] == RQ, out)
    expect("a forced pattern whose folder does not exist is still warned about", "src/no-such-part" in out and "! " in out, out)
    # amend ends with the brief as it is now, and `brief` reprints it for the manager only
    expect("amend reprints the badge line and the amended brief",
           "--- brief" in out and f"badge: {PRE} ID:EMP-02" in out and "Files you own: gym/prereg/G8.json, src/" in out, out)
    rc, out = run("brief", "EMP-02", "--by", mgr, at=4104)
    expect("office.py brief reprints the badge line and the full brief from the roster",
           rc == 0 and f"badge: {g1}" in out and "--- brief" in out and "Job: grade G99 and G8" in out
           and "Files you own: gym/prereg/G8.json" in out and "clock-in --badge" in out, out)
    expect("the brief is built from the profile: the project's name, the employee skill, the tool's own path, the "
           "resource's name, and no interpreter but the profile's",
           "You are a Testbed employee" in out and "invoke the foundry-employee skill" in out
           and (proj / "scripts" / "foundry" / "office.py").as_posix() in out and "The rig: through the queue only" in out
           and "FOUNDRY_SEAT" in out and prof().py + " " in out, out)
    expect("a grader's brief names what it owns and what it never opens, from the profile",
           "never open src/" in out and "you own only gym/prereg, gym/lanes, gym/run.py" in out, out)
    rc, out = run("brief", "EMP-02", "--by", g1, at=4104)
    expect("only the manager reprints a brief", rc != 0 and "not the current manager" in out, out)
    rc, out = run("amend", "EMP-02", "--by", mgr, "--add-files", "x", "--set-files", "y", at=4105)
    expect("--add-files and --set-files together are refused", rc != 0, out)
    expect("files_warnings: a new file in an existing folder is fine, a missing folder is not",
           files_warnings("scripts/foundry/new-file.py, scripts/foundry/*.py", ROOT) == []
           and len(files_warnings("src/nope-x/**", ROOT)) == 1)
    # --files that covers a file the profile's measure.vendored_paths names warns (hire, amend) and the brief names it
    expect("vendored_files reads the profile's paths and fills a glob in from the checkout",
           vendored_files(ROOT) == ["gym/gym_kit.py", "gym/kit2.py"], str(vendored_files(ROOT)))
    vw = vendored_warnings("gym/run.py, gym/gym_kit.py", ROOT)
    expect("a vendored file in --files warns, naming the file and the profile key",
           len(vw) == 1 and "gym/gym_kit.py" in vw[0] and "measure.vendored_paths" in vw[0] and "kit2" not in vw[0], str(vw))
    expect("a broad pattern covering both warns once with both; unrelated files and free text do not",
           vendored_hits("gym/**", ROOT) == ["gym/gym_kit.py", "gym/kit2.py"] and len(vendored_warnings("gym/**", ROOT)) == 1
           and vendored_warnings("gym/lanes/g18_hardening.py, scripts/foundry/office.py, the review file only", ROOT) == []
           and vendored_warnings("", ROOT) == [] and vendored_warnings("gym/x.py", tmp / "no-such-base") == [])
    os.environ["FOUNDRY_PROFILE"] = str(tmp / "bare.toml")
    expect("with no measure.vendored_paths in the profile nothing is vendored",
           vendored_files(ROOT) == [] and vendored_warnings("gym/**", ROOT) == [], str(vendored_files(ROOT)))
    os.environ.pop("FOUNDRY_PROFILE")
    rc, out = run("assign", "MGR-1", "--session", "local_mgr", at=4103)
    rc2, out2 = run("roster", at=4104)
    expect("a manager's session is recorded and shown", rc == 0 and "session local_mgr" in out2, out + out2)

    # the brief: the manager on the clock, the queue rule, and the state's known tooling bugs
    st2 = {**state, "shift": {"id": "test-shift", "crew_max": 9},
           "tooling_known": ["known bug 1: the queue exits 127 on an absolute path; use a relative path"]}
    (tmp / "state.json").write_text(json.dumps(st2), encoding="utf-8")
    rc, out = run("hire", "--by", mgr, "--name", "temp-1", "--role", "scout", "--kind", "temp", "--job", "read", "--eta", "30m",
                  "--rq", at=4200)
    expect("a --rq hire is refused for no other --rq badge and its brief names rq.py run --id",
           rc == 0 and re.search(r'rq\.py"? run --id TMP-', out) and (proj / "scripts" / "foundry" / "rq.py").as_posix() in out, out)
    t1 = badge_of(out)
    expect("a brief names the manager on the clock, the queue rule and known tooling bugs",
           rc == 0 and "manager on the clock" in out and "known bug 1" in out and "(rq.py run)" in out
           and "can neither replace the first's entry nor be freed by its release" in out
           and "session that started you." not in out.split("not the session that started you")[0], out)
    rc, out = run("hire", "--by", mgr, "--name", "temp-2", "--role", "scout", "--kind", "temp", "--job", "read", "--eta", "30m",
                  "--rq", at=4201)
    expect("two badges may both take --rq", rc == 0 and "hired TMP-" in out, out)
    rc, out = run("hire", "--by", mgr, "--name", "temp-3", "--role", "scout", "--kind", "temp", "--job", "read", "--eta", "30m",
                  "--rq", "--seat", "side", at=4202)
    expect("--rq with --seat is refused", rc == 3 and "give one" in out, out)
    rc, out = run("clock-in", "--badge", t1, at=4210)
    rc, out = run("end-shift", "--by", mgr, at=4300)
    c = crew(d, t0 + 4301)
    by = {b["id"]: b for b in c["badges"]}
    expect("end-shift keeps a working temp and clocks out one that never came in",
           rc == 0 and by["TMP-01"]["on"] and by["TMP-02"]["result"] == "lost", out)
    crew_file = d / "end-shift-crew.json"
    rc, out = run("end-shift", "--by", mgr, "--lose-temps", "--out", str(crew_file), at=4310)
    expect("end-shift --lose-temps clocks the working temp out",
           rc == 0 and not next(b for b in crew(d, t0 + 4311)["badges"] if b["id"] == "TMP-01")["on"], out)
    wrote = json.loads(crew_file.read_text(encoding="utf-8")) if crew_file.exists() else None
    expect("end-shift --out writes the crew list as JSON",
           isinstance(wrote, list) and any(x.startswith("TMP-01 ") for x in wrote), out)
    n_before = len(read_events(d))
    rc, out = run("end-shift", "--by", mgr, "--out", str(d / "no-such-dir" / "crew.json"), at=4320)
    expect("end-shift --out into a missing folder is refused before any event is written",
           rc != 0 and len(read_events(d)) == n_before and not (d / "no-such-dir").exists(), out)

    # the crew's own tools: me, status, progress --run, runs, the queued start, handin, the clock-out sha check
    n_ev = len(read_events(d))
    rc, out = run("me", "--badge", b1, at=4400)
    expect("me reprints the brief, the manager and the place in the queue without a punch",
           rc == 0 and "--- your brief" in out and "Job: build the thing" in out and "manager on the clock: MGR-1" in out
           and "your queued job: none" in out and len(read_events(d)) == n_ev, out)
    rc, out = run("me", "--badge", g1, at=4401)
    expect("me lists what the manager amended", rc == 0 and "amended" in out and "grade G99" in out, out)
    rc, out = run("status", at=4402)
    expect("status without a badge is the roster", rc == 0 and "Crew office" in out, out)
    rc, out = run("status", "--badge", b1, at=4403)
    expect("status with a badge is me", rc == 0 and "--- your brief" in out, out)
    rundir = tmp / "wt" / "out" / "gym" / "G99" / "run-1"
    rundir.mkdir(parents=True)
    rc, out = run("progress", "--badge", b1, "--pct", "85", "--run", str(rundir), at=4410)
    expect("progress --run records the folder's absolute path", rc == 0 and rundir.resolve().as_posix() in out, out)
    r = subprocess.run([sys.executable, __file__, "progress", "--badge", b1, "--pct", "85", "--run", "out/gym/G99/run-1"],
                       capture_output=True, text=True, encoding="utf-8", env={**env, "FOUNDRY_NOW": str(t0 + 4410.5)},
                       cwd=tmp / "wt", timeout=60)
    expect("progress --run takes a path relative to the caller's folder", r.returncode == 0 and rundir.resolve().as_posix() in r.stdout, r.stdout + r.stderr)
    rc, out = run("progress", "--badge", b1, "--pct", "85", "--run", str(tmp / "no-such-run"), at=4411)
    expect("progress --run refuses a folder that is not there", rc != 0 and "no such folder" in out, out)
    rc, out = run("runs", at=4412)
    expect("runs lists the posted folder once, with its badge",
           rc == 0 and "EMP-01" in out and out.count(rundir.resolve().as_posix()) == 1, out)
    rc, out = run("runs", "--id", "EMP-02", at=4412)
    expect("runs --id keeps to that badge", rc == 0 and "no run folder posted by EMP-02" in out, out)
    rc, out = run("roster", at=4413)
    expect("the roster shows a posted run folder", rc == 0 and "run: " + rundir.resolve().as_posix() in out, out)
    T2 = t0 + 4420
    rqx = {"seats": ["main", "side"],
           "holds": [{"lane": "main", "id": "EMP-09", "since": T2 - 600, "max": 3600},
                     {"lane": "side", "id": "EMP-09", "since": T2 - 600, "max": 3600}],
           "queue": [{"id": "EMP-03", "all": True, "max": 1800}, {"id": "EMP-01", "max": 900, "lane": None},
                     {"id": "EMP-02-dry", "max": 900, "lane": "side"}]}
    est = lambda i: rq_start_estimate(rqx, i, T2)
    expect("the start estimate adds the holds' limits and the waiters ahead",
           est("EMP-03") == (T2 + 3000, None) and est("EMP-01") == (T2 + 4800, None)
           and est("EMP-02") == (T2 + 5700, None) and est("EMP-07") == (None, None),  # EMP-01 took side on the tie
           str([est(i) for i in ("EMP-03", "EMP-01", "EMP-02")]))
    rqx["holds"][0]["max"] = 60
    expect("with a hold past its own --max the start is unknown, never 'next'",
           est("EMP-01")[0] is None and "past its own --max" in est("EMP-01")[1], str(est("EMP-01")))
    # the same through the office's files: rq.queue.json's max/lane/any, crew(), the roster's and me's lines
    (d / "rq.seats").write_text("main\nside\n", encoding="utf-8")
    for lk, hid in ((d / "rq.lock", "EMP-09"), (d / "rq.lock.side", "EMP-08")):
        lk.mkdir()
        (lk / "hold.json").write_text(json.dumps({"id": hid, "job": "x", "since": T2 - 600, "max": 3600,
                                                  "lane": "main" if lk.name == "rq.lock" else "side"}), encoding="utf-8")
    (d / "rq.queue.json").write_text(json.dumps([
        {"id": "EMP-07", "job": "a", "prio": 2, "at": T2 - 50, "beat": T2, "max": 1200, "any": True},
        {"id": "EMP-01", "job": "b", "prio": 5, "at": T2 - 40, "beat": T2, "max": 900}]), encoding="utf-8")
    me1 = next(b for b in crew(d, T2)["badges"] if b["id"] == "EMP-01")
    expect("a queue entry with no seat waits for the default seat; the any-seat waiter ahead takes the other on a tie, "
           "as the queue does",
           me1["vm_start"] == T2 + 3000 and me1["vm_start_why"] is None, str((me1["vm_start"], me1["vm_start_why"])))
    over_rq = {"seats": ["main", "side"], "holds": [{"lane": "side", "id": "EMP-08", "since": T2 - 9000, "max": 60}],
               "queue": [{"id": "EMP-01", "max": 900, "lane": "main"}, {"id": "EMP-02", "max": 900, "lane": "side"}]}
    any_rq = {**over_rq, "queue": [{"id": "EMP-01", "max": 900, "lane": None}, {"id": "EMP-02", "max": 900, "lane": None}]}
    expect("an any-seat waiter takes the free seat, not the one whose hold is overdue; the next one behind it is known too",
           rq_start_estimate(any_rq, "EMP-01", T2) == (T2, None) and rq_start_estimate(any_rq, "EMP-02", T2) == (T2 + 900, None),
           str([rq_start_estimate(any_rq, i, T2) for i in ("EMP-01", "EMP-02")]))
    expect("an overdue hold makes only the starts that need its seat unknown",
           rq_start_estimate(over_rq, "EMP-01", T2) == (T2, None) and rq_start_estimate(over_rq, "EMP-02", T2)[0] is None,
           str([rq_start_estimate(over_rq, i, T2) for i in ("EMP-01", "EMP-02")]))
    rc, out = run("roster", at=4420)
    rc2, out2 = run("me", "--badge", b1, at=4420)
    expect("the roster and me print the start as an estimate, not a bound",
           "queue start about" in out and "an estimate, not a bound" in out and "at the latest" not in out + out2
           and "your queued job: queued (place 2 of 2); start about" in out2, out + out2)
    expect("the roster names the resource and its seats, never a lane, for the queue",
           f"  {RES} (a running job is a hold" in out and "seat main: EMP-09" in out and "seat side: EMP-08" in out
           and "lane main" not in out and "lane side" not in out, out)
    (d / "rq.queue.json").write_text(json.dumps([
        {"id": "EMP-01", "job": "b", "prio": 5, "at": T2 - 40, "beat": T2 + 3600, "max": 900}]), encoding="utf-8")
    rc, out = run("roster", at=4420 + 3600)  # both holds are now past their --max
    expect("the roster says unknown, with no estimate wording, when a hold ahead is overdue",
           "queue start unknown: EMP-09's hold on main is past its own --max" in out and "past its own --max (an estimate" not in out, out)
    rc, out = run("me", "--badge", b1, "--json", at=4420)
    expect("me takes no --json", rc == 2, out)
    (d / "rq.queue.json").write_text(json.dumps([
        {"id": "MGR-1-counted-G1", "job": "counted", "prio": 0, "at": T2, "beat": T2, "all": True}]), encoding="utf-8")
    rc, out = run("me", "--badge", b1, at=4420)
    expect("me says FREEZE while a counted run is queued", rc == 0 and "FREEZE" in out, out)

    # no shared resource in the profile: the same office files are not read, no queue line is printed in the roster,
    # the brief or me, and --rq and --seat are refused with the key to set
    nr = {"FOUNDRY_PROFILE": str(tmp / "no-resource.toml")}
    rc, out = run("roster", at=4420, **nr)
    rc2, out2 = run("me", "--badge", b1, at=4420, **nr)
    expect("with no [resource] name the roster and me print no queue line, hold or freeze",
           rc == 0 and rc2 == 0 and all(x not in out + out2 for x in ("seat main", "waiting 1.", "COUNTED", "FREEZE:", "FREEZE by",
                                                                     "queued job", "counted run in the queue", "rq.py", "--waiting-on"))
           and "you see it as FREEZE in `" in out2,  # the brief's own sentence is the one place the word stays
           out + out2)
    os.environ.update(nr)
    c_nr = crew(d, T2)
    expect("with no [resource] name crew() reports no hold, waiter or sweep",
           not has_resource() and c_nr["vm"] == {"holds": [], "queue": [], "sweeps": [], "unmarked": [], "dev": []}
           and all(b["vm"] is None and b["vm_start"] is None for b in c_nr["badges"]), str(c_nr["vm"]))
    os.environ.pop("FOUNDRY_PROFILE")
    for flag in (("--rq",), ("--seat", "side")):
        n_badges = len(read_roster(d)["badges"])
        rc, out = run("hire", "--by", mgr, "--name", "nr-1", "--role", "scout", "--kind", "temp", "--job", "read",
                      "--eta", "30m", *flag, at=4421, **nr)
        expect(f"with no [resource] name hire {flag[0]} is refused, naming the key to set, and mints nothing",
               rc == 3 and "[resource] name" in out and ".foundry/foundry.toml" in out
               and len(read_roster(d)["badges"]) == n_badges, out)
    rc, out = run("amend", "EMP-01", "--by", mgr, "--rq", at=4422, **nr)
    expect("with no [resource] name amend --rq is refused the same way",
           rc == 3 and "[resource] name" in out and not read_roster(d)["badges"]["EMP-01"].get("vmdir") == RQ, out)
    rc, out = run("hire", "--by", mgr, "--name", "nr-2", "--role", "grader", "--kind", "session", "--job", "grade G77",
                  "--eta", "30m", "--lane", "G77", at=4423, **nr)
    expect("with no [resource] name a brief (a grader's too) has no queue, seat, waiting-on or counted-sweep line",
           rc == 0 and "--- brief" in out and all(x not in out for x in ("rq.py", "through the queue", "its queue", "Seat:",
                                                                          "place in the queue", "--waiting-on",
                                                                          "COUNTED SWEEP", "FOUNDRY_SEAT")), out)
    run("clock-out", "--by", mgr, "--id", parse_line(badge_of(out))[0]["ID"] if rc == 0 else "EMP-00", "--result", "lost", at=4424)

    (d / "rq.queue.json").write_text("[]", encoding="utf-8")
    shutil.rmtree(d / "rq.lock")
    shutil.rmtree(d / "rq.lock.side")
    (d / "rq.seats").unlink()
    expect("owned patterns: a folder, a glob, braces and a file cover their paths; free text and a bare word are set aside",
           owned_patterns("src/a/**, ./scripts/office.py; docs/x (new), the review file only, none, src/{b,c}/core") ==
           (["src/a/**", "scripts/office.py", "docs/x", "src/b/core", "src/c/core"], ["the review file only", "none"])
           and owns(["src/a/**", "gym/lanes"], "src/a/core/lib.py") and owns(["gym/lanes"], "gym/lanes/g1.py")
           and owns(["scripts/*.py"], "scripts/office.py") and not owns(["src/a/**"], "src/ab/x.py"),
           str(owned_patterns("src/a/**, ./scripts/office.py; docs/x (new), the review file only, none, src/{b,c}/core")))
    p2 = owned_patterns("src/{a,b}/{core,tests}, docs/x.md (new, see {a,b}), scripts, nope", ROOT)
    expect("owned patterns: two brace groups expand, a note with a brace is dropped, a bare word that exists is a path",
           p2 == (["src/a/core", "src/a/tests", "src/b/core", "src/b/tests", "docs/x.md", "scripts"], ["nope"])
           and owns(p2[0], "src/b/tests/t.py") and owns(p2[0], "scripts/office.py"), str(p2))
    gcw = lambda s: bool(GIT_CONFIG_WRITE.search(s))
    expect("the git-config pattern catches a write and passes a read",
           gcw('git config user.name "sweep-check-test"') and gcw("git -C $wt config --local user.email t@example.invalid")
           and gcw('git config user.name "$(git config --get user.name)-x"')
           and not gcw("git config --get user.name") and not gcw("git config user.name") and not gcw("git config --list")
           and not gcw("git config --local -l") and not gcw("git config --show-origin user.name")
           and gcw('["git", "config", "user.name", "x"]') and gcw("git config --unset user.name")
           and gcw("git config --local --unset-all user.email")
           and not gcw("git config user.name 2>/dev/null") and not gcw("name=$(git config user.name 2>/dev/null)"))
    # the project's own hand-in check, by the profile: no command, a command with no paths, a path that matches
    hc_top, hc_changed = tmp, ["src/app/core/lib.py", "docs/x.md"]
    os.environ["FOUNDRY_PROFILE"] = str(tmp / "bare.toml")
    expect("with no measure.handin_check the hand-in check is skipped and nothing is said",
           project_handin_check(hc_top, hc_changed) == (None, None, None), str(project_handin_check(hc_top, hc_changed)))
    os.environ["FOUNDRY_PROFILE"] = str(tmp / "no-paths.toml")
    hc = project_handin_check(hc_top, hc_changed)
    expect("a hand-in check with no measure.handin_check_paths is not run, and a warning names it",
           hc[0] is None and hc[2] == "not run" and "check.py" in (hc[1] or "") and "names no path" in (hc[1] or ""), str(hc))
    os.environ.pop("FOUNDRY_PROFILE")
    hc = project_handin_check(hc_top, ["docs/x.md"])
    expect("a hand-in check whose paths match no changed file is not run, and a warning names it",
           hc[0] is None and hc[2] == "not run" and "check.py" in (hc[1] or "") and "was not run" in (hc[1] or ""), str(hc))
    (tmp / "check.rc").write_text("0", encoding="utf-8")
    hc = project_handin_check(hc_top, hc_changed)
    expect("a hand-in check that exits 0 on a matching change passes with no problem and no warning", hc == (None, None, "passed"), str(hc))
    (tmp / "check.rc").write_text("7", encoding="utf-8")
    hc = project_handin_check(hc_top, hc_changed)
    expect("a hand-in check that exits non-zero is a problem that names the command, the file and its last output",
           hc[1] is None and hc[2] == "exit 7" and "exited 7" in (hc[0] or "") and "src/app/core/lib.py" in hc[0]
           and "the check ran" in hc[0], str(hc))
    (tmp / "check.rc").write_text("0", encoding="utf-8")
    # handin, against a scratch repo: main, then a branch in a linked worktree
    repo = tmp / "repo"
    wt = tmp / "repo-wt"
    henv = {k: v for k, v in env.items() if k in nogit or k.startswith("FOUNDRY_")}

    def g(*args, cwd=repo):
        r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, env=genv, timeout=60)
        assert r.returncode == 0, (args, r.stdout, r.stderr)
        return r.stdout.strip()

    repo.mkdir()
    g("init", "-q", "-b", "main")
    put(repo, "src/app/core/lib.py", "A = 1\n")
    put(repo, "docs/readme.md", "x\n")
    g("add", "-A")
    g("commit", "-q", "-m", "base")
    g("worktree", "add", "-q", str(wt), "-b", "claude/job", "main")
    rc, out = run("amend", "EMP-01", "--by", mgr, "--set-files", "src/app/**", at=4430)

    def handin(*args, at, cwd=wt):
        r = subprocess.run([sys.executable, __file__, "handin", "--badge", b1, *args], capture_output=True, text=True,
                           encoding="utf-8", env={**henv, "FOUNDRY_NOW": str(t0 + at)}, cwd=cwd, timeout=120)
        return r.returncode, r.stdout + r.stderr

    put(wt, "src/app/tests/t.py", "def test_t():\n    pass\n")
    g("add", "-A", cwd=wt)
    g("commit", "-q", "-m", "a test", cwd=wt)
    put(wt, "leftover.txt", "x\n")
    put(wt, "report.md", "what I did\n")
    rc, out = handin("--file", "report.md", at=4440)
    expect("handin refuses a dirty tree, and the report file itself is not the leftover",
           rc == 1 and "NOT READY" in out and "not clean (1 path(s), first: leftover.txt" in out, out)
    (wt / "leftover.txt").unlink()
    rc, out = handin("--file", "report.md", at=4441)
    hi = d / "handins" / "EMP-01.md"
    expect("handin passes a clean branch inside its files and writes the hand-in with the report",
           rc == 0 and "READY (0 problem" in out and hi.is_file() and "what I did" in hi.read_text(encoding="utf-8")
           and "claude/job" in hi.read_text(encoding="utf-8"), out)
    expect("a hand-in whose commits change no file under measure.handin_check_paths says the check was not run, as a "
           "warning that names it", "warning  the project's hand-in check" in out and "check.py" in out
           and "was not run" in out and "hand-in check" in hi.read_text(encoding="utf-8"), out)
    (wt / "report.md").unlink()
    rc, out = handin(at=4441.5)
    expect("a re-run without --file keeps the report an earlier run filed",
           rc == 0 and "earlier run filed is kept" in out and "what I did" in hi.read_text(encoding="utf-8"), out)
    by0 = next(b for b in crew(d, t0 + 4441.6)["badges"] if b["id"] == "EMP-01")
    expect("the employee's own handin counts as heard", by0["heard"] == t0 + 4441.5, str(by0["heard"]))
    r = subprocess.run([sys.executable, __file__, "handin", "--badge", b1, "--repo", str(wt), "--by", mgr],
                       capture_output=True, text=True, encoding="utf-8", env={**henv, "FOUNDRY_NOW": str(t0 + 4441.7)},
                       cwd=tmp, timeout=120)
    by0 = next(b for b in crew(d, t0 + 4441.8)["badges"] if b["id"] == "EMP-01")
    expect("a handin the manager runs (--repo, --by) is logged under the manager and is not the employee being heard",
           r.returncode == 0 and "run by MGR-1" in hi.read_text(encoding="utf-8") and by0["heard"] == t0 + 4441.5
           and any(e["ev"] == "handin" and e["id"] == "MGR-1" and e.get("for") == "EMP-01" for e in read_events(d)),
           r.stdout + r.stderr)
    expect("the report an employee filed outlives the manager's run", "what I did" in hi.read_text(encoding="utf-8"))
    r = subprocess.run([sys.executable, __file__, "handin", "--badge", b1, "--repo", str(wt), "--by", g1],
                       capture_output=True, text=True, encoding="utf-8", env={**henv, "FOUNDRY_NOW": str(t0 + 4441.75)},
                       cwd=tmp, timeout=120)
    expect("--by takes the manager's line only", r.returncode == 3 and "not the current manager" in r.stderr, r.stdout + r.stderr)
    # a report in a new folder is still not the leftover; an edited tracked report is one
    put(wt, "out-notes/new/r.md", "report\n")
    rc, out = handin("--file", "out-notes/new/r.md", at=4441.8)
    expect("an untracked report in a new folder is not a leftover", rc == 0 and "not clean" not in out, out)
    h1 = d / "handins" / "EMP-01.1.md"
    expect("a hand-in with another report keeps the earlier one as <id>.1.md; two hand-ins leave two files",
           h1.is_file() and "what I did" in h1.read_text(encoding="utf-8") and "report" in hi.read_text(encoding="utf-8")
           and "what I did" not in hi.read_text(encoding="utf-8") and "kept as" in out, out)
    rc, out = handin("--file", "out-notes/new/r.md", at=4441.805)
    expect("a re-run with the same report overwrites, keeps the first round's file, and makes no third",
           h1.is_file() and "what I did" in h1.read_text(encoding="utf-8") and "report" in hi.read_text(encoding="utf-8")
           and not (d / "handins" / "EMP-01.2.md").exists() and "kept as" not in out, out)
    put(wt, "out-notes/new/other.md", "x\n")
    rc, out = handin("--file", "out-notes/new/r.md", at=4441.81)
    expect("another untracked file beside it is named by its own path", rc == 1 and "first: out-notes/new/other.md" in out, out)
    shutil.rmtree(wt / "out-notes")
    put(wt, "src/app/tests/t.py", "def test_t():\n    return None\n")
    rc, out = handin("--file", "src/app/tests/t.py", at=4441.82)
    expect("an edited tracked file passed as the report is still a leftover", rc == 1 and "src/app/tests/t.py" in out, out)
    expect("an earlier NOT READY hand-in with another report is overwritten, not kept as <id>.2.md",
           not (d / "handins" / "EMP-01.2.md").exists() and "kept as" not in out and h1.is_file(), out)
    g("checkout", "-q", "--", "src/app/tests/t.py", cwd=wt)
    # the main checkout: other people's changed paths are a warning, this badge's own are the problem
    put(repo, "docs/someone-elses.md", "x\n")
    rc, out = handin("--commits", g("rev-parse", "--short", "claude/job"), at=4441.9, cwd=repo)
    expect("in the main checkout, changed paths outside the badge's files only warn",
           rc == 0 and "not yours to commit" in out and "not clean" not in out, out)
    put(repo, "src/app/core/wip.py", "\n")
    rc, out = handin("--commits", g("rev-parse", "--short", "claude/job"), at=4441.95, cwd=repo)
    expect("in the main checkout, an uncommitted path of the badge's own is a problem", rc == 1 and "src/app/core/wip.py" in out, out)
    (repo / "src/app/core/wip.py").unlink()
    (repo / "docs/someone-elses.md").unlink()
    put(wt, "src/app/core/lib.py", "A = 2\n")
    put(wt, "docs/readme.md", "y\n")
    g("add", "-A", cwd=wt)
    g("commit", "-q", "-m", "code, and a file outside", cwd=wt)
    (tmp / "check.rc").write_text("1", encoding="utf-8")
    rc, out = handin(at=4442)
    expect("handin names a file outside the badge's files, and runs the project's hand-in check after a change under "
           "its paths: a non-zero exit is a PROBLEM",
           rc == 1 and "docs/readme.md" in out and "outside the files your badge owns" in out
           and "PROBLEM  the project's hand-in check" in out and "exited 1" in out and "src/app/core/lib.py" in out, out)
    rc, out = run("amend", "EMP-01", "--by", mgr, "--add-files", "docs/readme.md", at=4443)
    rc, out = handin(at=4443.5)
    expect("a widened badge does not stand in for the hand-in check: it is still NOT READY while the check fails",
           rc == 1 and "exited 1" in out and "outside the files your badge owns" not in out, out)
    (tmp / "check.rc").write_text("0", encoding="utf-8")
    rc, out = handin(at=4444)
    expect("handin is READY once the badge is widened and the hand-in check passes, and the hand-in says it passed",
           rc == 0 and "the project's hand-in check" not in out and "): passed" in hi.read_text(encoding="utf-8"), out)
    put(wt, "src/app/tests/id.sh", "git config user.name scratch-test\n")
    g("add", "-A", cwd=wt)
    g("commit", "-q", "-m", "a test that writes the identity", cwd=wt)
    rc, out = handin(at=4444.5)
    expect("handin warns about a `git config user.*` write added by a commit",
           rc == 0 and "warning" in out and "src/app/tests/id.sh" in out, out)
    put(wt, "src/app/tests/id.sh", "# git config user.name scratch-test\n")
    g("add", "-A", cwd=wt)
    g("commit", "-q", "--amend", "-m", "a test with only a comment about it", cwd=wt)
    rc, out = handin(at=4444.6)
    expect("a whole-line comment naming the command is not a hit", rc == 0 and "id.sh" not in out.split("file(s)")[1], out)
    g("reset", "-q", "--hard", "HEAD~1", cwd=wt)
    put(repo, "docs/other.md", "main moved\n")
    g("add", "-A")
    g("commit", "-q", "-m", "main moves")
    rc, out = handin(at=4445)
    expect("handin warns when main has moved past the fork", rc == 0 and "commit(s) your branch lacks" in out, out)
    g("config", "user.name", "leaked-by-a-test", cwd=wt)
    rc, out = handin(at=4446)
    expect("handin catches a git identity written into the shared repo config",
           rc == 1 and "leaked-by-a-test" in out, out)
    g("config", "--unset", "user.name", cwd=wt)
    rc, out = handin("--commits", "0123abc", at=4447)
    expect("handin names a commit that does not exist", rc == 1 and "0123abc does not exist" in out, out)
    rc, out = handin(at=4448, cwd=tmp)
    expect("handin outside a git checkout is refused", rc == 3 and "not a git checkout" in out, out)
    expect("a handin is logged in the time clock and counts as heard",
           any(e["ev"] == "handin" and e["id"] == "EMP-01" and e["ok"] for e in read_events(d)))
    rc, out = run("me", "--badge", b1, at=4449)
    expect("me shows the last hand-in check", rc == 0 and "last hand-in check: NOT READY" in out, out)

    def me_in(cwd, at):
        r = subprocess.run([sys.executable, __file__, "me", "--badge", b1], capture_output=True, text=True,
                           encoding="utf-8", env={**henv, "FOUNDRY_NOW": str(t0 + at)}, cwd=cwd, timeout=120)
        return r.returncode, r.stdout + r.stderr
    rc, out = me_in(wt, 4449.1)
    expect("me prints the branch the session is on, the brief has one branch line, and no main warning off main",
           rc == 0 and "your branch here: claude/job in " in out and out.count("Branch: if your session starts in its "
                                                                              "own worktree") == 1
           and "you are on main" not in out, out)
    rc, out = me_in(repo, 4449.15)
    expect("me in a checkout on main says never commit there and to cut claude/<job>, and the branch line never "
           "says to work on the start branch unconditionally",
           rc == 0 and "your branch here: main in " in out and "you are on main: never commit here" in out
           and "Never commit on main" in out and "work on the branch your session starts on" not in out, out)
    rc, out = me_in(tmp, 4449.2)
    expect("me outside a git checkout says so", rc == 0 and "your branch here: none" in out, out)
    rc, out = me_in(wt, 4449.3)
    expect("with no review since the clock-in, me says none names the lane", rc == 0
           and "no review merged to main since your clock-in" in out and "names G99" in out, out)
    # reviews merged to main after b1's clock-in (t0 + 200): one names its lane G99, one names only G77
    for rel, text in (("docs/reviews/2027-01-15-g99.md", "# Review\nG99 Needs changes: a High.\n"),
                      ("docs/reviews/2027-01-15-g77.md", "# Review\nG77 and G990 only.\n")):
        put(repo, rel, text)
        g("add", "--", rel)
        r = subprocess.run(["git", "commit", "-q", "-m", "review " + rel], cwd=repo, capture_output=True, text=True,
                           env={**genv, "GIT_COMMITTER_DATE": f"{int(t0) + 4000} +0000"}, timeout=60)
        assert r.returncode == 0, r.stderr
    rc, out = me_in(wt, 4449.4)
    expect("me lists a review merged to main since the clock-in that names the lane, and not one that does not",
           rc == 0 and "reviews merged to main since your clock-in" in out and "docs/reviews/2027-01-15-g99.md (G99)" in out
           and "2027-01-15-g77.md" not in out, out)
    expect("reviews_since reads milestones from the job text",
           reviews_since({"job": "M4 slice 1b and M40x", "lane": ""}, t0)[0] == ["M4"])

    # reserve_adr counts drafts on unmerged branches, not only the main branch's records (paths.decisions)
    ra = tmp / "repo-adr"
    ra.mkdir()
    g("init", "-q", "-b", "main", cwd=ra)
    put(ra, "docs/decisions/0026-on-main.md", "x\n")
    g("add", "-A", cwd=ra)
    g("commit", "-q", "-m", "adr 26", cwd=ra)
    g("switch", "-q", "-c", "claude/contract-x", cwd=ra)
    put(ra, "docs/decisions/0032-a-draft.md", "x\n")
    g("add", "-A", cwd=ra)
    g("commit", "-q", "-m", "adr 32 draft", cwd=ra)
    g("switch", "-q", "main", cwd=ra)
    office = tmp / "office-adr"
    first, second = reserve_adr(office, ra, t0), reserve_adr(office, ra, t0 + 1)
    expect("with 0026 on main and 0032 drafted on a branch, two reservations give 0033 and 0034",
           (first, second) == ("0033", "0034") and adr_numbers(ra) == [26, 32], f"{first} {second} {adr_numbers(ra)}")

    # handin warns when a branch changes or drops a contract or prereg that main's gym/prereg pins
    r76, w76, w76b = tmp / "repo-j76", tmp / "repo-j76-wt", tmp / "repo-j76-wt2"
    r76.mkdir()
    g("init", "-q", "-b", "main", cwd=r76)
    cpath = "gym/contracts/G99-artifacts.md"
    put(r76, cpath, "draft\n")
    g("add", "-A", cwd=r76)
    g("commit", "-q", "-m", "contract draft", cwd=r76)
    g("worktree", "add", "-q", str(w76), "-b", "claude/m99", "main", cwd=r76)
    for rel, text, msg in (("gym/notes.md", "n\n", "notes"), (cpath, "draft\na1\n", "a1")):
        put(w76, rel, text)
        g("add", "-A", cwd=w76)
        g("commit", "-q", "-m", msg, cwd=w76)
    a1 = g("rev-parse", "--short=8", "HEAD", cwd=w76)
    sha = lambda b: hashlib.sha256(b).hexdigest()
    # one prereg shape: later pins sit in amendments[].pinned_changes.contract and .contract_commit, and
    # an amendment with no contract pin (a tables re-pin) comes after the latest one
    put(r76, "gym/prereg/G99.json", json.dumps({
        "prereg_id": "G99-v1",
        "contract": {"path": cpath, "git_blob": "x", "sha256": sha(b"draft\n"),
                     "commit": g("rev-parse", "--short=8", "HEAD", cwd=r76) + " (main, 'draft')"},
        "contract_history": [{"commit": "0000000", "sha256": sha(b"pre-draft\n"), "version": "read first"}],
        "amendments": [{"id": "a1", "written_at": "2027-01-02T10:00:00+00:00", "data_existed": False,
                        "pinned_changes": {"contract": sha(b"draft\na1\n"),
                                           "contract_commit": f"{a1} (claude/m99, contract amendment 1 on top of the draft)"}},
                       {"id": "a2", "pinned_changes": {"tables_sha256": "c" * 64}}]}))
    g("add", "-A", cwd=r76)
    g("commit", "-q", "-m", "prereg pins a1", cwd=r76)
    rq0 = {"vm": {"sweeps": [], "unmarked": []}}

    def pin_warns(wt_dir):
        _, ws, _ = handin_checks({"files": "gym/**", "role": "BUILDER"}, wt_dir, "main", [], rq0)
        return [x for x in ws if re.search(r"\bpin(s|ned)?\b|\bprereg\b", x)]
    expect("a branch that holds the pinned text gets no pin warning", pin_warns(w76) == [], str(pin_warns(w76)))
    for text, msg, want in (("draft\na1 reworded\n", "reword a1", "its text matches no pin"),
                            ("draft\n", "back to the draft", "its text is an older pin's")):
        put(w76, cpath, text)
        g("add", "-A", cwd=w76)
        g("commit", "-q", "-m", msg, cwd=w76)
        ws = pin_warns(w76)
        expect(f"a pinned contract changed on the branch warns ({want})",
               any(want in x and "G99-artifacts.md" in x and "appended amendment" in x for x in ws), str(ws))
    g("reset", "-q", "--keep", "HEAD~3", cwd=w76)  # back to 'notes': the pinned a1 is gone from the branch
    ws = pin_warns(w76)
    expect("a commit main's prereg names, reset off the branch, warns",
           any(f"names commit {a1}" in x and "no longer on it" in x for x in ws), str(ws))
    g("worktree", "add", "-q", str(w76b), "-b", "claude/g99", "main", cwd=r76)
    put(w76b, "gym/prereg/G99.json", json.dumps({"prereg_id": "G99-v1", "contract": {"path": cpath, "sha256": sha(b"draft\n")},
                                                 "amendments": []}))
    g("add", "-A", cwd=w76b)
    g("commit", "-q", "-m", "prereg rewritten", cwd=w76b)
    ws = pin_warns(w76b)
    expect("a branch that rewrites a pinned prereg's earlier amendment warns, and no unrelated pin commit is named",
           any("rewrites what main's gym/prereg/G99.json pinned" in x for x in ws) and not any("names commit" in x for x in ws), str(ws))
    g("rm", "-q", "gym/prereg/G99.json", cwd=w76b)
    g("commit", "-q", "-m", "prereg dropped", cwd=w76b)
    ws = pin_warns(w76b)
    expect("a branch that removes a pinned prereg warns", any("removes gym/prereg/G99.json" in x for x in ws), str(ws))
    expect("prereg_pins reads the latest pin and the named commits",
           prereg_pins({"contract": {"path": "c.md", "sha256": "a" * 64, "commit": "abcdef12 (x)"},
                        "amendments": [{"contract_sha256": "b" * 64, "contract_commit": "1234567"}, {"id": "a2"}]})
           == ("c.md", ["a" * 64, "b" * 64], ["abcdef12", "1234567"]) and prereg_pins({"prereg_id": "G0"}) is None
           and prereg_pins(["not", "an", "object"]) is None)
    h, c6, x2 = "1" * 64, "2" * 64, "3" * 64
    g26 = prereg_pins({"contract": {"path": "g26.md", "sha256": h, "commit": "6a4ab3ff (dated)"},
                       "pinned": {"contract_sha256": c6},
                       "amendments": [{"contract_pinned": {"commit": "82f23b75", "sha256": h}},
                                      {"contract_pinned": {"commits": ["92cd9b36 (x)", "f0c81099"], "sha256": c6, "was": h}}]})
    gx = prereg_pins({"contract": {"path": "gx.md", "sha256": h},
                      "pinned": {"contract_sha256": x2, "contract_sha256_after_a2": c6, "contract_sha256_after_a1": h,
                                 "contract_sha256_before_a1": "4" * 64},
                      "amendments": [{"contract_sha256_before": "4" * 64, "contract_amendment_adopted": {"commit": "b0e26bc1"}},
                                     {"contract_sha256_before": c6, "contract_sha256": x2,
                                      "contract_amendments_adopted": [{"commit": "050ed61f"}]}]})
    gx2 = prereg_pins({"contract_file": {"path": "gx2.md", "sha256": h, "commit": "a1cd8ec8 (dated)"}, "contract": None})
    expect("prereg_pins reads pinned/contract_pinned (commits list, was), pinned after_aN and adopted commits, and "
           "a contract_file block, with the latest pin last",
           g26 == ("g26.md", [h, c6], ["6a4ab3ff", "82f23b75", "92cd9b36", "f0c81099"])
           and gx == ("gx.md", ["4" * 64, c6, h, x2], ["b0e26bc1", "050ed61f"])
           and gx2 == ("gx2.md", [h], ["a1cd8ec8"]), f"{g26} {gx} {gx2}")

    rc, out = run("clock-out", "--badge", b1, "--result", "done", "--commits", "0123abc", at=4999)
    expect("a clock-out naming a commit the repo does not hold is refused", rc == 3 and "does not hold" in out, out)
    head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    rc, out = run("clock-out", "--badge", b1, "--result", "done", "--commits", head, at=5000)
    expect("the builder clocks out", rc == 0 and "done" in out, out)
    rc, out = run("clock-out", "--by", mgr, "--id", "EMP-02", "--result", "lost", at=5001)
    expect("the manager clocks out someone gone quiet", rc == 0, out)

    # a manager silent past MGR_STALE_S can be relieved only with --relieve; the old badge is revoked
    rc, out = run("appoint", "--name", "mgr-b", "--session", "local_mgr2", at=4310 + MGR_STALE_S + 600)
    expect("a stale manager is relieved by a new appointment", rc == 0 and "MGR-2" in out, out)
    expect("an appointment records the manager's session",
           read_roster(Path(env["FOUNDRY_PATHS_OFFICE"]))["badges"]["MGR-2"]["session"] == "local_mgr2", out)
    rc, out = run("verify", mgr, at=4310 + MGR_STALE_S + 601)
    expect("the relieved manager's badge is revoked", rc != 0 and "revoked" in out, out)

    # an appoint just before a slot boundary mints the next slot's badge and says so;
    # --this-slot keeps the current slot; 30 min before, the current slot. Each case in its own crew office.
    _, s0x, s1x = slot_at(DEFAULT_SLOTS, t0 + 50_000)
    nxt = slot_at(DEFAULT_SLOTS, s1x)
    here_id = slot_at(DEFAULT_SLOTS, s0x)[0]
    for case, before, extra, want_slot, want_end in (
            ("-15 min", 15 * 60, (), nxt[0], nxt[2]),
            ("-30 min", 30 * 60, (), here_id, s1x),
            ("-15 min --this-slot", 15 * 60, ("--this-slot",), here_id, s1x),
            ("-28 min --slot", 28 * 60, ("--slot", nxt[0]), nxt[0], nxt[2]),
            ("-28 min --slot this one", 28 * 60, ("--slot", here_id.upper()), here_id, s1x)):
        dd = tmp / ("office-appoint-" + str(len(ok) + len(bad)))
        at = s1x - before
        r = subprocess.run([sys.executable, __file__, "appoint", "--name", "mgr-edge", *extra], capture_output=True,
                           text=True, encoding="utf-8", timeout=60,
                           env={**env, "FOUNDRY_PATHS_OFFICE": str(dd), "FOUNDRY_NOW": str(at)})
        out = r.stdout + r.stderr
        rec = next(iter(read_roster(dd)["badges"].values()), {}) if r.returncode == 0 else {}
        expect(f"appoint at {case} mints the {want_slot} slot's badge, its finish that slot's end",
               rec.get("slot") == want_slot and f"SLOT:{want_slot.upper()}" in rec.get("line", "")
               and abs(at + rec.get("eta_s", 0) - want_end) < 2, out + str(rec))
        moved = want_slot != here_id and "--slot" not in extra
        expect(f"appoint at {case} " + ("warns the slot moved" if moved else "has no slot warning"),
               ("use --this-slot to keep the " + here_id in out) == moved, out)
    r = subprocess.run([sys.executable, __file__, "appoint", "--name", "mgr-bad", "--slot", "dawn"], capture_output=True,
                       text=True, encoding="utf-8", timeout=60,
                       env={**env, "FOUNDRY_PATHS_OFFICE": str(tmp / "office-appoint-bad"), "FOUNDRY_NOW": str(s1x - 600)})
    expect("appoint --slot with a slot the rota lacks is refused, naming the rota's slots",
           r.returncode == 3 and "day, swing, night" in r.stderr, r.stdout + r.stderr)

    # --slot names the slot now or the next one in its last hour; --slot with --this-slot is an error
    for n, (case, at, extra, want_rc) in enumerate((
            ("--slot the next slot 90 min before it starts is refused", s1x - 90 * 60, ("--slot", nxt[0]), 3),
            ("--slot the slot after next is refused", s1x - 10 * 60, ("--slot", slot_at(DEFAULT_SLOTS, nxt[2])[0]), 3),
            ("--slot with --this-slot is an argument error", s1x - 10 * 60, ("--slot", nxt[0], "--this-slot"), 2))):
        dd = tmp / f"office-appoint-l6-{n}"
        r = subprocess.run([sys.executable, __file__, "appoint", "--name", "mgr-l6", *extra], capture_output=True,
                           text=True, encoding="utf-8", timeout=60,
                           env={**env, "FOUNDRY_PATHS_OFFICE": str(dd), "FOUNDRY_NOW": str(at)})
        expect(f"appoint {case}",
               r.returncode == want_rc and not (dd / "roster.json").exists()
               and (want_rc != 3 or "name the slot now" in r.stderr), r.stdout + r.stderr)

    # a refused appoint --relieve --slot leaves the old manager on the clock, unrevoked, with no
    # `out relieved` event in the timeclock
    dd = tmp / "office-appoint-n1"
    def run_n1(*args, at):
        r = subprocess.run([sys.executable, __file__, *args], capture_output=True, text=True, encoding="utf-8",
                           timeout=60, cwd=tmp, env={**env, "FOUNDRY_PATHS_OFFICE": str(dd), "FOUNDRY_NOW": str(at)})
        return r.returncode, r.stdout + r.stderr
    rc, out = run_n1("appoint", "--name", "mgr-n1", at=s1x - 3 * 3600)
    run_n1("clock-in", "--badge", badge_of(out) if rc == 0 else "", at=s1x - 3 * 3600 + 60)
    for case, bad_slot in (("a slot past its last hour", nxt[0]), ("a slot the rota lacks", "dawn")):
        rc, out = run_n1("appoint", "--name", "mgr-n1b", "--relieve", "--slot", bad_slot, at=s1x - 90 * 60)
        mr = next((b for b in crew(dd, s1x - 90 * 60 + 1)["badges"] if b["id"] == "MGR-1"), {})
        ro = read_roster(dd)
        expect(f"a refused appoint --relieve --slot ({case}) leaves the old manager on the clock",
               rc == 3 and mr.get("on") and ro.get("manager") == "MGR-1" and not ro["badges"]["MGR-1"].get("revoked")
               and len(ro["badges"]) == 1
               and not any(e["ev"] == "out" and e.get("result") == "relieved" for e in read_events(dd)), out + str(mr))

    # a manager re-badged at 05:32 with --slot day is the day slot's manager from then on: its badge reads
    # the day slot (so its rota `day.ends` is read by the map) and a hire at 05:35 is stamped SLOT:DAY
    ds = named_slot(DEFAULT_SLOTS, "day", t0 + 50_000)
    ds = ds if ds[1] > t0 + 50_000 else named_slot(DEFAULT_SLOTS, "day", ds[2])
    dd = tmp / "office-appoint-m1"
    def run_m1(*args, at):
        r = subprocess.run([sys.executable, __file__, *args], capture_output=True, text=True, encoding="utf-8",
                           timeout=60, cwd=tmp, env={**env, "FOUNDRY_PATHS_OFFICE": str(dd), "FOUNDRY_NOW": str(at)})
        return r.returncode, r.stdout + r.stderr
    rc, out = run_m1("appoint", "--name", "mgr-m1", "--slot", "day", at=ds[1] - 28 * 60)
    m1 = badge_of(out) if rc == 0 else ""
    expect("appoint --slot day at 05:32 keeps the day slot's start on the badge",
           read_roster(dd)["badges"].get("MGR-1", {}).get("slot_start") == ds[1], out)
    run_m1("clock-in", "--badge", m1, at=ds[1] - 27 * 60)
    mrec = next((b for b in crew(dd, ds[1] - 26 * 60)["badges"] if b["id"] == "MGR-1"), None)
    expect("a --slot day badge clocked in at 05:33 reads the day slot (badge_slot), so its rota day.ends is read",
           mrec is not None and badge_slot(DEFAULT_SLOTS, mrec) == ds, str(mrec))
    rc, out = run_m1("hire", "--by", m1, "--name", "m1-crew", "--role", "builder", "--kind", "temp", "--job", "j",
                     "--eta", "30m", at=ds[1] - 25 * 60)
    expect("a hire at 05:35 by a --slot day manager is stamped SLOT:DAY", "SLOT:DAY " in (badge_of(out) if rc == 0 else ""),
           out)
    expect("without the --slot record the same badge at 05:33 reads no slot",
           mrec is not None and badge_slot(DEFAULT_SLOTS, {**mrec, "slot_start": None}) is None, str(mrec))

    # a manager badge with no slot recorded (an older format) hires by the clock look-ahead: the next slot
    # within APPOINT_LEAD_S of its start, otherwise the slot now
    expect("hire_slot for a slotless manager badge 5 min before a slot is that next slot",
           hire_slot(DEFAULT_SLOTS, {}, s1x - 5 * 60) == nxt[0])
    expect("hire_slot for a slotless manager badge an hour before a slot is the slot now",
           hire_slot(DEFAULT_SLOTS, {"slot": None}, s1x - 60 * 60) == here_id)

    # hire stamps the hiring manager's own badge slot. A manager appointed 10 min before a
    # boundary (the next slot's) hires next-slot crew at -5 min; one re-appointed with --this-slot hires this slot's
    # crew at -5 min; one appointed an hour before hires this slot's crew. The brief says stop at the end
    # and never to clear yourself, and it gives its Tests line and the manager's session
    # as the roster has it at print time.
    for n, (case, appoint_at, flags, hire_at, want_slot) in enumerate((
            ("appointed -10 min, hired -5 min", 10 * 60, (), 5 * 60, nxt[0]),
            ("appointed -10 min --this-slot, hired -5 min", 10 * 60, ("--this-slot",), 5 * 60, here_id),
            ("appointed -60 min, hired -30 min", 60 * 60, (), 30 * 60, here_id),
            ("appointed -30 min, hired +60 min, its slot ended", 30 * 60, (), -60 * 60, nxt[0]))):
        dd = tmp / f"office-hire-edge-{n}"
        def run_dd(*args, at):
            r = subprocess.run([sys.executable, __file__, *args], capture_output=True, text=True, encoding="utf-8",
                               timeout=60, cwd=tmp, env={**env, "FOUNDRY_PATHS_OFFICE": str(dd), "FOUNDRY_NOW": str(at)})
            return r.returncode, r.stdout + r.stderr
        rc, out = run_dd("appoint", "--name", "mgr-h", "--session", "local_hire-time", *flags, at=s1x - appoint_at)
        mh = badge_of(out) if rc == 0 else ""
        run_dd("clock-in", "--badge", mh, at=s1x - appoint_at + 30)
        rc, out = run_dd("hire", "--by", mh, "--name", f"edge-{n}", "--role", "builder",
                         "--kind", "temp", "--job", "j", "--eta", "30m", at=s1x - hire_at)
        line = badge_of(out) if rc == 0 else ""
        expect(f"hire ({case}) stamps SLOT:{want_slot.upper()}", f"SLOT:{want_slot.upper()} " in line, out)
        if n:
            continue
        expect("the hire brief says stop at the end and never clear yourself",
               "and stop. Never clear yourself" in out and "the user /clears it" in out, out)
        expect("the hire brief never tells a session to clear_session \"self\"",
               'clear_session "self"' not in out and "clear_session('self')" not in out, out)
        expect("the hire brief has one Tests line, run in the worktree; with no file list and no lane it names no selftest",
               out.count("Tests, run in your worktree") == 1 and "selftest`" not in out.split("--- brief", 1)[-1], out)
        expect("the hire brief carries no host note and no tag",
               not re.search(r"\((?:[JF]\d+|(?:night|day|swing) hole)", out) and "8 GB" not in out, out)
        expect("the hire brief names the manager's session from the roster", "session local_hire-time" in out, out)
        run_dd("assign", "MGR-1", "--session", "local_later-id", at=s1x - hire_at + 10)
        rc, out = run_dd("brief", "--by", mh, "TMP-01", at=s1x - hire_at + 20)
        rc2, out2 = run_dd("me", "--badge", line, at=s1x - hire_at + 30)
        expect("brief and me print the manager's session as the roster has it now, and say to check office.py roster",
               all("session local_later-id" in o and "local_hire-time" not in o and "check office.py roster" in o
                   for o in (out, out2)), out + out2)
        expect("the brief's manager line gives the manager's status while it is on the clock",
               "mgr-h (UP), session local_later-id" in out, out)
        rc3, out3 = run_dd("clock-out", "--badge", mh, "--result", "done", "--note", "end", at=s1x - hire_at + 40)
        rc, out = run_dd("me", "--badge", line, at=s1x - hire_at + 50)
        last = next((l for l in out.splitlines() if l.startswith("Manager at ")), "")
        expect("after the manager clocks out the brief's manager line says none on the clock and the last one is OUT",
               rc3 == 0 and "none on the clock" in last and "is OUT" in last, out3 + last)

    # appoint and assign warn when --session is local_ + CLAUDE_CODE_SESSION_ID (the CLI's id)
    dd = tmp / "office-cli-session"
    def run_cli(*args, at, cli="cli-uuid-1234"):
        r = subprocess.run([sys.executable, __file__, *args], capture_output=True, text=True, encoding="utf-8",
                           timeout=60, cwd=tmp, env={**env, "FOUNDRY_PATHS_OFFICE": str(dd), "FOUNDRY_NOW": str(t0 + at),
                                            "CLAUDE_CODE_SESSION_ID": cli})
        return r.returncode, r.stdout + r.stderr
    rc, out = run_cli("appoint", "--name", "mgr-cli", "--session", "local_cli-uuid-1234", at=100)
    expect("appoint warns when --session is local_ + CLAUDE_CODE_SESSION_ID",
           rc == 0 and "CLAUDE_CODE_SESSION_ID" in out and 'get_session "self"' in out, out)
    mc = badge_of(out) if rc == 0 else ""
    rc, out = run_cli("assign", "MGR-1", "--session", "local_app-5678", at=110)
    expect("assign with the app's id has no warning", rc == 0 and "CLAUDE_CODE_SESSION_ID" not in out, out)
    rc, out = run_cli("assign", "MGR-1", "--session", "local_cli-uuid-1234", at=120)
    expect("assign with the CLI's id warns", rc == 0 and "CLAUDE_CODE_SESSION_ID" in out, out)
    rc, out = run_cli("appoint", "--name", "mgr-cli2", "--relieve", "--session", "local_app-9999", at=130)
    expect("appoint with another id has no warning", "CLAUDE_CODE_SESSION_ID" not in out, out)

    # assign --dry-run lists what a session built and says whether a grader may go there; writes nothing
    dd = tmp / "office-assign-dry"
    def run_ad(*args, at):
        r = subprocess.run([sys.executable, __file__, *args], capture_output=True, text=True, encoding="utf-8",
                           timeout=60, cwd=tmp, env={**env, "FOUNDRY_PATHS_OFFICE": str(dd), "FOUNDRY_NOW": str(t0 + at)})
        return r.returncode, r.stdout + r.stderr
    rc, out = run_ad("appoint", "--name", "mgr-ad", at=100)
    ma = badge_of(out)
    run_ad("clock-in", "--badge", ma, at=110)
    rc, out = run_ad("hire", "--by", ma, "--name", "bld", "--role", "builder", "--kind", "session", "--job", "j",
                     "--eta", "30m", "--lane", "G77", at=120)
    bl = badge_of(out)
    run_ad("assign", "EMP-01", "--session", "local_bench-x", at=130)
    run_ad("clock-in", "--badge", bl, at=140)
    run_ad("clock-out", "--badge", bl, "--result", "partial", at=150)
    rc, out = run_ad("hire", "--by", ma, "--name", "grd", "--role", "grader", "--kind", "session", "--job", "g",
                     "--eta", "30m", "--lane", "G77", at=160)
    rc, out = run_ad("assign", "EMP-02", "--session", "local_bench-x", "--dry-run", at=170)
    expect("assign --dry-run lists the lanes a session built and says a grader would be refused",
           rc == 3 and "EMP-01 bld builder lane G77" in out and "built: G77" in out and "would be refused" in out, out)
    expect("assign --dry-run writes nothing",
           read_roster(dd)["badges"]["EMP-02"].get("session") is None, out)
    rc, out = run_ad("assign", "EMP-02", "--session", "local_bench-y", "--dry-run", at=180)
    expect("assign --dry-run on a fresh session says it would be taken",
           rc == 0 and "has held 0 badge(s)" in out and "would be taken" in out, out)

    # hire warns when the brief or done-when names a docs/reviews/ or docs/research/ file --files does not own
    dj = tmp / "office-report-paths"
    def run_j(*args, at):
        r = subprocess.run([sys.executable, __file__, *args], capture_output=True, text=True, encoding="utf-8",
                           timeout=60, cwd=tmp, env={**env, "FOUNDRY_PATHS_OFFICE": str(dj), "FOUNDRY_NOW": str(t0 + at)})
        return r.returncode, r.stdout + r.stderr
    rc, out = run_j("appoint", "--name", "mgr-rp", at=100)
    mj = badge_of(out)
    run_j("clock-in", "--badge", mj, at=110)
    rc, out = run_j("hire", "--by", mj, "--name", "rev", "--role", "reviewer", "--kind", "temp", "--eta", "30m",
                    "--job", "review a2 and a3; write docs/reviews/2027-01-02-g1-a2-a3.md.",
                    "--done-when", "the report docs/research/2027-01-02-x.md and docs/reviews/2027-01-02-g1-a2.md committed",
                    "--files", "docs/reviews/2027-01-02-g1-a2.md", at=120)
    expect("hire warns for each report path the brief or done-when names outside --files, and not for the one it owns",
           rc == 0 and "! report path: the brief names docs/reviews/2027-01-02-g1-a2-a3.md," in out
           and "names docs/research/2027-01-02-x.md," in out and "names docs/reviews/2027-01-02-g1-a2.md," not in out, out)
    tj = badge_of(out) if rc == 0 else ""
    rc, out = run_j("hire", "--by", mj, "--name", "rev2", "--role", "reviewer", "--kind", "temp", "--eta", "30m",
                    "--job", "review into docs/reviews/2027-01-02-ok.md; see docs/reviews/ for the form",
                    "--files", "docs/reviews/2027-01-02-ok.md", at=130)
    expect("no warning when --files owns the named report (a bare folder named in passing is not a file)",
           rc == 0 and "report path" not in out, out)
    # the Tests line follows the owned files, the lane and the profile's measure.selftest
    expect("a docs-only hire's brief says to run no selftest", rc == 0 and "Tests: none." in out
           and "selftest`" not in out.split("--- brief", 1)[-1], out)
    py = prof().py
    t_docs = " ".join(tests_lines({"files": "docs/decisions/0028-x.md, gym/contracts/G35-artifacts.md"}))
    t_lane = " ".join(tests_lines({"files": "gym/lanes/g24_settings.py, gym/prereg/G24.json", "lane": "G24"}))
    t_quiet = " ".join(tests_lines({"files": "gym/lanes/g18_hardening.py, gym/prereg/G18.json", "lane": "G18"}))
    t_code = " ".join(tests_lines({"files": "scripts/foundry/office.py, scripts/foundry/rq.py, docs/x.md"}))
    t_all = " ".join(tests_lines({"files": "scripts/**"}))
    t_src = " ".join(tests_lines({"files": "src/app/**"}))
    t_bare = " ".join(tests_lines({"files": ""}))
    expect("docs and gym contract files only: no selftest", "Tests: none." in t_docs and "selftest`" not in t_docs, t_docs)
    expect("a lane brief runs the lane's own selftest first, then the gym's own (measure.selftest), which it may run in "
           "the background; it names no crew tool the files do not touch",
           f"`{py} gym/lanes/g24_settings.py`" in t_lane and "`python gym/run.py selftest`" in t_lane
           and t_lane.index("g24_settings") < t_lane.index("gym/run.py selftest")
           and "run it in the background and wait for its notice" in t_lane and "office.py selftest" not in t_lane, t_lane)
    expect("a brief whose files touch Foundry tools names the selftest of each one touched, by its path in the worktree, "
           "and no other; with no lane it names no gym selftest",
           f"`{py} scripts/foundry/office.py selftest`" in t_code and f"`{py} scripts/foundry/rq.py selftest`" in t_code
           and "board.py selftest" not in t_code and "journal.py selftest" not in t_code and "gym/run.py" not in t_code
           and "gym/lanes/" not in t_code and "Tests: none" not in t_code
           and all(f"scripts/foundry/{n} selftest" in t_all for n in FOUNDRY_TOOLS), t_code + t_all)
    expect("a brief with no file list, or files that touch no tool, names no selftest and says so; every Tests line says "
           "to run in the worktree and keeps the map's check out of the main checkout",
           all("selftest`" not in t and "names no crew tool or gym selftest" in t for t in (t_src, t_bare))
           and all("run in your worktree" in t and "Never run `board.py check`" in t for t in (t_lane, t_quiet, t_code, t_src, t_bare)),
           t_src + t_bare)
    expect("a lane file with no __main__ block (G18) is never named as a runnable selftest; the brief points at the gym's "
           "own selftest instead", f"`{py} gym/lanes/g18_hardening.py`" not in t_quiet
           and "has no `__main__` block" in t_quiet and "only inside the gym's own selftest" in t_quiet
           and "`python gym/run.py selftest`" in t_quiet, t_quiet)
    expect("lane_files finds G1's file, not G10's; lane_selftests drops it (no __main__ block) and keeps G24's",
           lane_files("G1") == ["gym/lanes/g1_boot.py"] and lane_selftests("G1") == []
           and lane_selftests("G24") == ["gym/lanes/g24_settings.py"] and lane_files("G999") == [] and lane_selftests("") == [],
           f"{lane_files('G1')} {lane_selftests('G1')} {lane_selftests('G24')}")
    os.environ["FOUNDRY_PATHS_GYM"] = "no-such-gym"
    t_nogym = " ".join(tests_lines({"files": "src/app/**", "lane": "G24"}))
    expect("with no gym folder the lane lookups are skipped quietly: no lane file, no crash, the Tests line still prints",
           lane_files("G24") == [] and lane_selftests("G24") == [] and "g24_settings" not in t_nogym
           and "Tests, run in your worktree" in t_nogym, t_nogym)
    os.environ.pop("FOUNDRY_PATHS_GYM")
    os.environ["FOUNDRY_PROFILE"] = str(tmp / "bare.toml")
    t_noself = " ".join(tests_lines({"files": "gym/lanes/g24_settings.py", "lane": "G24"}))
    expect("with no measure.selftest in the profile a lane brief names the lane's own selftest and no gym command",
           "g24_settings.py`" in t_noself and "the gym's own selftest, `" not in t_noself, t_noself)
    os.environ.pop("FOUNDRY_PROFILE")
    rc, out = run_j("amend", "TMP-02", "--by", mj, "--done-when", "docs/research/2027-01-02-new.md written", at=140)
    expect("amend warns for a report path the amended done-when names outside the files",
           rc == 0 and "! report path: the brief names docs/research/2027-01-02-new.md," in out, out)
    expect("amend's tell line keeps the space before the session", "tell TMP-02 (" in out, out)

    # hire --adr reserves the next ADR number from one counter in the office; two hires, two numbers
    da = tmp / "office-adr-hire"
    (tmp / "state-crew5.json").write_text(json.dumps({**state, "shift": {"id": "test-shift", "crew_max": 5}}), encoding="utf-8")
    def run_a(*args, at):
        r = subprocess.run([sys.executable, __file__, *args], capture_output=True, text=True, encoding="utf-8",
                           timeout=60, cwd=tmp, env={**env, "FOUNDRY_PATHS_OFFICE": str(da), "FOUNDRY_NOW": str(t0 + at),
                                            "FOUNDRY_PATHS_STATE": str(tmp / "state-crew5.json")})
        return r.returncode, r.stdout + r.stderr
    rc, out = run_a("appoint", "--name", "mgr-adr", at=100)
    ma = badge_of(out)
    run_a("clock-in", "--badge", ma, at=110)
    nums = []
    for n, at in ((1, 120), (2, 130)):
        rc, out = run_a("hire", "--by", ma, "--name", f"contract-{n}", "--role", "builder", "--kind", "session",
                        "--eta", "1h", "--job", "write a contract and its ADR", "--files", "docs/decisions/**", "--adr", at=at)
        m = re.search(r"Your ADR number: (\d{4}), reserved", out)
        nums.append(int(m.group(1)) if rc == 0 and m else None)
    on_main = adr_numbers(main_checkout())
    expect("two hires with --adr get two numbers, one apart, past the main branch's records, and the brief names the "
           "profile's decisions folder and cites by file name",
           None not in nums and nums[1] == nums[0] + 1 and on_main == [3] and nums[0] == 4
           and "(docs/decisions/0005-<topic>.md)" in out
           and "cite other drafts by file name" in out.lower()
           and json.loads((da / ADR_COUNTER).read_text(encoding="utf-8"))["last"] == nums[1], f"{nums} {on_main} {out}")
    rc, out = run_a("hire", "--by", ma, "--name", "no-adr", "--role", "builder", "--kind", "temp", "--eta", "1h",
                    "--job", "j", at=140)
    expect("a hire without --adr reserves nothing", rc == 0 and "ADR number" not in out
           and json.loads((da / ADR_COUNTER).read_text(encoding="utf-8"))["last"] == (nums[1] or 0), out)
    # a TEMP badge whose --files names .claude/hooks/ or .claude/settings.json is warned at hire and amend,
    # and its brief says to deliver the change as a patch, not a commit
    dh = tmp / "office-harness"
    def run_h(*args, at):
        r = subprocess.run([sys.executable, __file__, *args], capture_output=True, text=True, encoding="utf-8",
                           timeout=60, cwd=tmp, env={**env, "FOUNDRY_PATHS_OFFICE": str(dh), "FOUNDRY_NOW": str(t0 + at)})
        return r.returncode, r.stdout + r.stderr
    rc, out = run_h("appoint", "--name", "mgr-hk", at=100)
    mh = badge_of(out)
    run_h("clock-in", "--badge", mh, at=110)
    rc, out = run_h("hire", "--by", mh, "--name", "hk", "--role", "builder", "--kind", "temp", "--eta", "30m",
                    "--job", "fix a hook", "--files", ".claude/hooks/guard.py, scripts/office.py", at=120)
    expect("hire warns for a temp whose --files names .claude/hooks/, and its brief says to deliver a patch",
           rc == 0 and "! harness config: --files names .claude/hooks on a TEMP badge" in out
           and "Harness config (.claude/hooks): " in out and HARNESS_BRIEF in out.split("--- brief", 1)[-1], out)
    rc, out = run_h("hire", "--by", mh, "--name", "hs", "--role", "builder", "--kind", "session", "--eta", "30m",
                    "--job", "fix a hook", "--files", ".claude/hooks/**, .claude/settings.json", at=130)
    expect("no harness warning for a session badge (the user can type its approval there)",
           rc == 0 and "harness config" not in out.lower(), out)
    rc, out = run_h("hire", "--by", mh, "--name", "pl", "--role", "builder", "--kind", "temp", "--eta", "30m",
                    "--job", "tools", "--files", "scripts/office.py, .claude/skills/foundry-employee/SKILL.md", at=140)
    expect("no harness warning for a temp whose files miss the harness config",
           rc == 0 and "harness config" not in out.lower(), out)
    tid = parse_line(badge_of(out))[0]["ID"] if rc == 0 else "TMP-00"
    rc, out = run_h("amend", tid, "--by", mh, "--add-files", ".claude/settings.json", at=150)
    expect("amend warns when it adds .claude/settings.json to a temp, and the reprinted brief says so",
           rc == 0 and "! harness config: --files names .claude/settings.json on a TEMP badge" in out
           and "Harness config (.claude/settings.json): " in out, out)
    expect("harness_hits reads folders and globs", harness_hits(".claude/**") == [".claude/settings.json", ".claude/hooks"]
           and harness_hits(".claude/hooks") == [".claude/hooks"] and harness_hits("scripts/**") == [],
           harness_hits(".claude/**"))
    # `**/` matches zero folders, and a glob naming another hooks file still warns. A glob that
    # would also own a file of that name under .claude/hooks/ (`**/settings.json`) names the hooks too.
    for globs, want in ((".claude/**/*.json", [".claude/settings.json", ".claude/hooks"]), (".claude/*/guard.py", [".claude/hooks"]),
                        (".claude/**/guard.py", [".claude/hooks"]), (".claude/**/settings.json", [".claude/settings.json", ".claude/hooks"]),
                        ("**/settings.json", [".claude/settings.json", ".claude/hooks"]), (".claude/*/no_python_stdin.py", [".claude/hooks"]),
                        (".claude/**/*.py", [".claude/hooks"]), (".claude/skills/**, scripts/**", [])):
        expect(f"harness_hits({globs!r}) == {want}", harness_hits(globs) == want, str(harness_hits(globs)))
    expect("owns() lets `**/` match no folder, for the hand-in check too",
           owns([".claude/**/*.json"], ".claude/settings.json") and owns(["docs/**/x.md"], "docs/x.md")
           and owns(["docs/**/x.md"], "docs/a/b/x.md") and not owns(["docs/**/x.md"], "docsx.md")
           and not owns(["docs/**/x.md"], "other/x.md"), "")
    # some file systems ignore case, and a brief may give the absolute path.
    for globs, want in ((".Claude/Hooks/x.py", [".claude/hooks"]), (".CLAUDE/Settings.json", [".claude/settings.json"]),
                        ("D:/some project/.claude/hooks/x.py", [".claude/hooks"]),
                        ("D:\\some project\\.Claude\\Hooks\\x.py", [".claude/hooks"]),
                        ("D:/some project/.claude/settings.json", [".claude/settings.json"]),
                        ("D:/repo/.claude/hooks", [".claude/hooks"]),
                        ("D:/some project/.claude/skills/x.md", [])):
        expect(f"harness_hits({globs!r}) == {want}", harness_hits(globs) == want, str(harness_hits(globs)))

    # an employee's punches from its worktree never write or stage the map's files there. office.py progress and
    # fail write only the crew office; the worktree's own board.py refuses its writing commands (it would write
    # the worktree's copies, which a later commit carries).
    rj, wj = tmp / "repo-wt-punch", tmp / "repo-wt-punch-wt"
    rj.mkdir()
    g("init", "-q", "-b", "main", cwd=rj)
    tools_here = Path(__file__).resolve().parent
    board_there = (tools_here / "board.py").is_file()
    for name in ("office.py", "foundry_profile.py") + (("board.py",) if board_there else ()):
        if (tools_here / name).is_file():
            put(rj, "scripts/foundry/" + name, (tools_here / name).read_text(encoding="utf-8"))
    put(rj, ".foundry/foundry.toml", prof_head)
    put(rj, "docs/progress/state.json", json.dumps(state) + "\n")
    put(rj, "docs/progress-map.html", "<!doctype html><title>map</title>\n")
    g("add", "-A", cwd=rj)
    g("commit", "-q", "-m", "base", cwd=rj)
    g("worktree", "add", "-q", str(wj), "-b", "claude/wt-punch", "main", cwd=rj)
    # the worktree's own tools find their own checkout and its main checkout: only the office is shared
    jenv = {k: v for k, v in nogit.items() if not k.startswith("FOUNDRY_")}
    jenv.update({"FOUNDRY_PATHS_OFFICE": str(dj), "FOUNDRY_NOW": str(t0 + 200),
                 "PYTHONDONTWRITEBYTECODE": "1"})  # a __pycache__ in the scratch worktree is not the map
    run_j("clock-in", "--badge", tj, at=150)

    def in_wt(script, *args):
        r = subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True, encoding="utf-8",
                           env=jenv, cwd=wj, timeout=300)
        return r.returncode, r.stdout + r.stderr

    n_ev = len(read_events(dj))
    rc1, out1 = in_wt(wj / "scripts" / "foundry" / "office.py", "progress", "--badge", tj, "--pct", "40", "--note", "from the worktree")
    rc2, out2 = in_wt(wj / "scripts" / "foundry" / "office.py", "fail", "--badge", tj, "--what", "x VOID", "--verdict", "VOID")
    wt_status = g("status", "--porcelain", "--untracked-files=all", cwd=wj)
    expect("office.py progress and fail run from a worktree's own copy punch the shared office and leave the worktree's "
           "tree and index untouched", rc1 == 0 and rc2 == 0 and wt_status == "" and len(read_events(dj)) == n_ev + 2
           and not (rj / "out").exists() and not (wj / "out").exists(), out1 + out2 + wt_status)
    if board_there:
        rc3, out3 = in_wt(wj / "scripts" / "foundry" / "board.py", "fail", "--what", "x VOID")
        rc4, out4 = in_wt(wj / "scripts" / "foundry" / "board.py", "note", "--by", "TMP-01", "a note")
        rc5, out5 = in_wt(wj / "scripts" / "foundry" / "board.py", "check", "--no-build")
        wt_status = g("status", "--porcelain", "--untracked-files=all", cwd=wj)
        expect("the worktree's board.py fail and note are refused (exit 3) and write nothing; check --no-build writes "
               "nothing either", rc3 == 3 and rc4 == 3 and "linked worktree" in out3 and "office.py fail" in out3
               and wt_status == "", f"{rc3} {rc4} {rc5}: " + out3 + out4 + out5[-300:] + wt_status)
    else:
        print("  skip the worktree's board.py case: no board.py beside office.py")
    g("worktree", "remove", "--force", str(wj), cwd=rj)

    # the founder: one badge outside the headcount, on its own roster line above the manager; it clocks in, posts
    # progress and clocks out, and its line is refused wherever the manager's is asked for
    df = tmp / "office-founder"
    (tmp / "state-founder.json").write_text(json.dumps(state), encoding="utf-8")  # crew_max 2

    def run_f(*args, at):
        r = subprocess.run([sys.executable, __file__, *args], capture_output=True, text=True, encoding="utf-8",
                           timeout=60, cwd=tmp, env={**env, "FOUNDRY_PATHS_OFFICE": str(df), "FOUNDRY_NOW": str(t0 + at),
                                                    "FOUNDRY_PATHS_STATE": str(tmp / "state-founder.json")})
        return r.returncode, r.stdout + r.stderr
    rc, out = run_f("found", "--name", "founder-a", "--session", "local_fdr", at=10)
    f1 = badge_of(out) if rc == 0 else ""
    expect("found mints the one founder badge, FDR-1, with the profile's prefix and ROLE:FOUNDER",
           rc == 0 and f1.startswith(f"{PRE} ID:FDR-1 ") and "ROLE:FOUNDER" in f1
           and read_roster(df).get("founder") == "FDR-1" and ((df / "badges" / "FDR-1.svg").is_file() or not HAVE_SEGNO), out)
    rc, out = run_f("verify", f1, at=11)
    expect("a founder's line verifies", rc == 0 and "genuine: FDR-1 founder-a founder" in out, out)
    rc, out = run_f("found", "--name", "founder-b", at=12)
    expect("a second founder badge replaces one that never clocked in, and the old line is revoked",
           rc == 0 and "FDR-2" in out and read_roster(df)["founder"] == "FDR-2" and run_f("verify", f1, at=13)[0] == 3, out)
    f2 = badge_of(out) if rc == 0 else ""
    rc, out = run_f("clock-in", "--badge", f2, at=20)
    expect("the founder clocks in, with no finish estimate", rc == 0 and "FDR-2 founder-b clocked in" in out
           and "approximate finish" not in out, out)
    rc, out = run_f("found", "--name", "founder-c", at=30)
    expect("found is refused while another founder badge is on the clock, and changes nothing",
           rc == 3 and "is the founder and on the clock" in out and "--relieve" in out
           and read_roster(df)["founder"] == "FDR-2" and "FDR-3" not in read_roster(df)["badges"], out)
    rc, out = run_f("appoint", "--name", "mgr-f", "--session", "local_mgr-f", at=40)
    mf = badge_of(out) if rc == 0 else ""
    run_f("clock-in", "--badge", mf, at=50)
    rc, out = run_f("progress", "--badge", f2, "--pct", "20", "--note", "auditing the roadmap", at=60)
    expect("the founder posts progress", rc == 0 and "FDR-2 at 20%" in out, out)
    hire_args = ("--name", "b-f", "--role", "builder", "--kind", "temp", "--job", "j", "--eta", "30m")
    rc, out = run_f("hire", "--by", f2, *hire_args, at=70)
    expect("hire refuses a founder's line as --by: the founder does not hire",
           rc == 3 and "the founder does not hire" in out and len(read_roster(df)["badges"]) == 3, out)
    rc, out = run_f("hire", "--by", mf, "--name", "founder-x", "--role", "founder", "--kind", "session", "--job", "j", "--eta", "30m", at=71)
    expect("nobody is hired as a FOUNDER (or a MANAGER)", rc == 3 and "hire one of BUILDER" in out, out)
    rc, out = run_f("hire", "--by", mf, *hire_args, at=72)
    tf = badge_of(out) if rc == 0 else ""
    expect("with a founder and a manager on the clock, the first hire is crew 1 of 2: neither counts",
           rc == 0 and "crew 1 of 2" in out, out)
    for cmd_args in (("amend", "TMP-01", "--by", f2, "--job", "x"), ("end-shift", "--by", f2), ("brief", "TMP-01", "--by", f2),
                     ("assign", "TMP-01", "--session", "local_x", "--by", f2),
                     ("clock-out", "--by", f2, "--id", "TMP-01", "--result", "lost")):
        n_ev = len(read_events(df))
        rc, out = run_f(*cmd_args, at=80)
        expect(f"{cmd_args[0]} refuses a founder's line as --by and writes nothing",
               rc == 3 and "founder" in out and len(read_events(df)) == n_ev
               and read_roster(df)["badges"]["TMP-01"].get("session") is None, out)
    rc, out = run_f("assign", "TMP-01", "--session", "local_x", "--by", mf, at=81)
    expect("assign takes the manager's line as --by", rc == 0 and read_roster(df)["badges"]["TMP-01"]["session"] == "local_x", out)
    rc, out = run_f("clock-out", "--by", mf, "--id", "FDR-2", "--result", "lost", at=82)
    expect("the manager does not clock the founder out", rc == 3 and "does not clock the founder out" in out, out)
    rc, out = run_f("amend", "FDR-2", "--by", mf, "--job", "x", at=83)
    expect("a founder badge is not amended", rc == 3 and "no employee badge" in out, out)
    rc, out = run_f("roster", at=90)
    rows = out.splitlines()
    i_f = next((i for i, l in enumerate(rows) if l.startswith("  founder FDR-2 founder-b: UP")), -1)
    i_m = next((i for i, l in enumerate(rows) if l.startswith("  manager MGR-1 mgr-f: UP")), -1)
    expect("the roster shows the founder on its own line above the manager, outside the headcount and the crew rows",
           rc == 0 and 0 <= i_f < i_m and "20%" in rows[i_f] and "auditing the roadmap" in rows[i_f]
           and "crew 1 of 2" in out and "on the clock (0):" in out and "    FDR-2" not in out, out)
    cf = crew(df, t0 + 90)
    expect("crew() names the founder, and the headcount holds neither the founder nor the manager",
           cf["founder"] == "FDR-2" and [b["id"] for b in headcount(cf)] == ["TMP-01"], str(cf["founder"]))
    late_f = next(b for b in crew(df, t0 + 60 + 4 * 3600)["badges"] if b["id"] == "FDR-2")
    expect("a founder is never OVERDUE; silent past the manager's limit it reads STALE",
           late_f["status"] == "STALE" and next(b for b in crew(df, t0 + 60 + 3600)["badges"] if b["id"] == "FDR-2")["status"] == "UP",
           late_f["status"])
    rc, out = run_f("me", "--badge", f2, at=91)
    expect("me for a founder prints its record and the manager, and no employee brief",
           rc == 0 and "FDR-2 founder-b (founder, session)" in out and "manager on the clock: MGR-1" in out
           and "a founder has no brief" in out and "foundry-founder" in out and "--- your brief" not in out, out)
    rc, out = run_f("end-shift", "--by", mf, at=92)
    expect("the manager's end-shift leaves the founder on the clock and out of the crew list",
           rc == 0 and "FDR-2" not in out and next(b for b in crew(df, t0 + 93)["badges"] if b["id"] == "FDR-2")["on"], out)
    rc, out = run_f("found", "--name", "founder-c", "--relieve", at=100)
    f3 = badge_of(out) if rc == 0 else ""
    evf = [e for e in read_events(df) if e["id"] == "FDR-2" and e["ev"] == "out"]
    expect("found --relieve mints FDR-3, clocks the old founder out as relieved and revokes its badge",
           rc == 0 and "FDR-3" in f3 and "FDR-2 relieved" in out and len(evf) == 1 and evf[0]["result"] == "relieved"
           and read_roster(df)["founder"] == "FDR-3" and run_f("verify", f2, at=101)[0] == 3
           and read_roster(df)["manager"] == "MGR-1", out)
    run_f("clock-in", "--badge", f3, at=110)
    rc, out = run_f("clock-out", "--badge", f3, "--result", "done", "--note", "the audit is filed", at=120)
    expect("the founder clocks out", rc == 0 and "FDR-3 founder-c clocked out" in out, out)
    rc, out = run_f("roster", at=130)
    expect("a founder off the clock still has its roster line, as OUT", "  founder FDR-3 founder-c: OUT" in out, out)

    # titles, models, the push rule, the freeze, the round, the hand-off brief and the timers, in an office of
    # their own: a profile with [titles], [models], [flagged] and git.push, and a state with usage, decisions,
    # blockers and a failure
    dT = tmp / "office-titles"
    iso = lambda ts: dt.datetime.fromtimestamp(ts, dt.timezone.utc).isoformat()
    state_t = {"shift": {"id": "t-shift", "crew_max": 12,
                         "blocks": [{"time": "10:00", "title": "build M1", "status": "done", "checkpoint": "C1"},
                                    {"title": "grade G1", "status": "pending", "done_when": "G1 says PASS"}]},
               "rota": {"slots": DEFAULT_SLOTS}, "now": {"headline": "M1 is being built", "tree": "abc1234"},
               "usage": {"stop": 80, "points": [{"at": iso(t0 - 5 * 3600), "weekly": 40}]},
               "decisions": [{"id": "D1", "question": "how many seats", "status": "open"},
                             {"id": "D2", "question": "settled", "status": "decided"}],
               "blockers": [{"what": "the signing key", "owner": "the user"}, {"what": "a slow test", "owner": "EMP-01"}],
               "failures": [{"id": "F1", "what": "G1 VOID on the harness", "status": "open", "owner": "EMP-01", "from": "R999"},
                            {"id": "F2", "what": "old", "status": "fixed"}]}
    (tmp / "state-titles.json").write_text(json.dumps(state_t), encoding="utf-8")
    put(tmp, "titles.toml", prof_head + resource + "[git]\npush = true\n[models]\nscout = \"model-s\"\nfixer = \"model-f\"\n"
        "[flagged.fixer]\nmodel = \"model-flag\"\ntrailer = \"Built-by: model-flag\"\n"
        "[titles.auditor]\nlike = \"reviewer\"\nkinds = [\"session\"]\ndoes = \"audits the release notes\"\n"
        "[titles.broken]\nlike = \"nobody\"\n")

    def run_t(*args, at, profile="titles.toml", state_name="state-titles.json", cwd=tmp, base=None):
        e = {**(base or env), "FOUNDRY_PATHS_OFFICE": str(dT), "FOUNDRY_NOW": str(t0 + at),
             "FOUNDRY_PATHS_STATE": str(tmp / state_name)}
        if profile:
            e["FOUNDRY_PROFILE"] = str(tmp / profile)
        r = subprocess.run([sys.executable, __file__, *args], capture_output=True, text=True, encoding="utf-8",
                           timeout=120, cwd=cwd, env=e)
        return r.returncode, r.stdout + r.stderr

    def hire_t(name, *more, at, kind="temp", **kw):
        return run_t("hire", "--by", mT, "--name", name, "--kind", kind, "--job", f"the job of {name}", "--eta", "30m",
                     *more, at=at, **kw)

    rc, out = run_t("found", "--name", "fdr-t", at=1)
    fT = badge_of(out) if rc == 0 else ""
    rc, out = run_t("appoint", "--name", "mgr-t", "--session", "local_mgr-t", at=2)
    mT = badge_of(out) if rc == 0 else ""
    run_t("clock-in", "--badge", mT, at=3)
    rosterT = lambda: read_roster(dT)["badges"]

    rc, out = hire_t("fix-1", "--title", "fixer", "--files", "src/app/**", at=10)
    fx = badge_of(out) if rc == 0 else ""
    rec_fx = rosterT().get("TMP-01", {})
    expect("hire --title fixer sets the role BUILDER, keeps the title on the roster and prints it",
           rc == 0 and "ROLE:BUILDER" in fx and rec_fx.get("title") == "fixer" and rec_fx.get("role") == "BUILDER"
           and "hired TMP-01 fix-1 (fixer (builder), temp)" in out, out)
    expect("the brief prints the title's card: its role, kinds, what it does, may write and hands in",
           "Your card (fixer): role builder; hired as session or temp" in out and "    Does: fixes one filed failure" in out
           and "    May write: the files its badge owns" in out and "    Hands in: its commits, the failure's id" in out
           and "TMP-01 (fix-1, fixer (builder))" in out, out)
    expect("a flagged title's brief names the model of [flagged], not of [models], and the trailer every commit ends with",
           "Model: model-flag (the manager sets the session to it; say in your first progress note which model you run on)" in out
           and "Model: model-f (" not in out
           and "Every commit of yours ends with the trailer: Built-by: model-flag. Your commits get an in-depth review." in out
           and "  model: model-flag ([flagged.fixer])" in out, out)
    expect("with git.push true the brief says to push only the badge's own branch",
           "git add -- <paths> only; push only your own branch, never the main branch)" in out and "; no push)" not in out, out)
    rc, out = run_t("brief", "TMP-01", "--by", mT, at=11, profile=None)
    expect("with git.push false (the default) the brief says no push, and with no [models] or [flagged] no model or trailer",
           rc == 0 and "git add -- <paths> only; no push)" in out and "Model:" not in out and "trailer" not in out
           and "Your card (fixer)" in out, out)
    n_badges = len(rosterT())
    rc, out = hire_t("x-1", "--title", "plumber", at=12)
    expect("hire refuses an unknown title, lists the known ones (the profile's too) and mints nothing",
           rc == 3 and "the known titles are" in out and all(t in out for t in ("auditor", "builder", "cleaner", "fixer", "grader",
                                                                              "reviewer", "scout", "triager"))
           and len(rosterT()) == n_badges, out)
    rc, out = hire_t("x-2", "--title", "broken", at=13)
    expect("hire refuses a title whose profile card is broken, and says what is wrong with it",
           rc == 3 and "is broken" in out and "names no built-in card" in out and len(rosterT()) == n_badges, out)
    rc, out = hire_t("x-3", "--title", "auditor", at=14)
    rc2, out2 = hire_t("x-4", "--title", "grader", "--lane", "G1", at=14.5)
    expect("hire refuses a kind the title's card does not allow: a profile card's session only, a grader as a temp",
           rc == 3 and "title auditor is hired as session, not as a temp" in out and rc2 == 3 and "independent" in out2
           and len(rosterT()) == n_badges, out + out2)
    rc, out = hire_t("x-5", "--title", "fixer", "--role", "scout", at=15)
    expect("--title with a --role its card does not carry is refused", rc == 3 and "is a BUILDER card" in out
           and len(rosterT()) == n_badges, out)
    rc, out = run_t("hire", "--by", mT, "--name", "x-6", "--kind", "temp", "--job", "j", "--eta", "30m", at=16)
    expect("hire with neither --role nor --title is a usage error (exit 2)", rc == 2 and "--role or --title" in out, out)
    rc, out = hire_t("aud-1", "--title", "auditor", at=17, kind="session")
    rec_au = rosterT().get("EMP-01", {})
    expect("a profile card built like a built-in takes its role and independence and its own text; no model is named for it",
           rc == 0 and rec_au.get("role") == "REVIEWER" and rec_au.get("title") == "auditor"
           and "Your card (auditor): role reviewer; hired as session; independent" in out
           and "    Does: audits the release notes" in out and "    May write: its review file only (under docs/reviews/)" in out
           and "Model:" not in out, out)
    rc, out = hire_t("sc-1", "--role", "scout", at=18)
    rec_sc = rosterT().get("TMP-02", {})
    expect("--role alone hires on the role's own card, prints as before, and reads [models] by the role",
           rc == 0 and rec_sc.get("title") == "scout" and "hired TMP-02 sc-1 (scout, temp)" in out
           and "Your card (scout): role scout" in out and "(sc-1, scout), hired by" in out and "Model: model-s (" in out, out)
    rc, out = hire_t("tri-1", "--title", "triager", at=19)
    expect("a title [models] does not name reads the model of its role",
           rc == 0 and rosterT().get("TMP-03", {}).get("role") == "SCOUT" and "Model: model-s (" in out
           and "Your card (triager)" in out, out)
    n_badges = len(rosterT())
    rc, out = hire_t("fix-2", "--title", "fixer", "--model", "model-other", at=20)
    expect("hiring a flagged title with another --model is refused and mints nothing",
           rc == 3 and "is flagged" in out and "--force-model" in out and len(rosterT()) == n_badges, out)
    rc, out = hire_t("fix-2", "--title", "fixer", "--model", "model-other", "--force-model", at=21)
    expect("--force-model takes it: the brief names that model, the roster keeps it, and the trailer still stands",
           rc == 0 and rosterT().get("TMP-04", {}).get("model") == "model-other" and "Model: model-other (" in out
           and "the trailer: Built-by: model-flag." in out, out)
    rc, out = hire_t("cl-1", "--title", "cleaner", "--model", "model-c", at=22)
    expect("hire --model overrides [models] and is stored", rc == 0 and rosterT().get("TMP-05", {}).get("model") == "model-c"
           and "Model: model-c (" in out and "model-s" not in out, out)
    run_t("clock-in", "--badge", fx, at=30)
    rc, out = run_t("roster", at=31)
    rc2, out2 = run_t("me", "--badge", fx, at=32)
    expect("the roster and me show the title beside the role, and me the model",
           "    TMP-01 fix-1 fixer (builder) temp: UP" in out and "TMP-01 fix-1 (fixer (builder), temp): UP" in out2
           and "your model: model-flag ([flagged.fixer])" in out2 and "Your card (fixer)" in out2, out + out2)
    os.environ["FOUNDRY_PROFILE"] = str(tmp / "titles.toml")
    cards = title_cards()
    expect("title_cards(): seven built-in cards and the profile's over them; a badge from before titles reads as its role",
           set(TITLE_CARDS) == {"builder", "fixer", "grader", "reviewer", "scout", "triager", "cleaner"}
           and cards["grader"]["kinds"] == ["session"] and cards["grader"]["independent"] and cards["reviewer"]["independent"]
           and cards["cleaner"]["role"] == "SCOUT" and cards["fixer"]["role"] == "BUILDER" and cards["auditor"]["like"] == "reviewer"
           and "problem" in cards["broken"] and TITLE_CARDS["reviewer"]["kinds"] == ["session", "temp"]
           and title_of({"role": "SCOUT"}) == "scout" and title_text({"role": "SCOUT"}) == "scout"
           and model_of({"role": "SCOUT"}) == ("model-s", "[models] scout") and push_text().startswith("push only"), str(cards))
    os.environ.pop("FOUNDRY_PROFILE")
    expect("with no [titles], [models] or [flagged] in the profile: the built-in cards, no model, no push",
           set(title_cards()) == set(TITLE_CARDS) and model_of({"role": "SCOUT"}) == ("", "") and flagged_of("fixer") is None
           and push_text() == "no push", str(model_of({"role": "SCOUT"})))

    # handin: a commit of a flagged-title badge without the trailer line is a PROBLEM
    wtf = tmp / "repo-wt-flag"
    g("worktree", "add", "-q", str(wtf), "-b", "claude/fix-f1", "main")
    put(wtf, "src/app/core/fix.py", "B = 2\n")
    g("add", "-A", cwd=wtf)
    g("commit", "-q", "-m", "fix F1", cwd=wtf)
    put(wtf, "fix-report.md", "what the fixer did\n")
    rc, out = run_t("handin", "--badge", fx, "--file", "fix-report.md", at=40, cwd=wtf, base=henv)
    expect("handin makes a flagged title's commit without the trailer a PROBLEM that names the trailer and the commit",
           rc == 1 and "NOT READY" in out and "1 commit(s) lack the trailer line `Built-by: model-flag`" in out
           and g("rev-parse", "--short=8", "HEAD", cwd=wtf) in out, out)
    g("commit", "-q", "--amend", "-m", "fix F1\n\nwhy it broke\n\nBuilt-by: model-flag", cwd=wtf)
    rc, out = run_t("handin", "--badge", fx, "--file", "fix-report.md", at=41, cwd=wtf, base=henv)
    expect("with the trailer line on every commit the same hand-in is READY",
           rc == 0 and "READY (0 problem" in out and "lack the trailer" not in out, out)
    rc, out = run_t("handin", "--badge", fx, "--file", "fix-report.md", at=42, cwd=wtf, base=henv, profile="bare.toml")
    expect("with no [flagged] in the profile no trailer is asked for", rc == 0 and "trailer" not in out, out)

    # the freeze: the manager's, kept in the office, seen by the roster, me and freeze_facts(), with or without a queue
    rc, out = run_t("freeze", "show", at=50)
    expect("freeze show with no freeze says the checkout is open; freeze_facts() says off",
           rc == 0 and "no freeze" in out and freeze_facts(dT, t0 + 50) ==
           {"on": False, "by": None, "why": "", "lane": None, "at": None, "max_s": None, "stale": False}, out)
    n_ev = len(read_events(dT))
    rc, out = run_t("freeze", "on", "--by", fT, "--why", "counted run of G1", at=51)
    rc2, out2 = run_t("freeze", "on", "--by", mT, at=52)
    rc3, out3 = run_t("freeze", "on", "--why", "counted run of G1", at=53)
    rc4, out4 = run_t("freeze", "off", "--by", fT, at=54)
    expect("freeze on refuses a founder's line, a missing --why and a missing --by; off refuses a founder's line; "
           "nothing is written",
           rc == 3 and "founder" in out and rc2 == 3 and "--why" in out2 and rc3 == 3 and "--by" in out3 and rc4 == 3
           and "founder" in out4 and not (dT / FREEZE_FILE).exists() and len(read_events(dT)) == n_ev, out + out2 + out3 + out4)
    rc, out = run_t("freeze", "on", "--by", mT, "--why", "counted run of G1", "--lane", "G1", "--max", "3h", at=60)
    fj = json.loads((dT / FREEZE_FILE).read_text(encoding="utf-8")) if (dT / FREEZE_FILE).exists() else {}
    ev = read_events(dT)[-1]
    expect("freeze on writes freeze.json (by, why, lane, at, max_s) and punches the time clock under the manager",
           rc == 0 and fj == {"by": "MGR-1", "why": "counted run of G1", "lane": "G1", "at": t0 + 60, "max_s": 10800}
           and ev["ev"] == "freeze" and ev["on"] is True and ev["id"] == "MGR-1" and "FREEZE on by MGR-1" in out, out + str(fj))
    fz = freeze_facts(dT, t0 + 61)
    expect("freeze_facts() reports the freeze, and stale once past at + max_s",
           fz == {"on": True, "by": "MGR-1", "why": "counted run of G1", "lane": "G1", "at": t0 + 60, "max_s": 10800, "stale": False}
           and freeze_facts(dT, t0 + 60 + 10801)["stale"] and not freeze_facts(dT, t0 + 60 + 10799)["stale"], str(fz))
    rc, out = run_t("freeze", "on", "--by", mT, "--why", "another", at=62)
    expect("a second freeze on is refused while one is on, and the first stands",
           rc == 3 and "already on" in out and freeze_facts(dT, t0 + 62)["why"] == "counted run of G1", out)
    rc, out = run_t("roster", at=63)
    rc2, out2 = run_t("me", "--badge", fx, at=64)
    rc3, out3 = run_t("me", "--badge", fx, at=64, profile="no-resource.toml")
    rc4, out4 = run_t("freeze", "show", at=65)
    rc5, out5 = run_t("roster", "--json", at=65)
    expect("the roster prints a FREEZE line, me says FREEZE (with no shared resource too), show prints it, roster --json carries it",
           "  FREEZE by MGR-1 since " in out and "lane G1" in out and "counted run of G1" in out
           and "FREEZE: the main checkout is frozen by MGR-1" in out2 and "FREEZE: the main checkout is frozen by MGR-1" in out3
           and rc4 == 0 and out4.startswith("FREEZE by MGR-1") and rc5 == 0 and json.loads(out5)["freeze"]["on"] is True,
           out + out2 + out3 + out4)
    rc, out = run_t("handin", "--badge", fx, "--file", "fix-report.md", at=66, cwd=wtf, base=henv)
    expect("a hand-in during a freeze warns that the main checkout is frozen",
           rc == 0 and "warning  the main checkout is frozen (by MGR-1" in out, out)
    rc, out = run_t("roster", at=60 + 10900)
    expect("past its --max the roster's FREEZE line reads STALE", "STALE? it is past its limit" in out, out)
    rc, out = run_t("freeze", "off", "--by", mT, "--note", "records committed", at=70)
    ev = read_events(dT)[-1]
    rc2, out2 = run_t("freeze", "off", "--by", mT, at=71)
    rc3, out3 = run_t("me", "--badge", fx, at=72, profile="no-resource.toml")
    rc4, out4 = run_t("roster", at=72)
    expect("freeze off removes the file and punches the clock; a second off writes nothing; the roster and me say so no more",
           rc == 0 and not (dT / FREEZE_FILE).exists() and ev["ev"] == "freeze" and ev["on"] is False
           and ev.get("note") == "records committed" and "freeze lifted by MGR-1" in out and rc2 == 0
           and "nothing to lift" in out2 and read_events(dT)[-1] == ev and "FREEZE:" not in out3 and "FREEZE" not in out4
           and "no freeze on the main checkout" in out3, out + out2 + out3 + out4)
    (dT / FREEZE_FILE).write_text("{not json", encoding="utf-8")
    fz = freeze_facts(dT, t0 + 73)
    rc, out = run_t("roster", at=73)
    expect("a freeze.json that cannot be read counts as a freeze in force, and nothing crashes",
           fz["on"] and fz["by"] == "unknown" and "cannot be read" in fz["why"] and rc == 0 and "  FREEZE by unknown" in out, out)
    (dT / FREEZE_FILE).unlink()

    # the round: what needs the manager, most pressing first; it writes only with --by
    rc, out = run_t("fail", "--badge", fx, "--what", "G1 VOID on the rig", "--lane", "G1", "--verdict", "VOID", at=80)
    rid = (re.search(r"reported (R\d+)", out) or [None, "R?"])[1]
    n_ev = len(read_events(dT))
    rc, out = run_t("round", "--json", at=90)
    try:
        rj_ = json.loads(out)
    except ValueError:
        rj_ = {"needs": [], "crew": [], "seats": [], "first": ""}
    kinds = [n["kind"] for n in rj_["needs"]]
    texts = "\n".join(n["text"] for n in rj_["needs"])
    first_of = lambda k: kinds.index(k) if k in kinds else -1
    expect("round --json lists what needs the manager in order: usage, what waits on the user, reports, hand-ins, crew",
           rc == 0 and 0 == first_of("usage") < first_of("decision") < first_of("blocker") < first_of("report")
           < first_of("handin") < first_of("crew") and set(rj_) >= {"needs", "notes", "crew", "seats", "first", "usage", "freeze"},
           out)
    expect("the round names each thing and what to do about it",
           "no usage point in the last 4 hours (the last is 40%" in texts and "board.py usage <percent>" in texts
           and "D1 waits on the user" in texts and "D2 waits" not in texts and "the signing key" in texts and "a slow test" not in texts
           and f"{rid} from TMP-01 is not filed (G1 VOID: G1 VOID on the rig)" in texts and f"fail --from {rid}" in texts
           and "a new hand-in, TMP-01.md (Hand-in TMP-01 fix-1 (fixer (builder)): READY" in texts
           and "EMP-01 aud-1 (auditor (reviewer)) is a session badge with no session" in texts and "assign EMP-01" in texts
           and rj_["first"] == rj_["needs"][0]["text"], texts)
    expect("the round's crew is one line each and the shared resource's seats follow",
           [b["id"] for b in rj_["crew"]] == ["TMP-01", "EMP-01", "TMP-02", "TMP-03", "TMP-04", "TMP-05"]
           and rj_["crew"][0]["text"].startswith("TMP-01 fix-1 fixer (builder) temp: UP")
           and [s["text"] for s in rj_["seats"]] == ["seat main: free", "seat side: free"], str(rj_["crew"]) + str(rj_["seats"]))
    expect("a round without --by writes nothing: no punch, no seen file",
           len(read_events(dT)) == n_ev and not (dT / SEEN_FILE).exists() and rj_.get("wrote") is None, str(rj_.get("wrote")))
    rc, out = run_t("round", at=91)
    expect("the round as text: the numbered needs, the crew, the seats, and a last line `first: ...`",
           rc == 0 and "  needs you (" in out and "    1. [usage] no usage point" in out and "  crew (6):" in out
           and f"  {RES}:" in out and "    seat main: free" in out and "nothing written (no --by)" in out
           and out.rstrip().splitlines()[-1].startswith("first: no usage point in the last 4 hours"), out)
    rc, out = run_t("round", "--by", fT, at=92)
    expect("round refuses a founder's line as --by and writes nothing",
           rc == 3 and "founder" in out and len(read_events(dT)) == n_ev and not (dT / SEEN_FILE).exists(), out)
    run_t("progress", "--badge", mT, "--pct", "35", "--note", "block 1 merged", at=93)
    rc, out = run_t("round", "--by", mT, at=94)
    ev = read_events(dT)[-1]
    seen = json.loads((dT / SEEN_FILE).read_text(encoding="utf-8")) if (dT / SEEN_FILE).exists() else {}
    expect("round --by posts the manager's heartbeat (a progress punch, pct unchanged) and marks the listed hand-ins seen",
           rc == 0 and ev["ev"] == "progress" and ev["id"] == "MGR-1" and ev["pct"] == 35 and ev["note"].startswith("round:")
           and list(seen.get("seen", {})) == ["TMP-01.md"] and seen.get("by") == "MGR-1"
           and "posted MGR-1's heartbeat; marked seen: TMP-01.md" in out and "a new hand-in, TMP-01.md" in out, out)
    rc, out = run_t("round", at=95)
    expect("a hand-in marked seen is not listed again", rc == 0 and "a new hand-in" not in out, out)
    rc, out = run_t("handin", "--badge", fx, "--file", "fix-report.md", at=96, cwd=wtf, base=henv)
    rc, out = run_t("round", at=97)
    expect("a hand-in written again after it was seen is new again", rc == 0 and "a new hand-in, TMP-01.md" in out, out)
    over = json.loads(json.dumps(state_t))
    over["usage"]["points"].append({"at": iso(t0 + 98), "weekly": 85})
    (tmp / "state-titles-over.json").write_text(json.dumps(over), encoding="utf-8")
    rc, out = run_t("round", at=99, state_name="state-titles-over.json")
    expect("usage at or past the stop is the first thing, and a fresh point is not asked for again",
           "    1. [usage] usage 85% is at or past the stop at 80%: start no new work" in out
           and "no usage point in the last" not in out and out.rstrip().splitlines()[-1].startswith("first: usage 85%"), out)
    run_t("freeze", "on", "--by", mT, "--why", "counted run of G2", "--max", "30m", at=100)
    rc, out = run_t("round", "--json", at=101)
    rc2, out2 = run_t("round", "--json", at=100 + 1900)
    fr1 = [n for n in json.loads(out)["needs"] if n["kind"] == "freeze"]
    fr2 = [n for n in json.loads(out2)["needs"] if n["kind"] == "freeze"]
    expect("a freeze in force is listed to know, not to act on; past its limit it is one to act on",
           len(fr1) == 1 and fr1[0]["act"] is False and "a freeze is in force by MGR-1" in fr1[0]["text"]
           and len(fr2) == 1 and fr2[0]["act"] is True and "STALE?" in fr2[0]["text"] and "freeze off" in fr2[0]["text"],
           str(fr1) + str(fr2))
    run_t("freeze", "off", "--by", mT, at=102)
    (dT / "rq.lock").mkdir()
    (dT / "rq.lock" / "hold.json").write_text(json.dumps({"id": "MGR-1-counted-G1", "job": "counted G1", "since": t0 + 103,
                                                          "max": 600, "all": True, "prio": 0}), encoding="utf-8")
    rc, out = run_t("round", "--json", at=110)
    rc2, out2 = run_t("round", "--json", at=110 + 700)
    cr1 = [n for n in json.loads(out)["needs"] if n["kind"] == "counted"]
    cr2 = [n for n in json.loads(out2)["needs"] if n["kind"] == "counted"]
    expect("a counted run in the queue is listed to know; one whose hold is past its limit looks dead and is to act on",
           len(cr1) == 1 and cr1[0]["act"] is False and "MGR-1-counted-G1 is in the queue" in cr1[0]["text"]
           and len(cr2) == 1 and cr2[0]["act"] is True and "looks dead" in cr2[0]["text"] and "force-release" in cr2[0]["text"]
           and json.loads(out)["seats"][0]["text"].startswith("seat main: MGR-1-counted-G1 since "), str(cr1) + str(cr2))
    shutil.rmtree(dT / "rq.lock")

    # the hand-off brief: Markdown, filled from the office and the state, three sections left to the manager
    run_t("assign", "TMP-01", "--session", "local_fix", at=119)
    n_ev = len(read_events(dT))
    rc, out = run_t("handoff", "--by", fT, at=120)
    expect("handoff refuses a founder's line and writes nothing",
           rc == 3 and "founder" in out and not (dT / "briefs").exists() and len(read_events(dT)) == n_ev, out)
    run_t("freeze", "on", "--by", mT, "--why", "counted run of G3", at=121)
    rc, out = run_t("handoff", "--by", mT, at=122)
    ho = Path(out.splitlines()[0].strip()) if rc == 0 and out.strip() else tmp / "none"
    slot_t = rosterT()["MGR-1"]["slot"]
    md = ho.read_text(encoding="utf-8") if ho.is_file() else ""
    expect("handoff writes <office>/briefs/handoff-<slot>-<YYYYMMDD>.md and prints its path first",
           rc == 0 and ho.parent == dT / "briefs" and ho.name == f"handoff-{slot_t}-{local(t0 + 122):%Y%m%d}.md" and md, out)
    expect("the hand-off brief carries the state's now, the shift's blocks with their status, and every badge on the clock",
           "- headline: M1 is being built" in md and "- tree: abc1234" in md and "## Shift t-shift (crew_max 12)" in md
           and "- [done] 10:00 build M1 (checkpoint C1)" in md and "- [pending] grade G1; done when: G1 says PASS" in md
           and "- MGR-1 mgr-t, manager, session, session local_mgr-t: " in md
           and "- TMP-01 fix-1, fixer (builder), temp, session local_fix: the job of fix-1; " in md and "%, finish ~" in md
           and "- hired, not clocked in: EMP-01 aud-1 (auditor (reviewer))" in md and "\nBenches: \n" in md, md)
    expect("the hand-off brief lists open failures with status and owner, open decisions, the freeze, the journal and usage",
           "## Open failures (1)" in md and "- F1 open, owner EMP-01: G1 VOID on the harness" in md and "- F2" not in md
           and f"- reports not filed yet: {rid}" in md and "## Open decisions (1)" in md and "- D1: how many seats" in md
           and "- FREEZE by MGR-1 since " in md and "counted run of G3" in md and "## Journal" in md
           and "## Usage" in md and "- 40% at " in md and "the stop is 80%" in md, md)
    heads = ["## The user's words this slot (quoted, with the time)", "## Promised to the crew",
             "## Background jobs this session started"]
    expect("the hand-off brief ends with three sections for the manager to fill, each with one line saying what goes there",
           all(h in md for h in heads) and md.count("_Fill by hand: ") == 4
           and md.index(heads[0]) < md.index(heads[1]) < md.index(heads[2]), md[-900:])
    rc, out = run_t("handoff", "--by", mT, at=123)
    ho2 = Path(out.splitlines()[0].strip()) if rc == 0 and out.strip() else tmp / "none"
    expect("a second handoff never overwrites: it writes <name>-2.md and leaves the first as it was",
           rc == 0 and ho2.name == ho.stem + "-2.md" and ho2.is_file() and ho.read_text(encoding="utf-8") == md, out)
    rc, out = run_t("handoff", "--by", mT, "--out", str(tmp / "my-handoff.md"), at=124)
    rc2, out2 = run_t("handoff", "--by", mT, "--out", str(tmp / "my-handoff.md"), at=125)
    rc3, out3 = run_t("handoff", "--by", mT, "--out", str(tmp / "no-such-folder" / "h.md"), at=126)
    expect("handoff --out writes the named file, a second call beside it as -2, and a missing folder is refused",
           rc == 0 and (tmp / "my-handoff.md").is_file() and rc2 == 0 and (tmp / "my-handoff-2.md").is_file()
           and rc3 == 3 and "folder does not exist" in out3, out + out2 + out3)
    run_t("freeze", "off", "--by", mT, at=127)

    # a freeze.json with an odd number holds (ON, by unknown, the reason in why) and nothing that prints it crashes
    odd_ok, odd_out = True, ""
    for label, text in (("at in milliseconds", '{"by": "MGR-1", "why": "w", "at": 1790000000000, "max_s": 60}'),
                        ("at 1e999", '{"by": "MGR-1", "why": "w", "at": 1e999, "max_s": 60}'),
                        ("at NaN", '{"by": "MGR-1", "why": "w", "at": NaN}'),
                        ("at below zero", '{"by": "MGR-1", "why": "w", "at": -5}'),
                        ("at true", '{"by": "MGR-1", "why": "w", "at": true}'),
                        ("at a list", '{"by": "MGR-1", "why": "w", "at": [1]}'),
                        ("nested past the reader's depth", '{"at": ' + "[" * 200000 + "]" * 200000 + "}"),
                        ("max_s 1e999", '{"by": "MGR-1", "why": "w", "at": %r, "max_s": 1e999}' % (t0 + 127),),
                        ("max_s below zero", '{"by": "MGR-1", "why": "w", "at": %r, "max_s": -1}' % (t0 + 127),),
                        ("max_s a word", '{"by": "MGR-1", "why": "w", "at": %r, "max_s": "long"}' % (t0 + 127),)):
        (dT / FREEZE_FILE).write_text(text, encoding="utf-8")
        try:
            fz = freeze_facts(dT, t0 + 127.5)
            line = freeze_text(fz, t0 + 127.5)
        except Exception as e:  # the case is that there is none
            fz, line = {}, f"{type(e).__name__}: {e}"
        outs = [run_t("roster", at=127.5), run_t("me", "--badge", fx, at=127.5), run_t("round", at=127.5),
                run_t("freeze", "show", at=127.5), run_t("freeze", "show", "--json", at=127.5),
                run_t("handoff", "--by", mT, "--out", str(tmp / "odd-handoff.md"), at=127.5)]
        good = (fz.get("on") is True and fz.get("by") == "unknown" and "cannot be read" in fz.get("why", "")
                and fz.get("at") is None and line.startswith("by unknown")
                and all(rc_ == 0 and "Traceback" not in o_ for rc_, o_ in outs) and "FREEZE by unknown" in outs[0][1]
                and "frozen by unknown" in outs[1][1] and "FREEZE by unknown" in outs[3][1])
        if not good:
            odd_ok, odd_out = False, odd_out + f"\n{label}: {fz} {line}\n" + "\n".join(o_[-400:] for _, o_ in outs)
    (dT / FREEZE_FILE).unlink()
    expect("a freeze.json whose at or max_s is not a sane time or length reads as ON by unknown, and the roster, me, "
           "round, handoff and freeze show print it without a traceback", odd_ok, odd_out)
    try:
        bad_line = freeze_text({"on": True, "by": "MGR-1", "why": "w", "lane": None, "at": 1.79e12, "max_s": float("inf"),
                                "stale": False}, t0 + 127.5)
    except Exception as e:
        bad_line = f"{type(e).__name__}: {e}"
    expect("freeze_text() says a time it cannot show instead of raising",
           bad_line.startswith("by MGR-1 since a time that cannot be shown") and "limit cannot be shown" in bad_line, bad_line)
    try:
        u_text = [usage_text({"stop": "eighty", "last": None, "at": None}, t0), usage_text({"stop": None, "last": 40.0, "at": t0 - 60}, t0),
                  usage_text(usage_facts({"usage": {"stop": "x"}}, t0), t0)]
    except Exception as e:
        u_text = [f"{type(e).__name__}: {e}"]
    expect("a usage stop that is not a number is said, not formatted",
           len(u_text) == 3 and u_text[0] == "no usage point recorded; the stop is not a number"
           and u_text[1].startswith("40% at ") and u_text[1].endswith("the stop is not a number")
           and u_text[2] == "no usage point recorded; the stop is 80%", str(u_text))
    # freeze --max takes a unit, as rq.py and sweep.py do; --eta alone still reads a bare number as minutes
    rc, out = run_t("freeze", "on", "--by", mT, "--why", "counted run of G3", "--max", "180", at=128)
    rc2, out2 = run_t("freeze", "on", "--by", mT, "--why", "counted run of G3", "--max", "1h30", at=128)
    rc3, out3 = run_t("hire", "--help", at=128)
    rc4, out4 = run_t("progress", "--help", at=128)
    try:
        durs = (parse_dur("45"), parse_dur("1h30"), parse_dur("30m", unit=True), parse_dur("1h30m", unit=True), parse_dur("3h", unit=True))
    except Refused as e:
        durs = str(e)
    expect("freeze on --max refuses a bare number and names the units; hire and progress say --eta still reads one as minutes",
           rc == 3 and "write a unit: 30m, 3h" in out and rc2 == 3 and "cannot read the duration" in out2
           and not (dT / FREEZE_FILE).exists() and "bare number as minutes" in " ".join(out3.split())
           and "bare number as minutes" in " ".join(out4.split()) and durs == (2700, 5400, 1800, 5400, 10800),
           out + out2 + str(durs))
    # a counted sweep's own freeze is not lifted under it without --force
    n_ev = len(read_events(dT))
    sweep_ok, sweep_out = True, ""
    for by_, why_ in (("MGR-1-sweep", "counted sweep"), ("MGR-1-counted-G1", "a run"), ("MGR-1", "Counted sweep of 3 lanes")):
        (dT / FREEZE_FILE).write_text(json.dumps({"by": by_, "why": why_, "lane": None, "at": t0 + 128, "max_s": 3600}),
                                      encoding="utf-8")
        rc, out = run_t("freeze", "off", "--by", mT, at=128.5)
        if not (rc == 3 and "sweep.py" in out and " status" in out and "--force" in out and "may still be running" in out
                and (dT / FREEZE_FILE).exists() and len(read_events(dT)) == n_ev):
            sweep_ok, sweep_out = False, sweep_out + f"\n{by_}/{why_}: {rc} {out}"
    rc, out = run_t("freeze", "off", "--by", mT, "--force", "--note", "the sweep's session died", at=129)
    ev = read_events(dT)[-1]
    expect("freeze off refuses a counted sweep's freeze (by its why or its id) and names sweep.py status; --force lifts it",
           sweep_ok and rc == 0 and not (dT / FREEZE_FILE).exists() and ev["ev"] == "freeze" and ev["on"] is False
           and "freeze lifted by MGR-1" in out, sweep_out + out)
    # an earlier hand-in kept as <id>.<n>.md is not a new hand-in
    live_before = [h["file"] for h in new_handins(dT)[0]]
    (dT / "handins").mkdir(parents=True, exist_ok=True)
    (dT / "handins" / "TMP-01.1.md").write_text("# Hand-in TMP-01 fix-1 (fixer (builder)): READY\n", encoding="utf-8")
    (dT / "handins" / "TMP-77.md").write_text("# Hand-in TMP-77 x (builder): READY\n", encoding="utf-8")
    new_, stamps_ = new_handins(dT)
    rc, out = run_t("round", at=129.5)
    expect("the round lists only the live <id>.md hand-ins, never an archived <id>.<n>.md",
           [h["file"] for h in new_] == sorted(live_before + ["TMP-77.md"]) and "TMP-01.1.md" not in stamps_
           and "TMP-77.md" in out and "TMP-01.1.md" not in out, str(new_) + out)
    (dT / "handins" / "TMP-01.1.md").unlink()
    (dT / "handins" / "TMP-77.md").unlink()
    head_ = (dT / "handins" / "TMP-01.md").read_text(encoding="utf-8").split("\n", 1)[0] if (dT / "handins" / "TMP-01.md").is_file() else ""
    expect("the hand-in file's heading shows the title as the roster does", head_.startswith("# Hand-in TMP-01 fix-1 (fixer (builder)): "), head_)
    rc, out = run_t("brief", "TMP-01", "--by", mT, at=129.6, profile="no-resource.toml")
    rc2, out2 = run_t("brief", "TMP-01", "--by", mT, at=129.6)
    expect("with no shared resource the brief says a counted run shows as FREEZE in `office.py me`",
           rc == 0 and "While a counted run is going (you see it as FREEZE in `" in out and " me`)" in out
           and "the manager says when" not in out and rc2 == 0 and "the roster says COUNTED SWEEP" in out2, out)

    # the manager's timer list: a file the tool writes and checks; it creates no timer
    tf_ = dT / TIMERS_FILE
    rc, out = run_t("timers", "show", at=130)
    rc2, out2 = run_t("timers", "init", "--by", fT, at=131)
    rc3, out3 = run_t("timers", "init", at=132)
    expect("timers show with no file exits 1 and names init; init refuses a founder's line and a missing --by",
           rc == 1 and "timers init" in out and rc2 == 3 and "founder" in out2 and rc3 == 3 and not tf_.exists(), out + out2 + out3)
    rc, out = run_t("timers", "init", "--by", mT, at=133)
    tj_ = json.loads(tf_.read_text(encoding="utf-8")) if tf_.exists() else {"timers": []}
    by_name = {t.get("name"): t for t in tj_["timers"]}
    expect("timers init writes the round and each slot's hand-off (40 min before its end) and start, from the rota and the "
           "manager skill's name",
           rc == 0 and list(by_name) == ["round", "handoff-day", "start-day", "handoff-swing", "start-swing", "handoff-night",
                                         "start-night"]
           and by_name["round"] == {"name": "round", "recurring": True, "every": "2h",
                                    "prompt": "/foundry-manager status, then the round"}
           and by_name["handoff-day"] == {"name": "handoff-day", "recurring": True, "at": "13:20",
                                          "prompt": "/foundry-manager shift-change"}
           and by_name["handoff-night"]["at"] == "05:20" and by_name["handoff-swing"]["at"] == "21:20"
           and by_name["start-swing"] == {"name": "start-swing", "recurring": True, "at": "14:00",
                                          "prompt": "/foundry-manager start"}, out + str(tj_))
    expect("timers init says the tool creates no timer", "the manager creates them in its session: this file is the list" in out, out)
    body = tf_.read_text(encoding="utf-8") if tf_.exists() else ""
    rc, out = run_t("timers", "init", "--by", mT, at=134)
    rc2, out2 = run_t("timers", "show", at=135)
    expect("a second timers init leaves the file as it is; show prints it and finds its shape right (exit 0)",
           rc == 0 and "already there" in out and tf_.read_text(encoding="utf-8") == body and rc2 == 0
           and "7 timers, the shape is right" in out2 and "    handoff-day: at 13:20, recurring: /foundry-manager shift-change" in out2
           and "the manager creates them in its session: this file is the list" in out2, out + out2)
    tj_["timers"] += [{"name": "odd", "recurring": "yes", "prompt": "x"}, {"recurring": True, "at": "25:00", "prompt": ""}, 7,
                      {"name": "late", "recurring": False, "every": "soon", "prompt": "p"}]
    tf_.write_text(json.dumps(tj_), encoding="utf-8")
    rc, out = run_t("timers", "show", at=136)
    expect("timers show exits 1 and names each bad entry and what is wrong with it",
           rc == 1 and "BAD entry 8 (odd): recurring is not true or false, neither every nor at" in out
           and "BAD entry 9 (unnamed): no name, at '25:00' is not a clock time (HH:MM), no prompt" in out
           and "BAD entry 10: not an object" in out and "BAD entry 11 (late): every 'soon' is not a duration" in out
           and "BAD entry 1 " not in out, out)
    tf_.write_text("[1, 2]", encoding="utf-8")
    rc, out = run_t("timers", "show", at=137)
    expect("a timers file of another shape is named as such (exit 1)", rc == 1 and 'not {"timers": [...]}' in out, out)

    # a quiet office with no shared resource: nothing needs the manager; then no state file at all
    dq = tmp / "office-quiet"
    _, q0, q1 = slot_at(DEFAULT_SLOTS, t0 + 86400)

    def run_q(*args, ts, state_name="state-quiet.json"):
        r = subprocess.run([sys.executable, __file__, *args], capture_output=True, text=True, encoding="utf-8", timeout=120,
                           cwd=tmp, env={**env, "FOUNDRY_PATHS_OFFICE": str(dq), "FOUNDRY_NOW": str(ts),
                                         "FOUNDRY_PATHS_STATE": str(tmp / state_name),
                                         "FOUNDRY_PROFILE": str(tmp / "no-resource.toml")})
        return r.returncode, r.stdout + r.stderr

    quiet = {"shift": {"id": "q-shift", "crew_max": 2}, "usage": {"points": [{"at": iso(q0 + 500), "weekly": 10}]}}
    (tmp / "state-quiet.json").write_text(json.dumps(quiet), encoding="utf-8")
    rc, out = run_q("appoint", "--name", "mgr-q", "--this-slot", ts=q0 + 600)
    mq = badge_of(out) if rc == 0 else ""
    run_q("clock-in", "--badge", mq, ts=q0 + 610)
    rc, out = run_q("round", "--by", mq, ts=q0 + 700)
    expect("in a quiet office with no shared resource the round lists nothing, prints no seat, and says to end the turn",
           rc == 0 and "  needs you: nothing" in out and "crew: nobody hired or on the clock" in out and "seat " not in out
           and "usage: 10% at " in out and out.rstrip().splitlines()[-1] == "first: nothing needs you; end the turn", out)
    quiet["usage"]["points"][0]["weekly"] = 80
    (tmp / "state-quiet-over.json").write_text(json.dumps(quiet), encoding="utf-8")
    rc, out = run_q("round", ts=q0 + 701, state_name="state-quiet-over.json")
    expect("with no stop in the state the round reads limits.usage_stop from the profile",
           rc == 0 and "usage 80% is at or past the stop at 80%" in out, out)
    if (tools_here / "journal.py").is_file():
        quiet["usage"]["points"] = [{"at": iso(q1 - 2000), "weekly": 10}]
        (tmp / "state-quiet-late.json").write_text(json.dumps(quiet), encoding="utf-8")
        rc, out = run_q("round", "--json", ts=q1 - 1800, state_name="state-quiet-late.json")
        try:
            needs_q = json.loads(out)["needs"]
        except ValueError:
            needs_q = []
        expect("inside the last hour of the shift the round says the journal's plan is due and how to make it ready",
               rc == 0 and [n["kind"] for n in needs_q] == ["journal"] and "journal.py" in needs_q[0]["text"]
               and " ready`" in needs_q[0]["text"], out)
    else:
        print("  skip the round's journal case: no journal.py beside office.py")
    n_ev = len(read_events(dq))
    rc, out = run_q("round", ts=q0 + 710, state_name="no-such-state.json")
    rc2, out2 = run_q("handoff", "--by", mq, ts=q0 + 711, state_name="no-such-state.json")
    hq = Path(out2.splitlines()[0].strip()) if rc2 == 0 and out2.strip() else tmp / "none"
    mdq = hq.read_text(encoding="utf-8") if hq.is_file() else ""
    rc3, out3 = run_q("timers", "init", "--by", mq, ts=q0 + 712, state_name="no-such-state.json")
    rc4, out4 = run_q("freeze", "on", "--by", mq, "--why", "counted run of G1", ts=q0 + 713, state_name="no-such-state.json")
    rc5, out5 = run_q("roster", ts=q0 + 714, state_name="no-such-state.json")
    expect("with no state file the round, the hand-off and the timers each say what is missing, and nothing crashes",
           rc == 0 and "note: no state file (" in out and "board.py" in out and "first: " in out
           and rc2 == 0 and "**Missing:** no state file (" in mdq and "- not read (no state)" in mdq
           and "## The user's words this slot" in mdq
           and rc3 == 0 and "the profile's: there is no state file" in out3 and (dq / TIMERS_FILE).is_file()
           and "Traceback" not in out + out2 + out3 + out4 + out5, out + out2 + out3)
    expect("with no shared resource and no state file a freeze still holds: the roster prints its FREEZE line",
           rc4 == 0 and rc5 == 0 and "  FREEZE by MGR-1 since " in out5 and freeze_facts(dq, q0 + 715)["on"], out4 + out5)

    # concurrent punches under the lock lose nothing
    d = Path(env["FOUNDRY_PATHS_OFFICE"])
    before = len(read_events(d))
    procs = [subprocess.Popen([sys.executable, __file__, "_stress", "40"], env={**env, "FOUNDRY_NOW": str(t0 + 9000)})
             for _ in range(6)]
    for p in procs:
        p.wait(timeout=120)
    evs = read_events(d)
    seqs = [e["seq"] for e in evs]
    expect("240 concurrent appends all land, numbered once each",
           len(evs) - before == 240 and seqs == list(range(1, len(evs) + 1)), f"{len(evs) - before} landed")

    # the roster's JSON names a plate only when the file is there (no segno, no plate: null)
    plates = [b["plate"] for b in crew(d)["badges"]]
    gone = d / "badges" / "EMP-01.svg"
    held = gone.read_bytes() if gone.is_file() else None
    if held is not None:
        gone.unlink()
    p_gone = next((b["plate"] for b in crew(d)["badges"] if b["id"] == "EMP-01"), "absent")
    if held is not None:
        gone.write_bytes(held)
    expect("the roster's JSON gives a badge's plate as null when the file is not there, never a path that does not exist",
           bool(plates) and all(p is None or Path(p).is_file() for p in plates) and p_gone is None
           and (any(plates) if HAVE_SEGNO else not any(plates)), str(plates) + str(p_gone))

    # the plate: deterministic, and the line round-trips through parse into the same plate
    roster = read_roster(d)
    rec = roster["badges"]["EMP-01"]
    fields, _ = parse_line(rec["line"])
    rebuilt = make_line(load_key(d), {k: fields[k] for k in FIELDS})
    expect("the line round-trips through parse into the same line", rebuilt == rec["line"])
    p1 = plate(d, rec)
    if p1 is None:  # segno is optional: every case above ran without a plate
        print("  skip the plate is an SVG (segno is not installed)")
    else:
        svg1 = p1.read_text(encoding="utf-8")
        svg2 = plate(d, {**rec, "line": rebuilt}).read_text(encoding="utf-8")
        expect("the plate is an SVG and the same line draws the same plate", svg1.startswith("<svg") and svg1 == svg2)

    for x in ok:
        print(f"  ok   {x}")
    for x in bad:
        print(f"  FAIL {x}")
    print(f"office selftest: {len(ok)} ok, {len(bad)} failed" + (f" (scratch kept: {tmp.as_posix()})" if bad else ""))
    if not bad:
        def unlock(fn, path, _exc):  # git writes its objects read-only, which some systems will not delete
            try:
                os.chmod(path, 0o700)
                fn(path)
            except OSError:
                pass
        shutil.rmtree(tmp, **({"onexc": unlock} if sys.version_info >= (3, 12) else {"onerror": unlock}))
    return 1 if bad else 0


def stress(n):
    d = office_dir()
    for i in range(n):
        with locked(d):
            append_event(d, {"at": now_ts(), "id": "STRESS", "ev": "progress", "pct": i})


def main(argv):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # some consoles default to a code page
    if len(argv) > 1 and argv[1] == "selftest":
        return selftest()
    if len(argv) > 2 and argv[1] == "_stress":
        stress(int(argv[2]))
        return 0
    p = argparse.ArgumentParser(prog="office.py", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("found", help="mint the one founder badge")
    s.add_argument("--name", required=True)
    s.add_argument("--relieve", action="store_true", help="replace a founder badge that is on the clock")
    s.add_argument("--session")
    s = sub.add_parser("appoint")
    s.add_argument("--name", required=True)
    s.add_argument("--relieve", action="store_true")
    s.add_argument("--session")
    which = s.add_mutually_exclusive_group()  # --slot with --this-slot is an error, not a silent pick
    which.add_argument("--this-slot", action="store_true",
                       help="keep the current slot even within APPOINT_LEAD_S of the next one")
    which.add_argument("--slot", help="the slot this manager is for (day, swing, night): the slot now, or the next one "
                                      "in the last hour before it starts")
    s = sub.add_parser("hire")
    for k in ("--by", "--name", "--kind", "--job"):
        s.add_argument(k, required=True)
    s.add_argument("--eta", required=True, help="how long the job should take (90m, 2h, 1h30m); --eta alone still "
                                                "reads a bare number as minutes (freeze --max refuses one)")
    s.add_argument("--role", help="builder, grader, reviewer or scout (or give --title, which sets the role)")
    s.add_argument("--title", help="the card the badge is hired on: builder, fixer, grader, reviewer, scout, triager, "
                                   "cleaner, or one the profile adds under [titles]")
    s.add_argument("--model", help="the model id the brief names, in place of the profile's [models] or [flagged]")
    s.add_argument("--force-model", action="store_true",
                   help="take --model for a flagged title whose [flagged] table names another model")
    for k in ("--lane", "--seat", "--files", "--done-when"):
        s.add_argument(k)
    s.add_argument("--rq", action="store_true")
    s.add_argument("--force-files", action="store_true", help="keep a --files pattern whose folder does not exist yet")
    s.add_argument("--adr", action="store_true",
                   help="reserve the next ADR number from the office's one counter and print it in the brief")
    s = sub.add_parser("assign")
    s.add_argument("id")
    s.add_argument("--session", required=True)
    s.add_argument("--by", help="the manager's line (optional; a founder's line is refused)")
    s.add_argument("--dry-run", action="store_true",
                   help="list the badges and lanes the session has held, and say if assign would be refused; write nothing")
    s = sub.add_parser("amend")
    s.add_argument("id")
    s.add_argument("--by", required=True)
    for k in ("--job", "--add-files", "--set-files", "--done-when", "--eta", "--seat"):
        s.add_argument(k)
    s.add_argument("--rq", action="store_true")
    s.add_argument("--force-files", action="store_true", help="keep a --files pattern whose folder does not exist yet")
    s = sub.add_parser("brief", help="reprint a badge's line and brief (the manager)")
    s.add_argument("id")
    s.add_argument("--by", required=True)
    s = sub.add_parser("clock-in")
    s.add_argument("--badge", required=True)
    s = sub.add_parser("progress")
    s.add_argument("--badge", required=True)
    s.add_argument("--pct", type=int, required=True)
    s.add_argument("--eta", help="the approximate finish: a clock time (17:50) or a length from now (40m, 2h); --eta "
                                 "alone still reads a bare number as minutes (freeze --max refuses one)")
    s.add_argument("--note")
    s.add_argument("--waiting-on")
    s.add_argument("--run")
    for name in ("me", "status"):  # `status` is what sessions guess; without a badge it is the roster
        s = sub.add_parser(name)
        s.add_argument("--badge", required=name == "me")
        if name == "status":
            s.add_argument("--json", action="store_true", help="the roster as JSON (without --badge)")
    s = sub.add_parser("runs")
    s.add_argument("--id")
    s = sub.add_parser("handin")
    s.add_argument("--badge", required=True)
    s.add_argument("--base", help="the branch you were cut from (default: the profile's main_branch)")
    s.add_argument("--commits")
    s.add_argument("--file")
    s.add_argument("--repo", help="the checkout to check (default: the current directory)")
    s.add_argument("--by", help="the manager's line, when the manager runs the check for an employee")
    s = sub.add_parser("fail")
    s.add_argument("--badge", required=True)
    s.add_argument("--what", required=True)
    for k in ("--lane", "--run-id", "--verdict", "--plan"):
        s.add_argument(k)
    s = sub.add_parser("clock-out")
    s.add_argument("--badge")
    s.add_argument("--by")
    s.add_argument("--id")
    s.add_argument("--result", required=True)
    s.add_argument("--note")
    s.add_argument("--commits")
    s = sub.add_parser("roster")
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("end-shift")
    s.add_argument("--by", required=True)
    s.add_argument("--lose-temps", action="store_true")
    s.add_argument("--out", help="also write the log entry's crew list as JSON to this file")
    s = sub.add_parser("freeze", help="hold the main checkout still for a counted run (on, off: the manager; show: anyone)")
    s.add_argument("action", choices=("on", "off", "show"))
    s.add_argument("--by", help="the manager's line (on and off)")
    s.add_argument("--why", help="on: the run the freeze covers")
    s.add_argument("--lane", help="on: the lane being counted")
    s.add_argument("--max", help="on: how long the freeze should last at most, with its unit (3h, 90m; a bare "
                                 "number is refused); past it the freeze reads STALE")
    s.add_argument("--force", action="store_true", help="off: lift a freeze a counted sweep set while it may still run")
    s.add_argument("--note", help="off: a word for the time clock")
    s.add_argument("--json", action="store_true", help="show: freeze_facts as JSON")
    s = sub.add_parser("round", help="the manager's wake-up: what needs the manager first, the crew, the seats")
    s.add_argument("--by", help="the manager's line: also posts the heartbeat and marks the listed hand-ins seen")
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("handoff", help="write the next manager's hand-off brief (Markdown)")
    s.add_argument("--by", required=True)
    s.add_argument("--out", help="the file to write (default: <office>/briefs/handoff-<slot>-<YYYYMMDD>.md)")
    s = sub.add_parser("timers", help="the manager's timer list: init writes it, show prints and checks it")
    s.add_argument("action", choices=("init", "show"))
    s.add_argument("--by", help="the manager's line (init)")
    s = sub.add_parser("verify")
    s.add_argument("line")
    s = sub.add_parser("badge")
    s.add_argument("id")
    a = p.parse_args(argv[1:])
    if a.cmd == "clock-out" and not (a.badge or a.by):
        p.error("clock-out needs --badge (your own) or --by and --id (the manager)")
    if a.cmd == "hire" and not (a.role or a.title):
        p.error("hire needs --role or --title")
    fn = {"found": cmd_found, "appoint": cmd_appoint, "hire": cmd_hire, "assign": cmd_assign, "amend": cmd_amend, "brief": cmd_brief,
          "clock-in": cmd_clock_in, "progress": cmd_progress,
          "fail": cmd_fail, "clock-out": cmd_clock_out, "roster": cmd_roster, "end-shift": cmd_end_shift,
          "verify": cmd_verify, "badge": cmd_badge, "me": cmd_me, "runs": cmd_runs, "handin": cmd_handin,
          "freeze": cmd_freeze, "round": cmd_round, "handoff": cmd_handoff, "timers": cmd_timers,
          "status": cmd_me if getattr(a, "badge", None) else cmd_roster}[a.cmd]
    try:
        return fn(a, office_dir(), now_ts())
    except Refused as e:
        print(f"refused: {e}", file=sys.stderr)
        return getattr(e, "code", 3)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
