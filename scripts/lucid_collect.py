#!/usr/bin/env python3
"""Cron entry point: builds the context block for the nightly review agent job.

Thin wrapper so Hermes cron can point --script at a single file with no args.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lucid_ops

if __name__ == "__main__":
    sys.argv = [sys.argv[0], "collect"]
    raise SystemExit(lucid_ops.main())
