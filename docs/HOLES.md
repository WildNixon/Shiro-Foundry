# Known holes and next improvements

Written at 0.1.0 from three checks: every selftest and test run together (17 runs, all passing), an end-to-end trial on a scratch project (install, found, appoint, hire, clock in, board, decisions, flow, plan chart, journal, queue, hooks), and a review of every command the skills name against the tools' code. What those checks fixed is in the changelog. What they left open is here, most important first.

## Not verified

1. **The skills have not been run on a second project from a clean start.** They are conversions of skills in daily use, and each rule was kept, but nobody has yet followed the general text with no other knowledge. An earlier rewrite of the same skills lost to the original on a held-out test (it led with routine steps ahead of the key action and padded its answers), so this text needs its own test before it replaces skills that work: a pool of real incidents from at least two projects, scored on the first action and on precision.
2. **Only one host.** Everything was run on Windows with Git Bash and Python 3.14. Python 3.11 to 3.13, Linux and macOS are expected to work (standard library only; one 3.12-only call was removed) and have not been run.
3. **The chart pages' script was not executed after the port.** `flow.py build` and `plan_flow.py build` write their pages and the pages' data was checked; the six small changes to the page script were checked by reading.
4. **The map and chart pages were not looked at in a browser** after the port: their HTML was built and searched for leftovers, not viewed.

## Missing: a project must supply these

5. **A gym to start from.** Nothing scaffolds `gym/` (a `run.py`, a lane-inputs table, the first lane). The gym skill and its `gym_kit.py` are the material; the first grader builds it. Until then the board says "no gym yet", no milestone can pass, and `lanes_for.py` has nothing to read.
6. **A sweep.** The skills describe a counted sweep of every lane at a push's close; the tool that runs one is the project's own (`measure.sweep` names it; no tool reads the key).
7. **A system graph reader.** The canvas (`flow_page.py`) can draw a graph of the system as built; the reader that makes one from the code is the project's own.
8. **A way to read usage.** The manager reads the plan's weekly usage in the app and records it with `board.py usage`. No tool reads it.

## Rules the tools do not enforce

9. **`[models]` and `[flagged]`.** No tool reads them. The manager looks them up and sets the session's model by hand; the hire brief does not print them. Wanted: `hire --title`, with the title's card, model and trailer printed into the brief and refused when broken.
10. **Titles beyond four roles.** `office.py --role` takes builder, grader, reviewer, scout. Fixer, triager and cleaner are cards in the manager's brief template, hired under one of the four.
11. **`git.push`, `git.merge`, `slots.round_every`, `slots.review_window_min`, `measure.done_means`.** Rules for people. The hire brief always says "no push".
12. **A freeze without a queue.** A counted run freezes the main checkout through the resource queue (its id marks it). A project with no shared resource has no tool-visible freeze: it is kept by hand. Also, `plan_flow.py` treats a priority-0 job as counted while `office.py` and `board.py` go by the id alone; pick one.
13. **`rq.py --max` is not enforced.** A hold past its limit reads OVERDUE; nothing ends it.
14. **Units differ.** A bare number is seconds for `rq.py --max` and minutes for `office.py --eta`. The skills say so; one unit would be better.
15. **The badge is a claim, not a credential.** The signing key sits beside the roster. It stops mix-ups and keeps an honest record; it does not stop a session that sets out to cheat.

## The manager still writes scratch scripts for

16. A log entry, `now`, a rota day, a checkpoint, a blocker, the checklist, a queue entry, the research-and-review window. Each is an edit of the state through `board.write_state`. Wanted: a `board.py` command for each, and `rr` windows written from the profile.
17. **The round.** It is two commands and an order of attention in the skill. Wanted: one `office.py round` that prints what needs the manager first, and marks hand-ins seen.
18. **The hand-off brief** for the next manager, and the manager's timer file (`manager-timers.json`): both hand-kept; their shapes are described only in the skill.

## Rough edges

19. `board.py` and `flow.py` read a stage's exit cell differently (the board takes full ids and runs only). The roadmap format page says what both accept.
20. The starter roadmap is an example with a PASS row, so a new project's board warns that no lane backs it until the founder replaces the starter. `founder.py doctor` and `audit` both say the roadmap is still the starter.
21. The map prints command lines with the host's absolute paths (so does every brief). Fine for one machine; noisy in a repository several people clone.
22. `graph_readonly.py` matches a protected file by name in shell commands, and looks for the profile module only in `scripts/foundry` and beside itself. `hooks.protect` does not follow `paths.flow`.
23. Decision briefs (`D<n>-topic.md`) and decision records hired with `--adr` (`NNNN-topic.md`) share `paths.decisions`.
24. The default lane pattern and push-block pattern (`G1`, `Q1`) are one project's habits. Both are profile keys.
25. `foundry-bench` and the manager's `references/app.md` describe the Claude desktop app's session tools by name; another harness needs its own version of those two files.
26. The cleaner card is a temp that uses the queue, while the app notes say work that waits on the shared resource belongs to a session.
27. `founder.py audit` lists the manager's roadmap proposals (`<paths.handoff>/<date>-proposal-<topic>.md`) by file name only; whether each was answered is the founder's to track.
28. The example profile leaves out keys the tools read with defaults: `[skills]`, `resource.shell`, `measure.grader_no_read`, `measure.handin_check_timeout_s`, `measure.unit_manifests`, `measure.not_built`, `roadmap.late_stages`, `roadmap.block_id`, `board.phases_title`, `git.branch_prefix`, `hooks.protect_reason`. `foundry_profile.py show` prints them all.

## Found in the source skills during conversion (fixed here, worth knowing)

- The hand-off told every open question to cite a D-number, but no tool issued one: `board.py decide` now does.
- A manager who posted only on its two-hour round read STALE at two hours: the skill now has it post at each block end, merge and filing.
- The reviewer "never touches the shared resource" and the brief template let it queue a test job: now "only the one short job its brief names".
- The grader's example brief worked in the main checkout, against the rule that no employee writes there: it works in its own worktree.
- Three files stated the "a session cannot clear itself" rule with different scope: one statement, in `app.md`.
- A stale note said a chained command reached the shell as its first word only: the queue passes it whole.

## The source projects

The two projects these came from still run their own copies. Moving one over is a profile, not a rewrite: `badge_prefix`, `paths.office` and the roadmap id shapes keep its badges, office and roadmap valid; the queue's files are renamed (`vm.*` to `rq.*`), the lane-inputs table's `crates` key becomes `units`, and briefs name `--rq`/`--seat`. Do it at a slot boundary with nothing counted in the queue, after the test in item 1.
