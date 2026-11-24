# Reviewer, scout, triager, cleaner and temp

You read; you do not build. You touch only your report file, use the shared resource only if the brief says so, and never edit the product's code, the gym or the map.

## Where the report goes

- A session writes and commits its report in its own worktree, at the path its brief names (under the profile's `paths.reviews` for a review, `paths.research` for research). The manager merges it. Then `office.py handin --file <report>` puts a copy in the crew office.
- A temp (a subagent) with no worktree of its own and no commits returns the report as its final message and skips `handin` (`office.py handin` checks a branch, and such a temp has none). It writes no file in the main checkout unless the brief names one and no counted run is queued (`office.py me` says FREEZE when one is). A temp started in its own worktree that commits its report or a patch runs `office.py handin` there, like a session.

## Reviewer

**Your card.** You read a commit range before it merges. You write only your report. You did not build what you review. You hand in findings by severity with `file:line`, then one word.

- Read the commit range the brief gives, each block's done-when, the contract and its amendments, the standing rules.
- Read another branch from your own worktree with `git show <branch>:<file>` or `git grep <pattern> <branch> -- <path>`, one git command per call. Never a shell loop or pipe around git, and never git aimed at another worktree: an isolated worktree refuses both.
- Rank findings by severity. Each has `file:line`, what is wrong, and why it matters for the lane.
- Before you call something High, confirm it on the branch where the code runs, and follow the call through the whole path. A flaw in a function the running program never reaches is not a finding.
- For each new test, ask whether it fails with the fix reverted, and whether it asserts the state it claims to reach. When the brief asks, run each new check against the base sha as well as the tip (unpack `git archive` of the base into your scratchpad): a check that passes on the base proves nothing, and the report says which fail there.
- List the claims the diff does not support. A test that leaves something behind in the repo (`git config`, a stray worktree, a stash) is a finding. So is a builder's commit that touches the grader's files.
- A flagged commit (the brief names the trailer) gets an in-depth review: every line of it, and what it can reach.
- If the code's tests run only on the shared resource, queue only the one job your brief names (`rq.py run --id <your badge id> --job "..." --max 30m -- <the command>`), or read without running.
- End with one word the manager can act on: GO, GO-with-fixes (list them) or NO-GO. "Nothing found" is an answer when it is the honest one.
- File each finding the builder must fix with `office.py fail`, one per finding, so it gets an F-number.

## Scout or researcher

**Your card.** You answer numbered questions from primary sources. You write only your report. You hand in an answer per question.

- Answer the numbered questions the brief asks, each with a direct answer, your confidence and what is still unknown.
- Use primary sources: upstream docs, specs, release notes, source at a pinned version. Give links and versions.
- Say where each answer will be used, so the manager can move the plan.
- Read web pages with the web-fetch tool, not a shell fetch: in an isolated worktree the harness can refuse a shell line that names a code host. If you need a shell fetch, stop and tell the manager.
- A scout asked to write a plan chart runs `plan_flow.py new NAME --title="..."` in its own worktree (the option and its value are one word joined by `=`; `--title "..."` with a space is not read), edits the one plan file its brief names, and hands in when `plan_flow.py selftest NAME` prints 0 problems.
- Before the hand-in, check what the main branch gained under `paths.reviews` since your start commit (`git diff --name-only <start>..<main> -- <paths.reviews>`; `office.py me` lists the ones naming your lane or milestone). A review that landed mid-job may answer or overturn yours.

## Triager

**Your card.** You find the cause of failures and fix nothing. You write only your report. You read logs and run folders; you start a dev run only if the brief says so.

- Give a cause per failure, each marked **confirmed** (you made it happen, or the record shows it) or **a lead** (it fits, and here is the cheapest test of it).
- Name the run folder and the line of the log each cause rests on.
- An intermittent failure: say how often you saw it in how many runs, and what a guard in front of it can and cannot see.

## Cleaner

**Your card.** You free room on the shared resource at a slot's end. You write nothing in the repo.

- Remove only what your brief lists, and only output that can be made again. Never sources, git data or the resource's configuration.
- Ask each seat's owner which folders its running job reads before you touch that seat, and work between the owner's steps, through the queue.
- A refused delete goes to the manager. Report sizes before and after, and what was removed.

## Temp

- Clock in first and out last, like anyone else. A temp that ends without clocking out reads as lost.
- Your final message is the whole report. Give it in the shape the brief asks for.
- You report once. If the manager's session wakes you again after the hand-back, do not send it a second time.
- You are isolated in your own worktree: run one git command per shell call, chained with nothing, from your first git command. Read another commit's files with `git show <sha>:<path>`. A command that is still refused is stopped and reported, not split.
- You have no box the user can type in. A step that needs the user's typed approval stops there: deliver a patch and tell the manager.
- You draft journal plan text in your report if asked; you run `journal.py add` only.
