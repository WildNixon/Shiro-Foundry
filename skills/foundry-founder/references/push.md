# Planning a push

A push is a dated stretch of rota slots that drives named milestones to a verdict, with its own usage budget, a freeze and a close. A project can run shift after shift without one; a push is for when the user wants a lot done inside a window (before a usage reset, a demo, a release).

You plan it. The user approves it. The managers run it.

## Before the draft

1. `founder.py audit` and `flow.py build`: what is ready to start, what waits on which decision, which lane has sat longest in one step. Read the managers' proposals too (`<date>-proposal-<topic>.md` under `paths.handoff`): a queue or roadmap change one asks for is settled before the draft.
2. `board.py brief --keys usage,decisions_open,failures_open`: the usage left before the reset, the open decisions, the failures that are still open from the last push. Old failures come before new milestones unless the user says otherwise.
3. If the profile names a shared resource: `rq.py status`, and how many seats it has. That number, not the headcount, limits how many builders can run work that needs it. Everything else is host-only work and can run beside it.
4. Draw the plan when it has more than a handful of blocks or an order that matters: `plan_flow.py new <push name> --title "…" --by "<your line>"`, fill in the stages, steps and what each needs first, `plan_flow.py selftest <name>`, `plan_flow.py build`. The user judges a chart faster than a list.

## Sizing

- **Slots:** count them from the start to the freeze, by the rota.
- **Usage:** the budget is the stop minus what is used now. Divide the last push's usage by its slots to get a rate; a plan that needs more than the budget is cut before it is shown, not during the push.
- **Headcount:** `crew_max` is the user's number. More crew costs usage roughly in proportion; idle sessions cost almost nothing, a waiting session that wakes every few minutes costs a lot.
- **Blocks:** each fits one slot, names the milestone it serves, and has a done-when that can be checked (a lane's verdict on a counted run, a merged commit with its review, a report on the main branch). The block that runs a counted gym carries the checkpoint.
- **Order:** measures first. For each milestone: the contract, then an independent grader's prereg and lane before any data, then the code, then the counted run. A push whose graders are hired on the last day ends with nothing counted.
- **Leave room:** the last slots are the freeze, the full sweep of every lane (`sweep.py run`: one lane at a time, each up to its `--max-per-lane`, 3 hours by default), and the close. Plan them as blocks.

## The draft

`founder.py push new <name>` writes the starter under `paths.handoff` (`<date>-<name>-draft.md`) with what the state already knows. Fill it in:

```
# <Name>: draft

Written <date time> by <your badge> on the user's "<the words that asked for it>".

## Window
- Start, freeze, close (each a date and time), and the slots between.
- Usage: used now, the stop, the budget, the last push's rate.
- The shared resource: seats, and how many builders may need it at once.

## Blocks
1. <Q1, title> (<slots>). What it does. Done when: <checkable>.
2. …

## Left out, and why
- <milestone>: waits on D<n> / carried / not in this budget.

## The user's calls before the first block
1. Settings: usage stop, headcount, heavy work pre-approved or not, the model for each title.
2. D<n>: <question> (recommended: …).
```

## Approval

- Show the user the draft's path, the chart, and the calls, in that order. Ask for the scope and for each call.
- Record the answers in the draft in the user's own words with the time. "Approve as drafted" covers the scope; it does not answer a decision the draft lists as open. Each of those is recorded when it is answered (`board.py decide answer`).
- A reading of yours ("the last push's settings carry over") is written as yours and asked at the next chance.

## Queueing

Only after the approval:

- **The shifts** go into the state's `queue`, one JSON file a shift, each with its `id`, `title`, `milestone`, `crew_max` (always: `queue add` refuses a shift without one, and `office.py hire` refuses on a shift without one), `heavy_ok` and `blocks` (each block a `title`, a `time` and a `done_when`; the counted block its `checkpoint`): `board.py queue add --file <shift>.json`, in order (`--at <n>` for a place; `queue list`, `queue move <id> <n>` and `queue rm <id> --note "..."` to check and correct). The `crew_max` and `heavy_ok` in each file are the user's, as the draft quotes them.
- **A limit of the shift already running**, changed by the approval: `board.py shift set --crew-max <n> --heavy-ok yes|no --by <badge id> --words "<the user's own words>"`. The manager runs it when one is on the clock.
- **The dated one-shot timers** (the freeze, the close) go into the manager's timer list (`<office>/manager-timers.json`; `office.py timers init` writes its recurring entries, a dated one is added by hand, and `office.py timers show` checks the shape). The manager creates the timers in its session.
- **The road graph** gets the push's order where it differs from the roadmap's (`flow.py graph link Q3a Q3b --by "<your line>"`).

When a manager is on the clock it runs these from your files, exactly as drafted; tell it in one message.

## The close

The manager runs it (`sweep.py run`, then the close note); you read it (`sweep.py status --out <the sweep's folder>` for the lanes run and left). The close note under `paths.handoff` holds: every lane's verdict from the sweep, each lane that did not pass as a numbered failure with a plan, the milestones that moved, usage spent against the budget, and what carries. After it: `/foundry-founder audit`, and re-size the next push from what this one took.
