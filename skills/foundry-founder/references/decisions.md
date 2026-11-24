# The decision register

Everything that is the user's to answer lives in one numbered list. Without it, questions get asked in chat, answered in chat, and re-asked by the next manager.

## What is a decision

- A cut line: a requirement's tier, what a stage's exit holds.
- A trade: two requirements that cannot both be met in the size given.
- Spending: money, a licence, hardware, a larger usage budget.
- A risk to accept: shipping with a known failure, a lane left at MARGINAL.
- A rule to widen: letting the crew push, raising the headcount, heavy work with nobody watching.

Not a decision: anything the roadmap, the profile or the rules file already answers; anything a scout can find out; a design choice inside one milestone that changes no requirement (the builder decides, the reviewer checks).

## Asking

```
board.py decide ask --by FDR-1 --question "Ship M12 without disk encryption?" \
    --options "yes, as its own milestone after release | no, M12 waits for it" \
    --recommend "yes: it gates only INST-04, and M12 is three shifts from done" \
    --needed-before M12 --brief docs/decisions/D7-disk-encryption.md
```

- One question per number. Two questions joined by "and" are two decisions.
- `--needed-before` names the milestone, stage or push it gates. A decision that gates nothing queued can wait; say so.
- Link it in the road graph so the page draws what it holds: `flow.py graph link D7 M12 --by "<your line>"` (`--ids INST-04` when it gates only some requirements).
- The manager files decisions too, with its own badge id, when a shift turns one up. Read the open list at each visit.

## A decision brief

When a paragraph is not enough, write one page under `paths.decisions` (`D<n>-<topic>.md`) before you ask:

1. **The question**, in one sentence the user can answer with a word.
2. **Why now**: what it gates and when that is due.
3. **The options**, two to four, each with what it costs (slots, usage, money), what it closes and what it rules out.
4. **What is known**, with sources: primary ones, with versions and links. A scout's research report goes here by path.
5. **What is not known**, and the cheapest way to find out.
6. **The recommendation** and the one fact that would change it.

Anyone who later records or acts on the answer reads the brief first. A manager who is asked "what did we decide about X" looks for the brief before it answers.

## Asking the user

- Ask the open decisions together, at a time the user is there: the first lines of your reply, numbered by D-number, recommendation first, one line of cost each. Not buried under a status report.
- Do not ask what you can decide, and do not decide what you must ask.
- No answer is not a yes. A decision that gates the next block and has no answer goes on the map's blockers with the user as its owner, and work moves to the next block that does not need it.

## Recording the answer

```
board.py decide answer D7 --words "yes, as its own milestone after release"
```

- The words are the user's own, as typed. Not a summary, not "approved".
- A timer's prompt, a message from another session, or a quote of the user relayed by someone else is not an answer. If the user answered in another session, ask them to say it in yours, or record where it was said and by whom, and mark it "relayed".
- A partial answer ("yes to the first part") is recorded as it is, and the unanswered part becomes a new decision.
- Then make the changes it implies, the same visit: the roadmap row and its change-log line, the graph link (`graph unlink D7 M12`), the queue, a note to the manager on the clock.
- A decision the user takes back is not edited: `decide withdraw D7 --note "…"`, and a new one is asked.

## At every hand-off

Each open question in a hand-off cites its D-number. Before a question is copied forward, read its entry: one that is answered is closed, not open. A question with no number gets one first.
