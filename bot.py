"""
Telegram Group Broadcaster Bot — fully inline-button driven UI
"""

import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
)

from config import Config
from account_manager import AccountManager
from broadcaster import Broadcaster
from db import Database

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

bot = Client(
    "broadcaster_bot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN,
)

db = Database()
account_manager = AccountManager(db)
broadcaster = Broadcaster(db, account_manager)


# ── Keyboards ─────────────────────────────────────────────────────────────────

def kb_main():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 Accounts", callback_data="menu_accounts"),
         InlineKeyboardButton("📣 Broadcast", callback_data="menu_broadcast")],
        [InlineKeyboardButton("⚙️ Config", callback_data="menu_config"),
         InlineKeyboardButton("📊 Status", callback_data="menu_status")],
        [InlineKeyboardButton("📢 Set Log Channel", callback_data="set_log_channel")],
    ])

def kb_accounts(accounts):
    rows = []
    for acc in accounts:
        icon = "🟢" if acc["active"] else "🔴"
        rows.append([InlineKeyboardButton(
            f"{icon} {acc['phone']} — {acc.get('label','—')}",
            callback_data=f"acc_detail:{acc['phone']}"
        )])
    rows.append([InlineKeyboardButton("➕ Add Account", callback_data="add_account_start")])
    rows.append([InlineKeyboardButton("🔙 Back", callback_data="menu_main")])
    return InlineKeyboardMarkup(rows)

def kb_account_detail(phone):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✏️ Edit Label", callback_data=f"edit_label:{phone}"),
         InlineKeyboardButton("📝 Edit Ad Text", callback_data=f"edit_ad:{phone}")],
        [InlineKeyboardButton("🔄 Refresh Groups", callback_data=f"refresh_groups:{phone}")],
        [InlineKeyboardButton("🗑 Remove Account", callback_data=f"remove_acc:{phone}")],
        [InlineKeyboardButton("🔙 Back", callback_data="menu_accounts")],
    ])

def kb_broadcast(has_message):
    rows = [
        [InlineKeyboardButton("✏️ Set Message", callback_data="set_message")],
    ]
    if has_message:
        rows.append([InlineKeyboardButton("👁 Preview Message", callback_data="preview_message")])
        rows.append([InlineKeyboardButton("🚀 Start Broadcast", callback_data="confirm_broadcast")])
    if broadcaster.get_status()["running"]:
        rows.append([InlineKeyboardButton("🛑 Stop Broadcast", callback_data="stop_broadcast")])
    rows.append([InlineKeyboardButton("🔙 Back", callback_data="menu_main")])
    return InlineKeyboardMarkup(rows)

def kb_config(cfg):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(f"⏱ Group Interval: {cfg['group_interval']}s", callback_data="cfg_group_interval")],
        [InlineKeyboardButton(f"📦 Batch Size: {cfg['batch_size']} groups", callback_data="cfg_batch_size")],
        [InlineKeyboardButton(f"⏸ Batch Pause: {cfg['batch_interval']}s", callback_data="cfg_batch_interval")],
        [InlineKeyboardButton("🔙 Back", callback_data="menu_main")],
    ])

def kb_confirm_broadcast():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Confirm", callback_data="do_broadcast"),
         InlineKeyboardButton("❌ Cancel", callback_data="menu_broadcast")],
    ])

def kb_back(target="menu_main"):
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data=target)]])


# ── Guards ────────────────────────────────────────────────────────────────────

def is_admin(uid): return uid in Config.ADMIN_IDS

def admin_only(func):
    async def wrapper(client, message: Message):
        if not is_admin(message.from_user.id):
            await message.reply("⛔ Unauthorized.")
            return
        return await func(client, message)
    wrapper.__name__ = func.__name__
    return wrapper

def admin_cb(func):
    async def wrapper(client, cb: CallbackQuery):
        if not is_admin(cb.from_user.id):
            await cb.answer("⛔ Unauthorized", show_alert=True)
            return
        return await func(client, cb)
    wrapper.__name__ = func.__name__
    return wrapper


# ── /start ────────────────────────────────────────────────────────────────────

@bot.on_message(filters.command("start") & filters.private)
@admin_only
async def cmd_start(client, message: Message):
    await message.reply(
        "📣 <b>Telegram Group Broadcaster</b>\n\nChoose an option below:",
        reply_markup=kb_main()
    )


# ── Main menu ─────────────────────────────────────────────────────────────────

@bot.on_callback_query(filters.regex("^menu_main$"))
@admin_cb
async def cb_menu_main(client, cb: CallbackQuery):
    await cb.message.edit_text(
        "📣 <b>Telegram Group Broadcaster</b>\n\nChoose an option below:",
        reply_markup=kb_main()
    )


# ── Accounts menu ─────────────────────────────────────────────────────────────

@bot.on_callback_query(filters.regex("^menu_accounts$"))
@admin_cb
async def cb_menu_accounts(client, cb: CallbackQuery):
    accounts = account_manager.list_accounts()
    total_groups = sum(a.get("group_count", 0) for a in accounts)
    text = (
        f"👤 <b>Accounts ({len(accounts)})</b>\n"
        f"Total groups across all accounts: <b>{total_groups}</b>\n\n"
        "Tap an account to manage it, or add a new one."
    )
    await cb.message.edit_text(text, reply_markup=kb_accounts(accounts))


@bot.on_callback_query(filters.regex("^acc_detail:"))
@admin_cb
async def cb_acc_detail(client, cb: CallbackQuery):
    phone = cb.data.split(":", 1)[1]
    acc = db.get_account(phone)
    if not acc:
        await cb.answer("Account not found.", show_alert=True)
        return
    ad_preview = (acc.get("ad_message") or "<i>Uses default broadcast message</i>")[:100]
    text = (
        f"👤 <b>{acc.get('label', phone)}</b>\n\n"
        f"📱 Phone: <code>{phone}</code>\n"
        f"👥 Groups: <b>{acc.get('group_count', 0)}</b>\n"
        f"📝 Ad text:\n{ad_preview}"
    )
    await cb.message.edit_text(text, reply_markup=kb_account_detail(phone))


# ── Add account flow ──────────────────────────────────────────────────────────

@bot.on_callback_query(filters.regex("^add_account_start$"))
@admin_cb
async def cb_add_account_start(client, cb: CallbackQuery):
    db.set_user_state(cb.from_user.id, "awaiting_phone")
    await cb.message.edit_text(
        "📱 <b>Step 1 of 3 — Phone Number</b>\n\n"
        "Send your phone number with country code:\n"
        "Example: <code>+919876543210</code>",
        reply_markup=kb_back("menu_accounts")
    )


@bot.on_callback_query(filters.regex("^edit_label:"))
@admin_cb
async def cb_edit_label(client, cb: CallbackQuery):
    phone = cb.data.split(":", 1)[1]
    db.set_user_state(cb.from_user.id, f"awaiting_label:{phone}")
    await cb.message.edit_text(
        f"✏️ <b>Edit Label</b> for <code>{phone}</code>\n\nSend the new label/name:",
        reply_markup=kb_back(f"acc_detail:{phone}")
    )


@bot.on_callback_query(filters.regex("^edit_ad:"))
@admin_cb
async def cb_edit_ad(client, cb: CallbackQuery):
    phone = cb.data.split(":", 1)[1]
    db.set_user_state(cb.from_user.id, f"awaiting_ad:{phone}")
    await cb.message.edit_text(
        f"📝 <b>Edit Ad Message</b> for <code>{phone}</code>\n\n"
        "Send the custom ad text for this account.\n"
        "Leave blank (send <code>-</code>) to use the default message.",
        reply_markup=kb_back(f"acc_detail:{phone}")
    )


@bot.on_callback_query(filters.regex("^refresh_groups:"))
@admin_cb
async def cb_refresh_groups(client, cb: CallbackQuery):
    phone = cb.data.split(":", 1)[1]
    await cb.answer("Fetching groups…")
    await cb.message.edit_text(f"🔄 Fetching groups for <code>{phone}</code>…")
    groups = await account_manager.get_groups(phone)
    acc = db.get_account(phone)
    await cb.message.edit_text(
        f"✅ Found <b>{len(groups)}</b> groups for <code>{phone}</code>",
        reply_markup=kb_account_detail(phone)
    )


@bot.on_callback_query(filters.regex("^remove_acc:"))
@admin_cb
async def cb_remove_acc(client, cb: CallbackQuery):
    phone = cb.data.split(":", 1)[1]
    await account_manager.remove_account(phone)
    await cb.message.edit_text(
        f"✅ Account <code>{phone}</code> removed.",
        reply_markup=kb_back("menu_accounts")
    )


# ── Broadcast menu ────────────────────────────────────────────────────────────

@bot.on_callback_query(filters.regex("^menu_broadcast$"))
@admin_cb
async def cb_menu_broadcast(client, cb: CallbackQuery):
    msg_text = db.get_global_config("broadcast_message")
    status = broadcaster.get_status()
    text = "📣 <b>Broadcast</b>\n\n"
    if status["running"]:
        text += (
            f"🟢 <b>Broadcast running</b>\n"
            f"✅ Sent: {status['sent']} | ❌ Failed: {status['failed']}\n"
            f"📈 {status['progress']}\n\n"
        )
    if msg_text:
        preview = msg_text[:80] + ("…" if len(msg_text) > 80 else "")
        text += f"📝 <b>Current message:</b>\n<i>{preview}</i>"
    else:
        text += "⚠️ No message set yet."
    await cb.message.edit_text(text, reply_markup=kb_broadcast(bool(msg_text)))


@bot.on_callback_query(filters.regex("^set_message$"))
@admin_cb
async def cb_set_message(client, cb: CallbackQuery):
    db.set_user_state(cb.from_user.id, "awaiting_broadcast_message")
    await cb.message.edit_text(
        "✏️ <b>Set Broadcast Message</b>\n\n"
        "Send the message to broadcast to all groups.\n"
        "Supports HTML: <b>bold</b>, <i>italic</i>, <code>code</code>, links.",
        reply_markup=kb_back("menu_broadcast")
    )


@bot.on_callback_query(filters.regex("^preview_message$"))
@admin_cb
async def cb_preview_message(client, cb: CallbackQuery):
    msg_text = db.get_global_config("broadcast_message")
    accounts = account_manager.list_accounts()
    cfg = db.get_broadcast_config()
    total_groups = sum(a.get("group_count", 0) for a in accounts)
    await cb.message.edit_text(
        f"👁 <b>Preview</b>\n\n"
        f"{msg_text}\n\n"
        f"<b>───────────────</b>\n"
        f"👤 Accounts: {len(accounts)}\n"
        f"👥 ~{total_groups} groups total\n"
        f"⏱ Interval: {cfg['group_interval']}s | Batch: {cfg['batch_size']} → {cfg['batch_interval']}s pause",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 Start Broadcast", callback_data="confirm_broadcast")],
            [InlineKeyboardButton("✏️ Edit Message", callback_data="set_message")],
            [InlineKeyboardButton("🔙 Back", callback_data="menu_broadcast")],
        ])
    )


@bot.on_callback_query(filters.regex("^confirm_broadcast$"))
@admin_cb
async def cb_confirm_broadcast(client, cb: CallbackQuery):
    if broadcaster.get_status()["running"]:
        await cb.answer("Already running!", show_alert=True)
        return
    accounts = account_manager.list_accounts()
    total_groups = sum(a.get("group_count", 0) for a in accounts)
    cfg = db.get_broadcast_config()
    await cb.message.edit_text(
        f"🚀 <b>Confirm Broadcast</b>\n\n"
        f"👤 Accounts: <b>{len(accounts)}</b>\n"
        f"👥 Groups: ~<b>{total_groups}</b>\n"
        f"⏱ Delay: {cfg['group_interval']}s between groups\n"
        f"📦 Batch: {cfg['batch_size']} groups then {cfg['batch_interval']}s pause\n\n"
        "Ready to start?",
        reply_markup=kb_confirm_broadcast()
    )


@bot.on_callback_query(filters.regex("^do_broadcast$"))
@admin_cb
async def cb_do_broadcast(client, cb: CallbackQuery):
    status_msg = await cb.message.edit_text("⏳ Starting broadcast…")
    asyncio.create_task(broadcaster.run(bot, cb.from_user.id, status_msg))


@bot.on_callback_query(filters.regex("^stop_broadcast$"))
@admin_cb
async def cb_stop_broadcast(client, cb: CallbackQuery):
    broadcaster.stop_flag = True
    await cb.answer("🛑 Stop signal sent.", show_alert=True)
    await cb.message.edit_text(
        "🛑 Stop signal sent. Will halt after current group.",
        reply_markup=kb_back("menu_broadcast")
    )


# ── Config menu ───────────────────────────────────────────────────────────────

@bot.on_callback_query(filters.regex("^menu_config$"))
@admin_cb
async def cb_menu_config(client, cb: CallbackQuery):
    cfg = db.get_broadcast_config()
    await cb.message.edit_text(
        "⚙️ <b>Configuration</b>\n\nTap a setting to change it:",
        reply_markup=kb_config(cfg)
    )


@bot.on_callback_query(filters.regex("^cfg_"))
@admin_cb
async def cb_cfg_item(client, cb: CallbackQuery):
    key = cb.data  # cfg_group_interval / cfg_batch_size / cfg_batch_interval
    labels = {
        "cfg_group_interval":  ("group_interval",  "⏱ Group Interval", "seconds between each group message", "5"),
        "cfg_batch_size":      ("batch_size",       "📦 Batch Size",     "groups per batch before pausing",    "10"),
        "cfg_batch_interval":  ("batch_interval",   "⏸ Batch Pause",    "seconds to pause between batches",   "60"),
    }
    db_key, title, desc, example = labels[key]
    db.set_user_state(cb.from_user.id, f"awaiting_cfg:{db_key}")
    await cb.message.edit_text(
        f"⚙️ <b>{title}</b>\n\n{desc}\n\nCurrent: <b>{db.get_global_config(db_key)}</b>\n\nSend a number:",
        reply_markup=kb_back("menu_config")
    )


# ── Status menu ───────────────────────────────────────────────────────────────

@bot.on_callback_query(filters.regex("^menu_status$"))
@admin_cb
async def cb_menu_status(client, cb: CallbackQuery):
    s = broadcaster.get_status()
    stats = db.get_broadcast_stats()
    log_ch = db.get_global_config("log_channel") or "Not set"
    text = (
        f"📊 <b>Status</b>\n\n"
        f"Running: {'🟢 Yes' if s['running'] else '🔴 No'}\n"
        f"✅ Sent: {s['sent']}\n"
        f"❌ Failed: {s['failed']}\n"
        f"⏳ Flood waits: {s['flood_waits']}\n"
        f"👤 Account: <code>{s.get('current_account','—')}</code>\n"
        f"📈 Progress: {s['progress']}\n\n"
        f"<b>Last 24h totals:</b>\n"
        f"✅ {stats.get('sent',0)} sent | ❌ {stats.get('failed',0)} failed | ⏳ {stats.get('flood_waits',0)} flood waits\n\n"
        f"📢 Log channel: <code>{log_ch}</code>"
    )
    await cb.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh", callback_data="menu_status")],
            [InlineKeyboardButton("🔙 Back", callback_data="menu_main")],
        ])
    )


# ── Log channel ───────────────────────────────────────────────────────────────

@bot.on_callback_query(filters.regex("^set_log_channel$"))
@admin_cb
async def cb_set_log_channel(client, cb: CallbackQuery):
    db.set_user_state(cb.from_user.id, "awaiting_log_channel")
    current = db.get_global_config("log_channel") or "Not set"
    await cb.message.edit_text(
        f"📢 <b>Set Log Channel</b>\n\n"
        f"Current: <code>{current}</code>\n\n"
        "Send the channel username or ID:\n"
        "Example: <code>@mybotlogs</code> or <code>-100123456789</code>\n\n"
        "⚠️ Add this bot as <b>admin</b> in that channel first.",
        reply_markup=kb_back("menu_main")
    )


# ── Universal text input handler ──────────────────────────────────────────────

@bot.on_message(filters.private & filters.text & ~filters.command(["start"]))
@admin_only
async def handle_states(client, message: Message):
    uid = message.from_user.id
    state = db.get_user_state(uid)
    if not state:
        await message.reply("Use /start to open the menu.")
        return

    text = message.text.strip()

    # ── Phone number ──
    if state == "awaiting_phone":
        db.set_user_state(uid, None)
        msg = await message.reply(f"🔐 Sending OTP to <code>{text}</code>…")
        result = await account_manager.start_login(text, text, None)
        if result["status"] == "otp_sent":
            db.set_user_state(uid, f"awaiting_otp:{text}")
            await msg.edit_text(
                f"✅ OTP sent to <code>{text}</code>\n\n"
                "<b>Step 2 of 3 — Enter OTP</b>\n"
                "Send the code you received:"
            )
        else:
            await msg.edit_text(
                f"❌ {result.get('error','Unknown error')}",
                reply_markup=kb_back("menu_accounts")
            )

    # ── OTP ──
    elif state and state.startswith("awaiting_otp:"):
        phone = state.split(":", 1)[1]
        db.set_user_state(uid, None)
        msg = await message.reply("🔄 Verifying OTP…")
        result = await account_manager.complete_login(phone, text)
        if result["status"] == "2fa_required":
            db.set_user_state(uid, f"awaiting_2fa:{phone}")
            await msg.edit_text(
                "🔒 <b>2FA Enabled</b>\n\nSend your cloud password:"
            )
        elif result["status"] == "success":
            db.set_user_state(uid, f"awaiting_label_new:{phone}")
            acc = db.get_account(phone)
            await msg.edit_text(
                f"✅ Logged in! Found <b>{acc.get('group_count',0)}</b> groups.\n\n"
                "<b>Step 3a — Account Label</b>\n"
                "Send a name/label for this account:\n"
                "Example: <code>Main Shop</code>"
            )
        else:
            await msg.edit_text(
                f"❌ {result.get('error')}",
                reply_markup=kb_back("menu_accounts")
            )

    # ── 2FA ──
    elif state and state.startswith("awaiting_2fa:"):
        phone = state.split(":", 1)[1]
        db.set_user_state(uid, None)
        msg = await message.reply("🔄 Verifying password…")
        result = await account_manager.complete_2fa(phone, text)
        if result["status"] == "success":
            db.set_user_state(uid, f"awaiting_label_new:{phone}")
            acc = db.get_account(phone)
            await msg.edit_text(
                f"✅ Logged in! Found <b>{acc.get('group_count',0)}</b> groups.\n\n"
                "<b>Step 3a — Account Label</b>\n"
                "Send a name/label for this account:"
            )
        else:
            await msg.edit_text(
                f"❌ {result.get('error')}",
                reply_markup=kb_back("menu_accounts")
            )

    # ── New account label (after successful login) ──
    elif state and state.startswith("awaiting_label_new:"):
        phone = state.split(":", 1)[1]
        db.set_user_state(uid, f"awaiting_ad_new:{phone}")
        db.update_account_label(phone, text)
        await message.reply(
            f"✅ Label set to <b>{text}</b>\n\n"
            "<b>Step 3b — Custom Ad Message</b>\n"
            "Send the ad message for this account.\n"
            "Or send <code>-</code> to use the default broadcast message."
        )

    # ── New account ad text (after label) ──
    elif state and state.startswith("awaiting_ad_new:"):
        phone = state.split(":", 1)[1]
        db.set_user_state(uid, None)
        ad = None if text == "-" else text
        db.update_account_ad(phone, ad)
        acc = db.get_account(phone)
        await message.reply(
            f"🎉 <b>Account setup complete!</b>\n\n"
            f"📱 Phone: <code>{phone}</code>\n"
            f"🏷 Label: {acc.get('label', phone)}\n"
            f"👥 Groups: {acc.get('group_count', 0)}\n"
            f"📝 Ad: {'Custom' if ad else 'Using default'}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👤 View Accounts", callback_data="menu_accounts")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")],
            ])
        )

    # ── Edit existing label ──
    elif state and state.startswith("awaiting_label:"):
        phone = state.split(":", 1)[1]
        db.set_user_state(uid, None)
        db.update_account_label(phone, text)
        await message.reply(
            f"✅ Label updated to <b>{text}</b>",
            reply_markup=kb_account_detail(phone)
        )

    # ── Edit existing ad ──
    elif state and state.startswith("awaiting_ad:"):
        phone = state.split(":", 1)[1]
        db.set_user_state(uid, None)
        ad = None if text == "-" else text
        db.update_account_ad(phone, ad)
        await message.reply(
            f"✅ Ad message {'cleared (using default)' if not ad else 'updated'}.",
            reply_markup=kb_account_detail(phone)
        )

    # ── Broadcast message ──
    elif state == "awaiting_broadcast_message":
        db.set_user_state(uid, None)
        db.set_global_config("broadcast_message", text)
        await message.reply(
            "✅ Broadcast message saved!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👁 Preview", callback_data="preview_message")],
                [InlineKeyboardButton("🚀 Broadcast", callback_data="confirm_broadcast")],
                [InlineKeyboardButton("🔙 Menu", callback_data="menu_broadcast")],
            ])
        )

    # ── Config value ──
    elif state and state.startswith("awaiting_cfg:"):
        cfg_key = state.split(":", 1)[1]
        db.set_user_state(uid, None)
        if not text.isdigit():
            await message.reply("❌ Please send a number.", reply_markup=kb_back("menu_config"))
            return
        db.set_global_config(cfg_key, text)
        cfg = db.get_broadcast_config()
        await message.reply(
            f"✅ Updated! New config:\n"
            f"⏱ Group interval: {cfg['group_interval']}s\n"
            f"📦 Batch size: {cfg['batch_size']} groups\n"
            f"⏸ Batch pause: {cfg['batch_interval']}s",
            reply_markup=kb_back("menu_config")
        )

    # ── Log channel ──
    elif state == "awaiting_log_channel":
        db.set_user_state(uid, None)
        db.set_global_config("log_channel", text)
        await message.reply(
            f"✅ Log channel set to <code>{text}</code>",
            reply_markup=kb_back("menu_main")
        )


if __name__ == "__main__":
    logger.info("Starting Broadcaster Bot…")
    bot.run()
