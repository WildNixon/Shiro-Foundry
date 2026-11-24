# Shiro Foundry documentation

Shiro Foundry lets one person run a software project with a crew of Claude Code agents. These pages take you from an empty project to a first working shift, and then serve as the reference.

Commands are written relative to a project that has the Foundry installed: `python scripts/foundry/office.py ...`. If your tools live elsewhere, read `scripts/foundry` as your `paths.tools`.

## The pages

| Page | What it holds |
|---|---|
| [getting-started.md](getting-started.md) | Requirements, install, `founder.py init`, the starter gym, and a complete first day with real commands and output |
| [concepts.md](concepts.md) | The levels, badges, slots and shifts, the gym, the shared resource, the freeze, the journal, pushes, "the user's own words" |
| [tools.md](tools.md) | Every tool: who runs it, every command and flag, exit codes, the files it reads and writes |
| [profile.md](profile.md) | Every key of `.foundry/foundry.toml`, the environment overrides, `.foundry/rules.md`, worked examples |
| [state.md](state.md) | The state file and the crew office's files: every key, its shape, the command that writes it |
| [gym.md](gym.md) | Setting up and running the measure: `gym_init.py`, lanes, dev and counted runs, `sweep.py`, `lanes_for.py` |
| [charts.md](charts.md) | The progress map, the workflow page and road graph, plan charts, the roadmap's table format |
| [hooks.md](hooks.md) | The two optional hooks: what each refuses, what it cannot see, how to switch them on |
| [troubleshooting.md](troubleshooting.md) | The refusals and warnings a new user meets, each with its meaning and what to do; a short FAQ |
| [adopting.md](adopting.md) | Bringing the Foundry into an existing project, and moving a project off the older per-project tools |

`HOLES.md` in this folder lists what is known to be missing or untested. `../CHANGELOG.md` lists what changed.

## Which page answers what

| Question | Page |
|---|---|
| How do I install it, and what does the installer copy? | [getting-started.md](getting-started.md#install) |
| What do I type first? | [getting-started.md](getting-started.md#a-first-day) |
| Who is allowed to do what? | [concepts.md](concepts.md#the-levels) |
| What is a badge, and is it secure? | [concepts.md](concepts.md#badges-and-the-time-clock) |
| What is the difference between a slot and a shift? | [concepts.md](concepts.md#the-rota-slot-and-the-work-shift) |
| What does PASS, MARGINAL, FAIL, MEASURING or VOID mean for my milestone? | [gym.md](gym.md#what-each-verdict-word-means-for-the-map) |
| Why must the grader be another session? | [concepts.md](concepts.md#the-gym-in-one-page) |
| What exactly does `office.py hire` take? | [tools.md](tools.md#badges-and-hiring) |
| What are the exit codes of a tool? | [tools.md](tools.md), under each tool |
| Which file does a tool write? | [tools.md](tools.md), and [state.md](state.md) for the shapes |
| What does a profile key do, and what is its default? | [profile.md](profile.md) |
| How do I describe a VM or a GPU the crew must share? | [profile.md](profile.md#worked-examples) |
| How do I give a title its own model? | [profile.md](profile.md#titles-flagged-titles-and-models) |
| What is in `state.json`, and which command writes each key? | [state.md](state.md) |
| What is in the office folder? | [state.md](state.md#the-crew-office) |
| How do I start a gym, add a lane, run a counted run? | [gym.md](gym.md) |
| How do I run every lane at a push's close? | [gym.md](gym.md#the-sweep) |
| How is the roadmap's table read? | [charts.md](charts.md#the-roadmaps-tables) |
| How do I draw a plan before it is built? | [charts.md](charts.md#plan-charts) |
| A command said "refused" or "held". What now? | [troubleshooting.md](troubleshooting.md) |
| Every tool says "the profile cannot be read". | [troubleshooting.md](troubleshooting.md#the-profile-does-not-parse) |
| The roadmap gained a milestone or a decision. How does the state learn of it? | [state.md](state.md#milestones-and-lanes), [state.md](state.md#decisions) |
| Does it need the desktop app? What does it cost? Can the crew push? | [troubleshooting.md](troubleshooting.md#faq) |
| My project already has code, or already runs the older tools. | [adopting.md](adopting.md) |

## The skills are the routine

These pages describe the tools and the ideas. The routine itself, step by step, is in the skills the installer copies to `.claude/skills/`:

| Skill | For |
|---|---|
| `foundry-founder` | Founding a project, the roadmap audit, planning a push, the decision register |
| `foundry-manager` | Running a rota slot: start, direct, block end, shift change |
| `foundry-employee` | Every hire: clock in, work inside the brief, report failures, hand in, clock out |
| `foundry-flow` | The charts: who edits and who reads |
| `foundry-bench` | An idle session proves it is cleared and reports ready for its next badge |
| `gym` | Building, running, grading and auditing a measure |

Where a page here and a tool disagree, the tool is right: each tool's module docstring is its own command reference.
