"""Mattermost のチャンネルログと添付ファイルをローカルにエクスポートする。

使い方:
    uv run mm-export [--channel-id CHANNEL_ID]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .api import MattermostClient
from .config import ATTACHMENTS_DIR, load_settings
from .db import connect, upsert_channel, upsert_file, upsert_post, upsert_user


def _safe_filename(name: str) -> str:
    return "".join(c if c not in '/\\:*?"<>|' else "_" for c in name)


def export_channel(channel_id: str | None = None) -> None:
    settings = load_settings()
    channel_id = channel_id or settings.channel_id

    client = MattermostClient(settings)
    conn = connect()

    channel = client.get_channel(channel_id)
    upsert_channel(
        conn,
        {
            "id": channel["id"],
            "name": channel.get("name"),
            "display_name": channel.get("display_name"),
            "team_id": channel.get("team_id"),
        },
    )
    conn.commit()
    print(f"チャンネル: {channel.get('display_name')} ({channel_id})")

    attachments_dir = ATTACHMENTS_DIR / channel_id
    attachments_dir.mkdir(parents=True, exist_ok=True)

    known_users: set[str] = set()
    post_count = 0
    file_count = 0

    for post in client.iter_channel_posts(channel_id):
        user_id = post.get("user_id", "")
        if user_id and user_id not in known_users:
            try:
                user = client.get_user(user_id)
                upsert_user(
                    conn,
                    {
                        "id": user["id"],
                        "username": user.get("username"),
                        "nickname": user.get("nickname"),
                        "first_name": user.get("first_name"),
                        "last_name": user.get("last_name"),
                    },
                )
            except Exception as exc:  # noqa: BLE001
                print(f"  警告: ユーザー {user_id} の取得に失敗: {exc}")
            known_users.add(user_id)

        upsert_post(
            conn,
            {
                "id": post["id"],
                "channel_id": post.get("channel_id", channel_id),
                "user_id": user_id,
                "root_id": post.get("root_id") or "",
                "create_at": post.get("create_at", 0),
                "update_at": post.get("update_at", 0),
                "edit_at": post.get("edit_at", 0),
                "delete_at": post.get("delete_at", 0),
                "type": post.get("type", ""),
                "message": post.get("message", ""),
            },
        )
        post_count += 1

        for file_id in post.get("file_ids") or []:
            try:
                info = client.get_file_info(file_id)
                ext = info.get("extension", "")
                local_name = f"{file_id}_{_safe_filename(info.get('name', file_id))}"
                local_path = attachments_dir / local_name

                if not local_path.exists():
                    content = client.download_file(file_id)
                    local_path.write_bytes(content)

                upsert_file(
                    conn,
                    {
                        "id": file_id,
                        "post_id": post["id"],
                        "name": info.get("name", local_name),
                        "extension": ext,
                        "size": info.get("size", 0),
                        "mime_type": info.get("mime_type", ""),
                        "local_path": str(local_path.relative_to(ATTACHMENTS_DIR)),
                    },
                )
                file_count += 1
            except Exception as exc:  # noqa: BLE001
                print(f"  警告: 添付ファイル {file_id} の取得に失敗: {exc}")

        if post_count % 200 == 0:
            conn.commit()
            print(f"  {post_count} 件の投稿を処理済み...")

    conn.commit()
    conn.close()
    print(f"完了: 投稿 {post_count} 件, 添付ファイル {file_count} 件をエクスポートしました。")


def main() -> None:
    parser = argparse.ArgumentParser(description="Mattermost チャンネルログ エクスポート")
    parser.add_argument(
        "--channel-id",
        default=None,
        help="エクスポート対象のチャンネルID (省略時は .env の CHANNEL_ID を使用)",
    )
    args = parser.parse_args()
    export_channel(channel_id=args.channel_id)


if __name__ == "__main__":
    main()
