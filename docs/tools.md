# Tools reference

Every tool is one Python file under `paths.tools` (default `scripts/foundry`). They use the standard library only; `segno` is optional and draws the badges' QR plates. Each tool's module docstring is its own command reference, and it is the truth where this page and a tool differ.

Conventions on this page:

- Commands are written `python scripts/foundry/<tool>.py ...`. Run the manager's and the founder's commands from the main checkout. An employee copies the absolute paths from its brief.
- `LINE` is a whole badge line, in quotes. An id is the short form: `MGR-1`, `EMP-07`.
- "Office" is `paths.office` in the main checkout (default `out/foundry`). File shapes are in [state.md](state.md).
- Every tool with commands has a `selftest`, except `gym_init.py` (its checks are `tests/gym_init_test.py`). A selftest works in a temp folder; `flow.py selftest` and `plan_flow.py selftest` also read the project, and `flow.py selftest --logic` does not.
- A profile that cannot be read stops every tool: it prints `foundry: the profile cannot be read: ...` on stderr and exits 2, and nothing is done. That covers a TOML error, a file that is not UTF-8, a key of the wrong kind, and a `FOUNDRY_PROFILE` that names no file. Only `foundry_profile.py` (`where`, `show`) and `founder.py doctor` go on, and each names the problem. See [troubleshooting.md](troubleshooting.md#the-profile-does-not-parse).

| Tool | For | Run by |
|---|---|---|
| [`founder.py`](#founderpy) | Scaffold a project, check the install, audit the roadmap, start a push draft | Founder |
| [`office.py`](#officepy) | Badges, the time clock, the roster, briefs, hand-ins, the freeze, the round | Everyone |
| [`rq.py`](#rqpy) | The queue for the shared resource's seats | Everyone who has a resource job |
| [`sweep.py`](#sweeppy) | A counted run of every lane, one at a time | Manager |
| [`board.py`](#boardpy) | The progress map, the check, the brief, every state edit, the decision register | Manager (founder for decisions; employees read only) |
| [`journal.py`](#journalpy) | The shift journal | Everyone logs; the manager plans |
| [`flow.py`](#flowpy) | The workflow page and the road graph | Founder and manager edit; everyone reads |
| [`flow_graph.py`](#flow_graphpy) | The road graph's edit commands, run as `flow.py graph ...` | Founder and manager |
| [`flow_page.py`](#flow_pagepy) | The canvas the chart pages share (a library, no commands) | Nobody directly |
| [`plan_flow.py`](#plan_flowpy) | Plan charts | Founder and manager make; everyone reads |
| [`lanes_for.py`](#lanes_forpy) | Which gym lanes a change can move | Manager |
| [`gym_init.py`](#gym_initpy) | Start a gym, add a lane, check the gym | Founder or the first grader |
| [`foundry_profile.py`](#foundry_profilepy) | Print the profile in force | Anyone |

---

## founder.py

The founder's own tool. It scaffolds and reads; it does not write the roadmap or the queue.

| Command | What it does |
|---|---|
| `founder.py init [--project NAME] [--resource NAME] [--gym]` | Writes the starter profile (`.foundry/foundry.toml`), the rules file, a starter roadmap, the state (through `board.py init`) and the git-ignore lines for the office, the built pages and the crew's worktrees folder (`git.worktrees`). `--resource` names the shared resource in the profile. `--gym` also runs `gym_init.py init` and git-ignores `out/gym`. Never overwrites: a file that exists is kept and named. The starter roadmap opens with a `<!-- STARTER` line, and the new state takes no milestone or decision from it |
| `founder.py doctor [--selftest]` | Checks the interpreter, the profile, every tool (one `ok` line when all are there), every skill, that the office, the built pages and the worktrees folder are git-ignored (each a PROBLEM when not), the state, the roadmap, the hooks, `segno`. `--selftest` also runs each tool's selftest |
| `founder.py audit [--json]` | The roadmap audit in one read: distance to the goal by tier, top-tier requirements no milestone names, duplicate ids, the queue's gaps, open decisions that gate something queued, decisions open a week, failures with no plan, managers' proposal files, usage against the stop, then what `flow.py selftest`, `flow.py brief` and `board.py brief --keys warnings` print. Writes nothing |
| `founder.py push new NAME [--title TEXT] [--by FDR-1]` | Writes a push plan's starter, `<paths.handoff>/<date>-<name>-draft.md`, with the usage budget, the resource's seats, the open failures and the open decisions filled in from the state. `--by` is the badge id |
| `founder.py selftest` | Its own checks |

**Exit codes.** `init`: 1 when a PROBLEM line printed. `doctor`: 1 when a PROBLEM line printed. `audit`: 1 when it printed a PROBLEM. `push new`: 2 when the name is empty or the draft exists.

**Reads.** The profile, the templates (`<tools>/templates/`), the state, the roadmap, `.claude/skills/` (and `~/.claude/skills/`), `.claude/hooks/`, `.claude/settings.json`.

**Writes.** `init`: `.foundry/foundry.toml`, `.foundry/rules.md`, `paths.roadmap`, `paths.state` and the map (through `board.py init`), `.gitignore`. `push new`: one file under `paths.handoff`. Nothing else.

---

## office.py

The crew office: badges, the time clock and the roster for the founder, the one manager and its employees.

**Exit codes.** 0 done. 1 a check that found something (`handin` NOT READY; `timers show` with a bad entry or no file). 2 a command line that cannot be read, or a `--files` path whose folder is missing. 3 refused; the message says why.

**Reads.** The profile; the state file (`shift.id`, `shift.crew_max`, `rota.slots`, `tooling_known`, and for the round: usage, decisions, failures); the office; the queue's files; git (for `handin`, `me`, `clock-out --commits`).

**Writes.** Only in the office: `badge_key.json`, `roster.json`, `timeclock.jsonl`, `badges/<id>.svg`, `handins/<id>.md`, `freeze.json`, `handins-seen.json`, `manager-timers.json`, `briefs/handoff-*.md`, `adr-next.json`. It never writes the tree.

### Badges and hiring

| Command | Who | What it does |
|---|---|---|
| `office.py found --name NAME [--relieve] [--session local_...]` | Founder | Mints the one FOUNDER badge (`FDR-n`). Refused while another founder badge is on the clock, unless `--relieve`. The founder is outside the headcount and never hires |
| `office.py appoint --name NAME [--relieve] [--session local_...] [--this-slot \| --slot day\|swing\|night]` | Manager | Mints the one MANAGER badge (`MGR-n`). Refused while another manager is on the clock and UP, unless `--relieve`. A manager appointed within 20 minutes of the next slot's start is that slot's manager; `--this-slot` keeps the current slot. `--slot` names the slot now, or the next one in the last hour before it starts |
| `office.py hire --by MGR_LINE --name N (--role R \| --title T) --kind session\|temp --job TEXT --eta 90m [--lane G1] [--rq \| --seat NAME] [--files TEXT] [--done-when TEXT] [--force-files] [--adr] [--model ID [--force-model]]` | Manager | Mints an employee badge (`EMP-n` for a session, `TMP-n` for a temp) and prints its line and a ready brief |
| `office.py assign ID --session local_... [--by MGR_LINE] [--dry-run]` | Manager | Records the session the app returned for a badge (a manager's or a founder's too). `--dry-run` lists the badges and lanes the session has held, says whether `assign` would be refused, and writes nothing |
| `office.py amend ID --by MGR_LINE [--job TEXT] [--add-files TEXT \| --set-files TEXT] [--done-when TEXT] [--eta 2h] [--rq \| --seat NAME] [--force-files]` | Manager | Widens, narrows or rewords a badge's job. Logged in the time clock |
| `office.py brief ID --by MGR_LINE` | Manager | Reprints a badge's line and its brief as the roster has it now |
| `office.py verify LINE` | Anyone | Checks a line: `genuine: ...` or a refusal |
| `office.py badge ID` | Anyone | Redraws a badge's plate and prints its line. The plate needs the optional `segno`; without it `badge` says so, and everything else works |

`hire` in detail:

- `--role` is `builder`, `grader`, `reviewer` or `scout`. `--title` names the card the badge is hired on and sets the role. The built-in titles: `builder`, `fixer` (role builder; session or temp); `grader` (role grader; session only; independent); `reviewer` (role reviewer; session or temp; independent); `scout`, `triager`, `cleaner` (role scout; temp or session). A project adds titles under `[titles]` in the profile. `--role` alone hires on the role's own card.
- `--eta` is how long the job takes: `90m`, `2h`, `1h30m`. A bare number is minutes.
- `--rq`: the badge reaches the shared resource through `rq.py run --id <its id>`, any seat; many badges share the queue. `--seat NAME`: one seat of its own. Both are refused when the profile names no shared resource.
- `--files`: the files the badge owns, comma-separated prefixes or globs. A pattern whose folder does not exist is refused (exit 2) unless `--force-files`.
- `--adr`: reserves the next decision-record number (`NNNN`) for the badge and prints it in the brief.
- `--model`: the model the brief names, kept on the roster. Without it the brief prints `Model: <id>` when the profile's `[models]` names the title or the role (the title first). For a title with a `[flagged.<title>]` table, a `--model` other than the table's needs `--force-model`.
- The brief's push rule follows `git.push`: `false` (the default) prints "no push"; `true` prints "push only your own branch, never the main branch".

`hire` refuses (exit 3): an unknown title or role; a title whose profile card is broken; a kind the card does not allow; a grader as a temp; a grader with no `--lane`; a second grader for a lane on the shift; `--rq` or `--seat` with no shared resource; a `--seat` another badge holds; any hire while the shift has no `crew_max`, or is at it.

### The clock

| Command | Who | What it does |
|---|---|---|
| `office.py clock-in --badge LINE` | Everyone | Presents the badge. Refused for a changed line, a revoked badge, or one already on the clock |
| `office.py progress --badge LINE --pct N [--eta 40m\|17:50] [--note TEXT] [--waiting-on EMP-07\|MGR-3-counted] [--run DIR]` | Everyone | Posts progress. `--eta` is the time left (a bare number is minutes) or a clock time. `--waiting-on`: not STALE or OVERDUE while that badge's (or queue id's) job holds a seat or waits. `--run`: a run folder, recorded by its absolute path |
| `office.py me --badge LINE` | Everyone | Your own record: the brief again, what the manager amended, the manager on the clock, a freeze, your place in the queue and an estimate of its start. Writes nothing |
| `office.py status [--badge LINE] [--json]` | Everyone | `me` with a badge; the roster without one |
| `office.py roster [--json]` | Everyone | Who is on the clock, their job, percent and approximate finish; the shared resource's seats, who holds each and who waits; a freeze or a counted run. In the JSON a badge's `plate` is its plate file, or null when none was drawn |
| `office.py runs [--id EMP-07]` | Everyone | The run folders the crew posted, newest first |
| `office.py fail --badge LINE --what TEXT [--lane L] [--run-id R] [--verdict V] [--plan TEXT]` | Everyone | Reports a failure. It gets a report number, `R<seq>`; the manager files it with `board.py fail --from R<seq>` |
| `office.py clock-out --badge LINE --result done\|partial\|failed\|handed-off [--note TEXT] [--commits a,b]` | Everyone | Clocks out. A sha the repository does not hold is refused |
| `office.py clock-out --by MGR_LINE --id EMP-07 --result lost [--note TEXT]` | Manager | Clocks out an employee who is gone |

### Hand-ins

| Command | Who | What it does |
|---|---|---|
| `office.py handin --badge LINE [--base main] [--commits a,b] [--file REPORT.md]` | Employee | Run in your own worktree before clock-out. Checks the branch against the badge and writes `<office>/handins/<ID>.md` with the report file's text |
| `office.py handin --badge LINE --repo DIR --by MGR_LINE` | Manager | The same check, run for an employee. Logged under the manager, so it does not count as the employee being heard |

`--base` is the branch you were cut from (default: the profile's `main_branch`). Without `--commits`, the commits checked are those on the branch past the base. A re-run without `--file` keeps the report an earlier run filed. An earlier READY hand-in with a different report is kept as `<ID>.<n>.md`. The hand-in file's heading names the badge, its title and READY or NOT READY.

What it checks. A **PROBLEM** makes the hand-in NOT READY (exit 1); a **warning** must be explained in the report.

The three walls (the road graph, the measure's files, a run's records) read more than each commit's own file list. They also read the branch's tree against the base: what the branch changed since the fork, and where its tree differs from the base now. So a merge that kept one side (`git merge -s ours`), or a commit left out of `--commits`, does not hide a change. A path where only the base moved on since the fork is not held against the badge.

The walls always stand against the profile's main branch as well as `--base`. `--base` names the branch a badge was cut from, for the check of its own files; a walled change made on that branch would otherwise pass unseen. So whenever `--base` is not the main branch there is a warning saying both were checked, and when the main branch is not in the repository at all, it is a PROBLEM for any badge but the manager's.

| Check | Result |
|---|---|
| A named commit does not exist | PROBLEM |
| The tree is not clean (the untracked `--file` report does not count) | PROBLEM |
| The branch changes the road graph's files (any badge but the manager's or founder's) | PROBLEM: `your branch changes the road graph ...` |
| The branch changes a path under `measure.grader_owned` (any role but grader) | PROBLEM: `your branch changes the measure's files ...` |
| The branch changes a path under `measure.records` (any badge that is neither a grader nor the manager) | PROBLEM: `your branch changes a run's records ...` |
| Changed files outside the files the badge owns | PROBLEM (a warning when the badge also lists a pattern that cannot be checked) |
| The repository's own git config sets `user.name` or `user.email` | PROBLEM |
| A flagged title's commit lacks the profile's trailer line | PROBLEM |
| The profile's `measure.handin_check` command exits non-zero | PROBLEM |
| No commit past the base | warning |
| The main branch has commits the branch lacks; commits already in the main branch as copies | warning |
| A commit adds what reads as a `git config user.*` write | warning |
| The branch changes or removes a contract or prereg that the main branch's prereg pins | warning |
| `measure.handin_check` is set and did not run (no changed file matches `measure.handin_check_paths`, a timeout, it could not start) | warning |
| A counted run is in the queue, or a freeze is on | warning |
| The badge names no checkable file list | warning |
| `--base` is not the profile's main branch (the walls were checked against both) | warning |
| The main branch is not in this repository, so the walls cannot be checked against it | PROBLEM (a warning for the manager's badge) |
| `git diff` of the branch against the base did not run, so the walls saw only the commits | warning |

### The round and the hand-off

| Command | Who | What it does |
|---|---|---|
| `office.py round [--by MGR_LINE] [--json]` | Manager | The manager's wake-up: what needs the manager, most pressing first (usage, what waits on the user, a counted run or freeze, reports not filed, new hand-ins, STALE or OVERDUE crew, the journal's plan), then the crew, the seats and a `first: ...` line. Only a live `<ID>.md` counts as a hand-in; an earlier one kept as `<ID>.<n>.md` is not listed. With `--by` it also posts the manager's heartbeat and marks the listed hand-ins seen. Without it, it writes nothing |
| `office.py end-shift --by MGR_LINE [--lose-temps] [--out crew.json]` | Manager | The slot's crew summary. A temp that never came in or went silent is clocked out as lost; one still working stays on the clock (`--lose-temps` clocks every temp out as lost). `--out` writes the log entry's crew list as JSON, for `board.py log add --crew-file` |
| `office.py handoff --by MGR_LINE [--out FILE]` | Manager | Writes the next manager's hand-off brief as Markdown (default `<office>/briefs/handoff-<slot>-<YYYYMMDD>.md`) and prints its path. Three sections are left for the manager to fill by hand. Never overwrites: a second call writes `<name>-2` |
| `office.py timers init --by MGR_LINE` | Manager | Writes `<office>/manager-timers.json` when it is missing: the round (every `slots.round_every`), and each slot's hand-off (40 minutes before its end) and start |
| `office.py timers show` | Manager | Prints the list and checks its shape. Exit 1: a bad entry, or no file |

The tool creates no timer. The manager creates them in its session; the file is the list.

### The freeze

| Command | Who | What it does |
|---|---|---|
| `office.py freeze on --by MGR_LINE --why TEXT [--lane G1] [--max 3h]` | Manager | Holds the main checkout still for a counted run. Writes `freeze.json`. `--max`: how long it should last at most, with its unit (`30m`, `3h`); a bare number is refused (exit 3). Past it the freeze reads STALE. A second `on` is refused until `off` |
| `office.py freeze off --by MGR_LINE [--note TEXT] [--force]` | Manager | Lifts it. A freeze a counted sweep or counted run set (its `why` starts "counted sweep", or its `by` is a `-sweep` or `-counted` id) is refused (exit 3) without `--force`: the sweep may still be running, and it lifts its own freeze at its end |
| `office.py freeze show [--json]` | Anyone | Whether a freeze is on, by whom, since when |

`on` and `off` are punches in the time clock. While a freeze is on, the roster and every `me` say FREEZE, `board.py` holds its edits, and `flow.py graph` edits, `gym_init.py init` and `lane add`, and `plan_flow.py new` are refused in the main checkout ([concepts.md](concepts.md#the-freeze-during-a-counted-run)). A project with a shared resource usually needs no `freeze on`: the counted run's queue id marks it.

A `freeze.json` that cannot be read, or whose time or length is not a sane one, reads as a freeze that is on, by "unknown", with the reason in `why`: a tool that cannot tell holds still. `freeze off` removes it.

`--eta` (of `hire`, `amend` and `progress`) is the one place a bare number is still read, as minutes.

---

## rq.py

A fair queue over the seats of the one shared resource. One job holds a seat at a time. It refuses to run (exit 2) when the profile names no shared resource.

| Command | Who | What it does |
|---|---|---|
| `rq.py run --id EMP-07 --job "unit tests + lint" --touched "src/app src/core" [--prio 5] [--max 30m] [--wait 4h] [--seat NAME \| --all-seats] [--exclusive] [--no-prepare] [--enforce-max] -- <command>` | Everyone | The preferred way. Queues for any free seat, runs the profile's `resource.prepare` line there, runs `<command>` (a shell command line) with the seat's name in the variable `resource.seat_env` names, then releases the seat with a note naming `--touched`, whatever the command's exit |
| `rq.py take --id EMP-07 --job "..." [--prio 5] [--max 30m] [--wait 4h] [--seat NAME] [--exclusive]` | Everyone | By hand: blocks until this id holds the first seat (or `--seat`), then prints that seat's last release note. Work in that seat only, and release when done |
| `rq.py release --id EMP-07 --note "what ran" --touched "src/app src/core"` | The holder | Frees the id's holds |
| `rq.py leave --id EMP-07 [--note TEXT]` | The waiter | Takes a waiter out of the queue. Its waiting process exits 6 at its next poll |
| `rq.py status [--resource] [--json]` | Anyone | Each seat's holder and minutes of its `--max`, then the waiters. `--resource` also runs the profile's `resource.status` command and prints what it says. `--json` prints one object for other tools |
| `rq.py force-release --by MGR-01 --note "why" [--seat NAME]` | Manager | Frees a hold whose owner is gone. `--by` is the manager's badge id |
| `rq.py selftest` | Anyone | Its rules, on scratch seats in a temp folder |

Flags of `run` and `take`:

| Flag | Meaning |
|---|---|
| `--id` | Required. The badge id, not the line. A counted run uses `<badge id>-counted-<lane>`; a sweep uses `<badge id>-sweep` |
| `--job` | Required. What the job is, in words |
| `--prio` | Default 5. Lower runs first: 0 counted runs and their dry runs, 1 the slot-end checks, 2 the critical path the manager names. A waiter older than 90 minutes ranks at 2 |
| `--max` | How long the hold may last. Default `resource.default_max` (30 minutes). Needs a unit, and is longer than zero |
| `--wait` | How long to wait for a seat. Default 4 hours. Needs a unit, and is longer than zero |
| `--seat NAME` | That seat only |
| `--all-seats` | (`run`) Wait until every seat is free, then hold them all. The command runs in the first seat, with the variable `resource.seats_env` names listing every seat held |
| `--exclusive` | Mark the job exclusive: only one exclusive job holds a seat at a time. A job whose `--job` text or command matches `resource.exclusive` is exclusive without the flag |
| `--touched` | (`run`) What the job touches in the seat; written into the release note for the next holder's prepare line |
| `--no-prepare` | (`run`) Skip the prepare line |
| `--enforce-max` | (`run`) End this job at its `--max` plus `resource.max_grace` |

**Times carry a unit.** `--max` and `--wait` take `90s`, `30m`, `2h` or `4h30m`. A bare number is refused (exit 2), and so is a zero time such as `0s`.

**One job per badge.** `run` and `take` refuse (exit 3) an id that already waits or holds a seat. To chain steps, quote the whole chain as one word after `--` (`-- "step-one && step-two"`).

**Whole-resource jobs and backfill.** Behind a waiting `--all-seats` job, another waiter takes a free seat only when its `--max` is 30 minutes or less and ends before the last busy seat's hold reaches its limit. Once the whole-resource job has waited 60 minutes, nothing backfills.

**The prepare line** reads `FOUNDRY_SEAT` and `FOUNDRY_SEATS` (or the names the profile gives them), `FOUNDRY_JOB_ID`, `FOUNDRY_TOUCHED`, `FOUNDRY_LAST_HOLDER`, `FOUNDRY_LAST_NOTE` and `FOUNDRY_LAST_TOUCHED`. Its exit code is printed, not acted on.

**The shell.** Commands run as `<shell> -c "<line>"`. The shell is `resource.shell` when set, else `bash` from the PATH, else `sh`.

**What `run` prints.** `rq: running in seat ...` before the command; `rq: started [<token>]` once the command's shell was started; `rq: finished exit <n> [<token>]` when the command ended by itself; then the release. The token is what the caller put in `FOUNDRY_RQ_TOKEN` (empty brackets when it set none). `rq.py` takes that variable out of the command's environment, so a command cannot print the two lines for itself. `sweep.py` reads them to tell a lane that ran from one the queue never ran. A hold or a wait under a minute is printed in seconds.

**Stopping a `run`.** Every `run` job runs in a process group of its own (on Windows, a job object). An interrupt (Ctrl+C), TERM or HUP where the platform has them, or BREAK on Windows (Ctrl+Break) ends the job with everything it started, releases the seat with a note saying so, and exits 130 (after printing `rq: interrupted`), or 128 plus the signal's number. A stop while `run` still waits takes it out of the queue. A KILL cannot be caught: the job runs on and the seat stays held until the manager's `force-release`.

**Enforcing `--max`** is opt-in: `resource.enforce_max = true`, or `run --enforce-max` for one job. When on, a `run` job (its prepare line included) still going at its `--max` plus the grace (`resource.max_grace`) is ended as a whole group, with everything it started, its seat is released with a note, and `run` exits 124. Off, nothing ends a job: a long hold only reads OVERDUE. A `take` hold is never ended.

**Exit codes.** `run`: the command's own exit code; 2 a usage error or no shared resource; 3 refused (the id already waits or holds a seat); 6 the wait ran out, or the job was taken out with `leave`; 124 ended at its limit; 130, or 128 plus a signal's number, stopped. `take`: 0 held; 3 refused; 6 not taken within `--wait`. `release`: 3 when the id holds no seat. `leave`: 3 when the id is not waiting. `force-release`: 3 when `--by` is not a manager id; 1 when the seat is free.

**`status --json`** prints one object: `resource`, `now`, `enforce_max`, `seats` (each `seat`, `holder`, and for a held seat `job`, `since`, `max`, `overdue`, `all`, `exclusive`, `prio`, `via`; `holder` is null when the seat is free), `queue` (the waiters in order: `id`, `job`, `prio`, `at`, `wants`, `max`, `exclusive`; `wants` is `all`, `any` or a seat's name) and `counted` (`holding` and `waiting`: the ids that mark a counted run). Times are seconds since the epoch.

**Reads.** The profile's `[resource]` table; `rq.seats` in the office (one seat a line), which overrides the profile's list when present.

**Writes.** In the office: `rq.queue.json`, `rq.requeue.json`, `rq.released.json`, `rq.mutex`, and for each seat a lock folder and a last-release note. The first seat uses `rq.lock` and `rq.last`; another seat `S` uses `rq.lock.S` and `rq.last.S`.

---

## sweep.py

The counted sweep: the gym's counted run for each lane, one lane at a time, in the main checkout, stopped the moment the tree it is counting changes. See [gym.md](gym.md#the-sweep).

| Command | What it does |
|---|---|
| `sweep.py run --id MGR-01 --out out/sweeps/<name> [--lanes "G1 G2"] [--queued-at SHA] [--check-only] [--max-per-lane 3h] [--wait 4h] [--touched "what the runs touch in the seat"]` | Runs the sweep |
| `sweep.py status --out out/sweeps/<name>` | The lanes run with their exit codes and notes, those run with no verdict, the lanes the queue did not run, the lane in flight, the lanes left. A lane in flight with no sweep alive reads `VOID: not run` |
| `sweep.py selftest` | Its own checks |

| Flag | Meaning |
|---|---|
| `--id` | The badge id of whoever queued it. The queue id (`<id>-sweep`) and the freeze carry it |
| `--out` | The sweep's own folder for its logs and tables. It must lie inside the main checkout under a git-ignored folder, and must not exist yet |
| `--lanes` | The lanes, in order. Default: every lane the gym knows (the `LANES` of the gym's `run.py`; without one, the `*.json` names under `<paths.gym>/prereg`) |
| `--queued-at` | The commit the sweep was asked for (default: HEAD now). When the main branch has moved since, `lanes_for.py` says which lanes the commits between can move, and the sweep does not start if one of them is a lane it would run |
| `--check-only` | Do the start checks, write `source.txt`, run nothing |
| `--max-per-lane` | The longest one lane may take, with a unit (default `3h`) |
| `--wait` | How long one lane may wait in the queue (the queue's own default when left out) |
| `--touched` | Passed to the queue's release note for each lane |

The command of one lane is `measure.counted` in the profile, with `<lane>` replaced. With a shared resource, each lane runs as `rq.py run --id <badge id>-sweep --prio 0 --all-seats --max <max-per-lane> --job "counted sweep: <lane>" -- <command>`.

**The freeze.** With or without a shared resource, the sweep turns the office's freeze on for its whole run and off at its end, because between two lanes its queue id neither holds nor waits. Its `freeze.json` carries one extra key, `sweep` (the sweep's folder). At the end it removes the file only while it is still its own. A freeze this id set by hand (`office.py freeze on`) is kept: the sweep runs under it and leaves it on. A freeze a sweep under this id wrote and left on is taken over, unless that sweep's `alive` file is still fresh: then that sweep is running and this one is refused (exit 3). It does not start while someone else's freeze is on, or the file cannot be read (exit 3). Before every lane the freeze is read again: when the one the sweep runs under was lifted or replaced, the sweep stops there (exit 3) and says which.

**One sweep at a time.** A running sweep keeps `sweep.lock` in the office and removes it at its end. A sweep does not start (exit 3) while the sweep the lock names still touches its `alive` file, whatever freeze is on and whoever set it. A lock whose `alive` went stale is a killed sweep's, and is written over.

**The tree.** Before the first lane the main checkout must be clean. Before each later lane, and again after every lane, it must still be at the commit the sweep started at, and clean apart from the run's own records (`measure.records`). Anything else stops the sweep at once (exit 4); a lane during which the tree changed carries the note `tree changed during this lane: ...` on its `runs.tsv` row. HEAD's reflog is compared as well, so a commit that was made and reset away again during a lane is a change too.

**A lane's exit code.** A lane that exits non-zero does not stop the sweep: its exit code is recorded and the grader reads the run. The exit codes listed in `measure.no_verdict_exits` (default `[2, 3]`, the scaffolded runner's "refused" and "the runner failed") mean the command ran and gave no verdict. Such a lane carries `no verdict (exit <n>)` on its `runs.tsv` row, `status` lists it under its own heading, the last summary line counts the two kinds apart, and the sweep itself exits 1.

**A lane the queue never ran.** A lane counts as run only when its log holds both of `rq.py`'s lines with the lane's own token: `rq: started [<token>]` and `rq: finished exit <n> [<token>]`. Without both (the queue refused, waited too long, stopped at the prepare line, could not start the shell, failed itself, ended the command at its limit, or was stopped) the row carries `not run (the queue: exit <n>): ...` with `rq.py`'s last line, and the sweep stops (exit 6).

**Stopping it.** A file named `sweep-STOP` in the office pauses the sweep before the next lane (exit 0). An interrupt (Ctrl+C), TERM, HUP or BREAK is passed on to the lane in flight; the sweep waits up to 20 seconds for `rq.py` to end the job and release its seats, lifts its own freeze, writes `ended <time> interrupted` and exits 130, or 128 plus the signal's number. If `rq.py` had to be killed, `source.txt` and stderr say that its seats may still be held, until the manager's `rq.py force-release`. A KILL of the sweep itself cannot be caught: its freeze stays on until the next sweep under the id takes it over, or the manager lifts it (`office.py freeze off --force`).

**Exit codes of `run`.**

| Code | Meaning |
|---|---|
| 0 | Every lane was run and gave a verdict, whatever the word (or `--check-only` passed, or `sweep-STOP` paused it) |
| 1 | Every lane was run, and at least one gave no verdict (its exit code is in `measure.no_verdict_exits`) |
| 2 | Usage, or a refusal before anything was written (no `measure.counted`, no lanes, a bad `--out`, an unknown `--queued-at`) |
| 3 | A freeze stands in the way: someone else's is on or `freeze.json` cannot be read, another sweep is still running, or the freeze this sweep ran under was lifted or replaced before a lane |
| 4 | The main checkout is not clean, its HEAD moved (or moved and came back), or it changed during a lane |
| 5 | The commits since `--queued-at` can move a lane of this sweep (queue it again at the new sha) |
| 6 | The queue did not run a lane (refused, not taken within `--wait`, no shell, ended at its limit, stopped) |
| 130 | The sweep was interrupted (Ctrl+C); 128 plus a signal's number: it was stopped by that signal |

A sweep that stops early (3, 4, 6) exits with that code even when a lane before the stop gave no verdict. `status`: 0, or 2 when `--out` is not a sweep's folder.

**Reads.** `measure.counted`, `measure.records`, `measure.sweep_skip`, `measure.no_verdict_exits`, `resource.name`, `paths.gym`, `paths.office`, `main_branch`; git.

**Writes.** Under `--out`: `source.txt`, `started.tsv`, `runs.tsv` (with a note when the queue did not run the lane, the lane gave no verdict, or the tree changed during it), `<lane>.log`, `alive`. In the office: `freeze.json` and `sweep.lock`, for the length of the run. It commits nothing. Its last lines tell whoever queued it to commit the run's records.

---

## board.py

The progress map: where the project is, kept by hand and checked against the gym. Its one hand-kept input is the state file; `write_state` is the state's one writer.

**Reads.** The state (`paths.state`), the gym's series, prereg, contract and grade files (`paths.gym`), the office (the roster, the time clock, the queue, the freeze), the roadmap's tables (`paths.roadmap`), git.

**Writes.** The state and the map (`paths.map`), and `pending-state.jsonl` in the office for held edits. In a linked worktree every writing form is refused (exit 3): the state and the map are written in the main checkout only.

### Reading

| Command | Who | What it does |
|---|---|---|
| `board.py` (or `board.py build`) | Manager | Builds the map from the state and the gym's series. Prints each warning |
| `board.py check` | Manager | Builds, then prints the shift-start summary and every warning. Exit 1 when a warning is present. When the roadmap names a milestone or an open decision the state lacks, the warning gives the command: `board.py milestone sync`, `board.py decide adopt D<n>` |
| `board.py check --no-build` | Anyone | The same summary; writes nothing. The form an employee uses |
| `board.py open` | Manager | Builds, then opens the map in the browser |
| `board.py brief [--full] [--keys a,b]` | Manager, founder | One compact JSON; writes nothing. Warnings come first. Long texts are cut unless `--full`. `--keys` prints only those keys (warnings always; a key it does not know comes back under `unknown_keys`). Exit 1 means only "warnings present" |
| `board.py decide list [--open]` | Anyone | The decision register, newest first |
| `board.py queue list` | Anyone | The later shifts |
| `board.py pending` | Anyone | The edits held while the main checkout was frozen. A line of the file that cannot be read is shown as `UNREADABLE line, kept and skipped` |
| `board.py stamp` | Anyone | The time now, as the state file writes it. Use it in a script instead of calling `date` |
| `board.py selftest` | Anyone | Checks on made-up inputs, in a temp folder |

The brief's keys: `warnings`, `at`, `tree`, `now`, `slot`, `shift`, `blocks`, `next_block`, `queue`, `crew`, `attention`, `recent_runs`, `usage`, `checkpoints`, `checkpoints_passed_earlier`, `failures_open`, `untriaged`, `research_review`, `blockers`, `decisions_open`, `release`, `held_edits`. Only in a project with a shared resource: `resource`, `counted_sweep`, `counted_unmarked`, `dev_not_counted`.

### State edits

Each edit sets `updated`, writes the state and rebuilds the map. Each command takes only its own options; any other is refused and nothing is written. A bare `--` ends the options, so a text may start with `--`.

| Command | Writes | Notes |
|---|---|---|
| `board.py note --by MGR-1 "text"` | `notes` | A note at the top |
| `board.py usage 12 [--stop 80] [--reset 2030-01-07T01:00-06:00]` | `usage` | A weekly-usage point, in percent. A later `--reset` starts a new line of points |
| `board.py block 3 done [--note "text"]` | `shift.blocks[2]` | Statuses: `done`, `partial`, `skipped`, `in-progress`, `pending`, `blocked`, `paused` |
| `board.py fail --what "text" [--lane L] [--run-id R] [--verdict V] [--plan P] [--owner O] [--status open\|planned\|fixed\|dropped] [--from R12,R13]` | `failures` | The next `F<nnn>`. Without `--status`, an entry with a plan and an owner is `planned`, any other `open` |
| `board.py rr --kind review\|research --by "TMP-1 x" --topic "text" [--report P] [--commit C] [--finding "a \| b"] [--action "a \| b"] [--slot day] [--date 2030-01-02]` | `research_review` | The next `RR<nnn>` |
| `board.py log add --by MGR-1 --title "text" [--slot day] [--done "a \| b"] [--not-done "a \| b"] [--verdicts "G1 PASS \| G2 FAIL"] [--commits a,b] [--next "text"] [--crew-file crew.json \| --crew "a \| b"]` | `log` | A log entry at the top, dated from the clock. `--crew-file` takes the JSON list `office.py end-shift --out` wrote |
| `board.py now [--headline "text"] [--position "text"] [--tree <sha>\|auto]` | `now` | At least one of the three. `--tree auto` is the last commit on this branch that is not only records (the map's files, reports, notes, run records) |
| `board.py rota set --date 2030-01-02 --slot day [--shift ID] [--manager MGR-2] [--ends 16:00] [--note "text"]` | `rota.days` | Writes or updates that day's slot entry. An empty `--ends` or `--note` takes the key out |
| `board.py rota slots [--rr-min 90]` | `rota.slots[].rr`, `rota.rr_since` | Writes each slot's research-and-review window from its start (default length: `slots.review_window_min`), and sets `rota.rr_since` to now when it is missing |
| `board.py checkpoint add --lane G1 --milestone M1 [--builder EMP-3] [--grader EMP-4] [--note "text"] [--block 3]` | `checkpoints`, `lanes`, and `checkpoint` on that block | A grader who is the builder is refused |
| `board.py checkpoint set G1 [--builder ID] [--grader ID] [--note "text"]` | `checkpoints` | |
| `board.py blocker add --what "text" --owner "the user" [--needs D7] [--shift ID]` | `blockers` | Standing unless `--shift` ties it to a shift (`promote` drops it then) |
| `board.py blocker rm 2\|"start of its text" --note "text" [--by MGR-1]` | `blockers`, `notes` | What it was and the note go to `notes` |
| `board.py checklist add "text"`, `checklist done 2`, `checklist rm 2`, `checklist reset` | `checklist` | The list the next manager walks: add a line, tick one, remove one, clear the ticks |
| `board.py shift set [--crew-max 4] [--heavy-ok yes\|no] [--milestone M1] [--when "text"] --by MGR-1 --words "the user's own words"` | `shift` | `crew_max` and `heavy_ok` are the user's numbers: `--words` is required with them, and is appended to the shift's `when` with the time |
| `board.py shift blocks --file blocks.json` | `shift.blocks` | Replaces the current shift's blocks with a JSON list, before its work begins. Refused once a block is done, skipped, partial or in progress |
| `board.py queue add --file shift.json [--at 1]` | `queue` | A queued shift has `id`, `title`, `crew_max` and `blocks` (each with a title). Ids are unique across the shift and the queue. Place 1 is promoted next |
| `board.py queue rm ID --note "text" [--by MGR-1]`, `board.py queue move ID 1` | `queue` | |
| `board.py milestone set M1 --status done\|partial\|in-progress\|planned [--note "text"] [--force --words "the user's own words"] [--title "text" --lane G1]` | `milestones` | `done` is refused unless the milestone's lane has PASS as its latest counted verdict in the gym's series; `--force --words` records the user's override. `--title` and `--lane` add a milestone the list does not have yet. For a new id the roadmap names, no `--title` is needed: it takes the roadmap's title and lane, and every other milestone the roadmap names is added too. For a milestone the list has, `--title` changes nothing, and another `--lane` is refused (exit 3) unless `--force --words` records the change (`forced` then keeps `lane_was`) |
| `board.py milestone sync [--prune]` | `milestones` | Adds every milestone the roadmap's tables name and the state lacks: `planned`, with the roadmap's title and lane. It also rewrites, from its row, the title and lane of a planned milestone nothing has touched (no note, checkpoint, forced record, shift or log entry). `--prune` removes the planned, untouched ones the roadmap no longer names; without it they are only named |
| `board.py promote` | `shift`, `queue`, `blockers` | When every block of the shift is done or skipped: moves `queue[0]` into `shift` and its blockers into `blockers` |

**Exit codes of an edit command.** 0 written (or held). 1 there is no state file: `no state yet (...): run board.py init first`. 2 the command cannot be read or names something the state does not have. 3 a rule refuses it (a linked worktree, a milestone done whose lane has not passed, a milestone's lane re-pointed without the user's words, a grader who is the builder, blocks replaced after work began). 4 held under a hold that looks dead. 5 not held (the office's lock was busy: run it again). `promote`: 2 when nothing is queued or a block is still pending; 3 during a freeze.

**Held edits.** While a counted run's id holds or waits for the shared resource, or the office's freeze is on, an edit run in the main checkout is checked, then held in the office's `pending-state.jsonl` and applied with its own time by the next writing command run there after the run. `board.py pending` lists what is held.

- A held edit keeps the JSON of a `--file` it was given and the commit `--tree auto` meant.
- A number that names an item (`blocker rm 2`, `checklist done 2`, `block 3 done`, `checkpoint add --block 3`, `queue move ID 2`, `queue add --at 2`) is read against the state as it is written, the list `board.py check` prints, and kept as the item's identity: the blocker's or line's text, the block's title, the queued shift's id.
- The edit is checked against the state as it will be once the edits already held are applied. So a second `blocker rm` of the same blocker is refused at once (exit 2), not at the replay.
- At the replay each edit finds its item again. One whose item is gone, or cannot be told from another, stays in the file with the reason (`board.py pending` prints `FAILED: ...`), and the later ones are still applied. Settle it by hand, then delete the file.
- Every held edit has an id, and the state keeps the id of the last one replayed in `_applied`. A replay cut short between the two writes never applies an edit twice.

### Decisions

| Command | Who | What it does |
|---|---|---|
| `board.py decide ask --by FDR-1 --question "text" [--options "a \| b"] [--recommend "a"] [--needed-before M12] [--brief docs/decisions/D7-x.md]` | Founder, manager | Files the next `D<n>` in `state.decisions`: a question only the user answers. The id is the one after the highest of the register and of the roadmap's decisions table together, so one id never means two questions. Ids follow the profile's `roadmap.decision_id`; where that pattern is not a prefix and a number, `ask` cannot pick the next one and takes `--id <id>`. `--by` is the badge id |
| `board.py decide answer D7 --words "the user's own words"` | Founder, manager | Records the answer. Empty words are refused |
| `board.py decide withdraw D7 --note "text"` | Founder, manager | The question no longer needs an answer. It also takes an answered entry that was adopted from a roadmap that no longer names it |
| `board.py decide adopt D2 [--by MGR-1] [--needed-before M3]` | Founder, manager | A register entry for a decision the roadmap's table already names, under the same id. The question is the roadmap's row. It is answered where the roadmap says Decided, else open. Refused (exit 2) when the register has the id or the roadmap does not |
| `board.py decide adopt D2 --refresh` | Founder, manager | Reads an adopted entry again from the roadmap's row, after the row was rewritten. Only an entry adopted by `roadmap` itself (`init`'s, or `adopt` with no `--by`) that nobody has answered or withdrawn through the register; any other is refused (exit 2) |
| `board.py decide list [--open]` | Anyone | Reads only |

Only an open decision is answered or withdrawn. A changed question is asked as a new one. The check warns while the register and the roadmap disagree on whether a decision is answered, names a decisions row that opens like a row and was not read, and names an id that stands in more than one row. An entry answered or withdrawn through the register carries `settled`.

### Init

| Command | Who | What it does |
|---|---|---|
| `board.py init` | Founder (through `founder.py init`) | Writes a starter state when none exists, then builds the map. Refuses to overwrite (exit 3) |

The starter state takes its rota from the profile's `[slots]`, its `crew_max` from `limits.crew_max` and its usage stop from `limits.usage_stop`. When a roadmap is already there, `init` also lists every milestone its tables name (as `milestone sync` does) and adopts every decision its table names (as `decide adopt` does). The starter roadmap `founder.py init` writes is the exception: while its first line opens with `<!-- STARTER`, its rows are examples, nothing is taken from it, and the check's roadmap-against-state lines are skipped. `init`'s closing `Next:` line says which case it met.

---

## journal.py

The shift journal: holes, failures of the process and improvements, each with an action plan for the user's approval. It runs on the office's badges.

Everyone with a badge:

| Command | What it does |
|---|---|
| `journal.py add --badge LINE --kind hole\|failure\|improvement --what TEXT [--fix TEXT] [--where TEXT] [--what-file F] [--fix-file F] [--carry CREW]` | Logs an entry as you notice it; prints its id (`J12`) |
| `journal.py mine --badge LINE` | Your own entries and what became of them |
| `journal.py show --badge LINE J29,J32 [--json]` | Reads the entries you name; read-only |

The manager on the clock only (`--by` is the manager's badge line):

| Command | What it does |
|---|---|
| `journal.py add --by LINE --kind K --what TEXT [--fix TEXT] [--where TEXT] [--from EMP-07]` | `--from`: logged for a crew member |
| `journal.py show --by LINE [J12,...] [--all] [--json]` | The live entries. `--all`: closed ones too |
| `journal.py plan --by LINE J12,J14-J16 --fix TEXT [--files TEXT] [--how TEXT] [--owner TEXT] [--carry CREW]` | The action for one entry or several. Planning an approved entry again clears its approval |
| `journal.py set --by LINE J12 --status fixed\|covered\|dropped\|left\|open [--note TEXT] [--commit SHA] [--of J3]` | `fixed`: `--commit` or `--note`. `covered`: `--of` or `--note`. `dropped`, `left`: `--note` |
| `journal.py due [--by LINE --end 16:00]` | When the plan is due (an hour before the slot's end) and where it stands: OPEN, READY or APPROVED. `--end`: the user's end for this manager, when the rota does not carry it |
| `journal.py ready --by LINE` | Refuses while an entry has no plan; writes the plan file for the user and marks the plan ready |
| `journal.py approve --by LINE --words "the user's own words" [--only J1,J2 \| --except J4]` | Records the user's approval of the ready plan |
| `journal.py carry --by LINE J12,J14 --to CREW\|none [--note TEXT]` | The lesson also holds for another crew (`none`: it does not) |
| `journal.py take --by LINE [--max 10] [--list] [--from FILE [--crew NAME]]` | Takes the lessons other crews carried here into this journal as open entries, each once |
| `journal.py selftest` | Its own checks |

An entry is open (no plan), planned, left, or closed: fixed, covered or dropped.

**Exit codes.** 0 done; 3 refused (the message says why).

**Reads.** The office (badges, the roster), the state's rota for the slot's end, the profile's `crew` and `[crews]`.

**Writes.** In the office: `journal.jsonl` (append-only), and under `journal/`: `journal.md` (the page a person opens), `plan-<YYYYMMDD>-<HHMM>-<badge id>.md`, `carry-<crew>.jsonl`. Nothing in git changes.

---

## flow.py

The road to the goal as a dependency graph, the pipeline every milestone moves through, and where work waits. See [charts.md](charts.md).

| Command | Who | What it does |
|---|---|---|
| `flow.py build` (the default) | Founder, manager | Writes `workflow.html`, `brief.json` and `graph.json` under `paths.flow_out` and prints the findings |
| `flow.py brief` | Anyone | Prints the findings as JSON |
| `flow.py edges` | Anyone | Prints the graph as parsed from the roadmap, to check an edit kept its shape |
| `flow.py selftest` | Anyone | Exit 1 when the roadmap no longer parses into a sound graph (a milestone or decision row that opens like a row and does not parse, and an id that stands in two rows, are each named with the row's line), or the road graph asset was changed by hand or no longer names the roadmap's milestones, decisions and stages. Inputs a new project does not have yet are NOTE lines only |
| `flow.py selftest --logic` | Anyone | Just the tool's own checks, with no project read |
| `flow.py graph ...` | See below | The road graph asset |

Options: `--out=DIR` puts the built files elsewhere (a branch's build); `--root=DIR` reads another checkout. Both are written joined by `=`. Run from any worktree, it reads the main checkout's live files unless `--root` says otherwise.

**Reads.** The roadmap, the state, the gym's series, git (when each lane's contract and prereg first appeared), the office (roster, time clock, the queue), `road.graph.json`.

**Writes.** Only under `paths.flow_out` (or `--out`). A build never dirties the tree.

## flow_graph.py

The road graph as an authored asset. It is run as `flow.py graph ...`. Both files lie in `paths.flow`: `road.graph.json` (the nodes and links) and `road.edits.jsonl` (every edit, signed with the office's key and chained to the one before).

Edits take the badge line of the manager on the clock, or of the founder. A crew badge is refused.

| Command | What it does |
|---|---|
| `flow.py graph seed --by LINE` | Once: writes the asset from the links `flow.py` reads out of the roadmap's prose, each marked seeded (unconfirmed) |
| `flow.py graph link FROM TO [--ids A-01,B-02] [--why TEXT] --by LINE` | FROM must come before TO. `--ids`: a decision gates only those requirement ids |
| `flow.py graph unlink FROM TO --by LINE` | Removes a link |
| `flow.py graph confirm FROM TO [--why TEXT] --by LINE` | Marks a seeded link as checked |
| `flow.py graph node add ID [--type milestone\|decision\|stage\|block] [--note TEXT] --by LINE` | Adds a node |
| `flow.py graph node set ID --note TEXT --by LINE` | Sets a node's note |
| `flow.py graph node rm ID --by LINE` | Refused while a link touches it |
| `flow.py graph undo --by LINE` | Takes back the last edit (again: puts it back) |

Anyone may read, with no badge:

| Command | What it does |
|---|---|
| `flow.py graph show [ID]` | The asset in short, or one node with its pins and links |
| `flow.py graph trace ID [--up\|--down]` | Everything ID waits on, or everything that waits on ID (both by default) |
| `flow.py graph verify` | Exit 1 when the asset was changed by hand or the log's chain is broken |

**During a freeze.** An edit writes tracked files. So in the main checkout every edit command (`seed`, `link`, `unlink`, `confirm`, `node`, `undo`) is refused, exit 3 with one line naming the freeze, while the manager's freeze is on or a counted run or sweep holds or waits for the shared resource. The badge is checked first. `show`, `trace` and `verify` only read and are never refused. A worktree is never frozen.

**Exit codes.** 0 done; 1 `verify` found tampering; 3 refused (a crew badge, or a freeze).

**Writes.** `road.graph.json` and `road.edits.jsonl` under `paths.flow`. It commits nothing: commit the two files with the map.

## flow_page.py

The canvas the chart pages share: typed nodes with named pins, pan and zoom, search, a details panel, tracing. It has no commands. `flow.py` and `plan_flow.py` import it. A project's own "system graph" reader can draw onto it: [charts.md](charts.md#a-projects-own-system-graph).

---

## plan_flow.py

Plan charts: a plan written as one file, drawn as a flow chart and checked against the tree. See [charts.md](charts.md#plan-charts).

| Command | What it does |
|---|---|
| `plan_flow.py list` | Every plan under the flow folder, with its counts and problems |
| `plan_flow.py new NAME --title "..." [--question "..."] [--by "LINE"]` | Starts `NAME.plan.toml` there from the template. Never overwrites |
| `plan_flow.py build [NAME] [--out DIR] [--by "LINE"]` | Writes `NAME.html` and `NAME.graph.json` (every plan when no NAME) |
| `plan_flow.py show NAME ID` | One stage, step, decision or lane, with its links |
| `plan_flow.py trace NAME ID [--up\|--down]` | Everything before it, or everything that follows from it |
| `plan_flow.py edges NAME` | Every link, one per line, then the problems |
| `plan_flow.py selftest [NAME]` | The plan's own checks (every plan when no NAME). Exit 1 on a problem |

An option's value follows it (`--title "x"`) or is joined to it (`--title="x"`).

It works on the checkout the shell stands in. A write that would land in the main checkout (`new` there, a `build` there, or an `--out` that points into it) takes the manager's badge or the founder's (`--by "LINE"`); without it the command exits 2. Anyone else works in a worktree, or builds with an `--out` outside the main checkout. During a freeze even the manager's `new` is refused there, and a build may write only under the git-ignored output folder.

**Exit codes.** 0 done. 1 a selftest or build found a problem, or `new` found the plan already there. 2 a command line that cannot be read, an unknown plan, or a write into the main checkout without the badge. 3 a write into the main checkout refused during a freeze (or while the office cannot be read, so a freeze cannot be ruled out): the same code `flow.py graph` and `gym_init.py` give.

**Reads.** `NAME.plan.toml` under `paths.flow`; each step's and decision's anchor (a file and a text it must hold); the roadmap row a decision names; the office (for the badge and the freeze).

**Writes.** Under `paths.flow_out` (or `--out`); `new` writes one file under `paths.flow`. It commits nothing.

---

## lanes_for.py

Which gym lanes a change can move. The manager's tool for the merge gate and a short sweep. See [gym.md](gym.md#lanes_forpy-and-lane-inputstoml).

| Command | What it does |
|---|---|
| `lanes_for.py <git range>` | The lanes whose inputs the range touches, one per line, with the matching rule as a trailing comment |
| `lanes_for.py --files a b c` | The same for a list of repository paths |
| `lanes_for.py <range> --explain` | Per lane, every touched path that matched and why; then the touched paths no lane watches |
| `lanes_for.py <range> --skip GLOB` | Leave the touched paths matching GLOB out (may repeat) |
| `lanes_for.py check` | The project's own table: every lane in the gym's `run.py` has an entry and the other way round, every group and unit a lane names exists; prints the units no lane reads |
| `lanes_for.py selftest` | Its rules, on a scratch tree in a temp folder |

A range is anything `git diff --name-only` takes (`a..b`, `a...b`), or one commit, which means its diff against its first parent.

**Exit codes.** 0 (with no output when no lane is touched); 2 on a usage or git error. A project with no gym folder or no table selects no lane (one line on stderr, exit 0).

**Reads.** `lane-inputs.toml` in the gym folder; the gym's `run.py` as text, for the lane names; `measure.not_built`, `measure.unit_manifests`; git. It never imports anything under the gym folder. **Writes** nothing.

---

## gym_init.py

Starts a gym: the smallest one the Foundry's tools can read. See [gym.md](gym.md).

| Command | What it does |
|---|---|
| `gym_init.py init [--lane G1] [--title "what the lane proves"]` | Writes the gym folder (`paths.gym`): `run.py`, `gym_kit.py`, `lane-inputs.toml`, `README.md`, one example lane with its prereg template and contract template, and an empty series file. A file that is already there is kept and named |
| `gym_init.py lane add G2 [--title "what the lane proves"]` | One more lane in a gym that has a `run.py`: its lane file, prereg template, contract template, empty series file, its line in `run.py`'s `LANES` and its entry in `lane-inputs.toml` |
| `gym_init.py check` | Reads the gym as the tools will and prints what is wrong. Exit 1 on any problem. A prereg that is still a template is a note, not a problem |

`init` and `lane add` write tracked files. So in the main checkout they are refused (exit 3, one line naming the freeze) while the manager's freeze is on or a counted run or sweep holds or waits for the shared resource. In a worktree, and in a project with no crew office yet, nothing is frozen. `check` only reads and always runs.

`lane add` never leaves a `run.py` that does not compile: if the file would not compile with the lane's line added to `LANES`, it leaves `run.py` alone and exits 1.

**Exit codes.** 0 done. 1 `check` found a problem, or `lane add` could not finish an edit. 2 a refusal of the request itself (a lane name the profile does not read, no gym to add to, no templates). 3 refused during a freeze.

It works on the checkout the script lies in (`FOUNDRY_ROOT` names another) and writes only under that checkout's gym folder. The templates are the files under `templates/gym` beside the script. It commits nothing.

The gym's own runner, `<paths.gym>/run.py`, is the project's file once scaffolded. Its commands and exit codes are in [gym.md](gym.md#the-runners-exit-codes).

---

## foundry_profile.py

Reads the project's profile for every other tool. See [profile.md](profile.md).

| Command | What it does |
|---|---|
| `foundry_profile.py show [KEY]` | The profile in force as JSON. KEY is one dotted key, for example `paths.office`. With a profile that cannot be read it prints the defaults, names each problem on stderr and exits 1 |
| `foundry_profile.py where` | The checkout, the main checkout and the profile file in use. Each problem with the file is a `PROBLEM` line, and exit 1 |
| `foundry_profile.py selftest` | Its own checks |

Every other tool loads the profile strictly: a profile that cannot be read ends the tool with `foundry: the profile cannot be read: <file>: <problem>` on stderr and exit 2, never a traceback and never the defaults in silence. The problems it names: a TOML error; a file that is not UTF-8; a key of the wrong kind (`paths = "x"` where a table belongs, a list written as text, a number in quotes); a `FOUNDRY_PROFILE` that names no file. `where`, `show`, `founder.py doctor` and the hooks load it without that check, because they must go on.

**Reads.** `.foundry/foundry.toml` in the checkout, else in the main checkout, else the defaults; the environment overrides. **Writes** nothing.

---

## The Foundry's own tests

For someone changing the tools, in the Foundry repository:

```
python tests/run_all.py --keep-going
```

It runs every tool's `selftest`, the two hooks' selftests, and every file under `tests/` and `hooks/test_*.py`, each in its own process, in temp folders only. Exit 1 when any failed; without `--keep-going` it stops at the first failure. CI runs the same line.

| File | What it checks |
|---|---|
| `tests/py311_syntax_test.py` | Every Python file in the repository is Python 3.11 syntax |
| `tests/office_wall_test.py` | The hand-in wall between builder and grader: the measure's files and a run's records, in a commit or in the branch's tree |
| `tests/board_edits_test.py` | The board's edit commands, the freeze marker, the stage-exit reader and the starter roadmap |
| `tests/board_guard_test.py` | The board's counted-run guard: held edits and their replay |
| `tests/board_ends_test.py` | An end the user set for a manager's slot (`ends` in `rota.days`) |
| `tests/sweep_test.py` | The sweep: its selftest, then a scratch shared resource, the freeze, a stop |
| `tests/gym_init_test.py` | `gym_init.py` and the gym it starts: the selftest, a dev run and counted runs through its `run.py` |
| `tests/test_flow_graph.py`, `tests/test_plan_flow.py` | The road graph asset and the plan charts, and the structure of the built pages |
