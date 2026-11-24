"""Tests for tools/sweep.py, the counted sweep, on a scratch project in a temp folder.

    <python> tests/sweep_test.py

Runs the tool's own selftest (a project with no shared resource: the clean-tree stop, the queued-at check both
ways, a lane's failure not stopping the sweep, the out-folder refusals, the cut-off lane, the freeze on and off),
then the cases that need more:
- a scratch shared resource: each lane goes through the queue as <badge id>-sweep at prio 0 holding every seat,
  the sweep's own freeze is on for the whole run and off after it, the seats are free afterwards;
- a lane the queue refuses, or fails before running, stops the sweep (exit 6) and is recorded as not run, whatever
  the queue's exit code; a lane that itself exits 1 was run;
- a stop sent to the sweep (TERM; on Windows a BREAK) is passed on to rq.py: the lane's command is ended, the seats
  are released, the freeze is lifted, source.txt ends `interrupted`; a second sweep under the id refuses meanwhile;
- a gym with no run.py: the lanes are the *.json names under its prereg folder, in number order;
- a gym that names no lane: refused (exit 2);
- a sweep-STOP file in the office pauses the sweep before the next lane.
The scratch repository's git identity comes from the environment (never `git config`); the measure.counted command
is a small python script the scratch project carries. Nothing outside the temp folder is read or written, and no
real resource is used.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(TOOLS))
import sweep  # noqa: E402


def main() -> int:
    ok, bad, skipped = [], [], []

    def expect(name, cond, detail=""):
        (ok if cond else bad).append(name)
        print(("  ok   " if cond else "  FAIL ") + name + ("" if cond else f": {detail}"))

    def skip(name):
        skipped.append(name)
        print("  skip " + name)

    def text_of(path):
        try:
            return Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""

    st = subprocess.run([sys.executable, str(TOOLS / "sweep.py"), "selftest"], capture_output=True, text=True, timeout=600)
    print(st.stdout.strip().splitlines()[-1] if st.stdout.strip() else st.stderr.strip())
    expect("the tool's own selftest passes", st.returncode == 0, st.stdout[-2000:] + st.stderr[-2000:])

    # resolved at once: a temp folder is often reached through a link or a short name, and a child's cwd comes
    # back under the real spelling
    tmp = Path(tempfile.mkdtemp(prefix="foundry-sweep-test-")).resolve()

    def stopped_sweep(s, name, lane, sig=None, how="TERM; on Windows BREAK"):
        """Start a sweep whose first lane sleeps, try a second sweep under the id, send the first a stop, and check
        what both left."""
        fake = s.repo / "out" / "fake"
        for f in (fake / f"{lane}.started", fake / f"{lane}.slept"):
            f.unlink(missing_ok=True)
        log = tmp / f"{name}.log"
        p = s.start(log, "run", "--id", "MGR-9", "--out", f"out/sweeps/{name}", "--lanes", f"{lane} G3",
                    FAKE_SLEEP=lane, FAKE_SLEEP_S="6")
        up = s.wait_for((fake / f"{lane}.started").exists)
        t = time.time()
        held = [(s.office / n).is_dir() for n in ("rq.lock", "rq.lock.b")]
        rc2, o2 = s.sweep("run", "--id", "MGR-9", "--out", f"out/sweeps/{name}-second", "--lanes", "G2")
        on = sweep.freeze_owner(s.office)
        want = s.stop(p, sig)
        try:
            rc = p.wait(timeout=90)
        except subprocess.TimeoutExpired:
            p.kill()
            rc = "still running 90 s after the stop"
        src = s.source(name)
        if os.name == "nt" and (want is None or rc == 0):
            skip(f"a stop sent to a sweep with a shared resource ({how}): this host delivers no BREAK (no console "
                 "is attached)")
            return
        expect(f"a second sweep under the id refuses (exit 3) while the first runs, and leaves its freeze on ({how})",
               up and rc2 == 3 and "still running" in o2 and on == "MGR-9"
               and not (s.repo / "out" / "sweeps" / f"{name}-second").exists(), (up, rc2, o2, on))
        expect(f"a stop sent to the sweep ({how}) ends it through its cleanup: exit {want}, source.txt ends "
               "`interrupted`, never `exit 0`, and rq.py was not killed",
               up and rc == want and src.rstrip().endswith("interrupted") and "exit 0" not in src
               and "\nkilled " not in src, (up, rc, want, src, text_of(log)))
        last = text_of(s.office / "rq.last")
        expect("... the stop was passed on to rq.py, which released every seat it held and said so in rq.last",
               held == [True, True] and not (s.office / "rq.lock").exists() and not (s.office / "rq.lock.b").exists()
               and "MGR-9-sweep" in last and "stopped by" in last, (held, last))
        expect("... and the sweep's own freeze is lifted", not (s.office / "freeze.json").exists())
        time.sleep(max(0.0, t + 7.5 - time.time()))
        expect("... and the lane's command was ended with it: it did not run on, and the lane has no row",
               not (fake / f"{lane}.slept").exists() and not s.rows(name), s.rows(name))
        rc, o = s.sweep("status", "--out", f"out/sweeps/{name}")
        expect("... and status reads the lane in flight as VOID: not run, the end as interrupted",
               rc == 0 and "VOID: not run" in o and "interrupted" in o and "left (1): G3" in o, (rc, o))

    try:
        # a scratch shared resource with two seats
        s = sweep.Scratch(tmp / "res", resource=True)
        rc, o = s.sweep("run", "--id", "MGR-9", "--out", "out/sweeps/r1", "--lanes", "G1 G3", "--max-per-lane", "20m",
                        "--touched", "the bench", FAKE_FAIL="G1")
        rows = s.rows("r1")
        expect("with a shared resource both lanes run and the first one's failure does not stop the sweep",
               [(r[0], r[1]) for r in rows] == [("G1", "3"), ("G3", "0")], (rc, o, rows))
        expect("the first lane's exit 3 means its command ran and gave no verdict: the note is on its row, the "
               "summary sets it apart, and the sweep exits 1",
               rc == 1 and [len(r) for r in rows] == [6, 5] and rows[0][5] == "no verdict (exit 3)"
               and "2 of 2 lane(s) run: 1 gave a verdict (G3 exit 0), 1 gave no verdict (G1 exit 3)" in o, (rc, o, rows))
        holds = [s.seen(l).get("hold") or {} for l in ("G1", "G3")]
        expect("each lane holds the queue as <badge id>-sweep at prio 0, every seat, with its --max and job text",
               all(h.get("id") == "MGR-9-sweep" and h.get("prio") == 0 and h.get("all") is True and h.get("max") == 1200
                   and h.get("via") == "run" for h in holds)
               and [h.get("job") for h in holds] == ["counted sweep: G1", "counted sweep: G3"], holds)
        expect("the lane's command sees every seat held", [s.seen(l).get("seats") for l in ("G1", "G3")] == ["a,b", "a,b"],
               [s.seen(l) for l in ("G1", "G3")])
        fz = [s.seen(l).get("freeze") or {} for l in ("G1", "G3")]
        expect("with a shared resource the sweep's own freeze is on for the whole run (one freeze, both lanes: the "
               "queue id holds nothing between two lanes) and off at the end",
               all(f.get("by") == "MGR-9" and f.get("why") == sweep.WHY and f.get("lane") is None for f in fz)
               and fz[0].get("at") == fz[1].get("at") and isinstance(fz[0].get("at"), float)
               and fz[0].get("max_s") == 2 * (1200 + 4 * 3600) and not (s.office / "freeze.json").exists(), fz)
        expect("a lane runs in the main checkout, however the temp folder is spelled",
               sweep.same_path(s.seen("G1").get("cwd", ""), s.repo), (s.seen("G1").get("cwd"), str(s.repo)))
        expect("source.txt records the freeze the sweep wrote",
               f"\nfreeze by MGR-9 at {fz[0].get('at')!r}: written by this sweep" in s.source("r1"), s.source("r1"))
        last = (s.office / "rq.last").read_text(encoding="utf-8") if (s.office / "rq.last").exists() else ""
        expect("the seats are free afterwards and rq.last names the last lane and --touched",
               not (s.office / "rq.lock").exists() and not (s.office / "rq.lock.b").exists()
               and "MGR-9-sweep" in last and "counted sweep: G3 (exit 0)" in last and "touched: the bench" in last, last)
        log = (s.repo / "out" / "sweeps" / "r1" / "G1.log").read_text(encoding="utf-8")
        expect("the lane's log holds the queue's lines and the run's output",
               "rq: running in seat a" in log and "fake counted run of G1" in log, log)
        m = re.search(r"^rq: started \[([0-9a-f]{16})\]$", log, re.M)
        tok = m.group(1) if m else "no started line"
        expect("the lines the sweep looks for are the ones rq.py prints after it started the command and when the "
               "command ended by itself, both with the lane's own token (rq.STARTED, rq.FINISHED in both tools)",
               sweep.lane_ran(log, tok, 3) == (True, True) and sweep.lane_ran(log, tok, 0) == (True, False)
               and sweep.lane_ran(log, "", 3) == (False, False), (tok, log))
        g3 = re.search(r"^rq: started \[([0-9a-f]{16})\]$", text_of(s.repo / "out" / "sweeps" / "r1" / "G3.log"), re.M)
        expect("each lane has a token of its own, and the lane's command is not given it",
               bool(g3) and g3.group(1) != tok and all(s.seen(l).get("token") is None for l in ("G1", "G3")),
               [s.seen(l).get("token") for l in ("G1", "G3")])
        expect("source.txt names the resource", "\nresource bench\n" in s.source("r1"), s.source("r1"))
        st2 = subprocess.run([sys.executable, str(TOOLS / "rq.py"), "status", "--json"], capture_output=True, text=True,
                             env=s.env, timeout=60)
        try:
            j = json.loads(st2.stdout)
        except ValueError:
            j = {}
        expect("rq.py status --json reads the office the sweep left: both seats free, nothing counted",
               st2.returncode == 0 and [x.get("holder") for x in j.get("seats", [])] == [None, None]
               and j.get("counted") == {"holding": [], "waiting": []}, st2.stdout + st2.stderr)
        s.commit("records")

        # the queue refuses the lane: the id already holds a seat
        lk = s.office / "rq.lock"
        lk.mkdir(parents=True)
        (lk / "holder").write_text("MGR-9-sweep\n", encoding="utf-8")
        rc, o = s.sweep("run", "--id", "MGR-9", "--out", "out/sweeps/r2", "--lanes", "G2 G3")
        rows = s.rows("r2")
        expect("a lane the queue refuses stops the sweep (exit 6): recorded as not run, the next lane not started",
               rc == 6 and len(rows) == 1 and rows[0][0] == "G2" and rows[0][1] == "3" and "not run (the queue: exit 3)" in rows[0][5]
               and "not run: G2 G3" in o and not s.seen("G2"), (rc, o, rows))
        rc, o = s.sweep("status", "--out", "out/sweeps/r2")
        expect("status shows the refused lane with its note and the lane left",
               rc == 0 and "not run (the queue: exit 3)" in o and "left (1): G3" in o, (rc, o))
        expect("... and status counts it as not run, not among the lanes run",
               "run (0): none" in o and "not run by the queue (1" in o, o)
        expect("... and the freeze the sweep wrote is lifted after the stop", not (s.office / "freeze.json").exists())
        shutil.rmtree(lk)

        # the queue fails before it runs the lane, with exit 1: the code a lane's own non-PASS verdict has too
        (s.office / "rq.queue.json").write_text('[{"id": "EMP-1"}]', encoding="utf-8")  # an entry rq.py cannot read
        rc, o = s.sweep("run", "--id", "MGR-9", "--out", "out/sweeps/r2b", "--lanes", "G2 G3")
        rows = s.rows("r2b")
        expect("a lane the queue never ran is not recorded as run whatever rq.py's exit code (here rq.py itself "
               "failed, exit 1): the row carries the note, the sweep stops with exit 6",
               rc == 6 and len(rows) == 1 and rows[0][:2] == ["G2", "1"] and len(rows[0]) == 6
               and rows[0][5].startswith("not run (the queue: exit 1)") and "not run: G2 G3" in o and not s.seen("G2")
               and s.source("r2b").rstrip().endswith("exit 6"), (rc, o, rows))
        rc, o = s.sweep("status", "--out", "out/sweeps/r2b")
        expect("... and status counts it as not run", rc == 0 and "run (0): none" in o and "not run by the queue (1" in o
               and "not run (the queue: exit 1)" in o and "left (1): G3" in o, (rc, o))
        (s.office / "rq.queue.json").unlink()
        rc, o = s.sweep("run", "--id", "MGR-9", "--out", "out/sweeps/r2c", "--lanes", "G2 G3", FAKE_EXIT1="G2")
        rows = s.rows("r2c")
        expect("a lane the queue ran that exits 1 itself (a verdict that is not PASS) was run: no note, the sweep goes on",
               rc == 0 and [(r[0], r[1], len(r)) for r in rows] == [("G2", "1", 5), ("G3", "0", 5)], (rc, o, rows))
        s.commit("records")

        # the queue prints `running in seat` and then cannot start the shell (exit 127): the command never ran
        s.write_profile(resource=True, more='shell = "no-such-shell-here"\n')
        rc, o = s.sweep("run", "--id", "MGR-9", "--out", "out/sweeps/h1", "--lanes", "G2 G3")
        rows = s.rows("h1")
        log = text_of(s.repo / "out" / "sweeps" / "h1" / "G2.log")
        expect("a lane whose shell the queue could not start is not run (exit 6), though its log has the `running in "
               "seat` line: the row says the command was never started, with rq.py's reason; the next lane is not started",
               rc == 6 and "rq: running in seat" in log and len(rows) == 1 and rows[0][:2] == ["G2", "127"]
               and rows[0][5].startswith("not run (the queue: exit 127): its command was never started")
               and "cannot start the shell" in rows[0][5] and "0 of 2 lane(s) run; not run: G2 G3" in o, (rc, o, rows, log))
        # the queue ends the command at its limit (exit 124), and the command printed the marker words itself
        s.write_profile(resource=True, more='enforce_max = true\nmax_grace = "1s"\n')
        t = time.time()
        rc, o = s.sweep("run", "--id", "MGR-9", "--out", "out/sweeps/h2", "--lanes", "G2 G3", "--max-per-lane", "2s",
                        FAKE_SLEEP="G2", FAKE_SLEEP_S="8", FAKE_SPOOF="G2")
        rows = s.rows("h2")
        log = text_of(s.repo / "out" / "sweeps" / "h2" / "G2.log")
        expect("a lane the queue ended at its limit is not run (exit 6): started, and did not end by itself; the "
               "words `rq: started` and `rq: finished exit` printed by the command itself do not pass for the queue's",
               rc == 6 and len(rows) == 1 and rows[0][:2] == ["G2", "124"]
               and rows[0][5].startswith("not run (the queue: exit 124): its command was started and did not end by itself")
               and "rq: finished exit 124 []" in log and "rq: started []" in log and "not run: G2 G3" in o
               and time.time() - t < 8, (rc, o, rows, log))
        rc, o = s.sweep("status", "--out", "out/sweeps/h2")
        expect("... and status counts it as not run", rc == 0 and "run (0): none" in o and "not run by the queue (1" in o, o)
        s.write_profile(resource=True)
        time.sleep(1.0)
        s.commit("records")

        # a stop sent to the sweep while a lane holds the seats
        stopped_sweep(s, "i1", "G1")
        s.commit("records")
        if os.name == "nt":
            skip("POSIX only: an interrupt (INT, as Ctrl+C sends) to the sweep alone is passed on to rq.py the same way")
        else:
            import signal
            stopped_sweep(s, "i2", "G2", signal.SIGINT, "INT, as Ctrl+C sends, to the sweep alone")
            s.commit("records")

        # a sweep-STOP file pauses before the next lane
        (s.office / "sweep-STOP").write_text("", encoding="utf-8")
        rc, o = s.sweep("run", "--id", "MGR-9", "--out", "out/sweeps/r3", "--lanes", "G2")
        expect("a sweep-STOP file in the office pauses the sweep before the next lane (exit 0, nothing run)",
               rc == 0 and "paused before G2" in o and not s.rows("r3") and "not run: G2" in o, (rc, o))
        (s.office / "sweep-STOP").unlink()

        # the lane list without a run.py: the prereg folder's *.json names, in number order
        p = sweep.Scratch(tmp / "prereg")
        (p.repo / "gym" / "run.py").unlink()
        (p.repo / "gym" / "prereg").mkdir()
        for lane in ("G10", "G2", "G7"):
            (p.repo / "gym" / "prereg" / f"{lane}.json").write_text("{}", encoding="utf-8")
        (p.repo / "gym" / "prereg" / "notes.md").write_text("x", encoding="utf-8")
        p.commit("a gym with prereg files and no run.py")
        rc, o = p.sweep("run", "--id", "MGR-9", "--out", "out/sweeps/p1", "--check-only")
        expect("with no run.py the lanes are the prereg folder's *.json names, in number order",
               rc == 0 and "\nlanes G2 G7 G10\n" in p.source("p1"), (rc, o, p.source("p1")))
        for lane in ("G10", "G2", "G7"):
            (p.repo / "gym" / "prereg" / f"{lane}.json").unlink()
        p.commit("no lanes at all")
        rc, o = p.sweep("run", "--id", "MGR-9", "--out", "out/sweeps/p2")
        expect("a gym that names no lane is refused (exit 2) and told to give --lanes",
               rc == 2 and "--lanes" in o and not (p.repo / "out" / "sweeps" / "p2").exists(), (rc, o))
        rc, o = p.sweep("run", "--id", "MGR-9", "--out", "out/sweeps/p3", "--lanes", "G7")
        expect("--lanes runs a lane the gym does not list, with the freeze on during it and off after",
               rc == 0 and [r[0] for r in p.rows("p3")] == ["G7"] and (p.seen("G7").get("freeze") or {}).get("by") == "MGR-9"
               and not (p.office / "freeze.json").exists(), (rc, o))
    finally:
        sweep.rmtree(tmp)
    expect("the test leaves no temp folder behind (read-only git objects included)", not tmp.exists(), str(tmp))
    print(f"sweep_test: {len(ok)} ok, {len(bad)} failed" + (f", {len(skipped)} skipped" if skipped else ""))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
