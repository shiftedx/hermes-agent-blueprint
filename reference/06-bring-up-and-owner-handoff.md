# 06. Bring-up checklist & owner handoff — §11–§13

_The definition of done. Verify each box with a command and its output, not an assertion._

---

## 11. Bring-up checklist

Work top to bottom; each step is verifiable.

- [ ] Hermes Desktop installed; `hermes --version` recorded; the `hermes` CLI is on PATH.
- [ ] Profile created; **owner** ran the wizard and chose the model. No messaging platform configured.
- [ ] `$WORKSPACE` created outside any cloud-sync folder; `scratch/`, `outputs/`, `Vault/` present.
- [ ] `$VAULT` and `$PROFILE_HOME/memories` are git repos.
- [ ] `SOUL.md` written from the §3a template with the blanks filled. Under ~1KB. `display.personality: ''`.
- [ ] `$WORKSPACE/AGENTS.md` written from §3b, including the "setup is complete" line.
- [ ] `MEMORY.md` / `USER.md` exist and are empty.
- [ ] §4 autonomy block applied. `command_allowlist` has no destructive shapes. `tirith_fail_open: false` **and** the `tirith` binary resolves on the gateway's PATH.
- [ ] Skills trimmed. `curator.prune_builtins: false`. `skills.external_dirs` points at `custom-skills/`. Verified with `hermes prompt-size` before/after; record both numbers.
- [ ] Holographic plugin enabled, **exactly one copy** on the plugin scan path. `pragma table_info(facts)` matches §6.
- [ ] FTS query sanitization confirmed present (`grep _sanitize_fts_query` per §6). No local patch needed on current builds.
- [ ] Vault scaffolded (`Home.md`, `Lucid Dreamer/Lucid Dreamer Index.md`, `Memory/{Facts,Topics}`, `Diagrams/`). `obsidian-vault` skill pointed at `$VAULT`.
- [ ] Scripts installed from `scripts/` into `$PROFILE_HOME/scripts/`; `lucid.config.json` in `$PROFILE_HOME/lucid/` with `vault_path` set and `topics` tuned to the owner; prompts in `lucid/prompts/`.
- [ ] `python lucid_common.py --paths` exits 0. Required paths all `ok`; the vault may be `absent` until Obsidian opens it.
- [ ] Each of the six entry points run once by hand, exit cleanly, and produce their expected output.
- [ ] ⚑ **`hermes cron tick` scheduled task registered and verified** (§8a via `scripts/setup-windows-scheduler.ps1`). Without this nothing below runs.
- [ ] Six lucid crons + log-rotate cron created with `--deliver local`, spaced per §8, export scheduled **after** the review.
- [ ] **Ticker proof:** create a throwaway job due in ~2 minutes, wait, and confirm output appears in `$HERMES_ROOT/cron/output/` and a row lands in `cron/executions.db`. Delete it. Do not skip this — it is the single most likely thing to be silently broken on a desktop install.
- [ ] **Live smoke test:** owner opens the desktop app and gets a reply in chat.
- [ ] **Memory smoke test:** tell it a fact, confirm a row lands in `facts`, ask for it back in a fresh session.
- [ ] **Lucid smoke test:** run `lucid_ops.py collect` by hand (should print context, no errors), then trigger the nightly review once manually and read the morning report.
- [ ] Build a 10-question fixed memory quiz from known facts; record the baseline score. Re-run it after any memory or prompt change.

---

## 12. Suggested skills for the agent doing this setup

Invoke these rather than improvising:

- **`superpowers:using-superpowers`** — first, as always; establishes skill discipline for the rest of the session.
- **`superpowers:brainstorming`** — before writing `SOUL.md`/`AGENTS.md`. The persona is a design decision about how the owner wants to be taught, not a text-generation task. Interview them.
- **`superpowers:verification-before-completion`** — mandatory for §11. Every checkbox needs a command and its output, not an assertion.
- **`superpowers:systematic-debugging`** — when the gateway won't connect, memory tools throw, or a cron is silently failing. The failure modes here (silent schema mismatch, dual plugins, unloaded service) all look like something else at first glance.
- **`obsidian-vault`** — the actual mechanism for §7; read it before scaffolding the vault so the note/wikilink conventions match what the nightly gardening job expects.
- **`hermes-agent-tools` / `agent-workflow-conventions`** — Hermes-native config, cron, and skill mechanics; prefer these over guessing CLI flags.
- **`handoff`** — when this setup is done, write the *next* handoff for the new agent's owner: what's live, what's scheduled, what to check when it breaks.
- **`superpowers:test-driven-development`** — if you write or port any lucid scripts. Fixed input → asserted output, because these run unattended at 3am and nobody reads their logs until something is already wrong.


## 13. Hand this to the owner, not just the agent

Two things the human needs to know on day one, because no config can enforce them:

1. **The agent runs with real autonomy and real filesystem access.** The guardrails in §4 make that survivable, not risk-free. Checkpoints give a 7-day undo window on file edits; the vault and memories are in git. Those are the safety net — verify they work before trusting them.
2. **The nightly report is the interface.** With no chat platform it lands in `$HERMES_ROOT/cron/output/` and as a note in the vault's `Lucid Dreamer` folder — so the habit to build is *opening Obsidian in the morning*, not waiting for a notification. If the report stops appearing, or says "healthy" every day forever, something is wrong. Silence from `preflight`/`debrief` is good; silence from the review is not.
3. **The machine has to be awake for any of it.** A closed laptop runs no nightly review. If that's the situation, move the cycle to a time the machine is reliably on (§8a).
4. **There's a YOLO toggle in the status bar that turns off approval prompts.** Know what it does before using it (§4).
