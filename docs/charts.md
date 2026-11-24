# The map and the charts

Three kinds of page, each built from files the crew already keeps. A page is never edited: a change is made in its source, then the page is rebuilt.

| Page | Answers | Its source | Tool | Built file |
|---|---|---|---|---|
| The progress map | Where is the project now? What needs me? | The state file, the gym's series, the office, the roadmap | `board.py` | `docs/progress-map.html` (checked in) |
| The workflow page | What must come first on the road to the goal? Which decision gates what? Where does work wait? | The roadmap, the state, the series, the office, git, and the road graph | `flow.py` | `out/flow/workflow.html` (git-ignored) |
| A plan chart | Is this design right, before anyone builds it? | One file, `docs/flow/NAME.plan.toml` | `plan_flow.py` | `out/flow/NAME.html` (git-ignored) |

Commands and flags in full: [tools.md](tools.md). Who may edit what, and the routine: the `foundry-flow` skill.

- [The progress map](#the-progress-map)
- [The workflow page and the road graph](#the-workflow-page-and-the-road-graph)
- [Plan charts](#plan-charts)
- [The roadmap's tables](#the-roadmaps-tables)
- [A project's own system graph](#a-projects-own-system-graph)

## The progress map

```
python scripts/foundry/board.py           # build the map
python scripts/foundry/board.py check     # build, then the shift-start summary and every warning
python scripts/foundry/board.py open      # build, then open it in the browser
```

The page's sections, in order: Status, Crew on the clock, Notes, Decisions, Research and review, Gym checkpoints, Failures and action plans, Before a shift, This shift, Next shifts, Blockers and open questions, Road to the goal, Milestone track, Side tracks, Gym lanes, Block log, Standing rules, How this map is kept. What needs attention is first on the page.

Where each fact comes from:

| On the map | Read from | Typed by hand? |
|---|---|---|
| Now, the shift's blocks, the queue, blockers, notes, the log, failures, decisions, the rota | The state file | Yes, through `board.py` commands |
| A lane's verdict, n, run id and date | `gym/series/*.json` | Never |
| Whether a lane has a prereg, a contract, a grade | Files under `gym/` | Never |
| Who is on the clock, their job, percent and approximate finish | The office's time clock | Never |
| The shared resource's seats, a counted run in the queue | The queue's files in the office | Never |
| Each requirement's status, the release stages | The tables of the roadmap | In the roadmap, by the founder |

The builder warns when these disagree, so a stale map announces itself. Some of the warnings:

- The state's `now.tree` is behind HEAD: something was committed after the last update.
- A lane ran after the state's last update.
- A lane's latest run is FAIL, VOID, MARGINAL or STARVED and no failure entry names it.
- A crew report (`R<seq>`) has no failure entry.
- The shift's milestone has no checkpoint; a checkpoint has no prereg or no grader.
- A lane has a prereg but no row in `state.lanes`.
- A `PASS` requirement row names a lane whose newest run is no longer PASS, or names no lane.
- An employee is STALE or OVERDUE; employees are on the clock and no manager is.
- The journal's plan is due.

A project with no gym folder, no roadmap or no state yet still gets a map: each missing input is one line under Needs attention.

The map prints tool commands relative to the checkout. `board.absolute_commands = true` in the profile prints the host's absolute paths.

`board.py brief` gives the same facts as one compact JSON, for an agent. The manager commits the state file and the map together.

## The workflow page and the road graph

```
python scripts/foundry/flow.py build
```

```
wrote ~/myproject/out/flow/workflow.html
  P0 met: 1 / 5
  P0 part built: 1
  Milestones done: 0 / 3
  In work: 1
  Ready to start: 0
  Need the user: 0
  Crew on the clock: 0
  Failures open: 0
- [user] Decisions holding the most work: D2 (Storage format (DATA-01)) holds 1 unmet P0 behind M2 (DATA-01).
- [watch] M1 in “Build and dev runs” for 0.0 days: Lane G1; 1 failures open or planned on the lane; crew now: nobody.
- [info] Failure backlog: 0 open and 1 planned of 1 filed; most on G1 (1).
- [info] Longest chain of open milestones: M1 → M2 → M3. Its first link sets the earliest date for its last.
```

(Some findings are cut from this output.) It writes `workflow.html`, `brief.json` and `graph.json` under `paths.flow_out`. The page's sections: What to look at (the findings), the road graph, the pipeline (which step each milestone stands in), lane timelines, flow over time, open milestones. On the road graph, a click on a node shows its links, and a double-click opens a milestone: what it waits on, the requirements it closes, its gym pipeline.

`flow.py brief` prints the tiles and the findings as JSON. A finding's `kind` is `user`, `act`, `watch` or `info`.

A new project still gets a page: each input that is missing is a "not read" line on the page and in the findings.

### The road graph asset

Which milestone must come first, and which decision gates what, is written down in one place: `docs/flow/road.graph.json`. Every edit is logged in `docs/flow/road.edits.jsonl`, signed with the office's key and chained to the edit before it.

Until the graph is seeded, the order is guessed from the roadmap's prose, and the page says so. Seeding writes those guessed links, each marked unconfirmed:

```
python scripts/foundry/flow.py graph seed --by "<the founder's or the manager's line>"
python scripts/foundry/flow.py graph show
```

```
7 nodes (3 milestones, 2 decisions, 2 stages), 4 links, 4 seeded and not yet confirmed
  R0.reached → 1.0.exit  [seeded from ROADMAP.md's prose]  UNCONFIRMED
  D2.decides → M2.gate (DATA-01 only)  [seeded from ROADMAP.md's prose]  UNCONFIRMED
  M1.done → M2.after  [seeded from ROADMAP.md's prose]  UNCONFIRMED
  M2.done → M3.after  [seeded from ROADMAP.md's prose]  UNCONFIRMED
```

A node has typed pins: a milestone's `done` links to another's `after`; a decision's `decides` links to a milestone's `gate`.

| When | Run |
|---|---|
| You checked a seeded link against the roadmap | `flow.py graph confirm M1 M2 --why "the store needs the app to start" --by LINE` |
| A seeded link is wrong, or a gate falls away | `flow.py graph unlink M1 M2 --by LINE` |
| A decision now gates a milestone | `flow.py graph link D3 M5 --by LINE` (only some requirement ids: `--ids REQ-06`) |
| The roadmap gained a milestone | `flow.py graph node add M9 --by LINE`, and `board.py milestone sync` so the state lists it too |
| The last edit was wrong | `flow.py graph undo --by LINE` |

Only the manager on the clock and the founder edit it, with their badge line. An edit writes tracked files, so in the main checkout every edit command is refused (exit 3) while a freeze is on or a counted run or sweep is in the queue ([concepts.md](concepts.md#the-freeze-during-a-counted-run)). Anyone reads it, at any time:

```
python scripts/foundry/flow.py graph trace M3 --up
```

```
M3 waits on (3 links):
  M2.done → M3.after  [seeded from ROADMAP.md's prose]  UNCONFIRMED
    D2.decides → M2.gate (DATA-01 only)  [seeded from ROADMAP.md's prose]  UNCONFIRMED
    M1.done → M2.after  [the store needs the app to start]
```

```
python scripts/foundry/flow.py graph verify
```

```
graph ok: 7 nodes, 4 links, 2 edits, last confirm by FDR-1
```

`verify` exits 1 when the asset was changed by hand or the log's chain is broken. `flow.py selftest` fails for the same reason, and the page marks it. An optional hook refuses a direct edit of the two files ([hooks.md](hooks.md)). The tool commits nothing: commit the two files with the map.

After every roadmap edit:

```
python scripts/foundry/flow.py selftest
python scripts/foundry/flow.py edges
```

```
M1    in work                lane G1    after -            gates -          holds APP-01
M2    waits on a milestone   lane G2    after M1           gates D2(DATA-01) holds APP-02,DATA-01
M3    waits on a milestone   lane -     after M2           gates -          holds DATA-02,DOC-01,REL-01
D1   decided  -> -
D2   open     -> M2(DATA-01)
R0    0/3 <- M1,M2
1.0   1/6 <- M1,M2,M3
```

`selftest` exits 1 when a row no longer parses, a count table disagrees with the rows, or the road graph no longer names the roadmap's milestones, decisions and stages. A milestone or decision row that opens like a row and does not parse, and an id that stands in two rows, are each named by line:

```
FAIL ROADMAP.md line 50: decision D4 already has a row (line 49); an id stands in one row
FAIL ROADMAP.md line 51: a decision row that did not parse (it needs 5 cells, each closed by a pipe; a pipe inside a cell is written \|): | D5 | broken row | Open
```
 It also fails when the roadmap names a milestone the state's `milestones` list lacks; `board.py milestone sync` adds it.

## Plan charts

A plan chart is a design to judge before it is built: stages in order, the steps inside each stage and what each needs first, the decisions that are the user's, and the gym lanes that would close a stage. All of it is written in one file. That file is the chart.

```
python scripts/foundry/plan_flow.py new store --title "The store" --question "One file or a folder?" --by "<the manager's or the founder's line>"
```

```
wrote ~/myproject/docs/flow/store.plan.toml
next: write its stages, steps and decisions, then `plan_flow.py selftest store` and `plan_flow.py build store`
```

`new` writes the file from a template whose comments explain each key. NAME is lower-case letters, digits and dashes. In the main checkout, `new` and `build` take the manager's badge or the founder's; in a worktree no badge is asked.

### The plan file

```toml
[meta]
title = "The store"
written = "2026-11-24"
question = "One file or a folder?"
buys = ["what the user makes survives a restart"]      # what the plan gains, one line each
costs = ["one more format to keep readable"]           # what it costs
unknowns = ["how large one file gets after a year"]    # what nobody has measured or decided yet

[[stage]]                       # stages, in order
id = "S1"
title = "Write and read one file"
about = "The smallest store that keeps a note."

[[stage]]
id = "S2"
title = "Survive a crash"
about = "A half-written file never replaces a good one."

[[step]]
id = "A1"
stage = "S1"
title = "The file format"
what = "One JSON file with a version field."
state = "user"                  # have | new | measure | user
effort = "S"                    # S | M | L
confidence = "estimate"         # read | memory | estimate
needs = []

[[step]]
id = "A2"
stage = "S1"
title = "Save and load"
what = "The app writes the file on save and reads it at start."
state = "new"
effort = "M"
confidence = "estimate"
needs = ["A1"]                  # the steps that must be done first
anchor = ["src/app.py", "one screen"]   # a file, and a text it must hold

[[step]]
id = "B1"
stage = "S2"
title = "Write to a temp file, then rename"
what = "A crash mid-write leaves the old file whole."
state = "new"
effort = "S"
confidence = "memory"
needs = ["A2"]

[[decision]]                    # the user's
id = "Q1"
title = "One file or a folder"
question = "Storage format: one file, or a folder of files?"
options = ["one file", "a folder of files"]
lean = "One file: fewer moving parts."
answer = ""                     # the user's words, quoted, with the time
gates = ["S1"]                  # the stages the answer shapes
roadmap = "D2"                  # a decision row of the roadmap; the chart shows where that row stands

[[lane]]                        # a gym lane that would close a stage
id = "L1"
of = "S2"
title = "A killed save loses nothing"
checks = ["the file after a kill is the old one or the new one, never a mix", "control: a save with no kill"]
```

| Key | Values |
|---|---|
| A step's `state` | `have` (in the tree today), `new` (to build), `measure` (a fact nobody has read yet), `user` (waits on the user) |
| `effort` | The plan's own estimate, never a measurement: `S` (under one slot), `M` (one or two slots), `L` (three or more) |
| `confidence` | Where the claim comes from: `read` (from the tree, or a brief that read its source), `memory` (general knowledge, to confirm), `estimate` |
| `needs` | The steps that must be done first |
| `anchor` | A file and a text it must hold. The selftest fails when either is gone, so a plan cannot drift from the tree unnoticed |
| More step keys | `why`, `result`, `input`, `output`, `tool`, `where`, `risk`, `source`, `changes` |
| `[[section]]` | More for the chart's first panel: a `title` with `items = [...]` or `text = "..."` |

### Checking and reading it

Run the selftest after every edit of the file.

```
python scripts/foundry/plan_flow.py selftest store
```

```
store flow selftest: 1 decision, 1 lane, 2 stage, 3 step, 5 links, 0 problems
```

When the tree moves under an anchor, it says so and exits 1:

```
PROBLEM A2: its anchor src/app.py is gone
store flow selftest: 1 decision, 1 lane, 2 stage, 3 step, 5 links, 1 problems
```

```
python scripts/foundry/plan_flow.py show store A2
```

```
step A2: Save and load (to build · M)
  what: The app writes the file on save and reads it at start.
  comes in: A1  (needs; must be done first)
  goes out: B1  (needs; must be done first)
```

```
python scripts/foundry/plan_flow.py trace store B1 --up
```

```
before B1 (2): A2, A1
```

```
python scripts/foundry/plan_flow.py edges store
```

```
then   S1.next -> S2.after  # the plan's order
needs  A1.out -> A2.in  # must be done first
needs  A2.out -> B1.in  # must be done first
gate   Q1.decides -> S1.gate  # the answer shapes this stage
sub    S2.gym -> L1.checkpoint  # the stage is done when this lane says PASS
```

```
python scripts/foundry/plan_flow.py build store --by "<the manager's or the founder's line>"
```

```
wrote ~/myproject/out/flow/store.html and store.graph.json: 1 decision, 1 lane, 2 stages, 3 steps, 5 links
```

The page has three views: Pipeline, Every step, Your questions. `plan_flow.py list` names every plan with its counts and problems.

A plan chart is a plan, not a verdict. A step's `state = "have"` is a claim checked only by its anchor. A stage is done when its gym lane says PASS, never because the chart says so. The road to the goal is not a plan chart: that is the road graph.

## The roadmap's tables

The founder writes `docs/ROADMAP.md` as prose and tables. `flow.py` and `board.py` read the tables by the shape of each row, one line at a time, wherever the row stands in the file. Headings and prose are for people.

The full format, with every form each cell accepts, is `skills/foundry-founder/references/roadmap-format.md` in the Foundry repository (`.claude/skills/foundry-founder/references/roadmap-format.md` in an installed project). The same roadmap is `profile/ROADMAP.example.md`, which `founder.py init` copies as the starter, under a first line that marks it (`<!-- STARTER ...`). In short:

| Row | Shape | Example |
|---|---|---|
| Stage | Bold first cell: the stage's id, then its title. Then the theme, then the exit: requirement ids | `\| **R0 Usable** \| One person can do the main job \| APP-01–02, DATA-01 \| M1, M2 \| M1 done \|` |
| Milestone | Four cells: id, theme, Closes, Why here | `\| M2 \| Store: what the user makes is kept \| APP-02, DATA-01 \| Needs M1. Needs D2 \|` |
| Requirement | Id, tier, status, Where, note | `\| APP-02 \| P0 \| Part \| M2 \| editing works; undo is missing \|` |
| Decision | Id, decision, Where it stands, owner, Needed before | `\| D2 \| Storage format (DATA-01) \| Open: one file, or a folder of files \| the user \| M2 (DATA-01) \|` |
| Count (optional) | One row a tier: PASS, Part, Planned, Decided, Open, Total | `\| **P0** \| 0 \| 1 \| 2 \| 1 \| 1 \| 5 \|` |

Rules that hold for every row:

- A row starts at the start of a line with `| `, and its cells are split by ` | ` (one space each side). A pipe inside a cell is written `\|`.
- A requirement's status is exactly one of `PASS`, `Part`, `Planned`, `Decided`, `Open`. `PASS` and `Decided` count as met.
- An exit cell takes full ids, runs (`APP-01–03`), short lists (`APP-01, 03, 04`), remarks in parentheses, and `every P0`.
- In a milestone's **Why here**, every other milestone id named must come first, and every decision id named gates the milestone. So name one there only when it must come first.
- A decision's **Where it stands** is read by how it starts: `**Decided` is decided; `Open` is open.
- A decision's **Needed before** names what waits on the answer: `M2`, or `M2 (DATA-01)` for one requirement of it.

The id shapes (`APP-01`, `P0`, `R0`, `M1`, `D1`, the goal `1.0`) are the defaults. A project that names things its own way sets the `[roadmap]` keys in the profile ([profile.md](profile.md#roadmap)).

Once the road graph is seeded, the links are read from the graph, and the roadmap's prose is only compared against it.

The roadmap's decisions table and the decision register are two records with one set of numbers. The table is the founder's record in the roadmap. The register is `state.decisions`, written by `board.py decide`. `board.py decide adopt D<n>` gives a decision the roadmap names its register entry under the same id, and `decide adopt D<n> --refresh` reads it again after its row was rewritten. `board.py decide ask` gives a new question the id after the highest of both. The ids follow the profile's `roadmap.decision_id`. `board.py check` warns when the roadmap names an open decision the register lacks, when the two disagree on whether one is answered, when a decisions row opens like a row and was not read, and when one id stands in two rows.

The state's milestone list follows the roadmap the same way: `board.py milestone sync` adds every milestone the tables name and the state lacks, and rewrites the title and lane of a planned one nothing has touched; `milestone sync --prune` removes the planned, untouched ones the roadmap no longer names.

`board.py init` does both when a real roadmap is already there. The starter `founder.py init` writes is not one: its first line opens with `<!-- STARTER`, its rows are examples, and while that line stands the state takes nothing from it and the check does not compare the two. The founder who writes the real roadmap takes the line out, then runs `milestone sync` and `decide adopt` for each decision.

## A project's own system graph

The canvas the workflow page and the plan charts are drawn on is `flow_page.py`. A project may add a third kind of chart: a reader that draws the system as built (its components and what calls what) from the code. The Foundry ships no such reader, because it depends on the project's language and layout.

What `flow_page.py` offers a reader:

| Name | What it is |
|---|---|
| `flow_page.canvas_html(data, fallback_svg, shell)` | The canvas, its tool bar and its details panel as HTML. `data` is the graph (it is embedded as JSON). `fallback_svg` shows where scripts are off. `shell` holds this graph's own words: the keys `views` (a list of `(id, label)` pairs for the view buttons), `find` (the search box's hint), `toggle` (the checkbox's label), `aria` and `hint` |
| `flow_page.js(profile)` | The page script: the shared canvas code around the reader's own profile script, which says how this graph's nodes and pins are drawn |
| `flow_page.CSS` | The canvas's styles |

`plan_flow.py` is the worked example of a second graph on the canvas: it passes `canvas_html` its own data and shell, and `js()` its own profile script. Read it before writing a reader.

A chart with facts and words of its own can also register itself in `plan_flow.CHARTS` under a name. Its entry is a dict with the keys `name`, `plan`, `model` and `render`; `model` is a callable that takes the checkout's root and returns `(nodes, edges, problems, meta)`. It is then reached through `plan_flow.py` by that name, like any plan.

Nobody edits a system graph: a wrong link in it means the code is wrong. Name the reader's tool, and who may run it, in the charts section of `.foundry/rules.md`.
