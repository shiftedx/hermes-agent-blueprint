#!/usr/bin/env python3
"""Lucid Dreamer — clone the agent's MEMORIES (SQL facts) and DREAMS (daily session logs)
into the vault as one colourful, connected Obsidian graph.

  Memory/Facts/*    — one node per holographic fact (coloured by topic)
  Memory/Topics/*   — topic hub notes that cluster facts + dreams
  Lucid Dreamer/*   — one condensed "dream" node per day's session log, on a timeline
  Memory Review.md / Lucid Dreamer Index.md — the two indexes, cross-linked
  .obsidian/graph.json — per-topic colours, a distinct dream colour, low-trust dimming, tuned layout

The Memory/ + Lucid Dreamer/ trees are a read-only mirror of the SQL store + daily logs,
regenerated nightly. Read-only on the DB (safe while the gateway is live). Stdlib only.
"""
import json
import re
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import lucid_common as LC

DB_PATH = LC.DB_PATH
DREAMS_SRC = LC.MEMORY_DIR       # GLOBAL daily "dream" notes

MAX_TOPICS_PER_FACT = 4
MAX_TOPICS_PER_DREAM = 3
BAD = re.compile(r'[#\^\[\]\|:\\/<>"?*]')

# Topic clustering + colours come from lucid.config.json (see lucid_common).
# Edit them there, not here — these scripts are meant to be dropped in unchanged.
TOPIC_MAP = LC.topics()
COLORS = LC.topic_colors()

DREAM_COLOR = "b39ddb"      # ethereal violet — the "dreams"
LOWTRUST_COLOR = "455a64"   # muted slate — uncertain memories recede
ANCHOR_COLOR = "ffd54f"     # warm gold — the index hubs
DEFAULT_COLOR = "78909c"    # grey — anything without an assigned colour

# Display name used in the generated index notes / diagram. Defaults to the
# profile name, which is usually the agent's name anyway.
AGENT = str(LC.config_value("agent_name") or LC.PROFILE_NAME).strip() or LC.PROFILE_NAME

# Fact CATEGORY colours. Categories are whatever the agent writes into
# facts.category, so this can't be exhaustive; unknown categories fall back to
# DEFAULT_COLOR. Override with "category_colors" in lucid.config.json.
CAT_COLORS = {str(k): str(v).lstrip("#")
              for k, v in (LC.config_value("category_colors") or {
                  "identity": "2196f3", "career": "f44336", "projects": "4caf50",
                  "goals": "cddc39", "values": "9c27b0", "tech_stack": "00bcd4",
                  "hardware": "ff9800", "output_style": "e91e63", "interests": "8d6e63",
                  "infrastructure": "3f51b5", "security": "009688", "learning": "22c55e",
                  "general": "78909c",
              }).items()}

# Optional whole-project colouring: {"project-keyword": "hex"}. When an owner
# works across several projects, colouring by PROJECT reads far better than by
# category — each project cluster becomes one colour. Empty by default.
PROJECT_COLORS = {str(k).lower(): str(v).lstrip("#")
                  for k, v in (LC.config_value("project_colors") or {}).items()}

# graph layout (edit to taste). Tuned for a spread, readable, captivating map.
GRAPH = {
    "centerStrength": 0.28, "repelStrength": 13, "linkStrength": 0.75, "linkDistance": 135,
    "nodeSizeMultiplier": 1.45, "lineSizeMultiplier": 0.7, "textFadeMultiplier": 0,
    "showArrow": False, "showTags": False, "showOrphans": True, "hideUnresolved": True,
}


# Optional: map a fact-category PREFIX to a project name, e.g. {"gm_": "game-project"}.
# Lets a multi-project owner colour the graph by project. Empty by default.
CAT_PREFIX_PROJECT = {str(k).lower(): str(v).lower()
                      for k, v in (LC.config_value("project_category_prefixes") or {}).items()}


def project_for(category) -> Optional[str]:
    """Project name for a fact category, or None when not using projects."""
    cat = (category or "").lower()
    for prefix, proj in CAT_PREFIX_PROJECT.items():
        if cat.startswith(prefix):
            return proj
    return cat if cat in PROJECT_COLORS else None


def tag_slug(topic: str) -> str:
    return "mem/" + re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")


def load_vault() -> Optional[Path]:
    return LC.vault_path()


def fmt_date(ts) -> str:
    """Format a fact timestamp as YYYY-MM-DD.

    The schema declares TIMESTAMP but SQLite stores whatever it is given, and
    CURRENT_TIMESTAMP yields TEXT like "2026-08-15 04:27:50" — not an epoch int.
    Handle text first, epoch second, and only then give up.
    """
    if ts in (None, ""):
        return "?"
    s = str(ts).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:len(fmt) + 2].split(".")[0], fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(s.replace("Z", "")).strftime("%Y-%m-%d")
    except ValueError:
        pass
    try:
        return datetime.fromtimestamp(float(s)).strftime("%Y-%m-%d")
    except (ValueError, OSError, OverflowError):
        return "?"


def slug(content: str, fid: int) -> str:
    s = re.sub(r"\s+", " ", BAD.sub("", content)).strip()
    if len(s) > 52:
        s = s[:52].rsplit(" ", 1)[0]
    return f"{s} ({fid})"


def topics_for(content: str, cap: int = MAX_TOPICS_PER_FACT) -> List[str]:
    low = content.lower()
    hits = [t for t, kws in TOPIC_MAP.items() if any(k in low for k in kws)]
    return (hits or ["General"])[:cap]


def trust_band(t: float) -> str:
    return "low" if t < 0.6 else "med" if t < 0.85 else "high"


def dream_excerpt(text: str) -> str:
    for role, content in re.findall(r"\*\*(USER|ASSISTANT):\*\*\s*(.+?)(?=\n\*\*|\n### |\Z)",
                                    text, re.S):
        c = content.strip()
        if role == "USER" and c and not c.startswith("[CONTEXT COMPACTION"):
            # strip wikilink/embed brackets so a transcript can't spawn dangling graph links
            return re.sub(r"\s+", " ", c.replace("[[", "").replace("]]", "").replace("![", ""))[:200]
    return ""


def write_index(path: Path, lines: List[str]):
    path.write_text("\n".join(lines), encoding="utf-8")


def write_constellation(vault: Path, topic_members: dict, dream_count: int, fact_count: int):
    """A star-map cover (Diagrams/Memory Constellation.excalidraw) — topic nodes sized by
    activity, a violet Dreams node, on a night canvas. Deterministic so re-runs don't churn git."""
    import math
    diagrams = vault / "Diagrams"
    diagrams.mkdir(parents=True, exist_ok=True)
    BG, INK, GOLD, VIOLET = "#0e1018", "#c9d1e0", "#ffd54f", "#" + DREAM_COLOR
    ctr = [1000]

    def nid():
        ctr[0] += 7
        return str(ctr[0])

    def b(t, x, y, w, h, **kw):
        e = {"type": t, "version": 1, "versionNonce": ctr[0] * 3, "isDeleted": False, "id": nid(),
             "fillStyle": "solid", "strokeWidth": 1, "strokeStyle": "solid", "roughness": 0,
             "opacity": 100, "angle": 0, "x": x, "y": y, "strokeColor": "#ffffff",
             "backgroundColor": "transparent", "width": w, "height": h, "seed": ctr[0] * 5,
             "groupIds": [], "frameId": None, "roundness": None, "boundElements": [],
             "updated": 1, "link": None, "locked": False}
        e.update(kw)
        return e

    def dot(cx, cy, r, fill, stroke="#ffffff", op=100, sw=1):
        return b("ellipse", cx - r, cy - r, 2 * r, 2 * r, backgroundColor=fill, strokeColor=stroke,
                 strokeWidth=sw, opacity=op)

    def txt(s, cx, y, size, color, fam=2):
        w = max(20, int(len(s) * size * 0.6))
        return b("text", cx - w // 2, y, w, int(size * 1.25), text=s, originalText=s, fontSize=size,
                 fontFamily=fam, textAlign="center", verticalAlign="top", strokeColor=color,
                 baseline=int(size * 0.9), lineHeight=1.25)

    def ln(x1, y1, x2, y2, color, op=28, sw=1):
        return b("line", x1, y1, abs(x2 - x1), abs(y2 - y1), points=[[0, 0], [x2 - x1, y2 - y1]],
                 strokeColor=color, opacity=op, strokeWidth=sw, lastCommittedPoint=None,
                 startBinding=None, endBinding=None, startArrowhead=None, endArrowhead=None)

    CX, CY, R = 560, 720, 340
    els = []
    for i in range(24):                       # ambient dream-stars (kept below the title band)
        a, rr = i * 2.39996, 150 + (i * 53 % 360)
        sx, sy = CX + rr * math.cos(a), CY + rr * math.sin(a)
        if sy > 300:
            els.append(dot(sx, sy, 2 + (i % 3), VIOLET, stroke=VIOLET, op=20, sw=0))
    els.append(txt(f"{AGENT}  ·  Memories & Dreams", CX, 44, 34, GOLD, fam=1))
    els.append(txt(f"{fact_count} facts   ·   {dream_count} dreams   ·   {len(topic_members)} topics",
                   CX, 98, 16, INK))
    ring = [(t, len(set(topic_members[t])), "#" + COLORS.get(t, DEFAULT_COLOR))
            for t in sorted(topic_members, key=lambda x: -len(set(topic_members[x])))]
    ring.append(("Dreams", dream_count, VIOLET))
    pos = {}
    for i, (name, c, color) in enumerate(ring):
        ang = -math.pi / 2 + 2 * math.pi * i / len(ring)
        pos[name] = (CX + R * math.cos(ang), CY + R * math.sin(ang), 18 + 5 * math.sqrt(max(c, 1)), color)
    for nx, ny, r, color in pos.values():
        els.append(ln(CX, CY, nx, ny, color))
    els.append(dot(CX, CY, 46, "#1c2030", stroke=GOLD, sw=2))
    els.append(txt(AGENT, CX, CY - 12, 18, GOLD, fam=1))
    for name, (nx, ny, r, color) in pos.items():
        els.append(dot(nx, ny, r, color, stroke="#ffffff", sw=1))
        els.append(txt(name, nx, ny + r + 4, 13, color))
    doc = {"type": "excalidraw", "version": 2, "source": "https://excalidraw.com", "elements": els,
           "appState": {"gridSize": None, "viewBackgroundColor": BG}, "files": {}}
    (diagrams / "Memory Constellation.excalidraw").write_text(json.dumps(doc, indent=1), encoding="utf-8")


def main() -> int:
    vault = load_vault()
    if vault is None or not vault.exists():
        print(f"[mem-export] no usable vault — skipping (vault={vault}).")
        return 0
    if not DB_PATH.exists():
        print(f"[mem-export] no memory_store.db at {DB_PATH} — skipping.")
        return 0

    con = sqlite3.connect(str(DB_PATH), timeout=15)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA busy_timeout=15000")
    rows = con.execute("select fact_id, content, trust_score, category, tags, updated_at from facts order by fact_id").fetchall()
    con.close()

    mem = vault / "Memory"
    facts_dir, topics_dir = mem / "Facts", mem / "Topics"
    dreams_dir = vault / "Lucid Dreamer"
    for d in (facts_dir, topics_dir):
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True, exist_ok=True)
    dreams_dir.mkdir(parents=True, exist_ok=True)

    topic_members = {}   # topic -> [note names] (facts + dreams)

    # ---- MEMORIES: one node per fact ----
    for r in rows:
        content = (r["content"] or "").strip()
        topics = topics_for(content)
        name = slug(content, r["fact_id"])
        for t in topics:
            topic_members.setdefault(t, []).append(name)
        _proj = project_for(r["category"])
        tags = ["fact", f"trust/{trust_band(float(r['trust_score']))}", f"cat/{r['category']}"] + ([f"proj/{_proj}"] if _proj else []) + [tag_slug(t) for t in topics]
        body = ["---", "type: fact", f"fact_id: {r['fact_id']}", f"trust: {float(r['trust_score']):.2f}",
                f"category: {r['category']}", f"updated: {fmt_date(r['updated_at'])}",
                f"tags: [{', '.join(tags)}]", "---", content, "", "## Topics"]
        body += [f"- [[{t}]]" for t in topics]
        (facts_dir / f"{name}.md").write_text("\n".join(body), encoding="utf-8")

    # ---- DREAMS: one condensed node per day's session log, on a timeline ----
    dream_dates = sorted(p.stem for p in DREAMS_SRC.glob("20*.md")) if DREAMS_SRC.is_dir() else []
    for i, date in enumerate(dream_dates):
        raw = (DREAMS_SRC / f"{date}.md").read_text(encoding="utf-8", errors="replace")
        sessions = len(re.findall(r"^### Session:", raw, re.M)) or len(re.findall(r"\bSession\b", raw))
        topics = topics_for(raw, MAX_TOPICS_PER_DREAM)
        for t in topics:
            topic_members.setdefault(t, []).append(date)
        tags = ["dream"] + [tag_slug(t) for t in topics]
        nav = []
        if i > 0:
            nav.append(f"[[{dream_dates[i-1]}|← prev]]")
        if i < len(dream_dates) - 1:
            nav.append(f"[[{dream_dates[i+1]}|next →]]")
        body = ["---", "type: dream", f"date: {date}", f"sessions: {sessions}",
                f"tags: [{', '.join(tags)}]", "---", f"# Dream — {date}", "",
                f"_{sessions} session(s). Auto-condensed from the day's Hermes logs._", ""]
        ex = dream_excerpt(raw)
        if ex:
            body += [f"> {ex}", ""]
        body += ["## Topics"] + [f"- [[{t}]]" for t in topics]
        body += ["", "## Timeline", "- " + "  ·  ".join(nav) if nav else "", "", "[[Lucid Dreamer Index]]"]
        (dreams_dir / f"{date}.md").write_text("\n".join(body), encoding="utf-8")

    # ---- TOPIC HUBS (cluster both facts and dreams) ----
    for t, names in sorted(topic_members.items()):
        facts_n = sorted(n for n in set(names) if n not in dream_dates)
        dreams_n = sorted(n for n in set(names) if n in dream_dates)
        hub = ["---", "type: moc", f"tags: [memory-topic, {tag_slug(t)}]",
               f"created: {datetime.now():%Y-%m-%d}", "---", f"# {t}", "",
               f"_{len(facts_n)} fact(s) · {len(dreams_n)} dream(s) — auto-generated mirror._", ""]
        if facts_n:
            hub += ["## Facts"] + [f"- [[{n}]]" for n in facts_n]
        if dreams_n:
            hub += ["", "## Dreams"] + [f"- [[{n}]]" for n in dreams_n]
        (topics_dir / f"{BAD.sub('', t)}.md").write_text("\n".join(hub), encoding="utf-8")

    # ---- INDEXES (cross-linked so memories + dreams are ONE component) ----
    rev = ["---", "type: index", "tags: [memory, moc-hub]", f"created: {datetime.now():%Y-%m-%d}", "---",
           "# Memory Review", "",
           f"1:1 graph mirror of {AGENT}'s fact store — **{len(rows)} facts** across "
           f"**{len(topic_members)} topics**, plus **{len(dream_dates)} dreams** (daily logs). "
           f"Regenerated nightly; the SQL store is the live engine.", "", "→ [[Lucid Dreamer Index]]", "",
           "## Topics"]
    for t, names in sorted(topic_members.items()):
        rev.append(f"- [[{t}]] · {len(set(names))}")
    write_index(mem / "Memory Review.md", rev)

    idx = ["---", "type: index", "tags: [lucid-dreamer, moc-hub]", f"created: {datetime.now():%Y-%m-%d}", "---",
           "# Lucid Dreamer Index", "",
           f"**{len(dream_dates)} dreams** — condensed daily session logs, on a timeline. "
           f"Each links to the topics it touched, weaving into the memory graph.", "", "→ [[Memory Review]]", "",
           "## Dreams"]
    idx += [f"- [[{d}]]" for d in reversed(dream_dates)]
    write_index(dreams_dir / "Lucid Dreamer Index.md", idx)

    old_root = vault / "Memory Review.md"
    if old_root.exists():
        old_root.unlink()

    write_constellation(vault, topic_members, len(dream_dates), len(rows))

    # ---- GRAPH COLOURS + LAYOUT (.obsidian/graph.json; merge, preserve other keys) ----
    obs = vault / ".obsidian"
    if obs.is_dir():
        groups = [
            {"query": 'path:"Lucid Dreamer"', "color": {"a": 1, "rgb": int(DREAM_COLOR, 16)}},
            {"query": 'file:"Memory Review" file:"Lucid Dreamer Index" file:"Home"',
             "color": {"a": 1, "rgb": int(ANCHOR_COLOR, 16)}},
            {"query": "tag:#trust/low", "color": {"a": 1, "rgb": int(LOWTRUST_COLOR, 16)}},
        ]
        for proj, col in PROJECT_COLORS.items():
            groups.append({"query": f"tag:#proj/{proj}", "color": {"a": 1, "rgb": int(col, 16)}})
        for cat, col in CAT_COLORS.items():
            if cat[:3] in ("cw_", "cl_", "hu_"):  # project facts coloured by proj tag above
                continue
            groups.append({"query": f"tag:#cat/{cat}", "color": {"a": 1, "rgb": int(col, 16)}})
        for t in sorted(topic_members, key=lambda x: -len(set(topic_members[x]))):
            groups.append({"query": f"tag:#{tag_slug(t)}", "color": {"a": 1, "rgb": int(COLORS.get(t, DEFAULT_COLOR), 16)}})
        gpath = obs / "graph.json"
        try:
            g = json.loads(gpath.read_text(encoding="utf-8")) if gpath.exists() else {}
            g = g if isinstance(g, dict) else {}
        except Exception:
            g = {}
        g["colorGroups"] = groups
        g.update(GRAPH)
        gpath.write_text(json.dumps(g, indent=2), encoding="utf-8")
        print(f"[mem-export] graph: {len(groups)} colour groups + layout -> {gpath}")

    print(f"[mem-export] {len(rows)} facts + {len(dream_dates)} dreams + {len(topic_members)} topics -> {vault}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
