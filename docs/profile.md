# The profile

A project keeps one small file, `.foundry/foundry.toml`, in its main checkout. It names the project, the crew, the paths and the limits. Every tool reads it through `foundry_profile.py` and falls back to a default for whatever the file leaves out. A project with no profile at all still works on the defaults.

`founder.py init` writes a commented starter. The founder fills it in with you: every limit in it is your number.

```
python scripts/foundry/foundry_profile.py show              # the profile in force, as JSON
python scripts/foundry/foundry_profile.py show paths.office # one dotted key
python scripts/foundry/foundry_profile.py where             # the checkout, the main checkout, the file in use
```

**A profile that cannot be read stops every tool.** It is never replaced by the defaults in silence: the tool prints `foundry: the profile cannot be read: ...` on stderr and exits 2, and nothing is done. Four things are named this way: a TOML error; a file that is not UTF-8; a key of the wrong kind (`paths = "x"` where the `[paths]` table belongs, a list written as text, a number in quotes); and a `FOUNDRY_PROFILE` that names no file. `foundry_profile.py where` and `founder.py doctor` still run, and print a `PROBLEM` line for each. `foundry_profile.py show` prints the defaults, names the problems on stderr and exits 1. Run `where` after every edit. See [troubleshooting.md](troubleshooting.md#the-profile-does-not-parse).

A worktree reads its own `.foundry/foundry.toml` when it has one, else the main checkout's.

- [Top-level keys](#top-level-keys)
- [`[commands]`](#commands)
- [`[paths]`](#paths)
- [`[skills]`](#skills)
- [`[slots]`](#slots)
- [`[limits]`](#limits)
- [`[resource]`](#resource)
- [`[measure]`](#measure)
- [`[roadmap]`](#roadmap)
- [`[board]`, `[git]`, `[hooks]`, `[crews]`](#board-git-hooks-crews)
- [Titles, flagged titles and models](#titles-flagged-titles-and-models)
- [Environment overrides](#environment-overrides)
- [`.foundry/rules.md`](#foundryrulesmd)
- [Worked examples](#worked-examples)

## Top-level keys

| Key | Default | Read by | What it changes |
|---|---|---|---|
| `project` | `""`: the main checkout's folder name | `board.py`, `flow.py`, `plan_flow.py`, `founder.py`, `office.py` | The project's name on the pages and in every brief |
| `crew` | `""`: made from `project`, lower case, dashes | `journal.py`, `office.py` | This crew's name when lessons carry between crews |
| `badge_prefix` | `"FB1"` | `office.py`; named in messages by `flow_graph.py`, `plan_flow.py` and the graph hook | The first word of every badge line. A line with another prefix does not verify |
| `main_branch` | `"main"` | `office.py`, `sweep.py` | The base `handin` compares a branch against; the branch named in briefs |

## `[commands]`

| Key | Default | Read by | What it changes |
|---|---|---|---|
| `python` | `""`: the interpreter running the tool | `office.py` (briefs), `board.py` (printed commands) | The interpreter that briefs and help text name. Set a full path when the bare `python` on the host is not the one you want |
| `test` | `""` | `office.py` | The project's own test command. Every builder's brief names it |

## `[paths]`

Relative to the checkout unless absolute. The office and the live state are always read from the main checkout.

| Key | Default | Read by | What it is |
|---|---|---|---|
| `tools` | `scripts/foundry` | `office.py`, `board.py`, `founder.py`, the graph hook | Where the tools lie. Briefs print this path |
| `office` | `out/foundry` | `office.py`, `rq.py`, `journal.py`, `board.py`, `flow.py`, `sweep.py` | The crew office: badges, the time clock, the journal, the queue. Must be git-ignored |
| `state` | `docs/progress/state.json` | `board.py`, `office.py`, `flow.py`, `founder.py` | The state file |
| `map` | `docs/progress-map.html` | `board.py` | The built progress map |
| `roadmap` | `docs/ROADMAP.md` | `board.py`, `flow.py`, `flow_graph.py`, `founder.py` | The roadmap |
| `flow` | `docs/flow` | `flow_graph.py`, `plan_flow.py`, `office.py` (the hand-in check), the graph hook | The road graph asset and the plan files (checked in) |
| `flow_out` | `out/flow` | `flow.py`, `plan_flow.py`, `founder.py` | Built chart pages. Must be git-ignored |
| `reviews` | `docs/reviews` | `office.py`, `board.py` | Where review files go; named on a reviewer's card |
| `research` | `docs/research` | `office.py`, `board.py` | Where research reports go; named on a scout's card |
| `handoff` | `docs/handoff` | `founder.py`, `board.py` | Push drafts, founding notes, managers' proposal files |
| `decisions` | `docs/decisions` | `office.py` (`hire --adr`) | Decision records and decision briefs |
| `gym` | `gym` | `board.py`, `office.py`, `flow.py`, `lanes_for.py`, `gym_init.py`, `sweep.py` | The gym folder: `series/`, `prereg/`, `contracts/`, `charts/`, `grades/`, `lanes/` |
| `rules` | `.foundry/rules.md` | `founder.py` | The rules file |

## `[skills]`

The name of the skill each level loads. Change one only when a project keeps its own copy of a skill under another name.

| Key | Default | Read by |
|---|---|---|
| `founder` | `foundry-founder` | `founder.py doctor`, `office.py` |
| `manager` | `foundry-manager` | `founder.py doctor`, `office.py`, `board.py` |
| `employee` | `foundry-employee` | `founder.py doctor`, `office.py` (the first line of every brief), `board.py` |
| `flow` | `foundry-flow` | `founder.py doctor` |
| `bench` | `foundry-bench` | `founder.py doctor` |
| `gym` | `gym` | `founder.py doctor`, `office.py` (a grader's brief) |

## `[slots]`

| Key | Default | Read by | What it changes |
|---|---|---|---|
| `day`, `swing`, `night` (any name, `HH:MM`) | `06:00`, `14:00`, `22:00` | `board.py init`, `office.py`, `founder.py` | The rota a new state file starts with. Once the state exists, its `rota.slots` wins |
| `round_every` | `"2h"` | `office.py timers init` | How often the round timer in `manager-timers.json` fires |
| `review_window_min` | `90` | `board.py init`, `board.py rota slots` | The length of each slot's research-and-review window |

Any key under `[slots]` whose value is a five-character `HH:MM` text is a slot. To change the slots of a project that already has a state, see [troubleshooting.md](troubleshooting.md#faq).

## `[limits]`

Every number here is yours.

| Key | Default | Read by | What it changes |
|---|---|---|---|
| `usage_stop` | `80` | `board.py`, `office.py`, `founder.py` | Percent of the plan's weekly usage at which the manager stops and asks. The state's `usage.stop` wins once set |
| `crew_max` | `4` | `board.py init`, `founder.py push new` | The headcount the starter shift gets. After that each shift names its own; `office.py hire` reads the shift's, not this |
| `stale_min` | `45` | `office.py`, `board.py` | An employee silent this many minutes reads STALE |
| `overdue_min` | `15` | `office.py`, `board.py` | An employee this far past its finish reads OVERDUE |
| `manager_stale_min` | `120` | `office.py` | A manager or founder silent this long reads STALE, and the manager can be relieved |

## `[resource]`

The one shared thing the crew queues for. An empty `name` means there is none: `rq.py` then refuses to run, and `hire --rq` and `--seat` are refused.

| Key | Default | Read by | What it changes |
|---|---|---|---|
| `name` | `""` | `rq.py`, `office.py`, `board.py`, `flow.py`, `founder.py`, `sweep.py` | What the resource is called in messages. Non-empty switches the queue on |
| `seats` | `["main"]` | `rq.py`, `office.py`, `board.py`, `founder.py` | How many jobs it takes at once, each by name. The file `rq.seats` in the office (one seat a line) overrides this list |
| `seat_env` | `"FOUNDRY_SEAT"` | `rq.py`, `office.py` | The variable a queued command reads its seat from |
| `seats_env` | `"FOUNDRY_SEATS"` | `rq.py` | The variable that lists every seat held, for a whole-resource job |
| `prepare` | `""` | `rq.py` | A shell line run in the seat before each `run` job. Empty: none |
| `exclusive` | `""` | `rq.py` | A regex. A job whose text or command matches never holds a seat at the same time as another such job |
| `status` | `""` | `rq.py status --resource` | A command that prints the resource's own health (disk, memory) |
| `default_max` | `"30m"` | `rq.py`, `office.py` | A hold's limit when `--max` is not given. Always with a unit: a bare number here is not read, and 30 minutes stands |
| `shell` | `""`: `bash` on the PATH, else `sh` | `rq.py` | The shell a queued command line runs in |
| `enforce_max` | `false` | `rq.py` | `true`: a `run` job still going at its `--max` plus `max_grace` is ended with everything it started (exit 124) |
| `max_grace` | `"2m"` | `rq.py` | The grace before an enforced `--max` ends a job |

## `[measure]`

How "done" is decided: the gym.

| Key | Default | Read by | What it changes |
|---|---|---|---|
| `done_means` | `"the milestone's gym lane says PASS"` | no tool | A rule for people |
| `lane_pattern` | `\bG(?:X\d+[a-z]?\|L\d+\|\d+)\b` | `board.py`, `flow_graph.py`, `gym_init.py` | How a lane's name looks in text: `G1`, `G12`, `GX3`, `GL2` |
| `counted` | `""` | `sweep.py`, `founder.py doctor` | The command of a counted run, with `<lane>`. `sweep.py` refuses to start when it is empty or has no `<lane>` |
| `dev` | `""` | `office.py` | The command of a dev run. A queued job whose text holds it (up to `<lane>`) is read as a dev run, not a possible counted one |
| `sweep` | `""` | no tool | The project's own sweep command, for people |
| `selftest` | `""` | `office.py` | The gym's own selftest command, printed in a builder's brief |
| `grader_owned` | `["gym/prereg", "gym/lanes", "gym/run.py", "gym/gym_kit.py"]` | `office.py` | Paths only a grader writes. `handin` makes any other role's change to them a PROBLEM |
| `records` | `["gym/series", "gym/charts", "gym/grades"]` | `board.py`, `sweep.py`, `office.py handin` | A run's records. A commit of only these does not move `now.tree`; a sweep allows them to change between lanes; `handin` makes a change to them a PROBLEM for any badge that is neither a grader nor the manager |
| `grader_no_read` | `[]` | `office.py` | Paths a grader never opens (the builder's code); printed in the grader's brief |
| `handin_check` | `""` | `office.py handin` | A command `handin` runs in the worktree when the branch changes a file that matches `handin_check_paths`. Non-zero exit: a PROBLEM |
| `handin_check_paths` | `[]` | `office.py handin` | Globs |
| `handin_check_timeout_s` | `900` | `office.py handin` | How long the check may run |
| `vendored_paths` | `[]` | `office.py hire` | Globs a badge should not own without saying so; `hire` prints a warning |
| `unit_manifests` | `[]` | `lanes_for.py` | Globs of TOML manifests to read build units from |
| `not_built` | `["tests/", "benches/", "examples/", "*.md"]` | `lanes_for.py` | Paths inside a unit that move no lane |
| `sweep_skip` | `[]` | `sweep.py` | Globs of changed paths left out of its "did the main branch move a lane" check |
| `no_verdict_exits` | `[2, 3]` | `sweep.py` | Exit codes of the `counted` command that mean "it ran and gave no verdict". The defaults are the scaffolded runner's: 2 refused, 3 the runner failed. A lane that exits with one is listed apart, and the sweep exits 1. `[]` for none |

## `[roadmap]`

The shape of the roadmap's ids. The table formats are in [charts.md](charts.md#the-roadmaps-tables).

| Key | Default | Read by | What it is |
|---|---|---|---|
| `requirement_id` | `[A-Z0-9]+-\d+` | `board.py`, `flow.py`, `founder.py` | A requirement's id: `APP-01` |
| `tiers` | `["P0", "P1", "P2"]` | `board.py`, `flow.py`, `founder.py` | The priorities. The first is the tier the goal waits on |
| `stage_id` | `R\d` | `board.py`, `flow.py`, `flow_graph.py` | A numbered stage: `R0` |
| `milestone_id` | `M\d+` | `flow.py`, `flow_graph.py`, `founder.py`, `office.py` | A milestone: `M1` |
| `decision_id` | `D\d+` | `flow.py`, `flow_graph.py` | A decision: `D1` |
| `goal` | `"1.0"` | `board.py`, `flow_graph.py` | The last stage, and the word in "the road to 1.0" |
| `late_stages` | `[]` | `flow_graph.py` | Named stages between the numbered ones and the goal, in order: `["Beta"]` |
| `block_id` | `[QP]\d+[a-z]?` | `flow_graph.py` | How a push block's title opens on the map: `Q1: M2 store` |

## `[board]`, `[git]`, `[hooks]`, `[crews]`

| Key | Default | Read by | What it changes |
|---|---|---|---|
| `board.phases_title` | `"Phases"` | `board.py` | The heading over `state.phases` on the map |
| `board.absolute_commands` | `false` | `board.py` | `true`: the map and the check print tool commands with the host's absolute paths |
| `git.push` | `false` | `office.py` | The brief's push rule. `false`: "no push". `true`: "push only your own branch, never the main branch". No tool enforces it |
| `git.merge` | `"cherry-pick by commit"` | no tool | A rule for the manager |
| `git.worktrees` | `".claude/worktrees"` | `office.py`, `founder.py` | Named in the brief's branch line. `founder.py init` git-ignores it, and `doctor` makes it a PROBLEM when it is not ignored: an untracked worktree folder makes the main checkout read as dirty to a counted run |
| `git.branch_prefix` | `"claude/"` | `office.py` | Named in the brief's branch line |
| `hooks.protect` | `["docs/flow/road.graph.json", "docs/flow/road.edits.jsonl"]` | `graph_readonly.py` | Files only a tool may write. Left out of the file (the starter profile leaves it out), the hook protects the two road graph files under `paths.flow`, wherever that is. See [hooks.md](hooks.md) |
| `hooks.protect_reason` | `""` | `graph_readonly.py` | Text that replaces the hook's refusal message |
| `[crews.<name>]` `lessons = "<path>"` | none | `journal.py`, `office.py` | Another crew that works this way, and the file where its lessons for this crew lie |

## Titles, flagged titles and models

A badge is hired on a title's card. The built-in cards are `builder`, `fixer`, `grader`, `reviewer`, `scout`, `triager` and `cleaner`. A project adds or changes a card:

```toml
[titles.auditor]
like = "reviewer"                 # a built-in card to start from
kinds = ["session"]               # and any of: role, kinds, does, may_write, hands_in, independent
does = "audits one merged change against the security rules"

[titles.security-fixer]
like = "fixer"
```

| Card key | Meaning |
|---|---|
| `like` | The built-in card to start from. A card with no `like` and no `role` is broken, and `hire` refuses the title |
| `role` | `builder`, `grader`, `reviewer` or `scout` |
| `kinds` | A list of `session`, `temp` |
| `does`, `may_write`, `hands_in` | The card's three lines, printed in the brief. `{reviews}`, `{research}` and `{grader_owned}` in a text are filled in from the profile |
| `independent` | `true` or `false`. Printed on the card |

`[models]` maps a title or a role to a model id. The brief prints `Model: <id>`, the title looked up before the role. `office.py hire --model ID` overrides it for one hire.

```toml
[models]
builder = "claude-opus-5-5"
reviewer = "claude-sonnet-5-5"
```

In the starter profile the `[models]` header and its lines are commented out. Uncomment the header together with the lines you want. A table may be declared only once in the file: a second `[models]` header (or a second `[hooks]`, which the starter does declare) breaks the file, and a broken profile stops every tool.

`[flagged.<title>]` marks a title whose work gets a heavy review:

```toml
[flagged.security-fixer]
model = "claude-opus-5-5"
trailer = "Built-by: claude-opus-5-5 (security fix; heavy review)"
```

With those tables in place:

```
python scripts/foundry/office.py hire --by "<the manager's line>" --name sec1 --title security-fixer --kind session --job "fix F001" --eta 1h --files "src/"
```

```
hired EMP-03 sec1 (security-fixer (builder), session); crew 1 of 4 on start
  model: claude-opus-5-5 ([flagged.security-fixer]): set the session to it before it starts
  flagged title: every commit ends with `Built-by: claude-opus-5-5 (security fix; heavy review)` (handin checks it); its commits get an in-depth review
```

The brief then says:

```
Your card (security-fixer): role builder; hired as session or temp
Model: claude-opus-5-5 (the manager sets the session to it; say in your first progress note which model you run on)
Every commit of yours ends with the trailer: Built-by: claude-opus-5-5 (security fix; heavy review). Your commits get an in-depth review.
```

What the tools do with these, and what they leave to the manager:

- The tool prints the model. It does not set it. The manager starts the session on that model.
- `handin` makes a flagged title's commit without the trailer line a PROBLEM.
- A `--model` other than the flagged table's is refused unless `--force-model`.
- A `[flagged.<title>]` table with neither `model` nor `trailer` makes `hire` refuse the title.
- A card's `kinds` is enforced: hiring the `auditor` above as a temp is refused.

## Environment overrides

For tests and odd layouts.

| Variable | Meaning |
|---|---|
| `FOUNDRY_ROOT` | The checkout, in place of the nearest parent folder that holds `.foundry` or `.git` |
| `FOUNDRY_MAIN` | The main checkout, in place of the one git's common dir names |
| `FOUNDRY_PROFILE` | The TOML file to read. One that names no file is a problem like a broken profile (exit 2), not the defaults |
| `FOUNDRY_<SECTION>_<KEY>` | Any scalar or list key of a section: `FOUNDRY_PATHS_OFFICE`, `FOUNDRY_LIMITS_USAGE_STOP`, `FOUNDRY_RESOURCE_SEATS` |
| `FOUNDRY_<KEY>` | A top-level key: `FOUNDRY_BADGE_PREFIX`, `FOUNDRY_MAIN_BRANCH` |

A value is read by the default's type: a boolean takes `1`, `true`, `yes` or `on`; a whole number is parsed (a bad one keeps the default); a list is split at commas; anything else is text. A table inside a section cannot be set this way.

## `.foundry/rules.md`

The profile holds facts a tool reads. The rules file holds what people and agents must know that no tool reads: this project's standing rules and lessons, sorted by situation, so an agent reads only the section it is in. A brief names the sections a job needs.

`founder.py init` writes an outline with these sections; replace each bracketed line or delete it:

| Section | What belongs there |
|---|---|
| Always | Whether the crew may push, and where. What needs your word every time. Where captures, logs and scratch files go |
| The host | The interpreter to use and why. What the shell here cannot do. What is not installed and where it runs instead |
| At a slot start | What the manager checks before any work. Where the weekly usage is read, and what happens at the stop |
| Using the shared resource | What it is, how many seats, what a job may assume about a seat. What is cleaned between jobs. How it is brought back after a restart. How a stuck job is stopped |
| Merging | The merge gate. The full check at each slot's end |
| The charts | Any reader of the project's own that draws a system graph |
| Before a counted run | The dev run first. What must be green and clean |
| Before a builder hands in | The checks every change runs: format, lint, tests |
| Shared files | Files every lane reads, so a change there moves other lanes |
| Reporting | Where run results go |
| Closing a push | The freeze, the full sweep, where the close note goes |

Keep it short. Each line is a rule the project paid for; say in a few words what taught it. A rule that would hold in every project belongs in the skills, not here.

After the founder's first version, a line is added the way any change to how the crew works is: logged in the journal, planned by the manager, approved by you. Neither the manager nor an employee edits the file.

## Worked examples

Each example shows only the lines that differ from the starter profile.

### A project with no shared resource

```toml
project = "Notes App"

[commands]
test = "pytest -q"

[resource]
name = ""                       # nothing is shared

[measure]
counted = "python gym/run.py counted <lane>"
dev = "python gym/run.py dev <lane>"
selftest = "python gym/run.py selftest"
```

- `rq.py` refuses to run, and `office.py hire --rq` is refused.
- A counted run is frozen by hand with `office.py freeze on`, or by `sweep.py`, which turns the freeze on itself.
- `founder.py doctor` prints a note, not a problem: `no shared resource named: rq.py and the queue's freeze are off`.

### A project with a two-seat VM

```toml
[resource]
name = "the dev VM"
seats = ["a", "b"]              # two jobs at once, each in its own seat
prepare = "sh tools/clean-seat.sh"
exclusive = "ui-test"           # two UI test jobs never hold seats at the same time
status = "sh tools/vm-status.sh"
default_max = "30m"
```

`tools/clean-seat.sh`, `tools/vm-status.sh` and the word `ui-test` stand for the project's own scripts and job names. A job reads its seat from `FOUNDRY_SEAT`:

```
python scripts/foundry/rq.py run --id EMP-02 --job "unit tests" --touched "src" --max 5m -- 'echo seat=$FOUNDRY_SEAT'
```

```
rq: EMP-02 queued at 15:17 (prio 5, any seat): unit tests
rq: EMP-02 holds seat b (FOUNDRY_SEAT=b) from 15:17 for up to 5 min (waited 0 min). rq.last.b:
(none)
rq: running in seat b: echo seat=$FOUNDRY_SEAT
seat=b
rq: EMP-02 released seat b at 15:17
```

The prepare line runs in the seat before each `run` job and can read what the last holder touched (`FOUNDRY_LAST_TOUCHED`). A counted run that must have the whole VM is queued with `--all-seats`.

### A project with a GPU

Name the seats after the device ids, and have the queue set the variable the framework already reads:

```toml
[resource]
name = "the GPUs"
seats = ["0", "1"]
seat_env = "CUDA_VISIBLE_DEVICES"
default_max = "2h"
enforce_max = true              # a training job past its --max plus the grace is ended
max_grace = "5m"
```

```
python scripts/foundry/rq.py run --id EMP-05 --job "train smoke test" --max 10m -- 'echo gpu=$CUDA_VISIBLE_DEVICES'
```

```
rq: EMP-05 queued at 15:25 (prio 5, any seat): train smoke test
rq: EMP-05 holds seat 1 (CUDA_VISIBLE_DEVICES=1) from 15:25 for up to 10 min (waited 0 min). rq.last.1:
(none)
rq: running in seat 1: echo gpu=$CUDA_VISIBLE_DEVICES
gpu=1
rq: EMP-05 released seat 1 at 15:25
```

With one GPU, `seats = ["0"]`.

### Titles and flagged titles with models

See [Titles, flagged titles and models](#titles-flagged-titles-and-models) above: the `[titles]`, `[models]` and `[flagged]` tables there are a complete example, with the output they produce.
