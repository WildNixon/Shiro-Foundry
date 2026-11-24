# G1 artifacts: Example: the answers are the medians, and beat the mean (DRAFT: a template, not yet a contract)

The builder writes this file before any code, and takes the word DRAFT out of the first line when it is ready to
be read. The grader reads it, then writes the prereg and the lane from it, and pins this file by its sha256. After
the pin, change it only by adding a dated amendment at the end; the grader pins each one again.

## What is under test

One or two sentences: the thing that ships, and where it ships. Name the command or the build, not the idea.

## The command

The one command a run starts, from the checkout's top, and what it needs to be there first. The runner sets
`GYM_RUN_DIR` to the run folder; the command writes every artifact below into that folder and nothing else
anywhere in the checkout.

    <the command>

## The artifacts

One row per file the command leaves in the run folder. The grader reads these files and no other part of the
project.

| File | Format | What it holds |
|---|---|---|
| `samples.jsonl` | one JSON object per line | `id` (text), `values` (a list of numbers), `answer` (a number) |

## What a unit is

What is drawn independently, and how many a run makes. Say what would make two rows the same unit.

## What the builder does not promise

What the artifacts leave out, what may differ between hosts, what is known to be rough.

## How to see it fail

One way to break the thing on purpose, so the grader can check that its lane sees the break.

## Amendments

None yet. Each one: the date and time, who wrote it, whether counted data existed, what changed and why.
