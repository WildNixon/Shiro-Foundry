"""PreToolUse hook: the road graph is manager driven; the crew reads it and never edits it. The hook refuses a
tool call that writes a protected file directly, in any checkout or worktree. The protected files are
hooks.protect when the project's own profile file sets it; otherwise they are road.graph.json and
road.edits.jsonl under the profile's paths.flow (default docs/flow), so a project that moves paths.flow moves the
protection with it. Their only writer is `flow.py graph ...`, which takes the manager's badge and logs the edit.

It refuses everyone, the manager too, so it needs no idea of who is asking: the manager's way in is the script.
Reading (Read, Grep, cat, git show, git log, git diff) and committing (git add, git commit) pass.

Edit, Write and NotebookEdit are refused by path. The path is first read as the file system reads it: `.` and
`..` are resolved in the text (docs/progress/../flow/road.graph.json), and trailing dots and spaces and an NTFS
stream suffix (road.graph.json. and road.graph.json::$DATA) are dropped, without regard to case. A shell command
is refused when it names a protected file together with a form that writes: a redirect onto it, tee, sed -i,
rm/mv/del/truncate, cp onto it, the PowerShell content and item cmdlets, git checkout/restore/rm/mv/apply/stash
of it.

A writer counts only in the stage of a pipe that names the file (cat <file> | tee /tmp/copy runs; cat a | tee <file>
does not), a copy when the file is any plain argument but the first, and git behind any of its own options. The
forms that touch git's index alone run (git reset <file>, git restore --staged, git rm --cached). A quoted text
with a space is prose and is dropped first (a commit message on one line or many), but for a path into a
protected file or folder, and for the command handed to a shell (bash -c "...", powershell -Command "...", cmd /c
"...", eval "..."), which is read as a command line of its own.

A shell command that never names the file can still replace it through its folder, so the folder a protected file
lies in (docs/flow) is a target too, for these forms only: rm, rmdir, mv and the PowerShell item cmdlets with the
folder as an argument (or fed by a pipe from a command that names it); a copy whose destination is the folder;
find on it with -delete or -exec rm; and git checkout, restore, clean, stash, rm and mv with a pathspec that is
the folder or covers it from above (`.`, `docs`, `:/`). A wildcard counts when it can match a protected file or
its folder (docs/flow/*, docs/fl*, and for git '*.json'), and not otherwise ('*.py', docs/*.md). After `cd` into
the folder in the same command, `.` is the folder and a bare wildcard is read there. Reading the folder (ls, git
status, git add, git diff, git log, copying it away) passes.

All of that is best effort, on the command's text alone. What it does not see is listed in the README beside
this file (a script that opens the file itself, a Windows 8.3 short name, a link, a name built from a variable, a
git command with no pathspec). Those are caught by `flow.py graph verify` (the signed log) and at hand-in.

How a shell command names a protected file. A bare name that is distinctive (it has two or more dots, like
road.graph.json, or is 16 characters or longer) is matched wherever it stands, so `cd docs/flow && rm
road.graph.json` is caught. A name that is not (state.json, config.toml) is matched by its path tail, the last two
path parts (progress/state.json), so it does not stop every command that mentions some state.json; the price is
that `cd docs/progress && rm state.json` is not seen. A file at the top of the repository has only its name.

The profile: the hook reads paths.tools out of $CLAUDE_PROJECT_DIR/.foundry/foundry.toml itself (tomllib) and
looks for foundry_profile.py there, then in $CLAUDE_PROJECT_DIR/scripts/foundry (the default paths.tools), then
in ../tools beside itself. With the module, the profile in force is read through it (and the main checkout is
named for it, so it does not ask git). Without it, the hook goes by what the toml file alone says. A hook must
never crash the session, so when neither can be read, the built-in defaults stand.

Reads the hook's JSON on stdin; exit 2 with a reason on stderr blocks the call; exit 0 lets it run.
Selftest: <python> graph_readonly.py selftest
"""
import bisect
import contextlib
import fnmatch
import io
import json
import os
import posixpath
import re
import sys
from pathlib import Path

DEFAULT_FLOW = "docs/flow"
GRAPH_FILES = ("road.graph.json", "road.edits.jsonl")  # under paths.flow
DEFAULT_PROTECT = [f"{DEFAULT_FLOW}/{n}" for n in GRAPH_FILES]
DEFAULT_PREFIX = "FB1"
DEFAULT_TOOLS = "scripts/foundry"
# before a path tail: no name character, so progress/state.json does not match in myprogress/state.json
TAIL_START = r"(?<![A-Za-z0-9_.-])"
TOKEN = r"[^\s\"'|;&<>()]*"  # the rest of one shell word
# a quoted string that is a path: no space before its first slash (D:/..., /c/..., $DIR/..., ./...)
PATHLIKE = re.compile(r"[^\s\\/]*[\\/]")
# a word that writes its argument, anywhere in one stage of a pipe (git, and sed or perl with a suffix after -i, are
# read word by word: git_writes, in_place)
WRITERS = re.compile(
    r"(?:^|[\s;&|(`/\\])(?:tee|rm|mv|del|erase|ren|rename|move|truncate|shred|unlink|dd|install|patch|touch"
    r"|sed\s+(?:-[a-z]*\s+)*-[a-z]*i|perl\s+(?:-[a-z]*\s+)*-[a-z]*i"
    r"|set-content|add-content|clear-content|out-file|remove-item|move-item|rename-item|new-item|ri|sc|ac|mi|rni|ni"
    r")(?=\s|$|\.exe)", re.I)

# --- a protected file's folder as the target of a command (the forms that replace the file without naming it)
# one shell word: quoted parts and bare characters run together; a quote left open is a word of its own
WORD = re.compile(r"(?:\"[^\"\n]*\"|'[^'\n]*'|[^\s\"'])+|[\"']")
OPERATOR = re.compile(r"[0-9&]*>[>|]?|\|")  # a redirect or a pipe: set apart as a word of its own
SUBSHELL = re.compile(r"\$\(|`")  # a command substitution starts a command of its own
REDIR_WORD = re.compile(r"[0-9&]*>[>|]?$")
GLOB = re.compile(r"[*?\[{]")
MAGIC = re.compile(r":(?:\(([^)]*)\)|([!^/]+))?")  # git pathspec magic: :/ :! :^ :(top) :(exclude)
ASSIGN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")  # VAR=value before a command
WRAPPERS = {"sudo", "doas", "env", "command", "builtin", "exec", "time", "nice", "nohup", "xargs", "call", "start",
            "%", "foreach", "foreach-object", "if", "then", "else", "elif", "do", "while", "until", "!"}
CD = {"cd", "chdir", "pushd", "set-location", "sl", "push-location"}
REMOVERS = {"rm", "rmdir", "rd", "del", "erase", "unlink", "shred", "mv", "move", "ren", "rename",
            "remove-item", "ri", "move-item", "mi", "rename-item", "rni"}
COPIERS = {"cp", "copy", "copy-item", "cpi", "xcopy", "robocopy", "rsync", "install"}
DEST_OPT = re.compile(r"-(?:dest\w*|t|-target-directory)$", re.I)  # -Destination (-Dest...), cp -t
FILE_WRITERS = {"tee", "truncate", "dd", "patch", "touch", "set-content", "add-content", "clear-content", "out-file",
                "new-item", "sc", "ac", "ni", "sed", "gsed", "perl"}
KNOWN = REMOVERS | COPIERS | CD | FILE_WRITERS | {"git", "find"}  # what command_of looks for past a wrapper
# git verbs that write the working tree from a pathspec. reset is not one: given a path it only unstages
GIT_PATH_VERBS = {"checkout", "restore", "clean", "stash", "rm", "mv", "apply"}
GIT_OPTS_WITH_VALUE = {"-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"}  # -C is read for its folder
GIT_VALUE_OPTS = {"-m", "--message", "-s", "--source", "-b", "-B", "--orphan", "-e", "--exclude", "--conflict",
                  "--pathspec-from-file", "-U", "--unified", "--inter-hunk-context"}  # the next word is their value
STASH_READS = {"list", "show", "pop", "apply", "drop", "clear", "branch", "create", "store", "save"}  # no pathspec
INPLACE = re.compile(r"-[A-Za-z0-9]*i|--in-place")  # at the start of an argument of sed or perl
STARS = re.compile(r"\*+")
BRACES = re.compile(r"\{[^{}/]*\}")
# the option whose quoted value is a message: -m, -am, --message (only on a line that says git)
MESSAGE_OPT = re.compile(r"(?:^|\s)(?:-[A-Za-z]*m|--message=?)\s*$")
# a quoted text that is a command handed to a shell: bash -c "...", powershell -NoProfile -Command "...", cmd /c "...".
# The option stands right before the quote, and a shell's name anywhere before it in the same command
PAYLOAD_OPT = re.compile(r"(?:^|\s)(?:-c(?:om\w*)?|-[a-z]{1,3}c|-enc\w*|/c|/k)\s*$", re.I)
SHELL_NAME = re.compile(r"(?:^|[\s;&|(`/\\])(?:bash|sh|zsh|dash|ksh|ash|busybox|pwsh|powershell|cmd)(?:\.exe)?(?=\s)", re.I)
EVAL = re.compile(r"(?:^|[\s;&|(`])(?:eval|iex|invoke-expression)\s*$", re.I)  # eval "...", Invoke-Expression "..."
COMMAND_END = re.compile(r"[;\n|&]")

# set by configure(): the protected files as regexes, and the refusal text
PROTECT = []
PATH = None      # a whole path that is a protected file (or its .tmp)
NAMED = None     # a protected file's name anywhere in a text
REDIRECT = None  # a redirect whose target is a protected file
DIRS = []        # the folders the protected files lie in, as lists of lower-case path parts (none for the top)
TARGETS = []     # (lower-case path parts, whether a file) of every protected file and folder, for wildcards
TOP = False      # whether a protected file lies at the top of the repository
DIR = None       # a whole normalised path that is one of those folders
DIRTAIL = None   # one of those folders named anywhere in a text
HINT = None      # the cheap first check: a text that matches none of it cannot touch a protected file
REASON = ""


def distinctive(name: str) -> bool:
    """A bare file name that can stand for its file in a shell command: two or more dots, or 16 characters or more."""
    return name.count(".") >= 2 or len(name) >= 16


def shell_pattern(path: str) -> str:
    """How a shell command names the protected repo path: its bare name when that is distinctive or the file is at
    the top of the repository, else its last two path parts."""
    parts = path.split("/")
    name = re.escape(parts[-1])
    if len(parts) == 1 or distinctive(parts[-1]):
        return name
    return TAIL_START + re.escape(parts[-2]) + r"[\\/]+" + name


def configure(protect=None, prefix=None, reason=None, flow_tool="flow.py"):
    """Build the regexes and the refusal text for a list of protected repo paths. An empty list protects nothing."""
    global PROTECT, PATH, NAMED, REDIRECT, DIRS, TARGETS, TOP, DIR, DIRTAIL, HINT, REASON
    protect = DEFAULT_PROTECT if protect is None else protect
    clean = []
    for p in protect:
        parts = [seg for seg in re.split(r"[\\/]+", str(p).strip()) if seg and seg != "."]
        if parts and "/".join(parts) not in clean:
            clean.append("/".join(parts))
    PROTECT = clean
    if not clean:
        PATH = NAMED = REDIRECT = DIR = DIRTAIL = HINT = None
        DIRS, TARGETS, TOP = [], [], False
        REASON = ""
        return
    names = []
    for p in clean:
        n = shell_pattern(p)
        if n not in names:
            names.append(n)
    file = "(?:" + "|".join(names) + ")"
    whole = "|".join(r"[\\/]+".join(re.escape(seg) for seg in p.split("/")) for p in clean)
    PATH = re.compile(r"(?:^|[\\/])(?:" + whole + r")(?:\.tmp)?$", re.I)
    NAMED = re.compile(file, re.I)
    # a redirect whose target is the file: > f, >> f, 2> f, >| f, > "f", > "D:/a spaced dir/docs/flow/f";
    # the quoted form is bounded so a long line cannot make it slow
    REDIRECT = re.compile(r">[>|]?[ \t]*(?:\"[^\"\n]{0,4096}?|'[^'\n]{0,4096}?|" + TOKEN + ")" + file, re.I)
    DIRS, TOP = [], any("/" not in p for p in clean)
    for p in clean:
        parts = [seg.lower() for seg in p.split("/")[:-1]]
        if parts and parts not in DIRS:
            DIRS.append(parts)
    TARGETS = [([seg.lower() for seg in p.split("/")], True) for p in clean] + [(d, False) for d in DIRS]
    hints = [re.escape(p.split("/")[-1]) for p in clean] + [r"(?<![A-Za-z0-9])git(?![A-Za-z0-9])"]
    if DIRS:
        DIR = re.compile(r"(?:^|/)(?:" + "|".join("/".join(re.escape(x) for x in d) for d in DIRS) + r")$", re.I)
        DIRTAIL = re.compile(TAIL_START + "(?:" + "|".join(r"[\\/]+".join(re.escape(x) for x in d) for d in DIRS)
                             + r")(?![A-Za-z0-9_-])", re.I)
        hints += [re.escape(x) for d in DIRS for x in d]  # each part: a wildcard may stand for the others (docs/fl*)
    else:
        DIR = DIRTAIL = None
    HINT = re.compile("|".join(dict.fromkeys(hints)), re.I)
    listed = " and ".join(clean) if len(clean) < 3 else ", ".join(clean)
    verb = "is" if len(clean) == 1 else "are"
    REASON = reason or (
        f"Blocked: {listed} {verb} written only by `{flow_tool} graph ...` (link, unlink, confirm, node, undo), "
        f"which takes the manager's badge line (--by \"{prefix or DEFAULT_PREFIX} ID:MGR-...\") and logs the edit. "
        "The manager uses that; anyone else may read the graph (flow.py graph show, graph trace, the built page) "
        "and asks the manager for a change.")


def read_toml(path) -> dict:
    """A toml file as a dict; {} when it is missing or cannot be read. Never raises."""
    try:
        import tomllib
        with open(path, "rb") as f:
            d = tomllib.load(f)
        return d if isinstance(d, dict) else {}
    except BaseException:
        return {}


def table(d: dict, name: str) -> dict:
    v = d.get(name)
    return v if isinstance(v, dict) else {}


def str_list(v) -> bool:
    return isinstance(v, list) and all(isinstance(x, str) for x in v)


def protect_of(file: dict, flow=None) -> list:
    """The protected files: hooks.protect when the project's own profile file sets a list of paths, else the road
    graph and its edit log under paths.flow."""
    own = table(file, "hooks").get("protect")
    if str_list(own):
        return own
    flow = str(flow if isinstance(flow, str) and flow.strip() else DEFAULT_FLOW).replace("\\", "/").rstrip("/")
    return [f"{flow}/{n}" for n in GRAPH_FILES]


def tool_of(tools) -> str:
    tools = tools if isinstance(tools, str) and tools.strip() else DEFAULT_TOOLS
    return (tools.replace("\\", "/").rstrip("/") + "/flow.py").lstrip("/")


def load_profile():
    """Configure from the project's profile: through foundry_profile.py when it is found, else from the toml file
    alone, else the built-in defaults. Never raises, and never asks git for anything."""
    raw = {}
    try:
        here = Path(__file__).resolve().parent
        project = os.environ.get("CLAUDE_PROJECT_DIR")
        raw = read_toml(Path(project) / ".foundry" / "foundry.toml") if project else {}
        tools = table(raw, "paths").get("tools")
        places = []
        if project and isinstance(tools, str) and tools.strip():
            places.append(Path(project) / tools)
        if project:
            places.append(Path(project) / DEFAULT_TOOLS)
        places.append(here.parent / "tools")
        place = next((d for d in places if (d / "foundry_profile.py").is_file()), None)
        if place is None:
            return configure_from(raw)
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
            prof = load_quietly(fp, start)
        finally:
            if had is None:
                os.environ.pop("FOUNDRY_MAIN", None)
        if prof is None:  # the profile file is there and cannot be read: go by what the toml reader alone made of it
            return configure_from(raw)
        # the module fills hooks.protect with its default, so whether the project set it is read from its file
        file = read_toml(prof.file) if prof.file else {}
        env = prof.get("hooks.protect") if "FOUNDRY_HOOKS_PROTECT" in os.environ else None
        protect = env if str_list(env) else protect_of(file, prof.get("paths.flow"))
        reason = prof.get("hooks.protect_reason") or None
        configure(protect, prof.badge_prefix, reason if isinstance(reason, str) else None, tool_of(prof.get("paths.tools")))
    except BaseException:  # a broken profile module may raise anything, SystemExit included
        try:
            configure_from(raw)
        except BaseException:
            configure()


def load_quietly(fp, start):
    """The profile through the module, or None. A module whose load() is strict prints the trouble and raises
    SystemExit(2) on a profile file it cannot read; the hook asks for strict=False, falls back to load(start) on a
    module from before that argument, and lets neither form, nor what it prints, reach the tool call."""
    try:
        with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
            try:
                return fp.load(start, strict=False)
            except TypeError:
                return fp.load(start)
    except (SystemExit, Exception):
        return None


def configure_from(file: dict):
    """Configure from the project's toml file alone (no profile module): what it says, defaults for the rest."""
    prefix = file.get("badge_prefix")
    reason = table(file, "hooks").get("protect_reason")
    configure(protect_of(file, table(file, "paths").get("flow")),
              prefix.upper() if isinstance(prefix, str) and prefix.strip() else None,
              reason if isinstance(reason, str) and reason else None, tool_of(table(file, "paths").get("tools")))


def norm_path(path) -> str:
    """A path as the file system would read it, from its text alone: forward slashes, `.` and `..` resolved, and in
    each part the trailing dots and spaces and a `:stream` suffix dropped (Windows opens road.graph.json., and
    road.graph.json::$DATA, as road.graph.json). A drive letter is dropped with its colon. Nothing is asked of the
    disk, so a link or an 8.3 short name stays what it is."""
    parts, first = [], True
    for seg in str(path).strip().replace("\\", "/").split("/"):
        if first and seg not in ("", "?", "."):
            first = False
            if len(seg) >= 2 and seg[1] == ":" and seg[0].isalpha():
                seg = seg[2:]
        cut = seg.find(":")
        if cut != -1:
            seg = seg[:cut]
        if seg not in (".", ".."):
            seg = seg.rstrip(". ")
        parts.append(seg)
    return posixpath.normpath("/".join(parts))


def is_file(path) -> bool:
    """Whether a path, however it is spelled, is a protected file (or its .tmp)."""
    t = str(path).strip()
    return bool(PATH.search(t) or PATH.search(norm_path(t)))


def pathspec(word: str):
    """A shell word as the path it names, normalised: an option's value (--opt=value), and git's pathspec magic
    taken off. None for an empty word and for a pathspec that excludes (:!x, :^x, :(exclude)x)."""
    w = word.strip()
    if w.startswith("--") and "=" in w:
        w = w.split("=", 1)[1]
    if not w:
        return None  # an empty word (a message that was dropped) names nothing
    m = MAGIC.match(w)
    if m:
        if "exclude" in (m.group(1) or "") or any(c in (m.group(2) or "") for c in "!^"):
            return None
        w = w[m.end():] or "."  # :/ alone is the top of the tree
    return norm_path(w)


def glob_hits(n: str, inside: bool, git: bool) -> bool:
    """Whether a normalised path with a wildcard can match a protected file or its folder. Part by part, as a shell
    expands it, against the last parts of each protected path (so any checkout's full path counts); a pattern with
    fewer parts than the path counts only after a `cd` into the folder. For git, whose `*` also crosses `/` and
    whose pathspec takes a folder with all in it, the whole pattern is also tried on the path and each folder
    above it. A wildcard that can match none of the protected names is not a target: `*.py`, `docs/*.md`."""
    if len(n) > 1024:
        return True  # no real pattern is this long: it is not worked out, and counts
    pat = STARS.sub("*", BRACES.sub("*", n.lower()))
    w = [x for x in pat.split("/") if x not in ("", ".")]
    if not w:
        return False
    rel = "/".join(w)
    for parts, is_a_file in TARGETS:
        k = len(parts)
        if len(w) >= k:
            if all(fnmatch.fnmatchcase(parts[i], w[len(w) - k + i]) for i in range(k)):
                return True
        elif inside and is_a_file and all(fnmatch.fnmatchcase(parts[k - len(w) + i], w[i]) for i in range(len(w))):
            return True
        if git and any(fnmatch.fnmatchcase("/".join(parts[:j]), rel) for j in range(1, k + 1)):
            return True
        if git and inside and is_a_file and fnmatch.fnmatchcase(parts[-1], rel):
            return True
    return False


def dir_target(word: str, inside: bool = False, git: bool = False) -> bool:
    """Whether a shell word names a protected file's folder as a whole, however spelled, or is a wildcard that can
    match a protected file or its folder (docs/flow/*, docs/fl*). `inside`: the command has changed into the
    folder, so `.` is it and a bare wildcard is read there. `git`: the word is a git pathspec."""
    n = pathspec(word)
    if n is None:
        return False
    if GLOB.search(n):
        return bool(TARGETS) and glob_hits(n, inside, git)
    return DIR is not None and (bool(DIR.search(n)) or (inside and n == "."))


def names_file(word: str) -> bool:
    """Whether a shell word names a protected file: its path under any spelling, or its name as NAMED reads it."""
    return bool(NAMED.search(word)) or is_file(word)


def covers(word: str) -> bool:
    """Whether a git pathspec without a wildcard takes in a protected file from above: `.`, `:/`, or a folder on
    the way down to it (docs, docs/)."""
    n = pathspec(word)
    if n is None or not (DIRS or TOP) or GLOB.search(n):
        return False
    if n in (".", "/"):
        return True
    parts = n.lower().split("/")
    return any(len(parts) < len(d) and d[:len(parts)] == parts for d in DIRS)


def is_guarded_path(text: str) -> bool:
    """A quoted string that is a protected file's path or its folder's, spaces and all ("D:/my project/docs/flow/...")."""
    t = text.strip()
    return bool(PATHLIKE.match(t) and (is_file(t) or dir_target(t)))


def strip_messages(cmd: str, depth: int = 0) -> str:
    """Drop quoted text that holds a space (a commit message, a note): prose that names the file writes nothing.
    A quoted single word stays: it is a path. A quoted path with spaces into a protected file stays too.

    A quote closes at the next same quote on its line; one left open is kept as a character. Inside double quotes
    `\\"` is a quote character, not the end (when no other end is on the line, or the text up to it is a protected
    path, it is the end after all: a Windows path may close on a backslash); outside quotes it opens nothing. The
    message of git's -m or --message may run over lines and is always dropped. The text handed to a shell (bash
    -c "...", sh -c, powershell -Command, cmd /c, eval, Invoke-Expression) is a command: it is kept, without its
    quotes, as a command of its own, and read the same way.

    One pass: the next quote and newline positions are cached, so each is searched for once: linear in the command."""
    out, i, n = [], 0, len(cmd)
    nxt = {'"': -2, "'": -2, "\n": -2, "u": -2}  # cached next position at or after i (-2: not searched yet)
    shells = [m.end() for m in SHELL_NAME.finditer(cmd)]  # where a shell is named, and where a command ends
    ends = [m.start() for m in COMMAND_END.finditer(cmd)]

    def payload(at: int, before: str) -> bool:
        """Whether the quote at `at` opens a command handed to a shell named earlier in the same command."""
        if EVAL.search(before):
            return True
        if not shells or not PAYLOAD_OPT.search(before):
            return False
        k = bisect.bisect_left(shells, at) - 1  # the last shell name before the quote
        if k < 0:
            return False
        e = bisect.bisect_left(ends, at) - 1  # the last end of a command before the quote
        return e < 0 or ends[e] < shells[k]

    def find(ch: str, start: int) -> int:
        p = nxt[ch]
        if p == -1 or (p >= start):
            return p
        p = cmd.find(ch, start)
        nxt[ch] = p
        return p

    def escaped(p: int) -> bool:
        k = p - 1
        while k >= 0 and cmd[k] == "\\":
            k -= 1
        return (p - 1 - k) % 2 == 1

    def find_plain(start: int) -> int:
        """The next double quote at or after start that no backslash escapes."""
        p = nxt["u"]
        if p == -1 or (p >= start):
            return p
        p = cmd.find('"', start)
        while p != -1 and escaped(p):
            p = cmd.find('"', p + 1)
        nxt["u"] = p
        return p

    while i < n:
        c = cmd[i]
        if c not in "\"'":
            j = min((p for p in (find('"', i), find("'", i)) if p != -1), default=n)
            out.append(cmd[i:j])
            i = j
            continue
        if escaped(i):  # \" or \' outside quotes is the character itself
            out.append(c)
            i += 1
            continue
        before = cmd[max(0, i - 240):i]
        message = bool(MESSAGE_OPT.search(before)) and "git" in before.lower()
        first, nl = find(c, i + 1), find("\n", i + 1)
        close = first
        if c == '"' and first != -1:
            real = find_plain(i + 1)
            if real != -1 and real != first and (message or nl == -1 or real < nl) and not is_guarded_path(cmd[i + 1:first - 1]):
                close = real
        if close == -1 or (not message and nl != -1 and nl < close):
            out.append(c)  # unclosed on its line: keep the quote, go on after it
            i += 1
            continue
        body = cmd[i + 1:close]
        if payload(i, before):
            inner = body.replace('\\"', '"') if c == '"' else body
            out.append(" ; " + (strip_messages(inner, depth + 1) if depth < 3 else "") + " ; ")
        elif is_guarded_path(body):
            out.append(cmd[i:close + 1])
        elif message or any(ch.isspace() for ch in body):
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


def unquote(word: str) -> str:
    """A shell word without its quotes, and without the brackets and separators that stand against it."""
    return word.replace('"', "").replace("'", "").lstrip("({&`$").rstrip(")`;,")


def base_name(word: str) -> str:
    base = re.split(r"[\\/]", word)[-1].lower()
    return base[:-4] if base.endswith(".exe") else base


def command_of(words):
    """(the command's name in lower case without its folder and .exe, its arguments) for one pipeline stage. Past
    VAR=value; and past sudo, env, xargs, `then` and the like, where the command is the first word after them that
    this hook knows (their own options and values are not told apart from it otherwise)."""
    i = 0
    while i < len(words) and ASSIGN.match(words[i]):
        i += 1
    if i >= len(words):
        return "", []
    if base_name(words[i]) not in WRAPPERS:
        return base_name(words[i]), words[i + 1:]
    for j in range(i + 1, len(words)):
        b = base_name(words[j])
        if b in KNOWN:
            return b, words[j + 1:]
    return "", []


def git_writes(args, inside: bool) -> bool:
    """A git command line (after `git`) that rewrites or removes a protected file in the working tree: by its
    name, through its folder, or by a pathspec that takes it in."""
    i = 0
    while i < len(args) and args[i].startswith("-"):  # git's own options, before the subcommand
        if args[i] == "-C" and i + 1 < len(args):
            inside = inside or dir_target(args[i + 1])
            i += 1
        elif args[i] in GIT_OPTS_WITH_VALUE:
            i += 1
        i += 1
    if i >= len(args) or args[i].lower() not in GIT_PATH_VERBS:
        return False
    verb, rest = args[i].lower(), args[i + 1:]
    if verb == "apply":  # a patch names what it changes inside itself; only --include=<the file> and the like show here
        return any(names_file(w) for w in rest)
    if verb == "stash" and rest and rest[0].lower() in STASH_READS:
        return False  # list, show, pop and the like take no pathspec; save takes a message
    if verb == "rm" and "--cached" in rest:
        return False  # the index only
    if verb == "restore" and ("--staged" in rest or "-S" in rest) and "--worktree" not in rest and "-W" not in rest:
        return False  # the index only
    paths, dashed, skip = [], False, False  # (word, whether it stands after `--`)
    for w in rest:
        if skip:
            skip = False
        elif w == "--" and not dashed:
            dashed = True
        elif w.startswith("-") and not dashed:
            skip = w in GIT_VALUE_OPTS  # its value is the next word: a message, a branch, a tree
        else:
            paths.append((w, dashed))
    # `git checkout <one word>` with no `--` may switch to a branch of that name (docs, docs/flow); a path form
    # of it restores from the index only. It is refused only when the word is the protected file itself, `.`, or
    # a wildcard, none of which is a branch
    one_word = verb == "checkout" and not dashed and len(paths) == 1
    for w, after in paths:
        if names_file(w):
            return True
        n = pathspec(w)
        if n is None:
            continue
        if GLOB.search(n):
            if glob_hits(n, inside, True):
                return True
        elif one_word:
            if n == "." and (DIRS or TOP):
                return True
        elif dir_target(w, inside, True) or (covers(w) and (verb != "checkout" or after or n == ".")):
            return True
    return False


def in_place(words) -> bool:
    """sed or perl editing in place: -i, -i.bak, -pi, -pi.bak, --in-place, --in-place=.bak."""
    for i, w in enumerate(words):
        if base_name(w) in ("sed", "gsed", "perl"):
            return any(INPLACE.match(a) for a in words[i + 1:])
    return False


def copy_args(args):
    """(the plain arguments of a copy, the destinations an option names). Options, a redirect with its target, and
    a comment are not arguments."""
    plain, dest, i = [], [], 0
    while i < len(args):
        a = args[i]
        if a.startswith("#"):
            break
        if REDIR_WORD.match(a):
            i += 2
            continue
        if a.lower().startswith("--target-directory="):
            dest.append(a.split("=", 1)[1])
        elif DEST_OPT.match(a) and i + 1 < len(args):
            dest.append(args[i + 1])
            i += 1
        elif not a.startswith("-"):
            plain.append(a)
        i += 1
    return plain, dest


def stage_writes(raw: str, words, inside: bool, fed_dir: bool, fed_file: bool) -> bool:
    """One pipeline stage: its text and its unquoted words. `fed_dir`, `fed_file`: an earlier stage of the pipe
    named the folder, or the file. A writer writes the protected file only when the file (or its folder) is an
    argument of that writer's own stage, or the writer takes its arguments from the pipe (xargs, or a remover
    with none of its own)."""
    verb, args = command_of(words)
    if verb == "git":
        return git_writes(args, inside)
    named = any(names_file(w) for w in words)
    if named and (in_place(words) or WRITERS.search(raw)):
        return True
    piped = bool(words) and base_name(words[0]) == "xargs"
    if fed_file and piped and (in_place(words) or WRITERS.search(raw)):
        return True
    ci = next((k for k, w in enumerate(words) if base_name(w) in COPIERS), None)
    if ci is not None:  # copying it away is a read; copying onto it, or into its folder, is a write
        plain, dest = copy_args(words[ci + 1:])
        if any(names_file(w) or dir_target(w, inside) for w in (dest if dest else plain[1:])):
            return True
    if verb in REMOVERS:
        if any(dir_target(w, inside) for w in args) or fed_dir:
            return True
        return fed_file and not [w for w in args if not w.startswith("-")]
    if verb == "find" and (named or any(dir_target(w, inside) for w in args)):
        if "-delete" in args:
            return True
        for a, b in zip(args, args[1:]):
            if a in ("-exec", "-execdir", "-ok", "-okdir") and command_of([b])[0] in REMOVERS:
                return True
    return False


def line_writes(seg: str, inside: bool):
    """(whether one command writes a protected file, `inside` after it). The command is cut into the stages of its pipe."""
    pairs = [(r, u) for r, u in ((t, unquote(t)) for t in WORD.findall(OPERATOR.sub(lambda m: " " + m.group(0) + " ", seg))) if u]
    for (_, a), (_, b) in zip(pairs, pairs[1:]):
        if REDIR_WORD.match(a) and is_file(b):  # a redirect onto the file under another spelling
            return True, inside
    fed_dir = fed_file = False
    raws, words = [], []
    for r, u in pairs + [("|", "|")]:
        if u != "|":
            raws.append(r)
            words.append(u)
            continue
        verb, args = command_of(words)
        if verb in CD:
            inside = any(dir_target(a, False) for a in args)
        elif stage_writes(" ".join(raws), words, inside, fed_dir, fed_file):
            return True, inside
        fed_dir = fed_dir or any(dir_target(x, inside) for x in words)
        fed_file = fed_file or any(names_file(x) for x in words)
        raws, words = [], []
    return False, inside


def segment_writes(seg: str, inside: bool):
    """One command of the line, and each command substitution in it ($(...), `...`) as a command of its own."""
    pieces = SUBSHELL.split(seg)
    hit, inside = line_writes(" ".join(pieces), inside)
    if hit:
        return True, inside
    for piece in pieces[1:]:
        if HINT.search(piece) or inside:
            if line_writes(piece, inside)[0]:
                return True, inside
    return False, inside


def shell_writes(cmd: str) -> bool:
    cmd = cmd or ""
    if HINT is None or not HINT.search(cmd):  # the cheap check first; most commands stop here
        return False
    cmd = strip_messages(strip_heredocs(cmd))
    if not HINT.search(cmd):
        return False
    if NAMED.search(cmd) and REDIRECT.search(cmd):
        return True
    inside = False
    for seg in re.split(r"[;\n]|&&|\|\|", cmd):
        if not HINT.search(seg) and not inside:
            continue
        hit, inside = segment_writes(seg, inside)
        if hit:
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
    return is_file(path)


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
    # the same file under another spelling: `.` and `..`, trailing dots and spaces, an NTFS stream, any case
    bad_paths += ["docs/progress/../flow/road.graph.json", "docs/flow/./road.graph.json", "docs/flow/road.graph.json.",
                  "docs/flow/road.graph.json::$DATA", "docs\\flow\\road.graph.json . .", "docs/flow/road.graph.json:s",
                  "D:\\repo\\docs\\x\\..\\flow\\ROAD.GRAPH.JSON", "docs/flow./road.edits.jsonl", "docs//flow//road.graph.json",
                  "\\\\?\\D:\\repo\\docs\\flow\\road.graph.json", "docs/flow/road.graph.json.tmp.", "docs/flow/x/../road.graph.json"]
    good_paths += ["docs/flow/../road.graph.json", "docs/flow/road.graph.json/../notes.md", "docs/flow/road.graph.jsonx",
                   "docs/flow/notes.md", "docs/flow", "main:x"]
    # the file replaced through its folder, by a command that never names it
    bad_cmds += ["cp /tmp/road.graph.json docs/flow/", "Copy-Item x docs/flow/", "git checkout main -- docs/flow", "git restore docs/flow",
                 "rm -rf docs/flow", "mv docs/flow elsewhere", "rm -rf ./docs/flow/", "rm -rf docs/flow/*", "rm -rf DOCS\\Flow",
                 "rmdir /s /q docs\\flow", "Remove-Item -Recurse -Force .\\docs\\flow\\", "Move-Item docs/flow C:/tmp/x",
                 "git checkout .", "git checkout -- docs", "git checkout HEAD~1 -- .", "git restore .", "git restore --source=HEAD~2 docs",
                 "git stash push -- docs", "git stash -- docs/flow", "git stash push docs/flow", "git clean -fd docs/flow",
                 "git clean -fdx .", "git rm -r docs/flow", "git mv docs/flow plan", "git reset docs/flow", "git reset -- docs/flow/",
                 "git restore --staged --worktree .", "git checkout main -- :/docs/flow", "git checkout main -- ':(top)docs/flow'",
                 "git checkout main -- 'docs/flow/*.json'", "git -C docs/flow checkout .", "cd docs/flow && rm *",
                 "cd docs/flow && cp /tmp/road.graph.json .", "cd docs/flow && git checkout main -- .", "(cd docs/flow && rm *)",
                 "ls docs/flow | xargs rm", "ls|xargs rm -rf docs/flow", "xargs -n 1 rm -rf docs/flow", "Get-ChildItem docs/flow | Remove-Item",
                 "find docs/flow -delete", "find docs/flow -name '*.json' -exec rm {} +", "sudo rm -rf docs/flow", "env A=1 rm -rf docs/flow",
                 "if true; then rm -rf docs/flow; fi", "x=$(rm -rf docs/flow)", "rm -rf \"D:/my project/docs/flow\"",
                 "Remove-Item -Recurse 'D:\\my project\\docs\\flow'", "robocopy src docs\\flow /E", "rsync -a src/ docs/flow/",
                 "Copy-Item -Destination docs/flow -Path x", "cp -t docs/flow a b", "rm -rf docs/progress/../flow", "rm -rf docs/flow.",
                 # and the file itself under another spelling, in a shell command
                 "echo x > docs/progress/../flow/road.graph.json", "rm docs/flow/./road.graph.json", "rm docs/flow/road.graph.json.",
                 "Set-Content docs/flow/road.graph.json::$DATA x"]
    # reading the folder, committing it, and the everyday git commands that name no path
    good_cmds += ["ls docs/flow", "git status", "git status docs/flow", "git add docs/flow", "git add .", "git diff -- docs/flow",
                  "git diff .", "git log -- docs/flow", "git log -- .", "git show main:docs/flow", "cp -r docs/flow /tmp/backup",
                  "Copy-Item docs/flow/* C:/tmp", "Copy-Item -Recurse docs/flow C:/tmp/b", "robocopy docs\\flow backup /MIR",
                  "git stash", "git stash list", "git stash pop", "git stash show -p", "git stash push -m \"wip on the flow page\"",
                  "git checkout main", "git checkout -b docs", "git checkout docs", "git checkout feature/docs", "git reset --hard",
                  "git reset --hard origin/main", "git reset .", "git restore --staged .", "git restore --staged docs/flow",
                  "git rm --cached -r docs/flow", "git clean -fd", "git checkout main -- docs/ROADMAP.md",
                  "git checkout main -- ':!docs/flow'", "git mv docs/flow/a.md docs/flow/b.md", "grep -r rm docs/flow",
                  "find docs/flow -name '*.json'", "tar czf x.tgz docs/flow", "du -sh docs/flow", "mkdir -p docs/flow",
                  "rm out/flow/x", "rm -rf out/flow", "rm -rf docs/flowers", "rm -rf docs/flow2", "rm docs/flow/notes.md", "rm *",
                  "cd docs/flow && ls", "cd docs/flow && git status", "cd docs/flow && rm notes.md", "cd docs/flow; cd ../..; rm -rf *",
                  "ls docs/flow | grep rm", "cat docs/flow/demo.plan.toml | tee /tmp/x", "git diff --stat docs/flow | cat",
                  "git commit -m \"rm -rf docs/flow is refused now\"", "cp notes.md docs/ROADMAP.md"]
    # --- the second review: forms that got past, and ordinary commands that were refused
    # a copy onto the file is a write wherever the file stands after the source
    bad_cmds += [f"cp /tmp/x {g} 2>/dev/null", f"cp /tmp/x {g} --force", f"cp /tmp/x {g} | cat", f"cp /tmp/x {g} # note",
                 f"Copy-Item x.json {g} -Force", "copy x docs\\flow\\road.graph.json /Y", f"cp -f /tmp/x {g} -v",
                 f"Copy-Item -Destination {g} -Path x.json -Force", f"cp a b {g} 2>&1 | tee log.txt",
                 # sed and perl in place, with a suffix or the long option
                 f"sed -i.bak 's/a/b/' {g}", f"sed --in-place 's/a/b/' {g}", f"sed -i'' 's/a/b/' {g}",
                 f"sed --in-place=.bak s/a/b/ {g}", f"perl -pi.bak -e 's/a/b/' {g}", f"sed -E -i.orig s/a/b/ {g}",
                 # git with its own options before the verb
                 f"git --no-pager checkout main -- {g}", f"git -c core.autocrlf=false checkout -- {g}",
                 f"git --git-dir=.git --work-tree=. checkout -- {g}", f"git --no-pager -C . restore {l}",
                 "git --no-pager restore docs/flow", "git -c a.b=c --no-pager checkout main -- docs/flow",
                 # a shell inside a shell
                 f"bash -c \"rm {g}\"", f"sh -c 'rm {g}'", f"powershell -Command \"Remove-Item {g}\"",
                 "cmd /c \"del docs\\flow\\road.graph.json\"", "powershell -NoProfile -Command \"Remove-Item -Recurse docs/flow\"",
                 "bash -lc \"cd docs/flow && rm *\"", f"eval \"rm {g}\"", f"pwsh -NoLogo -NonInteractive -c \"Set-Content {g} x\"",
                 f"sudo sh -c 'echo x > {g}'", f"bash -c \"sh -c 'rm {g}'\"", f"wsl bash -c \"rm -rf docs/flow\"",
                 f"Invoke-Expression \"Remove-Item {g}\"", f"bash --noprofile --norc -e -u -x -v -o pipefail -c \"rm {g}\"",
                 # an escaped quote does not turn the rest of the line into a message
                 f"echo \"5\\\" pipe\"; rm {g}; echo \"x y\"", f"echo 5\\\" pipe; rm {g}; echo \"x y\"",
                 "echo \"a \\\"b\\\" c\" && rm -rf docs/flow && echo \"d e\"",
                 # a wildcard that can match a protected name, or its folder's
                 "git checkout -- '*.json'", "git restore 'docs/*'", "git restore '*'", "git clean -fdx 'docs/fl*'",
                 "rm -rf docs/fl*", "rm docs/*/road.*", "rm docs/flow/road.graph.jso?", "rm docs/flow/*.jsonl",
                 "cd docs/flow && rm *.json", "git rm 'docs/flow/road.*'",
                 # still refused: the file by name, a tree and a path, a writer fed by the pipe
                 f"git checkout {g}", "git checkout main docs/flow", f"ls {g} | xargs rm", f"Get-Item {g} | Remove-Item",
                 "find . -name road.graph.json | xargs sed -i s/a/b/", "find docs/flow -name road.graph.json -delete",
                 f"rm $(echo {g})", f"cat a | tee -a {g}", f"git diff | tee {g}", f"Get-Content a | Set-Content {g}",
                 f"git apply --include={g} fix.patch", f"git stash push -m wip -- {g}"]
    for was in ("git reset docs/flow", "git reset -- docs/flow/"):  # the index only, like the same on the file
        bad_cmds.remove(was)
    good_cmds += [
        # a wildcard that can match no protected name is not the folder
        "git restore '*.py'", "git rm *.pyc", "git checkout -- '*.md'", "git clean -fd '*.o'", "git checkout main -- docs/*.md",
        "rm docs/flow/*.md", "cd docs/flow && rm *.md", "git restore 'tools/*'", "rm -rf out/fl*", "git checkout -- 'docs/*.md'",
        # an option's value is no pathspec; one word after checkout may be a branch
        "git stash push -m docs", "git stash save docs", "git stash push --message docs/flow", "git checkout docs/flow",
        "git checkout docs", "git checkout -b docs/flow", "git restore -s docs tools/x.py", "git checkout -B docs",
        # reading the graph into a pipe whose writer has another target
        f"cat {g} | tee /tmp/copy.json", f"git diff {g} | tee x", f"Get-Content {g} | Set-Content C:/tmp/copy.json",
        f"git log -- {g} | tee /tmp/log.txt", f"jq . {g} | Out-File C:/tmp/pretty.json", f"cat {g} | sed -i s/a/b/ other.txt",
        f"grep -c M1 {g} | xargs echo", f"cat {g} | xargs -n 1 echo",
        # the index only
        f"git restore --staged {g}", f"git reset {g}", f"git rm --cached {g}", "git reset docs/flow", "git reset -- docs/flow/",
        f"git reset -q -- {g} {l}", f"git restore -S {l}",
        # a commit message is never a command, on one line or many
        f"git commit -m \"Map: graph edit 12\n\nnever rm {g} by hand\nsecond line\"",
        f"git commit -am 'first line\n\nrm -rf docs/flow would be refused\n' && git status",
        f"git commit --message=\"do not\nrm {g}\" {g}", f"git commit -m \"rm {g}\"", f"git tag -a v1 -m \"cp x {g}\"",
        # a quoted text after -c that is no shell's command
        "grep -c \"rm docs/flow\" notes.md", "bash run.sh | grep -c \"rm docs/flow\"", f"python -c \"print('rm {g}')\"", "git -c \"user.name=rm docs/flow\" status",
        # the copy the other way round, with the same trailing words
        f"cp {g} /tmp/copy.json 2>/dev/null", f"cp {g} /tmp/copy.json --force", f"Copy-Item {g} C:/tmp/copy.json -Force",
        f"copy docs\\flow\\road.graph.json C:\\tmp\\copy.json /Y", f"cp {g} /tmp/copy.json # keep a copy",
        f"sed -n 1,5p {g}", f"sed -e s/a/b/ {g} | head", f"perl -ne 'print' {g}", f"git --no-pager diff {g}",
        f"git --no-pager log -- {g}", f"bash -c \"cat {g}\"", f"powershell -Command \"Get-Content {g}\"",
        "bash -c \"ls docs/flow\"", f"echo \"5\\\" pipe\"; cat {g}; echo \"x y\""]
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
            (json.dumps({"tool_name": "Bash", "tool_input": "rm -rf docs/flow"}), 2),  # unreadable, and names the folder
            (json.dumps({"tool_name": "Bash", "tool_input": "rm -rf docs/flowers"}), 0),
            (json.dumps({"tool_name": "Bash", "tool_input": {"command": "rm -rf docs/flow"}}).replace("flow", "f\\u006cow"), 2),
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
    own += [("own list: the folder of a listed file is a target, and reading it runs",
             bash("rm -rf data") and bash("git checkout main -- data") and bash("cp x.json data/") and not bash("ls data")
             and not bash("git add data") and not bash("cp -r data /tmp/copy")),
            ("own list: a file at the top is covered by `git checkout .`, and no folder stands for it",
             bash("git checkout .") and bash("git restore .") and not bash("rm -rf docs/flow") and not bash("git status")),
            ("own list: another spelling of the listed file is blocked",
             edit("data/x/../ledger.v1.json") and edit("data/ledger.v1.json.") and edit("LOCKFILE::$DATA") and not edit("data/../ledger.v1.json"))]
    configure([], "XB2")
    own += [("an empty list protects nothing", not edit(g) and not bash(f"rm {g}") and not bash("rm -rf docs/flow")
             and not bash("git checkout .") and decide("{not json " + g, io.StringIO()) == 0)]
    configure(["docs/flow/road.graph.json"], None, "Ask the manager.")
    own += [("hooks.protect_reason replaces the refusal text", REASON == "Ask the manager." and edit(g) and not edit(l))]
    # a name that is not distinctive is matched in a shell command by its last two path parts
    s = "docs/progress/state.json"
    configure([s, "config.toml"], "XB2")
    own += [("distinctive: two dots or 16 characters; state.json and config.toml are not",
             distinctive("road.graph.json") and distinctive("a-long-ledger.json") and not distinctive("state.json")
             and not distinctive("config.toml")),
            ("generic name: Edit of the file is blocked by path, another state.json is not",
             edit(s) and edit("D:\\repo\\docs\\progress\\state.json") and not edit("out/state.json")),
            ("generic name: a shell write naming its path tail is blocked",
             bash(f"rm {s}") and bash(f"echo x > D:/repo/{s}") and bash("Set-Content docs\\progress\\state.json x")
             and bash("cd docs && sed -i s/a/b/ progress/state.json") and bash(f"rm \"D:/my project/{s}\"")),
            ("generic name: a command that writes some other state.json runs",
             not bash("rm out/state.json") and not bash("echo x > state.json")
             and not bash("rm myprogress/state.json") and not bash("cp a.json build/cache/state.json")),
            ("generic name: reading it runs", not bash(f"cat {s}") and not bash(f"git diff {s}")),
            ("generic name: another spelling of its path is blocked, in Edit and in a shell write",
             edit("docs/progress/./state.json") and edit("docs/x/../progress/state.json.") and bash("rm docs/progress/./state.json")
             and bash("echo x > docs/x/../progress/state.json") and bash("Set-Content docs/progress/state.json::$DATA x")
             and not bash("cat docs/progress/./state.json") and not bash("rm docs/progress/../state.json")),
            ("generic name: its folder is a target too", bash("rm -rf docs/progress") and bash("git restore docs/progress")
             and not bash("ls docs/progress") and not bash("rm -rf out/progress2")),
            ("generic name: unreadable input is refused only when it names the path tail",
             decide("{not json progress/state.json", io.StringIO()) == 2 and decide("{not json state.json", io.StringIO()) == 0
             and decide(json.dumps({"tool_name": "Edit", "tool_input": {"file_path": "D:\\repo\\docs\\progress\\state.json"}}),
                        io.StringIO()) == 2),
            ("a generic name at the top of the repository has only its name, so it is matched at any depth",
             bash("rm config.toml") and bash("echo x > sub/config.toml") and edit("config.toml") and edit("/repo/config.toml"))]
    # what the profile's toml file alone says
    own += [("protect_of: hooks.protect in the file wins", protect_of({"hooks": {"protect": ["a/b.json"]}}, "plan/flow") == ["a/b.json"]),
            ("protect_of: without it, the road graph files under paths.flow",
             protect_of({}, "plan\\flow/") == ["plan/flow/road.graph.json", "plan/flow/road.edits.jsonl"]),
            ("protect_of: a hooks.protect that is no list of paths, or no paths.flow, leaves the defaults",
             protect_of({"hooks": {"protect": "docs"}}, None) == DEFAULT_PROTECT and protect_of({"hooks": 7}, 3) == DEFAULT_PROTECT),
            ("read_toml of a missing file is empty", read_toml("no/such/file.toml") == {})]
    configure_from({"badge_prefix": "kb1", "paths": {"flow": "plan/flow", "tools": "tools/fdy"}})
    own += [("from the toml file alone: paths.flow moves the protection, the reason has the prefix and paths.tools",
             edit("plan/flow/road.graph.json") and not edit(g) and "KB1 ID:MGR-" in REASON and "`tools/fdy/flow.py graph" in REASON)]
    configure_from({"paths": "odd", "hooks": {"protect_reason": 5}, "badge_prefix": 9})
    own += [("from an odd toml file: the defaults", edit(g) and edit(l) and f"{DEFAULT_PREFIX} ID:MGR-" in REASON)]
    # the profile module: a strict load (SystemExit and a line on stderr), one from before `strict`, and one that raises
    class Strict:
        @staticmethod
        def load(start, strict=True):
            if strict:
                print("the profile cannot be read", file=sys.stderr)
                raise SystemExit(2)
            return "lenient"

    class Older:
        @staticmethod
        def load(start):
            return "older"

    class Exits:
        @staticmethod
        def load(start, strict=True):
            print("the profile cannot be read", file=sys.stderr)
            raise SystemExit(2)

    class Raises:
        @staticmethod
        def load(start, strict=True):
            raise RuntimeError("broken")

    was, sys.stderr = sys.stderr, io.StringIO()
    try:
        got = [load_quietly(m, ".") for m in (Strict, Older, Exits, Raises)]
        said = sys.stderr.getvalue()
    finally:
        sys.stderr = was
    own += [("the profile is loaded with strict=False; a module from before it by load(start); a load that exits or "
             "raises gives None and prints nothing into the tool call", got == ["lenient", "older", None, None] and said == "")]
    configure(DEFAULT_PROTECT, DEFAULT_PREFIX)
    # a line built to be slow is still decided at once (each is 100 KB or more)
    import time
    slow = ["git checkout ' " * 20000 + "docs/flow", "rm \"a\" 'b' \" " * 15000 + "docs/flow", "rm -rf " + "a/../" * 30000 + "docs/flow",
            "cp " + "docs/flow " * 20000, "ls docs/flow " + "| x " * 30000 + "| rm", "git status; " * 15000 + "rm -rf docs/flow",
            "rm -rf " + "docs/flow/" * 20000, "git x " + "> a " * 30000 + "docs/flow", "git checkout -- " + ":" * 100000 + "docs/flow",
            "git checkout -- " + ":(" * 50000 + "docs/flow", "rm -rf docs" + "/" * 100000 + "flow", "rm -rf docs/flow" + "." * 100000,
            "$(" * 50000 + "rm -rf docs/flow", "git " + "-C x " * 30000 + "checkout .",
            "echo \"" + "\\\" " * 40000 + f"\"; rm {g}", "echo " + "\\\" " * 40000 + f"; rm {g}", "echo \"" + "\\" * 100001 + f"\" ; rm {g}",
            ("echo \" \\\" \\\" \\\"\n" * 10000) + f"rm {g}", "bash -c \"" * 20000 + f"rm {g}", "bash " + "-x " * 40000 + f"-c \"rm {g}\"",
            "rm docs/flow/" + "*?" * 40000, "git restore " + "'*.py' " * 20000 + "docs", "git commit " + "-m \"a b\" " * 15000 + g,
            "git commit -m \"" + "line\n" * 30000 + f"\" ; rm {g}", "cp " + f"{g} " * 15000, "rm docs/flow/" + "{a,b}" * 20000,
            "x \"a\\\"\" " * 20000 + f"; rm {g}", "git checkout -- '" + "*a" * 300 + "' docs/flow"]
    t0 = time.perf_counter()
    for c in slow:
        bash(c)
    edit("a/../" * 40000 + g)
    took = time.perf_counter() - t0
    own += [(f"{len(slow) + 1} lines built to be slow are decided in under 10 s together (took {took:.2f} s)", took < 10.0)]
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
    if HINT is None:
        return 0
    if not HINT.search(raw) and "\\u" not in raw.lower():
        return 0
    err, data = err or sys.stderr, None
    try:
        data = json.loads(raw)
        stop = isinstance(data, dict) and blocked(data)
    except Exception as e:
        decoded = "" if data is None else json.dumps(data, ensure_ascii=False, default=str)
        if not any(rx.search(t) for rx in (NAMED, DIRTAIL) if rx is not None for t in (raw, decoded)):
            return 0
        print(f"graph_readonly could not read this call ({type(e).__name__}) and it names a protected file or its "
              "folder, so it is refused. " + REASON, file=err)
        return 2
    if stop:
        print(REASON, file=err)
        return 2
    return 0


configure()

if __name__ == "__main__":
    sys.exit(main())
