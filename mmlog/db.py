"""SQLite (FTS5) によるローカルデータストア。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS channels (
    id TEXT PRIMARY KEY,
    name TEXT,
    display_name TEXT,
    team_id TEXT
);

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT,
    nickname TEXT,
    first_name TEXT,
    last_name TEXT
);

CREATE TABLE IF NOT EXISTS posts (
    id TEXT PRIMARY KEY,
    channel_id TEXT,
    user_id TEXT,
    root_id TEXT,
    create_at INTEGER,
    update_at INTEGER,
    edit_at INTEGER,
    delete_at INTEGER,
    type TEXT,
    message TEXT
);
CREATE INDEX IF NOT EXISTS idx_posts_create_at ON posts (create_at);
CREATE INDEX IF NOT EXISTS idx_posts_user_id ON posts (user_id);

CREATE TABLE IF NOT EXISTS files (
    id TEXT PRIMARY KEY,
    post_id TEXT,
    name TEXT,
    extension TEXT,
    size INTEGER,
    mime_type TEXT,
    local_path TEXT
);
CREATE INDEX IF NOT EXISTS idx_files_post_id ON files (post_id);

-- trigram トークナイザーを使用: 日本語など単語分割できない言語でも
-- 部分一致検索ができる (3文字以上のクエリが対象)
CREATE VIRTUAL TABLE IF NOT EXISTS posts_fts USING fts5 (
    message,
    content='posts',
    content_rowid='rowid',
    tokenize='trigram'
);

CREATE TRIGGER IF NOT EXISTS posts_ai AFTER INSERT ON posts BEGIN
    INSERT INTO posts_fts(rowid, message) VALUES (new.rowid, new.message);
END;
CREATE TRIGGER IF NOT EXISTS posts_ad AFTER DELETE ON posts BEGIN
    INSERT INTO posts_fts(posts_fts, rowid, message) VALUES ('delete', old.rowid, old.message);
END;
CREATE TRIGGER IF NOT EXISTS posts_au AFTER UPDATE ON posts BEGIN
    INSERT INTO posts_fts(posts_fts, rowid, message) VALUES ('delete', old.rowid, old.message);
    INSERT INTO posts_fts(rowid, message) VALUES (new.rowid, new.message);
END;
"""


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def upsert_channel(conn: sqlite3.Connection, channel: dict) -> None:
    conn.execute(
        """
        INSERT INTO channels (id, name, display_name, team_id)
        VALUES (:id, :name, :display_name, :team_id)
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name,
            display_name=excluded.display_name,
            team_id=excluded.team_id
        """,
        channel,
    )


def upsert_user(conn: sqlite3.Connection, user: dict) -> None:
    conn.execute(
        """
        INSERT INTO users (id, username, nickname, first_name, last_name)
        VALUES (:id, :username, :nickname, :first_name, :last_name)
        ON CONFLICT(id) DO UPDATE SET
            username=excluded.username,
            nickname=excluded.nickname,
            first_name=excluded.first_name,
            last_name=excluded.last_name
        """,
        user,
    )


def upsert_post(conn: sqlite3.Connection, post: dict) -> None:
    # 既存行があれば FTS トリガーが正しく追従するよう一旦 DELETE してから INSERT する
    conn.execute("DELETE FROM posts WHERE id = ?", (post["id"],))
    conn.execute(
        """
        INSERT INTO posts
            (id, channel_id, user_id, root_id, create_at, update_at, edit_at, delete_at, type, message)
        VALUES
            (:id, :channel_id, :user_id, :root_id, :create_at, :update_at, :edit_at, :delete_at, :type, :message)
        """,
        post,
    )


def upsert_file(conn: sqlite3.Connection, file_row: dict) -> None:
    conn.execute(
        """
        INSERT INTO files (id, post_id, name, extension, size, mime_type, local_path)
        VALUES (:id, :post_id, :name, :extension, :size, :mime_type, :local_path)
        ON CONFLICT(id) DO UPDATE SET
            post_id=excluded.post_id,
            name=excluded.name,
            extension=excluded.extension,
            size=excluded.size,
            mime_type=excluded.mime_type,
            local_path=excluded.local_path
        """,
        file_row,
    )
