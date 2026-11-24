# Merging

Read this before every merge into the main branch. You merge; employees never do. The profile's `git.merge` names the way (default: cherry-pick by commit).

## Before the merge

1. **Not during a counted run.** While a counted run is in the queue, waiting or running, or a freeze is on, nothing merges: the run samples the tree. After it ends, its records are committed first, as the run's own commit, before any merge touches main; then the freeze is lifted.
2. **Start from the hand-in.** `<office>/handins/<id>.md` has the branch, the tip, the changed files and each PROBLEM or warning. A PROBLEM is fixed by the employee before you merge: files outside the badge, a path under `measure.grader_owned` changed by a badge that is not a grader's, a run's records (`measure.records`) changed by a badge that is neither a grader's nor yours, a flagged title's commit without its trailer, a change to the road graph. The grader's files, the records and the road graph are also checked in the branch's tree against the base, so a path marked "the branch's tree differs" is in no commit you were shown: a merge that kept one side, or a commit left out of `--commits`. They are always checked against the main branch as well as the `--base` given: a hand-in run with another `--base` carries a warning saying so, and a walled change made on that other branch is still a PROBLEM. An employee's report is not proof: read the commits.
3. **Read the range.** `git log --oneline <main>..<branch>`, every commit. Merge by commit, never a branch tip you have not read, and never rewrite the main branch.
4. **Look for copies.** `git cherry <main> <branch>`. A `-` line is a commit main already has as a copy under another sha: ask the author to rebase onto main first.
5. **Check the claims against the diff.** The files are the ones in its brief. The grader's files are untouched by a builder. The checks it names ran, and their logs or run folders exist. A test for a fix was shown failing with the fix reverted; if the hand-in does not give both results, ask for the control before you merge.
6. **Review.** A reviewer who did not build it reads every change before it merges and gives GO, GO-with-fixes or NO-GO. A flagged title's commits get the in-depth review. Before you relay a reviewer's High to the builder, confirm it yourself where the code runs.
7. **The road graph.** A branch that changes the road graph's two files is sent back: `office.py handin` reports it. Graph edits are made only through `flow.py graph ... --by`.

## A milestone that merges with its grader's branch

- Take the merge set from git, never from a list in notes or a message. A list in notes goes stale while main's copy of the lane falls behind. Run `git log --oneline <main>..<grader branch> -- <paths.gym>` and `git cherry <main> <grader branch>`. Every `+` commit is in the set unless you name why it is left.
- After the picks, check main's lane: its grader version line matches the grader branch tip's, and its prereg pins the contract main now has.
- Also run `git diff --stat <main>...<branch> -- <paths.gym>/contracts`. A contract change merges together with its grader's re-pin, or the hand-off notes "no counted <lane> until re-pinned". `board.py check` warns while a lane's prereg pins no version of its contract as main has it.
- A contract or prereg that a prereg on main pins by sha256 is never committed over, reset, removed or renumbered. A change comes as a new appended amendment, which the grader pins again.

## A branch that changes a skill, a tool or the hire brief

It merges at a slot boundary (the hand-off), or earlier when a follow-up builds on its files, after a fresh review of its last commit and with no counted run queued. Crew on the clock keep the brief they were given. The hand-off entry names the change, so the next manager briefs new crew from it.

## The gate

- Run the project's merge gate from `.foundry/rules.md` on the merged tree. `<py> <tools>/lanes_for.py <range>` lists the gym lanes whose inputs the range touches (`--explain` says why): each gets a dev run before its next counted run, and a past PASS of that lane no longer covers the new code.
- A full check at each slot's end, if the rules name one (the counted sweep of every lane is `sweep.py run`: `shifts.md`, "Closing a shift of work").

## After the merge

- If the merge changes something a past PASS covered, say so on the map (a note, or a `failures` entry with a plan to re-run) and queue the re-run. Do not leave the milestone reading done on a PASS of older code.
- Before the last dev run ahead of a counted run, the tree must be the one the counted run will use: a main that moves after the grader's GO (a code merge, not reports or run records) means one more dev run, or the grader's written reason why the change cannot touch the lane.
- Quote a commit's sha only from the commit's own output. Never write a sha into a message or the state in the same step as the commit that makes it.
- Close the journal entries the merge fixes (`journal.py set --status fixed --commit <sha>`), and set the failures it fixes to `fixed`, saying where.
- Post your progress.

## Never

- Merge a branch you built or directed without a review by someone who did not.
- Merge during a counted run, or before a finished run's records are committed.
- Rewrite, amend or reorder a commit the main branch already has. A wrong title is corrected with a git note.
- `git add -A`, or push when the profile's `git.push` does not allow it.
