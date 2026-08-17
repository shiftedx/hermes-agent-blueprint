# 02. Autonomy & capability — §4–§5

_Approval posture, guardrails, and skill-set trimming. The ⚑ items are what make high autonomy survivable — do not drop them._

---

## 4. Permissions & autonomy posture

This mirrors the reference deployment's autonomy level exactly, as requested. It is a **high-trust, high-autonomy** configuration: local shell, real filesystem access, no per-command approval prompts for ordinary work. The guardrails that make that survivable are the ones marked ⚑ — do not drop those.

```yaml
agent:
  max_turns: 90                  # per-turn tool-call ceiling; bulk work hits this, not a policy limit
  gateway_timeout: 1800
  restart_drain_timeout: 60
  service_tier: ''
  tool_use_enforcement: auto
  environment_probe: true
  environment_hint: "<one or two sentences describing the machine and preferred tools>"
  disabled_toolsets:
    - image_gen                  # drop only if the owner actually wants image generation
  reasoning_effort: medium
  verbose: false

terminal:
  backend: local                 # host execution, NOT docker. Full real filesystem.
  cwd: <WORKSPACE>               # ⚑ scopes default work to the workspace
  timeout: 180
  persistent_shell: true
  lifetime_seconds: 300

approvals:
  mode: smart                    # ⚑ model-classified: routine acts, genuinely risky asks
  timeout: 60
  cron_mode: allow               # unattended cron jobs don't stall on approval
  mcp_reload_confirm: false
  destructive_slash_confirm: false

command_allowlist:               # ⚑ KEEP THIS MINIMAL — see below
  - script execution via heredoc
  - script execution via -e/-c flag

hooks_auto_accept: false

security:
  allow_private_urls: false      # ⚑ no LAN/localhost fetches by default
  redact_secrets: true           # ⚑ scrubs secrets from tool output/logs
  tirith_enabled: true           # ⚑ policy engine
  tirith_path: tirith
  tirith_timeout: 5
  tirith_fail_open: false        # ⚑ fail CLOSED — if the policy engine is down, block
  allow_lazy_installs: false     # ⚑ no silent package installs
  website_blocklist:
    enabled: false
    domains: []

tool_loop_guardrails:            # ⚑ the runaway-loop brake
  warnings_enabled: true
  hard_stop_enabled: true
  warn_after:      { exact_failure: 1, same_tool_failure: 3, idempotent_no_progress: 1 }
  hard_stop_after: { exact_failure: 3, same_tool_failure: 8, idempotent_no_progress: 2 }

checkpoints:                     # ⚑ file-level undo for agent edits
  enabled: true
  max_snapshots: 50
  max_total_size_mb: 500
  retention_days: 7
  auto_prune: true

code_execution: { mode: project, max_tool_calls: 50, timeout: 300 }
sessions:  { auto_prune: true, retention_days: 90, vacuum_after_prune: true }
session_reset: { at_hour: 4, idle_minutes: 1440, mode: both }
updates: { pre_update_backup: quick, backup_keep: 5, non_interactive_local_changes: stash }
timezone: <TZ>
```

### Things worth understanding, not just pasting

- **`command_allowlist` is a footgun.** It bypasses approval for matching command shapes. The reference deployment once had recursive-delete, `git push --force`, and force-branch-delete on this list; they were **removed** and only the two script-execution entries kept. Do not add destructive shapes. Anything not on this list still runs — it just goes through the approval classifier first.
- **`tirith_fail_open: false` is a deliberate change from the reference deployment's earlier state.** It used to fail *open* (allow when the policy engine is unreachable) because the engine timed out under heavy local inference load. It is now fail-**closed**. Keep it closed; if you see spurious blocks, raise `tirith_timeout` rather than opening the gate. Confirm the `tirith` binary is actually resolvable on the gateway's PATH — fail-closed with a missing binary blocks everything.
- **The guardrail counters count *failures*, not calls.** A successful call resets the same-tool counter to zero. So "hard stop after 8" means *8 consecutive failures of the same tool*, not 8 uses. Unlimited consecutive *successful* calls are fine. If you see repeated hard-stops, the tool is genuinely broken — go fix the tool, don't raise the threshold. (This exact symptom on the reference deployment was a silently-broken memory tool, §6.)
- **`agent.max_turns: 90`** is the real ceiling on bulk work in one turn. If an agent starts inventing chunking cron jobs to work around a ceiling, that's a signal something below it is failing.
- ⚑ **The desktop app has a "YOLO" toggle in the status bar that bypasses dangerous-command approval prompts for the session.** It sits on top of everything in this section: flipping it on turns `approvals.mode: smart` into no approvals at all. Nothing in config prevents that — it's a per-session UI control. Point it out to the owner explicitly rather than hoping they don't find it, and explain what it switches off. The status bar is also where approval requests appear, so it's worth a minute of orientation on day one.
- **MCP servers cost prompt budget before they do anything.** Each server's tool schemas are injected every turn. On the reference deployment two MCP servers accounted for ~12k tokens of prefill and were removed. Add MCP servers only when the owner actually uses them, and measure with `hermes prompt-size` after each addition.

---

## 5. Capability surface (skills)

```yaml
skills:
  external_dirs:
    - <PROFILE_HOME>/custom-skills   # REQUIRED — skills here are invisible without this
  template_vars: true
  inline_shell: false
  write_approval: false
  creation_nudge_interval: 15
  disabled: [ ... ]                  # see below

curator:
  enabled: true
  interval_hours: 168
  stale_after_days: 30
  archive_after_days: 90
  prune_builtins: false              # ⚑ MUST be false — see below
  backup: { enabled: true, keep: 5 }

platform_toolsets:                   # per-platform tool exposure; keep both lists identical
  cli:     [holographic_memory, memory, skills, terminal, delegation]
  discord: [holographic_memory, memory, skills, terminal, delegation]

plugins:
  enabled: [holographic]

toolsets: [hermes-cli]
```

### Skill discipline — the single highest-leverage tuning knob

Every enabled skill's index entry and every tool's schema is injected into **every request**. On the reference deployment, cutting the enabled set from ~150 to ~21 took system prompt 20.8KB→14.8KB, skills index 8.5KB→2.8KB, tool schemas 49KB→37.7KB, and live per-request tools ~72→~30 — roughly halving prefill and turning a cold one-shot from a 30s+ timeout into ~11–16s. **Do this early.** It matters more on smaller/local models but helps everywhere.

Method:
```bash
hermes --profile "$PROFILE" skills list      # canonical names
hermes prompt-size                            # measure before and after
```
The desktop app has a Skills pane for browsing and installing. Use it to *explore*; do the bulk disable via `skills.disabled` in config, because the trap below is about exact naming and the CLI list is the source of truth for those names.
Put everything you don't want into `skills.disabled` (an explicit disable list), and leave `curator.prune_builtins: false` so the list is the *sole* control.

**Three traps, all hit on the reference deployment:**

1. ⚑ **`curator.prune_builtins: true` will silently gut the skill set.** The weekly curator prunes bundled skills unused for 30 days, and the bundled-manifest then reports them "seeded" so re-sync restores nothing. The symptom is a mysteriously shrinking, stale skill list. Keep it `false`. Recovery if it already happened: `hermes --profile "$PROFILE" skills repair-official all --restore --yes`.
2. ⚑ **`skills.disabled` must use REGISTRY names from `hermes skills list`, not the directory leaf names.** They differ (a hub name like `peft-fine-tuning` vs. a dir named `peft`). Using dir names silently no-ops — a first attempt on the reference deployment left 45 skills enabled instead of 21 for exactly this reason. Verify the count afterward via the `/skill` autocomplete list or `prompt-size`.
3. **There are two upstream skill sources**: the core bundle (`hermes-agent/skills/`) and the optional set (`hermes-agent/optional-skills/`). `skills repair-official` only covers the optional set. Core-bundle skills (diagram/creative ones, e.g. excalidraw) must be copied manually into `$PROFILE_HOME/skills/`.

**Core-behavior keep-list** (adapt to the owner's actual use; this is the minimum for what this doc describes):
`obsidian-vault`, `handoff`, `hermes-agent-tools`, `agent-workflow-conventions`, plus whatever the owner genuinely uses. Disable everything else and let it grow back on demand.

Also: keep `$PROFILE_HOME/skills/.restore-backups` (or any backup dir) **out of** the skills tree — backup dirs inside it get parsed as skills and inject stray index entries.

---
