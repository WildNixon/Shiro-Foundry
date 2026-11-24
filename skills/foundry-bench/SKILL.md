---
name: foundry-bench
description: The Foundry bench "cleared and ready". After the user types /clear in a bench session, they type /foundry-bench; the bench proves it is cleared, retitles itself "Bench <n> (waits for a badge)" and flags the manager on the clock. Use it only when the user types /foundry-bench in a session whose title starts with "Bench ". Never loaded by a manager, a founder or an employee holding a badge.
---

# Foundry bench

You are a bench session of a Foundry crew: an idle session kept open so a manager can hire it by message. The user has just cleared you. This turn does one thing: it proves the clear, marks the bench idle and flags the manager. Take no badge, edit no file, queue no job, and commit nothing.

1. **Load the app's tools in one call:** ToolSearch `select:mcp__ccd_session_mgmt__get_session,mcp__ccd_session_mgmt__get_usage,mcp__ccd_session_mgmt__set_session_title,SendMessage`. If a tool is missing, tell the user which, and stop.
2. **Who you are:** `get_session` with `"self"`. Keep its `sessionId` and `title`. The title must start with `Bench `, followed by the bench's number or letter. If it does not, say this is not a bench and stop.
3. **Prove the clear:** `get_usage` with `"self"`. Read `context.categories`. The clear is proved when there is no `Messages` category, or its `tokens` are under 30000 (this turn alone reads about 14,000; a bench after a job holds far more). Also look at your own conversation: nothing may come before the user's `/foundry-bench`. If either check fails, tell the user the bench is not cleared ("type /clear here, then /foundry-bench again") and stop. Do not message the manager.
4. **Mark it idle:** `set_session_title` with `"self"` and `Bench <n> (waits for a badge)`, exactly.
5. **Find the manager.** Read `.foundry/foundry.toml` in the checkout your working directory lies in. The roster command is `<py> <tools>/office.py roster`: `<py>` is the profile's `commands.python` (if it is empty, the interpreter `.foundry/rules.md` names, else `python`), and `<tools>` is `paths.tools` (default `scripts/foundry`) under your checkout. Run it by full path, without changing directory. Its manager line names the last appointed manager and its session id. That manager is on the clock only when the line reads UP or STALE, not OUT, and names a session. With no manager on the clock (OUT, no session, or no profile found), message no one: tell the user the bench is ready and no manager is on the clock, and stop. Between slots the line can name a retired session.
6. **Flag the manager:** `SendMessage` to that session id, with this message:
   `BENCH-READY Bench <n> session <your sessionId> cleared at <the time in the roster's header>; context Messages <tokens or 0>; titled "(waits for a badge)".`
7. **Tell the user** in one line that Bench <n> is ready and the manager has been flagged. Then stop.

A refusal at any step (a permission prompt, a hook) means stop and tell the user the exact refusal; do not try another route. When a manager later sends you a brief with a badge line, load the `foundry-employee` skill and follow the brief.
