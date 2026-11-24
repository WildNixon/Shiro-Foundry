#!/usr/bin/env python3
"""Plan charts: a plan written as one file, drawn as a flow chart and checked against the tree.

    python tools/plan_flow.py list                               every plan under the flow folder, with its counts and problems
    python tools/plan_flow.py new NAME --title "…" [--question "…"] [--by "LINE"]   start NAME.plan.toml there from the template
    python tools/plan_flow.py build [NAME] [--out DIR] [--by "LINE"]   writes NAME.html and NAME.graph.json (every plan when no NAME)
    python tools/plan_flow.py show NAME ID                       one stage, step, decision or lane, with its links
    python tools/plan_flow.py trace NAME ID [--up|--down]        everything before it, or everything that follows from it
    python tools/plan_flow.py edges NAME                         every link, one per line, then the problems
    python tools/plan_flow.py selftest [NAME]                    the plan's own checks (every plan when no NAME); exit 1 on a problem

An option's value follows it (--title "x") or is joined to it (--title="x"): both forms are read.

A plan chart is a design to judge: stages in order, the steps inside each stage and what each step needs first, the
decisions that are the user's and the stages each one shapes, and the gym lanes that would close a stage. All of it
is written in NAME.plan.toml under the profile's paths.flow (docs/flow by default). That file is the chart: make one
with `new`, change it by editing the file, and run `selftest NAME` after every edit. The page is never edited. What
is read from the tree at each build: each step's and decision's anchor (a file and a text it must hold) and the
roadmap row a decision names, so a plan cannot drift from the tree unnoticed.

The road to the goal is not a plan chart (flow.py, the manager's road graph). A project may add its own reader
that draws a "system graph" from its code onto the same canvas (flow_page.py); a chart with facts and words of
its own registers itself in CHARTS and is then reached here by its name.

It works on the checkout the shell stands in (the working directory's, so a worktree's own plans and pages; the
script's own checkout when the shell is outside any). It writes only under that checkout's paths.flow_out
(git-ignored), or --out, and `new` writes one file under paths.flow. A write that would land in the main checkout
(`new` there, a `build` there, or an --out that points into it) takes the manager's badge or the founder's
(--by "<badge line>"): anyone else works in a worktree, or builds with an --out outside the main checkout. During
a freeze even the manager's `new` is refused there, and a build may write only under the main checkout's
git-ignored output folder. The main checkout is frozen by the same rule the office and the board use: a counted
sweep or run holds or waits for the shared resource, known by its queue id (<badge>-sweep,
<badge>-counted[-<lane>]) and never by its priority alone; or the manager's own freeze is on (`office.py freeze on`,
the office's freeze.json), which is how a project with no shared resource freezes. A prio-0 or whole-resource job
under a plain id only gets a note, and that freeze is kept by hand. It commits nothing. Standard library only.

Exit code: 0 done; 1 a selftest or build found a problem, or `new` found the plan already there; 2 a command line
that cannot be read, an unknown plan, or a write into the main checkout without the manager's badge; 3 a write
into the main checkout refused during a freeze (or while the office cannot be read, so a freeze cannot be ruled
out): the same code `flow.py graph` and gym_init.py give for the same freeze.
"""
import datetime as dt
import json
import os
import re
import sys
import time
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import foundry_profile as fp  # noqa: E402
import flow  # noqa: E402  (page chrome)
import flow_graph  # noqa: E402  (trace)
import flow_page  # noqa: E402  (the canvas)

P = fp.load(__file__)
HERE = P.root
PLANS = Path(str(P.get("paths.flow")))          # where the plan files lie, under a checkout
OUT = Path(str(P.get("paths.flow_out")))        # where the built pages go, under a checkout
ROADMAP = flow_graph.ROADMAP
SUFFIX = ".plan.toml"
NAME = re.compile(r"[a-z][a-z0-9-]{0,39}")
TAKEN = ("os", "system", "road", "workflow", "brief", "graph")  # the flow folders already hold files of these names
CHARTS = {}  # name -> a chart with its own facts and words (see chart()); a project's own reader fills it
STATES = {"have": "done", "new": "queued", "measure": "measure", "user": "user"}  # the plan's word -> the canvas's dot
STATE_WORDS = {"have": "in the tree today", "new": "to build", "measure": "to measure", "user": "waits on the user"}
EFFORTS = {"S": "under one slot", "M": "one or two slots", "L": "three or more slots"}
CONFIDENCE = {"read": "read from the tree or a brief that read its source", "memory": "general knowledge, to confirm", "estimate": "an estimate"}
STEP_KEYS = ("what", "why", "result", "input", "output", "tool", "where", "risk", "source", "changes")
OPEN_WORDS = ("open again", "still open", "waits for the user", "wait for the user")
SECTIONS = (("buys", "What it buys"), ("costs", "What it costs"), ("unknowns", "Not known yet"))


def checkout():
    """The checkout the shell stands in, when it is one of this project's (the main checkout or a worktree of it);
    else the one the profile was loaded for (FOUNDRY_ROOT, or the one that holds this script)."""
    if os.environ.get("FOUNDRY_ROOT"):
        return HERE
    top = flow.git(Path.cwd(), "rev-parse", "--show-toplevel").strip()
    try:
        return Path(top) if top and same(fp.main_checkout(Path(top)), flow.main_root()) else HERE
    except OSError:
        return HERE


def same(a, b):
    """Whether two paths are one folder on disk, however each is spelled (a drive letter, a UNC share, a mapped
    drive, a junction): the file system's answer, not the strings'."""
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def nearest(path):
    """The nearest folder of a path that exists (a folder not made yet has none of its own to ask about)."""
    near = Path(path).resolve()
    while not near.is_dir() and near != near.parent:
        near = near.parent
    return near


def under(path, folder):
    """Whether a path is the folder or lies in it. The part of the folder that exists is matched on disk (so any
    spelling of it counts); the rest of it, not made yet, is matched by name."""
    path, folder = Path(path).resolve(), Path(folder).resolve()
    if path == folder or folder in path.parents:
        return True
    base = nearest(folder)
    rest = [p.lower() for p in folder.relative_to(base).parts]
    for a in [path, *path.parents]:
        if same(a, base):
            return [p.lower() for p in path.relative_to(a).parts][:len(rest)] == rest
    return False


def in_main(target):
    """Whether a path lies in the main checkout: git's answer for its nearest folder that exists (a worktree kept
    under the main checkout's folder is its own checkout), else whether it sits under the main checkout's folder."""
    main = flow.main_root()
    top = flow.git(nearest(target), "rev-parse", "--show-toplevel").strip()
    if top:
        return same(top, main)
    return under(target, main)


# The freeze is read by flow_graph.py, for this tool, the graph's edits and gym_init.py alike: one reader, one rule.
freeze_marker = flow_graph.freeze_marker
frozen = flow_graph.frozen


class Frozen(str):
    """A refusal for the freeze of the main checkout (exit 3, as `flow.py graph` and gym_init.py give it); any other
    refusal is a plain text (exit 2)."""


def refusal_code(why):
    return 3 if isinstance(why, Frozen) else 2


def refused(opts, what, target):
    """Why this write may not land at `target`, or None. The main checkout takes files from the manager only (the
    crew never leaves one there), and during a freeze from nobody: only its git-ignored output folder is written then."""
    try:
        if not in_main(target):
            return None
        ignored = under(target, flow.main_root() / OUT.parts[0]) if not OUT.is_absolute() else under(target, OUT)
    except OSError as e:
        return f"{what}: could not tell whether {target} is in the main checkout ({e}); nothing written."
    by = opts.get("--by")
    try:
        flow_graph.manager(by if isinstance(by, str) else "")
    except flow_graph.Refused as e:
        return (f"{what} would write into the main checkout ({target}), which takes the manager's badge: --by \"<{P.badge_prefix} line>\" ({e}). "
                "Anyone else: run it from your own worktree" + (", or pass --out <a folder outside the main checkout>" if what == "build" else "") + ".")
    if not ignored:
        state = frozen()
        if state is None:
            return Frozen(f"{what}: the crew office's resource queue or freeze could not be read, so a freeze cannot be ruled out; nothing written to {target}.")
        runs, maybe = state
        if maybe:
            print(f"plan_flow: note: {', '.join(maybe)} holds or waits for the shared resource at prio 0 or as a whole, under a plain id (the roster's COUNTED?). "
                  "This tool, like the office and the board, sees a counted run only by its queue id: if that job is one, the freeze is yours to keep by hand "
                  "(`office.py freeze on`).", file=sys.stderr)
        if runs:
            return Frozen(f"{what} would change the main checkout during a freeze ({'; '.join(runs)}). "
                          "Wait until the counted run ends, its records are committed and the freeze is lifted"
                          + ("; a build into the main checkout's git-ignored output folder is allowed meanwhile." if what == "build" else "."))
    return None


def write_refused(root, cmd, opts):
    """Why `new` or `build` may not write for this checkout and these options, or None. Every other command only reads."""
    if cmd == "new":
        return refused(opts, "new", root / PLANS)
    if cmd == "build":
        return refused(opts, "build", Path(opts["--out"]) if isinstance(opts.get("--out"), str) else root / OUT)
    return None


def read(path):
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def roadmap_rows(root, ids, bad):
    """Where each named decision row of the roadmap stands. A row that is not there is a problem line."""
    road = read(flow.at(root, "roadmap")) or ""
    rows = {}
    for d in ids:
        m = re.search(r"^\| " + re.escape(d) + r" \|[^|]*\| (.*?) \| [^|]* \| [^|]* \|$", road, re.M)
        if not m:
            bad.append(f"{ROADMAP} has no {d} row")
            continue
        cell = m[1]
        low = cell.lower()
        rows[d] = {"text": cell, "decided": cell.startswith("**Decided") and not any(w in low for w in OPEN_WORDS)}
    return rows


def cycle(ids, pre):
    """One id on a cycle of `pre` (id -> the ids it needs), or None."""
    seen = {}

    def walk(n):
        if seen.get(n) == 1:
            return n
        if seen.get(n) == 2:
            return None
        seen[n] = 1
        for p in pre.get(n, ()):
            hit = walk(p)
            if hit:
                return hit
        seen[n] = 2
        return None

    for i in ids:
        hit = walk(i)
        if hit:
            return hit
    return None


def build_model(root, path, name=None, rows=(), bad=None, then="the plan's order"):
    """(nodes by id, edges, problems, meta) from one plan file and the tree. `rows`: roadmap decision rows to read
    beside the ones the plan's decisions name. `bad`: problem lines the caller already has. `then`: why one stage follows the last."""
    bad = [] if bad is None else bad
    try:
        shown = path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        shown = path.name
    text = read(path)
    if text is None:
        return {}, [], bad + [f"{shown} is missing"], {}
    try:
        plan = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        return {}, [], bad + [f"{shown} is not TOML: {e}"], {}
    nodes, edges = {}, []

    def tables(key):
        """The plan's [[key]] tables that carry an id; one without is a problem line and is left out."""
        got = plan.get(key, [])
        if not isinstance(got, list):
            bad.append(f"{key} must be written as [[{key}]] tables")
            return []
        out = []
        for i, raw in enumerate(got):
            if not isinstance(raw, dict) or not isinstance(raw.get("id"), str) or not raw["id"]:
                bad.append(f"{key} {i + 1} has no id")
            else:
                out.append(raw)
        return out

    def names(raw, key):
        v = raw.get(key, [])
        if not isinstance(v, list) or any(not isinstance(x, str) for x in v):
            bad.append(f"{raw['id']}: {key} must be a list of ids")
            return []
        return v

    def add(n):
        if n["id"] in nodes:
            bad.append(f"two nodes are named {n['id']}")
        nodes[n["id"]] = n

    def link(a, out, b, inn, kind, why=""):
        edges.append({"a": a, "out": out, "b": b, "in": inn, "kind": kind, "why": why})

    def anchor(n, raw):
        a = raw.get("anchor")
        if not a:
            return
        if not isinstance(a, list) or len(a) != 2 or any(not isinstance(x, str) for x in a):
            bad.append(f"{raw['id']}: an anchor is [file, text]")
            return
        body = read(root / a[0])
        n["anchor"] = a[0]
        if body is None:
            bad.append(f"{raw['id']}: its anchor {a[0]} is gone")
        elif a[1] and a[1] not in body:
            bad.append(f"{raw['id']}: {a[0]} no longer holds '{a[1]}'")

    stages = tables("stage")
    order = [s["id"] for s in stages]
    for i, s in enumerate(stages):
        add({"id": s["id"], "type": "stage", "title": s.get("title", ""), "about": s.get("about", ""), "n": i + 1, "state": "stage", "steps": [], "label": ""})
        if i:
            link(order[i - 1], "next", s["id"], "after", "then", then)
    if not stages:
        bad.append("the plan has no stage")
    for raw in tables("step"):
        st = raw.get("stage")
        n = {"id": raw["id"], "type": "step", "title": raw.get("title", ""), "stage": st, "plan_state": raw.get("state"), "effort": raw.get("effort"),
             "confidence": raw.get("confidence"), "needs": names(raw, "needs")}
        for k in STEP_KEYS:
            if raw.get(k):
                n[k] = raw[k]
        if st not in order:
            bad.append(f"{raw['id']}: no stage '{st}'")
        if n["plan_state"] not in STATES:
            bad.append(f"{raw['id']}: state must be one of {', '.join(STATES)}")
        if n["effort"] not in EFFORTS:
            bad.append(f"{raw['id']}: effort must be S, M or L")
        if n["confidence"] not in CONFIDENCE:
            bad.append(f"{raw['id']}: confidence must be one of {', '.join(CONFIDENCE)}")
        n["state"] = STATES.get(n["plan_state"], "waits")
        n["label"] = f"{STATE_WORDS.get(n['plan_state'], '?')} · {n['effort']}"
        anchor(n, raw)
        add(n)
        if st in order and nodes[st]["type"] == "stage":
            nodes[st]["steps"].append(raw["id"])
    for n in [x for x in nodes.values() if x["type"] == "step"]:
        for p in n["needs"]:
            if p not in nodes or nodes[p]["type"] != "step":
                bad.append(f"{n['id']}: needs '{p}', which is not a step")
            else:
                link(p, "out", n["id"], "in", "needs", "must be done first")
    steps = {i: n["needs"] for i, n in nodes.items() if n["type"] == "step"}
    hit = cycle(list(steps), steps)
    if hit:
        bad.append(f"the steps' needs form a cycle through {hit}")
    decisions = tables("decision")
    asked = list(dict.fromkeys(list(rows) + [d["roadmap"] for d in decisions if isinstance(d.get("roadmap"), str) and d["roadmap"]]))
    road = roadmap_rows(root, asked, bad)
    for raw in decisions:
        row = road.get(raw.get("roadmap")) if raw.get("roadmap") else None
        answer = raw.get("answer", "")
        decided = bool(answer or (row and row["decided"]))
        n = {"id": raw["id"], "type": "decision", "title": raw.get("title", ""), "question": raw.get("question", ""), "options": names(raw, "options"),
             "lean": raw.get("lean", ""), "answer": answer, "roadmap": raw.get("roadmap", ""), "row": flow_page.cut(row["text"], 420) if row else "",
             "state": "done" if decided else "user", "label": "answered by the user" if answer else "decided in the roadmap" if decided else "the user's to answer"}
        anchor(n, raw)
        add(n)
        for g in names(raw, "gates"):
            if g not in order:
                bad.append(f"{raw['id']}: gates '{g}', which is not a stage")
            else:
                link(raw["id"], "decides", g, "gate", "gate", "the answer shapes this stage")
    for raw in tables("lane"):
        add({"id": raw["id"], "type": "lane", "title": raw.get("title", ""), "checks": names(raw, "checks"), "state": "waits", "label": "no contract yet", "of": raw.get("of", "")})
        if raw.get("of") not in order:
            bad.append(f"{raw['id']}: its stage '{raw.get('of')}' is not a stage")
        else:
            link(raw["of"], "gym", raw["id"], "checkpoint", "sub", "the stage is done when this lane says PASS")
    tally = {"states": {}, "efforts": {}}
    gated = {}
    for e in edges:
        if e["kind"] == "gate":
            gated.setdefault(e["b"], []).append(e["a"])
    for s in order:
        if nodes[s]["type"] != "stage":  # a later table took the stage's id; "two nodes are named" already says so
            continue
        mine = [nodes[i] for i in nodes[s]["steps"] if nodes[i]["type"] == "step"]
        if not mine:
            bad.append(f"stage {s} has no step")
        st = {k: sum(1 for n in mine if n["plan_state"] == k) for k in STATES}
        ef = {k: sum(1 for n in mine if n["effort"] == k) for k in EFFORTS}
        nodes[s].update(tally_states=st, tally_efforts=ef,
                        gated=gated.get(s, []), label=f"{len(mine)} step{'' if len(mine) == 1 else 's'}" + (" · gated by " + ", ".join(gated[s]) if s in gated else ""))
        for k, v in st.items():
            tally["states"][k] = tally["states"].get(k, 0) + v
        for k, v in ef.items():
            tally["efforts"][k] = tally["efforts"].get(k, 0) + v
    head = plan.get("meta", {}) if isinstance(plan.get("meta", {}), dict) else {}
    sections = [{"title": title, "items": head[k]} for k, title in SECTIONS if isinstance(head.get(k), list) and head[k]]
    for s in plan.get("section", []) if isinstance(plan.get("section", []), list) else []:
        if isinstance(s, dict) and s.get("title"):
            sections.append({"title": str(s["title"]), "items": s["items"]} if isinstance(s.get("items"), list) else {"title": str(s["title"]), "text": str(s.get("text", ""))})
    meta = {"plan": head, "tally": tally, "state_words": STATE_WORDS, "efforts": EFFORTS, "confidence": CONFIDENCE, "stages": [s for s in order if nodes[s]["type"] == "stage"],
            "sections": sections, "name": name or "", "file": shown,
            "words": {"status": "", "cli": f"plan_flow.py show {name}" if name else "", "trace": f"plan_flow.py trace {name}" if name else ""}}
    return nodes, edges, bad, meta


def show(nodes, edges, nid, out=None):
    out = out or sys.stdout
    n = nodes.get(nid)
    if not n:
        print(f"no node '{nid}'; ids: {', '.join(sorted(nodes))}", file=sys.stderr)
        return 2
    print(f"{n['type']} {nid}: {n['title']} ({n['label']})", file=out)
    for k in ("about", "question", "answer", "lean", "row") + STEP_KEYS:
        if n.get(k):
            print(f"  {k}: {n[k]}", file=out)
    for k in ("options", "checks", "steps"):
        for v in n.get(k, []):
            print(f"  {k[:-1]}: {v}", file=out)
    for name, es, end in (("comes in", [e for e in edges if e["b"] == nid], "a"), ("goes out", [e for e in edges if e["a"] == nid], "b")):
        for e in es:
            print(f"  {name}: {e[end]}  ({e['kind']}; {e['why']})", file=out)
    return 0


def traced(edges, nid, up):
    """The ids before nid (up) or after it, nearest first, each once."""
    g = {"edges": [{"from": e["a"], "to": e["b"]} for e in edges]}
    return list(dict.fromkeys(e["from"] if up else e["to"] for _, e in flow_graph.trace(g, nid, up)))


PINS = {"stage": (["after", "gate"], ["next", "steps", "gym"]), "decision": ([], ["decides"]), "step": (["in"], ["out"]), "lane": (["checkpoint"], [])}


def shell(file, find, aria="Plan chart canvas"):
    """The canvas's buttons and words for one plan. `file`: the plan's path as the hint names it."""
    return {"views": [("pipeline", "Pipeline"), ("all", "Every step"), ("ask", "Your questions")], "find": find,
            "toggle": "show steps already in the tree", "aria": aria,
            "hint": "Drag to pan, Ctrl + wheel or the buttons to zoom, click a node for its details and everything before and after it, "
                    f"double-click a stage to open its steps. This is a plan: nothing on it is built. It is edited in {flow.esc(file)}."}


P_CSS = """
.gn.st-measure .sd{fill:var(--s7)}.ge.needs{stroke:var(--s1);stroke-width:1.3}
.gpanel ul{margin:2px 0 2px 16px;padding:0;color:var(--ink2)}.gpanel li{margin:2px 0}
"""

P_JS = r"""
const PINS=D.pins,M=D.meta,WORDS=M.words||{};
const isOn=n=>S.done||n.type!=='step'||n.plan_state!=='have';
const list=a=>a&&a.length?'<ul>'+a.map(x=>'<li>'+esc(x)+'</li>').join('')+'</ul>':'';
const tally=(t,words)=>Object.keys(words).filter(k=>t[k]).map(k=>t[k]+' '+words[k]).join(', ');
const asks=D.nodes.filter(n=>n.type==='decision');
const follow=()=>{const s=M.stages,n=s.length;if(!n)return'no stage yet';
  if(n===1)return'one stage so far: '+esc(s[0]);
  return'follow '+esc(s[0])+' to '+esc(s[n-1])+(n<=3?', top to bottom':': down the first column, up the second'+(n>9?', and so on in turn':n>6?', down the third':''))};
const P={home:'pipeline',keepFrom:1,small:{step:2},
opens:n=>n.type==='stage',
foot:n=>n.label,
reveal(n){S.sub=null;if(n.type==='step'){S.view='all';if(!isOn(n))S.done=true}else S.view=n.type==='decision'?'ask':'pipeline'},
scene(nodes,add){
  let cols=[],edges=[],extra=[];
  if(S.view==='sub'&&N.has(S.sub)){
    const m=N.get(S.sub),inn=D.edges.filter(e=>e.b===m.id),out=D.edges.filter(e=>e.a===m.id);
    inn.forEach(e=>add(N.get(e.a)));add(m);out.forEach(e=>add(N.get(e.b)));
    const steps=m.steps.map(id=>N.get(id));steps.forEach(add);
    edges=inn.concat(out).concat(steps.map(s=>({a:m.id,out:'steps',b:s.id,in:'in',kind:'sub',why:'a step of this stage'})))
      .concat(D.edges.filter(e=>e.kind==='needs'&&nodes.has(e.a)&&nodes.has(e.b)));
    cols=[inn.map(e=>e.a),[m.id],m.steps,out.map(e=>e.b)];
    return{cols,edges,extra,nowrap:true}}
  if(S.view==='all'){
    D.nodes.filter(n=>n.type==='step'&&isOn(n)).forEach(add);
    edges=D.edges.filter(e=>e.kind==='needs'&&nodes.has(e.a)&&nodes.has(e.b));
    cols=M.stages.map(s=>N.get(s).steps.filter(id=>nodes.has(id)));
    return{cols,edges,extra,nowrap:true}}
  if(S.view==='ask'){
    D.nodes.filter(n=>n.type==='decision'||n.type==='stage').forEach(add);
    edges=D.edges.filter(e=>e.kind==='gate');
    cols=[asks.map(n=>n.id),M.stages.slice()];
    return{cols,edges,extra,nowrap:true}}
  D.nodes.filter(n=>n.type==='stage'||n.type==='lane').forEach(add);
  edges=D.edges.filter(e=>nodes.has(e.a)&&nodes.has(e.b));
  // three stages to a column, every other column bottom to top, so each "next" link stays short and the canvas keeps the order
  for(let i=0;i<M.stages.length;i+=3){const c=M.stages.slice(i,i+3);cols.push((i/3)%2?c.reverse():c)}
  cols.push(D.nodes.filter(n=>n.type==='lane').map(n=>n.id));
  return{cols,edges,extra,nowrap:true}},
crumb(){return S.view==='sub'?'<a data-back="1">'+(S.from==='all'?'Every step':'Pipeline')+'</a> › inside <b>'+esc(N.get(S.sub).title)+'</b>: what gates it, its steps in order, what follows':
  S.view==='all'?'one column per stage, left to right; a line means "must be done first"':S.view==='ask'?(asks.length?'each question that is yours, and the stages its answer shapes':'this plan asks nothing of you yet'):follow()},
status(){let t=M.counts+' · a plan, nothing built · '+(WORDS.status?esc(WORDS.status)+' · ':'')+'built '+esc(M.built)+' at '+esc(M.head);
  if(M.problems.length)t+=' · <b class="bad">'+M.problems.length+' out of step with the tree</b>: '+esc(M.problems[0]);
  return t},
intro(){const p=M.plan,t=M.tally;
  return'<h3>'+esc(p.title||'The plan')+'</h3><p>'+esc(p.question||'')+'</p>'
  +'<h4>Size of the work (this plan\'s estimates)</h4><p>'+esc(tally(t.states,M.state_words))+'.</p><p>'+esc(tally(t.efforts,M.efforts))+'.</p>'
  +(M.sections||[]).map(s=>'<h4>'+esc(s.title)+'</h4>'+(s.items?list(s.items):'<p>'+esc(s.text||'')+'</p>')).join('')
  +(asks.length?'<h4>Yours to answer</h4>'+asks.map(n=>'<button type="button" class="lk" data-go="'+esc(n.id)+'"><b>'+esc(n.id)+'</b> '+esc(n.title)+'<small>'+esc(n.label)+'</small></button>').join(''):'')
  +'<h4>Reading it</h4><p>Blue-grey dot: to build · purple: to measure first · amber: waits on you · green: in the tree today. Dashed amber line: a decision shapes that stage. Blue line: must be done first.</p>'
  +(M.problems.length?'<h4>Out of step ('+M.problems.length+')</h4>'+list(M.problems):'')},
detail(n){const o=[];
  if(n.type==='stage'){
    if(S.view!=='sub'||S.sub!==n.id)o.push('<div class="row3"><div class="seg"><button type="button" data-open="'+esc(n.id)+'">Open its '+n.steps.length+(n.steps.length===1?' step':' steps')+'</button></div></div>');
    o.push(row('Stage',n.n+' of '+M.stages.length)+row('What',n.about)+row('Shaped by your answers to',(n.gated||[]).join(', '))+row('Steps',tally(n.tally_states||{},M.state_words))+row('Effort (estimates)',tally(n.tally_efforts||{},M.efforts)));
    o.push('<h4>Its steps, in order</h4>');n.steps.forEach(id=>{const s=N.get(id);o.push('<button type="button" class="lk" data-go="'+esc(id)+'"><b>'+esc(id)+'</b> '+esc(s.title)+'<small>'+esc(s.label)+'</small></button>')})}
  else if(n.type==='step'){
    o.push(row('Stage',N.get(n.stage)?N.get(n.stage).title:n.stage)+row('What',n.what)+row('Why',n.why)+row('Result',n.result)+row('Goes in',n.input)+row('Comes out',n.output)+row('Tool',n.tool)+row('Where it runs',n.where)
      +row('Effort (an estimate)',n.effort+': '+M.efforts[n.effort])+row('State',M.state_words[n.plan_state])+row('Risk',n.risk)+row('Changes',n.changes)
      +row('How sure',M.confidence[n.confidence])+row('From',n.source)+row('Checked against',n.anchor))}
  else if(n.type==='decision'){
    o.push(row('The question',n.question));if(n.options.length)o.push('<h4>Options</h4>'+list(n.options));
    o.push(row('Your answer',n.answer)+row('This plan\'s lean',n.lean)+row('Roadmap row',n.roadmap)+row('Where that row stands',n.row))}
  else if(n.type==='lane')o.push('<h4>What it would check</h4>'+list(n.checks));
  return o.join('')},
linkNote(e){return' · '+e.kind},
cli(n){return WORDS.cli?'<h4>From the command line</h4><code>'+esc(WORDS.cli)+' '+esc(n.id)+'</code>'+(WORDS.trace?'<code>'+esc(WORDS.trace)+' '+esc(n.id)+' --up</code>':''):''}};
"""


def graph_data(root, nodes, edges, bad, meta, now):
    c = {}
    for n in nodes.values():
        c[n["type"]] = c.get(n["type"], 0) + 1
    meta = dict(meta, problems=bad, built=dt.datetime.fromtimestamp(now).strftime("%a %Y-%m-%d %H:%M"),
                head=flow.git(root, "rev-parse", "--short", "HEAD").strip() or "unknown commit",
                counts=", ".join(f"{v} {k}{'' if v == 1 else 's'}" for k, v in sorted(c.items())) + f", {len(edges)} links")
    return {"nodes": list(nodes.values()), "edges": edges, "pins": {t: {"i": i, "o": o} for t, (i, o) in PINS.items()}, "meta": meta}


def page(data, title, h1, stamp, sub, canvas_shell, fallback):
    """One plan chart's page. `stamp` and `sub` are HTML; `title` and `h1` are text."""
    return "".join([
        '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
        f'<title>{flow.esc(title)}</title><style>{flow.CSS}{flow_page.CSS}{P_CSS}</style></head><body><main>',
        f"<h1>{flow.esc(h1)}</h1>", f'<p class="stamp">{stamp}</p>', f'<p class="sub">{sub}</p>',
        flow_page.canvas_html(data, fallback, canvas_shell),
        f"<script>{flow_page.js(P_JS)}</script></main></body></html>"])


def render(data):
    m = data["meta"]
    name, title = m["name"], m["plan"].get("title") or m["name"]
    first = next((n["id"] for n in data["nodes"] if n["type"] == "step"), "A1")
    n = len(m["stages"])
    return page(
        data, f"{P.project} plan: {title}", f"{P.project} plan: {title}, as a flow chart",
        f'Built {flow.esc(m["built"])} at {flow.esc(m["head"])} by plan_flow.py from {flow.esc(m["file"])}. '
        "This is a plan to judge: nothing on it is built, and every effort is an estimate.",
        f"<b>Pipeline</b> shows the plan's {n} stage{'' if n == 1 else 's'} in order, with the gym lanes that would close them. "
        "<b>Your questions</b> shows the answers the plan needs from you and the stages each one shapes. <b>Every step</b> shows all of them "
        "with what must come first. Double-click a stage to open it; click a step for what goes in, what comes out, the tool, the risk and "
        "how sure the plan is.",
        shell(m["file"], f"Find a node ({flow.esc(first)}, a word of its title…)"),
        f"<p>The chart needs scripts. `plan_flow.py edges {flow.esc(name)}` prints every link.</p>")


def chart(name):
    """One plan chart by name: where its plan is, how its model is built and how its page is drawn. A chart with
    facts of its own (a project's reader that checks its plan against more than anchors) puts the same four keys in
    CHARTS[name]: its "model" is a callable root -> (nodes, edges, problems, meta), and it may hand build_model its
    own `rows`, `bad` and `then`."""
    if name in CHARTS:
        return CHARTS[name]
    rel = PLANS / (name + SUFFIX)
    return {"name": name, "plan": rel, "model": lambda root: build_model(root, root / rel, name), "render": render}


def plan_names(root):
    return sorted(p.name[:-len(SUFFIX)] for p in (root / PLANS).glob("*" + SUFFIX))


def counts(nodes, edges):
    c = {}
    for n in nodes.values():
        c[n["type"]] = c.get(n["type"], 0) + 1
    return ", ".join(f"{v} {k}" for k, v in sorted(c.items())) + f", {len(edges)} links"


def put(path, text):
    """Write a built file as a new file put in the old one's place, so a link left at that name (a hardlink or a
    symlink to a file elsewhere) is replaced, never written through."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.unlink(missing_ok=True)
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def run(c, cmd, rest, opts, root):
    """One command on one chart. Returns the exit code; None when the command or its arguments are not known."""
    nodes, edges, bad, meta = c["model"](root)
    if cmd == "selftest" and not rest:
        for line in bad:
            print("PROBLEM " + line)
        print(f"{c['name']} flow selftest: {counts(nodes, edges)}, {len(bad)} problems")
        return 1 if bad or not nodes else 0
    if cmd == "edges" and not rest:
        for e in edges:
            print(f"{e['kind']:6} {e['a']}.{e['out']} -> {e['b']}.{e['in']}  # {e['why']}")
        for line in bad:
            print("PROBLEM " + line)
        return 0
    if cmd == "show" and len(rest) == 1:
        return show(nodes, edges, rest[0])
    if cmd == "trace" and len(rest) == 1:
        if rest[0] not in nodes:
            return show(nodes, edges, rest[0])
        for way in [w for w in ("up", "down") if "--" + w in opts or not ({"--up", "--down"} & set(opts))]:
            got = traced(edges, rest[0], way == "up")
            print(f"{'before' if way == 'up' else 'after'} {rest[0]} ({len(got)}): " + (", ".join(got) or "nothing"))
        return 0
    if cmd == "build" and not rest:
        if not nodes:
            for line in bad:
                print("PROBLEM " + line, file=sys.stderr)
            return 1
        data = graph_data(root, nodes, edges, bad, meta, time.time())
        out = Path(opts["--out"]) if isinstance(opts.get("--out"), str) else root / OUT  # a branch's chart never lands on the main checkout's page
        out.mkdir(parents=True, exist_ok=True)
        put(out / f"{c['name']}.html", c["render"](data))
        put(out / f"{c['name']}.graph.json", json.dumps(data, ensure_ascii=False, indent=1) + "\n")
        print(f"wrote {out / (c['name'] + '.html')} and {c['name']}.graph.json: {data['meta']['counts']}")
        for line in bad:
            print("PROBLEM " + line)
        return 0
    return None


TEMPLATE = """# {title}: a plan to judge, not a decision.
#
# plan_flow.py draws this file as {name}.html in the flow output folder and checks it (`plan_flow.py selftest {name}`).
# Edit the plan here and run the selftest after every edit; the page is never edited. Nothing here is built
# because the plan says so: a step is done when the tree and its gym lane say so.
#
# A step's `state`: "have" (in the tree today), "new" (to build), "measure" (a fact nobody has read yet),
# "user" (waits on the user). `effort` is this plan's own estimate, never a measurement: S (under one slot),
# M (one or two slots), L (three or more). `confidence` says where the claim comes from: "read" (from the tree
# or a brief that read its source), "memory" (general knowledge, to confirm), "estimate".
# `needs` lists the steps that must be done first. An `anchor` is a file and a text it must hold; the selftest
# fails when either is gone, so the plan cannot drift from the tree unnoticed.
# A step may also say: why, result, input, output, tool, where, risk, source, changes.

[meta]
title = {title_q}
written = "{day}"
question = {question_q}
buys = []      # what the plan gains, one line each
costs = []     # what it costs, one line each
unknowns = []  # what nobody has measured or decided yet

# ---------------------------------------------------------------- stages, in order

[[stage]]
id = "S1"
title = "First stage"
about = "What this stage does and why it comes first."

# ---------------------------------------------------------------- steps

[[step]]
id = "A1"
stage = "S1"
title = "First step"
what = "What is done, in one or two sentences."
state = "new"
effort = "S"
confidence = "estimate"
needs = []
# anchor = ["path/in/the/tree", "a text that file must hold"]

# ---------------------------------------------------------------- decisions (the user's)
# The answer is the user's words, quoted, with the time and the question asked. `roadmap` names a decision row
# of the roadmap (D2); the chart shows where that row stands.
#
# [[decision]]
# id = "Q1"
# title = "The question in a few words"
# question = "The whole question."
# options = ["One answer", "Another"]
# lean = "What this plan would pick, and why."
# answer = ""
# gates = ["S1"]
# roadmap = ""

# ---------------------------------------------------------------- gym lanes that would close a stage
#
# [[lane]]
# id = "L1"
# of = "S1"
# title = "What the lane proves"
# checks = ["One thing it measures", "One control"]

# ---------------------------------------------------------------- more for the chart's first panel
#
# [[section]]
# title = "A heading"
# items = ["one line", "another"]   # or: text = "a paragraph"
"""


def new(root, name, opts):
    if not NAME.fullmatch(name) or name in TAKEN:
        print(f"plan_flow: a plan's name is lower-case letters, digits and dashes, starting with a letter, and not one of {', '.join(TAKEN)}", file=sys.stderr)
        return 2
    title = opts.get("--title")
    if not isinstance(title, str) or not title.strip():
        print('plan_flow: new needs --title "what the plan is about"', file=sys.stderr)
        return 2
    why = write_refused(root, "new", opts)
    if why:
        print("plan_flow: " + why, file=sys.stderr)
        return refusal_code(why)
    path = root / PLANS / (name + SUFFIX)
    if path.exists():
        print(f"plan_flow: {path} is already there; edit it, or pick another name", file=sys.stderr)
        return 1
    question = opts.get("--question") if isinstance(opts.get("--question"), str) else ""
    one = " ".join(title.split())
    text = TEMPLATE.format(name=name, title=one, title_q=json.dumps(one, ensure_ascii=False), question_q=json.dumps(" ".join(question.split()), ensure_ascii=False),
                           day=dt.date.today().isoformat())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {path}\nnext: write its stages, steps and decisions, then `plan_flow.py selftest {name}` and `plan_flow.py build {name}`")
    return 0


def template_check():
    """The selftest of a project with no plan yet: the plan `new` would write, built in a temp folder, must hold no
    problem and draw a page. Exit 1 when it does not. It writes nothing outside that temp folder."""
    import tempfile
    with tempfile.TemporaryDirectory(prefix="foundry-plan-selftest-") as td:
        root = Path(td)
        path = root / "template.plan.toml"
        path.write_text(TEMPLATE.format(name="template", title="Template", title_q='"Template"', question_q='""', day=dt.date.today().isoformat()),
                        encoding="utf-8", newline="\n")
        nodes, edges, bad, meta = build_model(root, path, "template")
        if nodes and not bad:
            try:
                page = render(graph_data(root, nodes, edges, bad, meta, time.time()))
                if 'id="gdata"' not in page:
                    bad.append("the template's page holds no chart data")
            except Exception as e:
                bad.append(f"the template's page could not be drawn ({type(e).__name__}: {e})")
    for line in bad:
        print("PROBLEM " + line)
    print(f"no plan under {PLANS.as_posix()} yet; the template flow selftest: {counts(nodes, edges)}, {len(bad)} problems")
    return 1 if bad or not nodes else 0


def usage():
    print(__doc__.strip().split("\n\n")[1], file=sys.stderr)
    return 2


VALUED = ("--title", "--question", "--by", "--out")  # the options that take a value; every other option is a switch


def parse(argv):
    """(arguments, options). An option's value is joined to it (--out=DIR) or follows it (--out DIR); a valued
    option with nothing after it, and every switch (--up, --down), is True."""
    args, opts, i = [], {}, 0
    while i < len(argv):
        a = argv[i]
        i += 1
        if not a.startswith("--"):
            args.append(a)
        elif "=" in a:
            k, v = a.split("=", 1)
            opts[k] = v
        elif a in VALUED and i < len(argv):
            opts[a] = argv[i]
            i += 1
        else:
            opts[a] = True
    return args, opts


def main(argv, root=None):
    root = root or checkout()
    args, opts = parse(argv)
    cmd = args[0] if args else "list"
    if cmd == "build":
        why = write_refused(root, "build", opts)
        if why:
            print("plan_flow: " + why, file=sys.stderr)
            return refusal_code(why)
    known = plan_names(root)
    if cmd == "list" and len(args) <= 1:
        for name in known:
            nodes, edges, bad, meta = chart(name)["model"](root)
            print(f"{name:14} {meta.get('plan', {}).get('title', '') or '(no title)'}: {counts(nodes, edges)}, {len(bad)} problems")
        if not known:
            print(f'no plan under {PLANS.as_posix()}; start one with `plan_flow.py new NAME --title "…"`')
        return 0
    if cmd == "new" and len(args) == 2:
        return new(root, args[1], opts)
    if cmd in ("selftest", "build") and len(args) == 1:  # every plan
        if not known and cmd == "selftest":  # nothing of the project's to check yet: the tool checks its own template
            return template_check()
        if not known:
            print(f"plan_flow: no plan under {PLANS.as_posix()}", file=sys.stderr)
            return 1
        return max(run(chart(name), cmd, [], opts, root) for name in known)
    if cmd in ("selftest", "build", "edges", "show", "trace") and len(args) >= 2:
        if args[1] not in known:
            print(f"plan_flow: no plan '{args[1]}'; plans: {', '.join(known) or 'none'}", file=sys.stderr)
            return 2
        code = run(chart(args[1]), cmd, args[2:], opts, root)
        return usage() if code is None else code
    return usage()


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main(sys.argv[1:]))
