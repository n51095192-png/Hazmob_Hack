import asyncio
import logging
import os
import re
import time
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError
from telethon.tl.types import Message, DocumentAttributeFilename
import mysql.connector
from mysql.connector import Error

# ---------- Settings ----------
API_ID = 20579339
API_HASH = "46188ecc09a9b8d3f934d280b19c1f39"
SESSION_FILE = "my_session"

# ---------- Database ----------
DB_CONFIG = {
    'host': 'db4free.net',
    'database': 'noaprojectdb',
    'user': 'noaishere',
    'password': 'Mohammad86$',
    'port': 3306
}

# ---------- Constants ----------
DEFAULT_LIMIT = 5
STARRED_CHANNELS = ["amyraxvpn", "prrofile_purple", "vpn11ir", "hex_proxy"]
SPECIAL_LIMIT_CHANNELS = {"hex_proxy": 10}
CYCLE_INTERVAL = 1800  # 30 minutes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# ---------- Regex Patterns ----------
VPNFILE_PATTERN = re.compile(r'\.npvt$', re.IGNORECASE)

PROXY_LINK_PATTERN = re.compile(
    r'(https?://t\.me/proxy\?[^\s<>"\']+|tg://proxy\?[^\s<>"\']+)',
    re.IGNORECASE
)

CONFIG_PATTERNS = {
    'vless':  re.compile(r'vless://[^\s<>"\']+', re.IGNORECASE),
    'vmess':  re.compile(r'vmess://[^\s<>"\']+', re.IGNORECASE),
    'trojan': re.compile(r'trojan://[^\s<>"\']+', re.IGNORECASE),
    'ss':     re.compile(r'ss://[^\s<>"\']+', re.IGNORECASE),
}

# ---------- Database Helpers ----------
def get_connection():
    return mysql.connector.connect(**DB_CONFIG)


def setup_database():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS npvt_files (
            id INT AUTO_INCREMENT PRIMARY KEY,
            channel_username VARCHAR(255) NOT NULL,
            channel_title VARCHAR(255),
            file_name VARCHAR(500),
            file_data LONGBLOB,
            message_id BIGINT,
            message_date DATETIME,
            is_starred TINYINT(1) DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS proxies (
            id INT AUTO_INCREMENT PRIMARY KEY,
            channel_username VARCHAR(255) NOT NULL,
            channel_title VARCHAR(255),
            proxy_link TEXT NOT NULL,
            message_id BIGINT,
            message_date DATETIME,
            is_starred TINYINT(1) DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS configs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            channel_username VARCHAR(255) NOT NULL,
            channel_title VARCHAR(255),
            protocol VARCHAR(20) NOT NULL,
            config_value TEXT NOT NULL,
            message_id BIGINT,
            message_date DATETIME,
            is_starred TINYINT(1) DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
    """)

    conn.commit()
    cursor.close()
    conn.close()
    logger.info("Database tables verified/created.")


def clear_all_tables():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM npvt_files")
    cursor.execute("DELETE FROM proxies")
    cursor.execute("DELETE FROM configs")
    conn.commit()
    cursor.close()
    conn.close()
    logger.info("All tables cleared.")


def save_npvt_file(channel_username, channel_title, file_name, file_data,
                   message_id, message_date, is_starred):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO npvt_files
            (channel_username, channel_title, file_name, file_data,
             message_id, message_date, is_starred)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (channel_username, channel_title, file_name, file_data,
          message_id, message_date, int(is_starred)))
    conn.commit()
    cursor.close()
    conn.close()


def save_proxy(channel_username, channel_title, proxy_link,
               message_id, message_date, is_starred):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO proxies
            (channel_username, channel_title, proxy_link,
             message_id, message_date, is_starred)
        VALUES (%s, %s, %s, %s, %s, %s)
    """, (channel_username, channel_title, proxy_link,
          message_id, message_date, int(is_starred)))
    conn.commit()
    cursor.close()
    conn.close()


def save_config(channel_username, channel_title, protocol, config_value,
                message_id, message_date, is_starred):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO configs
            (channel_username, channel_title, protocol, config_value,
             message_id, message_date, is_starred)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (channel_username, channel_title, protocol, config_value,
          message_id, message_date, int(is_starred)))
    conn.commit()
    cursor.close()
    conn.close()


# ---------- Core Scraper ----------
async def process_channel(client, dialog, limit):
    channel = dialog.entity
    channel_title = getattr(channel, 'title', 'Unknown')
    raw_username = getattr(channel, 'username', None) or str(channel.id)
    channel_username = raw_username.lower().lstrip('@')
    is_starred = channel_username in STARRED_CHANNELS

    logger.info(f"Processing: @{channel_username} | starred={is_starred} | limit={limit}")

    collected = 0

    async for message in client.iter_messages(channel, limit=200):
        if collected >= limit:
            break
        if not isinstance(message, Message):
            continue

        msg_date = message.date
        msg_id = message.id
        found_something = False

        # --- Check for .npvt file attachment ---
        if message.document:
            for attr in message.document.attributes:
                if isinstance(attr, DocumentAttributeFilename):
                    if VPNFILE_PATTERN.search(attr.file_name):
                        try:
                            file_bytes = await client.download_media(
                                message, file=bytes
                            )
                            save_npvt_file(
                                channel_username, channel_title,
                                attr.file_name, file_bytes,
                                msg_id, msg_date, is_starred
                            )
                            logger.info(f"  [NPVT] {attr.file_name}")
                            found_something = True
                        except Exception as e:
                            logger.warning(f"  [NPVT] download error: {e}")

        text = message.text or ""

        # --- Check for Telegram proxy links in text ---
        proxy_matches = PROXY_LINK_PATTERN.findall(text)
        for link in proxy_matches:
            save_proxy(
                channel_username, channel_title, link,
                msg_id, msg_date, is_starred
            )
            logger.info(f"  [PROXY] {link[:60]}...")
            found_something = True

        # --- Check for VPN config strings ---
        for protocol, pattern in CONFIG_PATTERNS.items():
            for match in pattern.finditer(text):
                save_config(
                    channel_username, channel_title,
                    protocol, match.group(0),
                    msg_id, msg_date, is_starred
                )
                logger.info(f"  [CONFIG/{protocol.upper()}] found")
                found_something = True

        if found_something:
            collected += 1

    logger.info(f"  Done @{channel_username}: {collected} items collected.")


async def scrape_all(client):
    logger.info("Starting full scrape cycle...")
    clear_all_tables()

    async for dialog in client.iter_dialogs():
        if not dialog.is_channel:
            continue

        raw_username = getattr(dialog.entity, 'username', None) or ""
        channel_key = raw_username.lower().lstrip('@')

        limit = SPECIAL_LIMIT_CHANNELS.get(channel_key, DEFAULT_LIMIT)

        try:
            await process_channel(client, dialog, limit)
            await asyncio.sleep(1.5)  # gentle rate limiting
        except FloodWaitError as e:
            logger.warning(f"FloodWait {e.seconds}s for {channel_key}, sleeping...")
            await asyncio.sleep(e.seconds + 5)
        except Exception as e:
            logger.error(f"Error processing {channel_key}: {e}")

    logger.info("Scrape cycle complete.")


# ---------- Main Loop ----------
async def main():
    setup_database()

    client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
    await client.start()
    logger.info("Telegram client connected.")

    while True:
        try:
            await scrape_all(client)
        except Exception as e:
            logger.error(f"Cycle error: {e}")

        logger.info(f"Sleeping {CYCLE_INTERVAL // 60} minutes until next cycle...")
        await asyncio.sleep(CYCLE_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
