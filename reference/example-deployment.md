# Example deployment & verification log — §10

_This file is **not** instructions. It is the record of one real deployment that this blueprint
was extracted from: what was checked against a live install, what earlier notes got wrong, and
what was still outstanding at the time of writing._

_Read it for two reasons. First, the specific numbers (fact counts, note counts, timings) give
you a sense of what a healthy year-old deployment looks like — yours will differ and that is
fine. Second, the corrections table is a catalogue of exactly the kind of claim that rots: every
row is something a previous handoff asserted confidently and that turned out to be false on
re-reading the live system. Expect this document to develop its own such rows over time, and
prefer [00-verify-your-build.md](00-verify-your-build.md) over anything asserted here._

---

## 10. Adversarial review — what was verified, and what the older notes got wrong

**Desktop-specific claims** (§0 install layout, §8a ticker requirement, delivery targets, GUI surfaces) were checked against the official Hermes Agent documentation — the desktop app guide, the scheduled-tasks docs, and the cron troubleshooting guide — not inferred from the CLI deployment. The load-bearing one, restated because it is the thing most likely to be assumed away: **cron is fired by the gateway's background ticker; a chat session does not tick the scheduler.** `deliver: local` writing to `$HERMES_ROOT/cron/output/` and `hermes cron tick` as a one-shot runner were both confirmed in the CLI on the reference machine.

Everything in §4–§8 was read from the **live** reference install at write time, not from notes. Verified: Hermes v0.20.1 / config schema v33; gateway loaded with a live PID; fact store 266 facts with `facts_fts` in sync at 266; current schema confirmed via `pragma table_info(facts)`; retrieval FTS patch confirmed still present post-update; exporter confirmed on current column names; 13 active cron jobs; vault at 263 fact notes / 13 topic hubs / 63 nightly journals; single LaunchAgent label.

Corrections applied here that contradict an earlier handoff for the same system, and the working notes behind it:

| Claim in older material | Actual, verified now |
|---|---|
| `security.tirith_fail_open: true` kept deliberately | It is **false** (fail-closed). This doc prescribes fail-closed. |
| `MEMORY.md`/`USER.md` converted to durable "pointers" | **Did not hold.** Both contain facts again; auto-flush rewrites them. §3c says so plainly. |
| `mcp_servers: {}` after the slimming pass | MCP servers are configured again on the reference machine. This doc keeps them out of the core baseline and warns about their prompt cost. |
| Nightly-review rule 5 SQL columns | Names the **legacy** schema; corrected to the current schema in §8. Still uncorrected upstream. |
| Second-profile guidance, model/port/endpoint specifics, job-search & media pipelines | Out of scope here by request; also machine-specific. Ignore entirely. |

A claim in my own first draft that **turned out to be wrong**, corrected here after checking the install tree rather than the notes:

> "The retrieval FTS patch is a local edit to a bundled file, wiped by every `hermes update`; keep a diff and re-apply."

It isn't a local edit any more. `git status` on the install tree shows `retrieval.py` byte-identical to HEAD, and the sanitization landed upstream in `cb6d6d46a` (April 2026). There is no patch to carry. §6 now says so, and gives the one-line grep to confirm it on your build. The lesson generalizes: a note saying "we patched X" ages badly, because upstream may simply adopt the fix — re-check the tree before inheriting maintenance work that no longer exists.

Latent issues on the reference deployment:
1. **Fixed while writing this.** Memory export ran at 02:00, before the 03:00 review, so the vault mirror lagged a night. Rescheduled to 03:20; verified next run `2026-08-15T03:20`, ordering now review → export → snapshot. Backup at `cron/jobs.json.bak-exportreorder-*`.
2. **Fixed while writing this.** The nightly-review prompt carried legacy SQL column names (`entities, trust, source`) on its direct-SQLite fallback path — dead on arrival against the current schema, and only reachable when the fact tool is already broken. Rewritten to the current schema with `INSERT OR IGNORE` (the `content` UNIQUE constraint does the dedup) and an explicit "don't touch facts_fts, the triggers handle it" clause. Verified: rest of the prompt byte-intact, fallback SQL dry-run on a DB copy inserts once, ignores the duplicate, and keeps `facts`/`facts_fts` counts in step. Backup at `cron/jobs.json.bak-reviewprompt-*`.
3. `updates.non_interactive_local_changes: stash` silently auto-stashes local edits to the install tree on update; five orphaned `hermes-update-autostash-*` stashes have accumulated since April. Nothing is currently broken by this, but any local modification you make there will vanish the same way.

