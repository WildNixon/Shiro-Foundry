# The gym in a Foundry project

The gym decides what "done" means: a milestone is done when its lane says PASS on a counted run. This page is about setting one up and running it with the Foundry's tools. The method itself (how to choose a unit, a null and a bar, how to write a grader that cannot be fooled, how to audit one) is in the `gym` skill (`.claude/skills/gym/SKILL.md` and its references). Read it before changing a grader. The ideas in short are in [concepts.md](concepts.md#the-gym-in-one-page).

- [Starting a gym](#starting-a-gym)
- [The files](#the-files)
- [The lane interface](#the-lane-interface)
- [The series record](#the-series-record)
- [The order of work between builder and grader](#the-order-of-work-between-builder-and-grader)
- [Dev runs](#dev-runs)
- [Counted runs](#counted-runs)
- [The sweep](#the-sweep)
- [`lanes_for.py` and `lane-inputs.toml`](#lanes_forpy-and-lane-inputstoml)
- [What each verdict word means for the map](#what-each-verdict-word-means-for-the-map)

## Starting a gym

```
python scripts/foundry/gym_init.py init --lane G1 --title "the app starts and shows one screen"
```

It writes the smallest gym the tools can read, under `paths.gym` (default `gym/`). A file that is already there is kept and named, never overwritten. `founder.py init --gym` runs the same command, and git-ignores the run folders (`/out/gym/`). The three `[measure]` lines are printed with `python`, or with the profile's `commands.python` when that is set. The output, and the three `[measure]` lines it tells you to set, are in [getting-started.md](getting-started.md#start-the-gym).

What it writes runs as it is: `run.py selftest` passes and `run.py dev G1` grades the example lane's own stand-in. It is a start, not a gym that decides anything. The prereg is a template, the contract is a draft, and the example lane grades a toy task.

One more lane:

```
python scripts/foundry/gym_init.py lane add G2 --title "what the user makes is kept"
```

```
wrote gym/lanes/g2_what_the_user_makes_is_k.py
wrote gym/prereg/G2.json
wrote gym/contracts/G2-artifacts.md
wrote gym/series/G2.json
edited gym/run.py: LANES now names G2
edited gym/lane-inputs.toml: [lanes.G2] added (list there every path the lane's result depends on)

Next: python gym/run.py selftest, then python ~/myproject/scripts/foundry/gym_init.py check
```

Read the gym as the tools will:

```
python scripts/foundry/gym_init.py check
```

```
note    G1: its contract is still a draft
note    G2: its prereg is still a template (not registered): no counted run until the grader fills it
note    G2: its prereg pins no contract yet (contract.path is empty)
note    G2: its contract is still a draft
gym_init check: 2 lane(s) (G1, G2), 0 problem(s), 4 note(s)
```

`init` and `lane add` write tracked files. In the main checkout they are refused (exit 3) while the manager's freeze is on or a counted run or sweep is in the queue: a counted run checks that the tree is clean, and a new file would stop it. In a worktree nothing is frozen. `lane add` exits 1 and leaves `run.py` alone if the file would not compile with the lane's line added. `check` only reads and always runs.

`check` exits 1 on any problem. It looks at: the lane names in `run.py` against `measure.lane_pattern`; each lane's file (with a selftest block), prereg and contract; a prereg that pins a contract, against the sha256 of that file in this checkout; `lane-inputs.toml` against `run.py`, both ways; what `run.py list` prints; and each series file's shape. A prereg that is still a template is a note, not a problem.

## The files

| File | What it is | Who writes it | When |
|---|---|---|---|
| `gym/run.py` | The runner: `list`, `selftest`, `dev <lane>`, `counted <lane>` | A grader | When the runner itself must change |
| `gym/gym_kit.py` | Shared grading code (the verdict words, the bootstrap) | A grader | Rarely |
| `gym/contracts/<lane>-artifacts.md` | The contract | The builder | Before any code |
| `gym/prereg/<lane>.json` | The pre-registration | An independent grader | After reading the contract, before any counted data |
| `gym/lanes/<lane>_*.py` | The lane | The same grader | With the prereg |
| `gym/lane-inputs.toml` | Which paths can change each lane's result | The manager | When a lane's inputs change |
| `gym/series/<lane>.json` | The record: one point per counted run | `run.py counted` only | Never by hand |
| `gym/grades/<lane>-<run id>.md` | The grade of one counted run, in words | `run.py counted` only | |
| `gym/charts/<lane>.html` | The lane's chart | `run.py counted` only | |
| `gym/README.md` | The gym's own page: the commands and the order of work | | |
| `out/gym/<lane>/<run id>/` | A run's folder: the manifest, the artifacts, the grade. Git-ignored | A run | |

Two profile keys keep the wall between builder and grader:

- `measure.grader_owned` (default `gym/prereg`, `gym/lanes`, `gym/run.py`, `gym/gym_kit.py`): only a grader writes these. `office.py handin` makes any other role's change to them a PROBLEM.
- `measure.records` (default `gym/series`, `gym/charts`, `gym/grades`): a run's records, written by the run and committed by whoever queued it, as the run's own commit. `office.py handin` makes a change to them a PROBLEM for any badge that is neither a grader nor the manager.

`handin` reads the branch's tree against its base as well as each commit, so a merge that kept one side does not carry a change past either wall.

## The lane interface

A lane file gives the runner:

| Name | What it is |
|---|---|
| `LANE`, `TITLE`, `GRADER_VERSION` | The lane's name as `run.py`'s `LANES` spells it, one line on what it proves, the grader's version |
| `collect(run_dir, root, mode)` | Runs the contract's command; the artifacts land in `run_dir`. Returns facts for the manifest |
| `grade(run_dir)` | Reads that folder and nothing else. Returns a dict with `verdict`, `n` and `why` at least (`headline` and `bar` are charted) |
| `selftest()` | Returns 0 when every verdict word and every control was reached by a planted run |
| `honest_grade(result, run_dir)` | Optional: the text of the grade file |

A lane file ends with an `if __name__ == "__main__":` block that runs its selftest, so the file can be run alone. `office.py hire` names that command in the brief of a badge hired for the lane.

The verdict word is the lane's. The runner never chooses one, and a lane that returns no known word is refused. It changes one only when nothing shows that a counted run sampled the commit it names: such a run is published as VOID ([Counted runs](#counted-runs)).

`gym/lanes/g1_example.py` is a whole lane on a toy task, to copy and replace. Until its `COLLECT` names the contract's command it grades its own stand-in, and a counted run on the stand-in is VOID.

### The runner's exit codes

| Code | Meaning |
|---|---|
| 0 | PASS, a passing selftest, or `list` |
| 1 | Any other verdict word (MARGINAL, FAIL, MEASURING, STARVED, VOID, SATURATED), or a failing selftest |
| 2 | A refusal (nothing was published), or a command line the runner does not know |
| 3 | The runner failed: an error that is no refusal, with its traceback on stderr, or a lane (or code it calls) that ended the process with `sys.exit`, whatever code it gave. There is no verdict. Never read it as a FAIL, and a lane's `sys.exit(0)` is never the PASS code |
| 130 | Interrupted (Ctrl+C). There is no verdict |

Exits 2 and 3 are the defaults of the profile's `measure.no_verdict_exits`: `sweep.py` lists a lane that ends with one apart from the lanes that gave a verdict.

## The series record

`gym/series/<lane>.json` is what the board and the chart pages read. One point per counted run, oldest first:

```json
{
 "meta": {"lane": "G1", "grader": "g1-v1", "prereg": "G1-v1-medians-beat-the-mean"},
 "points": [
  {
   "run_id": "20261124-153129-0068",
   "verdict": "VOID",
   "n": 0,
   "why": "(stand-in artifacts) instrument void: the artifacts are the lane's stand-in, not the thing under test (set COLLECT from the contract) (n reported as 0)",
   "headline": 100.0,
   "commit": "1633a1bd4be04d42855d927937115c3524804529",
   "run_dir": "out/gym/G1/20261124-153129-0068",
   "ts": 1795555889.55
  }
 ]
}
```

A point the runner itself made VOID (nothing showed that the run sampled the commit it names) also carries `lane_verdict`: the word the lane said.

What the board takes from it: the last point's `verdict`, `n`, `run_id` and `ts` (the lane's latest run), the point before it (the previous verdict), the count of each verdict, and `meta.grader`. A file with no point is a lane that has not run counted yet. A project whose gym has its own runner only needs to write this shape for the board to read it.

A series never changes grader version or prereg in place: a new instrument starts a new file, and the old one is moved aside, not deleted.

## The order of work between builder and grader

1. **The manager sets the checkpoint** before any code: the lane, the milestone, the builder, the grader.
   ```
   python scripts/foundry/board.py checkpoint add --lane G1 --milestone M1 --builder EMP-01 --grader EMP-02 --block 3
   ```
2. **The builder writes the contract**: what is under test, the one command, the artifacts it leaves in the run folder, what a unit is.
3. **The grader reads the contract and writes the prereg**: the question, the unit, the null to beat, the minimum n, the bar, the controls and what voids a run, the rule that maps results to a verdict word. The grader pins the contract in the prereg by its sha256 and sets `"status": "registered"`.
4. **The grader writes the lane**: pure code that reads the run folder, with a veto for the cheapest worthless winner, a control that must fail, a self-check on every run, and a selftest that reaches every verdict word.
5. **Both are committed before the first counted run.** The bar never moves after that. A change is a dated amendment that says whether counted data existed. The builder answers the grader's questions by a dated contract amendment; the grader pins that by a prereg amendment.
6. **The builder builds**, and checks with dev runs. A dev run decides nothing.
7. **The grader dry-grades a dev run** at the tree the counted run will use, and says GO.
8. **The counted run**, in the checkpoint's block, then its records are committed.
9. **A run that did not pass is filed** as a numbered failure with a plan. It is never run again unchanged until it passes.

The grader is its own session, hired with `--title grader --lane <lane>`. It does not open the builder's code: a lane reads the run folder, and what the contract says is in it.

## Dev runs

```
python gym/run.py dev G1
```

```
G1 dev 20261124-151438-0ae5: MEASURING (n=40) (stand-in artifacts) the prereg registers no bar or minimum n yet, so nothing can be decided
dry grade (not published): ~/myproject/out/gym/G1/20261124-151438-0ae5/dry-grade.json
```

A dev run collects, grades dry and publishes nothing. It leaves `dry-grade.json` in the run folder.

- **With no shared resource**, the builder runs it in its own worktree.
- **With a shared resource**, it goes through the queue under the builder's badge id:
  ```
  python scripts/foundry/rq.py run --id EMP-01 --job "dev run G1" --max 30m -- "python gym/run.py dev G1"
  ```
  A job whose `--job` text starts with `dev`, or says `dev run`, `(dev)`, `not counted` or `uncounted`, or holds the profile's `measure.dev` command, is read as a dev run and never as a possible counted one.

The builder posts the run folder so the grader finds it without a relay:

```
python scripts/foundry/office.py progress --badge "<your line>" --pct 70 --eta 30m --run out/gym/G1/20261124-151438-0ae5
python scripts/foundry/office.py runs
```

A builder reports the grader's word on a dev run, not its own reading of it.

## Counted runs

A counted run adds one point to the lane's series, a grade file and a chart. `run.py` refuses one (exit 2, nothing written) when:

- the checkout is not a git checkout, or `git status` shows any change, tracked or not;
- the lane has no prereg, or the prereg is still a template;
- the prereg pins no contract;
- the prereg's `contract.path` does not resolve to a file inside the checkout (an absolute path elsewhere, or one whose `..` leaves it);
- the contract's file does not have the pinned sha256.

```
refused: the tree is not clean (M docs/progress-map.html; M docs/progress/state.json; ...): commit or remove every change, tracked or not, then run again
```

The runner looks again after the collect. It publishes the run as VOID with the reason, whatever the lane said, when nothing shows that the run sampled the commit it names:

- the tree is not clean after the collect (the manifest's `tree_clean_after` is false, and the changed paths are in `tree_changes_after`);
- git cannot say whether it is (`tree_clean_after` is null): git answered before the run, so something in the run stopped it;
- HEAD, or HEAD's reflog, is not what it was before the collect (the manifest's `head_moved`, and `commit_after` when HEAD names another commit): the collect committed, reset or checked out, so a clean tree afterwards says nothing.

The lane's own word is kept as `lane_verdict` in the series point and in the run folder's `grade.json`. The runner asks git with `GIT_DIR`, `GIT_WORK_TREE` and `GIT_INDEX_FILE` taken out of the environment, so a collect that sets one does not point these checks at another repository. So keep run folders and scratch files under a git-ignored folder (`out/`), and let no collect commit.

Exit 3 from the runner is not a verdict: the runner itself failed (its traceback is on stderr), or a lane called `sys.exit`. Exit 130 is an interrupt. Nothing was decided either way; find the cause, then run again.

The command is the lane's pinned run command from its prereg: the profile's `measure.counted` plus any flag the prereg names. The manager asks the grader for it, and runs it in the main checkout, in the checkpoint's block, after the grader's pins.

**With a shared resource**, the manager queues it under a marked id. The id is what freezes the main checkout:

```
python scripts/foundry/rq.py run --id MGR-2-counted-G1 --prio 0 --all-seats --max 3h --job "counted G1" -- "python gym/run.py counted G1"
```

Leave out `--all-seats` when the lane needs one seat and the seats share no state.

**With no shared resource**, the manager turns the freeze on by hand, runs the command, commits the records and lifts the freeze. `--max` takes a unit (`30m`, `3h`); a bare number is refused.

```
python scripts/foundry/office.py freeze on --by "<the manager's line>" --why "counted G1" --lane G1 --max 3h
python gym/run.py counted G1
git add -- gym/series gym/charts gym/grades
git commit -m "G1 counted run: records"
python scripts/foundry/office.py freeze off --by "<the manager's line>" --note "records committed"
```

A real counted run of the starter lane, with its prereg registered but its `COLLECT` still the stand-in:

```
G1 20261124-153129-0068: VOID (n=0) (stand-in artifacts) instrument void: the artifacts are the lane's stand-in, not the thing under test (set COLLECT from the contract) (n reported as 0)
series: ~/myproject/gym/series/G1.json
honest grade: ~/myproject/gym/grades/G1-20261124-153129-0068.md
commit the records (series, grades, charts) before the next counted run
```

Whoever ran it commits the records as the run's own commit, before any merge or map edit touches the main branch. Commit them as the runner wrote them.

While the run waits or runs, nothing in the main checkout changes: [concepts.md](concepts.md#the-freeze-during-a-counted-run).

## The sweep

`sweep.py` runs the counted run of every lane, one lane at a time, in the main checkout. A push closes with one. Full flags and exit codes: [tools.md](tools.md#sweeppy).

```
python scripts/foundry/sweep.py run --id MGR-1 --out out/sweeps/close-1 --check-only
```

```
sweep: start check passed for G1 at 8ff7bc4d90; --check-only, nothing run
```

```
python scripts/foundry/sweep.py status --out out/sweeps/close-1
```

```
sweep: MGR-1: G1 at 8ff7bc4d90
  run (0): none
  left (1): G1 (not run; that is not a verdict)
  the sweep: ended 2026-11-24 15:17:44 exit 0 (check only)
```

Then the sweep itself, under a new folder name:

```
python scripts/foundry/sweep.py run --id MGR-1 --out out/sweeps/close-2
```

How it behaves:

- **`--out`** is the sweep's own folder. It must lie under a git-ignored folder of the main checkout and must not exist yet. A `--check-only` run uses its folder up too: give the real run a new name.
- **The command** of each lane is `measure.counted` with `<lane>` replaced. The sweep refuses to start when that key is empty or has no `<lane>`.
- **Before the first lane** the main checkout must be clean. **Before each later lane, and again after every lane,** it must still be at the commit the sweep started at, and clean apart from the run's own records (`measure.records`). HEAD's reflog is compared too, so a commit made and reset away again counts. Anything else stops the sweep at once (exit 4). The lanes left are "not run", which is not a verdict, and a lane during which the tree changed carries the note `tree changed during this lane: ...` on its `runs.tsv` row.
- **A lane that exits non-zero does not stop the sweep.** Its exit code is recorded and the grader reads the run.
- **A lane with no verdict.** The exit codes in `measure.no_verdict_exits` (default `[2, 3]`: the runner refused, or the runner failed) mean the command ran and gave no verdict. Such a lane carries `no verdict (exit <n>)` on its row, `status` lists it under its own heading, and the sweep itself exits 1.
- **If the main branch moved** between `--queued-at` and the start, `lanes_for.py` says which lanes the commits between can move. The sweep does not start if one of them is a lane it would run (exit 5): queue it again at the new commit.
- **The freeze.** With or without a shared resource, the sweep turns the office's freeze on for its whole run and off at its end: between two lanes its queue id neither holds nor waits. It does not start while someone else's freeze is on (exit 3). A freeze its own badge id set by hand stays as it is: the sweep runs under it and leaves it on. Before every lane it reads the freeze again, and stops (exit 3) when the one it runs under was lifted or replaced. `office.py freeze off` lifts a sweep's freeze only with `--force`.
- **With a shared resource**, each lane also runs through the queue under `<badge id>-sweep` at prio 0 with every seat. A lane counts as run only when its log holds both of the queue's lines with the lane's own token, `rq: started [<token>]` and `rq: finished exit <n> [<token>]`. Otherwise (the queue refused, waited too long, could not start the shell, ended the command at its limit, or was stopped) it is recorded `not run (the queue: exit <n>): ...`, and the sweep stops (exit 6).
- **One sweep at a time.** A running sweep keeps `sweep.lock` in the office. A second sweep is refused (exit 3) while the first still touches its `alive` file, whoever queued it.
- **To pause it**, create a file named `sweep-STOP` in the office. The sweep stops before the next lane (exit 0).
- **To stop it**, interrupt it (Ctrl+C, TERM, HUP, or BREAK on Windows). It passes the stop on to the lane in flight, lifts its own freeze, writes `ended <time> interrupted` and exits 130, or 128 plus the signal's number. If it says seats may still be held, the manager frees them with `rq.py force-release`.
- **A lane in flight with no sweep alive** (a host shutdown, a killed session) reads `VOID: not run` in `status`.

It commits nothing. Its last lines tell whoever queued it to commit the run's records before anything else touches the main branch.

It writes, all under `--out`: `source.txt` (the id, the commits, the lanes, the resource, the freeze it wrote, and at the end `ended <time> exit <n>` or `ended <time> interrupted`), `started.tsv`, `runs.tsv` (lane, exit code, start, end, seconds, and a note when the queue did not run the lane, the lane gave no verdict, or the tree changed during it), `<lane>.log` and `alive`.

A sweep of two lanes whose preregs are still templates, so the runner refused both:

```
sweep: ended, exit 1: 2 of 2 lane(s) run: 0 gave a verdict, 2 gave no verdict (G1 exit 2, G2 exit 2)
```

```
sweep: MGR-1: G1 G2 at 8fe54fe31d
  run (0): none
  run, with no verdict (2; the command ran and gave none):
    G1  exit 2  0s  no verdict (exit 2)
    G2  exit 2  0s  no verdict (exit 2)
  left (0): none
  the sweep: ended 2026-11-24 17:32:36 exit 1
```

The sweep's exit codes, from 0 to 130, are in [tools.md](tools.md#sweeppy).

## `lanes_for.py` and `lane-inputs.toml`

After a merge, which lanes could that change have moved? `lanes_for.py` answers from a table the project keeps, `gym/lane-inputs.toml`. The manager uses it at the merge gate and to pick the lanes of a short sweep.

```
python scripts/foundry/lanes_for.py HEAD~2..HEAD --explain
```

```
G1    # path; always
        gym/prereg/G1.json  <- path
        gym/run.py  <- always
G2    # path; always
        gym/contracts/G2-artifacts.md  <- path
        gym/lanes/g2_what_the_user_makes_is_k.py  <- path
        gym/prereg/G2.json  <- path
        gym/run.py  <- always
# watched by no lane:
        docs/progress-map.html
        docs/progress/state.json
        gym/charts/G1.html
        gym/grades/G1-20261124-153129-0068.md
        gym/lane-inputs.toml
        gym/series/G1.json
        gym/series/G2.json
```

Without `--explain` it prints one lane a line. With no lane touched it prints nothing and exits 0. `--files a b c` takes a list of paths in place of a git range. `--skip GLOB` leaves matching paths out.

The table:

```toml
version = 1

[always]                      # paths that can change every lane (a lock file, the gym's shared code)
paths = ["requirements.lock", "gym/gym_kit.py", "gym/run.py"]

[broad]                       # what `broad = true` lanes react to
paths = ["src/", "tests/"]

[units.core]                  # a unit: a folder that is built as one thing, and the units it needs
dir = "src/core"
needs = ["util"]

[units.util]
dir = "src/util"

[groups.harness]              # inputs several lanes share
paths = ["tools/harness/"]
units = ["core"]

[lanes.G1]
paths = ["gym/lanes/g1_example.py", "gym/prereg/G1.json", "gym/contracts/G1-artifacts.md"]
units = ["core"]              # the lane reacts to these units and to every unit they need
uses = ["harness"]

[lanes.G2]
paths = ["gym/lanes/g2_store.py", "gym/prereg/G2.json"]
broad = true                  # only when the lane's inputs cannot be told from the code
```

- A path is a prefix (a folder ends in `/`) or a glob (`*` crosses `/`), from the checkout's top.
- Inside a unit, the files `measure.not_built` names (default `tests/`, `benches/`, `examples/` and `*.md`) select nothing through a unit or a broad rule.
- A unit with `own_paths = false` stands for its needs only.
- `measure.unit_manifests` (globs) names TOML manifests to read units from as well: the folder of each is a unit named by its `[package]` name, needing the units its `[dependencies]` and `[build-dependencies]` name.
- A lane that lists too little is not selected when it should be. Add to a lane's `paths` every part of the project its result depends on.

Check the table against the gym:

```
python scripts/foundry/lanes_for.py check
```

```
lanes in run.py: 1; in the table: 1
units no lane reads: none
lanes_for check: ok
```

It reads the gym's `run.py` as text for the lane names and never imports anything under the gym folder.

## What each verdict word means for the map

The board reads each lane's latest counted verdict from its series file. Nobody types one.

| Word | Is the milestone done? | What the manager does | What the check does |
|---|---|---|---|
| `PASS` | Yes. `board.py milestone set M1 --status done` is accepted | Marks the milestone done; the founder changes the requirement rows to `PASS` in the roadmap, naming the lane and its run | Warns about a `PASS` requirement row whose lane's newest run is no longer PASS, or that names no lane |
| `MARGINAL` | No | Files a failure with a plan | Warns while the lane has no failure entry naming it |
| `FAIL` | No | Files a failure with a plan | Warns while the lane has no failure entry naming it |
| `VOID` | No. The instrument broke; the run says nothing about the thing under test | Files a failure with a plan; fixes the instrument or the run, then runs again | Warns while the lane has no failure entry naming it |
| `STARVED` | No | Files a failure with a plan | Warns while the lane has no failure entry naming it |
| `MEASURING` | No | Nothing to file: the lane runs on | Asks for no entry |
| `SATURATED` | No | Nothing to file: the grader builds a harder measure | Asks for no entry |

`milestone set --status done` on a lane that has not passed:

```
refused: M1 is not done: its lane G1 has VOID as its latest counted verdict (run 20261124-153129-0068), not PASS. A milestone is done only when its gym lane says PASS. Run the lane's counted run, or record the user's override: --force --words "the user's own words"
```

After the VOID run above, the check's lines for the lane:

```
  checkpoints: 1
    G1 for M1: latest VOID; prereg yes; builder EMP-01; grader EMP-02
  needs attention: 1
    [lane] G1 VOID, run 20261124-153129-0068: F001 planned, owner EMP-01 / the next slot
```

A failure entry names a lane's run by `lane` and `run_id`, or by `lane` alone with no `run_id`. That is why `F001`, filed earlier for G1 with no run id, covers this run.

A failure that cannot be made to happen on demand is not dropped after one clean run: the manager skill keeps it `planned` until three clean runs of its lane in a row, or a fix with a test that makes it happen and then passes.
