# The employee brief

`office.py hire` prints the badge line and the brief's skeleton: the badge, the line that says to load the `foundry-employee` skill first, the clock-in command with the interpreter and tool paths resolved, the job, done-when, the lane, the files, how it reaches the shared resource, the estimate, the Tests line, the known tooling bugs and the report commands. A session starts knowing only its brief, so add what it needs above that skeleton, in your own words. Never write "based on the findings": say what the findings are.

## Titles

A title is a card of rules, not a rank. It says what an employee may write, whether it may use the shared resource, whether it must be independent of the build, and how it hands in. There is no seniority, and no employee directs another. `office.py hire` knows four roles; hire each title under the role in the table and paste its card's row into the brief as its rules.

| Title | Hire as `--role` | Does | May write | Shared resource | Kind | Independent of the build | Hands in |
|---|---|---|---|---|---|---|---|
| **Builder** | builder | One block of the plan | Its own worktree, the files in its brief | Yes, by the queue | Session; a temp only for work that needs no queue | No | By file, with commits and the checks it ran |
| **Fixer** | builder | One numbered failure, reproduced first | As a builder | As a builder | As a builder | No | By file, with the failing case before and after the fix |
| **Grader** | grader | The measure for one checkpoint: sets it before data, grades the counted run | Only the grader's files and its notes | Reads run folders; a dev run only if the brief says so | Session, never a temp | Yes: never opens the builder's code | A verdict word and the grade file |
| **Reviewer** | reviewer | Reads a commit range before it merges | Only its report | No, unless the brief names one short job | Session, or a temp on a timer turn | Yes: did not build it | Findings by severity with `file:line`, then GO, GO-with-fixes or NO-GO |
| **Scout** (researcher) | scout | Answers numbered questions from primary sources | Only its report | No | Session, or a temp | n/a | An answer per question, the confidence, what is unknown |
| **Triager** | scout | Finds the cause of failures; fixes nothing | Only its report | Reads logs; a dev run only if the brief says so | Temp or session | n/a | A cause per failure, each marked confirmed or a lead |
| **Cleaner** | scout | Frees room on the shared resource at slot end | Nothing in the repo | Yes, between the owners' steps, after asking each seat's owner what its running job reads | Temp | n/a | Sizes before and after, and what was removed |

- **The roles the tool takes.** `--role` is `builder`, `grader`, `reviewer` or `scout`, in any case; any other word is refused (exit 3), and there is no `--title`. A grader must be `--kind session` and name its `--lane`. The title lives only in the brief you finish.
- **Model tiers.** The profile's `[models]` table maps a role or title to a model; empty means the session's own. `office.py hire` does not read it: you look the model up (`foundry_profile.py show models`) and start or switch the session on it (`app.md`, "Models").
- **A flagged title** (the profile's `[flagged]` table, for example a security fixer): it runs on the model the profile names, every commit carries the profile's trailer, and its commits get an in-depth review by the next slot's reviewer. `office.py hire` does not read `[flagged]` either, so the skeleton says none of it: write all three into the brief yourself (`foundry_profile.py show flagged` prints the model and the trailer). A commit built on another model names that model instead.
- **Verdict words.** A grader hands in one of PASS, MARGINAL, FAIL, MEASURING, VOID, STARVED. `board.py` also draws SATURATED (the gym skill's word for a test pinned at its maximum); it knows no other word. `office.py fail --verdict` takes any text, so write the word as the grade file has it.
- **A project's own title** is a card in `.foundry/rules.md` with the same columns. Add one only when its rules differ from every card above.
- **A bench** is not a title (`app.md`, "Bench sessions").

## Hiring cases

- **A fix round on a reviewed branch** goes to its builder's own session under a new badge: `hire`, then `assign` the old session. The brief names the review report and the branch to keep. The old badge stays closed.
- **A grader's cross-lane request** (a builder must amend another lane's contract or harness) widens that builder's badge in the same step: `office.py amend <builder id> --by "<your line>" --add-files <those files>`, then tell the builder.
- **A reprint.** `office.py brief EMP-07 --by "<your line>"` reprints the badge line and the brief from the roster, for a bench re-badge or a refused session start; `amend` ends by printing it. `office.py me --badge "<its line>"` is the employee's own copy, for a session that was cleared.
- **Known tooling bugs** and their workarounds go in `state.tooling_known` (one line each); `hire` prints them into every brief. Remove a line when its fix is merged.
- **A numbered decision record** (an ADR): hire with `--adr` (item 1 below). The brief then names its file, `<paths.decisions>/<NNNN>-<topic>.md`. An ADR is a design record a builder or scout writes; it is not a D-number: the user's decisions are `board.py decide`'s, and their briefs lie in the same folder as `D<n>-<topic>.md`.

## What to add

1. **One paragraph of context.** The shift and its milestone, the block this job belongs to, and what exists already (commits, contracts, run ids). Name the files and docs to read first, and the sections of `.foundry/rules.md` the job needs. For each failure or defect you assign, name the branch or commit it lives on, and check it exists there (a defect on an unmerged branch is not on the main branch).
   - A job on a milestone names its road-graph node (`flow.py graph show M1`), so the employee reads the same links. A job on a step of a plan names the plan and the step.
   - A job that writes a numbered decision record is hired with `--adr`: the office reserves its number from one counter and prints it in the brief. Never write "the next free number on your branch"; drafts cite each other by file name, not number.
2. **What done looks like.** It must be checkable and cover the whole job: a commit with these files, a test green, a prereg amendment pinned, a run graded with a verdict word. Repeat it in `--done-when` so the map's tile shows it.
   - A job that ends in a dev run says where the run folder lands and puts `office.py progress --run <that folder>` in its done-when, so `office.py runs` lists it for the grader.
   - A done-when for a High finding names the code and its check on the running product ("the sender built, and the count of sends is above 0 in a started build"), never a document. "An amendment describing the fix" lets a High fix land as prose. A design-only step is its own block, with its own done-when, ahead of the block that builds it.
   - A job that pins a reference (an expected colour, a crop, a region, an expected output) maps it first: where it sits, and that it holds across the states the product can be in. The reference goes in with that map, and the grader's prereg asks for it. A reference taken without the map can measure a state (what happened to have focus), not the thing.
   - Name a list, function or variable by its file and its enclosing function ("`bad` in `selftest()` of `tools/check.py`"), never by a bare name. Search for the name first: one name can mean two things in one file.
   - Name every input file by its path, never by what it does ("the allow-list"). Check the path exists and holds what you say before you send the brief.
   - A job whose tool writes a checked-in file (a generated page) owns that file's path too, so the tool and its output land together.
   - A job whose tool runs only on the shared resource gets a short queue slot (`--rq`), or its brief says its first real run is a later queued job. Never leave a builder to find out that its checks cannot run where it works.
3. **What not to touch.** The files other employees own, the state file and the map, the founder's files (the roadmap, the profile, the rules file), the road graph, other seats. A grader also gets the builder's code ("never opened").
4. **Where it works.** Its worktree (or "the main checkout: touch only your files, commit nothing outside them, switch no branch"), and how it reaches the shared resource (`rq.py run --id <its badge>`).
   - The branch is the one line `office.py hire` prints. A session in its own worktree works on the branch it starts on (a new one at the main branch's tip, or a fix round's branch kept as it is) and reports its name. A temp or bench cuts `claude/<job>` from the main branch or from the sha you name. Never add a second branch instruction beside that line; name the sha or branch the line refers to.
   - If a counted run is or may be queued during the job: "commit only in your worktree; nothing in the main checkout while a counted run is queued or running".
   - If it will wait on another badge's job: "post progress with `--waiting-on <that badge>` while you wait".
5. **Tests.** Name the commands that test what it touches, run in its worktree: the selftest of each tool it changes (`office.py selftest`, `board.py selftest`, `rq.py selftest`, the gym's own `measure.selftest`), and the project's checks from `.foundry/rules.md`. `office.py hire` builds the Tests line from the profile's `commands.test` (the project's own test command, first when it is set), the files and the lane: none for a job that owns only docs or contracts (it says so in the hand-in), a lane job's own selftest, the selftest of each foundry tool the files cover, then the gym's `measure.selftest`. Add no second Tests line that disagrees with it. Never tell an employee to run `board.py check` or `build` in the main checkout.
   - A fix to a file reader (a run loader, a series or prereg parser) gets a selftest that writes the file to disk and goes through the reader itself, not one that hands the parsed data in from memory. Checks that inject the data can pass with the fix reverted.
6. **Heavy work.** Pre-approved for this shift (`heavy_ok`), or "ask the manager on the clock first".
7. **Harness config.** A job that touches the harness's settings or hooks waits for the user's approval typed in that session, not a quote of it. Ask the user to type it there before you send the brief. Such a job goes to a bench session, never a temp: a temp has no box for the user to type in.
8. **How to end.** `office.py handin` in its worktree, then clock out with the result and commits (a temp with no worktree and no commits skips `handin`: "A temp brief"). Say which of its queued jobs need `--all-seats`. `office.py handin` runs the profile's hand-in check (`measure.handin_check`) by itself when the branch changes a file that matches `measure.handin_check_paths`; say whether the employee also runs it first and gives its numbers. A session's final message is its report: what is done, what is not, the verdicts, the commits, the next step. Then it messages you and stops. Never tell it to clear itself (`app.md`).

## Example (a grader session)

```
**G1 grader** - pins the builder's answers and grades the counted G1 run.

M1 startup (shift m1-startup, slot day). The contract is gym/contracts/G1-artifacts.md (<commit>);
your prereg and lane exist (gym/prereg/G1.json, gym/lanes/g1_startup.py, <commit>). The builder's dated
amendment answering Q1-Q9 is <commit>. Read gym/contracts/G1-grader-notes.md first.

Done when: a prereg amendment pins the amendment's sha256 before any G1 data; the dry run calibrates;
the counted run (block 15:30, queued by the manager) is graded with a verdict word and a grade file.

You work in your own worktree and touch only gym/prereg/G1.json, gym/lanes/g1_startup.py and
gym/contracts/G1-grader-notes.md; commit only those. Never open src/.
Read the run folder, the main branch's contract and prereg, and your own files, never another worktree; for
what a harness writes, ask the builder for the record's form.
Heavy work: none; you grade run folders the builder posts.
While you wait on the builder's dev run or the counted run, post `progress --waiting-on <its badge or queue id>`
at once.
A dev run of a timing check takes `--all-seats`; a one-seat run shares the machine, so say which bars it
cannot decide.

<the skeleton office.py hire printed>
```

## Research and review briefs

Both are hires of the slot's window, hired new. Each touches only its report file, uses the shared resource only if the brief names one short job, and never edits the product's code, the gym or the map.

While a counted run is in the queue, each works and commits in its own worktree and never writes into the main checkout, not even a draft.

Name the reviews a job must read by milestone or lane ("the reviews of G1"), not by file: one that merges mid-job is then still in scope, and `office.py me` lists it. When one merges, send the employee one line.

- **Reviewer:** the commit range (`<from>..<to>`, the previous hand-off's tree to this one's), each block's done-when, the contract and its amendments, the standing rules. Ask for:
  - findings ranked by severity, each with `file:line`, what is wrong, and why it matters for the lane;
  - a list of claims the diff does not support;
  - "nothing found" when that is the honest answer;
  - one closing word: GO, GO-with-fixes or NO-GO.
  Report: `<paths.reviews>/<date>-<slot>.md`.
  - Say where the code's tests can run. If they run only on the shared resource, name the one job it may queue once a seat frees (`rq.py run --id <its badge> --job "the branch's tests" --max 30m -- <the test command>`; `--job` is required), and hire it with `--rq`, or tell it to read without running.
  - Name the branch, so it reads files with `git show <branch>:<path>` and `git diff <main>...<branch> -- <path>` from its own worktree, one git command per call. A git command aimed at another worktree, or git inside a shell loop, is refused in an isolated worktree.
  - Ask it to run each new check or selftest case against the base sha as well as the tip: `git archive -o <scratchpad>/base.tar <base sha>` (one git command), unpacked in the scratchpad, and the new checks run there. A check that passes on the base proves nothing, and the report says which fail there.
- **Researcher:** two to four numbered questions the coming blocks or the next queued shift must answer, why each matters, and where it will be used. Ask for primary sources (upstream docs, specs, release notes, source files at a pinned version) with links and versions, a direct answer per question, the confidence, and what is still unknown. Report: `<paths.research>/<date>-<slot>-<topic>.md`. A temp reads upstream pages with the web-fetch tool, not a shell fetch: the harness's guard for isolated worktrees can refuse a shell line that names a code host, and no project change lifts that guard. Research that needs a shell fetch goes to a bench session.

## A temp brief

Shorter: the skeleton plus the question and the shape of the answer you want back ("a list of `file:line` with one sentence each"). A temp clocks in first and out last; it reports failures like anyone else.

- Hand-in: a temp that only reads, with no worktree of its own and no commits, returns its report as its final message and skips `office.py handin` (the skeleton's hand-in line is for a job with a worktree; say so in the brief). A temp started in its own worktree that commits (a report file, a patch) runs `office.py handin` there like a session, before it clocks out.

- Never ask any employee to run `journal.py plan`, `carry`, `ready`, `approve` or `set`: it runs `journal.py add` only, drafts plan text in its report, and you enter it.
- A temp is isolated in its own worktree: the harness refuses any git command aimed at another directory. So it reads another branch's or commit's files with `git show <sha>:<path>` from its own worktree (into its scratchpad when it must run them). Say so in the brief, and give it the sha, not a worktree to look in.
- To test a branch tip, have it cut its branch from that sha (`git switch -c claude/<job> <sha>`).
- Tell it to run one git command per shell call, chained with nothing, from its first git command: the harness refuses chained git lines there. A command that is still refused is stopped and reported, not split.

## The manager line

When you paste a manager line into a message, take it from `office.py roster`. The brief `office.py hire` prints already ends with the manager and its session as the roster has them at print time, and `office.py me` and `office.py brief` reprint them as they are then.
