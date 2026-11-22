"""SQLite storage and forward-only migrations for TugmaBot."""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import timedelta
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator


DATABASE_PATH = Path(os.getenv("DATABASE_PATH", "tugmabot.db")).expanduser()
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DATABASE_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with connect() as db:
        db.execute("PRAGMA journal_mode = WAL")
        db.execute("""CREATE TABLE IF NOT EXISTS users(
            user_id INTEGER PRIMARY KEY, qoida TEXT, viloyat TEXT, elon TEXT,
            matnlink TEXT
        )""")
        columns = {row["name"] for row in db.execute("PRAGMA table_info(users)")}
        for column in ("qoida", "viloyat", "elon", "matnlink"):
            if column not in columns:
                db.execute(f"ALTER TABLE users ADD COLUMN {column} TEXT")

        db.executescript("""
        CREATE TABLE IF NOT EXISTS regions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE COLLATE NOCASE,
            active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            region_id INTEGER NOT NULL REFERENCES regions(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            telegram_id TEXT NOT NULL UNIQUE,
            active INTEGER NOT NULL DEFAULT 1,
            can_post INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS scheduled_posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER NOT NULL,
            text TEXT NOT NULL DEFAULT '',
            photo_file_id TEXT,
            schedule_type TEXT NOT NULL CHECK(schedule_type IN ('once','daily','weekly')),
            run_at TEXT,
            weekdays TEXT NOT NULL DEFAULT '[]',
            run_time TEXT,
            interval_days INTEGER NOT NULL DEFAULT 1,
            occurrences_total INTEGER,
            occurrences_sent INTEGER NOT NULL DEFAULT 0,
            next_run_at TEXT,
            last_occurrence_key TEXT,
            timezone TEXT NOT NULL DEFAULT 'Asia/Tashkent',
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS scheduled_post_channels (
            post_id INTEGER NOT NULL REFERENCES scheduled_posts(id) ON DELETE CASCADE,
            channel_id INTEGER NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
            PRIMARY KEY(post_id, channel_id)
        );
        CREATE TABLE IF NOT EXISTS published_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL REFERENCES scheduled_posts(id) ON DELETE CASCADE,
            channel_id INTEGER NOT NULL REFERENCES channels(id) ON DELETE CASCADE,
            telegram_chat_id TEXT,
            occurrence_key TEXT NOT NULL,
            telegram_message_id INTEGER,
            is_photo INTEGER NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'sending',
            error TEXT,
            published_at TEXT,
            UNIQUE(post_id, channel_id, occurrence_key)
        );
        CREATE INDEX IF NOT EXISTS idx_posts_admin_status
            ON scheduled_posts(admin_id, status);
        """)
        published_columns = {row["name"] for row in db.execute("PRAGMA table_info(published_messages)")}
        if "telegram_chat_id" not in published_columns:
            db.execute("ALTER TABLE published_messages ADD COLUMN telegram_chat_id TEXT")
            db.execute("UPDATE published_messages SET telegram_chat_id=(SELECT telegram_id FROM channels WHERE channels.id=published_messages.channel_id)")
        if "is_photo" not in published_columns:
            db.execute("ALTER TABLE published_messages ADD COLUMN is_photo INTEGER NOT NULL DEFAULT 0")
        post_columns = {row["name"] for row in db.execute("PRAGMA table_info(scheduled_posts)")}
        migrations = {
            "interval_days": "INTEGER NOT NULL DEFAULT 1",
            "occurrences_total": "INTEGER",
            "occurrences_sent": "INTEGER NOT NULL DEFAULT 0",
            "next_run_at": "TEXT",
            "last_occurrence_key": "TEXT",
        }
        for column, definition in migrations.items():
            if column not in post_columns:
                db.execute(f"ALTER TABLE scheduled_posts ADD COLUMN {column} {definition}")


def backup_database(retain_days: int = 7) -> Path | None:
    if not DATABASE_PATH.exists():
        return None
    backup_dir = DATABASE_PATH.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    target = backup_dir / f"tugmabot-{stamp}.sqlite3"
    source = sqlite3.connect(DATABASE_PATH)
    destination = sqlite3.connect(target)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    cutoff = time.time() - timedelta(days=retain_days).total_seconds()
    for old_file in backup_dir.glob("tugmabot-*.sqlite3"):
        if old_file.stat().st_mtime < cutoff:
            old_file.unlink()
    return target


def get_links(user_id: int) -> tuple[str | None, str | None, str | None, str | None]:
    with connect() as db:
        row = db.execute(
            "SELECT qoida, viloyat, elon, matnlink FROM users WHERE user_id=?",
            (user_id,),
        ).fetchone()
    return tuple(row) if row else (None, None, None, None)


def set_link(user_id: int, field: str, value: str | None) -> None:
    if field not in {"qoida", "viloyat", "elon", "matnlink"}:
        raise ValueError("Unsupported link setting")
    with connect() as db:
        db.execute("INSERT OR IGNORE INTO users(user_id) VALUES(?)", (user_id,))
        db.execute(f"UPDATE users SET {field}=? WHERE user_id=?", (value, user_id))


def list_regions():
    with connect() as db:
        return db.execute("SELECT * FROM regions WHERE active=1 ORDER BY name").fetchall()


def add_channel(region: str, name: str, telegram_id: str) -> None:
    with connect() as db:
        db.execute("INSERT OR IGNORE INTO regions(name) VALUES(?)", (region.strip(),))
        row = db.execute("SELECT id FROM regions WHERE name=? COLLATE NOCASE", (region.strip(),)).fetchone()
        db.execute(
            "INSERT INTO channels(region_id,name,telegram_id) VALUES(?,?,?)",
            (row["id"], name.strip(), telegram_id.strip()),
        )


def update_channel(channel_id: int, region: str, name: str, telegram_id: str, can_post: bool) -> None:
    with connect() as db:
        db.execute("INSERT OR IGNORE INTO regions(name) VALUES(?)", (region.strip(),))
        row = db.execute("SELECT id FROM regions WHERE name=? COLLATE NOCASE", (region.strip(),)).fetchone()
        db.execute("UPDATE channels SET region_id=?,name=?,telegram_id=?,can_post=? WHERE id=?",
                   (row["id"], name.strip(), telegram_id.strip(), int(can_post), channel_id))


def channels_for_region(region_id: int, active_only: bool = True):
    sql = "SELECT c.*, r.name AS region_name FROM channels c JOIN regions r ON r.id=c.region_id WHERE c.region_id=?"
    if active_only:
        sql += " AND c.active=1 AND c.can_post=1"
    sql += " ORDER BY c.name"
    with connect() as db:
        return db.execute(sql, (region_id,)).fetchall()


def all_channels():
    with connect() as db:
        return db.execute("SELECT c.*, r.name AS region_name FROM channels c JOIN regions r ON r.id=c.region_id ORDER BY r.name,c.name").fetchall()


def set_channel_status(channel_id: int, active: bool, can_post: bool | None = None) -> None:
    with connect() as db:
        if can_post is None:
            db.execute("UPDATE channels SET active=? WHERE id=?", (int(active), channel_id))
        else:
            db.execute("UPDATE channels SET active=?,can_post=? WHERE id=?", (int(active), int(can_post), channel_id))


def delete_channel(channel_id: int) -> None:
    with connect() as db:
        # Retain channel rows so previously published Telegram message IDs stay usable.
        db.execute("UPDATE channels SET active=0 WHERE id=?", (channel_id,))


def create_post(admin_id: int, text: str, photo_file_id: str | None, schedule_type: str,
                channel_ids: list[int], run_at: str | None = None,
                weekdays: list[int] | None = None, run_time: str | None = None,
                occurrences_total: int | None = None, interval_days: int = 1,
                next_run_at: str | None = None) -> int:
    with connect() as db:
        cur = db.execute(
            "INSERT INTO scheduled_posts(admin_id,text,photo_file_id,schedule_type,run_at,weekdays,run_time,status,occurrences_total,interval_days,next_run_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (admin_id, text, photo_file_id, schedule_type, run_at,
             json.dumps(weekdays or []), run_time, "pending" if schedule_type == "once" else "active",
             occurrences_total, interval_days, next_run_at),
        )
        post_id = cur.lastrowid
        db.executemany("INSERT INTO scheduled_post_channels(post_id,channel_id) VALUES(?,?)",
                       [(post_id, cid) for cid in channel_ids])
        return post_id


def list_posts(admin_id: int):
    with connect() as db:
        return db.execute("SELECT * FROM scheduled_posts WHERE admin_id=? ORDER BY id DESC", (admin_id,)).fetchall()


def get_post(post_id: int, admin_id: int):
    with connect() as db:
        post = db.execute("SELECT * FROM scheduled_posts WHERE id=? AND admin_id=?", (post_id, admin_id)).fetchone()
        if not post:
            return None, []
        channels = db.execute("SELECT c.* FROM channels c JOIN scheduled_post_channels pc ON pc.channel_id=c.id WHERE pc.post_id=?", (post_id,)).fetchall()
    return post, channels


def update_post_status(post_id: int, admin_id: int, status: str) -> bool:
    with connect() as db:
        cur = db.execute("UPDATE scheduled_posts SET status=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND admin_id=?", (status, post_id, admin_id))
        return cur.rowcount > 0


def delete_post(post_id: int, admin_id: int) -> bool:
    with connect() as db:
        cur = db.execute("DELETE FROM scheduled_posts WHERE id=? AND admin_id=?", (post_id, admin_id))
        return cur.rowcount > 0


def update_post_content(post_id: int, admin_id: int, text: str | None = None,
                        photo_file_id: str | None = None, update_photo: bool = False) -> bool:
    with connect() as db:
        if update_photo:
            cur = db.execute("UPDATE scheduled_posts SET text=?,photo_file_id=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND admin_id=?",
                             (text or "", photo_file_id, post_id, admin_id))
        else:
            cur = db.execute("UPDATE scheduled_posts SET text=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND admin_id=?",
                             (text or "", post_id, admin_id))
        return cur.rowcount > 0


def update_post_time(post_id: int, admin_id: int, run_at: str | None = None,
                     weekdays: list[int] | None = None, run_time: str | None = None,
                     next_run_at: str | None = None) -> bool:
    with connect() as db:
        cur = db.execute("UPDATE scheduled_posts SET run_at=COALESCE(?,run_at),weekdays=COALESCE(?,weekdays),run_time=COALESCE(?,run_time),next_run_at=COALESCE(?,next_run_at),status=?,updated_at=CURRENT_TIMESTAMP WHERE id=? AND admin_id=?",
                         (run_at, json.dumps(weekdays) if weekdays is not None else None,
                          run_time, next_run_at, "pending" if run_at is not None else "active", post_id, admin_id))
        return cur.rowcount > 0


def advance_limited_post(post_id: int, occurrence_key: str):
    """Advance a finite campaign exactly once for each completed occurrence."""
    with connect() as db:
        post = db.execute("SELECT * FROM scheduled_posts WHERE id=?", (post_id,)).fetchone()
        if not post or post["last_occurrence_key"] == occurrence_key:
            return None
        sent = int(post["occurrences_sent"] or 0) + 1
        total = int(post["occurrences_total"] or 0)
        if sent >= total:
            db.execute("UPDATE scheduled_posts SET occurrences_sent=?,last_occurrence_key=?,next_run_at=NULL,status='published',updated_at=CURRENT_TIMESTAMP WHERE id=?",
                       (sent, occurrence_key, post_id))
        else:
            current = datetime.fromisoformat(occurrence_key)
            next_run = current + timedelta(days=int(post["interval_days"] or 1))
            db.execute("UPDATE scheduled_posts SET occurrences_sent=?,last_occurrence_key=?,next_run_at=?,status='active',updated_at=CURRENT_TIMESTAMP WHERE id=?",
                       (sent, occurrence_key, next_run.isoformat(), post_id))
        return db.execute("SELECT * FROM scheduled_posts WHERE id=?", (post_id,)).fetchone()


def replace_post_channels(post_id: int, admin_id: int, channel_ids: list[int]) -> bool:
    with connect() as db:
        exists = db.execute("SELECT 1 FROM scheduled_posts WHERE id=? AND admin_id=?", (post_id, admin_id)).fetchone()
        if not exists:
            return False
        db.execute("DELETE FROM scheduled_post_channels WHERE post_id=?", (post_id,))
        db.executemany("INSERT INTO scheduled_post_channels(post_id,channel_id) VALUES(?,?)",
                       [(post_id, channel_id) for channel_id in channel_ids])
        return True


def published_messages(post_id: int):
    with connect() as db:
        return db.execute("SELECT pm.*,COALESCE(pm.telegram_chat_id,c.telegram_id) AS telegram_id FROM published_messages pm JOIN channels c ON c.id=pm.channel_id WHERE pm.post_id=? AND pm.status='sent' AND pm.telegram_message_id IS NOT NULL ORDER BY pm.id",
                          (post_id,)).fetchall()


def update_published_message(row_id: int, message_id: int, is_photo: bool) -> None:
    with connect() as db:
        db.execute("UPDATE published_messages SET telegram_message_id=?,is_photo=? WHERE id=?",
                   (message_id, int(is_photo), row_id))


def claim_delivery(post_id: int, channel_id: int, occurrence_key: str) -> bool:
    """Persist a claim before the Telegram call, preventing restart duplicates."""
    with connect() as db:
        try:
            db.execute("INSERT INTO published_messages(post_id,channel_id,occurrence_key,status) VALUES(?,?,?,'sending')",
                       (post_id, channel_id, occurrence_key))
            return True
        except sqlite3.IntegrityError:
            return False


def delivery_was_sent(post_id: int, channel_id: int, occurrence_key: str) -> bool:
    with connect() as db:
        row = db.execute("SELECT status FROM published_messages WHERE post_id=? AND channel_id=? AND occurrence_key=?",
                         (post_id, channel_id, occurrence_key)).fetchone()
    return bool(row and row["status"] == "sent")


def finish_delivery(post_id: int, channel_id: int, occurrence_key: str,
                    message_id: int | None = None, error: str | None = None,
                    is_photo: bool = False, telegram_chat_id: str | None = None) -> None:
    with connect() as db:
        db.execute("UPDATE published_messages SET telegram_message_id=?,is_photo=?,telegram_chat_id=?,status=?,error=?,published_at=? WHERE post_id=? AND channel_id=? AND occurrence_key=?",
                   (message_id, int(is_photo), telegram_chat_id, "sent" if error is None else "error", error,
                    datetime.now().isoformat() if error is None else None,
                    post_id, channel_id, occurrence_key))


def set_post_result(post_id: int, status: str) -> None:
    with connect() as db:
        db.execute("UPDATE scheduled_posts SET status=?,updated_at=CURRENT_TIMESTAMP WHERE id=?", (status, post_id))
