# The shape of ROADMAP.md

The founder writes the roadmap as prose and tables. Two tools read the tables: `flow.py` (the road graph, the
pipeline, the findings) and `board.py` (the progress map's "road to the goal"). They read rows by their shape, one
line at a time, wherever the row stands in the file. Headings, prose and the header rows of the tables are for
people; the tools skip them.

This page lists every row shape the tools accept, each with a small example, and ends with a complete roadmap.
The same roadmap is `profile/ROADMAP.example.md`.

The roadmap's place is `paths.roadmap` in the profile (`docs/ROADMAP.md` unless the project says otherwise).

## What the profile names

The IDs in the examples are the defaults. A project that names things its own way says so in
`.foundry/foundry.toml`:

| Key | Default | What it is |
|---|---|---|
| `roadmap.requirement_id` | `[A-Z0-9]+-\d+` | a requirement's ID: `APP-01` |
| `roadmap.tiers` | `["P0", "P1", "P2"]` | the priorities; the **first** is the tier the goal waits on |
| `roadmap.stage_id` | `R\d` | a numbered stage: `R0` |
| `roadmap.milestone_id` | `M\d+` | a milestone: `M1` |
| `roadmap.decision_id` | `D\d+` | a decision: `D1` |
| `roadmap.goal` | `"1.0"` | the last stage, and the word in "the road to 1.0" |
| `roadmap.late_stages` | `[]` | named stages between the numbered ones and the goal, in order: `["Beta"]` |
| `roadmap.block_id` | `[QP]\d+[a-z]?` | how a push block's title opens on the map: `Q1: M2 store` |
| `measure.lane_pattern` | `\bG(?:X\d+[a-z]?\|L\d+\|\d+)\b` | a gym lane's name: `G1` |

Rules that hold for every row:

- A row starts at the start of a line with `| ` and its cells are split by ` | ` (one space each side).
- A cell holds no `|`.
- A requirement ID that takes part in a list or a run ends in `-digits` and holds at least one letter: `APP-01`.
  The digits keep their width, so `APP-01–03` is `APP-01`, `APP-02`, `APP-03`.

## Stage rows

```
| **R0 Usable** | One person can do the main job | APP-01–02, DATA-01 | M1, M2 | M1 done |
| **1.0 Release** | Ready for anyone | every P0 PASS; DOC-01 | M3 | — |
```

- Cell 1 is bold. Its first word is the stage's ID; the rest is its title. A stage is a row whose first word
  matches `roadmap.stage_id`, or is one of `roadmap.late_stages`, or is `roadmap.goal`. Any other bold first cell
  is not a stage (so a row such as `| **Later** | … |` is left alone).
- Cell 2 is the theme.
- Cell 3 is the exit: the requirement IDs that must be met before the stage is reached.
- Any cells after the third are for people.

How the exit cell is read:

| Written | Read as |
|---|---|
| `APP-01, DATA-01` | those two IDs |
| `APP-01–03` | a run, with an en dash (a hyphen also works for `flow.py`) |
| `APP-01, 03, 04; DATA-02` | a short list: `APP-01`, `APP-03`, `APP-04`, `DATA-02` (`flow.py` only) |
| `APP-01 (basic)` | `APP-01`; what stands in parentheses is a remark |
| `every P0 PASS` or `All P0` | every requirement of the first tier (`flow.py` only) |
| `All P0 except REL-04's sign-off; DOC-01` | every first-tier ID but `REL-04`, and `DOC-01` (`flow.py` only) |

The two tools differ here, so keep to what both read where you can:

- `board.py` reads only numbered stages, and only when the bold cell holds an ID **and** a title (`**R0 Usable**`).
  It reads full IDs and en-dash runs; it does not read short lists or "every P0".
- `flow.py` reads numbered stages, late stages and the goal, with or without a title.

So write a numbered stage's exit with full IDs and en-dash runs, and keep "every P0" for a late stage or the goal.

Order on the road: the numbered stages by number, then each late stage, then the goal. Every numbered stage leads
to the first stage after them.

`flow.py selftest` reports a stage with no exit IDs, a roadmap with no numbered stage, and a late stage or a goal
that has no row.

## Milestone rows

```
| M1 | Skeleton: the app starts | APP-01 | First: everything else needs it |
| M2 | Store: what the user makes is kept | APP-02, DATA-01 | Needs M1. Needs D2 |
| M3 | Ship: backups, the guide, the release | DATA-02, DOC-01, REL-01 | Last. After M2 |
```

Four cells: the ID, the theme, **Closes** and **Why here**.

- **Closes** lists the requirement IDs the milestone holds, in the forms of the table above (full IDs, runs,
  short lists, remarks in parentheses). An ID with no requirement row is reported.
- **Why here** is prose, and three things in it are read:
  - every other milestone ID it names is a milestone that must come first (`Needs M1`, `After M2`);
  - every decision ID it names gates the whole milestone (`Needs D2`);
  - a cell that starts with `Last` puts the milestone after every other open one.

  So name a milestone or a decision in Why here only when it must come first. Once the manager has seeded the road
  graph (`flow.py graph seed`), the links are read from the graph, and this prose is only compared against it.

A milestone also holds every requirement whose **Where** cell names it (see below).

### Milestone sections (optional)

A milestone can have a bullet of its own, with its lane and what it closes:

```
- **M1 Skeleton (lane G1):** done (G1 PASS). → APP-01.
- **M2 Store (lane G2):** in work. → APP-02, DATA-01; the base for DATA-02.
```

- The bullet starts `- **`, then the milestone's ID, and the bold part ends with `**`.
- `(lane G1)` inside the bold part names its gym lane.
- What follows the **last** `→` on the line is read as IDs the milestone closes, added to the table's Closes. A
  part after a `;` that reads as a remark (it holds words, such as "the base for DATA-02") is left out.

One line can give the lanes of many milestones:

```
**Lanes** (each milestone's gym lane): M1 G1, M2 G2, M3 none yet.
```

It starts with a bold label whose first word is `Lanes`; each `M1 G1` pair on it is read. A lane the map's own
state names for a milestone wins over both.

## Requirement rows

```
| APP-01 | P0 | PASS | M1 | G1 graded it |
| APP-02 | P0 | Part | M2 | editing works; undo is missing |
| DATA-01 | P0→P1* | Planned | M2 | a change of tier is proposed |
```

- Cell 1: the ID.
- Cell 2: the tier, one of `roadmap.tiers`. `P0→P1*` proposes a change; the row then counts as the tier after
  the arrow.
- Cell 3: the status, exactly one of these words:

  | Status | Meaning | Met? |
  |---|---|---|
  | `PASS` | a gym lane graded it | yes |
  | `Part` | some of it is built or graded; the note names the gap | no |
  | `Planned` | inside a milestone already planned | no |
  | `Decided` | answered by a decision record (for an ID that is a decision) | yes |
  | `Open` | no milestone yet | no |

- Cell 4, **Where**: every milestone ID in it holds this requirement.
- Cell 5 on: a note. On a `PASS` row, `board.py` looks in Where and the note for the name of the lane that graded
  it, and says so when that lane's newest counted run is no longer PASS, or when no lane is named.

A row with another status word, or with a cell missing, does not parse; `flow.py selftest` counts such rows and
fails. A first-tier requirement that is not met, that no open milestone holds and no open decision names, is
reported as a hole in the plan.

## The Count table

```
| P | PASS | Part | Planned | Decided | Open | Total |
|---|---|---|---|---|---|---|
| **P0** | 1 | 1 | 1 | 1 | 1 | 5 |
| **P1** | 0 | 0 | 1 | 0 | 0 | 1 |
```

One row per tier: the tier in bold, then six numbers, in this order: PASS, Part, Planned, Decided, Open, Total.
The table is optional. When it is there, `flow.py` counts the requirement rows itself and reports a tier whose
first five numbers differ (the Total is not checked).

## The decisions table

```
| # | Decision | Where it stands | Owner | Needed before |
|---|---|---|---|---|
| D1 | Release channel (REL-01) | **Decided:** one stable channel | the user | — |
| D2 | Storage format (DATA-01) | Open: one file, or a folder of files | the user | M2 (DATA-01) |
```

Five cells: the ID, the decision, **Where it stands**, the owner, **Needed before**.

**Where it stands** is read by how it starts:

| It starts with | Read as |
|---|---|
| `**Decided` | decided: it gates nothing any more |
| `**Decided` and the cell also holds `Still open` | part open: it still gates |
| `**Half` | part open: it still gates |
| `Open` | open: it gates |
| `**Adapted` | open: it gates |
| anything else | open, and `flow.py` reports the wording |

`plan_flow.py` reads the same cell for a plan's decision that names a roadmap row: decided when it starts with
`**Decided` and holds none of "open again", "still open", "waits for the user", "wait for the user".

**Needed before** names what waits on the answer:

| Written | Read as |
|---|---|
| `M2` | the decision gates the whole milestone |
| `M2 (DATA-01)` | it gates only that ID of the milestone; the rest may go on |
| `R0` or `R0's exit` | it gates the stage's exit |
| `R0's exit (APP-02)` | it gates that ID of the stage's exit |
| `M2 (DATA-01); the rest of DATA-02` | IDs named beside the targets also count as waiting on it |
| `—` | nothing waits |

A milestone's Why here that names the decision gates the whole milestone too, unless Needed before narrows it to
some IDs.

## A complete minimal roadmap

Two stages, three milestones, six requirements, two decisions. `flow.py selftest` accepts it with 0 problems
(in a project that has nothing else yet, each missing input is a NOTE line).

```markdown
# Example roadmap to 1.0

A complete, minimal roadmap in the shapes `flow.py` and `board.py` read (the foundry-founder skill's `references/roadmap-format.md` explains each).
Copy it to `docs/ROADMAP.md`, keep the tables, and replace the rows with your own.

## Stages

| Stage | Theme | Exit (requirement IDs) | Milestones | Now |
|---|---|---|---|---|
| **R0 Usable** | One person can do the main job from start to end | APP-01–02, DATA-01 | M1, M2 | M1 done |
| **1.0 Release** | Ready for anyone | every P0 PASS; DOC-01 | M3 | — |

## Milestones

- **M1 Skeleton (lane G1):** done (G1 PASS). → APP-01.

**Lanes** (each milestone's gym lane): M1 G1, M2 G2, M3 none yet.

| Milestone | Theme | Closes | Why here |
|---|---|---|---|
| M1 | Skeleton: the app starts and shows one screen | APP-01 | First: everything else needs it |
| M2 | Store: what the user makes is kept | APP-02, DATA-01 | Needs M1. Needs D2 |
| M3 | Ship: backups, the guide, the release | DATA-02, DOC-01, REL-01 | Last. After M2 |

## Requirements and where they stand

| ID | P | Status | Where | Note |
|---|---|---|---|---|
| APP-01 | P0 | PASS | M1 | G1 graded it |
| APP-02 | P0 | Part | M2 | editing works; undo is missing |
| DATA-01 | P0 | Planned | M2 | waits on D2 |
| DATA-02 | P0 | Open | M3 | backups: no design yet |
| DOC-01 | P1 | Planned | M3 | the user guide |
| REL-01 | P0 | Decided | M3 | one stable channel (D1) |

### Count

| P | PASS | Part | Planned | Decided | Open | Total |
|---|---|---|---|---|---|---|
| **P0** | 1 | 1 | 1 | 1 | 1 | 5 |
| **P1** | 0 | 0 | 1 | 0 | 0 | 1 |
| **P2** | 0 | 0 | 0 | 0 | 0 | 0 |

## Decisions

| # | Decision | Where it stands | Owner | Needed before |
|---|---|---|---|---|
| D1 | Release channel (REL-01) | **Decided:** one stable channel | the user | — |
| D2 | Storage format (DATA-01) | Open: one file, or a folder of files | the user | M2 (DATA-01) |
```

To check a roadmap after an edit:

```
python tools/flow.py selftest     # 0 problems, or a FAIL line for each
python tools/flow.py edges        # each milestone with what it waits on, each decision with what it gates
```
