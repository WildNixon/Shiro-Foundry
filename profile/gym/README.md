# The gym

A gym decides what "done" means here: a milestone is done when its lane says PASS on a counted run. This folder
was started by the Foundry's `gym_init.py` and is the project's own from then on. The method is in the gym skill;
read it before changing a grader.

## The commands

    python gym/run.py list              the lanes
    python gym/run.py selftest          the kit's, the runner's and every lane's selftest
    python gym/run.py dev G1            an uncounted run: collects, grades dry, publishes nothing
    python gym/run.py counted G1        a counted run: one point in gym/series/G1.json

Exit codes:

| Code | Meaning |
|---|---|
| 0 | PASS, a passing selftest, or `list` |
| 1 | any other verdict word (MARGINAL, FAIL, MEASURING, STARVED, VOID, SATURATED), or a failing selftest |
| 2 | a refusal (nothing was published), or a command line the runner does not know |
| 3 | the runner failed: an error that is no refusal, with its traceback on stderr, or a lane (or code it calls) that called `sys.exit`, whatever code it gave. There is no verdict: never read it as a FAIL, and a lane's `sys.exit(0)` is never the PASS code |
| 130 | interrupted (Ctrl+C). There is no verdict |

A run's folder is `out/gym/<lane>/<run id>/`. Keep `out/` git-ignored: a counted run needs a clean tree before it
starts and checks it again after the collect. The runner publishes a counted run as VOID with the reason,
whatever the lane said, when nothing shows it sampled the commit it names: the tree is not clean after the
collect; git cannot say whether it is (it could before the run); or HEAD or its reflog is not what it was before
the collect (the collect committed, reset or checked out). It asks git without `GIT_DIR`, `GIT_WORK_TREE` and
`GIT_INDEX_FILE`, so a collect that sets one does not turn these checks to another repository.

A counted run is refused when the prereg's `contract.path` does not resolve to a file inside the checkout (an
absolute path elsewhere, or one whose `..` leaves it).

## Who writes which file

| File | Who | When |
|---|---|---|
| `contracts/<lane>-artifacts.md` | the builder | before any code |
| `prereg/<lane>.json` | an independent grader | after reading the contract, before any counted data |
| `lanes/<lane>_*.py` | the same grader | with the prereg |
| `run.py`, `gym_kit.py` | a grader | when the runner itself must change |
| `lane-inputs.toml` | the manager | when a lane's inputs change |
| `series/`, `grades/`, `charts/` | `run.py counted` only | never by hand |

The grader is never the builder, and never the manager who directed the build. The grader does not open the
builder's code: a lane reads the run folder, and what the contract says is in it.

## The order of work for a lane

1. The builder writes the contract: what is under test, the one command, the artifacts it leaves in the run
   folder, what a unit is.
2. The grader reads the contract and writes the prereg: the question, the unit, the null to beat, the minimum n,
   the bar, the controls and what voids a run, the rule that maps results to a verdict word. The grader pins the
   contract in the prereg by its sha256 and sets `"status": "registered"`.
3. The grader writes the lane: pure code that reads the run folder, with a veto for the cheapest worthless
   winner, a control that must fail, a self-check on every run, and a selftest that reaches every verdict word.
4. Both are committed before the first counted run. The bar never moves after that. A change is a dated
   amendment that says whether counted data existed.
5. The builder builds, and checks with `dev` runs. A dev run decides nothing.
6. A counted run: a clean tree, `python gym/run.py counted <lane>`, then commit the records it wrote.
7. A run that did not pass is filed as a numbered failure with a plan. It is never re-run until it passes without
   a change.

`gym_init.py lane add <lane> --title "..."` adds the files for one more lane; `gym_init.py check` reads the gym
as the Foundry's tools will.

## The verdict words

| Word | Meaning |
|---|---|
| PASS | the bar is met under the prereg's rule at n >= the minimum, and the controls held |
| MARGINAL | inside the noise: the interval straddles the bar |
| FAIL | the bar is missed with enough n, and the controls held, so the miss is real |
| MEASURING | too few units so far, or no bar registered yet |
| STARVED | too few units, and the rows show why |
| VOID | the instrument broke: a control failed, the wrong thing was graded, the self-check failed. n is reported as 0 |
| SATURATED | pinned at the maximum: the test is too easy |

The word is the lane's. `run.py` never chooses one (its one change is the VOID above, for a run that cannot be
said to have sampled its commit; the point keeps the lane's word as `lane_verdict`), and a run's outcome is told by quoting it, not by a builder's
own reading of a dev run.

## What a lane file gives the runner

    LANE, TITLE, GRADER_VERSION        its name as run.py's LANES spells it, one line, the grader's version
    collect(run_dir, root, mode)       run the contract's command; the artifacts land in run_dir
    grade(run_dir)                     a dict with "verdict", "n" and "why" at least ("headline" and "bar" are charted)
    selftest()                         0 when every verdict word and every control was reached by a planted run
    honest_grade(result, run_dir)      optional: the text of the grade file

A lane file ends with an `if __name__ == "__main__":` block that runs its selftest, so the file can be run alone.

## The series file

`gym/series/<lane>.json` is the record the board and the chart pages read:

    {"meta": {"lane": "G1", "grader": "g1-v1", "prereg": "<prereg_id>"},
     "points": [{"run_id": "20300110-113607-0a1f", "verdict": "PASS", "n": 40, "ts": 1894300567.1,
                 "why": "...", "headline": 97.5, "commit": "<sha>", "run_dir": "out/gym/G1/20300110-113607-0a1f"}]}

One point per counted run, oldest first. A file with no point is a lane that has not run counted yet. A series
never changes grader version or prereg in place: a new instrument starts a new file, and the old one is moved
aside, not deleted.

## The example lane

`lanes/g1_example.py` is a whole lane on a toy task, to copy and replace. Until its `COLLECT` names the
contract's command it grades its own stand-in, and a counted run on the stand-in is VOID.
