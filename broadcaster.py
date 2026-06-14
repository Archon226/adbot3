"""
Broadcaster — sends the configured message to every group for each account.
Supports: group interval, batch size/interval, flood-wait handling, live logs.
"""
import asyncio
import logging
from typing import Optional

from pyrogram import Client
from pyrogram.types import Message
from telethon.errors import (
    FloodWaitError, ChatWriteForbiddenError, UserBannedInChannelError,
    SlowModeWaitError, ChannelPrivateError, MsgIdInvalidError,
)

from db import Database
from account_manager import AccountManager

logger = logging.getLogger(__name__)


class Broadcaster:
    def __init__(self, db: Database, account_manager: AccountManager):
        self.db = db
        self.account_manager = account_manager
        self.stop_flag = False
        self._status = {
            "running": False,
            "sent": 0,
            "failed": 0,
            "flood_waits": 0,
            "current_account": None,
            "progress": "—",
        }

    def get_status(self) -> dict:
        return dict(self._status)

    async def run(self, bot: Client, admin_id: int, status_msg: Message):
        self.stop_flag = False
        self._status = {"running": True, "sent": 0, "failed": 0, "flood_waits": 0,
                        "current_account": None, "progress": "—"}

        cfg = self.db.get_broadcast_config()
        group_interval  = cfg["group_interval"]
        batch_size      = cfg["batch_size"]
        batch_interval  = cfg["batch_interval"]
        default_message = self.db.get_global_config("broadcast_message")
        log_channel     = self.db.get_global_config("log_channel")
        accounts        = self.account_manager.list_accounts()

        if not accounts:
            await status_msg.edit_text("❌ No accounts found.")
            return
        if not default_message:
            await status_msg.edit_text("❌ No broadcast message set.")
            return

        total_sent = 0
        total_failed = 0
        total_fw = 0

        for acc in accounts:
            if self.stop_flag:
                break

            phone = acc["phone"]
            label = acc.get("label", phone)
            message_text = acc.get("ad_message") or default_message
            self._status["current_account"] = phone

            await status_msg.edit_text(
                f"📡 Broadcasting via <b>{label}</b> (<code>{phone}</code>)…\n"
                f"Sent: {total_sent} | Failed: {total_failed}"
            )

            client = await self.account_manager.get_client(phone)
            if not client:
                await self._log(bot, log_channel, f"❌ Could not connect account <code>{phone}</code>")
                continue

            groups = await self.account_manager.get_groups(phone)
            total_groups = len(groups)
            sent = failed = 0

            for i, group in enumerate(groups, 1):
                if self.stop_flag:
                    break

                self._status["progress"] = f"{i}/{total_groups} groups (acc: {label})"
                gid    = group["id"]
                gtitle = group["title"]

                try:
                    sent_msg = await client.send_message(gid, message_text)
                    sent += 1
                    total_sent += 1
                    self._status["sent"] = total_sent

                    # Build message link
                    username = group.get("username")
                    if username:
                        link = f"https://t.me/{username}/{sent_msg.id}"
                    else:
                        # For private groups, use numeric ID format
                        clean_id = str(gid).lstrip("-100").lstrip("-")
                        link = f"https://t.me/c/{clean_id}/{sent_msg.id}"

                    self.db.log_broadcast(phone, str(gid), gtitle, "sent", link)
                    await self._log(bot, log_channel,
                        f"✅ Sent | <b>{gtitle}</b>\n📎 {link}\n👤 <code>{phone}</code>")

                except FloodWaitError as e:
                    wait = e.seconds
                    total_fw += 1
                    self._status["flood_waits"] = total_fw
                    self.db.log_broadcast(phone, str(gid), gtitle, "flood_wait",
                                          error=f"FloodWait {wait}s")
                    await self._log(bot, log_channel,
                        f"⏳ FloodWait <b>{wait}s</b> | <b>{gtitle}</b> | <code>{phone}</code>")
                    await asyncio.sleep(wait + 2)
                    # Retry once after wait
                    try:
                        sent_msg = await client.send_message(gid, message_text)
                        sent += 1
                        total_sent += 1
                        self._status["sent"] = total_sent
                        username = group.get("username")
                        link = (f"https://t.me/{username}/{sent_msg.id}" if username
                                else f"https://t.me/c/{str(gid).lstrip('-100').lstrip('-')}/{sent_msg.id}")
                        self.db.log_broadcast(phone, str(gid), gtitle, "sent", link)
                        await self._log(bot, log_channel,
                            f"✅ Sent (retry) | <b>{gtitle}</b>\n📎 {link}\n👤 <code>{phone}</code>")
                    except Exception as retry_e:
                        failed += 1
                        total_failed += 1
                        self._status["failed"] = total_failed
                        self.db.log_broadcast(phone, str(gid), gtitle, "failed",
                                              error=str(retry_e))
                        await self._log(bot, log_channel,
                            f"❌ Failed (retry) | <b>{gtitle}</b> | <code>{phone}</code>\n<code>{retry_e}</code>")

                except (ChatWriteForbiddenError, UserBannedInChannelError, ChannelPrivateError) as e:
                    failed += 1
                    total_failed += 1
                    self._status["failed"] = total_failed
                    self.db.log_broadcast(phone, str(gid), gtitle, "failed", error=str(e))
                    await self._log(bot, log_channel,
                        f"🚫 No permission | <b>{gtitle}</b> | <code>{phone}</code>")

                except SlowModeWaitError as e:
                    wait = e.seconds
                    await self._log(bot, log_channel,
                        f"🐢 SlowMode <b>{wait}s</b> | <b>{gtitle}</b> | <code>{phone}</code> — skipping")
                    failed += 1
                    total_failed += 1
                    self._status["failed"] = total_failed
                    self.db.log_broadcast(phone, str(gid), gtitle, "failed",
                                          error=f"SlowMode {wait}s")

                except Exception as e:
                    failed += 1
                    total_failed += 1
                    self._status["failed"] = total_failed
                    self.db.log_broadcast(phone, str(gid), gtitle, "failed", error=str(e))
                    await self._log(bot, log_channel,
                        f"❌ Error | <b>{gtitle}</b> | <code>{phone}</code>\n<code>{e}</code>")

                # ── Batch logic ──
                if i % batch_size == 0 and i < total_groups:
                    await self._log(bot, log_channel,
                        f"⏸ Batch pause {batch_interval}s after {i} groups…")
                    await asyncio.sleep(batch_interval)
                else:
                    await asyncio.sleep(group_interval)

            await self._log(bot, log_channel,
                f"🏁 Done with <b>{label}</b> (<code>{phone}</code>)\n"
                f"✅ Sent: {sent} | ❌ Failed: {failed}")

        # ── Final summary ──
        self._status["running"] = False
        summary = (
            f"🎉 <b>Broadcast Complete!</b>\n\n"
            f"✅ Total Sent: {total_sent}\n"
            f"❌ Total Failed: {total_failed}\n"
            f"⏳ Flood Waits: {total_fw}\n"
            f"👤 Accounts used: {len(accounts)}"
        )
        try:
            await status_msg.edit_text(summary)
        except Exception:
            pass
        await self._log(bot, log_channel, summary)
        if admin_id:
            try:
                await bot.send_message(admin_id, summary)
            except Exception:
                pass

    async def _log(self, bot: Client, log_channel: Optional[str], text: str):
        """Post a log message to the log channel if configured."""
        logger.info(text.replace("**", "").replace("`", ""))
        if not log_channel:
            return
        try:
            await bot.send_message(log_channel, text,
                                   disable_web_page_preview=True)
        except Exception as e:
            logger.warning(f"Failed to post to log channel: {e}")
