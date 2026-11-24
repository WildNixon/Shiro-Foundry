"""Tests for the no_python_stdin PreToolUse hook as a project's settings run it.

    <python> test_no_python_stdin.py

Takes the hook command from settings.example.json beside this file (or, when the hooks are installed in a
project's .claude/hooks, from that project's .claude/settings.json), puts this interpreter in place of the
`<python>` placeholder, and runs it in the shell the harness runs hook commands in, with CLAUDE_PROJECT_DIR set
to a scratch copy that has the hook file and to one that does not:
- a missing hook file lets every call run (exit 0), where a bare `<python> <file>` command exits 2 and blocks
  every call;
- a missing interpreter says the hook is inactive (exit 1, which does not block);
- with the file, a `python -` command is blocked (exit 2) and an ordinary one runs (exit 0);
- heredoc data that has a `python -` line is not blocked;
then runs the hook's own selftest. Everything it writes is in a temp folder.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLACEHOLDER = "<python>"
MARK = "reads the script from stdin"  # a piece of the hook's own reason


def hook_shell():
    """The shell hook commands run in: CLAUDE_CODE_GIT_BASH_PATH when set; on Windows the bash that ships beside
    git (a bash.exe in the system folder is a launcher for another system, not this shell); else bash, else sh."""
    env = os.environ.get("CLAUDE_CODE_GIT_BASH_PATH")
    if env and Path(env).is_file():
        return env
    if os.name == "nt":
        git = shutil.which("git")
        for parent in Path(git).resolve().parents if git else []:
            for cand in (parent / "bin" / "bash.exe", parent / "usr" / "bin" / "bash.exe"):
                if cand.is_file():
                    return str(cand)
        return None
    return shutil.which("bash") or shutil.which("sh")


def settings_file():
    """The project's own settings when these tests lie in <project>/.claude/hooks, else the example beside them."""
    own = HERE.parent / "settings.json"
    if HERE.parent.name == ".claude" and own.is_file():
        return own
    return HERE / "settings.example.json"


def hook_entry(hook_name, interpreter=None):
    """(matcher, command) of the PreToolUse entry that runs `hook_name`, with the placeholder filled in."""
    f = settings_file()
    settings = json.loads(f.read_text(encoding="utf-8"))
    py = interpreter or Path(sys.executable).as_posix()
    for entry in settings["hooks"]["PreToolUse"]:
        for h in entry["hooks"]:
            if hook_name in h.get("command", ""):
                return entry["matcher"], h["command"].replace(PLACEHOLDER, py)
    raise SystemExit(f"no {hook_name} hook in {f}")


def main() -> int:
    shell = hook_shell()
    if not shell:
        print("test_no_python_stdin: no shell found to run the hook command in; set CLAUDE_CODE_GIT_BASH_PATH")
        return 1
    _, cmd = hook_entry("no_python_stdin.py")
    py = Path(sys.executable).as_posix()
    bare = f'"{py}" "$CLAUDE_PROJECT_DIR/.claude/hooks/no_python_stdin.py"'  # a command with no guard for a missing file
    tmp = Path(tempfile.mkdtemp(prefix="hook-test-"))
    ok, bad = [], []

    def expect(name, cond, detail=""):
        (ok if cond else bad).append(name)
        print(("  ok   " if cond else "  FAIL ") + name + ("" if cond else f": {detail}"))

    try:
        with_dir, without_dir = tmp / "with", tmp / "without"
        (with_dir / ".claude" / "hooks").mkdir(parents=True)
        without_dir.mkdir()
        shutil.copy2(HERE / "no_python_stdin.py", with_dir / ".claude" / "hooks" / "no_python_stdin.py")

        def run(command, project, shell_cmd):
            payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": shell_cmd}})
            r = subprocess.run([shell, "-c", command], input=payload, capture_output=True, text=True,
                               env={**os.environ, "CLAUDE_PROJECT_DIR": str(project)}, timeout=60)
            return r.returncode, r.stderr

        stdin_cmd = "python - <<'EOF'\nprint(1)\nEOF"
        data_cmd = "cat > cases.txt <<'EOF'\npython - <<X\nEOF"
        rc, err = run(cmd, without_dir, "ls")
        expect("a missing hook file lets an ordinary call run (exit 0)", rc == 0, f"{rc} {err}")
        rc, err = run(cmd, without_dir, stdin_cmd)
        expect("a missing hook file blocks nothing (exit 0)", rc == 0, f"{rc} {err}")
        rc, err = run(bare, without_dir, "ls")
        expect("control: a command without the guard blocks every call when the file is missing (exit 2)", rc == 2, f"{rc} {err}")
        _, gone = hook_entry("no_python_stdin.py", (tmp / "no-such-python").as_posix())
        rc, err = run(gone, with_dir, stdin_cmd)
        expect("a missing interpreter says the hook is inactive (exit 1: the call is not blocked)",
               rc == 1 and "inactive" in err, f"{rc} {err}")
        rc, err = run(cmd, with_dir, stdin_cmd)
        expect("with the file, `python -` is blocked (exit 2, the hook's reason)", rc == 2 and MARK in err, f"{rc} {err}")
        rc, err = run(cmd, with_dir, "python tools/office.py roster")
        expect("with the file, an ordinary python call runs (exit 0)", rc == 0, f"{rc} {err}")
        rc, err = run(cmd, with_dir, data_cmd)
        expect("heredoc data with a `python -` line runs (exit 0)", rc == 0, f"{rc} {err}")
        rc, err = run(cmd, with_dir, data_cmd + "\npython -")
        expect("a `python -` command after the heredoc ends is still blocked", rc == 2, f"{rc} {err}")
        # A `<<word` the body-strip could take for a heredoc must not hide a later `python -`. The first three have
        # no end line and fail closed (the whole command is checked); the CRLF one is not fail-closed: its end line
        # `EOF\r` matches with the \r ignored, and the `python -` after it is still blocked. Each is also in the
        # hook selftest's `bad`.
        cases = [("a shift in $((x<<y))", "echo $((x<<y))\npython -"),
                 ("<<EOF inside quotes", "echo \"use <<EOF here\"\npython -"),
                 ("<<EOF in a comment", "# see <<EOF\npython -"),
                 ("a CRLF heredoc (end line EOF\\r matched)", "cat <<EOF\r\nx\r\nEOF\r\npython -\r"),
                 ("a quoted <<EOF before a real heredoc", "echo \"<<EOF\"\npython -\ncat <<EOF\nx\nEOF"),
                 ("a comment <<EOF before a real heredoc", "# see <<EOF\npython -\ncat <<EOF\nx\nEOF"),
                 ("a quoted part in the end word", "cat <<E\"OF\"\nx\nEOF\npython -\nE"),
                 ("a dash in the end word", "cat <<EOF-1\nx\nEOF-1\npython -\nEOF"),
                 ("a backslash after the opener", "cat <<EOF \\\n&& python -\nx\nEOF")]
        for name, shell_cmd in cases:
            rc, err = run(cmd, with_dir, shell_cmd)
            expect(name + ", then `python -`: blocked (exit 2)", rc == 2 and MARK in err, f"{rc} {err}")
        rc, err = run(cmd, with_dir, "cat <<EOF\r\npython -\r\nEOF\r\nls\r")
        expect("CRLF heredoc data with a `python -` line runs (exit 0)", rc == 0, f"{rc} {err}")
        st = subprocess.run([sys.executable, str(HERE / "no_python_stdin.py"), "selftest"], capture_output=True, text=True)
        print(st.stdout.strip())
        expect("the hook's own selftest passes", st.returncode == 0, st.stdout)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"test_no_python_stdin: {len(ok)} ok, {len(bad)} failed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
