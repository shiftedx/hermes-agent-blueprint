# 05. Operations & hygiene — §9

_Keeping it alive, editing config safely, and the failure modes that present as silence._

---

## 9. Keeping it alive & operational hygiene

On this install there are two moving pieces: the **app** (interactive use) and the **scheduled task** that ticks cron (§8a). No gateway, no supervised service. The config-edit rule below applies regardless; the gateway subsection is reference material in case that changes.

⚑ **Safe config-edit procedure — applies to the desktop app too.** Anything running the agent may *write* `config.yaml`, so editing it live races that process and your edit is silently clobbered. **Quit the app** (and stop the ticker service if running) before hand-editing config, then restart.

```bash
cp config.yaml "config.yaml.bak-$(date +%Y%m%d-%H%M%S)"    # ALWAYS back up first
$EDITOR config.yaml
```
Prefer the app's Settings UI for simple values. For the bulk config in §4–§6, edit the file with everything stopped — the UI doesn't expose most of these keys.

This is the same class of bug as any GUI app that owns a config file: it may rewrite the file from in-memory state when it quits, reverting your edit. After editing a config a GUI also owns, re-read the file once the app has quit and confirm your change survived.

### Only if you switch to a gateway

The gateway runs as a **user-level supervised service** — launchd on macOS (`~/Library/LaunchAgents/ai.hermes.gateway-<profile>.plist`), systemd user units on Linux, Task Scheduler on Windows. Start at login, restart on crash, **one label per profile**. Two services sharing a label produce an endless mutual-SIGTERM restart loop — historically the worst failure mode here.

Because restart-on-crash is unconditional, a plain `hermes gateway stop` is immediately relaunched by the supervisor. To actually stop it:
```bash
# macOS
launchctl bootout gui/$(id -u)/ai.hermes.gateway-$PROFILE      # clean stop, waits out the drain
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/ai.hermes.gateway-$PROFILE.plist
launchctl kickstart -k "gui/$(id -u)/ai.hermes.gateway-$PROFILE"   # restart without editing
# Linux: systemctl --user stop/start hermes-gateway@$PROFILE
```

**Most likely failure mode: "service not loaded."** A burst of `hermes update` / `gateway restart` can boot the job out and never re-bootstrap it — restart-on-crash cannot revive a job that no longer exists. The tell is silence: no morning report, and jobs in the Cron pane with stale last-run times.
```bash
hermes --profile "$PROFILE" gateway status     # "✗ Gateway service is not loaded"
launchctl list | grep hermes                   # empty = not loaded
hermes --profile "$PROFILE" gateway start      # auto-reloads the definition
```
Ignore these in the logs — they are **not** fatal: transient DNS errors to chat-platform hosts (irrelevant with no platform configured), and `SOUL.md`/`MEMORY.md` "file not found" warnings.

⚑ **Log rotation gap.** `gateway.log` / `gateway.error.log` are the *supervisor's* stdout/stderr redirects (kernel-level `O_APPEND`). Hermes' own `logging.max_size_mb` rotating handler **never touches them** — they grow unbounded (112MB on the reference deployment). Keep the daily rotate cron that truncates them in place above a threshold; in-place truncation is safe on a live process thanks to `O_APPEND`.

### With the `cron tick` scheduler (the setup here)

Much less to maintain: no service to fall out of a supervisor, no drain, no log-rotation gap. The failure mode is quieter, though — a broken scheduled task produces no logs at all, and the only symptom is that the morning report stops appearing. Check the task and the execution history when in doubt:
```bash
sqlite3 "$PROFILE_HOME/cron/executions.db" \
  "select job_id, started_at, status from executions order by started_at desc limit 10;"
```

**Config-drift gotcha, generally:** any GUI app that owns a config file (model servers, desktop launchers) may rewrite it from in-memory state on quit, silently reverting your file edits. If you edit a config that a running app also owns, verify it stuck after the app next quits.

**Log-grep gotcha:** traceback continuation lines carry no timestamp, so date filters like `awk '$1>="2026-08-01"'` pass them regardless of age. Undated traceback blocks in a filtered grep may be months old. Don't diagnose from them.

