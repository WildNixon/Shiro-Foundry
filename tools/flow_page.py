#!/usr/bin/env python3
"""The road graph's canvas on the workflow page (after UE5's Flow Graph): typed nodes with named pins, links that
land on their pins, pan and zoom, search, a details panel, tracing up and down any number of links, a milestone's
own sub-graph (the requirements it closes and its gym pipeline) and a view of the push's blocks.

flow.py builds the data here (graph_data) and embeds it; the page stays one static file with no library. The page
only shows: an edit is `flow.py graph ...` with the manager's badge, and the panel prints the command to use.

Nothing here reads the profile: flow.py hands over what a project names its own way in `ctx` (the first tier, the
goal, the named late stages, how a milestone's and a push block's ID read). A project may add its own reader that
draws a "system graph" from its code onto this same canvas: it passes canvas_html its own data and shell, and
js() its own page profile.
"""
import collections
import datetime as dt
import json
import re

KIND = {("done", "after"): "after", ("decides", "gate"): "gate", ("decides", "exit"): "gate", ("reached", "exit"): "reached",
        ("then", "after"): "then", ("runs", "push"): "runs", ("closes", "exit"): "feed"}
BLOCK = r"(?:[QP]\d+[a-z]?)"  # how a push block's title opens, unless ctx["BLOCK"] says otherwise
MS = r"(?:M\d+)"             # a milestone's ID, unless ctx["MS"] says otherwise


def cut(s, n):
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def day(ts):
    return dt.datetime.fromtimestamp(ts).strftime("%m-%d") if ts else None


def clock(ts, now):
    if not isinstance(ts, (int, float)):
        return str(ts) if ts else ""
    d = dt.datetime.fromtimestamp(ts)
    return d.strftime("%H:%M") if d.date() == dt.datetime.fromtimestamp(now).date() else d.strftime("%m-%d %H:%M")


def graph_data(M, ctx, authored, seeded_guess):
    """Everything the canvas draws. `authored`: the asset's links, or None; `seeded_guess`: the links read from
    the roadmap's prose, drawn (as guesses) while there is no asset."""
    MET, STAGES, LABEL, order = ctx["MET"], ctx["STAGES"], ctx["STATE_LABEL"], ctx["STAGE_ORDER"]
    reqs, ms, now = M["reqs"], M["ms"], M["now"]
    top, goal, late = ctx.get("TOP", "P0"), ctx.get("GOAL", "1.0"), list(ctx.get("LATE", ()))
    block_id = re.compile(r"\s*(?P<id>" + ctx.get("BLOCK", BLOCK) + r")\b[:,]?\s*")
    ms_id = re.compile(r"\b" + ctx.get("MS", MS) + r"\b")
    last = {}
    for e in M["evs"]:
        if e.get("ev") == "progress":
            last[e["id"]] = e
    live = {}
    for b in M["live"]:
        p = last.get(b["id"], {})
        live[b["id"]] = {"id": b["id"], "role": b["role"].lower(), "job": cut(b["job"], 150), "pct": p.get("pct"),
                         "eta": clock(p.get("eta"), now), "note": cut(p.get("note"), 150), "waits": p.get("waiting_on") or "",
                         "heard": clock(p.get("at"), now)}
    fails = collections.defaultdict(list)
    for f in M["state"]["failures"]:
        if f.get("status") in ("open", "planned") and isinstance(f.get("lane"), str):
            fails[f["lane"]].append([str(f.get("id") or "?"), f["status"], cut(f.get("what"), 130)])
    nodes = []
    for m in sorted(ms.values(), key=lambda m: ctx["mnum"](m["id"])):
        L = M["lanes"].get(m["lane"]) if m["lane"] else None
        c = collections.Counter("met" if reqs[i]["status"] in MET else reqs[i]["status"] for i in m["ids"] if reqs[i]["p"] == top)
        fl = fails.get(m["lane"], []) if m["lane"] else []
        nodes.append({
            "id": m["id"], "type": "milestone", "title": m["title"], "state": m["state"], "label": LABEL[m["state"]],
            "done": m["done"], "lane": m["lane"], "pipe": STAGES[m["stage"]], "theme": cut(m["theme"], 220), "why": cut(m["why"], 220),
            "p0": dict(c), "left": len(m["left"]), "reqs": [[i, reqs[i]["p"], reqs[i]["status"]] for i in m["ids"]],
            "crew": [live[x] for x in m["crew"] if x in live], "block": m["block"],
            "verdict": list(L["newest"]) if L and L["newest"] else None, "runs": L["runs"] if L else 0,
            "steps": [[STAGES[i], day(L["t"][i]) if L else None] for i in range(1, 5)],
            "fails": fl[:8], "fails_n": len(fl)})
    for d in M["decisions"].values():
        nodes.append({"id": d["id"], "type": "decision", "title": d["what"], "state": "done" if d["state"] == "decided" else "user",
                      "label": {"decided": "decided", "part": "part open", "open": "open"}[d["state"]], "done": d["state"] == "decided",
                      "stands": cut(d["stands"], 320), "owner": d["owner"], "need": cut(d["need"], 200), "holds": d.get("p0", [])})
    for sid in [s for s in order if s in M["stages"]]:
        s = M["stages"][sid]
        c = dict(s["counts"])
        nodes.append({"id": sid, "type": "stage", "title": s["title"], "theme": cut(s["theme"], 200), "exit": cut(s["exit"], 240),
                      "met": s["met"], "total": len(s["ids"]), "done": bool(s["ids"]) and s["met"] == len(s["ids"]),
                      "state": "done" if s["ids"] and s["met"] == len(s["ids"]) else "stage", "label": f"{s['met']} of {len(s['ids'])} exit IDs met",
                      "p0": {"met": s["met"], **{k: c.get(k, 0) for k in ("Part", "Planned", "Open")}}})
    blocks = []
    for b in M["state"]["shift"]["blocks"]:
        m = block_id.match(b["title"])
        if not m or any(x["id"] == m["id"] for x in blocks):
            continue
        st = str(b.get("status") or "pending")
        blocks.append({"id": m["id"], "type": "block", "title": cut(b["title"][m.end():], 90), "full": cut(b["title"], 400),
                       "state": {"done": "done", "partial": "work", "pending": "queued"}.get(st, "waits"), "label": st, "done": st == "done",
                       "time": cut(b.get("time"), 80), "done_when": cut(b.get("done_when"), 240), "note": cut(b.get("note"), 240),
                       "lane": b.get("checkpoint") if isinstance(b.get("checkpoint"), str) else None,
                       "names": [x for x in dict.fromkeys(ms_id.findall(b["title"])) if x in ms]})
    nodes += blocks
    known = {n["id"] for n in nodes}

    edges = []
    for e in (authored if authored is not None else seeded_guess):
        if e["from"] in known and e["to"] in known:
            kind = KIND.get((e["out"], e["in"]), "after")
            edges.append({"a": e["from"], "out": e["out"], "b": e["to"], "in": e["in"], "kind": "pgate" if kind == "gate" and e.get("ids") else kind,
                          "ids": e.get("ids") or [], "why": "" if e.get("seeded") else e.get("why", ""),
                          "soft": bool(e.get("seeded")) or authored is None})
    have = {(e["a"], e["b"]) for e in edges}
    rs = [s for s in order if s in M["stages"] and s not in late]  # the numbered stages: milestones feed these
    unmet = {s: {i for i in M["stages"][s]["ids"] if reqs[i]["status"] not in MET} for s in rs}
    for m in ms.values():  # read from the roadmap's Closes column and requirement rows, so never authored
        for s in rs:
            ids = sorted(set(m["ids"]) & unmet[s])
            if ids and not m["done"]:
                edges.append({"a": m["id"], "out": "closes", "b": s, "in": "exit", "kind": "feed", "ids": ids, "why": "", "soft": False, "derived": True})
    if not any(e["kind"] == "then" for e in edges):  # the map lists the push's blocks in order
        for a, b in zip(blocks, blocks[1:]):
            edges.append({"a": a["id"], "out": "then", "b": b["id"], "in": "after", "kind": "then", "ids": [], "why": "the map's order", "soft": False, "derived": True})
    for b in blocks:  # a block's title names the milestones it works on
        for mid in b["names"]:
            if (b["id"], mid) not in have:
                edges.append({"a": b["id"], "out": "runs", "b": mid, "in": "push", "kind": "runs", "ids": [], "why": "named in the block's title", "soft": False, "derived": True})
    G = M["graph"]
    return {"nodes": nodes, "edges": edges, "stages": [s for s in order if s in M["stages"]],
            "meta": {"built": dt.datetime.fromtimestamp(now).strftime("%a %Y-%m-%d %H:%M"), "asset": G is not None, "ok": M["graph_ok"],
                     "lines": M["graph_lines"], "bad": M["graph_bad"], "notes": M["graph_notes"][:12], "notes_n": len(M["graph_notes"]),
                     "soft": sum(1 for e in edges if e["soft"]), "live": len(live),
                     "tier": top, "goal": goal, "late": late, "roadmap": ctx.get("ROADMAP", "ROADMAP.md")}}


ROAD_SHELL = {
    "views": [("road", "Road"), ("push", "This push")], "find": "Find a node (M1, D2, a word of its title…)", "toggle": "show done and decided",
    "aria": "Road graph canvas",
    "hint": 'Drag to pan, Ctrl + wheel or the buttons to zoom, click a node for its details and its whole chain, '
            'double-click a milestone to open it. This page only shows the graph: a change is the manager\'s, through <code>flow.py graph</code>.'}


def canvas_html(data, fallback_svg, shell=ROAD_SHELL):
    """The canvas, its tool bar and panel; the old static SVG shows where scripts are off. `shell`: this graph's
    view buttons and words (the road graph's unless another graph passes its own)."""
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    on = ' class="on"'  # not written inside the f-string: a backslash in a replacement field needs Python 3.12
    views = "".join(f'<button type="button" data-view="{v}"{on if i == 0 else ""}>{name}</button>' for i, (v, name) in enumerate(shell["views"]))
    return (f'<div class="gbar"><div class="seg" role="group" aria-label="View">{views}</div>'
            '<span id="gcrumb" class="crumb"></span><span class="grow"></span>'
            f'<input id="gsearch" type="search" placeholder="{shell["find"]}" aria-label="Find a node">'
            f'<label class="chk"><input id="gdone" type="checkbox"> {shell["toggle"]}</label>'
            '<div class="seg"><button type="button" data-zoom="-1" aria-label="Zoom out">−</button><button type="button" data-zoom="0">Fit</button>'
            '<button type="button" data-zoom="1" aria-label="Zoom in">+</button></div></div>'
            '<div id="gstatus" class="gstatus"></div>'
            f'<div class="gwrap"><div id="canvas" class="canvas" tabindex="0" aria-label="{shell["aria"]}"></div>'
            '<aside id="gpanel" class="gpanel" aria-live="polite"></aside></div>'
            f'<p class="stamp">{shell["hint"]}</p>'
            f'<noscript><div class="panel scroll">{fallback_svg}</div></noscript>'
            f'<script type="application/json" id="gdata">{blob}</script>')


CSS = """
.gbar{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:6px 0}.grow{flex:1}
.seg{display:inline-flex;border:1px solid var(--border);border-radius:8px;overflow:hidden}
.seg button{font:inherit;font-size:12.5px;padding:4px 10px;border:0;background:var(--surface);color:var(--ink2);cursor:pointer}
.seg button+button{border-left:1px solid var(--border)}.seg button.on{background:var(--ink);color:var(--page)}
.seg button:hover:not(.on){color:var(--ink)}
#gsearch{font:inherit;font-size:12.5px;padding:4px 8px;border:1px solid var(--border);border-radius:8px;background:var(--surface);color:var(--ink);width:230px;max-width:100%}
.chk{font-size:12.5px;color:var(--ink2);white-space:nowrap}.crumb{font-size:12.5px;color:var(--ink2)}
.crumb a{color:var(--s1);cursor:pointer;text-decoration:underline}
.gstatus{font-size:12px;color:var(--ink2);margin:0 0 6px}.gstatus b.bad{color:var(--crit)}.gstatus b.soft{color:var(--serious)}
.gwrap{display:flex;gap:8px;align-items:stretch}
.canvas{flex:1;min-width:0;height:640px;background:var(--surface);border:1px solid var(--border);border-radius:10px;overflow:hidden;cursor:grab;
touch-action:none;outline:none;background-image:radial-gradient(var(--grid) 1px,transparent 1px);background-size:22px 22px}
.canvas:focus-visible{border-color:var(--ink2)}.canvas.drag{cursor:grabbing}.canvas svg{width:100%;height:100%;max-width:none}
.gpanel{width:320px;flex:none;height:640px;overflow:auto;background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:10px 12px;font-size:12.5px}
@media (max-width:900px){.gwrap{flex-direction:column}.gpanel{width:auto;height:auto;max-height:420px}.canvas{height:480px}}
.gpanel h3{font-size:14px;margin:0 0 2px}.gpanel h4{font-size:11px;margin:10px 0 3px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}
.gpanel p{margin:2px 0;color:var(--ink2)}.gpanel .tag{display:inline-block;font-size:11px;padding:0 6px;border-radius:9px;color:#fff;background:var(--tc);margin-right:4px}
.gpanel .lk{display:block;padding:2px 0;color:var(--ink);cursor:pointer;border:0;background:none;font:inherit;text-align:left;width:100%}
.gpanel .lk:hover b{text-decoration:underline}.gpanel .lk small{color:var(--muted);display:block}
.gpanel code{display:block;font-size:11px;background:var(--page);border:1px solid var(--border);border-radius:6px;padding:4px 6px;margin:3px 0;white-space:pre-wrap;word-break:break-word}
.gpanel .rq{display:inline-block;font-size:11px;border-left:3px solid var(--open);padding:0 5px;margin:0 4px 3px 0;white-space:nowrap}
.gpanel .row3{display:flex;gap:4px;margin:6px 0}.gpanel .row3 .seg button{font-size:11.5px;padding:3px 8px}
.t-milestone{--tc:var(--s1)}.t-decision{--tc:#b77d00}.t-stage{--tc:var(--ink2)}.t-block{--tc:var(--s7)}.t-lane{--tc:var(--s3)}.t-req{--tc:var(--muted)}.t-step{--tc:var(--s3)}
.gn{cursor:pointer;outline:none}.gn .box{fill:var(--surface);stroke:var(--border);stroke-width:1}.gn .hd{fill:var(--tc)}
.gn .tt{fill:#fff;font-size:11.5px;font-weight:600}.gn .chip{font-size:10px;font-weight:700;fill:#fff}
.gn .pl{font-size:9.5px;fill:var(--muted)}.gn .pin{fill:var(--surface);stroke:var(--axis);stroke-width:1.2}.gn .pin.used{fill:var(--tc);stroke:var(--tc)}
.gn .ft{font-size:10.5px;fill:var(--ink2)}.gn .sd{fill:var(--open)}
.gn.st-done .sd{fill:var(--good)}.gn.st-work .sd{fill:var(--s1)}.gn.st-queued .sd{fill:var(--s1l)}.gn.st-ready .sd{fill:var(--s7)}.gn.st-user .sd{fill:var(--warn)}.gn.st-stage .sd{fill:var(--ink2)}
.gn.done .hd{opacity:.55}.gn:focus-visible .box,.gn.sel .box{stroke:var(--ink);stroke-width:2}.gn.found .box{stroke:var(--s2);stroke-width:2}
.gn .pulse{fill:#fff;stroke:none}@media (prefers-reduced-motion:no-preference){.gn .pulse{animation:gpulse 1.6s ease-in-out infinite}}
@keyframes gpulse{0%,100%{opacity:1}50%{opacity:.25}}
.ge{fill:none;stroke:var(--ink2);stroke-width:1.6}.ge.gate{stroke:var(--warn);stroke-dasharray:6 4}.ge.pgate{stroke:var(--warn);stroke-width:1.1;stroke-dasharray:2 4}
.ge.feed{stroke:var(--axis);stroke-width:1.1}.ge.then,.ge.runs{stroke:var(--s7)}.ge.sub{stroke:var(--s3);stroke-width:1.2}.ge.soft{opacity:.5}
.gar{fill:var(--ink2)}svg.dim .gn:not(.hl),svg.dim .ge:not(.hl){opacity:.12}svg.dim .ge.hl{opacity:1;stroke-width:2.4}
.v-PASS{fill:#b8f5b8}.v-FAIL{fill:#ffc9c9}.v-VOID{fill:#e5e5e5}.v-MEASURING,.v-MARGINAL{fill:#ffe6a3}
"""

# The page script is three pieces in one closure: JS_A (the data and helpers), a profile (the pin table PINS and the
# object P: which nodes a view shows, what the panel says about a node) and JS_B (layout, drawing, pan, zoom, search,
# trace). ROAD_JS is the road graph's profile; a project's own reader brings its own. js(profile) joins them.
JS_A = r"""
(function(){
const blob=document.getElementById('gdata'),host=document.getElementById('canvas');if(!blob||!host)return;
const D=JSON.parse(blob.textContent),N=new Map(D.nodes.map(n=>[n.id,n])),panel=document.getElementById('gpanel');
const W=198,HEAD=22,ROW=13,FOOT=24,COL=W+78,GAP=12;
const S={view:'road',sub:null,done:false,sel:null,trace:'both',k:1,x:0,y:0,q:'',hits:[],hit:0};
let SC=null;
const esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const cut=(s,n)=>{s=String(s||'');return s.length<=n?s:s.slice(0,n-1).trimEnd()+'…'};
"""

ROAD_JS = r"""
const PINS={milestone:{i:['after','gate','push'],o:['done','closes','gym']},decision:{i:[],o:['decides']},stage:{i:['exit'],o:['reached']},
block:{i:['after'],o:['then','runs']},lane:{i:['checkpoint'],o:['verdict']},req:{i:['closes'],o:[]},step:{i:['in'],o:['out']}};
const P={home:'road',small:{req:1,step:2},drop:{lane:-12},flat:{feed:1},
opens:n=>n.type==='milestone',
foot:n=>n.label+(n.type==='milestone'&&!n.done?' · '+n.left+' '+D.meta.tier+' left':''),
reveal(n){if(n.type==='block')S.view='push';else{if(S.view!=='road'){S.view='road';S.sub=null}if(n.done)S.done=true}},
scene(nodes,add){
  let cols=[],edges=[],extra=[];
  if(S.view==='sub'&&N.has(S.sub)){
    const m=N.get(S.sub),inn=D.edges.filter(e=>e.b===m.id),out=D.edges.filter(e=>e.a===m.id);
    inn.forEach(e=>add(N.get(e.a)));add(m);out.forEach(e=>add(N.get(e.b)));
    const reqs=m.reqs.map(r=>({id:r[0],type:'req',title:r[0],label:r[1]+' · '+r[2],state:(r[2]==='PASS'||r[2]==='Decided')?'done':r[2]==='Part'?'work':r[2]==='Planned'?'queued':'waits',syn:1}));
    reqs.forEach(add);
    edges=inn.concat(out).concat(reqs.map(r=>({a:m.id,out:'closes',b:r.id,in:'closes',kind:'sub',ids:[],why:'',derived:1})));
    cols=[inn.map(e=>e.a),[m.id],out.map(e=>e.b).concat(reqs.map(r=>r.id))];
    if(m.lane){let prev=m.id,po='gym';
      m.steps.forEach((s,i)=>{const id='step'+i,n={id,type:'step',title:s[0],label:s[1]?'since '+s[1]:'not yet',state:s[1]?'done':'waits',syn:1};add(n);extra.push(id);
        edges.push({a:prev,out:po,b:id,in:'in',kind:'sub',ids:[],why:'',derived:1});prev=id;po='out'});
      const v=m.verdict,L={id:m.lane,type:'lane',title:'gym lane',state:v&&v[0]==='PASS'?'done':v?'work':'waits',label:v?m.runs+' counted run'+(m.runs===1?'':'s'):'no counted run yet',verdict:v,fails:m.fails,fails_n:m.fails_n,runs:m.runs,of:m.id,syn:1};
      add(L);extra.push(L.id);edges.push({a:prev,out:'out',b:L.id,in:'checkpoint',kind:'sub',ids:[],why:'',derived:1})}
  }else if(S.view==='push'){
    const bl=D.nodes.filter(n=>n.type==='block');bl.forEach(add);
    const ms=[...new Set(D.edges.filter(e=>e.kind==='runs').map(e=>e.b))];ms.forEach(id=>add(N.get(id)));
    const dec=[...new Set(D.edges.filter(e=>(e.kind==='gate'||e.kind==='pgate')&&ms.includes(e.b)&&N.get(e.a)&&(S.done||!N.get(e.a).done)).map(e=>e.a))];dec.forEach(id=>add(N.get(id)));
    edges=D.edges.filter(e=>nodes.has(e.a)&&nodes.has(e.b));cols=[bl.map(n=>n.id),dec,ms];
  }else{
    const vis=n=>S.done||!n.done;
    D.nodes.filter(n=>n.type!=='block'&&(n.type==='stage'||vis(n))).forEach(add);
    edges=D.edges.filter(e=>nodes.has(e.a)&&nodes.has(e.b));
    const ms=[...nodes.values()].filter(n=>n.type==='milestone'),depth=new Map(),pre=new Map(ms.map(m=>[m.id,[]]));
    edges.forEach(e=>{if(e.kind==='after'&&pre.has(e.b)&&pre.has(e.a))pre.get(e.b).push(e.a)});
    const dep=(id,seen)=>{if(depth.has(id))return depth.get(id);if(seen.has(id))return 0;seen.add(id);const p=pre.get(id);const d=p.length?1+Math.max(...p.map(x=>dep(x,seen))):0;depth.set(id,d);return d};
    ms.forEach(m=>dep(m.id,new Set()));const nl=Math.max(0,...depth.values())+1;
    cols=[[...nodes.values()].filter(n=>n.type==='decision').map(n=>n.id)];
    for(let k=0;k<nl;k++)cols.push(ms.filter(m=>depth.get(m.id)===k).map(m=>m.id));
    const st=D.stages.filter(s=>nodes.has(s)),late=new Set(D.meta.late||[]);cols.push(st.filter(s=>!late.has(s)));st.filter(s=>late.has(s)).forEach(s=>cols.push([s]));
  }
  return{cols,edges,extra,nowrap:S.view==='sub'}},
crumb(){return S.view==='sub'?'<a data-back="1">Road</a> › inside <b>'+esc(S.sub)+'</b>: what it waits on, what it closes, its gym pipeline':''},
status(){const m=D.meta;let t;
  if(!m.asset)t='<b class="soft">Links are guessed from '+esc(m.roadmap)+'\'s prose</b> (drawn faint): the graph is not seeded yet. The manager runs <code>flow.py graph seed</code>.';
  else if(!m.ok)t='<b class="bad">'+esc(m.lines.filter(x=>x.indexOf('TAMPERED')===0).join(' ')||m.lines.join(' '))+'</b>';
  else t=esc(m.lines[m.lines.length-1]||'')+(m.soft?' · <b class="soft">'+m.soft+' seeded link'+(m.soft===1?'':'s')+' not yet confirmed</b> (drawn faint)':'');
  if(m.bad&&m.bad.length&&m.ok)t+=' · <b class="bad">'+m.bad.length+' node or link out of step with the roadmap</b>: '+esc(m.bad[0]);
  if(m.notes_n)t+=' · '+m.notes_n+' prose mention'+(m.notes_n===1?'':'s')+' without a link';
  return t+' · '+m.live+' on the clock at the build ('+esc(m.built)+')'},
intro(){const c={};SC.nodes.forEach(x=>c[x.type]=(c[x.type]||0)+1);
  return'<h3>'+(S.view==='push'?'This push':S.view==='sub'?'Inside '+esc(S.sub):'Road to '+esc(D.meta.goal))+'</h3><p>'+Object.keys(c).map(k=>c[k]+' '+k+(c[k]===1?'':'s')).join(', ')+', '+SC.edges.length+' links in view.</p>'
  +'<h4>Node types</h4>'+['milestone','decision','stage','block','lane'].map(t=>'<p><span class="tag t-'+t+'">'+t+'</span> pins in: '+(PINS[t].i.join(', ')||'none')+'; out: '+(PINS[t].o.join(', ')||'none')+'</p>').join('')
  +'<h4>Links</h4><p>solid: must come first · dashed amber: a decision gates it (dotted: only some IDs) · thin grey: feeds a stage · purple: the push\'s blocks · faint: not confirmed by the manager</p>'
  +'<h4>Reading it</h4><p>Click a node to light everything before and after it. Double-click a milestone to open it. A white dot in a header means crew are on the clock for it.</p>'},
detail(n){const o=[];
  if(n.type==='milestone'){
    if(S.view!=='sub'||S.sub!==n.id)o.push('<div class="row3"><div class="seg"><button type="button" data-open="'+esc(n.id)+'">Open '+esc(n.id)+'</button></div></div>');
    o.push(row('Theme',n.theme)+row('Pipeline',n.pipe+(n.lane?', lane '+n.lane:', no lane yet'))+row('Newest counted run',n.verdict?n.verdict[0]+' ('+n.verdict[1]+(n.verdict[2]!=null?', n='+n.verdict[2]:'')+') of '+n.runs:'')+row('In this push',n.block)+row('Why here (the roadmap\'s words)',n.why));
    if(n.crew.length){o.push('<h4>On the clock at the build</h4>');n.crew.forEach(c=>o.push('<p><b>'+esc(c.id)+'</b> '+esc(c.role)+(c.pct!=null?' · '+esc(c.pct)+'%':'')+(c.eta?' · finish about '+esc(c.eta):'')+(c.waits?' · waits on '+esc(c.waits):'')+'<br>'+esc(c.note||c.job)+'</p>'))}
    if(n.reqs.length){o.push('<h4>Requirements it holds ('+n.left+' '+esc(D.meta.tier)+' left)</h4><p>');n.reqs.forEach(r=>o.push('<span class="rq" style="border-color:var('+((r[2]==='PASS'||r[2]==='Decided')?'--good':r[2]==='Part'?'--s1':r[2]==='Planned'?'--s1l':'--open')+')">'+esc(r[0])+' '+esc(r[1])+' '+esc(r[2])+'</span>'));o.push('</p>')}
  }else if(n.type==='decision')o.push(row('Where it stands',n.stands)+row('Owner',n.owner)+row('Needed before (the roadmap\'s words)',n.need)+row('Unmet '+D.meta.tier+' behind it',(n.holds||[]).join(', ')));
  else if(n.type==='stage')o.push(row('Theme',n.theme)+row('Exit (the roadmap\'s words)',n.exit));
  else if(n.type==='block')o.push(row('Block',n.full)+row('When',n.time)+row('Done when',n.done_when)+row('Note',n.note)+row('Checkpoint lane',n.lane));
  else if(n.type==='lane')o.push(row('Lane of',n.of)+row('Counted runs',n.runs)+row('Newest',n.verdict?n.verdict[0]+' ('+n.verdict[1]+')':''));
  if(n.fails&&n.fails_n){o.push('<h4>Open findings on lane '+esc(n.type==='lane'?n.id:n.lane)+' ('+n.fails_n+')</h4>');n.fails.forEach(f=>o.push('<p><b>'+esc(f[0])+'</b> '+esc(f[1])+': '+esc(f[2])+'</p>'));if(n.fails_n>n.fails.length)o.push('<p>…and '+(n.fails_n-n.fails.length)+' more on the map.</p>')}
  return o.join('')},
linkNote(e){return(e.ids&&e.ids.length&&e.kind!=='feed'?' · only '+esc(e.ids.join(', ')):'')+(e.kind==='feed'?' · '+e.ids.length+' unmet ID'+(e.ids.length===1?'':'s'):'')+(e.derived?' · read at build':e.soft?' · not confirmed':'')},
cli(n){const soft=D.edges.find(e=>e.soft&&(e.a===n.id||e.b===n.id));
  return'<h4>From the command line</h4><code>flow.py graph show '+esc(n.id)+'</code><code>flow.py graph trace '+esc(n.id)+' --up</code>'+(soft&&D.meta.asset?'<p>The manager confirms a seeded link:</p><code>flow.py graph confirm '+esc(soft.a)+' '+esc(soft.b)+' --why "…" --by "&lt;manager\'s line&gt;"</code>':'')}};
"""

JS_B = r"""
S.view=P.home;
const small=n=>!!P.small[n.type];
const hOf=n=>small(n)?38:HEAD+Math.max(PINS[n.type].i.length,PINS[n.type].o.length,1)*ROW+FOOT;
function pinY(n,name,side){if(small(n))return n.y+hOf(n)/2;const i=Math.max(0,PINS[n.type][side].indexOf(name));return n.y+HEAD+i*ROW+ROW/2+2}

function scene(){
  const nodes=new Map(),add=n=>{if(n&&!nodes.has(n.id))nodes.set(n.id,Object.assign({},n))};
  const r=P.scene(nodes,add),edges=r.edges,extra=r.extra||[];let cols=r.cols;
  cols=cols.map(c=>[...new Set(c)]).filter(c=>c.length);
  if(!r.nowrap){const MAXC=12,wide=[];cols.forEach(c=>{const parts=Math.ceil(c.length/MAXC),per=Math.ceil(c.length/parts);for(let i=0;i<c.length;i+=per)wide.push(c.slice(i,i+per))});cols=wide}
  const near=new Map([...nodes.keys()].map(k=>[k,[]]));edges.forEach(e=>{if(near.has(e.a)&&near.has(e.b)){near.get(e.a).push(e.b);near.get(e.b).push(e.a)}});
  const stack=()=>{const tall=Math.max(...cols.map(c=>c.reduce((s,id)=>s+hOf(nodes.get(id))+GAP,0)));
    cols.forEach((c,ci)=>{let y=(tall-c.reduce((s,id)=>s+hOf(nodes.get(id))+GAP,0))/2;c.forEach(id=>{const n=nodes.get(id);n.x=ci*COL;n.y=y;y+=hOf(n)+GAP})});return tall};
  let tall=cols.length?stack():0;
  for(let it=0;it<3;it++){cols.forEach(c=>{const key=new Map(c.map((id,i)=>{const ys=near.get(id).filter(x=>!c.includes(x)&&!extra.includes(x)).map(x=>nodes.get(x).y+hOf(nodes.get(x))/2);
    return[id,ys.length?ys.reduce((a,b)=>a+b,0)/ys.length:nodes.get(id).y+hOf(nodes.get(id))/2+i*1e-3]}));c.sort((a,b)=>key.get(a)-key.get(b))});tall=stack()}
  extra.forEach((id,i)=>{const n=nodes.get(id);n.x=COL+i*(W+36);n.y=tall+26+((P.drop||{})[n.type]||0)});
  const used=new Set();edges.forEach(e=>{used.add(e.a+'|o|'+e.out);used.add(e.b+'|i|'+e.in)});
  return{nodes,edges,used};
}

function closure(id,dir){const seen=new Set([id]),todo=[id];while(todo.length){const n=todo.pop();SC.edges.forEach(e=>{const[a,b]=dir==='up'?[e.b,e.a]:[e.a,e.b];if(a===n&&!seen.has(b)){seen.add(b);todo.push(b)}})}return seen}
function lit(){if(!S.sel||!SC.nodes.has(S.sel))return null;const up=S.trace!=='down'?closure(S.sel,'up'):new Set([S.sel]),dn=S.trace!=='up'?closure(S.sel,'down'):new Set([S.sel]);return{up,dn,all:new Set([...up,...dn])}}

function draw(){
  SC=scene();const L=lit(),o=[];
  o.push('<svg xmlns="http://www.w3.org/2000/svg" class="'+(L?'dim':'')+'"><defs><marker id="gar" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto"><path d="M0,0 L8,4 L0,8 z" class="gar"/></marker></defs><g id="gvp">');
  SC.edges.forEach(e=>{const a=SC.nodes.get(e.a),b=SC.nodes.get(e.b);if(!a||!b)return;const x1=a.x+W,y1=pinY(a,e.out,'o'),x2=b.x,y2=pinY(b,e.in,'i'),c=Math.max(46,Math.abs(x2-x1)/2);
    const on=L&&((L.up.has(e.a)&&L.up.has(e.b))||(L.dn.has(e.a)&&L.dn.has(e.b)));
    const same=a.x===b.x,mx=a.x+W/2,d=same?(b.y>a.y?'M'+mx+','+(a.y+hOf(a))+' L'+mx+','+(b.y-2):'M'+mx+','+a.y+' L'+mx+','+(b.y+hOf(b)+2)):'M'+x1+','+y1.toFixed(1)+' C'+(x1+c)+','+y1.toFixed(1)+' '+(x2-c)+','+y2.toFixed(1)+' '+(x2-2)+','+y2.toFixed(1);
    o.push('<path class="ge '+e.kind+(e.soft?' soft':'')+(on?' hl':'')+'" d="'+d+'"'+((P.flat||{})[e.kind]?'':' marker-end="url(#gar)"')+'><title>'+esc(e.a+'.'+e.out+' → '+e.b+'.'+e.in+(e.ids&&e.ids.length?' ('+e.ids.join(', ')+')':'')+(e.soft?' · not confirmed':'')+(e.why?' · '+e.why:''))+'</title></path>')});
  SC.nodes.forEach(n=>{const h=hOf(n),x=n.x,y=n.y,cls='gn t-'+n.type+' st-'+n.state+(n.done?' done':'')+(n.id===S.sel?' sel':'')+(L&&L.all.has(n.id)?' hl':'')+(S.hits.includes(n.id)?' found':'');
    o.push('<g class="'+cls+'" data-id="'+esc(n.id)+'" tabindex="0" role="button" aria-label="'+esc(n.type+' '+n.id+' '+n.title+', '+n.label)+'">');
    o.push('<rect class="box" x="'+x+'" y="'+y+'" width="'+W+'" height="'+h+'" rx="7"/>');
    if(small(n)){o.push('<rect class="hd" x="'+x+'" y="'+y+'" width="5" height="'+h+'" rx="2"/><text class="ft" style="font-weight:600;fill:var(--ink)" x="'+(x+12)+'" y="'+(y+16)+'">'+esc(cut(n.title,28))+'</text><circle class="sd" cx="'+(x+15)+'" cy="'+(y+27)+'" r="3.5"/><text class="ft" x="'+(x+23)+'" y="'+(y+30.5)+'">'+esc(cut(n.label,28))+'</text><circle class="pin used" cx="'+x+'" cy="'+(y+h/2)+'" r="3.5"/>'+(P.small[n.type]===2?'<circle class="pin used" cx="'+(x+W)+'" cy="'+(y+h/2)+'" r="3.5"/>':'')+'</g>');return}
    const v=n.verdict,live=n.crew&&n.crew.length;
    o.push('<path class="hd" d="M'+x+','+(y+HEAD)+' v-'+(HEAD-7)+' a7,7 0 0 1 7,-7 h'+(W-14)+' a7,7 0 0 1 7,7 v'+(HEAD-7)+' z"/>');
    if(live)o.push('<circle class="pulse" cx="'+(x+10)+'" cy="'+(y+11)+'" r="3.5"/>');
    o.push('<text class="tt" x="'+(x+(live?19:8))+'" y="'+(y+15)+'">'+esc(cut(n.id+' '+n.title,(live?26:28)-(v?String(v[0]).length+2:0)))+'</text>');
    if(v)o.push('<text class="chip v-'+esc(v[0])+'" x="'+(x+W-7)+'" y="'+(y+15)+'" text-anchor="end">'+esc(v[0])+'</text>');
    PINS[n.type].i.forEach((p,i)=>{const py=y+HEAD+i*ROW+ROW/2+2;o.push('<circle class="pin'+(SC.used.has(n.id+'|i|'+p)?' used':'')+'" cx="'+x+'" cy="'+py+'" r="3.5"/><text class="pl" x="'+(x+8)+'" y="'+(py+3)+'">'+p+'</text>')});
    PINS[n.type].o.forEach((p,i)=>{const py=y+HEAD+i*ROW+ROW/2+2;o.push('<circle class="pin'+(SC.used.has(n.id+'|o|'+p)?' used':'')+'" cx="'+(x+W)+'" cy="'+py+'" r="3.5"/><text class="pl" x="'+(x+W-8)+'" y="'+(py+3)+'" text-anchor="end">'+p+'</text>')});
    const foot=P.foot?P.foot(n):n.label;
    o.push('<circle class="sd" cx="'+(x+11)+'" cy="'+(y+h-13)+'" r="3.5"/><text class="ft" x="'+(x+19)+'" y="'+(y+h-9.5)+'">'+esc(cut(foot,30))+'</text>');
    if(n.p0){const t=Object.values(n.p0).reduce((a,b)=>a+b,0);let acc=0;if(t)[['met','--good'],['Part','--s1'],['Planned','--s1l'],['Open','--open']].forEach(([k,c])=>{const q=n.p0[k]||0;if(q){const w=(W-16)*q/t;o.push('<rect x="'+(x+8+acc).toFixed(1)+'" y="'+(y+h-5)+'" width="'+Math.max(w-1,1).toFixed(1)+'" height="3" rx="1.5" style="fill:var('+c+')"/>');acc+=w}})}
    o.push('</g>')});
  o.push('</g></svg>');host.innerHTML=o.join('');place();bar();side();
}
function place(){const g=document.getElementById('gvp');if(g)g.setAttribute('transform','translate('+S.x.toFixed(1)+','+S.y.toFixed(1)+') scale('+S.k.toFixed(3)+')')}
function box(ids){let a=1e9,b=1e9,c=-1e9,d=-1e9;SC.nodes.forEach(n=>{if(ids&&!ids.has(n.id))return;a=Math.min(a,n.x);b=Math.min(b,n.y);c=Math.max(c,n.x+W);d=Math.max(d,n.y+hOf(n))});return a>c?null:[a,b,c,d]}
function fit(ids,maxk){const r=host.getBoundingClientRect(),bb=box(ids);if(!bb||!r.width)return;const pad=28,k=Math.min(maxk||1,(r.width-pad*2)/(bb[2]-bb[0]),(r.height-pad*2)/(bb[3]-bb[1]));
  S.k=Math.max(.08,k);S.x=(r.width-(bb[0]+bb[2])*S.k)/2;S.y=(r.height-(bb[1]+bb[3])*S.k)/2;place()}
function zoom(f,cx,cy){const r=host.getBoundingClientRect();cx=cx==null?r.width/2:cx;cy=cy==null?r.height/2:cy;const k=Math.min(2.5,Math.max(.08,S.k*f));S.x=cx-(cx-S.x)*k/S.k;S.y=cy-(cy-S.y)*k/S.k;S.k=k;place()}
function centre(id){const n=SC.nodes.get(id);if(!n)return;const r=host.getBoundingClientRect();S.x=r.width/2-(n.x+W/2)*S.k;S.y=r.height/2-(n.y+hOf(n)/2)*S.k;place()}

function go(id){ // select a node wherever it lives, changing the view if this one does not show it
  if(!SC.nodes.has(id)){const n=N.get(id);if(!n)return;P.reveal(n);
    document.getElementById('gdone').checked=S.done;S.sel=id;draw();fit();if(SC.nodes.has(id)&&S.k<.55){S.k=.8;centre(id)}return}
  S.sel=id;draw()}
function open(id){if(P.keepFrom&&S.view!=='sub')S.from=S.view;S.view='sub';S.sub=id;S.sel=id;draw();fit()}

function bar(){document.querySelectorAll('[data-view]').forEach(b=>b.classList.toggle('on',b.dataset.view===S.view));
  document.getElementById('gcrumb').innerHTML=P.crumb();document.getElementById('gstatus').innerHTML=P.status()}

function row(k,v){return v?'<p><b>'+esc(k)+':</b> '+esc(v)+'</p>':''}
function side(){
  const n=S.sel&&(SC.nodes.get(S.sel)||N.get(S.sel));
  if(!n){panel.innerHTML=P.intro();return}
  const o=['<h3>'+esc(n.id)+' '+esc(n.title)+'</h3><p><span class="tag t-'+n.type+'">'+n.type+'</span>'+esc(n.label)+(n.verdict?' · '+esc(n.verdict[0])+(n.verdict[2]!=null?' n='+esc(n.verdict[2]):''):'')+'</p>'];
  if(SC.nodes.has(n.id)&&!n.syn)o.push('<div class="row3"><div class="seg" role="group" aria-label="Trace">'+[['both','Before and after'],['up','Before'],['down','After']].map(t=>'<button type="button" data-trace="'+t[0]+'"'+(S.trace===t[0]?' class="on"':'')+'>'+t[1]+'</button>').join('')+'</div></div>');
  o.push(P.detail(n));
  if(!n.syn){[['Comes in',D.edges.filter(e=>e.b===n.id),'a'],['Goes out',D.edges.filter(e=>e.a===n.id),'b']].forEach(([name,es,end])=>{if(!es.length)return;o.push('<h4>'+name+' ('+es.length+')</h4>');
      es.forEach(e=>{const x=N.get(e[end]);o.push('<button type="button" class="lk" data-go="'+esc(e[end])+'"><b>'+esc(e[end])+'</b> '+esc(cut(x?x.title:'',30))+'<small>'+esc(e.a+'.'+e.out+' → '+e.b+'.'+e.in)+P.linkNote(e)+(e.why?' · '+esc(e.why):'')+'</small></button>')})});
    o.push(P.cli(n))}
  panel.innerHTML=o.join('');panel.scrollTop=0}

// pan, zoom, select
let drag=null;
host.addEventListener('pointerdown',e=>{if(e.button!==0)return;drag={x:e.clientX,y:e.clientY,sx:S.x,sy:S.y,moved:false,id:(e.target.closest('.gn')||{dataset:{}}).dataset.id||null};host.setPointerCapture(e.pointerId)});
host.addEventListener('pointermove',e=>{if(!drag)return;const dx=e.clientX-drag.x,dy=e.clientY-drag.y;if(!drag.moved&&Math.hypot(dx,dy)<4)return;drag.moved=true;host.classList.add('drag');S.x=drag.sx+dx;S.y=drag.sy+dy;place()});
let lastUp={t:0,id:null};
host.addEventListener('pointerup',e=>{const d=drag;drag=null;host.classList.remove('drag');if(!d||d.moved)return;
  if(d.id){const now=Date.now(),dbl=lastUp.id===d.id&&now-lastUp.t<420;lastUp={t:now,id:d.id};const n=N.get(d.id);if(dbl&&n&&P.opens(n)){open(d.id);return}S.sel=S.sel===d.id&&!dbl?null:d.id;draw()}
  else if(S.sel){S.sel=null;draw()}});
host.addEventListener('pointercancel',()=>{drag=null;host.classList.remove('drag')});
host.addEventListener('wheel',e=>{if(!(e.ctrlKey||e.metaKey))return;e.preventDefault();const r=host.getBoundingClientRect();zoom(e.deltaY<0?1.15:1/1.15,e.clientX-r.left,e.clientY-r.top)},{passive:false});
host.addEventListener('keydown',e=>{const g=e.target.closest&&e.target.closest('.gn');
  if(e.key==='Enter'&&g){e.preventDefault();const id=g.dataset.id;if(S.sel===id&&N.get(id)&&P.opens(N.get(id)))open(id);else{S.sel=id;draw();const f=host.querySelector('.gn[data-id="'+CSS.escape(id)+'"]');if(f)f.focus()}}
  else if(e.key==='Escape'){if(S.sel){S.sel=null;draw()}else if(S.view==='sub'){S.view=S.from||P.home;S.sub=null;draw();fit()}}
  else if(e.key==='+'||e.key==='=')zoom(1.2);else if(e.key==='-')zoom(1/1.2);else if(e.key==='0')fit();
  else if(e.key.indexOf('Arrow')===0&&!g){e.preventDefault();const s=40;S.x+=e.key==='ArrowLeft'?s:e.key==='ArrowRight'?-s:0;S.y+=e.key==='ArrowUp'?s:e.key==='ArrowDown'?-s:0;place()}});
document.addEventListener('click',e=>{const t=e.target.closest('[data-view],[data-zoom],[data-back],[data-go],[data-open],[data-trace]');if(!t)return;
  if(t.dataset.view){S.view=t.dataset.view;S.sub=null;S.sel=null;draw();fit()}
  else if(t.dataset.zoom!=null){const z=+t.dataset.zoom;if(z)zoom(z>0?1.25:.8);else fit()}
  else if(t.dataset.back){S.view=S.from||P.home;S.sub=null;draw();fit()}
  else if(t.dataset.go)go(t.dataset.go);else if(t.dataset.open)open(t.dataset.open);else if(t.dataset.trace){S.trace=t.dataset.trace;draw()}});
document.getElementById('gdone').addEventListener('change',e=>{S.done=e.target.checked;draw();fit()});
const sb=document.getElementById('gsearch');
function find(){const q=sb.value.trim().toLowerCase();S.q=q;S.hit=0;S.hits=q?D.nodes.filter(n=>n.id.toLowerCase()===q).concat(D.nodes.filter(n=>n.id.toLowerCase()!==q&&(n.id+' '+n.title).toLowerCase().indexOf(q)>=0)).map(n=>n.id):[];draw()}
sb.addEventListener('input',find);
sb.addEventListener('keydown',e=>{if(e.key!=='Enter'||!S.hits.length)return;e.preventDefault();const id=S.hits[S.hit%S.hits.length];S.hit++;go(id);if(SC.nodes.has(id)){if(S.k<.6)S.k=.85;centre(id)}});
window.addEventListener('resize',()=>place());
draw();fit();
window.__flowGraph={S,D,go,open,fit,scene:()=>SC};
})();
"""


def js(profile):
    """The page script for one graph: the shared canvas around a profile (PINS and P)."""
    return JS_A + profile + JS_B


JS = js(ROAD_JS)
