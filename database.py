import hashlib
import sqlite3
import threading
from datetime import datetime, timezone

import config

_local = threading.local()

SCHEMA_VERSION = 1

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS sources (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    type            TEXT NOT NULL CHECK(type IN ('channel', 'video', 'reddit', 'discord', 'facebook')),
    url             TEXT NOT NULL,
    channel_id      TEXT,
    channel_name    TEXT,
    last_scanned_at TEXT,
    status          TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'paused', 'removed')),
    added_by        TEXT NOT NULL DEFAULT 'manual',
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_sources_channel_id ON sources(channel_id);

CREATE TABLE IF NOT EXISTS transcripts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id       INTEGER REFERENCES sources(id),
    video_id        TEXT NOT NULL UNIQUE,
    title           TEXT NOT NULL,
    duration        INTEGER,
    channel_name    TEXT,
    published_at    TEXT,
    segment_count   INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_transcripts_video_id ON transcripts(video_id);

CREATE TABLE IF NOT EXISTS transcript_segments (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    transcript_id   INTEGER NOT NULL REFERENCES transcripts(id) ON DELETE CASCADE,
    text            TEXT NOT NULL,
    start_time      REAL NOT NULL,
    duration        REAL NOT NULL,
    segment_index   INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_segments_transcript ON transcript_segments(transcript_id);

CREATE TABLE IF NOT EXISTS suggestions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    url             TEXT NOT NULL,
    normalized_url  TEXT NOT NULL,
    user_fingerprint TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'rejected', 'auto_approved')),
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_suggestions_normalized ON suggestions(normalized_url);

CREATE TABLE IF NOT EXISTS news_articles (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    title               TEXT NOT NULL,
    content             TEXT NOT NULL,
    summary             TEXT,
    sources_referenced  TEXT,
    generated_date      TEXT NOT NULL,
    created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_news_date ON news_articles(generated_date);

CREATE TABLE IF NOT EXISTS admins (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    email           TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS search_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    query           TEXT NOT NULL,
    result_count    INTEGER,
    ip_address      TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_search_log_date ON search_log(created_at);
"""


def get_connection():
    """Get a thread-local SQLite connection."""
    if not hasattr(_local, "connection") or _local.connection is None:
        db_path = config.DATA_DIR / "sunosmart.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _local.connection = conn
    return _local.connection


def initialize_db():
    """Create tables if they don't exist."""
    conn = get_connection()
    conn.executescript(SCHEMA_SQL)
    row = conn.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
    if row is None:
        conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
    conn.commit()


# --- Source Queries ---

def create_source(source_type, url, channel_id=None, channel_name=None, added_by="manual"):
    conn = get_connection()
    conn.execute(
        """INSERT OR IGNORE INTO sources (type, url, channel_id, channel_name, added_by)
           VALUES (?, ?, ?, ?, ?)""",
        (source_type, url, channel_id, channel_name, added_by)
    )
    conn.commit()
    return conn.execute("SELECT * FROM sources WHERE url = ?", (url,)).fetchone()


def get_active_sources(source_type=None):
    conn = get_connection()
    if source_type:
        return conn.execute(
            "SELECT * FROM sources WHERE status = 'active' AND type = ?", (source_type,)
        ).fetchall()
    return conn.execute("SELECT * FROM sources WHERE status = 'active'").fetchall()


def update_source_scanned(source_id):
    conn = get_connection()
    conn.execute(
        "UPDATE sources SET last_scanned_at = datetime('now'), updated_at = datetime('now') WHERE id = ?",
        (source_id,)
    )
    conn.commit()


# --- Transcript Queries ---

def create_transcript(source_id, video_id, title, duration, channel_name=None, segment_count=0):
    conn = get_connection()
    conn.execute(
        """INSERT OR IGNORE INTO transcripts (source_id, video_id, title, duration, channel_name, segment_count)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (source_id, video_id, title, duration, channel_name, segment_count)
    )
    conn.commit()
    return conn.execute("SELECT * FROM transcripts WHERE video_id = ?", (video_id,)).fetchone()


def get_transcript_by_video_id(video_id):
    conn = get_connection()
    return conn.execute("SELECT * FROM transcripts WHERE video_id = ?", (video_id,)).fetchone()


def get_all_transcripts():
    conn = get_connection()
    return conn.execute("SELECT * FROM transcripts ORDER BY created_at DESC").fetchall()


def get_transcripts_since(since_datetime):
    conn = get_connection()
    return conn.execute(
        "SELECT * FROM transcripts WHERE created_at >= ? ORDER BY created_at DESC",
        (since_datetime,)
    ).fetchall()


# --- Segment Queries ---

def insert_segments(transcript_id, segments):
    """Bulk insert transcript segments."""
    conn = get_connection()
    conn.executemany(
        """INSERT INTO transcript_segments (transcript_id, text, start_time, duration, segment_index)
           VALUES (?, ?, ?, ?, ?)""",
        [(transcript_id, s["text"], s["start"], s["duration"], i) for i, s in enumerate(segments)]
    )
    conn.commit()


def get_segments_for_transcript(transcript_id):
    conn = get_connection()
    return conn.execute(
        "SELECT * FROM transcript_segments WHERE transcript_id = ? ORDER BY segment_index",
        (transcript_id,)
    ).fetchall()


def get_all_segments_with_video_info():
    """Get all segments joined with their transcript info for search."""
    conn = get_connection()
    return conn.execute("""
        SELECT ts.id, ts.text, ts.start_time, ts.duration, ts.segment_index,
               ts.transcript_id, t.video_id, t.title as video_title, t.duration as video_duration
        FROM transcript_segments ts
        JOIN transcripts t ON t.id = ts.transcript_id
        ORDER BY t.id, ts.segment_index
    """).fetchall()


# --- Suggestion Queries ---

def create_suggestion(url, normalized_url, ip_address, user_agent):
    fingerprint = hashlib.sha256(f"{ip_address}:{user_agent}".encode()).hexdigest()[:16]
    conn = get_connection()
    existing = conn.execute(
        "SELECT id FROM suggestions WHERE normalized_url = ? AND user_fingerprint = ?",
        (normalized_url, fingerprint)
    ).fetchone()
    if existing:
        return None, "already_suggested"
    conn.execute(
        "INSERT INTO suggestions (url, normalized_url, user_fingerprint) VALUES (?, ?, ?)",
        (url, normalized_url, fingerprint)
    )
    conn.commit()
    count = conn.execute(
        "SELECT COUNT(DISTINCT user_fingerprint) as cnt FROM suggestions WHERE normalized_url = ? AND status = 'pending'",
        (normalized_url,)
    ).fetchone()["cnt"]
    return count, "ok"


def get_suggestion_counts():
    conn = get_connection()
    return conn.execute("""
        SELECT normalized_url, MIN(url) as sample_url,
               COUNT(DISTINCT user_fingerprint) as unique_users,
               MIN(created_at) as first_suggested,
               MAX(created_at) as last_suggested
        FROM suggestions WHERE status = 'pending'
        GROUP BY normalized_url
        ORDER BY unique_users DESC
    """).fetchall()


def approve_suggestion(normalized_url):
    conn = get_connection()
    conn.execute(
        "UPDATE suggestions SET status = 'approved' WHERE normalized_url = ?",
        (normalized_url,)
    )
    conn.commit()


def auto_approve_suggestion(normalized_url):
    conn = get_connection()
    conn.execute(
        "UPDATE suggestions SET status = 'auto_approved' WHERE normalized_url = ?",
        (normalized_url,)
    )
    conn.commit()


# --- News Queries ---

def create_news_article(title, content, summary=None, sources_referenced=None, generated_date=None):
    conn = get_connection()
    if generated_date is None:
        generated_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    conn.execute(
        """INSERT INTO news_articles (title, content, summary, sources_referenced, generated_date)
           VALUES (?, ?, ?, ?, ?)""",
        (title, content, summary, sources_referenced, generated_date)
    )
    conn.commit()


def get_latest_news(limit=3):
    conn = get_connection()
    return conn.execute(
        "SELECT * FROM news_articles ORDER BY generated_date DESC, id DESC LIMIT ?",
        (limit,)
    ).fetchall()


def get_news_archive(page=1, per_page=10):
    conn = get_connection()
    offset = (page - 1) * per_page
    articles = conn.execute(
        "SELECT * FROM news_articles ORDER BY generated_date DESC, id DESC LIMIT ? OFFSET ?",
        (per_page, offset)
    ).fetchall()
    total = conn.execute("SELECT COUNT(*) as cnt FROM news_articles").fetchone()["cnt"]
    return articles, total


def get_news_article(article_id):
    conn = get_connection()
    return conn.execute("SELECT * FROM news_articles WHERE id = ?", (article_id,)).fetchone()


# --- Admin Queries ---

def get_admin_by_email(email):
    conn = get_connection()
    return conn.execute("SELECT * FROM admins WHERE email = ?", (email,)).fetchone()


def create_admin(email, password_hash):
    conn = get_connection()
    conn.execute(
        "INSERT INTO admins (email, password_hash) VALUES (?, ?)",
        (email, password_hash)
    )
    conn.commit()


# --- Search Log ---

def log_search(query, result_count, ip_address):
    conn = get_connection()
    conn.execute(
        "INSERT INTO search_log (query, result_count, ip_address) VALUES (?, ?, ?)",
        (query, result_count, ip_address)
    )
    conn.commit()


def get_search_stats():
    conn = get_connection()
    return conn.execute("""
        SELECT COUNT(*) as total_searches,
               COUNT(DISTINCT query) as unique_queries,
               COUNT(DISTINCT ip_address) as unique_users
        FROM search_log
    """).fetchone()
