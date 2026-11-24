# The state file: the crew's keys

The state file (`paths.state`, default `docs/progress/state.json`) is edited by the manager only. `board.py init` writes a starter one when a project is founded. It is written with `indent=1`, UTF-8, `\n` line ends. Keep that format: `json.dumps(s, indent=1, ensure_ascii=False) + "\n"` round-trips the file byte for byte.

**Editing it.** Use a `board.py` command where one exists (`note`, `usage`, `block`, `fail`, `rr`, `decide`, `promote`). For a larger edit, write a scratch script that loads the state and saves it with `board.write_state(s)` (put `<tools>` on `sys.path`, then `import board`; it retries a failed open once), or with `open(p, "w", encoding="utf-8", newline="\n")`. A plain `open(p, "w")` can write other line ends. `board.write_state` refuses (ValueError, nothing written) a `notes` item without `at`, `by`, `text`, a `log` item without `date`, `title`, or a `decisions` item without `id`, `question`, `status`. Every edit sets `updated` (the time with its offset, from `board.py stamp`), or the check reads the state as stale. `board.py` reads everything below; `office.py` reads `shift.id`, `shift.crew_max`, `rota.slots` and `tooling_known`. In a linked worktree every writing form of `board.py` is refused (exit 3): the state and the map are written in the main checkout only.

**Whose keys.** The manager writes `shift`'s blocks and their statuses, `now`, `updated`, `rota`, `checkpoints`, `failures`, `research_review`, `usage`, `notes`, `log`, `tooling_known`. The founder writes the entries of `queue` (the later shifts) and the milestone list: by its own script when no manager is on the clock; while one is, the founder hands over its draft and the manager enters the entries exactly as drafted. The manager moves `queue[0]` into `shift` only with `board.py promote`. Decisions are written only by `board.py decide` (the manager and the founder both ask, each under its own badge id).

## On `shift` and every `queue` entry

| Key | Meaning |
|---|---|
| `milestone` | The milestone or side track the shift works toward (`M1`, `compat-s1`). The check warns when it has no checkpoint. |
| `crew_max` | The headcount the user set for this shift: employees holding badges at once, sessions and temps, the manager and the founder not counted. `office.py hire` refuses past it, and refuses every hire while the shift has none. The profile's `limits.crew_max` only fills the starter shift `board.py init` writes (and a push draft's starter): a queue entry needs its own. |
| `heavy_ok` | `true` pre-approves the project's heavy work for this shift (slots nobody watches). Default `false`: ask first. |
| `blocks[].checkpoint` | On the block that runs the counted run: the lane (`G1`). |

`promote` moves `queue[0]` into `shift`: its `id`, `title`, `when`, `before_start`, `blocks` and, when the entry has them, `milestone`, `crew_max` and `heavy_ok`; the entry's `blockers` go to `state.blockers`. It exits 2 when nothing is queued or a block of the current shift is not done or skipped. Each block has a `time`, a `title`, a `done_when` and a `status` (done, partial, skipped, in-progress, pending, blocked, paused: the words `board.py block <n> <status>` takes).

## `blockers` and `checklist`

- `blockers`: a list of `{"what": "...", "owner": "the user", "shift": "<shift id>"}`. One whose `owner` names the user (or, with no owner, whose `what` says "the user") shows under Needs attention as waiting on the user. `promote` drops the finished shift's blockers and keeps the ones with no `shift`. No command writes one: edit by script.
- `checklist`: a list of lines the next manager walks at a slot start; `board.py check` prints it and the map draws it. `board.py init` writes none, and no command edits it.

## `rota`

```json
"rota": {
 "slots": [{"id": "day", "start": "06:00"}, {"id": "swing", "start": "14:00"}, {"id": "night", "start": "22:00"}],
 "days": [{"date": "2026-03-02",
           "day":   {"shift": "m1-startup", "manager": "MGR-2", "note": "..."},
           "swing": {"shift": "m1-startup", "manager": "MGR-3"},
           "night": {"shift": "m2-storage", "manager": "MGR-4"}}]
}
```

- A slot runs from its start to the next slot's start, and the last wraps past midnight: a night slot dated 03-02 runs 22:00 on 03-02 to 06:00 on 03-03.
- Each slot names the work shift it runs (an id from `shift` or `queue`) and its manager's badge id. Write the entry at a slot's start (`start`) or the end of the one before (`shift-change`); keep past days as the record.
- Each slot may carry `rr`, its research-and-review window (`"22:15-23:45"`, inside the slot). `rota.rr_since` (an ISO time with offset) is the first slot the check holds to it. `board.py init` writes neither (its slots come from the profile's `[slots]` with `id` and `start` only), and no tool reads the profile's `slots.review_window_min`: the manager writes each slot's `rr` and `rr_since` by script, and until then no window is checked.
- A day's slot entry may carry `ends` (`"16:00"`, local `HH:MM`): the end the user set for that slot's manager when it runs past the slot. Put the user's own words in the entry's `note` beside it. The check then reads the manager as on the clock until `ends`, and warns only after it. The entry is the one dated by the slot's start, like every rota entry (a night manager who clocks in at 00:30 is in the night dated the day before); `ends` is the first such time after the slot's start, so a night slot's `"07:30"` is the next morning.

## `research_review`

```json
{"id": "RR001", "date": "2026-03-02", "slot": "night", "kind": "review", "by": "EMP-04 night-reviewer",
 "topic": "the swing slot's commits: block 3, the G1 amendment", "findings": ["..."],
 "actions": ["a failure filed; EMP-01 messaged", "block 6 note"], "report": "docs/reviews/2026-03-02-night.md",
 "commit": "ab12cd3"}
```

Newest first, numbered in order, never reused; `board.py rr ...` adds the next one. `kind` is `review` or `research`; `date` and `slot` are the slot's (a night slot keeps its start date). The map's Research and review section shows each entry and links its report. The check warns when a slot since `rr_since` is past its window with no entry.

## `checkpoints`

```json
{"lane": "G1", "milestone": "M1", "shift": "m1-startup", "builder": "EMP-03", "grader": "EMP-04",
 "set_at": "2026-03-02 06:10", "note": "contract <commit>; prereg <commit>"}
```

The verdict, prereg, contract and grade come from files under `paths.gym` (`series`, `prereg`, `contracts`, `grades`), never from this entry. The check warns when a checkpoint has no prereg, no grader, or a grader who is its builder.

## `failures`

```json
{"id": "F<nnn>", "at": "2026-03-02", "lane": "G1", "run_id": "20260302-153000-ab12", "verdict": "VOID",
 "what": "...", "plan": "...", "owner": "EMP-03 / the next slot / the user", "status": "open",
 "from": "R41", "shift": "m1-startup"}
```

- `id` is `F` and three digits, numbered in order, never reused. `board.py fail ...` appends the next one (held, like a note, during a counted run).
- `status`: `open` (no plan yet), `planned` (a plan and an owner), `fixed` (say where, in `plan`), or `dropped` (decided not to pursue; say who decided). An intermittent failure is not dropped after one clean run: it stays `planned` until three clean runs in a row or a fix with a test that makes it happen (SKILL.md, Directing).
- `from`: the crew's report it files (`R<seq>` from `office.py fail`), or a list of them when several reports describe one failure (`["R192", "R193"]`).
- The check warns about reports with no entry, and about a lane whose latest run is FAIL, VOID, MARGINAL or STARVED with no entry naming it (by `lane` and `run_id`, or `lane` alone with `run_id` null).

## Decisions

The decision register (`D<n>`) is written only by `board.py decide ask | answer | withdraw`, and read with `board.py decide list`. An answer is the user's own words, quoted. Never type a decision or its answer into the state by hand; never reuse a number.

## `usage`

```json
"usage": {"stop": 80, "reset": "2026-03-10T01:00-06:00",
          "points": [{"at": "2026-03-03T08:07-06:00", "weekly": 12}]}
```

The week's plan usage as the manager's rounds read it (percent, all models). Write it with `board.py usage 12 [--stop 80] [--reset <ISO time>]`: it appends a point, and a new `reset` starts a new line. `stop` is the percent at which the user said to stop and ask (the profile's `limits.usage_stop` until the user sets another). The map draws the points against the stop; at or past it, Needs attention says so.

## `notes`

`board.py note --by MGR-2 "text"` adds one; `board.py block 3 done --note "text"` sets a block of the current shift. Both set `updated` and rebuild the map.

```json
{"at": "2026-03-02 09:40", "by": "MGR-2", "text": "..."}
```

Newest first. For what the next manager must know that is not a block result. A note is an object with these three keys, never a bare string.

## `log[]` entries

Newest first: `date`, `time`, `slot` (the rota slot's id), `title`, `done`, `not_done`, `verdicts`, `commits`, `next`, and `crew` (the list `office.py end-shift` prints, e.g. `"EMP-03 m1-builder (builder, <session id>): done, 3.2 h"`).

## `tooling_known`

A list of one-line strings: tooling bugs the crew keeps hitting, each with its workaround (`"the queue exits 127 on an absolute path: give a path relative to the checkout"`). `office.py hire` prints the list into every brief. Remove a line when its fix is merged.

## The crew office (not in the state file)

`paths.office` in the main checkout is git-ignored, and every worktree reaches it through git's common dir:

- `badge_key.json`: the signing key; never replaced.
- `roster.json`: every badge issued.
- `timeclock.jsonl`: every punch, append-only, numbered by `seq`.
- `badges/<id>.svg`: the QR plates.
- `handins/<id>.md` (an earlier READY hand-in with another report is kept as `<id>.<n>.md`), `journal.jsonl` and `journal/` (`journal.md`, `plan-<YYYYMMDD>-<HHMM>-<badge id>.md`, `carry-<crew>.jsonl`), `pending-state.jsonl` (edits held during a counted run), `adr-next.json` (the counter `hire --adr` reserves from), and the queue's files (`rq.*`).

Never edit these by hand; the tools write them under a lock.

Two things in the office are the manager's own, written by hand from the main checkout, because no tool reads or writes them: `briefs/` (long briefs sent by path) and `manager-timers.json` (`app.md`, "Timers"). A badge stops mix-ups and keeps an honest record; it is not security against a session that sets out to cheat.
