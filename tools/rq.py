#!/usr/bin/env python3
"""The crew's resource queue: a fair queue over the seats of the one shared resource (a VM, a GPU, a test device,
a licence). One job holds a seat at a time.

The resource and its seats are named in the profile ([resource] name, seats). The file rq.seats in the office, one
seat per line, overrides the profile's list when present. The first seat (the first of the profile's
resource.seats) uses the office files rq.lock and rq.last; another seat S uses rq.lock.S and rq.last.S.

  rq.py run --id EMP-07 --job "unit tests + lint" --touched "src/app src/core" [--prio 5] [--max 30m] [--wait 4h]
            [--seat NAME | --all-seats] [--exclusive] [--no-prepare] [--enforce-max] -- <command>
      The preferred way. Queues for any free seat, runs the profile's resource.prepare line there (if one is set),
      runs <command> (a shell command line) with the seat's name in the variable resource.seat_env names (default
      FOUNDRY_SEAT), then releases the seat with an rq.last note naming --touched, whatever the command's exit.
      Exits with the command's exit code.
  rq.py take --id EMP-07 --job "..." [--prio 5] [--max 30m] [--wait 4h] [--seat NAME]
      By hand: blocks until this id holds the first seat (or --seat), then prints that seat's rq.last. Work in that
      seat only, and release when done. Exit 6: --wait passed, not taken.
  rq.py release --id EMP-07 --note "what ran" --touched "src/app src/core"
  rq.py leave --id EMP-07              take a waiter out of the queue; its waiting process exits 6 at its next poll
                                       (a hold is freed with release, or force-release by the manager)
  rq.py status [--resource] [--json]   (--resource also runs the profile's resource.status command and prints what
                                       it says: the resource's own health, read without taking a seat; --json
                                       prints one JSON object for other tools, see below)
  rq.py force-release --by MGR-01 --note "why" [--seat NAME]      (the manager only)
  rq.py selftest                       the rules below, on scratch seats in a temp folder

Order: lower --prio first, then first come; a waiter older than 90 minutes ranks at prio 2 (written into the queue so
every waiter agrees), so no one starves. 0 counted runs and their dry runs, 1 the slot-end checks, 2 the critical path
the manager names, 5 everyone else (the default). A `run` waiter takes the first free seat its turn allows; a `take`
waiter takes only its own seat, so it never blocks a `run` waiter behind it. Holds are resource.default_max long
(30 minutes) unless --max says otherwise; status marks a longer hold OVERDUE. A waiter that stops polling for 2
minutes drops out of the queue.

Times carry a unit: --max and --wait take 90s, 30m, 2h or a compound 4h30m, and refuse a bare number (exit 2),
because a bare number means seconds to one tool and minutes to the next, and a "120" meant as two hours becomes a
two-minute hold. A zero time (0s) is refused too (exit 2).

Stopping a `run`: an interrupt (Ctrl+C), TERM or HUP where the platform has them, or on Windows BREAK (Ctrl+Break,
a CTRL_BREAK_EVENT) ends the job with everything it started (every job's shell runs as a process group of its own;
on Windows in a job object), releases the seat with an rq.last note saying so, and exits 130 or 128 + the signal's
number. A stop while `run` still waits takes it out of the queue. A KILL (or Windows' TerminateProcess) cannot be
caught: the job runs on and the seat stays held until the manager's force-release.

Enforcing --max is opt-in: resource.enforce_max = true in the profile, or `run --enforce-max` for one job. When
on, a `run` job (its prepare line included) still going at its --max plus a grace (resource.max_grace, default
"2m") is ended with everything it started (on Windows the job runs in a job object that is ended whole, then
`taskkill /T /F` on the shell's pid; elsewhere the shell's process group gets TERM and, a few seconds later, KILL,
whether or not the shell itself has ended by then), its seat is released with an rq.last note saying it was ended
at its limit, and `run` exits 124. Off, nothing ends a job: a long hold only reads OVERDUE. A `take` hold is never ended.

status --json prints one object: {"resource", "now", "enforce_max", "seats": [{"seat", "holder", "job", "since",
"max", "overdue", "all", "exclusive", "prio", "via"}] (holder null when the seat is free), "queue": the waiters in
order [{"id", "job", "prio", "at", "wants" ("all", "any" or a seat's name), "max", "exclusive"}], "counted":
{"holding": [ids], "waiting": [ids]}}. A counted run or sweep is known by its id, <badge id>-sweep or
<badge id>-counted[-<lane>], the shape the office and the board read. Times are seconds since the epoch.

Exclusive jobs: some jobs cannot share the resource even from different seats (two harnesses that stop programs by
name in one machine stop each other's). resource.exclusive is a regex: a job whose --job text or command matches it
(or that passes --exclusive) is an exclusive job, and only one exclusive job holds a seat at a time; other jobs pass
it in the queue. An empty regex means no such rule.

Whole-resource jobs: `run --all-seats` (counted runs, and runs that must hold every seat because the seats share
state) waits until every seat is free and then holds them all. Behind it, a waiter takes a free seat meanwhile only
when its --max is 30 minutes or less and ends before the last busy seat's hold reaches its --max (a backfill): a
short test job runs while a long job finishes. If the busy job ends early, the whole-resource job can wait up to
30 minutes for the backfill, longer if the backfill overruns its own --max and --max is not enforced (status then
shows it OVERDUE). The command runs in the first seat, with the variable resource.seats_env names (default
FOUNDRY_SEATS) listing every seat held, and release frees them all. A whole-resource job keeps its place: a job
queued within 5 minutes of its own id's release, after the whole-resource job queued, never backfills ahead of it (a
re-queue goes behind it), and once the whole-resource job has waited 60 minutes nothing backfills.

One job per badge: `run` and `take` refuse (exit 3) an id that already waits in the queue or holds a seat, so a
second job can neither replace the first one's queue entry nor be freed by its release. A waiter the manager moved
with rq.requeue.json may take its own place again. A `run` releases only the seats its own process took (a token in
hold.json), never another hold under the same id; `release --id` frees the id's holds. hold.json records `via` (run
or take), and the refusal tells that holder what to do: a `take` holder releases its own hold when its work is done;
a `run` job's hold is never released by hand.

The prepare line (resource.prepare, a shell line; empty = none) runs before each `run` job, in the seat the job
took. It reads FOUNDRY_SEAT and FOUNDRY_SEATS (or the names the profile gives them), FOUNDRY_JOB_ID (this job's id),
FOUNDRY_TOUCHED (this job's --touched), FOUNDRY_LAST_HOLDER (the id that held the seat before), FOUNDRY_LAST_NOTE
(that holder's release note) and FOUNDRY_LAST_TOUCHED (what that holder said it touched), so it can bring the seat
back to a known state: clean what the last holder built, reset a device. Its exit code is printed, not acted on.
`run --no-prepare` skips it.

The shell: commands run as `<shell> -c "<line>"`. The shell is resource.shell when set, else bash from the PATH, else
sh. Exit 2: the project names no shared resource, or a usage error.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import foundry_profile as fp  # noqa: E402

P = fp.load(__file__)
RES = dict(P.get("resource") or {})  # the [resource] table in force; the selftest puts its own in
POLL = 15
STALE = 120
AGE = 90 * 60  # a waiter older than this ranks with the critical path (prio 2), so no one starves
BACKFILL_MAX = 30 * 60  # the longest --max that may backfill a free seat behind a waiting whole-resource job
REQUEUE_GAP = 5 * 60  # a job queued this soon after its id's release is a re-queue: it goes behind a whole-resource waiter
ALL_AGE = 60 * 60  # a whole-resource job that has waited this long gets no more backfills ahead of it
HOLD_TOKEN = None  # set by take(): this process's own holds carry it in hold.json, and run() releases only those
TOUCHED = "touched: "  # the second line of rq.last: what the holder said it touched
RUNNING = "rq: running in seat"  # how the line `run` prints starts, once it holds a seat and starts the job's
#                                  command; sweep.py reads a lane's log for it: with no such line the lane was not run
STARTED = "rq: started"  # the line `run` prints after the job's shell was started (RUNNING is printed before)
FINISHED = "rq: finished exit"  # ... and the one when the command ended by itself, with its exit code. Both end
#                                 with [<token>], the caller's FOUNDRY_RQ_TOKEN (empty when none was given): a job
#                                 that was ended at its limit or stopped has a `started` line and no `finished` one
TOKEN_ENV = "FOUNDRY_RQ_TOKEN"  # read by `run`, taken out of the job's environment
KILL_GRACE = 5  # seconds between TERM and KILL when a job's process group is ended
QUEUED = False  # set by take() once this process has put its own entry in the queue


def office():
    """The crew office, resolved at each call: FOUNDRY_PATHS_OFFICE when set (the selftest sets it), else the
    profile's paths.office under the main checkout."""
    env = os.environ.get("FOUNDRY_PATHS_OFFICE")
    if env:
        p = Path(env)
        return p if p.is_absolute() else P.main / p
    return P.path("office")


def queue_file():
    return office() / "rq.queue.json"


def requeue_file():
    """{id: at}: a waiter the manager moved to a newer copy of this tool keeps its place."""
    return office() / "rq.requeue.json"


def released_file():
    """{id: at}: each id's last release, so a re-queue is known."""
    return office() / "rq.released.json"


def seats_file():
    return office() / "rq.seats"


def seats():
    try:
        ls = [l.strip() for l in seats_file().read_text(encoding="utf-8").splitlines()
              if l.strip() and not l.startswith("#")]
    except OSError:
        ls = []
    if not ls:
        conf = RES.get("seats") or []
        if isinstance(conf, str):
            conf = conf.split(",")
        ls = [str(s).strip() for s in conf if str(s).strip()]
    return ls or ["main"]


def first():
    """The first seat: the first of the profile's resource.seats (office.py reads it the same way). Its office files
    carry no suffix, and `take` asks for it by default."""
    conf = RES.get("seats") or []
    if isinstance(conf, str):
        conf = conf.split(",")
    return next((str(s).strip() for s in conf if str(s).strip()), "main")


def lock_of(seat):
    return office() / ("rq.lock" if seat == first() else "rq.lock." + seat)


def last_of(seat):
    return office() / ("rq.last" if seat == first() else "rq.last." + seat)


_EXCL = {}


def exclusive_re():
    """resource.exclusive compiled, or None when it is empty or not a regex (said once on stderr)."""
    pat = str(RES.get("exclusive") or "")
    if pat not in _EXCL:
        try:
            _EXCL[pat] = re.compile(pat) if pat else None
        except re.error as e:
            print(f"rq: resource.exclusive is not a regex ({e}); no job is exclusive by its text", file=sys.stderr)
            _EXCL[pat] = None
    return _EXCL[pat]


def names_exclusive(text):
    r = exclusive_re()
    return bool(r and r.search(text or ""))


def is_exclusive(e):
    """A queue entry's or a hold's exclusive flag (the key `gui`); an entry without one is decided by its job text."""
    return bool(e["gui"]) if "gui" in e else names_exclusive(e.get("job", ""))


DUR = re.compile(r"(?:(\d+(?:\.\d+)?)h)?(?:(\d+(?:\.\d+)?)m)?(?:(\d+(?:\.\d+)?)s)?")


UNIT_HINT = "write a unit: 90s, 30m, 2h, 4h30m"
# A counted run or sweep by its queue id: <badge id>-sweep or <badge id>-counted[-<lane>] (office.py reads the same
# shape; a dry run's EMP-5-dry-sweep does not match).
COUNTED_ID = re.compile(r"[A-Z]+-\d+-(?:sweep|counted(?:-[0-9A-Z]+)?)", re.I)


def seconds(s):
    """A time with its unit, in seconds: 30m, 2h, 90s, or a compound 4h30m / 1h15m30s. A bare number is refused:
    it is seconds to one reader and minutes to the next."""
    s = str(s).strip().lower()
    m = DUR.fullmatch(s)
    if not s or not m or not any(m.groups()):
        if s.replace(".", "", 1).isdigit():
            raise ValueError(f"{s!r} has no unit; {UNIT_HINT}")
        raise ValueError(f"invalid duration {s!r}; {UNIT_HINT}")
    h, mi, se = (float(x) if x else 0.0 for x in m.groups())
    return int(h * 3600 + mi * 60 + se)


def dur(s):
    """seconds(), for a hold or a wait: a zero length is refused (it used to become 30 minutes without a word)."""
    v = seconds(s)
    if v <= 0:
        raise ValueError(f"{str(s).strip()!r} is no time at all: a hold or a wait is longer than zero; {UNIT_HINT}")
    return v


def dur_arg(s):
    """dur() for argparse, so the refusal prints its own words (exit 2)."""
    try:
        return dur(s)
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e))


def span(sec):
    """Seconds as a time with units: 5400 -> 1h30m, 90 -> 1m30s, 0 -> 0s."""
    sec = int(sec)
    h, m, s = sec // 3600, sec % 3600 // 60, sec % 60
    return "".join(f"{v}{u}" for v, u in ((h, "h"), (m, "m"), (s, "s")) if v) or "0s"


_SAID = set()


def _profile_time(key, default):
    """A time from the [resource] table; one that cannot be read is said once on stderr and the default stands."""
    raw = RES.get(key)
    if raw is None or raw == "":
        return seconds(default)
    try:
        return seconds(raw)
    except ValueError as e:
        if key not in _SAID:
            _SAID.add(key)
            print(f"rq: resource.{key} in the profile: {e}; using {default}", file=sys.stderr)
        return seconds(default)


def default_max():
    return _profile_time("default_max", "30m") or 1800


def max_grace():
    """How long past its --max an enforced job may still run (resource.max_grace, default 2m; 0s is allowed)."""
    return _profile_time("max_grace", "2m")


def enforcing(a=None):
    """True when --max is enforced: resource.enforce_max in the profile, or this run's --enforce-max."""
    v = RES.get("enforce_max")
    return bool(getattr(a, "enforce_max", False) or v is True or str(v).strip().lower() in ("1", "true", "yes", "on"))


def cmd_line(cmd):
    """The shell line for `run -- <cmd>`. One argument is a shell line as written (`-- "a && b"`); several are
    quoted word by word, so `-- sh -c 'a && b'` reaches sh with its script whole (a plain join gave sh -c only the
    first word)."""
    import shlex
    if len(cmd) == 1:
        return cmd[0]
    if not (len(cmd) >= 3 and cmd[1] == "-c") and any(re.search(r"&&|\|\||;|\|", w) for w in cmd):
        print("rq: warning: several words after --, and one holds a shell operator; each word is quoted, so the "
              "operator is not run. Quote the whole chain as one word, or queue `-- sh <file>`.",
              file=sys.stderr, flush=True)
    return shlex.join(cmd)


def hhmm(t):
    return time.strftime("%H:%M", time.localtime(t))


def me():
    """This tool's command line, as a message should print it."""
    return P.tool("rq.py")


class Mutex:
    def __enter__(self):
        self.dir = office() / "rq.mutex"
        self.dir.parent.mkdir(parents=True, exist_ok=True)
        for _ in range(400):
            try:
                self.dir.mkdir()
                return self
            except FileExistsError:
                try:
                    if time.time() - self.dir.stat().st_mtime > 30:
                        self.dir.rmdir()
                        continue
                except OSError:
                    pass
                time.sleep(0.05)
        raise SystemExit("rq: the queue's mutex is stuck; ask the manager")

    def __exit__(self, *exc):
        try:
            self.dir.rmdir()
        except OSError:
            pass


def read_queue():
    try:
        return json.loads(queue_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def write_queue(q):
    qf = queue_file()
    tmp = qf.with_suffix(".tmp")
    tmp.write_text(json.dumps(q, indent=1), encoding="utf-8")
    os.replace(tmp, qf)


def holder(seat=None):
    seat = seat or first()
    lk = lock_of(seat)
    if not lk.is_dir():
        return None
    h = {"id": (lk / "holder").read_text(encoding="utf-8").strip() if (lk / "holder").exists() else "?", "lane": seat}
    try:
        h.update(json.loads((lk / "hold.json").read_text(encoding="utf-8")))
    except (OSError, ValueError):
        h.setdefault("since", lk.stat().st_mtime)
    return h


def live(q, now):
    # Ageing is written into the entry itself, so every waiter (whatever copy of this file it started with) reads the
    # same order from the queue file.
    for e in q:
        if now - e["at"] > AGE and e["prio"] > 2:
            e["prio"] = 2
    return sorted((e for e in q if now - e["beat"] <= STALE), key=lambda e: (e["prio"], e["at"]))


def allocate(q, now=None):
    """Hand the free seats to the waiters in queue order: a `run` waiter (any) takes the first free seat, preferring a
    seat other than the first so a `take` waiter behind it can still take the first; a `take` waiter only its own
    seat. Behind a waiting whole-resource job, only a backfill that ends before the busy seats free (by their holds'
    --max) takes a seat."""
    now = time.time() if now is None else now
    every, one = seats(), first()
    free = [s for s in every if not lock_of(s).is_dir()]
    excl_busy = any(is_exclusive(holder(s) or {}) for s in every if lock_of(s).is_dir())
    got = {}
    until = None  # set once a whole-resource job waits: the time the last busy seat's hold reaches its --max
    all_at = None  # when that whole-resource job queued
    for e in q:
        if not free:
            break
        if e.get("all"):
            if until is None and len(free) == len(every):
                got[e["id"]] = "*"
                free = []
                continue
            if until is None:
                ends = [(h.get("since") or now) + (h.get("max") or 1800) for h in (holder(s) for s in every) if h]
                until = max(ends) if ends else now
                all_at = e["at"]
            continue  # it waits for the whole resource; the waiters behind it may only backfill
        if until is not None and (now - all_at > ALL_AGE or (e.get("requeued") and e["at"] >= all_at)):
            # a job re-queued right after its own release goes behind the whole-resource job, and one that has
            # waited ALL_AGE gets no more backfills, so a chain of short jobs cannot keep it waiting
            continue
        if until is not None and not (e.get("max") and e["max"] <= BACKFILL_MAX and now + e["max"] <= until):
            # an entry with no --max recorded, one past BACKFILL_MAX, or one that would outlast the busy seats'
            # holds waits. --max is enforced only when the project turns that on, so the cap bounds how long a
            # backfill can delay the whole-resource job once the seats free
            continue
        if excl_busy and is_exclusive(e):
            continue
        if e.get("any"):
            pick = next((s for s in free if s != one), free[0])
        else:
            want = e.get("lane", one)
            pick = want if want in free else None
        if pick:
            got[e["id"]] = pick
            free.remove(pick)
            excl_busy = excl_busy or is_exclusive(e)
    return got


def take(a, any_seat=False, via="take"):
    t0 = time.time()
    one = first()
    seat_req = getattr(a, "seat", None) or one
    if seat_req not in seats():
        print(f"rq: seat {seat_req} is not one of the seats ({', '.join(seats())})")
        return 3, None
    excl = bool(getattr(a, "exclusive", False)
                or names_exclusive(a.job + " " + " ".join(getattr(a, "cmd", None) or [])))
    seat_env = str(RES.get("seat_env") or "FOUNDRY_SEAT")
    global HOLD_TOKEN, QUEUED
    with Mutex():
        try:
            rq = json.loads(requeue_file().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            rq = {}
        waiting = next((e for e in live(read_queue(), t0) if e["id"] == a.id), None)
        holds = held_seat(a.id)
        # One job per badge: a second job under one id would replace the first one's queue entry, and its release
        # would free the first one's seat under a running job. Refuse the second. A waiter the manager moved
        # (rq.requeue.json) may retake its own queue place, never a second hold.
        if holds or (waiting and a.id not in rq):
            if holds:
                h = holder(holds) or {}
                head = (f"rq: {a.id} holds seat {holds} ({h.get('job', '?')}). One queue job per badge, so this "
                        "job is refused. ")
                release = (f"`{me()} release --id {a.id} --note \"what ran\"` (a `take` holder always "
                           "releases its own hold when its work is done)")
                wait = ("wait for it to end; it releases its own seat. Never `release` a `run` job's hold while the job "
                        "may still run: that frees its seat under the job. If its process is gone, ask the manager "
                        "to force-release it")
                # say what this holder must do, by how its hold was taken (hold.json "via")
                if h.get("via") == "take":
                    print(head + "That hold is a `take`: your own manual work on the seat. Finish that work, then free "
                          f"the seat yourself with {release}, and run this job again.", flush=True)
                elif h.get("via") == "run":
                    print(head + "That hold is a `run` job: " + wait + ". Then run this job again.", flush=True)
                else:
                    print(head + "Its hold.json does not say how it was taken. If it is your own "
                          f"`take` and your manual work on it is done, free it yourself with {release}. If it is a "
                          "`run` job, or you are not sure, " + wait + ". Then run this job again.", flush=True)
            else:
                print(f"rq: {a.id} already waits in the queue ({waiting.get('job', '?')}). One queue job per badge: "
                      f"wait for it, or take it out with `{me()} leave --id {a.id}`, then run again. A waiter "
                      "whose process died drops out 2 minutes after its last poll.", flush=True)
            return 3, None
        q = [e for e in read_queue() if e["id"] != a.id]
        at = rq.pop(a.id, t0)
        if at != t0:
            requeue_file().write_text(json.dumps(rq), encoding="utf-8")
        e = {"id": a.id, "job": a.job, "prio": a.prio, "at": at, "beat": t0, "gui": excl, "max": a.max}
        if requeued(a.id, t0):
            e["requeued"] = True
        if getattr(a, "all_seats", False):
            e["all"] = True
        elif any_seat:
            e["any"] = True
        else:
            e["lane"] = seat_req
        q.append(e)
        write_queue(q)
        QUEUED = True
    how = "every seat" if e.get("all") else ("any seat" if any_seat else "seat " + seat_req)
    print(f"rq: {a.id} queued at {hhmm(t0)} (prio {a.prio}, {how}"
          f"{', exclusive: one at a time across seats' if excl else ''}): {a.job}", flush=True)
    while True:
        now = time.time()
        with Mutex():
            q = live(read_queue(), now)
            for e in q:
                if e["id"] == a.id:
                    e["beat"] = now
            mine = next((e for e in q if e["id"] == a.id), None)
            if mine is None:
                print(f"rq: {a.id} is out of the queue (rq.py leave, or it stopped polling); run it again if "
                      "it is still wanted", flush=True)
                return 6, None
            seat = allocate(q, now).get(a.id)
            # the first seat keeps one more rule: a `run` waiter takes it only at the queue's head while a `take`
            # waiter for it stands ahead (a whole-resource entry is not such a waiter; allocate() already rules on
            # backfill behind it)
            if seat == one and q[0]["id"] != a.id and any(not x.get("any") and not x.get("all")
                                                         and x.get("lane", one) == one
                                                         for x in q[:q.index(mine)]):
                seat = None
            if seat:
                held = seats() if seat == "*" else [seat]
                HOLD_TOKEN = f"{os.getpid()}-{int(now * 1000)}"
                for s in held:
                    lk = lock_of(s)
                    lk.mkdir()
                    (lk / "holder").write_text(a.id + "\n", encoding="utf-8")
                    (lk / "hold.json").write_text(json.dumps(
                        {"id": a.id, "job": a.job, "since": now, "max": a.max, "lane": s, "gui": excl,
                         "all": len(held) > 1, "prio": a.prio, "token": HOLD_TOKEN, "via": via}),
                        encoding="utf-8")
                write_queue([e for e in q if e["id"] != a.id])
                seat = held[0]
                last = last_of(seat)
                print(f"rq: {a.id} holds seat{'s ' + ', '.join(held) if len(held) > 1 else ' ' + seat} "
                      f"({seat_env}={seat}) from {hhmm(now)} for up to {brief(a.max)} "
                      f"(waited {brief(now - t0)}). {last.name}:", flush=True)
                print(last.read_text(encoding="utf-8") if last.exists() else "(none)", flush=True)
                return 0, seat
            write_queue(q)
        if now - t0 > a.wait:
            with Mutex():
                write_queue([e for e in read_queue() if e["id"] != a.id])
            print(f"rq: {a.id} not taken within {brief(a.wait)}; left the queue", flush=True)
            return 6, None
        time.sleep(POLL)


def read_released():
    try:
        return json.loads(released_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def requeued(who, t0):
    """True when `who` released a seat within REQUEUE_GAP before t0 (its new job is a re-queue)."""
    at = read_released().get(who)
    return isinstance(at, (int, float)) and 0 <= t0 - at <= REQUEUE_GAP


def note_release(who, at):
    with Mutex():
        rel = {k: v for k, v in read_released().items() if isinstance(v, (int, float)) and at - v <= REQUEUE_GAP}
        rel[who] = at
        rf = released_file()
        tmp = rf.with_suffix(".tmp")
        tmp.write_text(json.dumps(rel), encoding="utf-8")
        os.replace(tmp, rf)


def held_seat(who):
    return next((s for s in seats() if (holder(s) or {}).get("id") == who), None)


def do_release(who, note, touched_arg, token=None):
    """Free who's holds; with a token (run's own release), only the holds this process took."""
    held = [s for s in seats() if (holder(s) or {}).get("id") == who
            and (token is None or (holder(s) or {}).get("token") == token)]
    if not held:
        print(f"rq: {who} holds no seat" + (" taken by this process (force-released?)" if token else ""))
        return 3
    for seat in held:      # a whole-resource hold (--all-seats) frees every seat it holds
        release_seat(who, seat, note, touched_arg)
    note_release(who, time.time())
    return 0


def last_parts(seat):
    """(holder id, note line, touched) from the seat's rq.last; three empty strings when there is none."""
    last = last_of(seat)
    try:
        lines = last.read_text(encoding="utf-8").splitlines()
    except OSError:
        return "", "", ""
    note = lines[0] if lines else ""
    line = next((l for l in lines if l.startswith(TOUCHED)), "")
    return note.split(" ")[0], note, line[len(TOUCHED):].strip()


def release_seat(who, seat, note, touched_arg):
    last = last_of(seat)
    touched = touched_arg or "none"
    # A hold that touched nothing ("none ...") leaves the previous holder's note still to act on: carry it.
    if touched.startswith("none") and last.exists():
        prev_id, _, left = last_parts(seat)
        if left and not left.startswith("none"):
            touched = f"{left} (carried from {prev_id}'s hold; {touched})"
    last.write_text(f"{who} {hhmm(time.time())} released seat {seat} after: {note}\n"
                    f"{TOUCHED}{touched}\n", encoding="utf-8")
    shutil.rmtree(lock_of(seat))
    print(f"rq: {who} released seat {seat} at {hhmm(time.time())}")


def release(a):
    return do_release(a.id, a.note, a.touched)


def leave(a):
    """Take a waiter out of the queue. Its waiting process finds itself gone at its next poll and exits 6, so nobody
    has to kill it and wait out STALE."""
    with Mutex():
        q = read_queue()
        mine = [e for e in q if e["id"] == a.id]
        if mine:
            write_queue([e for e in q if e["id"] != a.id])
    if not mine:
        held = held_seat(a.id)
        print(f"rq: {a.id} is not waiting" + (f"; it holds seat {held}: free it with release (or the manager's "
                                                 "force-release)" if held else ""))
        return 3
    print(f"rq: {a.id} left the queue at {hhmm(time.time())}" + (f" ({a.note})" if a.note else "") +
          "; its waiting process exits 6 within a poll")
    return 0


def shell():
    """The shell that runs a job's command line: resource.shell when set, else bash from the PATH, else sh. On
    Windows a bash.exe in the system folder is skipped (it is a launcher for another system, not a shell here), and
    the bash that ships beside git is tried before sh."""
    conf = str(RES.get("shell") or "").strip()
    if conf:
        return conf
    skip = None
    if os.name == "nt":
        skip = os.path.normcase(os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32"))
    exts = [""] + ([e for e in os.environ.get("PATHEXT", ".EXE").split(os.pathsep) if e] if os.name == "nt" else [])

    def on_path(name):
        for d in os.environ.get("PATH", "").split(os.pathsep):
            if not d or (skip and os.path.normcase(os.path.normpath(d)) == skip):
                continue
            for ext in exts:
                c = os.path.join(d, name + ext)
                if os.path.isfile(c) and (os.name == "nt" or os.access(c, os.X_OK)):
                    return c
        return None

    found = on_path("bash")
    if not found and os.name == "nt":
        git = on_path("git")
        for parent in (Path(git).resolve().parents if git else []):
            for cand in (parent / "bin" / "bash.exe", parent / "usr" / "bin" / "bash.exe"):
                if cand.is_file():
                    return str(cand)
    return found or on_path("sh") or "bash"


def win_job(proc):
    """Windows: put a just-started process in a job object of its own and return the job's handle (None when that
    cannot be done). What the process starts from then on is in the job too, whoever its parent is: a shell there
    can start a program through a helper that exits, and then no walk of parent ids (taskkill /T) finds the program."""
    try:
        import ctypes
        from ctypes import wintypes
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        k.CreateJobObjectW.restype = wintypes.HANDLE
        k.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        k.AssignProcessToJobObject.restype = wintypes.BOOL
        k.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        k.CloseHandle.argtypes = [wintypes.HANDLE]
        job = k.CreateJobObjectW(None, None)
        if not job:
            return None
        if not k.AssignProcessToJobObject(job, int(proc._handle)):
            k.CloseHandle(job)
            return None
        return job
    except Exception:
        return None


def win_job_end(job, close_only=False):
    try:
        import ctypes
        from ctypes import wintypes
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        k.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        k.CloseHandle.argtypes = [wintypes.HANDLE]
        if not close_only:
            k.TerminateJobObject(job, 124)
        k.CloseHandle(job)
    except Exception:
        pass


def end_tree(proc, job=None):
    """End a job's shell and everything it started: on Windows its job object (when there is one) and the tree under
    the shell's pid; elsewhere the process group the shell leads (run_line starts every job's shell as one). Never
    raises."""
    try:
        if os.name == "nt":
            if job:
                win_job_end(job)
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True, timeout=30)
        else:
            import signal
            # TERM to the group, then KILL to the group after the grace whether or not the shell itself has ended: a
            # child that ignores TERM must not outlive the seat. The KILL is left out only when the group is seen
            # empty first.
            gone = False
            try:
                os.killpg(proc.pid, signal.SIGTERM)
                end = time.time() + KILL_GRACE
                while time.time() < end:
                    proc.poll()  # reap the shell, so an ended shell does not keep the group looking alive
                    os.killpg(proc.pid, 0)
                    time.sleep(0.1)
            except ProcessLookupError:
                gone = True
            except OSError:
                pass
            if not gone:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except OSError:  # ProcessLookupError among them: the group ended in the meantime
                    pass
    except (OSError, subprocess.SubprocessError):
        pass
    try:
        proc.wait(timeout=5)
    except (OSError, subprocess.SubprocessError):
        try:
            proc.kill()
            proc.wait(timeout=10)
        except (OSError, subprocess.SubprocessError):
            pass


def stop_signals():
    """The signals that ask this process to stop, beyond the keyboard's interrupt, on this platform: TERM and HUP
    where the platform has them, and on Windows BREAK (Ctrl+Break, or a CTRL_BREAK_EVENT sent to the process group:
    the one stop a Windows process can be sent and still clean up after)."""
    import signal
    names = ("SIGBREAK", "SIGTERM") if os.name == "nt" else ("SIGTERM", "SIGHUP")
    return [getattr(signal, n) for n in names if hasattr(signal, n)]


def quiet_signals():
    """Ignore the keyboard's interrupt and every stop signal from here on, so a second one cannot cut a cleanup
    (a seat's release, a freeze's lift) short. Never raises."""
    import signal
    for sig in [signal.SIGINT] + stop_signals():
        try:
            signal.signal(sig, signal.SIG_IGN)
        except (OSError, ValueError, RuntimeError):
            pass


def on_stop_signals():
    """Make a stop signal end this process the way an exception does, so every `finally` runs: TERM, HUP or BREAK
    raises SystemExit(128 + the signal's number), the keyboard's interrupt raises KeyboardInterrupt as ever. The
    first one to arrive turns the others off (quiet_signals). Outside the main thread nothing is installed."""
    import signal

    def stop(signum, _frame):
        quiet_signals()
        if signum == signal.SIGINT:
            raise KeyboardInterrupt
        raise SystemExit(128 + signum)

    for sig in [signal.SIGINT] + stop_signals():
        try:
            signal.signal(sig, stop)
        except (OSError, ValueError, RuntimeError):
            pass


def started_line(token):
    """The line `run` prints once the job's shell has been started (the Popen succeeded)."""
    return f"{STARTED} [{token}]"


def finished_line(code, token):
    """The line `run` prints when the job's command ended by itself, with its own exit code."""
    return f"{FINISHED} {code} [{token}]"


def brief(sec):
    """A length for a status line: whole minutes, and seconds below one minute (45 s, not 0 min)."""
    sec = int(sec)
    return f"{sec // 60} min" if sec >= 60 else f"{max(sec, 0)} s"


def run_line(sh, line, env, deadline=None, said=None):
    """Run one shell line; (exit code, ended at its limit). The line runs as its own process group (a session of its
    own; on Windows a job object), so it can be ended with everything it started. With no deadline nothing ends it
    but a stop of this process. With one, it is ended, tree and all, when the deadline passes: the exit code is then
    124. An interrupt or a stop signal that reaches this process ends the line, tree and all, before it is passed
    on. (A line in a session of its own does not get the terminal's Ctrl+C itself: this process gets it and ends
    the line.) `said` is printed once the shell has been started, and not when it could not be."""
    proc = subprocess.Popen([sh, "-c", line], env=env, **({} if os.name == "nt" else {"start_new_session": True}))
    job = win_job(proc) if os.name == "nt" else None
    try:
        if said:
            print(said, flush=True)
        while True:
            left = 1.0 if deadline is None else deadline - time.time()
            if left <= 0:
                end_tree(proc, job)
                return 124, True
            try:
                code = proc.wait(timeout=min(left, 1.0))
                if job:
                    win_job_end(job, close_only=True)
                return code, False
            except subprocess.TimeoutExpired:
                continue
    except BaseException:  # an interrupt of this process must not leave the job running
        quiet_signals()
        end_tree(proc, job)
        raise


def drop_own(who):
    """After a stop while queueing: take this process's own queue entry out and free the holds it took. Never
    raises."""
    try:
        if QUEUED:
            with Mutex():
                write_queue([e for e in read_queue() if e["id"] != who])
        if HOLD_TOKEN and any((holder(s) or {}).get("token") == HOLD_TOKEN for s in seats()):
            do_release(who, "stopped before its job started", "", token=HOLD_TOKEN)
    except (Exception, SystemExit):
        pass


def run(a):
    if not a.cmd:
        print("rq: run needs a command after --")
        return 2
    on_stop_signals()  # a TERM, HUP or BREAK now ends the job and releases the seat, as an interrupt does
    try:
        rc, seat = take(a, any_seat=not a.seat, via="run")
    except BaseException:
        quiet_signals()
        drop_own(a.id)
        raise
    if rc:
        return rc
    code, ended, deadline, cut_by = 1, False, None, ""
    if enforcing(a):
        grace = max_grace()
        deadline = ((holder(seat) or {}).get("since") or time.time()) + a.max + grace
        print(f"rq: --max is enforced: the job is ended at {time.strftime('%H:%M:%S', time.localtime(deadline))} "
              f"({span(a.max)} plus {span(grace)} grace) if it still runs", flush=True)
    try:
        prev_id, prev_note, prev_touched = last_parts(seat)
        env = dict(os.environ)
        # the caller's token marks this run's own `started` and `finished` lines; the job is not given it, so
        # nothing the job prints can pass for them
        token = env.pop(TOKEN_ENV, "")
        env[str(RES.get("seat_env") or "FOUNDRY_SEAT")] = seat
        env[str(RES.get("seats_env") or "FOUNDRY_SEATS")] = ",".join(
            s for s in seats() if (holder(s) or {}).get("id") == a.id)
        prepare = str(RES.get("prepare") or "").strip()
        sh = shell()
        if prepare and not a.no_prepare:
            print(f"rq: preparing seat {seat}: {prepare}", flush=True)
            prc, ended = run_line(sh, prepare, dict(
                env, FOUNDRY_JOB_ID=a.id, FOUNDRY_TOUCHED=a.touched, FOUNDRY_LAST_HOLDER=prev_id,
                FOUNDRY_LAST_NOTE=prev_note, FOUNDRY_LAST_TOUCHED=prev_touched), deadline)
            if prc and not ended:
                print(f"rq: the prepare line exited {prc}; the job runs all the same", flush=True)
        if ended:
            code = 124
        else:
            line = cmd_line(a.cmd)
            print(f"{RUNNING} {seat}: {line}", flush=True)
            code, ended = run_line(sh, line, env, deadline, said=started_line(token))
            if not ended and 0 <= code <= 255:
                print(finished_line(code, token), flush=True)
        if ended:
            print(f"rq: {a.id}'s job was still running at its limit ({span(a.max)} plus {span(max_grace())} grace) "
                  "and was ended with what it started; exit 124. A counted run it was in is VOID: not run.", flush=True)
    except OSError as e:
        print(f"rq: cannot start the shell ({e}); set resource.shell in the profile", flush=True)
        code = 127
    except (KeyboardInterrupt, SystemExit) as e:
        quiet_signals()
        if isinstance(e, SystemExit) and not (isinstance(e.code, int) and e.code > 128):
            raise  # not a stop signal's exit (the queue's own refusal, say): the note below carries the exit code
        sig = e.code - 128 if isinstance(e, SystemExit) else 0
        cut_by = f"signal {sig}" if sig else "an interrupt"
        code = 128 + sig if sig else 130
        print(f"rq: {a.id}'s job was stopped by {cut_by} sent to the queue; it was ended and its seat is released. "
              "A counted run it was in is VOID: not run.", flush=True)
        raise
    finally:
        quiet_signals()
        # A code outside 0..255 is a platform status (the host shut down, the job was interrupted), not the command's
        # own exit: the run was cut off, and a counted run it was in is VOID: not run.
        cut = f" = 0x{code & 0xFFFFFFFF:08X}: killed, not finished (host shutdown or reboot?)" if not 0 <= code <= 255 else ""
        if ended:
            note = (f"{a.job} (ended at its limit: still running at --max {span(a.max)} plus {span(max_grace())} "
                    "grace; exit 124; what it left in the seat is unknown)")
        elif cut_by:
            note = f"{a.job} (stopped by {cut_by} sent to the queue; what it left in the seat is unknown)"
        else:
            note = f"{a.job} (exit {code}{cut})"
        do_release(a.id, note, a.touched, token=HOLD_TOKEN)
    return code


def force_release(a):
    if not a.by.startswith("MGR-"):
        print("rq: only the manager force-releases")
        return 3
    seat = a.seat or first()
    h = holder(seat)
    if h is None:
        print(f"rq: seat {seat} is free")
        return 1
    last_of(seat).write_text(f"{a.by} {hhmm(time.time())} force-released {h['id']}'s hold on seat {seat} "
                             f"({h.get('job', '?')}): {a.note}\n{TOUCHED}unknown; prepare the seat as after an "
                             f"unknown holder\n", encoding="utf-8")
    shutil.rmtree(lock_of(seat))
    print(f"rq: {a.by} force-released {h['id']}'s hold on seat {seat}")
    return 0


def resource_status():
    """What the profile's resource.status command prints, or one line saying why there is nothing to print."""
    cmd = str(RES.get("status") or "").strip()
    if not cmd:
        return "no status command is configured (resource.status in the profile)"
    try:
        r = subprocess.run([shell(), "-c", cmd], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as e:
        return f"unknown (the status command did not finish: {type(e).__name__})"
    out = (r.stdout + r.stderr).strip()
    return (out or "(no output)") + ("" if r.returncode == 0 else f"\n(the status command exited {r.returncode})")


def status_facts(now=None):
    """What status --json prints: the seats, the waiters in order, and the counted runs holding or waiting."""
    now = time.time() if now is None else now
    out = {"resource": str(RES.get("name") or ""), "now": now, "enforce_max": enforcing(), "seats": [], "queue": [],
           "counted": {"holding": [], "waiting": []}}
    for seat in seats():
        h = holder(seat)
        if h is None:
            out["seats"].append({"seat": seat, "holder": None})
            continue
        since, mx = h.get("since", now), h.get("max", 1800) or 1800
        out["seats"].append({"seat": seat, "holder": h["id"], "job": h.get("job", ""), "since": since, "max": mx,
                             "overdue": now - since > mx, "all": bool(h.get("all")), "exclusive": is_exclusive(h),
                             "prio": h.get("prio"), "via": h.get("via")})
        if COUNTED_ID.fullmatch(str(h["id"])) and h["id"] not in out["counted"]["holding"]:
            out["counted"]["holding"].append(h["id"])
    for e in live(read_queue(), now):
        out["queue"].append({"id": e["id"], "job": e.get("job", ""), "prio": e["prio"], "at": e["at"],
                             "wants": "all" if e.get("all") else "any" if e.get("any") else e.get("lane", first()),
                             "max": e.get("max"), "exclusive": is_exclusive(e)})
        if COUNTED_ID.fullmatch(str(e["id"])) and e["id"] not in out["counted"]["waiting"]:
            out["counted"]["waiting"].append(e["id"])
    return out


def status(a):
    now = time.time()
    if getattr(a, "json", False):
        facts = status_facts(now)
        if getattr(a, "resource", False):
            facts["resource_status"] = resource_status()
        print(json.dumps(facts, indent=1))
        return 0
    for seat in seats():
        h = holder(seat)
        if h is None:
            print(f"seat {seat}: free")
            continue
        age, mx = now - h.get("since", now), h.get("max", 1800) or 1800
        flag = "OVERDUE" if age > mx else "ok"
        print(f"seat {seat}: {h['id']} since {hhmm(h.get('since', now))} ({brief(age)} of {brief(mx)}, {flag}"
              f"{', exclusive' if is_exclusive(h) else ''}{', ALL SEATS' if h.get('all') else ''}): {h.get('job', '?')}")
    q = live(read_queue(), now)
    print(f"queue: {len(q)} waiting")
    for i, e in enumerate(q, 1):
        how = ("every seat" if e.get("all") else "any seat" if e.get("any") else "seat " + e.get("lane", first())) + \
              (", exclusive" if is_exclusive(e) else "")
        print(f"  {i}. {e['id']} prio {e['prio']} since {hhmm(e['at'])} ({how}): {e['job']}")
    for seat in seats():
        last = last_of(seat)
        if last.exists():
            print(f"{last.name}: " + last.read_text(encoding="utf-8").strip().replace("\n", " | "))
    if getattr(a, "resource", False):
        print(f"{RES.get('name') or 'resource'}: {resource_status()}")
    return 0


def selftest():
    """The queue's rules on scratch seats (a, b) in a temp office; nothing in the project's office is read or
    written, and the project's own resource commands are not run."""
    import tempfile
    import types
    global RES, HOLD_TOKEN
    keep_res, keep_token = RES, HOLD_TOKEN
    keep_env = {k: os.environ.get(k) for k in ("FOUNDRY_PATHS_OFFICE",)}
    tmp = Path(tempfile.mkdtemp(prefix="foundry-rq-selftest-"))
    ok, bad, skipped = [], [], []

    def expect(what, cond, detail=""):
        (ok if cond else bad).append(what + ("" if cond else f": {detail}"))
    try:
        os.environ["FOUNDRY_PATHS_OFFICE"] = str(tmp)
        RES = {"name": "bench", "seats": ["a", "y", "z"], "seat_env": "FOUNDRY_SEAT", "seats_env": "FOUNDRY_SEATS",
               "prepare": "", "exclusive": "", "status": "", "default_max": "30m", "shell": keep_res.get("shell", "")}
        expect("the office is the temp folder while FOUNDRY_PATHS_OFFICE names it", office() == tmp, office())
        expect("without rq.seats the profile's resource.seats are the seats", seats() == ["a", "y", "z"], seats())
        seats_file().write_text("# scratch seats\na\nb\n", encoding="utf-8")
        expect("rq.seats in the office overrides the profile's list", seats() == ["a", "b"], seats())
        expect("the first seat's files carry no suffix; another seat's carry its name",
               (lock_of("a").name, last_of("a").name, lock_of("b").name, last_of("b").name)
               == ("rq.lock", "rq.last", "rq.lock.b", "rq.last.b"))
        now = time.time()
        lock_of("b").mkdir()  # a long job holds b for 2 h; a is free
        (lock_of("b") / "hold.json").write_text(json.dumps({"id": "EMP-L", "since": now - 600, "max": 7200}),
                                                encoding="utf-8")
        whole = {"id": "EMP-A", "job": "counted G2", "prio": 5, "at": now - 900, "beat": now, "all": True, "max": 7200}
        short = {"id": "EMP-X", "job": "unit tests", "prio": 5, "at": now - 60, "beat": now, "any": True, "max": 1200}
        expect("a short job queued behind a whole-resource job backfills the free seat",
               allocate([whole, dict(short)], now).get("EMP-X") == "a")
        expect("a job whose --max is past the backfill cap does not backfill",
               "EMP-X" not in allocate([whole, dict(short, max=BACKFILL_MAX + 60)], now))
        expect("a job that would outlast the busy seat's hold does not backfill",
               "EMP-X" not in allocate([dict(whole), dict(short)], now + 7200 - 600 - 600))
        expect("a short job re-queued right after its own release does not backfill ahead of the whole-resource job",
               "EMP-X" not in allocate([whole, dict(short, requeued=True)], now))
        expect("a re-queue that was already waiting before the whole-resource job queued still backfills",
               allocate([whole, dict(short, requeued=True, at=now - 1000)], now).get("EMP-X") == "a")
        expect("after ALL_AGE of waiting, nothing backfills ahead of the whole-resource job",
               "EMP-X" not in allocate([dict(whole, at=now - ALL_AGE - 60), dict(short)], now))
        shutil.rmtree(lock_of("b"))
        expect("with every seat free the whole-resource job takes them all",
               allocate([whole, dict(short)], now) == {"EMP-A": "*"})
        note_release("EMP-OLD", now - REQUEUE_GAP - 60)
        note_release("EMP-X", now - 30)
        expect("a job queued within REQUEUE_GAP of its id's release is a re-queue; another id's is not",
               requeued("EMP-X", now) and not requeued("EMP-Y", now) and not requeued("EMP-OLD", now))
        expect("the release record drops entries older than REQUEUE_GAP",
               "EMP-OLD" not in read_released() and "EMP-X" in read_released())

        # the order: prio, then arrival; ageing to prio 2; a silent waiter drops out
        q = [{"id": "EMP-1", "prio": 5, "at": now - 100, "beat": now}, {"id": "EMP-2", "prio": 0, "at": now - 10, "beat": now},
             {"id": "EMP-3", "prio": 5, "at": now - 200, "beat": now}, {"id": "EMP-4", "prio": 5, "at": now - AGE - 5, "beat": now},
             {"id": "EMP-5", "prio": 1, "at": now - 300, "beat": now - STALE - 5}]
        expect("order is prio then arrival, a waiter past 90 minutes ranks at prio 2, a silent one drops out",
               [e["id"] for e in live(q, now)] == ["EMP-2", "EMP-4", "EMP-3", "EMP-1"] and q[3]["prio"] == 2,
               [e["id"] for e in live(q, now)])
        a1 = {"id": "EMP-1", "prio": 5, "at": now - 100, "beat": now, "any": True, "max": 1200, "job": "t"}
        t1 = {"id": "EMP-2", "prio": 5, "at": now - 50, "beat": now, "lane": "a", "max": 1200, "job": "t"}
        expect("a `run` waiter prefers a seat other than the first, so a `take` waiter behind it gets the first",
               allocate([a1, t1], now) == {"EMP-1": "b", "EMP-2": "a"}, allocate([a1, t1], now))

        # the wiring, through take() and do_release() themselves (no hand-set `requeued`, no direct note_release),
        # as `run` queues (any seat): a job that takes and releases b, then re-queues behind a whole-resource waiter,
        # is held back; another id queued the same way still backfills. Here the busy seat is a and the free one b;
        # a later case frees a instead, so a backfill on the first seat behind the whole-resource waiter is pinned too.
        for f in (queue_file(), released_file()):
            f.unlink(missing_ok=True)
        job = lambda who, **kw: types.SimpleNamespace(**{**dict(  # noqa: E731
            id=who, job="unit tests", prio=5, max=1200, wait=0, seat=None, exclusive=False, cmd=None), **kw})
        rc, seat = take(job("EMP-X"), any_seat=True, via="run")
        expect("take() on free scratch seats gives EMP-X seat b", (rc, seat) == (0, "b"), (rc, seat))
        rc, seat = take(job("EMP-X"), any_seat=True, via="run")
        expect("one job per id: a second take() under an id that holds a seat is refused (exit 3)",
               (rc, seat) == (3, None) and not lock_of("a").is_dir(), (rc, seat))
        rc = do_release("EMP-X", "unit tests", "src/app")
        expect("do_release() frees b, records EMP-X's release time and writes rq.last.b with the touched note",
               rc == 0 and not lock_of("b").is_dir() and requeued("EMP-X", time.time())
               and last_parts("b")[0] == "EMP-X" and last_parts("b")[2] == "src/app", (rc, read_released(), last_parts("b")))
        now = time.time()
        lock_of("a").mkdir()  # a long job holds a; a whole-resource job waits; b is free
        (lock_of("a") / "hold.json").write_text(json.dumps({"id": "EMP-L", "since": now - 600, "max": 7200}),
                                                encoding="utf-8")
        write_queue([dict(whole, at=now - 900, beat=now)])
        rc, seat = take(job("EMP-X"), any_seat=True, via="run")
        expect("take() of EMP-X re-queued after its own do_release() does not backfill b ahead of the whole-resource job",
               rc == 6 and seat is None and not lock_of("b").is_dir(), (rc, seat))
        rc, seat = take(job("EMP-Y"), any_seat=True, via="run")
        expect("take() of another id queued the same way still backfills b", (rc, seat) == (0, "b"), (rc, seat))
        do_release("EMP-Y", "unit tests", "none")
        expect("a release that touched nothing carries the previous holder's touched note",
               last_parts("b")[2].startswith("src/app (carried from EMP-X's hold"), last_parts("b"))

        # a free, b held long, a whole-resource job waiting ahead: a short job (another id) takes a
        shutil.rmtree(lock_of("a"))
        now = time.time()
        lock_of("b").mkdir()
        (lock_of("b") / "hold.json").write_text(json.dumps({"id": "EMP-L", "since": now - 600, "max": 7200}),
                                                encoding="utf-8")
        write_queue([dict(whole, at=now - 900, beat=now)])
        rc, seat = take(job("EMP-Z"), any_seat=True, via="run")
        expect("take() of a short job behind a whole-resource waiter backfills the first seat when it is the free one",
               (rc, seat) == (0, "a"), (rc, seat))
        do_release("EMP-Z", "unit tests", "none")
        shutil.rmtree(lock_of("b"))
        queue_file().unlink(missing_ok=True)

        # one job per id, a waiter: an id that waits is refused; the manager's requeue lets it take its place again
        now = time.time()
        write_queue([{"id": "EMP-W", "job": "first", "prio": 5, "at": now - 30, "beat": now, "lane": "nowhere", "max": 600}])
        rc, seat = take(job("EMP-W"), any_seat=True, via="run")
        expect("one job per id: take() under an id that waits in the queue is refused (exit 3)",
               (rc, seat) == (3, None) and read_queue()[0]["job"] == "first", (rc, seat))
        requeue_file().write_text(json.dumps({"EMP-W": now - 30}), encoding="utf-8")
        rc, seat = take(job("EMP-W"), any_seat=True, via="run")
        expect("a waiter the manager moved (rq.requeue.json) takes its own place again",
               rc == 0 and seat == "b" and "EMP-W" not in json.loads(requeue_file().read_text(encoding="utf-8")), (rc, seat))
        do_release("EMP-W", "moved", "none")
        rc, seat = take(job("EMP-W", seat="nowhere"))
        expect("take() refuses a seat that is not listed (exit 3)", (rc, seat) == (3, None), (rc, seat))

        # exclusive jobs: by the profile's regex, by the flag, and no rule when the regex is empty
        now = time.time()
        gjob = dict(short, id="EMP-G", job="dev run G6")
        lock_of("a").mkdir()
        (lock_of("a") / "hold.json").write_text(json.dumps({"id": "EMP-H", "since": now, "max": 1800, "job": "dev run G5"}),
                                                encoding="utf-8")
        expect("with resource.exclusive empty, two jobs naming G5 and G6 hold seats at the same time",
               allocate([dict(gjob)], now).get("EMP-G") == "b", allocate([dict(gjob)], now))
        RES["exclusive"] = r"\bG(?:5|6)\b"
        expect("with resource.exclusive set, a job matching it waits while another matching job holds a seat",
               "EMP-G" not in allocate([dict(gjob)], now))
        expect("a job that does not match passes the waiting exclusive job",
               allocate([dict(gjob), dict(short)], now) == {"EMP-X": "b"}, allocate([dict(gjob), dict(short)], now))
        shutil.rmtree(lock_of("a"))
        got = allocate([dict(gjob), dict(short, id="EMP-G2", job="dev run G5"), dict(short)], now)
        expect("of two exclusive waiters only the first takes a seat; the plain job behind takes the other",
               got == {"EMP-G": "b", "EMP-X": "a"}, got)
        RES["exclusive"] = ""
        rc, seat = take(job("EMP-E1", exclusive=True), any_seat=True, via="run")
        rc2, seat2 = take(job("EMP-E2", exclusive=True), any_seat=True, via="run")
        rc3, seat3 = take(job("EMP-E3"), any_seat=True, via="run")
        expect("--exclusive: a second exclusive job waits (exit 6 at --wait 0) while the first holds; a plain job runs",
               (rc, seat, rc2, seat2, rc3, seat3) == (0, "b", 6, None, 0, "a"), (rc, seat, rc2, seat2, rc3, seat3))
        RES["exclusive"] = r"\bslow\b"
        rc, seat = take(job("EMP-E4", job="tests", cmd=["make", "slow"]), any_seat=True, via="run")
        expect("a job whose command matches resource.exclusive is exclusive too", (rc, seat) == (6, None), (rc, seat))
        do_release("EMP-E1", "x", "none")
        do_release("EMP-E3", "x", "none")
        RES["exclusive"] = "("
        expect("a resource.exclusive that is not a regex makes no job exclusive", not names_exclusive("dev run G5"))
        RES["exclusive"] = ""

        # force-release and leave
        rc, seat = take(job("EMP-F"), any_seat=True, via="take")
        rc1 = force_release(types.SimpleNamespace(by="EMP-09", note="x", seat="b"))
        rc2 = force_release(types.SimpleNamespace(by="MGR-01", note="its process is gone", seat="b"))
        rc3 = force_release(types.SimpleNamespace(by="MGR-01", note="again", seat="b"))
        expect("only the manager force-releases (exit 3); the manager frees the seat (0); a free seat is exit 1",
               (rc1, rc2, rc3) == (3, 0, 1) and not lock_of("b").is_dir() and last_parts("b")[2].startswith("unknown"),
               (rc1, rc2, rc3))
        write_queue([{"id": "EMP-V", "job": "t", "prio": 5, "at": time.time(), "beat": time.time(), "any": True}])
        rc1 = leave(types.SimpleNamespace(id="EMP-V", note="not needed"))
        rc2 = leave(types.SimpleNamespace(id="EMP-V", note=""))
        expect("leave takes a waiter out (0); an id that is not waiting is exit 3",
               (rc1, rc2) == (0, 3) and read_queue() == [], (rc1, rc2))
        expect("the default --max is resource.default_max", default_max() == 1800)

        expect("dur reads 30m, 2h, 90s and compound 4h30m, 1h15m30s",
               [dur(x) for x in ("30m", "2h", "90s", "4h30m", "1h15m30s", "1.5h")]
               == [1800, 7200, 90, 16200, 4530, 5400])
        bad_dur, said = [], []
        for x in ("", "h", "4x", "30mh", "m30", "120", "90", "1.5", "0", "0s", "0m", "0h0m0s", "-5m"):
            try:
                dur(x)
                bad_dur.append(x)
            except ValueError as e:
                said.append(str(e))
        expect("dur refuses empty, unit-only, unknown-unit and out-of-order durations, and a bare number",
               not bad_dur and all(UNIT_HINT in s for s in said) and "has no unit" in said[5], (bad_dur, said))
        expect("dur refuses a zero time (0s, 0m) with its own words, and a negative one: neither becomes 30 minutes",
               not bad_dur and len(said) == 13 and all("no time at all" in s for s in said[9:12]), (bad_dur, said[9:]))
        expect("span writes seconds back with units", [span(x) for x in (5400, 90, 0, 7200)] == ["1h30m", "1m30s", "0s", "2h"])
        RES["default_max"] = "45"
        expect("a bare number in resource.default_max is not read: the 30-minute default stands", default_max() == 1800)
        RES["default_max"] = "30m"
        RES["max_grace"] = "0s"
        zero = max_grace()
        del RES["max_grace"]
        expect("resource.max_grace defaults to 2m and may be 0s", (max_grace(), zero) == (120, 0), (max_grace(), zero))
        RES["enforce_max"] = True
        on = enforcing()
        del RES["enforce_max"]
        expect("resource.enforce_max or --enforce-max turns enforcing on; neither leaves it off",
               on and enforcing(types.SimpleNamespace(enforce_max=True)) and not enforcing()
               and not enforcing(types.SimpleNamespace(enforce_max=False)))

        # status --json's facts: a counted sweep holds every seat, a counted run and a plain job wait
        now = time.time()
        for s in ("a", "b"):
            lock_of(s).mkdir()
            (lock_of(s) / "holder").write_text("MGR-9-sweep\n", encoding="utf-8")
            (lock_of(s) / "hold.json").write_text(json.dumps(
                {"id": "MGR-9-sweep", "job": "counted sweep: G1", "since": now - 7200, "max": 3600, "lane": s,
                 "all": True, "prio": 0, "via": "run"}), encoding="utf-8")
        write_queue([{"id": "EMP-7", "job": "unit tests", "prio": 5, "at": now - 50, "beat": now, "any": True, "max": 600},
                     {"id": "MGR-9-counted-G2", "job": "counted G2", "prio": 0, "at": now - 10, "beat": now, "all": True},
                     {"id": "EMP-5-dry-sweep", "job": "dry", "prio": 5, "at": now - 5, "beat": now, "lane": "b"}])
        f = status_facts(now)
        expect("status facts: each seat with its holder, since, max and overdue",
               [(s["seat"], s["holder"], s["max"], s["overdue"], s["all"]) for s in f["seats"]]
               == [("a", "MGR-9-sweep", 3600, True, True), ("b", "MGR-9-sweep", 3600, True, True)], f["seats"])
        expect("status facts: the waiters in queue order with what each wants",
               [(e["id"], e["wants"]) for e in f["queue"]]
               == [("MGR-9-counted-G2", "all"), ("EMP-7", "any"), ("EMP-5-dry-sweep", "b")], f["queue"])
        expect("status facts: the counted run holding and the one waiting, by id; a dry run's id is not counted",
               f["counted"] == {"holding": ["MGR-9-sweep"], "waiting": ["MGR-9-counted-G2"]}, f["counted"])
        for s in ("a", "b"):
            shutil.rmtree(lock_of(s))
        queue_file().unlink(missing_ok=True)
        f = status_facts(now)
        expect("status facts: a free seat has holder null, and nothing is counted",
               f["seats"] == [{"seat": "a", "holder": None}, {"seat": "b", "holder": None}]
               and f["queue"] == [] and f["counted"] == {"holding": [], "waiting": []}, f)
        expect("cmd_line keeps sh -c's script as one word", cmd_line(["sh", "-c", "a && b"]) == "sh -c 'a && b'",
               cmd_line(["sh", "-c", "a && b"]))
        expect("cmd_line passes a single shell-line argument as written", cmd_line(["a && b"]) == "a && b")
        expect("cmd_line leaves plain words plain", cmd_line(["make", "test", "G2"]) == "make test G2")

        # the commands end to end, each in its own process, on a second temp office and a profile made of env only
        off2 = tmp / "office2"
        off2.mkdir()
        env = {k: v for k, v in os.environ.items() if not k.startswith("FOUNDRY_")}
        (tmp / "none.toml").write_text("", encoding="utf-8")  # an empty profile file: every key comes from env
        env.update(FOUNDRY_PROFILE=str(tmp / "none.toml"), FOUNDRY_PATHS_OFFICE=str(off2), FOUNDRY_RESOURCE_NAME="bench",
                   FOUNDRY_RESOURCE_SEATS="a, b", RQ_T=off2.as_posix())
        if RES.get("shell"):
            env["FOUNDRY_RESOURCE_SHELL"] = str(RES["shell"])

        def cli(*args, **more):
            r = subprocess.run([sys.executable, str(Path(__file__).resolve()), *args], capture_output=True, text=True,
                               env=dict(env, **more), timeout=120)
            return r.returncode, r.stdout + r.stderr

        rc, out = cli("status", FOUNDRY_RESOURCE_NAME="")
        expect("with no resource named, a command exits 2 with one line saying where to name it",
               rc == 2 and len(out.strip().splitlines()) == 1 and "[resource]" in out, (rc, out))
        rc, out = cli("status")
        expect("status lists each seat and the queue", rc == 0 and "seat a: free" in out and "queue: 0 waiting" in out, (rc, out))
        rc, out = cli("status", "--resource")
        expect("status --resource without resource.status says none is configured",
               rc == 0 and "no status command is configured" in out, (rc, out))
        rc, out = cli("status", "--json")
        try:
            j = json.loads(out)
        except ValueError:
            j = {}
        expect("status --json prints one JSON object: resource, seats, queue, counted",
               rc == 0 and j.get("resource") == "bench" and [s["seat"] for s in j.get("seats", [])] == ["a", "b"]
               and j.get("queue") == [] and j.get("counted") == {"holding": [], "waiting": []}
               and j.get("enforce_max") is False, (rc, out))
        for flag in ("--max", "--wait"):
            rc, out = cli("take", "--id", "EMP-01", "--job", "by hand", flag, "120")
            expect(f"{flag} with a bare number is refused (exit 2) and told to write a unit",
                   rc == 2 and UNIT_HINT in out and not (off2 / "rq.lock").is_dir(), (rc, out))
        rc, out = cli("run", "--id", "EMP-01", "--job", "x", "--max", "120", "--", "true")
        expect("run --max with a bare number is refused too (exit 2)", rc == 2 and UNIT_HINT in out, (rc, out))
        for flag in ("--max", "--wait"):
            rc, out = cli("run", "--id", "EMP-01", "--job", "x", flag, "0s", "--", "true")
            expect(f"{flag} 0s is refused (exit 2) with a clear line, not read as 30 minutes",
                   rc == 2 and "no time at all" in out and not (off2 / "rq.lock").is_dir()
                   and not (off2 / "rq.lock.b").is_dir(), (rc, out))
        rc, out = cli("take", "--id", "EMP-01", "--job", "by hand", "--wait", "1s")
        rc2, out2 = cli("take", "--id", "EMP-01", "--job", "again", "--wait", "1s")
        rc3, out3 = cli("run", "--id", "EMP-01", "--job", "again", "--wait", "1s", "--", "true")
        expect("take holds the first seat; a second take or run under the id is refused (exit 3) and told to release",
               rc == 0 and "holds seat a" in out and rc2 == 3 and rc3 == 3 and "release --id EMP-01" in out2, (rc, rc2, rc3, out2))
        rc, out = cli("status")
        expect("status prints a hold of a few seconds in seconds (N s of 30 min), not as 0 of 30 min",
               rc == 0 and re.search(r"seat a: EMP-01 since \d\d:\d\d \(\d+ s of 30 min, ok", out), (rc, out))
        expect("brief: seconds below one minute, whole minutes from there",
               [brief(x) for x in (0, 7.9, 59, 60, 119, 1800)] == ["0 s", "7 s", "59 s", "1 min", "1 min", "30 min"])
        # an interrupt that comes up out of a command (as it does after run's cleanup), in a process of its own
        code = ("import sys\nsys.path.insert(0, " + repr(str(Path(__file__).resolve().parent)) + ")\nimport rq\n\n\n"
                "def cut_short(_a):\n    raise KeyboardInterrupt\n\n\n"
                "rq.dispatch = cut_short\nsys.argv = ['rq.py', 'status']\nsys.exit(rq.main())\n")
        r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, timeout=120)
        expect("an interrupt that reaches main() ends in exit 130 with one line, not a traceback",
               r.returncode == 130 and "Traceback" not in r.stdout + r.stderr and "rq: interrupted" in r.stdout,
               (r.returncode, r.stdout, r.stderr))
        rc, out = cli("force-release", "--by", "EMP-02", "--note", "x")
        expect("force-release by an employee is refused (exit 3)", rc == 3 and (off2 / "rq.lock").is_dir(), (rc, out))
        rc, out = cli("release", "--id", "EMP-01", "--note", "by hand", "--touched", "src/app")
        rc2, _ = cli("release", "--id", "EMP-01", "--note", "twice")
        expect("release frees the seat and writes rq.last; a second release is exit 3",
               rc == 0 and rc2 == 3 and not (off2 / "rq.lock").is_dir()
               and "touched: src/app" in (off2 / "rq.last").read_text(encoding="utf-8"), (rc, rc2, out))
        sh = shell()
        if not (os.path.isfile(sh) or shutil.which(sh)):
            skipped.append("the `run` cases: no bash or sh on this host (set resource.shell)")
        else:
            rc, out = cli("run", "--id", "EMP-02", "--job", "unit tests", "--touched", "src/core", "--",
                          'printf "%s|%s" "$FOUNDRY_SEAT" "$FOUNDRY_SEATS" > "$RQ_T/out.txt"; exit 7')
            got = (off2 / "out.txt").read_text(encoding="utf-8") if (off2 / "out.txt").exists() else None
            last_b = (off2 / "rq.last.b").read_text(encoding="utf-8") if (off2 / "rq.last.b").exists() else ""
            expect("run sets the seat variables, exits with the command's exit code and releases the seat with a note",
                   rc == 7 and got == "b|b" and not (off2 / "rq.lock.b").is_dir()
                   and "unit tests (exit 7)" in last_b and "touched: src/core" in last_b, (rc, got, last_b, out))
            prep = ('printf "%s|%s|%s|%s|%s" "$MY_SEAT" "$FOUNDRY_LAST_HOLDER" "$FOUNDRY_LAST_TOUCHED" "$FOUNDRY_JOB_ID" '
                    '"$FOUNDRY_TOUCHED" > "$RQ_T/prep.txt"; printf "%s" "$FOUNDRY_LAST_NOTE" > "$RQ_T/note.txt"')
            rc, out = cli("run", "--id", "EMP-03", "--job", "lint", "--seat", "b", "--touched", "docs", "--",
                          'printf "%s" "$MY_SEAT" > "$RQ_T/out.txt"',
                          FOUNDRY_RESOURCE_PREPARE=prep, FOUNDRY_RESOURCE_SEAT_ENV="MY_SEAT")
            got = (off2 / "prep.txt").read_text(encoding="utf-8") if (off2 / "prep.txt").exists() else None
            note = (off2 / "note.txt").read_text(encoding="utf-8") if (off2 / "note.txt").exists() else ""
            expect("resource.prepare runs before the job with the seat, the last holder, its note and what it touched; "
                   "resource.seat_env renames the seat variable",
                   rc == 0 and got == "b|EMP-02|src/core|EMP-03|docs" and "unit tests (exit 7)" in note
                   and (off2 / "out.txt").read_text(encoding="utf-8") == "b", (rc, got, note, out))
            (off2 / "prep.txt").unlink(missing_ok=True)
            rc, out = cli("run", "--id", "EMP-03", "--job", "lint", "--no-prepare", "--", "true",
                          FOUNDRY_RESOURCE_PREPARE=prep + "; exit 9")
            expect("run --no-prepare skips the prepare line", rc == 0 and not (off2 / "prep.txt").exists(), (rc, out))
            rc, out = cli("run", "--id", "EMP-04", "--job", "lint", "--", "exit 0", FOUNDRY_RESOURCE_PREPARE="exit 9")
            expect("a prepare line that fails is said, and the job runs all the same",
                   rc == 0 and "prepare line exited 9" in out, (rc, out))
            rc, out = cli("run", "--id", "EMP-05", "--job", "counted G2", "--all-seats", "--",
                          'printf "%s|%s" "$FOUNDRY_SEAT" "$FOUNDRY_SEATS" > "$RQ_T/out.txt"')
            got = (off2 / "out.txt").read_text(encoding="utf-8")
            expect("run --all-seats holds every seat, runs in the first and frees them all",
                   rc == 0 and got == "a|a,b" and not (off2 / "rq.lock").is_dir() and not (off2 / "rq.lock.b").is_dir(),
                   (rc, got, out))
            rc, out = cli("status", "--resource", FOUNDRY_RESOURCE_STATUS="echo 12 GB free")
            expect("status --resource prints what resource.status says", rc == 0 and "bench: 12 GB free" in out, (rc, out))

            # enforcing --max: off, a job past its limit runs on; on, it is ended with what it started
            slow = 'sleep 4; printf done > "$RQ_T/slow.txt"'
            rc, out = cli("run", "--id", "EMP-06", "--job", "slow", "--max", "1s", "--", slow)
            expect("with enforcing off, a job past its --max runs to its own end",
                   rc == 0 and (off2 / "slow.txt").exists() and "enforced" not in out, (rc, out))
            (off2 / "slow.txt").unlink(missing_ok=True)
            prof = tmp / "enforce.toml"
            prof.write_text('[resource]\nname = "bench"\nseats = ["a", "b"]\nmax_grace = "1s"\n', encoding="utf-8")
            t = time.time()
            rc, out = cli("run", "--id", "EMP-06", "--job", "slow", "--max", "1s", "--enforce-max", "--",
                          'sleep 30; printf done > "$RQ_T/slow.txt"', FOUNDRY_PROFILE=str(prof))
            took = time.time() - t
            last_b = (off2 / "rq.last.b").read_text(encoding="utf-8") if (off2 / "rq.last.b").exists() else ""
            expect("run --enforce-max ends a job still going at --max plus resource.max_grace: exit 124, the seat "
                   "released, rq.last says it was ended at its limit",
                   rc == 124 and took < 20 and not (off2 / "rq.lock.b").is_dir()
                   and "ended at its limit" in last_b and "--max 1s plus 1s grace" in last_b, (rc, took, last_b, out))
            time.sleep(1.5)
            expect("... and what the job started is ended with it (nothing ran after the sleep)",
                   not (off2 / "slow.txt").exists())
            prof.write_text('[resource]\nname = "bench"\nseats = ["a", "b"]\nmax_grace = "1s"\nenforce_max = true\n',
                            encoding="utf-8")
            rc, out = cli("run", "--id", "EMP-06", "--job", "quick", "--max", "20s", "--", "exit 3",
                          FOUNDRY_PROFILE=str(prof))
            expect("with resource.enforce_max on, a job inside its limit exits with its own code",
                   rc == 3 and "--max is enforced" in out and "quick (exit 3)" in
                   (off2 / "rq.last.b").read_text(encoding="utf-8"), (rc, out))
            rc, out = cli("run", "--id", "EMP-06", "--job", "slow", "--max", "1s", "--", "sleep 30",
                          FOUNDRY_PROFILE=str(prof))
            expect("with resource.enforce_max on, a job past its limit is ended without the flag (exit 124)",
                   rc == 124 and not (off2 / "rq.lock.b").is_dir(), (rc, out))
            rc, out = cli("status", "--json", FOUNDRY_PROFILE=str(prof))
            expect("status --json says enforcing is on", rc == 0 and json.loads(out).get("enforce_max") is True, (rc, out))

            # the lines a caller reads to tell whether the job's command ran: started, finished, the caller's token
            rc, out = cli("run", "--id", "EMP-06", "--job", "marks", "--",
                          'printf "[%s]" "$FOUNDRY_RQ_TOKEN" > "$RQ_T/tok.txt"; echo "rq: started [t0k]"; exit 7',
                          FOUNDRY_RQ_TOKEN="t0k")
            lines = out.splitlines()
            expect("run prints `rq: started [token]` once the shell is started, after the `running in seat` line, and "
                   "`rq: finished exit N [token]` when the command ended by itself",
                   rc == 7 and lines.count(started_line("t0k")) == 2 and finished_line(7, "t0k") in lines
                   and [l.startswith(RUNNING) for l in lines].index(True) < lines.index(started_line("t0k")), (rc, out))
            tok = (off2 / "tok.txt").read_text(encoding="utf-8") if (off2 / "tok.txt").exists() else None
            expect("... and the job is not given the token (FOUNDRY_RQ_TOKEN is taken out of its environment)",
                   tok == "[]", tok)
            rc, out = cli("run", "--id", "EMP-06", "--job", "no shell", "--", "true", FOUNDRY_RQ_TOKEN="t0k",
                          FOUNDRY_RESOURCE_SHELL="no-such-shell-here")
            expect("a shell that cannot be started: exit 127, the `running in seat` line but no `started` line",
                   rc == 127 and RUNNING in out and STARTED not in out and FINISHED not in out
                   and not (off2 / "rq.lock.b").is_dir(), (rc, out))
            rc, out = cli("run", "--id", "EMP-06", "--job", "slow", "--max", "1s", "--enforce-max", "--", "sleep 30",
                          FOUNDRY_PROFILE=str(prof), FOUNDRY_RQ_TOKEN="t0k")
            expect("a job ended at its limit has a `started` line and no `finished` line (exit 124)",
                   rc == 124 and started_line("t0k") in out and FINISHED not in out, (rc, out))
            rc, out = cli("run", "--id", "EMP-06", "--job", "quick", "--max", "45s", "--", "true")
            expect("a hold shorter than a minute is printed in seconds, not as 0 min",
                   rc == 0 and "for up to 45 s (waited 0 s)" in out and "0 min" not in out, (rc, out))

            # stopping a `run`: a stop signal sent to rq.py itself ends the job and releases the seat
            import signal
            prof.write_text('[resource]\nname = "bench"\nseats = ["a", "b"]\nmax_grace = "1s"\n', encoding="utf-8")
            new_group = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {}

            def started(log, *args):
                with open(log, "wb") as lf:
                    return subprocess.Popen([sys.executable, str(Path(__file__).resolve()), *args], stdout=lf,
                                            stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                            env=dict(env, FOUNDRY_PROFILE=str(prof)), **new_group)

            def until(cond, limit):
                end = time.time() + limit
                while time.time() < end and not cond():
                    time.sleep(0.1)
                return cond()

            def text_of(path):
                try:
                    return path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    return ""

            sigs = [signal.CTRL_BREAK_EVENT] if os.name == "nt" else [signal.SIGTERM, signal.SIGHUP, signal.SIGINT]
            if os.name == "nt":
                skipped.append("POSIX only: an INT (Ctrl+C) sent to `run` ends in exit 130 with no traceback (main's "
                               "own catch is tested above)")
            for n, sig in enumerate(sigs):
                name = "BREAK" if os.name == "nt" else signal.Signals(sig).name
                want = 128 + (signal.SIGBREAK if os.name == "nt" else sig)
                if os.name != "nt" and sig == signal.SIGINT:
                    want = 130  # the documented exit of an interrupt, with no traceback
                log, pidf, late = tmp / f"stop{n}.log", off2 / "job.pid", off2 / "late.txt"
                for f in (pidf, late):
                    f.unlink(missing_ok=True)
                t = time.time()
                # the first with --max enforced, the next without: a stop ends the job's whole group either way
                proc = started(log, "run", "--id", "EMP-07", "--job", "long", "--max", "5m",
                               *(["--enforce-max"] if n == 0 else []), "--",
                               'echo $$ > "$RQ_T/job.pid"; (sleep 6; printf done > "$RQ_T/late.txt") & wait')
                up = until(pidf.exists, 30)
                try:
                    proc.send_signal(sig)
                    sent = True
                except OSError:
                    sent = False
                try:
                    rc = proc.wait(timeout=40)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    rc = "still running 40 s after the signal"
                last_b = text_of(off2 / "rq.last.b")
                if os.name == "nt" and (not sent or rc == 0):
                    skipped.append("a BREAK sent to `run`: this host delivered none (no console is attached)")
                    if (off2 / "rq.lock.b").is_dir():
                        cli("force-release", "--by", "MGR-01", "--note", "selftest", "--seat", "b")
                    continue
                expect(f"a {name} sent to rq.py while its job runs releases the seat with a note saying so "
                       f"(exit {want})",
                       up and rc == want and not (off2 / "rq.lock.b").is_dir() and "stopped by " in last_b
                       and "stopped by " in text_of(log) and "Traceback" not in text_of(log)
                       and started_line("") in text_of(log) and FINISHED not in text_of(log),
                       (up, rc, last_b, text_of(log)))
                time.sleep(max(0.0, t + 8 - time.time()))
                expect(f"... and the job is ended with it: nothing of it runs on after the {name}", not late.exists())
                if os.name != "nt":
                    try:
                        os.kill(int(text_of(pidf).strip() or 0) or -1, 0)
                        alive = True
                    except (OSError, ValueError):
                        alive = False
                    expect(f"... and the job's shell is gone after the {name}", not alive)
            # a stop while `run` still waits for a seat: it leaves the queue and holds nothing
            for seat in ("a", "b"):
                cli("take", "--id", f"EMP-1{seat.upper()}", "--job", "by hand", "--seat", seat, "--wait", "5s")
            log = tmp / "stopw.log"
            proc = started(log, "run", "--id", "EMP-08", "--job", "waits", "--wait", "15s", "--", "true")
            up = until(lambda: any(e.get("id") == "EMP-08" for e in (json.loads(text_of(off2 / "rq.queue.json") or "[]"))), 30)
            try:
                proc.send_signal(sigs[0])
            except OSError:
                pass
            try:
                rc = proc.wait(timeout=60)
            except subprocess.TimeoutExpired:
                proc.kill()
                rc = "still running 60 s after the signal"
            q_left = [e.get("id") for e in json.loads(text_of(off2 / "rq.queue.json") or "[]")]
            if os.name == "nt" and rc == 6:
                skipped.append("a BREAK sent to a waiting `run`: this host delivered none (no console is attached)")
            else:
                expect("a stop signal sent to a `run` that still waits takes it out of the queue; the seats' holders stay",
                       up and rc == 128 + (signal.SIGBREAK if os.name == "nt" else sigs[0]) and "EMP-08" not in q_left
                       and (off2 / "rq.lock").is_dir() and (off2 / "rq.lock.b").is_dir(), (up, rc, q_left, text_of(log)))
            for seat in ("a", "b"):
                cli("release", "--id", f"EMP-1{seat.upper()}", "--note", "selftest")

            # --enforce-max outside Windows: the group is KILLed after the grace even when the shell has ended
            if os.name == "nt":
                skipped.append("POSIX only: at an enforced --max a child that ignores TERM is KILLed with its group "
                               "(Windows ends the job object whole, tested above)")
            else:
                late = off2 / "ign.txt"
                late.unlink(missing_ok=True)
                t = time.time()
                rc, out = cli("run", "--id", "EMP-09", "--job", "ignores TERM", "--max", "1s", "--enforce-max", "--",
                              '(trap "" TERM; sleep 14; printf done > "$RQ_T/ign.txt") & wait', FOUNDRY_PROFILE=str(prof))
                took = time.time() - t
                expect("at an enforced --max the shell ends at TERM and the seat is released (exit 124)",
                       rc == 124 and took < 14 and not (off2 / "rq.lock.b").is_dir(), (rc, took, out))
                time.sleep(max(0.0, t + 16 - time.time()))
                expect("... and its child that ignores TERM was KILLed with the group: it wrote nothing afterwards",
                       not late.exists())
    finally:
        RES, HOLD_TOKEN = keep_res, keep_token
        for k, v in keep_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(tmp, ignore_errors=True)
    for x in ok:
        print(f"  ok   {x}")
    for x in skipped:
        print(f"  skip {x}")
    for x in bad:
        print(f"  FAIL {x}")
    print(f"rq selftest: {len(ok)} ok, {len(bad)} failed" + (f", {len(skipped)} skipped" if skipped else ""))
    return 1 if bad else 0


def main():
    if sys.argv[1:2] == ["selftest"]:
        return selftest()
    if not P.has_resource():
        where = P.file or (P.main / ".foundry" / "foundry.toml")
        print(f"rq: this project names no shared resource, so there is nothing to queue for; name one under "
              f"[resource] (name, seats) in {where}")
        return 2
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd_name", required=True)
    for name in ("take", "run"):
        t = sub.add_parser(name)
        t.add_argument("--id", required=True)
        t.add_argument("--job", required=True)
        t.add_argument("--prio", type=int, default=5)
        t.add_argument("--max", type=dur_arg, default=default_max())
        t.add_argument("--wait", type=dur_arg, default=4 * 3600)
        t.add_argument("--seat", default=None)
        t.add_argument("--exclusive", action="store_true")
        if name == "run":
            t.add_argument("--all-seats", action="store_true")
            t.add_argument("--touched", default="")
            t.add_argument("--no-prepare", action="store_true")
            t.add_argument("--enforce-max", action="store_true")
            t.add_argument("cmd", nargs=argparse.REMAINDER)
    r = sub.add_parser("release")
    r.add_argument("--id", required=True)
    r.add_argument("--note", required=True)
    r.add_argument("--touched", default="")
    f = sub.add_parser("force-release")
    f.add_argument("--by", required=True)
    f.add_argument("--note", required=True)
    f.add_argument("--seat", default=None)
    s = sub.add_parser("status")
    s.add_argument("--resource", action="store_true")
    s.add_argument("--json", action="store_true")
    lv =sub.add_parser("leave")
    lv.add_argument("--id", required=True)
    lv.add_argument("--note", default="")
    a = p.parse_args()
    if a.cmd_name == "run" and a.cmd and a.cmd[0] == "--":
        a.cmd = a.cmd[1:]
    try:
        return dispatch(a)
    except KeyboardInterrupt:
        # the cleanup has run by now (run's `finally` ended the job and released the seat): the documented exit,
        # not a traceback
        quiet_signals()
        print("rq: interrupted", flush=True)
        return 130


def dispatch(a):
    if a.cmd_name == "take":
        return take(a)[0]
    return {"run": run, "release": release, "force-release": force_release, "status": status, "leave": leave}[a.cmd_name](a)


if __name__ == "__main__":
    sys.exit(main())
