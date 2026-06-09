import asyncio
import logging
import os
import re
import mysql.connector
from telethon import TelegramClient, events
from telethon.tl.types import Message, DocumentAttributeFilename
from telethon.errors import FloodWaitError

# ---------- Settings ----------
API_ID = 20579339
API_HASH = "46188ecc09a9b8d3f934d280b19c1f39"
SESSION_FILE = "my_session"

# ---------- Database Config ----------
DB_CONFIG = {
    'host': 'sql12.freesqldatabase.com',
    'database': 'sql12829888',
    'user': 'sql12829888',
    'password': 'X7YNr1iUEt',
    'port': 3306
}

# ---------- Targets & Logic ----------
STARRED_CHANNELS = ["AmyraxVPN", "prrofile_purple", "vpn11ir", "hex_proxy"]
HEX_PROXY_LIMIT = 10
DEFAULT_LIMIT = 5

# Regex Patterns
CONFIG_PATTERN = r"(vless|vmess|trojan|ss):\/\/[^\s]+"
PROXY_PATTERN = r"(https?:\/\/t\.me\/proxy\?[^\s]+|tg:\/\/proxy\?[^\s]+)"

def get_db_connection():
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

def setup_db():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS telegram_items (
                id INT AUTO_INCREMENT PRIMARY KEY,
                channel_name VARCHAR(255),
                category VARCHAR(50),
                content TEXT,
                filename VARCHAR(255),
                is_starred BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        cursor.close()
        conn.close()

async def scrape_channels(client):
    print("Starting scraping cycle...")
    conn = get_db_connection()
    if not conn:
        return
    
    cursor = conn.cursor()
    # Clear old data
    cursor.execute("DELETE FROM telegram_items")
    conn.commit()

    async for dialog in client.iter_dialogs():
        if not dialog.is_channel:
            continue

        username = dialog.entity.username
        if not username:
            continue

        is_starred = username.lower() in [s.lower() for s in STARRED_CHANNELS]
        limit = HEX_PROXY_LIMIT if username.lower() == "hex_proxy" else DEFAULT_LIMIT
        
        found_count = 0
        async for message in client.iter_messages(dialog.id, limit=50): # Look back further to find specific items
            if found_count >= limit:
                break

            category = None
            content = None
            filename = None

            # 1. Check for NPVT Files
            if message.file and message.file.ext == ".npvt":
                category = "npvt"
                # Store message ID or some reference to download later, or store the content if it's text
                # For simulation, we'll store the filename and message info
                filename = "Unknown"
                for attr in message.document.attributes:
                    if isinstance(attr, DocumentAttributeFilename):
                        filename = attr.file_name
                content = f"msg_id_{message.id}" # Placeholder for actual file logic
                
            # 2. Check for Proxy Links
            elif message.text:
                proxies = re.findall(PROXY_PATTERN, message.text)
                if proxies:
                    category = "proxy"
                    content = proxies[0]
                
                # 3. Check for Configs
                else:
                    configs = re.findall(CONFIG_PATTERN, message.text)
                    if configs:
                        category = "config"
                        content = configs[0]

            if category and content:
                cursor.execute(
                    "INSERT INTO telegram_items (channel_name, category, content, filename, is_starred) VALUES (%s, %s, %s, %s, %s)",
                    (username, category, content, filename, is_starred)
                )
                found_count += 1
                conn.commit()

    cursor.close()
    conn.close()
    print("Scraping cycle finished.")

async def main():
    setup_db()
    client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
    await client.start()

    while True:
        try:
            await scrape_channels(client)
        except Exception as e:
            print(f"Error during scrape: {e}")
        
        print("Sleeping for 30 minutes...")
        await asyncio.sleep(1800)

if __name__ == "__main__":
    asyncio.run(main())
