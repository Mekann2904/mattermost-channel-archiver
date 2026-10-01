# mattermost-channel-archiver

Mattermost の特定チャンネルのログ(投稿・添付ファイル)をローカルにエクスポートし、ブラウザで閲覧・全文検索するためのツールです。

## セットアップ

`.env` に以下を設定済みであること:

```
MATTERMOST_URL=https://your-mattermost-server
MATTERMOST_TOKEN=xxxxxxxx
CHANNEL_ID=xxxxxxxx
```

### 認証方式の切り替え (`MATTERMOST_AUTH`)

`MATTERMOST_AUTH` で認証方式を明示的に選択します。省略時は `token` です。

| 値 | 認証方式 | 必要な設定 |
| --- | --- | --- |
| `token` (デフォルト) | `MATTERMOST_TOKEN` の PAT で認証 | `MATTERMOST_TOKEN` (必須) |
| `desktop` | macOS デスクトップアプリのログインセッションで認証 | なし (`MATTERMOST_TOKEN` との併記はエラー) |

### PATが作れない場合 (macOS限定)

サーバー設定によってはパーソナルアクセストークン (PAT) を作成できないアカウントがあります
(Mattermost のデフォルトでは管理者のみ作成可)。その場合は `MATTERMOST_AUTH=desktop` を
使うと、**Mattermost デスクトップアプリのログインセッション**で認証できます:

```
MATTERMOST_URL=https://your-mattermost-server
MATTERMOST_AUTH=desktop
CHANNEL_ID=xxxxxxxx
```

- 事前に macOS 用デスクトップアプリで対象サーバーにログインしておいてください
- 初回のみ macOS の許可ダイアログが出ます (Keychain の「Mattermost Safe Storage」読み取り)。「常に許可」推奨
- PAT と違いセッションには期限があります(サーバー設定依存)。切れたらデスクトップアプリで再ログインしてください
- この方式は macOS 専用です (Linux では PAT を使ってください)

仕組みは [mattermost-exporter](https://github.com/Mekann2904/mattermost-exporter) の自動検出を移植したものです。

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

`--channel-id` で複数チャンネルをエクスポートしている場合は、チャンネル選択プルダウンも表示されます。選択すると即座にその場で絞り込まれます(各投稿にもチャンネル名のバッジが表示されます)。エクスポート済みチャンネルが1つだけの場合は、このプルダウンは表示されません。

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
