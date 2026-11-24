# The profile and the rules file

Two files in `.foundry/` make the shared skills and tools fit this project. `founder.py init` writes starters of both. You fill them in with the user; the manager and the crew read them and never edit them.

## `.foundry/foundry.toml`

Every key is optional and has a default. `foundry_profile.py show` prints the profile in force; `foundry_profile.py where` says which file was read and whether it parsed. A profile that cannot be read (a TOML error, a file that is not UTF-8, a key of the wrong kind such as a number in quotes or a list written as text, a `FOUNDRY_PROFILE` that names no file) stops every tool: each prints `foundry: the profile cannot be read: ...` and exits 2, and the whole crew stands still until it is fixed (only `where` and `founder.py doctor` still run). So check `where` after every edit, before you commit it. A table may be declared only once: the starter's `[models]` header is commented out, so uncomment it with its lines; never add a second header of a table that is there.

| Section | What it settles | Ask the user for |
|---|---|---|
| top level | `project`, `crew` (this crew's short name), `badge_prefix`, `main_branch` | The name |
| `[commands]` | `python`: the interpreter every brief names. `test`: the project's own test command, which `office.py hire` puts first in every brief's Tests line | Only when the host's bare `python` is the wrong one; the test command |
| `[paths]` | Where the tools, the office, the state, the map, the roadmap, the flow files, reviews, research, hand-offs, decisions and the gym live | Nothing, unless the repo already uses other folders |
| `[slots]` | When each rota slot starts; `round_every`, the round timer `office.py timers init` writes; `review_window_min`, the length of each slot's research-and-review window (`board.py init` and `board.py rota slots` write it into the rota) | The hours they want work to run |
| `[limits]` | `usage_stop`, `crew_max`, when a silent employee reads STALE or OVERDUE | **Every number** |
| `[resource]` | The one thing the crew queues for: its name, its seats, the variable a job reads its seat from, a `prepare` command, an `exclusive` pattern, a `status` command, `default_max`; `enforce_max` and `max_grace` (below) | Whether there is one, how many jobs it takes at once, and whether the queue may end a job that runs past its `--max` |
| `[measure]` | The counted-run, dev-run and selftest commands, the files only a grader writes, a run's record folders, the hand-in check, `sweep_skip` | How a run is started in this repo |
| `[roadmap]` | The shape of ids in the roadmap and the goal's name | Nothing, unless the project already numbers things |
| `[board]` | `phases_title`; `absolute_commands` (true: the map and the check print tool commands with the host's absolute paths; default: relative to the checkout) | Nothing |
| `[git]` | Whether the crew may push, how branches merge, where worktrees go | **Whether the crew may push** (default: never) |
| `[titles.<name>]` | An extra hire card, or a change to a built-in one (below) | Only when a kind of work needs rules no built-in card has |
| `[models]`, `[flagged.<title>]` | The model each title or role runs on; titles whose commits carry a trailer and get a heavy review | Which work they want on which model |
| `[crews.<name>]` | Other crews that work this way and where their lessons arrive from | Whether lessons should carry between their projects |
| `[hooks]` | The files only a tool may write, when they are not the road graph's two | Nothing |

Things to get right the first time:

- **The office must be git-ignored.** It holds the badge key, the time clock and the journal; a tracked office dirties the tree on every punch. `founder.py init` adds the ignore line and `founder.py doctor` checks it.
- **A resource only when the crew truly shares one.** With `name` empty the queue, the seats and the counted-run freeze of the queue all switch off. Two builders compiling on one machine is not by itself a shared resource; one VM, one GPU or one device that cannot run two jobs is.
- **Seats are what can run at once without the jobs seeing each other.** If two seats share a temp folder or a display, name the jobs that collide with `exclusive`, or use one seat.
- **`grader_owned` is the wall between builder and grader.** List every file a grader's verdict depends on. The tools use the list in two places: a grader's brief says "you own only" these, and `office.py handin` sends back any badge that is not a grader's whose branch changes a path under them, in a commit or in its tree against the base (a PROBLEM, whatever the badge's own `--files` say). A path you leave out of the list has no wall. The default lists `gym/prereg`, `gym/lanes`, `gym/run.py` and `gym/gym_kit.py`. `measure.records` (a run's series, charts and grades) has the same kind of wall: `handin` sends back a badge that is neither a grader's nor the manager's whose branch changes them.
- **The three `[measure]` lines.** `counted`, `dev` and `selftest` are how the tools start the gym: `sweep.py` runs `counted` for each lane and refuses to start when it is empty or has no `<lane>`; `office.py` reads `dev` to tell a dev job from a counted one in the queue and puts `selftest` in a brief's Tests line; `founder.py doctor` notes an empty `counted`. `gym_init.py init` prints all three for the gym it scaffolds (`<py> gym/run.py counted <lane>`, `... dev <lane>`, `... selftest`): copy them in. A single counted run is still queued, or run under a freeze, by the manager, with the command the lane's grader gives.
- **`[titles.<name>]`: a hire card.** `office.py hire --title <name>` takes the seven built-in cards (builder, fixer, grader, reviewer, scout, triager, cleaner) and the ones written here. A card starts from the built-in its `like` names and replaces any of `role` (builder, grader, reviewer, scout), `kinds` (a list of `session`, `temp`), `does`, `may_write`, `hands_in` (one line each, printed into the brief) and `independent` (true or false). `hire` refuses a title whose card is broken, and a kind the card does not allow. The card is what the brief prints; what the tools enforce beyond it is the role (`grader_owned`, below) and a `[flagged.<name>]` table of the same name.

  ```toml
  [titles.auditor]
  like = "reviewer"
  kinds = ["session"]
  ```
- **`[models]` and `[flagged.<title>]`.** `office.py hire` reads both. The brief prints `Model: <id>` from `[models]` (the title first, then the role), or from the hire's own `--model`. A title with a `[flagged.<title>]` table (`model`, `trailer`, at least one) is built on that model: the brief names it and says every commit ends with the trailer, `hire` refuses another `--model` unless `--force-model` is given, and `office.py handin` makes a commit of that badge without the trailer line a PROBLEM. No tool sets a session's model: the manager does, in the app.
- **`git.push`.** `office.py hire` prints the brief's push rule from it: `false` (the default) is "no push", `true` is "push only your own branch, never the main branch". No tool pushes, and none stops a push: the rule is the brief's and the skills'.
- **`resource.enforce_max`, `resource.max_grace`.** Off (the default), a job past its `--max` only reads OVERDUE and nothing ends it. With `enforce_max = true`, `rq.py` ends a `run` job still going at its `--max` plus `max_grace` (default `"2m"`), with everything it started, releases its seat and exits 124; `rq.py run --enforce-max` does the same for one job. Turn it on only when the user agrees that an under-estimated job may be killed: a counted run ended that way decided nothing and is run again. Every time in the queue carries a unit (`default_max = "30m"`, `--max 3h`): a unit is required, and a bare number is refused (in `default_max` it is not read, and 30 minutes stands). `office.py freeze on --max` and `sweep.py --max-per-lane` take a unit the same way.
- **`measure.no_verdict_exits`.** The exit codes of the `counted` command that mean "it ran and gave no verdict" (default `[2, 3]`: the scaffolded runner's refusal and its own failure). `sweep.py` lists such a lane apart and exits 1. A project with its own runner lists that runner's codes, or `[]`.
- **`git.worktrees`.** `founder.py init` git-ignores this folder and `founder.py doctor` makes it a PROBLEM when it is not ignored: an untracked worktree makes the main checkout read as dirty to a counted run. If you move it, ignore the new place.
- **`measure.sweep_skip`.** Globs of changed paths `sweep.py` leaves out when it asks whether the commits since the sweep was queued can move one of its lanes (grader notes, for example). Default: none.
- **Keys that are rules for people, not switches.** No tool reads `git.merge`, `measure.done_means` or `measure.sweep`: the skills tell the manager to look each up and act on it, so changing one changes nothing until a manager reads it. (`sweep.py run` is the counted sweep for any project; `measure.sweep` is only a note on how this project runs its own, if it has one.)
- **`hooks.protect` follows `paths.flow` when you leave it out.** The hook then protects `road.graph.json` and `road.edits.jsonl` under `paths.flow`, and finds the profile's reader under `paths.tools`. Set `hooks.protect` only to protect other files; once set, it is the whole list and no longer follows the flow folder.
- **Limits are recorded with the user's words.** When the user changes one in conversation ("stop at 95% this week"), write the change with its date in the rules file's "Always" section as well as the profile, so the next manager knows it was the user's and until when it holds. A shift's headcount or heavy work goes into the state the same way, with the words: `board.py shift set --crew-max <n> --heavy-ok yes|no --by <badge id> --words "<the user's own words>"` (the tool refuses either without `--words`, and keeps the words in the shift's `when`). The usage stop is `board.py usage <percent> --stop <n>`, the manager's.

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
