"""SQLite-backed digest storage — powers the dashboard, deadline docket,
and archive.

save_digest() is idempotent per run_date: it deletes any existing rows
for that date before inserting, so running the digest twice on the same
day (a manual click plus a scheduled GitHub Action, for example) never
duplicates rows.
"""
import sqlite3
import json
from datetime import datetime, timezone

DB_PATH = "digest.db"

_NEW_COLUMNS = ("why_it_matters", "deadline", "cross_categories", "identifiers")


def init_db(path=DB_PATH):
    conn = sqlite3.connect(path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS digests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_date TEXT NOT NULL,
            category TEXT NOT NULL,
            title TEXT,
            link TEXT,
            source TEXT,
            published TEXT,
            priority TEXT,
            summary TEXT,
            watchlist_matches TEXT,
            also_reported_by TEXT,
            why_it_matters TEXT,
            deadline TEXT,
            cross_categories TEXT,
            identifiers TEXT
        )
    """)
    # Read/bookmark state is tracked separately, keyed by the article's link
    # rather than its digests.id — the same story can appear in multiple
    # run_dates (e.g. still open in Archive & Trends the next day), and a
    # single global state per link is what makes "already read" mean
    # anything sensible across those repeats.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS article_state (
            link TEXT PRIMARY KEY,
            is_read INTEGER NOT NULL DEFAULT 0,
            is_bookmarked INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT
        )
    """)
    # Lightweight migration for databases created before these columns existed.
    existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(digests)").fetchall()}
    for col in _NEW_COLUMNS:
        if col not in existing_cols:
            conn.execute(f"ALTER TABLE digests ADD COLUMN {col} TEXT")
    conn.commit()
    return conn


def save_digest(articles, path=DB_PATH, run_date=None):
    run_date = run_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    conn = init_db(path)
    # Idempotent: clear any prior run for this date before inserting, so
    # re-running the digest (manual + scheduled both firing) never doubles rows.
    conn.execute("DELETE FROM digests WHERE run_date = ?", (run_date,))
    for a in articles:
        published = a["published"]
        published_str = published.isoformat() if hasattr(published, "isoformat") else str(published)
        conn.execute(
            "INSERT INTO digests (run_date, category, title, link, source, published, "
            "priority, summary, watchlist_matches, also_reported_by, why_it_matters, "
            "deadline, cross_categories, identifiers) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                run_date, a["category"], a["title"], a["link"], a["source"], published_str,
                a.get("priority", "Low"), a.get("summary", ""),
                json.dumps(a.get("watchlist_matches", [])),
                json.dumps(a.get("also_reported_by", [])),
                json.dumps(a.get("why_it_matters", {})),
                a.get("deadline"),
                json.dumps(a.get("cross_categories", [])),
                json.dumps(a.get("identifiers", [])),
            ),
        )
    conn.commit()
    conn.close()
    return run_date


def get_available_dates(path=DB_PATH):
    conn = init_db(path)
    rows = conn.execute("SELECT DISTINCT run_date FROM digests ORDER BY run_date DESC").fetchall()
    conn.close()
    return [r[0] for r in rows]


def _hydrate(row):
    d = dict(row)
    d["watchlist_matches"] = json.loads(d["watchlist_matches"] or "[]")
    d["also_reported_by"] = json.loads(d["also_reported_by"] or "[]")
    d["why_it_matters"] = json.loads(d["why_it_matters"] or "{}")
    d["cross_categories"] = json.loads(d["cross_categories"] or "[]")
    d["identifiers"] = json.loads(d["identifiers"] or "[]")
    return d


def get_state_map(links, path=DB_PATH):
    """Batch-fetch read/bookmark state for a list of links in one query,
    instead of one query per card (matters once a digest has 50+ articles)."""
    if not links:
        return {}
    conn = init_db(path)
    conn.row_factory = sqlite3.Row
    placeholders = ",".join("?" for _ in links)
    rows = conn.execute(
        f"SELECT link, is_read, is_bookmarked FROM article_state WHERE link IN ({placeholders})",
        list(links),
    ).fetchall()
    conn.close()
    return {r["link"]: {"read": bool(r["is_read"]), "bookmarked": bool(r["is_bookmarked"])} for r in rows}


def _upsert_state(link, path, **fields):
    conn = init_db(path)
    existing = conn.execute("SELECT link FROM article_state WHERE link = ?", (link,)).fetchone()
    now = datetime.now(timezone.utc).isoformat()
    if existing:
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        conn.execute(
            f"UPDATE article_state SET {set_clause}, updated_at = ? WHERE link = ?",
            (*fields.values(), now, link),
        )
    else:
        cols = ["link", *fields.keys(), "updated_at"]
        placeholders = ",".join("?" for _ in cols)
        conn.execute(
            f"INSERT INTO article_state ({', '.join(cols)}) VALUES ({placeholders})",
            (link, *fields.values(), now),
        )
    conn.commit()
    conn.close()


def mark_read(link, read=True, path=DB_PATH):
    _upsert_state(link, path, is_read=int(read))


def toggle_bookmark(link, path=DB_PATH):
    """Flips bookmark state and returns the new value, so the caller can
    update the UI immediately without a second read."""
    conn = init_db(path)
    row = conn.execute("SELECT is_bookmarked FROM article_state WHERE link = ?", (link,)).fetchone()
    conn.close()
    new_value = not bool(row[0]) if row else True
    _upsert_state(link, path, is_bookmarked=int(new_value))
    return new_value


def get_bookmarked(path=DB_PATH):
    """All bookmarked articles, most recently bookmarked first, joined
    against the most recent digests row for each link so titles/summaries
    are available even if the link fell out of the active date range."""
    conn = init_db(path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT d.* FROM digests d
        INNER JOIN article_state s ON s.link = d.link
        WHERE s.is_bookmarked = 1
        AND d.id = (SELECT MAX(id) FROM digests WHERE link = d.link)
        ORDER BY s.updated_at DESC
    """).fetchall()
    conn.close()
    return [_hydrate(r) for r in rows]


def get_digest(run_date, path=DB_PATH):
    conn = init_db(path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM digests WHERE run_date = ? "
        "ORDER BY CASE priority WHEN 'High' THEN 0 WHEN 'Medium' THEN 1 ELSE 2 END, published DESC",
        (run_date,),
    ).fetchall()
    conn.close()
    return [_hydrate(r) for r in rows]


def get_stats_by_date(path=DB_PATH):
    conn = init_db(path)
    rows = conn.execute(
        "SELECT run_date, category, COUNT(*) FROM digests GROUP BY run_date, category ORDER BY run_date"
    ).fetchall()
    conn.close()
    return rows


def get_upcoming_deadlines(path=DB_PATH):
    """All articles with a successfully-parsed deadline, deduplicated by
    link, most imminent first."""
    conn = init_db(path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM digests WHERE deadline IS NOT NULL AND deadline != '' ORDER BY deadline ASC"
    ).fetchall()
    conn.close()
    seen_links = set()
    results = []
    for r in rows:
        d = _hydrate(r)
        if d["link"] in seen_links:
            continue
        seen_links.add(d["link"])
        results.append(d)
    return results
