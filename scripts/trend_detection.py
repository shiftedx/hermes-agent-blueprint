#!/usr/bin/env python3
"""
14-day trend detection for Lucid Dreamer.

Scans daily notes for recurring topics, problems, and patterns.
Outputs a structured JSON report consumed by the nightly review prompt.
"""

import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import lucid_common as LC

MEMORY_DIR = LC.MEMORY_DIR

# Topics come from lucid.config.json (see lucid_common.topics()). Each topic is a
# list of lowercase substrings; a day "hits" a topic if any substring appears.
# Substring matching, not word-boundary regex, so keywords stay easy to write.
TOPIC_KEYWORDS = LC.topics()

PROBLEM_SIGNALS = [
    r"\b(still broken|still failing|keeps happening|recurring|again|third time|same issue)\b",
    r"\b(TODO|FIXME|blocked|waiting on|unresolved|deferred|need to)\b",
]


def load_notes(days: int = 14):
    """Load daily notes for the past N days. Returns {date_str: content}."""
    notes = {}
    today = datetime.now()
    for i in range(days):
        day = today - timedelta(days=i)
        path = MEMORY_DIR / f"{day.strftime('%Y-%m-%d')}.md"
        if path.exists():
            notes[day.strftime("%Y-%m-%d")] = path.read_text(encoding="utf-8", errors="replace")
    return notes


def detect_topics(notes):
    """Find which days each topic appeared on."""
    topic_days = defaultdict(list)
    for date, content in sorted(notes.items()):
        lower = content.lower()
        for topic, keywords in TOPIC_KEYWORDS.items():
            if any(k in lower for k in keywords):
                topic_days[topic].append(date)
    return dict(topic_days)


def detect_recurring_problems(notes):
    """Find topics that appear as problems on multiple days."""
    problems = []
    for date, content in sorted(notes.items()):
        lower = content.lower()
        for pattern in PROBLEM_SIGNALS:
            matches = re.findall(pattern, lower, re.IGNORECASE)
            for match in matches:
                # Find surrounding context
                idx = lower.find(match.lower())
                snippet = content[max(0, idx-60):idx+120].strip()
                problems.append({"date": date, "signal": match, "snippet": snippet[:200]})
    return problems


def extract_mentioned_entities(notes):
    """Extract frequently mentioned proper nouns / entities."""
    counter: Counter = Counter()
    entity_pattern = re.compile(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b')
    skip = {"The", "This", "That", "There", "When", "Where", "How", "What", "Which",
            "Also", "Note", "Done", "Step", "Run", "Set", "Now", "Yes", "No", "Reply"}
    for content in notes.values():
        for match in entity_pattern.finditer(content):
            entity = match.group(1)
            if entity not in skip and len(entity) > 3:
                counter[entity] += 1
    return counter.most_common(20)


def build_report(days: int = 14) -> dict:
    notes = load_notes(days)
    if not notes:
        return {"error": "No daily notes found", "days_loaded": 0}

    topic_days = detect_topics(notes)
    problems = detect_recurring_problems(notes)
    entities = extract_mentioned_entities(notes)

    # Identify hot topics (appeared on 3+ days)
    hot_topics = {t: d for t, d in topic_days.items() if len(d) >= 3}

    # Identify cold topics (only 1 day)
    cold_topics = {t: d for t, d in topic_days.items() if len(d) == 1}

    return {
        "generated_at": datetime.now().isoformat(),
        "days_analyzed": len(notes),
        "date_range": {
            "from": min(notes.keys()) if notes else None,
            "to": max(notes.keys()) if notes else None,
        },
        "hot_topics": hot_topics,
        "all_topics": {t: {"days": d, "frequency": len(d)} for t, d in sorted(topic_days.items(), key=lambda x: -len(x[1]))},
        "recurring_problems": problems[:10],
        "top_entities": [{"entity": e, "mentions": c} for e, c in entities],
        "summary": _summarize(hot_topics, problems, len(notes)),
    }


def _summarize(hot_topics: dict, problems: list, days: int) -> str:
    lines = []
    if hot_topics:
        topics_str = ", ".join(f"{t} ({len(d)}d)" for t, d in sorted(hot_topics.items(), key=lambda x: -len(x[1])))
        lines.append(f"Recurring topics over {days} days: {topics_str}.")
    if problems:
        lines.append(f"{len(problems)} recurring problem signals detected.")
    if not lines:
        lines.append(f"No strong trends detected over {days} days.")
    return " ".join(lines)


def main():
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 14
    report = build_report(days)

    output_path = LC.REVIEW_DIR / "trends.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(f"Trend report written to {output_path}")
    print(f"Days analyzed: {report.get('days_analyzed', 0)}")
    if report.get("summary"):
        print(f"Summary: {report['summary']}")
    if report.get("hot_topics"):
        print("Hot topics:")
        for topic, days_list in report["hot_topics"].items():
            print(f"  {topic}: {len(days_list)} days — {', '.join(days_list[-3:])}")


if __name__ == "__main__":
    main()
