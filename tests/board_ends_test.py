#!/usr/bin/env python3
"""A user-set end for a manager's slot (`ends` in rota.days) is read by board.user_end.

    python tests/board_ends_test.py [--tools DIR]

Pure: imports tools/board.py and calls user_end on made-up states and badges; nothing is read or written.
--tools DIR imports board.py and office.py from DIR instead (to show a test fails on older code).
"""
import datetime as dt
import sys
from pathlib import Path

_dir = Path(__file__).resolve().parent.parent / "tools"
if "--tools" in sys.argv:
    _dir = Path(sys.argv[sys.argv.index("--tools") + 1]).resolve()
sys.path.insert(0, str(_dir))
import office  # noqa: E402
import board  # noqa: E402

# the cases are written for a three-slot rota; every state below names it, whatever the project's own rota is
SLOTS = [{"id": "day", "start": "06:00"}, {"id": "swing", "start": "14:00"}, {"id": "night", "start": "22:00"}]


def rota(days):
    return {"rota": {"slots": SLOTS, "days": days}}


def ts(day, hhmm):
    return dt.datetime.fromisoformat(f"{day}T{hhmm}:00").astimezone().timestamp()


def main():
    ok, bad = [], []

    def expect(what, cond, detail=""):
        (ok if cond else bad).append(what + ("" if cond else f": {detail}"))

    day = {"date": "2030-11-11", "day": {"shift": "S3", "manager": "MGR-3", "ends": "16:00"},
           "night": {"shift": "S3", "ends": "07:30"}}
    state = rota([day])
    b_day = {"id": "MGR-3", "slot": "day", "in_at": ts("2030-11-11", "06:57")}
    expect("a day slot's ends is that day at 16:00", board.user_end(state, b_day) == ts("2030-11-11", "16:00"),
           board.user_end(state, b_day))
    b_night = {"id": "MGR-4", "slot": "night", "in_at": ts("2030-11-11", "22:05")}
    expect("a night slot's ends earlier than the clock-in is the next morning",
           board.user_end(state, b_night) == ts("2030-11-12", "07:30"), board.user_end(state, b_night))
    b_swing = {"id": "MGR-5", "slot": "swing", "in_at": ts("2030-11-11", "14:05")}
    expect("a slot with no ends has none", board.user_end(state, b_swing) is None)
    expect("a badge with no rota day has none",
           board.user_end(state, {"id": "MGR-6", "slot": "day", "in_at": ts("2030-11-12", "06:05")}) is None)
    b_late = {"id": "MGR-7", "slot": "night", "in_at": ts("2030-11-12", "00:30")}
    expect("a night manager who clocks in after midnight reads the night that began the evening before",
           board.user_end(state, b_late) == ts("2030-11-12", "07:30"), board.user_end(state, b_late))
    nxt = rota([day, {"date": "2030-11-12", "night": {"ends": "08:00"}}])
    expect("... and never the next night's ends", board.user_end(nxt, b_late) == ts("2030-11-12", "07:30"),
           board.user_end(nxt, b_late))
    b_after = {"id": "MGR-8", "slot": "day", "in_at": ts("2030-11-11", "13:00")}
    lunch = rota([{"date": "2030-11-11", "day": {"ends": "12:00"}}])
    expect("an ends before the clock-in stays that day, not 24 h later",
           board.user_end(lunch, b_after) == ts("2030-11-11", "12:00"), board.user_end(lunch, b_after))
    bad_state = rota([{"date": "2030-11-11", "day": {"ends": "4pm"}}])
    expect("an ends that is not HH:MM is ignored", board.user_end(bad_state, b_day) is None)
    expect("a state without a rota is fine", board.user_end({}, b_day) is None)

    # an end at or before the slot's start rolls to the next day only for a slot that crosses midnight
    typo = rota([{"date": "2030-11-11", "day": {"ends": "05:00"}, "night": {"ends": "21:00"}}])
    expect("a day slot's ends before its start is refused, not read as 05:00 the next day",
           board.user_end(typo, b_day) is None, board.user_end(typo, b_day))
    expect("a night slot's ends far past its end (21:00 the next day) is refused",
           board.user_end(typo, b_night) is None, board.user_end(typo, b_night))
    expect("a night slot's 07:30 still reads as the next morning",
           board.user_end(state, b_night) == ts("2030-11-12", "07:30"))
    typos = getattr(board, "ends_typos", lambda *_: [])(typo, dt.datetime.fromisoformat("2030-11-11T15:00:00").astimezone())
    expect("the check warns for each refused end, saying it is ignored",
           len(typos) == 2 and all("ignored" in w for w in typos) and "does not cross midnight" in " ".join(typos), typos)
    expect("the check has no warning for good ends",
           getattr(board, "ends_typos", lambda *_: ["missing"])(state, dt.datetime.fromisoformat("2030-11-11T15:00:00").astimezone()) == [])

    now15 = dt.datetime.fromisoformat("2030-11-11T15:00:00").astimezone()
    typos_of = getattr(board, "ends_typos", lambda *_: None)

    # a next-morning ends keeps its wall-clock time on a DST night (it only bites where the host's zone has DST)
    for night, morning in (("2030-11-02", "2030-11-03"), ("2030-03-09", "2030-03-10")):
        dst = rota([{"date": night, "night": {"ends": "07:30"}}])
        b_dst = {"id": "MGR-2", "slot": "night", "in_at": ts(night, "22:05")}
        expect(f"the night of {night} reads ends 07:30 as {morning} 07:30 local, across the DST change",
               board.user_end(dst, b_dst) == ts(morning, "07:30"), board.user_end(dst, b_dst))

    # a next-morning ends reads at most 4 h past the slot's end (a night "14:00" is a typo)
    wide = rota([{"date": "2030-11-11", "night": {"ends": "14:00"}}])
    expect("a night ends of 14:00 (8 h past the slot's end) is refused",
           board.user_end(wide, b_night) is None, board.user_end(wide, b_night))
    ok10 = rota([{"date": "2030-11-11", "night": {"ends": "10:00"}}])
    expect("a night ends of 10:00 (4 h past) still reads as the next morning",
           board.user_end(ok10, b_night) == ts("2030-11-12", "10:00"), board.user_end(ok10, b_night))

    # a bad days entry is skipped with a warning; the scan goes on and nothing raises
    messy = rota(["x", {"date": "2030-13-45", "day": {"ends": "05:00"}},
                                {"date": "2030-11-11", "day": {"ends": "05:00"}}])
    try:
        w = typos_of(messy, now15)
        raised = None
    except Exception as ex:  # noqa: BLE001 - the point of the check
        w, raised = None, ex
    expect("a string days entry and a bad date never stop ends_typos",
           raised is None and w is not None and len(w) == 3
           and "not an object" in w[0] and "bad date" in w[1] and "05:00" in w[2], raised or w)
    try:
        got = board.user_end(rota(["x", day]), b_day)
    except Exception as ex:  # noqa: BLE001
        got = f"raised {ex!r}"
    expect("user_end reads past a string days entry", got == ts("2030-11-11", "16:00"), got)

    # an ends that is not a time is warned, not silently ignored
    garbled = rota([{"date": "2030-11-11", "day": {"ends": "24:00"}, "swing": {"ends": "7:3"},
                                  "night": {"ends": "07:30pm"}}])
    w = typos_of(garbled, now15) or []
    expect("24:00, 7:3 and 07:30pm are each warned as not a time",
           len(w) == 3 and all("not a time" in x for x in w), w)
    expect("... and still read as no end", board.user_end(garbled, b_day) is None)

    # a manager appointed and clocked in just before its slot starts reads that slot's ends
    slots = SLOTS
    ms = getattr(office, "manager_slot", None)
    expect("a manager appointed at 13:55 is the swing slot's manager, with the swing slot's end",
           ms is not None and ms(slots, ts("2030-11-11", "13:55"))[0] == "swing"
           and ms(slots, ts("2030-11-11", "13:55"))[2] == ts("2030-11-11", "22:00"))
    expect("... but one appointed at 13:00 is the day slot's",
           ms is not None and ms(slots, ts("2030-11-11", "13:00"))[0] == "day")
    early = rota([{"date": "2030-11-11", "day": {"ends": "16:00"}, "swing": {"ends": "23:00"}}])
    b_early = {"id": "MGR-9", "slot": "swing", "in_at": ts("2030-11-11", "13:57")}
    expect("a swing manager clocked in at 13:57 reads the swing slot's ends (23:00)",
           board.user_end(early, b_early) == ts("2030-11-11", "23:00"), board.user_end(early, b_early))
    b_stray = {"id": "MGR-1", "slot": "swing", "in_at": ts("2030-11-11", "10:00")}
    expect("a swing badge clocked in hours before its slot still reads none",
           board.user_end(early, b_stray) is None, board.user_end(early, b_stray))

    for x in ok:
        print(f"  ok   {x}")
    for x in bad:
        print(f"  FAIL {x}")
    print(f"board ends test: {len(ok)} ok, {len(bad)} failed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
