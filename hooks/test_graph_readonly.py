"""Tests for the graph_readonly PreToolUse hook as a project's settings run it.

    <python> test_graph_readonly.py

Takes the hook command from settings.example.json beside this file (or the project's .claude/settings.json when
installed there), fills in this interpreter, and runs it in the harness's hook shell with CLAUDE_PROJECT_DIR set
to a scratch copy that has the hook file and to one that does not:
- a missing hook file lets every call run (exit 0);
- with the file, an Edit or Write of the road graph or its edit log is blocked (exit 2), in a worktree's copy too;
- a shell command that writes either file is blocked; one that reads or commits it runs;
- the settings entry matches the edit tools and both shells;
- a project whose profile lists other files protects those instead; a profile module that cannot be imported
  leaves the defaults in force and crashes nothing;
then runs the hook's own selftest. Everything it writes is in a temp folder.
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
    tmp = Path(tempfile.mkdtemp(prefix="hook-test-"))
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
                               text=True, env={**base_env, "CLAUDE_PROJECT_DIR": str(project)}, timeout=60)
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
        # a long line is decided fast, and what the hook cannot read is refused when it names the file
        hook = with_dir / ".claude" / "hooks" / "graph_readonly.py"

        def timed(payload: str):
            t = time.monotonic()
            r = subprocess.run([sys.executable, str(hook)], input=payload.encode("utf-8"), capture_output=True, timeout=60,
                               env={**base_env, "CLAUDE_PROJECT_DIR": str(with_dir)})
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
            expect("a profile file that cannot be read leaves the defaults in force", rc == 2 and "FB1 ID:MGR-" in err, f"{rc} {err}")
            (own / ".foundry" / "foundry.toml").write_text('[hooks]\nprotect = "docs"\n', encoding="utf-8")
            rc, err = run(own, "Edit", file_path=g)
            expect("a hooks.protect that is not a list leaves the defaults in force", rc == 2, f"{rc} {err}")
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
        st = subprocess.run([sys.executable, str(HERE / "graph_readonly.py"), "selftest"], capture_output=True, text=True)
        print(st.stdout.strip())
        expect("the hook's own selftest passes", st.returncode == 0, st.stdout)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"test_graph_readonly: {len(ok)} ok, {len(bad)} failed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
