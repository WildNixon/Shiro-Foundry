# What a worktree, the shell and the app can and cannot do

Each line is a mistake crew sessions made more than once. The first four parts hold in every project. The last part, "Host notes", shows what a project records about its own machine: your project's are in `.foundry/rules.md`.

## Your worktree and the repo

- Give your own worktree's files by absolute path. Never `cd` to the main checkout, even to read: the shell's working directory stays there for your later commands.
- Read the main branch's files by absolute path with the Read or Grep tool, or with `git show <main>:<path>` (or `git log <main>`) from your own worktree, which shares the main checkout's object store. Never aim git at another checkout (`git -C <path>`): an isolated worktree's harness refuses it.
- Another employee's branch is already in your repo: `git log <main>..<branch>`, `git show <sha>`. Do not fetch for it.
- No push, and no fetch from a remote, unless the brief says the profile allows it.
- In an isolated worktree (a temp, or a session started with worktree isolation), run one git command per shell call, chained with nothing (`&&`, `;` or `|`). The harness refuses git chained with other tools there. Use this form from your first git command. Once a command has been refused, stop and report it; do not split that command to get it through.
- An Edit or Write to another worktree's files is refused by a hook. That refusal is the rule working: send a patch.
- Search with the Grep tool, and scope it to your own worktree's path. A recursive search from the main checkout also walks every worktree copied under it.

## The shared resource

(Skip if the profile names none.)

- You reach it only through `rq.py`, by the path your brief gives. You never open a remote shell to it yourself, and you never kill a process on it or on the host. A hung job is the manager's to stop, and each stop needs the user's word.
- Its storage is shared and can fill within hours. `rq.py status --resource` shows its health without taking a seat. Prune only what your brief lists; a refused delete goes to the manager.
- A tool your job needs may exist only on the resource, or only on the host. Your brief says which; if it does not and a command is missing, report it with `fail` rather than installing anything.
- Tooling bugs that are open now, with their workarounds, are at the end of your brief (`office.py me` prints it again).

## Files

- Read a large JSON (a manifest, a run record) by key with a script, or by `offset` and `limit`; the Read tool stops at a size limit.
- The crew office is the profile's `paths.office` in the main checkout. You read it through `office.py` (`me`, `roster`, `runs`), not by opening its files, and you cannot write it from a worktree.
- A run folder is under your own worktree's output folder. The main checkout's does not have it. Name it by absolute path.
- Open a file for writing with `encoding="utf-8", newline="\n"`, so a checked-in file keeps its line ends on any host.
- Write a script to a file with the Write tool and run it by path. Do not feed a script to an interpreter on standard input or as a long quoted one-liner: nested quotes break, and on some hosts the read hangs.
- From a script, take the time from `datetime.now().astimezone()` or `board.py stamp`, not from a shell command run by subprocess.

## The app

- A message between sessions is held until the receiver's turn ends, and the app caps cross-session sends, so keep them few and short. Put a long text in a file in your worktree and send its path.
- Address the manager by the session id `office.py me` prints, not by a title.
- `sleep` followed by a read is blocked. Run the job in the background and end your turn; its end wakes you.
- You cannot clear your own session, and you cannot start one.
- If your session's model was switched mid-job, say in the hand-in which model built which commit.

## Host notes: what a project records

**Everything below is an example.** These are lessons one project recorded for one host (Windows, with Git Bash as the shell, and a build machine reached through the queue). They show the kind of line a project keeps in `.foundry/rules.md` under a "host" heading. They bind you only if your project's rules file says them.

*Example: the interpreter.*
- "Run Python by the full path the brief prints, never bare `python` or `py`. On this host the bare name is a store alias that leaks memory at every launch, and the selftests need free memory to run: check it with the project's watcher before each selftest."
- "Never feed Python on standard input: no `python -`, and no heredoc into Python. It hangs here, and a hook refuses it. Write the script to a file, then run that file."
- "`python -c` with nested quotes breaks in this shell. Use a script file."

*Example: the shell.*
- "A Windows path that ends in a backslash inside double quotes breaks the shell tool's quoting. Use forward slashes."
- "A heredoc mangles backslashes. Write files with the Write tool."
- "Calling `date` or `bash` from a script by subprocess can reach a different shell (WSL) and give the wrong time. Use `board.py stamp`."
- "A plain `open(path, 'w')` writes CRLF here. Pass `newline='\n'`."
- "The gym's record writer writes CRLF on this host; git converts on add and warns. Commit the records as they are."

*Example: the build machine.*
- "The host has no compiler for the product. Every build, format, lint and test runs on the build machine, through the queue."
- "The repo has no remote. Never fetch or push."
- "The build machine has no size profiler. Measure a binary's size by listing its symbols sorted by size, through the queue."
- "The build machine's disk is grown only for a measured need that remains after pruning. Prune output that can be made again first; never touch sources, git data or the machine's configuration."
- "Ask the user before heavy work on this PC: other work shares it. A shift's `heavy_ok` pre-approves it for that shift."
- "After a restart, check it was a real one (the system's last boot time): a resume from fast startup looks like a restart and frees no memory."

If your project's rules file has no host section and a command fails in a way this page does not explain, report it with `office.py fail` and log it with `journal.py add --kind hole`: that is how the next line gets written.
