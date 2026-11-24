# Hooks

Two Claude Code `PreToolUse` hooks. Each reads the tool call as JSON on stdin; exit 2 with a reason on stderr
refuses the call, exit 0 lets it run. Both are standard library Python and neither one writes anything.

## no_python_stdin.py

Refuses a shell command that feeds python its script on stdin (`python -`, `python3 - <<EOF`, `... | py -`).
In some harness shells such a python never sees the end of its input and the call hangs until it times out.
The refusal tells the agent to write the script to a file and run that. Heredoc data is not a command: a
`python -` line inside the body of `cat > f <<EOF` passes.

A project wants it when a stdin-fed python has hung there once. On a host where it runs fine, leave it out.

## graph_readonly.py

Refuses a direct write of the road graph files, in any checkout or worktree: `Edit`, `Write` and `NotebookEdit`
by path, and a shell command that names one of the files together with a form that writes (a redirect, `tee`,
`sed -i`, `rm`, `mv`, a copy onto it, the PowerShell content and item cmdlets, `git checkout` or `restore` of
it). Reading and committing pass. The manager changes the graph with `flow.py graph ...`, which takes a badge
and logs the edit; everyone else reads.

The protected files are `hooks.protect` in `.foundry/foundry.toml` (default `docs/flow/road.graph.json` and
`docs/flow/road.edits.jsonl`). The refusal names the badge prefix from the profile; `hooks.protect_reason`
replaces the whole refusal text. The hook finds `foundry_profile.py` in `$CLAUDE_PROJECT_DIR/scripts/foundry`
or in `../tools` beside itself; if it cannot import it or read the profile, the defaults stand. A shell command
is matched by file name alone, so list files whose names are their own (not `state.json`). It is best effort:
a script that opens the file itself is not seen here; `flow.py graph verify` and the hand-in check catch that.

A project wants it once it keeps a road graph and more than one agent works in the repository.

## Installing

Changing the harness's configuration is the user's own step: an agent does not edit `.claude/settings.json`,
its permissions or its hooks. The user does this, or tells an agent in plain words to do it:

1. Copy `no_python_stdin.py` and `graph_readonly.py` (either or both) to `<project>/.claude/hooks/`. Keep
   `no_python_stdin.py` beside `graph_readonly.py`: the second uses the first to read heredocs.
2. Paste the `hooks` block of `settings.example.json` into `<project>/.claude/settings.json`, keeping only the
   entries for the hooks installed, and put the Python interpreter in place of each `<python>`: a full path, or
   a name the hook shell finds on its PATH. Python 3.11 or newer.
3. Start a new session, since hooks are read at session start.

The command in the example is guarded two ways. If the hook file is missing (a worktree made before the hook
was added), every call runs. If the interpreter is missing, the hook says it is inactive and the call runs.
A bare `<python> <file>` command would exit 2 on a missing file and refuse every call.

## Tests

    <python> hooks/no_python_stdin.py selftest
    <python> hooks/graph_readonly.py selftest
    <python> hooks/test_no_python_stdin.py
    <python> hooks/test_graph_readonly.py

The two `test_` files run the command from `settings.example.json` (or from the project's own
`.claude/settings.json` when they lie in `.claude/hooks`) in the hook shell, on scratch folders in the temp
directory.
