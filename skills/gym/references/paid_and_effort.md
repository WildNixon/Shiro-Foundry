# Paid gyms, tournaments and the effort axis

## Money discipline

Use this whenever an iteration costs real money (cloud LLM calls, image or video generation, paid APIs).

- **Quote before you spend.** Estimate every call before making it (a `check_cost` / `estimate()` step), and offer a
  `--dry` run that prints the plan and the estimate with zero calls.
- **Hard cap on the whole run** (`--cap`), on top of per-call budgets and the account's daily cap. The provider may
  refuse the last unit of balance, so cap one unit below what is left.
- **Ledger every charge** in integer micro-dollars, append-only. One short generated line costs about 1,680
  micro-dollars; in cents it would round to 0 and the cap would never trip. Derived totals are a cache rebuilt by
  replaying the ledger, never reset to zero.
- **Classify provider errors by type and text,** not only by status code. "Credit balance too low" arrives as a 400
  invalid_request; billing errors as 403; bad key 401; rate limit 429/529 with retry-after. Each needs a different
  reaction.
- **On a refusal or crash, still write the results file.** Money spent with no record of what it bought is the worst
  outcome.
- **No plateau stop rule.** A paid loop stops at the cap, not "when it stops improving", because a plateau can spend
  without limit.
- **Unknown model ids bill at the highest rate and get flagged.** Price tables are matched by longest prefix.

## Tournaments (paid regeneration)

- Incumbent vs challenger on the same brief. Pin the seed where the API allows it.
- Re-roll only a genuine failure (a dead render, a refused generation), never "I'd like a better one".
- **Incumbent protection is mandatory** when regenerating a library that already works: the challenger has to beat
  the incumbent on the grader, as shipped (post-bake), by the pre-declared margin.
- A losing challenger is discarded. Keep its file on disk with its score in the filename, as evidence.
- Owner-visible taste calls (blind reads) come after the pure-code gates, and only for candidates that already passed
  them.

## The effort axis (accuracy per unit of effort)

Use this when the question is "is the bigger, slower or cloud arm worth it?", not just "is it more accurate?".

- **One unit for every arm.** `eu` = an integer micro-dollar equivalent. Cloud is the metered price. Local is tokens
  x a probed ms/token (measured at rest, per model) converted at a fixed rate per model-second.
- **Tokens, never wall clock.** The same local work measured 85 ms or 3.6 s depending on whether another lane had
  evicted the model. Wall clock measures contention.
- **The reward is paired.** For each unit: `d_acc - RATE * d_eu / 1000`, with RATE pre-registered. Label each pair:
  paid (more effort, more accuracy), wasted (more effort, no gain), saved (less effort, same accuracy), lost (less
  effort, lost accuracy), even, floor.
- **Block the reward hack.** A shorter answer that dropped content is "lost", never "saved". A canned or code-only arm
  can never earn "saved".
- **Gate-only lanes.** If effort's share of the reward falls outside a pre-registered window for a lane (it dominates,
  or it is a rounding error), that lane prints eu and labels but never a verdict on the effort axis.
- **Warm-up before verdicts.** History-paired lanes need a minimum number of counted rows before the first
  informative block.

## Model or weights swap evaluations

When the question is "should model X replace model Y in seat Z?":

- Pre-register a parity bar on the seat's own metric, measured on the same items as the incumbent (judge seat: AUC,
  ECE, mismatch gap, plus whether the seat's calibration procedure still produces a usable operating point).
- Secondary bars: VRAM, p50 latency at realistic prompt length, and anything the swap was supposed to buy (one base
  model shared across seats, fewer devices). If the reason for the swap disappears, stop there.
- Run every lane that shares the weights. A voice adapter that fixed the voice rails also cost the router 8-11
  points, because the router shares those weights. "Dropping the old adapter is not free" was learned by measuring
  it, not by assuming it.
- For a speech model, measure on the real input mix: on real radio captures most of the audio was music, and the
  better ASR model transcribed the lyrics, so the swap needed a speech/music gate first.
- The verdict vocabulary still applies: a swap candidate that wins on one axis and fails a guard is "SWAP-CANDIDATE,
  not a drop-in", with the missing piece named.
