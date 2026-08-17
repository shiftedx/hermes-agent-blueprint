# Lucid Dreamer scripts

Stdlib-only Python. No pip installs. Works on Windows, macOS and Linux — every path is
built with `pathlib` and every subprocess uses `sys.executable`, so there are no bash
assumptions. The only external binary needed is `git` (for the nightly snapshot), which
must be on PATH.

## Install

Copy **all** `.py` files into your profile's scripts directory, and the config one level
over into `lucid/`:

```
<HERMES_ROOT>/profiles/<profile>/
  scripts/            <- every .py file here, together
  lucid/
    lucid.config.json <- lucid.config.json, with the placeholders filled in
    prompts/          <- nightly-review.md and gardening.md from ../templates/prompts/
```

They must stay in one directory — they import `lucid_common` as a sibling.

Then edit `lucid.config.json`. The only value you **must** set is `vault_path`.
`agent_name`, `timezone`, `topics` and the colour maps are worth tuning; everything else
has a working default.

## Confirm it landed correctly

```
python lucid_common.py --paths
```

Prints every path it resolved and whether it exists. If `fact store`, `sessions` or
`config` show `exists=False`, the scripts are in the wrong directory — fix that before
going further. `plugin dir exists=False` means the holographic memory plugin isn't where
expected, which the health check will also flag.

## The six cron entry points

Point Hermes cron's `--script` at these. Each takes no arguments.

| Script | Agent? | What it does |
|---|---|---|
| `lucid_preflight.py` | no | Extract last 2 days of sessions + trends. **Silent unless unhealthy.** |
| `lucid_collect.py` | feeds one | Extract a week + trends, print the context block the nightly review reasons over. |
| `lucid_memory_export.py` | no | Mirror the fact store into the vault as notes, then git-commit. |
| `lucid_snapshot.py` | no | Git-commit the vault and memories dir. |
| `lucid_garden.py` | feeds one | Scan the vault's wikilink graph → `vault_garden.json`. |
| `lucid_debrief.py` | no | Extract today's sessions. **Silent unless unhealthy.** |

Order matters: **review before export**, or the vault mirror is always a night stale.
See handoff §8 for the schedule.

Exit code 1 from preflight/debrief means issues were found and printed. Silence is
success — that's deliberate, a watchdog that talks every day gets ignored.

## The supporting modules

- `lucid_common.py` — path detection and config loading. Everything else imports it.
  Run it directly to debug paths.
- `lucid_ops.py` — the preflight/debrief/collect logic and the health check.
- `extract_sessions.py` — turns session transcripts into readable daily notes.
- `trend_detection.py` — 14-day topic/problem trends from those notes.
- `export_facts_to_vault.py` — fact store → vault notes, topic hubs, graph colours.
- `vault_garden.py` — wikilink graph analysis (orphans, dangling links, hubs).
- `snapshot.py` — git commit helper; self-heals by initialising a repo if absent.

## Windows scheduling

`setup-windows-scheduler.ps1` registers the every-minute `hermes cron tick` task that
makes scheduled jobs actually fire. Run it in a normal PowerShell:

```powershell
.\setup-windows-scheduler.ps1 -Profile <profile>
```

It tests the tick command before scheduling anything, then prints verification steps.
**Do them.** This script has not been executed on a Windows machine by its author — the
PowerShell is straightforward and the logic is standard `Register-ScheduledTask`, but
treat it as unverified until you have watched a real job fire.

## Safety properties worth knowing

- Everything that touches `memory_store.db` opens it **read-only in practice** (SELECT
  only). Safe to run while the agent is live.
- `snapshot.py` runs `git -c safe.directory=*`, so it works when the repo is owned by a
  different user than the caller.
- The exporter **regenerates** `Memory/Facts`, `Memory/Topics` and the dream notes each
  run — treat those trees as derived output, never hand-edit them. Everything else in
  the vault is the agent's and the owner's to write.
- Re-running any script is safe. The pipeline is idempotent; a second run with no new
  data commits nothing.
