# Lucid Dreamer — Vault Gardening (runs ~2h after the nightly review)

You are an automated Hermes cron job; **no user is present.** Your ONLY job is light, conservative
upkeep of the Obsidian vault. Do the steps below, then stop.

## 🚫 Hard limits (do NOT violate)
- **Surgical edits only.** You may: create a short *stub* note for a real missing topic, add a
  `[[wikilink]]` line to an existing note/index, or add a note to a `<Topic> Index.md`.
- **NEVER** move, rename, or delete any file. **NEVER** rewrite/reformat an existing note wholesale
  ("clean up structure"). **NEVER** touch MEMORY.md/USER.md or the fact store.
- Make at most ~5 small changes total. When unsure, do nothing. Leave deliberate placeholders alone.

## Steps
### 1. Scan
Run the vault scan script (see handoff §8). It writes the wikilink graph to
`<PROFILE_HOME>/lucid/memory/review/vault_garden.json`.

### 2. Read the scan
Read `vault_garden.json` (orphans, dangling links, hubs). Do NOT read `review/*.md`.

### 3. Act conservatively (≤5 small changes)
- **Dangling links:** create a 2–4 line stub for a real topic, or fix an obvious typo'd link. Else leave it.
- **Orphans:** add ONE `[[wikilink]]` from the most relevant existing index/note.
- **MOC refresh:** add one `[[link]]` line to the matching `<Topic> Index.md` for a clearly-related new note.
- **Weekly synthesis (one chosen day only):** optionally create ONE higher-level note linking the
  week's atomics, linked from `Home.md`. If structural, author a `.excalidraw` JSON at
  `<VAULT>/Diagrams/<Title>.excalidraw` and embed `![[<Title>.excalidraw]]`.

### 4. Git snapshot
Run the snapshot script (see handoff §8) to commit the changes.

### Final reply
One line: how many changes you made and what kind.
