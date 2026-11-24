# Pre-registration, verdicts and the statistics behind them

Read this for any gym whose result will decide something: shipping a candidate, flipping a flag, keeping a LoRA,
swapping a judge. A pure "find the best layout" search can skip the prereg, but it still needs the verdict words.

## When a prereg is required

Write one when the result will change what ships or what runs. Write it **before the first counted row exists**,
because a bar chosen after seeing numbers cannot fail in the way that matters. Preregs come in several shapes: an
open-book exam lane with a rotated-key control and a retrieval-augmented null (the template below), a paraphrase
A/B with a Jaccard precondition that pools across rounds (the short example after it), or a three-arm adapter test
(incumbent, candidate, plain base) with six bars.

## Template

```json
{
  "prereg_id": "<lane>-v1-<question in 3-5 words>",
  "written_at": "<ISO-8601 timestamp with UTC offset>",
  "written_before": "<proof no counted data existed: e.g. 'gym/series/x.json did not exist'>",
  "supersedes": null,
  "question": "Does <change> make <thing> better at <task>, as it ships?",
  "arms": {"A": "incumbent (shipped)", "B": "candidate", "C": "plain base (is the incumbent itself worth keeping?)"},
  "unit_of_inference": "the QUESTION (qid); cycles that re-ask a set are not independent",
  "pairing": "cycles 2k and 2k+1 draw the same set: Random('set-%d' % (cyc // 2)); letters from a disjoint stream",
  "preconditions": [
    "item-set Jaccard within pairs >= 0.95, else NOT GRADED",
    "served weights == <expected weights file> at the first and last ask, else VOID (composer impurity)"
  ],
  "statistic": "H1 = 100 x mean over distinct qids of mean(B_ok - A_ok)",
  "estimator": "paired bootstrap resampling distinct qids, B = 2000, seed 0; plus a sign test on discordant pairs",
  "min_n": {"units": 200, "distinct_items": 40},
  "bars": [
    {"id": "b1", "what": "H1 >= +5 points and CI lower bound > 0", "kind": "ship"},
    {"id": "b2", "what": "B beats the retrieval-augmented null", "kind": "ship"},
    {"id": "b3", "what": "ungrounded-number rate <= 0.022", "kind": "guard (must not regress)"}
  ],
  "controls": [
    {"name": "rotated_key", "expect": "open-book score under a key rotated one letter <= 15", "void_if": "> 15 on >= 40 pairs"},
    {"name": "grader_selfcheck", "expect": "true key = 100, all-rotated = 0 every cycle", "void_if": "any cycle fails"}
  ],
  "decision_rule": {
    "VOID": "any precondition or control fails (report n = 0)",
    "MEASURING": "units < min_n.units or distinct items < min_n.distinct_items",
    "STARVED": "as MEASURING, and the rows show a stall/pause share > 0.5",
    "PASS": "every ship bar and every guard bar holds",
    "MARGINAL": "CI straddles the ship bar, guards hold",
    "FAIL": "otherwise"
  },
  "constants_pinned_in_code": ["MIN_UNITS = 200", "SEED_FMT = 'set-%d'"],
  "amendments": []
}
```

A second shape, shortened: a paraphrase A/B that one round cannot decide, so pooling is registered up front.

```json
{
  "prereg_id": "paraphrase-v2-pooled-effect",
  "question": "Does paraphrasing the question change the answer rate, as it ships?",
  "unit_of_inference": "the QUESTION (qid), pooled at unit level across rounds of the same bank and grader version",
  "preconditions": ["item-set Jaccard within pairs >= 0.95, else NOT GRADED"],
  "min_n": {"units": 1900},
  "bars": [{"id": "b1", "what": "CI on the paired delta lies inside +/-2 points", "kind": "no-harm"}],
  "decision_rule": {"MEASURING": "pooled units < 1900 (one round gives about 840; report the running CI, no word)"}
}
```

### Amendments

An amendment appends; it never edits a field in place. Each one carries `id`, `at`, `by`, `before_data` (a
sentence proving whether counted data existed yet), `reason` and `what`. If data already existed, the amendment may
only fix reporting (for example, how a VOID is labelled). It may not move a bar, a minimum n or the decision rule
toward the observed numbers. When a review finds that the design itself was wrong (wrong unit, wrong path graded),
write v2 of the prereg, mark v1 superseded, and treat earlier rows as a different instrument.

## The `verdict()` contract

A lane's verdict is a pure function of the rows in the round's window:

```python
def verdict(rows, *, pause_share=None) -> dict:
    # returns {"verdict": WORD, "n": units_counted, "units": units_seen, "why": "...", "invalid": [...]}
```

- WORD comes from one fixed vocabulary, kept in one place in code (`gym_kit.WORDS`, or the project's own list):
  PASS, FAIL, VOID, MEASURING, MARGINAL, SATURATED, STARVED, plus OFF-SHIFT where lanes run on a schedule. A
  lane-internal word like INVALID is returned as VOID with n = 0, so the round launcher never rewords it into
  STARVED or MEASURING.
- Rows from cold-judge cycles, impure-composer cycles or corpus-drift cycles are excluded from the decision but stay
  in the series, stamped with why.
- A verdict that fails on ANY violation can't tell a known defect from a regression. Partition violations into
  pre-declared findings and NEW ones, sum over all rows (not `rows[-1]`), and print every group, not `top[:4]`.
- The selftest proves every word is reachable: plant rows that should produce PASS, FAIL, VOID, MEASURING and STARVED,
  and assert each one. Add one plant per control (a cold judge, an impure composer, a broken grader) and assert
  each produces VOID.

## Statistics recipes

`scripts/gym_kit.py` implements these with the standard library only.

**Paired bootstrap by unit.** Collect `(unit_id, a, b)` per paired observation. Resample distinct unit ids with
replacement and average each unit's mean delta. Report the mean and the 2.5/97.5 percentiles. Never resample cycles
or raw rows when units repeat.

**Sign test / McNemar on discordant pairs.** For binary outcomes, count units where only B was right (b) and only A
was right (c). The exact two-sided binomial p on b of (b + c) is the McNemar exact test. A practical ship rule used
before: at least 20 discordant pairs and b >= 2c.

**Median and fraction-under-bar.** For ratios such as model MAE over null MAE: report the median, the fraction of
cycles under the bar, and the same two numbers for the final quarter. "Sustained" means the final quarter (or the
final N cycles) holds, not that the overall mean dips under.

**Non-inferiority.** "Did the flip hurt anything?" Each scene's post-flip mean must be >= the pre-flip mean minus 1 sd
of the pre-flip per-cycle noise. When the pre sd is 0, use the metric's quantisation step as the margin.

**Power.** With CI half-width h at n units, a half-width of b needs about `n * (h / b) ** 2` units. Use it to decide
whether to pool rounds, and pre-register the pooling before the next round runs.

**Pooling across rounds.** Pool only rounds with the same instrument (same bank, world, grader version, length class
where the metric depends on length). Pool at the unit level, not by averaging round means.

## Calibrated judges, in one paragraph

To use an LLM as a verifier or judge: compute its probability with grammar-constrained decoding and logprobs; measure
AUC, raw ECE and a mismatch-control gap on items with known truth, judged by a model other than the answerer; fit
Platt (or isotonic) on a holdout. Pre-register bars (for example AUC >= 0.90, gap >= 0.5, raw ECE <= 0.10). If the
raw ECE fails but the calibrated map passes, the license is "this judge through this map only", and the lane keeps
printing the raw number. Compare a new judge to the incumbent on the same pairs, with a parity bar decided first
(one judge swap failed at AUC 0.878 vs the incumbent's 0.931, against a parity bar of 0.911).
