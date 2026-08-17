#!/usr/bin/env python3
"""Lucid Dreamer — vault gardener (deterministic graph analysis).

Scans the Obsidian vault, builds the [[wikilink]] graph, and reports:
  - orphans       : notes with zero inbound links (excluding Home/Index/MOC entry points)
  - dangling_links: [[targets]] that point to notes which don't exist
  - most_linked   : the hub notes (highest inbound)
  - stats         : note + link counts
Writes lucid/memory/review/vault_garden.json for the nightly review to reason over
(suggest connections for orphans, fix dangling links, refresh MOCs, synthesize).

Deterministic so the small model doesn't have to grep the graph by hand.
OS-agnostic, stdlib only, Optional[...]. Reads vault_path from lucid.config.json.
"""
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set

import lucid_common as LC

REVIEW_DIR = LC.REVIEW_DIR

WIKILINK = re.compile(r"\[\[([^\]]+)\]\]")
EXCLUDE_DIRS = {".obsidian", ".trash", "_templates"}
# entry-point notes are allowed to have no inbound links
ENTRY_HINTS = ("index", "home", "moc", "map of content")


def link_target(raw: str) -> str:
    # [[Note|alias]] / [[Note#heading]] -> "Note"
    return raw.split("|")[0].split("#")[0].strip()


def strip_code(text: str) -> str:
    # Drop fenced + inline code markers so `[[wikilinks]]` shown as examples aren't counted as links.
    # Strip only backtick delimiters (not content between them) so filename stems with backticks
    # match their link targets consistently.
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    text = re.sub(r"`", "", text)
    return text


def main() -> int:
    cfg = LC.load_config()
    vp = cfg.get("vault_path")
    if not vp or not str(vp).strip() or str(vp).startswith("<"):
        print("[garden] no vault_path configured — skipping vault gardening.")
        return 0
    vault = Path(vp)
    if not vault.exists():
        print(f"[garden] vault not found at {vault} — skipping.")
        return 0

    notes: Dict[str, Dict] = {}  # stem_lower -> {name, outlinks:set}
    for fp in vault.rglob("*.md"):
        if any(part in EXCLUDE_DIRS for part in fp.parts):
            continue
        text = strip_code(fp.read_text(encoding="utf-8", errors="replace"))
        outs: Set[str] = set()
        for m in WIKILINK.finditer(text):
            t = link_target(m.group(1))
            if t:
                outs.add(t.lower())
        notes[fp.stem.lower().replace("`", "")] = {"name": fp.stem, "outlinks": outs}

    existing = set(notes.keys())
    inbound: Dict[str, int] = {k: 0 for k in notes}
    dangling: Dict[str, List[str]] = {}
    for k, info in notes.items():
        for t in info["outlinks"]:
            if t == k:
                continue
            if t in existing:
                inbound[t] += 1
            else:
                dangling.setdefault(info["name"], []).append(t)

    orphans = sorted(
        notes[k]["name"] for k in notes
        if inbound[k] == 0 and not any(h in k for h in ENTRY_HINTS)
    )
    by_inbound = sorted(notes.keys(), key=lambda k: inbound[k], reverse=True)

    out = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "vault": str(vault),
        "note_count": len(notes),
        "total_outlinks": sum(len(i["outlinks"]) for i in notes.values()),
        "orphans": orphans,
        "dangling_links": {k: sorted(set(v)) for k, v in dangling.items()},
        "most_linked": [
            {"note": notes[k]["name"], "inbound": inbound[k]}
            for k in by_inbound[:5] if inbound[k] > 0
        ],
    }
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    (REVIEW_DIR / "vault_garden.json").write_text(json.dumps(out, indent=2), encoding="utf-8")

    print(f"[garden] {out['note_count']} notes, {out['total_outlinks']} links")
    print(f"[garden] orphans ({len(orphans)}): {', '.join(orphans) if orphans else 'none'}")
    dl = sum(len(v) for v in out['dangling_links'].values())
    print(f"[garden] dangling links: {dl}" + (f"  {out['dangling_links']}" if dl else ""))
    print(f"[garden] wrote {REVIEW_DIR / 'vault_garden.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
