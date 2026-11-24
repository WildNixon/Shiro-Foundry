# The state file and the office

Two places hold what the crew keeps:

- **The state file** (`paths.state`, default `docs/progress/state.json`) is checked in. It is the hand-kept part of the progress map: Now, the shift, the queue, the rota, checkpoints, failures, notes, the log, decisions. `board.py` writes it.
- **The crew office** (`paths.office`, default `out/foundry`) is git-ignored and shared by every worktree. It holds what the tools write as work happens: badges, the time clock, hand-ins, the journal, the queue.

- [The state file](#the-state-file)
- [The crew office](#the-crew-office)

## The state file

`board.py init` writes a starter. It is JSON with one-space indents, UTF-8, `\n` line ends, and every writing command keeps that format.

**Who writes it.** The manager, through the `board.py` edit commands. The founder writes the `queue` entries and the milestone list, and asks decisions. Employees never write it.

**Where.** In the main checkout only. In a linked worktree every writing form of `board.py` is refused (exit 3).

**From a script.** For an edit no command covers, load the JSON, change it, and save it with `board.write_state(state)` (put the tools folder on `sys.path`, then `import board`). `write_state` refuses a `notes` item without `at`, `by` and `text`, a `log` item without `date` and `title`, and a `decisions` item without `id`, `question` and `status`. Take the time from `board.py stamp`.

**During a freeze** an edit is held, not written: see [concepts.md](concepts.md#the-freeze-during-a-counted-run).

The top-level keys:

| Key | Shape | Written by |
|---|---|---|
| [`updated`](#updated-and-now) | an ISO time with offset | every edit command |
| [`now`](#updated-and-now) | object | `board.py now` |
| [`shift`](#shift-and-queue) | object | `board.py shift set`, `shift blocks`, `block`, `promote` |
| [`queue`](#shift-and-queue) | list of shifts | `board.py queue add`, `rm`, `move`, `promote` |
| [`blockers`](#blockers-and-checklist) | list | `board.py blocker add`, `rm`, `promote` |
| [`checklist`](#blockers-and-checklist) | list | `board.py checklist add`, `done`, `rm`, `reset` |
| [`log`](#log) | list, newest first | `board.py log add` |
| [`milestones`](#milestones-and-lanes) | list | `board.py milestone set`, `milestone sync`, `init` |
| [`lanes`](#milestones-and-lanes) | object | `board.py checkpoint add` |
| [`rota`](#rota) | object | `board.py rota set`, `rota slots` |
| [`checkpoints`](#checkpoints) | list | `board.py checkpoint add`, `set` |
| [`failures`](#failures) | list | `board.py fail` |
| [`notes`](#notes) | list, newest first | `board.py note` (and `blocker rm`, `queue rm`) |
| [`research_review`](#research_review) | list, newest first | `board.py rr` |
| [`usage`](#usage) | object | `board.py usage` |
| [`decisions`](#decisions) | list, newest first | `board.py decide ask`, `answer`, `withdraw`, `adopt`, `init` |
| [`tooling_known`](#tooling_known) | list of strings | by script |
| `_applied` | text | `board.py`, when it replays a held edit: the id of the last one applied. Never by hand |

A project may also keep `phases` (a list of items with a `status`), drawn on the map under the heading `board.phases_title`. No command writes it.

An edit command run with no state file exits 1: `no state yet (...): run board.py init first`.

### `updated` and `now`

```json
"updated": "2026-11-24T15:16:22-06:00",
"now": {
 "headline": "M1 skeleton in work",
 "position": "block 1 of 3: the contract is next",
 "tree": "ac9e22a",
 "plan_file": "docs/progress/state.json (the shift's blocks)"
}
```

Every edit sets `updated`; the check reads an old one as a stale state. `now.tree` is the last code commit. `board.py now --tree auto` finds it: the last commit on the branch that is not only records (the map's files, reports, notes, run records). The check warns when HEAD has moved past it.

```
python scripts/foundry/board.py now --headline "M1 skeleton in work" --position "block 1 of 3: the contract is next" --tree auto
```

### `shift` and `queue`

```json
"shift": {
 "id": "start",
 "title": "No shift planned yet",
 "when": "day slot",
 "crew_max": 4,
 "heavy_ok": false,
 "milestone": "M1",
 "before_start": [],
 "blocks": [
  {"time": "1h", "title": "G1 contract and prereg",
   "done_when": "the contract is committed and the grader has pinned it", "status": "partial",
   "note": "15:15 11-24 the contract is not written yet"},
  {"time": "1h", "title": "G1 counted run", "done_when": "G1 has a counted verdict",
   "checkpoint": "G1", "status": "pending"}
 ]
},
"queue": []
```

| Key | Meaning |
|---|---|
| `id`, `title` | The work shift. Ids are unique across the shift and the queue |
| `when` | Free text. `shift set` appends a dated record of each change, with the user's words |
| `crew_max` | The headcount the user set for this shift: employees holding badges at once, sessions and temps. The manager and the founder are not counted. `office.py hire` refuses past it, and refuses every hire while the shift has none |
| `heavy_ok` | `true` pre-approves the project's heavy work for this shift. Default `false`: ask first |
| `milestone` | The milestone the shift works toward. The check warns when it has no checkpoint |
| `blocks[]` | `time`, `title`, `done_when`, `status`; `checkpoint` (a lane) on the block that runs the counted run; `note` |
| `blocks[].status` | `done`, `partial`, `skipped`, `in-progress`, `pending`, `blocked` or `paused` |

```
python scripts/foundry/board.py shift set --crew-max 4 --by MGR-2 --words "Four is fine."
python scripts/foundry/board.py shift blocks --file blocks.json
python scripts/foundry/board.py block 1 partial --note "the contract is not written yet"
```

A `queue` entry is a shift with the same keys. `queue add --file shift.json` requires `id`, `title`, `crew_max` (a whole number) and `blocks`; an entry may also carry `blockers`.

```json
{"id": "m2-store", "title": "M2: the store", "milestone": "M2", "crew_max": 3, "heavy_ok": false,
 "blocks": [{"time": "2h", "title": "G2 contract and prereg", "done_when": "the prereg is registered"}]}
```

```
python scripts/foundry/board.py queue add --file shift.json --at 1
python scripts/foundry/board.py promote
```

`promote` moves `queue[0]` into `shift` when every block of the current shift is done or skipped, and the entry's `blockers` into `blockers`.

### `blockers` and `checklist`

```json
"blockers": [
 {"what": "the test phone is not on the desk", "owner": "the user", "needs": "D3", "shift": "m2-store",
  "at": "2026-11-24T15:20-06:00"}
],
"checklist": [
 "check the VM is up",
 {"text": "read the newest review", "done": "2026-11-24T15:21-06:00"}
]
```

A blocker whose `owner` names the user shows under Needs attention. A blocker with a `shift` is dropped when that shift is promoted away; one without stands. `--needs` must name a decision in the register. A checklist line is a string; a ticked one is an object with `text` and `done`.

```
python scripts/foundry/board.py blocker add --what "the test phone is not on the desk" --owner "the user" --needs D3
python scripts/foundry/board.py blocker rm 1 --note "the phone arrived" --by MGR-2
python scripts/foundry/board.py checklist add "check the VM is up"
python scripts/foundry/board.py checklist done 1
```

### `log`

```json
{"date": "2026-11-24", "time": "15:16", "slot": "swing", "title": "Swing: M1 skeleton started", "by": "MGR-1",
 "done": ["the app starts (d1b7df33)", "D1 answered"],
 "not_done": ["the G1 contract", "the grader has no session yet"],
 "verdicts": [], "commits": [], "next": "start the grader; write the contract",
 "crew": ["EMP-01 m1-builder (builder, local_...): partial, 0.0 h"]}
```

Newest first. The newest entry is the hand-off. `--verdicts` items must each name a verdict word; `--commits` takes hashes of 7 to 40 hex digits; `crew` is the list `office.py end-shift --out` writes.

```
python scripts/foundry/board.py log add --by MGR-1 --title "Swing: M1 skeleton started" --slot swing --done "the app starts (d1b7df33) | D1 answered" --next "start the grader; write the contract" --crew-file crew.json
```

### `milestones` and `lanes`

```json
"milestones": [
 {"id": "M1", "title": "Skeleton: the app starts", "status": "in-progress", "lane": "G1", "note": ""}
],
"lanes": {"G1": "M1"}
```

A milestone's `status` is `done`, `partial`, `in-progress` or `planned`. `done` is refused unless the milestone's lane (its own `lane`, its checkpoint's, or its `lanes` row) has PASS as its latest counted verdict. A forced `done` carries `"forced": {"at", "words", "lane", "verdict"}` with the user's words.

**Where the list comes from.** The roadmap's milestone tables. `board.py milestone sync` adds every milestone they name and the state lacks, as `planned`, with the roadmap's title and lane. It also rewrites the title and lane of a planned milestone nothing has touched (no note, checkpoint, forced record, shift or log entry) from its row, and names the planned, untouched ones the roadmap no longer has; `milestone sync --prune` removes those. A milestone that work has touched is never rewritten or removed. `board.py init` does the same adding when a real roadmap is already there. It takes nothing from the starter roadmap `founder.py init` writes (first line `<!-- STARTER`): its rows are examples. `milestone set` of a new id the roadmap names needs no `--title` and adds the others too. `--title` and `--lane` are for a milestone neither has yet.

**The lane is what the milestone is judged on.** For a milestone the list has, `--title` changes nothing, and `--lane <another lane>` is refused (exit 3) unless `--force --words "<the user's own words>"` records the change. The entry then carries `"forced": {"at", "words", "lane", "lane_was"}`, and keeps it while the lane stays that one.

`lanes` maps a lane to what it gates. `checkpoint add` adds the row. The lane's verdict, n and run id are never stored here: they are read from the series files.

```
python scripts/foundry/board.py milestone sync
python scripts/foundry/board.py milestone sync --prune
python scripts/foundry/board.py milestone set M1 --status in-progress
python scripts/foundry/board.py milestone set M9 --status planned --title "Sync: two devices agree" --lane G9
python scripts/foundry/board.py milestone set M1 --status done
python scripts/foundry/board.py milestone set M2 --status planned --lane G9 --force --words "Judge M2 on G9."
```

### `rota`

```json
"rota": {
 "slots": [
  {"id": "day", "start": "06:00", "rr": "06:00-07:30"},
  {"id": "swing", "start": "14:00", "rr": "14:00-15:30"},
  {"id": "night", "start": "22:00", "rr": "22:00-23:30"}
 ],
 "rr_since": "2026-11-24T15:30-06:00",
 "days": [
  {"date": "2026-11-24",
   "swing": {"shift": "start", "manager": "MGR-1"},
   "night": {"shift": "start", "manager": "MGR-2", "ends": "07:30", "note": "user: 'run until half past seven'"}}
 ]
}
```

- `slots`: a slot runs from its start to the next slot's start; the last wraps past midnight. `rr` is the slot's research-and-review window.
- `rr_since`: the first time from which the check holds a slot to its window. A starter state has the `rr` windows and no `rr_since`, so no window is checked until `board.py rota slots` sets it.
- `days`: one entry a date, one object a slot: the work shift it runs, its manager's badge id, an optional `ends` (the end the user set for that manager, local `HH:MM`) and `note`. A night slot's entry is dated by the slot's start.

```
python scripts/foundry/board.py rota set --date 2026-11-24 --slot swing --shift start --manager MGR-1
python scripts/foundry/board.py rota slots --rr-min 90
```

### `checkpoints`

```json
{"lane": "G1", "milestone": "M1", "shift": "start", "builder": "EMP-01", "grader": "EMP-02",
 "set_at": "2026-11-24 15:15", "note": "contract and prereg to come"}
```

One per lane. The verdict, prereg, contract and grade come from files under `paths.gym`, never from this entry. The check warns when a checkpoint has no prereg, no grader, or a grader who is its builder.

```
python scripts/foundry/board.py checkpoint add --lane G1 --milestone M1 --builder EMP-01 --grader EMP-02 --block 3
python scripts/foundry/board.py checkpoint set G1 --note "contract ab12cd3; prereg cd34ef5"
```

### `failures`

```json
{"id": "F001", "at": "2026-11-24", "lane": "G1", "run_id": null, "verdict": null,
 "what": "the app exits 1 when the config folder is missing",
 "plan": "create the folder at start; add a test", "owner": "EMP-01 / the next slot",
 "status": "planned", "from": "R7", "shift": "start"}
```

`id` is `F` and three digits, in order, never reused. `status` is `open`, `planned`, `fixed` or `dropped`. `from` is the crew's report it files (`R<seq>` from `office.py fail`), or a list of them. The check warns about reports with no entry, and about a lane whose latest run is FAIL, VOID, MARGINAL or STARVED with no entry naming it.

```
python scripts/foundry/board.py fail --what "the app exits 1 when the config folder is missing" --lane G1 --plan "create the folder at start; add a test" --owner "EMP-01 / the next slot" --from R7
```

### `notes`

```json
{"at": "2026-11-24T15:16-06:00", "by": "MGR-1", "text": "the grader starts next slot"}
```

Newest first. For what the next manager must know that is not a block result. A note is an object with these three keys, never a bare string.

```
python scripts/foundry/board.py note --by MGR-1 "the grader starts next slot"
```

### `research_review`

```json
{"id": "RR001", "date": "2026-11-24", "slot": "night", "kind": "review", "by": "TMP-1 night-reviewer",
 "topic": "the swing slot's commits", "findings": ["no test for the config folder"],
 "actions": ["F002 filed"], "report": "docs/reviews/2026-11-24-night.md", "commit": "ab12cd3"}
```

`kind` is `review` or `research`. `date` and `slot` default to the slot now (a night slot keeps its start date).

```
python scripts/foundry/board.py rr --kind review --by "TMP-1 night-reviewer" --topic "the swing slot's commits" --report docs/reviews/2026-11-24-night.md --commit ab12cd3 --finding "no test for the config folder" --action "F002 filed"
```

### `usage`

```json
"usage": {"stop": 80, "reset": "2026-12-01T01:00-06:00",
          "points": [{"at": "2026-11-24T15:15-06:00", "weekly": 12}]}
```

The plan's weekly usage, in percent, as the manager read it. `stop` is the percent at which the user said to stop and ask. A later `--reset` starts a new line of points.

```
python scripts/foundry/board.py usage 12 --stop 80 --reset 2026-12-01T01:00-06:00
```

### `decisions`

```json
{"id": "D1", "asked": "2026-11-24T15:14-06:00", "by": "FDR-1",
 "question": "Storage format: one file, or a folder of files?",
 "options": ["one file", "a folder of files"], "recommend": "one file: fewer moving parts",
 "needed_before": "M2", "status": "answered",
 "answer": "One file. Keep it simple until someone needs more.",
 "answered": "2026-11-24T15:15-06:00", "brief": ""}
```

`status` is `open`, `answered` or `withdrawn`. A withdrawn one carries `note` and `withdrawn`. Never type a decision or its answer into the file by hand.

**Ids.** The register and the roadmap's decisions table share one set of ids, in the shape the profile's `roadmap.decision_id` gives (`D1` by default). `decide ask` gives the id after the highest in either, and an id is never reused. Where the pattern is not a prefix and a number, `ask` cannot pick one and takes `--id <id>`.

**Adopted entries.** A decision the roadmap's table already names gets its register entry under the same id with `decide adopt <id>`. `board.py init` adopts every one a real roadmap has (never the starter's examples). An adopted entry carries `"from": "roadmap"`, the roadmap's row as its `question`, and `"by": "roadmap"` unless `--by` names a badge. It is `answered` where the roadmap says Decided (the roadmap's wording is the `answer`), else `open`.

- `decide adopt <id> --refresh` reads the entry again from the row, after the roadmap was rewritten. It takes only an entry adopted by `roadmap` itself that nobody has answered or withdrawn through the register.
- An entry answered or withdrawn through the register carries `"settled": "register"`: a person settled it, and `--refresh` leaves it alone from then on.
- `decide withdraw <id> --note "text"` also takes an answered entry that was adopted from a roadmap that no longer names it. Nothing else takes an old roadmap's answer out of the register.

The check warns while the two disagree on whether a decision is answered, when the roadmap names an open decision the register lacks, when a decisions row opens like a row and was not read, and when one id stands in more than one row.

```
python scripts/foundry/board.py decide ask --by FDR-1 --question "Storage format: one file, or a folder of files?" --options "one file | a folder of files" --recommend "one file: fewer moving parts" --needed-before M2
python scripts/foundry/board.py decide answer D1 --words "One file. Keep it simple until someone needs more."
python scripts/foundry/board.py decide withdraw D2 --note "the format was fixed by D1"
python scripts/foundry/board.py decide adopt D4 --by MGR-1 --needed-before M4
python scripts/foundry/board.py decide adopt D2 --refresh
```

### `tooling_known`

```json
"tooling_known": ["the queue exits 127 on an absolute path: give a path relative to the checkout"]
```

Tooling bugs the crew keeps hitting, each with its workaround. `office.py hire` prints the list into every brief. No command writes it; remove a line when its fix is merged.

## The crew office

Everything here is in `paths.office` of the main checkout. Every worktree reaches the same folder. The tools write these files under a lock: do not edit them by hand.

| File | What it is | Written by |
|---|---|---|
| `badge_key.json` | The signing key. Written once, never replaced: a new key would void every badge | `office.py` |
| [`roster.json`](#rosterjson) | Every badge issued | `office.py` |
| [`timeclock.jsonl`](#timeclockjsonl) | Every punch, append-only | `office.py` |
| `badges/<id>.svg` | The QR plates. They need the optional `segno`; without it no plate is drawn and the badge is its line alone | `office.py` |
| `handins/<id>.md` | The hand-in check's result with the employee's report. An earlier READY hand-in with another report is kept as `<id>.<n>.md` | `office.py handin` |
| [`freeze.json`](#freezejson) | The freeze marker. Absent means no freeze | `office.py freeze`, `sweep.py` |
| [`handins-seen.json`](#handins-seenjson) | Which hand-ins the manager's round has shown | `office.py round --by` |
| [`manager-timers.json`](#manager-timersjson) | The list of timers the manager keeps in its session | `office.py timers init`; dated one-shot timers by hand |
| `briefs/` | Hand-off briefs (`handoff-<slot>-<YYYYMMDD>.md`) and long briefs the manager sends by path | `office.py handoff`; the manager |
| `adr-next.json` | The counter `hire --adr` reserves decision-record numbers from: `{"last": 12, "at": ...}` | `office.py hire --adr` |
| [`pending-state.jsonl`](#pending-statejsonl) | State edits held during a freeze, one a line | `board.py` |
| [`rq.*`](#the-queues-files) | The resource queue | `rq.py` |
| [`journal.jsonl`, `journal/`](#the-journal) | The shift journal | `journal.py` |
| `sweep-STOP` | An empty file someone creates to pause a sweep before its next lane | by hand |
| `sweep.lock` | Present while a sweep runs: `{"id", "out", "alive", "at"}` (who, its folder, its `alive` file). A second sweep is refused while the first still touches its `alive` file; a stale lock is a killed sweep's and is written over | `sweep.py` |

### `roster.json`

```json
{
 "v": 1,
 "manager": "MGR-1",
 "founder": "FDR-1",
 "badges": {
  "EMP-01": {
   "id": "EMP-01",
   "line": "FB1 ID:EMP-01 NAME:M1-BUILDER ROLE:BUILDER KIND:SESSION SHIFT:START SLOT:SWING ISSUED:1795554920 SIG:6TNBQE54VOAJ33GL",
   "name": "m1-builder",
   "role": "BUILDER",
   "kind": "SESSION",
   "shift": "start",
   "slot": "swing",
   "issued": 1795554920.68,
   "session": "local_...",
   "revoked": null,
   "job": "M1: the app starts and shows one screen; write the G1 contract first",
   "done_when": "the contract is committed; the app starts; a dev run is dry-graded GO by the G1 grader",
   "lane": "G1",
   "vmdir": "",
   "files": "src/, gym/contracts/G1-artifacts.md",
   "eta_s": 10800,
   "by": "MGR-1",
   "title": "builder"
  }
 }
}
```

`vmdir` is how the badge reaches the shared resource: `"rq"` for a badge hired with `--rq`, a seat's name for `--seat`, empty for neither. A badge hired with `--model` carries `model`; one hired with `--adr` carries `adr`. A replaced manager's or founder's badge carries `revoked` (a time) and `revoked_why`.

### `timeclock.jsonl`

One JSON object a line, numbered by `seq`. Times are seconds since the epoch. The roster's statuses are worked out from this file.

```json
{"seq": 5, "at": 1795554936.6, "id": "EMP-01", "ev": "in"}
{"seq": 6, "at": 1795554937.2, "id": "EMP-01", "ev": "progress", "pct": 20, "eta": 1795562137.2, "note": "writing the G1 contract"}
{"seq": 7, "at": 1795554943.9, "id": "EMP-01", "ev": "fail", "what": "the app exits 1 when the config folder is missing", "lane": "G1", "plan": "create the folder at start; add a test"}
{"seq": 9, "at": 1795554949.5, "id": "EMP-01", "ev": "handin", "ok": true, "tip": "d1b7df33", "branch": "claude/m1-builder", "problems": 0, "warnings": 0}
{"seq": 10, "at": 1795554950.1, "id": "EMP-01", "ev": "out", "result": "partial", "note": "the app starts; config-folder fix reported as R7", "commits": ["d1b7df3"]}
{"seq": 12, "at": 1795554971.0, "id": "MGR-1", "ev": "freeze", "on": true, "why": "counted G1", "lane": "G1", "max_s": 3600}
{"seq": 13, "at": 1795554973.2, "id": "MGR-1", "ev": "freeze", "on": false, "was_by": "MGR-1", "held_s": 2, "note": "run ended"}
{"seq": 14, "at": 1795554979.3, "id": "MGR-1", "ev": "shift-end", "note": "slot swing, shift start"}
{"seq": 15, "at": 1795554982.6, "id": "MGR-1", "ev": "handoff", "file": ".../out/foundry/briefs/handoff-swing-20261124.md"}
```

| `ev` | Written by | Extra keys |
|---|---|---|
| `in` | `clock-in` | |
| `progress` | `progress`, and `round --by` (the manager's heartbeat) | `pct`, `eta`, `note` |
| `fail` | `fail` | `what`, `lane`, `run_id`, `verdict`, `plan`. Its `seq` is the report number: `R7` is the event with `seq` 7 |
| `handin` | `handin` | `ok`, `tip`, `branch`, `problems`, `warnings`; `for` when the manager ran it |
| `out` | `clock-out`, and a relieved manager or founder | `result`, `note`, `commits` |
| `amend` | `amend` | what changed |
| `freeze` | `freeze on`, `freeze off` | `on`; then `why`, `lane`, `max_s`, or `was_by`, `held_s`, `note` |
| `shift-end` | `end-shift` | `note` |
| `handoff` | `handoff` | `file` |
| `timers` | `timers init` | `file`, `n` |

### `freeze.json`

```json
{"by": "MGR-2", "why": "counted G1", "lane": "G1", "at": 1795555786.27, "max_s": 3600}
```

Present while a freeze is on. `office.py freeze show --json` prints the same facts with `on` and `stale`:

```json
{"on": true, "by": "MGR-2", "why": "counted G1", "lane": "G1", "at": 1795555786.27, "max_s": 3600, "stale": false}
```

A freeze `sweep.py` wrote for itself has `by` set to the badge id that queued the sweep, `why` "counted sweep", `lane` null, and one extra key, `sweep`: the sweep's folder. `office.py freeze off` lifts such a freeze only with `--force`.

A file that cannot be read, or whose `at` or `max_s` is not a sane time or length, reads as a freeze that is on: `"by": "unknown"`, with the reason in `why`. `office.py freeze off` removes it.

### `pending-state.jsonl`

One held edit a line:

```json
{"id": "20261124T163307-dffbbfe4", "at": "2026-11-24T16:33:07-06:00", "argv": ["note", "--by", "MGR-1", "the grader starts next slot"]}
{"id": "20261124T163308-c5ea9f43", "at": "2026-11-24T16:33:08-06:00", "argv": ["blocker", "rm", "1", "--note", "the phone arrived", "--by", "MGR-1"], "ref": {"kind": "blocker", "arg": 2, "key": "the test phone is not on the desk"}}
```

| Key | Meaning |
|---|---|
| `id` | The edit's own id: the time it was held and eight random hex digits. The state's `_applied` names the last one replayed, so a replay cut short never applies one twice |
| `at` | When the edit was made. It is applied with this time |
| `argv` | The command line as it was given (a `--file` is kept as its JSON, `--tree auto` as the commit it meant) |
| `ref` | Only on an edit that names an item by a number: `kind` (`blocker`, `checklist`, `block`, `queue`, `queue-at`), `arg` (which argument holds the number) and `key` (the item's identity: the blocker's or line's text, the block's title, the queued shift's id). At the replay the item is found again by `key` |
| `failed` | Only on an edit that did not apply at the replay: the reason. The line stays in the file until the manager settles it by hand and deletes the file |

A line of the file that cannot be read as a held edit is kept as it is and skipped; `board.py pending` shows it as `UNREADABLE line, kept and skipped`.

### `handins-seen.json`

```json
{"seen": {"EMP-01.md": 1795554949.936}, "at": 1795554954.77, "by": "MGR-1"}
```

Each hand-in file's name with the time stamp it had when the round listed it, then when and by whom the list was last written.

### `manager-timers.json`

```json
{
 "timers": [
  {"name": "round", "recurring": true, "every": "2h", "prompt": "/foundry-manager status, then the round"},
  {"name": "handoff-day", "recurring": true, "at": "13:20", "prompt": "/foundry-manager shift-change"},
  {"name": "start-day", "recurring": true, "at": "06:00", "prompt": "/foundry-manager start"}
 ]
}
```

Each entry has `name`, `recurring`, `every` or `at`, and `prompt`. `office.py timers init` writes the round and, for each slot of the rota, a hand-off 40 minutes before its end and a start. The tool creates no timer: the manager creates them in its session from this list, and `office.py timers show` checks the file's shape.

### The queue's files

| File | What it is |
|---|---|
| `rq.queue.json` | The waiters, in the order they queued: a JSON list |
| `rq.lock/` | A folder that exists while the first seat is held. Another seat `S` uses `rq.lock.S/` |
| `rq.lock/hold.json` | The hold |
| `rq.last` | The first seat's last release note. Another seat `S` uses `rq.last.S` |
| `rq.released.json` | Each id's last release time: `{"EMP-04": 1795555787.4}` |
| `rq.requeue.json` | Waiters the manager moved, so each may take its own place again |
| `rq.seats` | Optional, by hand: one seat a line. Overrides the profile's `resource.seats` |
| `rq.mutex/` | The queue's own lock |

A hold:

```json
{"id": "EMP-04", "job": "by hand", "since": 1795555787.22, "max": 300, "lane": "a", "gui": false,
 "all": false, "prio": 5, "token": "29392-1795555787224", "via": "take"}
```

In this file the seat is under the key `lane` and the exclusive mark under `gui`. `max` is in seconds. `via` is `run` or `take`. Read the queue with `rq.py status --json` instead of these files: it prints `seat` and `exclusive`.

A release note:

```
EMP-04 15:29 released seat a after: done
touched: src
```

### The journal

`journal.jsonl` is append-only, one event a line. An entry's state is worked out from its events.

```json
{"at": 1795554944.4, "ev": "add", "by": "EMP-01", "role": "BUILDER", "kind": "hole", "what": "the brief names two different interpreters for the two selftests", "fix": "print commands.python in both", "where": "office.py hire"}
{"at": 1795554964.6, "ev": "plan", "by": "MGR-1", "ids": [1], "fix": "office.py prints commands.python for both selftest lines", "files": "scripts/foundry/office.py", "how": "", "owner": "the next slot's fixer"}
{"at": 1795554965.0, "ev": "ready", "by": "MGR-1", "ids": [1], "file": ".../out/foundry/journal/plan-20261124-1516-MGR-1.md", "end": 1795579200.0, "due": 1795575600.0}
{"at": 1795554965.6, "ev": "approve", "by": "MGR-1", "ids": [1], "words": "Yes, fix J1 next slot."}
```

An entry's id is its place among the `add` events: the first is `J1`.

Under `journal/`:

| File | What it is |
|---|---|
| `journal.md` | The page a person opens |
| `plan-<YYYYMMDD>-<HHMM>-<badge id>.md` | A plan file `journal.py ready` wrote for the user |
| `carry-<crew>.jsonl` | The outbox of lessons for another crew |
