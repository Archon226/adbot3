"""
Configuration — edit this file or set environment variables.
"""
import os
from typing import List


class Config:
    # ── Bot credentials (get from @BotFather) ─────────────────────────────────
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

    # ── Telegram API credentials (get from my.telegram.org) ──────────────────
    API_ID: int = int(os.getenv("API_ID", "0"))
    API_HASH: str = os.getenv("API_HASH", "YOUR_API_HASH_HERE")

    # ── Admin Telegram user IDs (get yours via @userinfobot) ─────────────────
    ADMIN_IDS: List[int] = [
        int(x) for x in os.getenv("ADMIN_IDS", "0").split(",") if x.strip().isdigit()
    ]

    # ── Default broadcast config (overridable via /setconfig) ─────────────────
    DEFAULT_GROUP_INTERVAL: int = int(os.getenv("GROUP_INTERVAL", "5"))    # seconds between each group
    DEFAULT_BATCH_SIZE: int = int(os.getenv("BATCH_SIZE", "10"))           # groups per batch
    DEFAULT_BATCH_INTERVAL: int = int(os.getenv("BATCH_INTERVAL", "60"))   # seconds between batches

    # ── File paths ────────────────────────────────────────────────────────────
    DB_PATH: str = os.getenv("DB_PATH", "broadcaster.db")
    SESSIONS_DIR: str = os.getenv("SESSIONS_DIR", "accounts")
