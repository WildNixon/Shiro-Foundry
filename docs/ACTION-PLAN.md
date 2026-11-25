# Action plans: review of 0.2.1

A third review of the whole repository at `c75907b` (0.2.1), done 2026-11-25 on Linux with Python 3.13. The suite passed before the review (23 of 23, 5 min 21 s). Four reviewers read the code in parallel and reproduced what they could in scratch projects; nothing in the repository was changed.

**60 findings, none already in [HOLES.md](HOLES.md).** 47 were reproduced (marked **R**), 13 are from reading only (marked **S**). Nothing below has been fixed yet.

The plans are in the order to do them. Each is sized to be one branch.

| # | Plan | Kind | Findings | Size |
|---|---|---|---|---|
| 1 | [The gym and sweep on a real project](#1-the-gym-and-sweep-on-a-real-project) | holes | 8 | M |
| 2 | [One lock for every shared file](#2-one-lock-for-every-shared-file) | holes | 9 | M |
| 3 | [The hand-in check's walls](#3-the-hand-in-checks-walls) | holes | 7 | M |
| 4 | [Crash safety of the graph and of held edits](#4-crash-safety-of-the-graph-and-of-held-edits) | holes | 6 | S |
| 5 | [Damaged and wrong-typed input](#5-damaged-and-wrong-typed-input) | holes | 11 | M |
| 6 | [The hooks](#6-the-hooks) | holes, optimization | 6 | M |
| 7 | [Install, version and doctor](#7-install-version-and-doctor) | improvement | 4 | M |
| 8 | [Speed](#8-speed) | optimization | 5 | S–M |
| 9 | [Upkeep](#9-upkeep) | improvement | 4 | L |

Plans 1 to 3 are the ones that can make the tools say something false (a PASS-shaped result for a run that never happened, a lost failure report, a READY for a branch that strays). Do those before another project adopts this.

---

## 1. The gym and sweep on a real project

**Why first.** The starter gym and the sweep were each tested alone. Together, on a fresh project, the sweep cannot finish two lanes, and a lane that never ran is counted as having given a verdict.

| | Finding | Where |
|---|---|---|
| **R** High | The starter runner's `counted` refuses any dirty tree, but lane 1 leaves its own records (series, chart, grade) uncommitted, so lane 2 always refuses. The sweep tolerates those paths; the runner does not. | `profile/gym/run.py:316-321`, `tools/sweep.py:166-171` |
| **R** High | A fresh gym's first counted run refuses itself: importing the kit and the lane writes `gym/__pycache__`, which is untracked. Every test sets `PYTHONDONTWRITEBYTECODE=1`, which hides it. | `profile/gym/run.py:66,118-120`, `tools/gym_init.py:179-188` |
| **R** High | Only exits 2 and 3 mean "no verdict". A command that does not exist (127) or was killed (-9, 137) is listed as "gave a verdict" and the sweep exits 0. | `tools/sweep.py:498-513,705-709` |
| **R** Med | The runner appends the series point before it writes the grade and chart. A failure in between exits 3 "no verdict" with the point already published; the map reads the series. | `profile/gym/run.py:287-306` |
| **R** Med | `lanes_for.py` reads `git diff --name-only`, which quotes non-ASCII paths. A change to `src/a/café.txt` matches no lane, so the "commits since queued" check passes wrongly. | `tools/lanes_for.py:211-224` |
| **R** Low | Lane names are read from `run.py` as text: a commented-out lane is still swept, single-quoted keys give no lanes. | `tools/lanes_for.py:74-77`, `tools/gym_init.py:228-231` |
| **S** Low | `gym_init.py check` accepts preregs the runner refuses (a git blob hash, a fallback from `G1b.json` to `G1.json`). | `tools/gym_init.py:375-378,414-415` |
| **S** Low | Two sweeps started together can both pass the start checks; the lock is written after them. | `tools/sweep.py:583-599,656-666` |

**Steps**

1. `run.py counted`: leave the profile's `measure.records` paths out of the clean check, the way the sweep does. Set `sys.dont_write_bytecode = True` before the first import, and have `gym_init` write a `gym/.gitignore` for `__pycache__/`.
2. `sweep.py`: a verdict is an exit in a declared set (0 and 1 by default; add `measure.verdict_exits`). Everything else, including negative codes and 126 and up, is "not run".
3. `run.py`: build the grade text and chart first, append the series point last.
4. `lanes_for.py`: `git -c core.quotepath=off diff -z --name-only` with a timeout; read `LANES` with `ast` instead of a pattern.
5. `gym_init.py check`: call the runner's own `prereg_refusal` rules.
6. `sweep.py`: create `sweep.lock` with `O_EXCL` before the checks; remove it on refusal.

**Tests to add.** One end-to-end test: `gym_init init`, add a second lane, register both preregs, commit, run `sweep.py` with the real runner and **without** `PYTHONDONTWRITEBYTECODE`. Cases for exit 127 and a killed lane; a non-ASCII path; a commented lane.

**Done when** that test passes on all three systems and a sweep of two starter lanes ends with two verdicts.

---

## 2. One lock for every shared file

**Why.** Several sessions write the same files at once. The office lock can be taken from a live holder, the board does not lock at all, and the queue's mutex gives up before it would break a dead one.

| | Finding | Where |
|---|---|---|
| **R** High | The office lock counts as stale after 30 s by file time alone; the holder's PID is never read. `hire --adr` holds it across two git calls. Reproduced: two hires both printed `hired EMP-01`, one roster line lost. The holder's `finally` then deletes whoever holds the lock by then. `journal.py`, `board.py` and `flow_graph.py` share this lock. | `tools/office.py:407-430` |
| **R** High | Every ordinary `board.py` edit is an unlocked read-change-write of `state.json`. 12 parallel `note` left 11; 8 parallel `fail` left 7, each exiting 0. | `tools/board.py:3823-4033`, `3039-3060`, `3004-3018` |
| **R** Med | A queue mutex left by a killed process: waiters give up after 20 s, but it only counts as stale after 30 s, so they exit instead of taking over. `take` installs no stop handler, which is one way to leave it. | `tools/rq.py:333-349,1148` |
| **R** Med | After a suspend or clock step of over 2 minutes, the first poller drops every waiter, itself included, because it filters on old beats before refreshing its own. | `tools/rq.py:386-392,511-519` |
| **S** Low | Breaking a stale lock or mutex is check-then-delete: a second waiter can delete the first's fresh lock. | `tools/office.py:413-416`, `tools/rq.py:338-341` |
| **S** Low | The first-run badge key is created outside the lock and not atomically; two first commands can each write a different key. | `tools/office.py:433-439` |
| **S** Low | `freeze on`/`off` decide on a `freeze.json` read before the lock, and the sweep writes it with no lock. | `tools/office.py:2873-2918`, `tools/sweep.py:338-349` |
| **S** Low-Med | The board reads "is there a freeze" once, then writes later with no re-check, so an edit can land in a checkout frozen in between. | `tools/board.py:5043,5089-5094` |
| **S** Med | On Windows `os.replace` fails while a reader has the file open. `office.write_roster` retries; the board's and journal's writers do not. The map itself is written in place. | `tools/board.py:998,697,2998`, `tools/journal.py:361` |

**Steps**

1. One lock helper in `foundry_profile.py` (every tool already imports it): an `O_EXCL` file holding PID and start time; stale means that PID is dead, not that time passed; break it by renaming to a unique name and checking the content is still what was judged; wait longer than any stale age.
2. One `atomic_write(path, text)` helper with the replace retry, used for the roster, state, pending edits, journal, freeze, key, hand-ins and the map.
3. Use both in `office.py` (move the git calls of `hire --adr` out of the lock, create the key under it), `board.py` (lock around read-edit-write, and re-read the freeze inside it), `journal.py`, `flow_graph.py`, `sweep.py` (freeze writes), and `rq.py` (the mutex).
4. `rq.py`: refresh the caller's beat before filtering; treat a poll gap far over the interval as a suspend. Give `take` the same stop handler as `run`.

**Tests to add.** 12 parallel `board.py note` keep 12; two `hire` with a slow git keep two badges; a mutex left by a dead PID is taken over; beats set 130 s back do not empty the queue.

**Done when** those four pass 50 times in a row on each system.

---

## 3. The hand-in check's walls

**Why.** HOLES.md item 27 names this as the wall most worth fresh eyes. Each of these is an honest mistake, not a cheat, that ends in READY.

| | Finding | Where |
|---|---|---|
| **R** High | `handin --commits <subset>` checks "files your badge owns" only for the named commits. A branch whose other commit touches `docs/sneak.md` is READY. The tree's file list is already gathered and never checked. | `tools/office.py:2246-2258,2406-2416` |
| **R** High | Most git calls in the check ignore the exit code, and a 60 s timeout returns empty. With a corrupt index and an uncommitted file, `handin` said READY, 0 problems. | `tools/office.py:1942-1950,2256,2268,2293,2421-2441` |
| **R** Med | `measure.grader_owned` and `measure.records` are matched as literal prefixes while every neighbouring key takes globs. `gym/prereg/**` switches the wall off in silence. | `tools/office.py:2350-2357,2382-2384` |
| **R** Med | `hire --files "src/a.txt src/b.txt"` (spaces, or one free-text entry) makes the list uncheckable; `hire` says nothing and outside files become a warning. | `tools/office.py:1972-1994,2406-2418` |
| **R** Med | Running the worktree's own copy of the tool reads the worktree's profile, so a branch that is behind main, or that edits `.foundry/foundry.toml`, is checked against its own walls. | `tools/foundry_profile.py:339` |
| **R** Med | `handin` run in the main checkout on `main` gives READY with 0 commits and overwrites the worktree's NOT READY hand-in. | `tools/office.py:2259-2261,2549` |
| **S** Low | The project's check command runs with `shell=True` and a timeout that kills only the shell: children are orphaned, and on Windows the call can hang past the timeout. It ignores `resource.shell`. | `tools/office.py:2071-2075` |

**Steps**

1. A `git_ok()` helper: a non-zero exit or a timeout becomes a PROBLEM line "could not check X". Use it for every call in `handin_checks`.
2. Run the own-files check over the named commits **and** the files changed since the fork point.
3. Match `grader_owned` and `records` with `owns()`; have the profile check and `doctor` warn on a pattern that matches nothing.
4. `hire` and `amend` print the entries that cannot be checked and refuse when none can (unless forced). Outside files stay a PROBLEM when any checkable pattern exists.
5. `handin` loads the profile from the main branch (`git show <main>:.foundry/foundry.toml`), records which it used, and warns when the worktree's differs.
6. For a builder, HEAD on the main branch with no `--commits` is a PROBLEM. Never replace a hand-in from another worktree without keeping it.
7. Run the check command through `rq.py`'s process code (group or job object, tree ended on timeout).

**Tests to add** to `tests/office_wall_test.py`: one per row above. Each must fail on today's code.

**Done when** all seven fail before and pass after.

---

## 4. Crash safety of the graph and of held edits

| | Finding | Where |
|---|---|---|
| **R** Med | A graph edit replaces the asset, then appends the log. A failure in between leaves it TAMPERED for good: no repair command, and the hook blocks restoring the file with git. | `tools/flow_graph.py:444-456` |
| **R** High-Med | Replaying held edits marks an edit `failed` on any exception, and failed edits are never retried. One unreadable `state.json` at that moment (a merge marker) loses every held edit; `pending` still says the next build applies them. | `tools/board.py:918-929,5051` |
| **R** Med | `graph link Q1 Q2` (block to block) is accepted and verifies, then `flow.py` treats Q2 as a milestone and the selftest fails. | `tools/flow.py:494-496` |
| **R** Med | `flow.py selftest --logic` reads the real office when `paths.office` is absolute, so it fails for good on such a project, and `founder.py audit` with it. | `tools/flow.py:1510-1522` |
| **R** Med | A chart page draws nothing when any title holds `<!--` followed by `<script`: only `</` is escaped in the embedded data. | `tools/flow_page.py:141` |
| **R** Low | A series point's `n` goes into the map unescaped in two places (two others escape it). | `tools/board.py:2331,2630` |

**Steps**

1. `flow_graph.write()`: append and flush the log entry first, then replace the asset; `verify` rolls forward when the asset is one entry behind. Add `graph repair` for anything else, by the manager's badge.
2. `apply_pending`: if the state cannot be read, stop before the loop and leave the file alone. Mark `failed` only when the edit itself is refused.
3. `flow.py`: take milestone dependencies only from edges that leave a `done` pin.
4. The logic selftest forces every input path under its temp root.
5. `flow_page.py`: escape every `<` in the data as `<`. `board.py`: `esc(n)` at both sites.

**Tests to add.** An append that raises leaves the graph usable; a replay against a broken state keeps the edits pending; the block link; the `<!-- <script` title (the structural page check can assert the data element closes); a hostile `n`.

---

## 5. Damaged and wrong-typed input

**Why.** One bad line in one shared file stops the whole crew with a traceback. The tools already have the right habit in places (`safe_state`, the profile's exit 2); it is not applied everywhere.

| | Finding | Where |
|---|---|---|
| **R** High | `progress --eta 1795572961000` (an epoch, read as minutes) is written to the clock, then `roster`, `round`, `me` and `handoff` traceback for everyone until that badge punches again. | `tools/office.py:1934-1935,257-298` |
| **R** Med | A cut-off last line in `timeclock.jsonl` breaks `roster` and `round`; the next punch is glued onto it and lost. An empty roster or key file, text for `crew_max`, a slot start of `"6"`: all tracebacks. | `tools/office.py:303-305,433-478` |
| **R** Med | `shift blocks --file` and `queue add --file` accept wrong-typed fields, write the state, and every later build tracebacks. `brief` hides it. | `tools/board.py:3240-3250,3594-3618` |
| **R** Med | One malformed gym file (an empty contract, `points: null`, a text `ts`) tracebacks every board command. | `tools/board.py:1494-1525` |
| **R** Med | A `state.json` or roadmap that is not UTF-8 (a Windows editor saving ANSI) is a `UnicodeDecodeError` traceback. | `tools/board.py:1049,1086,1128,1394,2085` |
| **R** Med-Low | Fuzzing found 113 spots where a wrong type or missing key in `state.json` tracebacks; `normalize()` covers three keys. | `tools/board.py:1029,966` |
| **R** Med | A graph node with no `type`, a log line that is JSON but not an object, or a 1,200-link chain (recursion) crash the flow tools. | `tools/flow.py:675`, `tools/flow_graph.py:317,367` |
| **R** Low-Med | One wrong-typed value in one plan file takes down `plan_flow.py list`, `build` and `selftest` for every plan. | `tools/plan_flow.py:305-331` |
| **R** Low | A queue entry without `at` crashes every `rq.py` command for the whole crew. | `tools/rq.py:359-392` |
| **R** Low | A refused `hire --adr` still uses up the ADR number. | `tools/office.py:1518-1521` |
| **S** Low | A journal line that is JSON but not an object tracebacks every journal command. | `tools/journal.py:125-152` |

**Steps**

1. Bound `--eta` before the punch (at most 7 days ahead; hour and minute ranges). Parse every argument before taking a lock or reserving a number.
2. One reader for line files (`timeclock`, journal, graph log, queue): skip and report a line that is not a JSON object; start every append on a fresh line.
3. `board.py`: grow `normalize`/`check_shape` into one schema pass run on read **and** before every write, so a command cannot write a state the next build cannot read. Build each lane record inside its own `try`. Read text with `(OSError, UnicodeDecodeError)` caught.
4. `flow_graph`: flag untyped nodes on load; make `cycle()` a loop.
5. `plan_flow`: type-check before the membership tests; one plan's failure is one PROBLEM line.
6. Every tool's `main()`: a last `except Exception` that prints one line naming the file and exits 2, with the traceback behind `FOUNDRY_DEBUG=1`.

**Tests to add.** A small fuzz test (the reviewer's was about 60 lines): replace each node of a state with `None`, `5`, `"zz"`, `[]`, `{}` and assert no command prints `Traceback`. The same for one line of each line file.

---

## 6. The hooks

| | Finding | Where |
|---|---|---|
| **R** Med | `no_python_stdin` misses common forms: `PYTHONPATH=. python - <<EOF`, `env python3 -`, `time python -`, `python3 -W ignore -`, and the dashless ones that read stdin just the same (`python3 <<EOF`, `echo … \| python3`, `python3 < s.py`). | `hooks/no_python_stdin.py:16` |
| **R** Med | `graph_readonly` lets through `git checkout HEAD~1 docs` (restores the graph from another commit) and anything after a single `&` (`echo hi & rm -rf docs/flow`). Neither is in the README's list. | `hooks/graph_readonly.py:587,701` |
| **R** Med | `graph_readonly` blocks ordinary reads: `grep -c move docs/flow/road.edits.jsonl`, `grep -w rm …`, `git clean -n docs/flow`. A writer word is matched anywhere in the command, not as the command. | `hooks/graph_readonly.py:75-79,106,631` |
| **R** Low | `no_python_stdin` tracebacks (exit 1, the call still runs) on a JSON list or a non-text command. | `hooks/no_python_stdin.py:174-175` |
| **R** Low-Med | `doctor` reports a hook as installed when the settings still hold the `<python>` placeholder; the hook then prints "inactive" on every call. | `tools/founder.py:269-278` |
| **R** Low-Med | The two hooks add about 90 ms to every Bash call on Linux (27 + 64), more on Windows. Most of it is start-up before a 0.01 ms pre-check. | `hooks/graph_readonly.py` |

**Steps**

1. Move `command_of()` (the tokeniser that skips `VAR=`, wrappers, `then`/`do`/`{`) into a small shared module; use it in both hooks.
2. `no_python_stdin`: block when the command is python and it has a lone `-`, or no script argument while stdin is a heredoc, pipe or `<`.
3. `graph_readonly`: count a writer only when it is the command (or follows a wrapper or `xargs`); split on a lone `&`; for `checkout` with two or more path words apply the path check without `--`; let `clean -n` through.
4. Type guards on the payload in both.
5. `doctor`: parse the settings, find the hook's entry, flag the placeholder or a missing interpreter, run the hook once on a sample.
6. Speed: one entry script for both hooks that reads the payload and does the cheap text pre-check **before** importing anything else; the selftests move to `hooks/test_*.py`.

**Tests to add.** Each form above as a case in the two hook test files. A timing check that an unrelated command returns in under about 40 ms.

**Update** `hooks/README.md`'s list of what the hook cannot see once the two gaps are closed.

---

## 7. Install, version and doctor

| | Finding | Where |
|---|---|---|
| **R** Low-Med | `install.py` writes outside the project: through a dangling symlink at a destination, and with `--tools-dir ../x` or an absolute path. Its docstring says it never does. | `install.py:36-37,77-90` |
| **R** Med | No manifest, upgrade or uninstall. `--check` exits 0 when files differ; a tool removed upstream is never mentioned; each `--force` adds another `.bak`. `doctor` checks only that 13 files exist. | `install.py:68-92`, `tools/founder.py:221-229` |
| **R** Med | The version is kept by hand in four places (`foundry_profile.py:37`, read by nothing; README; CHANGELOG; HOLES). No `--version`. | |
| **R** Low | Small mismatches: `doctor --selftest` skips two selftests the docs say it runs; `--help` on subcommands errors or, for `board.py brief --help`, runs the brief; `install.py --check --hooks` prints "Hooks copied." | `tools/founder.py:42`, `install.py:98-100` |

**Steps**

1. Refuse a `--tools-dir` that resolves outside the project and a destination that is a symlink; copy by temp file and replace.
2. Write `.foundry/installed.json`: version, and a hash for each file installed. `--check` exits 1 on drift and lists files the manifest has that upstream no longer ships. Add `--uninstall` (removes only unchanged files from the manifest).
3. `doctor` compares the installed files with the manifest and says which differ.
4. `VERSION` in `foundry_profile.py` is the one source; every tool takes `--version`; a test asserts README, CHANGELOG and HOLES agree with it.
5. `--help` works on every subcommand and exits 0.

**Tests to add.** `tests/install_test.py` (there is none today): fresh install, re-install, drift, `--force`, symlink, outside path, uninstall.

---

## 8. Speed

| | Finding | Now | After |
|---|---|---|---|
| **R** | `tests/run_all.py` runs 23 entries one after another. Six of them are 83% of the time; `sweep_test.py` re-runs the sweep selftest. Every entry already works in its own temp folder. | 5 min 21 s here, × 12 CI jobs | about 70 s with a process pool |
| **R** | CI has no job timeout, no cancel of superseded runs, no lint. | | |
| **R** | `office.py` re-reads the whole time clock for every punch and up to five times in `me`; the clock is never rotated. A 40-commit hand-in starts 99 git processes. | `me` 3.4 s at 200k events | one read per command; one `git log` for the range |
| **R** | The board reads the roadmap 7 times and each series file twice per build. Nothing bounds `state.json` or the page: 2.8 MB of HTML at a large state, rewritten and committed on every edit. | build 0.18 s (fine), diffs grow | read once; page shows the latest N, older entries in a side file |
| **R** | `board.py check --no-build` ("reads and writes nothing") rewrites `.git/index` and takes its lock, which can fail another session's commit. | | `--no-optional-locks` on every git call |

**Steps**

1. `run_all.py --jobs N` (default: the CPU count) with a process pool; print results in a fixed order; drop the doubled sweep selftest. Check first that `rq.py` and `sweep.py` selftests do not share an office path when run side by side.
2. CI: `timeout-minutes: 20`, a `concurrency` group that cancels older runs of a branch, and one lint job (`ruff check` on Linux, one Python) outside the matrix.
3. `office.py`: read events once per command and pass them down; keep the sequence number in a small counter file; rotate the clock at a slot boundary into `timeclock-<date>.jsonl`. `handin`: one `git log --name-only -z` for the range.
4. `board.py`: read the roadmap and series once per build; cap the rendered log, notes and closed failures; `GIT_OPTIONAL_LOCKS=0` in the shared `git()`.
5. The hook start-up cost is in plan 6.

**Done when** the suite runs in under 90 s locally and a CI job in under 3 minutes.

---

## 9. Upkeep

Do this last and on its own branch: it moves a lot of lines and would make every other diff hard to read.

| | Finding |
|---|---|
| Size | `office.py` is 5,510 lines and `board.py` 5,108. `office.py`'s selftest is one 1,900-line function (35% of the file); `board.py`'s is 843 lines; `rq.py` and `sweep.py` are each about a third selftest. All of it is installed into every project. |
| Doubles | Two parsers of the same argv grammar in `board.py` must be kept in step by hand (`split_argv` and the loop in `edit_state`); a drift points a held edit at the wrong argument. Queue constants copied from `rq.py`; `read_freeze` re-implements `office.freeze_facts`; three pipe-splitting helpers. |
| Dead | `rq.py` `win_job()` (replaced by `win_start`); unused `d` parameters in `office.mint` and `manager_of`; a blank gap between the decorator and `def locked`; `journal.py` imports `subprocess` only for its selftest. |
| Coverage | `journal.py` and `install.py` have no file under `tests/`. No test measures coverage. |

**Steps**

1. Move each selftest to `tests/<tool>_selftest.py`; the tool's `selftest` command runs it when the file is there (so the repo keeps one command) and says "not installed" in a project. This alone cuts the installed tools by about a quarter and speeds the hook's import.
2. Split `office.py` (badge and clock; hand-in; round and hand-off) and `board.py` (state and schema; edits; render). Keep `office.py` and `board.py` as the entry points so no skill's command line changes.
3. One argv parser in `board.py` that returns values and positions; delete the copies and the dead code above.
4. Add coverage to one CI job as a report, with no threshold at first.

---

## From HOLES.md, still worth doing

These are already listed there; the review found nothing that changes them, only reasons to do two of them sooner.

- **Item 1, a fresh session on a new project.** Plan 1's first two findings are what such a run would have hit on its first counted sweep. Do the trial after plans 1 to 3, not before.
- **Item 27, a third review.** This document is it for the tools. The skills' text (`skills/`) was not reviewed here beyond checking 26 commands they name against the tools (all exist).
- **Item 4, the Mermaid diagrams** are still not rendered; a CI step with the Mermaid CLI would settle it.

## What held up

Worth knowing what not to touch: every string from the state, roadmap and plans is escaped in the pages (one field aside); held edits are not applied twice when a run is killed between its two writes; git arguments are never built from unchecked text; the journal locks every write; the two copies of `gym_kit.py` are tested for equality; the sweep reuses the queue's process code; polling intervals and per-lane git calls are not a cost.
