#!/usr/bin/env python3
"""The counted-run guard of tools/board.py, tested against a scratch project.

    python tests/board_guard_test.py

Nothing in the checkout or its crew office is read or written: the project is a scratch folder (FOUNDRY_ROOT,
FOUNDRY_MAIN), its state is made by `board.py init`, the state and the map are scratch files (FOUNDRY_PATHS_STATE,
FOUNDRY_PATHS_MAP), the office is a scratch folder (FOUNDRY_PATHS_OFFICE), the shared resource is a made-up one
(FOUNDRY_RESOURCE_NAME, FOUNDRY_RESOURCE_SEATS), and FOUNDRY_SWEEP_GUARD says whether the run counts as the main
checkout (1) or as a worktree (0). Git never looks above the scratch folder (GIT_CEILING_DIRECTORIES), so the test
reads the same with the temp folder inside a repository.
"""
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
BOARD = TOOLS / "board.py"


def remove_tree(path):
    """Removes a scratch folder even when something in it is read-only (git's objects are): the handler makes the
    entry and its folder writable and tries once more."""
    def retry(fn, p, _exc):
        try:
            os.chmod(os.path.dirname(p), 0o700)
            os.chmod(p, 0o700)
            fn(p)
        except OSError:
            pass
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=retry)
    else:
        shutil.rmtree(path, onerror=retry)


class Cut(BaseException):
    """The kill the replay test sends between the state's write and the pending file's."""


def main():
    # resolved at once: macOS's /var is a link and Windows may hand out an 8.3 name, and the tools resolve theirs
    tmp = Path(tempfile.mkdtemp(prefix="board-guard-")).resolve()
    proj = tmp / "project"
    office = tmp / "office"
    proj.mkdir()
    office.mkdir()
    state, out = tmp / "state.json", tmp / "map.html"
    base = {k: v for k, v in os.environ.items() if not k.startswith("FOUNDRY_")}
    # git stops looking for a repository at the scratch folder: one above the temp folder is never read
    base["GIT_CEILING_DIRECTORIES"] = str(tmp)
    base.update({"FOUNDRY_ROOT": str(proj), "FOUNDRY_MAIN": str(proj),
                 "FOUNDRY_PATHS_OFFICE": str(office), "FOUNDRY_PATHS_STATE": str(state), "FOUNDRY_PATHS_MAP": str(out),
                 "FOUNDRY_RESOURCE_NAME": "test rig", "FOUNDRY_RESOURCE_SEATS": "main"})
    ok, bad = [], []

    def run(*args, guard="1", resource=True):
        env = {**base, "FOUNDRY_SWEEP_GUARD": guard}
        if not resource:
            env["FOUNDRY_RESOURCE_NAME"] = ""
        r = subprocess.run([sys.executable, str(BOARD), *args], capture_output=True, text=True, encoding="utf-8",
                           env=env, cwd=proj, timeout=300)
        return r.returncode, r.stdout + r.stderr

    def expect(what, cond, detail=""):
        (ok if cond else bad).append(what + ("" if cond else f": {str(detail).strip()[-500:]}"))

    def notes():
        return [n.get("text") for n in json.loads(state.read_text(encoding="utf-8")).get("notes", [])]

    def queue(*entries):
        (office / "rq.queue.json").write_text(json.dumps(list(entries)), encoding="utf-8")

    def hold(who, since, mx=36000):
        lk = office / "rq.lock"
        lk.mkdir(exist_ok=True)
        (lk / "holder").write_text(who + "\n", encoding="utf-8")
        (lk / "hold.json").write_text(json.dumps({"id": who, "job": "counted sweep", "since": since, "max": mx,
                                                  "lane": "main", "all": True}), encoding="utf-8")

    def checkout_files():
        """The state, the map and the office this checkout would have by default: none of them may appear or change."""
        seen = []
        for p in (ROOT / "docs" / "progress" / "state.json", ROOT / "docs" / "progress-map.html", ROOT / "out" / "foundry"):
            for f in ([p] if not p.is_dir() else sorted(x for x in p.rglob("*") if x.is_file())):
                seen.append((f.as_posix(), f.stat().st_mtime_ns if f.exists() else None))
        return seen

    before_tree = checkout_files()
    now = time.time()

    rc, o = run("stamp")
    expect("stamp prints a time with an offset", rc == 0 and "T" in o and o.strip()[-6] in "+-", o)

    # a project with no state yet: check --no-build and brief read it as a starter state, and write nothing
    rc, o = run("check", "--no-build")
    expect("with no state yet, check --no-build prints its summary and writes nothing",
           "NOT rebuilt" in o and "no state yet" in o and "Traceback" not in o and not out.exists() and not state.exists(), o)
    rc, o = run("note", "--by", "MGR-9", "too early")
    expect("an edit with no state yet is refused in one line, no traceback",
           rc != 0 and "run board.py init first" in o and "Traceback" not in o and not state.exists(), o)

    # init writes the starter state once
    rc, o = run("init")
    expect("init writes the starter state and the map", rc == 0 and state.exists() and out.exists() and "wrote" in o, o)
    first = state.read_bytes()
    rc, o = run("init")
    expect("a second init is refused with exit 3 and leaves the state alone", rc == 3 and "refused" in o and state.read_bytes() == first, o)
    out.unlink(missing_ok=True)
    before_state = state.read_bytes()

    # check --no-build writes nothing, sweep or no sweep (the form an employee uses)
    rc, o = run("check", "--no-build")
    expect("check --no-build reads only: no map, the state untouched",
           "NOT rebuilt" in o and not out.exists() and state.read_bytes() == before_state, o)

    # a sweep waiting in the queue guards as much as one running
    queue({"id": "MGR-9-sweep", "job": "counted sweep", "prio": 0, "at": now, "beat": now, "all": True})
    rc, o = run("note", "--by", "MGR-9", "held note one")
    expect("a note during a sweep is held with exit 0", rc == 0 and "held, not written" in o, o)
    rc, o = run("usage", "31")
    expect("a usage point during a sweep is held", rc == 0 and "held, not written" in o, o)
    rc, o = run("usage", "311")
    expect("a bad edit during a sweep is refused, not held", rc == 2 and "held" not in o, o)
    rc, o = run("decide", "ask", "--by", "FDR-1", "--question", "Held question?")
    expect("a decision asked during a sweep is held like a note", rc == 0 and "held, not written" in o, o)
    rc, o = run("decide", "answer", "D1", "--words", "")
    expect("a bad decide during a sweep is refused, not held", rc == 2 and "held, not written" not in o, o)
    rc, o = run("check")
    expect("check during a sweep does not rebuild the map", "NOT rebuilt" in o and "(not rebuilt)" in o and not out.exists(), o)
    rc, o = run("build")
    expect("build during a sweep does not rebuild the map", rc == 0 and "NOT rebuilt" in o and not out.exists(), o)
    rc, o = run("promote")
    expect("promote during a sweep is refused with exit 3", rc == 3, o)
    expect("the state is untouched during the sweep", state.read_bytes() == before_state)
    rc, o = run("pending")
    expect("pending lists three held edits and the sweep", rc == 0 and "3 edit(s) held" in o and "MGR-9-sweep" in o, o)
    rc, o = run("brief")
    j = json.loads(o[o.index("{"):])
    expect("brief names the sweep and the held edits", j["counted_sweep"] == ["MGR-9-sweep"] and j["held_edits"] == 3,
           (j.get("counted_sweep"), j.get("held_edits")))
    expect("brief lists the resource's seat and who waits",
           j["resource"][0]["seat"] == "main" and j["resource"][-1] == {"queue": ["MGR-9-sweep"]}, j.get("resource"))

    # a project with no shared resource has no queue to wait out: the same office files freeze nothing
    rc, o = run("brief", resource=False)
    j = json.loads(o[o.index("{"):])
    expect("with no resource in the profile, brief has no resource section and no queue keys",
           not {"resource", "counted_sweep", "counted_unmarked", "dev_not_counted"} & set(j), sorted(j))
    rc, o = run("check", "--no-build", resource=False)
    expect("... and check names no counted run", "NOT rebuilt: check --no-build" in o and "counted sweep" not in o, o[-400:])

    # only a badge's own sweep id counts: a dry run's id does not freeze the state
    queue({"id": "EMP-5-dry-sweep", "job": "dry", "prio": 5, "at": now, "beat": now})
    rc, o = run("brief")
    expect("an id that is not <badge>-sweep does not guard", json.loads(o[o.index("{"):])["counted_sweep"] == [], o[:300])
    queue({"id": "MGR-9-sweep", "job": "counted sweep", "prio": 0, "at": now, "beat": now, "all": True})

    # a run that is not in the main checkout neither holds nor applies the held edits
    rc, o = run("build", guard="0")
    expect("a worktree's run leaves the held edits in the office",
           len((office / "pending-state.jsonl").read_text(encoding="utf-8").splitlines()) == 3 and "applied" not in o
           and "held note one" not in notes(), o)
    out.unlink(missing_ok=True)

    # a hold guards too; one far past its own limit reads DEAD? and held edits exit 4
    queue()
    hold("MGR-9-sweep", now - 60)
    rc, o = run("build")
    expect("a sweep that holds the seat guards too", "NOT rebuilt" in o and "DEAD" not in o, o)
    hold("MGR-9-sweep", now - 2 * 86400, mx=3600)
    rc, o = run("note", "--by", "MGR-9", "held under a dead sweep")
    expect("under a dead sweep an edit is still held, with exit 4 and DEAD?",
           rc == 4 and "held, not written" in o and "DEAD" in o and "force-release" in o, o)
    rc, o = run("brief")
    expect("brief flags the dead sweep", "DEAD?" in json.loads(o[o.index("{"):])["counted_sweep"][0], o[:300])

    # a held line that cannot apply stays in the file, marked; the others go in, in order, with their own times
    with open(office / "pending-state.jsonl", "a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"at": "2030-01-11T05:00:00-06:00", "argv": ["block", "999", "done"]}) + "\n")
    shutil.rmtree(office / "rq.lock")
    rc, o = run("build")
    expect("after the sweep the held edits are applied and the bad one is kept", rc == 0 and "applied 4 of 5" in o and "did not apply" in o and out.exists(), o)
    st = json.loads(state.read_text(encoding="utf-8"))
    ns = notes()
    expect("the held notes are in, the later one on top",
           ns[:2] == ["held under a dead sweep", "held note one"], ns[:3])
    expect("the held usage point is in", st["usage"]["points"][-1]["weekly"] == 31, st["usage"]["points"][-1])
    expect("the held decision is in, as D1 and open",
           [(d["id"], d["status"], d["question"]) for d in st.get("decisions", [])] == [("D1", "open", "Held question?")],
           st.get("decisions"))
    left = [json.loads(l) for l in (office / "pending-state.jsonl").read_text(encoding="utf-8").splitlines()]
    expect("the line that failed stays, marked failed", len(left) == 1 and left[0]["argv"][1] == "999" and left[0].get("failed"), left)
    rc, o = run("build")
    expect("a failed line is not replayed again", "applied" not in o and notes()[:2] == ns[:2], o)
    rc, o = run("pending")
    expect("pending shows the failed line", "1 edit(s) held" in o and "FAILED" in o, o)

    # with no sweep an edit is written at once
    rc, o = run("note", "--by", "MGR-9", "written at once")
    expect("with no sweep a note is written at once", rc == 0 and notes()[0] == "written at once", o)
    rc, o = run("decide", "answer", "D1", "--words", "Yes, go on.")
    rc2, o2 = run("decide", "list")
    expect("with no sweep a decision is answered at once, and decide list shows the words",
           rc == 0 and rc2 == 0 and "D1 answered" in o2 and "-> Yes, go on." in o2, o + o2)

    # the office's freeze marker (office.py freeze on) guards like a sweep, with a shared resource or without one
    def freeze(at, max_s=3600):
        (office / "freeze.json").write_text(json.dumps({"by": "MGR-9", "why": "counted G1 by hand", "lane": "G1",
                                                        "at": at, "max_s": max_s}), encoding="utf-8")

    freeze(time.time() - 30)
    frozen_state, frozen_map = state.read_bytes(), out.read_bytes()
    rc, o = run("checklist", "add", "held under a freeze")
    expect("a freeze holds an edit (exit 0) and says who froze and why",
           rc == 0 and "held, not written" in o and "MGR-9 froze the main checkout" in o and "counted G1 by hand" in o, o)
    rc, o = run("log", "add", "--by", "MGR-9", "--title", "held log entry", resource=False)
    expect("... in a project with no shared resource too", rc == 0 and "held, not written" in o, o)
    rc, o = run("milestone", "set", "M1", "--status", "finished")
    expect("a bad edit during a freeze is refused, not held", rc == 2 and "held, not written" not in o, o)
    rc, o = run("build")
    expect("build during a freeze does not rewrite the map", rc == 0 and "NOT rebuilt" in o and out.read_bytes() == frozen_map, o)
    rc, o = run("check", resource=False)
    expect("check during a freeze does not rewrite the map, and Needs attention says who froze and why",
           "NOT rebuilt" in o and "[freeze] MGR-9 froze the main checkout" in o and out.read_bytes() == frozen_map, o[-500:])
    for c in ("promote", "init"):
        rc, o = run(c)
        expect(f"{c} during a freeze is refused with exit 3", rc == 3 and "refused" in o and "frozen" in o, o)
    rc, o = run("brief")
    j = json.loads(o[o.index("{"):])
    expect("brief has `freeze` with the facts, beside an empty counted_sweep",
           j.get("freeze", {}).get("by") == "MGR-9" and j["freeze"]["why"] == "counted G1 by hand" and j["counted_sweep"] == []
           and j["freeze"]["stale"] is False, j.get("freeze"))
    queue({"id": "MGR-9-sweep", "job": "counted sweep", "prio": 0, "at": now, "beat": time.time(), "all": True})
    rc, o = run("note", "--by", "MGR-9", "held under both")
    expect("a sweep and a freeze together: the edit is held and both are named",
           rc == 0 and "held, not written" in o and "MGR-9-sweep" in o and "froze the main checkout" in o, o)
    queue()
    freeze(time.time() - 7200, max_s=60)
    rc, o = run("note", "--by", "MGR-9", "held under a stale freeze")
    expect("a freeze past its limit still holds, with exit 4, DEAD? and office.py freeze off",
           rc == 4 and "held, not written" in o and "DEAD?" in o and "freeze off" in o and "force-release" not in o, o)
    expect("the state and the map are untouched during the freeze", state.read_bytes() == frozen_state and out.read_bytes() == frozen_map)
    (office / "freeze.json").unlink()
    rc, o = run("build")
    st = json.loads(state.read_text(encoding="utf-8"))
    expect("after the freeze the held edits are applied, in order",
           rc == 0 and "applied 4 of 4" in o and st.get("checklist") == ["held under a freeze"]
           and st["log"][0]["title"] == "held log entry" and notes()[:2] == ["held under a stale freeze", "held under both"], o)
    rc, o = run("brief")
    expect("with the freeze lifted, brief has no `freeze` key", "freeze" not in json.loads(o[o.index("{"):]), o[:200])

    # a replay cut short after the state was written and before the pending file was: the next run finds the
    # edit's id in the state (`_applied`) and does not apply it again
    pending = office / "pending-state.jsonl"
    failed_only = pending.read_bytes()  # the line that failed earlier stays in the file throughout
    freeze(time.time() - 30)
    run("note", "--by", "MGR-9", "held once")
    kept = pending.read_bytes()
    (office / "freeze.json").unlink()
    rc, o = run("build")
    held_id = json.loads(kept.decode("utf-8").splitlines()[-1]).get("id")
    expect("a held edit has an id, and the state names the last one it took",
           rc == 0 and "applied 1 of 1" in o and bool(held_id) and pending.read_bytes() == failed_only
           and json.loads(state.read_text(encoding="utf-8")).get("_applied") == held_id, o)
    pending.write_bytes(kept)  # the file as a run killed between the two writes would have left it
    rc, o = run("build")
    expect("a held edit the state already has is dropped from the file, not applied twice",
           rc == 0 and notes().count("held once") == 1 and "not applied twice" in o and "applied 1 of" not in o
           and pending.read_bytes() == failed_only, o)
    rc, o = run("check")
    expect("the check has no warning about the state's `_applied` key", "_applied" not in o, o[-400:])

    # a line of the pending file that is not a held edit (a list, a string, not JSON, an object with no argv) is
    # kept as it is, reported and skipped: it never stops a writing command or the `pending` list
    odd_lines = b'[1, 2]\n"x"\nnot json at all\n{"at": "2030-01-11T05:00:00-06:00"}\n'
    freeze(time.time() - 30)
    run("note", "--by", "MGR-9", "held before the odd lines")
    pending.write_bytes(odd_lines + pending.read_bytes())
    rc, o = run("pending")
    expect("pending lists the unreadable lines as such and does not crash",
           rc == 0 and "Traceback" not in o and o.count("UNREADABLE line") == 4, o)
    rc, o = run("note", "--by", "MGR-9", "held beside the odd lines")
    expect("an edit is still held with unreadable lines in the file", rc == 0 and "held, not written" in o and "Traceback" not in o, o)
    rc, o = run("brief")
    expect("the brief still prints", "Traceback" not in o and "held_edits" in o, o[-300:])
    (office / "freeze.json").unlink()
    rc, o = run("build")
    expect("a build with unreadable lines applies the held edits beside them and says how many lines it skipped",
           rc == 0 and "Traceback" not in o and "applied 2 of 2" in o and "4 line(s)" in o and "cannot be read as a held edit" in o
           and notes()[:2] == ["held beside the odd lines", "held before the odd lines"], o)
    expect("... and keeps those lines byte for byte", pending.read_bytes() == odd_lines + failed_only, pending.read_bytes())
    rc, o = run("note", "--by", "MGR-9", "written with odd lines in the file")
    expect("... and the next edit is written at once", rc == 0 and notes()[0] == "written with odd lines in the file"
           and pending.read_bytes() == odd_lines + failed_only, o)
    pending.write_bytes(failed_only)

    # the page the scratch project gets: its own name, the resource by its name, no word of another project
    page = out.read_text(encoding="utf-8")
    expect("the map is headed by the project's name and has the resource card and the Decisions section",
           "<h1>project progress map</h1>" in page and "test rig: seats" in page and 'id="decisions"' in page, page[:400])

    # a whole-resource job under a plain id whose text says dev is named, not flagged as maybe counted
    queue({"id": "EMP-188", "job": "G7 then G20 (dev runs, not counted)", "prio": 5, "at": now, "beat": time.time(), "all": True})
    rc, o = run("brief")
    j = json.loads(o[o.index("{"):])
    expect("brief: a dev all-seats job is not counted_unmarked, and is named in dev_not_counted",
           j["counted_unmarked"] == [] and j.get("dev_not_counted") == ["EMP-188"], (j["counted_unmarked"], j.get("dev_not_counted")))
    rc, o = run("check", "--no-build")
    expect("check names the dev job in one line and gives no plain-id warning",
           "dev, not counted: EMP-188" in o and "under a plain id" not in o, o)
    queue({"id": "EMP-77", "job": "G18", "prio": 5, "at": now, "beat": time.time(), "all": True})
    rc, o = run("brief")
    expect("an all-seats job that does not say dev is still flagged",
           json.loads(o[o.index("{"):])["counted_unmarked"] == ["EMP-77"], o[:300])
    # with both kinds queued, check names the dev job once
    queue({"id": "EMP-77", "job": "G18", "prio": 5, "at": now, "beat": time.time(), "all": True},
          {"id": "EMP-188", "job": "dev run G7", "prio": 5, "at": now, "beat": time.time(), "all": True})
    rc, o = run("check", "--no-build")
    expect("check prints the dev line once when the plain-id warning also fires",
           o.lower().count("dev, not counted") == 1 and "under a plain id" in o, o[-600:])
    queue()

    # in-process rows: board.py's functions on hand-made input (nothing written outside tmp)
    mine_env = [k for k in base if k.startswith("FOUNDRY_") or k == "GIT_CEILING_DIRECTORIES"] + ["FOUNDRY_SWEEP_GUARD"]
    saved = {k: os.environ.get(k) for k in mine_env + ["FOUNDRY_PROFILE"]}
    os.environ.update({k: base[k] for k in mine_env if k in base})
    os.environ.pop("FOUNDRY_PROFILE", None)  # the defaults: the scratch project has no profile file
    os.environ["FOUNDRY_SWEEP_GUARD"] = "1"  # the held edits below are the main checkout's
    sys.path.insert(0, str(TOOLS))
    import datetime as dt
    import board

    # the same cut, made where it happens: three held notes, the run killed after the first one's state write
    sink = io.StringIO()
    t0 = dt.datetime.now().astimezone()
    with contextlib.redirect_stdout(sink):
        held_rc = [board.hold_edit(["note", "--by", "MGR-9", f"cut {i}"], t0) for i in (1, 2, 3)]
    write_pending = board.write_pending

    def cut(_held):
        raise Cut()
    board.write_pending = cut
    try:
        with contextlib.redirect_stdout(sink):
            board.apply_pending()
        killed = False
    except Cut:
        killed = True
    finally:
        board.write_pending = write_pending
    mid, mid_lines = notes(), len(pending.read_text(encoding="utf-8").splitlines())
    expect("a replay killed after the first edit's state write leaves that edit in the state and all three still in the file",
           held_rc == [0, 0, 0] and killed and mid[0] == "cut 1" and "cut 2" not in mid and mid_lines == 4, (held_rc, killed, mid[:3]))
    with contextlib.redirect_stdout(sink):
        done = board.apply_pending()
    after = notes()
    expect("the next replay applies the other two and nothing twice",
           done == 2 and after[:3] == ["cut 3", "cut 2", "cut 1"] and all(after.count(f"cut {i}") == 1 for i in (1, 2, 3))
           and pending.read_bytes() == failed_only, (done, after[:5], sink.getvalue()[-400:]))

    # write_state refuses a note or log item of the wrong shape, and writes nothing
    bad_path = tmp / "bad-state.json"
    for what, st, want in (("a bare-string note", {"notes": ["oops"], "log": []}, "state.notes[0]"),
                           ("a log item with no title", {"notes": [], "log": [{"date": "x", "title": "t"}, {"date": "y"}]},
                            "state.log[1]")):
        try:
            board.write_state(st, bad_path)
            err = None
        except ValueError as e:
            err = str(e)
        expect(f"write_state refuses {what} with the key and index, and writes nothing",
               err is not None and want in err and not bad_path.exists(), err)
    board.write_state({"notes": [{"at": "a", "by": "b", "text": "c"}], "log": [{"date": "d", "title": "t"}]}, bad_path)
    expect("write_state takes well-formed notes and log", bad_path.exists())

    # a session badge hired over 15 min ago with no session and no clock-in is named
    nowdt = dt.datetime.now().astimezone()
    old = nowdt.timestamp() - 20 * 60
    crew_in = {"badges": [
        {"id": "EMP-301", "name": "a", "role": "BUILDER", "kind": "SESSION", "status": "HIRED", "session": None, "issued": old},
        {"id": "EMP-302", "name": "b", "role": "BUILDER", "kind": "SESSION", "status": "HIRED", "session": "local_x", "issued": old},
        {"id": "EMP-303", "name": "c", "role": "BUILDER", "kind": "SESSION", "status": "HIRED", "session": None,
         "issued": nowdt.timestamp() - 60}]}
    attn = [t for _, g, t, _ in board.attention({}, {}, crew_in, {"seats": []}, nowdt) if g == "crew"]
    expect("attention: an unassigned session badge past 15 min reads 'no session: assign a bench or clock it out'",
           any(t.startswith("EMP-301 hired at") and "no session: assign a bench or clock it out" in t for t in attn)
           and not any("EMP-302" in t and "no session" in t for t in attn)
           and not any("EMP-303" in t for t in attn), attn)

    # an OVERDUE badge whose job holds a seat says so in attention (office.crew's status_text)
    crew_od = {"badges": [{"id": "EMP-305", "name": "d", "role": "BUILDER", "kind": "SESSION", "status": "OVERDUE",
                           "status_text": "OVERDUE (test rig: holds main, 12 of 240 min)", "session": "local_y", "issued": old}]}
    attn = [t for _, g, t, _ in board.attention({}, {}, crew_od, {"seats": []}, nowdt) if g == "crew"]
    expect("attention: OVERDUE while holding a seat reads 'OVERDUE (<resource>: holds <seat>, N of M min)'",
           attn == ["EMP-305 d is OVERDUE (test rig: holds main, 12 of 240 min); chase it or clock it out"], attn)

    # a seat held past its own limit is under Needs attention, by its seat
    res = {"seats": [{"seat": "main", "hold": {"id": "EMP-9", "max": 1800, "since": old, "overdue": True}}]}
    attn = [t for _, g, t, _ in board.attention({}, {}, {"badges": []}, res, nowdt) if g == "resource"]
    expect("attention: a seat held past its limit reads 'seat main is held by EMP-9 past its 30 min'",
           len(attn) == 1 and attn[0].startswith("seat main is held by EMP-9 past its 30 min"), attn)

    for k, v in saved.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v

    expect("the checkout's own state, map and office were not touched", checkout_files() == before_tree, checkout_files())
    expect("the scratch project folder itself was never written", not any(proj.iterdir()), [p.name for p in proj.iterdir()])

    for x in ok:
        print(f"  ok   {x}")
    for x in bad:
        print(f"  FAIL {x}")
    print(f"board guard test: {len(ok)} ok, {len(bad)} failed" + (f" (scratch kept: {tmp.as_posix()})" if bad else ""))
    if not bad:
        remove_tree(tmp)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
