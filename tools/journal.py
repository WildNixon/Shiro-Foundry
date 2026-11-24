#!/usr/bin/env python3
"""The shift journal: the holes, failures and improvements a shift finds in how the crew works (the skills,
the tools, the briefs, the manager's own slips), each with an action plan, ready for the user's approval an hour
before the slot ends. One file for every crew that works this way: it runs beside that crew's office.py, and a
lesson one crew learned carries to the others (carry, take).

Everyone with a badge (the limited form for crew):
    python tools/journal.py add --badge LINE --kind hole|failure|improvement --what TEXT [--fix TEXT] [--where TEXT]
                                  [--what-file F] [--fix-file F]   log an entry as you notice it; prints its id (J12)
    python tools/journal.py mine --badge LINE                    your own entries and what became of them
    python tools/journal.py show --badge LINE J29,J32 [--json]   read the entries you name (anyone's, open or
                                                                   closed); read-only

The manager on the clock only (--by is the manager's badge line):
    python tools/journal.py add --by LINE --kind K --what TEXT [--fix TEXT] [--where TEXT] [--from EMP-07]
                                                                   --from: logged for a crew member (a hand-in, a message)
    python tools/journal.py show --by LINE [J12,...] [--all] [--json]
                                                                   the live entries (--all: closed ones too; ids: those)
    python tools/journal.py plan --by LINE J12,J14-J16 --fix TEXT [--files TEXT] [--how TEXT] [--owner TEXT]
                                                                   the action for one entry or several; planning an
                                                                   approved entry again clears its approval
    python tools/journal.py set --by LINE J12 --status fixed|covered|dropped|left|open [--note TEXT] [--commit SHA]
                                  [--of J3]                        fixed: --commit or --note; covered: --of or --note;
                                                                   dropped, left: --note (why, or to whom)
    python tools/journal.py due [--by LINE --end 16:00]          when the plan is due (an hour before the slot's end)
                                                                   and where it stands; --end: the user's end for this
                                                                   manager, when the rota does not carry it
    python tools/journal.py ready --by LINE                      refuses while an entry has no plan; writes the plan
                                                                   file for the user and marks the plan ready
    python tools/journal.py approve --by LINE --words "the user's own words" [--only J1,J2 | --except J4]
                                                                   record the user's approval of the ready plan
    python tools/journal.py carry --by LINE J12,J14 --to CREW|none [--note TEXT]
                                                                   the lesson also holds for another crew (none: it
                                                                   does not); add and plan take --carry too. A carried
                                                                   entry reaches that crew's outbox once it is fixed
                                                                   or approved (journal/carry-<crew>.jsonl in the office)
    python tools/journal.py take --by LINE [--max 10] [--list] [--from FILE [--crew NAME]]
                                                                   take the lessons other crews carried here into
                                                                   this journal as open entries (each once); plan
                                                                   each in this crew's form, cover it or drop it
    python tools/journal.py selftest

The crews are named in the profile (.foundry/foundry.toml): `crew` is this one, and the [crews] table maps each
other crew to the file (or files) where its lessons for this crew lie (name -> {lessons = "path"}). `carry --to`
takes any crew that table names, or none.

An entry is open (no plan), planned, left (to a named owner or the next slot), or closed: fixed, covered (a
duplicate, or a rule that already says it) or dropped. A failing test or run is not a journal entry: that is
`office.py fail`. No run outcome or verdict goes in an entry (graders read results only after pinning).

The journal lives in the crew office (the profile's paths.office: journal.jsonl, append-only; its journal/ folder
holds journal.md and the plan files), so every worktree reaches the same one and nothing in git changes when it
is written. Standard library only; badges and the office come from office.py.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import foundry_profile as fp  # noqa: E402
P = fp.load(__file__)
import office  # noqa: E402

KINDS = ("hole", "failure", "improvement")
LIVE = ("open", "planned", "left")
CLOSED = ("fixed", "covered", "dropped")
PLAN_LEAD_S = 3600          # the plan is ready for the user this long before the slot ends
END_KEPT_S = 4 * 3600       # a manager's `due --end` still reads this long after it passed
RECENT_S = 24 * 3600        # journal.md and a first plan list entries closed inside this
TAKE_MAX = 10               # lessons one `take` brings in: each becomes an open entry that needs a plan


def me():
    """This crew's name (the profile's `crew`, as office.CREW; FOUNDRY_CREW for the selftest)."""
    fn = getattr(office, "crew_name", None)  # asked at each call: the selftest changes the environment mid-run
    return fn() if fn else (os.environ.get("FOUNDRY_CREW") or getattr(office, "CREW", "") or P.crew)


def lessons():
    """{other crew: [the files where its lessons for this crew lie]}: the profile's [crews] table
    (name -> {lessons = path or paths}), as office.LESSONS; FOUNDRY_LESSONS, a JSON object, for the selftest.
    A crew the table names with no file is still a crew to carry to: its list is empty."""
    env = os.environ.get("FOUNDRY_LESSONS")
    fn = getattr(office, "lessons", None)
    try:
        raw = json.loads(env) if env else fn() if fn else {**(P.get("crews") or {}), **(getattr(office, "LESSONS", None) or {})}
    except ValueError:
        raw = {}
    out = {}
    for k, v in (raw or {}).items() if isinstance(raw, dict) else ():
        if isinstance(v, dict):
            v = v.get("lessons")
        out[str(k).lower()] = [v] if isinstance(v, str) else [str(p) for p in (v or [])]
    out.pop(me(), None)
    return out


def parse_crews(text):
    """The crews a lesson carries to: [] for `none`."""
    names = [t for t in re.split(r"[,\s]+", (text or "").lower()) if t]
    if names == ["none"]:
        return []
    known = sorted(lessons())
    off = [n for n in names if n not in known]
    if off or not names:
        raise office.Refused(f"carry to {', '.join(off) or 'whom'}? This office knows " + (", ".join(known) or "no other crew")
                         + " (the profile's [crews] table); write one of them, or none")
    return names


def jfile(d):
    return d / "journal.jsonl"


def read_j(d):
    f = jfile(d)
    if not f.exists():
        return []
    out = []
    for l in f.read_text(encoding="utf-8").splitlines():
        try:
            if l.strip():
                out.append(json.loads(l))
        except ValueError:  # a torn line never stops the journal
            continue
    return out


def append_j(d, ev):
    """Call under office.locked(d)."""
    f = jfile(d)
    prefix = ""
    if f.is_file() and f.stat().st_size > 0:
        with open(f, "rb") as rh:
            rh.seek(-1, 2)
            if rh.read(1) != b"\n":
                prefix = "\n"
    with open(f, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(prefix + json.dumps(ev, ensure_ascii=False) + "\n")
    return ev


def fold(events):
    """(entries by number, ready events, end events, skipped add count) from the journal's events, in order."""
    entries, readies, ends, skipped = {}, [], [], 0
    for e in events:
        ev = e.get("ev")
        if ev == "add":
            try:
                at, by, kind, what = e["at"], e["by"], e["kind"], e["what"]
            except KeyError:
                skipped += 1
                continue
            n = len(entries) + 1
            entries[n] = {"n": n, "id": f"J{n}", "at": at, "by": by, "role": e.get("role", ""),
                          "kind": kind, "what": what, "fix": e.get("fix", ""), "where": e.get("where", ""),
                          "src": e.get("src", ""), "status": "open", "plan": None, "approved": None,
                          "note": "", "commit": "", "of": "", "closed_at": None, "touched": e["at"],
                          # carry: None (nobody decided), [] (this crew only) or the other crews it holds for;
                          # origin: {"crew", "id"} when the entry was taken from another crew
                          "carry": e.get("carry"), "carry_note": "", "origin": e.get("origin")}
        elif ev == "plan":
            for n in e.get("ids", []):
                x = entries.get(n)
                if x:
                    x["plan"] = {k: e.get(k, "") for k in ("fix", "files", "how", "owner")} | {"at": e["at"], "by": e["by"]}
                    x["status"], x["approved"], x["closed_at"], x["touched"] = "planned", None, None, e["at"]
                    if "carry" in e:
                        x["carry"] = e["carry"]
        elif ev == "carry":
            for n in e.get("ids", []):
                x = entries.get(n)
                if x:
                    x["carry"], x["carry_note"], x["touched"] = e.get("to", []), e.get("note", ""), e["at"]
        elif ev == "status":
            for n in e.get("ids", []):
                x = entries.get(n)
                if not x:
                    continue
                st = e["set"]
                if st == "open":  # reopened: its plan stays, its approval does not
                    st, x["approved"] = ("planned" if x["plan"] else "open"), None
                x["status"] = st
                x["note"] = e.get("note") or x["note"]
                x["commit"] = e.get("commit") or x["commit"]
                x["of"] = e.get("of") or x["of"]
                x["closed_at"] = e["at"] if st in CLOSED else None
                x["touched"] = e["at"]
        elif ev == "approve":
            for n in e.get("ids", []):
                x = entries.get(n)
                if x and x["status"] == "planned":
                    x["approved"] = {"at": e["at"], "by": e["by"], "words": e.get("words", "")}
        elif ev == "ready":
            readies.append(e)
        elif ev == "end":
            ends.append(e)
    return entries, readies, ends, skipped


def parse_ids(text, entries):
    out = []
    for tok in [t for t in re.split(r"[,\s]+", text or "") if t]:
        m = re.fullmatch(r"[Jj]?(\d+)(?:-[Jj]?(\d+))?", tok)
        if not m:
            raise office.Refused(f"cannot read the entry id {tok!r}; write J12, J12,J14 or J12-J15")
        a, b = int(m.group(1)), int(m.group(2) or m.group(1))
        if b < a:
            raise office.Refused(f"the range {tok} runs backwards")
        for n in range(a, b + 1):
            if n not in entries:
                raise office.Refused(f"no journal entry J{n} (the newest is J{len(entries)})")
            if n not in out:
                out.append(n)
    if not out:
        raise office.Refused("name at least one entry (J12)")
    return out


def ids_text(ns):
    return ", ".join(f"J{n}" for n in ns) or "none"


# --- when the plan is due ---

def rota_end(state, sid, s0, s1):
    """The user's `ends` for the slot (sid, s0, s1) from its rota.days entry, as epoch seconds, or None."""
    try:
        import board
        day = f"{office.local(s0):%Y-%m-%d}"
        entry = next((e for e in (state.get("rota") or {}).get("days", [])
                      if isinstance(e, dict) and e.get("date") == day), {}).get(sid) or {}
        text = entry.get("ends") if isinstance(entry, dict) else None
        if hasattr(board, "read_ends"):
            return board.read_ends(sid, s0, s1, text)[0]
        # a board.py without read_ends: the HH:MM after the slot's start, the next day for a slot
        # that crosses midnight, and never more than a slot's length past its end
        import datetime as dt
        m = re.match(r"^([01]?\d|2[0-3]):([0-5]\d)$", str(text or "").strip())
        if not m:
            return None
        start = office.local(s0)
        for day in (0, 1):
            t = dt.datetime.combine(start.date() + dt.timedelta(days=day), dt.time(int(m.group(1)), int(m.group(2)))).astimezone().timestamp()
            if s0 < t <= s1 + (s1 - s0):
                return t
        return None
    except Exception:  # the rota's `ends` is a refinement; the slot's own end always stands
        return None


def shift_end(state, now, ends, mgr_id):
    """(end, why): the end of the shift the manager on the clock is working at `now`. In order: the manager's own
    `due --end` (while it is ahead, or passed less than END_KEPT_S ago); the rota's `ends` for the slot now; the
    `ends` of the slot before, while that is still ahead (the user's hours crossing a boundary); the slot's end."""
    mine = [e for e in ends if e.get("by") == mgr_id and e["at"] <= now]
    if mine and mine[-1]["end"] > now - END_KEPT_S:
        return mine[-1]["end"], f"set by {mgr_id} (due --end)"
    slots = (state.get("rota") or {}).get("slots")
    sid, s0, s1 = office.slot_at(slots, now)
    t = rota_end(state, sid, s0, s1)
    if t and t > now - END_KEPT_S:
        return t, f"the rota's `ends` for the {sid} slot"
    psid, p0, p1 = office.slot_at(slots, s0 - 1)
    t = rota_end(state, psid, p0, p1)
    if t and t > now:
        return t, f"the rota's `ends` for the {psid} slot"
    return s1, f"the {sid} slot's end"


def facts(d, state, now, events=None):
    """Where the journal stands at `now`: the shift's end and the plan's due time, the entries with no plan, the
    planned ones the user has not approved, and one word: OPEN (not due yet), DUE (past due and not ready), READY
    (the plan file is written and waits for the user) or APPROVED (ready, and nothing waits for the user)."""
    events = read_j(d) if events is None else events
    entries, readies, ends, skipped = fold(events)
    # drop entries stamped in the future (a clock step back) but keep their numbers stable
    future = [n for n, x in entries.items() if x["at"] > now]
    for n in future:
        del entries[n]
    readies = [r for r in readies if r["at"] <= now]
    ends = [e for e in ends if e["at"] <= now]
    mgr_id = office.read_roster(d).get("manager")
    end, why = shift_end(state, now, ends, mgr_id)
    due = end - PLAN_LEAD_S
    slots = (state.get("rota") or {}).get("slots")
    _, w0, w1 = office.slot_at(slots, end - 1)
    window = max(w1 - w0, 2 * PLAN_LEAD_S)  # a ready counts for this shift when made within one slot's length of its end
    ready = next((r for r in reversed(readies) if end - window <= r["at"] and r.get("end") == end), None)
    unplanned = [n for n, x in entries.items() if x["status"] == "open"]
    pending = [n for n, x in entries.items() if x["status"] == "planned" and not x["approved"]]
    # planned, or planned again, after the plan file was written: the user has not been shown it
    late = [n for n in pending if not ready or n not in ready.get("ids", []) or entries[n]["plan"]["at"] > ready["at"]]
    if not ready or unplanned or late:
        word = "DUE" if now >= due else "OPEN"
    else:
        word = "READY" if pending else "APPROVED"
    try:
        inbox = len(waiting(events)[0])
    except Exception:  # another crew's file never breaks this journal
        inbox = 0
    undecided = [n for n, x in entries.items() if x["status"] == "planned" and x["carry"] is None and not x["origin"]] \
        if lessons() else []
    return {"now": now, "end": end, "end_why": why, "due": due, "state": word, "manager": mgr_id,
            "inbox": inbox, "undecided": undecided,
            "unplanned": unplanned, "pending": pending, "late": late, "ready_at": ready["at"] if ready else None,
            "file": ready.get("file") if ready else None, "skipped": skipped, "entries": entries, "readies": readies}


def warnings(d, state, now, manager_on=True):
    """board.py check's sentences: nothing before the due time, or with no manager on the clock."""
    if not manager_on:
        return []
    try:
        f = facts(d, state, now)
    except Exception as e:  # the journal never breaks the check
        return [f"The shift journal cannot be read ({type(e).__name__}: {e}); run `{P.tool('journal.py')} due`."]
    skipped_warn = ([f"The shift journal has {f['skipped']} malformed add line(s); run `{P.tool('journal.py')} due`."]
                     if f.get("skipped") else [])
    if now < f["due"] or f["state"] == "APPROVED":
        return skipped_warn
    at = f"due at {office.hhmm(f['due'], now)}, an hour before the end at {office.hhmm(f['end'], now)} ({f['end_why']})"
    if f["state"] == "READY":
        return skipped_warn + [f"The shift journal's action plan ({at}) is ready and waits for the user's approval of "
                               f"{ids_text(f['pending'])}: ask the user ({f['file']}), then `journal.py approve --words`."]
    todo = []
    if f["unplanned"]:
        todo.append(f"{ids_text(f['unplanned'])} with no plan (`journal.py plan` or `set`)")
    if f["late"] and f["ready_at"]:
        todo.append(f"{ids_text(f['late'])} planned after the plan file was written")
    return skipped_warn + [f"The shift journal's action plan ({at}) is not ready" + (": " + "; ".join(todo) if todo else "")
                           + ". Run `journal.py ready`, then ask the user to approve it."]


def end_shift_line(d, state, now):
    """One line for office.py end-shift, or '' when the plan is approved."""
    f = facts(d, state, now)
    if f["state"] == "APPROVED":
        return ""
    return (f"the shift journal is {f['state']}: {len(f['unplanned'])} with no plan, {len(f['pending'])} awaiting the "
            "user's approval (journal.py due); name it in the hand-off")


# --- lessons between crews ---

def carried(x):
    """A lesson leaves for another crew once its fix is known to hold here: fixed, or planned and approved."""
    return bool(x["carry"]) and (x["status"] == "fixed" or (x["status"] == "planned" and bool(x["approved"])))


def atomic_write(path, text):
    """Write text to path via a temp file and os.replace, as board.write_state does."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def write_outboxes(d, entries):
    """journal/carry-<crew>.jsonl in the office for each other crew: this crew's lessons for it, rewritten whole."""
    es = list(entries.values())
    for crew in sorted(set(lessons()) | {c for x in es for c in (x["carry"] or [])}):
        rows = [{"crew": me(), "id": x["id"], "kind": x["kind"], "what": x["what"],
                 "fix": (x["plan"] or {}).get("fix") or x["fix"], "where": x["where"],
                 "files": (x["plan"] or {}).get("files", ""),
                 "result": result_text(x) if x["status"] == "fixed" else "approved, not done yet",
                 "note": x["carry_note"], "at": x["touched"]}
                for x in es if carried(x) and crew in x["carry"]]
        f = d / "journal" / f"carry-{crew}.jsonl"
        if rows or f.exists():
            atomic_write(f, "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))


def read_pack(path, crew=""):
    """(the lessons in a pack file, why it could not be read or ''). A folder stands for its carry-<this crew>.jsonl."""
    p = Path(path)
    if not p.is_absolute():  # a path in the profile is written relative to the main checkout
        p = P.main / p
    if p.is_dir():
        p = next((q for q in (p / f"carry-{me()}.jsonl", p / "journal" / f"carry-{me()}.jsonl") if q.is_file()), p)
    if not p.is_file():
        return [], f"{path}: no such file yet"
    rows = []
    for l in p.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(l) if l.strip() else None
        except ValueError:
            continue
        if isinstance(r, dict) and r.get("id") and r.get("what"):
            r["crew"] = str(r.get("crew") or crew)
            if r["crew"] and r["crew"] != me():
                rows.append(r)
    return rows, ""


def waiting(events, sources=None):
    """(the lessons other crews carried here that this journal has not taken, notes on sources not read)."""
    taken = {(e["origin"].get("crew"), e["origin"].get("id")) for e in events if e.get("ev") == "add" and e.get("origin")}
    out, notes = [], []
    for crew, path in (sources if sources is not None else [(c, p) for c, ps in lessons().items() for p in ps]):
        rows, why = read_pack(path, crew)
        if why:
            notes.append(why)
        for r in rows:
            if (r["crew"], r["id"]) not in taken:
                taken.add((r["crew"], r["id"]))
                out.append(r)
    return out, notes


# --- text ---

def cell(s):
    return re.sub(r"\s+", " ", str(s or "")).replace("|", "\\|").strip() or "—"


def who(x):
    return (x["by"] + (f" for {x['src']}" if x["src"] else "")
            + (f" from {x['origin']['crew']} {x['origin']['id']}" if x["origin"] else ""))


def carry_text(x):
    if x["origin"]:
        return f"from {x['origin']['crew']}"
    return "?" if x["carry"] is None else (", ".join(x["carry"]) or "none")


def result_text(x):
    bits = [x["status"].upper()]
    if x["commit"]:
        bits.append(x["commit"])
    if x["of"]:
        bits.append(f"see {x['of']}")
    if x["note"]:
        bits.append(x["note"])
    return ": ".join([bits[0], ", ".join(bits[1:])]) if len(bits) > 1 else bits[0]


def line_of(x, now):
    tag = x["status"].upper() + (" (approved)" if x["approved"] else "")
    if x["carry"]:
        tag += f" (carries to {', '.join(x['carry'])}" + ("" if carried(x) else ", once fixed or approved") + ")"
    out = [f"{x['id']} {x['kind']} {tag} {office.hhmm(x['at'], now)} {who(x)}"
           + (f" [{x['where']}]" if x["where"] else "") + f": {x['what']}"]
    if x["plan"]:
        p = x["plan"]
        out.append("      plan: " + p["fix"] + (f" | files: {p['files']}" if p["files"] else "")
                   + (f" | how: {p['how']}" if p["how"] else "") + (f" | owner: {p['owner']}" if p["owner"] else ""))
    elif x["fix"]:
        out.append(f"      draft fix: {x['fix']}")
    if x["status"] in CLOSED + ("left",):
        out.append(f"      {result_text(x)}")
    return "\n".join(out)


def plan_rows(xs):
    others = bool(lessons())  # the last column: the other crews the lesson carries to (? = nobody decided)
    out = ["| Id | Kind | From | What | Fix | Files | How |" + (" Also for |" if others else ""),
           "|---|---|---|---|---|---|---|" + ("---|" if others else "")]
    for x in xs:
        p = x["plan"] or {}
        how = " / ".join(t for t in (p.get("how"), p.get("owner")) if t)
        out.append(f"| {x['id']} | {x['kind']} | {cell(who(x))} | {cell(x['what'])} | {cell(p.get('fix') or x['fix'])} "
                   f"| {cell(p.get('files'))} | {cell(how)} |" + (f" {carry_text(x)} |" if others else ""))
    return out


def result_rows(xs):
    out = ["| Id | Kind | From | What | Result |", "|---|---|---|---|---|"]
    for x in xs:
        out.append(f"| {x['id']} | {x['kind']} | {cell(who(x))} | {cell(x['what'])} | {cell(result_text(x))} |")
    return out


def plan_doc(f, mgr, now, since):
    """The plan file's text and the ids that wait for the user."""
    es = list(f["entries"].values())
    pending = [x for x in es if x["status"] == "planned" and not x["approved"]]
    approved = [x for x in es if x["status"] == "planned" and x["approved"]]
    left = [x for x in es if x["status"] == "left"]
    closed = [x for x in es if x["status"] in CLOSED and (x["closed_at"] or 0) > since]
    out = [f"# Shift journal action plan, {office.local(now):%Y-%m-%d %H:%M}",
           "",
           f"Written by {mgr['id']} {mgr['name']}. The shift ends at {office.hhmm(f['end'], now)} ({f['end_why']}); "
           f"the plan is due an hour before, at {office.hhmm(f['due'], now)}.",
           "",
           f"## For your approval ({len(pending)})",
           ""]
    out += plan_rows(pending) if pending else ["Nothing waits for approval."]
    if pending:
        out += ["", "To approve, tell the manager in your own words: all of it, or all but the ids you name. "
                    "The manager records your words with `journal.py approve`."]
    if approved:
        out += ["", f"## Approved earlier, not done yet ({len(approved)})", ""] + plan_rows(approved)
    if left:
        out += ["", f"## Left to an owner ({len(left)})", ""] + result_rows(left)
    out += ["", f"## Closed since the last plan ({len(closed)})", ""]
    out += result_rows(closed) if closed else ["None."]
    return "\n".join(out) + "\n", [x["n"] for x in pending]


def render_md(d, now):
    """journal/journal.md in the office: the live entries and the ones closed in the last day, for a person to open."""
    try:
        entries, _, _, _ = fold(read_j(d))
        es = list(entries.values())
        live = [x for x in es if x["status"] in LIVE]
        closed = [x for x in es if x["status"] in CLOSED and (x["closed_at"] or 0) > now - RECENT_S]
        out = [f"# Shift journal, as of {office.local(now):%Y-%m-%d %H:%M}", "",
               "Written by journal.py from journal.jsonl; edit neither by hand.", "",
               f"## Live ({len(live)})", "", "```"] + [line_of(x, now) for x in live] + ["```", "",
               f"## Closed in the last day ({len(closed)})", "", "```"] + [line_of(x, now) for x in closed] + ["```"]
        atomic_write(d / "journal" / "journal.md", "\n".join(out) + "\n")
        write_outboxes(d, entries)
    except OSError:
        pass  # the page is a convenience; the jsonl is the record


def text_arg(text, file, name):
    if text and file:
        raise office.Refused(f"--{name} and --{name}-file: give one")
    if file:
        p = Path(file)
        if not p.is_file():
            raise office.Refused(f"--{name}-file {file}: no such file")
        text = p.read_text(encoding="utf-8")
    return re.sub(r"\s+", " ", text or "").strip()


# --- the commands ---

def manager(d, line, now):
    """The manager's roster record when `line` is the manager on the clock; Refused otherwise. Call under the lock."""
    if not line:
        raise office.Refused("this is the manager's command: --by \"<the manager's badge line>\"")
    return office.manager_of(d, office.load_key(d), office.read_roster(d), line, office.crew(d, now))


def cmd_add(a, d, now):
    if a.kind not in KINDS:
        raise office.Refused(f"--kind is one of {', '.join(KINDS)}")
    if bool(a.badge) == bool(a.by):
        raise office.Refused("give --badge (your own line) or --by (the manager's line), one of them")
    what = text_arg(a.what, a.what_file, "what")
    fix = text_arg(a.fix, a.fix_file, "fix")
    if not what:
        raise office.Refused("--what says what happened (one or two sentences)")
    carry = parse_crews(a.carry) if a.carry else None
    with office.locked(d):
        if a.by:
            rec = manager(d, a.by, now)
        else:
            rec = office.verify_line(office.load_key(d), office.read_roster(d), a.badge)
            if a.src:
                raise office.Refused("--from is the manager's (it logs an entry for a crew member); log your own with --badge")
        if a.src and a.src not in office.read_roster(d)["badges"]:
            raise office.Refused(f"--from {a.src}: no such badge")
        n = len(fold(read_j(d))[0]) + 1
        append_j(d, {"at": now, "ev": "add", "by": rec["id"], "role": rec["role"], "kind": a.kind, "what": what,
                     **({"fix": fix} if fix else {}), **({"where": a.where} if a.where else {}),
                     **({"src": a.src} if a.src else {}), **({"carry": carry} if carry is not None else {})})
        render_md(d, now)
    print(f"J{n} logged by {rec['id']} ({a.kind}): {what}")
    if not fix:
        print("  no draft fix given: the manager plans it from the entry alone")
    return 0


def cmd_mine(a, d, now):
    rec = office.verify_line(office.load_key(d), office.read_roster(d), a.badge)
    entries, _, _, _ = fold(read_j(d))
    mine = [x for x in entries.values() if rec["id"] in (x["by"], x["src"])]
    if not mine:
        print(f"{rec['id']} has no journal entry (journal.py add --badge ... --kind hole --what ... --fix ...)")
        return 0
    for x in mine:
        print(line_of(x, now))
    return 0


def show_named(a, d, now):
    """the read-only form for anyone with a genuine badge (on the roster, not revoked): the named entries only,
    open or closed. It writes nothing and needs no lock."""
    if a.by:
        raise office.Refused("give --badge (your own line) or --by (the manager's line), one of them")
    if a.all:
        raise office.Refused("--all is the manager's full listing; with --badge, name the entries (J29,J32)")
    if not a.ids:
        raise office.Refused("with --badge, name the entries to read: show --badge \"<your line>\" J29,J32")
    office.verify_line(office.load_key(d), office.read_roster(d), a.badge)
    entries, _, _, _ = fold(read_j(d))
    es = [entries[n] for n in parse_ids(a.ids, entries)]
    if a.json:
        print(json.dumps({"entries": es}, indent=1, ensure_ascii=False))
        return 0
    for x in es:
        print(line_of(x, now))
    return 0


def cmd_show(a, d, now):
    if a.badge:
        return show_named(a, d, now)
    if not a.by:
        raise office.Refused("show --by \"<the manager's line>\" lists every live entry; anyone else reads named "
                         "entries with show --badge \"<your line>\" J29,J32")
    with office.locked(d):
        manager(d, a.by, now)
    f = facts(d, office.read_state(), now)
    es = ([f["entries"][n] for n in parse_ids(a.ids, f["entries"])] if a.ids
          else [x for x in f["entries"].values() if a.all or x["status"] in LIVE])
    if a.json:
        print(json.dumps({**{k: f[k] for k in ("state", "end", "due", "unplanned", "pending", "file")}, "entries": es},
                         indent=1, ensure_ascii=False))
        return 0
    print(due_text(f, now))
    for x in es:
        print(line_of(x, now))
    if not es:
        print("no live entry" + ("" if a.all else " (--all lists the closed ones)"))
    return 0


def cmd_plan(a, d, now):
    fix = text_arg(a.fix, None, "fix")
    if not fix:
        raise office.Refused("--fix says what will be done")
    carry = parse_crews(a.carry) if a.carry else None
    with office.locked(d):
        rec = manager(d, a.by, now)
        entries, _, _, _ = fold(read_j(d))
        ids = parse_ids(a.ids, entries)
        check_carry(entries, ids, carry)
        shut = [n for n in ids if entries[n]["status"] in CLOSED]
        if shut:
            raise office.Refused(f"{ids_text(shut)} closed already ({', '.join(entries[n]['status'] for n in shut)}); "
                             "reopen it first (set --status open) or log a new entry")
        was = [n for n in ids if entries[n]["approved"]]
        append_j(d, {"at": now, "ev": "plan", "by": rec["id"], "ids": ids, "fix": fix, "files": a.files or "",
                     "how": a.how or "", "owner": a.owner or "", **({"carry": carry} if carry is not None else {})})
        render_md(d, now)
    print(f"planned {ids_text(ids)}: {fix}")
    if was:
        print(f"  {ids_text(was)} had the user's approval of the earlier plan; it is cleared: run `ready` and ask again")
    return 0


def cmd_set(a, d, now):
    st = a.status
    if st not in CLOSED + ("left", "open"):
        raise office.Refused(f"--status is one of {', '.join(CLOSED + ('left', 'open'))}")
    note = text_arg(a.note, None, "note")
    if st == "fixed" and not (a.commit or note):
        raise office.Refused("fixed: name what fixed it (--commit SHA, or --note for a fix outside git)")
    if st == "covered" and not (a.of or note):
        raise office.Refused("covered: name the entry it repeats (--of J3) or the rule that already says it (--note)")
    if st in ("dropped", "left") and not note:
        raise office.Refused(f"{st}: --note says " + ("why" if st == "dropped" else "to whom (an owner, or the next slot) and why"))
    if a.commit and not hasattr(office, "git"):
        raise office.Refused("this crew keeps no git: fixed takes --note (the stage folder or file that holds the fix)")
    if a.commit and office.git(["rev-parse", "--verify", "--quiet", a.commit + "^{commit}"], office.ROOT)[0] != 0:
        raise office.Refused(f"--commit {a.commit}: this repo does not hold it; read the sha from the commit's own output")
    with office.locked(d):
        rec = manager(d, a.by, now)
        entries, _, _, _ = fold(read_j(d))
        ids = parse_ids(a.ids, entries)
        of = ""
        if a.of:
            of = ids_text(parse_ids(a.of, entries))
            if set(parse_ids(a.of, entries)) & set(ids):
                raise office.Refused("--of names the entry itself")
        append_j(d, {"at": now, "ev": "status", "by": rec["id"], "ids": ids, "set": st,
                     **({"note": note} if note else {}), **({"commit": a.commit} if a.commit else {}),
                     **({"of": of} if of else {})})
        render_md(d, now)
    print(f"{ids_text(ids)}: {st}" + (f" ({a.commit})" if a.commit else "") + (f"; {note}" if note else ""))
    return 0


def due_text(f, now):
    head = (f"shift journal {f['state']}: the plan is due at {office.hhmm(f['due'], now)}, an hour before the end at "
            f"{office.hhmm(f['end'], now)} ({f['end_why']})")
    if f["state"] in ("OPEN", "DUE"):
        left = f["due"] - now
        head += f"; {'in ' + office.ago(left) if left > 0 else office.ago(-left) + ' ago'}"
    lines = [head]
    if f.get("skipped"):
        lines.append(f"  {f['skipped']} journal line(s) skipped (malformed add)")
    if f["unplanned"]:
        lines.append(f"  no plan yet: {ids_text(f['unplanned'])}")
    if f["pending"]:
        lines.append(f"  planned, awaiting the user's approval: {ids_text(f['pending'])}"
                     + (f" ({ids_text(f['late'])} not in the plan file yet: run ready again)" if f["late"] and f["ready_at"] else ""))
    if f["file"]:
        lines.append(f"  plan file ({office.hhmm(f['ready_at'], now)}): {f['file']}")
    if f["undecided"]:
        lines.append(f"  no word yet on whether it also holds for {', '.join(sorted(lessons()))}: {ids_text(f['undecided'])} "
                     "(journal.py carry J.. --to <crew>|none)")
    if f["inbox"]:
        lines.append(f"  {f['inbox']} lesson{'s' if f['inbox'] != 1 else ''} from {', '.join(sorted(lessons()))} "
                     "wait to be taken (journal.py take --list, then take)")
    return "\n".join(lines)


def check_carry(entries, ids, to):
    back = [n for n in ids if to and entries[n]["origin"] and entries[n]["origin"]["crew"] in to]
    if back:
        raise office.Refused(f"{ids_text(back)} came from {entries[back[0]]['origin']['crew']}; it does not carry back there")


def cmd_carry(a, d, now):
    to = parse_crews(a.to)
    note = text_arg(a.note, None, "note")
    with office.locked(d):
        rec = manager(d, a.by, now)
        entries, _, _, _ = fold(read_j(d))
        ids = parse_ids(a.ids, entries)
        check_carry(entries, ids, to)
        append_j(d, {"at": now, "ev": "carry", "by": rec["id"], "ids": ids, "to": to, **({"note": note} if note else {})})
        entries, _, _, _ = fold(read_j(d))
        render_md(d, now)
    print(f"{ids_text(ids)}: " + (f"also holds for {', '.join(to)}" if to else "this crew only"))
    if to:
        gone = [n for n in ids if carried(entries[n])]
        held = [n for n in ids if n not in gone]
        if gone:
            print(f"  in the outbox now ({ids_text(gone)}): " + ", ".join((d / 'journal' / f'carry-{c}.jsonl').as_posix() for c in to))
        if held:
            print(f"  {ids_text(held)} reaches the outbox once it is fixed, or planned and approved by the user")
    return 0


def cmd_take(a, d, now):
    if a.max < 1:
        raise office.Refused("--max is at least 1")
    with office.locked(d):
        rec = manager(d, a.by, now)
        events = read_j(d)
        rows, notes = waiting(events, [(a.crew or "", a.src)] if a.src else None)
        if a.src and notes:
            raise office.Refused(notes[0])
        if not a.src and not lessons():
            raise office.Refused("this office names no other crew (the profile's [crews] table); give --from FILE --crew NAME")
        for why in notes:
            print(f"  not read: {why}")
        if not rows:
            print("no lesson from another crew waits")
            return 0
        if a.list:
            for r in rows:
                print(f"{r['crew']} {r['id']} {r.get('kind', '')}: {r['what']}")
            print(f"{len(rows)} wait; `take` brings in the first {min(a.max, len(rows))} as open entries")
            return 0
        n = len(fold(events)[0])
        got = []
        for r in rows[:a.max]:
            form = r.get("form") or r.get(f"{me()}_form") or ""
            fix = " ".join(t for t in (f"{r['crew']}'s fix: {r['fix']}" if r.get("fix") else "",
                                       f"({r['result']})" if r.get("result") else "",
                                       f"Here: {form}" if form else "", f"Note: {r['note']}" if r.get("note") else "") if t)
            where = r.get("target") or r.get("where") or ""
            where = ", ".join(where) if isinstance(where, list) else str(where)
            kind = r.get("kind") if r.get("kind") in KINDS else "improvement"
            n += 1
            append_j(d, {"at": now, "ev": "add", "by": rec["id"], "role": rec["role"], "kind": kind,
                         "what": re.sub(r"\s+", " ", str(r["what"])).strip(), **({"fix": fix} if fix else {}),
                         **({"where": where} if where else {}), "origin": {"crew": r["crew"], "id": str(r["id"])}})
            got.append(f"J{n} taken from {r['crew']} {r['id']} ({kind}): {r['what']}")
        render_md(d, now)
    print("\n".join(got))
    print(f"  each is open: plan it in this crew's form (plan), or close it: covered (--note names the rule that already "
          f"says it) or dropped (--note says why it cannot happen here)")
    if len(rows) > len(got):
        print(f"  {len(rows) - len(got)} more wait (journal.py take)")
    return 0


def cmd_due(a, d, now):
    if a.end:
        with office.locked(d):
            rec = manager(d, a.by, now)
            end = office.parse_eta(a.end, now)
            if end <= now:
                raise office.Refused(f"--end {a.end} is not ahead of now")
            append_j(d, {"at": now, "ev": "end", "by": rec["id"], "end": end})
    f = facts(d, office.read_state(), now)
    print(due_text(f, now))
    if a.end:
        print(f"  make a one-shot timer for {office.hhmm(f['due'], now)} (journal.py ready, then ask the user)")
    return 0


def cmd_ready(a, d, now):
    state = office.read_state()
    with office.locked(d):
        rec = manager(d, a.by, now)
        f = facts(d, state, now)
        if f["unplanned"]:
            raise office.Refused(f"{ids_text(f['unplanned'])} has no plan: plan each (journal.py plan J.. --fix ...) or "
                             "close it (set --status covered|dropped|left|fixed), then run ready again")
        since = f["readies"][-1]["at"] if f["readies"] else now - RECENT_S
        text, ids = plan_doc(f, rec, now, since)
        (d / "journal").mkdir(parents=True, exist_ok=True)
        out = d / "journal" / f"plan-{office.local(now):%Y%m%d-%H%M}-{rec['id']}.md"
        out.write_text(text, encoding="utf-8", newline="\n")
        append_j(d, {"at": now, "ev": "ready", "by": rec["id"], "ids": ids, "file": out.as_posix(),
                     "end": f["end"], "due": f["due"]})
        render_md(d, now)
    late = now - f["due"]
    print(f"plan ready at {office.hhmm(now, now)} ({office.ago(late) + ' past its due time' if late > 60 else 'on time'}): {out.as_posix()}")
    if ids:
        print(f"  {len(ids)} for the user's approval: {ids_text(ids)}")
        print("  ask the user now, with the file; then: journal.py approve --by \"<your line>\" --words \"<their own words>\"")
    else:
        print("  nothing waits for approval; name the file in the hand-off")
    if f["undecided"]:
        print(f"  no word yet on whether it also holds for {', '.join(sorted(lessons()))}: {ids_text(f['undecided'])} "
              "(journal.py carry J.. --to <crew>|none); the plan file shows these as ?")
    return 0


def cmd_approve(a, d, now):
    words = text_arg(a.words, None, "words")
    if len(words) < 2:
        raise office.Refused("--words quotes the user's own words of approval (a timer's or a session's text is not the user's)")
    with office.locked(d):
        rec = manager(d, a.by, now)
        f = facts(d, office.read_state(), now)
        entries = f["entries"]
        if not f["ready_at"]:
            raise office.Refused("no ready plan for this shift: run journal.py ready first, so the user approves a file they can read")
        asked = [n for n in f["pending"] if n not in f["late"]]
        if a.only and a.exc:
            raise office.Refused("--only and --except: give one")
        ids = asked
        if a.only:
            ids = parse_ids(a.only, entries)
            off = [n for n in ids if n not in asked]
            if off:
                raise office.Refused(f"{ids_text(off)} is not in the ready plan awaiting approval ({ids_text(asked)})")
        elif a.exc:
            skip = parse_ids(a.exc, entries)
            ids = [n for n in asked if n not in skip]
        if not ids:
            raise office.Refused("nothing in the ready plan waits for approval" + (f" ({ids_text(f['late'])} was planned "
                             "after the plan file was written: run ready again)" if f["late"] else ""))
        append_j(d, {"at": now, "ev": "approve", "by": rec["id"], "ids": ids, "words": words})
        render_md(d, now)
    rest = [n for n in f["pending"] if n not in ids]
    print(f"approved by the user ({words!r}): {ids_text(ids)}")
    if rest:
        print(f"  not approved: {ids_text(rest)}; plan it again, leave it (set --status left) or drop it, on the user's words")
    return 0


# --- selftest ---

def remove_tree(path):
    """Remove a temp folder and all in it. A file that is read-only (git's objects on Windows) is made writable and
    tried once more; what still cannot go is left, never an error."""
    import shutil

    def retry(func, p, _exc):
        try:
            os.chmod(p, 0o700)
            func(p)
        except OSError:
            pass

    if sys.version_info >= (3, 12):  # onexc came with 3.12, where onerror is deprecated
        shutil.rmtree(path, onexc=retry)
    else:
        shutil.rmtree(path, onerror=retry)


def selftest():
    """Every check runs in one temp folder, which is removed at the end whether they pass or not."""
    import tempfile
    tmp = Path(tempfile.mkdtemp(prefix="foundry-journal-selftest-")).resolve()  # its real name, so paths compare
    try:
        code = _selftest(tmp)
    finally:
        remove_tree(tmp)
    if tmp.exists():
        print(f"FAIL the selftest left its temp folder behind: {tmp}")
        return 1
    return code


def _selftest(tmp):
    state = {"shift": {"id": "test-shift", "crew_max": 3}, "rota": {"slots": office.DEFAULT_SLOTS}}
    (tmp / "state.json").write_text(json.dumps(state), encoding="utf-8")
    d = tmp / "office"
    d3 = tmp / "office-other"  # a second crew's office, for the lessons that pass between them
    crews = {"FOUNDRY_CREW": "home", "FOUNDRY_LESSONS": json.dumps({"other": str(d3 / "journal" / "carry-home.jsonl")})}
    env = {**os.environ, "FOUNDRY_PATHS_OFFICE": str(tmp / "office"), "FOUNDRY_PATHS_STATE": str(tmp / "state.json"), **crews}
    os.environ.update(crews)  # facts() and warnings() are also called in this process
    office_text = (Path(__file__).resolve().parent / "office.py").read_text(encoding="utf-8")
    this_slot = ["--this-slot"] if "--this-slot" in office_text else []  # an older office.py appoints for the slot now
    # the clock starts 5 h before a slot's end, so the plan is due 4 h in
    _, _, s1 = office.slot_at(office.DEFAULT_SLOTS, 1_800_000_000.0)
    t0 = s1 - 5 * 3600
    due = 4 * 3600
    ok, bad = [], []
    here = str(Path(__file__).resolve())
    officepy = str(Path(__file__).resolve().parent / "office.py")

    def run(script, *args, at=0.0, e=None):
        r = subprocess.run([sys.executable, script, *args], capture_output=True, text=True, encoding="utf-8",
                           env={**(e or env), "FOUNDRY_NOW": str(t0 + at)}, timeout=60)
        return r.returncode, r.stdout + r.stderr

    def j(*args, at=0.0, e=None):
        return run(here, *args, at=at, e=e)

    def expect(what, cond, detail=""):
        (ok if cond else bad).append(what + ("" if cond else f": {str(detail).strip()[:400]}"))

    def badge_of(out):
        return next(l[len("badge: "):] for l in out.splitlines() if l.startswith("badge: "))

    def warns(at, on=True):
        return warnings(d, json.loads((tmp / "state.json").read_text(encoding="utf-8")), t0 + at, on)

    def stand(at):
        os.environ["FOUNDRY_PATHS_OFFICE"] = str(d)
        try:
            return facts(d, json.loads((tmp / "state.json").read_text(encoding="utf-8")), t0 + at)["state"]
        finally:
            os.environ.pop("FOUNDRY_PATHS_OFFICE", None)

    os.environ["FOUNDRY_PATHS_OFFICE"] = str(d)  # warnings() reads the roster through the office
    _, out = run(officepy, "appoint", "--name", "mgr-a", *this_slot)
    mgr = badge_of(out)
    run(officepy, "clock-in", "--badge", mgr, at=10)
    _, out = run(officepy, "hire", "--by", mgr, "--name", "b1", "--role", "builder", "--kind", "session", "--job", "x", "--eta", "60m", at=20)
    b1 = badge_of(out)
    _, out = run(officepy, "hire", "--by", mgr, "--name", "r1", "--role", "reviewer", "--kind", "temp", "--job", "y", "--eta", "60m", at=21)
    r1 = badge_of(out)
    run(officepy, "clock-in", "--badge", b1, at=30)

    rc, out = j("due", at=40)
    expect("an empty journal before the due time reads OPEN", rc == 0 and "shift journal OPEN" in out, out)
    expect("no warning before the due time", warns(40) == [], warns(40))

    # the crew's limited form
    rc, out = j("add", "--badge", b1, "--kind", "hole", "--what", "the brief names a file that is vendored",
                "--fix", "hire warns on vendored paths", "--where", "office.py hire", at=100)
    expect("an employee logs an entry with its badge", rc == 0 and out.startswith("J1 logged by EMP-01 (hole)"), out)
    rc, out = j("add", "--badge", b1.replace("ROLE:BUILDER", "ROLE:MANAGER"), "--kind", "hole", "--what", "x", at=101)
    expect("a tampered line is refused", rc != 0 and "signature" in out, out)
    rc, out = j("add", "--badge", b1, "--kind", "bug", "--what", "x", at=102)
    expect("an unknown kind is refused", rc != 0 and "--kind is one of" in out, out)
    rc, out = j("add", "--badge", b1, "--kind", "hole", "--what", "  ", at=103)
    expect("an entry with no text is refused", rc != 0 and "--what" in out, out)
    rc, out = j("add", "--badge", b1, "--kind", "hole", "--what", "x", "--from", "EMP-02", at=104)
    expect("--from is the manager's", rc != 0 and "--from is the manager's" in out, out)
    for cmd in (("plan", "J1", "--fix", "x"), ("set", "J1", "--status", "dropped", "--note", "x"), ("ready",),
                ("approve", "--words", "yes do it"), ("show",), ("due", "--end", "23:00")):
        rc, out = j(cmd[0], "--by", b1, *cmd[1:], at=105)
        expect(f"an employee's line is refused for `{cmd[0]}`", rc != 0 and "not the current manager" in out, out)
    rc, out = j("add", "--badge", r1, "--kind", "improvement", "--what", "reviewer briefs could name the diff command", at=110)
    expect("a temp that never clocked in may still log (a genuine badge is enough)", rc == 0 and out.startswith("J2 "), out)
    rc, out = j("mine", "--badge", b1, at=111)
    expect("mine lists the employee's own entries only", rc == 0 and "J1 hole OPEN" in out and "J2" not in out, out)
    # the read-only show for an employee: the named entries only
    rc, out = j("show", "--badge", b1, "J2", at=112)
    expect("an employee reads a named entry with its badge", rc == 0 and "J2 improvement OPEN" in out
           and "reviewer briefs could name the diff command" in out and "J1 " not in out, out)
    rc, out = j("show", "--badge", b1, at=112)
    expect("an employee's show names the entries", rc != 0 and "name the entries" in out, out)
    rc, out = j("show", "--badge", b1, "--all", "J1", at=112)
    expect("--all stays the manager's", rc != 0 and "--all is the manager's" in out, out)
    rc, out = j("show", "--badge", b1, "J9", at=112)
    expect("an unknown id is refused", rc != 0 and "no journal entry J9" in out, out)
    rc, out = j("show", "--badge", b1.replace("ROLE:BUILDER", "ROLE:MANAGER"), "J1", at=112)
    expect("a tampered line is refused for show", rc != 0 and "signature" in out, out)
    rc, out = j("show", "J1", at=112)
    expect("show with neither line is refused", rc != 0 and "--badge" in out, out)
    roster_f = d / "roster.json"
    roster_text = roster_f.read_text(encoding="utf-8")
    ro = json.loads(roster_text)
    ro["badges"][office.parse_line(r1)[0]["ID"]].update(revoked=t0 + 112, revoked_why="selftest")
    roster_f.write_text(json.dumps(ro), encoding="utf-8")
    rc, out = j("show", "--badge", r1, "J2", at=113)
    expect("a revoked badge is refused for show", rc != 0 and "revoked" in out, out)
    roster_f.write_text(roster_text, encoding="utf-8")
    n_lines = len(jfile(d).read_text(encoding="utf-8").splitlines())
    expect("refused commands write nothing", n_lines == 2, n_lines)

    # the manager's
    whatf = tmp / "what.txt"
    whatf.write_text("I queued a job with a compound\nduration and the queue refused it", encoding="utf-8")
    rc, out = j("add", "--by", mgr, "--kind", "failure", "--what-file", str(whatf), "--fix", "rq reads XhYm", at=120)
    expect("the manager logs its own failure, text from a file, on one line",
           rc == 0 and "J3 logged by MGR-1 (failure): I queued a job with a compound duration and the queue" in out, out)
    rc, out = j("add", "--by", mgr, "--kind", "hole", "--what", "same as J1, from the hand-in", "--from", "EMP-01", at=121)
    expect("the manager logs for a crew member", rc == 0 and out.startswith("J4 "), out)
    rc, out = j("add", "--by", mgr, "--kind", "hole", "--what", "x", "--from", "EMP-77", at=122)
    expect("--from an unknown badge is refused", rc != 0 and "no such badge" in out, out)
    rc, out = j("mine", "--badge", b1, at=123)
    expect("mine also lists entries logged for the employee", "J4" in out and "J3" not in out, out)
    rc, out = j("show", "--by", mgr, at=124)
    expect("show lists the live entries and where the plan stands",
           rc == 0 and all(f"J{n} " in out for n in (1, 2, 3, 4)) and "no plan yet: J1, J2, J3, J4" in out
           and "draft fix: rq reads XhYm" in out, out)

    rc, out = j("ready", "--by", mgr, at=130)
    expect("ready is refused while an entry has no plan, and names them", rc != 0 and "J1, J2, J3, J4 has no plan" in out, out)
    rc, out = j("plan", "--by", mgr, "J1,J3", "--fix", "one builder: hire warns; rq duration parser", "--files",
                "tools/office.py, tools/rq.py", "--how", "builder", at=140)
    expect("plan takes a list of ids", rc == 0 and "planned J1, J3" in out, out)
    rc, out = j("plan", "--by", mgr, "J9", "--fix", "x", at=141)
    expect("an unknown id is refused", rc != 0 and "no journal entry J9" in out, out)
    rc, out = j("set", "--by", mgr, "J4", "--status", "covered", at=142)
    expect("covered needs --of or --note", rc != 0 and "covered:" in out, out)
    rc, out = j("set", "--by", mgr, "J4", "--status", "covered", "--of", "J4", at=143)
    expect("--of the entry itself is refused", rc != 0 and "itself" in out, out)
    rc, out = j("set", "--by", mgr, "J4", "--status", "covered", "--of", "J1", at=144)
    expect("a duplicate is covered by the first", rc == 0 and "J4: covered" in out, out)
    rc, out = j("set", "--by", mgr, "J2", "--status", "dropped", at=145)
    expect("dropped needs a reason", rc != 0 and "--note says why" in out, out)
    rc, out = j("set", "--by", mgr, "J2", "--status", "fixed", at=146)
    expect("fixed needs a commit or a note", rc != 0 and "fixed:" in out, out)
    rc, out = j("set", "--by", mgr, "J2", "--status", "fixed", "--commit", "0123456789abcdef0123456789abcdef01234567", at=147)
    expect("a commit the repo does not hold is refused (a crew with no git: any commit)",
           rc != 0 and ("does not hold" in out if hasattr(office, "git") else "keeps no git" in out), out)
    rc, out = j("set", "--by", mgr, "J2", "--status", "left", "--note", "to the next slot's manager: brief template", at=148)
    expect("left names an owner", rc == 0 and "J2: left" in out, out)
    rc, out = j("plan", "--by", mgr, "J4", "--fix", "x", at=149)
    expect("a closed entry is not planned again", rc != 0 and "closed already" in out, out)

    expect("past the due time with no ready plan, the check warns",
           len(warns(due + 60)) == 1 and "is not ready" in warns(due + 60)[0], warns(due + 60))
    expect("no warning with no manager on the clock", warns(due + 60, on=False) == [])
    expect("the state reads OPEN before the due time and DUE after", stand(due - 60) == "OPEN" and stand(due + 60) == "DUE")

    rc, out = j("approve", "--by", mgr, "--words", "yes, go", at=due - 700)
    expect("approve before ready is refused", rc != 0 and "no ready plan" in out, out)
    rc, out = j("ready", "--by", mgr, at=due - 600)
    plan_file = next(iter(sorted((d / "journal").glob("plan-*.md"))), None)
    text = plan_file.read_text(encoding="utf-8") if plan_file else ""
    expect("ready writes the plan file and says who to ask",
           rc == 0 and "on time" in out and "2 for the user's approval: J1, J3" in out and plan_file is not None, out)
    expect("the plan file has the approval table, the left entry and the closed one",
           "## For your approval (2)" in text and "| J1 | hole | EMP-01 |" in text and "tools/office.py, tools/rq.py" in text
           and "## Left to an owner (1)" in text and "| J2 |" in text and "COVERED: see J1" in text, text)
    expect("a ready plan awaiting approval warns after the due time, not before",
           warns(due - 500) == [] and len(warns(due + 60)) == 1 and "waits for the user's approval of J1, J3" in warns(due + 60)[0],
           warns(due + 60))
    rc, out = j("approve", "--by", mgr, "--words", " ", at=due - 400)
    expect("approval needs the user's words", rc != 0 and "user's own words" in out, out)
    rc, out = j("approve", "--by", mgr, "--words", "yes", "--only", "J2", at=due - 399)
    expect("approving an entry outside the plan is refused", rc != 0 and "not in the ready plan" in out, out)
    rc, out = j("approve", "--by", mgr, "--words", "approve all but the queue one", "--except", "J3", at=due - 390)
    expect("the user approves all but one", rc == 0 and "approved by the user" in out and ": J1" in out
           and "not approved: J3" in out, out)
    expect("one entry still unapproved keeps the plan READY", stand(due - 380) == "READY")
    rc, out = j("set", "--by", mgr, "J3", "--status", "dropped", "--note", "the user: not now", at=due - 370)
    expect("with the rest dropped on the user's word the plan is APPROVED, and the check is quiet",
           rc == 0 and stand(due + 60) == "APPROVED" and warns(due + 60) == [], warns(due + 60))

    rc, out = j("plan", "--by", mgr, "J1", "--fix", "a different fix", at=due - 300)
    expect("planning an approved entry again clears its approval",
           rc == 0 and "it is cleared" in out and stand(due + 60) == "DUE", out)
    rc, out = j("ready", "--by", mgr, at=due + 120)
    expect("a late ready says how late", rc == 0 and "past its due time" in out, out)
    rc, out = j("approve", "--by", mgr, "--words", "ok", at=due + 130)
    expect("approve takes the whole ready plan", rc == 0 and ": J1" in out and stand(due + 140) == "APPROVED", out)
    rc, out = j("add", "--badge", b1, "--kind", "hole", "--what", "a late one", at=due + 200)
    expect("an entry logged after the plan makes it DUE again", rc == 0 and stand(due + 210) == "DUE")
    rc, out = j("plan", "--by", mgr, "J5", "--fix", "y", at=due + 220)
    rc, out = j("approve", "--by", mgr, "--words", "ok", at=due + 230)
    expect("an entry planned after the plan file cannot be approved until ready runs again",
           rc != 0 and "run ready again" in out, out)
    rc, out = run(officepy, "end-shift", "--by", mgr, at=due + 240)
    if "journal.end_shift_line" in office_text:
        expect("office.py end-shift names a journal that is not approved", rc == 0 and "the shift journal is DUE" in out, out)
    rc, out = j("set", "--by", mgr, "J5", "--status", "fixed", "--note", "an office file, not in git", at=due + 250)
    rc, out = j("set", "--by", mgr, "J5", "--status", "open", at=due + 260)
    rc2, out2 = j("show", "--by", mgr, "--json", at=due + 261)
    js = json.loads(out2) if rc2 == 0 else {}
    expect("a reopened entry keeps its plan and reads planned",
           rc == 0 and next((x["status"] for x in js.get("entries", []) if x["id"] == "J5"), "") == "planned", out2)
    rc, out = j("ready", "--by", mgr, at=due + 300)
    text = sorted((d / "journal").glob("plan-*.md"))[-1].read_text(encoding="utf-8")
    expect("the next plan lists the approved entry as carried and the new one for approval",
           rc == 0 and "## Approved earlier, not done yet (1)" in text and "## For your approval (1)" in text
           and "| J5 |" in text and "| J3 |" not in text, text)
    expect("journal.md is written for a person", (d / "journal" / "journal.md").is_file()
           and "J1 hole PLANNED (approved)" in (d / "journal" / "journal.md").read_text(encoding="utf-8"))

    # lessons between crews: J1 is planned and approved, J5 planned and not approved, J2 left, J3 dropped, J4 covered
    T = due + 400
    outbox = d / "journal" / "carry-other.jsonl"

    def box():
        return [json.loads(l) for l in outbox.read_text(encoding="utf-8").splitlines()] if outbox.is_file() else None

    expect("the plan file marks an entry nobody decided on with ?", "Also for |" in text and "| ? |" in text, text)
    rc, out = j("ready", "--by", mgr, at=T)
    expect("ready names the entries with no carry decision", rc == 0 and "also holds for other: J1, J5" in out, out)
    rc, out = j("carry", "--by", mgr, "J1,J5", "--to", "mars", at=T + 1)
    expect("carrying to an unknown crew is refused", rc != 0 and "This office knows other" in out, out)
    rc, out = j("carry", "--by", b1, "J1", "--to", "other", at=T + 2)
    expect("an employee's line is refused for `carry`", rc != 0 and "not the current manager" in out, out)
    rc, out = j("take", "--by", b1, at=T + 3)
    expect("an employee's line is refused for `take`", rc != 0 and "not the current manager" in out, out)
    rc, out = j("carry", "--by", mgr, "J1,J5", "--to", "other", "--note", "their form: a stage folder", at=T + 4)
    expect("an approved entry reaches the other crew's outbox; one not approved waits",
           rc == 0 and "in the outbox now (J1)" in out and "J5 reaches the outbox once" in out
           and [r["id"] for r in box() or []] == ["J1"] and box()[0]["crew"] == "home", out)
    rc, out = j("carry", "--by", mgr, "J3", "--to", "other", at=T + 5)
    expect("a dropped entry never leaves", rc == 0 and [r["id"] for r in box()] == ["J1"], box())
    rc, out = j("add", "--badge", b1, "--kind", "improvement", "--what", "name the report file in the brief", "--carry", "other", at=T + 6)
    expect("an employee may say a lesson is general when it logs it", rc == 0 and out.startswith("J6 "), out)
    rc, out = j("plan", "--by", mgr, "J6", "--fix", "brief template line", "--carry", "none", at=T + 7)
    rc2, out2 = j("show", "--by", mgr, at=T + 8)
    expect("plan --carry none overrides it", rc == 0 and "J6 improvement PLANNED " in out2 and "J1 hole PLANNED (approved) (carries to other)" in out2
           and "J5 hole PLANNED (carries to other, once fixed or approved)" in out2, out2)

    # the other crew takes them
    env3 = {**env, "FOUNDRY_PATHS_OFFICE": str(d3), "FOUNDRY_CREW": "other",
            "FOUNDRY_LESSONS": json.dumps({"home": [str(outbox), str(tmp / "backlog.jsonl"), str(tmp / "missing.jsonl")]})}
    (tmp / "backlog.jsonl").write_text(
        json.dumps({"crew": "home", "id": "B-08", "kind": "hole", "what": "nothing may change in main during a counted run",
                    "fix": "freeze rule", "where": "manager SKILL.md", "other_form": "no stage install during a counted run",
                    "target": ["manager SKILL.md", "office.py"]}) + "\n"
        + json.dumps({"crew": "other", "id": "X1", "what": "its own lesson"}) + "\n{torn\n", encoding="utf-8")
    _, out = run(officepy, "appoint", "--name", "mgr-o", *this_slot, at=T + 10, e=env3)
    mgr3 = badge_of(out)
    run(officepy, "clock-in", "--badge", mgr3, at=T + 11, e=env3)
    rc, out = j("take", "--by", mgr3, "--list", at=T + 12, e=env3)
    expect("take --list shows what waits and writes nothing", rc == 0 and "home J1 hole:" in out and "home B-08 hole:" in out
           and "2 wait" in out and "missing.jsonl: no such file yet" in out and "X1" not in out and not jfile(d3).exists(), out)
    rc, out = j("due", at=T + 13, e=env3)
    expect("due counts the lessons that wait", rc == 0 and "2 lessons from home wait" in out, out)
    rc, out = j("take", "--by", mgr3, "--max", "1", at=T + 14, e=env3)
    expect("take brings in the first as an open entry", rc == 0 and "J1 taken from home J1 (hole)" in out and "1 more wait" in out, out)
    rc, out = j("take", "--by", mgr3, at=T + 15, e=env3)
    rc2, out2 = j("show", "--by", mgr3, at=T + 16, e=env3)
    expect("a backlog pack's lesson comes with the fix in this crew's form and its target files",
           rc == 0 and "J2 taken from home B-08" in out and "from home B-08 [manager SKILL.md, office.py]" in out2
           and "home's fix: freeze rule Here: no stage install during a counted run" in out2
           and "Note: their form: a stage folder" in out2 and "no plan yet: J1, J2" in out2, out2)
    rc, out = j("take", "--by", mgr3, at=T + 17, e=env3)
    expect("a lesson is taken once", rc == 0 and "no lesson from another crew waits" in out, out)
    rc, out = j("carry", "--by", mgr3, "J1", "--to", "home", at=T + 18, e=env3)
    expect("a taken lesson does not carry back", rc != 0 and "does not carry back" in out, out)
    rc, out = j("plan", "--by", mgr3, "J1", "--fix", "x", "--carry", "home", at=T + 19, e=env3)
    expect("nor through plan --carry", rc != 0 and "does not carry back" in out, out)
    rc, out = j("set", "--by", mgr, "J1", "--status", "fixed", "--note", "an office file", at=T + 20)
    rc2, out2 = j("take", "--by", mgr3, at=T + 21, e=env3)
    expect("a lesson fixed after it was taken is not taken twice", rc == 0 and box()[0]["result"].startswith("FIXED")
           and "no lesson" in out2, out2)
    rc, out = j("take", "--by", mgr3, "--from", str(tmp / "nowhere.jsonl"), at=T + 22, e=env3)
    expect("take --from a missing file is refused", rc != 0 and "no such file" in out, out)
    rc, out = j("carry", "--by", mgr, "J1", "--to", "none", at=T + 23)
    expect("carry --to none empties the outbox", rc == 0 and "this crew only" in out and box() == [], box())
    j("set", "--by", mgr, "J6", "--status", "dropped", "--note", "selftest", at=T + 24)

    # the end the user set
    rc, out = j("due", "--by", mgr, "--end", "2h", at=1000)
    expect("due --end moves the due time (the user's hours)", rc == 0 and "set by MGR-1" in out and "one-shot timer" in out, out)
    os.environ["FOUNDRY_PATHS_OFFICE"] = str(d)
    f = facts(d, state, t0 + 1001)
    expect("the plan is due an hour before the end the manager set", abs(f["due"] - (t0 + 1000 + 3600)) < 1, f["due"] - t0)
    sid, s0, s1b = office.slot_at(office.DEFAULT_SLOTS, t0)
    ends = office.local(s1b - 2 * 3600)
    st2 = {**state, "rota": {"slots": office.DEFAULT_SLOTS, "days": [{"date": f"{office.local(s0):%Y-%m-%d}", sid: {"ends": f"{ends:%H:%M}"}}]}}
    d2 = tmp / "office2"
    d2.mkdir()
    (d2 / "roster.json").write_text(json.dumps({"v": 1, "manager": None, "badges": {}}), encoding="utf-8")
    f = facts(d2, st2, t0 + 60)
    expect("the rota's `ends` for the slot sets the end", abs(f["end"] - (s1b - 2 * 3600)) < 1 and "rota" in f["end_why"], f["end_why"])
    f = facts(d2, state, t0 + 60)
    expect("otherwise the slot's own end", abs(f["end"] - s1b) < 1 and f["state"] == "OPEN", f["end_why"])
    f = facts(d2, state, s1b - 600)
    expect("an empty journal past its due time is DUE (the plan says so even when nothing was logged)", f["state"] == "DUE")
    entries, _, _, _ = fold(read_j(d))
    expect("ids read as lists and ranges", parse_ids("J1, 3-J5", entries) == [1, 3, 4, 5])
    with open(d / "journal.jsonl", "a", encoding="utf-8") as fh:
        fh.write("{torn\n")
    expect("a torn line does not stop the journal", len(fold(read_j(d))[0]) == 6)

    # a torn last line (no trailing newline) does not eat the next entry
    d_f2 = tmp / "office-f2"
    d_f2.mkdir()
    (d_f2 / "roster.json").write_text(json.dumps({"v": 1, "manager": None, "badges": {}}), encoding="utf-8")
    with open(jfile(d_f2), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"at": t0, "ev": "add", "by": "MGR-1", "kind": "hole", "what": "first"}) + "\n")
        fh.write(json.dumps({"at": t0 + 1, "ev": "add", "by": "MGR-1", "kind": "hole", "what": "torn"}))  # no trailing newline
    with office.locked(d_f2):
        append_j(d_f2, {"at": t0 + 2, "ev": "add", "by": "MGR-1", "kind": "hole", "what": "after torn"})
    entries_f2, _, _, _ = fold(read_j(d_f2))
    expect("append after a torn line recovers the torn entry and adds the new one",
           len(entries_f2) == 3 and entries_f2[2]["what"] == "torn" and entries_f2[3]["what"] == "after torn",
           {n: x["what"] for n, x in entries_f2.items()})

    # a keyless add event does not crash fold
    d_f3 = tmp / "office-f3"
    d_f3.mkdir()
    with open(jfile(d_f3), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"at": t0, "ev": "add", "by": "MGR-1", "kind": "hole", "what": "good"}) + "\n")
        fh.write(json.dumps({"at": t0 + 1, "ev": "add", "by": "MGR-1"}) + "\n")  # missing kind and what
        fh.write(json.dumps({"at": t0 + 2, "ev": "add", "by": "MGR-1", "kind": "hole", "what": "also good"}) + "\n")
    entries_f3, _, _, skipped_f3 = fold(read_j(d_f3))
    expect("a keyless add is skipped and the next entry keeps its number",
           len(entries_f3) == 2 and entries_f3[1]["what"] == "good" and entries_f3[2]["what"] == "also good",
           {n: x["what"] for n, x in entries_f3.items()})
    expect("fold counts the skipped add", skipped_f3 == 1, skipped_f3)
    os.environ["FOUNDRY_PATHS_OFFICE"] = str(d_f3)
    (d_f3 / "roster.json").write_text(json.dumps({"v": 1, "manager": "MGR-1", "badges": {}}), encoding="utf-8")
    w_f3 = warnings(d_f3, state, t0 + 3, manager_on=True)
    expect("warnings does not crash on a keyless add", not any("KeyError" in w for w in w_f3), w_f3)
    expect("warnings reports the skipped line", any("malformed" in w for w in w_f3), w_f3)
    os.environ.pop("FOUNDRY_PATHS_OFFICE", None)

    # keyless add, then take, then add — no J-id reuse
    d_n1 = tmp / "office-n1"
    d_n1_other = tmp / "office-n1-other"
    d_n1.mkdir()
    d_n1_other.mkdir()
    (d_n1 / "roster.json").write_text(json.dumps({"v": 1, "manager": None, "badges": {}}), encoding="utf-8")
    env_n1 = {**env, "FOUNDRY_PATHS_OFFICE": str(d_n1), "FOUNDRY_CREW": "n1home",
              "FOUNDRY_LESSONS": json.dumps({"n1other": str(d_n1_other / "carry-n1home.jsonl")})}
    os.environ.update({"FOUNDRY_CREW": "n1home", "FOUNDRY_LESSONS": json.dumps({"n1other": str(d_n1_other / "carry-n1home.jsonl")})})
    # write one good add, one keyless add, and one outbox entry
    with open(jfile(d_n1), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps({"at": t0, "ev": "add", "by": "MGR-1", "kind": "hole", "what": "first good"}) + "\n")
        fh.write(json.dumps({"at": t0 + 1, "ev": "add", "by": "MGR-1"}) + "\n")  # keyless
    (d_n1_other / "carry-n1home.jsonl").parent.mkdir(parents=True, exist_ok=True)
    (d_n1_other / "carry-n1home.jsonl").write_text(
        json.dumps({"crew": "n1other", "id": "X1", "kind": "hole", "what": "a lesson from another crew"}) + "\n",
        encoding="utf-8")
    _, out = run(officepy, "appoint", "--name", "mgr-n1", *this_slot, at=t0 + 10, e=env_n1)
    mgr_n1 = badge_of(out)
    run(officepy, "clock-in", "--badge", mgr_n1, at=t0 + 11, e=env_n1)
    rc, out = j("take", "--by", mgr_n1, at=t0 + 20, e=env_n1)
    expect("take after a keyless add prints J2 (not J3)", rc == 0 and "J2 taken from" in out, out)
    rc, out = j("add", "--by", mgr_n1, "--kind", "hole", "--what", "third entry", at=t0 + 30, e=env_n1)
    expect("the next add prints J3 (no id reuse)", rc == 0 and out.startswith("J3 logged"), out)
    entries_n1 = fold(read_j(d_n1))[0]
    expect("fold gives 3 entries with no gap", len(entries_n1) == 3
           and entries_n1[1]["what"] == "first good" and entries_n1[2]["what"] == "a lesson from another crew"
           and entries_n1[3]["what"] == "third entry", {n: x["what"] for n, x in entries_n1.items()})
    for k in ("FOUNDRY_CREW", "FOUNDRY_LESSONS"):
        os.environ.pop(k, None)

    for k in ("FOUNDRY_PATHS_OFFICE", *crews):
        os.environ.pop(k, None)

    # the crews come from the profile's [crews] table: one with no lessons file is still a crew to carry to
    was = {k: os.environ.pop(k) for k in ("FOUNDRY_PROFILE", "FOUNDRY_CREW", "FOUNDRY_LESSONS") if k in os.environ}
    (tmp / "crews.toml").write_text('crew = "home"\n[crews.Alpha]\n[crews.beta]\nlessons = "x/carry-home.jsonl"\n'
                                    '[crews.home]\nlessons = "self.jsonl"\n', encoding="utf-8")
    os.environ["FOUNDRY_PROFILE"] = str(tmp / "crews.toml")
    try:
        expect("the profile's [crews] table names the other crews", me() == "home"
               and lessons() == {"alpha": [], "beta": ["x/carry-home.jsonl"]}, lessons())
        expect("carry --to takes a crew the table names, or none", parse_crews("Alpha, beta") == ["alpha", "beta"] and parse_crews("none") == [])
        try:
            parse_crews("mars")
            expect("carry --to a crew the table does not name is refused", False)
        except office.Refused as e:
            expect("carry --to a crew the table does not name is refused", "alpha, beta" in str(e) and "[crews]" in str(e), e)
    finally:
        os.environ.pop("FOUNDRY_PROFILE", None)
        os.environ.update(was)

    for w in bad:
        print("FAIL", w)
    print(f"journal selftest: {len(ok)} ok, {len(bad)} failed")
    return 1 if bad else 0


def main(argv):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if len(argv) > 1 and argv[1] == "selftest":
        return selftest()
    p = argparse.ArgumentParser(prog="journal.py", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("add")
    s.add_argument("--badge")
    s.add_argument("--by")
    s.add_argument("--kind", required=True)
    for k in ("--what", "--what-file", "--fix", "--fix-file", "--where"):
        s.add_argument(k)
    s.add_argument("--from", dest="src")
    s.add_argument("--carry")
    s = sub.add_parser("carry")
    s.add_argument("ids")
    s.add_argument("--by", required=True)
    s.add_argument("--to", required=True)
    s.add_argument("--note")
    s = sub.add_parser("take")
    s.add_argument("--by", required=True)
    s.add_argument("--max", type=int, default=TAKE_MAX)
    s.add_argument("--list", action="store_true")
    s.add_argument("--from", dest="src")
    s.add_argument("--crew")
    s = sub.add_parser("mine")
    s.add_argument("--badge", required=True)
    s = sub.add_parser("show")
    s.add_argument("ids", nargs="?")
    s.add_argument("--by")
    s.add_argument("--badge")
    s.add_argument("--all", action="store_true")
    s.add_argument("--json", action="store_true")
    s = sub.add_parser("plan")
    s.add_argument("ids")
    s.add_argument("--by", required=True)
    s.add_argument("--fix", required=True)
    for k in ("--files", "--how", "--owner", "--carry"):
        s.add_argument(k)
    s = sub.add_parser("set")
    s.add_argument("ids")
    s.add_argument("--by", required=True)
    s.add_argument("--status", required=True)
    for k in ("--note", "--commit", "--of"):
        s.add_argument(k)
    s = sub.add_parser("due")
    s.add_argument("--by")
    s.add_argument("--end")
    s = sub.add_parser("ready")
    s.add_argument("--by", required=True)
    s = sub.add_parser("approve")
    s.add_argument("--by", required=True)
    s.add_argument("--words", required=True)
    s.add_argument("--only")
    s.add_argument("--except", dest="exc")
    a = p.parse_args(argv[1:])
    fn = {"add": cmd_add, "mine": cmd_mine, "show": cmd_show, "plan": cmd_plan, "set": cmd_set, "due": cmd_due,
          "ready": cmd_ready, "approve": cmd_approve, "carry": cmd_carry, "take": cmd_take}[a.cmd]
    try:
        return fn(a, office.office_dir(), office.now_ts())
    except office.Refused as e:
        print(f"refused: {e}", file=sys.stderr)
        return getattr(e, "code", 3)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
