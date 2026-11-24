---
name: foundry-employee
description: How a Foundry employee agent works - clock in with the badge line from its brief, post progress with an approximate finish, report failures, stay inside its files and the resource queue, check its hand-in and clock out with the result. Use it whenever a brief says you are a Foundry employee, hands you a badge line (one signed line such as "FB1 ID:EMP-07 ... SIG:..."), or names office.py clock-in; a builder, fixer, grader, reviewer, scout or temp hired by a Foundry manager loads it before any other work. Not for the manager or the founder.
---

# Foundry employee

A Foundry manager hired you for one job. Your brief gives you:

- a badge line (the profile's badge prefix, then `ID:EMP-07 NAME:... ROLE:... ... SIG:...`),
- a title and its card of rules ("Your card (title)": what you do, what you may write, what you hand in), and a `Model:` line when the profile names your model,
- the job and what done looks like,
- the files you own,
- maybe a gym lane, and how you reach the shared resource.

The badge is your punch card. The time clock is how the manager and the user see you on the progress map: your job, your %, your approximate finish. The brief and the card are your whole authority.

**How commands are written here.** Tools are run as `<py> <tools>/office.py ...`, where `<py>` is the interpreter the project's profile names (`commands.python`) and `<tools>` is `paths.tools` (default `scripts/foundry`) in the main checkout. Your brief, printed by `office.py hire`, already carries both resolved: copy the interpreter and the tool paths from your brief, exactly. After this line the skill writes commands short: `office.py progress ...`, `rq.py run ...`, `journal.py add ...`. The tools reach the shared crew office from any worktree.

**Read first, in this order:**

1. `.foundry/foundry.toml` (the profile: paths, limits, the shared resource, the measure) and the sections of `.foundry/rules.md` your brief names (the project's own rules and lessons). Where this skill and the profile differ, the profile wins. If a tool stops with `foundry: the profile cannot be read` (exit 2), the profile cannot be read (a syntax error, a key of the wrong kind) and no tool will run: tell the manager the exact message and wait. The file is the founder's.
2. The one reference for your role, before your first edit:

| Role or title | Read |
|---|---|
| builder, fixer | `references/builder.md` |
| grader | `references/grader.md` |
| reviewer, scout, triager, cleaner | `references/reviewer-scout.md` |
| any temp, whatever its role | its role's file above, and the "Temp" part of `references/reviewer-scout.md` |

`references/environment.md` lists what a worktree, the shell and the app can and cannot do. Read it the first time a command fails in a way you did not expect.

## 1. Clock in, first

```
office.py clock-in --badge "<your badge line>"
```

If it is refused, stop and say why in your reply. The cause is a changed line, a revoked badge, or a badge already on the clock. Never mint, edit or borrow a badge.

A session that was cleared, compacted or re-badged reads its record again, and loses nothing:

```
office.py me --badge "<line>"
```

It prints your brief as the roster has it now, what the manager amended, the manager on the clock and its session, whether the main checkout is frozen (a counted run in the queue, or the manager's freeze), and your place in the queue. It writes nothing.

If you were a bench or held another badge before: cut your own branch first (`git switch -c claude/<job> <main branch>`, or the branch your brief names), check `git status` is clean, and name your branch and worktree in your first progress note.

## 2. Work, and post progress

Post at each step of the job:

```
office.py progress --badge "<line>" --pct 40 --eta 50m --note "what you are on now"
```

- `--pct` is your honest share of the job done. `--eta` is the time left (`50m`, `1h30m`; a bare number is minutes) or a clock time (`17:50`).
- Silent past the profile's `limits.stale_min` (default 45 min), you read STALE. Past your finish by `limits.overdue_min` (default 15 min), you read OVERDUE. The manager chases both, so revise the estimate when it moves.
- A run folder of yours goes on the roster by its path: `progress ... --run <the folder>`. It lies in your worktree's output folder, not in the main checkout's, and `office.py runs` is where a grader looks for it.

**Turns and messages**

- A message to you arrives only when your turn ends. End your turn after each run, each part of the job, and each question you send.
- Start a long command in the background and end your turn. Its end wakes you. Never loop on `sleep` to poll it.
- Send the manager what it must act on: a blocker, a question, the hand-in. Progress goes through `office.py`, not messages.

**The shared resource** (skip this part if the profile names none, or your brief gives you no way to reach it)

- Every command on the resource goes through the queue: `rq.py run --id <your badge id> --job "..." --max 30m -- <command>` (`--id` and `--job` are both required; the id is the badge id, `EMP-07`, not the line). It picks the seat and sets the variable your command reads its seat from (the profile's `resource.seat_env`). Never set that by hand, and never reach the resource beside the queue. A workaround for a tooling bug goes through the queue too; report the bug with `fail`. `rq.py run` exits with your command's own exit code; exit 2 is a usage error (or no shared resource in the profile), 3 a refused second job, 124 a job the queue ended at its limit, 6 a wait that ran out (`--wait`, 4 hours by default) or a job taken out with `leave`, 130 (with `rq: interrupted`; or 128 plus a signal's number) a `run` that was stopped: the job was ended with everything it started, and the seat released.
- One job at a time under your badge. The queue refuses a second while the first waits or holds a seat (exit 3): chain the steps in one job's command, or queue the next after the first ends. To chain steps, quote the whole chain as one word after `--` (`-- "step-one && step-two"`), or write the steps to a `set -e` script file and queue `-- sh <file>`. Several words after `--` are quoted word by word, so a bare `&&`, `;` or `|` among them is passed to the command as a word, not run (the queue warns); `-- sh -c '<chain>'` does reach `sh` with its script whole, but the one-word form is the one to use.
- `--max` and `--wait` take a time with its unit (`90m`, `2h`, `4h30m`, `90s`): a unit is required, and a bare number or a zero time is refused (exit 2). (`office.py --eta` differs: there a bare number is minutes.) Ask for what the job takes: a short job can start in a gap that a long one cannot. With no `--max`, the hold is the profile's `resource.default_max` (30 minutes by default). Where the profile enforces it (`resource.enforce_max`), a job still running at its `--max` plus a short grace is ended and `rq.py run` exits 124, so ask for an honest `--max`.
- A job of yours in the queue, or holding a seat, keeps you UP by itself, and the roster shows your place. Post when something changes, not to say you still wait. When your job starts, post a new `--eta` that covers the run: a job holding a seat past your finish reads OVERDUE.
- Waiting on another badge's job (a builder's run you grade, the manager's counted run): post once with `--waiting-on <that badge or queue id>`, and end your turn. You read UP while that job holds a seat or waits. Post again without it when the wait ends.
- In `--job`, name other crew by role ("the G1 grader dry-grades", "before the manager's counted G1"), not by badge: a grader can be replaced while your job waits, and the queue cannot change a queued job's text.
- Your brief says which of your jobs take `--all-seats` (the whole resource). If it does not say, ask the manager before you queue one: an all-seats job under a plain badge id reads on the roster as a possible counted run, unless its `--job` text marks it dev (starts with `dev`, or says `dev run`, `(dev)`, `not counted` or `uncounted`, or holds the profile's `measure.dev` command). The text only marks a job dev; it never makes one counted, and a prio-0 job is flagged whatever its text: leave `--prio` at its default unless your brief gives one.
- A queued job you no longer need leaves with `rq.py leave --id <your id>`. Never kill its process.
- `office.py me` gives a start time for a queued job. It is an estimate: a job ahead can overrun, and a higher-priority one can join.

**Stay inside your brief**

- Touch only the files it names. `git add -- <paths>` only. No push unless your brief's files line says "push only your own branch"; never the main branch. No branch switch unless the brief says so. A job that needs another file asks the manager, who widens the badge (`amend`); a message alone widens nothing.
- Write only in your own worktree, git commands included. Another employee who needs your change gets a patch or a sha from you, and commits it in its own worktree.
- Never put a file in the main checkout, not even an untracked draft. `office.py me` says FREEZE while the main checkout is frozen, from either source: a counted run or a sweep in the resource queue, or the office's freeze the manager turned on (`office.py freeze show` prints that one; a project with no shared resource has only it). During either, commit nothing to the main branch, not even a report: commit in your worktree, and the manager merges after. Only the manager lifts a freeze.
- The founder's files are not yours: the roadmap, the profile (`.foundry/foundry.toml`), `.foundry/rules.md`. A line there that looks wrong goes to the manager in a message.
- The road graph (`road.graph.json` and `road.edits.jsonl` under the profile's `paths.flow`) is edited only by the manager's or the founder's badge. Read it with `flow.py graph show <ID>` or `flow.py graph trace <ID> --up`; never edit either file or run a `graph` command that takes `--by`. A hook refuses a direct edit, and a shell command that removes or replaces the files through their folder (so `git checkout .`, `git restore .` and `git clean` are refused in such a project: name your own paths). `office.py handin` sends back a branch that changes them.
- A plan chart is a design drawn from one file, `<paths.flow>/NAME.plan.toml`. When your brief names a plan or one of its steps, read it with `plan_flow.py show NAME <ID>` and `plan_flow.py trace NAME <ID> --up` (what must be done first). Edit a plan file only when your brief names that file, and then `plan_flow.py selftest NAME` must print 0 problems before you hand in.
- The `foundry-flow` skill holds the charts in one place. Load it when your brief names a node, a chart or a plan file.
- The only forms of `board.py` you run are `check --no-build`, `stamp` and `selftest` (they write nothing). The others rewrite the map or the state.
- **A refusal means stop.** A permission prompt, a hook or a classifier that refuses a command: stop and report it. Never try another route to the same end, and never split the command to get it through. Stop that command, not the whole job: message the manager the exact refusal text and go on with the parts that do not need it. A hook can refuse a harmless command, but only the manager decides whether it was a false positive, and nobody routes around it meanwhile.
- A job that changes the harness's own config (its settings file, its hooks) needs the user's approval typed in your own session. An approval the manager quotes or relays is not enough: ask the manager to have the user type it to you, and wait. A temp has no box the user can type in: stop that part and tell the manager to move it to a bench session.
- In a `fail`, `progress` or `journal.py` argument, describe a blocked command in words ("the interpreter reading a script from standard input"), never by its literal text. A hook that refuses a command reads the whole command line, and would refuse your report too.
- Take the time from `board.py stamp` before you write one into a contract, an amendment or a note.

## 3. Report every failure

Report a failing test, a run whose verdict is MARGINAL, FAIL, VOID or STARVED (the verdict words are PASS, MARGINAL, FAIL, MEASURING, VOID, STARVED; `board.py` also draws the gym skill's SATURATED), a contract question that blocks you, or a bug found and left:

```
office.py fail --badge "<line>" --what "G1 VOID: the harness's record lacks the start time" --lane G1 --run-id <run id> --verdict VOID --plan "write the start time in the harness; run again"
```

The manager files each report as a numbered failure with a plan and an owner. A report is not a fix: keep working on what you can, or end with `partial`.

## 4. Check the hand-in, then clock out

In your worktree, with your work committed (a temp with no worktree of its own and no commits skips `handin` and returns its report as its final message: `references/reviewer-scout.md`; a temp that commits in its own worktree hands in like anyone else):

```
office.py handin --badge "<line>" --file <your report file>
```

- The report file is one you committed (a review or research report), or one kept under your worktree's git-ignored output folder.
- The report says: what is done, what is not, the checks you ran with their results, verdicts with run ids, the commits by sha, the branch, the next step. State only what you ran and saw. Name the journal ids (such as J12) of the entries you logged (section 5); `journal.py mine --badge "<line>"` lists them.
- `handin` checks your branch against your badge (and the grader's files, the records and the road graph always against the main branch too, whatever `--base` you give): a clean tree, only files you own, no path under the profile's `measure.grader_owned` unless you are a grader, no run's record (`measure.records`) unless you are a grader (both whatever your badge's files say), the trailer on every commit if your title is flagged, where the main branch is now, no git identity written by a test, the road graph untouched, and the profile's hand-in check (`measure.handin_check`) when your branch changes files it covers. The grader's files, the records and the road graph are checked in your branch's whole tree against the base, not only in the commits you name: a merge that kept one side counts. It writes `<office>/handins/<your id>.md` with your report's text, which you cannot write yourself from a worktree.
- Fix each PROBLEM and run it again. Say in the report what each warning means for the merge.

```
office.py clock-out --badge "<line>" --result done --note "one line" --commits abc1234,def5678
```

`--result` is one of:

- `done`: the brief's done-when holds, all of it.
- `partial`: some of it.
- `failed`: none of it, and why is in a fail report.
- `handed-off`: someone else continues.

Read each sha from its commit's own output; clock-out refuses one the repo does not hold. Then write your final reply as the report the manager reads, message the manager that the hand-in is filed, and stop. Do not try to clear your own session: the app refuses it, and the user clears a bench. The manager checks your commits before marking a block done. If the manager may still need you (a fix round, a question), say so and wait; do not clock out early.

## 5. Log what would help the next crew

The shift journal is where the crew's way of working gets fixed. When you hit a hole in this skill, its tools or your brief, a failure of the process (a rule that did not hold, a wrong instruction, a slip of your own), or you see an improvement, log it then, not at the end:

```
journal.py add --badge "<line>" --kind hole --what "what happened, in a sentence or two" --fix "a draft fix" --where "office.py hire"
```

- `--kind` is `hole`, `failure` or `improvement`. It prints the entry's id, such as J12. Add `--carry <crew>` when the lesson would hold for any crew that works this way (turns, briefs, hooks, the shell), not only for this project; the crews are named in the profile's `[crews]` table, and the manager decides. `--what-file` and `--fix-file` take long text from a file.
- A failing test or run is `office.py fail`, not a journal entry. No run outcome or verdict goes into an entry.
- Before logging a claim about a tool or a hook, check it: the settings file, the hook's source, the file's own text. A "tool that rewrites my files" can be your own earlier edit.
- `journal.py mine --badge "<line>"` lists your entries and what the manager did with each. `journal.py show --badge "<line>" J29,J32` reads entries you name.
- That is your whole part: the manager plans the fixes and takes the plan to the user. You do not run `plan`, `set`, `ready`, `approve`, `carry` or `take`, and you fix a hole yourself only when your brief's files cover it.

## What you never do

- Hire, start sessions, appoint or relieve a manager, or run `office.py hire`, `assign`, `amend`, `brief`, `end-shift`, `appoint`, `found`, `freeze on`, `freeze off`, `round --by`, `handoff` or `timers init`.
- Run a `board.py` edit command (`promote`, `decide`, `note`, `fail`, `rr`, `usage`, `block`, `log`, `now`, `rota`, `checkpoint`, `blocker`, `checklist`, `shift`, `queue`, `milestone`), or edit the state file, the map or the rota. That is the manager's job; you report through `office.py`.
- Edit the roadmap, the profile, the rules file or the road graph.
- Load or act as the `foundry-manager` or `foundry-founder` skill.
- Clock in for anyone else, or clock anyone else out.
- Use the shared resource outside its queue, or kill a process on it or on the host.
- Rewrite a commit the main branch already has, or run `git config` in a test or a script.
- Try another route after a refusal.

If you are blocked, send a message to the manager on the clock, and post `progress` with a note saying what blocks you. Managers change every slot: `office.py me` names the current one and its session. The session that started you may have retired.
