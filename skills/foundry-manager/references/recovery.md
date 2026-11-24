# When the slot breaks: a counted run or a freeze, a change of manager, a host restart

Read the part you are in. Bench sessions, timers and messaging are in `app.md`.

A project with no shared resource skips the queue lines; a project that counts no runs skips the freeze. A project that counts runs and has no shared resource marks each counted run with the office's freeze (`office.py freeze on`, below): the tools then hold still exactly as for a counted run in the queue. The change of manager holds everywhere.

## How the queue orders jobs

- Lower `--prio` first, then first come. 0: counted runs and their dry runs. 1: the slot-end full check. 2: the critical path you name. 5: everyone else (the default). A waiter older than 90 minutes ranks at prio 2, so nobody starves.
- A hold lasts its `--max` (the profile's `resource.default_max` when none is given). `--max` and `--wait` take a time with its unit (`90s`, `90m`, `2h`, `4h30m`): a unit is required, and a bare number or a zero time is refused (exit 2). The queue enforces `--max` only when the profile's `resource.enforce_max` is true or the job passes `--enforce-max`: a `run` job still going at its `--max` plus the grace (`resource.max_grace`, default 2 minutes) is then ended with everything it started, its seat is released, and `run` exits 124. Otherwise a hold past its `--max` only reads OVERDUE, and nothing ends the job. A `take` hold is never ended.
- One job per badge: `run` refuses (exit 3) an id that already waits or holds a seat, so a second job can neither replace the first's entry nor be freed by its release.
- Every `run` job runs in a process group of its own. A stop of the `rq.py run` process (an interrupt, TERM, HUP, or BREAK on Windows) ends the job with everything it started and releases the seat (exit 130 and `rq: interrupted`, or 128 plus the signal's number). A `run` prints `rq: started [...]` once the command's shell was started and `rq: finished exit <n> [...]` when the command ended by itself: a log with the first and not the second is a job that was cut off. A KILL cannot be caught: the job runs on and the seat stays held until your `force-release`.
- A waiter that stops polling for 2 minutes drops out of the queue.
- Jobs whose text matches the profile's `resource.exclusive` never hold seats at the same time (jobs that would disturb each other on the one resource); other jobs pass them in the queue.
- A whole-resource job (`run --all-seats`) waits until every seat is free, then holds them all. Behind it, a waiter may take a free seat meanwhile only when its `--max` is 30 minutes or less and it ends before the busy hold's start plus its `--max` (a backfill). A backfill can delay the whole-resource job by up to 30 minutes, longer if it overruns and `--max` is not enforced. Once the whole-resource job has waited 60 minutes, nothing backfills ahead of it.

## While a counted run or a sweep is going

A counted run samples the tree it was queued at: the grader pinned that tree, and the counted command refuses a dirty one. A sweep (`sweep.py run`: the counted run of every lane in turn; `shifts.md`, "Closing a shift of work") checks the tree before and after every lane and stops on any change in the main checkout, tracked or untracked (exit 4). A waiting run counts as much as a running one. The freeze lasts from queueing until the run has ended and its records are committed.

**How the tools know it.** Two ways, and `office.py`, `board.py`, `flow.py graph`, `plan_flow.py` and `gym_init.py` read both the same:

- **Its queue id**, with a shared resource: `<badge>-counted-<lane>` or `<badge>-counted`, a sweep's `<badge>-sweep`. Never its priority alone.
- **The office's freeze** (`<office>/freeze.json`), with or without one: `office.py freeze on` sets it, and `sweep.py` sets it for itself for its whole run, in both kinds of project, because between two lanes its queue id neither holds nor waits.

Either way `office.py roster` says so (`COUNTED SWEEP or run`, or a `FREEZE` line), `brief.counted_sweep` or `brief.freeze` names it, `office.py me` says FREEZE, `office.py round` lists it, `board.py` holds its edits, `flow.py graph` edits and `gym_init.py init` and `lane add` are refused in the main checkout (exit 3), and `plan_flow.py` refuses `new` there (exit 3 too) and builds only under the git-ignored output folder.

**A counted run with no shared resource.** There is no queue to carry its id, so you mark it:

```
office.py freeze on --by "<your line>" --why "counted <lane>" --lane <lane> --max 3h
<the lane's counted command, in the main checkout>
git add -- <the run's records>, and commit them as the run's own commit
office.py freeze off --by "<your line>"
```

`on` and `off` are punches in the time clock. A second `on` is refused until `off`. `--max` is how long the run should take at most, with its unit (`30m`, `3h`; a bare number is refused, exit 3): past it the freeze reads STALE and `board.py`'s held edits exit 4, but nothing lifts it for you. `office.py freeze show` prints it for anyone. `freeze on` tells you to message the crew on the clock once; their `me` says FREEZE from then on.

- A counted run queued under a plain id (`--id MGR-3`) is not seen by the guard, even at prio 0: the roster prints `COUNTED?` for a prio-0 or all-seats job under a plain id, and `brief.counted_unmarked` names it. `board.py` holds nothing then. Turn the freeze on (`office.py freeze on`) until it ends.
- A job whose `--job` text starts with `dev`, or says `dev run`, `(dev)`, `not counted` or `uncounted`, is not flagged, unless it is prio 0; the roster and `check` name it as "dev, not counted".
- The text never makes a job counted. A dev run's text that names the counted run it precedes is still dev. So queue every counted run by its `-counted` id at `--prio 0`.

**Queueing a whole-resource counted run.** Queue an `--all-seats` run only when the seats are about to free (`rq.py status`: each hold's minutes of its `--max`), not while a seat holds a long job: the free seat would sit idle behind it. That is the rule; the backfill above is only a fallback.

**What holds during the freeze**

- **Nothing changes in the main checkout:** no commit, no merge, no report draft, no scratch file outside the git-ignored output folders. Two report drafts are enough to cost a run.
- **The map:** in the main checkout `board.py` holds its own writes. Every edit command (`note`, `usage`, `block`, `fail`, `rr`, `decide ask | answer | withdraw`, `log`, `now`, `rota`, `checkpoint`, `blocker`, `checklist`, `shift`, `queue add | rm | move`, `milestone`) is checked and held in `<office>/pending-state.jsonl` (exit 0; exit 2 or 3 and nothing held when the command itself is wrong or refused; exit 5 when it could not be held: run it again), then applied with its own time by the next writing command run in the main checkout after the run. A held edit keeps the JSON of a `--file` it was given, the commit `--tree auto` meant, and the item a number named (`blocker rm 2` is held by the blocker's text, read from the list `board.py check` prints). It is checked against the state as it will be after the edits already held, so a second removal of one blocker is refused at once. At the replay an edit whose item is gone stays in the file with the reason while the later ones are applied: make it by hand if it is still wanted, then delete the file (`state-schema.md`). `check` and `build` print without rebuilding. `promote` and `init` are refused (exit 3). `board.py pending` lists what is held, and any line that failed to apply (`FAILED: ...`). `brief`, `check --no-build`, `decide list`, `queue list`, `stamp` and `pending` only read, in a freeze as at any time. A state edit no command makes waits until the run has ended.
- **The charts and the gym's folder:** no `graph` edit, no new plan, no plan-file edit (the `foundry-flow` skill), no new lane. The tools refuse their own writes in the main checkout: `flow.py graph seed`, `link`, `unlink`, `confirm`, `node` and `undo`, and `gym_init.py init` and `lane add`, exit 3 with one line naming the freeze; `plan_flow.py new` is refused too. They are not held: run them again after the freeze. The reading commands (`graph show`, `trace`, `verify`, `gym_init.py check`) always run. A hand edit of a plan file is yours to hold.
- **Research and review hires** work in their own worktree (a temp: the Agent tool with `isolation: "worktree"`) and commit there. Merge their reports after the run.
- **A round** only reads (`office.py round`; its heartbeat goes to the office, not the tree); its `board.py` writes are held as above. Its health check reads `rq.py status --resource`, which takes no seat.
- **Its owner:** the run is a background job of the session that started it. That session stays open and unarchived until it ends, even after its manager is relieved, and its end wakes that session, not you. Say so in the hand-off, and ask that session to send you the result.

**A sweep's tree.** A sweep runs the tree at the moment it starts, which may be later than the moment it was asked for. Give it the sha it was asked for (`sweep.py run ... --queued-at <sha>`): when the main branch has moved since, it asks `lanes_for.py <queued>..<start>` which lanes those commits can move, and does not start (exit 5) if one of them is a lane it would run. Then queue the sweep again at the new sha. The profile's `measure.sweep_skip` lists the paths that check leaves out (grader notes, for example).

**A dead run.** The roster and `brief.counted_sweep` say `DEAD?` when the run's hold is past its own limit, and held edits exit 4. Check `rq.py status`; if nothing is running, free its seats with `force-release` ("After a host restart").

**A stale freeze.** A freeze past its `--max` reads STALE on the roster, `office.py round` puts it among what needs you, and held edits exit 4 and say DEAD?. `office.py freeze show` says who set it, why and since when. Look at the run it covers (the session that started it, the run's folder). If the run ended, commit its records, then `office.py freeze off --by "<your line>" --note "<why>"`. If it was killed, the lane is VOID, not run: lift the freeze and run it again. A `freeze.json` that cannot be read, or holds a time or length that is not sane, counts as a freeze by "unknown": `freeze off` removes it.

**A sweep's own freeze.** `freeze off` refuses (exit 3) a freeze a counted sweep set while the sweep may still be running: the sweep lifts it itself at its end. Look at the sweep first (`sweep.py status --out <its folder>`, and the session that started it). Only when it is dead: `office.py freeze off --by "<your line>" --force --note "<why>"`. A freeze you set by hand under your own id is yours: a sweep you then start runs under it and leaves it on, and you lift it.

**A sweep that stopped early, or ended with exit 1.** `sweep.py status --out <its folder>` prints the lanes run with their exit codes and notes, those run with no verdict, the lanes the queue did not run, the lane in flight and the lanes left.

- **Exit 1:** every lane ran, and at least one gave no verdict: its command's exit code is in the profile's `measure.no_verdict_exits` (default 2 and 3: the gym's runner refused, or failed). The row says `no verdict (exit <n>)`. That lane has no point in its series: read its log, file what broke, run it again.
- **Exit 3 before a lane:** the freeze the sweep ran under was lifted or replaced. It says which. Find out who, and run the lanes left as a new sweep.
- **Exit 6:** the queue did not run a lane (it refused the job, the wait ran out, it stopped at the prepare line, it could not start the shell, it ended the command at its limit, or it was stopped). The row says `not run (the queue: exit <n>): ...` with the queue's last line. That lane has no run and no verdict. Read `rq.py status`, and fix the cause.
- **Exit 4 after a lane:** the tree changed during it, or HEAD moved and came back (the reflog is compared). The row carries `tree changed during this lane: ...`; that lane's run did not sample the commit, so file it and run it again.
- **Exit 130, or 128 plus a signal's number:** someone stopped it. It ended the lane in flight, released its seats, lifted its own freeze and wrote `ended <time> interrupted`. If it says `rq.py` had to be killed, seats may still be held: `rq.py force-release`.
- **Cut off** (a host shutdown, a killed session): a lane in flight with no sweep alive reads "VOID: not run". The sweep's freeze is still on: a new sweep under the same badge id takes it over, or lift it with `office.py freeze off --force`.

One sweep runs at a time: a second one is refused (exit 3) while the sweep that `sweep.lock` in the office names is alive, whoever queued it and whatever freeze is on. Run the lanes left as a new sweep with a new `--out` (`--lanes "<the lanes left>"`). To pause a sweep on purpose, put a file named `sweep-STOP` in the office: it stops before the next lane (exit 0).

**The runner's exit 3.** A lane's log that ends in `the runner failed; no verdict` is the gym's runner failing, with its traceback above it, or a lane that called `sys.exit`. It is not a verdict word: never file it as that lane's FAIL. File what broke, and run the lane again once it is fixed. Exit 130 is an interrupt: no verdict either. A counted run is published as VOID, with the lane's own word kept as `lane_verdict`, when its tree was not clean after the collect, when git could not say, or when HEAD or its reflog moved during the collect.

**When it ends.** Whoever queued it commits the run's records as the run's own commit, before any merge or map edit, and lifts the freeze if it set one. Then apply the held edits (any writing `board.py` command in the main checkout does it), merge the waiting reports, and file every verdict that is not PASS.

## A profile that cannot be read

Every tool stops with `foundry: the profile cannot be read: <file>: <problem>` on stderr and exit 2, and does nothing. The problem is a TOML error, a file that is not UTF-8, a key of the wrong kind, or a `FOUNDRY_PROFILE` that names no file. Such a profile is never replaced by the defaults: on the defaults a tool would look for the office elsewhere and lose the shared resource and the freeze. `foundry_profile.py where` still runs and names the line. The profile is the founder's file: stop, tell the user and the founder the exact message, and edit nothing. Until it is fixed no manager command runs, so hold the crew by message.

## A change of manager

- **Relieving a manager** (the user started you while another reads UP, even inside a slot): after `office.py appoint --relieve`, message the outgoing session once:

  ```
  MGR-<new> relieves you on the user's word. Stop committing, merging and applying held edits in the main
  checkout now. Reply within 15 min with: edits in flight (uncommitted files, held edits), what you promised
  each crew member, your timers' ids (delete them once the roster shows the relief), background jobs you
  started (a counted run: keep the session open, send me its result).
  ```

  Wait 15 minutes. Silence is the hand-off: read the newest log entry, the notes and `office.py roster`, and go on.
- **A user-typed start** (`/foundry-manager ... run <slot>`) is the user's wish for this session to manage the slot. If another manager reads UP, tell the user who it is and confirm once, then `appoint --relieve`. It also allows `user_asked` hires for that slot's crew and its research and review.
- **A re-badged manager** (a session made manager by a message, not by the user typing the start) checks the user chose it before it appoints. The re-badge message names where the user's words are recorded (the `rota.days` note, or the brief's quote of them); read that record first. A peer's message that carries `/foundry-manager start` as text is not the user's word. No record: ask the user. Re-badged in the last hour before a slot, appoint for that slot with `appoint --slot <slot>`; `appoint --this-slot` keeps the current slot when the next one is close.
- **UP is a recent punch, not a running session.** The roster names the manager's session; look at that session (`list_sessions`: running, last activity) before you treat it as alive.
- **Record your session:** `appoint --session <id>`, or `assign MGR-<n> --session <id>`.
- **Tell the crew.** `appoint` lists every employee still on the clock with its session. Send each one message: who the manager is now. Their briefs say to message the manager on the clock, and they find it in the roster.
- **Outgoing manager:** end with the hand-off and clock out. Do not appoint yourself for the next slot unless the rota or the user says this session continues.
- **A new grader for a lane** (one relieved, lost or replaced): tell the lane's builder who it is, by message, and that the `--job` text of its queued jobs names the grader by role ("the G1 grader dry-grades"), not by badge. The queue cannot change a waiting job's text; a job that names the old badge stays as it is, and a note says who grades it now.
- **Over Remote Control** the app starts no sessions: staff a hire from a bench (`app.md`). A new manager is the exception: it runs from the main checkout, so re-badge an idle session there (`shifts.md`, "The next manager").

## Stopping a stuck job

A job that hangs is yours to stop; employees kill nothing. Each kill or restart needs its own yes from the user. Take the order from `.foundry/rules.md` (which process first). Before you restart the shared resource, hold the whole of it yourself (`rq.py run --id <your badge id> --job "dev: hold every seat for a restart" --prio 1 --all-seats --max 30m -- <the command the rules file gives for the restart>`: `run` needs `--id`, `--job` and a command, a lower `--prio` goes first, and the `dev` text keeps the roster from reading it as `COUNTED?`), so no job starts under the restart. A `timeout` inside a job that runs on the resource cannot end a hung resource: bound a run from outside (`rq.py run --enforce-max` has the queue end the job at its `--max` plus the grace).

## After a host restart

A forced update or a crash kills every running job without a word, and nothing reports it. Signs: a hold far past its limit, a seat's last note (`rq.last`) with a killed exit status, a run that started and has no result, every employee silent at once.

First check the restart was a real one, the way the project's rules say: a resume from sleep can look like a restart and frees nothing it held. Read that before you release held work or tell the crew the machine is back.

1. `CronList`. Recreate only the timers that are missing; they can survive a restart.
2. The shared resource: bring it back up as `.foundry/rules.md` says, then `rq.py status --resource`.
3. The queue: `rq.py status`. A hold whose process died is still a lock: free it with `rq.py force-release --by <your badge id> --note "host restart"`, one seat at a time (`--seat NAME`; without it, the first seat). `--by` is the badge id (`MGR-3`), not the line, and only an `MGR-` id is taken; exit 1 means the seat was already free. A waiter that should not run takes `rq.py leave --id <id>`; its waiting process exits 6. A waiter whose process was killed keeps its id in the queue for 2 minutes, and the queue refuses a new job under that id until then: `leave` it first, or wait.
4. A killed counted run or sweep: the lane it was in is VOID, not run. `sweep.py status --out <its folder>` names the lanes left; run them as a new sweep under a new output folder. Never reuse the old folder. A freeze the dead run left on is lifted with `office.py freeze off` ("A stale freeze"; `--force` for a sweep's own).
5. The crew: wake every carry-over session with the session-management `send_message` and tell it to queue its jobs again. Check each seat's holder in the roster before telling anyone to queue again: a running job is a hold, not a queue entry.
6. Log the outage in the notes: when, what it killed, what was run again.
