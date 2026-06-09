import asyncio
import logging
import os
import re
from datetime import datetime
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError
from telethon.tl.types import Message, MessageMediaDocument
import mysql.connector
from mysql.connector import pooling

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
    'port': 3306,
    'connection_timeout': 30,
    'autocommit': True,
}

# ---------- Starred Channels ----------
STARRED_CHANNELS = ['AmyraxVPN', 'prrofile_purple', 'vpn11ir', 'hex_proxy']
HEX_PROXY_CHANNEL = 'hex_proxy'

# ---------- Limits ----------
DEFAULT_LIMIT = 5
HEX_PROXY_LIMIT = 10

# ---------- Regex Patterns ----------

# NPVT file patterns
NPVT_EXTENSIONS = re.compile(r'\.npvt$', re.IGNORECASE)

# Telegram Proxy link patterns
PROXY_PATTERN = re.compile(
    r'(https://t\.me/proxy\?[^\s<>"\']+|tg://proxy\?[^\s<>"\']+)',
    re.IGNORECASE
)

# VPN Config patterns
CONFIG_PATTERNS = {
    'vless': re.compile(r'vless://[^\s<>"\'\n]+', re.IGNORECASE),
    'vmess': re.compile(r'vmess://[^\s<>"\'\n]+', re.IGNORECASE),
    'trojan': re.compile(r'trojan://[^\s<>"\'\n]+', re.IGNORECASE),
    'ss': re.compile(r'ss://[^\s<>"\'\n]+', re.IGNORECASE),
    'ssr': re.compile(r'ssr://[^\s<>"\'\n]+', re.IGNORECASE),
    'hysteria': re.compile(r'hysteria2?://[^\s<>"\'\n]+', re.IGNORECASE),
    'tuic': re.compile(r'tuic://[^\s<>"\'\n]+', re.IGNORECASE),
    'wireguard': re.compile(r'wireguard://[^\s<>"\'\n]+', re.IGNORECASE),
}

# ---------- Logging ----------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger(__name__)


# ============================================================
#  DATABASE MANAGER
# ============================================================
class DatabaseManager:
    def __init__(self):
        self.conn = None

    def connect(self):
        try:
            self.conn = mysql.connector.connect(**DB_CONFIG)
            log.info("Database connected successfully.")
        except mysql.connector.Error as e:
            log.error(f"Database connection failed: {e}")
            raise

    def ensure_tables(self):
        """Create tables if they do not exist."""
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS npvt_configs (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    channel_name VARCHAR(100) NOT NULL,
                    file_name VARCHAR(255),
                    file_content LONGTEXT,
                    is_starred TINYINT(1) DEFAULT 0,
                    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_channel (channel_name),
                    INDEX idx_starred (is_starred)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS proxy_configs (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    channel_name VARCHAR(100) NOT NULL,
                    proxy_link TEXT NOT NULL,
                    is_starred TINYINT(1) DEFAULT 0,
                    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_channel (channel_name),
                    INDEX idx_starred (is_starred)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS vpn_configs (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    channel_name VARCHAR(100) NOT NULL,
                    config_type VARCHAR(20) NOT NULL,
                    config_data TEXT NOT NULL,
                    is_starred TINYINT(1) DEFAULT 0,
                    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_channel (channel_name),
                    INDEX idx_type (config_type),
                    INDEX idx_starred (is_starred)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """)

            self.conn.commit()
            log.info("Database tables verified/created.")
        except mysql.connector.Error as e:
            log.error(f"Table creation error: {e}")
            raise
        finally:
            cursor.close()

    def clear_all(self):
        """Wipe all collected data for a fresh cycle."""
        cursor = self.conn.cursor()
        try:
            cursor.execute("DELETE FROM npvt_configs")
            cursor.execute("DELETE FROM proxy_configs")
            cursor.execute("DELETE FROM vpn_configs")
            self.conn.commit()
            log.info("Database cleared for new cycle.")
        except mysql.connector.Error as e:
            log.error(f"Clear error: {e}")
        finally:
            cursor.close()

    def insert_npvt(self, channel_name: str, file_name: str, file_content: str, starred: bool):
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO npvt_configs (channel_name, file_name, file_content, is_starred) VALUES (%s, %s, %s, %s)",
                (channel_name, file_name, file_content, int(starred))
            )
            self.conn.commit()
        except mysql.connector.Error as e:
            log.error(f"Insert NPVT error: {e}")
        finally:
            cursor.close()

    def insert_proxy(self, channel_name: str, proxy_link: str, starred: bool):
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO proxy_configs (channel_name, proxy_link, is_starred) VALUES (%s, %s, %s)",
                (channel_name, proxy_link, int(starred))
            )
            self.conn.commit()
        except mysql.connector.Error as e:
            log.error(f"Insert proxy error: {e}")
        finally:
            cursor.close()

    def insert_vpn_config(self, channel_name: str, config_type: str, config_data: str, starred: bool):
        cursor = self.conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO vpn_configs (channel_name, config_type, config_data, is_starred) VALUES (%s, %s, %s, %s)",
                (channel_name, config_type, config_data, int(starred))
            )
            self.conn.commit()
        except mysql.connector.Error as e:
            log.error(f"Insert config error: {e}")
        finally:
            cursor.close()

    def close(self):
        if self.conn and self.conn.is_connected():
            self.conn.close()
            log.info("Database connection closed.")


# ============================================================
#  COLLECTOR
# ============================================================
class VPNCollector:
    def __init__(self, client: TelegramClient, db: DatabaseManager):
        self.client = client
        self.db = db

    def is_starred(self, channel_username: str) -> bool:
        return channel_username.lstrip('@').lower() in [c.lower() for c in STARRED_CHANNELS]

    def get_limit(self, channel_username: str) -> int:
        clean = channel_username.lstrip('@').lower()
        if clean == HEX_PROXY_CHANNEL.lower():
            return HEX_PROXY_LIMIT
        return DEFAULT_LIMIT

    async def process_message(self, msg: Message, channel_name: str, starred: bool) -> dict:
        """
        Process a single message and extract all relevant items.
        Returns dict with counts of found items.
        """
        found = {'npvt': 0, 'proxy': 0, 'config': 0}

        # 1) NPVT files attached to message
        if msg.media and isinstance(msg.media, MessageMediaDocument):
            doc = msg.media.document
            if doc and hasattr(doc, 'attributes'):
                for attr in doc.attributes:
                    if hasattr(attr, 'file_name') and attr.file_name:
                        fname = attr.file_name
                        if NPVT_EXTENSIONS.search(fname):
                            try:
                                content_bytes = await self.client.download_media(msg, bytes)
                                content = content_bytes.decode('utf-8', errors='replace')
                                self.db.insert_npvt(channel_name, fname, content, starred)
                                found['npvt'] += 1
                                log.info(f"  [NPVT] {channel_name}: {fname}")
                            except Exception as e:
                                log.warning(f"  [NPVT] Could not download {fname}: {e}")

        # 2) Process text content
        text = msg.text or msg.message or ''
        if not text:
            return found

        # 2a) Telegram Proxy links in text
        proxy_matches = PROXY_PATTERN.findall(text)
        for proxy_link in proxy_matches:
            # Clean trailing punctuation
            proxy_link = proxy_link.rstrip('.,;:)\'\"')
            self.db.insert_proxy(channel_name, proxy_link, starred)
            found['proxy'] += 1
            log.info(f"  [PROXY] {channel_name}: {proxy_link[:70]}...")

        # 2b) VPN configs in text
        for config_type, pattern in CONFIG_PATTERNS.items():
            matches = pattern.findall(text)
            for cfg in matches:
                cfg = cfg.rstrip('.,;:)\'\"')
                self.db.insert_vpn_config(channel_name, config_type, cfg, starred)
                found['config'] += 1
                log.info(f"  [{config_type.upper()}] {channel_name}: {cfg[:60]}...")

        return found

    async def collect_from_channel(self, entity, channel_username: str):
        """Collect up to limit relevant messages from a channel."""
        starred = self.is_starred(channel_username)
        limit = self.get_limit(channel_username)

        log.info(f"\n{'━'*50}")
        log.info(f"Channel: @{channel_username} | starred={starred} | limit={limit}")

        total_useful = 0
        checked = 0
        max_scan = 50  # scan up to 50 messages to find `limit` useful ones

        try:
            async for msg in self.client.iter_messages(entity, limit=max_scan):
                if total_useful >= limit:
                    break
                checked += 1

                found = await self.process_message(msg, channel_username, starred)
                total_count = sum(found.values())
                if total_count > 0:
                    total_useful += 1
                    log.info(f"  msg_id={msg.id} → npvt={found['npvt']} proxy={found['proxy']} cfg={found['config']}")

                # Be polite to Telegram
                await asyncio.sleep(0.3)

        except FloodWaitError as e:
            log.warning(f"FloodWait for @{channel_username}: sleeping {e.seconds}s")
            await asyncio.sleep(e.seconds)
        except Exception as e:
            log.error(f"Error scanning @{channel_username}: {e}")

        log.info(f"@{channel_username}: scanned {checked} msgs, found {total_useful} useful")

    async def collect_all(self):
        """Collect from ALL joined channels/groups."""
        log.info("=" * 60)
        log.info("Starting collection cycle...")
        log.info("=" * 60)

        dialogs = await self.client.get_dialogs()
        channels = []

        for dialog in dialogs:
            entity = dialog.entity
            # Only channels (broadcasts), not groups or private chats
            if hasattr(entity, 'broadcast') and entity.broadcast:
                username = getattr(entity, 'username', None)
                if not username:
                    # Use channel ID if no username
                    username = f"id_{entity.id}"
                channels.append((entity, username))

        log.info(f"Found {len(channels)} channel(s) to process.")

        for entity, username in channels:
            await self.collect_from_channel(entity, username)
            # Small delay between channels
            await asyncio.sleep(1)

        log.info("=" * 60)
        log.info("Collection cycle complete.")
        log.info("=" * 60)


# ============================================================
#  MAIN LOOP
# ============================================================
async def main():
    db = DatabaseManager()
    db.connect()
    db.ensure_tables()

    client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
    await client.start()
    log.info("Telegram client started.")

    collector = VPNCollector(client, db)

    CYCLE_MINUTES = 30  # refresh interval

    try:
        while True:
            cycle_start = datetime.now()
            log.info(f"\n🔄 New cycle started at {cycle_start.strftime('%H:%M:%S')}")

            # 1) Wipe old data
            db.clear_all()

            # 2) Collect fresh data
            await collector.collect_all()

            # 3) Calculate how long to sleep until next cycle
            elapsed = (datetime.now() - cycle_start).total_seconds()
            sleep_time = max(0, CYCLE_MINUTES * 60 - elapsed)
            log.info(f"Next cycle in {sleep_time/60:.1f} minutes...")
            await asyncio.sleep(sleep_time)

    except KeyboardInterrupt:
        log.info("Stopped by user.")
    finally:
        await client.disconnect()
        db.close()


if __name__ == '__main__':
    asyncio.run(main())
