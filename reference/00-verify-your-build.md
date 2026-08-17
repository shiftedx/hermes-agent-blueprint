# 00. Verify your build first

Every version-sensitive claim in this blueprint is collected here so it can rot in one place
instead of eight. **Run these before pasting config from any later file.**

Written and verified against **Hermes Agent v0.20.1, config schema v33 (August 2026)**. Newer
builds are expected to work; the checks below tell you where they don't.

Set the variables from §0 first (`HERMES_ROOT`, `PROFILE`, `PROFILE_HOME`).

## 1. Version

```bash
hermes --version
```

Same major/minor as v0.20.x → everything here applies. A newer major → work through the rest of
this file, and re-check config key names in §4 against `hermes config check` before bulk-pasting.

## 2. Fact-store schema

The exporter, the nightly-review SQL fallback, and every script assume the current column names.

```bash
sqlite3 "$PROFILE_HOME/memory_store.db" "pragma table_info(facts);"
```

Expect: `fact_id, content, category, tags, trust_score, retrieval_count, helpful_count,
created_at, updated_at, hrr_vector`.

⚑ If you see `id`, `trust`, `source`, or `entities` as columns on `facts`, you are on the
**legacy schema**. Nothing in §8 will work as written and it will fail *silently inside cron*.
Migrate to the stock plugin before continuing — see §6.

Also confirm `content` really is the unique key, because §8's `INSERT OR IGNORE` fallback depends
on the database doing the dedup:

```bash
sqlite3 "$PROFILE_HOME/memory_store.db" \
  "select sql from sqlite_master where name='facts';" | grep -i 'unique'
```

## 3. Only one holographic plugin on the scan path

Two copies conflict, the stock plugin's `initialize()` throws on the legacy schema, and every
memory tool call then fails with a `NoneType` error.

```bash
find "$HERMES_ROOT" -name "__init__.py" -path "*holographic*" -not -path "*/venv/*"
```

More than one hit → move the extra **out of the plugin tree entirely**. Renaming a directory in
place does not disable it; the loader scans any subdirectory of `plugins/` containing
`__init__.py`.

## 4. FTS query sanitization is present

Without it, multi-word queries become implicit-AND and a hyphen acts as the FTS5 NOT operator, so
ordinary questions return nothing and the agent says "I don't know" while the fact sits in the
database.

```bash
grep -n "_sanitize_fts_query\|_FTS_STOPWORDS" \
  "$HERMES_ROOT/hermes-agent/plugins/memory/holographic/retrieval.py"
```

Hits → nothing to do; it is upstream (commit `cb6d6d46a`, April 2026). No hits → you are on a
pre-April-2026 build; **update rather than hand-patching**, because of check 6 below.

## 5. `facts` and `facts_fts` are in sync

```bash
sqlite3 "$PROFILE_HOME/memory_store.db" \
  "select (select count(*) from facts), (select count(*) from facts_fts);"
```

The two numbers must match. They diverge when something has hand-edited `facts_fts` — it is an
external-content FTS5 table kept in sync by AFTER INSERT/UPDATE/DELETE triggers on `facts`.
Repair with `INSERT INTO facts_fts(facts_fts) VALUES('rebuild');`, then stop editing it.

## 6. Local edits to the install tree do not survive

```bash
grep -n "non_interactive_local_changes" "$PROFILE_HOME/config.yaml"
git -C "$HERMES_ROOT/hermes-agent" stash list
```

If the setting is `stash` (the default this blueprint prescribes), `hermes update` silently
auto-stashes any local edit to the install tree. Your modification survives only as an orphaned
stash nobody reads. Keep patches *outside* the install tree, and treat a growing stash list as
accumulated debris rather than as saved work.

## 7. Cron actually fires

The load-bearing one. Jobs are run by the gateway's background ticker (60s); a chat session —
CLI or desktop app — does **not** tick the scheduler.

```bash
hermes --profile "$PROFILE" cron tick     # should exit cleanly; no-op when nothing is due
sqlite3 "$PROFILE_HOME/cron/executions.db" \
  "select job_id, started_at, status from executions order by started_at desc limit 5;"
```

An existing deployment whose most recent execution is days old has a dead ticker, whatever the
Cron pane says. See §8a for the fix.

## 8. Scripts land where they think they do

The bundled scripts derive every path from their own file location, so placement is the whole
configuration:

```bash
python "$PROFILE_HOME/scripts/lucid_common.py" --paths
```

Exits non-zero and marks `MISSING` if anything required is absent. Run this before wiring up any
schedule.

## What to do when a check fails

Fix the environment, not this blueprint's instructions — with one exception: if check 1 shows a
much newer Hermes and a later file's config key no longer exists, trust `hermes config check`
over this text, and please open an issue so the version note gets updated.
