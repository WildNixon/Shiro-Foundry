# Changelog

## 0.2.1 (2026-11-24)

The first release with a green CI run on every system.

- `rq.py` on Windows: a job's shell is now created suspended, placed in its job object and then resumed, so nothing it starts can be outside the job. Before, the job object was assigned after the shell had started, and on GitHub's Windows runner with Python 3.14 an enforced time limit released the seat while what the job had started ran on. Without a job object the tree is snapshotted and ended by handle. `sweep.py` starts a lane the same way when there is no shared resource.
- `rq.py`: a stop signal that arrives while the queue's mutex is held is raised when the mutex is left, so a stopped waiter always leaves the queue and never leaves the mutex behind.
- `tests/run_all.py` prints each failing test's output as a CI annotation.
- CI: all 12 jobs pass (Linux, macOS and Windows; Python 3.11, 3.12, 3.13, 3.14). This was the first run of the queue's Linux and macOS process-group and signal code.

## 0.2.0 (2026-11-24)

The first published release. It closes most of what 0.1.0's own audit found.

### New tools

- `sweep.py`: the counted sweep for any project. One lane at a time, through the resource queue when there is one and under its own freeze when there is none; it stops when the tree it counts changes, and refuses to start when the commits since it was queued can move one of its lanes.
- `gym_init.py`: scaffolds the smallest gym the tools can read (a runner, the kit, an example lane with a null, a veto and a control, prereg and contract templates), adds lanes, and checks a gym the way the tools will read it. A fresh gym cannot produce a PASS: the template prereg is marked not registered and a counted run refuses it.

### office.py

- Hiring by title: `hire --title` with cards for builder, fixer, grader, reviewer, scout, triager and cleaner, and a project's own cards in the profile's `[titles]`. The card is printed into the brief and a kind the card does not allow is refused.
- The brief prints the model from `[models]` or `[flagged.<title>]`, the trailer a flagged title's commits must carry, and push wording that follows `git.push`. The hand-in check sends back a flagged badge's commit without its trailer.
- The hand-in check sends back any badge that is not a grader's whose commits change a path under `measure.grader_owned`.
- `freeze on|off|show`: a freeze of the main checkout that every tool sees without a queue.
- `round`: what needs the manager, most pressing first, ending in one `first:` line. `handoff`: the next manager's brief from the roster and the state. `timers init|show`: the manager's timer list from the rota.
- The brief names the project's own test command (`commands.test`).

### board.py

- A command for every routine state edit: `log add`, `now`, `rota set`, `rota slots`, `checkpoint add|set`, `blocker add|rm`, `checklist add|done|rm|reset`, `shift set`, `shift blocks`, `queue add|rm|move|list`, `milestone set`. Each is held during a counted run or a freeze like `note`.
- `milestone set … done` is refused unless the lane's latest counted run is PASS; an override records the user's words.
- A stage's exit cell is read with the flow tool's own parser, so the map and the graph agree.
- The map prints command lines relative to the checkout.

### rq.py

- `--max` and `--wait` need a unit; a bare number is refused.
- `--enforce-max` (or `resource.enforce_max`): a job still running at its limit plus a grace is ended and its seat released.
- `status --json`.

### Hardening, from two independent reviews

- The hand-in walls read the branch's tree as well as its commits, always against the main branch as well as `--base`, so a merge that keeps one side, or a hand-in from a branch of a branch, cannot carry a change to the measure or to a run's records past the check.
- The sweep counts a lane as run only when the queue's own started and finished lines, carrying that lane's token, are in its log; a lane that gave no verdict is set apart; the tree, HEAD and its reflog are checked before and after every lane; the sweep's freeze holds for the whole run and is re-read before every lane.
- A profile that does not parse, is not UTF-8, has a key of the wrong kind, or is named by a `FOUNDRY_PROFILE` that points nowhere stops every tool with exit 2 and the reason. Before, the defaults were used in silence.
- Held edits are stored by the item they name, checked against the state as it will be, and replayed once.
- `board.py init` takes nothing from the starter roadmap; `milestone sync`, `decide adopt` and their `--prune` and `--refresh` forms bring the state in line with the roadmap the founder writes. Decision ids are shared between the roadmap and the register and follow the profile's pattern.
- The scaffolded gym runner publishes VOID when the tree, HEAD or its reflog changed during the collect, or when git cannot say; a lane that exits the process is a runner failure (exit 3), never a pass.
- The graph hook refuses more spellings of a write and fewer ordinary commands; its README lists exactly what it cannot see.
- Graph edits and the gym scaffold are refused in the main checkout during a freeze.
- Everything runs on Python 3.11 (one 3.12-only f-string removed; a test now scans for the pattern) and without the optional `segno` package.

### Other

- `plan_flow.py` takes options in the ordinary spaced form, and follows the same freeze rule as the office and the board (a counted run is known by its queue id or the freeze marker).
- `graph_readonly.py` follows `paths.flow` and `paths.tools`, and matches a generic file name by its path tail.
- `founder.py init --gym`; `founder.py audit` lists the managers' roadmap proposals.
- The starter roadmap carries no PASS row, so a new project's first check is quiet.
- The chart pages' script was run in two browsers with every view, node and trace clicked: no script errors. A structural check of both pages runs with the tests.
- Documentation under `docs/`.
- CI: every selftest and test on Linux, macOS and Windows for Python 3.11 to 3.14.

## 0.1.0 (2026-11-24)

The crew routine of one long-running project, made project-neutral. Not published.

### Skills

- `foundry-founder` (new as a skill): founding a project, the roadmap audit, push planning, the decision register, the profile. It replaces an earlier draft that was a level inside the manager skill and knew only a dashboard tool; it now covers the road graph, plan charts, the journal, the resource queue and the hooks.
- `foundry-manager`, `foundry-employee`, `foundry-flow`, `foundry-bench`: converted from the project's own skills. Every rule and its reason kept; project facts moved to the profile and the rules file; how the desktop app behaves and how to merge gathered into their own references.
- `gym`: the measure skill, with one project's private machinery removed and a section on how a Foundry project uses it.

### Tools

- `foundry_profile.py` (new): one profile file, `.foundry/foundry.toml`, read by every tool; defaults for everything; environment overrides for tests.
- `office.py` (was the project's crew office): the founder's badge (`found`), `--rq`/`--seat` for the shared resource, a profile-driven hand-in check, no project paths.
- `rq.py` (was a VM queue): a queue for the seats of any shared resource, with `prepare`, `exclusive` and `status` hooks from the profile.
- `board.py` (was the progress map): profile-driven paths and roadmap shapes, `init`, the `decide` register, a page that builds with inputs missing.
- `journal.py`, `flow.py`, `flow_graph.py`, `flow_page.py`, `plan_flow.py`, `lanes_for.py`: ported; crew names, badge prefix, paths and id shapes from the profile.
- `founder.py` (new): `init`, `doctor`, `audit`, `push new`.
- `install.py` (new): copies tools, templates, skills and (on request) hooks into a project; never overwrites without `--force`.

### Not carried over

The source projects' own wrappers and readers: the VM command wrapper, the system-graph and kernel-plan readers, and host watchdogs.
