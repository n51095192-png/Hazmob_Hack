import asyncio
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone

import mysql.connector
from telethon import TelegramClient


API_ID = int(os.getenv("API_ID", "20579339"))
API_HASH = os.getenv("API_HASH", "46188ecc09a9b8d3f934d280b19c1f39")
SESSION_FILE = os.getenv("SESSION_FILE", "my_session")

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "sql12.freesqldatabase.com"),
    "database": os.getenv("DB_NAME", "sql12829888"),
    "user": os.getenv("DB_USER", "sql12829888"),
    "password": os.getenv("DB_PASSWORD", "X7YNr1iUEt"),
    "port": int(os.getenv("DB_PORT", "3306")),
}

TABLE_NAME = os.getenv("TABLE_NAME", "telegram_items")
DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "downloads")

STARRED_CHANNELS = {
    "@AmyraxVPN",
    "@prrofile_purple",
    "@vpn11ir",
    "@hex_proxy",
}

DEFAULT_LIMIT = 5
SPECIAL_LIMITS = {
    "@hex_proxy": 10,
}

NPVT_EXT = ".npvt"
PROXY_RE = re.compile(r"https?://t\.me/proxy\?[^\s<>\"']+", re.IGNORECASE)
CONFIG_RE = re.compile(r"(?:vless|vmess|trojan|ss)://[^\s<>\"']+", re.IGNORECASE)


@dataclass
class ExtractedItem:
    item_type: str
    channel_username: str
    channel_title: str
    channel_starred: int
    source_message_id: int
    display_name: str | None = None
    payload: str | None = None
    file_name: str | None = None
    local_path: str | None = None
    source_text: str | None = None
    created_at: str | None = None


def get_connection():
    return mysql.connector.connect(**DB_CONFIG)


def ensure_schema(cursor):
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            item_type VARCHAR(32) NOT NULL,
            channel_username VARCHAR(128) NOT NULL,
            channel_title VARCHAR(255) NOT NULL,
            channel_starred TINYINT(1) NOT NULL DEFAULT 0,
            source_message_id BIGINT NOT NULL,
            display_name VARCHAR(255) NULL,
            payload TEXT NULL,
            file_name VARCHAR(255) NULL,
            local_path TEXT NULL,
            source_text LONGTEXT NULL,
            created_at DATETIME NOT NULL,
            UNIQUE KEY uniq_item (item_type, channel_username, source_message_id, file_name)
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
        """
    )


def clear_table(cursor):
    cursor.execute(f"TRUNCATE TABLE {TABLE_NAME}")


def normalize_username(entity) -> str:
    username = getattr(entity, "username", None)
    if username:
        return f"@{username}"
    title = getattr(entity, "title", None)
    if title:
        return title
    return "Private"


def extract_links(text: str):
    if not text:
        return []

    found = []
    seen = set()

    for match in PROXY_RE.finditer(text):
        value = match.group(0)
        if value not in seen:
            seen.add(value)
            found.append(("proxy", value))

    for match in CONFIG_RE.finditer(text):
        value = match.group(0)
        if value not in seen:
            seen.add(value)
            found.append(("config", value))

    return found


def is_npvt_file(message) -> bool:
    name = getattr(getattr(message, "file", None), "name", None)
    return bool(name and name.lower().endswith(NPVT_EXT))


def build_display_name(message, fallback: str) -> str:
    name = getattr(getattr(message, "file", None), "name", None)
    if name:
        return name
    text = getattr(message, "message", None) or getattr(message, "text", None)
    if text:
        first_line = text.strip().splitlines()[0].strip()
        if first_line:
            return first_line[:255]
    return fallback


async def save_item(cursor, conn, item: ExtractedItem):
    cursor.execute(
        f"""
        INSERT INTO {TABLE_NAME} (
            item_type,
            channel_username,
            channel_title,
            channel_starred,
            source_message_id,
            display_name,
            payload,
            file_name,
            local_path,
            source_text,
            created_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            channel_title = VALUES(channel_title),
            channel_starred = VALUES(channel_starred),
            display_name = VALUES(display_name),
            payload = VALUES(payload),
            local_path = VALUES(local_path),
            source_text = VALUES(source_text),
            created_at = VALUES(created_at)
        """,
        (
            item.item_type,
            item.channel_username,
            item.channel_title,
            item.channel_starred,
            item.source_message_id,
            item.display_name,
            item.payload,
            item.file_name,
            item.local_path,
            item.source_text,
            item.created_at,
        ),
    )
    conn.commit()


async def scrape_channel(client: TelegramClient, cursor, conn, channel_entity, limit: int, download_dir: str):
    channel_username = normalize_username(channel_entity)
    channel_title = getattr(channel_entity, "title", None) or channel_username
    starred = 1 if channel_username in STARRED_CHANNELS else 0

    collected = 0
    async for message in client.iter_messages(channel_entity, limit=200):
        if collected >= limit:
            break

        text = getattr(message, "message", None) or getattr(message, "text", None) or ""
        created_at = message.date.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S") if message.date else datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        if is_npvt_file(message):
            file_name = getattr(getattr(message, "file", None), "name", None)
            display_name = build_display_name(message, file_name or f"message_{message.id}.npvt")
            local_path = None

            os.makedirs(download_dir, exist_ok=True)
            if file_name:
                target_path = os.path.join(download_dir, file_name)
                local_path = await client.download_media(message, file=target_path)
            else:
                local_path = await client.download_media(message, file=download_dir)

            item = ExtractedItem(
                item_type="napster",
                channel_username=channel_username,
                channel_title=channel_title,
                channel_starred=starred,
                source_message_id=message.id,
                display_name=display_name,
                payload=None,
                file_name=file_name,
                local_path=local_path,
                source_text=text or None,
                created_at=created_at,
            )
            await save_item(cursor, conn, item)
            collected += 1
            continue

        extracted = extract_links(text)
        for item_type, payload in extracted:
            if collected >= limit:
                break
            display_name = build_display_name(message, payload)
            item = ExtractedItem(
                item_type=item_type,
                channel_username=channel_username,
                channel_title=channel_title,
                channel_starred=starred,
                source_message_id=message.id,
                display_name=display_name,
                payload=payload,
                file_name=None,
                local_path=None,
                source_text=text or None,
                created_at=created_at,
            )
            await save_item(cursor, conn, item)
            collected += 1


async def scrape_all():
    client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
    await client.start()

    conn = get_connection()
    cursor = conn.cursor()

    try:
        ensure_schema(cursor)
        conn.commit()
        clear_table(cursor)
        conn.commit()

        async for dialog in client.iter_dialogs():
            if not dialog.is_channel:
                continue

            entity = dialog.entity
            channel_username = normalize_username(entity)
            limit = SPECIAL_LIMITS.get(channel_username, DEFAULT_LIMIT)
            await scrape_channel(client, cursor, conn, entity, limit, DOWNLOAD_DIR)

    finally:
        cursor.close()
        conn.close()
        await client.disconnect()


async def main_loop():
    while True:
        try:
            logging.info("Starting scheduled scrape")
            await scrape_all()
            logging.info("Scrape complete, sleeping 30 minutes")
        except Exception:
            logging.exception("Scrape failed")
        await asyncio.sleep(1800)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    asyncio.run(main_loop())
