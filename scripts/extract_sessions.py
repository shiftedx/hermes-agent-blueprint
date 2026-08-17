#!/usr/bin/env python3
"""
Extract readable daily notes from Hermes sessions for Lucid Dreamer.

Handles both .jsonl and .json session formats.
Skips tool call noise, session_meta, empty turns.
Truncates long content to keep notes scannable.
"""

import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import lucid_common as LC

SESSIONS_DIR = LC.SESSIONS_DIR
MEMORY_DIR = LC.MEMORY_DIR

MAX_CONTENT_LEN = 800   # chars per message
MAX_TURNS_PER_SESSION = 40
SKIP_ROLES = {"session_meta", "tool", "system"}
# Optional per-owner noise filter, from lucid.config.json -> session_exclude_patterns.
# Empty by default: nothing is dropped unless the owner asks for it.
_EXCLUDE = [re.compile(p, re.IGNORECASE) for p in LC.exclude_patterns()]


def _parse_messages(path: Path) -> list[dict]:
    """Parse messages from a session file (.jsonl or .json)."""
    text = path.read_text(encoding="utf-8", errors="replace")
    messages = []

    if path.suffix == ".jsonl":
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                messages.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    else:
        # .json — could be a list or an object with messages key
        try:
            data = json.loads(text)
            if isinstance(data, list):
                messages = data
            elif isinstance(data, dict):
                messages = data.get("messages", data.get("turns", []))
        except json.JSONDecodeError:
            return []

    return messages


def _extract_text(content) -> str:
    """Extract plain text from content (str or list of blocks)."""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    parts.append(block.get("text", "").strip())
            elif isinstance(block, str):
                parts.append(block.strip())
        return " ".join(parts).strip()
    return ""


def _is_boring(text: str) -> bool:
    """Filter out noise: pure JSON blobs, empty, very short."""
    if len(text.strip()) < 30:
        return True
    stripped = text.strip()
    # Pure tool result JSON
    if stripped.startswith("{") and stripped.endswith("}") and len(stripped) > 300:
        try:
            json.loads(stripped)
            return True
        except Exception:
            pass
    if stripped.startswith("[") and stripped.endswith("]") and len(stripped) > 200:
        return True
    return False


def extract_day(date_str: str):
    """
    Extract session content for a given date (YYYYMMDD).
    Returns a markdown daily note or None if nothing found.
    """
    # Match both YYYYMMDD prefix and cron/gateway formats
    jsonl_sessions = sorted(SESSIONS_DIR.glob(f"{date_str}*.jsonl"))
    json_sessions = sorted(SESSIONS_DIR.glob(f"*{date_str}*.json"))
    # Exclude sessions.json master index
    json_sessions = [p for p in json_sessions if p.name != "sessions.json"]

    all_sessions = jsonl_sessions + json_sessions
    if not all_sessions:
        return None

    session_blocks = []

    for session_file in all_sessions:
        messages = _parse_messages(session_file)
        if not messages:
            continue

        turns = []
        for msg in messages[:MAX_TURNS_PER_SESSION * 2]:  # * 2 for user+assistant pairs
            role = msg.get("role", "")
            if role in SKIP_ROLES:
                continue
            if role not in ("user", "assistant"):
                continue

            text = _extract_text(msg.get("content", ""))
            if any(rx.search(text) for rx in _EXCLUDE):
                continue
            if _is_boring(text):
                continue

            # Truncate long content
            if len(text) > MAX_CONTENT_LEN:
                text = text[:MAX_CONTENT_LEN] + " [...]"

            turns.append(f"**{role.upper()}:** {text}")

            if len(turns) >= MAX_TURNS_PER_SESSION:
                turns.append("_[session truncated for length]_")
                break

        if turns:
            session_blocks.append(
                f"### Session: `{session_file.stem}`\n\n" + "\n\n".join(turns)
            )

    if not session_blocks:
        return None

    readable_date = datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")
    header = f"# Hermes Sessions — {readable_date}\n\n"
    return header + "\n\n---\n\n".join(session_blocks)


def main():
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    force = "--force" in sys.argv

    MEMORY_DIR.mkdir(parents=True, exist_ok=True)

    today = datetime.now()
    written = 0
    skipped = 0
    empty = 0

    for i in range(days):
        day = today - timedelta(days=i)
        date_key = day.strftime("%Y%m%d")
        note_path = MEMORY_DIR / f"{day.strftime('%Y-%m-%d')}.md"

        # Skip if already exists and non-trivial (unless --force)
        if note_path.exists() and note_path.stat().st_size > 200 and not force:
            skipped += 1
            print(f"  skip (exists): {note_path.name}")
            continue

        content = extract_day(date_key)
        if content:
            note_path.write_text(content, encoding="utf-8")
            written += 1
            word_count = len(content.split())
            print(f"  wrote: {note_path.name} ({word_count} words)")
        else:
            empty += 1
            print(f"  no sessions: {day.strftime('%Y-%m-%d')}")

    print(f"\nDone — {written} written, {skipped} skipped, {empty} empty days.")


if __name__ == "__main__":
    main()
