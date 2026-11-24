# Pitfall catalogue

Every entry is a measured incident from one long-running multi-agent project (about four months of gyms and
rounds), written as the rule plus what broke. The numbers are real; the project's own names are left out.
Use it as an audit pass: for each family, ask whether the gym in front of you could be making that mistake right
now.

Contents: 1 Grader · 2 Nulls and baselines · 3 Statistics · 4 Provenance, time and data · 5 Code and instrument
hygiene · 6 Search, tuners and ladders · 7 Judges and LLM lanes · 8 Long-running loops and control plane ·
9 Visual and web gyms

---

## 1. Grader

- **Free knob.** Can the optimiser raise the score without improving the artifact? viewBox padding was driven to zero
  until `fill` charged for it. Shrinking a mascot's motion would have "fixed" joint gaps that were really hair edges
  moving, so that candidate was rejected. Price the knob, or remove it.
- **Degenerate winner.** A dead clip is perfectly stable, looped and legible; eject-everyone scores catch 1.0; a
  shorter answer that dropped content looks "cheaper". Veto with a floor, and pair any catch rate with its false-
  positive rate (one detector lane's verdict is PASS only when red-team catch AND blue-team fp both hold).
- **Grade what ships.** Raw challengers vs baked incumbents gave 27 "upgrades", 9 real, and one shipped below floor.
  Grade post-palette, post-bake, post-quantise, through the real rails at the real scope (an open-book lane first
  graded a retrieval path the product's chat never runs).
- **Builder and grader share a definition.** A second set of portraits "passed" because the builder and the grader
  used the same garment flood fill; an eye check caught it. Define the target independently.
- **Grading a dead render.** The first web-design run graded the browser's error page after the preview server died.
  Serve the artifact from the gym itself and add a dead-render veto.
- **Charging the wrong party.** A reader was billed for the publisher's mint cost, which produced a "raise the cache
  lifetime" recommendation that had to be withdrawn. Check where each cost actually lands.
- **Snapshot context.** Groundedness graded against an HTTP snapshot (20 numbers) instead of the real prompt (76)
  made 4 of 5 "fabrications" false. Grade against the agent's true context, built in an isolated subprocess if
  imports collide.
- **Sample-count-dependent metric.** Loop-vs-median scored the same physical gap 98.4 at 4 frames and 0.0 at 8. If
  the score moves when only n changes, it measures n.
- **Comfortable case.** A clash grader that modelled only desktop scored 0.00 while live showed 8 px overlap at 1x.
  Grade the smallest screen, weakest frame, worst angle.
- **Tokeniser false positives.** A hallucination rail's tokeniser flagged good English, and a `\bmae\b` metric-leak
  rule fired on the name "Mae". Run every rail over a benign corpus and read what it flags.
- **Grader artifacts that look like findings.** One "hallucination" was a name the scene itself listed as a valid
  reference; one null "passed" through the phrase "no need", not through the weather. Before reporting a finding,
  read three of the flagged rows by hand.
- **Absent classes faked as 0.0.** `max(1, n)` denominators made a red-only corpus "measure" fp_rate 0.0. Emit only
  the keys whose class is present.
- **One quantity, one unit.** Synthetic telemetry gave a slip reading as "21 rpm" while every authored source said
  percent. Synthetic ranges come from the authored canon, never from chart convenience.
- **Prompt rules get parroted.** A rule quoted "based on the data provided" and the model said exactly that.
  Describe behaviour; don't supply quotable phrases.
- **Generative prompts describe motion, never a pose.** A pose prompt returns the same still N times (motion 11/100).
- **Honest refusals score well.** "I don't have that" is correct behaviour; only fabrication, leaks and false claims
  of action cost points. A past-tense claim of an action the agent cannot take is worse than an offer, because an
  offer can be declined. The subject of the verb is the signal ("you should replace" is advice, "I replaced" is a
  claim).

## 2. Nulls and baselines

- **Weak null.** A navigation lane vs free-flow looked like ratio 0.399; vs the strong per-hour null it was ~1.0.
  Use the strongest baseline that knows nothing the agent is meant to learn.
- **Null = supremum of the agent's family.** One threshold ladder's null was the best fixed threshold chosen by
  argmax on the same objective (0.9550 vs agent 0.9551): 317 cycles comparing a number to itself.
- **Candidate built from the null.** A weather replay of `persistence + noise` can never beat persistence, and a
  hard-coded sigma replayed on every row made 107/107 cycles restate one constant. Anchor replays on the actual.
- **Stand-ins for the graded thing.** A synthetic season and a replay-sigma path were how the weather gym lied
  twice. Below N real rows, the lane says MEASURING.
- **Tier labels lie; KIND is the honest split.** One item family (77% of the "tier 2" items) answered from one DB
  row; another leaked its answer into the title (the null solved 15/18). Retier by earnable vs lookup, and drop any
  generated item the grading null can solve.
- **Retrieval-augmented null.** When testing an open-book arm, add a null that gets the same retrieval. Beating only
  the plain null means retrieval did the work: ship retrieval, not the arm.
- **Easy/hard splits.** Splitting easy and hard across schedules (day vs night) is only valid for disjoint corpora
  graded independently. A within-cycle paired control (nominal vs fault, null vs agent) must stay in the same cycle,
  or the delta it measures is destroyed.
- **100% win on ties.** The navigation lane reported "win 100%" while its prediction equalled free-flow exactly (no
  trusted cells). Report ties separately.

## 3. Statistics

- **Mean of a heavy-tailed ratio.** Means showed three rounds of improvement (0.997 to 0.912); medians were flat
  (1.011, 0.959, 0.946, then 0.998 on the long round). Use the median plus fraction-under-bar.
- **Short rounds can't carry a trend.** A 4.2 h leg produced both a "gain" and a "format-fail doubled" regression;
  both vanished at n=127.
- **Pooled bar, single-cycle n.** A per-cycle ECE at n=36 has a perfect-scorer floor near 0.16, so a 0.10 bar set on
  598 pooled pairs printed NOT EARNED forever. Compare like n with like n.
- **Endpoint estimator.** `pts[0]` vs `pts[-1]` read cold-start fossils and single noisy samples (39.5 to 19.0 with
  zero changes). Open and close with windowed medians and print the estimator.
- **Unpaired confounded by set composition.** Adjacent-cycle question overlap was Jaccard 0.156, so the unpaired gap
  (+5.02) and paired gap (-1.91) had opposite signs on the same rows. Pair by construction (same seeded set for both
  arms of a pair) and check Jaccard >= 0.95 as a precondition.
- **Stratifying on a mediator.** Longer paraphrased prompts timed out the main model and a bare `except` handed them
  to a weaker one. Model was a mediator, so conditioning on it biased the estimate.
- **"Two rounds agree" can share a confounder.** Two rounds that agreed did so because both had the same
  assignment bias.
- **Zero-sd baseline.** "Within 1 sd of pre" fails any movement when pre-sd is 0. The honest margin there is the
  metric's quantisation.
- **Pool over the unit.** A per-exam median (48.4) understated a pooled-over-questions 59.2, because exam sizes vary.
- **Bootstrap over the wrong unit.** Resampling cycles that re-ask one question set measures the letter scramble.
  Resample distinct items.
- **Lifetime averages flatten learning.** Chart a rolling window beside any cumulative number.
- **Deterministic bands.** A seeded benchmark is flat by construction; label it a stability band where "movement is a
  regression, not learning". A ladder replaying `seed=99` every round re-measured one number (-1.7, bit-identical)
  for ~37 rounds. A fail there carries no information.
- **Misses folded into a mean.** "Mean lead 28.1 s" counted 447 misses as 0.0 s. Record a miss as `None` plus
  `missed=True`, average detections only, and give miss rate its own KPI.
- **Pool before you narrate, and state power.** The paraphrase effect read +1.66, then -0.48; pooled it was +0.95
  [-1.51, +3.42]. A ±2 band needed ~1,900 units, so pooling across rounds was pre-registered instead of narrating
  each one.

## 4. Provenance, time and data

- **Hindsight.** Weather "bets" targeted today, issued today, so the official comparison was nearly a nowcast; skill
  +0.99 was hindsight. A row is gradeable only if `made < date`, and the target is strictly after today.
- **Dedup that rewrites bets.** Keyed on (date, var), each later run replaced the earlier, so the best-informed rerun
  always won and lead-time history never existed. Bets freeze at first write; key on (date, var, horizon).
- **Off-by-one horizons.** `h = (date - made) + 1`, so h=1 was same-day and 64% of rows. Check what a pooled metric
  is pooling.
- **Survivor bias.** Pre-fix long-lead rows existed only on days the system was down. Exclude and count them.
- **Provenance absent or optimistic.** `src` missing read as None; a fault tag defaulted to `src:"live"` on 512
  emulator records. A provenance field must be present and must never default to the strongest claim.
- **Learning from your own output.** 34% of the alert corpus was the detector's own "early warning" rows.
- **Events without non-events.** An adjustment log only contains conditions that provoked a change. Sample state on
  a fixed clock (not "when something changed", which rebuilds the bias), with `settled` and `since_adjust_s`.
- **Repeated frames are not samples.** 40% of a baseline log was a frozen feed re-logged every 60 s (sd 0 on 12/17
  systems).
- **Gym traffic in the baseline.** A gym wrote the production feed the agent trains on; a resolved-phase sample
  polluted a baseline that a static aggregate could never outgrow. Sandbox the gym, gate samples on health, and cap
  the window so a bad patch can be outgrown.
- **A filter that rejects all gym rows.** `src == "user"` dropped every gym row, so "win 100%" was identity.
- **Renamed keys.** Composite `id::system` keys broke a bare-string match: every real fire counted as a false alarm
  for 4 days. When numbers jump, diff the key schema first.
- **Key presence lies.** 2,558 rows had the `actual_s` key, all null. Test the value.
- **Gym writes, live reads.** A simulator took over the live outbox when the real feed dropped and raised a
  user-facing alert about a device it wasn't reading. Vocabulary the real path cannot produce is a free provenance
  check.

## 5. Code and instrument hygiene

- **Falsy zero.** `(b.get("sd") or 1)` failed 12 perfectly constant baselines. Use `is None`.
- **`SystemExit` is not an `Exception`.** An `except Exception` guard would not have caught it and the round would
  have died at open.
- **Bare `except: continue`** silently reassigned an arm's questions to another model.
- **`points[0]` carries an obsolete schema.** Series gain keys over time. Inspect the last point or the union of
  keys.
- **Double scaling.** A tile read "5941%": the value was already a percentage. Absurd output is a gift; a plausible
  double-scale is the dangerous one.
- **Clock strings.** `t` was "HH:MM"; segment on epoch `ts`.
- **Windows default encoding.** `open()` defaults to cp1252 and mojibaked a ledger. Always `encoding="utf-8"`.
- **mtime-only cache keys.** Two writes within one filesystem tick (~0.5-1 ms) share an mtime, so a reader served a
  stale judge calibration 8/8 times. Key on `(st_mtime_ns, st_size)` and re-read while the file is under ~2 s old.
- **Env read at import.** Knob hot-reload can't reach a module that read env at import; a running process can
  predate its own fix; a build stamp may show the boot hash. A code fix needs a restart and proof the new code is the
  one running.
- **Flag-arm tests via `os.environ` only** became vacuous once the override file carried the flag. Pin the override
  file to a temp copy, pop the env var, reset any TTL cache, and assert the arm's state.
- **Test doubles must be reachable through every branch at every flag value.** A fake LLM answered but reported
  `healthy() == False`; when a flag routed one lane to the local branch, every line was the canned floor for a whole
  round. Its selftest now asserts reachability under both flag values.
- **Tests writing live files.** A smoke row landed in the live tuning journal. Point test writes at temp copies and
  fingerprint live files before and after.
- **A comment can be why nobody looked.** A docstring said a file "only changes on a full restart"; it changed twice
  in two minutes.
- **A non-collision proves nothing.** For timing races, pin the condition (`os.utime`) instead of hoping to hit it.
- **Read the product for the key name** before writing a check (one module said `feed`, another `feed_state`).
- **Harness picks the model from a knob, not `--model`.** A new judge arm graded all-HELD because the hold-out used
  the configured judge. Verify which model actually answered.
- **Shell traps.** `echo "$(date) $?"` logs 0 (the substitution resets `$?`). Reporters must `str()` what they
  concatenate, or a TypeError hides the real failure.

## 6. Search, tuners and ladders

- **Dead knobs.** For every tunable, ask: who calls `propose()`, does the metric's producer exist, and can the metric
  feel the knob? Four registered knobs failed one of these. A metric frozen into rows at write time can never re-score
  under a new knob value.
- **A/B pressure must fire.** A twin that never false-alarms at the default noise made the objective monotone, so
  the knob rode the floor. Grade across a noise band to expose the interior optimum.
- **Flapping.** A knob flipped 3.0 to 3.5 fourteen times in a night. Add a deadband.
- **Inert ranges.** A clamp `max(min_trips, 5)` made [2, 5) inert; registry bounds now match the reachable range.
- **Unreachable targets.** A sub-score pinned across two full plateau runs means the parameterisation cannot reach
  the goal (a linear offset cannot narrow a 73 degree ramp to 36). Before diagnosing a stuck gym, compare the
  achievable range with the pass mark (oracle k cleared the null by +1.0-1.8 vs a margin of 2.0, so nothing could
  ever promote).
- **Ladder seeding.** Tiers seeded from their index re-roll when reordered (one rung read 2.375 at index 1 and 13.281
  at index 2). `verify()` is one deterministic draw; repeating it is not confirmation. Use `robust()` over 25 seed
  bases, and read which rungs fail, not only the fraction. A rung failing a third of bases cannot order anything.
- **Data-fed rungs expire.** Tier ordering measured on a live corpus broke as the corpus grew. Re-verify per round.
- **State outlives tiers.** Dropping a rung left `tier=3` with 3 rungs defined. Clamp, say why, and reset progress.
- **CEILING for both mastery and failure.** The report gave "topped out" and "317 cycles, zero promotions" the same
  badge. Distinguish TOPPED OUT, CEILING and STUCK.
- **Margin 0 on a noisy delta** promotes on noise about 1 in 8 triples. Set the margin above the measured noise band.
- **Retire a converged control deliberately.** When an in-round control's delta converges (0.091, 0.018, 0.001), say
  so and retire it as a recorded change.
- **Owner calls are grader revisions.** "Mix and matching looks weird" became a new sub-score, recorded as its own
  row. The kept state was re-scored under the new grader (95.67 to 92.08) before any candidate was judged.

## 7. Judges and LLM lanes

- **Earn the judge.** Calibrate it on known truth: AUC, ECE, a mismatch-control gap, a holdout calibration map. One
  model (p(yes) = 0.66 on wrong answers) was a rubber stamp. If the raw bar fails, a consumer may use only the
  calibrated map, and the lane keeps reporting raw honestly.
- **Scope verifiers to reasoning content.** A verifier cannot verify a DB fact (AUC 0.716 on codes). An apparent ECE
  "drift" was really composition: DB-fact rows tripled in the pool.
- **Cross-model, never self-verify.** Cycles skip rather than swap in an unmeasured model.
- **Judge-cold cycles.** An absent judge fakes a good number in one lane (all held, so fp 0.0) and a bad one in
  another (code-only catch 0.50). Exclude cold cycles from the verdict but keep them, stamped, as the code-only floor.
- **Mid-round refits move the bar.** A judge threshold drifted 0.81 to 0.46 after a cold cycle triggered a refit.
  Refit only from an earned calibration.
- **An empty calibration is a contract.** After an identity change invalidated the old calibration, the judge read
  COLD on every cycle. Abstaining was correct.
- **Wake the model.** A cold server silently zeroed both arms across 227 questions. The signature: 0.0 plus zero
  discordant pairs. Check `healthy()` and that calls were actually made.
- **Verify the weights.** A server can serve a fallback weights file under the expected model's name. Read the
  served model path at the first and last ask; anything else is composer impurity, and the round is VOID.
- **Contention confounds time.** The same work went 85 ms to 3.6 s when another lane evicted the model. Measure
  effort in tokens, not wall clock.
- **Never run an A/B beside a live round** on a shared model slot.

## 8. Long-running loops and control plane

(The operational detail is in `rounds.md`.)

- A stale `.stop` file silently killed a lane for two rounds; it printed "done: 0 cycles" and returned success. A
  preflight now lists every stop file, and anything that writes a kill switch owns deleting it.
- "Is a round running?" means content freshness or a live pidfile, never file presence.
- A single fail-open 3 s HTTP probe decided a hard kill and killed two rounds. When state is unknown, hold; a
  destructive decision needs local proof and two readings.
- A grader's stop probe drained a live day series. Destructive probes fire only at targets the gym created.
- A smoke-scale test validates lifecycle mechanics but not timing: a 16-minute stagger, 15-minute print gaps and a
  deadline anchored after the stagger all survived smokes.
- Reset lanes destroy the prior round's evidence. Archive per round with a manifest (reset vs accumulates, sha), and
  certify past rounds from the archive.
- Deploying or restarting during a round cost a missed fault replay and judge-cold cycles.
- Paired schedule gates must partition the variable. "Red needs >= 8 h, blue needs <= 6 h" left a 6-8 h dead zone
  that a real round fell into.

## 9. Visual and web gyms

- Find the real defect source before tuning: the mascot's animation looked broken because of how the parts were
  *cut*, not the keyframes (fragments 15 to 3 after a re-cut).
- Verify the model against the real renderer: geometry scored perfectly while a CSS `transform-origin` bug made the
  live orbit non-circular.
- Measure layout positions (offsetTop chain), not `getBoundingClientRect`, while an element may be mid-entrance-
  transform.
- Normalise CRLF to LF before any 3-way merge. Areas that pass alone can fail merged; re-gate the merged tree.
- A "pause motion" control must turn OFF the no-preference rules, not just turn ON the reduce rules.
- Headless Chrome on Windows: `--window-size` can give 500x739; set metrics through CDP. Run perf A/Bs in a quiet
  window with no other Chrome load, and clean up orphaned Chrome processes (job object plus a busy flag).
- When the user reports a visual defect twice, stop eyeballing and build the grader.
