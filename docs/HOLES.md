# Known holes

What is not verified, not enforced or still missing at 0.2.1, most important first. The first audit's list (0.1.0) had 28 items; the changelog says which were closed and how. What is left is here, with nothing rounded up.

## Not verified

1. **Nobody but the authors has run the skills on a new project.** The skills are conversions of ones in daily use on two projects, and every command they name was checked against the tools, most by running it. That is not the same as a fresh manager session following the text with no other knowledge. An earlier rewrite of the same skills lost to the original on a held-out test (it led with routine steps ahead of the key action and padded its answers). A project that already runs working skills should test these on real incidents, scored on the first action and on precision, before switching.
2. **Linux and macOS run only in CI.** Development was on Windows with Git Bash. CI runs the whole suite on Linux, macOS and Windows for Python 3.11 to 3.14 and all 12 jobs pass; the badge on the README is the current answer. Nobody has used the tools by hand on Linux or macOS, and the tests on those systems are the queue's and the sweep's own cases, not a working day.
3. **The chart pages were run in two browsers, not every case.** Every view, node and trace button was clicked on a plan page and a workflow page with no script error, and a structural check of both runs with the tests. Not exercised: dragging, wheel zoom, the light theme.
4. **The diagrams in the documentation** (Mermaid) were written, not rendered.

## Rules the tools do not enforce

5. **The badge is a claim, not a credential.** The signing key sits beside the roster. It stops mix-ups and keeps an honest record; it does not stop a session that sets out to cheat. The same holds for `--by`: `board.py` does not check who runs an edit, so the split between what the founder and the manager may change is a rule in the skills.
6. **`--words` is whatever is typed.** `shift set`, `milestone set --force` and `decide answer` record the words given; nothing can check they were the user's.
7. **No push is a printed rule.** The brief says it (or "only your own branch" when the profile allows pushing); nothing stops a `git push`.
8. **A freeze holds the tools, not git.** While a counted run or a freeze is on, the board holds its edits and the graph, plan and gym tools refuse to write in the main checkout. A plain `git commit` there is not stopped by any tool; the sweep notices and stops.
9. **The session's model.** The brief prints the model a title should run on, and the hand-in check enforces a flagged title's commit trailer. Setting a session to that model is done in the app by the manager.
10. **The hook cannot see everything.** `graph_readonly.py` refuses direct edits and the common shell routes to the road graph's files. `hooks/README.md` lists what it cannot see (8.3 short names and links, names built by the shell, a `cd` in an earlier call, a bare `git reset --hard`). The signed edit log catches a change the hook missed: `flow.py selftest` then says TAMPERED.
11. **`rq.py --max` is enforced only when asked** (`--enforce-max` or `resource.enforce_max`). Otherwise a hold past its limit only reads OVERDUE. A `take` hold is never ended.

## Missing

12. **A way to read usage.** The manager reads the plan's weekly usage in the app and records it with `board.py usage`. The round reminds it when the last reading is old.
13. **A system graph reader.** The canvas can draw the system as built; the reader that makes that graph from a project's code is the project's own to write.
14. **Timers are a list, not timers.** `office.py timers init` writes what the manager should create in its session; the tool creates none, and they end with the session. A timer that must survive a restart is a scheduled task the user sets.
15. **Another harness.** `foundry-bench` and the manager's `references/app.md` describe the Claude desktop app's session tools by name. Another harness needs its own version of those two files.

## Rough edges

16. Decision briefs (`D<n>-topic.md`) and decision records hired with `--adr` (`NNNN-topic.md`) share `paths.decisions`.
17. The default lane pattern and push-block pattern (`G1`, `Q1`) are the source projects' habits. Both are profile keys.
18. The queue's files keep their original key names inside (`lane` for a seat, `gui` for exclusive); `rq.py status --json` prints the new names.
19. With two seats free, `rq.py run` may take the second and leave the first for a `take`.
20. Briefs print commands with the host's absolute paths (the map prints them relative). Fine for one machine; a brief pasted to another machine needs its paths changed.
21. A badge's title or model cannot be amended; it takes a new hire.
22. With a shared resource the sweep releases and re-takes the seats for each lane. Its freeze holds the checkout throughout, but a job already waiting for the whole resource can run between two lanes.
23. `measure.sweep`, `measure.done_means` and `git.merge` are notes for people; no tool reads them.
24. The defaults of `measure.grader_owned` and `measure.records` are written as `gym/...`. A project that moves `paths.gym` must change those two lists with it.
25. On Windows, when Git's `bash` is not first on the PATH, the queue can find the WSL launcher's `bash.exe` instead (it fails with "no installed distributions"). Set `resource.shell` to the shell you mean.
26. `board.py init` and `check` ignore the starter roadmap, but two commands do not: `decide ask` numbers past the starter's example decisions, and `milestone set` on an id the starter names still takes that milestone from the starter. `milestone sync` refreshes the planned ones after the founder writes the real roadmap; one already in progress keeps its starter title until it is renamed by hand.
27. Two independent reviews of this release found 8 High and 17 Medium defects between them; all were fixed and most fixes have a test that fails without them. A third review has not been done. The walls most worth a fresh pair of eyes are the hand-in check (`office.py handin`), the sweep's "was this lane really run" rule, and the hook's shell matching.

## The source projects

Glasswing and Shiro still run their own older copies. Moving one over is mostly a profile (`badge_prefix`, `paths.office` and the roadmap id shapes keep its badges, office and roadmap valid), plus renamed queue files and flags; [Adopting](adopting.md) has the steps. Do it at a slot boundary with nothing counted in the queue, after the test in item 1.
