---
name: gym
description: Build, run, grade or audit a "gym" - a measured improvement loop with a pure-code grader, a null to beat, vetoes and controls, a pre-registered bar, a search / tournament / paired A-B, a chart, and an honest verdict word (PASS, MARGINAL, FAIL, MEASURING, VOID). Use it whenever the user says gym, lane or round, "run X through a gym", "loop till it stops improving", "grade this change / round / model", wants to A/B a flag, prompt, model, LoRA or judge, tune a knob, pre-register an eval, or asks whether a score, grader, benchmark or "it improved" claim can be trusted - even if the word gym never appears. Also the checklist for auditing an existing grader and for grading a long-running round from its series files.
---

# The Gym

A gym turns "make it better" into a measurement you can lose:

    population -> grader (pure code) + vetoes + controls -> null to beat -> pre-registered bar
      -> loop (search | paired A/B | tournament | live cycles) -> stop rule -> chart -> verdict word -> honest grade

Two stances carry everything below.

- **The grader is the product.** Search is cheap. A grader that can be gamed, cannot fail, or scores the wrong
  population turns every later hour into a confident wrong answer. In every gym that worked, most of the effort went
  into the grader and its controls, not the loop.
- **An honest NO is a successful run.** "Change nothing" (one search gym: 1,228 evaluations, delta 0.0000), "NOT
  KEEP" (a fine-tuned adapter), "loses to persistence" (a weather forecaster) are all results. Having built or paid
  for a challenger is never a reason to ship it.

Distilled from 60-odd gym scripts and about 77 graded rounds on one long-running multi-agent project; the incidents
quoted below are real, with their identifiers removed. A project that already has its own gym machinery (series
writers, a round launcher, a verdict vocabulary, staging conventions) reuses it. Elsewhere, `scripts/gym_kit.py`
(stdlib only) supplies the series, search, paired statistics and chart parts.

## Which job is this?

| The ask | Mode | Start at |
|---|---|---|
| "make X better", "tune it", "loop till it plateaus" | **Build** a gym | the Build sequence below |
| "is the new flag / model / prompt / LoRA / judge better?" | **Paired A/B** with a prereg | steps 1-6, then `references/prereg_and_verdicts.md` |
| "grade last night's round", "what did round 12 say?" | **Grade a round** that already ran | `references/rounds.md`, section *Grading a round* |
| "can we trust this score / chart / grader?" | **Audit** | the Audit checklist below, then `references/pitfalls.md` |

## In a Shiro Foundry project

The method below is the same everywhere; a Foundry project adds who writes what, and where.

- The gym's folders live under the profile's `paths.gym`: `series/`, `prereg/`, `contracts/`, `charts/`, `grades/`
  and `lanes/`.
- The builder writes the contract `gym/contracts/<lane>-artifacts.md` before any code.
- An independent grader (never the builder, never the manager who directed the build) writes the prereg and the
  lane before any data exists, and pins the contract by sha256.
- Only the grader edits the paths listed in the profile's `measure.grader_owned`.
- A milestone is done only when its lane says PASS on a counted run. A run that did not pass is filed as a numbered
  failure with a plan.
- Run outcomes go to the contract owner's amendment, never into shared notes a grader reads before pinning.
- The board (`board.py`) reads lane facts from `gym/series/*.json`, never from a typed claim.
- `gym_init.py init` scaffolds a starter gym (`lane add <lane>` one more lane, `check` reads it as the tools will): a runner, one
  example lane, a prereg template marked not registered and a contract draft. It decides nothing until a grader writes the measure.
- The scaffolded runner is `gym/run.py list | selftest | dev <lane> | counted <lane>`; `counted` refuses a dirty tree and a
  prereg that is still a template, and only the manager runs it. A counted run is published as VOID when nothing shows it
  sampled the commit it names: the tree is not clean after the collect, or HEAD moved during it. Its exit code: 0 PASS, 1
  any other verdict word, 2 a refusal, 3 the runner itself failed or a lane called `sys.exit` (no verdict: never read it as
  a FAIL), 130 an interrupt.

## The Build sequence

1. **Name the thing graded, where it ships, and the population that already exists.** Grade what ships:
   post-bake, post-quantise, through the real rails, at the real scope, with the agent's true context. Grading raw
   challengers against baked incumbents once reported 27 upgrades where 9 were real. Calibrate on something already
   shipped (the live config, the incumbent, the current sheets). If no population exists, the first deliverable is
   a baseline capture, not a search.

2. **Pick the unit of inference and the null before writing the grader.**
   - The *unit* is whatever is independently drawn: the question, the trip, the scene. It is not the cycle. A
     bootstrap over cycles that re-ask the same questions only measures the answer-letter shuffle. One lane read
     CI [16.67, 16.67] at cycle level and [-16.0, 46.3] at question level.
   - The *null* is the strongest dumb baseline that knows nothing the agent is supposed to learn: persistence for
     a forecast, a global per-hour median for ETAs, lexical overlap or a DB lookup for an exam, a fixed threshold
     for a detector. A weak null makes everything look like skill: a free-flow baseline made a navigation lane look
     2.4x better than the strong null did. The null must never be the argmax of the agent's own parameter family,
     because that is a supremum the agent can only tie (one threshold ladder compared a number to itself for 317
     cycles). And a candidate built from the null, like a replay of `persistence + noise`, can never beat it.
   - Split items by KIND (earnable by reasoning vs answerable by lookup), not by authored tier labels. A model
     should not be graded on memorising a DB, and a verifier cannot verify a DB fact. Serve the DB.
   - Screen every generated item with the null that grades it, and drop items the null solves. The "hard" tier was
     once 77% single-row lookups.

3. **Write the grader in pure code.** It should be deterministic, cost $0 and take milliseconds, because a search
   calls it thousands of times. Return `(total, parts)` so each part charts on its own. Give the most weight to the
   part that matches the reported defect.
   - Define the target independently of the builder. A grader that uses the builder's own definition (the same
     flood fill, the same parser) verifies its own misses.
   - Grade LLM output through a forced parse (a JSON-schema enum or grammar), never free text. A capped free-text
     exam graded formatting as knowledge: 14.7% before the schema, 50-62% after.
   - When a case cannot be verified, SKIP it and count the skip. Guessing chases phantoms.
   - Honest refusals score well. Only fabrication, leaks and false claims of action cost points.

4. **Make the grader prove it can fail: vetoes, plants and controls.**
   - **Veto the degenerate winner.** Ask what the cheapest worthless artifact is that still scores well: a dead
     clip, an empty answer, eject-everyone (catch rate 1.0), a shorter answer that dropped content. Cap it to a
     floor. Weights alone will not catch it.
   - **Plant frauds.** Build candidates that cheat in specific known ways. Each must be caught by the check aimed at
     it, and one honest control must clear every check. A detector that fails everything sorts frauds perfectly
     and is worthless.
   - **Add controls that must fail.** A shuffled truth or a key rotated one letter should drop a skilled answerer
     to chance or below. The base graded against itself should score parity. A metric that ranks a control wrong is
     measuring noise: print it, but keep it out of the score.
   - **Self-check every cycle.** The true key must score 100 and an all-wrong vector 0 through the one grading
     function. Otherwise the cycle is VOID.

5. **Calibrate on the population.** Set floors from its distribution ("worse than anything we ship"), not from
   taste. Check that it is really one population: one floor over two families of clips (one scoring 78-88, the
   other 92-100) would have re-rolled every clip of the lower family. Score the extremes of the range. Record the
   before-bar; it goes on every chart as a dashed line.

6. **Pre-register anything that will decide a ship, a flag flip or a keep.** Do it before the first counted data
   exists. Write the hypothesis, unit, statistic, minimum n, bar, controls with their void conditions, any
   preconditions, and the rule that maps results to verdict words. Put it in a file with a timestamp and a
   "written before" sentence. Change it only by a dated amendment that says whether data existed yet. Never move a
   bar after seeing numbers. The template is in `references/prereg_and_verdicts.md`.

7. **Choose the loop shape by what one iteration costs.**
   - *Free and parameterised*: multi-restart compass search. Restart 0 is the shipped config; jittered restarts
     show you are not just sitting in the seed's basin. Use derivative-free search, because real objectives have
     cliffs.
   - *A discrete change* (flag, model, prompt, LoRA, judge): **paired A/B**. Both arms see the same items in the
     same cycle (same seed, same question set, asserted identical). Make item-set overlap across arms (Jaccard
     >= 0.95) a precondition the verdict checks. Arms that look paired but aren't are a common hidden confounder.
     When the incumbent is itself an earlier change (an old LoRA, an old flag), add the plain base as a third arm,
     so you also learn what the incumbent is worth. Dropping it may cost something elsewhere.
   - *A live agent*: time-budgeted cycles through the agent's real seams, letting its own learners run, with a
     periodic nominal-control cycle.
   - *Paid iterations*: a tournament (incumbent vs challenger, seed-pinned, hard dollar cap; a losing challenger is
     discarded). See `references/paid_and_effort.md`.

8. **Match the stop rule to the loop.** Free loops stop on a plateau (`patience` restarts without gaining `eps`).
   Live loops use a wall-clock deadline plus a `.stop` sentinel and a `.done` marker. Paid loops stop at a hard
   dollar cap, never a plateau, because a plateau spends without limit. On a refusal or crash, unwind cleanly and
   still write the results file.

9. **Persist, resume, archive.** Keep a series file `{"points": [...]}` and write it atomically (tmp + replace) with
   `encoding="utf-8"`. Every point carries an epoch `ts`, the grader version, and the world/bank/epoch tag. Series
   from different worlds, banks, grader versions or round lengths never pool. If something will reset the series,
   archive the old file with its sha first, or the evidence for a past result disappears.

10. **Chart every cycle.** Draw the before-bar dashed for the whole run. KPIs: the headline, its before value, the
    gain, n on the unit of inference, the evaluation count, and the miss/void/skip counts. Put a rolling window
    beside any cumulative mean. In the notes, write the weights, the gates, and what would count as a *regression*
    rather than learning.

11. **Return a verdict word, then write the honest grade** (next two sections).

## Verdict words

| Word | Meaning |
|---|---|
| PASS | the bar is met under the prereg rule at n >= min n, and the controls held |
| MARGINAL | inside the noise band, or the CI straddles the bar |
| FAIL | the bar is missed with enough n, and the controls held (so the miss is real) |
| MEASURING | too few units so far. A short run never gets PASS or FAIL |
| STARVED | too few units, and the rows show why (paused, contention, cold model) |
| VOID | the instrument broke: a control failed, the judge was cold, the model under test was the wrong one, or the grader self-check failed. Report n = 0 so nothing later rewords it as a starve |
| SATURATED | pinned at the maximum. The test is too easy; the next step is a harder grader, not more hours |

When the judge is absent, the calibration is empty or stale, or the model is cold, the gym abstains (VOID or
MEASURING). Voting on a stale calibration is worse than not voting.

## The honest grade

Write the final grade as:
1. the verdict word;
2. the headline against the before-bar, with CI and n on the unit of inference;
3. what did not improve, and why;
4. the ceiling (a metric pinned at its max is a measurement ceiling, not success);
5. which fixes were actually *exercised* (a fix whose trigger never fired is not proven);
6. the evidence trail (series, samples, rejected candidates kept on disk, prereg);
7. the rollback.

These habits keep a claim honest:
- **Median and fraction-under-bar for heavy-tailed ratios, never the mean.** Three short rounds of "steady
  improvement" by mean were flat by median. "Sustained" means the final quarter or the final N cycles, not a mean
  pulled under the line by a few outliers.
- **Pool before you narrate.** Two "contradictory" rounds (+1.66 and -0.48) pooled to noise around a small
  positive.
- **Paired beats unpaired.** On identical rows, the unpaired estimator said +5.02 while the paired one said -1.91.
  The gap came from which questions each arm drew, not from skill.
- **Never stratify on a mediator**, for example the model that answered *because* the other one timed out.
- **State the power.** If the CI half-width at n is h, reaching a half-width of b needs about n x (h/b)^2 units.
  Say how many more units would decide the question.
- **Treat an unbeatable result as a test that isn't hard enough.** Check whether a deliberately dumb candidate
  scores the same as the shipped one on each part.
- **Confirm the thing under test actually ran** (calls made, model warm, branch reached). Green counters over a
  silent composer are the most expensive false pass.

## Audit checklist (for an existing grader, chart or claim)

Go in order. Each item is a real incident; the full catalogue is in `references/pitfalls.md`.

1. **Can it fail?** Feed it a planted bad candidate and an all-wrong key. Does any metric sit pinned (cv about 0)?
2. **Is the null too weak, or too strong** (built from the agent's own family, or the candidate built from it)?
3. **Is the population what ships, and is it one population?**
4. **When were the inputs recorded?** A "forecast" written on or after its target day is an observation. Bets
   freeze at first write, and dedup must not let a later, better-informed rerun replace them.
5. **Provenance.** Is every row tagged with its source (user/sim/gym/test)? Is the tag ever absent, or defaulting to
   the strongest claim? Is gym, sim or the detector's own output leaking into what it learns from?
6. **Free knob, degenerate winner, or an unreachable target?** A sub-score pinned across two plateau runs means the
   parameterisation can't reach the goal. Re-parameterise instead of adding restarts.
7. **Code traps:** falsy zero (`x or default`), renamed keys, checking that a key exists instead of its value,
   reading an obsolete schema from `points[0]`, double scaling, `except Exception` swallowing an arm.
8. **Right unit, right window, right estimator?** Window on `ts`, not the whole file. Use windowed medians, never
   `pts[0]` vs `pts[-1]`. Never compare one cycle's n against a bar set on a pooled n.
9. **Is the judge earned and warm?** Earned means AUC and calibration on known truth, a different model from the
   answerer, and a calibrated map. Warm means on the cycles that count; cold cycles are excluded but kept, stamped.
10. **Do the tests pin their flag world and leave live files untouched?**

## Blast radius (a grader is a destructive test)

- Gyms and tests read copies and write temp paths. Fingerprint the live files before and after to prove nothing
  changed.
- A destructive probe (stop, kill, reset) fires only at targets the gym itself created. Against live state, test
  only the refusal path.
- Pin the flag world. A test that inherits the operator's live flags grades the box, not the code.
- Never deploy, restart agents or churn models during a live round.
- Stage the change, get the owner's OK, then install with a `--rollback`. New behaviour goes behind a flag that
  defaults to 0, and the flag-0 path stays byte-identical to before.
- Whatever writes a kill switch also owns deleting it. A preflight lists stale stop files before hours are spent.

## Reference files

Read only the one the current job needs.

- `references/pitfalls.md`: the full catalogue of measured traps, grouped by family. Read it when auditing, or when
  a curve looks too good.
- `references/prereg_and_verdicts.md`: prereg JSON template, the amendment rule, the `verdict()` contract, and
  recipes for paired bootstrap, sign test, McNemar and power.
- `references/rounds.md`: long-running and multi-lane rounds (liveness, stop files, contention, archiving) and
  grading a round from its series files.
- `references/paid_and_effort.md`: money discipline, tournaments, the effort/cost axis, model-swap evaluations.
- `scripts/gym_kit.py`: stdlib helpers (`Series`, `compass_search`, `multi_restart`, `paired_bootstrap`,
  `sign_test`, `power_n`, `decide`, `write_chart`). Run `python gym_kit.py --selftest` first.
