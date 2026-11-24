# The profile and the rules file

Two files in `.foundry/` make the shared skills and tools fit this project. `founder.py init` writes starters of both. You fill them in with the user; the manager and the crew read them and never edit them.

## `.foundry/foundry.toml`

Every key is optional and has a default. `foundry_profile.py show` prints the profile in force; `foundry_profile.py where` says which file was read and whether it parsed. A file that does not parse is reported and the defaults stand, so check `where` after every edit.

| Section | What it settles | Ask the user for |
|---|---|---|
| top level | `project`, `crew` (this crew's short name), `badge_prefix`, `main_branch` | The name |
| `[commands]` | `python`: the interpreter every brief names. `test`: the project's own test command, which `office.py hire` puts first in every brief's Tests line | Only when the host's bare `python` is the wrong one; the test command |
| `[paths]` | Where the tools, the office, the state, the map, the roadmap, the flow files, reviews, research, hand-offs, decisions and the gym live | Nothing, unless the repo already uses other folders |
| `[slots]` | When each rota slot starts, how often the manager's round fires, the research-and-review window | The hours they want work to run |
| `[limits]` | `usage_stop`, `crew_max`, when a silent employee reads STALE or OVERDUE | **Every number** |
| `[resource]` | The one thing the crew queues for: its name, its seats, the variable a job reads its seat from, a `prepare` command, an `exclusive` pattern, a `status` command | Whether there is one, and how many jobs it takes at once |
| `[measure]` | The counted-run and dev-run commands, the files only a grader writes, a run's record folders, the hand-in check | How a run is started in this repo |
| `[roadmap]` | The shape of ids in the roadmap and the goal's name | Nothing, unless the project already numbers things |
| `[git]` | Whether the crew may push, how branches merge, where worktrees go | **Whether the crew may push** (default: never) |
| `[models]`, `[flagged.<title>]` | The model each title runs on; titles whose commits carry a trailer and get a heavy review | Which work they want on which model |
| `[crews.<name>]` | Other crews that work this way and where their lessons arrive from | Whether lessons should carry between their projects |
| `[hooks]` | The files only a tool may write | Nothing |

Things to get right the first time:

- **The office must be git-ignored.** It holds the badge key, the time clock and the journal; a tracked office dirties the tree on every punch. `founder.py init` adds the ignore line and `founder.py doctor` checks it.
- **A resource only when the crew truly shares one.** With `name` empty the queue, the seats and the counted-run freeze of the queue all switch off. Two builders compiling on one machine is not by itself a shared resource; one VM, one GPU or one device that cannot run two jobs is.
- **Seats are what can run at once without the jobs seeing each other.** If two seats share a temp folder or a display, name the jobs that collide with `exclusive`, or use one seat.
- **`grader_owned` is the wall between builder and grader.** List every file a grader's verdict depends on. The tools use the list in two places: a grader's brief says "you own only" these, and `office.py handin` sends back any badge that is not a grader's whose commits change a path under them (a PROBLEM, whatever the badge's own `--files` say). A path you leave out of the list has no wall.
- **Keys that are rules for people, not switches.** No tool reads `[models]`, `[flagged]`, `git.push`, `git.merge`, `measure.done_means`, `measure.sweep`, `slots.round_every` or `slots.review_window_min`: the skills tell the manager to look each up and act on it (the session's model and a flagged title's trailer, whether to push, the round timer's interval, the length of each slot's `rr` window in the state). Changing one changes nothing until a manager reads it; the hire brief always prints "no push". `measure.counted` is read only by `founder.py doctor` (a note when it is empty); the manager queues the command itself.
- **`hooks.protect` does not follow `paths.flow`.** If you move the flow folder, change the two protected paths with it.
- **Limits are recorded with the user's words.** When the user changes one in conversation ("stop at 95% this week"), write the change with its date in the rules file's "Always" section as well as the profile, so the next manager knows it was the user's and until when it holds.

## `.foundry/rules.md`

The project's standing rules and lessons, by situation: Always, The host, Using the shared resource, Before a counted run, Before a builder hands in, Shared files, Reporting, Closing a push. A hire reads the sections its brief lists and no more, so keep each line whole in itself.

What belongs there:

- What the user has told this project's crew that no other project needs ("the shared PC also runs the main project's tests: ask before anything heavy").
- Facts about this host that have already cost someone a run (an interpreter alias, a shell that hangs on stdin, a tool that is not installed).
- Facts about this repository that are not visible from one file (a config every lane reads, a generated page that must be committed with its tool).

What does not: anything the skills already say, the history of how a rule was found (one clause is enough), and run results.

## Changing either file later

A profile or rules change is a change to how the crew works:

1. It starts as a journal entry (anyone's) or a decision (yours).
2. You write the change on a branch; the user approves it in their own words.
3. It merges at a slot boundary, after a review, never while a counted run is queued. The hand-off entry names it, so the next manager briefs new crew from it. Crew on the clock keep the brief they were given.
