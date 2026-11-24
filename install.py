#!/usr/bin/env python3
"""Install Shiro Foundry into a project.

    python install.py --project DIR [--skills project|user|none] [--tools-dir scripts/foundry] [--hooks]
                      [--force] [--dry-run]
    python install.py --check --project DIR      what an install would change; writes nothing (same as --dry-run)

Copies:
  tools/*.py and the templates      -> DIR/<tools-dir>/           (default scripts/foundry; templates/ beside them)
  skills/*                          -> DIR/.claude/skills/        (--skills project, the default)
                                       or ~/.claude/skills/       (--skills user: one copy for every project)
  hooks/*.py                        -> DIR/.claude/hooks/         (only with --hooks; it never edits settings.json:
                                                                   hooks/settings.example.json shows the block to add,
                                                                   and adding it is the user's own step)

A file that exists and differs is kept and listed, unless --force (then the old one is saved beside it as
<name>.bak-<date>). Nothing outside DIR (or ~/.claude/skills with --skills user) is touched, nothing is deleted,
and git is never run. Afterwards: `python DIR/<tools-dir>/founder.py init`, then `founder.py doctor`.
Standard library only; Python 3.11 or newer.
"""

import argparse
import datetime as dt
import filecmp
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def plan(args):
    project = Path(args.project).resolve()
    tools = project / args.tools_dir
    steps = []  # (src, dst)
    for f in sorted((HERE / "tools").glob("*.py")):
        steps.append((f, tools / f.name))
    for f in sorted((HERE / "profile").glob("*")):
        if f.is_file():
            steps.append((f, tools / "templates" / f.name))
    if args.skills != "none":
        base = (project / ".claude" / "skills") if args.skills == "project" else (Path.home() / ".claude" / "skills")
        for f in sorted((HERE / "skills").rglob("*")):
            if f.is_file() and "__pycache__" not in f.parts:
                steps.append((f, base / f.relative_to(HERE / "skills")))
    if args.hooks:
        for f in sorted((HERE / "hooks").glob("*.py")):
            if not f.name.startswith("test_"):
                steps.append((f, project / ".claude" / "hooks" / f.name))
    return project, steps


def main(argv):
    ap = argparse.ArgumentParser(description="Install Shiro Foundry into a project.")
    ap.add_argument("--project", required=True, help="the project's main checkout")
    ap.add_argument("--skills", choices=("project", "user", "none"), default="project")
    ap.add_argument("--tools-dir", default="scripts/foundry")
    ap.add_argument("--hooks", action="store_true", help="also copy the hooks into .claude/hooks (settings.json is yours to edit)")
    ap.add_argument("--force", action="store_true", help="replace files that differ (the old one is kept as .bak-<date>)")
    ap.add_argument("--dry-run", "--check", dest="dry", action="store_true")
    args = ap.parse_args(argv[1:])
    if sys.version_info < (3, 11):
        print("refused: Python 3.11 or newer is needed (the tools read TOML with tomllib)")
        return 2
    project, steps = plan(args)
    if not project.is_dir():
        print(f"refused: {project} is not a folder")
        return 2
    if project == HERE:
        print("refused: --project is the Shiro Foundry repository itself")
        return 2
    new = same = kept = replaced = 0
    tag = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    for src, dst in steps:
        if not dst.exists():
            new += 1
            print(f"{'would write' if args.dry else 'wrote':<12}{dst}")
            if not args.dry:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
        elif filecmp.cmp(src, dst, shallow=False):
            same += 1
        elif args.force:
            replaced += 1
            print(f"{'would replace' if args.dry else 'replaced':<12}{dst}")
            if not args.dry:
                shutil.copy2(dst, dst.with_name(dst.name + f".bak-{tag}"))
                shutil.copy2(src, dst)
        else:
            kept += 1
            print(f"{'kept':<12}{dst} (it differs; --force replaces it and keeps a .bak)")
    print(f"\n{'dry run: ' if args.dry else ''}{new} new, {replaced} replaced, {same} already current, {kept} kept as they were")
    if args.tools_dir.replace("\\", "/").strip("/") != "scripts/foundry":
        print(f'Set `tools = "{args.tools_dir}"` under [paths] in {project / ".foundry" / "foundry.toml"}: briefs print that path.')
    if args.hooks:
        print(f"Hooks copied. To switch them on, add the block from {HERE / 'hooks' / 'settings.example.json'} to "
              f"{project / '.claude' / 'settings.json'} yourself.")
    if not args.dry:
        t = project / args.tools_dir / "founder.py"
        print(f'\nNext:\n  python "{t}" init --project "<name>"\n  python "{t}" doctor')
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
