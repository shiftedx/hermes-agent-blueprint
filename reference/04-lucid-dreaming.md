# 04. The Lucid Dreaming protocol — §8

_The nightly cycle. **Read §8a before building anything else in this file** — without a ticker, every job below is created successfully and never runs._

---

## 8. The Lucid Dreaming protocol

**What it is:** a nightly, mostly-unattended cycle where the agent reviews the day's sessions, promotes durable facts into long-term memory, tends the vault, and delivers a morning report to the owner. "Dreaming" = offline consolidation while nobody's talking to it.

**Design rule that matters:** every step runs **without stopping the gateway.** Earlier designs stopped the service to get exclusive DB access; that caused downtime and missed messages. All scripts here are either read-only against live DBs or operate on files.

### 8a. ⚑ First: something has to fire the schedule

**On a desktop-only install, nothing does by default.** Cron jobs are fired by the gateway's background ticker thread, which ticks every 60 seconds. The desktop app runs its own local backend, but a chat session — CLI or app — does **not** tick the scheduler. If you skip this step, every job below is created successfully, shows up in the Cron pane, and never runs. There is no error message; the review just never arrives.

**Use the OS scheduler to call `hermes cron tick`.** No gateway, no long-running process. `hermes cron tick` runs any due jobs once and exits — exactly the shape a scheduled task wants. It survives the app being closed, has fewer moving parts than a gateway, and doesn't depend on gateway-without-platforms behaving.

A ready-made setup script ships in `scripts/setup-windows-scheduler.ps1`:
```powershell
.\setup-windows-scheduler.ps1 -Profile <profile>
```
It locates `hermes.exe`, **runs one tick to prove the command works before scheduling anything**, then registers a hidden task repeating every minute indefinitely. A lock file at `$HERMES_ROOT/cron/.tick.lock` stops overlapping ticks from double-running a batch, so a one-minute interval is safe.

On macOS the equivalent is a launchd agent with `StartInterval 60`; on Linux, a systemd timer. Same command either way:
```bash
hermes --profile "$PROFILE" cron tick    # no-op when nothing is due
```

⚑ **Verify with a real job, not with task status.** "Task registered" and "jobs actually run" are different claims. Create a throwaway job due in ~2 minutes, wait for it, confirm output appears in `$HERMES_ROOT/cron/output/` and a row lands in `cron/executions.db`, then delete it. Everything downstream depends on this working, and it fails silently when it doesn't.

**The alternative, for reference.** A headless gateway (`hermes gateway install` + `start`) also ticks the scheduler and gives you `gateway status` as a health check, at the cost of a supervised long-running process and the log-rotation gap in §9. If you ever switch to it, verify it genuinely stays up with zero platforms configured rather than assuming — a gateway with nothing to connect to exiting on startup is a plausible failure worth ruling out on the real machine.

**Machine availability.** This is written for a desktop that stays powered on, so 03:00 is fine. If the target ever becomes a laptop that sleeps overnight, move the whole cycle to a reliably-awake hour — the protocol cares about the *order* of the steps, not the time of day.

### The cycle (times are examples — space them, keep the order)

| Time | Job | Agent? | Runs | Does |
|---|---|---|---|---|
| 02:45 | `lucid-pre-flight` | no | `lucid_ops.py preflight` | Extract recent sessions + trends. Prints **only if unhealthy** (silence = good). |
| 03:00 | `lucid-nightly-review` | **yes** | `lucid_collect.sh` → agent prompt | The dream. Reviews, promotes facts, returns the **morning report**. |
| 03:20 | `lucid-memory-export` | no | export facts → vault, then snapshot | Mirrors the fact store into `Vault/Memory/**` and commits. |
| 03:30 | `lucid-git-snapshot` | no | `snapshot.py` | Git-commits vault + memories. |
| 05:00 | `lucid-vault-gardening` | **yes** | `vault_garden.py` → agent prompt | Conservative vault upkeep (≤5 small edits). |
| 18:00 | `lucid-session-debrief` | no | `lucid_ops.py debrief` | Same as preflight, for the day's sessions. |
| 04:15 | `gateway-log-rotate` | no | rotate script | See §9 — not lucid, but same unattended family. |

⚑ **Ordering is load-bearing: the export must run *after* the review.** The export mirrors the fact store to the vault, so if it runs first, the vault reflects yesterday's facts and the owner reads a mirror that is permanently one night stale. The reference deployment had exactly this bug (export at 02:00, review at 03:00) and it has now been corrected to 03:20.

Pick the gap from measured runtime, not habit. On the reference deployment the agent review completes in 15s–2m15s across the last week, so a 20-minute gap is ~10× the worst observed run and still lands before the 03:30 snapshot. Check yours:
```bash
sqlite3 "$PROFILE_HOME/cron/executions.db" \
  "select started_at, finished_at, status from executions where job_id='<review-job-id>' order by started_at desc limit 7;"
```

### The pieces

**`scripts/lucid_ops.py`** — one script, three modes (`preflight` | `debrief` | `collect`). It gathers DB stats, note stats, and trend data, computes a health verdict, and:
- preflight/debrief: print to stdout **only when there are issues** (quiet by default — noise trains the owner to ignore it),
- collect: print a compact context block for the LLM review.

It writes `lucid-health.json` and `trends.json` under `$HERMES_ROOT/lucid/memory/review/`.

**Two-stage cron pattern (the important structural idea):** each agent-run job is `script` **+** `prompt`. The deterministic script runs first and its stdout becomes the authoritative context for the agent step. The agent doesn't go hunting; it reasons over a fixed, cheap, reproducible input. Use this pattern for anything unattended.

**Nightly review prompt** (adapt; `<...>` are your paths):

```
You are <AGENT> running <OWNER>'s Lucid Dreamer nightly memory review. The script output above
is the authoritative context. Keep this run bounded and practical.

Environment:
- Profile home: <PROFILE_HOME>
- LUCID_HOME: <HERMES_ROOT>/lucid
- Human timezone: <TZ>
- Delivery: local file (no chat platform). Your final response is written to
  <HERMES_ROOT>/cron/output/. ALSO write the finished morning report to
  <VAULT>/Lucid Dreamer/<today>.md and add a link line to
  <VAULT>/Lucid Dreamer/Lucid Dreamer Index.md so it is readable in Obsidian.
- Fact store: <PROFILE_HOME>/memory_store.db
- Daily notes: <HERMES_ROOT>/lucid/memory/YYYY-MM-DD.md
- Review status: <HERMES_ROOT>/lucid/memory/review/lucid-health.json

Rules:
1. Do NOT read prior review markdown files; avoid circular self-grounding.
2. Use the script output first. Only inspect files/DB if needed to resolve a clear issue.
3. Keep under 5 tool calls unless something is genuinely broken.
4. Safe auto-apply only: high-confidence infrastructure facts, explicit user corrections, stable
   project conventions. NEVER auto-apply opinions, strategy, or sensitive personal facts.
5. If updating memory and the fact_store tool is unavailable, direct SQLite writes are allowed:
   `INSERT OR IGNORE INTO facts(content, category, tags, trust_score) VALUES (?, ?, ?, ?)`.
   `content` is UNIQUE and created_at/updated_at default automatically, so duplicates are rejected by
   the schema. AFTER-INSERT triggers keep facts_fts in sync — never hand-edit facts_fts. Facts written
   this way have no hrr_vector; that is fine, retrieval still finds them via FTS + Jaccard. Afterward
   verify `select count(*) from facts` equals `select count(*) from facts_fts`.
6. If MEMORY.md/USER.md are near cap, compact instead of appending. Do not bloat memory.
7. Final response must be the morning report: Health, Trends, Memory Actions Taken,
   Suggested Follow-ups, Approval Needed. Be concise.

Now perform the nightly review and return the morning report.
```

⚑ **Rule 5 is the one to get right, and it needs more than correct column names.** It only fires when the fact tool is broken — i.e. exactly when you need the fallback to work, which is also when nobody is awake to notice it failed. Three things make it correct:

- **Current column names.** A legacy schema (`entities`, `trust`, `source`) exists in the wild; writing against it fails outright. Check yours with `pragma table_info(facts)` before shipping.
- **`INSERT OR IGNORE`, not a read-then-write duplicate check.** `content` is `NOT NULL UNIQUE`, so the database already enforces dedup; a plain `INSERT` of an existing fact *raises*, and an agent that hits that mid-run tends to start improvising. Let the constraint do the work.
- **Do not touch `facts_fts`.** It is an external-content FTS5 table with AFTER INSERT/UPDATE/DELETE triggers on `facts`; it stays in sync by itself. Hand-editing it corrupts the index. The count check afterward is a sanity check, not a repair step.

Facts written this way have a NULL `hrr_vector`. That is harmless — vector similarity falls back to neutral and the fact is still retrievable via FTS + Jaccard. Say so in the prompt, or the agent will "fix" a non-problem.

Verify the whole fallback on a **copy** of the DB before trusting it, never on the live one:
```bash
cp memory_store.db /tmp/fb_test.db
sqlite3 /tmp/fb_test.db "insert or ignore into facts(content,category,tags,trust_score)
  values ('smoke test','infra','test',0.9);
  select (select count(*) from facts), (select count(*) from facts_fts);"
```
Counts must move together, and a second identical insert must be a no-op.

Rule 1 is not optional either: letting the review read its own prior reviews produces confident, compounding drift.

**Vault gardening prompt** — the value here is the hard limits, so keep them verbatim in spirit:

- Surgical edits only. Allowed: create a short *stub* note for a genuinely missing topic; add one `[[wikilink]]` to an existing note or index; add a note to a `<Topic> Index.md`.
- **NEVER** move, rename, or delete a file. **NEVER** rewrite or reformat an existing note wholesale. **NEVER** touch `MEMORY.md`/`USER.md` or the fact store.
- **≤5 small changes total.** When unsure, do nothing. Leave deliberate placeholders alone.
- Read only the machine-readable `review/vault_garden.json` (orphans / dangling links / hubs), never the prior `review/*.md`.
- Weekly (one chosen day) it may create *one* higher-level synthesis note linking the week's atomics, linked from `Home.md`, optionally with an `.excalidraw` diagram.
- End with one line summarizing what changed, then git-snapshot.

An unbounded "clean up the vault" agent will reformat everything it touches and you will lose work. The ≤5-changes ceiling is the whole safety design.

**`lucid.config.json`** — tunables read by the scripts: `agent_name`, `timezone`, `vault_path` (**the only value you must set**), `vault_journal_subdir`, `confidence_auto_apply`, `lookback_days_extract` / `lookback_days_review`, `trend_window_days`, char limits, `per_session_char_cap`, `exclude_session_id_substrings` (⚑ keep the `lucid` entry, or the agent dreams about dreaming), `session_exclude_patterns`, plus the `topics` keyword map and the `topic_colors` / `category_colors` / `project_colors` maps that drive the vault graph.

⚑ **Tune `topics` to what the owner actually does.** It drives both trend detection and the vault's topic clusters. The shipped defaults are deliberately generic (errors, learning, coding, infrastructure…); leave them and the graph stays vague. Ten minutes here is the difference between a memory graph that clusters meaningfully and one that dumps everything into "General".

### The scripts are included

`scripts/` in this package holds working, generalized versions of everything above — no authoring required. They are stdlib-only Python, `pathlib` throughout, no bash, and they **auto-detect every path from their own file location**, so the same files run unchanged on Windows, macOS and Linux. `git` on PATH is the only external dependency.

Install: copy every `.py` into `$PROFILE_HOME/scripts/` (they import each other as siblings, so keep them together), put `lucid.config.json` in `$PROFILE_HOME/lucid/`, and the two prompts in `$PROFILE_HOME/lucid/prompts/`. Then confirm placement before wiring anything:
```
python lucid_common.py --paths   # prints every resolved path; exits non-zero if one is missing
```
Six no-argument entry points map to the six cron jobs: `lucid_preflight.py`, `lucid_collect.py`, `lucid_memory_export.py`, `lucid_snapshot.py`, `lucid_garden.py`, `lucid_debrief.py`. See `scripts/README.md` for the full inventory and safety properties.

They were tested end to end against a synthetic profile — session extraction, trend detection, health check, fact export, topic hubs, git snapshot, graph scan, and an idempotent re-run. What that testing could **not** cover is Windows itself and the PowerShell scheduler script; run them once by hand before trusting the schedule.

**Cron management:**
```bash
hermes --profile "$PROFILE" cron list
hermes --profile "$PROFILE" cron remove <id>       # aliases: rm, delete
```
Create every job with `--deliver local` (output → `$HERMES_ROOT/cron/output/`). `origin` delivers to the chat that created the job, which is wrong for unattended work; the platform targets don't exist here.

Reschedule an existing job (no gateway restart needed — the CLI owns the lock; back up `cron/jobs.json` first):
```bash
hermes --profile "$PROFILE" cron edit <job_id> --schedule "20 3 * * *"
```

The desktop **Cron pane** shows these jobs and their status. It is a good read-only health check — if a job's last run is days stale, your ticker (§8a) is dead. Prefer the CLI for edits; the prompt text of an agent job is long and multi-line and the CLI round-trips it faithfully.

⚑ Audit `cron list` periodically. Agents create their own cron jobs to work around problems — the reference deployment had one the agent invented to chunk a bulk load around a guardrail. Remove those and fix the underlying cause. Also make sure every job inherits the main model (leave model/provider/base_url null) so a model swap doesn't require touching a dozen jobs.

---
