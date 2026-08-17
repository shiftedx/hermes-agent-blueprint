#!/usr/bin/env python3
"""Shared path detection + config loading for the Lucid Dreamer scripts.

Every script in this directory imports this instead of hardcoding paths.

Layout assumed (all scripts live together in the profile's scripts/ dir):

    <HERMES_ROOT>/                     ~/.hermes  or  %LOCALAPPDATA%\\hermes
      lucid/memory/                    GLOBAL daily "dream" notes + review state
      profiles/<profile>/
        scripts/                       <- these scripts
        lucid/lucid.config.json        <- config
        memory_store.db                <- fact store
        sessions/                      <- session transcripts
        memories/                      <- MEMORY.md / USER.md (git repo)

Nothing here is OS-specific: paths are built with pathlib, never string
concatenation, so the same files work on Windows, macOS and Linux.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Optional

SCRIPTS_DIR = Path(__file__).resolve().parent
PROFILE_HOME = SCRIPTS_DIR.parent
LUCID_DIR = PROFILE_HOME / "lucid"
CONFIG_PATH = LUCID_DIR / "lucid.config.json"

# <HERMES_ROOT>/profiles/<profile>  ->  <HERMES_ROOT>
HERMES_ROOT = PROFILE_HOME.parent.parent
PROFILE_NAME = PROFILE_HOME.name

# The daily "dream" notes are GLOBAL, not per-profile. This trips people up.
GLOBAL_LUCID = HERMES_ROOT / "lucid"
MEMORY_DIR = GLOBAL_LUCID / "memory"
REVIEW_DIR = MEMORY_DIR / "review"

DB_PATH = PROFILE_HOME / "memory_store.db"
SESSIONS_DIR = PROFILE_HOME / "sessions"
MEMORIES_DIR = PROFILE_HOME / "memories"
PLUGIN_DIR = HERMES_ROOT / "hermes-agent" / "plugins" / "memory" / "holographic"

_PLACEHOLDER = re.compile(r"^\s*<.*>\s*$")


def load_config() -> dict:
    """Read lucid.config.json. Missing or malformed config is not fatal —
    callers fall back to defaults so a half-finished setup still runs."""
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def config_value(key: str, default=None):
    return load_config().get(key, default)


def vault_path() -> Optional[Path]:
    """Configured vault, or None if unset / still a <placeholder>."""
    vp = load_config().get("vault_path")
    if not vp or not str(vp).strip() or _PLACEHOLDER.match(str(vp)):
        return None
    return Path(str(vp)).expanduser()


def topics() -> dict:
    """{topic name: [keyword, ...]} used to cluster facts and detect trends.

    Set `topics` in lucid.config.json to match what the owner actually works
    on — the defaults are deliberately generic. Keywords are matched
    lowercase as plain substrings, so keep them short and distinctive.
    """
    t = load_config().get("topics")
    if isinstance(t, dict) and t:
        return {k: [str(x).lower() for x in v] for k, v in t.items()}
    return {
        "Errors and Crashes": ["error", "exception", "traceback", "crash", "failed", "stack trace"],
        "Hermes Agent": ["hermes", "gateway", "skill", "cron", "toolset", "approval", "memory provider"],
        "Memory and Lucid": ["lucid", "memory", "fact store", "vault", "nightly review", "consolidat"],
        "Performance": ["latency", "throughput", "benchmark", "slow", "speedup"],
        "Security": ["security", "vulnerability", "credential", "secret", "cve", "auth"],
        "Infrastructure": ["config", "deploy", "install", "update", "backup", "venv", "docker"],
        "Learning": ["learned", "explain", "how does", "why does", "tutorial", "concept"],
    }


def topic_colors() -> dict:
    """{topic name: 6-digit hex, no #}. Any topic without an entry falls back
    to grey. Purely cosmetic — drives the Obsidian graph view."""
    c = load_config().get("topic_colors")
    if isinstance(c, dict) and c:
        return {k: str(v).lstrip("#") for k, v in c.items()}
    return {
        "Errors and Crashes": "e06c75",
        "Hermes Agent": "61afef",
        "Memory and Lucid": "ab47bc",
        "Performance": "f59e0b",
        "Security": "ff8b50",
        "Infrastructure": "56b6c2",
        "Learning": "22c55e",
        "General": "78909c",
    }


def exclude_patterns() -> list:
    """Regex strings; any message matching one is dropped from daily notes.
    Use for retired workflows or noisy automation you don't want dreamed about."""
    p = load_config().get("session_exclude_patterns")
    return [str(x) for x in p] if isinstance(p, list) else []


def print_paths() -> int:
    """`python lucid_common.py --paths` prints resolved paths — the fastest way to
    confirm the scripts landed in the right place before wiring up cron.

    Returns the number of REQUIRED paths that are missing, so this doubles as a
    self-check: a non-zero exit means do not wire up the schedule yet.
    """
    vault = vault_path()
    # (label, path, required) — required paths must exist before the cycle can run.
    rows = [
        ("hermes root", HERMES_ROOT, True),
        ("profile home", PROFILE_HOME, True),
        ("config", CONFIG_PATH, True),
        ("fact store", DB_PATH, True),
        ("sessions", SESSIONS_DIR, True),
        ("dream notes", MEMORY_DIR, False),   # created on first run
        ("review state", REVIEW_DIR, False),  # created on first run
        ("memories", MEMORIES_DIR, True),
        ("plugin dir", PLUGIN_DIR, True),
        ("vault", vault, False),              # may not exist until Obsidian opens it
    ]
    missing = 0
    print(f"  profile name  {PROFILE_NAME}")
    for label, path, required in rows:
        if path is None:
            print(f"  {label:<13} (not configured)")
            continue
        if Path(path).exists():
            mark = "ok"
        elif required:
            mark = "MISSING"
            missing += 1
        else:
            mark = "absent (created on first run)"
        print(f"  {label:<13} {path}  [{mark}]")
    if missing:
        print(f"\n{missing} required path(s) MISSING — the scripts are not installed correctly.")
        print("They must sit together in <PROFILE_HOME>/scripts/ and the config in "
              "<PROFILE_HOME>/lucid/lucid.config.json.")
    return missing


if __name__ == "__main__":
    # Accept `--paths` explicitly and also bare invocation, so either habit works.
    print("Lucid Dreamer — resolved paths\n")
    sys.exit(1 if print_paths() else 0)
