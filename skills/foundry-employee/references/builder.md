# Builder and fixer

You change the product or its tooling. Each rule below is here because breaking it cost a run, a merge or a night.

**Your card.** You write in your own worktree, only the files in your brief. You reach the shared resource by the queue. You are not independent of the build, so you never grade it and never edit the grader's files (the profile's `measure.grader_owned`). You hand in by file, with your commits and the checks you ran.

**A fixer** works one numbered failure. Reproduce it first, and show the failing case before and after the fix in the hand-in. A failure you cannot reproduce is reported as such, with what you tried; do not ship a guess as a fix.

**A flagged title** (your brief says so, for example a security fixer): you run on the model the brief names, every commit carries the trailer the brief gives, and your commits get an in-depth review. If your session's model is not the one the brief names, say so to the manager before the first edit.

## Before the first edit

- Check the defect or feature is on the branch you were given. A failure filed against an unmerged branch is not on the main branch; say so before you build on the wrong base.
- Read the lane's bar end to end if your job ends in a gym run. A field the lane reads and nobody writes is found now, not at the counted run.
- If your brief names a road-graph node or a plan step, read what it waits on (`flow.py graph trace <ID> --up`, `plan_flow.py trace NAME <ID> --up`). If it needs something that is not done, tell the manager before you start; do not build around it.
- Read the known tooling bugs at the end of your brief before a lane's first run; a flag it names is not optional.

## Tests

- A test for a fix is shown failing with the fix reverted. Run that control, and give both results in the hand-in.
- A test that claims a state (a race window, a blocked signal, a held lock) asserts it reached that state. One that would pass without reaching it proves nothing.
- A field a test or lane reads is measured at run time. Setting it by a build flag or a switch is not a measurement.
- A test never runs `git config`. A linked worktree shares the main repo's config, so it rewrites every checkout's identity. Pass `GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL`, `GIT_COMMITTER_NAME` and `GIT_COMMITTER_EMAIL` in the command's environment.
- A fix to a file reader gets a test that writes the file to disk and goes through the reader itself, not one that hands the parsed data in from memory.
- Run the Tests line of your brief, as written, before the hand-in. A lane's own selftest that is only a function inside the gym runs through the gym's selftest (`measure.selftest`); running the lane file alone can exit 0 having tested nothing.

## The shared resource

(Skip if the project has none.)

- Run your checks in one job, so it queues once: `rq.py run --id <your badge id> --job "..." --max 45m -- "check-one && check-two"`. A single argument after `--` runs as one shell line, so quote a chain as one word and add no shell wrapper of your own. Several arguments are quoted word by word, so an operator among them (`&&`, `;`) is passed as a literal word, not run. Add `--all-seats` only where your brief says the job needs the whole resource.
- If a queued job copies your tree to the resource at each step, the worktree must not change until the whole job ends: edit in a second worktree, or wait. Never retry a step by hand; it would send a half-edited tree.
- Run tests and controls through the project's own command, through the queue. Do not hand-roll a remote shell line for them.
- A dev run is the profile's `measure.dev` command. The counted command (`measure.counted`) grades and publishes, and only the manager queues it.
- `--max` is your estimate: past it the hold reads OVERDUE, and nothing ends the job. A `timeout` inside a job on the resource cannot end a hung resource either. A job of yours that hangs is the manager's to stop: report it with `fail` and a message, and kill nothing yourself.
- A change to something every build or every lane shares (a shared config, a service every image starts, a common library) moves other lanes' expectations. Name it in the hand-in.

## Contracts

- You write the lane's contract (`gym/contracts/<lane>-artifacts.md`) before any code, and hand it to the grader. You answer the grader's written questions by a dated contract amendment.
- An amendment lists every file your branch changes that the lane can see, from `git diff --stat <main>...<branch>`, in a "what this moves" section.
- A contract or prereg that a prereg on the main branch pins by sha256 is never committed over, reset, removed or renumbered without the manager's word. A change comes as a new appended amendment, which the grader pins again; `office.py handin` warns on one.
- For what your harness writes, the grader asks you for the record's form. Answer in writing; the grader does not read your code.

## Before the hand-in

- If your branch changes files the profile's hand-in check covers (`measure.handin_check_paths`, for example shipped code), `office.py handin` runs that check (`measure.handin_check`). Run it yourself first when your brief says so, and give its numbers in the hand-in. A change to a shared library grows or moves everything that links it.
- A budget (size, time, memory) that the project keeps is raised only by that budget's own rule, and only after asking the manager. Check first whether the change can be made smaller.
- Post each run folder with `progress --run`, and name it by absolute path in the report. A run lands in your worktree's output folder, not the main checkout's.
- Your own read of a dev run is not a verdict. Report the grader's word, and call yours "builder's read". A lane graded outside git, or before the contract is pinned, can say one word where the grader's grade says another.
- Run `office.py handin`. It checks most of this page.

## History

- Never rewrite a commit the main branch already has, pushed or not. Fix a wrong title with a git note.
- Rebase your own unmerged branch only if the brief allows it. After a reword, check `git diff --stat <main>...<tip>` still shows only your change, and that the branch still sits on its own base, not on main's tip.
- A commit you built on another model's turn keeps the trailer of the model that built it. Correct a wrong one with a git note, not an amend.
- Read a sha from its commit's own output before you quote it anywhere.
- No commits in the main checkout, and none anywhere to the main branch while a counted run is queued or running.
