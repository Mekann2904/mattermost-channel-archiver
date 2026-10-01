"""Mattermost REST API v4 向けの最小限のクライアント。"""

from __future__ import annotations

from typing import Any, Iterator

import requests

from .config import Settings


class MattermostClient:
    def __init__(self, settings: Settings):
        self.base_url = f"{settings.url}/api/v4"
        self.session = requests.Session()
        self.session.headers.update(
            {"Authorization": f"Bearer {settings.token}"}
        )

    def _get(self, path: str, **params: Any) -> requests.Response:
        resp = self.session.get(f"{self.base_url}{path}", params=params, timeout=30)
        resp.raise_for_status()
        return resp

    def get_me(self) -> dict:
        return self._get("/users/me").json()

    def get_channel(self, channel_id: str) -> dict:
        return self._get(f"/channels/{channel_id}").json()

    def get_user(self, user_id: str) -> dict:
        return self._get(f"/users/{user_id}").json()

    def get_file_info(self, file_id: str) -> dict:
        return self._get(f"/files/{file_id}/info").json()

    def download_file(self, file_id: str) -> bytes:
        resp = self.session.get(
            f"{self.base_url}/files/{file_id}", timeout=60
        )
        resp.raise_for_status()
        return resp.content

    def iter_channel_posts(
        self, channel_id: str, per_page: int = 200
    ) -> Iterator[dict]:
        """チャンネル内の全投稿を作成日時の古い順に yield する。"""
        page = 0
        all_posts: dict[str, dict] = {}
        order: list[str] = []
        while True:
            data = self._get(
                f"/channels/{channel_id}/posts",
                page=page,
                per_page=per_page,
            ).json()
            page_order = data.get("order", [])
            if not page_order:
                break
            all_posts.update(data.get("posts", {}))
            order.extend(page_order)
            if len(page_order) < per_page:
                break
            page += 1

        for post_id in sorted(set(order), key=lambda pid: all_posts[pid]["create_at"]):
            yield all_posts[post_id]
