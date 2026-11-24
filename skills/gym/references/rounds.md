# Long-running rounds: running them safely and grading them afterwards

A "round" is a multi-hour run of one or more gym lanes against a live system (for example: a nightly 7-12 h round,
or a day series of two 4.2 h legs, with 25-odd lanes launched by one orchestrator script from an operator
console). Each lane writes a series file; at the close, each lane returns a verdict word and the round gets a
verdict.

## Running a round without hurting it

**Liveness**
- "Is a round running?" is answered by a live wrapper pidfile (process liveness checked by handle plus creation
  time, so a reused pid reads as reused), then status-file content freshness (mtime < 90 s), then the log tail.
  File presence proves nothing, because files outlive dead rounds.
- On Windows, never use `os.kill(pid, 0)` as a liveness check: any signal other than CTRL terminates the target.
- When state is unknown, hold. A destructive decision (an idle-stop, a kill) needs local proof and two readings about
  60 s apart. It must not depend on a single fail-open HTTP probe: one 3 s probe that timed out killed a round at
  7%, and the same defect had earlier killed another round at 11.9 of 12 h, misattributed for 17 days.
- Log every stop with who called it and why. An unattributed stop is unrecoverable history.

**Stop files and pauses**
- Use one canonical map from lane to stop-file name. A teardown that writes `gym_l_ladder.stop` while the lane
  watches `gym_ladder.stop` never stops anything gracefully.
- Whatever writes a stop file owns deleting it after the drain. Run a preflight that lists every `*.stop` before
  launch, and have a lane that finds one say so loudly instead of exiting "done: 0 cycles".
- An operator pause gets its own flag. Never piggyback on an automated flag that another process clears (a memory
  watchdog deletes its own pause flag whenever RAM is healthy).
- Starting a round is the decision to resume, so clear any operator pause at start.
- Stagger waits poll the stop file every few seconds. One long sleep made a STOP take 19 minutes to drain.

**Timing**
- Anchor the deadline at t0, not after the launch stagger. Give each lane `hours - (stagger + grace)` so it exits
  cleanly before the wall deadline. One lane ran 18 minutes longer than advertised and blew through the next round's
  start.
- A drain is finished when the log says "round over", or when the log is quiet AND the status file is stale. Log
  silence alone is not death; supervisors print about every 15 minutes.
- Killing wedged processes flushes their buffers and refreshes the log mtime, which resets any "log quiet" clock.
- Smoke tests check lifecycle mechanics, not timing. Defects whose timescale is 15 minutes to 4 hours survive every
  smoke, so watch the first real round's timings.

**Readiness and contention**
- Refuse to launch onto a half-booted system (one launcher needed N-1 of the agent ports answering). Hold off any
  automation that stops idle services (idle-stop) for the prep window.
- Shared model slots are the main confounder. Warm only the model about to be asked, use a per-model launch lock
  (a check-then-act launcher left orphans holding about 15 GB), and give the judge a reserved slot when lanes compete
  for it. Cap prompt-cache RAM per model server.
- Print a memory line every 15 minutes (free RAM, the top RAM holders, placement) so that the cause of a pause can be
  named after the fact.
- Never deploy, restart agents or bounce models during a round. Check the deploy/cadence log first.

**Child processes on Windows**
- A process launched from a server that runs inside a kill-on-close Job dies when that server restarts.
  `DETACHED_PROCESS` does not escape a job; add `CREATE_BREAKAWAY_FROM_JOB` and warn loudly if it is refused.

**Schedule gates**
- Gates that split lanes by round length must partition the variable (red runs at >= 6.0 h, blue at < 6.0 h). Two
  independent thresholds leave a dead zone.
- An environment script that arms flags must reach scheduled launches too. A scheduled task inherits a bare
  environment.

## Archiving

- Some lanes reset their series every round; others accumulate across rounds. Record which in a per-round archive
  manifest (for example `rounds/<round>/manifest.json`: mode reset/accumulates, sha256 of each archived copy) at
  round close.
- Anything that certifies a past round reads the archive through its manifest. The live reset series no longer
  holds that round.
- Archives get pruned (a keep-last-N setting). A test that reads an old archive should fail with a named reason
  when the archive is gone, not silently.
- Archive the series of an aborted or killed round before the next launch overwrites it. File the round as
  `aborted` in the ledger rather than leaving it ungraded.

## Grading a round

Do these in order. Each step exists because skipping it once put a wrong number into the permanent ledger.

1. **Reproduce a round the ledger already grades, using your method, and require a match** before trusting the
   method on an ungraded round. A plausible error ratio of 0.399 came from the wrong null; the ledger said 1.0.
2. **Find the window.** The round's t0/t1 come from the launcher's log (first launch line, "round over" or last
   write). Segment every series on epoch `ts`.
3. **Know each lane's series mode.** For a reset lane, the whole file is the round (if it hasn't been reset again
   since). For an accumulating lane, cut it to the window; whole-file statistics span months.
4. **Read the schema from the last point or the union of keys,** not `points[0]`.
5. **Use the lane's own definitions.** Read the code for which null and which ratio the headline uses, and which
   values are already percentages.
6. **Reports are cross-checks, not the number.** HTML tiles are often last-cycle or lifetime values. Certify your
   slicing by reproducing a lifetime counter exactly, then trust the window.
7. **Look for a baseline before saying none exists.** Logs rotate (`.1` files).
8. **Respect length classes.** 4.2 h legs and 12 h nights are different instruments for any metric that learns over
   a round. Bars specified "over the final quarter of a 12 h round" are not met by a 4.2 h leg.
9. **Grade the instruments too.** Judge-warm share, LLM fail rate, pause hours, contention, starved lanes. Most
   REDs in a bad round are instrument debts, and they belong in the grade separately from product defects.
10. **Write the entry honestly.** Back up the ledger first. Correct earlier entries with a dated CORRECTION in place,
    keeping the original headline. Record standing failures (a lane that cannot pass on the current data) once, as
    standing items, instead of re-reporting them every round.

Grade the day round before the next scheduled launch: a ledger gate should refuse a launch while a completed round
is ungraded.
