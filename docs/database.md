# DB テーブル構成とSQLでの直接検索

エクスポート先は `data/mattermost_log.db` (SQLite) です。ビューワ(`mm-view`)を使わず、テーブル構造を直接知りたい場合や `sqlite3` コマンドで検索したい場合のリファレンスです。

## テーブル構成

### `posts` — 投稿本体

| カラム      | 型      | 内容                                   |
|-------------|---------|----------------------------------------|
| id          | TEXT PK | 投稿ID                                 |
| channel_id  | TEXT    | チャンネルID                           |
| user_id     | TEXT    | 投稿者ID (`users.id` を参照)           |
| root_id     | TEXT    | スレッド親投稿のID (返信でなければ空)  |
| create_at   | INTEGER | 作成日時 (UNIX時間・ミリ秒)            |
| update_at   | INTEGER | 更新日時 (ミリ秒)                      |
| edit_at     | INTEGER | 編集日時 (ミリ秒、未編集なら0)         |
| delete_at   | INTEGER | 削除日時 (ミリ秒、未削除なら0)         |
| type        | TEXT    | 投稿種別 (通常投稿は空文字)            |
| message     | TEXT    | 本文                                   |

### `users` — 投稿者情報

| カラム     | 型      | 内容            |
|------------|---------|-----------------|
| id         | TEXT PK | ユーザーID      |
| username   | TEXT    | ユーザー名      |
| nickname   | TEXT    | ニックネーム    |
| first_name | TEXT    | 名              |
| last_name  | TEXT    | 姓              |

### `files` — 添付ファイル情報

| カラム      | 型      | 内容                                                  |
|-------------|---------|--------------------------------------------------------|
| id          | TEXT PK | ファイルID                                            |
| post_id     | TEXT    | 添付元の投稿ID (`posts.id` を参照)                    |
| name        | TEXT    | 元のファイル名                                        |
| extension   | TEXT    | 拡張子                                                 |
| size        | INTEGER | サイズ (バイト)                                       |
| mime_type   | TEXT    | MIMEタイプ                                            |
| local_path  | TEXT    | `data/attachments/` からの相対パス                    |

### `channels` — チャンネル情報

| カラム       | 型      | 内容            |
|--------------|---------|-----------------|
| id           | TEXT PK | チャンネルID    |
| name         | TEXT    | チャンネル名    |
| display_name | TEXT    | 表示名          |
| team_id      | TEXT    | チームID        |

### `posts_fts` — 全文検索用 (FTS5 virtual table)

`posts.message` を `trigram` トークナイザーでインデックス化したものです(ビューワの3文字以上の検索で使用)。`posts` への書き込み時にトリガーで自動更新されるため、直接書き込む必要はありません。

## ターミナルから直接 SQL で検索する

追加のライブラリなしで、OS 標準 (または Homebrew 等で導入済み) の `sqlite3` コマンドラインツールからも検索できます。

```sh
# メッセージ本文にキーワードを含む投稿を検索 (3文字以上、FTS5 trigram を利用)
sqlite3 -header -column data/mattermost_log.db "
SELECT datetime(p.create_at/1000, 'unixepoch', 'localtime') AS time,
       u.username,
       p.message
FROM posts p
LEFT JOIN users u ON u.id = p.user_id
WHERE p.rowid IN (
  SELECT rowid FROM posts_fts WHERE posts_fts MATCH '\"授業検討\"'
)
ORDER BY p.create_at DESC;
"

# 2文字以下のキーワードなど、単純な部分一致で検索したい場合は LIKE を使う
sqlite3 -header -column data/mattermost_log.db "
SELECT datetime(p.create_at/1000, 'unixepoch', 'localtime') AS time,
       u.username,
       p.message
FROM posts p
LEFT JOIN users u ON u.id = p.user_id
WHERE p.message LIKE '%授業%'
ORDER BY p.create_at DESC;
"

# 特定ユーザーの投稿に紐づく添付ファイル一覧
sqlite3 -header -column data/mattermost_log.db "
SELECT datetime(p.create_at/1000, 'unixepoch', 'localtime') AS time,
       f.name, f.size, f.local_path
FROM files f
JOIN posts p ON p.id = f.post_id
JOIN users u ON u.id = p.user_id
WHERE u.username = 'tnal'
ORDER BY p.create_at DESC;
"
```

`sqlite3` が未導入の環境では `brew install sqlite` で導入できます(macOS 標準でも `/usr/bin/sqlite3` として同梱されていることが多いです)。
