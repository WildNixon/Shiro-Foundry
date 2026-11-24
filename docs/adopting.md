# Adopting the Foundry

Two cases:

- [An existing project that has never used it](#an-existing-project).
- [A project that already runs the older per-project copies of these tools](#moving-from-the-older-per-project-tools).

A new, empty project is the plain path in [getting-started.md](getting-started.md).

## An existing project

The Foundry adds files beside what you have. It rewrites nothing of yours.

### 1. Install, and look first

```
python shiro-foundry/install.py --project ~/myproject --check
python shiro-foundry/install.py --project ~/myproject
```

`--check` lists what would be written. The installer keeps any file that exists and differs, unless you pass `--force`. If your project already uses `scripts/foundry/` for something else, pass `--tools-dir <another path>` and set `paths.tools` in the profile to match.

### 2. `founder.py init` keeps what exists

```
python scripts/foundry/founder.py init --project "My Project"
```

In a project that already has these files, it says so and leaves them:

```
kept    .foundry/foundry.toml (it exists)
kept    .foundry/rules.md (it exists)
kept    docs/ROADMAP.md (it exists)
kept    docs/progress/state.json (it exists)
```

So a roadmap you already keep at `docs/ROADMAP.md` is not replaced. It adds the git-ignore lines for the office and the built pages if they are missing.

It also git-ignores the folder the crew's worktrees live in (`git.worktrees`), and `founder.py doctor` makes it a PROBLEM when that folder is not ignored.

When the state is new and your own roadmap is already there, the state starts from it: every milestone the roadmap's tables name is listed as `planned`, and every decision its table names gets a register entry under the same id (answered where the roadmap says Decided, else open). A roadmap that is still the starter `init` wrote (first line `<!-- STARTER`) gives the state nothing: its rows are examples.

### 3. Point the profile at your layout

Every path can be changed in `.foundry/foundry.toml`. The keys that most often differ in an existing project ([profile.md](profile.md) has them all):

| If your project... | Set |
|---|---|
| keeps its roadmap elsewhere | `paths.roadmap` |
| already has a `gym/` folder that means something else | `paths.gym`, and the `gym/...` paths in `measure.grader_owned` and `measure.records` |
| already uses `out/` for something that is not git-ignored | `paths.office` and `paths.flow_out`, to folders that are git-ignored |
| has a main branch that is not `main` | `main_branch` |
| has a test command | `commands.test`: every builder's brief names it |
| has a check every change to shipped code must pass | `measure.handin_check` and `measure.handin_check_paths` |
| has vendored code nobody should own by accident | `measure.vendored_paths` |
| names requirements, milestones or stages its own way | the `[roadmap]` keys, and `measure.lane_pattern` |
| must run Python by a full path | `commands.python` |

Then:

```
python scripts/foundry/foundry_profile.py where
python scripts/foundry/founder.py doctor
```

Fix every PROBLEM line before going on ([troubleshooting.md](troubleshooting.md#doctors-problem-lines)).

### 4. Bring the roadmap into the shape the tools read

The tools read the roadmap's tables by the shape of each row ([charts.md](charts.md#the-roadmaps-tables)). Prose and headings can stay as they are. What must exist, as table rows:

- requirement rows: id, tier, status, where, note;
- milestone rows: id, theme, Closes, Why here;
- stage rows, with each stage's exit as requirement ids;
- a decisions table, if decisions gate work.

```
python scripts/foundry/flow.py selftest
python scripts/foundry/flow.py edges
```

`selftest` prints a FAIL line for each row that does not parse, and `edges` prints the graph as it was read.

Once the tables parse, bring the state into line with them. `board.py check` names the command for each thing the state lacks:

```
python scripts/foundry/board.py milestone sync
python scripts/foundry/board.py decide adopt D4
```

`milestone sync` adds every milestone the roadmap names and the state lacks, and rewrites the title and lane of a planned one nothing has touched yet; `milestone sync --prune` removes such a one the roadmap no longer names. `decide adopt` gives a decision of the roadmap's table its register entry under the same id, and `decide adopt D4 --refresh` reads an adopted row again after you rewrote it. A milestone that work has touched, and a decision someone answered through the register, are never rewritten.

If your decisions are not numbered `D1`, `D2`, set `roadmap.decision_id`: every decision command goes by it. Where the pattern is not a prefix and a number, `board.py decide ask` takes `--id <id>`.

This is the founder's work, done with you: type `/foundry-founder found` and the founder reads the project's README, its build and test commands and its open issues first, then drafts the requirements and the roadmap as numbered decisions for you. Nothing is added to or cut from the roadmap without your answer.

### 5. Start the gym on one thing

A project with code already has behaviour worth measuring. Start with one lane for the milestone the first shift works toward:

```
python scripts/foundry/gym_init.py init --lane G1 --title "what the lane proves"
```

If the project already has a measure with its own runner, keep it. The board needs only the series file's shape ([gym.md](gym.md#the-series-record)) under `<paths.gym>/series/`, and `measure.counted` naming the command of a counted run.

### 6. Write the rules file from what the project already knows

`.foundry/rules.md` is where the project's own lessons go: which interpreter, what the shell cannot do, what needs your word every time, the merge gate ([profile.md](profile.md#foundryrulesmd)). An existing project has these already, in its README, its CI config and its contributors' heads. Write them down by situation, and delete the outline's sections you do not need.

### 7. A small first shift

Keep `crew_max` low, plan one milestone, and run one slot through to its hand-off before planning a push. The first day in [getting-started.md](getting-started.md#a-first-day) is the same from here.

Commit the profile, the rules file, the state, the map and the tools by path. The office (`out/foundry/`) is never committed.

## Moving from the older per-project tools

These tools were first written inside two projects, each with its own copy: Glasswing, an operating system build, and Shiro, an AI fleet. The Foundry is their project-neutral form. A project that runs the older copies moves over by writing a profile, not by rewriting its records.

The names below are the older copies' names as the OS build had them. Check them against your own copy's docstrings before you rely on them.

### What changed its name

| Older copy | Foundry |
|---|---|
| `pm.py` (the crew office) | `office.py` |
| `progress.py` (the progress map) | `board.py` |
| `vmq.py` (the VM queue) | `rq.py` |
| `journal.py`, `flow.py`, `flow_graph.py`, `flow_page.py`, `plan_flow.py`, `lanes_for.py` | the same names |
| the project's own sweep scripts | `sweep.py` |
| the project's own system-graph and plan readers, its VM command wrapper, host watchdogs | not carried over; they stay the project's own |

The skills are `foundry-founder`, `foundry-manager`, `foundry-employee`, `foundry-flow`, `foundry-bench` and `gym`. A brief the Foundry prints tells a hire to load the skill the profile's `[skills]` table names, so a project that keeps its own skill names for a while can say so there.

### The profile keys that keep old records valid

| Key | Set it to | What it keeps |
|---|---|---|
| `badge_prefix` | The older badges' first word (the OS build's was `GB1`) | Old badge lines verify. A badge's signature covers the whole line, the prefix included, and the signing is unchanged, so with the same key file and the same prefix an old line is still genuine |
| `paths.office` | The older office folder (the OS build's was `out/pm`) | The signing key (`badge_key.json`), the roster, the time clock with its report numbers (`R<seq>`), the hand-ins and the journal (`J<n>`) stay where they are and keep their ids |
| `paths.state`, `paths.map`, `paths.roadmap`, `paths.flow`, `paths.flow_out`, `paths.gym` | Where the project keeps each today | The state, the road graph and its signed log, the plans, the series files are read in place |
| `roadmap.requirement_id`, `roadmap.tiers`, `roadmap.stage_id`, `roadmap.milestone_id`, `roadmap.decision_id`, `roadmap.goal`, `roadmap.late_stages`, `roadmap.block_id` | The project's own id shapes | The roadmap parses as it is, and the road graph's node ids stay valid |
| `measure.lane_pattern` | How the project's lanes are named | Lane names in text are still recognised. The default is `\bG(?:X\d+[a-z]?\|L\d+\|\d+)\b` |
| `crew` and `[crews.<name>]` | This crew's name, and each other crew's lessons file | Lessons keep carrying between the two crews |
| `resource.seat_env` | The variable the project's scripts already read their seat from | Queued commands need no change |
| `resource.prepare` | The cleaning step the old queue ran before each job | The old queue's built-in step becomes a line the project owns |
| `resource.exclusive` | A regex for the jobs that could not share the machine | The old queue's built-in list becomes a pattern the project owns |

After writing the profile, check that the Foundry sees the old office:

```
python scripts/foundry/foundry_profile.py show paths.office
python scripts/foundry/office.py roster
python scripts/foundry/office.py verify "<an old badge line>"
python scripts/foundry/flow.py graph verify
python scripts/foundry/board.py check --no-build
```

None of these writes anything.

### The queue: renamed files and flags

`rq.py` does not read the old queue's files. Its files have new names in the same office folder:

| Older file | Foundry file |
|---|---|
| `vm.queue.json` | `rq.queue.json` |
| `vm.lock`, `vm.lock.<L>` | `rq.lock`, `rq.lock.<S>` |
| `vm.last`, `vm.last.<L>` | `rq.last`, `rq.last.<S>` |
| `vm.lanes` (one VM dir a line) | `rq.seats` (one seat a line), or `resource.seats` in the profile |
| `vm.requeue.json`, `vm.released.json` | `rq.requeue.json`, `rq.released.json` |

What the older queue called a lane (one VM dir) is a **seat**. "Lane" now means only a gym lane.

| Older flag | Foundry flag |
|---|---|
| `pm.py hire --vmq`, `amend --vmq` | `office.py hire --rq`, `amend --rq` |
| `pm.py hire --vmdir DIR`, `amend --vmdir DIR` | `office.py hire --seat NAME`, `amend --seat NAME` |
| `vmq.py run --crates "a b"`, `release --crates` | `rq.py run --touched "a b"`, `release --touched` |
| `vmq.py take --lane L`, `force-release --lane L` | `rq.py take --seat NAME`, `force-release --seat NAME` |
| `vmq.py run --gui` | `rq.py run --exclusive` |
| `vmq.py status --vm` | `rq.py status --resource`, which runs the profile's `resource.status` command |

Two more differences to know:

- `rq.py --max` and `--wait` refuse a bare number. Write a unit: `90m`, `2h`. So do `office.py freeze on --max` and `sweep.py --max-per-lane`. Only `office.py --eta` still reads a bare number, as minutes.
- A profile that cannot be read stops every tool (exit 2) instead of falling back to the defaults: a TOML error, a file that is not UTF-8, a key of the wrong kind, or a `FOUNDRY_PROFILE` that names no file. Run `foundry_profile.py where` after writing it.
- The roster records a queue badge's seat as `rq`. A badge hired by the older tool carries the older word, which the Foundry reads as a seat's name, not as the queue. So do not carry a queue badge across the move: have it clock out, and hire it again.

With nothing in the queue, there is nothing to convert: `rq.py` starts with an empty queue. To keep each seat's last release note, copy `vm.last` to `rq.last` (and `vm.last.<L>` to `rq.last.<S>`). To keep a seat list that was in `vm.lanes`, put it in `resource.seats`.

### The lane-inputs table: `crates` becomes `units`

In `<paths.gym>/lane-inputs.toml`, the key `crates` is now `units`, wherever it stands: in a lane and in a group. A build unit is declared as `[units.<name>]` with `dir` and `needs`.

```toml
# before
[lanes.G5]
crates = ["app", "core"]

# after
[lanes.G5]
units = ["app", "core"]
```

If the units came from build manifests, name the manifests in the profile: `measure.unit_manifests` takes globs of TOML manifest files, and the folder of each becomes a unit named by its `[package]` name. What counts as not built into a lane (tests, benches, examples, Markdown) is `measure.not_built`.

Then:

```
python scripts/foundry/lanes_for.py check
```

It compares the table with the lanes in the gym's `run.py`, both ways, and names every group and unit a lane lists that does not exist.

### Environment variables

The older copies had their own override variables. The Foundry's are `FOUNDRY_ROOT`, `FOUNDRY_MAIN`, `FOUNDRY_PROFILE` and `FOUNDRY_<SECTION>_<KEY>` ([profile.md](profile.md#environment-overrides)). A test or a wrapper that set an older variable must set the new one, for example `FOUNDRY_PATHS_OFFICE` for the office folder.

### Do it at a slot boundary, with nothing counted in the queue

The move changes which tool reads the office. Do it when the least is in flight.

1. **Pick a slot boundary.** The outgoing manager finishes its hand-off with the older tools and clocks out. No manager is on the clock during the move.
2. **Nothing counted in the queue.** No counted run or sweep is waiting or running, and its records are committed. A counted run samples the tree; replacing the tools under it voids it.
3. **The queue is empty and every seat is free.** Check with the older queue's `status`. `rq.py` will not see an old hold.
4. **The crew is clocked out**, or at least every badge that reaches the shared resource through the queue is.
5. **Install** (`install.py --project <dir>`), write the profile with the keys above, and run `foundry_profile.py where`, `founder.py doctor` and the read-only checks listed earlier.
6. **Rename in the lane-inputs table** (`crates` to `units`) and run `lanes_for.py check`.
7. **Replace the hooks** if they are on. The two hook files keep their names (`graph_readonly.py`, `no_python_stdin.py`), so a settings block that already points at `.claude/hooks/` needs no change. `install.py --project <dir> --hooks --force` copies the Foundry's versions over the old ones and keeps each old file as a `.bak`. The Foundry's `graph_readonly.py` takes its protected files from the profile ([hooks.md](hooks.md)). Changing the harness's hooks is your own step.
8. **Commit** the tools, the skills, the profile and the table as one change.
9. **Start the next slot with the Foundry's skill**: `/foundry-manager start`. The new manager is appointed by `office.py appoint` into the same office, and the hand-off it reads is the same state file.

Keep the older copies in the repository's history, not beside the new ones: two tools writing one office is how a roster goes wrong.

Both source projects still run their own copies at the time of this release. `HOLES.md` in this folder says what is not yet verified about the general form.
