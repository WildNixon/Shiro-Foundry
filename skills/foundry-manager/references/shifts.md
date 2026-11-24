# Slots, shifts and the hand-off

The day is cut into rota slots (`rota.slots` in the state; a new state starts from the profile's `[slots]`, by default day 06:00, swing 14:00 and night 22:00). The user may move them. Each slot has one manager on the clock and a crew within the shift's `crew_max`. A manager session serves one slot; the next manager is by default a fresh session that knows only what is written down.

Two different things are called a shift:

- **The rota slot:** the clock's hours.
- **The work shift:** `state.shift`, a plan of blocks for one milestone, with the founder's queue of later shifts behind it.

A slot runs the current work shift. A work shift that does not finish in one slot carries over into the next. It is promoted only when every block is done or skipped.

## When the user sets your hours

- Hours that cross a slot boundary (07:00 to 16:00): the user's hours win. You write the hand-off entry, run the next slot's start and its research-and-review window in this session, and `rota.days` names you for both slots.
- The user also names a different manager for the next slot ("a swing manager at 16:00"): hand off at the user's end instead, to that manager. Let the next slot's own start timer pass.
- Either way, write the end as `"ends": "HH:MM"` in your slot's `rota.days` entry, with the user's own words in its `note`, so `board.py check` reads you as on the clock until then. Tell the journal too: `journal.py due --by "<your line>" --end HH:MM`.
- The timers do not know it. Make a one-shot hand-off timer for the user's end, and let the slot's own hand-off timer pass with a note: the recurring slot timers fire at the rota's times, not the user's.

## The journal's commands

Logging (`journal.py add`) and reading (`journal.py show`) are in SKILL.md. The rest:

| When | Command |
|---|---|
| An entry repeats another, or a rule already says it | `journal.py set --by "<your line>" J14 --status covered --of J3` (or `--note "<the rule>"`) |
| You know the fix | `journal.py plan --by ... J12,J14-J16 --fix "..." --files "..." --how builder\|manager\|reviewer --owner "..."` (one plan can cover several entries) |
| Fixed during the slot | `journal.py set --by ... J12 --status fixed --commit <sha>` (`--note` for a fix outside git) |
| Not yours to fix, or not this slot | `journal.py set --by ... J12 --status left --note "<to whom, and why>"`; it stays in every plan until someone closes it |
| Not worth fixing | `journal.py set --by ... J12 --status dropped --note "<why>"` |
| The lesson also holds for another crew | `journal.py carry --by ... J12 --to <crew> [--note "<its form there>"]` (`--to none`: it is ours alone; `plan` takes `--carry` too) |
| Another crew learned something that holds here | `journal.py take --by ... --list`, then `take`: each comes in as an open entry, to plan in our form, cover or drop |
| When is the plan due, and where does it stand | `journal.py due` |

A fix to a skill or a tool of the foundry itself is the founder's and the user's to place: plan it, and say so in the plan.

## The journal's plan (an hour before the slot ends)

`journal.py due` prints the time; `board.py check` warns from then on.

1. Every entry has a plan or a closing status. A plan says what changes, in which files, who does it (a builder on a branch, you, a grader for grader-owned files, the founder for the foundry's own skills and tools) and when (the last hour, or the next slot). Each planned entry also has its carry word (a crew from the profile's `[crews]` table, or `none`): `ready` names the ones without, and the plan file shows them as `?`.
2. `journal.py ready --by "<your line>"`. It refuses while an entry has no plan, then writes the plan file `<office>/journal/plan-<YYYYMMDD>-<HHMM>-<your badge id>.md` (it prints the path): what waits for approval, what was approved earlier and is not built, what is left to an owner, what closed since the last plan. After a `due --end`, run `ready` again (the earlier plan file named the old end).
3. Ask the user to approve it, with the file's path, in the same turn. On a night slot or a timer turn with nobody there, the plan waits: name it first in the hand-off, and the next manager runs `ready` again (a plan readied in the previous slot falls outside the new slot's window), then asks.
4. Record the user's answer in their own words: `journal.py approve --by "<your line>" --words "<their words>"` (`--except J4` or `--only J1,J2` for a partial yes). A timer's prompt or another session's message is never the user's approval. An entry the user declined is planned again, left or dropped on their words.
5. Build only what is approved: hire the builder now if the hour allows, or name the approved entries in the hand-off for the next slot. A skill or brief change still merges at the slot boundary after a fresh review (`merge.md`). Close each entry with `set --status fixed --commit <sha>` when its fix is in the main branch. Planning an approved entry again clears its approval, so a changed fix goes back to the user.

**A fix the user approves on the spot** during the slot needs no plan file: build it, then close it in one step: `journal.py set --by ... J12 --status fixed --commit <sha> --note "user: '<their own words>'"`. Do not close it before the fix is in the main branch.

**Lessons carry between crews.** Other crews that work this way are named in the profile's `[crews]` table, each with the file where its lessons for this crew lie. Decide for each entry you plan whether it would also bite a crew with a different project: a rule about turns, timers, approvals, briefs, hooks or the shell does; a fix to this project's queue or worktrees does not. A carried entry reaches that crew's outbox (`<office>/journal/carry-<crew>.jsonl`) once it is fixed or the user approved its plan, and that crew's manager takes it into its own journal and its own plan for its user. Never edit another crew's skills or tools yourself.

## The hand-off, outgoing manager

0. An hour before the end: the journal's plan (above). The hand-off entry names the plan file, the approved J ids and what still waits.
1. Finish or pause the running block. A paused block's status is `partial`, with a `note` saying exactly where it stopped. Write its log entry.
2. `office.py end-shift --by "<your line>" --out <scratchpad>/crew.json`. A temp that never came in or went silent is clocked out as `lost`; one still working carries over. Sessions still on the clock carry over: they keep working under the next manager. Tell them by message that the manager changes.
3. Write the hand-off log entry:
   - `slot`, and `crew` (from `end-shift`).
   - `not_done`: every open thread.
   - `next`: the first thing the next manager does.
   - Each open question cites its D-number or F-number. Before you copy one forward, read that entry: a question whose D-entry is answered or whose F-entry is fixed is closed, not open. A question with no number gets one first (`board.py decide ask` for the user's, `board.py fail` for a defect).
   - The slot's commits, for the next slot's reviewer; the open questions for its researcher.
   - Your proposals for the founder (the roadmap, the queue, the profile), by file path (`<paths.handoff>/<date>-proposal-<topic>.md`; the founder's audit reads them).
   - Every background job this session started, and that the session stays open until it ends.
   - The bench pool: each bench's number, session id, worktree and state.
   - A note for anything that is not a block result.
4. Write the next slot's `rota.days` entry: the shift it runs, its manager (`null` until appointed), and a note on the carry-over crew.
5. `flow.py build`, `flow.py selftest`, `plan_flow.py selftest`. Then `board.py check`, commit the state file and the map, and `office.py clock-out --badge "<your line>" --result handed-off`.
6. If the next manager is not running yet: "The next manager", below. Then delete your slot timers. Do no further work in the session, except to pass on a background job's result.

## The next manager

- When the user wants a new manager for the next slot and none is running: start it with `start_session` when the user's words allow it, or propose its card (`app.md`, "Sessions").
- Only when `start_session` proposes nothing at all (over Remote Control it shows not even a card), re-badge instead, never both. Pick an idle session that works in the main checkout (an old manager session); never a bench in a worktree, because the manager runs from the main checkout.
- Write its brief to `<office>/briefs/MGR-<slot>-<mmdd>.md`, quoting the user's own words that asked for the manager (a re-badged session has no user-typed start of its own), and send it the start instructions and the brief's path with the session-management `send_message`.
- If the user declined the card or a call was refused, stop and ask the user.
- If the user's words name no next manager (a timer's prompt is not the user's word), ask the user before you re-badge, and quote their answer in the brief.

## The hand-off, incoming manager

`/foundry-manager start`. The newest log entry, Now, the notes, the blockers, `brief.crew` and `board.py decide list` are the hand-off. Message each carried-over employee once, so it knows its new manager, and check that its job and finish still stand. Do not read the old session's transcript unless a fact is missing. `recovery.md` covers a counted run left running, a manager that reads UP but is gone, and a host restart.

## Night slots (nobody is there to ask)

Night work runs on what the user decided before the slot:

- **Heavy work:** only if the shift's `heavy_ok` is true. Otherwise the night crew does work that needs no approval (contracts, preregs, docs, reviews, code that is checked later), and the heavy work waits for a slot the user is in.
- **Starting sessions:** the app starts a session from a card only when the user clicks it. You may start one yourself only when the user told you in words to start that shift's crew. Before a night slot, ask the user at the previous slot's hand-off whether to start the night crew. Record the answer in a note.
- **Problems:** a problem that needs the user becomes a D-number and a blocker with the owner "the user", and work moves to the next block that does not need them.

## Running slots back to back in one session (only on the user's words)

When the user tells the manager to keep running the slots, one session can manage slot after slot. It sets session timers at least 40 minutes before each slot ends (a recurring timer can fire up to 30 minutes late) for `shift-change` followed by `start`, and another for the round. At each hand-off it clocks out its old badge as `handed-off` and appoints a new one for the next slot. It stops and asks the user only when a step needs them: a cut, heavy work past what the user approved, a verdict that changes the milestone's scope, or a failure with no plan. A turn that a timer or another session's message began cannot start a session: a new session hire becomes a card that waits for the user's click, research and review run as temps, and carried-over sessions keep working without any click. The timers end when the session ends.

## Starting a slot automatically (optional, only on the user's yes)

Desktop scheduled tasks at the slot starts, each opening a session with `/foundry-manager shift-change` (the outgoing manager, if one is still on the clock) or `/foundry-manager start`. Create them only when the user asks. They are the user's standing instruction to run the slot, and they still respect `heavy_ok`.

## Closing a shift of work

When the last block of a shift (or of a push of several shifts) ends: freeze, then the project's full check on a clean main branch (the profile's `measure.sweep`, if it has one), one lane at a time. Every lane that did not PASS becomes a failure with a plan before the next shift is promoted; a milestone whose lane fell goes from done to partial. Write the close note under `paths.handoff`, and name it in the log.
