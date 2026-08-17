#!/usr/bin/env python3
"""Lucid Dreamer — session extraction, health check, and nightly context.

Modes:
  preflight  extract the last 2 days of sessions + trends. Prints ONLY if unhealthy.
  debrief    extract today's sessions. Prints ONLY if unhealthy.
  collect    extract a week + trends, then print the compact context block that
             the nightly-review agent job reasons over.

The silence in preflight/debrief is deliberate: a watchdog that speaks every day
trains its owner to ignore it. Exit code is 1 when there are issues, 0 otherwise.

Usage:  python lucid_ops.py [preflight|debrief|collect]
"""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

import lucid_common as LC

STATUS_PATH = LC.REVIEW_DIR / "lucid-health.json"
TRENDS_PATH = LC.REVIEW_DIR / "trends.json"


def run(script: str, *args: str, timeout: int = 180) -> dict:
    """Run a sibling script with the same interpreter. Never raises."""
    cmd = [sys.executable, str(LC.SCRIPTS_DIR / script), *args]
    try:
        p = subprocess.run(cmd, text=True, capture_output=True, timeout=timeout)
        return {"cmd": script, "returncode": p.returncode,
                "stdout": p.stdout.strip(), "stderr": p.stderr.strip()}
    except subprocess.TimeoutExpired as e:
        return {"cmd": script, "returncode": 124,
                "stdout": (e.stdout or ""), "stderr": f"timeout after {timeout}s"}
    except Exception as e:  # missing file, bad interpreter, etc.
        return {"cmd": script, "returncode": 127, "stdout": "", "stderr": str(e)}


def db_stats() -> dict:
    out = {"path": str(LC.DB_PATH), "exists": LC.DB_PATH.exists()}
    if not out["exists"]:
        return out
    con = sqlite3.connect(str(LC.DB_PATH))
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            "select count(*) facts, avg(trust_score) avg_trust, max(updated_at) max_updated from facts"
        ).fetchone()
        out.update(dict(row))
        out["avg_trust"] = round(float(out.get("avg_trust") or 0), 3)
        try:
            out["fts_count"] = con.execute("select count(*) from facts_fts").fetchone()[0]
        except Exception as e:
            out["fts_error"] = str(e)
    except sqlite3.OperationalError as e:
        # Almost always the legacy-vs-stock schema mismatch. Say so plainly.
        out["schema_error"] = f"{e} (expected columns: fact_id/content/category/tags/trust_score)"
    finally:
        con.close()
    return out


def note_stats(days: int = 14) -> dict:
    today = datetime.now()
    notes = []
    for i in range(days):
        day = today - timedelta(days=i)
        p = LC.MEMORY_DIR / f"{day:%Y-%m-%d}.md"
        if p.exists():
            txt = p.read_text(encoding="utf-8", errors="replace")
            notes.append({"date": f"{day:%Y-%m-%d}", "size": p.stat().st_size,
                          "sessions": txt.count("### Session:"), "words": len(txt.split())})
    return {"days_requested": days, "notes_found": len(notes), "notes": notes}


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        return {"error": str(e)}


def health(mode: str, runs: list) -> dict:
    LC.REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    status = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mode": mode,
        "profile": LC.PROFILE_NAME,
        "profile_home": str(LC.PROFILE_HOME),
        "hermes_root": str(LC.HERMES_ROOT),
        "plugin_present": (LC.PLUGIN_DIR / "plugin.yaml").exists(),
        "db": db_stats(),
        "notes": note_stats(14),
        "trends": load_json(TRENDS_PATH) if TRENDS_PATH.exists() else {"error": "missing trends.json"},
        "runs": runs,
    }
    issues = []
    db = status["db"]
    if not status["plugin_present"]:
        issues.append(f"holographic plugin not found at {LC.PLUGIN_DIR}")
    if not db.get("exists"):
        issues.append(f"fact store missing at {LC.DB_PATH}")
    elif db.get("schema_error"):
        issues.append(f"fact store schema mismatch: {db['schema_error']}")
    elif db.get("facts") != db.get("fts_count"):
        issues.append(f"FTS mismatch: facts={db.get('facts')} fts={db.get('fts_count')} "
                      f"(fix: INSERT INTO facts_fts(facts_fts) VALUES('rebuild'))")
    if status["notes"].get("notes_found", 0) == 0:
        issues.append("no daily notes found — session extraction may be broken, "
                      f"or {LC.SESSIONS_DIR} is empty")
    for r in runs:
        if r.get("returncode") != 0:
            issues.append(f"{r['cmd']} failed rc={r['returncode']}: {r.get('stderr')}")
    status["issues"] = issues
    STATUS_PATH.write_text(json.dumps(status, indent=2), encoding="utf-8")
    return status


def _quiet(mode: str, runs: list) -> int:
    status = health(mode, runs)
    if status["issues"]:
        print(f"Lucid {mode} issues:\n" + "\n".join(f"- {x}" for x in status["issues"]))
        print(f"status: {STATUS_PATH}")
        return 1
    return 0


def preflight() -> int:
    return _quiet("preflight", [run("extract_sessions.py", "2", "--force"),
                                run("trend_detection.py", "14", timeout=120)])


def debrief() -> int:
    return _quiet("debrief", [run("extract_sessions.py", "1", "--force")])


def collect() -> int:
    runs = [run("extract_sessions.py", "7", "--force", timeout=240),
            run("trend_detection.py", "14", timeout=120)]
    status = health("collect", runs)
    trends, notes, db = status.get("trends", {}), status.get("notes", {}), status.get("db", {})

    print("# Lucid Dreamer nightly context")
    print(f"generated_at: {status['generated_at']}")
    print(f"profile: {status['profile']}  ({status['profile_home']})")
    print(f"status_path: {STATUS_PATH}")
    print(f"issues: {json.dumps(status['issues'])}")
    print("\n## Fact store")
    print(json.dumps(db, indent=2))
    print("\n## Daily note coverage")
    print(json.dumps(notes, indent=2))
    print("\n## Trends")
    print(json.dumps({
        "days_analyzed": trends.get("days_analyzed"),
        "date_range": trends.get("date_range"),
        "summary": trends.get("summary"),
        "hot_topics": trends.get("hot_topics", {}),
        "recurring_problems": trends.get("recurring_problems", [])[:5],
        "top_entities": trends.get("top_entities", [])[:12],
    }, indent=2))
    print("\n## Recent note excerpts")
    for n in notes.get("notes", [])[:4]:
        p = LC.MEMORY_DIR / f"{n['date']}.md"
        txt = p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""
        print(f"\n### {n['date']} ({n['sessions']} sessions, {n['words']} words)\n"
              + " ".join(txt.split())[:1400])
    return 0


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "collect"
    fn = {"preflight": preflight, "debrief": debrief, "collect": collect}.get(mode)
    if not fn:
        print(f"unknown mode: {mode} (expected preflight|debrief|collect)", file=sys.stderr)
        return 2
    return fn()


if __name__ == "__main__":
    raise SystemExit(main())
