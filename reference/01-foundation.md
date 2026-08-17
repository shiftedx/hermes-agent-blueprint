# 01. Foundation — §0–§3

_Variables, install, profile layout, and the four identity files. Run [00-verify-your-build.md](00-verify-your-build.md) first._

---

## 0. Variables used throughout

Set these once; every command below uses them. Nothing else in this blueprint is path-dependent.

```bash
HERMES_ROOT="$HOME/.hermes"                 # macOS/Linux. On Windows: %LOCALAPPDATA%\hermes
PROFILE="<agent-name>"                      # lowercase, e.g. the agent's own name
PROFILE_HOME="$HERMES_ROOT/profiles/$PROFILE"
WORKSPACE="$HOME/Documents/$PROFILE-workspace"   # agent's working dir — NOT inside a cloud-sync folder
VAULT="$WORKSPACE/Vault"                    # Obsidian vault = the agent's browsable brain
# The bundled scripts call sys.executable, so no interpreter path needs pinning.
# If you invoke one by hand, any Python 3.9+ on PATH works — they are stdlib-only.
```

Placeholders in templates: `<AGENT>` = agent name, `<OWNER>` = the human's name, `<TZ>` = IANA timezone.

**Windows note:** paths become `%LOCALAPPDATA%\hermes\...`, the service manager is Task Scheduler rather than launchd/systemd, and shell wrappers should be `.py` invoked directly rather than `.sh`. Everything else is identical. Where this doc shows a `.sh` wrapper, a Python script works the same way and is the portable choice — `--script` runs `.sh`/`.bash` via bash and **everything else via Python**, so a `.py` wrapper is a first-class citizen.

> ⚠️ **Do not put `$WORKSPACE` inside iCloud/Dropbox/OneDrive.** Sync daemons race the vault's git repo and the SQLite DBs. This bit the reference deployment; the workspace was moved out of a synced folder for exactly this reason.

---

## 1. Prerequisites and install

1. Install from the **Hermes Desktop installer** at `hermes-agent.nousresearch.com` (macOS / Windows / Linux). The desktop installer lays down *both* the desktop app and the CLI into the same `HERMES_ROOT`. Take it over the CLI-only `install.sh` — you want both, because several steps below are CLI-only (cron editing, `prompt-size`, skills repair) even though day-to-day use is the app.
   ```bash
   hermes --version      # reference deployment: v0.20.1 (config schema v33)
   ```
   If `hermes` isn't on PATH after installing the app, find it under `$HERMES_ROOT` and add it — you'll need it. This doc was written against **0.20.x**; on a much newer major, re-check §4 key names before pasting config.
2. Create the profile and run the wizard **as the owner**, not autonomously — the owner picks the model and provider:
   ```bash
   hermes --profile "$PROFILE" setup
   ```
   Skip all messaging-platform setup. Leave `platforms: {}` and the `discord:`/`slack:`/`telegram:` blocks at defaults; they're inert without tokens in `.env`.
3. Create the workspace + vault dirs, and `git init` both the vault and the memories dir (versioning is what makes the nightly snapshot meaningful):
   ```bash
   mkdir -p "$WORKSPACE"/{scratch,outputs} "$VAULT"/{"Lucid Dreamer",Memory/Facts,Memory/Topics,Diagrams}
   git -C "$VAULT" init
   git -C "$PROFILE_HOME/memories" init
   ```
4. Open the vault once in Obsidian so `.obsidian/` is created. If you want hand-drawn diagrams, install the Excalidraw community plugin (Obsidian must be restarted to load it). `.gitignore` the plugin's `main.js`/`styles.css` (multi-MB) but track `manifest.json` and `community-plugins.json`.

**CLI gotcha that will waste your time:** gateway subcommands resolve the profile from the `--profile/-p` **flag** (or the sticky `active_profile` file), **not** from the `HERMES_PROFILE` env var — but `hermes config check` *does* honor the env var. Always use `hermes --profile "$PROFILE" gateway ...`. Using the env var for gateway commands silently targets the wrong profile.

---

## 2. Profile layout (what lives where)

```
$PROFILE_HOME/
  config.yaml            # everything in §4–§5. The live gateway also WRITES this — see §9 safe-edit.
  .env                   # secrets: platform tokens, API keys. Read at startup only.
  SOUL.md                # persona (§3)
  memories/
    MEMORY.md            # short durable notes about the world/work (char-capped)
    USER.md              # short durable notes about the human (char-capped)
    .git/                # nightly snapshot target
  memory_store.db        # holographic fact store (SQLite) — the REAL long-term memory (§6)
  state.db               # conversation history + FTS
  sessions/              # JSON transcripts
  skills/                # installed skills (see §5 for the two upstream sources)
  custom-skills/         # your own skills; must be registered via skills.external_dirs
  scripts/               # ALL lucid scripts live here together (§8) — they import each other
  lucid/
    lucid.config.json    # tunables for the lucid pipeline
    prompts/             # nightly-review.md + gardening.md (the two agent-job prompts)
    memory/review/       # machine-readable review state (vault_garden.json, health json)
  logs/                  # gateway.log, gateway.error.log, agent.log, errors.log
$HERMES_ROOT/lucid/memory/   # GLOBAL daily dream notes: YYYY-MM-DD.md + review/{lucid-health,trends}.json
$WORKSPACE/AGENTS.md     # workspace conventions the agent reads (§3)
```

Note the split: **daily dream notes live in the global `$HERMES_ROOT/lucid/memory/`**, not in the profile. Profiles do not share these — each profile writes its own set if it has its own lucid crons, but the path is global-shaped. Know which one you're looking at.

---

## 3. Identity layer — four files, four jobs

Keep these four straight; conflating them is the most common setup error.

| File | Written by | Read when | Job |
|---|---|---|---|
| `SOUL.md` | human (rarely) | every turn, system prompt | **Who the agent is.** Persona, tone, values. |
| `$WORKSPACE/AGENTS.md` | human | every turn | **How to work in this workspace.** Dirs, conventions, path rules. |
| `memories/MEMORY.md` | agent (auto-flush) | every turn | Short durable world/project notes. Char-capped. |
| `memories/USER.md` | agent (auto-flush) | every turn | Short durable notes about the human. Char-capped. |

**Do not use SOUL.md as a rules dump.** It is loaded every single turn; length there is a permanent tax on the context budget. The reference SOUL.md is ~700 bytes. Keep yours under ~1KB.

**Do not set a personality preset in `display.personality` if you have a SOUL.md.** The reference deployment had a preset silently fighting SOUL.md for tone; the presets were removed so SOUL.md is the sole persona source. Keep `display.personality: ''`.

### 3a. SOUL.md — teaching-assistant variant (fill the blanks)

This is the requested posture: **the agent does the real work, at full capability, but makes the work legible so the human learns from watching it.** It is not a tutor that withholds output, and not a black box that hands over answers.

```markdown
# <AGENT>

You are <AGENT>: <OWNER>'s capable, friendly personal operator — and, while you work, their guide.

Do the real work. When <OWNER> asks for something, build it, run it, verify it, and deliver it.
Never stall the job to quiz them, and never withhold a result to make a teaching point.

But narrate the path, briefly. Before a non-obvious move, say in one line what you're about to do
and why that approach over the alternative. After it works, name the idea that made it work.
When something breaks, show the actual error and how you read it — debugging is the most
teachable thing you do.

Offer the wheel, don't force it. On a low-stakes final step, ask if <OWNER> wants to try that
part themselves; if they say no or don't answer, just finish it. Their time and momentum
come first.

Use their words back to them. Introduce a real term once, plainly ("this is a race condition —
two things touching the same file at once"), then keep using it. Don't lecture, don't pad,
don't quiz.

Be honest before agreeable. Say plainly when an idea won't work and why, and back a good one
with real enthusiasm. If you're unsure, say so, then go verify.

Act, verify, finish. Lead with the result. Keep routine answers tight.
```

Blanks to fill: `<AGENT>`, `<OWNER>`. Nothing else is required.

### 3b. AGENTS.md — workspace conventions (fill the blanks)

```markdown
# <AGENT> workspace

Default workspace: `<WORKSPACE>`.

- Temporary work → `scratch/`; finished deliverables → `outputs/`; durable notes → `Vault/`
  using the `obsidian-vault` skill.
- Keep the workspace root tidy. Work in a project's own absolute path when one is named.
- <OWNER>'s real home is `<HOME>`; use absolute paths for Desktop, Downloads, Documents, repos.
- Setup is complete. Do not rerun first-run setup unless <OWNER> explicitly asks.
```

That last line matters: without it, agents re-trigger first-run setup flows and clobber config.

### 3c. MEMORY.md / USER.md — start them empty

Start both as empty files. The agent fills them via auto-flush. Two honest notes:

- There was an attempt on the reference deployment to convert these into **pointers** ("your durable memory is the fact store, not this file"). **It did not hold** — verified: both files have since drifted back to holding actual facts, because the auto-flush path writes to them regardless. Don't rely on a pointer surviving. If you want them to stay pointers, you must disable memory flushing, which costs you more than it buys.
- They are char-capped (`memory.memory_char_limit` / `user_char_limit`). When near cap the agent should **compact, not append**. That instruction lives in the nightly-review prompt (§8).

---
