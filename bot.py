import asyncio
import logging
import re
import io
import mysql.connector
from telethon import TelegramClient
from telethon.tl.types import (
    Channel, DocumentAttributeFilename, MessageMediaDocument
)
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger(__name__)

# ---------- Settings ----------
API_ID   = 20579339
API_HASH = "46188ecc09a9b8d3f934d280b19c1f39"
SESSION  = "my_session"

# ---------- Database ----------
DB_CFG = {
    "host":     "sql12.freesqldatabase.com",
    "database": "sql12829888",
    "user":     "sql12829888",
    "password": "X7YNr1iUEt",
    "port":     3306,
}

# ---------- Logic Settings ----------
STARED_CHANNELS     = {"@AmyraxVPN", "@prrofile_purple", "@vpn11ir", "@hex_proxy"}
HEX_PROXY_CHANNEL   = "@hex_proxy"
DEFAULT_LIMIT       = 5
SPECIAL_LIMIT       = 10

# ---------- Regex ----------
RE_PROXY   = re.compile(r"https?://t\.me/proxy\?[^\s\"\'\)]+", re.IGNORECASE)
RE_CONFIG  = re.compile(
    r"(?:vless|vmess|trojan|ss)://[^\s\"\'\)\<\>]+",
    re.IGNORECASE
)

# ──────────────────────────────────────────────────────────────────────────────
def get_conn():
    return mysql.connector.connect(**DB_CFG)

def ensure_tables(cur):
    cur.execute("""
        CREATE TABLE IF NOT EXISTS vpn_items (
            id         INT AUTO_INCREMENT PRIMARY KEY,
            type       VARCHAR(20)  NOT NULL,
            channel    VARCHAR(100) NOT NULL,
            content    TEXT,
            file_name  VARCHAR(255),
            file_data  LONGBLOB,
            is_stared  TINYINT(1)   DEFAULT 0,
            created_at DATETIME     DEFAULT CURRENT_TIMESTAMP
        )
    """)

def clear_items(cur):
    cur.execute("DELETE FROM vpn_items")

def insert_item(cur, type_, channel, content, file_name, file_data, is_stared):
    cur.execute(
        """INSERT INTO vpn_items
           (type, channel, content, file_name, file_data, is_stared)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (type_, channel, content, file_name, file_data, int(is_stared))
    )

# ──────────────────────────────────────────────────────────────────────────────
async def scrape_all(client: TelegramClient, cur, conn):
    log.info("Clearing old data ...")
    clear_items(cur)
    conn.commit()

    async for dialog in client.iter_dialogs():
        entity = dialog.entity

        # Only process channels (not private chats / groups)
        if not isinstance(entity, Channel):
            continue

        raw_username = getattr(entity, "username", None)
        if not raw_username:
            continue                           # skip channels with no public @

        channel_tag = f"@{raw_username}"
        is_stared   = channel_tag in STARED_CHANNELS
        limit       = SPECIAL_LIMIT if channel_tag == HEX_PROXY_CHANNEL else DEFAULT_LIMIT

        log.info(f"Processing {channel_tag}  (limit={limit}, stared={is_stared})")
        found = 0

        async for msg in client.iter_messages(entity, limit=200):
            if found >= limit:
                break

            # ── 1. NPVT file ──────────────────────────────────────────────
            if msg.file is not None:
                fname = None
                for attr in (msg.media.document.attributes if msg.media and hasattr(msg.media, "document") else []):
                    if isinstance(attr, DocumentAttributeFilename):
                        fname = attr.file_name
                        break

                if fname and fname.lower().endswith(".npvt"):
                    log.info(f"  Downloading npvt: {fname}")
                    try:
                        buf = io.BytesIO()
                        await client.download_media(msg, file=buf)
                        file_bytes = buf.getvalue()
                    except Exception as e:
                        log.warning(f"  Failed to download {fname}: {e}")
                        file_bytes = None

                    insert_item(cur, "napster", channel_tag,
                                fname, fname, file_bytes, is_stared)
                    conn.commit()
                    found += 1
                    continue

            # ── 2. Text-based content ─────────────────────────────────────
            text = msg.text or ""
            if not text:
                continue

            # Proxy links first
            proxies = RE_PROXY.findall(text)
            if proxies:
                for proxy_url in proxies:
                    if found >= limit:
                        break
                    insert_item(cur, "proxy", channel_tag,
                                proxy_url, None, None, is_stared)
                    conn.commit()
                    found += 1
                continue

            # V2Ray / SS configs
            configs = RE_CONFIG.findall(text)
            if configs:
                for cfg in configs:
                    if found >= limit:
                        break
                    insert_item(cur, "config", channel_tag,
                                cfg, None, None, is_stared)
                    conn.commit()
                    found += 1

    log.info("Scrape finished.")

# ──────────────────────────────────────────────────────────────────────────────
async def main():
    client = TelegramClient(SESSION, API_ID, API_HASH)
    await client.start()
    log.info("Telegram client started.")

    conn = get_conn()
    cur  = conn.cursor()
    ensure_tables(cur)
    conn.commit()

    while True:
        log.info("=== Starting scheduled scrape ===")
        try:
            await scrape_all(client, cur, conn)
        except Exception as exc:
            log.exception(f"Scrape error: {exc}")

        log.info("Sleeping 30 minutes ...")
        await asyncio.sleep(1800)

if __name__ == "__main__":
    asyncio.run(main())
