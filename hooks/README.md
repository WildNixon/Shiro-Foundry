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
it), or that replaces the files through their folder without naming them (below). Reading and committing pass.
The manager changes the graph with `flow.py graph ...`, which takes a badge and logs the edit; everyone else
reads.

The protected files follow the profile. When `.foundry/foundry.toml` sets `hooks.protect`, they are that list.
When it does not, they are `road.graph.json` and `road.edits.jsonl` under `paths.flow` (default `docs/flow`), so
a project that moves `paths.flow` moves the protection with it. The refusal names the badge prefix from the
profile; `hooks.protect_reason` replaces the whole refusal text.

The hook reads `paths.tools` out of `$CLAUDE_PROJECT_DIR/.foundry/foundry.toml` itself and looks for
`foundry_profile.py` there, then in `$CLAUDE_PROJECT_DIR/scripts/foundry`, then in `../tools` beside itself.
With the module it reads the profile in force; without it, it goes by the toml file alone; if neither can be
read, the built-in defaults stand. It never asks git for anything and never crashes a tool call: the profile
is loaded with `load(start, strict=False)` (by `load(start)` on a module from before that argument), and a
load that exits or raises, with whatever it printed, is dropped in favour of the toml file alone.

How a path is matched (`Edit`, `Write`, `NotebookEdit`, and a path in a shell command). The path is read as
the file system would read it, from its text alone and without regard to case: `\` is `/`, `.` and `..` are
resolved, and in each part trailing dots and spaces and an NTFS stream suffix are dropped. So
`docs/progress/../flow/road.graph.json`, `docs/flow/./road.graph.json`, `road.graph.json.` and
`road.graph.json::$DATA` are all the graph. The hook never touches the disk, so a name only the disk can
resolve is not seen (see the list below).

How a shell command is matched to a protected file:

- A bare name that is distinctive is matched wherever it stands. Distinctive means two or more dots
  (`road.graph.json`) or 16 characters or more. `cd docs/flow && rm road.graph.json` is refused.
- Any other name (`state.json`, `config.toml`) is matched by its path tail, the last two path parts
  (`progress/state.json`). A command that writes some other `state.json` runs. The price: `cd docs/progress &&
  rm state.json` is not seen, so prefer a distinctive name for a file that matters.
- A file at the top of the repository has only its name, and is matched by it.

`Edit`, `Write` and `NotebookEdit` are always matched by the whole path.

What counts as a write of a named file. The line is cut into commands (`;`, `&&`, `||`, a new line) and each
command into the stages of its pipe; a writer counts only in the stage that names the file:

- A redirect onto the file, anywhere on the line.
- A writer word in the same stage as the file: `tee`, `rm`, `mv`, `del`, `erase`, `ren`, `rename`, `move`,
  `truncate`, `shred`, `unlink`, `dd`, `install`, `patch`, `touch`, `Set-Content`, `Add-Content`,
  `Clear-Content`, `Out-File`, `Remove-Item`, `Move-Item`, `Rename-Item`, `New-Item` and their aliases; `sed`
  or `perl` in place (`-i`, `-i.bak`, `-pi.bak`, `--in-place`). So `cat a | tee <file>` is refused and
  `cat <file> | tee /tmp/copy.json`, `git diff <file> | tee x` and `Get-Content <file> | Set-Content
  C:/tmp/copy.json` run. A stage that takes its arguments from the pipe is a write when an earlier stage
  named the file: `ls <file> | xargs rm`, `Get-Item <file> | Remove-Item`.
- A copy with the file as any plain argument but the first, or after `-Destination` or `-t`, whatever follows
  it (`cp x <file> 2>/dev/null`, `Copy-Item x <file> -Force`, `copy x <file> /Y`). Copying the file away runs.
- `git checkout`, `restore`, `clean`, `stash`, `rm`, `mv` and `apply` with the file as an argument, behind any
  of git's own options (`--no-pager`, `-c k=v`, `--git-dir=`, `--work-tree=`, `-C x`). The forms that touch
  the index alone run: `git reset <file>`, `git restore --staged <file>`, `git rm --cached <file>`. So do
  `git add`, `commit`, `diff`, `log`, `show`.
- A quoted text with a space is prose, not a command, and is dropped before all of this: a commit message, on
  one line or many (`git commit -m "..."`), an `echo`. `\"` inside double quotes does not end them. Two kinds
  of quoted text are kept and read: a path with a space into a protected file or folder, and the command
  handed to a shell (`bash -c "..."`, `sh -c '...'`, `powershell -Command "..."`, `cmd /c "..."`, `eval
  "..."`, `Invoke-Expression "..."`), which is read as a command line of its own.

The folder a protected file lies in (`docs/flow`; a file at the top of the repository has none) is a target of
its own, because a command can replace the file through it without naming the file. These forms are refused
when an argument is the folder, however spelled, or a wildcard that can match a protected file or its folder
(`docs/flow/*`, `docs/flow/*.json`, `docs/fl*`). A wildcard that can match none of the protected names is not
a target: `docs/flow/*.md`, and for git `'*.py'`, `'*.md'`, `docs/*.md`.

- `rm`, `rmdir`, `rd`, `del`, `erase`, `unlink`, `shred`, `mv`, `move`, `ren`, `rename`, `Remove-Item`,
  `Move-Item`, `Rename-Item` and their aliases, also behind `sudo`, `env`, `xargs` or `then`, and also when
  an earlier command of the same pipe named the folder (`ls docs/flow | xargs rm`).
- A copy whose destination is the folder: `cp`, `copy`, `Copy-Item`, `xcopy`, `robocopy`, `rsync`, `install`
  with the folder as any plain argument but the first, or after `-Destination` or `-t`. Any file copied into
  the folder is refused, not only one named like the graph. Copying the folder away passes.
- `find` on the folder with `-delete`, or with `-exec` of one of the removers.
- `git checkout`, `restore`, `clean`, `stash`, `rm` and `mv` with a pathspec that is the folder, or that
  covers it from above (`.`, `:/`, `docs`), or a wildcard that can match a protected file as git reads it
  (`'*'`, `'*.json'`, `'docs/*'`). So `git checkout .`, `git restore .`, `git clean -fdx .` and `git stash push
  -- docs` are refused in a project that has this hook, in every checkout. An option's value is not a
  pathspec (`git stash push -m docs`, `git restore -s docs x`), and `git stash save` takes only a message.
  `git checkout <one word>` with no `--` runs when the word is the folder or a folder above it, since it may
  be a branch of that name (see below); with `.`, a wildcard or the file's own name it is refused. The forms
  that touch the index alone run: `git reset` with any pathspec, `git restore --staged`, `git rm --cached`.
  So do `git stash list`, `show`, `pop`, `apply` and `drop`.
- After `cd`, `pushd` or `Set-Location` into the folder in the same command, or `git -C` on it, `.` is the
  folder and a bare wildcard is read there: `cd docs/flow && rm *`, `cd docs/flow && rm *.json`,
  `cd docs/flow && cp /tmp/road.graph.json .`. `cd docs/flow && rm *.md` runs.

`ls docs/flow`, `git status`, `git add docs/flow`, `git diff -- docs/flow`, `git log -- docs/flow`,
`cp -r docs/flow /tmp/x`, `grep -r rm docs/flow` and `tar czf x.tgz docs/flow` pass.

### What it cannot see

The hook reads the text of one tool call and nothing else. It does not see:

- A Windows 8.3 short name (`ROADGR~1.JSO`, `docs\FLOW~1`), a symbolic link, a junction, a hard link, a
  `subst` or mapped drive, or any other second name of the file or its folder. Only the disk can say what
  such a name is, and the hook never asks it. This cannot be closed here.
- `git checkout docs/flow` (one word, no `--`) when no branch has that name: git then restores the folder
  from the index, which discards changes that are not staged. Only the disk can say whether it is a branch.
- A name the shell builds: a variable (`f=road.graph.json; rm docs/flow/$f`), a command substitution that
  prints the name, a backslash escape inside the name (`road\.graph.json`), an encoded command (`powershell
  -EncodedCommand`, `base64 -d | sh`).
- A wildcard or a name broken up by quotes (`rm -rf docs/fl*`, `road.gra"ph".json`) in a command that writes
  out neither the file's name, nor a part of its folder's path (`docs`, `flow`), nor `git`: `rm -rf d*/f*`,
  or `cd docs/flow` in an earlier call and then `rm road.gra"ph".json`. With one of those words on the line
  both are seen.
- A command inside a quoted text that is not handed to a shell by name: a substitution in a message or an
  echo (`git commit -m "$(rm docs/flow/road.graph.json)"`, `echo "$(rm -rf docs/flow) done"`), a text piped
  to a shell (`echo 'rm -rf docs/flow' | bash`), a shell named through a variable (`$SHELL -c "..."`), a
  command run on another host or in another program (`ssh host "..."`, `python -c "..."`, `node -e "..."`).
- A folder above the protected one in a command other than git: `rm -rf docs`, `mv docs elsewhere`,
  `Remove-Item -Recurse .`, `rm -rf *` at the top of the checkout.
- A folder reached step by step or in an earlier tool call: `cd docs && rm -rf flow`, or `cd docs/flow` in
  one call and `rm *` in the next (the shell keeps its working directory; the hook keeps nothing). For a
  generic file name this also holds for the file: `cd docs/progress && rm state.json`.
- A git command that names no path and moves the whole tree: `git stash`, `git stash pop`,
  `git reset --hard`, `git checkout <branch>`, `git switch`, `git merge`, `git pull`, `git rebase`,
  `git cherry-pick`, `git revert`, `git clean -fd`, `git apply <patch>`, `git am`, `git worktree remove`.
  Refusing those would stop ordinary work in every worktree. Apart from `apply` and `am`, they move committed
  or stashed content, which is the manager's own or shows at hand-in.
- A program that opens the file itself: a script (`python fix.py`, `bash fix.sh`), an editor, an archive
  unpacked into the folder (`tar -x -C docs/flow`, `unzip -d`, `Expand-Archive`), a link made over the file
  (`ln -sf`), and any other command that is not one of the writers named above.
- A tool the settings entry does not match: an MCP file tool, or a subagent in a harness that does not run
  hooks for it.

What gets past the hook is caught afterwards: `flow.py graph verify` fails when the graph is not what the
signed edit log left, the model flags it (`WARN TAMPERED`), and the hand-in check sends back a crew branch that
changes either file.

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
