# Writing the roadmap

The roadmap is one file, `paths.roadmap` (`docs/ROADMAP.md` by default). People read it; the tools parse its tables. `references/roadmap-format.md` has the exact shapes and a complete small example. Read that before the first row, and run `flow.py selftest` after every edit.

## The goal

One paragraph, then the checks that say it is reached. Each check names something a person or a lane can observe ("a new user installs it from one file and reaches the desktop in under five minutes"), not a quality ("fast", "polished"). Below it: what is out of scope, in a list. The user agrees to both before anything else is written.

## Requirements

One row each: an id (`AREA-nn`), a tier, a status, where it is measured.

- **Tier** is the cut line. The first tier (`P0`) is what the goal cannot ship without; the last is what would be nice. The user sets every tier; you propose.
- **Status** is one of the format's words. A row is met only when a gym lane passed it, or, for a row that is a decision, when the user decided it. A builder's claim never moves a row.
- A requirement nobody can test is rewritten until someone can. "Secure" becomes the three things an attacker must not be able to do.
- Keep where each requirement came from (a user's sentence with its date, a spec's section). A row with no source is the first candidate when something must be cut.

## Stages

A stage is a state of the whole project that could be shown to someone: "boots", "usable daily", "ready to release". Each has an **exit**: a list of requirement ids that must be met. A stage with a vague exit never closes.

## Milestones

A milestone is the unit a shift works toward. Each has six fields:

| Field | Rule |
|---|---|
| What | One sentence a stranger understands |
| Closes | The requirement ids it meets |
| Measure | The gym lane that says done, set before the work and owned by a grader who did not build it. No measure, no milestone |
| Needs | Other milestones, hardware, a decision by its D-number, something bought or signed |
| Size | Slots of work, as a range, with what the range depends on |
| Risk | What would make it slip, and the cheapest early test of that |

Rules that keep the map honest:

- Every first-tier requirement maps to a milestone. A requirement with no milestone is a hole; a milestone that closes no requirement is a candidate to cut.
- A milestone is done only when its lane says PASS on a counted run. MARGINAL, FAIL, VOID and STARVED are failures with a plan, not kinds of done.
- Order comes from "Needs", and the road graph holds it (`flow.py graph`). When the roadmap's prose and the graph disagree, the graph is what the tools use; fix one of them the same day.
- Size from evidence. After the first stage, the log says how long a block of that kind took; use it.

## Decisions

A decision is a question only the user can answer: a cut line, a trade between two requirements, something to buy, a risk to accept. Each has a D-number, the question, what it gates ("needed before M12"), and its state. The register is in the state (`board.py decide`); the roadmap's decisions table shows the same numbers so the graph can draw what each gates. `references/decisions.md`.

## The change log

The last section of the roadmap. One dated line per change: what changed, why, on whose words (quoted, with the time). A roadmap with no change log cannot be audited.

## A project that already exists

Adopting the foundry in a project with code and history:

1. Read what is there: the README, the issue list, the tests, the last months of commits. Write the goal from what the user says now, not from the old README.
2. List what already works as requirements with the status the format uses for "claimed, not measured" until a lane passes them. Nothing is PASS because it "has always worked".
3. The first milestones are usually measures for what exists: a lane per area that pins today's behaviour, so later work cannot break it unnoticed.
4. Keep the project's own dashboard or tracker if it has one and the user wants it; name it in the profile and say in the rules file which one wins when they disagree.
