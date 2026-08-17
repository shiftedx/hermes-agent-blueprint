---
name: hermes-agent-blueprint
description: Use when setting up, hardening, or debugging a Hermes Agent deployment — autonomy and approval posture, skill-set trimming, the holographic fact store, an Obsidian vault brain, and a nightly self-review ("Lucid Dreaming") cron cycle. Also use when a Hermes cron job, memory recall, or scheduled review has silently stopped working.
tested-against: Hermes Agent v0.20.1, config schema v33 (August 2026)
---

# Hermes Agent blueprint

Stands up a Hermes Agent profile with durable memory, a browsable Obsidian brain, and an
unattended nightly review cycle — or diagnoses one that has quietly stopped working.

Everything here is version-sensitive. **Run `reference/00-verify-your-build.md` first.** It is a
short list of commands that check every assumption this blueprint makes against the build in
front of you. Do not paste config from the later files until it passes.

## Before anything else

Read `reference/00-verify-your-build.md` and run it. It takes about two minutes and it is the
difference between this blueprint being accurate and being confidently wrong about a newer
Hermes.

## Decisions the owner makes, not you

Interview them before writing files. Wrong guesses here are expensive to undo:

1. **Model and provider** — the owner runs `hermes setup` themselves. Nothing here depends on it.
2. **Persona** — `templates/SOUL.md` ships a *teaching-assistant* posture: does the real work at
   full capability, but narrates the reasoning so the human learns from watching. Swap it if
   that is not what they want. Keep it under ~1KB; it is injected every turn.
3. **Autonomy level** — `reference/02` is a deliberately **high-trust** posture: local shell,
   real filesystem, no per-command prompts for ordinary work. The ⚑ guardrails are what make
   that survivable. Tighten it for a shared or minor's machine; do not tighten it silently.
4. **What fires the schedule** — a gateway service, or an OS timer calling `hermes cron tick`.
   See §8a. Getting this wrong is the single most common silent failure.
5. **Topic taxonomy** — `scripts/lucid.config.json`'s `topics` map drives both trend detection
   and the vault graph. The shipped defaults are generic on purpose. Ten minutes matching them
   to the owner's real work is the difference between a useful memory graph and a grey blob.
6. **Where the workspace lives** — anywhere outside iCloud/Dropbox/OneDrive. Sync daemons race
   the vault's git repo and the SQLite files.

## Files, and the § numbers they contain

Cross-references throughout use `§N`. Resolve them here:

| Read | Sections | Covers |
|---|---|---|
| `reference/00-verify-your-build.md` | — | version preflight; run this first |
| `reference/01-foundation.md` | §0–§3 | variables, install, profile layout, the four identity files |
| `reference/02-autonomy-and-capability.md` | §4–§5 | approvals, guardrails, skill trimming |
| `reference/03-memory-and-vault.md` | §6–§7 | fact store schema, retrieval, the Obsidian brain |
| `reference/04-lucid-dreaming.md` | §8 | the nightly cycle, cron prompts, ⚑ §8a scheduling |
| `reference/05-operations.md` | §9 | staying alive, safe config edits, log rotation |
| `reference/06-bring-up-and-owner-handoff.md` | §11–§13 | the checklist; what to tell the human |
| `reference/example-deployment.md` | §10 | one real deployment's numbers and corrections |

`templates/` holds `SOUL.md`, `AGENTS.md`, and the two cron prompts — all with `<PLACEHOLDER>`
blanks. `scripts/` is the nightly cycle, ready to install; see `scripts/README.md`.

## Working rules

- **Verify, don't assert.** Every checkbox in §11 needs a command and its output. Most of the
  corrections in `example-deployment.md` exist because earlier notes asserted state instead of
  re-reading it — including one where "we patched X locally" was wrong because upstream had
  adopted the fix months earlier.
- **Read §8a before building any part of §8.** Cron jobs are fired by the gateway's background
  ticker. Create the whole nightly cycle without one and every job is created successfully,
  appears in the Cron pane, and never runs. There is no error message.
- **Prove the schedule with a real job.** "Task registered" and "jobs run" are different claims.
  Create a throwaway job due in two minutes, confirm output lands in `$HERMES_ROOT/cron/output/`
  and a row appears in `cron/executions.db`, then delete it.
- **Measure the prompt budget.** `hermes prompt-size` before and after skill trimming; record
  both numbers. Trimming is the highest-leverage tuning knob here.
- **Test destructive SQL on a copy of the database.** Never the live one.
