"""Tests for the graph_readonly PreToolUse hook as a project's settings run it.

    <python> test_graph_readonly.py

Takes the hook command from settings.example.json beside this file (or the project's .claude/settings.json when
installed there), fills in this interpreter, and runs it in the harness's hook shell with CLAUDE_PROJECT_DIR set
to a scratch copy that has the hook file and to one that does not:
- a missing hook file lets every call run (exit 0);
- with the file, an Edit or Write of the road graph or its edit log is blocked (exit 2), in a worktree's copy too;
- a shell command that writes either file is blocked; one that reads or commits it runs;
- the same file under another spelling (`..`, a trailing dot, an NTFS stream) is blocked; a command that replaces
  the file through its folder without naming it (rm -rf, cp into it, git checkout of it) is blocked, and one that
  reads the folder runs; lines built to be slow are decided at once;
- the settings entry matches the edit tools and both shells;
- a project whose profile lists other files protects those instead; a profile module that cannot be imported
  leaves the defaults in force and crashes nothing, and so does one whose load() exits (a strict load) or is from
  before load(start, strict=False);
- a project that moves paths.flow moves the protection (with the module found through paths.tools, and with no
  module at all, from the toml file alone); a generic file name in hooks.protect is matched in a shell command by
  its path tail;
then runs the hook's own selftest. Everything it writes is in a temp folder. Each run names its scratch project
in FOUNDRY_ROOT as well as CLAUDE_PROJECT_DIR, so the profile is never looked for in a repository the temp folder
may lie in.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_no_python_stdin import hook_entry, hook_shell  # noqa: E402


def main() -> int:
    shell = hook_shell()
    if not shell:
        print("test_graph_readonly: no shell found to run the hook command in; set CLAUDE_CODE_GIT_BASH_PATH")
        return 1
    matcher, cmd = hook_entry("graph_readonly.py")
    tmp = Path(tempfile.mkdtemp(prefix="hook-test-")).resolve()  # its real name (macOS /var, a Windows 8.3 name)
    ok, bad = [], []
    base_env = {k: v for k, v in os.environ.items() if not k.startswith("FOUNDRY_")}

    def expect(name, cond, detail=""):
        (ok if cond else bad).append(name)
        print(("  ok   " if cond else "  FAIL ") + name + ("" if cond else f": {detail}"))

    def install(project):
        (project / ".claude" / "hooks").mkdir(parents=True)
        for f in ("graph_readonly.py", "no_python_stdin.py"):
            shutil.copy2(HERE / f, project / ".claude" / "hooks" / f)

    try:
        with_dir, without_dir = tmp / "with", tmp / "without"
        install(with_dir)
        without_dir.mkdir()

        def run(project, tool, **inp):
            r = subprocess.run([shell, "-c", cmd], input=json.dumps({"tool_name": tool, "tool_input": inp}), capture_output=True,
                               text=True, env={**base_env, "CLAUDE_PROJECT_DIR": str(project), "FOUNDRY_ROOT": str(project)}, timeout=60)
            return r.returncode, r.stderr

        g = "docs/flow/road.graph.json"
        expect("the settings entry covers the edit tools and both shells",
               set(matcher.split("|")) >= {"Edit", "Write", "NotebookEdit", "Bash", "PowerShell"}, matcher)
        rc, err = run(without_dir, "Edit", file_path=g)
        expect("a missing hook file blocks nothing (exit 0)", rc == 0, f"{rc} {err}")
        rc, err = run(with_dir, "Edit", file_path=str(with_dir / "docs" / "flow" / "road.graph.json"))
        expect("Edit of the graph is blocked (exit 2, the hook's reason)", rc == 2 and "flow.py graph" in err and "manager" in err, f"{rc} {err}")
        rc, err = run(with_dir, "Write", file_path="D:\\repo\\.claude\\worktrees\\emp-1\\docs\\flow\\road.edits.jsonl")
        expect("Write of the edit log in a worktree is blocked", rc == 2, f"{rc} {err}")
        rc, err = run(with_dir, "Edit", file_path="docs/ROADMAP.md")
        expect("Edit of another file runs (exit 0)", rc == 0, f"{rc} {err}")
        rc, err = run(with_dir, "Write", file_path="out/flow/graph.json")
        expect("Write of the built graph.json under out/ runs", rc == 0, f"{rc} {err}")
        rc, err = run(with_dir, "Bash", command=f"echo '{{}}' > {g}")
        expect("a redirect onto the graph is blocked", rc == 2, f"{rc} {err}")
        rc, err = run(with_dir, "PowerShell", command=f"Set-Content {g} '{{}}'")
        expect("Set-Content on the graph is blocked", rc == 2, f"{rc} {err}")
        rc, err = run(with_dir, "Bash", command=f"git checkout main -- {g}")
        expect("git checkout of the graph is blocked", rc == 2, f"{rc} {err}")
        rc, err = run(with_dir, "Bash", command=f"cat {g} && git log --oneline -- {g}")
        expect("reading the graph runs", rc == 0, f"{rc} {err}")
        rc, err = run(with_dir, "Bash", command=f"git add {g} docs/flow/road.edits.jsonl && git commit -m \"Map: graph edit 3\"")
        expect("committing the graph runs", rc == 0, f"{rc} {err}")
        rc, err = run(with_dir, "Bash", command="python tools/flow.py graph link M1 M2 --by \"FB1 ID:MGR-1 SIG:X\"")
        expect("the script that edits the graph runs", rc == 0, f"{rc} {err}")
        rc, err = run(with_dir, "Read", file_path=g)
        expect("Read of the graph runs even if the matcher were widened to it", rc == 0, f"{rc} {err}")
        # a checkout whose path has a space, quoted
        rc, err = run(with_dir, "Bash", command=f"rm \"D:/my project/{g}\"")
        expect("rm of the quoted spaced path is blocked", rc == 2, f"{rc} {err}")
        rc, err = run(with_dir, "PowerShell", command="Remove-Item \"D:\\my project\\docs\\flow\\road.edits.jsonl\"")
        expect("Remove-Item of the quoted spaced path is blocked", rc == 2, f"{rc} {err}")
        # the same file under another spelling
        for what, spelled in (("a path through ..", "docs/progress/../flow/road.graph.json"), ("a path through .", "docs/flow/./road.graph.json"),
                              ("a trailing dot", g + "."), ("an NTFS stream suffix", g + "::$DATA"), ("another case", "DOCS/Flow/Road.Graph.JSON")):
            rc, err = run(with_dir, "Edit", file_path=spelled)
            expect(f"Edit of the graph spelled with {what} is blocked", rc == 2, f"{rc} {err}")
            rc, err = run(with_dir, "Write", file_path=str(with_dir) + "\\" + spelled.replace("/", "\\"))
            expect(f"Write of it under the checkout's full path with {what} is blocked", rc == 2, f"{rc} {err}")
        rc, err = run(with_dir, "Edit", file_path="docs/flow/../road.graph.json")
        expect("a path that only passes through the folder is another file and runs", rc == 0, f"{rc} {err}")
        # the file replaced through its folder, by a command that never names it
        for tool, command in (("Bash", "cp /tmp/road.graph.json docs/flow/"), ("PowerShell", "Copy-Item x docs/flow/"),
                              ("Bash", "git checkout main -- docs/flow"), ("Bash", "git restore docs/flow"), ("Bash", "rm -rf docs/flow"),
                              ("Bash", "mv docs/flow elsewhere"), ("PowerShell", "Remove-Item -Recurse -Force .\\docs\\flow"),
                              ("Bash", "git checkout ."), ("Bash", "cd docs/flow && git checkout main -- ."),
                              ("Bash", "rm -rf \"D:/my project/docs/flow\""), ("Bash", "ls docs/flow | xargs rm")):
            rc, err = run(with_dir, tool, command=command)
            expect(f"`{command}` is blocked (exit 2, the hook's reason)", rc == 2 and "flow.py graph" in err, f"{rc} {err}")
        for command in ("ls docs/flow", "git status", "git add docs/flow", "git diff -- docs/flow", "git log -- docs/flow",
                        "cp -r docs/flow /tmp/backup", "git stash", "git reset --hard", "git checkout main", "rm -rf out/flow"):
            rc, err = run(with_dir, "Bash", command=command)
            expect(f"`{command}` runs (exit 0)", rc == 0, f"{rc} {err}")
        # the second review: forms that got past, and ordinary commands that were refused
        bs = "docs\\flow\\road.graph.json"
        for tool, command in (
                ("Bash", f"cp /tmp/x {g} 2>/dev/null"), ("Bash", f"cp /tmp/x {g} --force"), ("Bash", f"cp /tmp/x {g} | cat"),
                ("Bash", f"cp /tmp/x {g} # note"), ("PowerShell", f"Copy-Item x.json {g} -Force"), ("PowerShell", f"copy x {bs} /Y"),
                ("Bash", f"sed -i.bak 's/a/b/' {g}"), ("Bash", f"sed --in-place 's/a/b/' {g}"), ("Bash", f"sed -i'' 's/a/b/' {g}"),
                ("Bash", f"perl -pi.bak -e 's/a/b/' {g}"), ("Bash", f"git --no-pager checkout main -- {g}"),
                ("Bash", f"git -c core.autocrlf=false --git-dir=.git --work-tree=. checkout -- {g}"),
                ("Bash", f"bash -c \"rm {g}\""), ("Bash", f"sh -c 'rm {g}'"), ("PowerShell", f"powershell -Command \"Remove-Item {g}\""),
                ("PowerShell", f"cmd /c \"del {bs}\""), ("Bash", f"bash --noprofile --norc -e -u -x -v -o pipefail -c \"rm {g}\""),
                ("Bash", f"echo \"5\\\" pipe\"; rm {g}; echo \"x y\""), ("Bash", "git checkout -- '*.json'"),
                ("Bash", f"git checkout {g}"), ("Bash", f"ls {g} | xargs rm"), ("Bash", "rm -rf docs/fl*")):
            rc, err = run(with_dir, tool, command=command)
            expect(f"`{command}` is blocked (exit 2)", rc == 2 and "flow.py graph" in err, f"{rc} {err}")
        for tool, command in (
                ("Bash", "git restore '*.py'"), ("Bash", "git rm *.pyc"), ("Bash", "git checkout -- '*.md'"), ("Bash", "git clean -fd '*.o'"),
                ("Bash", "git checkout main -- docs/*.md"), ("Bash", "git stash push -m docs"), ("Bash", "git stash save docs"),
                ("Bash", "git checkout docs/flow"), ("Bash", f"cat {g} | tee /tmp/copy.json"), ("Bash", f"git diff {g} | tee x"),
                ("PowerShell", f"Get-Content {g} | Set-Content C:/tmp/copy.json"), ("Bash", f"git restore --staged {g}"),
                ("Bash", f"git reset {g}"), ("Bash", f"git rm --cached {g}"), ("Bash", "git reset docs/flow"),
                ("Bash", f"git commit -m \"Map: graph edit 12\n\nnever rm {g} by hand\nsecond line\""),
                ("Bash", f"cp {g} /tmp/copy.json 2>/dev/null"), ("Bash", f"bash -c \"cat {g}\""),
                ("Bash", "grep -c \"rm docs/flow\" notes.md"), ("Bash", f"sed -n 1,5p {g}"), ("Bash", f"git --no-pager diff {g}")):
            rc, err = run(with_dir, tool, command=command)
            expect(f"`{command}` runs (exit 0)", rc == 0, f"{rc} {err}")
        # a long line is decided fast, and what the hook cannot read is refused when it names the file
        hook = with_dir / ".claude" / "hooks" / "graph_readonly.py"

        def timed(payload: str):
            t = time.monotonic()
            r = subprocess.run([sys.executable, str(hook)], input=payload.encode("utf-8"), capture_output=True, timeout=60,
                               env={**base_env, "CLAUDE_PROJECT_DIR": str(with_dir), "FOUNDRY_ROOT": str(with_dir)})
            return r.returncode, time.monotonic() - t

        long_prose = "echo it's " + "a b " * 25000  # 100 KB, one line, an unclosed quote
        rc, dt = timed(json.dumps({"tool_name": "Bash", "tool_input": {"command": long_prose}}))
        expect("a 100 KB line without the file name runs in under 1 s", rc == 0 and dt < 1.0, f"{rc} {dt:.2f}s")
        rc, dt = timed(json.dumps({"tool_name": "Bash", "tool_input": {"command": long_prose + f" ; rm {g}"}}))
        expect("a 100 KB line with an unclosed quote that rm's the graph is blocked in under 2 s",
               rc == 2 and dt < 2.0, f"{rc} {dt:.2f}s")
        rc, dt = timed(json.dumps({"tool_name": "Bash", "tool_input": {"command": long_prose + f" ; cat {g}"}}))
        expect("a 100 KB line with an unclosed quote that reads the graph runs in under 2 s",
               rc == 0 and dt < 2.0, f"{rc} {dt:.2f}s")
        # lines built to be slow for the folder forms: quotes left open, a deep path, many pipes, many colons
        for what, line, want in (
                ("a quote opened 20000 times", "git checkout ' " * 20000 + "docs/flow", 2),
                ("a path through 30000 `..`", "rm -rf " + "a/../" * 30000 + "docs/flow", 2),
                ("30000 pipes", "ls docs/flow " + "| x " * 30000 + "| rm", 2),
                ("15000 commands", "git status; " * 15000 + "rm -rf docs/flow", 2),
                ("100000 colons", "git checkout -- " + ":" * 100000 + "docs/flow", 0),
                ("50000 substitutions", "$(" * 50000 + "ls docs/flow", 0),
                ("40000 escaped quotes", "echo \"" + "\\\" " * 40000 + f"\"; rm {g}", 2),
                ("a shell in a shell 20000 deep", "bash -c \"" * 20000 + f"rm {g}", 2),
                ("40000 options before -c", "bash " + "-x " * 40000 + f"-c \"rm {g}\"", 2),
                ("a message of 30000 lines", "git commit -m \"" + "line\n" * 30000 + f"\" ; rm {g}", 2),
                ("a wildcard of 80000 characters", "rm docs/flow/" + "*?" * 40000, 2),
                ("20000 wildcard pathspecs", "git restore " + "'*.py' " * 20000 + "tools", 0)):
            rc, dt = timed(json.dumps({"tool_name": "Bash", "tool_input": {"command": line}}))
            expect(f"a line of {len(line) // 1000} KB with {what} is decided in under 2 s (exit {want})", rc == want and dt < 2.0, f"{rc} {dt:.2f}s")
        rc, dt = timed(json.dumps({"tool_name": "Edit", "tool_input": {"file_path": "a/../" * 40000 + g}}))
        expect("an Edit path of 200 KB through `..` is blocked in under 2 s", rc == 2 and dt < 2.0, f"{rc} {dt:.2f}s")
        rc, _ = timed("{\"tool_name\": \"Bash\", \"tool_input\": {\"command\": \"rm " + g + "\"")  # cut short
        expect("malformed input naming the graph is blocked (exit 2)", rc == 2, str(rc))
        rc, _ = timed("{\"tool_name\": \"Bash\", \"tool_input\": {\"command\": \"ls\"")
        expect("malformed input not naming the graph runs (exit 0)", rc == 0, str(rc))

        # the profile: a project that lists its own files, and one whose profile module cannot be imported
        module = HERE.parent / "tools" / "foundry_profile.py"
        if not module.is_file():
            print("  skip the profile cases: no ../tools/foundry_profile.py beside the hooks")
        else:
            own = tmp / "own list"
            install(own)
            (own / "scripts" / "foundry").mkdir(parents=True)
            shutil.copy2(module, own / "scripts" / "foundry" / "foundry_profile.py")
            (own / ".foundry").mkdir()
            (own / ".foundry" / "foundry.toml").write_text(
                'badge_prefix = "xb2"\n[hooks]\nprotect = ["data/ledger.json"]\n', encoding="utf-8")
            rc, err = run(own, "Edit", file_path=str(own / "data" / "ledger.json"))
            expect("with hooks.protect in the profile, the listed file is blocked and the reason carries the badge prefix",
                   rc == 2 and "data/ledger.json" in err and "XB2 ID:MGR-" in err and "scripts/foundry/flow.py" in err, f"{rc} {err}")
            rc, err = run(own, "Bash", command="echo x > data/ledger.json")
            expect("a shell write of the listed file is blocked", rc == 2, f"{rc} {err}")
            rc, err = run(own, "Edit", file_path=g)
            expect("a file the profile's list leaves out is not protected", rc == 0, f"{rc} {err}")
            (own / ".foundry" / "foundry.toml").write_text("[hooks\nprotect = 7", encoding="utf-8")
            rc, err = run(own, "Edit", file_path=g)
            expect("a profile file that cannot be read leaves the defaults in force, and the module's own complaint "
                   "about it does not reach the tool call", rc == 2 and "FB1 ID:MGR-" in err and "Traceback" not in err
                   and "foundry:" not in err, f"{rc} {err}")
            rc, err = run(own, "Edit", file_path="docs/ROADMAP.md")
            expect("... and with that profile file another file still runs, in silence", rc == 0 and not err.strip(), f"{rc} {err}")
            rc, err = run(own, "Bash", command="ls docs/flow")
            expect("... and so does a command that only reads the folder", rc == 0 and not err.strip(), f"{rc} {err}")
            (own / ".foundry" / "foundry.toml").write_text('[hooks]\nprotect = "docs"\n', encoding="utf-8")
            rc, err = run(own, "Edit", file_path=g)
            expect("a hooks.protect that is not a list leaves the defaults in force", rc == 2, f"{rc} {err}")
            # the protection follows paths.flow; the module is found through paths.tools
            moved = tmp / "moved flow"
            install(moved)
            (moved / "tools" / "fdy").mkdir(parents=True)
            shutil.copy2(module, moved / "tools" / "fdy" / "foundry_profile.py")
            (moved / ".foundry").mkdir()
            (moved / ".foundry" / "foundry.toml").write_text(
                'badge_prefix = "kb1"\n[paths]\ntools = "tools/fdy"\nflow = "plan/flow"\n', encoding="utf-8")
            rc, err = run(moved, "Edit", file_path=str(moved / "plan" / "flow" / "road.graph.json"))
            expect("with paths.flow moved and no hooks.protect, the graph under the new folder is blocked; the module "
                   "is found through paths.tools (the reason names it and the badge prefix)",
                   rc == 2 and "plan/flow/road.graph.json" in err and "KB1 ID:MGR-" in err and "tools/fdy/flow.py" in err,
                   f"{rc} {err}")
            rc, err = run(moved, "Bash", command="echo x >> plan/flow/road.edits.jsonl")
            expect("... and a shell write of its edit log is blocked", rc == 2, f"{rc} {err}")
            rc, err = run(moved, "Edit", file_path=g)
            expect("... and the old default path is no longer protected", rc == 0, f"{rc} {err}")
            (moved / ".foundry" / "foundry.toml").write_text(
                '[paths]\ntools = "tools/fdy"\nflow = "plan/flow"\n[hooks]\nprotect = ["docs/progress/state.json"]\n',
                encoding="utf-8")
            rc, err = run(moved, "Edit", file_path="plan/flow/road.graph.json")
            expect("hooks.protect set in the project's file wins over paths.flow", rc == 0, f"{rc} {err}")
            rc, err = run(moved, "Bash", command="rm docs/progress/state.json")
            expect("a generic name in hooks.protect: a shell write naming its path tail is blocked", rc == 2, f"{rc} {err}")
            rc, err = run(moved, "Bash", command="rm out/cache/state.json && echo x > state.json")
            expect("... and a command that writes another state.json runs", rc == 0, f"{rc} {err}")
            # no profile module anywhere the hook looks: it goes by the toml file alone
            alone = tmp / "alone"
            install(alone)
            (alone / ".foundry").mkdir()
            (alone / ".foundry" / "foundry.toml").write_text('badge_prefix = "zb3"\n[paths]\nflow = "plan/flow"\n', encoding="utf-8")
            rc, err = run(alone, "Write", file_path="plan/flow/road.graph.json")
            rc2, err2 = run(alone, "Write", file_path=g)
            expect("with no profile module, the toml file alone moves the protection and names the prefix",
                   rc == 2 and "ZB3 ID:MGR-" in err and rc2 == 0 and "Traceback" not in err + err2, f"{rc} {err} {rc2} {err2}")
            (alone / ".foundry" / "foundry.toml").write_text('[paths\nflow = 7', encoding="utf-8")
            rc, err = run(alone, "Write", file_path=g)
            expect("... and a toml file that cannot be read leaves the built-in defaults", rc == 2 and "Traceback" not in err, f"{rc} {err}")
            rc, dt = timed(json.dumps({"tool_name": "Bash", "tool_input": {"command": "ls"}}))
            expect("a call that names no protected file is decided in under 1 s", rc == 0 and dt < 1.0, f"{rc} {dt:.2f}s")
            broken = tmp / "broken"
            install(broken)
            (broken / "scripts" / "foundry").mkdir(parents=True)
            (broken / "scripts" / "foundry" / "foundry_profile.py").write_text("import sys\nsys.exit(3)\ndef (:\n", encoding="utf-8")
            rc, err = run(broken, "Edit", file_path=g)
            expect("a profile module that cannot be imported: the hook does not crash, the defaults block the graph",
                   rc == 2 and "Traceback" not in err, f"{rc} {err}")
            rc, err = run(broken, "Edit", file_path="docs/ROADMAP.md")
            expect("and another file still runs (exit 0)", rc == 0 and "Traceback" not in err, f"{rc} {err}")
            (broken / "scripts" / "foundry" / "foundry_profile.py").write_text("import sys\nsys.exit(3)\n", encoding="utf-8")
            rc, err = run(broken, "Bash", command=f"rm {g}")
            expect("a profile module that exits on import does not take the hook with it", rc == 2, f"{rc} {err}")
            # a module whose load() is strict whatever it is asked (it prints and exits 2), and one from before `strict`
            head = "import sys\nfrom pathlib import Path\n\n\ndef checkout(start=None):\n    return Path(start)\n\n\n"
            for what, load in (("exits 2 whatever it is asked", "def load(start=None, strict=True):\n    print('foundry: the profile cannot be read', file=sys.stderr)\n    raise SystemExit(2)\n"),
                               ("takes no strict argument and exits 2", "def load(start=None):\n    print('foundry: the profile cannot be read', file=sys.stderr)\n    raise SystemExit(2)\n"),
                               ("takes no strict argument and raises", "def load(start=None):\n    raise ValueError('no profile')\n")):
                (broken / "scripts" / "foundry" / "foundry_profile.py").write_text(head + load, encoding="utf-8")
                rc, err = run(broken, "Edit", file_path=g)
                rc2, err2 = run(broken, "Edit", file_path="docs/ROADMAP.md")
                rc3, err3 = run(broken, "Bash", command="git status")
                expect(f"a profile module whose load() {what}: the graph is blocked by the defaults, other calls run, nothing else is printed",
                       rc == 2 and "FB1 ID:MGR-" in err and rc2 == 0 and rc3 == 0 and "Traceback" not in err + err2 + err3
                       and "foundry:" not in err + err2 + err3, f"{rc} {err} | {rc2} {err2} | {rc3} {err3}")
        st = subprocess.run([sys.executable, str(HERE / "graph_readonly.py"), "selftest"], capture_output=True, text=True)
        print(st.stdout.strip())
        expect("the hook's own selftest passes", st.returncode == 0, st.stdout)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"test_graph_readonly: {len(ok)} ok, {len(bad)} failed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
