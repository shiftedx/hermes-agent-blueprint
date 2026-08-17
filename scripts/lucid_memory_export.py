#!/usr/bin/env python3
"""Cron entry point: mirror the fact store into the vault, then snapshot it.

Read-only against memory_store.db, so it is safe while the agent is running.
Must be scheduled AFTER the nightly review, or the mirror is a night stale.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import export_facts_to_vault
import snapshot

if __name__ == "__main__":
    rc = export_facts_to_vault.main()
    if rc:
        raise SystemExit(rc)
    raise SystemExit(snapshot.main())
