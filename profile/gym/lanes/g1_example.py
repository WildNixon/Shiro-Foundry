"""G1: an example lane. Prereg: gym/prereg/G1.json. Contract: gym/contracts/G1-artifacts.md.

A complete, tiny lane to copy: it shows every part a lane needs, on a task small enough to read in one sitting.
Replace the task with your own; keep the parts.

The task: the thing under test answers "what is the median of these numbers?". The builder's command writes
samples.jsonl into the run folder, one unit per line: {"id": "...", "values": [numbers], "answer": number}.

    the grader      pure code. It works the truth out itself (its own median, never the builder's function) and
                    reads only the run folder: it imports nothing from the project.
    the unit        one distinct list of values. A list seen twice counts once.
    the null        the mean of the values: the strongest answer that knows nothing about medians. The headline
                    must beat it on the same units (a paired bootstrap by unit, from gym_kit).
    the veto        padding. Repeating one easy unit raises n and the score at no cost, so repeats count once; and
                    a list of fewer than MIN_VALUES numbers is skipped and counted (any answerer gets it right).
    the control     the truth rotated by one unit. An honest set of answers scores near zero against it; if the
                    rotated key scores above CONTROL_MAX the units cannot tell right from wrong, and the run is VOID.
    the self-check  every run: the true key must score 100 and an all-wrong key 0 through the one grading
                    function, or the run is VOID.

The bar and the minimum n are the prereg's (bars[b1].threshold, min_n.units). While the prereg leaves them empty
the lane can only say MEASURING. Run this file with no argument for its selftest.
"""
from __future__ import annotations

import json
import os
import random
import statistics
import subprocess
import sys

GYM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if GYM not in sys.path:
    sys.path.insert(0, GYM)

import gym_kit  # noqa: E402

LANE = "G1"
TITLE = "Example: the answers are the medians, and beat the mean"
GRADER_VERSION = "g1-v1"

# The command that makes the artifacts, as the builder's contract names it: a list of arguments, run in the
# checkout with GYM_RUN_DIR set to the run folder. It must write the files the contract lists into that folder.
# Empty: the lane's own stand-in writes them, so the example runs before any project code exists. A stand-in is
# not the thing under test: a counted run on it is VOID.
COLLECT = []
COLLECT_TIMEOUT_S = 600

ARTIFACT = "samples.jsonl"
MIN_VALUES = 3       # a shorter list is skipped: the null solves it
CONTROL_MAX = 20.0   # the rotated key may score at most this, in percent
TOLERANCE = 1e-9


class LaneRefused(Exception):
    gym_refused = True


def prereg():
    """The registered numbers: (bar in percent or None, minimum units or None)."""
    path = os.path.join(GYM, "prereg", LANE + ".json")
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError):
        return None, None
    bar = next((b.get("threshold") for b in doc.get("bars") or [] if isinstance(b, dict) and b.get("id") == "b1"), None)
    min_n = (doc.get("min_n") or {}).get("units") if isinstance(doc.get("min_n"), dict) else None
    number = lambda v: v if isinstance(v, (int, float)) and not isinstance(v, bool) else None  # noqa: E731
    return number(bar), number(min_n)


# ------------------------------------------------------------------------------------------ collect

def _stand_in(run_dir):
    rng = random.Random(0)
    with open(os.path.join(run_dir, ARTIFACT), "w", encoding="utf-8", newline="\n") as fh:
        for i in range(40):
            values = [rng.randrange(1, 1000) for _ in range(rng.choice((5, 7, 9)))]
            fh.write(json.dumps({"id": "u%02d" % i, "values": values, "answer": sorted(values)[len(values) // 2]}) + "\n")


def collect(run_dir, root, mode):
    """Make the artifacts in run_dir. Returns the facts the runner keeps in the manifest."""
    if not COLLECT:
        _stand_in(run_dir)
        return {"stand_in": True}
    env = dict(os.environ, GYM_RUN_DIR=run_dir)
    try:
        r = subprocess.run(list(COLLECT), cwd=root, env=env, capture_output=True, text=True, timeout=COLLECT_TIMEOUT_S)
    except (OSError, subprocess.SubprocessError) as e:
        return {"stand_in": False, "command": list(COLLECT), "error": "%s: %s" % (type(e).__name__, e)}
    with open(os.path.join(run_dir, "collect.log"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(r.stdout + r.stderr)
    return {"stand_in": False, "command": list(COLLECT), "exit": r.returncode}


# ------------------------------------------------------------------------------------------ grade

def truth_of(values):
    """The grader's own definition of the target."""
    return statistics.median(values)


def null_of(values):
    return sum(values) / len(values)


def right(answer, truth):
    return isinstance(answer, (int, float)) and not isinstance(answer, bool) and abs(answer - truth) <= TOLERANCE


def score(answers, key):
    """Percent of the units answered right against a key. The one grading function: the headline, the control and
    the self-check all go through it."""
    if not key:
        return None
    return 100.0 * sum(1 for a, k in zip(answers, key) if right(a, k)) / len(key)


def selfcheck():
    key = [1.0, 2.0, 3.0, 4.0]
    problems = []
    if score(key, key) != 100.0:
        problems.append("grader self-check: the true key did not score 100")
    if score([k + 1 for k in key], key) != 0.0:
        problems.append("grader self-check: an all-wrong key did not score 0")
    return problems


def load_run(run_dir):
    def opt(name):
        try:
            with open(os.path.join(run_dir, name), encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, ValueError):
            return None
    rows, bad = [], 0
    try:
        with open(os.path.join(run_dir, ARTIFACT), encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    row = None
                values = row.get("values") if isinstance(row, dict) else None
                if (isinstance(values, list) and values
                        and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in values)):
                    rows.append(row)
                else:
                    bad += 1
        found = True
    except OSError:
        found = False
    return {"dir": run_dir, "manifest": opt("manifest.json") or {}, "rows": rows, "bad_rows": bad, "found": found}


def evaluate(run, bar=None, min_n=None):
    """The verdict on a run, as a pure function of what the run folder held."""
    m = run["manifest"]
    collect_facts = m.get("collect") if isinstance(m.get("collect"), dict) else {}
    counted = m.get("mode") == "counted"
    void = list(selfcheck())
    if not run["found"]:
        void.append("the run folder has no %s" % ARTIFACT)
    if collect_facts.get("error") or collect_facts.get("exit") not in (None, 0):
        void.append("the collect command failed (%s)" % (collect_facts.get("error") or "exit %s" % collect_facts.get("exit")))
    if counted and collect_facts.get("stand_in"):
        void.append("the artifacts are the lane's stand-in, not the thing under test (set COLLECT from the contract)")
    if counted and m.get("tree_clean_after") is False:
        void.append("blast radius: the run changed the checkout (is the run folder git-ignored?)")

    units, repeats, short = {}, 0, 0
    for row in run["rows"]:
        values = row["values"]
        if len(values) < MIN_VALUES:
            short += 1
            continue
        key = tuple(sorted(values))
        if key in units:
            repeats += 1
            continue
        units[key] = row
    ids = list(units)
    truth = [truth_of(units[k]["values"]) for k in ids]
    answers = [units[k].get("answer") for k in ids]
    nulls = [null_of(units[k]["values"]) for k in ids]
    n = len(ids)
    headline = score(answers, truth)
    null_score = score(nulls, truth)
    rotated = score(answers, truth[1:] + truth[:1]) if n > 1 else None
    if rotated is not None and rotated > CONTROL_MAX:
        void.append("control: the truth rotated by one unit still scores %.1f (at most %.1f allowed): the units "
                    "cannot tell a right answer from a wrong one" % (rotated, CONTROL_MAX))
    pairs = [(i, 100.0 * right(nulls[i], truth[i]), 100.0 * right(answers[i], truth[i])) for i in range(n)]
    ci = gym_kit.paired_bootstrap(pairs)

    if void:
        word, why = gym_kit.decide(n, 0, void=void)
    elif bar is None or min_n is None:
        word, why = "MEASURING", "the prereg registers no bar or minimum n yet, so nothing can be decided"
    else:
        guards = [] if headline is None or headline >= bar else ["b1: %.1f%% right is under the bar %.1f%%" % (headline, bar)]
        word, why = gym_kit.decide(n, min_n, lo=ci["lo"], hi=ci["hi"], bar=0.0, guards_failed=guards)
        if word in ("PASS", "MARGINAL", "FAIL") and not guards:
            why = "answers minus the null, in points: " + why
    if collect_facts.get("stand_in"):
        why = "(stand-in artifacts) " + why
    return {
        "lane": LANE, "grader": GRADER_VERSION, "run_id": m.get("run_id") or os.path.basename(os.path.normpath(run["dir"])),
        "verdict": word, "why": why, "n": 0 if word == "VOID" else n, "headline": headline, "bar": bar, "min_n": min_n,
        "null": null_score, "delta": ci["mean"], "delta_ci": [ci["lo"], ci["hi"]], "control_rotated": rotated,
        "skipped": {"repeated_units": repeats, "short_units": short, "unreadable_rows": run["bad_rows"]},
        "void": void, "stand_in": bool(collect_facts.get("stand_in")),
    }


def grade(run_dir):
    bar, min_n = prereg()
    return evaluate(load_run(run_dir), bar, min_n)


def honest_grade(result, run_dir):
    s = result["skipped"]
    fmt = lambda v: "none" if v is None else "%.1f" % v  # noqa: E731
    return "\n".join([
        "# %s honest grade: %s" % (LANE, result["run_id"]),
        "",
        "1. **Verdict: %s.** %s" % (result["verdict"], result["why"]),
        "2. **Headline:** %s%% of %d units right (bar %s); the null scores %s%%; answers minus the null %s points, "
        "CI [%s, %s], by unit." % (fmt(result["headline"]), result["n"], fmt(result["bar"]), fmt(result["null"]),
                                   fmt(result["delta"]), fmt(result["delta_ci"][0]), fmt(result["delta_ci"][1])),
        "3. **What did not hold:** %s" % ("; ".join(result["void"]) or "nothing voided the run."),
        "4. **Ceiling:** 100% right is the most this grader can show; a run pinned there needs a harder task, not more runs.",
        "5. **Exercised:** the rotated-key control scored %s%% (limit %.1f); %d repeated, %d short and %d unreadable "
        "rows were left out." % (fmt(result["control_rotated"]), CONTROL_MAX, s["repeated_units"], s["short_units"], s["unreadable_rows"]),
        "6. **Evidence:** run `%s`; series `gym/series/%s.json`; prereg `gym/prereg/%s.json`." % (run_dir, LANE, LANE),
        "7. **Rollback:** this lane deploys nothing.",
        "",
    ])


# ------------------------------------------------------------------------------------------ selftest

def _rows(n=40, wrong=0, seed=1, size=7):
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        values = [rng.randrange(1, 1000) for _ in range(size)]
        rows.append({"id": "s%d" % i, "values": values, "answer": statistics.median(values) + (1 if i < wrong else 0)})
    return rows


def _run(rows, mode="dev", stand_in=False, clean=True, found=True):
    return {"dir": "selftest", "found": found, "rows": rows, "bad_rows": 0,
            "manifest": {"run_id": "selftest", "mode": mode, "tree_clean_after": clean, "collect": {"stand_in": stand_in}}}


def selftest():
    """Every verdict word this lane can say, and each control, reached by a planted run."""
    good = _rows()
    padded = _rows(n=5) * 8                                    # 40 rows, 5 units: the padding veto must see 5
    null_like = [dict(r, answer=null_of(r["values"])) for r in _rows()]  # a candidate that is the null cannot beat it
    flat = [{"id": "f%d" % i, "values": [5, 5, 5, i], "answer": 5} for i in range(40)]  # every truth is 5
    cases = [
        ("PASS", _run(good), 90, 20, "honest answers clear the bar and beat the null"),
        ("FAIL", _run(_rows(wrong=30)), 90, 20, "30 of 40 wrong: under the bar"),
        ("MARGINAL", _run(null_like), 0, 20, "the null as a candidate: it can tie the null, never beat it"),
        ("MEASURING", _run(good), 90, 200, "40 units against a minimum of 200"),
        ("MEASURING", _run(padded), 90, 20, "padding: 40 rows are 5 units"),
        ("MEASURING", _run(good), None, None, "no bar registered"),
        ("VOID", _run(flat), 90, 20, "the rotated-key control still scores: the units cannot fail"),
        ("VOID", _run(good, mode="counted", stand_in=True), 90, 20, "a counted run on the stand-in"),
        ("VOID", _run(good, mode="counted", clean=False), 90, 20, "the run changed the checkout"),
        ("VOID", _run([], found=False), 90, 20, "no artifact"),
    ]
    bad = 0
    for want, run, bar, min_n, what in cases:
        got = evaluate(run, bar, min_n)
        ok = got["verdict"] == want and (want != "VOID" or got["n"] == 0)
        bad += not ok
        print("  %s %s selftest: want %-9s got %-9s %s" % ("ok  " if ok else "FAIL", LANE, want, got["verdict"], what))
    padded_n = evaluate(_run(padded), 90, 1)["n"]
    if padded_n != 5:
        bad += 1
        print("  FAIL %s selftest: padding counted %d units, expected 5" % (LANE, padded_n))
    for problem in selfcheck():
        bad += 1
        print("  FAIL " + problem)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(selftest())
