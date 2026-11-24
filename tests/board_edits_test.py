#!/usr/bin/env python3
"""The edit commands of tools/board.py, the freeze marker, the stage-exit reader and the starter roadmap.

    python tests/board_edits_test.py

Every project here is a scratch folder (FOUNDRY_ROOT, FOUNDRY_MAIN) with a scratch office (FOUNDRY_PATHS_OFFICE);
nothing in this checkout, its state, its map or its crew office is read or written, and git never looks above
the scratch folder (GIT_CEILING_DIRECTORIES), so the test reads the same with the temp folder inside a repository.
Four parts:

  1. each edit command through the command line, on a project with no shared resource: what it writes, its exit
     codes, the refusal in a linked worktree, and the hold while the office's freeze marker is on (a held edit
     that names an item by its number finds that item again at the replay; a freeze.json with a number no clock
     can show still reads as a freeze); a milestone's lane is not re-pointed without the user's words;
  2. a stage's exit cell: board.py and flow.py read the starter roadmap and three hand-written rows the same way;
  3. the starter roadmap: nothing in it is PASS or done, its copy in the format page is byte-identical, flow.py
     selftest finds 0 problems in a project that holds only it, and a project fresh from founder.py init gets no
     warning about the roadmap from board.py check;
  4. printed commands: relative to the checkout on the map and in the check, absolute when the profile says so.
"""
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
BOARD = TOOLS / "board.py"
EXAMPLE = ROOT / "profile" / "ROADMAP.example.md"
FORMAT_PAGE = ROOT / "skills" / "foundry-founder" / "references" / "roadmap-format.md"


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


def with_board_key(text, value):
    """A profile's text with board.absolute_commands set: the line is replaced where the [board] table has it,
    added under the table's heading where it has not, and the table is appended only when the file has none (a
    second [board] table is not TOML)."""
    line = f"absolute_commands = {value}"
    head = re.search(r"^\[board\][^\n]*\n", text, re.M)
    if head is None:
        return text.rstrip("\n") + "\n\n[board]\n" + line + "\n"
    end = re.search(r"^\[", text[head.end():], re.M)
    stop = head.end() + end.start() if end else len(text)
    table, n = re.subn(r"^absolute_commands[ \t]*=[^\n]*", line, text[head.end():stop], count=1, flags=re.M)
    if not n:
        table = line + "\n" + table
    return text[:head.end()] + table + text[stop:]


def main():
    # resolved at once: macOS's /var is a link and Windows may hand out an 8.3 name, and the tools resolve theirs
    tmp = Path(tempfile.mkdtemp(prefix="board-edits-")).resolve()
    ok, bad = [], []
    clean = {k: v for k, v in os.environ.items() if not k.startswith("FOUNDRY_")}
    # git stops looking for a repository at the scratch folder: one above the temp folder is never read
    clean["GIT_CEILING_DIRECTORIES"] = str(tmp)

    def expect(what, cond, detail=""):
        (ok if cond else bad).append(what + ("" if cond else f": {str(detail).strip()[-600:]}"))

    def project(name, **more):
        """A scratch project folder with its own office; the environment a tool run in it gets. FOUNDRY_ROOT and
        FOUNDRY_MAIN pin the checkout, so the profile is the project's own .foundry/foundry.toml when it has one
        and the defaults when it has none; FOUNDRY_PROFILE is left unset (naming a file that is not there is an
        error, not the defaults)."""
        proj = tmp / name
        proj.mkdir()
        env = {**clean, "FOUNDRY_ROOT": str(proj), "FOUNDRY_MAIN": str(proj),
               "FOUNDRY_PATHS_OFFICE": str(tmp / (name + "-office")), "FOUNDRY_HOME": str(tmp / "home"), **more}
        (tmp / (name + "-office")).mkdir()
        return proj, env

    def run(env, tool, *args, cwd=None):
        r = subprocess.run([sys.executable, str(TOOLS / tool), *args], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", env=env, cwd=cwd or env["FOUNDRY_ROOT"], timeout=300)
        return r.returncode, r.stdout + r.stderr

    # ---- 1. the edit commands, on a project with no shared resource
    proj, env = project("edits", FOUNDRY_SWEEP_GUARD="1", FOUNDRY_RESOURCE_NAME="")
    office = Path(env["FOUNDRY_PATHS_OFFICE"])
    state_file = proj / "docs" / "progress" / "state.json"

    def b(*args):
        return run(env, "board.py", *args)

    def st():
        return json.loads(state_file.read_text(encoding="utf-8"))

    rc, o = b("log", "add", "--by", "MGR-1", "--title", "too early")
    expect("an edit with no state yet is refused in one line", rc != 0 and "run board.py init first" in o and "Traceback" not in o, o)
    rc, o = b("init")
    s0 = st()
    expect("init writes the rota's slots with their research-and-review windows, and no rr_since",
           rc == 0 and all(s.get("rr", "").startswith(s["start"]) for s in s0["rota"]["slots"]) and "rr_since" not in s0["rota"], o)
    rc, o = b("check")
    expect("a fresh state gives no research-and-review warning (no window is checked before `rota slots`)",
           "research-and-review window" not in o, o)

    blocks = tmp / "blocks.json"
    blocks.write_text(json.dumps([{"time": "06:00-08:00", "title": "Q1: skeleton", "done_when": "it starts"},
                                  {"time": "08:00-10:00", "title": "Q2: the counted run", "done_when": "G1 graded"}]), encoding="utf-8")
    rc, o = b("shift", "blocks", "--file", str(blocks))
    expect("shift blocks --file replaces the plan (exit 0) and rebuilds the map",
           rc == 0 and len(st()["shift"]["blocks"]) == 2 and "wrote" in o, o)
    rc, o = b("shift", "set", "--crew-max", "5", "--by", "MGR-1")
    expect("shift set --crew-max without --words is refused (exit 2)", rc == 2 and "--words" in o and st()["shift"]["crew_max"] != 5, o)
    rc, o = b("shift", "set", "--crew-max", "5", "--heavy-ok", "no", "--milestone", "M1", "--when", "day slot", "--by", "MGR-1",
              "--words", "five is enough")
    sh = st()["shift"]
    expect("shift set writes crew_max, heavy_ok, the milestone and `when` with the user's words and the time",
           rc == 0 and sh["crew_max"] == 5 and sh["heavy_ok"] is False and sh["milestone"] == "M1"
           and sh["when"].startswith("day slot; ") and 'on the user\'s words: "five is enough"' in sh["when"], sh.get("when"))
    rc, o = b("checkpoint", "add", "--lane", "G1", "--milestone", "M1", "--builder", "EMP-1", "--grader", "EMP-1")
    expect("checkpoint add with the builder as grader is refused (exit 3)", rc == 3 and st()["checkpoints"] == [], o)
    rc, o = b("checkpoint", "add", "--lane", "G1", "--milestone", "M1", "--builder", "EMP-1", "--block", "2", "--note", "n")
    rc2, o2 = b("checkpoint", "set", "G1", "--grader", "EMP-2")
    s1 = st()
    expect("checkpoint add then set: the entry, the block's checkpoint, the grader",
           rc == 0 and rc2 == 0 and s1["checkpoints"][0]["lane"] == "G1" and s1["checkpoints"][0]["grader"] == "EMP-2"
           and s1["shift"]["blocks"][1]["checkpoint"] == "G1" and s1["checkpoints"][0]["set_at"], o + o2)
    rc, o = b("check")
    expect("after shift set and checkpoint add the check has no milestone-checkpoint warning",
           "has no gym checkpoint" not in o and "No block of the shift carries" not in o, o)
    rc, o = b("milestone", "set", "M1", "--status", "in-progress", "--title", "Skeleton", "--lane", "G1")
    rc2, o2 = b("milestone", "set", "M1", "--status", "done")
    expect("milestone set done is refused (exit 3) with no counted run, and says the lane must say PASS",
           rc == 0 and rc2 == 3 and "G1 has no counted run" in o2 and "PASS" in o2 and st()["milestones"][0]["status"] == "in-progress", o2)
    series = proj / "gym" / "series"
    series.mkdir(parents=True)
    (series / "G1.json").write_text(json.dumps({"points": [{"run_id": "20300110-115716-d005", "verdict": "FAIL", "n": 30,
                                                            "ts": time.time() - 3600}]}), encoding="utf-8")
    rc, o = b("milestone", "set", "M1", "--status", "done")
    expect("... and with FAIL as the lane's latest counted verdict", rc == 3 and "G1 has FAIL as its latest counted verdict" in o, o)
    rc, o = b("milestone", "set", "M1", "--status", "done", "--force", "--words", "done for me")
    expect("--force --words records the user's override (exit 0)",
           rc == 0 and st()["milestones"][0]["status"] == "done" and st()["milestones"][0]["forced"]["words"] == "done for me", o)
    (series / "G1.json").write_text(json.dumps({"points": [{"run_id": "20300111-135643-0854", "verdict": "PASS", "n": 34,
                                                            "ts": time.time() - 60}]}), encoding="utf-8")
    rc, o = b("milestone", "set", "M1", "--status", "done")
    expect("milestone set done is taken once the series says PASS",
           rc == 0 and "forced" not in st()["milestones"][0] and "G1 PASS" in o, o)
    crew = tmp / "crew.json"
    crew.write_text(json.dumps(["EMP-1 m1-builder (builder): done, 2.0 h"], indent=1) + "\n", encoding="utf-8")
    rc, o = b("log", "add", "--by", "MGR-1", "--title", "Block 1", "--slot", "day", "--done", "the skeleton | the lane",
              "--not-done", "undo", "--verdicts", "G1 PASS n=34", "--commits", "abc1234", "--next", "block 2",
              "--crew-file", str(crew))
    e = st()["log"][0]
    expect("log add writes the whole entry, the crew from the file",
           rc == 0 and e["slot"] == "day" and e["done"] == ["the skeleton", "the lane"] and e["verdicts"] == ["G1 PASS n=34"]
           and e["crew"] == ["EMP-1 m1-builder (builder): done, 2.0 h"] and e["by"] == "MGR-1", o + str(e))
    rc, o = b("log", "add", "--by", "MGR-1", "--title", "t", "--crew", "a", "--crew-file", str(crew))
    expect("log add with both --crew and --crew-file is refused (exit 2)", rc == 2 and len(st()["log"]) == 1, o)
    rc, o = b("now", "--headline", "M1 done", "--position", "block 2 next")
    expect("now sets the headline and the position", rc == 0 and st()["now"]["headline"] == "M1 done"
           and st()["now"]["position"] == "block 2 next", o)
    rc, o = b("now", "--tree", "auto")
    expect("now --tree auto is refused where git has no history (exit 2)", rc == 2 and "--tree auto" in o, o)
    rc, o = b("rota", "set", "--date", "2030-01-12", "--slot", "night", "--shift", "start", "--manager", "MGR-4",
              "--ends", "07:30", "--note", "the user: until half past seven")
    rc2, o2 = b("rota", "set", "--date", "2030-01-11", "--slot", "day", "--manager", "MGR-2")
    days = st()["rota"]["days"]
    expect("rota set writes the entries, the days in date order; a night slot's morning end is taken",
           rc == 0 and rc2 == 0 and [d["date"] for d in days] == ["2030-01-11", "2030-01-12"]
           and days[1]["night"]["ends"] == "07:30" and days[0]["day"] == {"manager": "MGR-2"}, o + o2)
    rc, o = b("rota", "set", "--date", "2030-01-12", "--slot", "day", "--ends", "05:00")
    expect("rota set refuses an end before the slot's start (exit 2)", rc == 2 and "ignored" in o and "day" not in st()["rota"]["days"][1], o)
    rc, o = b("rota", "slots", "--rr-min", "45")
    r = st()["rota"]
    expect("rota slots --rr-min writes the windows and sets rr_since",
           rc == 0 and [s["rr"] for s in r["slots"]][0].endswith(":45") and r.get("rr_since"), o)
    b("decide", "ask", "--by", "MGR-1", "--question", "Which key?")
    rc, o = b("blocker", "add", "--what", "No signing key", "--owner", "the user", "--needs", "D1")
    rc2, o2 = b("check", "--no-build")
    expect("blocker add: the blocker waits on the user under Needs attention",
           rc == 0 and st()["blockers"][0]["needs"] == "D1" and "[the user] No signing key" in o2, o + o2[-300:])
    rc, o = b("blocker", "rm", "1", "--note", "the key came")
    expect("blocker rm by number removes it and leaves a note",
           rc == 0 and st()["blockers"] == [] and "the key came" in st()["notes"][0]["text"], o)
    b("checklist", "add", "Read the hand-off")
    b("checklist", "add", "Check usage")
    rc, o = b("checklist", "done", "2")
    rc2, o2 = b("check", "--no-build")
    expect("checklist add and done: the check prints the ticked line", rc == 0 and "2. [x] Check usage" in o2 and "1. Read the hand-off" in o2, o2[-500:])
    rc, o = b("checklist", "rm", "1")
    expect("checklist rm", rc == 0 and len(st()["checklist"]) == 1, o)
    q = tmp / "m2.json"
    q.write_text(json.dumps({"id": "m2-store", "title": "M2 store", "crew_max": 3, "milestone": "M2",
                             "blocks": [{"time": "06:00-08:00", "title": "Q1: store", "done_when": "x"}]}), encoding="utf-8")
    rc, o = b("queue", "add", "--file", str(q))
    rc2, o2 = b("queue", "add", "--file", str(q))
    expect("queue add takes a shift once; the same id again is refused (exit 2)",
           rc == 0 and rc2 == 2 and [x["id"] for x in st()["queue"]] == ["m2-store"], o + o2)
    q.write_text(json.dumps({"id": "m3-ship", "title": "M3 ship", "crew_max": 2, "blocks": [{"title": "Q1"}]}), encoding="utf-8")
    b("queue", "add", "--file", str(q), "--at", "1")
    rc, o = b("queue", "list")
    before = state_file.read_bytes()
    expect("queue list prints the queue in order and writes nothing",
           rc == 0 and o.index("1. m3-ship") < o.index("2. m2-store") and state_file.read_bytes() == before, o)
    rc, o = b("queue", "move", "m3-ship", "2")
    rc2, o2 = b("queue", "rm", "m3-ship", "--note", "not yet")
    expect("queue move and rm", rc == 0 and rc2 == 0 and [x["id"] for x in st()["queue"]] == ["m2-store"], o + o2)
    rc, o = b("block", "1", "done")
    rc2, o2 = b("shift", "blocks", "--file", str(blocks))
    expect("shift blocks is refused once a block is done (exit 3)", rc == 0 and rc2 == 3 and "before its work begins" in o2, o2)
    for what, args in (("an unknown form", ("rota", "clear")), ("an option of another command", ("now", "--by", "MGR-1")),
                       ("a value that starts with --", ("log", "add", "--by", "--title", "x"))):
        before = state_file.read_bytes()
        rc, o = b(*args)
        expect(f"{what} is refused (exit 2), nothing written", rc == 2 and state_file.read_bytes() == before, o)
    rc, o = b("check")
    s1 = st()
    expect("every edit set `updated` and the built map shows what they wrote",
           s1["updated"] != s0["updated"] and "Block 1" in (proj / "docs" / "progress-map.html").read_text(encoding="utf-8"), o[-300:])

    # the freeze marker holds edits with no shared resource, exactly as a counted run in the queue does
    def freeze(at, max_s=3600):
        (office / "freeze.json").write_text(json.dumps({"by": "MGR-1", "why": "a counted run by hand", "lane": "G1",
                                                        "at": at, "max_s": max_s}), encoding="utf-8")

    map_file = proj / "docs" / "progress-map.html"
    freeze(time.time() - 60)
    before, map_before = state_file.read_bytes(), map_file.read_bytes()
    rc, o = b("log", "add", "--by", "MGR-1", "--title", "held entry", "--crew-file", str(crew))
    expect("with a freeze on and no resource, log add is held (exit 0) and says who froze and why",
           rc == 0 and "held, not written" in o and "MGR-1 froze the main checkout" in o and "a counted run by hand" in o, o)
    q.write_text(json.dumps({"id": "m4-late", "title": "M4", "crew_max": 1, "blocks": [{"title": "Q1"}]}), encoding="utf-8")
    rc, o = b("queue", "add", "--file", str(q))
    expect("queue add --file is held too", rc == 0 and "held, not written" in o, o)
    q.unlink()
    crew.unlink()
    rc, o = b("queue", "add", "--file", str(tmp / "none.json"))
    expect("a bad edit during a freeze is refused, not held", rc == 2 and "held, not written" not in o, o)
    rc, o = b("check")
    expect("check during a freeze does not rebuild the map and lists the freeze under Needs attention",
           "NOT rebuilt" in o and "[freeze] MGR-1 froze the main checkout" in o and map_file.read_bytes() == map_before, o[-600:])
    rc, o = b("build")
    expect("build during a freeze does not rebuild the map", rc == 0 and "NOT rebuilt" in o and map_file.read_bytes() == map_before, o)
    rc, o = b("promote")
    expect("promote during a freeze is refused (exit 3)", rc == 3 and "refused" in o, o)
    rc, o = b("brief", "--keys", "freeze,held_edits")
    j = json.loads(o[o.index("{"):])
    expect("brief has `freeze` (the facts) and the held edits",
           j.get("freeze", {}).get("on") is True and j["freeze"]["by"] == "MGR-1" and j["freeze"]["lane"] == "G1"
           and j["freeze"]["stale"] is False and j["held_edits"] == 2, j)
    rc, o = b("pending")
    expect("pending lists the held edits and the freeze", rc == 0 and "2 edit(s) held" in o and "frozen: MGR-1 froze" in o, o)
    expect("the state is untouched during the freeze", state_file.read_bytes() == before)
    rc, o = run({**env, "FOUNDRY_SWEEP_GUARD": "0"}, "board.py", "brief", "--keys", "freeze")
    expect("a run that is not the main checkout still reads the freeze in its brief",
           json.loads(o[o.index("{"):]).get("freeze", {}).get("on") is True, o[:300])
    freeze(time.time() - 7200, max_s=600)
    rc, o = b("note", "--by", "MGR-1", "held under a stale freeze")
    expect("under a freeze past its limit an edit is still held, with exit 4, DEAD? and how to end it",
           rc == 4 and "held, not written" in o and "DEAD?" in o and "freeze off" in o, o)
    rc, o = b("check", "--no-build")
    expect("a stale freeze reads DEAD? under Needs attention", "[freeze]" in o and "DEAD?" in o, o[-500:])
    (office / "freeze.json").unlink()
    rc, o = b("build")
    s2 = st()
    expect("after the freeze the held edits are applied in order, the files read from what was held",
           rc == 0 and "applied 3 of 3" in o and s2["log"][0]["title"] == "held entry"
           and s2["log"][0]["crew"] == ["EMP-1 m1-builder (builder): done, 2.0 h"]
           and [x["id"] for x in s2["queue"]] == ["m2-store", "m4-late"] and s2["notes"][0]["text"] == "held under a stale freeze", o)
    rc, o = b("brief", "--keys", "freeze")
    expect("with no freeze, brief has no `freeze` key and does not call it unknown",
           "freeze" not in json.loads(o[o.index("{"):]) and "unknown_keys" not in o, o[:200])
    rc, o = b("init")
    expect("init on an existing state names the edit commands", rc == 3 and "log, now, rota" in o, o)

    # a freeze.json whose numbers no clock can show is a freeze by "unknown": nothing crashes, edits are held
    for name, body in (("`at` in milliseconds", json.dumps({"by": "MGR-1", "why": "w", "at": time.time() * 1000, "max_s": 600})),
                       ("`at` 1e999", '{"by": "MGR-1", "why": "w", "at": 1e999, "max_s": 600}'),
                       ("`max_s` 1e999", '{"by": "MGR-1", "why": "w", "at": %d, "max_s": 1e999}' % int(time.time()))):
        (office / "freeze.json").write_text(body, encoding="utf-8")
        rc, o = b("check", "--no-build")
        expect(f"freeze.json with {name}: check --no-build names a freeze by unknown and does not crash",
               "Traceback" not in o and "[freeze] unknown froze the main checkout" in o, o[-600:])
    before = state_file.read_bytes()
    rc, o = b("note", "--by", "MGR-1", "held under an odd freeze")
    expect("... and a note under it is held (exit 0), not written and not a traceback",
           rc == 0 and "Traceback" not in o and "held, not written" in o and "unknown froze" in o
           and state_file.read_bytes() == before, o)
    (office / "freeze.json").unlink()
    rc, o = b("build")
    expect("... and applied once the marker is gone", rc == 0 and "applied 1 of 1" in o
           and st()["notes"][0]["text"] == "held under an odd freeze", o)

    # milestone set: the lane of a milestone the list has is not re-pointed at one that passed
    lp, lenv = project("relane", FOUNDRY_SWEEP_GUARD="1", FOUNDRY_RESOURCE_NAME="")
    lstate = lp / "docs" / "progress" / "state.json"

    def lb(*args):
        return run(lenv, "board.py", *args)

    def m1():
        return json.loads(lstate.read_text(encoding="utf-8"))["milestones"][0]

    lb("init")
    (lp / "gym" / "series").mkdir(parents=True)
    for lane, verdict in (("G1", "FAIL"), ("G2", "PASS")):
        (lp / "gym" / "series" / f"{lane}.json").write_text(json.dumps({"points": [
            {"run_id": f"20300110-115716-000{lane[1]}", "verdict": verdict, "n": 30, "ts": time.time() - 600}]}), encoding="utf-8")
    rc, o = lb("milestone", "set", "M1", "--status", "in-progress", "--title", "Skeleton", "--lane", "G1")
    rc2, o2 = lb("milestone", "set", "M1", "--status", "done")
    expect("M1 on the lane G1 (latest FAIL) is not done (exit 3)", rc == 0 and rc2 == 3 and m1()["lane"] == "G1", o + o2)
    was = lstate.read_bytes()
    rc, o = lb("milestone", "set", "M1", "--status", "done", "--lane", "G2")
    expect("... and naming the passed lane G2 with it is refused too (exit 3): the lane and the status stay",
           rc == 3 and "re-point" in o and lstate.read_bytes() == was and m1()["lane"] == "G1" and m1()["status"] == "in-progress", o)
    rc, o = lb("milestone", "set", "M1", "--status", "in-progress", "--lane", "G2")
    expect("... with any status (exit 3)", rc == 3 and lstate.read_bytes() == was, o)
    rc, o = lb("milestone", "set", "M1", "--status", "done", "--lane", "G2", "--force")
    expect("--lane with --force and no words is refused (exit 2)", rc == 2 and "--words" in o and lstate.read_bytes() == was, o)
    rc, o = lb("milestone", "set", "M1", "--status", "in-progress", "--lane", "G1", "--title", "Another name")
    expect("the same lane again is no change, and --title does not rename an existing milestone",
           rc == 0 and m1()["lane"] == "G1" and m1()["title"] == "Skeleton" and "forced" not in m1() and "title is unchanged" in o, o)
    rc, o = lb("milestone", "set", "M1", "--status", "done", "--lane", "G2", "--force", "--words", "judge it on G2 from now on")
    f1 = m1().get("forced") or {}
    expect("--lane with --force --words re-points it (exit 0): `forced` has the words, the new lane and the old one",
           rc == 0 and m1()["lane"] == "G2" and m1()["status"] == "done" and f1.get("words") == "judge it on G2 from now on"
           and f1.get("lane") == "G2" and f1.get("lane_was") == "G1" and f1.get("at"), o + str(m1()))
    rc, o = lb("milestone", "set", "M1", "--status", "done")
    expect("... and a later plain done on the new lane's PASS keeps the record of the change",
           rc == 0 and (m1().get("forced") or {}).get("lane_was") == "G1" and m1()["lane"] == "G2", str(m1()))

    # held edits that name an item by its number: the number is the written state's, the item is what is held
    hp, henv = project("held", FOUNDRY_SWEEP_GUARD="1", FOUNDRY_RESOURCE_NAME="")
    hoffice = Path(henv["FOUNDRY_PATHS_OFFICE"])
    hstate = hp / "docs" / "progress" / "state.json"
    hpending = hoffice / "pending-state.jsonl"

    def hb(*args):
        return run(henv, "board.py", *args)

    def hs():
        return json.loads(hstate.read_text(encoding="utf-8"))

    def shift_file(sid):
        p = tmp / f"{sid}.json"
        p.write_text(json.dumps({"id": sid, "title": sid.upper(), "crew_max": 1, "blocks": [{"title": "Q1"}]}), encoding="utf-8")
        return str(p)

    hb("init")
    for what in ("alpha", "bravo", "charlie"):
        hb("blocker", "add", "--what", what, "--owner", "the user")
    for line in ("one", "two", "three", "dup", "dup"):
        hb("checklist", "add", line)
    plan = tmp / "plan.json"
    plan.write_text(json.dumps([{"title": "A"}, {"title": "B"}, {"title": "C"}]), encoding="utf-8")
    hb("shift", "blocks", "--file", str(plan))
    for sid in ("q1", "q2", "q3"):
        hb("queue", "add", "--file", shift_file(sid))
    (hoffice / "freeze.json").write_text(json.dumps({"by": "MGR-1", "why": "a counted run", "at": time.time() - 5,
                                                     "max_s": 3600}), encoding="utf-8")
    frozen = hstate.read_bytes()
    rc, o = hb("blocker", "rm", "1", "--note", "n1")
    rc2, o2 = hb("blocker", "rm", "2", "--note", "n2")
    expect("blocker rm 1 and blocker rm 2 are both held under a freeze", rc == 0 and rc2 == 0 and "held, not written" in o2, o + o2)
    rc, o = hb("blocker", "rm", "1", "--note", "again")
    expect("a second blocker rm 1 is checked against the list without the first: refused (exit 2), not held",
           rc == 2 and "held, not written" not in o and "gone" in o, o)
    rc, o = hb("blocker", "rm", "9", "--note", "n")
    expect("a number the written state does not have is refused (exit 2), not held", rc == 2 and "held, not written" not in o, o)
    rc, o = hb("checklist", "rm", "1")
    rc2, o2 = hb("checklist", "done", "2")
    expect("checklist rm 1 then checklist done 2 are held", rc == 0 and rc2 == 0, o + o2)
    rc, o = hb("checklist", "done", "4")
    expect("a line that reads like another one cannot be held by its text: refused (exit 2)",
           rc == 2 and "held, not written" not in o and "cannot be told" in o, o)
    plan.write_text(json.dumps([{"title": "C"}, {"title": "A"}]), encoding="utf-8")
    rc, o = hb("shift", "blocks", "--file", str(plan))
    rc2, o2 = hb("block", "3", "done")
    rc3, o3 = hb("checkpoint", "add", "--lane", "G9", "--milestone", "M9", "--block", "1")
    expect("a new plan, block 3 done and checkpoint add --block 1 are held", rc == 0 and rc2 == 0 and rc3 == 0, o + o2 + o3)
    rc, o = hb("checkpoint", "add", "--lane", "G8", "--milestone", "M8", "--block", "2")
    expect("--block 2 names a block the held plan drops: refused (exit 2), not held",
           rc == 2 and "held, not written" not in o and "gone" in o, o)
    rc, o = hb("queue", "rm", "q1", "--note", "n")
    rc2, o2 = hb("queue", "move", "q3", "2")
    rc3, o3 = hb("queue", "add", "--file", shift_file("q4"), "--at", "4")
    expect("queue rm q1, queue move q3 2 and queue add --at 4 (the end) are held", rc == 0 and rc2 == 0 and rc3 == 0, o + o2 + o3)
    lines = [json.loads(l) for l in hpending.read_text(encoding="utf-8").splitlines()]
    expect("every held edit has its own id, and one with a number keeps what the number named",
           len(lines) == 10 and len({h.get("id") for h in lines}) == 10 and all(h.get("id") for h in lines)
           and [h["ref"]["key"] for h in lines if h.get("ref")] == ["alpha", "bravo", "one", "two", "C", "A", "q2", None],
           [(h.get("id"), h.get("ref")) for h in lines])
    expect("the state is untouched while they are held", hstate.read_bytes() == frozen)
    # two lines whose item will not be found (as after a hand edit): they stay, the later ones are applied
    odd = [{"id": "odd-1", "at": "2030-01-11T05:00:00-06:00", "argv": ["blocker", "rm", "1", "--note", "x"],
            "ref": {"kind": "blocker", "arg": 2, "key": "zulu"}},
           {"id": "odd-2", "at": "2030-01-11T05:00:01-06:00", "argv": ["checklist", "rm", "4"],
            "ref": {"kind": "checklist", "arg": 2, "key": "dup"}}]
    hpending.write_text("".join(json.dumps(h) + "\n" for h in odd + lines), encoding="utf-8", newline="\n")
    (hoffice / "freeze.json").unlink()
    rc, o = hb("build")
    s3 = hs()
    expect("after the freeze: bravo is removed, not charlie", rc == 0 and "applied 10 of 12" in o
           and [x["what"] for x in s3["blockers"]] == ["charlie"], o + str(s3["blockers"]))
    expect("... the line `two` is ticked and `one` is gone",
           [(c["text"], bool(c["done"])) if isinstance(c, dict) else c for c in s3["checklist"]]
           == [("two", True), "three", "dup", "dup"], s3["checklist"])
    expect("... block C (3 when it was held, 1 in the new plan) is done, and block A carries the checkpoint",
           [(x["title"], x["status"], x.get("checkpoint")) for x in s3["shift"]["blocks"]]
           == [("C", "done", None), ("A", "pending", "G9")], s3["shift"]["blocks"])
    expect("... q3 is where q2 was, and q4 at the end", [x["id"] for x in s3["queue"]] == ["q3", "q2", "q4"], s3["queue"])
    left = [json.loads(l) for l in hpending.read_text(encoding="utf-8").splitlines()]
    expect("the two whose item is gone or cannot be told apart stay in the file with the reason",
           [h["id"] for h in left] == ["odd-1", "odd-2"] and "gone" in left[0].get("failed", "")
           and "cannot be told" in left[1].get("failed", ""), left)
    expect("the state names the last held edit it took (`_applied`), and the map builds with it",
           s3.get("_applied") == lines[-1]["id"] and "Traceback" not in o, s3.get("_applied"))

    # a linked worktree's edit is refused: the state is the main checkout's
    wt, wenv = project("worktree")
    wenv = {**wenv, "FOUNDRY_MAIN": str(proj)}
    for args in (("log", "add", "--by", "MGR-1", "--title", "t"), ("checklist", "add", "x"), ("milestone", "set", "M1", "--status", "planned")):
        rc, o = run(wenv, "board.py", *args)
        expect(f"`{args[0]}` in a linked worktree is refused (exit 3) and writes nothing there",
               rc == 3 and "linked worktree" in o and not any(wt.iterdir()), o)

    # ---- 2. a stage's exit cell: one reader for the map and the road graph
    sys.path.insert(0, str(TOOLS))
    mine_env = [k for k in env if k.startswith("FOUNDRY_") or k == "GIT_CEILING_DIRECTORIES"]
    saved = {k: os.environ.get(k) for k in mine_env + ["FOUNDRY_PROFILE"]}
    os.environ.update({k: env[k] for k in mine_env})
    os.environ.pop("FOUNDRY_PROFILE", None)  # the scratch project's own profile or the defaults, never another
    try:
        import board
        import flow
        import office as office_mod

        expect("board.py reads a stage's exit cell with flow.py itself", board.flow_tool() is flow, board.FLOW_ERROR)
        tier = flow.TOP
        rows = "\n".join([
            "| **R1 Core** | the main job | APP-01, 02; DATA-01–02 (the rest later) | M1 | x |",
            f"| **R2 Wide** | more of it | All {tier} except REL-01's sign-off; DOC-01 | M2 | x |",
            f"| **{flow.GOAL}** | the goal | every {tier} PASS | M3 | x |"])
        for name, text in (("the starter roadmap", EXAMPLE.read_text(encoding="utf-8")),
                           ("three hand-written stage rows", EXAMPLE.read_text(encoding="utf-8") + "\n" + rows + "\n")):
            reqs = {m[1]: (m[3] or m[2], m[4]) for m in board.REQ_ROW.finditer(text)}
            mine = {sid: [i for i in ids if i in reqs] for sid, _, _, ids in board.stage_rows(text, reqs)}
            freqs, theirs, *_ = flow.parse_roadmap(text)
            expect(f"{name}: both tools find the same stages, in the road's order",
                   list(mine) == flow.stage_order(theirs) and len(mine) >= 2, (list(mine), list(theirs)))
            expect(f"{name}: both tools read every exit cell as the same IDs",
                   all(mine[s] == theirs[s]["ids"] for s in mine) and set(reqs) == set(freqs),
                   {s: (mine[s], theirs[s]["ids"]) for s in mine if mine[s] != theirs[s]["ids"]})
        expect("... a short list, a run with a remark, 'All P0 except' and 'every P0 PASS' among them",
               mine["R1"] == ["APP-01", "APP-02", "DATA-01", "DATA-02"]
               and mine["R2"] == [i for i, (p, _) in reqs.items() if p == tier and i != "REL-01"] + ["DOC-01"]
               and mine[flow.GOAL] == [i for i, (p, _) in reqs.items() if p == tier], mine)

        # the freeze marker: board.py's own reader and office.py's give the same answer
        fdir = tmp / "freeze-compare"
        fdir.mkdir()
        now = time.time()
        cases = [("no file", None), ("on", {"by": "MGR-2", "why": "w", "lane": "G2", "at": now - 10, "max_s": 600}),
                 ("past its limit", {"by": "MGR-2", "why": "w", "lane": None, "at": now - 900, "max_s": 600}),
                 ("no limit", {"by": "MGR-2", "why": "", "at": now - 9e6}), ("no `at`", {"by": "MGR-2"}), ("not JSON", "{")]
        # numbers no clock can show: each reads as a freeze in force by "unknown", and neither reader raises
        odd = [("`at` in milliseconds", json.dumps({"by": "MGR-2", "why": "w", "lane": "G2", "at": now * 1000, "max_s": 600})),
               ("`at` 1e999", '{"by": "MGR-2", "why": "w", "at": 1e999, "max_s": 600}'),
               ("`max_s` 1e999", '{"by": "MGR-2", "why": "w", "at": %d, "max_s": 1e999}' % int(now))]
        have = getattr(office_mod, "freeze_facts", None)
        facts = ("on", "by", "lane", "at", "max_s", "stale")
        for name, body in cases + odd:
            (fdir / "freeze.json").unlink(missing_ok=True)
            if body is not None:
                (fdir / "freeze.json").write_text(body if isinstance(body, str) else json.dumps(body), encoding="utf-8")
            try:
                mine_f = board.read_freeze(fdir, now)
            except Exception as e:  # noqa: BLE001 - the point of the check
                mine_f = {"raised": f"{type(e).__name__}: {e}"}
            expect(f"freeze, {name}: the reader gives the seven keys",
                   set(mine_f) == set(board.FREEZE_KEYS) and mine_f["on"] is (body is not None), mine_f)
            if (name, body) in odd:
                try:
                    line = board.freeze_text(mine_f)
                except Exception as e:  # noqa: BLE001
                    line = f"raised {type(e).__name__}: {e}"
                expect(f"freeze, {name}: on, by unknown, the reason in `why`, no time kept, and its line is printed",
                       mine_f.get("on") is True and mine_f.get("by") == "unknown" and bool(mine_f.get("why"))
                       and mine_f.get("at") is None and mine_f.get("max_s") is None and mine_f.get("stale") is False
                       and line.startswith("unknown froze the main checkout: "), (mine_f, line))
            if have:
                try:
                    theirs_f = have(fdir, now)
                except Exception as e:  # noqa: BLE001
                    theirs_f = {"raised": f"{type(e).__name__}: {e}"}
                # the two `why` texts need not be the same words: each reader's own reason is taken
                expect(f"freeze, {name}: board.py's reader and office.freeze_facts agree",
                       "raised" not in theirs_f and "raised" not in mine_f
                       and {k: theirs_f.get(k) for k in facts} == {k: mine_f.get(k) for k in facts}
                       and bool(theirs_f.get("why")) == bool(mine_f.get("why")), (mine_f, theirs_f))
        # every time in a freeze's line is formatted under a guard, whatever a reader handed over
        for name, fz in (("an `at` in milliseconds", {"on": True, "by": "MGR-2", "at": now * 1000, "max_s": 600, "stale": True}),
                         ("an infinite `at` and `max_s`", {"on": True, "by": "MGR-2", "at": float("inf"),
                                                           "max_s": float("inf"), "stale": True}),
                         ("texts for numbers", {"on": True, "by": "MGR-2", "at": "soon", "max_s": "long", "stale": True})):
            try:
                line = board.freeze_text(fz)
            except Exception as e:  # noqa: BLE001
                line = f"raised {type(e).__name__}: {e}"
            expect(f"freeze_text with {name} prints its line", line.startswith("MGR-2 froze the main checkout") and "DEAD?" in line, line)
        # the office's answer is checked the same way: one that says on with a time no clock can show is "unknown"
        office_fn = getattr(office_mod, "freeze_facts", None)
        try:
            office_mod.freeze_facts = lambda d=None, now=None: {"on": True, "by": "MGR-7", "why": "w", "lane": None,
                                                               "at": time.time() * 1000, "max_s": 60, "stale": False}
            got = board.freeze_facts(now)
        except Exception as e:  # noqa: BLE001
            got = {"raised": f"{type(e).__name__}: {e}"}
        finally:
            if office_fn is None:
                del office_mod.freeze_facts
            else:
                office_mod.freeze_facts = office_fn
        expect("freeze_facts reads an office answer with `at` in milliseconds as a freeze by unknown",
               got.get("on") is True and got.get("by") == "unknown" and got.get("at") is None and bool(got.get("why")), got)
        expect("rr_slots writes a window from each slot's start, and refuses one longer than a slot",
               [s["rr"] for s in board.rr_slots([{"id": "day", "start": "06:00"}, {"id": "night", "start": "22:30"}], 120)]
               == ["06:00-08:00", "22:30-00:30"] and _raises(lambda: board.rr_slots([{"id": "a", "start": "06:00"},
                                                                                    {"id": "b", "start": "07:00"}], 90)))
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    # ---- 3. the starter roadmap
    ex = EXAMPLE.read_text(encoding="utf-8")
    page = FORMAT_PAGE.read_text(encoding="utf-8")
    a = page.index("```markdown\n") + len("```markdown\n")
    expect("the format page's complete roadmap is the starter, byte for byte", page[a:page.index("```\n", a)] == ex)
    statuses =re.findall(r"^\| [A-Z0-9]+-\d+ \| P\d \| (\w+) \|", ex, re.M)
    expect("the starter has every status but PASS, and no milestone is done",
           set(statuses) == {"Part", "Planned", "Decided", "Open"} and not re.search(r"\bdone\b", ex)
           and not re.search(r"\| PASS \||PASS\)", ex.split("### Count")[0]), statuses)
    count = re.search(r"^\| \*\*P0\*\* \| (\d+) \| (\d+) \| (\d+) \| (\d+) \| (\d+) \| (\d+) \|", ex, re.M)
    p0 = [s for s in re.findall(r"^\| [A-Z0-9]+-\d+ \| P0 \| (\w+) \|", ex, re.M)]
    expect("the starter's Count table agrees with its rows",
           count is not None and [int(x) for x in count.groups()]
           == [p0.count(k) for k in ("PASS", "Part", "Planned", "Decided", "Open")] + [len(p0)], count and count.groups())
    road, renv = project("only-roadmap")
    (road / "docs").mkdir()
    (road / "docs" / "ROADMAP.md").write_text(ex, encoding="utf-8", newline="\n")
    rc, o = run(renv, "flow.py", "selftest")
    last = (o.strip().splitlines() or [""])[-1]
    expect("flow.py selftest on a project that holds only the starter roadmap: 0 problems",
           rc == 0 and " 0 problems" in last and "FAIL" not in o, o[-600:])
    rc, o = run(renv, "board.py", "check", "--no-build")
    expect("... and board.py check there has no warning about the roadmap, and reads both stages",
           "ROADMAP" not in o.split("needs attention")[-1].replace("no roadmap", "") and "R0 0/3, 1.0 1/6" in o, o[-700:])
    fresh, fenv = project("founded")
    rc, o = run(fenv, "founder.py", "init", "--project", "Scratch")
    rc2, o2 = run(fenv, "board.py", "check")
    warns = [l for l in o2.splitlines() if l.strip().startswith("!")]
    expect("founder.py init writes the starter roadmap and the state",
           rc == 0 and (fresh / "docs" / "ROADMAP.md").is_file() and (fresh / "docs" / "progress" / "state.json").is_file(), o)
    expect("a project fresh from founder.py init: board.py check prints no warning about the roadmap",
           not [w for w in warns if "ROADMAP" in w or "PASS" in w or "roadmap" in w] and "PASS with no lane named: 0" in o2, o2[-800:])
    expect("... and no warning at all", rc2 == 0 and not warns and "warnings: none" in o2, warns)

    # ---- 3b. the roadmap's milestones and decisions in the state
    def tool(penv):
        return lambda *args: run(penv, "board.py", *args)

    def state_of(p):
        return json.loads((p / "docs" / "progress" / "state.json").read_text(encoding="utf-8"))

    # the founding story: founder.py init writes the starter roadmap and the state; the founder then writes the
    # real roadmap; sync and adopt bring the state to it, whatever was taken from the starter meanwhile
    pl, penv = project("plan")
    pb = tool(penv)
    pstate = pl / "docs" / "progress" / "state.json"
    rc, o = run(penv, "founder.py", "init", "--project", "Plan")
    starter = (pl / "docs" / "ROADMAP.md").read_text(encoding="utf-8")
    s = state_of(pl)
    expect("init takes no milestone and no decision from the starter roadmap",
           rc == 0 and starter.startswith("<!-- STARTER") and s["milestones"] == [] and s["decisions"] == [], (s["milestones"], s["decisions"]))
    rc, o = pb("milestone", "set", "M1", "--status", "in-progress")
    rc2, o2 = run(penv, "flow.py", "selftest")
    last = (o2.strip().splitlines() or [""])[-1]
    expect("after founder.py init and milestone set M1, flow.py selftest still finds 0 problems",
           rc == 0 and rc2 == 0 and " 0 problems" in last and "not in the map's milestones" not in o2
           and [m["id"] for m in state_of(pl)["milestones"]] == ["M1", "M2", "M3"], o + o2[-600:])
    # what an earlier init did by itself, done by hand here: the starter's decisions in the register
    rc, o = pb("decide", "adopt", "D1")
    rc2, o2 = pb("decide", "adopt", "D2")
    rc3, o3 = pb("decide", "ask", "--by", "FDR-1", "--question", "Which font?")
    expect("the starter's D1 and D2 are adopted, and decide ask takes D3 (never a second D1)",
           rc == 0 and rc2 == 0 and rc3 == 0 and "D3 filed" in o3
           and {d["id"]: d["status"] for d in state_of(pl)["decisions"]} == {"D1": "answered", "D2": "open", "D3": "open"}, o + o2 + o3)
    pb("milestone", "set", "M9", "--status", "planned", "--title", "Extra", "--note", "the user asked for it")
    was = pstate.read_bytes()
    rc, o = pb("decide", "adopt", "D2")
    rc2, o2 = pb("decide", "adopt", "D9")
    rc3, o3 = pb("milestone", "set", "M8", "--status", "planned")
    rc4, o4 = pb("decide", "withdraw", "D1", "--note", "an example")
    rc5, o5 = pb("decide", "adopt", "D3", "--refresh")
    rc6, o6 = pb("decide", "adopt", "D2", "--refresh", "--by", "MGR-1")
    expect("refused (exit 2), nothing written: adopt of an id the register has (it names --refresh) or the roadmap lacks, "
           "a milestone the roadmap does not name with no --title, withdraw of an answered decision the roadmap still "
           "names, --refresh of a decision a person asked, --refresh with another option",
           [rc, rc2, rc3, rc4, rc5, rc6] == [2] * 6 and "already has D2" in o and "--refresh" in o and "names no D9" in o2
           and "already answered" in o4 and "asked" in o5 and pstate.read_bytes() == was, o + o2 + o3 + o4 + o5 + o6)
    rc, o = pb("check")
    expect("while the roadmap is the starter the check says nothing about milestones or decisions the state lacks",
           "milestone sync" not in o and "decide adopt" not in o and "disagree" not in o, o[-600:])

    # the founder writes the real roadmap: other titles, another lane, M4 for M3, D5 for D1, D2 asked differently
    real = (ex.replace("M3", "M4").replace("Skeleton: the app starts", "Kernel: the app starts")
            .replace("Store: what the user makes is kept", "Vault: nothing the user makes is lost").replace("M2 G2", "M2 G7")
            .replace("| D1 | Release channel (REL-01)", "| D5 | Release cadence (REL-01)")
            .replace("Storage format (DATA-01)", "Where the data lives (DATA-01)"))
    expect("the real roadmap of this story differs from the starter in each of those", real.count("M4") >= 2 and "M3" not in real
           and "Kernel:" in real and "Vault:" in real and "M2 G7" in real and "| D5 |" in real and "| D1 |" not in real
           and "Where the data lives" in real)
    (pl / "docs" / "ROADMAP.md").write_text(real, encoding="utf-8", newline="\n")
    rc, o = pb("check")
    warns = [l for l in o.splitlines() if l.strip().startswith("!")]
    expect("the check now names the milestone the state lacks (the decided D5 is not asked for: only open ones are)",
           any("M4" in w and "milestone sync" in w for w in warns) and not any("decide adopt" in w for w in warns), warns)
    rc, o = pb("milestone", "sync")
    by_id = {m["id"]: m for m in state_of(pl)["milestones"]}
    expect("milestone sync adds M4 and rewrites the untouched planned M2 from its row, printing each change",
           rc == 0 and "added M4" in o and "M2 title" in o and "M2 lane" in o and by_id["M2"]["title"].startswith("Vault:")
           and by_id["M2"]["lane"] == "G7" and by_id["M4"]["status"] == "planned", o)
    expect("... leaves the milestone in progress as it was, and points at --prune for the ones the roadmap dropped",
           by_id["M1"]["title"].startswith("Skeleton:") and by_id["M1"]["status"] == "in-progress" and "M1 title" not in o
           and set(by_id) == {"M1", "M2", "M3", "M4", "M9"} and "--prune" in o and "M3" in o, o)
    rc, o = pb("milestone", "sync", "--prune")
    ids = [m["id"] for m in state_of(pl)["milestones"]]
    expect("milestone sync --prune removes the planned, untouched M3 and keeps M9 (it has a note), listing both",
           rc == 0 and "removed M3" in o and "M9 (it has a note)" in o and ids == ["M1", "M2", "M9", "M4"], o + str(ids))
    rc, o = pb("decide", "adopt", "D2", "--refresh")
    rc2, o2 = pb("decide", "adopt", "D5", "--by", "FDR-1")
    rc3, o3 = pb("decide", "withdraw", "D1")
    rc4, o4 = pb("decide", "withdraw", "D1", "--note", "the starter's example")
    reg = {d["id"]: d for d in state_of(pl)["decisions"]}
    expect("decide adopt --refresh reads D2 again from its new row; D5 is adopted; the starter's answered D1, which the "
           "roadmap no longer names, is withdrawn with --note (exit 2 without one)",
           [rc, rc2, rc3, rc4] == [0, 0, 2, 0] and reg["D2"]["question"] == "Where the data lives (DATA-01)"
           and reg["D2"]["status"] == "open" and reg["D5"]["status"] == "answered" and reg["D5"]["by"] == "FDR-1"
           and reg["D1"]["status"] == "withdrawn" and reg["D1"]["note"] == "the starter's example"
           and reg["D3"]["question"] == "Which font?", o + o2 + o3 + o4)
    pb("decide", "answer", "D2", "--words", "one file")
    was = pstate.read_bytes()
    rc, o = pb("decide", "adopt", "D2", "--refresh")
    rc2, o2 = pb("decide", "adopt", "D5", "--refresh")
    expect("--refresh never rewrites an entry a person answered here, nor one a badge adopted (exit 2)",
           rc == 2 and rc2 == 2 and pstate.read_bytes() == was, o + o2)
    (pl / "docs" / "ROADMAP.md").write_text(real.replace("Open: one file, or a folder of files", "**Decided:** one file"),
                                           encoding="utf-8", newline="\n")
    rc, o = pb("check")
    warns = [l for l in o.splitlines() if l.strip().startswith("!")]
    expect("with the state brought to the real roadmap, the check has no warning about the roadmap",
           not [w for w in warns if "ROADMAP" in w or "roadmap" in w or "milestone sync" in w or "decide adopt" in w
                or "disagree" in w], warns)
    rc, o = run(penv, "flow.py", "selftest")
    expect("... and flow.py selftest finds 0 problems", rc == 0 and " 0 problems" in (o.strip().splitlines() or [""])[-1], o[-600:])

    # what init says is next, and what it takes, depends on the roadmap it finds
    sd, senv = project("seeded")
    (sd / "docs").mkdir()
    (sd / "docs" / "ROADMAP.md").write_text(ex, encoding="utf-8", newline="\n")
    rc, o = run(senv, "board.py", "init")
    s = state_of(sd)
    expect("init with a real roadmap there starts the state with its milestones and decisions, and does not send the "
           "reader to `milestone set`",
           rc == 0 and [(m["id"], m["status"], m["lane"]) for m in s["milestones"]]
           == [("M1", "planned", "G1"), ("M2", "planned", "G2"), ("M3", "planned", "")]
           and {d["id"]: d["status"] for d in s["decisions"]} == {"D1": "answered", "D2": "open"}
           and "Next: the first shift plan" in o and "milestone set" not in o, o)
    st2, s2env = project("starter-init")
    (st2 / "docs").mkdir()
    (st2 / "docs" / "ROADMAP.md").write_text(starter, encoding="utf-8", newline="\n")
    rc, o = run(s2env, "board.py", "init")
    expect("init with the starter roadmap takes nothing and says the founder writes the roadmap first",
           rc == 0 and state_of(st2)["milestones"] == [] and state_of(st2)["decisions"] == []
           and "still the starter" in o and "board.py milestone sync" in o, o)

    # the profile may name decisions otherwise (roadmap.decision_id): the register follows it
    qd, qenv = project("q-ids", FOUNDRY_ROADMAP_DECISION_ID="Q\\d+")
    qb = tool(qenv)
    (qd / "docs").mkdir()
    (qd / "docs" / "ROADMAP.md").write_text(ex.replace("D1", "Q2").replace("D2", "Q7"), encoding="utf-8", newline="\n")
    rc, o = qb("init")
    rc2, o2 = qb("decide", "answer", "Q7", "--words", "one file")
    rc3, o3 = qb("decide", "ask", "--by", "FDR-1", "--question", "Which font?")
    rc4, o4 = qb("decide", "withdraw", "Q8", "--note", "not needed")
    rc5, o5 = qb("decide", "answer", "D1", "--words", "x")
    reg = {d["id"]: d["status"] for d in state_of(qd)["decisions"]}
    expect("with roadmap.decision_id = Q\\d+: init adopts Q2 and Q7, decide answer Q7 is taken, decide ask files Q8, "
           "withdraw Q8 is taken, and D1 is no id (exit 2)",
           [rc, rc2, rc3, rc4, rc5] == [0, 0, 0, 0, 2] and "Q8 filed" in o3
           and reg == {"Q2": "answered", "Q7": "answered", "Q8": "withdrawn"}, o + o2 + o3 + o4 + o5 + str(reg))
    nd, nenv = project("named-ids", FOUNDRY_ROADMAP_DECISION_ID="DEC-[a-z]+")
    nb = tool(nenv)
    nb("init")
    rc, o = nb("decide", "ask", "--by", "FDR-1", "--question", "Which font?")
    rc2, o2 = nb("decide", "ask", "--by", "FDR-1", "--question", "Which font?", "--id", "DEC-font")
    rc3, o3 = nb("decide", "ask", "--by", "FDR-1", "--question", "Again?", "--id", "DEC-font")
    rc4, o4 = nb("decide", "ask", "--by", "FDR-1", "--question", "Odd?", "--id", "D9")
    rc5, o5 = nb("decide", "answer", "DEC-font", "--words", "serif")
    expect("with a pattern that is not a prefix and a number, decide ask needs --id and says so; a taken id and one "
           "the pattern does not match are refused (exit 2)",
           [rc, rc2, rc3, rc4, rc5] == [2, 0, 2, 2, 0] and "--id" in o and "DEC-font filed" in o2
           and {d["id"]: d["status"] for d in state_of(nd)["decisions"]} == {"DEC-font": "answered"}, o + o2 + o3 + o4 + o5)

    # a state older than its roadmap: the check names what it lacks, and the commands fill it in
    lt, tenv = project("late", FOUNDRY_SWEEP_GUARD="1", FOUNDRY_RESOURCE_NAME="")
    tb = tool(tenv)
    tb("init")
    expect("init with no roadmap starts with no milestone and no decision",
           state_of(lt)["milestones"] == [] and state_of(lt)["decisions"] == [])
    (lt / "docs" / "ROADMAP.md").write_text(ex, encoding="utf-8", newline="\n")
    rc, o = tb("check")
    warns = [l for l in o.splitlines() if l.strip().startswith("!")]
    expect("the check warns, in one line each with the command, about the roadmap's milestones and its open decision",
           len([w for w in warns if "M1, M2, M3" in w and "board.py milestone sync" in w]) == 1
           and len([w for w in warns if "board.py decide adopt D2" in w and "D1" not in w]) == 1, warns)
    rc, o = tb("decide", "ask", "--by", "FDR-1", "--question", "Which font?")
    expect("decide ask on an empty register numbers after the roadmap's D2", rc == 0 and "D3 filed" in o, o)
    rc, o = tb("decide", "adopt", "D2", "--by", "MGR-1", "--needed-before", "M2")
    rc2, o2 = tb("decide", "adopt", "D1")
    reg = {d["id"]: d for d in state_of(lt)["decisions"]}
    expect("decide adopt files D2 open with the roadmap's question, and D1 answered with where it stands",
           rc == 0 and rc2 == 0 and reg["D2"]["status"] == "open" and reg["D2"]["question"] == "Storage format (DATA-01)"
           and reg["D2"]["needed_before"] == "M2" and reg["D2"]["by"] == "MGR-1" and reg["D1"]["status"] == "answered"
           and "one stable channel" in reg["D1"]["answer"], o + o2 + str(reg))
    rc, o = tb("milestone", "set", "M2", "--status", "in-progress")
    ms = state_of(lt)["milestones"]
    expect("milestone set of a new id the roadmap names adds the others too, and says so",
           rc == 0 and "M1, M3 added too" in o and [(m["id"], m["status"], m["lane"]) for m in ms]
           == [("M1", "planned", "G1"), ("M2", "in-progress", "G2"), ("M3", "planned", "")] and ms[1]["title"].startswith("Store"), o)
    rc, o = run(tenv, "flow.py", "selftest")
    expect("... and flow.py selftest finds 0 problems there",
           rc == 0 and " 0 problems" in (o.strip().splitlines() or [""])[-1], o[-600:])
    rc, o = tb("check")
    expect("... and the check's two lines are gone", "milestone sync" not in o and "decide adopt" not in o, o[-600:])

    def drop_m3():
        j = state_of(lt)
        j["milestones"] = [m for m in j["milestones"] if m["id"] != "M3"]
        (lt / "docs" / "progress" / "state.json").write_text(json.dumps(j, indent=1) + "\n", encoding="utf-8", newline="\n")

    drop_m3()
    rc, o = tb("milestone", "sync")
    ms2 = state_of(lt)["milestones"]
    rc2, o2 = tb("milestone", "sync")
    expect("milestone sync adds the one the state lacks and changes no other; a second sync adds nothing (exit 0)",
           rc == 0 and "added M3" in o and ms2 == ms and rc2 == 0 and "nothing to add" in o2 and state_of(lt)["milestones"] == ms, o + o2)
    rc, o = tb("milestone", "sync", "M1")
    expect("milestone sync takes no argument (exit 2)", rc == 2, o)
    drop_m3()
    (Path(tenv["FOUNDRY_PATHS_OFFICE"]) / "freeze.json").write_text(json.dumps({"by": "MGR-1", "why": "a counted run",
                                                                              "at": time.time() - 5, "max_s": 3600}), encoding="utf-8")
    rc, o = tb("milestone", "sync")
    expect("milestone sync under a freeze is held like the other edits",
           rc == 0 and "held, not written" in o and len(state_of(lt)["milestones"]) == 2, o)
    (Path(tenv["FOUNDRY_PATHS_OFFICE"]) / "freeze.json").unlink()
    rc, o = tb("build")
    expect("... and applied after it", rc == 0 and "applied 1 of 1" in o and state_of(lt)["milestones"] == ms, o)
    tb("decide", "answer", "D2", "--words", "one file")
    rc, o = tb("check")
    expect("the check says when the register calls a decision answered and the roadmap calls it open",
           len([l for l in o.splitlines() if l.strip().startswith("!") and "disagree" in l and "D2" in l]) == 1, o[-600:])

    # the roadmap's own rows: a decisions row the reader dropped, and an id two rows carry, are named by the check
    od, oenv = project("odd-road", FOUNDRY_RESOURCE_NAME="")
    run(oenv, "board.py", "init")
    (od / "docs" / "ROADMAP.md").write_text(
        ex.rstrip("\n") + "\n| D3 | Format: one file \\| a folder (DATA-02) | Open: undecided | the user | M3 |\n"
        "| D2 | Storage format, again | Open: still | the user | M2 |\n| D4 | a row with too few cells |\n\n"
        "| Milestone | Theme | Closes | Why here |\n|---|---|---|---|\n| M1 | Skeleton, a second row | APP-01 | First |\n",
        encoding="utf-8", newline="\n")
    rc, o = run(oenv, "board.py", "check")
    warns = [l for l in o.splitlines() if l.strip().startswith("!")]
    lost = [w for w in warns if "decisions row(s)" in w and "not read" in w]
    expect("the check names, in one line, a decisions row that opens like one and was not read (too few cells)",
           len(lost) == 1 and "D4" in lost[0] and "Traceback" not in o, warns)
    # the row with a pipe inside a cell is read by a reader that splits on unescaped pipes (flow.py's may or may
    # not): it is either named in that line, or it is a decision the register can adopt with its text whole
    rc, o = run(oenv, "board.py", "decide", "adopt", "D3")
    d3 = [d["question"] for d in state_of(od)["decisions"] if d["id"] == "D3"]
    expect("a decisions row with an escaped pipe is never dropped in silence: it is named as not read, or adopted whole",
           ("D3" in lost[0] and rc == 2) if lost and "D3" in lost[0] else (rc == 0 and d3 and "one file" in d3[0] and "a folder" in d3[0]),
           (lost, rc, o, d3))
    expect("... and the milestone and the decision that two rows carry",
           len([w for w in warns if "more than one milestone row for M1" in w]) == 1
           and len([w for w in warns if "more than one decision row for D2" in w]) == 1, warns)

    # ---- 4. printed commands
    fmap = (fresh / "docs" / "progress-map.html").read_text(encoding="utf-8")
    abs_tools = (fresh.resolve() / "scripts" / "foundry").as_posix()
    expect("the map prints tool commands relative to the checkout",
           "python scripts/foundry/board.py check</code>" in fmap and "python scripts/foundry/office.py roster" in fmap
           and abs_tools not in fmap, [l for l in fmap.splitlines() if "board.py check" in l][:2])
    rc, o = run(fenv, "board.py", "usage", "10")
    rc, o = run(fenv, "board.py", "check")
    expect("the check's hints are relative too", "python scripts/foundry/office.py roster" in o and abs_tools not in o, o[-600:])
    prof = fresh / ".foundry" / "foundry.toml"
    text = prof.read_text(encoding="utf-8")

    def parsed(want):
        """True when the profile file the scratch project has now parses, with board.absolute_commands as wanted
        and commands.python as wanted: a fixture that is not TOML must fail here, never pass on the defaults
        (foundry_profile.load may report a broken file in .problems, or print it and exit 2)."""
        import foundry_profile
        keys = [k for k in fenv if k.startswith("FOUNDRY_")]
        was = {k: os.environ.get(k) for k in keys + ["FOUNDRY_PROFILE"]}
        os.environ.update({k: fenv[k] for k in keys})
        os.environ.pop("FOUNDRY_PROFILE", None)
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                p = foundry_profile.load(str(fresh))
            return (p.problems == [] and p.file is not None and Path(p.file).resolve() == prof.resolve()
                    and (p.get("board.absolute_commands"), p.get("commands.python")) == want)
        except SystemExit:
            return False
        finally:
            for k, v in was.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    expect("the profile founder.py init wrote parses, with board.absolute_commands off", parsed((False, "")), text[-400:])
    expect("with_board_key replaces the key in a [board] table, adds it to one without it, and appends the table "
           "only to a file that has none",
           with_board_key("[board]\nx = 1\nabsolute_commands = false  # c\n\n[git]\ny = 2\n", "true")
           == "[board]\nx = 1\nabsolute_commands = true\n\n[git]\ny = 2\n"
           and with_board_key("[board]\nx = 1\n[git]\nabsolute_commands = false\n", "true")
           == "[board]\nabsolute_commands = true\nx = 1\n[git]\nabsolute_commands = false\n"
           and with_board_key('project = "x"\n', "true") == 'project = "x"\n\n[board]\nabsolute_commands = true\n')
    prof.write_text(with_board_key(text, "true"), encoding="utf-8", newline="\n")
    expect("the profile with board.absolute_commands = true parses (one [board] table)",
           parsed((True, "")) and prof.read_text(encoding="utf-8").count("[board]") == text.count("[board]") + ("[board]" not in text),
           prof.read_text(encoding="utf-8")[-400:])
    rc, o = run(fenv, "board.py", "check")
    fmap = (fresh / "docs" / "progress-map.html").read_text(encoding="utf-8")
    expect("board.absolute_commands = true prints the host's absolute paths on the map and in the check",
           f"{abs_tools}/board.py check" in fmap and f"{abs_tools}/office.py roster" in o, o[-400:])
    prof.write_text(text.replace('python = ""', 'python = "py3"', 1), encoding="utf-8", newline="\n")
    expect("the profile with commands.python set parses", parsed((False, "py3")), prof.read_text(encoding="utf-8")[:400])
    rc, o = run(fenv, "board.py", "check")
    expect("the profile's commands.python is printed when it is set",
           'python = "py3"' in prof.read_text(encoding="utf-8") and "py3 scripts/foundry/office.py roster" in o, o[-400:])

    for x in ok:
        print(f"  ok   {x}")
    for x in bad:
        print(f"  FAIL {x}")
    print(f"board edits test: {len(ok)} ok, {len(bad)} failed" + (f" (scratch kept: {tmp.as_posix()})" if bad else ""))
    if not bad:
        remove_tree(tmp)
    return 1 if bad else 0


def _raises(fn):
    try:
        fn()
    except ValueError:
        return True
    return False


if __name__ == "__main__":
    sys.exit(main())
