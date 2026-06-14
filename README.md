# 📣 Telegram Group Broadcaster Bot

A Pyrogram + Telethon powered Telegram bot for broadcasting messages to all groups
across multiple user-owned accounts (userbots). Admin-only, with live logs, intervals,
batch control, flood-wait handling, and per-account custom ad messages.

---

## Features

- ✅ Multiple user accounts (userbots) with individual ad messages
- ✅ Broadcasts to every group each account is joined in
- ✅ Configurable group-to-group interval, batch size, and batch pause
- ✅ Flood-wait detection with auto-retry
- ✅ SlowMode & permission error handling
- ✅ Live log channel (sent ✅ / failed ❌ / flood-wait ⏳ with group post links)
- ✅ Admin-only access (whitelist by user ID)
- ✅ Persistent SQLite storage (accounts, config, logs)
- ✅ Session files stored securely per account

---

## Setup

### 1. Clone / copy this folder

```bash
cd tg-broadcaster
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Get credentials

| What | Where |
|------|-------|
| `BOT_TOKEN` | [@BotFather](https://t.me/BotFather) → /newbot |
| `API_ID` + `API_HASH` | [my.telegram.org](https://my.telegram.org) → App |
| `ADMIN_IDS` | [@userinfobot](https://t.me/userinfobot) → your user ID |

### 4. Configure

```bash
cp .env.example .env
nano .env   # fill in BOT_TOKEN, API_ID, API_HASH, ADMIN_IDS
```

### 5. Run

```bash
python bot.py
```

---

## Bot Commands

### Account Management

| Command | Description |
|---------|-------------|
| `/addaccount` | Add a Telegram user account (supports OTP + 2FA) |
| `/listaccounts` | List all added accounts and group counts |
| `/removeaccount` | Remove an account and delete its session |

**Adding an account:**
Send details in this format when prompted:
```
+919876543210 | My Shop Account | 🔥 Check out our deals at t.me/myshop!
```
Or without a custom message (uses the default):
```
+919876543210 | My Shop Account
```

### Broadcast

| Command | Description |
|---------|-------------|
| `/setmessage` | Set the default broadcast message |
| `/setconfig` | Set intervals and batch size |
| `/preview` | Preview message + config before sending |
| `/broadcast` | Start broadcasting |
| `/stop` | Stop an ongoing broadcast |

**Config format** (`/setconfig`):
```
GROUP_INTERVAL | BATCH_SIZE | BATCH_INTERVAL
5 | 10 | 60
```
- `GROUP_INTERVAL` — seconds to wait between each group message
- `BATCH_SIZE` — how many groups to send to before pausing
- `BATCH_INTERVAL` — seconds to pause between batches

### Logs & Status

| Command | Description |
|---------|-------------|
| `/setlogchannel` | Set a channel for live broadcast logs |
| `/status` | View current broadcast progress |

**Log channel setup:**
1. Create a Telegram channel
2. Add your bot as admin
3. Run `/setlogchannel` and send `@yourchannel` or the channel ID

---

## Log Channel Format

Each event posts automatically:

```
✅ Sent | My Group Name
📎 https://t.me/groupname/123
👤 +919876543210

❌ Failed | Another Group | +91...
`ChatWriteForbiddenError`

⏳ FloodWait 30s | Some Group | +91...
```

---

## Project Structure

```
tg-broadcaster/
├── bot.py              # Pyrogram bot — commands, menus, state machine
├── broadcaster.py      # Broadcast engine — sends, handles errors, logs
├── account_manager.py  # Telethon user account login & session management
├── db.py               # SQLite — accounts, config, state, logs
├── config.py           # Env-based configuration
├── requirements.txt
├── .env.example
└── accounts/           # Telethon .session files (auto-created)
```

---

## How It Works

1. **Bot** (Pyrogram) runs as your admin control panel
2. **Userbots** (Telethon) log into your personal accounts and do the actual sending
3. Each account has its own `.session` file — login once, reconnects automatically
4. On `/broadcast`: for each account → fetch all joined groups → send message → wait → repeat

---

## Notes

- Accounts are **your own** Telegram numbers, used as userbots
- Session files are stored locally in `accounts/` — keep them secure
- The bot only responds to users listed in `ADMIN_IDS`
- Flood waits are handled automatically with a retry after the wait period
- Groups where you lack send permissions are skipped and logged as failed
