#!/usr/bin/env python3
"""The counted sweep: the gym's counted run for each lane, one lane at a time, in the main checkout, stopped the
moment the tree it is counting changes.

  sweep.py run --id MGR-01 --out out/sweeps/<name> [--lanes "G1 G2"] [--queued-at SHA] [--check-only]
               [--max-per-lane 3h] [--wait 4h] [--touched "what the runs touch in the seat"]
  sweep.py status --out out/sweeps/<name>
  sweep.py selftest

run
  --id            the badge id of whoever queued it (letters, a dash, a number: MGR-01). The queue id, and the
                  freeze, carry it, so the office and the board know a counted run is on.
  --out           the sweep's own folder for its logs and tables. It must lie inside the main checkout under a
                  git-ignored folder (out/), and must not exist yet: a sweep's folder is never used twice.
  --lanes         the lanes, in the order to run them. Default: every lane the gym knows (the LANES of the gym's
                  run.py as lanes_for.py reads them; without one, the *.json names under <paths.gym>/prereg).
  --queued-at     the commit the sweep was asked for (default: HEAD now). A sweep can wait, so by its start the
                  main branch may have moved: when it has, `lanes_for.py <queued>..<start>` says which lanes the
                  commits between can move, and the sweep does not start if one of them is a lane it would run.
  --check-only    do the start checks, write source.txt, run nothing. Exit 0: this sweep would start here.
  --max-per-lane  the longest one lane may take, with a unit (90m, 3h, 4h30m; default 3h). With a shared resource
                  it is the lane's --max in the queue (ended there only when the project enforces --max).
  --wait          how long one lane may wait in the queue for the resource (the queue's own default when left out).
  --touched       passed to the queue's release note for each lane.

The command of one lane is measure.counted in the profile, with <lane> replaced; it runs in the main checkout
through the queue's shell. The sweep refuses to start when measure.counted is empty or has no <lane>.

Before the first lane the main checkout must be clean (`git status --porcelain --untracked-files=all` prints
nothing). Before each later lane, and again after every lane, it must still be at the commit the sweep started at,
and clean apart from the run's own records (the paths of measure.records), which the lanes wrote. Anything else
stops the sweep at once with exit 4 and the changed paths: the lanes left are "not run", which is not a verdict,
and a lane during which the tree changed carries the note "tree changed during this lane: ..." on its runs.tsv
row. HEAD's reflog is compared as well, so a commit that was reset away again during a lane is a change too.

A lane's exit code. A lane that exits non-zero does not stop the sweep: its exit code is recorded and the grader
reads the run. The exit codes of measure.counted listed in measure.no_verdict_exits (default [2, 3]) mean the
command ran and gave no verdict. They are the scaffolded gym runner's: 0 PASS, 1 any other verdict word, 2 refused
(nothing written), 3 the runner failed (no verdict). Such a lane carries the note "no verdict (exit <n>)" on its
runs.tsv row, status lists it under its own heading, the last summary line counts the lanes that gave a verdict and
those that gave none apart, and the sweep itself exits 1.

The shared resource. When the profile names one, each lane runs as
`rq.py run --id <badge id>-sweep --prio 0 --all-seats --max <max-per-lane> --job "counted sweep: <lane>" -- <command>`,
so the roster and the board see a counted run in the queue. A lane counts as run only when its log holds both of
rq.py's own lines for it: "rq: started [<token>]", printed once the command's shell was started, and
"rq: finished exit <n> [<token>]", printed when the command ended by itself (rq.STARTED, rq.FINISHED). The token is
made for each lane and given to rq.py alone (FOUNDRY_RQ_TOKEN, which rq.py takes out of the command's
environment), so a command that prints those words itself is not taken for them. Whatever rq.py's exit code, a
log without both means the queue did not run the lane: it refused, waited too long, stopped at the prepare line,
could not start the shell (127), failed itself, ended the command at its limit (124) or was stopped. The row then
carries the note "not run (the queue: exit <n>): ..." with rq.py's last line, and the sweep stops (exit 6).

The freeze. With or without a shared resource the sweep turns the office's freeze on for its whole run and off at
its end, because between two lanes its queue id neither holds nor waits (freeze.json in the office: by, why
"counted sweep", lane null, at, max_s, and `sweep`, this sweep's folder; the file `office.py freeze` keeps, read
here through office.py's freeze_facts() when it has one). source.txt records the freeze this sweep wrote, and at
the end the sweep removes the file only while by, why and at are still its own: a freeze it did not write is never
removed. A freeze under this id that a sweep wrote and left on is taken over, unless that sweep's `alive` file is
still fresh: then that sweep is running and this one refuses (exit 3). A freeze this id set another way (by hand,
`office.py freeze on`) stays as it is: the sweep runs under it and leaves it on. The sweep does not start while
someone else's freeze is on, or the file cannot be read (exit 3). Before every lane the freeze is read again: when
the one the sweep runs under is gone or replaced, the sweep stops there (exit 3) and says which.

One sweep at a time. A running sweep keeps sweep.lock in the office ({"id", "out", "alive", "at"}: who, its folder,
its `alive` file) and removes it at its end. A sweep does not start (exit 3) while the sweep the lock names still
touches its `alive` file, whatever freeze is on and whoever set it; a lock whose `alive` went stale is a killed
sweep's and is written over.

A file sweep-STOP in the office pauses the sweep before the next lane (exit 0, the lanes left are not run).

Stopping a sweep: an interrupt (Ctrl+C), TERM or HUP where the platform has them, or on Windows BREAK (Ctrl+Break).
The sweep passes the stop on to the lane in flight (to rq.py, which ends its job and releases its seats; with no
resource it ends the lane's command itself), waits up to 20 seconds for rq.py to finish that, lifts its own freeze,
writes `ended <time> interrupted` and exits 130, or 128 + the signal's number. If rq.py had to be killed, source.txt
and stderr say so: its seats may still be held and the lane's command may still run, until the manager's
`rq.py force-release`. A KILL of the sweep itself cannot be caught: its freeze stays on until the next sweep under
the id takes it over or the manager lifts it.

What it writes, all under --out:
  source.txt    id, queued_at, started_at, started, lanes, resource; then what a moved start selected, a refusal,
                on Windows with no resource `job_object <lane>: ...` (how the lane's command was put in one),
                the freeze it wrote, and at the end `ended <time> exit <n>` (or `ended <time> interrupted`)
  started.tsv   lane, start time, HEAD: one line before each lane runs
  runs.tsv      lane, exit code, start, end, seconds, and a note when the queue did not run the lane, the lane
                gave no verdict, or the tree changed during it
  <lane>.log    the lane's output
  alive         touched every few seconds while the sweep runs

status reads them: the lanes run with their exit codes and notes, those run with no verdict, the lanes the queue did not run, the lane in
flight (a line in started.tsv with none in runs.tsv), and the lanes left. A lane in flight with no sweep alive (no
fresh `alive`, or an `ended` line) was cut off, by a host shutdown, a stop or a killed session, and reads "VOID:
not run".

The sweep commits nothing. Its last lines tell whoever queued it to commit the run's records (measure.records) as
the run's own commit before anything else touches the main branch.

Exit codes of run:
  0    every lane was run and gave a verdict, whatever the word (or --check-only passed, or sweep-STOP paused it)
  1    every lane was run, and at least one gave no verdict (its exit code is in measure.no_verdict_exits)
  2    usage, or a refusal before anything was written (no measure.counted, no lanes, a bad --out, an unknown
       --queued-at)
  3    a freeze stands in the way: someone else's is on or freeze.json cannot be read, another sweep is still
       running, or the freeze this sweep ran under was lifted or replaced before a lane
  4    the main checkout is not clean, its HEAD moved (or moved and came back), or it changed during a lane
  5    the commits since --queued-at can move a lane of this sweep (queue it again at the new sha)
  6    the queue did not run a lane (refused, not taken within --wait, no shell, ended at its limit, stopped)
  130  the sweep was interrupted (Ctrl+C); 128 + a signal's number: it was stopped by that signal
A sweep that stops early (3, 4, 6) exits with that code even when a lane before the stop gave no verdict.
status: 0, or 2 when --out is not a sweep's folder.

Profile keys read: measure.counted, measure.records, measure.sweep_skip (globs of changed paths the moved-start
check leaves out, e.g. grader notes; default none), measure.no_verdict_exits (a list of exit codes of
measure.counted that mean "ran, no verdict"; default [2, 3]; [] for none), resource.name, paths.gym, paths.office,
main_branch.
Standard library only.
"""
import argparse
import json
import os
import re
import secrets
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import foundry_profile as fp  # noqa: E402
import rq  # noqa: E402

P = fp.load(__file__)
BEAT = 5         # seconds between touches of <out>/alive
ALIVE_S = 60     # an `alive` older than this means no sweep is running
STOP_WAIT = 20   # seconds rq.py gets to end its job and release its seats once a stop is passed on to it
BADGE = re.compile(r"[A-Za-z]+-\d+")
LANE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")
WHY = "counted sweep"


def say(*a):
    print("sweep:", *a, flush=True)


def stamp(t=None):
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t))


def git(*args):
    """(exit code, stdout) of a git command in the main checkout."""
    try:
        r = subprocess.run(["git", "-C", str(P.main), *args], capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as e:
        return 127, str(e)
    return r.returncode, r.stdout if r.returncode == 0 else (r.stdout + r.stderr)


def records():
    rec = P.get("measure.records") or []
    if isinstance(rec, str):
        rec = [rec]
    return [str(r).replace("\\", "/").strip("/") for r in rec if str(r).strip()]


def dirty(allow_records=False):
    """The main checkout's changed paths as git prints them; with allow_records, the run's own records are left out."""
    args = ["status", "--porcelain", "--untracked-files=all"]
    if allow_records and records():
        args += ["--", "."] + [f":(exclude){r}" for r in records()]
    rc, out = git(*args)
    if rc:
        return [f"git status failed: {out.strip()}"]
    return [l for l in out.splitlines() if l.strip()]


def head():
    rc, out = git("rev-parse", "HEAD")
    return out.strip() if rc == 0 else ""


def natural(name):
    return [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", name)]


def known_lanes():
    """Every lane the gym knows: lanes_for.py's list when it has one, else the *.json names under the gym's prereg."""
    gym = P.path("gym")
    try:
        import lanes_for
        fn = getattr(lanes_for, "lane_names", None)
        names = list(fn(gym)) if fn else []
        if names:
            return names
    except (Exception, SystemExit):
        pass
    return sorted((p.stem for p in (gym / "prereg").glob("*.json")), key=natural)


def moved_lanes(queued, start):
    """(exit code, the lanes lanes_for.py says the commits queued..start can move, its raw output)."""
    cmd = [sys.executable, str(HERE / "lanes_for.py"), f"{queued}..{start}"]
    for g in P.get("measure.sweep_skip") or []:
        cmd += ["--skip", str(g)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=str(P.main),
                           env=dict(os.environ, FOUNDRY_ROOT=str(P.main), FOUNDRY_MAIN=str(P.main)))
    except (OSError, subprocess.SubprocessError) as e:
        return 127, [], str(e)
    lanes = [l.split()[0] for l in r.stdout.splitlines() if l.strip() and not l.startswith("#")]
    return r.returncode, lanes, (r.stdout + r.stderr).strip()


# --- the freeze: the office's own functions when office.py has them, else the office file itself ---

def _office_mod():
    try:
        import office
        return office if hasattr(office, "freeze_facts") else None
    except (Exception, SystemExit):
        return None


def freeze_file():
    return rq.office() / "freeze.json"


def freeze_read():
    """The freeze in force as a dict (by, why, lane, at, max_s), or None when it is off. It is read through
    office.py's freeze_facts() when the office has one, so both tools read the file one way; a file that cannot be
    read counts as a freeze in force by "unknown": a tool that cannot tell holds still."""
    off = _office_mod()
    if off:
        try:
            fz = off.freeze_facts(rq.office())
            return {k: fz.get(k) for k in ("by", "why", "lane", "at", "max_s")} if fz.get("on") else None
        except Exception:
            pass
    f = freeze_file()
    if not f.exists():
        return None
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
        if not isinstance(d, dict):
            raise ValueError("not an object")
        return d
    except (OSError, ValueError, RecursionError) as e:  # RecursionError: JSON nested too deep to read
        return {"by": "unknown", "why": f"freeze.json cannot be read ({type(e).__name__})", "lane": None, "at": None,
                "max_s": None}


def freeze_sweep():
    """The folder of the sweep that wrote the freeze in force (its `sweep` key), or "". freeze_facts() does not
    carry the key, so this one read is of the file itself."""
    try:
        d = json.loads(freeze_file().read_text(encoding="utf-8"))
        return str(d.get("sweep") or "") if isinstance(d, dict) else ""
    except (OSError, ValueError, RecursionError):
        return ""


def lock_file():
    """sweep.lock in the office: the sweep that is running, whatever freeze it runs under."""
    return rq.office() / "sweep.lock"


def lock_read():
    try:
        d = json.loads(lock_file().read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError, RecursionError):
        return {}


def running_sweep(now=None):
    """What sweep.lock says ({"id", "out", "alive", "at"}) while the sweep it names still touches its `alive` file;
    None when there is no lock or that sweep has stopped touching it (a lock left by a killed sweep is no bar)."""
    d = lock_read()
    now = time.time() if now is None else now
    try:
        return d if d.get("alive") and now - Path(str(d["alive"])).stat().st_mtime <= ALIVE_S else None
    except OSError:
        return None


def lock_on(by, out):
    f = lock_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps({"id": by, "out": str(out), "alive": str(Path(out) / "alive"), "at": time.time()},
                              ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, f)


def lock_off(out):
    """Remove sweep.lock if it still names this sweep's folder."""
    if lock_read().get("out") == str(out):
        try:
            lock_file().unlink()
        except OSError:
            pass


def no_verdict_exits():
    """measure.no_verdict_exits: the exit codes of measure.counted that mean the lane's command ran and gave no
    verdict. Default 2 and 3, the scaffolded gym runner's "refused, nothing written" and "the runner failed"."""
    raw = P.get("measure.no_verdict_exits")
    if raw is None:
        return {2, 3}
    if isinstance(raw, (str, int)):
        raw = str(raw).replace(",", " ").split()
    out = set()
    for x in raw:
        try:
            out.add(int(x))
        except (TypeError, ValueError):
            continue
    return out


def reflog_mark():
    """HEAD's reflog as one string, its length and its newest entry: it changes with every commit, reset or
    checkout, so a HEAD that moved and came back is seen."""
    rc, top = git("reflog", "-1", "--format=%H %gs")
    rc2, n = git("rev-list", "--walk-reflogs", "--count", "HEAD")
    return f"{n.strip() if rc2 == 0 else '?'} entries, newest: {top.strip() if rc == 0 else '?'}"


def alive_fresh(out, now=None):
    """True while the sweep whose folder is `out` touches its `alive` file."""
    now = time.time() if now is None else now
    try:
        return now - (Path(out) / "alive").stat().st_mtime <= ALIVE_S
    except OSError:
        return False


def freeze_on(by, max_s, out):
    """Write the office's freeze.json in the shape `office.py freeze on` writes, with one more key, `sweep`: this
    sweep's folder, where its `alive` file says whether it still runs. That command takes the manager's signed
    badge line, which a sweep is not given, so the sweep writes the file itself. Returns what it wrote."""
    f = freeze_file()
    f.parent.mkdir(parents=True, exist_ok=True)
    body = {"by": by, "why": WHY, "lane": None, "at": time.time(), "max_s": int(max_s), "sweep": str(out)}
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(body, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, f)
    return body


def freeze_is(mine):
    """True while the freeze in force is the one this sweep wrote: the same by, why and at."""
    d = freeze_read()
    return bool(d and mine and all(d.get(k) == mine.get(k) for k in ("by", "why", "at")))


def freeze_off(mine):
    """Turn the freeze off if it is still the one this sweep wrote (`mine`, what freeze_on returned); a freeze the
    sweep did not write is never removed. True when it removed the file."""
    if not freeze_is(mine):
        return False
    try:
        freeze_file().unlink()
    except OSError:
        return False
    return True


def rmtree(path):
    """Remove a folder with everything in it. A file that cannot be removed for being read-only (git's objects, on
    Windows) is made writable and tried again. Never raises."""
    import shutil
    import stat

    def again(func, p, _exc):
        try:
            os.chmod(p, stat.S_IWRITE | stat.S_IREAD)
            func(p)
        except OSError:
            pass

    try:
        if sys.version_info >= (3, 12):
            shutil.rmtree(path, onexc=again)
        else:
            shutil.rmtree(path, onerror=again)
    except OSError:
        pass


def same_path(a, b):
    """True when two paths name one place, however each is spelled (a link, a junction, a short name on the way)."""
    try:
        return os.path.samefile(a, b)
    except (OSError, ValueError):
        return Path(a).resolve() == Path(b).resolve()


# --- one lane ---

def lane_ran(text, token, code):
    """(started, finished) from a lane's log: whether it holds rq.py's own line for "the command's shell was
    started" and the one for "the command ended by itself with this exit code". Both lines end with the token this
    sweep gave rq.py for the lane and the lane's command never saw, so nothing the command prints passes for them.
    The lane was run only when both are there."""
    lines = text.splitlines()
    return (any(l.endswith(rq.started_line(token)) for l in lines),
            any(l.endswith(rq.finished_line(code, token)) for l in lines))


def queue_word(text, token):
    """rq.py's last own line in a lane's log (its reason, when it did not run the lane), without the marker lines
    and the lines of the seats' release that follow the reason."""
    own = [l.strip() for l in text.splitlines() if l.startswith("rq: ") and not l.endswith(f"[{token}]")
           and " released seat " not in l]
    return own[-1][:300] if own else ""


def stop_child(proc, use_rq, job=None, wait=None):
    """Pass a stop on to the lane in flight; True when rq.py had to be killed, so its seats may still be held.
    rq.py is sent the stop it cleans up after (TERM; on Windows a BREAK to its process group) and given `wait`
    seconds to end its job and release its seats. With no resource the lane's own command is ended, tree and all."""
    wait = STOP_WAIT if wait is None else wait
    if not use_rq:
        rq.end_tree(proc, job)
        return False
    import signal
    try:
        proc.send_signal(signal.CTRL_BREAK_EVENT if os.name == "nt" else signal.SIGTERM)
    except (OSError, ValueError):
        pass
    try:
        proc.wait(timeout=wait)
        return False
    except BaseException:  # it did not end in time (or a second stop came): no more waiting
        pass
    try:
        proc.kill()
        proc.wait(timeout=10)
    except (OSError, subprocess.SubprocessError):
        pass
    return True


def run_lane(a, lane, line, out, use_rq, state=None):
    """Run one lane's command, its output in <out>/<lane>.log; (exit code, note). The `alive` file is touched while
    it runs. A stop of the sweep is passed on to the lane (stop_child) before it goes on up; state["killed"] is
    then set when rq.py had to be killed."""
    state = {} if state is None else state
    more = {}
    token = secrets.token_hex(8)
    env = {k: v for k, v in os.environ.items() if k != rq.TOKEN_ENV}
    if use_rq:
        env[rq.TOKEN_ENV] = token  # rq.py ends its `started` and `finished` lines with it; the lane is not given it
        cmd = [sys.executable, str(HERE / "rq.py"), "run", "--id", f"{a.id}-sweep", "--prio", "0", "--all-seats",
               "--max", rq.span(a.max_per_lane), "--job", f"{WHY}: {lane}"]
        if a.wait:
            cmd += ["--wait", rq.span(a.wait)]
        if a.touched:
            cmd += ["--touched", a.touched]
        cmd += ["--", line]
        if os.name == "nt":  # a process group of its own, so a BREAK can be sent to rq.py and what it started
            more["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        cmd = [rq.shell(), "-c", line]
        if os.name != "nt":  # a process group of its own, so a stop can end the command with what it started
            more["start_new_session"] = True
    log = out / f"{lane}.log"
    with open(log, "wb") as f:
        try:
            io = {"cwd": str(P.main), "stdout": f, "stderr": subprocess.STDOUT, "stdin": subprocess.DEVNULL}
            if os.name == "nt" and not use_rq:
                # in its job object before its first instruction (rq.win_start), so a stop ends all it started
                proc, job = rq.win_start(cmd, env, **io)
                start = rq.LAST.get("start") or {}
                state["job_object"] = f"create {start.get('create')}, assign {start.get('assign')}"
            else:
                proc, job = subprocess.Popen(cmd, env=env, **io, **more), None
        except OSError as e:
            return 127, f"not run (cannot start: {e})"
        try:
            beat = 0.0
            while True:
                if time.time() - beat >= BEAT:
                    beat = time.time()
                    (out / "alive").write_text(f"{os.getpid()} {stamp()}\n", encoding="utf-8")
                try:
                    code = proc.wait(timeout=1.0)
                    break
                except subprocess.TimeoutExpired:
                    continue
            if job:
                rq.win_job_end(job, close_only=True)
        except BaseException:
            rq.quiet_signals()
            state["killed"] = stop_child(proc, use_rq, job)
            raise
    note = ""
    if use_rq:
        # rq.py's exit code alone cannot tell (1 is the gym runner's code for a verdict that is not PASS and rq.py's
        # own when it fails; 127 a shell that could not be started; 124 a job ended at its limit): the lane was run
        # only if rq.py started its command and saw it end by itself.
        try:
            text = log.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""
        started, finished = lane_ran(text, token, code)
        if not (started and finished):
            why = ("its command was started and did not end by itself (ended at its limit, or stopped)" if started
                   else "its command was never started")
            word = queue_word(text, token)
            note = f"not run (the queue: exit {code}): {why}" + (f"; the queue's last line: {word}" if word else "")
    return code, note


def tree_change(start, mark=None):
    """What changed in the tree being counted since the sweep started, as lines; [] when nothing did. The run's own
    records are left out. `mark` is HEAD's reflog at the start (reflog_mark): with HEAD where it was and the reflog
    changed, HEAD moved and came back (a commit and a reset), which a look at HEAD alone does not see."""
    now_head = head()
    changed = dirty(allow_records=True)
    if now_head != start:
        changed = [f"HEAD moved from {start[:10]} to {now_head[:10] or '?'}"] + changed
    elif mark is not None:
        now_mark = reflog_mark()
        if now_mark != mark:
            changed = [f"HEAD moved and came back to {start[:10]} (its reflog changed: {now_mark})"] + changed
    return changed


def cmd_run(a):
    if not BADGE.fullmatch(a.id or ""):
        say(f"--id {a.id!r} is not a badge id (letters, a dash, a number, like MGR-01); the queue id "
            "<badge id>-sweep is how the office and the board know a counted run")
        return 2
    counted = str(P.get("measure.counted") or "").strip()
    where = P.file or (P.main / ".foundry" / "foundry.toml")
    if not counted:
        say(f"measure.counted is empty: name the command of one counted run, with <lane>, under [measure] in {where}")
        return 2
    if "<lane>" not in counted:
        say(f"measure.counted has no <lane> ({counted!r}), so every lane would run the same command; fix it in {where}")
        return 2
    lanes = a.lanes.replace(",", " ").split() if a.lanes else known_lanes()
    if not lanes:
        say(f"no lanes: the gym at {P.path('gym')} names none yet (no LANES in its run.py, no prereg/*.json); "
            "give --lanes")
        return 2
    bad = [l for l in lanes if not LANE.fullmatch(l)]
    if bad or len(set(lanes)) != len(lanes):
        say(f"bad --lanes: {' '.join(bad) if bad else 'a lane is named twice'}")
        return 2

    # the out folder: inside the main checkout, git-ignored, new
    out = Path(a.out)
    out = out if out.is_absolute() else P.main / out
    out = Path(os.path.normpath(str(out)))
    rel = None
    # as written first (an out/ that is itself a link to another disk stays inside); then both resolved, so a
    # checkout reached under another spelling (a link, a junction, a short name) is still the same checkout
    for o, m in ((out, Path(os.path.normpath(str(P.main)))), (out.resolve(), P.main.resolve())):
        try:
            rel = o.relative_to(m).as_posix()
            break
        except ValueError:
            continue
    if rel is None:
        say(f"--out {a.out} is not inside the main checkout ({P.main})")
        return 2
    if rel in ("", "."):
        say("--out must be a folder of its own")
        return 2
    if out.exists():
        say(f"--out {rel} exists already; a sweep's folder is never used twice: give a new name")
        return 2
    rc, _ = git("check-ignore", "-q", rel + "/source.txt")
    if rc != 0:
        say(f"--out {rel} is not under a git-ignored folder (out/): the sweep's own files would dirty the tree it "
            "counts and stop it")
        return 2

    # someone else's freeze
    fz = freeze_read()
    if fz and fz.get("by") != a.id:
        since = f", since {stamp(fz['at'])}" if isinstance(fz.get("at"), (int, float)) else ""
        say(f"a freeze is on, by {fz.get('by')} ({fz.get('why')}{since}); a sweep does not start under someone "
            f"else's freeze. See `{P.tool('office.py')} freeze show`.")
        return 3
    other = running_sweep()
    if other:
        say(f"a sweep is still running: {other.get('id')}'s, in {other.get('out')} (sweep.lock in the office names "
            f"it and its `alive` file was touched in the last {ALIVE_S} s); a second sweep does not start beside it, "
            f"whatever freeze is on. See `{P.tool('sweep.py')} status --out <its folder>`.")
        return 3
    if fz and fz.get("why") == WHY and alive_fresh(freeze_sweep() or os.devnull):
        say(f"a sweep under {a.id} is still running (its folder: {freeze_sweep()}; its `alive` file was touched in the "
            f"last {ALIVE_S} s) and the freeze is its own; a second sweep under the id does not start, and does not "
            f"take that freeze over. See `{P.tool('sweep.py')} status --out <its folder>`.")
        return 3
    changed = dirty()
    if changed:
        say(f"the main checkout ({P.main}) is not clean; nothing started:")
        print("\n".join(changed), flush=True)
        return 4
    start = head()
    if not start:
        say(f"cannot read HEAD of {P.main}")
        return 2
    queued = start
    if a.queued_at:
        rc, got = git("rev-parse", "--verify", "--quiet", a.queued_at + "^{commit}")
        if rc != 0 or not got.strip():
            say(f"--queued-at {a.queued_at} is not a commit here")
            return 2
        queued = got.strip()
    use_rq = P.has_resource()
    out.mkdir(parents=True)
    src = out / "source.txt"
    src.write_text(f"id {a.id}\nqueued_at {queued}\nstarted_at {start}\nstarted {stamp()}\nlanes {' '.join(lanes)}\n"
                   f"resource {P.get('resource.name') if use_rq else 'none'}\n", encoding="utf-8")

    def record(line):
        with open(src, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    if queued != start:
        say(f"queued at {queued[:10]}, starting at {start[:10]}: the main branch moved while the sweep waited")
        lrc, sel, raw = moved_lanes(queued, start)
        record(f"moved_selects {' '.join(sel)}")
        hit = [l for l in lanes if l in sel]
        why = ""
        if lrc != 0:
            why = f"lanes_for.py failed (exit {lrc}), so it cannot be told which lanes moved"
        elif hit:
            why = f"the commits since it was queued can move lane(s) {' '.join(hit)} of this sweep"
        if why:
            say(f"not started: {why}. Queue it again at the new sha ({start[:10]}).")
            if raw:
                print("\n".join(raw.splitlines()[:40]), flush=True)
            record(f"refused: {why} (between {queued} and {start})")
            return 5
        say(f"nothing since {queued[:10]} can move a lane of this sweep")
    if a.check_only:
        say(f"start check passed for {' '.join(lanes)} at {start[:10]}; --check-only, nothing run")
        record(f"ended {stamp()} exit 0 (check only)")
        return 0

    stop_file = rq.office() / "sweep-STOP"
    code, done, mine, kept, outcome, state = 0, [], None, None, "", {}
    no_verdict = no_verdict_exits()
    mark = reflog_mark()
    # the longest the freeze can be needed: each lane's limit, and with a resource each lane's wait in the queue
    max_s = (a.max_per_lane + ((a.wait or 4 * 3600) if use_rq else 0)) * len(lanes)
    rq.on_stop_signals()  # a TERM, HUP or BREAK now ends the sweep through the `finally` below, as an interrupt does
    try:
        (out / "alive").write_text(f"{os.getpid()} {stamp()}\n", encoding="utf-8")
        lock_on(a.id, out)
        if fz and fz.get("why") != WHY:
            kept = fz
            say(f"this id's own freeze is on already ({fz.get('why')}); the sweep runs under it and leaves it on: "
                "it did not write it, so lifting it is yours")
            record(f"freeze_kept by {fz.get('by')} at {fz.get('at')!r}: on before the sweep, not the sweep's to lift")
        else:
            if fz:
                say(f"taking over this id's own freeze, left on since {stamp(fz.get('at'))} by a sweep that no longer runs")
            mine = freeze_on(a.id, max_s, out)
            record(f"freeze by {mine['by']} at {mine['at']!r}: written by this sweep, lifted at its end")
            say(f"the freeze is on for {a.id} until the sweep ends")
        say(f"counted runs at {start[:10]} for {a.id}: {' '.join(lanes)}"
            + (f" (each through the queue as {a.id}-sweep, prio 0, every seat)" if use_rq else ""))
        for lane in lanes:
            if stop_file.exists():
                say(f"{stop_file} is there: paused before {lane}")
                break
            if not freeze_is(mine or kept):
                # the freeze the sweep runs under is read again before every lane: without it nothing holds the
                # main checkout still for the lane
                now_fz = freeze_read()
                who = ("it was lifted (freeze.json is gone)" if not now_fz else
                       f"it was replaced by one by {now_fz.get('by')} ({now_fz.get('why')})")
                say(f"the freeze this sweep runs under is no longer {'its own' if mine else 'the one it started under'}: "
                    f"{who}. Stopped before {lane}; {lane} and the lanes after it are not run (that is not a verdict).")
                record(f"freeze_lost before {lane}: {who}")
                code = 3
                break
            changed = tree_change(start, mark)
            if changed:
                say(f"the tree being counted changed before {lane}; stopped. {lane} and the lanes after it are "
                    "not run (that is not a verdict):")
                print("\n".join(changed), flush=True)
                code = 4
                break
            t0 = time.time()
            with open(out / "started.tsv", "a", encoding="utf-8") as f:
                f.write(f"{lane}\t{stamp(t0)}\t{start}\n")
            say(f"{stamp(t0)[11:]} {lane}: {counted.replace('<lane>', lane)}")
            try:
                rc, note = run_lane(a, lane, counted.replace("<lane>", lane), out, use_rq, state)
            finally:
                if state.get("job_object"):  # Windows, no resource: how the lane's command was put in a job object
                    record(f"job_object {lane}: {state.pop('job_object')}")
            t1 = time.time()
            # the tree is read again after every lane: a change during the last lane is found too, and the lane it
            # happened under carries the mark
            not_run = bool(note)
            changed = [] if not_run else tree_change(start, mark)
            # the command ran and ended by itself, with an exit code that says it gave no verdict
            silent = not not_run and rc in no_verdict
            notes = ([note] if note else []) + ([f"no verdict (exit {rc})"] if silent else [])
            if changed:
                notes.append("tree changed during this lane: " + "; ".join(c.strip() for c in changed))
            note = "; ".join(notes)
            with open(out / "runs.tsv", "a", encoding="utf-8") as f:
                f.write("\t".join([lane, str(rc), stamp(t0), stamp(t1), str(int(t1 - t0))]
                                  + ([note.replace("\t", " ").replace("\n", " ")] if note else [])) + "\n")
            if not_run:
                say(f"{lane}: {note}; stopped. See {rel}/{lane}.log")
                code = 6
                break
            done.append((lane, rc, bool(changed), silent))
            say(f"{stamp(t1)[11:]} {lane} exit {rc} after {rq.span(int(t1 - t0))}"
                + (" (no verdict: its command ran and wrote none; the sweep goes on)" if silent
                   else "" if rc == 0 else " (the sweep goes on; the grader reads the run)"))
            if changed:
                say(f"the tree being counted changed during {lane}; stopped. Its row in runs.tsv carries the note, "
                    "and the lanes after it are not run (that is not a verdict):")
                print("\n".join(changed), flush=True)
                code = 4
                break
        if code == 0 and any(d[3] for d in done):
            code = 1  # nothing stopped the sweep, and a lane gave no verdict
    except BaseException as e:
        rq.quiet_signals()
        stopped = isinstance(e, KeyboardInterrupt) or (isinstance(e, SystemExit) and isinstance(e.code, int)
                                                       and e.code > 128)
        outcome = "interrupted" if stopped else f"failed ({type(e).__name__}: {e})"
        if stopped:
            say("stopped by an interrupt or a signal: the lane in flight was ended and is not run (VOID); "
                "the lanes left are not run")
        raise
    finally:
        rq.quiet_signals()
        if state.get("killed"):
            told = (f"rq.py did not end within {STOP_WAIT} s of the stop and was killed: the seats of "
                    f"{a.id}-sweep may still be held and the lane's command may still be running. See "
                    f"`{P.tool('rq.py')} status`; the manager frees a seat with `{P.tool('rq.py')} force-release "
                    "--by <MGR id> --note \"sweep stopped\" [--seat NAME]`")
            print("sweep: " + told, file=sys.stderr, flush=True)
            record("killed " + told)
        if mine and not freeze_off(mine):
            say("the freeze in force is no longer the one this sweep wrote; it is left as it is")
            record("freeze_left: the freeze in force at the end was not the one this sweep wrote; not removed")
        lock_off(out)
        try:
            (out / "alive").unlink()
        except OSError:
            pass
        record(f"ended {stamp()} " + (outcome or f"exit {code}"))

    def named(rows):
        return ", ".join(f"{l} exit {rc}" + (", the tree changed during it" if ch else "") for l, rc, ch, _ in rows)

    gave, none = [d for d in done if not d[3]], [d for d in done if d[3]]
    say(f"ended, exit {code}: {len(done)} of {len(lanes)} lane(s) run"
        + (f": {len(gave)} gave a verdict" + (f" ({named(gave)})" if gave else "")
           + f", {len(none)} gave no verdict" + (f" ({named(none)})" if none else "") if done else "")
        + (f"; not run: {' '.join(lanes[len(done):])}" if len(done) < len(lanes) else ""))
    recs = " ".join(records()) or "the run's records"
    say(f"the sweep commits nothing. {a.id}: commit the run's records ({recs}) as the run's own commit, before "
        f"anything else touches {P.get('main_branch') or 'main'}. The logs and tables are in {rel}.")
    return code


# --- status ---

def _rows(path):
    try:
        return [l.split("\t") for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    except OSError:
        return []


def sweep_facts(out, now=None):
    """What status prints, as a dict: planned, run and not_run [(lane, exit, seconds, note)] (not_run: the rows
    whose note says the queue never ran the lane), flight, alive, left, ended, killed."""
    now = time.time() if now is None else now
    src = {}
    try:
        for l in (out / "source.txt").read_text(encoding="utf-8").splitlines():
            k, _, v = l.partition(" ")
            src.setdefault(k, v)
    except OSError:
        return None
    planned = src.get("lanes", "").split()
    runs = _rows(out / "runs.tsv")
    started = [r[0] for r in _rows(out / "started.tsv")]
    run_names = [r[0] for r in runs]
    flight = [l for l in started if l not in run_names]
    try:
        fresh = now - (out / "alive").stat().st_mtime <= ALIVE_S
    except OSError:
        fresh = False
    rows = [(r[0], r[1] if len(r) > 1 else "?", r[4] if len(r) > 4 else "?", r[5] if len(r) > 5 else "") for r in runs]
    return {"id": src.get("id", "?"), "planned": planned, "queued_at": src.get("queued_at", ""),
            "started_at": src.get("started_at", ""), "refused": src.get("refused:", ""), "ended": src.get("ended", ""),
            "killed": src.get("killed", ""),
            "run": [r for r in rows if not r[3].startswith(("not run", "no verdict"))],
            "no_verdict": [r for r in rows if r[3].startswith("no verdict")],
            "not_run": [r for r in rows if r[3].startswith("not run")],
            "flight": flight, "alive": fresh and "ended" not in src,
            "left": [l for l in planned if l not in started]}


def cmd_status(a):
    out = Path(a.out)
    out = out if out.is_absolute() else P.main / out
    f = sweep_facts(out)
    if f is None:
        say(f"{a.out} is not a sweep's folder (no source.txt)")
        return 2
    say(f"{f['id']}: {' '.join(f['planned'])} at {f['started_at'][:10]}"
        + (f" (queued at {f['queued_at'][:10]})" if f["queued_at"] != f["started_at"] else ""))
    if f["refused"]:
        print(f"  refused: {f['refused']}")
    print(f"  run ({len(f['run'])}):" + ("" if f["run"] else " none"))
    for lane, rc, secs, note in f["run"]:
        took = rq.span(int(secs)) if secs.isdigit() else secs
        print(f"    {lane}  exit {rc}  {took}" + (f"  {note}" if note else ""))
    if f["no_verdict"]:
        print(f"  run, with no verdict ({len(f['no_verdict'])}; the command ran and gave none):")
        for lane, rc, secs, note in f["no_verdict"]:
            took = rq.span(int(secs)) if secs.isdigit() else secs
            print(f"    {lane}  exit {rc}  {took}  {note}")
    if f["not_run"]:
        print(f"  not run by the queue ({len(f['not_run'])}; that is not a verdict):")
        for lane, rc, secs, note in f["not_run"]:
            print(f"    {lane}  exit {rc}  {note}")
    for lane in f["flight"]:
        if f["alive"]:
            print(f"  in flight: {lane}")
        else:
            print(f"  in flight: {lane}: no sweep is alive, so it was cut off. VOID: not run")
    print(f"  left ({len(f['left'])}): {' '.join(f['left']) or 'none'}"
          + (" (not run; that is not a verdict)" if f["left"] and not f["alive"] else ""))
    print(f"  the sweep: {'running' if f['alive'] else 'ended ' + f['ended'] if f['ended'] else 'not running, and it wrote no end line'}")
    if f["killed"]:
        print(f"  {f['killed']}")
    return 0


# --- the scratch project the selftest and tests/sweep_test.py run on ---

FAKE = r'''import json, os, subprocess, sys, time
from pathlib import Path
lane = sys.argv[1]
root = Path(__file__).resolve().parent.parent
office = Path(os.environ["FAKE_OFFICE"])
seen = root / "out" / "fake"
seen.mkdir(parents=True, exist_ok=True)


def read(p):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


facts = {"seat": os.environ.get("FOUNDRY_SEAT"), "seats": os.environ.get("FOUNDRY_SEATS"),
         "cwd": os.getcwd(), "freeze": read(office / "freeze.json"), "hold": read(office / "rq.lock" / "hold.json"),
         "lock": read(office / "sweep.lock"), "token": os.environ.get("FOUNDRY_RQ_TOKEN")}
(seen / (lane + ".json")).write_text(json.dumps(facts), encoding="utf-8")
series = root / "gym" / "series"
series.mkdir(parents=True, exist_ok=True)
with open(series / (lane + ".json"), "a", encoding="utf-8") as f:
    f.write(json.dumps({"lane": lane, "at": time.time()}) + "\n")
print("fake counted run of", lane, flush=True)
if lane in os.environ.get("FAKE_DIRTY", "").split():
    (root / "stray.txt").write_text("x", encoding="utf-8")
if lane in os.environ.get("FAKE_COMMIT", "").split():
    subprocess.run(["git", "-C", str(root), "commit", "-q", "--allow-empty", "-m", "moved under the sweep"])
if lane in os.environ.get("FAKE_COMMIT_RESET", "").split():
    subprocess.run(["git", "-C", str(root), "commit", "-q", "--allow-empty", "-m", "made and taken back under the sweep"])
    subprocess.run(["git", "-C", str(root), "reset", "-q", "--soft", "HEAD~1"])
if lane in os.environ.get("FAKE_SPOOF", "").split():
    tok = os.environ.get("FOUNDRY_RQ_TOKEN", "")
    print("rq: started [" + tok + "]\nrq: finished exit 124 [" + tok + "]\nrq: finished exit 0 [" + tok + "]", flush=True)
if lane in os.environ.get("FAKE_UNFREEZE", "").split():
    (office / "freeze.json").unlink()
if lane in os.environ.get("FAKE_REFREEZE", "").split():
    (office / "freeze.json").write_text(json.dumps(dict(facts["freeze"] or {}, at=time.time(), sweep="")), encoding="utf-8")
if lane in os.environ.get("FAKE_SLEEP", "").split():
    (seen / (lane + ".started")).write_text(str(os.getpid()), encoding="utf-8")
    time.sleep(float(os.environ.get("FAKE_SLEEP_S", "8")))
    (seen / (lane + ".slept")).write_text("x", encoding="utf-8")
if lane in os.environ.get("FAKE_EXIT1", "").split():
    sys.exit(1)
sys.exit(3 if lane in os.environ.get("FAKE_FAIL", "").split() else 0)
'''

TABLE = '''[lanes.G1]
paths = ["src/a/"]
[lanes.G2]
paths = ["src/b/"]
[lanes.G3]
paths = ["src/c/"]
'''


class Scratch:
    """A scratch git repository in a temp folder with a three-lane gym, a fake measure.counted and a profile kept
    outside the tree. Git's identity comes from the environment; nothing here runs `git config`."""

    def __init__(self, tmp, resource=False, counted=None):
        # resolved once, here: a temp folder is often reached through a link or a short name (macOS /var, a
        # Windows runner's RUNNER~1), and a child's cwd comes back under the real spelling
        self.tmp = Path(tmp).resolve()
        self.repo = self.tmp / "proj"
        self.office = self.repo / "out" / "foundry"
        self.profile = self.tmp / "foundry.toml"
        for d in ("gym", "fake", "src/a", "src/b", "src/c", "docs"):
            (self.repo / d).mkdir(parents=True)
        (self.repo / ".gitignore").write_text("/out/\n", encoding="utf-8")
        (self.repo / "gym" / "run.py").write_text('LANES = {\n    "G1": 1,\n    "G2": 2,\n    "G3": 3,\n}\n', encoding="utf-8")
        (self.repo / "gym" / "lane-inputs.toml").write_text(TABLE, encoding="utf-8")
        (self.repo / "fake" / "counted.py").write_text(FAKE, encoding="utf-8")
        for d in "abc":
            (self.repo / "src" / d / "code.txt").write_text("1\n", encoding="utf-8")
        py = str(sys.executable).replace("\\", "/")
        self.counted = f'"{py}" fake/counted.py <lane>' if counted is None else counted
        self.write_profile(resource)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(("FOUNDRY_", "FAKE_", "GIT_"))}
        self.env.update(FOUNDRY_ROOT=str(self.repo), FOUNDRY_MAIN=str(self.repo), FOUNDRY_PROFILE=str(self.profile),
                        FAKE_OFFICE=str(self.office), GIT_AUTHOR_NAME="sweep-test", GIT_COMMITTER_NAME="sweep-test",
                        GIT_AUTHOR_EMAIL="sweep-test@example.invalid", GIT_COMMITTER_EMAIL="sweep-test@example.invalid")
        self.git("init", "-q", "-b", "main")
        self.commit("start")

    def write_profile(self, resource=False, counted=None, measure="", more=""):
        """`measure` is more lines for the [measure] table, `more` for the [resource] table."""
        counted = self.counted if counted is None else counted
        text = f"project = \"scratch\"\n[measure]\ncounted = '{counted}'\nrecords = [\"gym/series\"]\n{measure}"
        if resource:
            text += '[resource]\nname = "bench"\nseats = ["a", "b"]\n' + more
        self.profile.write_text(text, encoding="utf-8")

    def git(self, *args):
        r = subprocess.run(["git", "-C", str(self.repo), *args], capture_output=True, text=True, env=self.env)
        if r.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)}: {r.stdout}{r.stderr}")
        return r.stdout.strip()

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", message)
        return self.git("rev-parse", "HEAD")

    def sweep(self, *args, **more):
        r = subprocess.run([sys.executable, str(HERE / "sweep.py"), *args], capture_output=True, text=True,
                           env=dict(self.env, **more), timeout=300)
        return r.returncode, r.stdout + r.stderr

    def start(self, log, *args, **more):
        """A sweep started and left running, its output in the file `log`, in a process group of its own on
        Windows so stop() can reach it."""
        kw = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {}
        with open(log, "wb") as f:
            return subprocess.Popen([sys.executable, str(HERE / "sweep.py"), *args], stdout=f, stderr=subprocess.STDOUT,
                                    stdin=subprocess.DEVNULL, env=dict(self.env, **more), **kw)

    @staticmethod
    def stop(proc, sig=None):
        """Send a running sweep the stop it cleans up after: TERM (or `sig`), on Windows a BREAK to its group.
        Returns the exit code the sweep should end with, or None when the stop could not be sent."""
        import signal
        try:
            if os.name == "nt":
                proc.send_signal(signal.CTRL_BREAK_EVENT)
                return 128 + signal.SIGBREAK
            proc.send_signal(sig or signal.SIGTERM)
            return 130 if sig == signal.SIGINT else 128 + (sig or signal.SIGTERM)
        except (OSError, ValueError):
            return None

    def wait_for(self, cond, limit=60):
        end = time.time() + limit
        while time.time() < end and not cond():
            time.sleep(0.1)
        return bool(cond())

    def seen(self, lane):
        try:
            return json.loads((self.repo / "out" / "fake" / f"{lane}.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def rows(self, name):
        return _rows(self.repo / "out" / "sweeps" / name / "runs.tsv")

    def source(self, name):
        try:
            return (self.repo / "out" / "sweeps" / name / "source.txt").read_text(encoding="utf-8")
        except OSError:
            return ""


def selftest():
    """The sweep's rules on a scratch project with no shared resource; tests/sweep_test.py adds the queue."""
    import stat
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="foundry-sweep-selftest-")).resolve()
    alt = tmp.parent / (tmp.name + "-alt")  # a second spelling of tmp (a link or a junction), made further down
    ok, bad, skipped = [], [], []

    def expect(what, cond, detail=""):
        (ok if cond else bad).append(what + ("" if cond else f": {detail}"))

    def unlink_alt():
        for rm in (os.unlink, os.rmdir):
            try:
                rm(alt)
                return
            except OSError:
                continue
    try:
        s = Scratch(tmp)
        out_dir = s.repo / "out" / "sweeps"

        # refusals before anything is written
        s.write_profile(counted="")
        rc, o = s.sweep("run", "--id", "MGR-9", "--out", "out/sweeps/r0")
        expect("an empty measure.counted is refused at the start (exit 2) with where to name it",
               rc == 2 and "measure.counted is empty" in o and not (out_dir / "r0").exists(), (rc, o))
        s.write_profile(counted="make counted")
        rc, o = s.sweep("run", "--id", "MGR-9", "--out", "out/sweeps/r0")
        expect("a measure.counted with no <lane> is refused (exit 2)", rc == 2 and "no <lane>" in o, (rc, o))
        s.write_profile()
        rc, o = s.sweep("run", "--id", "MGR-9", "--out", "runs/s1")
        expect("--out outside a git-ignored folder is refused (exit 2)",
               rc == 2 and "git-ignored" in o and not (s.repo / "runs").exists(), (rc, o))
        rc, o = s.sweep("run", "--id", "MGR-9", "--out", str(tmp / "elsewhere"))
        expect("--out outside the main checkout is refused (exit 2)", rc == 2 and "not inside the main checkout" in o, (rc, o))
        (out_dir / "old").mkdir(parents=True)
        rc, o = s.sweep("run", "--id", "MGR-9", "--out", "out/sweeps/old")
        expect("--out that exists is refused (exit 2): a sweep's folder is never used twice",
               rc == 2 and "never used twice" in o and not (out_dir / "old" / "source.txt").exists(), (rc, o))
        rc, o = s.sweep("run", "--id", "sweeper", "--out", "out/sweeps/r1")
        expect("an --id that is not a badge id is refused (exit 2)", rc == 2 and "badge id" in o, (rc, o))
        rc, o = s.sweep("run", "--id", "MGR-9", "--out", "out/sweeps/r1", "--max-per-lane", "180")
        expect("--max-per-lane with a bare number is refused (exit 2) and told to write a unit",
               rc == 2 and rq.UNIT_HINT in o and not (out_dir / "r1").exists(), (rc, o))
        rc, o = s.sweep("run", "--id", "MGR-9", "--out", "out/sweeps/r1", "--lanes", "G1 G1")
        expect("a lane named twice is refused (exit 2)", rc == 2 and "twice" in o, (rc, o))
        rc, o = s.sweep("run", "--id", "MGR-9", "--out", "out/sweeps/r1", "--queued-at", "0123456789abcdef")
        expect("a --queued-at that is no commit is refused (exit 2)", rc == 2 and "not a commit" in o, (rc, o))

        # a dirty tree at the start
        (s.repo / "note.txt").write_text("x", encoding="utf-8")
        rc, o = s.sweep("run", "--id", "MGR-9", "--out", "out/sweeps/d1")
        expect("an untracked file in the main checkout stops the start (exit 4), named, with nothing written",
               rc == 4 and "note.txt" in o and not (out_dir / "d1").exists(), (rc, o))
        (s.repo / "note.txt").unlink()

        # someone else's freeze
        s.office.mkdir(parents=True, exist_ok=True)
        (s.office / "freeze.json").write_text(json.dumps({"by": "EMP-1", "why": "counted run", "lane": "G1",
                                                          "at": time.time(), "max_s": 600}), encoding="utf-8")
        rc, o = s.sweep("run", "--id", "MGR-9", "--out", "out/sweeps/f1")
        expect("someone else's freeze stops the start (exit 3) and stays as it was",
               rc == 3 and "EMP-1" in o and not (out_dir / "f1").exists()
               and freeze_owner(s.office) == "EMP-1", (rc, o))
        (s.office / "freeze.json").write_text("{broken", encoding="utf-8")
        rc, o = s.sweep("run", "--id", "MGR-9", "--out", "out/sweeps/f2")
        expect("a freeze file that cannot be read counts as someone's freeze (exit 3)",
               rc == 3 and "unknown" in o and not (out_dir / "f2").exists(), (rc, o))
        (s.office / "freeze.json").write_text(json.dumps({"by": "MGR-9", "why": WHY, "lane": None,
                                                          "at": time.time() - 9000, "max_s": 600}), encoding="utf-8")

        # the whole run: every lane the gym knows, one failing, the freeze on for the run and off after
        rc, o = s.sweep("run", "--id", "MGR-9", "--out", "out/sweeps/s1", "--max-per-lane", "10m", FAKE_FAIL="G2")
        rows = s.rows("s1")
        expect("with no --lanes every lane of the gym's run.py is run, in its order",
               [r[0] for r in rows] == ["G1", "G2", "G3"], (rc, o))
        expect("a lane that exits non-zero does not stop the sweep: its exit code is in runs.tsv",
               [r[1] for r in rows] == ["0", "3", "0"], (rc, rows, o))
        expect("a lane whose exit code says no verdict (3: the runner failed) carries the note on its row, the others "
               "none, and the sweep itself exits 1",
               rc == 1 and [len(r) for r in rows] == [5, 6, 5] and rows[1][5] == "no verdict (exit 3)", (rc, rows, o))
        expect("the summary line counts the lanes that gave a verdict and those that gave none apart",
               "ended, exit 1: 3 of 3 lane(s) run: 2 gave a verdict (G1 exit 0, G3 exit 0), 1 gave no verdict (G2 exit 3)"
               in o, o)
        expect("each lane's output is in its own log", all("fake counted run of " + l in
               (out_dir / "s1" / f"{l}.log").read_text(encoding="utf-8") for l in ("G1", "G2", "G3")))
        fz = [s.seen(l).get("freeze") or {} for l in ("G1", "G2", "G3")]
        expect("with no shared resource the freeze is on for the whole run: by the badge id, why, lane null, max_s",
               all(f.get("by") == "MGR-9" and f.get("why") == WHY and f.get("lane") is None and f.get("max_s") == 1800
                   and isinstance(f.get("at"), (int, float)) for f in fz) and fz[0].get("at") == fz[2].get("at"), fz)
        expect("... an own freeze left on by a cut-off sweep is taken over, and the freeze is off at the end",
               "taking over" in o and not (s.office / "freeze.json").exists(), o)
        expect("a lane runs in the main checkout, with no queue hold",
               same_path(s.seen("G1").get("cwd", ""), s.repo) and s.seen("G1").get("hold") is None,
               (s.seen("G1"), str(s.repo)))
        src = s.source("s1")
        sha = s.git("rev-parse", "HEAD")
        expect("source.txt has the id, the sha queued at and started at, the lanes, and the end",
               f"id MGR-9\nqueued_at {sha}\nstarted_at {sha}\n" in src and "\nlanes G1 G2 G3\n" in src
               and "\nresource none\n" in src and "\nended " in src and src.rstrip().endswith("exit 1"), src)
        expect("the records the lanes wrote do not stop the later lanes, and the sweep commits nothing",
               s.git("rev-parse", "HEAD") == sha and "gym/series/G1.json" in s.git("status", "--porcelain", "--untracked-files=all"))
        tail = o.strip().splitlines()[-1]
        expect("the last line tells whoever queued it to commit the run's records before anything else touches main",
               "commits nothing" in tail and "MGR-9" in tail and "gym/series" in tail and "main" in tail, tail)
        rc, o = s.sweep("status", "--out", "out/sweeps/s1")
        expect("status lists the lanes run with their exit codes, the one with no verdict under its own heading, "
               "none in flight, none left",
               rc == 0 and "run (2)" in o and "run, with no verdict (1" in o and "G2  exit 3" in o
               and "no verdict (exit 3)" in o and "in flight" not in o and "left (0): none" in o, (rc, o))
        rc, o = s.sweep("run", "--id", "MGR-9", "--out", "out/sweeps/s2")
        expect("a sweep does not start on the last sweep's uncommitted records (exit 4)",
               rc == 4 and "gym/series" in o, (rc, o))
        s.commit("the sweep's records")
        rc, o = s.sweep("run", "--id", "MGR-9", "--out", "out/sweeps/v1", "--lanes", "G1 G2", FAKE_EXIT1="G1")
        expect("a lane that exits 1 (a verdict that is not PASS) gave a verdict: no note, and the sweep exits 0",
               rc == 0 and [(r[1], len(r)) for r in s.rows("v1")] == [("1", 5), ("0", 5)]
               and "2 gave a verdict (G1 exit 1, G2 exit 0), 0 gave no verdict" in o, (rc, s.rows("v1"), o))
        s.commit("records")
        s.write_profile(measure="no_verdict_exits = [1, 7]\n")
        rc, o = s.sweep("run", "--id", "MGR-9", "--out", "out/sweeps/v2", "--lanes", "G1 G2 G3", FAKE_EXIT1="G1", FAKE_FAIL="G2")
        rows = s.rows("v2")
        expect("measure.no_verdict_exits names the exit codes that mean no verdict: with [1, 7] an exit 1 is one and "
               "an exit 3 is not (sweep exit 1)",
               rc == 1 and [(r[1], len(r)) for r in rows] == [("1", 6), ("3", 5), ("0", 5)]
               and rows[0][5] == "no verdict (exit 1)", (rc, rows, o))
        s.commit("records")
        s.write_profile(measure="no_verdict_exits = []\n")
        rc, o = s.sweep("run", "--id", "MGR-9", "--out", "out/sweeps/v3", "--lanes", "G2", FAKE_FAIL="G2")
        expect("an empty measure.no_verdict_exits sets no exit code apart (sweep exit 0)",
               rc == 0 and [(r[1], len(r)) for r in s.rows("v3")] == [("3", 5)], (rc, s.rows("v3"), o))
        s.write_profile()
        s.commit("the sweep's records")

        # the tree changes under the sweep
        rc, o = s.sweep("run", "--id", "MGR-9", "--out", "out/sweeps/c1", FAKE_DIRTY="G1")
        expect("a file that appears in the tree stops the sweep before the next lane (exit 4), named",
               rc == 4 and "stray.txt" in o and [r[0] for r in s.rows("c1")] == ["G1"] and "not run: G2 G3" in o, (rc, o))
        expect("... and the freeze is off after the stop", not (s.office / "freeze.json").exists())
        row = (s.rows("c1") or [[]])[0]
        expect("... and the lane during which the tree changed carries the note on its runs.tsv row, with the path",
               len(row) == 6 and row[5].startswith("tree changed during this lane:") and "stray.txt" in row[5], row)
        rc, o = s.sweep("status", "--out", "out/sweeps/c1")
        expect("status of a stopped sweep: one lane run, two left and not run",
               rc == 0 and "run (1)" in o and "left (2): G2 G3" in o and "not a verdict" in o and "exit 4" in o, (rc, o))
        expect("... and status shows the lane's note", "tree changed during this lane" in o and "stray.txt" in o, o)
        (s.repo / "stray.txt").unlink()
        s.commit("records")
        rc, o = s.sweep("run", "--id", "MGR-9", "--out", "out/sweeps/c2", "--lanes", "G2 G1", FAKE_COMMIT="G2")
        expect("a commit to the main branch under the sweep stops it before the next lane (exit 4)",
               rc == 4 and "HEAD moved" in o and [r[0] for r in s.rows("c2")] == ["G2"], (rc, o))
        expect("... and that lane's row says HEAD moved during it", "HEAD moved" in ((s.rows("c2") or [[]])[0] + [""] * 6)[5],
               s.rows("c2"))
        s.commit("records")
        rc, o = s.sweep("run", "--id", "MGR-9", "--out", "out/sweeps/c3", "--lanes", "G1 G3", FAKE_DIRTY="G3")
        rows = s.rows("c3")
        expect("a tree that changed during the last lane is found too (exit 4): that lane's row carries the note, "
               "the lane before it none",
               rc == 4 and [r[0] for r in rows] == ["G1", "G3"] and len(rows[0]) == 5 and len(rows[1]) == 6
               and "tree changed during this lane" in rows[1][5] and "stray.txt" in rows[1][5]
               and "the tree changed during it" in o and s.source("c3").rstrip().endswith("exit 4"), (rc, rows, o))
        (s.repo / "stray.txt").unlink()
        base = s.commit("records")

        # the sha it was queued at against the sha it starts at
        (s.repo / "docs" / "notes.md").write_text("a note\n", encoding="utf-8")
        s.commit("docs only")
        rc, o = s.sweep("run", "--id", "MGR-9", "--out", "out/sweeps/q1", "--queued-at", base, "--check-only")
        src = s.source("q1")
        expect("--queued-at: commits that can move no lane do not stop the start; --check-only runs nothing (exit 0)",
               rc == 0 and "nothing since" in o and "start check passed" in o and f"queued_at {base}\n" in src
               and f"started_at {s.git('rev-parse', 'HEAD')}\n" in src and not s.rows("q1")
               and not (s.office / "freeze.json").exists(), (rc, o, src))
        (s.repo / "src" / "b" / "code.txt").write_text("2\n", encoding="utf-8")
        s.commit("a change in G2's inputs")
        rc, o = s.sweep("run", "--id", "MGR-9", "--out", "out/sweeps/q2", "--queued-at", base[:12], "--lanes", "G1 G3",
                        "--check-only")
        expect("--queued-at: a commit that moves a lane this sweep does not run does not stop it",
               rc == 0 and "moved_selects G2" in s.source("q2"), (rc, o, s.source("q2")))
        rc, o = s.sweep("run", "--id", "MGR-9", "--out", "out/sweeps/q3", "--queued-at", base)
        src = s.source("q3")
        expect("--queued-at: a commit that can move a lane of the sweep stops the start (exit 5): queue it again",
               rc == 5 and "can move lane(s) G2" in o and "Queue it again at the new sha" in o
               and "refused: " in src and not s.rows("q3") and not (s.office / "freeze.json").exists(), (rc, o, src))
        rc, o = s.sweep("status", "--out", "out/sweeps/q3")
        expect("status of a refused sweep says why", rc == 0 and "refused:" in o and "run (0)" in o, (rc, o))

        # the main checkout under another spelling: --out through a link (a junction on Windows) to the same folder
        linked = False
        try:
            os.symlink(tmp, alt, target_is_directory=True)
            linked = True
        except (OSError, NotImplementedError, AttributeError):
            if os.name == "nt":
                linked = subprocess.run(["cmd", "/c", "mklink", "/J", str(alt), str(tmp)], capture_output=True).returncode == 0
        if linked:
            rc, o = s.sweep("run", "--id", "MGR-9", "--out", str(alt / "proj" / "out" / "sweeps" / "j1"), "--check-only")
            expect("--out given through a link to the main checkout is still inside it: paths are compared resolved",
                   rc == 0 and (out_dir / "j1" / "source.txt").exists(), (rc, o))
            unlink_alt()
        else:
            skipped.append("--out through a link to the main checkout: this host lets the test make neither a "
                           "symlink nor a junction")

        # the freeze is the sweep's own: a second sweep under the id, a freeze it did not write
        live = out_dir / "live"
        live.mkdir()
        (live / "alive").write_text("1 now\n", encoding="utf-8")
        (s.office / "freeze.json").write_text(json.dumps({"by": "MGR-9", "why": WHY, "lane": None, "at": time.time(),
                                                          "max_s": 600, "sweep": str(live)}), encoding="utf-8")
        rc, o = s.sweep("run", "--id", "MGR-9", "--out", "out/sweeps/m1", "--lanes", "G1")
        expect("a second sweep under the id refuses (exit 3) while the first one's `alive` is fresh, and leaves its freeze",
               rc == 3 and "still running" in o and not (out_dir / "m1").exists()
               and json.loads((s.office / "freeze.json").read_text(encoding="utf-8")).get("sweep") == str(live), (rc, o))
        old = time.time() - ALIVE_S - 30
        os.utime(live / "alive", (old, old))
        rc, o = s.sweep("run", "--id", "MGR-9", "--out", "out/sweeps/m2", "--lanes", "G1")
        fz = s.seen("G1").get("freeze") or {}
        expect("... once that `alive` is stale the freeze is taken over: rewritten as this sweep's, lifted at its end, "
               "and source.txt says the sweep wrote it",
               rc == 0 and "taking over" in o and not (s.office / "freeze.json").exists()
               and same_path(fz.get("sweep", ""), out_dir / "m2")
               and f"\nfreeze by MGR-9 at {fz.get('at')!r}: written by this sweep" in s.source("m2"), (rc, o, fz, s.source("m2")))
        s.commit("records")
        rc, o = s.sweep("run", "--id", "MGR-9", "--out", "out/sweeps/m3", "--lanes", "G1", FAKE_REFREEZE="G1")
        expect("a freeze the sweep did not write is never removed: one that replaced its own during the run (another "
               "`at`) is still there at the end, and source.txt says it was left",
               rc == 0 and freeze_owner(s.office) == "MGR-9" and "\nfreeze_left" in s.source("m3"), (rc, o, s.source("m3")))
        s.commit("records")
        by_hand = {"by": "MGR-9", "why": "counted run, set by hand", "lane": None, "at": time.time(), "max_s": 600}
        (s.office / "freeze.json").write_text(json.dumps(by_hand), encoding="utf-8")
        rc, o = s.sweep("run", "--id", "MGR-9", "--out", "out/sweeps/m4", "--lanes", "G1")
        try:
            after = json.loads((s.office / "freeze.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            after = None
        expect("a freeze this id set by hand is not the sweep's: the sweep runs under it and leaves it on, unchanged",
               rc == 0 and after == by_hand and "\nfreeze_kept" in s.source("m4") and "taking over" not in o
               and (s.seen("G1").get("freeze") or {}).get("why") == by_hand["why"], (rc, o, after))
        (s.office / "freeze.json").unlink()
        s.commit("records")

        # the freeze is read again before every lane
        rc, o = s.sweep("run", "--id", "MGR-9", "--out", "out/sweeps/m5", "--lanes", "G1 G2", FAKE_UNFREEZE="G1")
        expect("a freeze lifted under the sweep stops it before the next lane (exit 3), saying it was lifted",
               rc == 3 and "it was lifted" in o and [r[0] for r in s.rows("m5")] == ["G1"] and "not run: G2" in o
               and "\nfreeze_lost before G2" in s.source("m5") and s.source("m5").rstrip().endswith("exit 3"),
               (rc, o, s.source("m5")))
        s.commit("records")
        rc, o = s.sweep("run", "--id", "MGR-9", "--out", "out/sweeps/m6", "--lanes", "G1 G2", FAKE_REFREEZE="G1")
        expect("a freeze replaced under the sweep stops it before the next lane (exit 3), saying by whom, and the "
               "new freeze stays",
               rc == 3 and "it was replaced by one by MGR-9" in o and [r[0] for r in s.rows("m6")] == ["G1"]
               and freeze_owner(s.office) == "MGR-9", (rc, o))
        (s.office / "freeze.json").unlink()
        s.commit("records")
        (s.office / "freeze.json").write_text(json.dumps(by_hand), encoding="utf-8")
        rc, o = s.sweep("run", "--id", "MGR-9", "--out", "out/sweeps/m7", "--lanes", "G1 G2", FAKE_UNFREEZE="G1")
        expect("... and so does the lifting of a hand-set freeze the sweep started under (exit 3)",
               rc == 3 and "the one it started under" in o and [r[0] for r in s.rows("m7")] == ["G1"], (rc, o))
        s.commit("records")

        # one sweep at a time, whatever freeze is on: sweep.lock in the office
        lock = {"id": "MGR-9", "out": str(live), "alive": str(live / "alive"), "at": time.time()}
        (s.office / "sweep.lock").write_text(json.dumps(lock), encoding="utf-8")
        (live / "alive").write_text("1 now\n", encoding="utf-8")
        (s.office / "freeze.json").write_text(json.dumps(by_hand), encoding="utf-8")
        rc, o = s.sweep("run", "--id", "MGR-9", "--out", "out/sweeps/k1", "--lanes", "G1")
        expect("under the id's hand-set freeze a second sweep is refused (exit 3) while sweep.lock names a sweep whose "
               "`alive` is fresh",
               rc == 3 and "still running" in o and "sweep.lock" in o and not (out_dir / "k1").exists()
               and json.loads((s.office / "sweep.lock").read_text(encoding="utf-8")) == lock, (rc, o))
        (s.office / "freeze.json").unlink()
        rc, o = s.sweep("run", "--id", "MGR-9", "--out", "out/sweeps/k1", "--lanes", "G1")
        expect("... and with no freeze on at all (exit 3)", rc == 3 and "still running" in o and not (out_dir / "k1").exists(),
               (rc, o))
        os.utime(live / "alive", (old, old))
        rc, o = s.sweep("run", "--id", "MGR-9", "--out", "out/sweeps/k2", "--lanes", "G1")
        seen_lock = s.seen("G1").get("lock") or {}
        expect("a lock whose `alive` went stale is a killed sweep's: the sweep starts, the lock names it while it runs "
               "and is gone at its end",
               rc == 0 and same_path(seen_lock.get("out", ""), out_dir / "k2") and seen_lock.get("id") == "MGR-9"
               and seen_lock.get("alive", "").endswith("alive") and not (s.office / "sweep.lock").exists(), (rc, o, seen_lock))
        s.commit("records")

        # HEAD moved and came back during a lane
        rc, o = s.sweep("run", "--id", "MGR-9", "--out", "out/sweeps/c4", "--lanes", "G1 G2", FAKE_COMMIT_RESET="G1")
        rows = s.rows("c4")
        expect("a commit made and reset away during a lane is seen in HEAD's reflog (exit 4): the lane's row says "
               "HEAD moved and came back, the next lane is not run",
               rc == 4 and [r[0] for r in rows] == ["G1"] and len(rows[0]) == 6
               and rows[0][5].startswith("tree changed during this lane: HEAD moved and came back")
               and "not run: G2" in o, (rc, rows, o))
        s.commit("records")

        # a freeze file nested too deep to read
        (s.office / "freeze.json").write_text("[" * 200000, encoding="utf-8")
        rc, o = s.sweep("run", "--id", "MGR-9", "--out", "out/sweeps/f3", "--lanes", "G1")
        expect("a freeze.json nested too deep to read counts as someone's unreadable freeze (exit 3), not a traceback",
               rc == 3 and "unknown" in o and "Traceback" not in o and not (out_dir / "f3").exists(), (rc, o[-600:]))
        (s.office / "freeze.json").unlink()

        # a stop sent to the sweep: the lane in flight is ended, the freeze lifted, the end line says interrupted
        t = time.time()
        p = s.start(tmp / "i1.log", "run", "--id", "MGR-9", "--out", "out/sweeps/i1", "--lanes", "G1 G2",
                    FAKE_SLEEP="G1", FAKE_SLEEP_S="6")
        up = s.wait_for((s.repo / "out" / "fake" / "G1.started").exists)
        t = time.time()
        on = freeze_owner(s.office)
        want = s.stop(p)
        try:
            rc = p.wait(timeout=60)
        except subprocess.TimeoutExpired:
            p.kill()
            rc = "still running 60 s after the stop"
        src = s.source("i1")
        no_break = os.name == "nt" and (want is None or rc == 0)
        if no_break:
            skipped.append("a stop sent to the sweep: this host delivers no BREAK (no console is attached)")
        else:
            expect("a stop sent to the sweep (TERM; on Windows BREAK) ends it through its cleanup: exit 128 + the "
                   "signal, and source.txt ends `interrupted`, never `exit 0`",
                   up and rc == want and "\nended " in src and src.rstrip().endswith("interrupted") and "exit 0" not in src,
                   (up, rc, want, src, (tmp / "i1.log").read_text(encoding="utf-8", errors="replace")))
            if os.name == "nt":
                expect("on Windows, with no resource, the lane's command is put in its job object before it runs "
                       "(rq.win_start), and source.txt says so",
                       "\njob_object G1: create ok, assign ok\n" in src, src)
            expect("... its freeze was on during the lane and is lifted by the stop",
                   on == "MGR-9" and not (s.office / "freeze.json").exists(), on)
            time.sleep(max(0.0, t + 7.5 - time.time()))
            expect("... and the lane in flight was ended with it: its command did not run on, and it has no row",
                   not (s.repo / "out" / "fake" / "G1.slept").exists() and not s.rows("i1"), s.rows("i1"))
            rc, o = s.sweep("status", "--out", "out/sweeps/i1")
            expect("status of a stopped sweep: the lane in flight reads VOID: not run, the end reads interrupted",
                   rc == 0 and "G1: no sweep is alive" in o and "VOID: not run" in o and "interrupted" in o
                   and "left (1): G2" in o, (rc, o))
        (s.office / "freeze.json").unlink(missing_ok=True)
        s.commit("records")

        # stop_child on its own: rq.py is given a moment to clean up; killed only when it does not end
        child = tmp / "child.py"
        child.write_text("import signal\nimport sys\nimport time\n"
                         "for n in ('SIGBREAK', 'SIGTERM'):\n"
                         "    if hasattr(signal, n) and sys.argv[1] == 'deaf':\n"
                         "        signal.signal(getattr(signal, n), signal.SIG_IGN)\n"
                         "print('up', flush=True)\ntime.sleep(60)\n", encoding="utf-8")
        got = {}
        for kind in ("hears", "deaf"):
            kw = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {}
            c = subprocess.Popen([sys.executable, str(child), kind], stdout=subprocess.PIPE, stdin=subprocess.DEVNULL, **kw)
            c.stdout.readline()
            t = time.time()
            got[kind] = (stop_child(c, True, None, wait=3), c.poll() is not None, time.time() - t < (3 if kind == "hears" else 20))
            c.stdout.close()
        if no_break:
            skipped.append("stop_child: this host delivers no BREAK (no console is attached)")
        else:
            expect("a child that ends at the stop inside the wait is not killed: its seats were its own to release",
                   got["hears"] == (False, True, True), got)
        expect("a child that does not end inside the wait is killed, and that is reported (the seats may still be held)",
               got["deaf"] == (True, True, True), got)
        log = f"rq: X-1-sweep queued\n{rq.RUNNING} a: make G1\n{rq.started_line('tk')}\nout"
        expect("a lane was run only when its log holds rq.py's `started` and `finished` lines with this lane's token "
               "and exit code; the `running in seat` line alone, another token or another exit code is not enough",
               lane_ran(log + rq.finished_line(1, "tk") + "\n", "tk", 1) == (True, True)
               and lane_ran(log + "\n", "tk", 1) == (True, False)
               and lane_ran(log + "\n" + rq.finished_line(0, "tk") + "\n", "tk", 1) == (True, False)
               and lane_ran(log.replace("[tk]", "[]") + "\n" + rq.finished_line(1, "") + "\n", "tk", 1) == (False, False)
               and lane_ran(f"rq: X-1-sweep queued\n{rq.RUNNING} a: make G1\nrq: cannot start the shell\n", "tk", 127)
               == (False, False) and lane_ran("", "tk", 0) == (False, False))
        expect("the queue's own last line is what a not-run note quotes, never a marker line",
               queue_word(log + "\nrq: X's job was still running at its limit\n", "tk")
               == "rq: X's job was still running at its limit")

        # a lane that was cut off
        cut = out_dir / "cut"
        cut.mkdir()
        (cut / "source.txt").write_text("id MGR-9\nqueued_at abc\nstarted_at abc\nlanes G1 G2 G3\n", encoding="utf-8")
        (cut / "started.tsv").write_text("G1\t2000-01-01 00:00:00\tabc\nG2\t2000-01-01 00:10:00\tabc\n", encoding="utf-8")
        (cut / "runs.tsv").write_text("G1\t0\t2000-01-01 00:00:00\t2000-01-01 00:10:00\t600\n", encoding="utf-8")
        rc, o = s.sweep("status", "--out", "out/sweeps/cut")
        expect("a lane in started.tsv with no line in runs.tsv and no sweep alive was cut off: VOID: not run",
               rc == 0 and "G2: no sweep is alive" in o and "VOID: not run" in o and "left (1): G3" in o
               and "G1  exit 0  10m" in o, (rc, o))
        (cut / "alive").write_text("1 now\n", encoding="utf-8")
        rc, o = s.sweep("status", "--out", "out/sweeps/cut")
        expect("with a fresh `alive` the same lane reads in flight, not VOID",
               rc == 0 and "in flight: G2" in o and "VOID" not in o and "running" in o, (rc, o))
        old = time.time() - ALIVE_S - 30
        os.utime(cut / "alive", (old, old))
        rc, o = s.sweep("status", "--out", "out/sweeps/cut")
        expect("an `alive` that went stale reads cut off again", "VOID: not run" in o, o)
        rc, o = s.sweep("status", "--out", "out/sweeps/nothing")
        expect("status of a folder that is no sweep's is exit 2", rc == 2, (rc, o))

        ro = tmp / "ro" / "deep"
        ro.mkdir(parents=True)
        (ro / "object").write_text("x", encoding="utf-8")
        os.chmod(ro / "object", stat.S_IREAD)
        rmtree(tmp / "ro")
        expect("rmtree removes a folder that holds a read-only file (git's objects, on Windows)", not (tmp / "ro").exists())
    finally:
        unlink_alt()
        rmtree(tmp)
    expect("the selftest leaves no temp folder behind (the scratch repository's read-only git objects included)",
           not tmp.exists(), str(tmp))
    for x in ok:
        print(f"  ok   {x}")
    for x in skipped:
        print(f"  skip {x}")
    for x in bad:
        print(f"  FAIL {x}")
    print(f"sweep selftest: {len(ok)} ok, {len(bad)} failed" + (f", {len(skipped)} skipped" if skipped else ""))
    return 1 if bad else 0


def freeze_owner(office_dir):
    try:
        return json.loads((Path(office_dir) / "freeze.json").read_text(encoding="utf-8")).get("by")
    except (OSError, ValueError):
        return None


def span_arg(s):
    try:
        v = rq.seconds(s)
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e))
    if v <= 0:
        raise argparse.ArgumentTypeError(f"{s!r} is no time at all; {rq.UNIT_HINT}")
    return v


def main():
    if sys.argv[1:2] == ["selftest"]:
        return selftest()
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd_name", required=True)
    r = sub.add_parser("run")
    r.add_argument("--id", required=True)
    r.add_argument("--out", required=True)
    r.add_argument("--lanes", default="")
    r.add_argument("--queued-at", default="")
    r.add_argument("--check-only", action="store_true")
    r.add_argument("--max-per-lane", type=span_arg, default=3 * 3600)
    r.add_argument("--wait", type=span_arg, default=0)
    r.add_argument("--touched", default="")
    s = sub.add_parser("status")
    s.add_argument("--out", required=True)
    a = p.parse_args()
    try:
        return {"run": cmd_run, "status": cmd_status}[a.cmd_name](a)
    except KeyboardInterrupt:
        say("interrupted")
        return 130


if __name__ == "__main__":
    sys.exit(main())
