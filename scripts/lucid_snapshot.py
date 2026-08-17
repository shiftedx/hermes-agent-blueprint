#!/usr/bin/env python3
"""Cron entry point: git-commit the vault and the memories dir.

Versions whatever the agent changed tonight so it is revertible. Read-only with
respect to the fact store, so it is safe to run while the agent is live.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import snapshot

if __name__ == "__main__":
    raise SystemExit(snapshot.main())
