# The state file: the crew's keys

The state file (`paths.state`, default `docs/progress/state.json`) is edited by the manager only. `board.py init` writes a starter one when a project is founded. It is written with `indent=1`, UTF-8, `\n` line ends. Keep that format: `json.dumps(s, indent=1, ensure_ascii=False) + "\n"` round-trips the file byte for byte.

**Editing it.** Use the `board.py` command for the key:

| Key | Command |
|---|---|
| `notes` | `note --by MGR-2 "text"` |
| `usage` | `usage 12 [--stop 80] [--reset <ISO time>]` |
| `shift.blocks[]` | `block <n> <status> [--note "text"]`; the whole list, before its work begins: `shift blocks --file blocks.json` |
| `shift` | `shift set [--crew-max <n>] [--heavy-ok yes\|no] [--milestone M1] [--when "text"] --by MGR-2 --words "<the user's own words>"`; `promote` |
| `queue` | `queue add --file shift.json [--at <n>]`, `queue rm <shift id> --note "text" [--by MGR-2]`, `queue move <shift id> <n>`, `queue list` |
| `log` | `log add --by MGR-2 --title "text" [--slot day] [--done "a \| b"] [--not-done "a \| b"] [--verdicts "G1 PASS \| G2 FAIL"] [--commits a,b] [--next "text"] [--crew-file crew.json \| --crew "a \| b"]` |
| `now` | `now [--headline "text"] [--position "text"] [--tree <sha>\|auto]` |
| `rota` | `rota set --date YYYY-MM-DD --slot day [--shift ID] [--manager MGR-2] [--ends HH:MM] [--note "text"]`; `rota slots [--rr-min 90]` |
| `checkpoints` | `checkpoint add --lane G1 --milestone M1 [--builder EMP-3] [--grader EMP-4] [--note "text"] [--block <n>]`; `checkpoint set G1 [--builder ID] [--grader ID] [--note "text"]` |
| `blockers` | `blocker add --what "text" --owner "the user" [--needs D7] [--shift ID]`; `blocker rm <n>\|"<start of its text>" --note "text" [--by MGR-2]` |
| `checklist` | `checklist add "text"`, `checklist done <n>`, `checklist rm <n>`, `checklist reset` |
| `milestones` | `milestone set M1 --status done\|partial\|in-progress\|planned [--note "text"] [--force --words "<the user's own words>"] [--title "text" --lane G1]`; `milestone sync` |
| `failures`, `research_review`, `decisions` | `fail`, `rr`, `decide ask\|answer\|withdraw\|adopt` |

Each takes only its own options, sets `updated`, keeps the file's format and rebuilds the map. Exit 0: written, or held during a freeze. Exit 1: there is no state file (`run board.py init first`: founding is the founder's). Exit 2: the command cannot be read or names something the state does not have. Exit 3: a rule refuses it. Exit 4: held under a hold that looks dead. Exit 5: not held, run it again. A bare `--` ends the options, so a text may start with `--`.

**An edit held during a freeze** (`recovery.md`) is kept in `<office>/pending-state.jsonl` and replayed after it. Three things to know when you make one:

- A number that names an item (`blocker rm 2`, `checklist done 2`, `block 3 done`, `checkpoint add --block 3`, `queue move <id> 2`, `queue add --at 2`) is read against the state as it is written, the list `board.py check` prints, and held as the item itself: the blocker's or line's text, the block's title, the queued shift's id. An item that a held edit adds has no number until it is applied.
- The edit is checked against the state as it will be after the edits already held. A second `blocker rm` of the same blocker is refused at once (exit 2).
- At the replay each edit finds its item again. One whose item is gone, or cannot be told from another, stays in the file with the reason (`board.py pending` prints `FAILED: ...`), and the later ones are still applied. Make that edit by hand if it is still wanted, then delete the file.

The state's `_applied` is the id of the last held edit replayed, so a replay cut short never applies one twice. Leave it alone.

A larger edit (a key no command writes: `phases`, `tooling_known`, a block's `time` or `done_when` once work began) still goes through `board.write_state`: write a script that loads the state and saves it with `board.write_state(s)` (put `<tools>` on `sys.path`, then `import board`; it retries a failed open once). A plain `open(p, "w")` can write other line ends. `board.write_state` refuses (ValueError, nothing written) a `notes` item without `at`, `by`, `text`, a `log` item without `date`, `title`, or a `decisions` item without `id`, `question`, `status`. Such a script sets `updated` itself (the time with its offset, from `board.py stamp`), or the check reads the state as stale.

`board.py` reads everything below; `office.py` reads `shift.id`, `shift.crew_max`, `rota.slots`, `tooling_known` and, for `round` and `handoff`, `now`, `shift.blocks`, `usage`, `failures`, `decisions` and `blockers`. In a linked worktree every writing form of `board.py` is refused (exit 3): the state and the map are written in the main checkout only.

**Whose keys.** The manager writes `shift`'s blocks and their statuses, `now`, `updated`, `rota`, `checkpoints`, `failures`, `research_review`, `usage`, `notes`, `log`, `tooling_known`. The founder writes the entries of `queue` (the later shifts) and the milestone list: with `board.py queue add --file` itself when no manager is on the clock; while one is, the founder hands over its files and the manager runs `queue add` on each, exactly as drafted. The manager moves `queue[0]` into `shift` only with `board.py promote`. Decisions are written only by `board.py decide` (the manager and the founder both ask, each under its own badge id). No command checks whose badge runs it: these are rules the levels keep.

## On `shift` and every `queue` entry

| Key | Meaning |
|---|---|
| `milestone` | The milestone or side track the shift works toward (`M1`, `compat-s1`). The check warns when it has no checkpoint. |
| `crew_max` | The headcount the user set for this shift: employees holding badges at once, sessions and temps, the manager and the founder not counted. `office.py hire` refuses past it, and refuses every hire while the shift has none. The profile's `limits.crew_max` only fills the starter shift `board.py init` writes (and a push draft's starter): a queue entry needs its own, and `queue add` refuses one without. On the current shift it changes only with `shift set --crew-max <n> --by <badge id> --words "<the user's own words>"`. |
| `heavy_ok` | `true` pre-approves the project's heavy work for this shift (slots nobody watches). Default `false`: ask first. `shift set --heavy-ok yes\|no` needs `--words` too. |
| `when` | When the shift runs, as text. `shift set` appends a dated record to it for each `crew_max`, `heavy_ok` or `milestone` it sets: the time, the badge id, what changed and the user's words. |
| `blocks[].checkpoint` | On the block that runs the counted run: the lane (`G1`). `checkpoint add --block <n>` writes it. |

`queue add --file` takes one shift as a JSON object: `id` and `title` (texts), `crew_max` (a whole number), `blocks` (a list of at least one, each block with a `title` and no status but `pending`), and whatever else the shift carries (`milestone`, `heavy_ok`, `when`, `before_start`, `blockers`). An id is used once across the shift and the queue. It goes to the end of the queue, or to place `--at <n>`; place 1 is promoted next.

`promote` moves `queue[0]` into `shift`: its `id`, `title`, `when`, `before_start`, `blocks` and, when the entry has them, `milestone`, `crew_max` and `heavy_ok`; the entry's `blockers` go to `state.blockers`. It exits 2 when nothing is queued or a block of the current shift is not done or skipped. Each block has a `time`, a `title`, a `done_when` and a `status` (done, partial, skipped, in-progress, pending, blocked, paused: the words `board.py block <n> <status>` takes). `shift blocks --file` replaces the current shift's blocks with a JSON list, all pending; it is refused (exit 3) once a block is done, skipped, partial or in progress.

## `blockers` and `checklist`

- `blockers`: a list of `{"what": "...", "owner": "the user", "needs": "D7", "shift": "<shift id>", "at": "<ISO time>"}`, written by `blocker add` (`needs` and `shift` only when given; `needs` must be a decision in the register). One whose `owner` names the user (or, with no owner, whose `what` says "the user") shows under Needs attention as waiting on the user. A blocker with no `shift` is standing; `promote` drops the finished shift's blockers and keeps the standing ones. `blocker rm` takes its number as `board.py check` prints it, or the start of its text, and moves what it was, with the note, to `notes`.
- `checklist`: the lines the next manager walks at a slot start; `board.py check` prints it and the map draws it. An item is a plain string, or `{"text": "...", "done": "<ISO time>"}` once `checklist done <n>` ticked it; `checklist reset` turns every item back into its plain line. `board.py init` writes none.

## `rota`

```json
"rota": {
 "slots": [{"id": "day", "start": "06:00", "rr": "06:00-07:30"}, {"id": "swing", "start": "14:00", "rr": "14:00-15:30"},
           {"id": "night", "start": "22:00", "rr": "22:00-23:30"}],
 "rr_since": "2026-03-02T06:05-06:00",
 "days": [{"date": "2026-03-02",
           "day":   {"shift": "m1-startup", "manager": "MGR-2", "note": "..."},
           "swing": {"shift": "m1-startup", "manager": "MGR-3"},
           "night": {"shift": "m2-storage", "manager": "MGR-4"}}]
}
```

- A slot runs from its start to the next slot's start, and the last wraps past midnight: a night slot dated 03-02 runs 22:00 on 03-02 to 06:00 on 03-03.
- Each slot names the work shift it runs (an id from `shift` or `queue`) and its manager's badge id. Write the entry at a slot's start (`start`) or the end of the one before (`shift-change`), with `rota set`; keep past days as the record. `rota set` writes or updates one slot of one day; `--shift` must be the id of the shift, of a queued one, or of one the rota already names, and `--manager` opens with a badge id.
- Each slot carries `rr`, its research-and-review window (`"22:00-23:30"`, inside the slot): the slot's first `slots.review_window_min` minutes (default 90). `board.py init` writes it, and `rota slots [--rr-min <minutes>]` writes it again. `rota.rr_since` (an ISO time with offset) is the first moment the check holds slots to their windows: `init` leaves it out, and `rota slots` sets it to now when it is missing. Until then no window is checked. A window of another shape (`"22:15-23:45"`) is a larger edit.
- A day's slot entry may carry `ends` (`"16:00"`, local `HH:MM`): the end the user set for that slot's manager when it runs past the slot (`rota set --ends 16:00 --note "<the user's own words>"`; an empty `--ends ""` or `--note ""` takes the key out). Put the user's own words in the entry's `note` beside it. The check then reads the manager as on the clock until `ends`, and warns only after it. The entry is the one dated by the slot's start, like every rota entry (a night manager who clocks in at 00:30 is in the night dated the day before); `ends` is the first such time after the slot's start, so a night slot's `"07:30"` is the next morning.

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

`checkpoint add` writes the entry (one a lane; `shift` is the current shift, `set_at` the clock's time) and the lane's row in `state.lanes`; `checkpoint set` changes `builder`, `grader` or `note`. Both refuse (exit 3) a grader who is the builder. The verdict, prereg, contract and grade come from files under `paths.gym` (`series`, `prereg`, `contracts`, `grades`), never from this entry. The check warns when a checkpoint has no prereg, no grader, or a grader who is its builder.

## `milestones`

```json
{"id": "M1", "title": "Skeleton", "status": "in-progress", "lane": "G1", "note": "",
 "forced": {"at": "2026-03-02T15:40-06:00", "words": "<the user's own words>", "lane": "G1", "verdict": "VOID"}}
```

- **The list follows the roadmap.** `milestone sync` adds every milestone the roadmap's tables name and the state lacks (planned, with the roadmap's title and lane), and rewrites the title and lane of a planned one nothing has touched (no note, checkpoint, forced record, shift or log entry). `milestone sync --prune` removes the planned, untouched ones the roadmap no longer names. A milestone work has touched is never rewritten or removed. The check names the command when one is missing. `board.py init` takes the milestones of a real roadmap, and nothing from the starter (first line `<!-- STARTER`). `milestone set` of a new id the roadmap names needs no `--title`, and adds the others the roadmap names too. `--title` (and `--lane`) add a milestone neither has.
- **`milestone set`** changes a `status` (done, partial, in-progress, planned) and `note`. `done` is refused (exit 3) unless the milestone's lane (its own `lane`, its checkpoint's, or its `state.lanes` row) has PASS as its latest counted verdict in the gym's series. `--force --words "<the user's own words>"` records the user's override as `forced`, and the check goes on saying so; a later `milestone set` that is not forced takes it out.
- **An existing milestone keeps its title and its lane.** `--title` on one changes nothing (the command says so). `--lane <another lane>` is refused (exit 3): the lane is what the milestone is judged on. Only `--lane <lane> --force --words "<the user's own words>"` re-points it; `forced` then carries `lane_was`, and keeps it while the lane stays that one.

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

The decision register (`D<n>`) is written only by `board.py decide ask | answer | withdraw | adopt`, and read with `board.py decide list`. An answer is the user's own words, quoted. Never type a decision or its answer into the state by hand; never reuse a number.

The register and the roadmap's decisions table share their ids, in the shape the profile's `roadmap.decision_id` gives. `decide ask` takes the id after the highest in either (`--id <id>` where the pattern is not a prefix and a number). A decision the roadmap's table already names gets its entry under the same id: `decide adopt D4 [--by MGR-2] [--needed-before M4]` (refused, exit 2, when the register has the id or the roadmap does not). An adopted entry carries `"from": "roadmap"`; it is answered where the roadmap says Decided, else open. `decide adopt D4 --refresh` reads it again from a reworded row, but only an entry adopted with no `--by` that nobody settled here: `decide answer` and `decide withdraw` mark an adopted entry `"settled": "register"`. `decide withdraw` also takes an answered entry adopted from a roadmap that no longer names it. The check names `decide adopt` when the roadmap has an open decision the register lacks, and warns while the two disagree on whether one is answered: the roadmap's row is the founder's to bring into line.

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

Newest first: `date`, `time`, `slot` (the rota slot's id), `title`, `by` (the badge id that wrote it), `done`, `not_done`, `verdicts`, `commits` (lists), `next`, and `crew` (the list `office.py end-shift` prints, e.g. `"EMP-03 m1-builder (builder, <session id>): done, 3.2 h"`; left out when none is given). `log add` writes one at the top: the date and time from the clock, the slot from the rota unless `--slot` names it. `--done`, `--not-done`, `--verdicts` and `--crew` split on `|`; each `--verdicts` item names a verdict word; `--commits` takes hashes of 7 to 40 hex digits; `--crew-file` takes the JSON list `office.py end-shift --out` wrote.

## `now`

`headline`, `position` and `tree` (the last code commit), set by `board.py now`. `--tree auto` takes the last commit on the branch that is not only records (the map's files, reports, notes, run records); a sha is checked against git.

## `tooling_known`

A list of one-line strings: tooling bugs the crew keeps hitting, each with its workaround (`"the queue exits 127 on an absolute path: give a path relative to the checkout"`). `office.py hire` prints the list into every brief. Remove a line when its fix is merged.

## The crew office (not in the state file)

`paths.office` in the main checkout is git-ignored, and every worktree reaches it through git's common dir:

- `badge_key.json`: the signing key; never replaced.
- `roster.json`: every badge issued.
- `timeclock.jsonl`: every punch, append-only, numbered by `seq`.
- `badges/<id>.svg`: the QR plates. They need the optional `segno`; without it `office.py badge` says so, no plate is drawn, and everything else works.
- `handins/<id>.md` (an earlier READY hand-in with another report is kept as `<id>.<n>.md`; a round lists only the live `<id>.md`), `journal.jsonl` and `journal/` (`journal.md`, `plan-<YYYYMMDD>-<HHMM>-<badge id>.md`, `carry-<crew>.jsonl`), `pending-state.jsonl` (edits held during a counted run or a freeze, one a line: `id`, `at`, `argv`, a `ref` when it names an item by number, `failed` when it did not apply; a line that cannot be read is kept and skipped, and `board.py pending` shows it as UNREADABLE), `adr-next.json` (the counter `hire --adr` reserves from), and the queue's files (`rq.*`).
- `sweep.lock`: present while a sweep runs; a second sweep is refused while the first is alive.
- `freeze.json`: the freeze `office.py freeze on` or a sweep set (`{"by", "why", "lane", "at", "max_s"}`, and `sweep`, its folder, on a sweep's own; no file means no freeze). A file that cannot be read, or holds a time or length that is not sane, reads as a freeze that is on, by "unknown". `board.py brief` carries it as the key `freeze` (`on`, `by`, `why`, `lane`, `at`, `max_s`, `stale`), only while one is on.
- `handins-seen.json`: the hand-ins `office.py round --by` has listed (`{"seen": {file name: its time stamp}, "at", "by"}`), so a round names only the new ones.
- `briefs/handoff-<slot>-<YYYYMMDD>.md`: the hand-off brief `office.py handoff` writes (a second one that day is `-2`).

Never edit these by hand; the tools write them under a lock. The one way to lift a freeze is `office.py freeze off` (`--force` for a freeze a sweep set, and only once that sweep is dead).

Two things in the office are also the manager's to write, from the main checkout: `briefs/` (long briefs sent by path; the hand-written parts of a hand-off brief) and `manager-timers.json` (`{"timers": [{"name", "recurring", "every" or "at", "prompt"}]}`; `office.py timers init` writes it once from the rota's slots, `office.py timers show` prints it and checks its shape, and a dated one-shot is added by hand: `app.md`, "Timers"). A badge stops mix-ups and keeps an honest record; it is not security against a session that sets out to cheat.
