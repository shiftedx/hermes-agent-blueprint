# Hermes Agent blueprint

A complete, reusable setup for a [Hermes Agent](https://hermes-agent.nousresearch.com) that has
**durable long-term memory**, an **Obsidian vault it uses as a browsable brain**, and a nightly
self-review cycle it runs unattended — plus the autonomy and approval posture that makes running
it that way survivable.

Packaged as a skill: point an agent at `SKILL.md` and say *"set this up."*

> **Tested against Hermes Agent v0.20.1, config schema v33 (August 2026).** Everything here is
> version-sensitive. [`reference/00-verify-your-build.md`](reference/00-verify-your-build.md) is
> a two-minute preflight that checks every assumption against the build in front of you. Run it
> first.

## What you get

- **A memory that actually recalls.** The holographic fact store, its real schema, the FTS
  pitfalls that make an agent say "I don't know" while the fact sits in the database, and the
  prompt wording that measurably changes recall.
- **A brain you can read.** Every fact mirrored into an Obsidian vault as linked notes with topic
  hubs and a coloured graph, git-versioned nightly.
- **A nightly "Lucid Dreaming" cycle.** Preflight → review → memory export → git snapshot →
  vault gardening → debrief, producing a morning report. Runs without stopping the agent, and
  with hard limits so an unattended agent can't reformat your notes at 3am.
- **An autonomy posture with the guardrails spelled out.** Local shell and real filesystem
  access, with the specific settings that keep that from being reckless — and an honest account
  of which ones are load-bearing.
- **The failure modes.** Most of this repo's value is the silent ones, collected in one place.

## Quick start

```bash
git clone https://github.com/shiftedx/hermes-agent-blueprint
cd hermes-agent-blueprint
```

Then hand the directory to your agent: *"read SKILL.md and set this up."* Or, as a Claude Code
skill, drop it in `~/.claude/skills/hermes-agent-blueprint/`.

The human has exactly three jobs: install Hermes, run `hermes setup` yourself (you pick the
model), and answer the six questions in `SKILL.md` under "Decisions the owner makes, not you."

## Layout

```
SKILL.md                    thin entry point — read this first
reference/
  00-verify-your-build.md   version preflight; every version-sensitive claim, in one place
  01-foundation.md          §0–§3   variables, install, profile layout, the identity files
  02-autonomy-and-capability.md  §4–§5  approvals, guardrails, skill trimming
  03-memory-and-vault.md    §6–§7   fact store, retrieval, the Obsidian brain
  04-lucid-dreaming.md      §8      the nightly cycle ⚑ read §8a first
  05-operations.md          §9      staying alive, safe config edits, log rotation
  06-bring-up-and-owner-handoff.md  §11–§13  the checklist, and what to tell the human
templates/                  SOUL.md, AGENTS.md, and the two cron prompts — all with blanks
scripts/                    the nightly cycle, ready to install (stdlib-only Python)
```

Cross-references use `§N`; the table above maps them to files.

## The one thing that will silently not work

Hermes cron jobs are fired by the **gateway's background ticker**. A chat session — CLI or
desktop app — does not tick the scheduler. On a desktop-only install, you can create the entire
nightly cycle, watch every job appear correctly in the Cron pane, and have none of them ever run.
There is no error message; the morning report simply never arrives.

§8a covers the fix (an OS timer calling `hermes cron tick`, with a ready-made PowerShell script
for Windows) and, more importantly, how to *prove* it works — "task registered" and "jobs run"
are different claims.

## Scope and honest caveats

- **No model choices, providers, endpoints, or hardware.** The model is a swappable detail
  throughout; the owner picks it in the setup wizard.
- **Written for a desktop-app install with no chat platform.** If you run a gateway with Discord
  or Telegram attached, §8a is the only part that changes — the ticker comes free, and delivery
  targets a chat instead of a file.
- **The scripts are tested; Windows is not.** The nightly cycle was verified end to end against a
  synthetic profile — session extraction, trend detection, health check, fact export, topic hubs,
  git snapshot, graph scan, idempotent re-run. What that could not cover is Windows itself and
  `setup-windows-scheduler.ps1`, which are reasoned from documentation. Run each entry point by
  hand once before trusting the schedule, and please open an issue with what you find.
- **This will rot.** It is pinned to a Hermes version: a "we patched this file locally" note can
  be wrong because upstream adopted the fix months earlier. Prefer the verification commands
  over the prose, and send a PR when a claim goes stale.

## Contributing

Corrections against newer Hermes builds are the most useful thing you can send — especially
config keys that moved, schema changes, and anything in `00-verify-your-build.md` that no longer
holds. Please include the `hermes --version` you saw it on.

## License

MIT. See [LICENSE](LICENSE).
