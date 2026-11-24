# The toolkit: every tool, file and skill, and who may write what

## Skills

| Skill | Who loads it | How |
|---|---|---|
| `foundry-founder` | The founder | The user types `/foundry-founder [found \| audit \| push \| decide \| status]` |
| `foundry-manager` | The one manager of a rota slot | The user types `/foundry-manager [start \| shift-change \| block-end \| status]` |
| `foundry-employee` | Every hire: builder, fixer, grader, reviewer, scout, triager, cleaner, temp | The brief `office.py hire` prints says to load it first |
| `foundry-flow` | The founder or manager before a graph edit or a new plan chart; an employee whose brief names a node or a plan | By name |
| `foundry-bench` | An idle session kept for the next hire | The user types `/foundry-bench` in it after `/clear` |
| `gym` | Whoever builds, runs, grades or audits a measure | By name; the grader's and builder's references point at it |

## Tools (`paths.tools`, default `scripts/foundry`)

| Tool | What it is | Founder | Manager | Employee |
|---|---|---|---|---|
| `foundry_profile.py` | Reads `.foundry/foundry.toml`; `show`, `where`. A profile that cannot be read (a TOML error, not UTF-8, a key of the wrong kind, a `FOUNDRY_PROFILE` naming no file) stops every other tool (exit 2, `foundry: the profile cannot be read`); `where` names each problem, and `show` prints them and exits 1 | reads | reads | reads |
| `founder.py` | `init [--gym]`, `doctor`, `audit` (it lists the managers' proposals), `push new` | runs | `doctor` only | no |
| `gym_init.py` | Starts a gym: `init` scaffolds the folder (`run.py`, the kit, one example lane with a prereg template and a contract draft), `lane add` adds a lane's files, `check` reads the gym as the tools will. In the main checkout `init` and `lane add` are refused (exit 3) during a freeze or a counted run | `init` once, at the founding; `check` | `check` | a grader: `lane add` for its own lane, `check`; anyone: `check` |
| `<paths.gym>/run.py` | The gym's own runner, once scaffolded: `list`, `selftest`, `dev <lane>`, `counted <lane>` (the three `[measure]` commands) | `selftest`, to see the scaffold runs | `counted` (inside a queue job or a freeze), `selftest` | `selftest`, `dev`; never `counted` |
| `office.py` | The crew office: signed badges, the time clock, the roster, briefs, hand-ins, failure reports, the freeze, the round, the hand-off brief, the timer list | `found`, clock in and out, `progress`, `me`, `roster`, `freeze show`, `timers show` (`hire`, `assign --by`, `amend`, `brief`, `end-shift`, `freeze on\|off`, `round --by`, `handoff` and `timers init` refuse its badge) | everything but `found`: `hire --title`, `assign`, `amend`, `brief`, `end-shift`, `freeze on\|off\|show`, `round [--by]`, `handoff --by`, `timers init\|show` | `clock-in`, `progress`, `me`, `fail`, `handin`, `clock-out`, `runs`, `roster`, `freeze show` |
| `rq.py` | The queue for the shared resource's seats (every command but `selftest` exits 2 when the profile names no resource). `--max` and `--wait` need a unit. A stopped `run` ends its job and releases its seat | `status` | `run`, `status [--json]`, `leave`, `force-release --by MGR-<n>` (an `MGR-` id only) | `run`, `leave`, `status` under its own badge id |
| `sweep.py` | The counted sweep: `measure.counted` for each lane in turn on a clean main checkout, under its own freeze for the whole run, and through the queue when there is a shared resource; `status` reads a sweep's folder | `status` | `run --id MGR-<n> --out <a new folder>`, `status` | `status` |
| `board.py` | The progress map, its checks, the `brief`, and the state edits | `brief`, `check`, `decide` (`ask`, `answer`, `withdraw`, `adopt [--refresh]`, `list`), `note`; `init` once; with no manager on the clock: `queue add\|rm\|move`, `shift set\|blocks`, `milestone set\|sync [--prune]` | every command: also `log add`, `now`, `rota set\|slots`, `checkpoint add\|set`, `blocker add\|rm`, `checklist add\|done\|rm\|reset`, `block`, `fail`, `rr`, `usage`, `promote` | `check --no-build`, `stamp`, `selftest`, `queue list`, `decide list` only |
| `journal.py` | The shift journal: holes, failures of the process, improvements, the plan for the user's approval, lessons carried between crews | `add --badge`, `mine` | every command | `add --badge`, `mine`, `show --badge <ids>` |
| `flow.py` | The workflow page and its findings; `graph …` edits the road graph (in the main checkout an edit is refused, exit 3, during a freeze or a counted run) | read commands; `graph` edits with `--by` | read commands; `graph` edits with `--by` | `graph show`, `graph trace`, the page |
| `plan_flow.py` | Plan charts from `<paths.flow>/NAME.plan.toml` | `new`, `build` (in the main checkout with `--by "<its line>"`), reads | `new`, `build` (in the main checkout with `--by "<its line>"`), reads | reads; `new` and `build` only in its own worktree; edits a plan file only when its brief names it |
| `lanes_for.py` | Which gym lanes a set of changed files can move | reads | reads | reads |

## Files

| File | What it holds | Who writes it |
|---|---|---|
| `.foundry/foundry.toml`, `.foundry/rules.md` | The profile and the project's rules | The founder, on the user's words |
| `paths.roadmap` | The goal, stages, milestones, requirements, decisions, the change log | The founder, on the user's answers |
| `paths.state` | Now, the shift and its blocks, the queue, the rota, checkpoints, failures, notes, the log, research and review, usage, decisions | The manager, through the `board.py` edit commands (a larger edit: a script that saves with `board.write_state`); the founder through `board.py decide` and `note`, and the queue's entries with `board.py queue add --file` when no manager is on the clock (while one is, the manager runs it on the founder's files, exactly as drafted) |
| `paths.map` | The dashboard page | `board.py` only |
| `<paths.flow>/road.graph.json`, `road.edits.jsonl` | The road graph and its signed edit log | `flow.py graph … --by` only (a hook refuses anything else) |
| `<paths.flow>/NAME.plan.toml` | A plan chart's source | Whoever made the plan; an employee only when its brief names the file |
| `paths.office` (git-ignored) | `badge_key.json`, `roster.json`, `timeclock.jsonl`, `badges/`, `handins/`, `journal.jsonl`, `journal/` (`journal.md`, the `plan-*.md` files, `carry-<crew>.jsonl`), `pending-state.jsonl`, `adr-next.json`, `freeze.json` (the freeze: `office.py freeze`, or a sweep's own), `handins-seen.json` (the hand-ins a round has listed), the queue's `rq.*` files | The tools, under a lock. Never by hand |
| `<paths.office>/briefs/`, `<paths.office>/manager-timers.json` | Long briefs sent by path, and the hand-off briefs `office.py handoff` writes (`handoff-<slot>-<date>.md`); the list of the manager's timers | `office.py handoff` and `office.py timers init` write the starters; the manager fills a hand-off brief's hand-written parts and adds a dated one-shot timer by hand. The tool creates no timer: the manager creates them in its session from the list |
| A sweep's folder (`--out`, under a git-ignored folder) | `source.txt`, `started.tsv`, `runs.tsv`, a log a lane | `sweep.py run`; never used twice |
| `<paths.handoff>/<date>-proposal-<topic>.md` | A manager's proposal to change the roadmap, a queued shift or the profile | The manager; the founder's audit reads them |
| `<paths.gym>/prereg`, `lanes`, and the rest of `measure.grader_owned` | The measure | Graders only (`office.py handin` makes any other badge's change there a PROBLEM). `gym_init.py init` writes the starters once, before any grader: a prereg template marked not registered and an example lane |
| `<paths.gym>/contracts/<lane>-artifacts.md` | What the builder promises a lane will see | The builder; amendments are dated |
| `<paths.gym>/series`, `charts`, `grades` | A run's records | The run writes them; whoever queued it (the manager, or a grader) commits them as the run's own commit. `office.py handin` makes any other badge's change there a PROBLEM |
| `paths.reviews`, `paths.research` | Each slot's review and research reports | The reviewer or scout who wrote the report, and only that file |
| `paths.handoff` | Founding notes, push drafts, close notes | The founder (drafts), the manager (closes) |
| `paths.decisions` | Decision briefs | Whoever asks the decision |

## The hooks (optional, in `.claude/hooks/`)

| Hook | Refuses | Install it when |
|---|---|---|
| `graph_readonly.py` | A direct write to the road graph's two files under `paths.flow` (or to the files the profile's `hooks.protect` lists, when it sets that), and a shell command that removes, moves or replaces them through their folder (`git checkout .` and `git restore .` among them). It finds the profile's reader under `paths.tools` | Always, once the road graph exists |
| `no_python_stdin.py` | A shell command that feeds python on stdin | The host's shell hangs on it (some Windows setups) |

Installing or changing a hook is a change to the harness config: the user approves it by typing in the session that makes it.

## What reads what

```
ROADMAP.md ──┐
state.json ──┼─> board.py ──> the map, brief (the manager's and founder's start)
gym/series ──┤
the office ──┘
ROADMAP.md, state.json, gym/series, git, the office, road.graph.json ──> flow.py ──> the workflow page, findings
NAME.plan.toml ──> plan_flow.py ──> one plan page
the office's journal ──> journal.py ──> the plan file the user approves
the office, state.json ──> office.py round, handoff ──> what needs the manager; the next manager's brief
the queue's ids, the office's freeze.json ──> office.py, board.py, flow.py graph, plan_flow.py, gym_init.py, sweep.py ──> the freeze of the main checkout
measure.counted, the gym's lanes ──> sweep.py ──> a counted run a lane, and the sweep's folder
```

Lane facts are never typed: a verdict on the map comes from a series file. Crew facts are never typed: they come from the time clock. A page that disagrees with its inputs says so in its warnings, so a stale map announces itself.
