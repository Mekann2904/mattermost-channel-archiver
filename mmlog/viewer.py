"""エクスポート済みの Mattermost ログをブラウザで閲覧・検索するビューワ。

使い方:
    uv run mm-view [--port 5000] [--host 127.0.0.1]
    ブラウザで http://127.0.0.1:5000 を開く
"""

from __future__ import annotations

import argparse
import re
import sqlite3
from datetime import datetime
from pathlib import Path

from flask import Flask, g, render_template, request, send_from_directory
from markupsafe import Markup, escape

from .config import ATTACHMENTS_DIR, DB_PATH

PAGE_SIZE = 50

app = Flask(__name__)

_URL_RE = re.compile(r"(https?://[^\s<>\"]+)")


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        if not DB_PATH.exists():
            raise RuntimeError(
                f"{DB_PATH} が見つかりません。先に `uv run mm-export` を実行してください。"
            )
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        g.db = conn
    return g.db


@app.teardown_appcontext
def close_db(_exc: BaseException | None) -> None:
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


@app.template_filter("datetime")
def format_datetime(value_ms: int) -> str:
    if not value_ms:
        return ""
    return datetime.fromtimestamp(value_ms / 1000).strftime("%Y-%m-%d %H:%M:%S")


def _highlight(segment: str, pattern: re.Pattern[str] | None) -> str:
    if pattern is None:
        return segment
    return pattern.sub(lambda m: f"<mark>{m.group(0)}</mark>", segment)


@app.template_filter("render_message")
def render_message(text: str, query: str = "") -> Markup:
    escaped = str(escape(text or ""))

    pattern = None
    query = (query or "").strip()
    if query:
        pattern = re.compile(re.escape(query), re.IGNORECASE)

    # URL をリンク化する際、リンクの href 属性自体はハイライト対象にせず
    # 表示テキスト部分にのみハイライトをかける
    parts: list[str] = []
    last_end = 0
    for m in _URL_RE.finditer(escaped):
        parts.append(_highlight(escaped[last_end : m.start()], pattern))
        url = m.group(1)
        parts.append(
            f'<a href="{url}" target="_blank" rel="noopener">'
            f"{_highlight(url, pattern)}</a>"
        )
        last_end = m.end()
    parts.append(_highlight(escaped[last_end:], pattern))

    html = "".join(parts)
    return Markup(html.replace("\n", "<br>"))


@app.template_filter("filesize")
def filesize(num_bytes: int) -> str:
    size = float(num_bytes or 0)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.0f}{unit}" if unit == "B" else f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


def _display_name(row: sqlite3.Row) -> str:
    if row is None:
        return "(unknown)"
    return row["nickname"] or row["username"] or row["user_id"] or "(unknown)"


@app.route("/")
def index():
    db = get_db()

    q = request.args.get("q", "").strip()
    user_filter = request.args.get("user", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    page = max(int(request.args.get("page", 1) or 1), 1)

    conditions = ["p.delete_at = 0"]
    params: list = []

    if q:
        if len(q) >= 3:
            # trigram トークナイザーはクエリ構文(AND/OR/演算子等)と衝突しうる記号を
            # 含む自由入力を扱うため、常にフレーズクエリとしてクォートして渡す
            fts_query = '"' + q.replace('"', '""') + '"'
            conditions.append(
                "p.rowid IN (SELECT rowid FROM posts_fts WHERE posts_fts MATCH ?)"
            )
            params.append(fts_query)
        else:
            # trigram は3文字未満のクエリにマッチできないため LIKE にフォールバック
            escaped = (
                q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            )
            conditions.append("p.message LIKE ? ESCAPE '\\'")
            params.append(f"%{escaped}%")

    if user_filter:
        conditions.append("(u.username = ? OR u.nickname = ?)")
        params.extend([user_filter, user_filter])

    if date_from:
        params.append(int(datetime.strptime(date_from, "%Y-%m-%d").timestamp() * 1000))
        conditions.append("p.create_at >= ?")

    if date_to:
        params.append(
            int(datetime.strptime(date_to, "%Y-%m-%d").timestamp() * 1000) + 86_400_000
        )
        conditions.append("p.create_at < ?")

    where_clause = " AND ".join(conditions)

    total = db.execute(
        f"""
        SELECT COUNT(*) FROM posts p
        LEFT JOIN users u ON u.id = p.user_id
        WHERE {where_clause}
        """,
        params,
    ).fetchone()[0]

    rows = db.execute(
        f"""
        SELECT p.*, u.username, u.nickname
        FROM posts p
        LEFT JOIN users u ON u.id = p.user_id
        WHERE {where_clause}
        ORDER BY p.create_at DESC
        LIMIT ? OFFSET ?
        """,
        [*params, PAGE_SIZE, (page - 1) * PAGE_SIZE],
    ).fetchall()

    post_ids = [row["id"] for row in rows]
    files_by_post: dict[str, list[sqlite3.Row]] = {}
    if post_ids:
        placeholders = ",".join("?" for _ in post_ids)
        for frow in db.execute(
            f"SELECT * FROM files WHERE post_id IN ({placeholders})", post_ids
        ):
            files_by_post.setdefault(frow["post_id"], []).append(frow)

    users = db.execute(
        "SELECT DISTINCT username FROM users WHERE username IS NOT NULL ORDER BY username"
    ).fetchall()

    total_pages = max((total + PAGE_SIZE - 1) // PAGE_SIZE, 1)

    return render_template(
        "index.html",
        rows=rows,
        files_by_post=files_by_post,
        display_name=_display_name,
        users=users,
        q=q,
        user_filter=user_filter,
        date_from=date_from,
        date_to=date_to,
        page=page,
        total=total,
        total_pages=total_pages,
    )


@app.route("/attachments/<path:filepath>")
def attachment(filepath: str):
    return send_from_directory(ATTACHMENTS_DIR, filepath)


def main() -> None:
    parser = argparse.ArgumentParser(description="Mattermost ログビューワ")
    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="待受ポート番号 (デフォルト: 5000)。"
        " macOS では AirPlay Receiver が 5000 番を使っていることがあるので、"
        " その場合は --port 5050 のように変更してください。",
    )
    parser.add_argument(
        "--host", default="127.0.0.1", help="待受ホスト (デフォルト: 127.0.0.1)"
    )
    args = parser.parse_args()
    app.run(debug=True, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
