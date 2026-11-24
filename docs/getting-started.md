# Getting started

This page takes a project from nothing to a first working shift. The output shown was produced by running each command in a scratch project. It is trimmed, the project folder is written `~/myproject`, and the interpreter is written `python`.

- [Requirements](#requirements)
- [Install](#install)
- [Found the project: `founder.py init` and `doctor`](#found-the-project)
- [Start the gym: `gym_init.py init`](#start-the-gym)
- [A first day](#a-first-day)

## Requirements

- **Claude Code.** The manager's routine (starting sessions, bench sessions, timers, messages between sessions) is written for the desktop app. The tools themselves are plain Python and run anywhere.
- **Python 3.11 or newer.** The tools read TOML with `tomllib`. No packages are needed. `segno` is optional: with it, each badge also gets a QR plate drawn as an SVG.
- **git.** The crew works in worktrees of one repository, and every worktree finds the shared office through git's common dir.

## Install

```
git clone <the Shiro Foundry repository> shiro-foundry
python shiro-foundry/install.py --project ~/myproject --check
python shiro-foundry/install.py --project ~/myproject
```

`--check` (the same as `--dry-run`) prints what an install would write and writes nothing.

| Flag | Meaning |
|---|---|
| `--project DIR` | Required. The project's main checkout. |
| `--skills project\|user\|none` | Where the skills go. `project` (the default) is `DIR/.claude/skills/`. `user` is `~/.claude/skills/`, one copy for every project. `none` copies no skill. |
| `--tools-dir PATH` | Where the tools go inside the project. Default `scripts/foundry`. If you change it, set `tools = "<path>"` under `[paths]` in the profile; the installer reminds you. |
| `--hooks` | Also copy the two hooks to `DIR/.claude/hooks/`. It never edits `settings.json`: see [hooks.md](hooks.md). |
| `--force` | Replace a file that exists and differs. The old one is kept beside it as `<name>.bak-<date>`. |
| `--dry-run`, `--check` | Print the plan, write nothing. |

What it copies:

| From the Foundry | To the project |
|---|---|
| `tools/*.py` | `<tools-dir>/` |
| `profile/` (the templates, `profile/gym/` included) | `<tools-dir>/templates/` |
| `skills/*` | `.claude/skills/` (or `~/.claude/skills/`) |
| `hooks/*.py` except the `test_` files, only with `--hooks` | `.claude/hooks/` |

The installer copies files and does nothing else. It never runs git and deletes nothing. A file that exists and differs is kept and listed, unless you pass `--force`. It refuses (exit 2) on a Python older than 3.11, when `--project` is not a folder, and when `--project` is the Foundry repository itself.

Its last lines:

```
52 new, 0 replaced, 0 already current, 0 kept as they were
Hooks copied. To switch them on, add the block from .../hooks/settings.example.json to ~/myproject/.claude/settings.json yourself.

Next:
  python "~/myproject/scripts/foundry/founder.py" init --project "<name>"
  python "~/myproject/scripts/foundry/founder.py" doctor
```

## Found the project

Run these from the project's main checkout.

```
python scripts/foundry/founder.py init --project "My Project"
```

```
wrote   .foundry/foundry.toml: the profile; fill in the limits with the user
wrote   .foundry/rules.md: the rules file; replace each bracketed line or delete it
wrote   docs/ROADMAP.md: a starter roadmap in the shape the tools read
added   .gitignore: /out/foundry/, /out/flow/, /.claude/worktrees/, /out/sweeps/
wrote   docs/progress/state.json: the starter state (board.py init)

Next: `founder.py doctor`, then the goal and the requirements with the user (/foundry-founder found).
```

`init` never overwrites: a file that exists is kept and named. It git-ignores the office, the built pages, the sweep folders (`/out/sweeps/`) and the folder the crew's worktrees live in (`git.worktrees`); with `--gym`, the gym's run folders (`/out/gym/`) too.

The starter roadmap's first line is `<!-- STARTER ...`: its rows are examples. While that line is there, the new state takes no milestone and no decision from it, and the check does not compare the two. When the founder writes the real roadmap, that line goes, and two commands bring the state into line (section 1 below). Its options:

| Option | Meaning |
|---|---|
| `--project NAME` | The project's name, written into the profile. Without it, the main checkout's folder name. |
| `--resource NAME` | Name the one shared resource (a VM, a GPU, a device) in the profile. Leave it out when the crew shares nothing. |
| `--gym` | Also run `gym_init.py init` (see the next section). |

It creates no office folder. The office (`out/foundry/`) appears with the first badge.

Then check the install:

```
python scripts/foundry/founder.py doctor
```

```
ok      python 3.14.3 (...)
ok      profile ~/myproject/.foundry/foundry.toml
ok      tools: all 13 present in scripts/foundry
ok      skill foundry-founder (project)
ok      skill foundry-manager (project)
ok      skill foundry-employee (project)
ok      skill foundry-flow (project)
ok      skill foundry-bench (project)
ok      skill gym (project)
ok      paths.office (out/foundry) is outside git's view
ok      paths.flow_out (out/flow) is outside git's view
ok      state docs/progress/state.json
note    roadmap docs/ROADMAP.md is still the starter: the founder has not written it
note    no shared resource named: rq.py and the queue's freeze are off
note    hook graph_readonly.py is in .claude/hooks but .claude/settings.json does not run it
note    hook no_python_stdin.py is in .claude/hooks but .claude/settings.json does not run it
ok      segno is installed: badges get QR plates

doctor: 0 problem(s), 4 note(s)
```

`doctor` exits 1 when it printed a `PROBLEM` line. A `note` is not a problem. `doctor --selftest` also runs each tool's selftest. Run before `init`, the missing state and roadmap are PROBLEM lines; that is expected. The PROBLEM lines are explained in [troubleshooting.md](troubleshooting.md#doctors-problem-lines).

## Start the gym

The gym is the measure that decides what "done" means ([concepts.md](concepts.md#the-gym-in-one-page), [gym.md](gym.md)). `gym_init.py` writes the smallest one the tools can read, for the project's first grader to build on.

```
python scripts/foundry/gym_init.py init --lane G1 --title "the app starts and shows one screen"
```

```
wrote gym/run.py
wrote gym/lane-inputs.toml
wrote gym/README.md
wrote gym/gym_kit.py
wrote gym/lanes/g1_example.py
wrote gym/prereg/G1.json
wrote gym/contracts/G1-artifacts.md
wrote gym/series/G1.json

Next:
  python gym/run.py selftest
  python gym/run.py dev G1
  python ~/myproject/scripts/foundry/gym_init.py check
Then the builder writes the contract, and an independent grader the prereg and the lane (gym/README.md has the order of work).

Profile lines to set under [measure] in .foundry/foundry.toml:
  counted = 'python gym/run.py counted <lane>'
  dev = 'python gym/run.py dev <lane>'
  selftest = 'python gym/run.py selftest'

note: out/ is not git-ignored here. A run's folder is out/gym/<lane>/<run id>/, and a counted run needs a clean tree: add `out/` to .gitignore.
```

Do the three things it says:

1. Put the three lines under `[measure]` in `.foundry/foundry.toml`. `counted` is the command the manager queues and the sweep runs, with `<lane>` replaced. `dev` marks a job as a dev run in the queue. `selftest` is named in every builder's brief. `gym_init.py` prints them with `python`, or with the profile's `commands.python` when that is set; write the interpreter your crew should use.
2. Check `.gitignore`. `founder.py init` ignores the office, the built pages, the sweep folders (`/out/sweeps/`) and the worktrees folder, and `/out/gym/` with `--gym`. If you scaffolded the gym with `gym_init.py init` instead, add `/out/gym/` yourself: a counted run refuses a tree with any untracked path in it. Ignoring all of `out/` in one line does the same.
3. Run the checks:

```
python scripts/foundry/gym_init.py check
```

```
note    G1: its prereg is still a template (not registered): no counted run until the grader fills it
note    G1: its prereg pins no contract yet (contract.path is empty)
note    G1: its contract is still a draft
gym_init check: 1 lane(s) (G1), 0 problem(s), 3 note(s)
```

```
python gym/run.py dev G1
```

```
G1 dev 20261124-151438-0ae5: MEASURING (n=40) (stand-in artifacts) the prereg registers no bar or minimum n yet, so nothing can be decided
dry grade (not published): ~/myproject/out/gym/G1/20261124-151438-0ae5/dry-grade.json
```

The starter is a start, not a gym that decides anything. The prereg is a template, and `run.py` refuses a counted run on it:

```
python gym/run.py counted G1
```

```
refused: ~/myproject/gym/prereg/G1.json is still a template: the grader fills it, sets "status" to "registered" and commits it before the first counted run
```

Commit what you have so far (the tools, the skills, `.foundry/`, `docs/`, `gym/`, `.gitignore`).

## A first day

You type two slash commands. The agents run everything else. The commands below are the ones they run, so you can follow along, check their work, or do a step by hand.

| Section | Who | What |
|---|---|---|
| 1 | You, then the founder | `/foundry-founder found`: the badge, the roadmap, the road graph, the first shift, a decision for you |
| 2 | You, then the manager | `/foundry-manager start`: appoint and clock in |
| 3 | Manager | The board's check, the map, the round, usage |
| 4 | Manager | Hire by title, the checkpoint |
| 5 | Employee | Clock in, progress, a failure report, the journal, the hand-in, clock out |
| 6 | Manager | The next round: file the report, read the hand-in, set the block |
| 7 | You and the manager | A decision asked and answered |
| 8 | You and the manager | The journal's plan and your approval |
| 9 | Manager | The hand-off |

### 1. Found

In a session opened in the main checkout, type:

```
/foundry-founder found
```

The founder asks you for the goal, drafts the requirements and the roadmap, fills in the profile with your limits, seeds the road graph, plans the first shift and brings you a numbered list of decisions. It works through these commands.

**Its badge.** One founder at a time. The session id comes from the desktop app.

```
python scripts/foundry/office.py found --name founder --session local_<this session's id>
```

```
founded: FDR-1 (founder) holds the one founder badge
badge: FB1 ID:FDR-1 NAME:FOUNDER ROLE:FOUNDER KIND:SESSION SHIFT:START SLOT:SWING ISSUED:1795554887 SIG:VYKDEZS5CTPW444W
next: python ~/myproject/scripts/foundry/office.py clock-in --badge "FB1 ID:FDR-1 NAME:FOUNDER ... SIG:VYKDEZS5CTPW444W"
the founder hires no one: appoint a manager (office.py appoint), who hires the crew
```

```
python scripts/foundry/office.py clock-in --badge "FB1 ID:FDR-1 NAME:FOUNDER ROLE:FOUNDER KIND:SESSION SHIFT:START SLOT:SWING ISSUED:1795554887 SIG:VYKDEZS5CTPW444W"
```

```
FDR-1 founder clocked in at 15:14
```

The whole line is the badge. From here on it is written `"<the founder's line>"`.

**The roadmap.** The founder writes `docs/ROADMAP.md` with you: the goal, the stages, the milestones, the requirements, the decisions. The `<!-- STARTER` line goes with the examples. (This walkthrough keeps the starter's rows as if they were the project's own.) Then it checks that the tools can read it:

```
python scripts/foundry/flow.py selftest
```

```
NOTE the road graph is not seeded yet, so its links are guessed from the roadmap's prose
flow selftest: 6 requirements, 3 milestones, 2 decisions, 2 stages, 0 problems
```

A milestone or decision row that opens like a row and does not parse, and an id that stands in two rows, are each a FAIL line with the row's line number.

**The state follows the roadmap.** Now that the roadmap is the real one, `board.py check` names what the state lacks:

```
! docs/ROADMAP.md's milestone tables name M1, M2, M3, which the state's milestones lack: run python scripts/foundry/board.py milestone sync.
! docs/ROADMAP.md names the open decision(s) D2, which the register lacks: run python scripts/foundry/board.py decide adopt D2.
```

```
python scripts/foundry/board.py milestone sync
python scripts/foundry/board.py decide adopt D1
python scripts/foundry/board.py decide adopt D2
```

```
milestone sync: added M1, M2, M3 from docs/ROADMAP.md (planned; M1 Skeleton: the app starts and shows one screen [G1]; M2 Store: what the user makes is kept [G2]; M3 Ship: backups, the guide, the release)
D1 adopted from docs/ROADMAP.md (answered): Release channel (REL-01)
D2 adopted from docs/ROADMAP.md (open; it waits on the user): Storage format (DATA-01)
```

`milestone sync` lists every milestone the roadmap's tables name. `decide adopt` gives a decision of the roadmap's table its entry in the decision register, under the same number: answered where the roadmap says Decided, open otherwise. Both are run again whenever the roadmap changes: `milestone sync` also rewrites the title and lane of a planned milestone nothing has touched yet, `milestone sync --prune` removes such a one the roadmap no longer names, and `decide adopt D2 --refresh` reads an adopted row again.

**The road graph.** Seeded once from the roadmap's prose. Each link starts unconfirmed; the founder checks each one.

```
python scripts/foundry/flow.py graph seed --by "<the founder's line>"
```

```
graph edit 1 by FDR-1: seeded 7 nodes and 4 links from ROADMAP.md; each link is unconfirmed until graph confirm
commit docs/flow/road.graph.json and docs/flow/road.edits.jsonl with the map
```

```
python scripts/foundry/flow.py graph confirm M1 M2 --why "the store needs the app to start" --by "<the founder's line>"
```

```
graph edit 2 by FDR-1: confirmed M1.done → M2.after  [the store needs the app to start]
```

**The first shift.** Blocks go in from a JSON file. Each block has a `time`, a `title` and a `done_when`; the block that runs the counted gym carries `checkpoint`.

```json
[
 {"time": "1h", "title": "G1 contract and prereg", "done_when": "the contract is committed and the grader has pinned it"},
 {"time": "3h", "title": "M1: the app starts and shows one screen", "done_when": "dev run dry-graded GO by the G1 grader"},
 {"time": "1h", "title": "G1 counted run", "done_when": "G1 has a counted verdict", "checkpoint": "G1"}
]
```

```
python scripts/foundry/board.py shift blocks --file blocks.json
python scripts/foundry/board.py milestone set M1 --status in-progress
```

```
the shift start has 3 block(s), all pending
M1 is in-progress
```

**A decision for you.** Every question that is yours to answer gets a D-number. The roadmap's decisions table and the register share the numbers: D1 and D2 are the roadmap's, so a new question is D3.

```
python scripts/foundry/board.py decide ask --by FDR-1 --question "Backups: on every save, or once a day?" --options "on every save | once a day" --recommend "once a day: simpler" --needed-before M3
```

```
D3 filed (open; it waits on the user)
```

```
python scripts/foundry/board.py decide list --open
```

```
2 decision(s) open
  D3 open 2026-11-24T15:14 FDR-1: Backups: on every save, or once a day? [recommended: once a day: simpler] [needed before M3]
  D2 open 2026-11-24T15:14 roadmap: Storage format (DATA-01) [needed before M2 (DATA-01)]
```

A decision the founder writes into the roadmap's table first gets its register entry with `board.py decide adopt D<n>`, under the same number.

The founder commits the roadmap, the profile, the state, the map and the graph files, and tells you the list of decisions. You may answer now or later.

### 2. Appoint and clock in

In a new session in the main checkout, type:

```
/foundry-manager start
```

The manager appoints itself. There is one manager; a second appointment is refused while another manager is fresh.

```
python scripts/foundry/office.py appoint --name day-manager --session local_<this session's id>
```

```
appointed MGR-1 (day-manager) as the one manager
badge: FB1 ID:MGR-1 NAME:DAY-MANAGER ROLE:MANAGER KIND:SESSION SHIFT:START SLOT:SWING ISSUED:1795554909 SIG:MCZUFKVBQMW2NRYN
next: python ~/myproject/scripts/foundry/office.py clock-in --badge "FB1 ID:MGR-1 NAME:DAY-MANAGER ... SIG:MCZUFKVBQMW2NRYN"
```

```
python scripts/foundry/office.py clock-in --badge "<the manager's line>"
```

```
MGR-1 day-manager clocked in at 15:15; approximate finish 22:00
```

A manager's finish is the end of its slot. The slot here is `swing` because the scratch run happened in the afternoon.

### 3. The board's check and the map

```
python scripts/foundry/board.py check
```

```
My Project progress map, shift-start check at 2026-11-24 15:15
  state updated 2026-11-24T15:15:08-06:00 (0 h ago)
  tree main bb6d8bc clean; last commit 2026-11-24 15:15 "founding: first shift, D3, the road graph"
  shift: No shift planned yet
  next block: 1h G1 contract and prereg
       done when: the contract is committed and the grader has pinned it
  queue: 0 shift(s) after this one
  blockers: 0
  decisions open: 2
    D3 Backups: on every save, or once a day? (needed before M3)
    D2 Storage format (DATA-01) (needed before M2 (DATA-01))
  rota: swing slot 14:00-22:00; on the rota: nothing; crew_max 4; heavy work asks first
  crew (2; python scripts/foundry/office.py roster for the full list):
    FDR-1 founder founder: UP 0%; found the project: the roadmap, the profile, audits, pushes and decisions
    MGR-1 day-manager manager: UP 0%; manage the slot: rota, crew, checkpoints, failures, the map
  checkpoints: 0
  failures open or planned: 0; reported, not triaged: 0
  road to 1.0 (docs/ROADMAP.md): P0 met 1 of 5, 1 part-way, 2 planned, 1 open; R0 0/3, 1.0 1/6
  needs attention: 2
    [the user] D3 waits on the user (needed before M3): Backups: on every save, or once a day?
    [the user] D2 waits on the user (needed before M2 (DATA-01)): Storage format (DATA-01)
  WARNINGS (1):
    ! G1 has a prereg but no row in state.lanes; add it with its checkpoint.
  map: docs/progress-map.html (rebuilt)
```

`check` exits 1 when a warning is present. It also rebuilds the map, `docs/progress-map.html`: open it in a browser (`python scripts/foundry/board.py open` builds and opens it). What needs you is first on the page. The manager fixes or explains every warning before work starts.

Then the round, which is what every later wake-up starts with:

```
python scripts/foundry/office.py round --by "<the manager's line>"
```

```
Round at 2026-11-24 15:15 (~/myproject/out/foundry); manager MGR-1
  needs you (3):
    1. [usage] no usage point in the last 4 hours (none is recorded): read the plan's weekly usage and record it, `python ~/myproject/scripts/foundry/board.py usage <percent>`
    2. [decision] D3 waits on the user (needed before M3): Backups: on every save, or once a day?: ask the user, in the open, with the options
    3. [decision] D2 waits on the user (needed before M2 (DATA-01)): Storage format (DATA-01): ask the user, in the open, with the options
  usage: no usage point recorded; the stop is 80%
  crew: nobody hired or on the clock
  posted MGR-1's heartbeat
first: no usage point in the last 4 hours ...
```

No tool reads your plan's usage. The manager reads it in the app and records it:

```
python scripts/foundry/board.py usage 12
```

```
usage 12% recorded (1 point(s) this week)
```

### 4. Hire by title

Each hire is one badge, one title, one job and one set of files. `--kind session` is a session you can open and steer. `--kind temp` is a subagent inside the manager's turn.

```
python scripts/foundry/office.py hire --by "<the manager's line>" --name m1-builder --title builder --kind session --job "M1: the app starts and shows one screen; write the G1 contract first" --eta 3h --lane G1 --files "src/, gym/contracts/G1-artifacts.md" --done-when "the contract is committed; the app starts; a dev run is dry-graded GO by the G1 grader"
```

```
hired EMP-01 m1-builder (builder, session); crew 1 of 4 on start
badge: FB1 ID:EMP-01 NAME:M1-BUILDER ROLE:BUILDER KIND:SESSION SHIFT:START SLOT:SWING ISSUED:1795554920 SIG:6TNBQE54VOAJ33GL

--- brief (paste into start_session's prompt or the Agent prompt) ---
You are a My Project employee, badge EMP-01 (m1-builder, builder), hired by the manager MGR-1.
First invoke the foundry-employee skill and follow it. Then clock in before any other work:
    python ~/myproject/scripts/foundry/office.py clock-in --badge "FB1 ID:EMP-01 NAME:M1-BUILDER ... SIG:6TNBQE54VOAJ33GL"

Job: M1: the app starts and shows one screen; write the G1 contract first
Done when: the contract is committed; the app starts; a dev run is dry-graded GO by the G1 grader
Your card (builder): role builder; hired as session or temp
    Does: builds what the job names, with the tests that show it works
    May write: the files its badge owns, in its own worktree or on its own branch
    Hands in: its commits, the tests it ran with their results, and a report through handin
Lane: G1
Files you own: src/, gym/contracts/G1-artifacts.md (touch nothing else; git add -- <paths> only; no push)
...
```

The brief goes on with the branch rule, the tests to run, and the exact `progress`, `fail`, `handin` and `clock-out` commands. The manager finishes it, starts the session with it, and records the session:

```
python scripts/foundry/office.py assign EMP-01 --session local_<the new session's id>
```

```
EMP-01 is session local_<the new session's id>
```

The grader is its own session, hired for a lane. A grader as a temp is refused:

```
python scripts/foundry/office.py hire --by "<the manager's line>" --name g1-grader --role grader --kind temp --job "G1 grader" --eta 2h --lane G1
```

```
refused: a GRADER is its own session: a subagent of the manager is not independent of the build
```

```
python scripts/foundry/office.py hire --by "<the manager's line>" --name g1-grader --title grader --kind session --job "G1 grader: pin the contract, write the prereg and the lane, dry-grade the dev run, grade the counted run" --eta 3h --lane G1 --files "gym/prereg/G1.json, gym/lanes/g1_example.py" --done-when "prereg registered; the counted run graded with a verdict word"
```

```
hired EMP-02 g1-grader (grader, session); crew 2 of 4 on start
```

Then the checkpoint: the lane, its milestone, the builder and the grader, and the block that runs the counted run.

```
python scripts/foundry/board.py checkpoint add --lane G1 --milestone M1 --builder EMP-01 --grader EMP-02 --block 3 --note "contract and prereg to come"
```

```
checkpoint G1 set for M1, on block 3
wrote docs/progress-map.html; 0 warning(s)
```

The warning from the check is gone.

### 5. An employee's day

The builder's session starts in its own worktree (the brief names `.claude/worktrees`). It copies every command from its brief. The tools reach the one office from any worktree.

**Clock in.**

```
python ~/myproject/scripts/foundry/office.py clock-in --badge "<the builder's line>"
```

```
EMP-01 m1-builder clocked in at 15:15; approximate finish 18:15
```

A line that was changed or mistyped is refused:

```
refused: badge EMP-09: the signature does not match (a changed or mistyped line)
```

**Its own record.** After a `/clear` or a compaction, `me` gives the brief back. It writes nothing.

```
python ~/myproject/scripts/foundry/office.py me --badge "<the builder's line>"
```

```
EMP-01 m1-builder (builder, session): UP 0% finish ~18:15; last heard 15:15; session local_...
manager on the clock: MGR-1 day-manager (UP), session local_...
your branch here: claude/m1-builder in ~/myproject/.claude/worktrees/m1-builder (report this name)
no review merged to main since your clock-in (15:15) names G1, M1
no freeze on the main checkout

--- your brief as the roster has it now ---
...
```

**Progress.** `--pct` is the honest share done. `--eta` is the time left (`50m`, `1h30m`; a bare number is minutes) or a clock time (`17:50`).

```
python ~/myproject/scripts/foundry/office.py progress --badge "<the builder's line>" --pct 20 --eta 2h --note "writing the G1 contract"
```

```
EMP-01 at 20%, approximate finish 17:15
```

**A failure.** A failing test, a run that did not pass, a blocking question or a bug found and left is reported. It gets a report number, `R<seq>`.

```
python ~/myproject/scripts/foundry/office.py fail --badge "<the builder's line>" --what "the app exits 1 when the config folder is missing" --lane G1 --plan "create the folder at start; add a test"
```

```
reported R7 by EMP-01: the app exits 1 when the config folder is missing
```

**The journal.** A hole in a skill, a tool or the brief is logged when it is noticed.

```
python ~/myproject/scripts/foundry/journal.py add --badge "<the builder's line>" --kind hole --what "the brief names two different interpreters for the two selftests" --fix "print commands.python in both" --where "office.py hire"
```

```
J1 logged by EMP-01 (hole): the brief names two different interpreters for the two selftests
```

**The hand-in.** Run in the worktree, with the work committed. Here the builder also committed a change to `README.md`, which its badge does not own:

```
python ~/myproject/scripts/foundry/office.py handin --badge "<the builder's line>" --file out/report.md
```

```
hand-in check for EMP-01: NOT READY (1 problem(s), 0 warning(s))
  claude/m1-builder at 11b58e53 in ~/myproject/.claude/worktrees/m1-builder; 1 commit(s), 2 file(s)
  PROBLEM  1 changed file(s) outside the files your badge owns (src/, gym/contracts/G1-artifacts.md): README.md: take them out, or ask the manager to widen the badge (office.py amend --add-files). If your branch was cut from a branch other than main, pass --base <that branch>
  written: ~/myproject/out/foundry/handins/EMP-01.md
  fix the problems and run it again; then clock out with the same commits
```

`handin` exits 1 on NOT READY. After the stray file is taken out of the commit:

```
hand-in check for EMP-01: READY (0 problem(s), 0 warning(s))
  claude/m1-builder at d1b7df33 in ~/myproject/.claude/worktrees/m1-builder; 1 commit(s), 1 file(s)
  written: ~/myproject/out/foundry/handins/EMP-01.md
  then: clock-out --result … --commits d1b7df33
```

**Clock out.** `--result` is `done`, `partial`, `failed` or `handed-off`.

```
python ~/myproject/scripts/foundry/office.py clock-out --badge "<the builder's line>" --result partial --note "the app starts; config-folder fix reported as R7" --commits d1b7df33
```

```
EMP-01 m1-builder clocked out at 15:15: partial (0.0 h)
```

The hand-in file the manager reads:

```markdown
# Hand-in EMP-01 m1-builder (builder): READY

- checked 2026-11-24 15:15 Central Standard Time by `office.py handin`: 0 problem(s), 0 warning(s)
- worktree: ~/myproject/.claude/worktrees/m1-builder
- branch: claude/m1-builder at d1b7df33, forked from main at dcab7008
- commits (1): d1b7df33
- files changed (1): src/app.py
- job: M1: the app starts and shows one screen; write the G1 contract first
- done when: the contract is committed; the app starts; a dev run is dry-graded GO by the G1 grader

## The employee's report

# M1 hand-in
...
```

### 6. The manager's next round

```
python scripts/foundry/office.py round --by "<the manager's line>"
```

```
Round at 2026-11-24 15:15 (~/myproject/out/foundry); manager MGR-1
  needs you (5):
    1. [decision] D3 waits on the user (needed before M3): ...: ask the user, in the open, with the options
    2. [decision] D2 waits on the user (needed before M2 (DATA-01)): ...: ask the user, in the open, with the options
    3. [report] R7 from EMP-01 is not filed (G1: the app exits 1 when the config folder is missing): file it, `python ~/myproject/scripts/foundry/board.py fail --from R7 --what "..."`
    4. [handin] a new hand-in, EMP-01.md (Hand-in EMP-01 m1-builder (builder): READY; written 15:15): read it (~/myproject/out/foundry/handins/EMP-01.md), then merge its commits or send it back
    5. [crew] EMP-02 g1-grader (grader) is a session badge with no session: start or re-badge a bench and record it, `python ~/myproject/scripts/foundry/office.py assign EMP-02 --session local_...`, or clock it out
  usage: 12% at 15:15 (1 min ago); the stop is 80%
  crew (1):
    EMP-02 g1-grader grader session: HIRED 0% no estimate; heard —; no session
  posted MGR-1's heartbeat; marked seen: EMP-01.md
first: D3 waits on the user ...
```

The manager acts on each line. It files the report as a numbered failure with a plan and an owner:

```
python scripts/foundry/board.py fail --what "the app exits 1 when the config folder is missing" --lane G1 --plan "create the folder at start; add a test" --owner "EMP-01 / the next slot" --from R7
```

```
F001 filed (planned)
```

It reads the hand-in, checks the commit, and merges it (the manager skill's `references/merge.md` is the routine). It sets the block:

```
python scripts/foundry/board.py block 1 partial --note "the contract is not written yet"
```

```
block 1 (1h) is partial
```

### 7. A decision asked and answered

The manager asks you the open decisions together, each with its options and the recommendation. You answer D2 in the chat. The manager records your words as you typed them:

```
python scripts/foundry/board.py decide answer D2 --words "One file. Keep it simple until someone needs more."
```

```
D2 answered
wrote docs/progress-map.html; 1 warning(s)
  ! The register and the roadmap disagree on whether a decision is answered: D2 (docs/ROADMAP.md: open; the register: answered). Record the answer (decide answer) or correct the roadmap's row.
```

The warning is the next step. The roadmap's decisions table still says `Open` for D2. The roadmap is the founder's file, so the manager names D2 in its hand-off, and the founder changes the row's **Where it stands** to `**Decided:** one file`. The warning then stops.

```
python scripts/foundry/board.py decide list
```

```
3 decision(s), 1 open
  D3 open 2026-11-24T15:14 FDR-1: Backups: on every save, or once a day? [recommended: once a day: simpler] [needed before M3]
  D2 answered 2026-11-24T15:14 roadmap: Storage format (DATA-01) -> One file. Keep it simple until someone needs more.
  D1 answered 2026-11-24T15:14 roadmap: Release channel (REL-01) -> Decided: one stable channel
```

An empty `--words` is refused. Why the words are kept verbatim is in [concepts.md](concepts.md#the-users-own-words).

### 8. The journal's plan and your approval

An hour before the slot ends, the manager brings you the journal's plan: what the shift found wrong with its own skills, tools and briefs, and a fix for each.

```
python scripts/foundry/journal.py due
```

```
shift journal OPEN: the plan is due at 21:00, an hour before the end at 22:00 (the swing slot's end); in 5.7 h
  no plan yet: J1
```

`ready` refuses while an entry has no plan:

```
python scripts/foundry/journal.py ready --by "<the manager's line>"
```

```
refused: J1 has no plan: plan each (journal.py plan J.. --fix ...) or close it (set --status covered|dropped|left|fixed), then run ready again
```

```
python scripts/foundry/journal.py plan --by "<the manager's line>" J1 --fix "office.py prints commands.python for both selftest lines" --files "scripts/foundry/office.py" --owner "the next slot's fixer"
python scripts/foundry/journal.py ready --by "<the manager's line>"
```

```
planned J1: office.py prints commands.python for both selftest lines
plan ready at 15:16 (on time): ~/myproject/out/foundry/journal/plan-20261124-1516-MGR-1.md
  1 for the user's approval: J1
  ask the user now, with the file; then: journal.py approve --by "<your line>" --words "<their own words>"
```

The manager shows you the plan file. You approve in your own words, all of it or part (`--only J1,J2`, `--except J4`). Only approved fixes are built.

```
python scripts/foundry/journal.py approve --by "<the manager's line>" --words "Yes, fix J1 next slot."
```

```
approved by the user ('Yes, fix J1 next slot.'): J1
```

### 9. The hand-off

You type `/foundry-manager shift-change`, or the manager's hand-off timer fires. The manager closes the slot.

```
python scripts/foundry/office.py end-shift --by "<the manager's line>" --out crew.json
```

```
end of slot swing (14:00-22:00) by MGR-1; temps clocked out: none
  the log entry's crew field:
[
 "EMP-01 m1-builder (builder, local_...): partial, 0.0 h",
 "EMP-02 g1-grader (grader): on the clock 0%, 0.0 h"
]
  wrote the crew list to crew.json
then: clock MGR-1 out (clock-out --badge ... --result done|handed-off) after the hand-off entry is written
```

The log entry, the rota entry and Now:

```
python scripts/foundry/board.py log add --by MGR-1 --title "Swing: M1 skeleton started" --slot swing --done "the app starts (d1b7df33) | D2 answered" --not-done "the G1 contract | the grader has no session yet | the roadmap's D2 row (the founder's)" --next "start the grader; write the contract" --crew-file crew.json
python scripts/foundry/board.py rota set --date 2026-11-24 --slot swing --shift start --manager MGR-1
python scripts/foundry/board.py now --headline "M1 skeleton in work" --position "block 1 of 3: the contract is next" --tree auto
```

```
log entry added (2026-11-24 15:16, swing slot): Swing: M1 skeleton started
rota 2026-11-24 swing: shift start, manager MGR-1
now updated (headline, position, tree ac9e22a)
```

The hand-off brief for the next manager:

```
python scripts/foundry/office.py handoff --by "<the manager's line>"
```

```
~/myproject/out/foundry/briefs/handoff-swing-20261124.md
hand-off brief for the swing slot written by MGR-1; fill its three hand-written sections and the benches line before the next manager reads it
```

The brief holds Now, the shift's blocks, who is on the clock, the open failures and decisions, the freeze, the journal and usage, all read from the office and the state. Three sections are left for the manager to write by hand: your words this slot (quoted, with the time), what was promised to the crew, and the background jobs the session started.

The manager commits the state and the map, then clocks out:

```
python scripts/foundry/office.py clock-out --badge "<the manager's line>" --result handed-off --note "hand-off written"
```

```
MGR-1 day-manager clocked out at 15:16: handed-off (0.0 h)
```

The next manager is a fresh session. It knows only what was written down: the newest log entry, Now, the notes, the blockers, the crew, the open decisions and the hand-off brief.

## Where to go next

- The ideas behind this walkthrough: [concepts.md](concepts.md).
- A real measure in place of the starter: [gym.md](gym.md).
- A shared VM or GPU: [profile.md](profile.md#worked-examples) and `rq.py` in [tools.md](tools.md#rqpy).
- The pages you can open in a browser: [charts.md](charts.md).
- A command refused something: [troubleshooting.md](troubleshooting.md).
