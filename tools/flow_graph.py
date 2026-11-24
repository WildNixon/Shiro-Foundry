#!/usr/bin/env python3
"""The road graph as an authored asset (after UE5's Flow Graph: typed nodes, named pins, explicit links).

Both files lie in the profile's paths.flow (docs/flow unless the project says otherwise):

  road.graph.json   the nodes and the links between their pins; the only place a link is written down
  road.edits.jsonl  every edit, in order, signed with the crew office's key and chained to the one before

Only the manager on the clock edits it (or the founder), and only through this script (run as `flow.py graph ...`):

  flow.py graph seed --by "<manager's badge line>"        once: write the asset from the links flow.py reads out of
                                                          ROADMAP.md's prose today, each marked seeded (unconfirmed)
  flow.py graph link FROM TO [--ids A-01,B-02] [--why TEXT] --by LINE
                                                          FROM must come before TO; the pins follow from the two types;
                                                          --ids: a decision gates only those requirement IDs
  flow.py graph unlink FROM TO --by LINE
  flow.py graph confirm FROM TO [--why TEXT] --by LINE    a seeded link the manager has checked
  flow.py graph node add ID [--type T] [--note TEXT] --by LINE
  flow.py graph node set ID --note TEXT --by LINE
  flow.py graph node rm ID --by LINE                      refused while a link touches it
  flow.py graph undo --by LINE                            take back the last edit (again: put it back)

Anyone may read (no badge):

  flow.py graph show [ID]             the asset in short, or one node with its pins and links
  flow.py graph trace ID [--up|--down]  everything ID waits on, or everything that waits on ID (both by default)
  flow.py graph verify                exit 1 when the asset was changed by hand or the log's chain is broken

A crew badge is refused: only a MANAGER badge that is the roster's manager, or a FOUNDER badge (an FDR- id), edits.
The badge and the signed log keep an honest record, as badges do (office.py): they are not security. A project's
hooks may also refuse a hand edit of either file (the profile's hooks.protect); ask the manager for a change.
The script commits nothing: the manager commits the flow folder like any other map edit.

What an ID is comes from the profile's [roadmap] table: milestone_id, decision_id, stage_id, the goal (the last
stage) and, when the project has them, late_stages (named stages between the numbered ones and the goal) and
block_id (how a push block's title opens). A lane is named as measure.lane_pattern says.
"""
import argparse
import collections
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import foundry_profile as fp  # noqa: E402

P = fp.load(__file__)


def at(root, name):
    """paths.<name> under `root` (an absolute path in the profile stands as it is)."""
    return Path(root) / str(P.get(f"paths.{name}"))


def rx(key, default):
    """A profile regex as a non-capturing group; a pattern that does not compile falls back to the default."""
    text = str(P.get(key) or default)
    try:
        re.compile(text)
    except re.error:
        text = default
    return "(?:" + text + ")"


ASSET = Path(str(P.get("paths.flow"))) / "road.graph.json"
LOG = Path(str(P.get("paths.flow"))) / "road.edits.jsonl"
TYPES = ("milestone", "decision", "stage", "block")
MS = rx("roadmap.milestone_id", r"M\d+")          # a milestone's ID
DEC = rx("roadmap.decision_id", r"D\d+")          # a decision's ID
STAGE = rx("roadmap.stage_id", r"R\d")            # a numbered stage's ID
BLOCK = rx("roadmap.block_id", r"[QP]\d+[a-z]?")  # the ID that opens a push block's title on the map
LANE = rx("measure.lane_pattern", r"\bG\d+\b")    # a gym lane's name
GOAL = str(P.get("roadmap.goal") or "1.0")       # the last stage: every numbered stage leads to it
# the named stages after the numbered ones, in order, the goal last
LATE = tuple(dict.fromkeys([str(x) for x in (P.get("roadmap.late_stages") or [])] + [GOAL]))
ROADMAP = Path(str(P.get("paths.roadmap"))).name
SEEDED = f"seeded from {ROADMAP}'s prose"

# what each node type offers; a link joins an out pin to an in pin
PINS = {"milestone": {"in": ("after", "gate", "push"), "out": ("done", "closes", "gym")},
        "decision": {"in": (), "out": ("decides",)},
        "stage": {"in": ("exit",), "out": ("reached",)},
        "block": {"in": ("after",), "out": ("then", "runs")},
        "lane": {"in": ("checkpoint",), "out": ("verdict",)}}
# the links a manager may write, by the two node types: (out pin, in pin, what it means)
LINKS = {("milestone", "milestone"): ("done", "after", "must be done first"),
         ("decision", "milestone"): ("decides", "gate", "must be decided first"),
         ("decision", "stage"): ("decides", "exit", "must be decided before the stage's exit"),
         ("stage", "stage"): ("reached", "exit", "must be reached first"),
         ("block", "block"): ("then", "after", "runs first in the push"),
         ("block", "milestone"): ("runs", "push", "the push block that works on it")}
# read from the roadmap's own structured cells at build time, so never written by hand
DERIVED = {("milestone", "stage"): f"a milestone feeds a stage through the requirement IDs it closes ({ROADMAP}'s Closes column)",
           ("milestone", "lane"): f"a milestone's gym lane comes from the map and {ROADMAP}'s lane line",
           ("lane", "milestone"): "a lane's verdict is read from the gym's series"}


class Refused(Exception):
    pass


def type_of(nid):
    """The node type an ID implies, or None."""
    if re.fullmatch(MS, nid):
        return "milestone"
    if re.fullmatch(DEC, nid):
        return "decision"
    if nid in LATE or re.fullmatch(STAGE, nid):
        return "stage"
    if re.fullmatch(BLOCK, nid):
        return "block"
    if re.fullmatch(LANE, nid):
        return "lane"
    return None


def canon(v):
    return json.dumps(v, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha(v):
    return hashlib.sha256(canon(v).encode("utf-8")).hexdigest()


def body_hash(g):
    return sha({"v": g.get("v"), "nodes": g.get("nodes"), "edges": g.get("edges")})


def ekey(e):
    return f"{e['from']}>{e['to']}"


def empty():
    return {"v": 1, "head": None, "nodes": {}, "edges": []}


def load(root):
    """(graph or None when there is no asset yet, problems with its shape)."""
    f = Path(root) / ASSET
    if not f.exists():
        return None, []
    try:
        g = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return None, [f"{ASSET.as_posix()} could not be read ({type(e).__name__})"]
    bad = []
    if not isinstance(g, dict) or not isinstance(g.get("nodes"), dict) or not isinstance(g.get("edges"), list):
        return None, [f"{ASSET.as_posix()} is not a graph (nodes and edges)"]
    for nid, n in g["nodes"].items():
        if not isinstance(n, dict) or n.get("type") not in TYPES:
            bad.append(f"node {nid} has no known type")
    keep = []
    for e in g["edges"]:
        if isinstance(e, dict) and all(isinstance(e.get(k), str) for k in ("from", "out", "to", "in")):
            keep.append(e)
        else:
            bad.append("a link without from, out, to and in was left out")
    g["edges"] = keep
    return g, bad


def read_log(root):
    f = Path(root) / LOG
    if not f.exists():
        return []
    out = []
    for line in f.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except ValueError:
                out.append({"unreadable": line[:60]})
    return out


def office():
    """(office dir, the office module) or (None, None) when office.py cannot be loaded."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    try:
        import office as mod
    except Exception:
        return None, None
    finally:
        sys.path.pop(0)
    return mod.office_dir(), mod


def office_key(d):
    """The office key if this checkout can reach it; never creates one."""
    try:
        return bytes.fromhex(json.loads((Path(d) / "badge_key.json").read_text(encoding="utf-8"))["key"])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def verify(root, office_dir=None):
    """(ok, lines). Not ok: the asset differs from what the last logged edit left, or the chain or a signature
    is broken. No asset at all is ok (not seeded yet)."""
    g, bad = load(root)
    log = read_log(root)
    if g is None and not bad and not log:
        return True, [f"no graph asset yet: flow.py reads links from {ROADMAP}'s prose until the manager runs graph seed"]
    lines = list(bad)
    if g is None:
        return False, lines or [f"{LOG.as_posix()} exists but {ASSET.as_posix()} does not"]
    if not log:
        return False, lines + [f"{ASSET.as_posix()} has no edit log beside it: it was not written by flow.py graph"]
    d, off = office()
    d = Path(office_dir) if office_dir else d
    key = office_key(d) if d else None
    prev, ok = None, not bad
    for i, e in enumerate(log, 1):
        if "unreadable" in e or e.get("seq") != i or e.get("prev") != prev:
            lines.append(f"TAMPERED: edit log entry {i} is unreadable, out of order or does not follow the one before")
            ok = False
            break
        if key and off and e.get("sig") != off.sign(key, canon({k: v for k, v in e.items() if k != "sig"})):
            lines.append(f"TAMPERED: edit log entry {i} ({e.get('op')} by {e.get('by')}) does not carry the office's signature")
            ok = False
        prev = sha(e)
    if ok and log[-1].get("graph") != body_hash(g):
        lines.append(f"TAMPERED: {ASSET.as_posix()} is not what the last logged edit left "
                     f"(entry {len(log)}, {log[-1].get('op')} by {log[-1].get('by')}); it was changed outside flow.py graph")
        ok = False
    if ok and g.get("head") != prev:
        lines.append(f"TAMPERED: {ASSET.as_posix()}'s head does not name the last edit log entry")
        ok = False
    if ok:
        lines.append(f"graph ok: {len(g['nodes'])} nodes, {len(g['edges'])} links, {len(log)} edits, last {log[-1].get('op')} by "
                     f"{log[-1].get('by')}" + ("" if key else "; signatures not checked (no office key reachable from here)"))
    return ok, lines


# ---------------------------------------------------------------- checks on the graph itself

def blocks_in(root):
    """Push blocks of the shift on the map, by the ID that opens each title (Q3a, P1)."""
    try:
        st = json.loads(at(root, "state").read_text(encoding="utf-8"))
        titles = [str(b.get("title") or "") for b in (st.get("shift") or {}).get("blocks") or [] if isinstance(b, dict)]
    except (OSError, ValueError, AttributeError):
        return {}
    out = {}
    for t in titles:
        m = re.match(r"\s*(?P<id>" + BLOCK + r")\b", t)
        if m:
            out.setdefault(m["id"], t)
    return out


def node_type(g, nid, blocks=()):
    n = g["nodes"].get(nid)
    return n["type"] if n else "block" if nid in blocks else None


def cycle(edges):
    """A list of IDs that form a loop, or None."""
    nxt = collections.defaultdict(list)
    for e in edges:
        nxt[e["from"]].append(e["to"])
    state = {}

    def walk(n, path):
        state[n] = 1
        for m in nxt[n]:
            if state.get(m) == 1:
                return path[path.index(m):] + [m] if m in path else [n, m]
            if m not in state:
                r = walk(m, path + [m])
                if r:
                    return r
        state[n] = 2
        return None

    for n in list(nxt):
        if n not in state:
            r = walk(n, [n])
            if r:
                return r
    return None


def check_link(g, a, b, blocks):
    ta, tb = node_type(g, a, blocks), node_type(g, b, blocks)
    for nid, t in ((a, ta), (b, tb)):
        if t is None:
            hint = type_of(nid)
            raise Refused(f"{nid} is not a node of the graph" + (f" (add it first: graph node add {nid})" if hint in TYPES and hint != "block"
                                                                 else " (a push block is read from the map's shift)" if hint == "block" else ""))
    if a == b:
        raise Refused("a node cannot link to itself")
    if (ta, tb) not in LINKS:
        why = DERIVED.get((ta, tb))
        raise Refused(f"no link runs from a {ta} to a {tb}" + (f": {why}" if why else
                      "; a link runs " + ", ".join(f"{x} to {y}" for x, y in LINKS)))
    return LINKS[(ta, tb)]


# ---------------------------------------------------------------- edits (the manager's badge only)

def may_edit(rec, roster):
    """Whether a verified badge edits the graph: the roster's manager, or a founder (role FOUNDER, an FDR- id)."""
    role, bid = str(rec.get("role") or "").upper(), str(rec.get("id") or "")
    return (role == "MANAGER" and roster.get("manager") == bid) or (role == "FOUNDER" and bid.startswith("FDR-"))


def manager(by, office_dir=None):
    """The roster record of the manager on the clock, or of a founder, for this badge line; Refused for anyone else."""
    d, off = office()
    if off is None:
        raise Refused("office.py could not be loaded, so no badge can be checked")
    d = Path(office_dir) if office_dir else d
    if not by:
        raise Refused(f"an edit needs the manager's badge (or the founder's): --by \"<{P.badge_prefix} line>\"")
    key = office_key(d)
    if key is None:
        raise Refused(f"no crew office key under {d}, so no badge can be checked")
    roster = off.read_roster(d)
    try:
        rec = off.verify_line(key, roster, by)
    except off.Refused as e:
        raise Refused(str(e))
    if not may_edit(rec, roster):
        raise Refused(f"badge {rec['id']} ({rec.get('role', '?').lower()}) may read the graph but not edit it: only the manager "
                      f"on the roster ({roster.get('manager') or 'none appointed'}) or the founder edits. Ask the manager for the change.")
    return rec, d, off, key


def write(root, g, entry_fields, off, key, d):
    """Under the office lock: append the signed log entry and write the asset it describes."""
    root = Path(root)
    (root / ASSET).parent.mkdir(parents=True, exist_ok=True)
    g["nodes"] = dict(sorted(g["nodes"].items(), key=lambda kv: (TYPES.index(kv[1]["type"]), sortkey(kv[0]))))
    g["edges"] = sorted(g["edges"], key=lambda e: (sortkey(e["to"]), sortkey(e["from"])))
    log = read_log(root)
    entry = {"seq": len(log) + 1, "at": int(time.time()), **entry_fields, "prev": sha(log[-1]) if log else None,
             "graph": body_hash(g)}
    entry["sig"] = off.sign(key, canon(entry))
    g["head"] = sha(entry)
    tmp = root / (ASSET.as_posix() + ".tmp")
    tmp.write_text(json.dumps({"v": g["v"], "head": g["head"], "nodes": g["nodes"], "edges": g["edges"]}, indent=1,
                              ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    for _ in range(50):
        try:
            os.replace(tmp, root / ASSET)
            break
        except OSError:  # a file a reader has open this instant may refuse the replace; try again shortly
            time.sleep(0.05)
    else:
        os.replace(tmp, root / ASSET)
    with open(root / LOG, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
    return entry


def sortkey(nid):
    m = re.match(r"([A-Za-z]*)(\d+)(.*)", nid)
    return (m[1], int(m[2]), m[3]) if m else (nid, 0, "")


def edit(root, by, op, change, office_dir=None):
    """Check the badge, make sure the asset is sound, apply `change(g) -> (kind, key, before, after, text)` and log it."""
    rec, d, off, key = manager(by, office_dir)
    with off.locked(d):
        g, bad = load(root)
        if op == "seed":
            if g is not None or read_log(root):
                raise Refused("the graph is already seeded; edit it with link, unlink, confirm and node")
            g = empty()
        else:
            if g is None:
                raise Refused("no graph asset yet: run graph seed first" if not bad else bad[0])
            ok, lines = verify(root, d)
            if not ok:
                raise Refused("the asset does not match its edit log, so no edit is added on top of it: "
                              + "; ".join(x for x in lines if x.startswith("TAMPERED")))
        kind, k, before, after, text = change(g)
        loop = cycle(g["edges"])
        if loop:
            raise Refused("that would make a loop: " + " → ".join(loop))
        e = write(root, g, {"by": rec["id"], "op": op, "kind": kind, "key": k, "before": before, "after": after}, off, key, d)
    print(f"graph edit {e['seq']} by {rec['id']}: {text}")
    print(f"commit {ASSET.as_posix()} and {LOG.as_posix()} with the map")
    return e


def put(g, kind, k, val):
    """Set (or with None, drop) one node or link."""
    if kind == "node":
        if val is None:
            g["nodes"].pop(k, None)
        else:
            g["nodes"][k] = val
    elif kind == "edge":
        g["edges"] = [e for e in g["edges"] if ekey(e) != k] + ([val] if val else [])
    else:  # the seed: the whole graph
        g["nodes"], g["edges"] = (dict(val["nodes"]), list(val["edges"])) if val else ({}, [])


def find(g, a, b):
    return next((e for e in g["edges"] if e["from"] == a and e["to"] == b), None)


def seed_from(M):
    """Nodes and links as flow.py reads them from the roadmap today (its prose included)."""
    nodes, edges = {}, []
    for mid in M["ms"]:
        nodes[mid] = {"type": "milestone"}
    for did in M["decisions"]:
        nodes[did] = {"type": "decision"}
    for sid in M["stages"]:
        nodes[sid] = {"type": "stage"}

    def add(a, b, ids=None):
        if a in nodes and b in nodes and a != b and not any(e["from"] == a and e["to"] == b for e in edges):
            out, inn, _ = LINKS[(nodes[a]["type"], nodes[b]["type"])]
            edges.append({"from": a, "out": out, "to": b, "in": inn, "why": SEEDED, "seeded": True, **({"ids": ids} if ids else {})})

    for m in M["ms"].values():
        for dep in m["deps"]:
            add(dep, m["id"])
    for d in M["decisions"].values():
        for t in d["full"]:
            add(d["id"], t)
        for t, ids in d["partial"].items():
            add(d["id"], t, ids)
        for t, ids in d["stage_ids"].items():
            add(d["id"], t, ids)
    # every numbered stage leads to the first named stage after them; those follow one another to the goal
    late = [s for s in LATE if s in M["stages"]]
    for s in [s for s in M["stages"] if s not in LATE]:
        if late:
            add(s, late[0])
    for a, b in zip(late, late[1:]):
        add(a, b)
    while cycle(edges):  # prose can name two milestones in each other's row; the seed keeps the first and says so
        loop = cycle(edges)
        drop = next(e for e in edges if e["from"] == loop[-2] and e["to"] == loop[-1])
        edges.remove(drop)
        print(f"seed: left out {drop['from']} → {drop['to']} ({ROADMAP}'s prose makes a loop: {' → '.join(loop)})")
    return nodes, edges


# ---------------------------------------------------------------- reading

def trace(g, nid, up):
    """[(depth, link)] walking the links into nid (up) or out of it, each node once."""
    seen, out, todo = {nid}, [], [(nid, 1)]
    while todo:
        n, depth = todo.pop(0)
        for e in g["edges"]:
            a, b = (e["to"], e["from"]) if up else (e["from"], e["to"])
            if a == n:
                out.append((depth, e))
                if b not in seen:
                    seen.add(b)
                    todo.append((b, depth + 1))
    return out


def link_text(e):
    return (f"{e['from']}.{e['out']} → {e['to']}.{e['in']}" + (f" ({', '.join(e['ids'])} only)" if e.get("ids") else "")
            + (f"  [{e['why']}]" if e.get("why") else "") + ("  UNCONFIRMED" if e.get("seeded") else ""))


def show(g, nid=None):
    if nid is None:
        c = collections.Counter(n["type"] for n in g["nodes"].values())
        print(f"{len(g['nodes'])} nodes (" + ", ".join(f"{c[t]} {t}s" for t in TYPES if c[t]) + f"), {len(g['edges'])} links, "
              f"{sum(1 for e in g['edges'] if e.get('seeded'))} seeded and not yet confirmed")
        for e in g["edges"]:
            print("  " + link_text(e))
        return 0
    n = g["nodes"].get(nid)
    if not n:
        print(f"{nid} is not a node the manager wrote into the graph (lanes, requirements and push blocks are read at build time)")
        return 1
    pins = PINS[n["type"]]
    print(f"{nid}: {n['type']}" + (f", note: {n['note']}" if n.get("note") else ""))
    print(f"  in pins: {', '.join(pins['in']) or 'none'}; out pins: {', '.join(pins['out']) or 'none'}")
    for label, es in (("in", [e for e in g["edges"] if e["to"] == nid]), ("out", [e for e in g["edges"] if e["from"] == nid])):
        for e in es:
            print(f"  {label:3} {link_text(e)}")
    return 0


# ---------------------------------------------------------------- the command line

def main(argv, root, model=None):
    """`flow.py graph ...`. `model` is a callable giving flow.py's model of the roadmap (the seed reads it)."""
    p = argparse.ArgumentParser(prog="flow.py graph", description="The road graph asset. Reading is open; editing takes the manager's badge (or the founder's).")
    sub = p.add_subparsers(dest="cmd", required=True)
    by = argparse.ArgumentParser(add_help=False)
    by.add_argument("--by", default="", help="the manager's badge line (or the founder's)")
    sub.add_parser("seed", parents=[by])
    for name in ("link", "unlink", "confirm"):
        s = sub.add_parser(name, parents=[by])
        s.add_argument("src")
        s.add_argument("dst")
        if name != "unlink":
            s.add_argument("--why", default="")
        if name == "link":
            s.add_argument("--ids", default="")
    s = sub.add_parser("node", parents=[by])
    s.add_argument("what", choices=("add", "set", "rm"))
    s.add_argument("id")
    s.add_argument("--type", choices=TYPES)
    s.add_argument("--note")
    sub.add_parser("undo", parents=[by])
    s = sub.add_parser("show")
    s.add_argument("id", nargs="?")
    s = sub.add_parser("trace")
    s.add_argument("id")
    s.add_argument("--up", action="store_true")
    s.add_argument("--down", action="store_true")
    sub.add_parser("verify")
    a = p.parse_args(argv)
    try:
        return run(a, Path(root), model)
    except Refused as e:
        print(f"refused: {e}", file=sys.stderr)
        return 3


def run(a, root, model):
    if a.cmd == "verify":
        ok, lines = verify(root)
        print("\n".join(lines))
        return 0 if ok else 1
    if a.cmd in ("show", "trace"):
        g, bad = load(root)
        if g is None:
            print(bad[0] if bad else "no graph asset yet (the manager runs: flow.py graph seed)")
            return 1
        if a.cmd == "show":
            return show(g, a.id)
        if a.id not in g["nodes"]:
            print(f"{a.id} is not a node of the graph")
            return 1
        for up in ([True] if a.up and not a.down else [False] if a.down and not a.up else [True, False]):
            rows = trace(g, a.id, up)
            print(f"{a.id} waits on ({len(rows)} links):" if up else f"waiting on {a.id} ({len(rows)} links):")
            for depth, e in rows:
                print("  " * depth + link_text(e))
        return 0

    blocks = blocks_in(root)
    if a.cmd == "seed":
        def change(g):
            nodes, edges = seed_from(model())
            put(g, "graph", "", {"nodes": nodes, "edges": edges})
            return "graph", "", None, {"nodes": nodes, "edges": edges}, (
                f"seeded {len(nodes)} nodes and {len(edges)} links from {ROADMAP}; each link is unconfirmed until graph confirm")
    elif a.cmd == "link":
        ids = [x.strip() for x in a.ids.split(",") if x.strip()]

        def change(g):
            out, inn, means = check_link(g, a.src, a.dst, blocks)
            if ids and out != "decides":
                raise Refused("--ids narrows a decision's gate; it has no meaning on a link from a " + node_type(g, a.src, blocks))
            before = find(g, a.src, a.dst)
            after = {"from": a.src, "out": out, "to": a.dst, "in": inn, "why": a.why or (before or {}).get("why", ""), **({"ids": ids} if ids else {})}
            if before == after:
                raise Refused(f"{a.src} → {a.dst} is already linked that way")
            put(g, "edge", ekey(after), after)
            return "edge", ekey(after), before, after, f"{'relinked' if before else 'linked'} {link_text(after)} ({a.src} {means})"
    elif a.cmd in ("unlink", "confirm"):
        def change(g):
            before = find(g, a.src, a.dst)
            if not before:
                raise Refused(f"there is no link {a.src} → {a.dst}")
            if a.cmd == "unlink":
                put(g, "edge", ekey(before), None)
                return "edge", ekey(before), before, None, f"unlinked {a.src} → {a.dst}"
            after = {k: v for k, v in before.items() if k != "seeded"}
            after["why"] = a.why or ("" if before.get("why") == SEEDED else before.get("why", ""))
            if after == before:
                raise Refused(f"{a.src} → {a.dst} is already confirmed")
            put(g, "edge", ekey(after), after)
            return "edge", ekey(after), before, after, f"confirmed {link_text(after)}"
    elif a.cmd == "node":
        def change(g):
            before = g["nodes"].get(a.id)
            if a.what == "add":
                if before:
                    raise Refused(f"{a.id} is already a node")
                t = a.type or type_of(a.id)
                if t not in TYPES:
                    raise Refused(f"{a.id}: name its --type ({', '.join(TYPES)}); lanes and requirements are read at build time")
                after = {"type": t, **({"note": a.note} if a.note else {})}
            elif not before:
                raise Refused(f"{a.id} is not a node")
            elif a.what == "set":
                if a.note is None:
                    raise Refused("node set takes --note TEXT (an empty text clears it)")
                after = {"type": before["type"], **({"note": a.note} if a.note else {})}
                if after == before:
                    raise Refused(f"{a.id}'s note is already that")
            else:
                touching = [ekey(e) for e in g["edges"] if a.id in (e["from"], e["to"])]
                if touching:
                    raise Refused(f"{a.id} still has links ({', '.join(touching)}); unlink them first")
                after = None
            put(g, "node", a.id, after)
            return "node", a.id, before, after, {"add": "added", "set": "noted", "rm": "removed"}[a.what] + f" node {a.id}"
    else:  # undo
        def change(g):
            log = read_log(root)
            last = log[-1] if log else None
            if not last or last.get("op") == "seed":
                raise Refused("nothing to take back (the seed stays)")
            put(g, last["kind"], last["key"], last["before"])
            return last["kind"], last["key"], last["after"], last["before"], (
                f"took back edit {last['seq']} ({last['op']} {last['key']} by {last['by']})")
    edit(root, a.by, a.cmd if a.cmd != "node" else f"node {a.what}", change)
    return 0
