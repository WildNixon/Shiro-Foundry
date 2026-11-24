---
name: foundry-flow
description: The Foundry flow charts and their tools - the road graph (flow.py) and plan charts (plan_flow.py). How the founder and the manager make, edit and use a chart, and how the crew reads and uses one. Use it whenever work touches the project's flow folder (the profile's paths.flow, default docs/flow) or its built pages, whenever someone asks for a flow chart or flowchart of a plan, a design or a push, and before answering "what does this wait on", "what gates this" or "what comes first" - even when the word chart is never said. The founder or manager loads it before a graph edit or a new plan chart; an employee loads it when a brief names a node, a chart or a plan file.
---

# Foundry flow charts

Two kinds of chart, one canvas. Each has one source and one tool. The pages are built from the source and never edited.

**Read first:** `.foundry/foundry.toml` (the profile: `paths.flow`, `paths.flow_out`, `paths.roadmap`, `paths.state`) and the flow section of `.foundry/rules.md`, if it has one. Where this skill and the profile differ, the profile wins.

**How commands are written here.** Tools are run as `<py> <tools>/flow.py ...`, where `<py>` is the interpreter the profile names (`commands.python`) and `<tools>` is `paths.tools` (default `scripts/foundry`) in the main checkout; a brief printed by `office.py hire` carries both resolved, so an employee copies the paths from its brief. After this line the skill writes them short: `flow.py build`, `plan_flow.py list`. "Your badge line" is the whole signed line you clocked in with.

**Option forms differ between the two tools.** `plan_flow.py` and the plain `flow.py` commands read an option only as one word joined by `=`: `--title="..."`, `--question="..."`, `--by="<badge line>"`, `--out=<dir>`, `--root=<dir>`. Written with a space (`--by "<line>"`), the value is taken for a name and the command fails or prints its usage. `flow.py graph ...` reads options the ordinary way, with a space: `--by "<badge line>"`, `--why "..."`, `--ids A-01,B-02`, `--note "..."` (the `=` form works there too).

| Chart | Answers | Its source | Tool | Page |
|---|---|---|---|---|
| Road graph | What must come first on the road to the goal, which decision gates what, where work waits | `<paths.flow>/road.graph.json` and its signed log `road.edits.jsonl` (the links); the roadmap, the state file and the gym's series (everything else) | `flow.py` | `<paths.flow_out>/workflow.html` |
| Plan chart | A design to judge before it is built: stages, steps and what each needs first, the user's decisions, the lanes that would close a stage | `<paths.flow>/NAME.plan.toml`, one file a plan | `plan_flow.py` | `<paths.flow_out>/NAME.html` |

Pick by the question. Order and gates between milestones: the road graph. A piece of work that does not exist yet and needs its steps laid out: a plan chart.

A project may add a third chart of its own: a reader that draws the system as built (its components and what calls what) from the code onto the same canvas. If your project has one, `.foundry/rules.md` names its tool; nobody edits such a graph, because a wrong link in it means the code is wrong.

## Who may do what

| | Founder | Manager | Crew (any other badge) |
|---|---|---|---|
| Road graph | Owns its shape: seeds it once, decides its nodes and gates. Edits through `flow.py graph ... --by` | Keeps it true during a shift (a decision answered, a block reordered, a seeded link checked). Edits through `flow.py graph ... --by` | Reads only: `graph show`, `graph trace`, `graph verify`, `flow.py brief`, the page. Never a command that takes `--by`; never the two files |
| Plan chart | Makes and edits plans for the roadmap and a push (`plan_flow.py new`, `build`); in the main checkout with its own badge (`--by="<founder's line>"`), or in its own worktree with none | Makes it (`plan_flow.py new`), edits the plan file, reads it | Reads. Makes or edits a plan file only when the brief names that one file, and only in its own worktree |

- A hook refuses a direct write to the road graph's two files from anyone, founder and manager included, and `office.py handin` sends back a branch that changes them. A hand edit shows as TAMPERED in `flow.py selftest` and on the page.
- A plan file has no hook: `office.py handin` flags one changed outside the badge's files. So a brief names the one plan file (`<paths.flow>/NAME.plan.toml`), never the whole flow folder.
- Any `plan_flow.py` write that would land in the main checkout (`new` there, a `build` there, or an `--out` that points into it) takes the badge of the roster's manager or of the founder (`--by="<badge line>"`, the same two badges `flow.py graph` takes) and refuses anyone else (exit 2), so a crew member's plan or page cannot land there.
- An employee who sees a wrong link, a missing step or a stale chart messages the manager; it does not fix the chart. A manager who thinks the graph's shape is wrong (a milestone missing from the roadmap, a gate that should not exist) writes a proposal for the founder; the roadmap is not the manager's to edit.

## The freeze comes first

While a counted run or a sweep is in the resource queue, waiting or running (`office.py roster` or `board.py brief` shows it), nothing in the main checkout changes. For the charts that means: no `graph` edit, no `plan_flow.py new`, no edit of a plan file, no commit or merge under the flow folder, by anyone. Reading goes on (`show`, `trace`, `list`, `selftest`, `brief`), and so do builds, which write only under the git-ignored `paths.flow_out`. Note the edits a build calls for and make them when the run has ended and its records are committed.

`plan_flow.py` helps with its own writes only: when the queue shows a counted run it refuses `new` in the main checkout even with your badge, and lets a build write only under the git-ignored output folder. It knows a counted run by its queue id (`<badge>-sweep`, `<badge>-counted-<lane>`) or prio 0, and refuses when it cannot read the queue. (`office.py` and `board.py` go by the id alone: a prio-0 job under a plain id is only `COUNTED?` to them.) A whole-resource job under a plain id (the roster's `COUNTED?`) only gets a note: if it is a counted run, the freeze is kept by hand. A hand edit of a plan file, a `graph` edit and a commit are not checked by any tool. The rule is yours to keep; the tool is a second pair of eyes, not the rule.

A project that counts no runs has no freeze. A project that counts runs but names no shared resource has no queue for the tools to read: `plan_flow.py`, `board.py` and `office.py` then see no counted run and refuse nothing, and the freeze is kept by hand, from the moment the manager says a counted run is going until it says its records are committed.

## Make a chart (founder or manager)

- **The road graph** is made once: `flow.py graph seed --by "<badge line>"` writes the links the roadmap's prose implies today, each marked unconfirmed (drawn faint). After that it is only edited. Until it is seeded, the order is guessed from the roadmap's prose, and the page says so.
- **A plan chart** for a design, a push or a block of work that needs judging before it is hired out:
  1. `plan_flow.py new NAME --title="What the plan is about" --question="What the user must judge" --by="<badge line>"` writes `<paths.flow>/NAME.plan.toml` from the template (it never overwrites). NAME is lower-case letters, digits and dashes.
  2. Write the plan in that file: `[[stage]]` tables in order, `[[step]]` tables (each with its `stage`, `state`, `effort`, `confidence` and the steps it `needs`), `[[decision]]` tables for what is the user's (with the stages each `gates`), `[[lane]]` tables for the gym lanes that would close a stage. The template's comments say what each key means. Give a step an `anchor` (a file and a text it must hold) wherever the plan rests on something in the tree, so the selftest fails when the tree moves.
  3. `plan_flow.py selftest NAME` until it prints 0 problems, then `plan_flow.py build NAME --by="<badge line>"`.
  4. Outside a freeze, commit the plan file like any other doc: `git add -- <paths.flow>/NAME.plan.toml`. The page is under the git-ignored output folder and is never committed.

  A scout can write the plan for you: name the plan file in its brief and make "selftest prints 0 problems" part of done-when. The scout runs `new` in its own worktree (no badge is asked there), commits the file on its branch, and the manager merges it.

A plan chart is a plan. A step's `state = "have"` is a claim checked only by its anchor; a stage is done when its gym lane says PASS, never because the chart says so. An answer in a `[[decision]]` is the user's own words, quoted, with the time and the question asked, and carries the D-number the decision register gave it (`board.py decide`).

## Edit the road graph (founder or manager)

Only through `flow.py graph ... --by "<badge line>"`, and never during a freeze. Commit the two files with the map; the tool commits nothing.

| When | Run |
|---|---|
| Once, when the graph is first set up | `graph seed --by LINE` |
| You have checked a seeded link against the roadmap | `graph confirm M1 M2 --why "needs M1's storage layout" --by LINE`; a wrong one leaves with `graph unlink M1 M2 --by LINE` |
| The user decides something, or a "needs" changes | `graph link D3 M5 --by LINE` (a decision gating only some requirement ids: `--ids REQ-06`); `graph unlink` when a gate falls away |
| Planning or reordering a push | `graph trace M6 --up` for everything it waits on; `graph link A B --by LINE` when an order is not what the map's list and titles say |
| The roadmap gained or lost a milestone, decision or stage | `flow.py selftest` names each: `graph node add M9 --by LINE` (`--type`, `--note`), `graph node set M9 --note "..." --by LINE`, or `graph node rm M9 --by LINE` after its links are unlinked |
| Writing a brief for a milestone | `graph show M3`, and name the node in the brief so the employee reads the same links |
| The last edit was wrong | `graph undo --by LINE` (again: puts it back) |
| selftest or the page says TAMPERED | Stop editing. `graph verify` names the entry. Find who changed the file (`git log -- <paths.flow>`) and file a failure. The hook refuses only a direct write that names the graph files; a folder-level git restore is not caught, so the restore is the user's own step: ask the user to run `git checkout <last good sha> -- <paths.flow>` themselves, then `graph verify` |

## Edit a plan chart

Outside a freeze, edit `<paths.flow>/NAME.plan.toml`, then `plan_flow.py selftest NAME`, then rebuild. Edit it when a step is done or its scope changes, when the user answers a decision (write the answer in, in their words), when a measurement lands (a `measure` step becomes `have`, with an anchor), and when the selftest reports the tree moved under an anchor.

## Use the charts (founder or manager)

| When | Run |
|---|---|
| Slot start, and every hand-off | `flow.py build` and `plan_flow.py build --by="<badge line>"` (every plan). Read `flow.py build`'s findings: what is ready to start, which decisions gate the most work, where work has waited longest, usage against the stop |
| While the crew waits on the shared resource | The same builds. The edits they call for too, unless the resource is busy with a counted run: then the freeze holds, and the edits wait |
| Planning or reordering a push | `flow.py graph trace M6 --up` |
| Writing a brief for a milestone | `flow.py graph show M3`; name the node in the brief |
| Writing a brief for a step of a plan | `plan_flow.py show NAME <ID>` and `plan_flow.py trace NAME <ID> --up`; name the plan and the step in the brief |
| After a roadmap edit (the founder's) | `flow.py selftest`. It fails when a row no longer parses, a count table disagrees with the rows, a decision's state wording is unknown, an input could not be read or held records of the wrong shape (the line says which), or the road graph was changed by hand or no longer names the roadmap's milestones, decisions and stages. `flow.py edges` prints the graph as parsed, to check an edit kept its shape |
| Before a hand-off, and after any plan edit | `plan_flow.py selftest` (every plan); a problem line is fixed in the plan file or filed |
| Asking the user to decide | `plan_flow.py list`, then show them the plan's page: its questions view is what is theirs |

On the road graph's page, a click on a node shows its links, and a double-click opens a milestone: what it waits on, the requirements it closes, its gym pipeline.

## Crew: read and use

Everything here writes nothing to the tree and needs no badge.

| You need | Run |
|---|---|
| What your milestone waits on, or what waits on it | `flow.py graph show <ID>`, `flow.py graph trace <ID> --up` (or `--down`) |
| The road's findings as JSON | `flow.py brief` (never `flow.py build` without `--out=<dir in your worktree>`: it reads the main checkout and would write the manager's page) |
| One step of a plan your brief names: what goes in, what comes out, what must be done first | `plan_flow.py show NAME <ID>`, `plan_flow.py trace NAME <ID> --up` |
| Every link of a plan, then its problems | `plan_flow.py edges NAME` |
| Which plans exist | `plan_flow.py list` |
| A page to look at | Run from your own worktree, `plan_flow.py build NAME` writes under its output folder (`--out=<dir>` for anywhere else). `plan_flow.py` works on the checkout your shell stands in, and refuses to write in the main checkout without the manager's or the founder's badge, an `--out` that points there included |

How to use what you read:

- Do the work in the order the chart gives. If your step `needs` one that is not done, say so to the manager before you start; do not build around it.
- Quote the node id (M3, or the plan's name and step id) in your hand-in, so the manager can check the same links.
- If your change moves a file or a text that a plan anchors, `plan_flow.py selftest` fails. Report the line with your hand-in; the manager updates the plan (you do, if your brief names the plan file).
- A link that looks wrong goes to the manager in a message, with the node ids and what you read in the tree.

## Rules that hold for everyone

- The page is built, never edited. A change is made in the source, then rebuilt.
- A build never dirties the tree: every page is under the git-ignored output folder.
- The tools commit nothing. The manager commits flow-folder edits made in the main checkout, and merges a plan file an employee committed on its own branch. Every commit names its paths: `git add -- <paths>`.
- A chart is not a verdict. Done is the measure's PASS; decided is the user's own words in the decision register and the roadmap.
