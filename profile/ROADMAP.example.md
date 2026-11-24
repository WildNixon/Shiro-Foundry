# Example roadmap to 1.0

A complete, minimal roadmap in the shapes `flow.py` and `board.py` read (the foundry-founder skill's `references/roadmap-format.md` explains each).
Copy it to `docs/ROADMAP.md`, keep the tables, and replace the rows with your own.

## Stages

| Stage | Theme | Exit (requirement IDs) | Milestones | Now |
|---|---|---|---|---|
| **R0 Usable** | One person can do the main job from start to end | APP-01–02, DATA-01 | M1, M2 | M1 done |
| **1.0 Release** | Ready for anyone | every P0 PASS; DOC-01 | M3 | — |

## Milestones

- **M1 Skeleton (lane G1):** done (G1 PASS). → APP-01.

**Lanes** (each milestone's gym lane): M1 G1, M2 G2, M3 none yet.

| Milestone | Theme | Closes | Why here |
|---|---|---|---|
| M1 | Skeleton: the app starts and shows one screen | APP-01 | First: everything else needs it |
| M2 | Store: what the user makes is kept | APP-02, DATA-01 | Needs M1. Needs D2 |
| M3 | Ship: backups, the guide, the release | DATA-02, DOC-01, REL-01 | Last. After M2 |

## Requirements and where they stand

| ID | P | Status | Where | Note |
|---|---|---|---|---|
| APP-01 | P0 | PASS | M1 | G1 graded it |
| APP-02 | P0 | Part | M2 | editing works; undo is missing |
| DATA-01 | P0 | Planned | M2 | waits on D2 |
| DATA-02 | P0 | Open | M3 | backups: no design yet |
| DOC-01 | P1 | Planned | M3 | the user guide |
| REL-01 | P0 | Decided | M3 | one stable channel (D1) |

### Count

| P | PASS | Part | Planned | Decided | Open | Total |
|---|---|---|---|---|---|---|
| **P0** | 1 | 1 | 1 | 1 | 1 | 5 |
| **P1** | 0 | 0 | 1 | 0 | 0 | 1 |
| **P2** | 0 | 0 | 0 | 0 | 0 | 0 |

## Decisions

| # | Decision | Where it stands | Owner | Needed before |
|---|---|---|---|---|
| D1 | Release channel (REL-01) | **Decided:** one stable channel | the user | — |
| D2 | Storage format (DATA-01) | Open: one file, or a folder of files | the user | M2 (DATA-01) |
