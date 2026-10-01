"""環境変数 (.env) から設定を読み込む。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from .desktop_auth import extract_desktop_token

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
ATTACHMENTS_DIR = DATA_DIR / "attachments"
DB_PATH = DATA_DIR / "mattermost_log.db"


@dataclass(frozen=True)
class Settings:
    url: str
    token: str
    channel_id: str


def load_settings() -> Settings:
    load_dotenv(PROJECT_ROOT / ".env")

    url = os.environ.get("MATTERMOST_URL", "").rstrip("/")
    token = os.environ.get("MATTERMOST_TOKEN", "").strip()
    auth = os.environ.get("MATTERMOST_AUTH", "").strip().lower() or "token"
    channel_id = os.environ.get("CHANNEL_ID", "")

    missing = [
        name
        for name, value in [
            ("MATTERMOST_URL", url),
            ("CHANNEL_ID", channel_id),
        ]
        if not value
    ]
    if missing:
        raise RuntimeError(
            f".env に次の設定が見つかりません: {', '.join(missing)}"
        )

    # 認証方式は明示的に選ぶ。暗黙のフォールバックはしない。
    #   token    : MATTERMOST_TOKEN (PAT またはセッショントークン) で認証
    #   desktop  : macOS デスクトップアプリのログインセッションで認証 (macOS限定)
    if auth not in ("token", "desktop"):
        raise RuntimeError(
            f"MATTERMOST_AUTH には token または desktop を指定してください (現在の値: {auth!r})"
        )

    if auth == "desktop":
        if token:
            raise RuntimeError(
                "MATTERMOST_AUTH=desktop の場合は MATTERMOST_TOKEN を設定しないでください。"
                "どちらで認証するか明示してください"
            )
        token = extract_desktop_token(url)
    elif not token:
        raise RuntimeError(
            "MATTERMOST_TOKEN が設定されていません。PAT を設定するか、"
            "デスクトップアプリのセッションを使う場合は MATTERMOST_AUTH=desktop "
            "を指定してください"
        )

    return Settings(url=url, token=token, channel_id=channel_id)
