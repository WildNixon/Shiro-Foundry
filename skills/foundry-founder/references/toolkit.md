# The toolkit: every tool, file and skill, and who may write what

## Skills

| Skill | Who loads it | How |
|---|---|---|
| `foundry-founder` | The founder | The user types `/foundry-founder [found \| audit \| push \| decide \| status]` |
| `foundry-manager` | The one manager of a rota slot | The user types `/foundry-manager [start \| shift-change \| block-end \| status]` |
| `foundry-employee` | Every hire: builder, grader, reviewer, scout, temp | The brief `office.py hire` prints says to load it first |
| `foundry-flow` | The founder or manager before a graph edit or a new plan chart; an employee whose brief names a node or a plan | By name |
| `foundry-bench` | An idle session kept for the next hire | The user types `/foundry-bench` in it after `/clear` |
| `gym` | Whoever builds, runs, grades or audits a measure | By name; the grader's and builder's references point at it |

## Tools (`paths.tools`, default `scripts/foundry`)

| Tool | What it is | Founder | Manager | Employee |
|---|---|---|---|---|
| `foundry_profile.py` | Reads `.foundry/foundry.toml`; `show`, `where` | reads | reads | reads |
| `founder.py` | `init`, `doctor`, `audit`, `push new` | runs | `doctor` only | no |
| `office.py` | The crew office: signed badges, the time clock, the roster, briefs, hand-ins, failure reports | `found`, clock in and out, `progress`, `me`, `roster` (`hire`, `assign --by`, `amend`, `brief` and `end-shift` refuse its badge) | everything but `found` | `clock-in`, `progress`, `me`, `fail`, `handin`, `clock-out`, `runs`, `roster` |
| `rq.py` | The queue for the shared resource's seats (every command but `selftest` exits 2 when the profile names no resource) | `status` | `run`, `status`, `leave`, `force-release --by MGR-<n>` (an `MGR-` id only) | `run`, `leave`, `status` under its own badge id |
| `board.py` | The progress map, its checks, the `brief`, and the state edits | `brief`, `check`, `decide`, `note`; `init` once | every command | `check --no-build`, `stamp`, `selftest` only |
| `journal.py` | The shift journal: holes, failures of the process, improvements, the plan for the user's approval, lessons carried between crews | `add --badge`, `mine` | every command | `add --badge`, `mine`, `show --badge <ids>` |
| `flow.py` | The workflow page and its findings; `graph …` edits the road graph | read commands; `graph` edits with `--by` | read commands; `graph` edits with `--by` | `graph show`, `graph trace`, the page |
| `plan_flow.py` | Plan charts from `<paths.flow>/NAME.plan.toml` | `new`, `build` (in the main checkout with `--by="<its line>"`), reads | `new`, `build` (in the main checkout with `--by="<its line>"`), reads | reads; `new` and `build` only in its own worktree; edits a plan file only when its brief names it |
| `lanes_for.py` | Which gym lanes a set of changed files can move | reads | reads | reads |

## Files

| File | What it holds | Who writes it |
|---|---|---|
| `.foundry/foundry.toml`, `.foundry/rules.md` | The profile and the project's rules | The founder, on the user's words |
| `paths.roadmap` | The goal, stages, milestones, requirements, decisions, the change log | The founder, on the user's answers |
| `paths.state` | Now, the shift and its blocks, the queue, the rota, checkpoints, failures, notes, the log, research and review, usage, decisions | The manager, through `board.py` or a script that saves with `board.write_state`; the founder through `board.py decide` and `note`, and the queue's entries by its own script when no manager is on the clock (while one is, the manager enters them exactly as the founder drafted them) |
| `paths.map` | The dashboard page | `board.py` only |
| `<paths.flow>/road.graph.json`, `road.edits.jsonl` | The road graph and its signed edit log | `flow.py graph … --by` only (a hook refuses anything else) |
| `<paths.flow>/NAME.plan.toml` | A plan chart's source | Whoever made the plan; an employee only when its brief names the file |
| `paths.office` (git-ignored) | `badge_key.json`, `roster.json`, `timeclock.jsonl`, `badges/`, `handins/`, `journal.jsonl`, `journal/` (`journal.md`, the `plan-*.md` files, `carry-<crew>.jsonl`), `pending-state.jsonl`, `adr-next.json`, the queue's `rq.*` files | The tools, under a lock. Never by hand |
| `<paths.office>/briefs/`, `<paths.office>/manager-timers.json` | Long briefs sent by path; the manager's timers | The manager, by hand: no tool reads or writes either |
| `<paths.handoff>/<date>-proposal-<topic>.md` | A manager's proposal to change the roadmap, a queued shift or the profile | The manager; the founder's audit reads them |
| `<paths.gym>/prereg`, `lanes`, and the rest of `measure.grader_owned` | The measure | Graders only |
| `<paths.gym>/contracts/<lane>-artifacts.md` | What the builder promises a lane will see | The builder; amendments are dated |
| `<paths.gym>/series`, `charts`, `grades` | A run's records | The run and its grader; committed as the run's own commit |
| `paths.reviews`, `paths.research` | Each slot's review and research reports | The reviewer or scout who wrote the report, and only that file |
| `paths.handoff` | Founding notes, push drafts, close notes | The founder (drafts), the manager (closes) |
| `paths.decisions` | Decision briefs | Whoever asks the decision |

## The hooks (optional, in `.claude/hooks/`)

| Hook | Refuses | Install it when |
|---|---|---|
| `graph_readonly.py` | A direct write to the files in the profile's `hooks.protect` | Always, once the road graph exists |
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
```

Lane facts are never typed: a verdict on the map comes from a series file. Crew facts are never typed: they come from the time clock. A page that disagrees with its inputs says so in its warnings, so a stale map announces itself.
