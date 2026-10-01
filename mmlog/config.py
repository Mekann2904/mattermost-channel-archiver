"""環境変数 (.env) から設定を読み込む。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

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
    token = os.environ.get("MATTERMOST_TOKEN", "")
    channel_id = os.environ.get("CHANNEL_ID", "")

    missing = [
        name
        for name, value in [
            ("MATTERMOST_URL", url),
            ("MATTERMOST_TOKEN", token),
            ("CHANNEL_ID", channel_id),
        ]
        if not value
    ]
    if missing:
        raise RuntimeError(
            f".env に次の設定が見つかりません: {', '.join(missing)}"
        )

    return Settings(url=url, token=token, channel_id=channel_id)
