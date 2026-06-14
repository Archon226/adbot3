"""
SQLite database for storing accounts, config, and state.
"""
import sqlite3
import json
from typing import Optional
from config import Config


class Database:
    def __init__(self):
        self.path = Config.DB_PATH
        self._init()

    def _conn(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self):
        with self._conn() as c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS accounts (
                    phone       TEXT PRIMARY KEY,
                    label       TEXT,
                    ad_message  TEXT,
                    active      INTEGER DEFAULT 1,
                    group_count INTEGER DEFAULT 0,
                    added_at    TEXT DEFAULT (datetime('now'))
                );

                CREATE TABLE IF NOT EXISTS global_config (
                    key   TEXT PRIMARY KEY,
                    value TEXT
                );

                CREATE TABLE IF NOT EXISTS user_state (
                    user_id INTEGER PRIMARY KEY,
                    state   TEXT
                );

                CREATE TABLE IF NOT EXISTS broadcast_log (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    phone       TEXT,
                    group_id    TEXT,
                    group_title TEXT,
                    status      TEXT,
                    message_link TEXT,
                    error       TEXT,
                    created_at  TEXT DEFAULT (datetime('now'))
                );
            """)
            # Seed defaults
            defaults = {
                "group_interval":  str(Config.DEFAULT_GROUP_INTERVAL),
                "batch_size":      str(Config.DEFAULT_BATCH_SIZE),
                "batch_interval":  str(Config.DEFAULT_BATCH_INTERVAL),
            }
            for k, v in defaults.items():
                c.execute("INSERT OR IGNORE INTO global_config(key,value) VALUES(?,?)", (k, v))

    # ── Config ────────────────────────────────────────────────────────────────
    def set_global_config(self, key: str, value: str):
        with self._conn() as c:
            c.execute("INSERT OR REPLACE INTO global_config(key,value) VALUES(?,?)", (key, value))

    def get_global_config(self, key: str) -> Optional[str]:
        with self._conn() as c:
            row = c.execute("SELECT value FROM global_config WHERE key=?", (key,)).fetchone()
            return row["value"] if row else None

    def get_broadcast_config(self) -> dict:
        return {
            "group_interval":  int(self.get_global_config("group_interval") or Config.DEFAULT_GROUP_INTERVAL),
            "batch_size":      int(self.get_global_config("batch_size")     or Config.DEFAULT_BATCH_SIZE),
            "batch_interval":  int(self.get_global_config("batch_interval") or Config.DEFAULT_BATCH_INTERVAL),
        }

    # ── User state ────────────────────────────────────────────────────────────
    def set_user_state(self, user_id: int, state: Optional[str]):
        with self._conn() as c:
            if state is None:
                c.execute("DELETE FROM user_state WHERE user_id=?", (user_id,))
            else:
                c.execute("INSERT OR REPLACE INTO user_state(user_id,state) VALUES(?,?)", (user_id, state))

    def get_user_state(self, user_id: int) -> Optional[str]:
        with self._conn() as c:
            row = c.execute("SELECT state FROM user_state WHERE user_id=?", (user_id,)).fetchone()
            return row["state"] if row else None

    # ── Accounts ──────────────────────────────────────────────────────────────
    def add_account(self, phone: str, label: str, ad_message: Optional[str] = None):
        with self._conn() as c:
            c.execute(
                "INSERT OR REPLACE INTO accounts(phone,label,ad_message) VALUES(?,?,?)",
                (phone, label, ad_message)
            )

    def remove_account(self, phone: str):
        with self._conn() as c:
            c.execute("DELETE FROM accounts WHERE phone=?", (phone,))

    def get_account(self, phone: str) -> Optional[dict]:
        with self._conn() as c:
            row = c.execute("SELECT * FROM accounts WHERE phone=?", (phone,)).fetchone()
            return dict(row) if row else None

    def list_accounts(self) -> list:
        with self._conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM accounts ORDER BY added_at").fetchall()]

    def update_group_count(self, phone: str, count: int):
        with self._conn() as c:
            c.execute("UPDATE accounts SET group_count=? WHERE phone=?", (count, phone))

    def update_account_label(self, phone: str, label: str):
        with self._conn() as c:
            c.execute("UPDATE accounts SET label=? WHERE phone=?", (label, phone))

    def update_account_ad(self, phone: str, ad_message):
        with self._conn() as c:
            c.execute("UPDATE accounts SET ad_message=? WHERE phone=?", (ad_message, phone))

    # ── Broadcast log ─────────────────────────────────────────────────────────
    def log_broadcast(self, phone: str, group_id: str, group_title: str,
                      status: str, message_link: str = None, error: str = None):
        with self._conn() as c:
            c.execute(
                "INSERT INTO broadcast_log(phone,group_id,group_title,status,message_link,error) VALUES(?,?,?,?,?,?)",
                (phone, group_id, group_title, status, message_link, error)
            )

    def get_broadcast_stats(self) -> dict:
        with self._conn() as c:
            row = c.execute("""
                SELECT
                    SUM(CASE WHEN status='sent'       THEN 1 ELSE 0 END) as sent,
                    SUM(CASE WHEN status='failed'     THEN 1 ELSE 0 END) as failed,
                    SUM(CASE WHEN status='flood_wait' THEN 1 ELSE 0 END) as flood_waits
                FROM broadcast_log
                WHERE created_at >= datetime('now', '-1 day')
            """).fetchone()
            return dict(row) if row else {"sent": 0, "failed": 0, "flood_waits": 0}
