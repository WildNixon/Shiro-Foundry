# Troubleshooting

The refusals and warnings a new user meets, each with what it means and what to do. The messages are quoted from the tools; paths are shortened to `~/myproject` and the interpreter to `python`.

One rule covers all of them: **a refusal means stop.** A tool, a hook or a permission prompt that says no is telling you something. Read the message, fix the cause or ask the user. Do not look for another route to the same end, and do not let an agent do so.

- [Badges and the clock](#badges-and-the-clock)
- [Hiring](#hiring)
- [The shared resource](#the-shared-resource)
- [The board: held, kept in pending, DEAD?, no state yet, the roadmap and the state](#the-board)
- [Counted runs, the sweep and the freeze](#counted-runs-and-the-sweep)
- [Hand-in PROBLEMs](#hand-in-problems)
- [The hooks' refusals](#the-hooks-refusals)
- [The charts](#the-charts)
- [The profile does not parse](#the-profile-does-not-parse)
- [Doctor's PROBLEM lines](#doctors-problem-lines)
- [FAQ](#faq)

## Badges and the clock

### A refused badge line

```
refused: badge EMP-09: the signature does not match (a changed or mistyped line)
```

The line was changed, cut short or retyped. A badge line must be passed whole, in quotes, exactly as `hire` printed it. Copy it again from the brief. The manager reprints it with `office.py brief EMP-09 --by "<the manager's line>"`; the holder reads its own record with `office.py me --badge "<line>"` once it has the right line. Never edit or make up a line.

```
refused: badge MGR-1 was revoked at 15:17: a new manager was appointed (swing-manager)
```

A newer manager or founder badge replaced this one. The old session stops managing. `office.py roster` names the manager on the clock.

```
refused: MGR-2 is already on the clock (in at 15:17)
```

The badge clocked in before. Nothing to do: carry on with `progress`.

```
refused: EMP-01 is not the current manager (MGR-2)
```

A manager's command (`hire`, `amend`, `end-shift`, `freeze`) was given another badge's line as `--by`. Only the manager on the clock runs them.

### `appoint` is refused

```
refused: MGR-2 (swing-manager) is the manager and on the clock, heard 15:29. There is one manager: ask the user before relieving it (appoint --relieve).
```

There is one manager at a time. If the other manager is working, this session is not needed. If it is gone, ask the user, then `office.py appoint --name NAME --relieve`. `found` refuses a second founder the same way.

### STALE and OVERDUE

On the roster:

```
    EMP-02 g1-grader grader session: STALE 10% finish ~15:19 (in 1 min); heard 15:18; "reading the contract"
```

In `board.py check`:

```
    ! EMP-02 g1-grader is STALE: not heard from since 15:18; the manager chases it or clocks it out.
```

- **STALE**: no `progress` for longer than `limits.stale_min` (45 minutes). For a manager or founder the limit is `limits.manager_stale_min` (2 hours).
- **OVERDUE**: past its own finish by more than `limits.overdue_min` (15 minutes).

Neither means the session is dead; they mean nobody has heard from it. Only `office.py progress` counts as being heard: commits and chat messages do not.

What to do, as the employee: post `progress` with an honest `--pct` and a new `--eta`. If you are waiting on someone else's job, post once with `--waiting-on <that badge or queue id>`.

What to do, as the manager: read the queue first (an employee whose job waits or holds a seat is not STALE). Then message the session. If it is gone, clock it out and hire again:

```
python scripts/foundry/office.py clock-out --by "<the manager's line>" --id EMP-02 --result lost --note "session closed"
```

`UP` is also not proof of life. The roster says so: "UP means a punch inside 2 h, not that the session is running: check the session itself".

### A session badge with no session

```
[crew] EMP-02 g1-grader (grader) is a session badge with no session: start or re-badge a bench and record it, `... office.py assign EMP-02 --session local_...`, or clock it out
```

The badge was hired as a session and nobody recorded which session holds it. It counts toward `crew_max` meanwhile. Start the session and run `office.py assign EMP-02 --session local_<its id>`, or clock the badge out as `lost`.

### A duration cannot be read

```
refused: cannot read the duration 'soon'; write 90m, 2h or 1h30m
```

`--eta` takes `90m`, `2h`, `1h30m`, a bare number of minutes, or (for `progress`) a clock time such as `17:50`.

```
refused: cannot read the duration '120': write a unit: 30m, 3h
```

`office.py freeze on --max` takes a unit, as the queue does. `--eta` is the one place a bare number is still read.

## Hiring

### `hire` refused for `crew_max`

```
refused: the shift start is at its crew_max of 1 (EMP-02 g1-grader); clock someone out or raise crew_max with a note
```

The shift's headcount is full. It counts every employee badge on the shift that is not clocked out, hired-but-not-in ones included. Clock out a badge that is finished or gone. Raising the number is the user's call; record their words:

```
python scripts/foundry/board.py shift set --crew-max 4 --by MGR-2 --words "Four is fine."
```

A different message, `the shift <id> has no crew_max in state.json`, means the shift was promoted from a queue entry that had none. The profile's `limits.crew_max` only fills the starter shift. Ask the user for the number and set it the same way.

### `--rq` with no resource

```
refused: --rq: this project names no shared resource. Name one as `[resource] name` in .foundry/foundry.toml (and its seats), then hire again
```

`--rq` and `--seat` say how a badge reaches the shared resource, and the profile names none. If the project shares nothing, hire without the flag. If it does, the founder names it in the profile ([profile.md](profile.md#resource)). If you believe the profile does name one, run `foundry_profile.py where`: a worktree with its own `.foundry/foundry.toml` reads that file, not the main checkout's.

### A grader as a temp

```
refused: a GRADER is its own session: a subagent of the manager is not independent of the build
```

Hire the grader with `--kind session`. The same rule applies to any title whose card allows only sessions:

```
refused: title auditor is hired as session, not as a temp: its card says independent, and a subagent of the manager is not
```

### An unknown title

```
refused: title 'security-fixer': the known titles are builder, cleaner, fixer, grader, reviewer, scout, triager (a project adds one as [titles.<name>] with like = "<built-in>" in .foundry/foundry.toml)
```

The title is not in the profile the tool read. Add its card under `[titles.<name>]`, or run `foundry_profile.py where` to see which file was read.

### A `--files` path that does not exist

```
refused: --files 'nosuch/dir/' matches no file and nosuch/dir/ does not exist in the main checkout: check the path (amend --set-files replaces the list). Fix the path, or pass --force-files if the job creates that folder
```

Exit 2. Usually a typo. When the job is to create that folder, pass `--force-files`.

### A flagged title and `--model`

```
refused: title security-fixer is flagged: its work is built on claude-opus-5-5 ([flagged.security-fixer] model), not claude-haiku-5. Drop --model, or pass --force-model if the user said so
```

## The shared resource

### `rq.py` with no resource

```
rq: this project names no shared resource, so there is nothing to queue for; name one under [resource] (name, seats) in ~/myproject/.foundry/foundry.toml
```

Exit 2. Run the command directly, without the queue, or name the resource in the profile.

### A bare-number `--max`

```
rq.py run: error: argument --max: '120' has no unit; write a unit: 90s, 30m, 2h, 4h30m
```

`rq.py --max` and `--wait` refuse a bare number, because "120" meant as two hours would become a two-minute hold. Write `120m` or `2h`. Exit 2. `sweep.py --max-per-lane` and `--wait` refuse one the same way.

```
rq.py run: error: argument --max: '0s' is no time at all: a hold or a wait is longer than zero; write a unit: 90s, 30m, 2h, 4h30m
```

A zero time is refused too.

Mind the difference: `office.py --eta` does take a bare number, and reads it as minutes. `office.py freeze on --max` does not.

### A second job under one badge

```
rq: EMP-04 holds seat a (first). One queue job per badge, so this job is refused. That hold is a `take`: your own manual work on the seat. Finish that work, then free the seat yourself with `python ~/myproject/scripts/foundry/rq.py release --id EMP-04 --note "what ran"` (a `take` holder always releases its own hold when its work is done), and run this job again.
```

Exit 3. One job per badge id. Chain the steps into one job, or queue the next after the first ends. A `run` job's hold is never released by hand: wait for it.

### A chain that does not run as a chain

```
rq: warning: several words after --, and one holds a shell operator; each word is quoted, so the operator is not run. Quote the whole chain as one word, or queue `-- sh <file>`.
```

Words after `--` are quoted one by one, so a bare `&&`, `;` or `|` among them reaches the command as a word. Write `-- "step-one && step-two"`.

### OVERDUE in `rq.py status`

```
seat a: MGR-2-counted-G1 since 15:17 (191 of 180 min, OVERDUE): counted G1
```

The hold is past its `--max` (the minutes held, of the minutes asked for). Nothing ends a job unless `--max` is enforced (`resource.enforce_max`). If the job is still working, leave it. If its session is gone, the manager frees the seat:

```
python scripts/foundry/rq.py force-release --by MGR-2 --note "the run's session is gone"
```

`--by` is the manager's badge id. Any other id gets `rq: only the manager force-releases`.

### Exit 6

`rq.py run` or `take` exits 6 when the wait ran out (`--wait`, 4 hours by default), or when the job was taken out of the queue with `rq.py leave`.

### Exit 124, exit 130

`rq.py run` exits 124 when the queue ended the job at its `--max` plus the grace (only where `--max` is enforced). It exits 130, or 128 plus a signal's number, when the `run` itself was stopped (Ctrl+C, TERM, HUP, or BREAK on Windows). Either way the job was ended with everything it started and the seat was released; the seat's last note says so. A job ended this way decided nothing: run it again.

## The board

### A held edit

```
note by MGR-1 added (checked, not written)
held, not written: the main checkout is frozen (MGR-1 froze the main checkout at 15:16 for G1: counted G1): nothing in this checkout may change until it ends. It is applied with this time by the next writing command run in the main checkout after it ends (board.py pending lists what is held).
```

Exit 0. Nothing is wrong. A counted run is in the queue, or the manager's freeze is on, so the edit was checked and put aside. It is applied, with the time you made it, by the next writing `board.py` command after the freeze ends:

```
python scripts/foundry/board.py pending
```

```
3 edit(s) held; frozen: MGR-1 froze the main checkout at 15:16 for G1: counted G1
  2026-11-24T15:16:11-06:00  note --by MGR-1 the grader starts next slot
  2026-11-24T15:16:12-06:00  blocker rm 1 --note the phone arrived --by MGR-1   (the blocker: the test phone is not on the desk)
  2026-11-24T15:16:13-06:00  checklist done 1   (the checklist line: check the VM is up)
```

Do not run the edit again, and keep no list of your own. During a freeze `board.py check` also says `map: docs/progress-map.html (not rebuilt)`, and `promote` and `init` are refused.

An edit that names an item by its number is held by what the item is (the text in parentheses above), so a list that changes meanwhile does not send it to the wrong item. The number is read against the state as it is written: the list `board.py check` prints during the freeze.

### An edit refused while others are held

```
refused: the blocker it names is gone: 'the test phone is not on the desk', once the 2 edit(s) already held are applied (board.py pending lists them)
```

Exit 2. An edit made during a freeze is checked against the state as it will be once the edits already held are applied. Here an earlier held edit removes that blocker, so a second removal has nothing to remove. Nothing to do.

```
no blocker 2: the state as it is written has 1. An edit held while the main checkout is frozen names an item by its number there (board.py check prints it); what an edit still held adds has no number until it is applied
```

Exit 2. An item that a held edit adds has no number yet. Make the second edit after the freeze.

### A held edit that stays in pending

After the freeze, from the first writing command:

```
  ! a held edit did not apply (the checklist line it names is gone: 'check the VM is up') and stays in pending-state.jsonl: {...}
applied 1 of 2 edit(s) held while the main checkout was frozen
  ! 1 held edit(s) did not apply: make them by hand, then delete ~/myproject/out/foundry/pending-state.jsonl
```

```
python scripts/foundry/board.py pending
```

```
1 edit(s) held; no counted sweep and no freeze: the next build, check or edit command run in the main checkout applies them
  2026-11-24T15:16:13-06:00  checklist done 1   (the checklist line: check the VM is up)   FAILED: the checklist line it names is gone: 'check the VM is up'
```

The item the edit named was gone at the replay, or two items read the same, so it could not be told which one was meant. That one edit is kept with its reason; the later ones were applied. Decide whether the edit is still wanted, make it by hand if so, then delete the file the message names. A line marked FAILED is not tried again.

### DEAD?

```
held, not written: a counted sweep is in the resource queue (MGR-2-counted-G1 (DEAD? its hold is past its limit, since 15:17)): nothing in this checkout may change until it ends; it looks DEAD (did the host restart?): check python scripts/foundry/rq.py status, and if no sweep is running, the manager frees its seats with python scripts/foundry/rq.py force-release. ...
```

Exit 4. A counted run's hold, or a freeze, is past its own limit. Usually the host restarted or the session that ran it is gone. The edit is still held.

1. Find out whether the run is alive: `rq.py status`, and the session that started it.
2. If it is running, wait. It took longer than its `--max`.
3. If it is gone, the manager frees it: `rq.py force-release --by MGR-2 --note "why"` for a queue hold, or `office.py freeze off --by "<the manager's line>"` for a freeze (with `--force` when a sweep set it: see [below](#freeze-off-is-refused)). A run that was cut off counted nothing: file it and queue it again.
4. Run any `board.py` writing command; the held edits are applied.

### Not held (exit 5)

`NOT held and not written: ... Run the command again.` The office's lock was busy at that instant. Run the same command again.

### "no state yet"

Under Needs attention on the map and in the brief:

```
[setup] no state yet: run founder.py init, or board.py init (it writes docs/progress/state.json)
```

From an edit command:

```
no state yet (~/myproject/docs/progress/state.json): run board.py init first
```

The edit command exits 1 and writes nothing. The project is not founded. Run `python scripts/foundry/founder.py init`. A manager who sees this stops and tells the user to run `/foundry-founder found`.

### The roadmap names a milestone or a decision the state lacks

```
! docs/ROADMAP.md's milestone tables name M4, which the state's milestones lack: run python scripts/foundry/board.py milestone sync.
! docs/ROADMAP.md names the open decision(s) D4, which the register lacks: run python scripts/foundry/board.py decide adopt D4.
```

The roadmap gained a row after the state was written. Run the command each warning gives:

```
python scripts/foundry/board.py milestone sync
python scripts/foundry/board.py decide adopt D4
```

```
milestone sync: added M4 from docs/ROADMAP.md (planned; M4 Sync: two devices agree)
D4 adopted from docs/ROADMAP.md (open; it waits on the user): Sync server (DATA-02)
```

`decide adopt` is refused (exit 2) when the register already has the id, or the roadmap's table does not name it. With a starter roadmap (first line `<!-- STARTER`) neither warning appears: its rows are examples.

### The roadmap was rewritten after the state had its rows

```
milestone sync: added M4 from docs/ROADMAP.md (planned; M4 Sync: two devices agree); refreshed from the roadmap: M2 title: 'Store: what the user makes is kept' -> 'Store: notes are kept'; M3 not in docs/ROADMAP.md: board.py milestone sync --prune removes the planned, untouched ones
```

`milestone sync` rewrites the title and lane of a planned milestone nothing has touched (no note, checkpoint, forced record, shift or log entry), and names the ones the roadmap no longer has. `milestone sync --prune` removes those:

```
milestone sync: nothing to add; the state has all 3 milestone(s) docs/ROADMAP.md names; removed M3 (planned, untouched, no longer in docs/ROADMAP.md)
```

A milestone that work has touched is left as it is. For a decision:

```
python scripts/foundry/board.py decide adopt D2 --refresh
python scripts/foundry/board.py decide withdraw D1 --note "the roadmap no longer names it"
```

```
D2 read again from docs/ROADMAP.md (open): Storage layout (DATA-01)
D1 withdrawn (adopted from docs/ROADMAP.md, which no longer names it)
```

`--refresh` reads an adopted entry again from its row. It is refused (exit 2) for an entry that was asked, adopted by a badge (`--by`), or answered or withdrawn through the register: a person settled that one. `decide withdraw` takes an adopted entry whose row is gone, answered or not.

### A roadmap row that was not read, or an id in two rows

```
! docs/ROADMAP.md: the decisions row(s) D5 open like a row and were not read (a missing cell, or a pipe inside a cell: write it another way); the tools do not know these decisions.
! docs/ROADMAP.md has more than one decision row for D4: the last one is read; give each its own id.
```

`flow.py selftest` fails on the same rows and names each by its line. Close every cell with a pipe, write a pipe inside a cell as `\|`, and give each row its own id.

### The register and the roadmap disagree

```
! The register and the roadmap disagree on whether a decision is answered: D2 (docs/ROADMAP.md: open; the register: answered). Record the answer (decide answer) or correct the roadmap's row.
```

An answer was recorded with `board.py decide answer`, and the roadmap's decisions table still says `Open` (or the other way round). The founder brings the roadmap's row into line: its **Where it stands** cell starts `**Decided:**` once the user has answered.

### "no gym yet"

```
[setup] no gym yet: the first grader sets up gym/ with the gym skill (lanes, preregs, series); lane checks are skipped
```

There is no gym folder, so no milestone can pass. Start one with `python scripts/foundry/gym_init.py init` ([gym.md](gym.md#starting-a-gym)).

### A linked worktree

```
refused: this is a linked worktree (~/myproject/.claude/worktrees/m1-builder), not the main checkout (~/myproject): board.py note would write docs/progress/state.json and docs/progress-map.html here, and a later commit could carry them. Only the main checkout's board.py writes the map. ...
```

Exit 3. The state and the map are written in the main checkout only. An employee reports with `office.py progress` and `office.py fail`, and reads with `board.py check --no-build`.

### "Now says the tree is at ... but HEAD is ..."

```
! Now says the tree is at ac9e22a but HEAD is 8ff7bc4; something was committed after the last update (.foundry/foundry.toml).
```

Code was committed after the state's `now.tree` was written. Update it at the block's end: `python scripts/foundry/board.py now --tree auto`.

### A milestone that will not go done

```
refused: M1 is not done: its lane G1 has VOID as its latest counted verdict (run 20261124-153129-0068), not PASS. A milestone is done only when its gym lane says PASS. ...
```

Exit 3. That is the rule working. See [gym.md](gym.md#what-each-verdict-word-means-for-the-map).

### A milestone's lane will not change

```
refused: M2 is judged on the lane G2, and --lane G1 would re-point it: --title and --lane are for a milestone the list does not have yet. To change an existing milestone's lane, record the user's override: --lane G1 --force --words "the user's own words"
```

Exit 3. A milestone's lane is what it is judged on, so pointing it at another lane (one that has passed, say) is the user's call. Ask, and record the words. `--title` on a milestone the list already has changes nothing, and the command says so.

## Counted runs and the sweep

### A dirty tree at a counted run

From the gym's runner:

```
refused: the tree is not clean (M docs/progress-map.html; M docs/progress/state.json; ...): commit or remove every change, tracked or not, then run again
```

From the sweep:

```
sweep: the main checkout (~/myproject) is not clean; nothing started:
?? stray.txt
```

A counted run samples the tree, so the tree must be exactly the commit the run names. Commit what belongs (the state and the map are the usual ones), remove what does not, and check that run folders and scratch files lie under a git-ignored folder (`out/`). Then run again. The sweep exits 4; the runner exits 2.

Untracked paths count. Crew worktrees that lie inside the main checkout (the default, `.claude/worktrees/`) show up as untracked unless the folder is git-ignored:

```
sweep: the main checkout (~/myproject) is not clean; nothing started:
?? .claude/worktrees/m1-builder/
```

`founder.py init` writes the ignore line for `git.worktrees`, and `founder.py doctor` makes a missing one a PROBLEM. In a project founded before that, run `founder.py init` again (it only adds what is missing) or add `/.claude/worktrees/` to `.gitignore` yourself, and commit it.

The sweep checks the tree again after every lane, and HEAD's reflog with it. A change during a lane stops it (exit 4), and that lane's row in `runs.tsv` carries the note `tree changed during this lane: ...`. The gym's runner checks after its collect: a counted run is published as VOID, with the lane's own word kept as `lane_verdict`, when the tree is not clean then, when git cannot say whether it is, or when HEAD or its reflog moved during the collect.

### The runner exits 3, or 130

Exit 3 from `gym/run.py` is not a verdict. The runner itself failed, and its traceback is on stderr, ending in `the runner failed; no verdict (...)`; or a lane, or code it calls, ended the process with `sys.exit` (whatever code it gave, 0 included). Never file it as a FAIL of the lane. Find the error (usually in the lane's own code), then run again. Exit 130 is an interrupt (Ctrl+C): no verdict either.

### The sweep exits 1

```
sweep: ended, exit 1: 2 of 2 lane(s) run: 0 gave a verdict, 2 gave no verdict (G1 exit 2, G2 exit 2)
```

Every lane ran, and at least one gave no verdict: its command ended with an exit code listed in `measure.no_verdict_exits` (default `[2, 3]`: the runner refused, or the runner failed). `sweep.py status` lists those lanes under `run, with no verdict`, and each lane's log says why. A lane with no verdict has no point in its series: fix the cause (a prereg that is still a template, a broken lane) and run it again.

### The sweep exits 6, or was interrupted

```
python scripts/foundry/sweep.py status --out out/sweeps/close-1
```

A row marked `not run (the queue: exit <n>): ...` is a lane the queue did not run: it refused the job, the wait ran out, it stopped at the prepare line, it could not start the shell, it ended the command at its limit, or it was stopped. The row ends with the queue's last line. The sweep stopped there with exit 6. That lane has no run and no verdict. Read `rq.py status`, fix the cause, and run the lanes left as a new sweep under a new `--out` (`--lanes "<the lanes left>"`).

A sweep that was stopped (Ctrl+C, TERM, HUP, BREAK) writes `ended <time> interrupted` into `source.txt` and exits 130, or 128 plus the signal's number. It ends the lane in flight, releases its seats and lifts its own freeze. If it says seats may still be held, the manager frees them with `rq.py force-release`.

```
sweep: a sweep is still running: MGR-1's, in out/sweeps/close-1 (sweep.lock in the office names ...
```

Exit 3. One sweep runs at a time, whoever queued it: the running sweep keeps `sweep.lock` in the office, and a second one is refused while the first still touches its `alive` file. A lock a killed sweep left behind goes stale and is written over.

The sweep also exits 3 in the middle of a run when the freeze it runs under is gone before a lane: `it was lifted (freeze.json is gone)`, or `it was replaced by one by ...`. Someone lifted or replaced the freeze under it. The lanes left are not run; find out who, then run them as a new sweep.

### `freeze off` is refused

```
refused: this freeze is a counted sweep's (by MGR-1-sweep since 15:17, limit 3.0 h (to 18:17): counted sweep), and the sweep may still be running: see it with `python ~/myproject/scripts/foundry/sweep.py status`. A sweep lifts its own freeze at its end; lifting it under a running sweep lets a commit into the checkout it measures. If the sweep is dead, lift it with: freeze off --force
```

Exit 3. A sweep turns the freeze on for its whole run and lifts it itself. Check the sweep first (`sweep.py status --out <its folder>`, and the session that started it). Only when it is dead:

```
python scripts/foundry/office.py freeze off --by "<the manager's line>" --force --note "the sweep's session died"
```

### A freeze by "unknown"

```
FREEZE by unknown: freeze.json cannot be read (JSONDecodeError: ...): the manager sets it again or lifts it
```

The office's `freeze.json` is damaged, or holds a time or a length that is not a sane one. A tool that cannot tell whether a freeze is on holds still, so this reads as a freeze. If no counted run is going, the manager removes it with `office.py freeze off --by "<the manager's line>"`.

### A graph edit or `gym_init.py` refused during a freeze

```
refused: graph confirm would change tracked files in the main checkout during a freeze (the manager's freeze by MGR-1 since 15:16, lane G1, limit 60 min (to 16:16): counted G1); nothing written. Wait until the counted run ends, its records are committed and the freeze is lifted (see it with `python ~/myproject/scripts/foundry/office.py freeze show`).
```

Exit 3. `flow.py graph seed`, `link`, `unlink`, `confirm`, `node` and `undo`, and `gym_init.py init` and `lane add`, write tracked files. In the main checkout they are refused while the manager's freeze is on or a counted run or sweep holds or waits for the shared resource. Unlike a `board.py` edit, the command is not held: run it again after the freeze. `flow.py graph show`, `trace` and `verify`, and `gym_init.py check`, only read and always run. In a worktree nothing is frozen.

### The prereg is still a template

```
refused: ~/myproject/gym/prereg/G1.json is still a template: the grader fills it, sets "status" to "registered" and commits it before the first counted run
```

The independent grader has not written the measure yet. That comes before any counted run ([gym.md](gym.md#the-order-of-work-between-builder-and-grader)).

### A sweep's folder exists, or is in the wrong place

```
sweep: --out out/sweeps/try1 exists already; a sweep's folder is never used twice: give a new name
sweep: --out docs/sweep1 is not under a git-ignored folder (out/): the sweep's own files would dirty the tree it counts and stop it
```

Exit 2. Give a new name under `out/`. A `--check-only` run uses its folder up as well.

## Hand-in PROBLEMs

`office.py handin` prints `NOT READY` and exits 1 while a PROBLEM stands. Fix each and run it again. A warning does not block; say in the report what it means for the merge.

| PROBLEM (in short) | Meaning | What to do |
|---|---|---|
| `changed file(s) outside the files your badge owns` | A commit touches a file the brief did not give you | Take the file out of the commit, or ask the manager to widen the badge (`office.py amend --add-files`). If the branch was cut from a branch other than the main one, pass `--base <that branch>` |
| `the tree is not clean` | Uncommitted or untracked files in the worktree | Commit your files or remove the leftovers. The manager merges commits, not a working tree. An untracked report passed with `--file` does not count |
| `your branch changes the measure's files` | You changed a path under `measure.grader_owned` and you are not a grader | Take the change out. Send the grader a patch or a written request |
| `your branch changes a run's records` | You changed a path under `measure.records` and you are neither a grader nor the manager | Take the change out. If a counted run wrote them in your worktree, tell the manager, who commits them |
| `your branch changes the road graph` | You changed `road.graph.json` or `road.edits.jsonl` | Take the change out. Ask the manager for the edit (`flow.py graph ...`) |
| `the repo's own git config sets user.name` | A test or script ran `git config` in a worktree, which rewrites every checkout's identity | Tell the manager. Do not unset it unless you set it. Give a scratch identity by `GIT_AUTHOR_*` and `GIT_COMMITTER_*` environment variables |
| `commit(s) lack the trailer line` | Your title is flagged, and a commit's message does not end with the profile's trailer | Reword each commit on your own branch so its message ends with the line. Never a commit already merged |
| `the project's hand-in check ... exited N` | The command in `measure.handin_check` failed | Fix what it names and run `handin` again |
| `commit X does not exist in this repo` | A sha passed with `--commits` is wrong or ambiguous | Read the sha from the commit's own output |

The last three name each path with where it was seen: `(in a commit)`, or `(the branch's tree differs from main)`. The second means the path is in no commit that was checked: a merge that kept one side (`git merge -s ours`), or a commit left out of `--commits`. `git diff --name-only main HEAD` lists it. Merging the branch would put your copy in place of the main branch's, so bring the file back to the base's copy.

`handin` itself is refused (exit 3) when run outside a git checkout, when `--file` names no file, or when `--base` names no branch.

The three walls are always checked against the profile's main branch as well as `--base`. So `--base <another branch>` brings a warning (`--base is side, not the main branch main: your own files were checked against side; the road graph, the measure's files and the run records were checked against both side and main`), and a walled change made on that other branch is still a PROBLEM. `cannot check the walls: no main here` is a PROBLEM too: run `handin` in a checkout of the project's own repository.

Common warnings: `main has N commit(s) your branch lacks` (say so in the report; rebase only if the brief allows it); `no commit of yours ... past main` (a report-only job names its report file in the clock-out note); `the project's hand-in check ... was not run` (run it yourself if your change needs it, and give its result).

## The hooks' refusals

```
Blocked: docs/flow/road.graph.json and docs/flow/road.edits.jsonl are written only by `scripts/foundry/flow.py graph ...` (link, unlink, confirm, node, undo), which takes the manager's badge line (--by "FB1 ID:MGR-...") and logs the edit. ...
```

`graph_readonly.py` stopped a direct write of the road graph: a write that names one of its two files, or a shell command that removes, moves or replaces them through their folder (`rm -rf docs/flow`, a copy into it, `git checkout .`, `git restore .`, `git clean`, `git stash push` with a pathspec that covers it). A command handed to a shell by name (`bash -c "..."`) is read too. It refuses everyone, the manager too. The manager and the founder change the graph with `flow.py graph ...`; anyone else asks the manager. If the command only read the file and was refused anyway, stop and tell the manager: the manager decides whether it was a false positive.

```
Blocked: `python -` reads the script from stdin, which can hang the call in this shell. Write the script to a file (a scratch folder is fine) and run it by path: `<python> <file>`.
```

`no_python_stdin.py` stopped a python fed on stdin. Write the script to a file and run the file. If a note or a report was refused, it quoted a blocked command literally: describe the command in words.

A message `... hook inactive: interpreter ... is missing` means the settings block names an interpreter the hook shell cannot find. The call ran; the hook did not. Put the right interpreter in `.claude/settings.json`. Details: [hooks.md](hooks.md).

## The charts

```
plan_flow: new would write into the main checkout (~/myproject/docs/flow), which takes the manager's badge: --by "<FB1 line>" ... Anyone else: run it from your own worktree.
```

Exit 2. In the main checkout, `plan_flow.py new` and `build` take the manager's badge or the founder's. An employee runs them in its own worktree, or builds with `--out` pointing outside the main checkout.

```
plan_flow: new would change the main checkout during a freeze (the manager's freeze by MGR-1 since 15:16, lane G1, limit 60 min (to 16:16): counted G1). Wait until the counted run ends, its records are committed and the freeze is lifted.
```

Exit 3, the same code `flow.py graph` and `gym_init.py` give for a freeze. During a freeze even the manager's `new` is refused in the main checkout. Make the plan after the freeze, or in a worktree.

```
PROBLEM A2: its anchor src/app.py is gone
```

`plan_flow.py selftest`: a file or a text the plan rests on moved. Update the plan file, or report the line to the manager.

```
FAIL M2 is in ROADMAP.md's milestone tables but not in the map's milestones
```

`flow.py selftest`: the roadmap names a milestone the state's `milestones` list lacks. Add it, with the roadmap's title and lane: `python scripts/foundry/board.py milestone sync`.

```
NOTE the road graph is not seeded yet, so its links are guessed from the roadmap's prose
```

Not a problem. The founder or the manager seeds it once: `flow.py graph seed --by "<line>"`.

A `flow.py graph` edit with a crew badge is refused: only the manager on the clock and the founder edit the graph. During a freeze it is refused for them too ([above](#a-graph-edit-or-gym_initpy-refused-during-a-freeze)). When `flow.py graph verify` or the page says the graph was changed by hand, stop editing, find who changed the file (`git log -- docs/flow`), and ask the user to restore the last good version themselves.

## The profile does not parse

```
foundry: the profile cannot be read: ~/myproject/.foundry/foundry.toml: Cannot declare ('models',) twice (at line 4, column 8)
foundry: fix the file (`foundry_profile.py where` checks it); nothing was done
```

Exit 2, on stderr, from every tool: `office.py`, `board.py`, `rq.py`, `flow.py`, `gym_init.py` and the rest. A profile that cannot be read is never replaced by the defaults in silence, and never ends in a traceback. A tool running on the defaults would look for the office in another folder, lose the shared resource and with it the counted-run freeze, and forget which files only a grader may change. So it stops, and nothing is done.

Two commands still run, to help you find the line:

```
python scripts/foundry/foundry_profile.py where
```

```
checkout       ~/myproject
main checkout  ~/myproject
profile        none (defaults)
PROBLEM        ~/myproject/.foundry/foundry.toml: Cannot declare ('models',) twice (at line 4, column 8)
```

`where` exits 1 when the file has a problem, and `founder.py doctor` prints `PROBLEM profile does not parse: ...`. Fix the line it names, then run `where` again. `foundry_profile.py show` also runs: it prints the defaults, names each problem on stderr (`PROBLEM the profile cannot be read, so these are the defaults: ...`) and exits 1.

The problems it names, besides a TOML error:

```
foundry: the profile cannot be read: ~/myproject/.foundry/foundry.toml: `paths` must be a table ([paths]), not str
foundry: the profile cannot be read: ~/myproject/.foundry/foundry.toml: `limits.usage_stop` must be a number, not str
foundry: the profile cannot be read: ~/myproject/.foundry/foundry.toml: `resource.seats` must be a list, not str
foundry: the profile cannot be read: ~/myproject/.foundry/foundry.toml: not UTF-8 text (invalid start byte at byte 7277); save it as UTF-8
foundry: the profile cannot be read: ~/myproject/nosuch.toml: FOUNDRY_PROFILE names no file
```

A key of the wrong kind: `paths = "x"` where the `[paths]` table belongs, a number in quotes, a list written as text. A file saved in another encoding. A `FOUNDRY_PROFILE` variable that points at a file that is not there.

The error above is a common one: a table may be declared only once in the file. In the starter profile the `[models]` header is commented out, and `[hooks]` is declared near the end. Uncomment the `[models]` header that is there instead of adding a second one, and add `hooks` lines under the `[hooks]` header that is there. Run `where` after every edit of the profile.

An agent that sees this message stops and tells the user: the profile is the founder's file.

## Doctor's PROBLEM lines

`founder.py doctor` exits 1 when any of these printed.

| Line | Meaning | What to do |
|---|---|---|
| `python X.Y.Z ...: 3.11 or newer is needed (tomllib)` | The interpreter is too old | Run the tools with Python 3.11 or newer; set `commands.python` in the profile |
| `profile does not parse: ...` | A TOML error, a file that is not UTF-8, a key of the wrong kind, or a `FOUNDRY_PROFILE` that names no file. Every other tool stops with exit 2 until it is fixed | Fix the line; see above |
| `tool missing beside founder.py: X` / `tool missing in paths.tools: X` | The install is not whole | Run `install.py --project <this project>` again |
| `skill X is not installed` | Not in `.claude/skills/` of the project, nor in `~/.claude/skills/` | Run `install.py` (with `--skills user` for one copy for every project) |
| `paths.office (out/foundry) is not git-ignored` | Every punch would dirty the tree | Add `/out/foundry/` to `.gitignore`. `founder.py init` does it |
| `paths.flow_out (out/flow) is not git-ignored` | Every build would dirty the tree | Add `/out/flow/` to `.gitignore` |
| `git.worktrees (.claude/worktrees) is not git-ignored` | The first crew worktree would make the main checkout read as dirty to a counted run | Run `founder.py init` again (it adds the line), or add `/.claude/worktrees/` to `.gitignore` |
| `state docs/progress/state.json is missing` | Not founded yet | `founder.py init` (it runs `board.py init`) |
| `state ... is not valid JSON` | The file was damaged by a hand edit | Restore it from git; edit only through `board.py` |
| `roadmap docs/ROADMAP.md is missing` | Not founded yet | `founder.py init` writes a starter |
| `selftest X: ...` (with `--selftest`) | A tool's own selftest failed | Read the line; reinstall if a file was changed |

Notes are not problems. `roadmap ... is still the starter` stays until the founder writes the real roadmap. `no shared resource named` is right for a project that shares nothing. `hook ... is in .claude/hooks but .claude/settings.json does not run it` means the hook's file was copied and not switched on.

## FAQ

**Does it need the desktop app?**
The tools do not: they are plain Python with the standard library and run anywhere Python 3.11 and git do. The manager's routine does: starting sessions, bench sessions, timers and messages between sessions are described for the Claude Code desktop app (the manager skill's `references/app.md`, and the `foundry-bench` skill). In another harness those two files need their own version.

**Can it run with one agent?**
The tools do not require a crew. One session can keep the state, the map, the roadmap, the journal and the charts. What one session cannot be is its own grader: `office.py hire` refuses a grader as a temp, and `board.py checkpoint` refuses a grader who is the builder. So a milestone can reach a counted PASS only with a second, independent session for the measure. A manager can hire every other role as a temp (a subagent in its own turn).

**What does it cost in usage?**
No tool reads your plan's usage. The manager reads it in the app and records it with `board.py usage <percent>`. At the stop (`limits.usage_stop`, default 80, or the state's `usage.stop`) it starts no new work and asks you. As a guide from the skills: more crew costs usage roughly in proportion; an idle session costs almost nothing; a waiting session that wakes every few minutes costs a lot; a manager turn that only reports "no change" still costs a full context. Keep `crew_max` low on a first day.

**Can the crew push?**
Not by default. `git.push = false` makes every brief say "no push". With `git.push = true` the brief says "push only your own branch, never the main branch". No tool enforces either: it is a rule the skills follow, and your harness permissions are the real gate.

**How do I change the slots?**
Before founding, set `[slots]` in the profile; `board.py init` writes them into the state. After that the state's `rota.slots` wins, and no command rewrites the slot list. Change it by script through `board.write_state` ([state.md](state.md#the-state-file)), at a slot boundary, then run `python scripts/foundry/board.py rota slots` to rewrite the review windows. `office.py timers init` writes `manager-timers.json` only when it is missing, so delete the old file first and run it again; the manager then replaces its session timers from the new list.

**How do I see what is in force?**
`python scripts/foundry/foundry_profile.py show` for the profile, `python scripts/foundry/office.py roster` for the crew, `python scripts/foundry/board.py check --no-build` for the project. None of the three writes anything.

**How do I upgrade?**
Pull the Foundry repository and run `install.py --project <dir> --check`. Files that are the same are skipped; a file you changed is kept and listed. `--force` replaces it and keeps the old one as `<name>.bak-<date>`. Do it at a slot boundary, then run `founder.py doctor`.

**How do I uninstall?**
There is no uninstall command; the installer only copied files. Remove what it copied: the tools folder (`scripts/foundry/`, templates included), the six skill folders under `.claude/skills/` (`foundry-founder`, `foundry-manager`, `foundry-employee`, `foundry-flow`, `foundry-bench`, `gym`), and the two hook files under `.claude/hooks/` together with their block in `.claude/settings.json`. Then decide what to keep of what the project made with it: `.foundry/`, the office (`out/foundry/`, git-ignored), the built pages (`out/flow/`), and the checked-in files (`docs/ROADMAP.md`, `docs/progress/`, `docs/progress-map.html`, `docs/flow/`, `gym/`). Those are the project's own record and nothing depends on the tools to read them.
