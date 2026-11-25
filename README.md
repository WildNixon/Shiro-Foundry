# Shiro Foundry

[![tests](https://github.com/WildNixon/Shiro-Foundry/actions/workflows/tests.yml/badge.svg)](https://github.com/WildNixon/Shiro-Foundry/actions/workflows/tests.yml)

Skills and tools for running a software project with a crew of Claude Code agents: a **founder** who writes the roadmap, one **manager** per shift, and badged **employees** who each do one job. A **gym** (a pre-registered, independently graded measure) decides what "done" means, so progress on the map is something a run proved, not something an agent said.

It is the project-neutral form of a routine worked out over several weeks of running two real projects around the clock: Glasswing, an operating system build, and Shiro, an AI fleet. Most lines in the skills are there because their absence cost a run.

## The levels

| Level | Owns | Never |
|---|---|---|
| **You** | The goal, every cut line, every approval | |
| **Founder** (`/foundry-founder`) | The roadmap, the profile, the road graph's shape, the queue of shifts and pushes, the decision register | Directs the crew, grades, merges |
| **Manager** (`/foundry-manager`) | The current shift: hires, briefs, checks hand-ins, merges, files failures, keeps the journal, hands off | Edits the roadmap, grades what it directed |
| **Employees** (`foundry-employee`) | One job each, by badge: builder, fixer, grader, reviewer, scout, triager, cleaner | Manage, or touch files outside their brief |

## What is in the box

**Skills** (`skills/`)

| Skill | For |
|---|---|
| `foundry-founder` | Founding a project, auditing the roadmap, planning a push, the decision register |
| `foundry-manager` | Running a rota slot: start, direct, block end, shift change |
| `foundry-employee` | Every hire: clock in, work inside the brief, report failures, hand in, clock out |
| `foundry-flow` | The charts: the road graph and plan charts, who edits and who reads |
| `foundry-bench` | An idle session proves it is cleared and reports ready for its next badge |
| `gym` | Building, running, grading and auditing a measure with an honest verdict word |

**Tools** (`tools/`, standard library only)

| Tool | What it does |
|---|---|
| `office.py` | The crew office: signed badge lines, the time clock, the roster, hiring by title, briefs, hand-in checks, failure reports, the manager's round and hand-off, the freeze |
| `rq.py` | A fair queue for one shared resource (a VM, a GPU, a device) and its seats |
| `sweep.py` | A counted sweep of every gym lane, one at a time, that stops the moment the tree it counts changes |
| `board.py` | The progress map: one page built from the state, the gym's series files, the office and the roadmap, with checks that make a stale map announce itself; the manager's `brief`; every routine state edit; the decision register |
| `journal.py` | The shift journal: holes in the skills and tools, failures of the process, improvements, and the plan you approve; lessons carry between crews |
| `flow.py`, `flow_graph.py`, `flow_page.py` | The road to the goal as a dependency graph, the pipeline step of every milestone, where work waits |
| `plan_flow.py` | Plan charts: a design drawn from one TOML file, to judge before it is built |
| `gym_init.py` | Scaffolds the smallest gym the tools can read: a runner, the kit, an example lane, prereg and contract templates |
| `lanes_for.py` | Which gym lanes a set of changed files can move |
| `founder.py` | `init` (scaffold a project), `doctor` (is the install whole), `audit` (the roadmap audit), `push new` (a push plan's starter) |
| `foundry_profile.py` | Reads the project's profile for every other tool |

**Hooks** (`hooks/`, optional): `graph_readonly.py` refuses a direct edit of the road graph's files; `no_python_stdin.py` refuses python fed on stdin, for hosts where that hangs.

**Templates** (`profile/`): a commented `foundry.toml`, a rules file outline, a starter roadmap in the shape the tools parse, and a starter gym.

## Documentation

| Page | What it answers |
|---|---|
| [Getting started](docs/getting-started.md) | Install, found a project, a first day with real commands and output |
| [Concepts](docs/concepts.md) | Levels, badges, slots and shifts, the gym, the freeze, the journal, pushes |
| [Tools](docs/tools.md) | Every command of every tool, with flags, exit codes and files |
| [Profile](docs/profile.md) | Every key of `.foundry/foundry.toml`, with worked examples |
| [State and office files](docs/state.md) | The shape of `state.json` and of each file in the crew office |
| [The gym](docs/gym.md) | Setting up the measure, dev and counted runs, the sweep |
| [Charts](docs/charts.md) | The map, the road graph, plan charts, the roadmap's format |
| [Hooks](docs/hooks.md) | What each hook refuses and how to switch it on |
| [Troubleshooting](docs/troubleshooting.md) | Refusals and warnings, and what to do about each |
| [Adopting](docs/adopting.md) | An existing project, or one that runs older copies of these tools |
| [Known holes](docs/HOLES.md) | What is not verified, not enforced or still missing |

## Requirements

- Claude Code. The manager's routine (starting sessions, benches, timers, messages between sessions) is written for the desktop app; the tools themselves run anywhere.
- Python 3.11 or newer. No packages needed; `segno` is optional and draws the badges' QR plates.
- git. The crew works in worktrees of one repository and the office is found through git's common dir.

## Install

```
git clone https://github.com/WildNixon/Shiro-Foundry.git
python Shiro-Foundry/install.py --project /path/to/your/project --check   # what it would change
python Shiro-Foundry/install.py --project /path/to/your/project           # tools + skills into the project
```

`--skills user` puts one copy of the skills in `~/.claude/skills` for every project; `--hooks` also copies the hooks (switching them on in `.claude/settings.json` is your own step: see [Hooks](docs/hooks.md)). The installer copies files and nothing else: it never runs git, deletes nothing, and keeps any file that differs unless you pass `--force`.

Then, in your project:

```
python scripts/foundry/founder.py init --project "My Project" --gym   # profile, rules, starter roadmap, state, starter gym
python scripts/foundry/founder.py doctor                              # is everything in place
```

## A first day

1. Type `/foundry-founder found`. The founder asks you for the goal, drafts requirements and a roadmap, fills in the profile with your limits (usage stop, headcount, whether the crew may push), seeds the road graph, plans the first shift, and brings you a numbered list of decisions.
2. Type `/foundry-manager start`. The manager clocks in, reads the board's brief, and hires by title: a builder for the first block, an independent grader for its measure, a reviewer and a scout for the slot's window. Each hire is a session you can open and steer, or a subagent for quick reads.
3. Watch `docs/progress-map.html` (the map) and `out/flow/workflow.html` (the graphs). What needs you is first on the page.
4. An hour before the slot ends the manager brings you the journal's plan: what the shift found wrong with its own skills, tools and briefs, and a fix for each. You approve in your own words; only approved fixes are built.
5. `/foundry-manager shift-change` writes the hand-off. The next manager is a fresh session that knows only what was written down.

[Getting started](docs/getting-started.md) walks through all of it with the commands and their output.

## The ideas it rests on

- **A report is not proof.** The manager reads the diff, the hand-in check and the run folder before a block is done; a milestone is done only when its lane says PASS on a counted run.
- **Builder and grader never share a head.** The grader writes the measure before any data, pins the builder's contract by hash, and never opens the builder's code. Bars do not move; amendments are dated. The hand-in check sends back anyone but a grader whose commits touch the measure's files.
- **One owner per file.** A badge names the files its holder may touch, and the hand-in check sends back a branch that strays.
- **The user's words, verbatim.** An approval or an answer is recorded as typed. A timer's prompt or another session's message is never the user's word.
- **A refusal means stop.** A permission prompt, a hook or a classifier that says no goes to the user; nobody tries another route.
- **Nothing is typed that can be read.** Lane verdicts come from series files, the crew from the time clock, order from the road graph. Pages warn when their inputs disagree.
- **The crew fixes its own process.** Every hole is logged when noticed, planned by the manager, approved by you, and merged at a slot boundary.

## Layout of a project that uses it

```
.foundry/foundry.toml        the profile: paths, slots, limits, the shared resource, the measure, model tiers
.foundry/rules.md            this project's standing rules and lessons, by situation
docs/ROADMAP.md              the goal, stages, milestones, requirements, decisions (the founder's)
docs/progress/state.json     Now, the shift, the queue, failures, notes, the log, decisions (the manager's)
docs/progress-map.html       the map (built)
docs/flow/                   the road graph and plan files
docs/reviews, research, handoff, decisions
gym/                         run.py, lanes/, prereg/, contracts/, series/, charts/, grades/
scripts/foundry/             the tools
out/foundry/                 the crew office (git-ignored): badges, the time clock, the journal, the queue
out/flow/                    built chart pages (git-ignored)
```

Every path can be changed in the profile.

## Tests

```
python tests/run_all.py --keep-going
```

runs each tool's selftest and the test files. All of them work in temp folders. CI runs the same on Linux, macOS and Windows for Python 3.11 to 3.14.

## Status

Version 0.2.1. The tools are ports of ones in daily use, extended for general use; the general forms of the skills have not yet been run on a new project from a clean start by anyone but their authors. [Known holes](docs/HOLES.md) lists what is unverified, not enforced or missing, and [the changelog](CHANGELOG.md) what changed.

## License

MIT. See `LICENSE`.
