#!/usr/bin/env python3
"""Cron entry point: evening session debrief (quiet unless unhealthy).

Thin wrapper so Hermes cron can point --script at a single file with no args.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lucid_ops

if __name__ == "__main__":
    sys.argv = [sys.argv[0], "debrief"]
    raise SystemExit(lucid_ops.main())
