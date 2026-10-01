# mattermost-channel-archiver

Mattermost の特定チャンネルのログ(投稿・添付ファイル)をローカルにエクスポートし、ブラウザで閲覧・全文検索するためのツールです。

## セットアップ

`.env` に以下を設定済みであること:

```
MATTERMOST_URL=https://your-mattermost-server
MATTERMOST_TOKEN=xxxxxxxx
CHANNEL_ID=xxxxxxxx
```

依存パッケージは `uv sync` で導入されます(既に導入済み)。

## エクスポート

```sh
uv run mm-export
```

`.env` の `CHANNEL_ID` のチャンネルの全投稿と添付ファイルを取得し、`data/mattermost_log.db` (SQLite) と `data/attachments/` 以下に保存します。再実行すると差分のみ更新されます(同じファイルは再ダウンロードしません)。

`--channel-id` で `.env` の値を一時的に上書きし、別チャンネルをエクスポートすることもできます:

```sh
uv run mm-export --channel-id xxxxxxxx
```

## 閲覧・検索

```sh
uv run mm-view
```

デフォルトではポート 5000 で起動します。起動後 http://127.0.0.1:5000 をブラウザで開くと、投稿一覧・キーワード検索(日本語は2文字以上、英数字などは3文字以上で高速検索)・ユーザー絞り込み・日付範囲での絞り込みができます。画像添付はサムネイル表示、その他のファイルはダウンロードリンクになります。

ポートを変更したい場合は `--port` オプションを指定します:

```sh
uv run mm-view --port 5050
```

## DB テーブル構成・SQLでの直接検索

`data/mattermost_log.db` のテーブル構成や、`sqlite3` コマンドから直接SQLで検索する方法は [docs/database.md](docs/database.md) を参照してください。

---

## 参考
- [Mattermostの特定のチャンネルをexportする方法](https://zenn.dev/minervajuppiter/articles/d5965a4a1323b2)
- [mattermost-exporter](https://github.com/Mekann2904/mattermost-exporter)
