#!/usr/bin/env python3
"""Tests for tools/plan_flow.py: `python tests/test_plan_flow.py`. A plan started by `new` must hold no problem
and build a page; every plan in the tree must hold no problem; a plan with a mistake must be told so; and the
commands must refuse what they cannot do. Everything is written under a scratch folder, never the tree.

The last section checks the built pages themselves, a plan chart and a workflow page (flow.py build on the example
roadmap), without running them: the embedded data parses and holds every node the page script looks up, every
element the script asks the page for is in the page, the script's brackets close, every name it uses is declared,
and no name of the project these tools came from is left. That is a check of structure, not an execution. To run
the pages for real as well, name a Chrome or Edge in FOUNDRY_TEST_BROWSER: the test then loads each page headless,
from its file, with a probe that walks every view, node, sub-view, trace and search, and fails on any script error.

The tools are loaded for a scratch project: FOUNDRY_ROOT and FOUNDRY_MAIN name an empty temp folder, and
GIT_CEILING_DIRECTORIES stops git at the temp folder, so nothing here walks up into a repository the temp folder
may lie in (the Foundry's own checkout included). The git identity comes from the environment.
"""
import atexit
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BROWSER = os.environ.get("FOUNDRY_TEST_BROWSER", "")  # optional: a Chrome or Edge to run the built pages in, headless
for _k in [k for k in os.environ if k.startswith("FOUNDRY_")]:
    os.environ.pop(_k)
_SCRATCH = Path(tempfile.mkdtemp(prefix="planflow-main-")).resolve()  # the project the tools are loaded for: empty
atexit.register(shutil.rmtree, _SCRATCH, ignore_errors=True)
os.environ["FOUNDRY_ROOT"] = os.environ["FOUNDRY_MAIN"] = str(_SCRATCH / "main")
(_SCRATCH / "main").mkdir()
os.environ["FOUNDRY_PATHS_OFFICE"] = str(_SCRATCH / "office" / "none")  # no badge here: the real office is never asked
# git looks no higher than the temp folder, under either of its names (as given, and resolved)
_TEMP = Path(tempfile.gettempdir())
os.environ["GIT_CEILING_DIRECTORIES"] = os.pathsep.join(dict.fromkeys([_TEMP.as_posix(), _TEMP.resolve().as_posix()]))
sys.path.insert(0, str(REPO / "tools"))
import plan_flow  # noqa: E402

FAILS = []
PLAN = '''[meta]
title = "Scratch"
buys = ["one gain"]
[[section]]
title = "More"
text = "a paragraph"
[[stage]]
id = "S1"
title = "one"
[[stage]]
id = "S2"
title = "two"
[[step]]
id = "A1"
stage = "S1"
title = "first"
state = "new"
effort = "S"
confidence = "estimate"
[[step]]
id = "A2"
stage = "S2"
title = "second"
state = "have"
effort = "M"
confidence = "read"
needs = ["A1"]
[[decision]]
id = "Q1"
title = "q"
gates = ["S2"]
[[lane]]
id = "L1"
of = "S2"
title = "lane"
checks = ["a control"]
'''


def check(name, cond, got=None):
    if not cond:
        FAILS.append(name)
        print(f"FAIL {name}" + (f": {got!r}" if got is not None else ""))


def call(root, *argv):
    """(exit code, stdout, stderr) of one plan_flow command on a scratch root."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = plan_flow.main(list(argv), root)
    return code, out.getvalue(), err.getvalue()


def top_names(js):
    """The names a script declares at the start of a line: const/let/var declarators and functions. The page script
    is one closure of three pieces, so a name two pieces declare stops the whole page (no node on this host to ask)."""
    names = []
    for line in js.splitlines():
        m = re.match(r"(?:const|let|var)\s+(.*)", line)
        if m:
            depth, quote, part, parts = 0, "", "", []
            for ch in m[1]:
                if quote:
                    quote = "" if ch == quote else quote
                elif ch in "'\"`":
                    quote = ch
                elif ch in "([{":
                    depth += 1
                elif ch in ")]}":
                    depth -= 1
                elif ch == "," and depth == 0:
                    parts.append(part)
                    part = ""
                    continue
                elif ch == ";" and depth == 0:
                    break
                part += ch
            names += [n[1] for n in (re.match(r"\s*([A-Za-z_$][\w$]*)\s*(?:=|$)", p) for p in parts + [part]) if n]
        m = re.match(r"function\s+([A-Za-z_$][\w$]*)", line)
        if m:
            names.append(m[1])
    return names


def has(bad, word):
    return any(word in line for line in bad)


# ------------------------------------------------------------------ the built pages, checked without a browser

JS_KEYWORDS = set("const let var function return if else for while do break continue new typeof instanceof in of null true "
                  "false this void delete switch case default try catch finally throw class extends super yield async await".split())
JS_GLOBALS = set("document window Math String Object JSON Array Set Map Date Number Boolean CSS Event KeyboardEvent undefined NaN "
                 "Infinity console parseInt parseFloat isNaN isFinite Symbol Promise Error RegExp innerWidth innerHeight "
                 "setTimeout clearTimeout requestAnimationFrame getComputedStyle location navigator".split())
NAME_RE = r"[A-Za-z_$][\w$]*"
# names of the project these tools were made in: none may reach a page
OLD_NAMES = re.compile(r"(?i:glasswing|chrysalis)|\bgw\b|\bGW_|\bGB1\b|\bpm\.py\b|\bvmq\b|--vmdir|--all-lanes|"
                       r"\bvm\.(?:queue|lock|last|lanes|released|requeue)\b|\bout/pm\b|progress\.py|os_flow|kernel_flow|\b(?:dev|the) VM\b")


def js_strip(js):
    """(the script with every string, template, regex literal and comment blanked out, problems). The length and
    the line breaks stay, so a position in the result is a position in the script."""
    out, bad, i, n, prev, word = [], [], 0, len(js), "", ""
    while i < n:
        ch = js[i]
        nxt = js[i + 1] if i + 1 < n else ""
        if ch == "/" and nxt == "/":
            j = js.find("\n", i)
            j = n if j < 0 else j
            out.append(" " * (j - i))
            i = j
            continue
        if ch == "/" and nxt == "*":
            j = js.find("*/", i + 2)
            if j < 0:
                bad.append(f"a /* comment opened at {i} never closes")
                j = n - 2
            out.append(re.sub(r"[^\n]", " ", js[i:j + 2]))
            i = j + 2
            continue
        if ch in "'\"`":
            j = i + 1
            while j < n and js[j] != ch:
                if js[j] == "\\":
                    j += 1
                elif js[j] == "\n" and ch != "`":
                    break
                j += 1
            if j >= n or js[j] != ch:
                bad.append(f"a string opened at {i} never closes: {js[i:i + 40]!r}")
                j = min(j, n - 1)
            out.append(ch + re.sub(r"[^\n]", " ", js[i + 1:j]) + ch)
            i = j + 1
            prev, word = ch, ""
            continue
        if ch == "/" and (prev == "" or prev in "(,=:[!&|?{};+-*%<>~^" or word in ("return", "typeof", "case", "in", "of", "void")):
            j, cls = i + 1, False
            while j < n and (js[j] != "/" or cls) and js[j] != "\n":
                if js[j] == "\\":
                    j += 1
                elif js[j] == "[":
                    cls = True
                elif js[j] == "]":
                    cls = False
                j += 1
            if j >= n or js[j] != "/":
                bad.append(f"a regex opened at {i} never closes: {js[i:i + 40]!r}")
            j += 1
            while j < n and js[j].isalpha():
                j += 1
            out.append("/" + " " * (j - i - 2) + "/")
            i = j
            prev, word = "/", ""
            continue
        out.append(ch)
        if not ch.isspace():
            word = (word + ch) if (ch.isalnum() or ch in "_$") and (prev.isalnum() or prev in "_$") else (ch if ch.isalnum() or ch in "_$" else "")
            prev = ch
        i += 1
    return "".join(out), bad


def js_balance(code):
    """Problems with the brackets of a stripped script: one that closes nothing, or is left open."""
    pairs, stack, bad = {")": "(", "]": "[", "}": "{"}, [], []
    for i, ch in enumerate(code):
        if ch in "([{":
            stack.append((ch, i))
        elif ch in pairs:
            if not stack or stack[-1][0] != pairs[ch]:
                bad.append(f"'{ch}' at {i} closes nothing: …{code[max(0, i - 30):i + 10].strip()}…")
                return bad
            stack.pop()
    if stack:
        ch, i = stack[-1]
        bad.append(f"'{ch}' at {i} is never closed: {code[i:i + 40].strip()}…")
    return bad


def js_declared(code):
    """Every name a stripped script declares anywhere: functions and their parameters, object methods, arrow
    parameters, catch names, and const/let/var names (a destructuring pattern's names too)."""
    names = set()
    ids = lambda text: set(re.findall(r"(?<![\w$.])" + NAME_RE, text))  # noqa: E731

    def matching_open(close):
        depth = 0
        for j in range(close, -1, -1):
            if code[j] in ")]}":
                depth += 1
            elif code[j] in "([{":
                depth -= 1
                if depth == 0:
                    return j
        return -1

    for m in re.finditer(r"\bfunction\s*(" + NAME_RE + r")?\s*\(([^()]*)\)", code):
        names |= ({m[1]} if m[1] else set()) | ids(m[2])
    for m in re.finditer(r"(" + NAME_RE + r")\s*\(([^()]*)\)\s*\{", code):  # a method of an object literal
        if m[1] not in JS_KEYWORDS:
            names |= {m[1]} | ids(m[2])
    for m in re.finditer(r"\bcatch\s*\(\s*(" + NAME_RE + r")", code):
        names.add(m[1])
    for m in re.finditer(r"=>", code):
        head = code[:m.start()].rstrip()
        if head.endswith(")"):
            j = matching_open(len(head) - 1)
            names |= ids(re.sub(r"=[^,\]})]*", "", head[j + 1:-1])) if j >= 0 else set()
        else:
            w = re.search(NAME_RE + r"$", head)
            names |= {w[0]} if w else set()
    for m in re.finditer(r"\b(?:const|let|var)\b", code):
        i, depth, want = m.end(), 0, True  # want: the next thing at depth 0 is a declarator's name or pattern
        while i < len(code):
            ch = code[i]
            if want and not ch.isspace():
                if ch in "[{":
                    j, d = i, 0
                    while j < len(code):
                        d += code[j] in "[{"
                        d -= code[j] in "]}"
                        if d == 0:
                            break
                        j += 1
                    names |= ids(re.sub(r":\s*", " ", code[i:j + 1]))
                    i = j + 1
                else:
                    w = re.match(NAME_RE, code[i:])
                    if not w:
                        break
                    names.add(w[0])
                    i += len(w[0])
                want = False
                continue
            if ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth -= 1
                if depth < 0:
                    break
            elif depth == 0 and ch == ";":
                break
            elif depth == 0 and ch == ",":
                want = True
            elif depth == 0 and re.match(r"\b(?:of|in)\b", code[i:]) and code[i - 1].isspace():
                break
            i += 1
    return names


def js_unknown(code):
    """The names a stripped script uses and nothing declares, in the order met. A name after a dot is a property;
    a name before a colon, right after `{` or `,`, is an object's key."""
    known = js_declared(code) | JS_KEYWORDS | JS_GLOBALS
    out = []
    for m in re.finditer(r"(?<![\w$])" + NAME_RE, code):
        name, before, after = m[0], code[:m.start()].rstrip(), code[m.end():].lstrip()
        if name in known or name in out or name[0].isdigit():
            continue
        if before.endswith(".") and not before.endswith("..."):
            continue
        if after.startswith(":") and before[-1:] in ("{", ","):
            continue
        out.append(name)
    return out


def page_parts(html):
    """(the page without its scripts, the data script's text or None, the other scripts' texts)."""
    data, scripts = None, []
    for m in re.finditer(r"<script([^>]*)>(.*?)</script>", html, re.S):
        if "application/json" in m[1]:
            data = m[2]
        else:
            scripts.append(m[2])
    return re.sub(r"(<script[^>]*>).*?</script>", lambda m: m[1] if "application/json" in m[1] else "", html, flags=re.S), data, scripts


def page_problems(html):
    """What is wrong with a built chart page, found without running it."""
    bad = []
    static, blob, scripts = page_parts(html)
    if blob is None:
        return ["the page holds no chart data (script#gdata)"]
    try:
        D = json.loads(blob.replace("<\\/", "</"))
    except ValueError as e:
        return [f"the chart data is not JSON ({e})"]
    if not scripts:
        bad.append("the page holds no script")
    every = "\n".join(scripts)

    # the data: every node the script looks up is there
    nodes = {}
    for n in D.get("nodes", []):
        if n.get("id") in nodes:
            bad.append(f"two nodes are named {n.get('id')}")
        nodes[n.get("id")] = n
    pins = D.get("pins")
    if pins is None:  # the road graph's pin table is in its script
        m = re.search(r"const PINS=\{(.*?)\};", every, re.S)
        pins = {t: {"i": re.findall(r"'([^']*)'", i), "o": re.findall(r"'([^']*)'", o)}
                for t, i, o in re.findall(r"(\w+):\{i:\[([^\]]*)\],o:\[([^\]]*)\]\}", m[1] if m else "")}
    if not pins:
        bad.append("the page has no pin table")
    for n in nodes.values():
        if n.get("type") not in pins:
            bad.append(f"node {n.get('id')} has the type {n.get('type')}, which has no pins")
        for key in ("title", "label", "state"):
            if not isinstance(n.get(key), str):
                bad.append(f"node {n.get('id')} has no {key}")
    for e in D.get("edges", []):
        for end, side, pin in ((e.get("a"), "o", e.get("out")), (e.get("b"), "i", e.get("in"))):
            if end not in nodes:
                bad.append(f"a link names {end}, which is not a node")
            elif pin not in (pins.get(nodes[end].get("type")) or {}).get(side, []):
                bad.append(f"a link lands on {end}.{pin}, a pin its type ({nodes[end].get('type')}) does not have")
    stages = D.get("stages", []) + (D.get("meta", {}).get("stages") or [])
    for s in stages:
        if s not in nodes:
            bad.append(f"the stage list names {s}, which is not a node")
    for n in nodes.values():
        for sid in n.get("steps", []) if D.get("pins") else []:  # a plan stage's steps are nodes (the road's are labels)
            if sid not in nodes:
                bad.append(f"{n['id']} lists the step {sid}, which is not a node")
        if D.get("pins") and n.get("type") == "step" and n.get("stage") not in nodes:
            bad.append(f"step {n['id']} names the stage {n.get('stage')}, which is not a node")

    # the script against the page
    views = set(re.findall(r'data-view="([^"]+)"', static))
    for v in re.findall(r"home:'([^']+)'", every) + re.findall(r"S\.view=(?:==)?'([^']+)'", every):
        if v not in views and v != "sub":
            bad.append(f"the script names the view '{v}', and the page has no button for it")
    asked = set(re.findall(r"getElementById\('([^']+)'\)", every))
    for sel in re.findall(r"querySelector(?:All)?\('([^']*)'\)", every) + re.findall(r"closest\('([^']*)'\)", every):
        asked |= set(re.findall(r"#([\w-]+)", sel))
        for attr in re.findall(r"\[(data-[\w-]+)", sel):
            if attr + "=" not in static and attr + "=" not in every:
                bad.append(f"the script selects [{attr}], and neither the page nor the script writes that attribute")
    for i in sorted(asked):
        if f'id="{i}"' not in static and f'id="{i}"' not in every:
            bad.append(f"the script asks for the element #{i}, and neither the page nor the script makes it")
    for name in sorted(set(re.findall(r"\.dataset\.(\w+)", every))):
        attr = "data-" + re.sub(r"[A-Z]", lambda m: "-" + m[0].lower(), name)
        if attr + "=" not in static and attr + "=" not in every:
            bad.append(f"the script reads dataset.{name}, and nothing writes {attr}")

    # each script on its own: strings and brackets close, every name is declared
    for k, js in enumerate(scripts):
        code, probs = js_strip(js)
        probs += js_balance(code)
        if not probs:
            probs += [f"it uses the name {x}, which nothing declares" for x in js_unknown(code)]
        bad += [f"script {k + 1}: {p}" for p in probs]

    for m in OLD_NAMES.finditer(html):
        bad.append(f"the page still holds an old name: …{html[max(0, m.start() - 30):m.end() + 20]}…")
        break
    return bad


# What the probe does in a real browser: every view, every node's panel and trace buttons, every node that opens
# (through the page's own button) with each node of its sub-view, the search box, the keys and the zoom buttons.
PROBE_HEAD = "<script>window.__errs=[];window.addEventListener('error',function(e){window.__errs.push(String(e.message))});</script>"
PROBE = r"""(function(){
var out={errors:[],views:{},went:0,opened:0,traced:0,drawn:0};
function note(what,e){out.errors.push(what+': '+(e&&e.message?e.message:e))}
try{var G=window.__flowGraph;
if(!G)out.errors.push('no window.__flowGraph: the page script did not run to its end');
else{var canvas=document.getElementById('canvas'),panel=document.getElementById('gpanel');
out.drawn=canvas.querySelectorAll('svg #gvp .gn').length;
Array.prototype.forEach.call(document.querySelectorAll('[data-view]'),function(b){try{b.click();out.views[b.dataset.view]=canvas.querySelectorAll('.gn').length}catch(e){note('view '+b.dataset.view,e)}});
try{document.getElementById('gdone').click()}catch(e){note('toggle',e)}
G.D.nodes.forEach(function(n){try{G.go(n.id);if(panel.innerHTML.indexOf('<h3>')<0)out.errors.push('no panel for '+n.id);else out.went++;
Array.prototype.forEach.call(panel.querySelectorAll('[data-trace]'),function(b){b.click();out.traced++})}catch(e){note('go '+n.id,e)}});
G.D.nodes.forEach(function(n){try{G.go(n.id);var btn=panel.querySelector('[data-open]');if(!btn)return;btn.click();out.opened++;
Array.from(G.scene().nodes.keys()).forEach(function(id){G.go(id)});
var back=document.querySelector('[data-back]');if(back)back.click();else out.errors.push('no way back from '+n.id)}catch(e){note('open '+n.id,e)}});
try{var sb=document.getElementById('gsearch');sb.value=G.D.nodes[0].id.toLowerCase();sb.dispatchEvent(new Event('input'));sb.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter'}))}catch(e){note('search',e)}
try{['+','-','0','ArrowLeft','Escape','Escape'].forEach(function(k){canvas.dispatchEvent(new KeyboardEvent('keydown',{key:k,bubbles:true}))});
Array.prototype.forEach.call(document.querySelectorAll('[data-zoom]'),function(b){b.click()})}catch(e){note('keys',e)}
try{var lk=panel.querySelector('[data-go]');if(lk)lk.click()}catch(e){note('panel link',e)}}
}catch(e){note('probe',e)}
out.errors=out.errors.concat(window.__errs||[]);
document.getElementById('probe').textContent='PROBE'+JSON.stringify(out)+'ENDPROBE';})();"""


def browser_run(browser, page, scratch):
    """The probe's report on one built page, run headless from its file; {"errors": [...]} when it could not run."""
    html = page.read_text(encoding="utf-8")
    probe = page.with_name("probe-" + page.name)
    probe.write_text(html.replace("<body>", "<body>" + PROBE_HEAD, 1).replace("</body>", '<pre id="probe"></pre><script>' + PROBE + "</script></body>", 1),
                     encoding="utf-8", newline="\n")
    try:
        r = subprocess.run([browser, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check", "--disable-extensions",
                            f"--user-data-dir={scratch / 'browser-profile'}", "--virtual-time-budget=4000", "--dump-dom", probe.as_uri()],
                           capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    except (OSError, subprocess.SubprocessError) as e:
        return {"errors": [f"the browser could not be run ({type(e).__name__}: {e})"]}
    m = re.search(r"PROBE(\{.*?\})ENDPROBE", r.stdout, re.S)
    return json.loads(m[1]) if m else {"errors": [f"the page gave no probe report (exit {r.returncode})"]}


def build_pages(root, out):
    """A plan chart and a workflow page for a scratch project made from the example roadmap, with a push of two
    blocks, an open finding and two lanes' counted runs, so every kind of node is on the page. Returns their paths."""
    repo = Path(__file__).resolve().parent.parent
    (root / "docs" / "flow").mkdir(parents=True)
    (root / "docs" / "flow" / "demo.plan.toml").write_text(PLAN, encoding="utf-8", newline="\n")
    (root / "docs" / "ROADMAP.md").write_text((repo / "profile" / "ROADMAP.example.md").read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    (root / "docs" / "progress").mkdir()
    (root / "docs" / "progress" / "state.json").write_text(json.dumps({
        "shift": {"blocks": [{"title": "Q1: M2 the store", "status": "partial", "time": "day", "done_when": "G2 says PASS", "checkpoint": "G2"},
                             {"title": "Q2: M3 the release", "status": "pending"}]},
        "failures": [{"id": "F001", "status": "open", "lane": "G2", "what": "undo loses the last edit"}]}), encoding="utf-8")
    (root / "gym" / "series").mkdir(parents=True)
    for lane, run, word, ts in (("G1", "20300110-113607-0a1f", "PASS", 1894300567.0), ("G2", "20300111-113607-0a2f", "FAIL", 1894386967.0)):
        (root / "gym" / "series" / f"{lane}.json").write_text(json.dumps({"meta": {"lane": lane}, "points": [
            {"run_id": run, "verdict": word, "n": 40, "ts": ts}]}), encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if not k.startswith("FOUNDRY_")}
    env.update(FOUNDRY_ROOT=str(root), FOUNDRY_MAIN=str(root), FOUNDRY_PATHS_OFFICE=str(root / "office"), PYTHONDONTWRITEBYTECODE="1")
    tools = repo / "tools"
    logs = []
    for args in (["plan_flow.py", "build", "demo", "--out", str(out)], ["flow.py", "build", f"--root={root}", f"--out={out}"]):
        r = subprocess.run([sys.executable, str(tools / args[0]), *args[1:]], env=env, cwd=str(root), capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        logs.append(f"{args[0]} exit {r.returncode}: {(r.stdout + r.stderr).strip()[-300:]}")
    return out / "demo.html", out / "workflow.html", logs


def page_checks():
    # the checker's own parts, on small scripts
    code, probs = js_strip("a='}';b=\"]\";c=s.replace(/[&<>\"]/g,x=>x)/2; // )\n/* { */d=`(`")
    check("strings, a regex, comments and a template are blanked out", not probs and not js_balance(code) and "&" not in code and code.count("/") == 3, (code, probs))
    check("a division is not read as a regex", js_strip("x=a/2;y=(b)/c;z=1")[0] == "x=a/2;y=(b)/c;z=1")
    check("an open string is reported", js_strip("a='x\nb=1")[1])
    check("a bracket left open is reported", js_balance(js_strip("f(function(){a=[1,2}")[0]))
    check("a bracket that closes nothing is reported", js_balance(js_strip("a=1)}")[0]))
    decl = js_declared(js_strip("const a=1,[b,c]=x,{d,e:f}=y;let g;function h(i,j){}const P={k(l){},m:n=>n,o:(p,[q,r])=>p};try{}catch(s){}for(const t of u){}")[0])
    check("declared names are found: functions, parameters, methods, arrows, patterns, catch",
          set("a b c d f g h i j k l n p q r s t P".split()) <= decl and "u" not in decl and "m" not in decl, sorted(decl))
    check("a name nothing declares is reported, and a property or a key is not",
          js_unknown(js_strip("const a={key:1,other:b};a.prop=c?d:a;[...a].map(x=>x.y+zz)")[0]) == ["b", "c", "d", "zz"],
          js_unknown(js_strip("const a={key:1,other:b};a.prop=c?d:a;[...a].map(x=>x.y+zz)")[0]))

    scratch = Path(tempfile.mkdtemp(prefix="planflow-pages-")).resolve()
    try:
        plan_page, flow_page, logs = build_pages(scratch / "proj", scratch / "pages")
        check("the plan page and the workflow page were built", plan_page.is_file() and flow_page.is_file(), logs)
        if not (plan_page.is_file() and flow_page.is_file()):
            return
        for name, page in (("plan", plan_page), ("workflow", flow_page)):
            html = page.read_text(encoding="utf-8")
            bad = page_problems(html)
            check(f"the {name} page: its data, its script and its elements agree", not bad, bad[:6])
            _, blob, scripts = page_parts(html)
            D = json.loads(blob.replace("<\\/", "</"))
            check(f"the {name} page draws every kind of node the example gives it",
                  {n["type"] for n in D["nodes"]} == ({"stage", "step", "decision", "lane"} if name == "plan" else {"milestone", "decision", "stage", "block"}),
                  sorted({n["type"] for n in D["nodes"]}))
            canvas = scripts[-1]
            # the same page with one thing broken at a time: the check must see each
            for what, broken, word in (
                    ("data that is not JSON", html.replace(blob, blob[:-1]), "not JSON"),
                    ("a link to a node that is not there", html.replace(blob, json.dumps(dict(D, edges=D["edges"] + [dict(D["edges"][0], b="NOPE")])).replace("</", "<\\/")), "NOPE, which is not a node"),
                    ("a node of a type with no pins", html.replace(blob, json.dumps(dict(D, nodes=D["nodes"] + [dict(D["nodes"][0], id="X9", type="ghost")])).replace("</", "<\\/")), "has no pins"),
                    ("an element the script asks for and the page lacks", html.replace('id="gstatus"', 'id="gstate"'), "#gstatus"),
                    ("a view with no button", html.replace('data-view="%s"' % re.search(r"home:'([^']+)'", canvas)[1], 'data-view="zz"'), "no button for it"),
                    ("a bracket left open", html.replace(canvas, canvas.replace("function place(){", "function place(){{", 1)), "clos"),
                    ("a helper that is called and not declared", html.replace(canvas, canvas.replace("function row(k,v)", "function rowx(k,v)", 1)), "the name row, which nothing declares"),
                    ("a string left open", html.replace(canvas, canvas.replace("const cut=", "const cut0='\nconst cut=", 1)), "never closes"),
                    ("an old name", html.replace("</main>", "<p>scripts/gw gym</p></main>"), "an old name")):
                got = page_problems(broken)
                check(f"the {name} page with {what} is reported", has(got, word), got[:3])
            if BROWSER:
                rep = browser_run(BROWSER, page, scratch)
                check(f"the {name} page runs in the browser with no script error", not rep.get("errors") and rep.get("drawn", 0) > 0
                      and rep.get("went") == len(D["nodes"]) and rep.get("opened", 0) > 0, rep)
                print(f"browser: the {name} page ran: {json.dumps(rep, ensure_ascii=False)}")
        if not BROWSER:
            print("pages: checked by structure only (FOUNDRY_TEST_BROWSER names no browser, so no page script was run)")
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def main():
    for name in plan_flow.plan_names(REPO):  # the Foundry's own plans, read where they lie
        bad = plan_flow.chart(name)["model"](REPO)[2]
        check(f"the tree's plan '{name}' has no problem", not bad, bad)

    with tempfile.TemporaryDirectory() as d:
        root = Path(d).resolve()
        check("list on an empty tree says how to start", "new NAME" in call(root, "list")[1])
        code, out, _ = call(root, "selftest")
        check("selftest with no plan checks the template and passes", code == 0 and "the template" in out and "0 problems" in out, out)
        check("build with no plan fails", call(root, "build", f"--out={root / 'page'}")[0] == 1)
        check("new needs a title", call(root, "new", "demo")[0] == 2)
        check("new refuses a taken name", call(root, "new", "os", "--title=x")[0] == 2)
        check("new refuses a name that is not a slug", call(root, "new", "../x", "--title=x")[0] == 2)
        code, out, _ = call(root, "new", "demo", '--title=A "quoted" plan', "--question=Why?")
        path = root / "docs" / "flow" / "demo.plan.toml"
        check("new writes the plan", code == 0 and path.is_file(), out)
        check("new never overwrites", call(root, "new", "demo", "--title=other")[0] == 1 and 'A \\"quoted\\" plan' in path.read_text(encoding="utf-8"))
        code, out, _ = call(root, "selftest", "demo")
        check("a new plan passes its selftest", code == 0 and "0 problems" in out, out)
        code, out, _ = call(root, "list")
        check("list names the plan and its title", code == 0 and 'demo' in out and 'A "quoted" plan' in out, out)
        code, out, _ = call(root, "build", "demo", f"--out={root / 'page'}")
        page = root / "page" / "demo.html"
        check("build writes the page and the graph", code == 0 and page.is_file() and (root / "page" / "demo.graph.json").is_file(), out)
        check("the page names its plan file and its command", "docs/flow/demo.plan.toml" in page.read_text(encoding="utf-8") and "plan_flow.py show demo" in page.read_text(encoding="utf-8"))
        check("build writes nothing beside --out", not (root / "out").exists())

        # an option's value may follow it as the next argument
        check("parse: joined and spaced values, switches, a valued option with nothing after it",
              plan_flow.parse(["new", "x", "--title", "a b", "--question=why", "--by", "L 1", "--up", "--out"])
              == (["new", "x"], {"--title": "a b", "--question": "why", "--by": "L 1", "--up": True, "--out": True}),
              plan_flow.parse(["new", "x", "--title", "a b", "--question=why", "--by", "L 1", "--up", "--out"]))
        check("parse: a spaced value is not read as an argument", plan_flow.parse(["build", "--out", "page", "demo"]) == (["build", "demo"], {"--out": "page"}))
        code, out, _ = call(root, "new", "spaced", "--title", "A spaced title", "--question", "Why so?")
        spaced = root / "docs" / "flow" / "spaced.plan.toml"
        check("new takes --title and --question in the spaced form", code == 0 and 'title = "A spaced title"' in spaced.read_text(encoding="utf-8")
              and 'question = "Why so?"' in spaced.read_text(encoding="utf-8"), out)
        code, out, _ = call(root, "build", "spaced", "--out", str(root / "page2"))
        check("build takes --out in the spaced form, and writes nowhere else", code == 0 and (root / "page2" / "spaced.html").is_file()
              and not (root / "out").exists() and not (root / "--out").exists(), out)
        check("new with a bare --title is refused", call(root, "new", "bare", "--title")[0] == 2 and not (root / "docs" / "flow" / "bare.plan.toml").exists())
        code, out, _ = call(root, "trace", "spaced", "A1", "--down")
        check("a switch still reads as a switch", code == 0 and out.startswith("after A1"), out)
        spaced.unlink()

        path.write_text(PLAN, encoding="utf-8", newline="\n")
        nodes, edges, bad, meta = plan_flow.chart("demo")["model"](root)
        check("a full plan has no problem", not bad, bad)
        check("the stages are chained", any(e["a"] == "S1" and e["b"] == "S2" and e["kind"] == "then" for e in edges))
        check("a decision gates its stage", any(e["a"] == "Q1" and e["b"] == "S2" and e["kind"] == "gate" for e in edges))
        check("a lane closes its stage", any(e["a"] == "S2" and e["b"] == "L1" and e["kind"] == "sub" for e in edges))
        check("the first panel's sections are read", [s["title"] for s in meta["sections"]] == ["What it buys", "More"], meta["sections"])
        check("trace up finds what comes first", plan_flow.traced(edges, "A2", True) == ["A1"], plan_flow.traced(edges, "A2", True))
        check("trace down finds what follows", plan_flow.traced(edges, "S1", False) == ["S2", "L1"], plan_flow.traced(edges, "S1", False))
        code, out, _ = call(root, "trace", "demo", "A2", "--up")
        check("trace prints one line a way", code == 0 and out.strip() == "before A2 (1): A1", out)
        code, out, _ = call(root, "show", "demo", "Q1")
        check("show prints a node with its links", code == 0 and "decision Q1" in out and "goes out: S2" in out, out)
        check("show of an unknown id fails", call(root, "show", "demo", "ZZ")[0] == 2)
        check("an unknown plan fails", call(root, "show", "nope", "A1")[0] == 2)
        check("an unknown command fails", call(root, "paint", "demo")[0] == 2)
        check("edges prints every link", call(root, "edges", "demo")[1].count("->") == len(edges))

        for name, text, word in (
                ("a table with no id", PLAN + '[[step]]\nstage = "S1"\n', "has no id"),
                ("needs that is not a list", PLAN.replace('needs = ["A1"]', 'needs = "A1"'), "must be a list"),
                ("an unknown need", PLAN.replace('needs = ["A1"]', 'needs = ["ZZ"]'), "not a step"),
                ("a gate on no stage", PLAN.replace('gates = ["S2"]', 'gates = ["S9"]'), "not a stage"),
                ("a lane of no stage", PLAN.replace('of = "S2"', 'of = "S9"'), "is not a stage"),
                ("a roadmap row that is not there", PLAN.replace('gates = ["S2"]', 'gates = ["S2"]\nroadmap = "D99"'), "no D99 row"),
                ("an anchor whose file is gone", PLAN.replace('needs = ["A1"]', 'needs = ["A1"]\nanchor = ["no/such/file", "x"]'), "is gone"),
                ("a plan with no stage", '[meta]\ntitle = "t"\n', "no stage"),
                ("a plan that is not TOML", "[[stage", "not TOML")):
            path.write_text(text, encoding="utf-8", newline="\n")
            bad = plan_flow.chart("demo")["model"](root)[2]
            check(f"{name} is reported", has(bad, word), bad)
        check("a selftest with a problem exits 1", call(root, "selftest", "demo")[0] == 1)
        check("a selftest of every plan exits 1 when one fails", call(root, "selftest")[0] == 1)

        # the main checkout takes a new plan or a page from the manager's badge only
        real = plan_flow.flow.main_root
        plan_flow.flow.main_root = lambda: root
        try:
            path.unlink()
            code, _, err = call(root, "new", "demo", "--title=x")
            check("new in the main checkout needs the manager's badge", code == 2 and "--by" in err and not path.exists(), err)
            code, _, err = call(root, "new", "demo", "--title=x", "--by=not a badge line")
            check("new in the main checkout refuses a line that is no badge", code == 2 and not path.exists(), err)
            code, _, err = call(root, "new", "demo", "--title", "x", "--by", "not a badge line")
            check("the spaced --by is read as the badge line, and refused when it is none", code == 2 and "--by" in err and not path.exists(), err)
            path.write_text(PLAN, encoding="utf-8", newline="\n")
            code, _, err = call(root, "build", "demo")
            check("build into the main checkout's out/ needs the badge", code == 2 and "--out" in err and not (root / "out").exists(), err)
            code, _, err = call(root, "build", "demo", f"--out={root / 'out' / 'flow'}")
            check("an --out that points into the main checkout needs the badge too", code == 2 and not (root / "out").exists(), err)
            code, _, err = call(root, "build", "demo", f"--out={root / 'docs' / 'pages'}")
            check("an --out anywhere in the main checkout needs the badge", code == 2 and not (root / "docs" / "pages").exists(), err)
            with tempfile.TemporaryDirectory() as other:
                check("build with an --out outside the main checkout is anyone's", call(root, "build", "demo", f"--out={Path(other) / 'page'}")[0] == 0)
            check("reading in the main checkout is anyone's", call(root, "show", "demo", "A1")[0] == 0 and call(root, "selftest", "demo")[0] == 0)
            check("in_main: the checkout, a file in it, a folder not made yet", all(plan_flow.in_main(p) for p in (root, path, root / "a" / "b")))
            check("in_main: a folder beside it is not", not plan_flow.in_main(root.parent / "elsewhere"))

            # the manager's badge passes the first gate; the freeze is the second
            real_manager, real_frozen = plan_flow.flow_graph.manager, plan_flow.frozen
            plan_flow.flow_graph.manager = lambda by, office_dir=None: None
            try:
                path.unlink()
                office = root / "office"  # a scratch crew office: the real reader on real files, no stub
                real_frozen_fn = plan_flow.frozen
                plan_flow.frozen = lambda: real_frozen_fn(office)
                now = time.time()
                office.mkdir()
                (office / "rq.queue.json").write_text(json.dumps([{"id": "MGR-1-sweep", "job": "the sweep", "prio": 0, "at": now, "beat": now}]), encoding="utf-8")
                check("a project with no shared resource has no freeze from a queue", plan_flow.frozen() == ([], []), plan_flow.frozen())
                (office / "freeze.json").write_text(json.dumps({"by": "MGR-1", "why": "counted G1", "lane": "G1", "at": now, "max_s": 3600}), encoding="utf-8")
                runs, maybe = plan_flow.frozen()
                check("the manager's freeze holds a project with no shared resource", len(runs) == 1 and "MGR-1" in runs[0] and "counted G1" in runs[0] and not maybe, runs)
                code, _, err = call(root, "new", "demo", "--title=x")
                check("new is refused during the manager's freeze: exit 3, as flow.py graph and gym_init.py give it",
                      code == 3 and "freeze" in err and "MGR-1" in err and not path.exists(), (code, err))
                code, _, err = call(root, "new", "demo")
                check("a usage error during the freeze is still exit 2", code == 2 and "--title" in err, (code, err))
                (office / "freeze.json").write_text(json.dumps({"by": "MGR-1", "why": "counted G1", "at": now - 7200, "max_s": 60}), encoding="utf-8")
                check("a freeze past its limit still holds until it is lifted", len(plan_flow.frozen()[0]) == 1, plan_flow.frozen())
                (office / "freeze.json").write_text("{not json", encoding="utf-8")
                code, _, err = call(root, "new", "demo", "--title=x")
                check("a freeze file that cannot be read is a freeze", code == 3 and "freeze" in err and not path.exists(), (code, err))
                (office / "freeze.json").write_text(json.dumps({"by": "MGR-2", "why": "by file", "lane": "G2", "at": now}), encoding="utf-8")
                d, off = plan_flow.flow_graph.office()

                class NoFacts:  # an office.py from before freeze_facts: the file is read with the same meaning
                    now_ts = staticmethod(off.now_ts)
                check("without office.freeze_facts the file is read with the same meaning",
                      "MGR-2" in plan_flow.freeze_marker(NoFacts, office) and "lane G2" in plan_flow.freeze_marker(NoFacts, office)
                      and "by file" in plan_flow.freeze_marker(NoFacts, office), plan_flow.freeze_marker(NoFacts, office))
                (office / "freeze.json").write_text("[1]", encoding="utf-8")
                check("and a file it cannot read is a freeze there too", "cannot be read" in plan_flow.freeze_marker(NoFacts, office))
                (office / "freeze.json").unlink()
                check("no freeze file: no freeze, by either reader", plan_flow.freeze_marker(NoFacts, office) == "" and plan_flow.freeze_marker(off, office) == "")
                (office / "rq.queue.json").unlink()
                office.rmdir()
                os.environ["FOUNDRY_RESOURCE_NAME"] = "the test rig"  # from here on the project has a queue to freeze on

                def queue(*entries):
                    (office / "rq.queue.json").write_text(json.dumps([dict(e, at=now, beat=now) for e in entries]), encoding="utf-8")

                def new_refused(word):
                    code, _, err = call(root, "new", "demo", "--title=x")
                    return code == 3 and word in err and not path.exists(), (code, err)

                check("no crew office folder: new is refused", *new_refused("could not be read"))
                office.mkdir()
                check("an office with no queue file is a clear queue", plan_flow.frozen() == ([], []), plan_flow.frozen())
                (office / "rq.queue.json").write_text("{not json", encoding="utf-8")
                check("a mangled queue file: new is refused", *new_refused("could not be read"))
                (office / "rq.queue.json").write_text('{"a": 1}', encoding="utf-8")
                check("a queue file that is not a list: new is refused", *new_refused("could not be read"))
                (office / "rq.lock").mkdir()
                queue()
                check("a held seat whose lock names nobody: new is refused", *new_refused("could not be read"))
                (office / "rq.lock").rmdir()
                queue({"id": "MGR-1-counted-G1", "job": "counted G1", "prio": 0, "all": True})
                check("a counted run in the queue: new is refused, badge or not", *new_refused("MGR-1-counted-G1"))
                code, _, err = call(root, "build", "no-such-plan", f"--out={root / 'docs' / 'pages'}")
                check("a build into the main checkout's tracked folders is refused during a freeze (exit 3)", code == 3 and "freeze" in err, (code, err))
                queue({"id": "EMP-9", "job": "a run", "prio": 0})
                check("prio 0 alone is no freeze: the office and the board go by the id, and so does this tool",
                      plan_flow.frozen() == ([], ["EMP-9"]), plan_flow.frozen())
                code, _, err = call(root, "new", "demo", "--title=x")
                check("a prio-0 job under a plain id gets a note, and the write goes on", code == 0 and "EMP-9" in err and "COUNTED?" in err and path.is_file(), err)
                path.unlink()
                queue({"id": "EMP-4", "job": "unit tests", "prio": 5})
                (office / "freeze.json").write_text(json.dumps({"by": "MGR-1", "why": "counted G1 on the bench", "at": now}), encoding="utf-8")
                check("the manager's freeze holds with a clear queue", *new_refused("counted G1 on the bench"))
                queue({"id": "MGR-1-counted-G1", "job": "counted G1", "prio": 0, "all": True})
                runs, _ = plan_flow.frozen()
                check("a counted run in the queue and the manager's freeze are both named", len(runs) == 2 and "MGR-1-counted-G1" in runs[0] and "freeze" in runs[1], runs)
                (office / "freeze.json").unlink()
                queue({"id": "MGR-1-sweep", "job": "the sweep", "prio": 1})
                path.write_text(PLAN, encoding="utf-8", newline="\n")
                code, out, err = call(root, "build", "demo")
                check("the manager's build into out/ goes on during a freeze", code == 0 and (root / "out" / "flow" / "demo.html").is_file(), err)
                path.unlink()
                queue({"id": "MGR-1-ci", "job": "ci on main", "prio": 1, "all": True})
                code, _, err = call(root, "new", "demo", "--title=x")
                check("a whole-resource job under a plain id gets a note, and the write goes on", code == 0 and "MGR-1-ci" in err and "COUNTED?" in err and path.is_file(), err)
                path.unlink()
                queue({"id": "EMP-3", "job": "dev run 4", "prio": 5, "all": True}, {"id": "EMP-4", "job": "unit tests", "prio": 5})
                code, _, err = call(root, "new", "demo", "--title=x")
                check("a dev run and a one-seat job are no freeze and no note", code == 0 and not err and path.is_file(), err)

                # a link left at the page's name is replaced, never written through
                elsewhere = root / "elsewhere.html"
                elsewhere.write_text("not a page", encoding="utf-8")
                page = root / "out" / "flow" / "demo.html"
                page.unlink()
                try:
                    os.link(elsewhere, page)
                except OSError:
                    page = None
                if page:
                    path.write_text(PLAN, encoding="utf-8", newline="\n")
                    code, _, err = call(root, "build", "demo")
                    check("a build replaces a hardlink at the page's name", code == 0 and elsewhere.read_text(encoding="utf-8") == "not a page" and "<script>" in page.read_text(encoding="utf-8"), err)
                check("a build leaves no temp file", not list((root / "out" / "flow").glob("*.tmp")))
            finally:
                plan_flow.flow_graph.manager, plan_flow.frozen = real_manager, real_frozen
                os.environ.pop("FOUNDRY_RESOURCE_NAME", None)

            # a chart with facts of its own (a project's reader) registers in CHARTS and is reached by its name
            path.write_text(PLAN, encoding="utf-8", newline="\n")
            rel = plan_flow.PLANS / "demo.plan.toml"
            plan_flow.CHARTS["demo"] = {"name": "demo", "plan": rel, "render": plan_flow.render,
                                        "model": lambda r: plan_flow.build_model(r, r / rel, "demo", bad=["a fact of its own is off"], then="its own order")}
            try:
                code, out, _ = call(root, "selftest", "demo")
                check("a registered chart's own facts reach the selftest", code == 1 and "PROBLEM a fact of its own is off" in out, out)
                check("a registered chart's own words reach the links", "its own order" in call(root, "edges", "demo")[1])
            finally:
                plan_flow.CHARTS.clear()
            check("without the registered chart the plan is clean again", call(root, "selftest", "demo")[0] == 0)
        finally:
            plan_flow.flow.main_root = real

    # in_main by git's own answer: a worktree under the main checkout's folder is its own checkout
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.invalid", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.invalid",
               GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
    with tempfile.TemporaryDirectory() as d:
        d = str(Path(d).resolve())
        repo = Path(d) / "repo"
        wt = repo / ".claude" / "worktrees" / "w"

        def git(*args):
            return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, env=env).returncode

        repo.mkdir()
        ok = git("init", "-q") == 0 and git("commit", "-q", "--allow-empty", "-m", "one") == 0 and git("worktree", "add", "-q", "-b", "w", str(wt)) == 0
        check("the scratch repository and its worktree were made", ok)
        if ok:
            real = plan_flow.flow.main_root
            plan_flow.flow.main_root = lambda: repo
            try:
                check("git: the main checkout and a folder in it are in main", plan_flow.in_main(repo) and plan_flow.in_main(repo / "out" / "flow"))
                check("git: a worktree under the main checkout's folder is not", not plan_flow.in_main(wt) and not plan_flow.in_main(wt / "out" / "flow"))
                check("git: a folder outside is not", not plan_flow.in_main(Path(d) / "other"))
                unc = "\\\\localhost\\" + str(repo).replace(":", "$", 1)
                if os.name == "nt" and os.path.isdir(unc):
                    check("the main checkout by its UNC name is still the main checkout", plan_flow.in_main(unc + "\\out\\x") and plan_flow.under(unc + "\\out\\x", repo / "out"), unc)
                    check("the worktree by its UNC name is still not", not plan_flow.in_main(unc + "\\.claude\\worktrees\\w\\out"))
            finally:
                plan_flow.flow.main_root = real
            git("worktree", "remove", "--force", str(wt))

    shared, mine = top_names(plan_flow.flow_page.js("")), top_names(plan_flow.P_JS)
    check("the name scan reads the shared script", {"W", "esc", "row", "S"} <= set(shared), shared)
    check("the name scan reads the plan profile", {"PINS", "P", "WORDS", "asks"} <= set(mine), mine)
    check("the plan profile declares no name the shared page script has", not set(shared) & set(mine), sorted(set(shared) & set(mine)))
    check("the scan would catch a clash", "W" in top_names(plan_flow.P_JS.replace("WORDS", "W")))
    check("the profile declares no name twice", len(mine) == len(set(mine)), mine)
    road = top_names(plan_flow.flow_page.ROAD_JS)
    check("the road graph's profile declares no name the shared page script has, and none twice",
          {"PINS", "P"} <= set(road) and not set(shared) & set(road) and len(road) == len(set(road)), road)
    with tempfile.TemporaryDirectory() as d:
        root = Path(d).resolve()
        (root / "docs" / "flow").mkdir(parents=True)
        (root / "docs" / "flow" / "demo.plan.toml").write_text(PLAN.replace('id = "A1"', 'id = "A\\"1"', 1).replace('needs = ["A1"]', 'needs = ["A\\"1"]'), encoding="utf-8", newline="\n")
        code, out, _ = call(root, "build", "demo", f"--out={root / 'page'}")
        html = (root / "page" / "demo.html").read_text(encoding="utf-8") if code == 0 else ""
        check("the page holds one script", html.count("<script>") == 1, html.count("<script>"))
        check("a quote in a step's id stays inside its attribute", 'placeholder="Find a node (A&quot;1,' in html, re.findall(r'placeholder="[^>]*', html))

    page_checks()

    print(f"plan flow tests: {'FAIL ' + str(len(FAILS)) if FAILS else 'ok'}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
