#!/usr/bin/env python3
"""Lucid Dreamer — git snapshot of the agent-edited stores.

Commits the Obsidian vault and the built-in memory dir (MEMORY.md/USER.md) to
git so every nightly change the agent makes is versioned and revertible.
Run as the final step of the nightly review.

OS-agnostic, stdlib only, no pip deps (shells out to `git`), Optional[...].
Paths and config come from lucid_common (auto-detected from this file's
location); vault_path is read from lucid.config.json. Self-heals: inits a repo (with .gitignore + identity) if
one isn't present yet.
"""
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

import lucid_common as LC


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    # safe.directory=* lets git operate when the repo is owned by a different uid than the
    # caller (e.g. running as root inside a Docker sandbox over a host-owned bind mount).
    return subprocess.run(["git", "-c", "safe.directory=*", "-C", str(repo), *args],
                          capture_output=True, text=True)


def ensure_repo(repo: Path, gitignore: str) -> None:
    if not (repo / ".git").exists():
        git(repo, "init", "-q")
        git(repo, "config", "user.email", "hermes@localhost")
        git(repo, "config", "user.name", "Hermes Agent")
        gi = repo / ".gitignore"
        if not gi.exists():
            gi.write_text(gitignore, encoding="utf-8")


def snapshot(repo: Path, label: str, gitignore: str) -> str:
    if not repo.exists():
        return f"  [skip] {label}: {repo} missing"
    ensure_repo(repo, gitignore)
    git(repo, "add", "-A")
    if git(repo, "diff", "--cached", "--quiet").returncode == 0:
        return f"  [no changes] {label}"
    msg = f"lucid snapshot {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    git(repo, "commit", "-q", "-m", msg)
    n = git(repo, "rev-list", "--count", "HEAD").stdout.strip()
    return f"  [committed] {label}: commit #{n} ({msg})"


VAULT_GITIGNORE = ".obsidian/workspace.json\n.obsidian/cache\n.trash/\n.DS_Store\nThumbs.db\n"
MEM_GITIGNORE = "*.lock\n*.bak.*\n"


def main() -> int:
    cfg = LC.load_config()
    repos: List[Tuple[Path, str, str]] = []
    vp = cfg.get("vault_path")
    if vp and str(vp).strip() and not str(vp).startswith("<"):
        repos.append((Path(vp), "vault", VAULT_GITIGNORE))
    repos.append((LC.MEMORIES_DIR, "memories", MEM_GITIGNORE))
    print("[snapshot] versioning agent-edited stores:")
    for repo, label, gi in repos:
        print(snapshot(repo, label, gi))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
