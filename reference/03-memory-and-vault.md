# 03. Memory & the vault brain — §6–§7

_The three memory layers, the fact-store schema, and the Obsidian mirror. Schema claims here are checked by [00-verify-your-build.md](00-verify-your-build.md)._

---

## 6. Memory architecture

Three layers. Understand the division or you will "fix" the wrong one.

| Layer | Storage | Role |
|---|---|---|
| Conversation | `state.db` (+ FTS) | recent context, compressed on threshold |
| Atomic facts | `memory_store.db` (SQLite, holographic plugin) | **durable long-term memory** — the real one |
| Markdown | `memories/MEMORY.md`, `USER.md` | small always-injected summary, char-capped |
| Browsable mirror | `$VAULT/Memory/**` | human-readable copy of the fact store (§7) |

The desktop app also ships a **Memory Graph** view — type `/journey` (aliases `/learning`, `/memory-graph`) in chat to see what the agent has learned. That's the fastest way for the owner to check memory is actually working, and it makes the whole system legible to a beginner in a way `sqlite3` never will. Show it to them early.

```yaml
memory:
  memory_enabled: true
  user_profile_enabled: true
  write_approval: false          # agent may write memory without asking
  memory_char_limit: 900
  user_char_limit: 500
  provider: holographic
  flush_min_turns: 6
  nudge_interval: 10

plugins:
  enabled: [holographic]
  holographic:
    auto_extract: true           # extract facts from conversation automatically
    default_trust: 0.5
    inject_on_start: true
    max_inject_facts: 15
    min_trust_inject: 0.6

context:
  engine: compressor
compression:
  enabled: true
  threshold: 0.4
  target_ratio: 0.18
  protect_last_n: 20
  protect_first_n: 3
  abort_on_summary_failure: false
```

### Current fact-store schema (verify before writing any script against it)

```sql
-- table: facts
fact_id | content | category | tags | trust_score |
retrieval_count | helpful_count | created_at | updated_at | hrr_vector
-- plus: facts_fts (external-content FTS5), entities, fact_entities, hrr_vectors, memory_banks
```

⚑ **A legacy schema exists in the wild** with columns `id / trust / source / entities`. Any script, prompt, or exporter written against the legacy names will fail — usually **silently, inside a cron job**, while the core memory looks perfectly healthy. Grep every script you inherit for bare `id`, `trust`, `source`, and `synced_sessions` before trusting it. (`synced_sessions` is a legacy-only table; the current plugin does not track sessions that way. Don't recreate it.)

**Never run more than one holographic plugin copy.** A profile-local legacy copy plus the bundled stock copy will conflict; the stock plugin's `initialize()` throws on the legacy schema, leaves its store as `None`, and every memory tool call then fails with a `NoneType` error — which then trips the tool-loop hard stop. Renaming a plugin dir in place does **not** disable it: the loader scans any subdirectory of `plugins/` containing `__init__.py`. Move it out of the tree entirely.

### Retrieval quality — now upstream, just verify it

Background worth knowing: a naive retriever passes the raw query straight to `facts_fts MATCH ?`. Two consequences — multi-word queries become implicit-AND, and **a hyphen is the FTS5 NOT operator**. Over-specified or hyphenated queries return *empty*, and the agent then confidently says "I don't know" while the fact sits in the DB. This was the single biggest recall failure on the reference deployment.

**It is fixed upstream.** `_fts_candidates` now calls `_sanitize_fts_query`, which drops FTS special characters and a stopword set and OR-joins the remaining tokens; the Jaccard + trust + HRR rerank preserves precision. Shipped in commit `cb6d6d46a` ("fix(memory/holographic): sanitize FTS5 queries for natural-language recall").

So there is **no local patch to carry and nothing for `hermes update` to wipe.** Just confirm it's present in your version:

```bash
grep -n "_sanitize_fts_query\|_FTS_STOPWORDS" \
  "$HERMES_ROOT/hermes-agent/plugins/memory/holographic/retrieval.py"
```
If those are missing, you're on a build older than April 2026 — update rather than hand-patching.

⚠️ **Related, and this one is live:** `updates.non_interactive_local_changes: stash` means `hermes update` **auto-stashes any local edit** to the install tree and moves on. Local modifications don't survive as modifications — they survive as orphaned git stashes nobody reads. If you must patch a bundled file, keep the diff *outside* the install tree and re-apply deliberately; don't assume the working file still has your change. Check for accumulated debris with `git -C "$HERMES_ROOT/hermes-agent" stash list`.

### Memory instruction tuning — counterintuitive result

When writing MEMORY.md guidance for the agent, aim for **paint-by-numbers but confident**: *"search the subject of the question; the returned facts ARE your knowledge; answer from them."* A stricter framing — "use ONLY retrieved facts, 1–3 keywords, never guess" — measurably **regressed** recall on the reference deployment (8/10 → 6/10 on a fixed quiz): the model chose synonym keywords that missed FTS, then bailed to "no info". Balanced wording recovered it. Build a small fixed quiz of known facts and re-run it after any memory change; do not tune this by feel.

### Full memory wipe (procedure, when the owner asks)

1. Stop the gateway cleanly (§9) — the gateway must not be the DB's second writer.
2. Facts: `DELETE FROM facts, entities, fact_entities, hrr_vectors;` then `INSERT INTO facts_fts(facts_fts) VALUES('rebuild');` then `VACUUM;`
3. Conversation: `DELETE FROM messages, sessions, compression_locks;` then rebuild **each** FTS table (`messages_fts`, and any trigram variant) then `VACUUM`. ⚑ `VACUUM` alone leaves the file huge — FTS5 segments retain deleted text until rebuilt. A 278MB file dropped to 124K only after the rebuilds.
4. Move `sessions/` transcripts aside; clear `$HERMES_ROOT/lucid/memory/` dreams + `review/` state; blank `MEMORY.md`/`USER.md`; clear the vault mirror dirs.
5. **Preserve:** `config.yaml`, `.env`, auth, cron store, skills, `SOUL.md` (persona ≠ memory), `.obsidian/`.
6. Back everything up first, to one timestamped dir. Restart the gateway.

---

## 7. The Obsidian vault brain

The vault is the **human-facing, linkable mirror** of the agent's mind. The SQL fact store stays authoritative; the vault is what the owner actually reads and navigates.

```
$VAULT/
  Home.md                     # top-level MOC (map of content); everything links back here
  Memory/
    Facts/                    # one note per atomic fact, generated (reference: 263 notes)
    Topics/                   # colored topic hubs, generated (reference: 13)
  Lucid Dreamer/
    Lucid Dreamer Index.md    # nightly reports prepend here
    YYYY-MM-DD.md             # nightly journals (reference: 63)
  Diagrams/                   # .excalidraw JSON authored by the agent
  references/
```

- `git init` the vault. The nightly snapshot commits agent-made changes so every night is revertible.
- The `obsidian-vault` skill is how the agent reads/writes notes and wikilinks. Point its `VAULT` variable at `$VAULT`.
- Diagrams: the agent authors `.excalidraw` JSON directly via file write; the Obsidian Excalidraw plugin renders it. No special tooling needed on the agent side.
- The fact→vault exporter (`lucid/scripts/export_facts_to_vault.py`) reads `fact_id, content, trust_score, category, tags, updated_at` and emits one note per fact with tags like `trust/<band>`, `cat/<category>`, plus topic hubs and a graph JSON. It is **read-only against the DB**, so it is safe to run while the gateway is live. Topic categories are configurable in `lucid.config.json`.
- For multi-project owners, color the graph **by project**, not by category — category coloring collapses into one blob.

---
