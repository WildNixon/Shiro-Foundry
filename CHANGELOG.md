# Changelog

## 0.1.0 (2026-11-24)

The first general release: the crew routine of one long-running project, made project-neutral.

### Skills

- `foundry-founder` (new as a skill): founding a project, the roadmap audit, push planning, the decision register, the profile. It replaces an earlier draft that was a level inside the manager skill and knew only a dashboard tool; it now covers the road graph, plan charts, the journal, the resource queue and the hooks.
- `foundry-manager`, `foundry-employee`, `foundry-flow`, `foundry-bench`: converted from the project's own skills. Every rule and its reason kept; project facts moved to the profile and the rules file; how the desktop app behaves and how to merge gathered into their own references.
- `gym`: the measure skill, with one project's private machinery removed and a section on how a Foundry project uses it.

### Tools

- `foundry_profile.py` (new): one profile file, `.foundry/foundry.toml`, read by every tool; defaults for everything; environment overrides for tests.
- `office.py` (was the project's crew office): the founder's badge (`found`), `--rq`/`--seat` for the shared resource, a profile-driven hand-in check, no project paths.
- `rq.py` (was a VM queue): a queue for the seats of any shared resource, with `prepare`, `exclusive` and `status` hooks from the profile.
- `board.py` (was the progress map): profile-driven paths and roadmap shapes, `init`, the `decide` register, a page that builds with inputs missing.
- `journal.py`, `flow.py`, `flow_graph.py`, `flow_page.py`, `plan_flow.py`, `lanes_for.py`: ported; crew names, badge prefix, paths and id shapes from the profile.
- `founder.py` (new): `init`, `doctor`, `audit`, `push new`.
- `install.py` (new): copies tools, templates, skills and (on request) hooks into a project; never overwrites without `--force`.

### Not carried over

The source project's own wrappers and readers: its VM command wrapper, its sweep scripts, its system-graph and kernel-plan readers, and host watchdogs. `docs/HOLES.md` says what a project must supply in their place.
