#!/usr/bin/env python3
"""Cron entry point: vault graph scan.

Writes lucid/memory/review/vault_garden.json (orphans / dangling links / hubs)
for the gardening agent job to reason over. Deterministic — the agent never has
to walk the graph by hand.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vault_garden

if __name__ == "__main__":
    raise SystemExit(vault_garden.main())
