# When the slot breaks: a counted run, a change of manager, a host restart

Read the part you are in. Bench sessions, timers and messaging are in `app.md`.

A project with no shared resource skips the queue lines; a project that counts no runs skips the freeze. A project that counts runs and has no shared resource keeps the freeze by hand: no tool sees the run, so `board.py` holds nothing, the roster and `office.py me` say nothing, and you tell every employee on the clock when the run starts and when its records are committed. The change of manager holds everywhere.

## How the queue orders jobs

- Lower `--prio` first, then first come. 0: counted runs and their dry runs. 1: the slot-end full check. 2: the critical path you name. 5: everyone else (the default). A waiter older than 90 minutes ranks at prio 2, so nobody starves.
- A hold lasts its `--max` (the profile's `resource.default_max` when none is given). `--max` needs a unit (`90m`, `2h`, `4h30m`); a bare number is seconds. The queue does not enforce it: past it the hold reads OVERDUE, and nothing ends the job.
- One job per badge: `run` refuses (exit 3) an id that already waits or holds a seat, so a second job can neither replace the first's entry nor be freed by its release.
- A waiter that stops polling for 2 minutes drops out of the queue.
- Jobs whose text matches the profile's `resource.exclusive` never hold seats at the same time (jobs that would disturb each other on the one resource); other jobs pass them in the queue.
- A whole-resource job (`run --all-seats`) waits until every seat is free, then holds them all. Behind it, a waiter may take a free seat meanwhile only when its `--max` is 30 minutes or less and it ends before the busy hold's start plus its `--max` (a backfill). Because `--max` is not enforced, a backfill can delay the whole-resource job by up to 30 minutes, longer if it overruns. Once the whole-resource job has waited 60 minutes, nothing backfills ahead of it.

## While a counted run or a sweep is in the queue

A counted run samples the tree it was queued at: the grader pinned that tree, and the counted command refuses a dirty one. A sweep (the profile's `measure.sweep`, every lane in turn) checks the tree before every lane and stops on any change in the main checkout, tracked or untracked. A waiting run counts as much as a running one. The freeze lasts from queueing until the run has ended and its records are committed.

**How the tools know it.** `office.py` and `board.py` know a counted run by its queue id only (`<badge>-counted-<lane>` or `<badge>-counted`, a sweep's `<badge>-sweep`): `office.py roster` prints `COUNTED SWEEP or run`, `brief.counted_sweep` names it, `office.py me` says FREEZE, and `board.py` holds its edits. `plan_flow.py` also treats any prio-0 job as one. The guard reads the resource queue, so a project with no shared resource has none of this: its freeze is kept by hand.

- A counted run queued under a plain id (`--id MGR-3`) is not seen by the guard, even at prio 0: the roster prints `COUNTED?` for a prio-0 or all-seats job under a plain id, and `brief.counted_unmarked` names it. `board.py` holds nothing then. Freeze main by hand until it ends.
- A job whose `--job` text starts with `dev`, or says `dev run`, `(dev)`, `not counted` or `uncounted`, is not flagged, unless it is prio 0; the roster and `check` name it as "dev, not counted".
- The text never makes a job counted. A dev run's text that names the counted run it precedes is still dev. So queue every counted run by its `-counted` id at `--prio 0`.

**Queueing a whole-resource counted run.** Queue an `--all-seats` run only when the seats are about to free (`rq.py status`: each hold's minutes of its `--max`), not while a seat holds a long job: the free seat would sit idle behind it. That is the rule; the backfill above is only a fallback.

**What holds during the freeze**

- **Nothing changes in the main checkout:** no commit, no merge, no report draft, no scratch file outside the git-ignored output folders. Two report drafts are enough to cost a run.
- **The map:** in the main checkout `board.py` holds its own writes. `note`, `usage`, `block`, `fail`, `rr` and `decide ask | answer | withdraw` are checked and held in `<office>/pending-state.jsonl` (exit 0; exit 2 and nothing held when the command itself is wrong; exit 5 when it could not be held: run it again), then applied with their own times by the next writing command run in the main checkout after the run. `check` and `build` print without rebuilding. `promote` and `init` are refused (exit 3). `board.py pending` lists what is held, and any line that failed to apply. `brief`, `check --no-build`, `decide list`, `stamp` and `pending` only read, in a freeze as at any time. A larger state edit waits until the run has ended; if it must be a script, the script takes its time from `board.py stamp` and names no next manager.
- **The charts:** no `graph` edit, no new plan, no plan-file edit (the `foundry-flow` skill).
- **Research and review hires** work in their own worktree (a temp: the Agent tool with `isolation: "worktree"`) and commit there. Merge their reports after the run.
- **A round** only reads (`roster`, `brief`); its writes are held as above. Its health check reads `rq.py status --resource`, which takes no seat.
- **Its owner:** the run is a background job of the session that started it. That session stays open and unarchived until it ends, even after its manager is relieved, and its end wakes that session, not you. Say so in the hand-off, and ask that session to send you the result.

**A sweep's tree.** A sweep runs the tree at the moment it starts, which may be later than the moment it was queued. If commits landed in between, ask whether they can move one of its lanes: `<py> <tools>/lanes_for.py <queued sha>..<now>` lists the lanes a range touches. If they can, queue the sweep again at the new sha. An earlier run's own record commits and grader notes do not count as a change.

**A dead run.** The roster and `brief.counted_sweep` say `DEAD?` when the run's hold is past its own limit, and held edits exit 4. Check `rq.py status`; if nothing is running, free its seats with `force-release` ("After a host restart").

**When it ends.** Whoever queued it commits the run's records as the run's own commit, before any merge or map edit. Then apply the held edits (any writing `board.py` command in the main checkout does it), merge the waiting reports, and file every verdict that is not PASS.

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

A job that hangs is yours to stop; employees kill nothing. Each kill or restart needs its own yes from the user. Take the order from `.foundry/rules.md` (which process first). Before you restart the shared resource, hold the whole of it yourself (`rq.py run --id <your badge id> --job "dev: hold every seat for a restart" --prio 1 --all-seats --max 30m -- <the command the rules file gives for the restart>`: `run` needs `--id`, `--job` and a command, a lower `--prio` goes first, and the `dev` text keeps the roster from reading it as `COUNTED?`), so no job starts under the restart. A `timeout` inside a job that runs on the resource cannot end a hung resource: bound a run from outside.

## After a host restart

A forced update or a crash kills every running job without a word, and nothing reports it. Signs: a hold far past its limit, a seat's last note (`rq.last`) with a killed exit status, a run that started and has no result, every employee silent at once.

First check the restart was a real one, the way the project's rules say: a resume from sleep can look like a restart and frees nothing it held. Read that before you release held work or tell the crew the machine is back.

1. `CronList`. Recreate only the timers that are missing; they can survive a restart.
2. The shared resource: bring it back up as `.foundry/rules.md` says, then `rq.py status --resource`.
3. The queue: `rq.py status`. A hold whose process died is still a lock: free it with `rq.py force-release --by <your badge id> --note "host restart"`, one seat at a time (`--seat NAME`; without it, the first seat). `--by` is the badge id (`MGR-3`), not the line, and only an `MGR-` id is taken; exit 1 means the seat was already free. A waiter that should not run takes `rq.py leave --id <id>`; its waiting process exits 6. A waiter whose process was killed keeps its id in the queue for 2 minutes, and the queue refuses a new job under that id until then: `leave` it first, or wait.
4. A killed counted run or sweep: the lane it was in is VOID, not run. Queue the remaining lanes again under a new output folder. Never reuse the old folder.
5. The crew: wake every carry-over session with the session-management `send_message` and tell it to queue its jobs again. Check each seat's holder in the roster before telling anyone to queue again: a running job is a hold, not a queue entry.
6. Log the outage in the notes: when, what it killed, what was run again.
