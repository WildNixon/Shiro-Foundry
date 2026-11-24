"""PreToolUse hook: the road graph is manager driven; the crew reads it and never edits it. The hook refuses a
tool call that writes a protected file directly, in any checkout or worktree. The protected files are the
profile's hooks.protect (default: docs/flow/road.graph.json and docs/flow/road.edits.jsonl). Their only writer is
`flow.py graph ...`, which takes the manager's badge and logs the edit.

It refuses everyone, the manager too, so it needs no idea of who is asking: the manager's way in is the script.
Reading (Read, Grep, cat, git show, git log, git diff) and committing (git add, git commit) pass.

Edit, Write and NotebookEdit are refused by path. A shell command is refused when it names a protected file (by
its file name) together with a form that writes: a redirect onto it, tee, sed -i, rm/mv/del/truncate, cp onto it,
the PowerShell content and item cmdlets, git checkout/restore/rm/mv/apply/stash of it. That is best effort: a
script that opens the file itself is not seen here, and is caught by `flow.py graph verify` (the signed log) and
at hand-in. Because a shell command is matched by file name alone, protect files whose names are their own.

The profile: the hook looks for foundry_profile.py in $CLAUDE_PROJECT_DIR/scripts/foundry (the default
paths.tools) and in ../tools beside itself. A hook must never crash the session, so when the module or the
profile cannot be read, the defaults above stand.

Reads the hook's JSON on stdin; exit 2 with a reason on stderr blocks the call; exit 0 lets it run.
Selftest: <python> graph_readonly.py selftest
"""
import io
import json
import os
import re
import sys
from pathlib import Path

DEFAULT_PROTECT = ["docs/flow/road.graph.json", "docs/flow/road.edits.jsonl"]
DEFAULT_PREFIX = "FB1"
TOKEN = r"[^\s\"'|;&<>()]*"  # the rest of one shell word
# a quoted string that is a path: no space before its first slash (D:/..., /c/..., $DIR/..., ./...)
PATHLIKE = re.compile(r"[^\s\\/]*[\\/]")
WRITERS = re.compile(
    r"(?:^|[\s;&|(`/\\])(?:tee|rm|mv|del|erase|ren|rename|move|truncate|shred|unlink|dd|install|patch|touch"
    r"|sed\s+(?:-[a-z]*\s+)*-[a-z]*i|perl\s+(?:-[a-z]*\s+)*-[a-z]*i"
    r"|set-content|add-content|clear-content|out-file|remove-item|move-item|rename-item|new-item|ri|sc|ac|mi|rni|ni"
    r"|git\s+(?:-C\s+\S+\s+)?(?:checkout|restore|rm|mv|apply|stash|reset|clean))(?=\s|$|\.exe)", re.I)
COPY = re.compile(r"(?:^|[\s;&|(`/\\])(?:cp|copy|copy-item|cpi|xcopy|robocopy)(?:\.exe)?\s", re.I)
# out-file and tee after a pipe write whatever the pipe carries

# set by configure(): the protected files as regexes, and the refusal text
PROTECT = []
PATH = None      # a whole path that is a protected file (or its .tmp)
NAMED = None     # a protected file's name anywhere in a text
REDIRECT = None  # a redirect whose target is a protected file
REASON = ""


def configure(protect=None, prefix=None, reason=None, flow_tool="flow.py"):
    """Build the regexes and the refusal text for a list of protected repo paths. An empty list protects nothing."""
    global PROTECT, PATH, NAMED, REDIRECT, REASON
    protect = DEFAULT_PROTECT if protect is None else protect
    clean = []
    for p in protect:
        parts = [seg for seg in re.split(r"[\\/]+", str(p).strip()) if seg and seg != "."]
        if parts and "/".join(parts) not in clean:
            clean.append("/".join(parts))
    PROTECT = clean
    if not clean:
        PATH = NAMED = REDIRECT = None
        REASON = ""
        return
    names = []
    for p in clean:
        n = re.escape(p.split("/")[-1])
        if n not in names:
            names.append(n)
    file = "(?:" + "|".join(names) + ")"
    whole = "|".join(r"[\\/]+".join(re.escape(seg) for seg in p.split("/")) for p in clean)
    PATH = re.compile(r"(?:^|[\\/])(?:" + whole + r")(?:\.tmp)?$", re.I)
    NAMED = re.compile(file, re.I)
    # a redirect whose target is the file: > f, >> f, 2> f, >| f, > "f", > "D:/a spaced dir/docs/flow/f";
    # the quoted form is bounded so a long line cannot make it slow
    REDIRECT = re.compile(r">[>|]?[ \t]*(?:\"[^\"\n]{0,4096}?|'[^'\n]{0,4096}?|" + TOKEN + ")" + file, re.I)
    listed = " and ".join(clean) if len(clean) < 3 else ", ".join(clean)
    verb = "is" if len(clean) == 1 else "are"
    REASON = reason or (
        f"Blocked: {listed} {verb} written only by `{flow_tool} graph ...` (link, unlink, confirm, node, undo), "
        f"which takes the manager's badge line (--by \"{prefix or DEFAULT_PREFIX} ID:MGR-...\") and logs the edit. "
        "The manager uses that; anyone else may read the graph (flow.py graph show, graph trace, the built page) "
        "and asks the manager for a change.")


def load_profile():
    """Configure from the project's profile; on any trouble the defaults stand. Never raises."""
    try:
        here = Path(__file__).resolve().parent
        project = os.environ.get("CLAUDE_PROJECT_DIR")
        places = ([Path(project) / "scripts" / "foundry"] if project else []) + [here.parent / "tools"]
        place = next((d for d in places if (d / "foundry_profile.py").is_file()), None)
        if place is None:
            return configure()
        sys.path.insert(0, str(place))
        try:
            import foundry_profile as fp
        finally:
            sys.path.pop(0)
        start = project or str(here)
        # the hook runs before every tool call: name the main checkout so the profile does not ask git for it
        had = os.environ.get("FOUNDRY_MAIN")
        if had is None:
            os.environ["FOUNDRY_MAIN"] = str(fp.checkout(start))
        try:
            prof = fp.load(start)
        finally:
            if had is None:
                os.environ.pop("FOUNDRY_MAIN", None)
        protect = prof.get("hooks.protect", DEFAULT_PROTECT)
        if not isinstance(protect, list) or not all(isinstance(x, str) for x in protect):
            protect = DEFAULT_PROTECT
        reason = prof.get("hooks.protect_reason") or None
        tool = (str(prof.get("paths.tools") or "").replace("\\", "/").rstrip("/") + "/flow.py").lstrip("/")
        configure(protect, prof.badge_prefix, reason if isinstance(reason, str) else None, tool)
    except BaseException:  # a broken profile module may raise anything, SystemExit included
        configure()


def is_guarded_path(text: str) -> bool:
    """A quoted string that is a protected file's path, spaces and all ("D:/my project/docs/flow/...")."""
    t = text.strip()
    return bool(PATH.search(t) and PATHLIKE.match(t))


def strip_messages(cmd: str) -> str:
    """Drop quoted text that holds a space (a commit message, a note): prose that names the file writes nothing.
    A quoted single word stays: it is a path. A quoted path with spaces into a protected file stays too.

    One pass: a quote closes at the next same quote on its line; one left open is kept as a character.
    The next quote and newline positions are cached, so each is searched for once: linear in the command."""
    out, i, n = [], 0, len(cmd)
    nxt = {'"': -2, "'": -2, "\n": -2}  # cached next position at or after i (-2: not searched yet)

    def find(ch: str, start: int) -> int:
        p = nxt[ch]
        if p == -1 or (p >= start):
            return p
        p = cmd.find(ch, start)
        nxt[ch] = p
        return p

    while i < n:
        c = cmd[i]
        if c not in "\"'":
            j = min((p for p in (find('"', i), find("'", i)) if p != -1), default=n)
            out.append(cmd[i:j])
            i = j
            continue
        close, nl = find(c, i + 1), find("\n", i + 1)
        if close == -1 or (nl != -1 and nl < close):
            out.append(c)  # unclosed on its line: keep the quote, go on after it
            i += 1
            continue
        body = cmd[i + 1:close]
        if any(ch.isspace() for ch in body) and not is_guarded_path(body):
            out.append('""')
        else:
            out.append(cmd[i:close + 1])
        i = close + 1
    return "".join(out)


def strip_heredocs(cmd: str) -> str:
    """Heredoc data is not a command (the no_python_stdin hook's reader, when it is beside this file)."""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from no_python_stdin import strip_heredoc_bodies
        return strip_heredoc_bodies(cmd)
    except Exception:
        return cmd
    finally:
        sys.path.pop(0)


def shell_writes(cmd: str) -> bool:
    if NAMED is None or not NAMED.search(cmd or ""):  # the cheap check first; most commands stop here
        return False
    cmd = strip_messages(strip_heredocs(cmd or ""))
    if not NAMED.search(cmd):
        return False
    if REDIRECT.search(cmd):
        return True
    for seg in re.split(r"[;\n]|&&|\|\|", cmd):
        if not NAMED.search(seg):
            continue
        if WRITERS.search(seg):
            return True
        if COPY.search(seg):  # copying it away is a read; copying onto it is a write
            words = [w.strip("\"'") for w in seg.split()]
            if words and NAMED.search(words[-1]):
                return True
    return False


def blocked(data: dict) -> bool:
    if PATH is None:
        return False
    tool = data.get("tool_name") or ""
    inp = data.get("tool_input") or {}
    if tool in ("Bash", "PowerShell"):
        return shell_writes(inp.get("command", ""))
    if tool not in ("Edit", "Write", "NotebookEdit", "MultiEdit"):
        return False  # Read, Grep and the rest only read
    path = inp.get("file_path") or inp.get("notebook_path") or ""
    return bool(PATH.search(str(path).strip()))


def selftest() -> int:
    """On the default protected files, whatever the project's profile says; then on a list of its own."""
    configure(DEFAULT_PROTECT, DEFAULT_PREFIX)
    g, l = "docs/flow/road.graph.json", "docs/flow/road.edits.jsonl"
    bad_paths = [g, l, "D:\\my project\\docs\\flow\\road.graph.json",
                 "D:/x/.claude/worktrees/w/docs/flow/road.edits.jsonl", "/repo/docs/flow/ROAD.GRAPH.JSON", g + ".tmp"]
    good_paths = ["docs/flow/readme.md", "docs/flow/road.graph.json.md", "tools/flow_graph.py", "out/flow/graph.json",
                  "notes/road.graph.json", "docs/flow2/road.graph.json", ""]
    bad_cmds = [f"echo x > {g}", f"echo x >> \"{l}\"", f"jq . a.json >{g}", f"cat a | tee {g}", f"sed -i 's/a/b/' {g}",
                f"rm {g}", f"rm -f {g} {l}", f"mv {g} /tmp/x", f"cp /tmp/x {g}", f"git checkout -- {g}",
                f"git restore {l}", f"git -C . checkout main -- {g}", f"Set-Content -Path {g} -Value x",
                f"'x' | Out-File {g}", f"Add-Content {l} 'x'", f"Remove-Item {g}", f"Copy-Item x.json {g}",
                f"cd docs/flow && rm road.graph.json", f"truncate -s 0 {l}", f"ls; echo x 2> {g}",
                f"git stash push {g}", f"perl -pi -e 's/a/b/' {g}", f"cat <<EOF > {g}\n{{}}\nEOF"]
    good_cmds = [f"cat {g}", f"git show main:{g}", f"git log -- {g} {l}", f"git diff {g}", f"git add {g} {l}",
                 f"git commit -m \"Map: graph edit 12 (M2 after M1)\" {g} {l}", f"grep -n M2 {g}", f"cp {g} /tmp/copy.json",
                 f"python tools/flow.py graph link M1 M2 --by \"{DEFAULT_PREFIX} ID:MGR-1 SIG:X\"",
                 "python tools/flow.py graph verify",
                 f"git commit -m \"do not rm {g} by hand\"", f"wc -l {l}", f"Get-Content {g}", f"head -3 {l} | cut -c1-80",
                 "rm out/flow/graph.json", "echo x > out/flow/brief.json", f"sha256sum {g} > /tmp/sum.txt",
                 f"cat > notes.md <<'EOF'\nnever rm {g}\nEOF", f"Copy-Item {g} C:/tmp/copy.json"]
    # a quoted path with spaces, each writer, bash and PowerShell forms
    mg, ml = "D:/my project/" + g, "D:\\my project\\docs\\flow\\road.edits.jsonl"
    for p in (mg, ml, "/d/my project/" + g):
        for q in ('"', "'"):
            s = q + p + q
            bad_cmds += [f"rm {s}", f"rm -f {s}", f"echo x > {s}", f"echo x >> {s}", f"cp x.json {s}", f"mv x.json {s}",
                         f"sed -i 's/a/b/' {s}", f"cat a | tee {s}", f"git checkout main -- {s}", f"truncate -s 0 {s}",
                         f"Set-Content -Path {s} -Value x", f"Set-Content {s} 'x'", f"Add-Content {s} 'x'",
                         f"'x' | Out-File {s}", f"'x' | Out-File -FilePath {s}", f"Remove-Item {s}",
                         f"Remove-Item -LiteralPath {s} -Force", f"Copy-Item x.json {s}", f"Move-Item x.json {s}",
                         f"Clear-Content {s}", f"New-Item -Force {s}", f"del {s}"]
        good_cmds += [f"cat \"{p}\"", f"Get-Content \"{p}\"", f"cp \"{p}\" /tmp/copy.json",
                      f"Copy-Item \"{p}\" C:/tmp/copy.json", f"git log -- \"{p}\""]
    good_cmds += [f"git commit -m \"never rm {g} by hand\"", f"echo \"don't rm {g}\" > notes.md"]
    fails = [("path", p) for p in bad_paths if not blocked({"tool_name": "Edit", "tool_input": {"file_path": p}})]
    fails += [("path", p) for p in good_paths if blocked({"tool_name": "Write", "tool_input": {"file_path": p}})]
    fails += [("cmd", c) for c in bad_cmds if not blocked({"tool_name": "Bash", "tool_input": {"command": c}})]
    fails += [("cmd", c) for c in good_cmds if blocked({"tool_name": "PowerShell", "tool_input": {"command": c}})]
    if not blocked({"tool_name": "NotebookEdit", "tool_input": {"notebook_path": g}}):
        fails.append(("path", "NotebookEdit"))
    # what the hook cannot read is refused only when it names a guarded file
    raws = [("{not json " + g, 2), ("{not json", 0), ("", 0),
            (json.dumps({"tool_name": "Bash", "tool_input": f"rm {g}"}), 2),  # tool_input a string
            (json.dumps({"tool_name": "Bash", "tool_input": {"command": 7}, "x": g}), 2),  # command a number
            (json.dumps({"tool_name": "Bash", "tool_input": "ls"}), 0),
            (json.dumps({"tool_name": "Edit", "tool_input": {"file_path": g}}).replace("road", "\\u0072oad"), 2),
            (json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls x"}}), 0)]
    fails += [("raw", r) for r, want in raws if decide(r, io.StringIO()) != want]
    n = len(bad_paths) + len(good_paths) + len(bad_cmds) + len(good_cmds) + 1 + len(raws)

    # a profile's own list: another file is protected, the road graph is not; an empty list protects nothing
    def edit(p):
        return blocked({"tool_name": "Edit", "tool_input": {"file_path": p}})

    def bash(c):
        return blocked({"tool_name": "Bash", "tool_input": {"command": c}})
    configure(["data\\ledger.v1.json", "./LOCKFILE"], "XB2")
    own = [("own list: Edit of the listed file is blocked", edit("C:/repo/data/ledger.v1.json")),
           ("own list: a file at the top of the repo is blocked", edit("LOCKFILE") and edit("/repo/LOCKFILE")),
           ("own list: the road graph is no longer protected", not edit(g) and not bash(f"rm {g}")),
           ("own list: a dot in the name is not a wildcard", not edit("data/ledgerXv1.json")),
           ("own list: a shell write of the listed file is blocked", bash("rm data/ledger.v1.json") and bash("echo x > LOCKFILE")),
           ("own list: a shell read of it runs", not bash("cat data/ledger.v1.json")),
           ("own list: the reason names the files and the profile's badge prefix",
            "data/ledger.v1.json and LOCKFILE are written only" in REASON and "XB2 ID:MGR-" in REASON),
           ("own list: unreadable input naming the file is refused", decide("{not json LOCKFILE", io.StringIO()) == 2)]
    configure([], "XB2")
    own += [("an empty list protects nothing", not edit(g) and not bash(f"rm {g}") and decide("{not json " + g, io.StringIO()) == 0)]
    configure(["docs/flow/road.graph.json"], None, "Ask the manager.")
    own += [("hooks.protect_reason replaces the refusal text", REASON == "Ask the manager." and edit(g) and not edit(l))]
    configure(DEFAULT_PROTECT, DEFAULT_PREFIX)
    own += [("the default reason names both files and the default prefix",
             f"{g} and {l} are written only" in REASON and f"{DEFAULT_PREFIX} ID:MGR-" in REASON)]
    fails += [("profile", name) for name, cond in own if not cond]
    n += len(own)
    for kind, c in fails:
        print("FAIL", kind, repr(c))
    print(f"graph_readonly selftest: {n - len(fails)} ok, {len(fails)} failed")
    return 1 if fails else 0


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        return selftest()
    raw = sys.stdin.buffer.read().decode("utf-8", "replace")
    load_profile()
    return decide(raw)


def decide(raw: str, err=None) -> int:
    """A call that names no protected file runs at once. One that does is decided, and if the hook cannot read it
    (bad JSON, an odd shape) it fails closed: exit 2. A JSON \\u escape could spell the name, so that input is parsed."""
    if NAMED is None:
        return 0
    if not NAMED.search(raw) and "\\u" not in raw.lower():
        return 0
    err, data = err or sys.stderr, None
    try:
        data = json.loads(raw)
        stop = isinstance(data, dict) and blocked(data)
    except Exception as e:
        decoded = "" if data is None else json.dumps(data, ensure_ascii=False, default=str)
        if not (NAMED.search(raw) or NAMED.search(decoded)):
            return 0
        print(f"graph_readonly could not read this call ({type(e).__name__}) and it names a protected file, so it is "
              "refused. " + REASON, file=err)
        return 2
    if stop:
        print(REASON, file=err)
        return 2
    return 0


configure()

if __name__ == "__main__":
    sys.exit(main())
