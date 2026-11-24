#!/usr/bin/env python3
"""Every Python file in the repository must be Python 3.11 syntax.

    <python> tests/py311_syntax_test.py [FILE ...]

Two checks over every .py file under the repository (or over the files named):

1. `ast.parse(source, feature_version=(3, 11))`: syntax that came after 3.11 which the parser knows by version
   (a `type` statement, type parameters in brackets).
2. The f-string rules that 3.12 lifted (PEP 701), which the parser does not report under feature_version. On 3.11
   a replacement field may hold no backslash, no comment, no quote of the kind that opened the f-string, and no
   line break unless the f-string is triple quoted. The tokenizer of Python 3.12 and newer gives an f-string's
   parts as tokens, so this check walks FSTRING_START..FSTRING_END and reports each case with file:line.
   On an interpreter older than 3.12 this part is skipped with a printed line: there the first check and the
   import of each file are the test, since such a file is a SyntaxError on that interpreter.

Exit 1 on any hit. Reads only; writes nothing.
"""
import ast
import io
import sys
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {"__pycache__", "out", "dist", "node_modules"}  # and every folder whose name starts with a dot
HAS_FSTRING_TOKENS = hasattr(tokenize, "FSTRING_START")  # Python 3.12 and newer


def python_files(root):
    out = []
    for f in sorted(Path(root).rglob("*.py")):
        rel = f.relative_to(root).parts[:-1]
        if not any(p in SKIP_DIRS or p.startswith(".") for p in rel):
            out.append(f)
    return out


def quote_of(text):
    """(quote character, whether triple) of a string token or an f-string's opening token (rb'..', f\"\"\", ...)."""
    i = 0
    while i < len(text) and text[i] not in "\"'":
        i += 1
    q = text[i:i + 1]
    return q, text[i:i + 3] == q * 3


def clashes(inner, outer):
    """Whether a string opened with `inner` cannot stand in a replacement field of an f-string opened with `outer`
    on 3.11: the same quote character, unless the outer is triple quoted and the inner is not."""
    return inner[0] == outer[0] and (inner[1] or not outer[1])


def fstring_hits(source):
    """[(line, what)] for each use of an f-string that needs Python 3.12. Needs the 3.12+ tokenizer."""
    hits, stack, prev = [], [], None  # stack: (quote, triple, line) of each f-string that is open
    start_t, middle_t, end_t = tokenize.FSTRING_START, tokenize.FSTRING_MIDDLE, tokenize.FSTRING_END
    # a template string (3.14) is newer than 3.11 whatever it holds; ast reports it, so it is only stepped over here
    opens = {start_t, getattr(tokenize, "TSTRING_START", start_t)}
    closes = {end_t, getattr(tokenize, "TSTRING_END", end_t)}
    middles = {middle_t, getattr(tokenize, "TSTRING_MIDDLE", middle_t)}
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        line = tok.start[0]
        in_field = bool(stack)  # between START and END, every token but the innermost MIDDLE lies in a field
        if tok.type in opens:
            q = quote_of(tok.string)
            for o in stack:
                if clashes(q, o):
                    hits.append((line, f"a nested f-string opened with {tok.string} inside one opened with {o[0] * (3 if o[1] else 1)}"))
                    break
            stack.append((q[0], q[1], line))
        elif tok.type in closes:
            if stack:
                stack.pop()
        elif tok.type in middles:
            # the text of the innermost f-string; it lies in a replacement field of every f-string around that one
            if len(stack) > 1 and "\\" in tok.string:
                hits.append((line, "a backslash in a nested f-string, so inside a replacement field"))
            if len(stack) > 1 and "\n" in tok.string and not all(o[1] for o in stack[:-1]):
                hits.append((line, "a line break in a nested f-string inside a replacement field of an f-string that is not triple quoted"))
        elif in_field:
            if tok.type == tokenize.COMMENT:
                hits.append((line, "a comment inside a replacement field"))
            elif tok.type in (tokenize.NL, tokenize.NEWLINE):
                if not all(o[1] for o in stack):
                    hits.append((line, "a line break inside a replacement field of an f-string that is not triple quoted"))
            else:
                if "\\" in tok.string:
                    hits.append((line, f"a backslash inside a replacement field ({tok.string[:30]})"))
                if tok.type == tokenize.STRING:
                    q = quote_of(tok.string)
                    for o in stack:
                        if clashes(q, o):
                            hits.append((line, f"a string in {q[0] * (3 if q[1] else 1)} quotes inside a replacement field of an "
                                               f"f-string opened with {o[0] * (3 if o[1] else 1)}"))
                            break
        # a token on a later line than the one before it ended on, with no line-break token between them: a
        # backslash line continuation, here inside a replacement field
        if in_field and prev is not None and prev.type not in (tokenize.NL, tokenize.NEWLINE, tokenize.COMMENT) \
                and line > prev.end[0]:
            hits.append((line, "a backslash line continuation inside a replacement field"))
        prev = tok
    return hits


def check_file(path, rel):
    """Lines of the form `file:line: what` for one file."""
    try:
        with open(path, encoding="utf-8") as fh:
            source = fh.read()
    except (OSError, UnicodeDecodeError) as e:
        return [f"{rel}:1: could not be read as UTF-8 ({type(e).__name__})"]
    out = []
    try:
        ast.parse(source, filename=str(rel), feature_version=(3, 11))
    except SyntaxError as e:
        out.append(f"{rel}:{e.lineno or 1}: not Python 3.11 syntax: {e.msg}")
    if HAS_FSTRING_TOKENS:
        try:
            out += [f"{rel}:{line}: f-string needs Python 3.12: {what}" for line, what in fstring_hits(source)]
        except (tokenize.TokenError, SyntaxError, IndentationError) as e:
            out.append(f"{rel}:1: could not be tokenized ({e})")
    return out


SAMPLES_BAD = [  # each needs 3.12; written as data so this file itself stays 3.11
    ("f'<b{\" class=\\\"on\\\"\" if i else \"\"}>'", "backslash"),
    ("f'{d['k']}'", "quotes"),
    ('f"{d["k"]}"', "quotes"),
    ("f'{x # note\n}'", "comment"),
    ("f'{x +\n y}'", "line break"),
    ("f'{f'{x}'}'", "nested"),
    ("f'{\"\\n\".join(a)}'", "backslash"),
    ('f"""{"""a"""}"""', "quotes"),
    ("f'{x + \\\n y}'", "line continuation"),
]
SAMPLES_GOOD = [
    "f'{d[\"k\"]}'", 'f"{d[\'k\']}"', 'f"""{d["k"]}"""', "f'''{x +\n y}'''", "f'a\\n{x}\\t'", "f'{x!r:>{w}}'",
    "f'{f\"{x}\"}'", "s = 'a' f'{x}' \"b\"", "f'{{not a field \\n}}'", "rf'\\d{n}'",
]


def main(argv):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    bad = []
    if HAS_FSTRING_TOKENS:  # the scanner's own cases first: it must see each form, and pass each 3.11 form
        for src, kind in SAMPLES_BAD:
            if not fstring_hits("x = " + src + "\n"):
                bad.append(f"scanner: missed a 3.12-only f-string ({kind}): {src!r}")
        for src in SAMPLES_GOOD:
            got = fstring_hits("x = " + src + "\n")
            if got:
                bad.append(f"scanner: flagged a 3.11 f-string: {src!r}: {got}")
    else:
        v = sys.version_info
        print(f"py311_syntax_test: Python {v[0]}.{v[1]} has no f-string tokens; the f-string scan is skipped (it needs 3.12 or newer). "
              "Here the parse of every file is the test.")
    files = [Path(a).resolve() for a in argv] or python_files(ROOT)
    for f in files:
        try:
            rel = f.relative_to(ROOT).as_posix()
        except ValueError:
            rel = str(f)
        bad += check_file(f, rel)
    for line in bad:
        print(line)
    print(f"py311_syntax_test: {len(files)} files, {len(bad)} problems" + ("" if HAS_FSTRING_TOKENS else " (f-string scan skipped)"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
