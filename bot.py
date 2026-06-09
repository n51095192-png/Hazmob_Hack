import asyncio
import logging
import re
import mysql.connector
from telethon import TelegramClient, events
from telethon.tl.types import Message, DocumentAttributeFilename
from datetime import datetime

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

# ---------- Project Logic Settings ----------
STARED_CHANNELS = ["@AmyraxVPN", "@prrofile_purple", "@vpn11ir", "@hex_proxy"]
SPECIAL_LIMIT_CHANNEL = "@hex_proxy"
DEFAULT_LIMIT = 5
SPECIAL_LIMIT = 10

# Regex Patterns
PROXY_PATTERN = r"(https?://t\.me/proxy\?server=[^\s]+)"
CONFIG_PATTERNS = r"(vless://[^\s]+|vmess://[^\s]+|trojan://[^\s]+|ss://[^\s]+)"

async def get_db_connection():
    return mysql.connector.connect(**DB_CONFIG)

async def clear_database(cursor, conn):
    cursor.execute("TRUNCATE TABLE items") # Assume table name is 'items'
    conn.commit()

async def scrape_telegram():
    client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
    await client.start()
    
    conn = await get_db_connection()
    cursor = conn.cursor()
    
    # 1. Clear DB before starting
    cursor.execute("DELETE FROM vpn_items") # Change to your table name
    conn.commit()

    async for dialog in client.iter_dialogs():
        if not dialog.is_channel:
            continue
        
        username = f"@{dialog.entity.username}" if dialog.entity.username else "Private"
        is_stared = 1 if username in STARED_CHANNELS else 0
        limit = SPECIAL_LIMIT if username == SPECIAL_LIMIT_CHANNEL else DEFAULT_LIMIT
        
        print(f"Scraping {username}...")
        found_count = 0
        
        async for message in client.iter_messages(dialog.entity, limit=100):
            if found_count >= limit:
                break
            
            item_data = None
            item_type = None
            file_name = None

            # 1. Check for NPVT Files
            if message.file and message.file.name and message.file.name.endswith(".npvt"):
                item_type = "napster"
                file_name = message.file.name
                # Store content or reference
                item_data = message.text if message.text else file_name
                found_count += 1

            # 2. Check for Proxy Links in text
            elif message.text:
                proxies = re.findall(PROXY_PATTERN, message.text)
                if proxies:
                    item_type = "proxy"
                    item_data = proxies[0]
                    found_count += 1
                
                # 3. Check for V2Ray Configs
                else:
                    configs = re.findall(CONFIG_PATTERNS, message.text)
                    if configs:
                        item_type = "config"
                        item_data = configs[0]
                        found_count += 1

            if item_type and item_data:
                query = "INSERT INTO vpn_items (type, channel, content, file_name, is_stared) VALUES (%s, %s, %s, %s, %s)"
                cursor.execute(query, (item_type, username, item_data, file_name, is_stared))
                conn.commit()

    await client.disconnect()
    cursor.close()
    conn.close()

async def main_loop():
    while True:
        print("Starting scheduled scrap...")
        try:
            await scrape_telegram()
            print("Scraping finished. Waiting 30 minutes...")
        except Exception as e:
            print(f"Error occurred: {e}")
        
        await asyncio.sleep(1800) # 30 minutes

if __name__ == "__main__":
    asyncio.run(main_loop())
