"""PreToolUse hook: refuse a shell command that runs python from stdin (`python -`, `python3 -`, `py -`).
In some harness shells a python that reads its script from stdin never gets an end of input and hangs the call.
Write a script file and run it instead.

Reads the hook's JSON on stdin; exit 2 with a reason on stderr blocks the call; exit 0 lets it run.
Selftest: <python> no_python_stdin.py selftest
Standard library only; nothing in it depends on the host or the project.
"""
import json
import re
import sys

# python, python3, python3.12, py, optionally a path or .exe, then a lone "-" as an argument
# only where a command starts (line start, after ; & | ( or a backtick) or after a path separator, so prose
# that mentions "python -" inside a note or commit message is not blocked
PAT = re.compile(r"(?:^|[;&|(`]\s*|[/\\])(?:python(?:3(?:\.\d+)?)?|py)(?:\.exe)?\s+(?:-[A-Za-z]+\s+)*-(?=\s|$|<|\||;|&|\))",
                 re.MULTILINE)

REASON = ("Blocked: `python -` reads the script from stdin, which can hang the call in this shell. "
          "Write the script to a file (a scratch folder is fine) and run it by path: `<python> <file>`.")


# a heredoc start (<<EOF, <<-EOF, <<'EOF', << "EOF"); not a here-string (<<<). The word must end where the shell
# word ends, so `<<E"OF"`, `<<EOF-1`, `<<E$x` or `<<EOF.x` give no match and fail closed
HEREDOC = re.compile(r"(?<!<)<<(-?)\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\2(?=[\s;&|<>()]|$)")
# characters after which a `#` starts a comment (a word start)
WORD_BREAK = " \t;&|()<>"


def heredoc_openers(line: str, stack: list):
    """The `<<` that bash reads as heredoc openers on one command line, skipping any inside quotes or after an
    unquoted comment `#`. `stack` carries the quote and `$(` state across lines and is updated in place. Returns a
    list of (tabs, word), or None for a `<<` in code that HEREDOC cannot read whole (fail closed)."""
    found, i, n = [], 0, len(line)
    while i < n:
        top = stack[-1] if stack else None
        c = line[i]
        if top == "sq":
            if c == "'":
                stack.pop()
            i += 1
            continue
        if c == "\\":
            i += 2
            continue
        if top == "dq":
            if c == '"':
                stack.pop()
            elif line.startswith("$(", i):
                stack.append(0)
                i += 2
                continue
            elif c == "`":
                stack.append("bt")
            i += 1
            continue
        # code: the top level, inside $( ) (an int: its open-paren depth) or inside backticks
        if c == "'":
            stack.append("sq")
        elif c == '"':
            stack.append("dq")
        elif c == "`":
            if top == "bt":
                stack.pop()
            else:
                stack.append("bt")
        elif line.startswith("$(", i):
            stack.append(0)
            i += 2
            continue
        elif c == "(" and isinstance(top, int):
            stack[-1] += 1
        elif c == ")" and isinstance(top, int):
            if top:
                stack[-1] -= 1
            else:
                stack.pop()
        elif c == "#" and (i == 0 or line[i - 1] in WORD_BREAK):
            break  # a comment runs to the end of the line
        elif line.startswith("<<<", i):
            i += 3
            continue
        elif line.startswith("<<", i):
            m = HEREDOC.match(line, i)
            if not m:
                return None
            found.append((bool(m.group(1)), m.group(3)))
            i = m.end()
            continue
        i += 1
    return found


def strip_heredoc_bodies(cmd: str) -> str:
    """The lines of a heredoc are data, not commands: a test file written with `cat > f <<EOF` whose data has a line
    starting `python -` must not be blocked. Drop each body (up to its delimiter line) and keep every command line,
    so `python - <<EOF` itself is still matched.

    A `<<word` with no delimiter line is not a heredoc we can trust (a shift in `$((x<<y))`, a `<<EOF` inside quotes
    or a comment), so the hook fails closed: if any heredoc is left open at the end, the whole command is checked
    as it came. A CRLF delimiter line (`EOF\\r`) still ends its body: a trailing \\r is ignored.

    A `<<` inside quotes or a comment opens nothing (heredoc_openers), so it cannot swallow the lines up to a later
    real heredoc's end. A `<<word` that HEREDOC cannot read whole keeps every line. An opener line ending in a
    backslash joins the next line in bash, so it keeps every line too."""
    lines, out, ends, stack = (cmd or "").split("\n"), [], [], []
    for line in lines:
        if ends:
            tabs, word = ends[0]
            end = line.rstrip("\r")
            if (end.lstrip("\t") if tabs else end) == word:
                ends.pop(0)
            continue
        out.append(line)
        ends = heredoc_openers(line, stack)
        if ends is None or (ends and line.rstrip("\r").endswith("\\")):
            return cmd or ""
    if ends:  # an unterminated <<word: keep every line (fail closed)
        return cmd or ""
    return "\n".join(out)


# Each of these once fooled a body-strip into dropping the later `python -` line (fail open).
# The first three have no delimiter line and are kept whole (fail closed). The CRLF case finds its end line
# with the \r ignored, so the `python -` after it is a command and is blocked.
OPEN_BAD = ["echo $((x<<y))\npython -", "echo \"use <<EOF here\"\npython -", "# see <<EOF\npython -",
          "cat <<EOF\r\nx\r\nEOF\r\npython -\r"]
# a fake `<<EOF` in quotes or a comment, then a real heredoc ending EOF, must not swallow the `python -` between them
FAKE_BAD = ["echo \"<<EOF\"\npython -\ncat <<EOF\nx\nEOF", "echo '<<EOF'\npython -\ncat <<EOF\nx\nEOF",
            "# see <<EOF\npython -\ncat <<EOF\nx\nEOF", "ls # <<EOF\npython -\ncat <<EOF\nx\nEOF"]
# bash ends each body at the whole word, not at a prefix of it
WORD_BAD = ["cat <<E\"OF\"\nx\nEOF\npython -\nE", "cat <<EOF-1\nx\nEOF-1\npython -\nEOF",
          "cat <<E$x\nx\nE$x\npython -\nE", "cat <<EOF.x\nx\nEOF.x\npython -\nEOF"]
# a backslash-newline joins the opener line with the next, which bash runs as a command
JOIN_BAD = ["cat <<EOF \\\n&& python -\nx\nEOF", "cat <<EOF \\\r\n&& python -\r\nx\r\nEOF\r"]


def blocked(cmd: str) -> bool:
    return bool(PAT.search(strip_heredoc_bodies(cmd or "")))


def selftest() -> int:
    bad = ["python - <<'EOF'\nprint(1)\nEOF", "cd x && python -", "python3 - < a.py", "py -", "python -I - <<EOF",
           "C:/Python312/python.exe - <<EOF", "echo hi | python -", "(python -)"]
    good = ["python -m pytest", "python -c 'print(1)'", "python tools/office.py roster", "python -I x.py",
            "git log -- a.py", "python script.py -", "pip install x", "python3 -V", "grep 'python -' notes.md",
            "python tools/board.py note --by X \"a hook refusing python - in a shell\"",
            "git commit -m \"hook: no python - in a shell\"",
            # heredoc data is not a command
            "cat > cases.txt <<'EOF'\npython - <<X\npy -\nEOF", "cat > a.md <<-EOF\n\tpython -\n\tEOF\nls",
            "git commit -F - <<'EOF'\nfix\n\npython - hung here\nEOF"]
    bad += ["cat > a <<EOF\nx\nEOF\npython - <<EOF\nprint(1)\nEOF",  # a command after a heredoc's end still counts
            "python - <<'EOF'\npython -\nEOF", "cat <<A <<B\na\nA\nb\nB\npython -"]
    bad += OPEN_BAD
    good += ["cat <<EOF\r\nx\r\nEOF\r\nls\r"]  # a CRLF heredoc ends at `EOF\r`; its data is still data
    bad += FAKE_BAD + WORD_BAD + JOIN_BAD
    # still heredocs: inside "$( )", in $( ) and backticks, a redirect after the word, a `#` mid-word
    good += ["git commit -m \"$(cat <<'EOF'\nfix\npython - hung\nEOF\n)\"", "x=$(cat <<EOF\npython -\nEOF\n)",
             "cat <<EOF>f\npython -\nEOF", "echo a#b; cat <<EOF\npython -\nEOF", "echo \"#\" 'x' <<<s; cat <<EOF\npy -\nEOF"]
    fails = [c for c in bad if not blocked(c)] + [c for c in good if blocked(c)]
    for c in fails:
        print("FAIL", repr(c))
    print(f"no_python_stdin selftest: {len(bad) + len(good) - len(fails)} ok, {len(fails)} failed")
    return 1 if fails else 0


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "selftest":
        return selftest()
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    cmd = (data.get("tool_input") or {}).get("command", "")
    if blocked(cmd):
        print(REASON, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
