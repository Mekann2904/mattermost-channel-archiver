"""macOS の Mattermost デスクトップアプリからセッショントークンを取得する。

mattermost-exporter (https://github.com/Mekann2904/mattermost-exporter) の
自動検出処理を Python に移植したもの。PAT を作成できないアカウントでも、
デスクトップアプリでログインしていればエクスポートできるようにする。
"""

from __future__ import annotations

import hashlib
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

APP_SUPPORT = Path.home() / "Library" / "Application Support" / "Mattermost"
KEYCHAIN_SERVICE = "Mattermost Safe Storage"

# セッショントークンの形 (通常26文字の印字可能ASCII)
TOKEN_RE = re.compile(r"^[\x21-\x7e]{20,40}$")
# 復号後の平文末尾にある PKCS7 パディング (0x01〜0x10)
PAD_RE = re.compile(r"[\x01-\x10]+$")


def _keychain_password() -> str:
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("macOS の security コマンドが見つかりません") from exc
    password = result.stdout.strip()
    if result.returncode != 0 or not password:
        raise RuntimeError(
            "Keychainから復号キーを取得できませんでした。"
            "「security」がKeychainにアクセスする許可ダイアログで"
            "「常に許可」を選んでください"
        )
    return password


def _decrypt(encrypted_value: bytes, host_key: str, password: str) -> str | None:
    """MMAUTHTOKEN の暗号化値を復号し、トークンらしき文字列を返す。"""
    # デスクトップアプリ (Electron) の Cookie 暗号化の仕様:
    #   v10 + AES-128-CBC + PKCS7 パディング
    #   鍵 = PBKDF2(Keychainのパスワード, "saltysalt", 1003回, SHA1, 16バイト)
    #   IV  = 16 バイトのスペース
    # 平文はアプリのバージョンによって 2 形式あり、新しい形式は先頭に
    # sha256(host_key) による整合性MACが 32 バイト付いている。
    if encrypted_value[:3] != b"v10":
        return None
    try:
        key = hashlib.pbkdf2_hmac(
            "sha1", password.encode(), b"saltysalt", 1003, dklen=16
        )
        decryptor = Cipher(algorithms.AES(key), modes.CBC(b" " * 16)).decryptor()
        plain = decryptor.update(encrypted_value[3:]) + decryptor.finalize()
    except Exception:  # 復号失敗 (鍵不一致・データ破損など)
        return None
    mac = hashlib.sha256(host_key.encode("latin1")).digest()
    body = plain[32:] if len(plain) >= 32 and plain[:32] == mac else plain
    token = PAD_RE.sub("", body.decode("latin1"))
    return token if TOKEN_RE.fullmatch(token) else None


def extract_desktop_token(server_url: str) -> str:
    """デスクトップアプリの Cookie から server_url のセッショントークンを取り出す。"""
    if sys.platform != "darwin":
        raise RuntimeError("デスクトップアプリからの自動検出はmacOS専用です")

    host = urlparse(server_url).hostname or ""
    if not host:
        raise RuntimeError(f"MATTERMOST_URL が不正です: {server_url!r}")

    cookies_path = APP_SUPPORT / "Cookies"
    if not cookies_path.exists():
        raise RuntimeError(
            "デスクトップアプリのCookieがありません(一度ログインしてください)"
        )

    # 起動中のアプリに DB をロックされている可能性があるため、コピーして読む
    with tempfile.TemporaryDirectory() as tmpdir:
        cookie_copy = Path(tmpdir) / "Cookies"
        shutil.copyfile(cookies_path, cookie_copy)
        conn = sqlite3.connect(cookie_copy)
        try:
            row = conn.execute(
                "SELECT host_key, encrypted_value FROM cookies "
                "WHERE name='MMAUTHTOKEN' AND host_key IN (?, ?) "
                "ORDER BY creation_utc DESC LIMIT 1",
                (host, f".{host}"),
            ).fetchone()
        finally:
            conn.close()

    if row is None or not row[1]:
        raise RuntimeError(
            f"このサーバー({host})のセッションCookieがありません。"
            "デスクトップアプリでログインしてください"
        )

    password = _keychain_password()
    token = _decrypt(row[1], row[0], password)
    if token is None:
        raise RuntimeError("トークンの復号に失敗しました")
    return token
