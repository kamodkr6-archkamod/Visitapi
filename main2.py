# =====================================================
# KAMOD VISIT BOT - HYBRID FULL FIXED
# OWNER   : @kamod_codex
# CHANNEL : @kamod_codex
# 💀 KAMOD WILL RISE 💀
# =====================================================
import logging
import asyncio
import json
import binascii
import os
import sys
import urllib3
import threading
import time
import requests
import base64
import random
import html
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember
from telegram.ext import (
    ApplicationBuilder, ContextTypes, CommandHandler,
    CallbackQueryHandler, Application, MessageHandler, filters
)
from telegram.request import HTTPXRequest
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
import aiohttp
from colorama import Fore, Style, init

# 🔥 app.py proven modules
from byte import encrypt_api, Encrypt_ID
from visit_count_pb2 import Info

init(autoreset=True)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ================= PYTHON 3.14 EVENT LOOP FIX =================
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())
# =============================================================

# ================= CONFIGURATION =================
BOT_TOKEN = "8019676929:AAF4ikptwlqbQYuOprsvEZ4dJyRirbYVNwI"

ADMIN_ID = 7114540206
PREMIUM_USERS = [7114540206]
OFFICIAL_GROUP_ID = -1003288356121
OFFICIAL_GROUP_LINK = "https://t.me/KAMOD_LIKE_GROUP"
CHANNEL_LINK = "@KAMOD_CODEX"
GROUP_LINK = "@KAMOD_LIKE_GROUP"
MUST_JOIN_CHANNELS = ["@KAMOD_CODEX", "@KAMOD_CODEX_BACKUP"]

# 🔥 account.json (jo app.py me use hota hai) — same
INPUT_VISIT  = "account.json"
OUTPUT_VISIT = "token_ind_visit.json"

DAILY_USAGE = {}
AUTO_VISITS = {}
AUTO_VISIT_STATS = {}

LIVE_JOBS = {}
LOG_BUFFER = []

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)


def log(msg):
    ts = time.strftime('%H:%M:%S')
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    LOG_BUFFER.append(line)
    if len(LOG_BUFFER) > 300:
        LOG_BUFFER.pop(0)


# ==============================================================================
#             AUTO JWT GENERATOR
# ==============================================================================
REFRESH_INTERVAL = 16000

class AutoJWTGenerator:
    def __init__(self):
        self.api_url = "https://all-in-one-jwt.vercel.app/token"

    def fetch_jwt_from_api(self, uid, password):
        try:
            params = {"uid": uid, "password": password}
            response = requests.get(self.api_url, params=params, timeout=(4, 8))
            if response.status_code == 200:
                data = response.json()
                if data.get("success") and "jwt_token" in data:
                    return data["jwt_token"]
                if "jwt_token" in data:
                    return data["jwt_token"]
                if "token" in data:
                    return data["token"]
            return None
        except:
            return None

    def process_visit_accounts(self):
        if not os.path.exists(INPUT_VISIT):
            log(f"❌ {INPUT_VISIT} not found")
            return

        with open(INPUT_VISIT, "r", encoding="utf-8") as f:
            accounts = json.load(f)

        valid_tokens = []
        lock = threading.Lock()
        done = 0
        total = len(accounts)
        start = time.time()

        def worker(acc):
            uid = acc.get("uid")
            pwd = acc.get("password")
            if uid and pwd:
                token = self.fetch_jwt_from_api(uid, pwd)
                if token:
                    with lock:
                        valid_tokens.append({"token": token})
                    log(f"✅ VISIT TOKEN OK: {uid}")
                else:
                    log(f"❌ FAILED: {uid}")

        with ThreadPoolExecutor(max_workers=30) as executor:
            futures = [executor.submit(worker, acc) for acc in accounts]
            for f in as_completed(futures):
                done += 1
                f.result()
                if done % 50 == 0 or done == total:
                    elapsed = time.time() - start
                    log(f"   📊 Refresh {done}/{total} | OK={len(valid_tokens)} | {done/elapsed:.1f}/s")

        with open(OUTPUT_VISIT, "w", encoding="utf-8") as f:
            json.dump(valid_tokens, f, indent=4)

        log(f"💾 Saved {len(valid_tokens)} Visit Tokens in {time.time()-start:.1f}s")


def run_auto_refresher():
    generator = AutoJWTGenerator()
    log("🚀 AUTO TOKEN REFRESHER STARTED")
    while True:
        generator.process_visit_accounts()
        log("😴 Sleeping 7 Hours...")
        time.sleep(REFRESH_INTERVAL)


# ==============================================================================
#             TOKEN MEMORY
# ==============================================================================
MEM_TOKENS = []

def refresh_tokens_ram():
    global MEM_TOKENS
    while True:
        try:
            if os.path.exists(OUTPUT_VISIT):
                with open(OUTPUT_VISIT, 'r') as f:
                    MEM_TOKENS = json.load(f)
            log(f"🔄 Loaded {len(MEM_TOKENS)} Visit Tokens")
        except Exception as e:
            log(f"Token Load Error: {e}")
        time.sleep(300)


# ==============================================================================
#             FF API (OB55) — app.py proven
# ==============================================================================
def get_api_url(region):
    if region == "IND":
        return "https://client.ind.freefiremobile.com/GetPlayerPersonalShow"
    if region in {"BR", "US", "SAC", "NA"}:
        return "https://client.us.freefiremobile.com/GetPlayerPersonalShow"
    return "https://clientbp.ggblueshark.com/GetPlayerPersonalShow"


def make_visit_payload(uid):
    return bytes.fromhex(encrypt_api("08" + Encrypt_ID(str(uid)) + "1801"))


def parse_player_info(response_data):
    try:
        info = Info()
        info.ParseFromString(response_data)
        return {
            "uid": info.AccountInfo.UID or 0,
            "nickname": info.AccountInfo.PlayerNickname or "",
            "likes": info.AccountInfo.Likes or 0,
            "region": info.AccountInfo.PlayerRegion or "",
            "level": info.AccountInfo.Levels or 0,
        }
    except Exception as e:
        log(f"❌ Protobuf error: {e}")
        return None


async def send_visit(session, url, token, data, host):
    headers = {
        "ReleaseVersion": "OB55",
        "X-GA": "v1 1",
        "Authorization": f"Bearer {token}",
        "Host": host,
    }
    try:
        async with session.post(url, headers=headers, data=data, ssl=False) as r:
            if r.status == 200:
                return True, await r.read()
            return False, None
    except Exception:
        return False, None


async def get_profile_name(uid, tokens, region="IND"):
    url = get_api_url(region)
    host = url.replace("https://", "").split("/")[0]
    data = make_visit_payload(uid)

    valid_tokens = [t for t in tokens if t.get('token')]
    if not valid_tokens:
        return "Unknown User", "N/A"

    sample = random.sample(valid_tokens, min(len(valid_tokens), 30))

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8)) as session:
        for t in sample:
            ok, body = await send_visit(session, url, t['token'], data, host)
            if ok and body:
                info = parse_player_info(body)
                if info:
                    return info["nickname"], info["likes"]

    return "Unknown User", "N/A"


# ==============================================================================
#             VISIT PROCESSOR (LIVE COUNT)
# ==============================================================================
async def process_visit_task(chat_id, user_id, uid, region, tokens, context, msg_id, is_auto=False):

    if chat_id != OFFICIAL_GROUP_ID:
        keyboard = [[InlineKeyboardButton("👥 JOIN OFFICIAL GROUP", url="https://t.me/KAMOD_LIKE_GROUP")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id, message_id=msg_id,
                text=(
                    "╭━━━━━━━━━━━━━━━━━━━━✪\n"
                    "│ ❌ COMMAND NOT ALLOWED\n"
                    "╰━━━━━━━━━━━━━━━━━━━━✪\n\n"
                    "🚀 This bot works only in\n"
                    "OFFICIAL GROUP."
                ),
                reply_markup=reply_markup
            )
        except:
            pass
        return 0

    start_time = time.time()
    url = get_api_url(region)
    host = url.replace("https://", "").split("/")[0]
    data = make_visit_payload(uid)

    name_task = asyncio.create_task(get_profile_name(uid, tokens, region))

    valid_tokens = [t for t in tokens if t.get("token")]
    if not valid_tokens:
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id, message_id=msg_id,
                text="⚠️ No Valid Tokens Found!"
            )
        except:
            pass
        return 0

    target_success = 2000
    total_success = 0
    total_sent = 0
    first_response = None
    player_info = None
    last_edit = 0

    LIVE_JOBS[uid] = {
        "sent": 0, "success": 0, "fail": 0,
        "target": target_success,
        "status": "running",
        "started": time.strftime('%H:%M:%S'),
    }

    sem = asyncio.Semaphore(800)
    lock = asyncio.Lock()

    connector = aiohttp.TCPConnector(
        limit=0, limit_per_host=0, ttl_dns_cache=600,
        keepalive_timeout=60, enable_cleanup_closed=True,
        force_close=False, use_dns_cache=True,
    )
    timeout = aiohttp.ClientTimeout(total=15, connect=5)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        try:
            await session.head(url, ssl=False, timeout=aiohttp.ClientTimeout(total=5))
        except:
            pass

        async def worker(tok):
            nonlocal total_success, total_sent, first_response, player_info, last_edit
            async with sem:
                ok, body = await send_visit(session, url, tok, data, host)
                async with lock:
                    total_sent += 1
                    if ok:
                        total_success += 1
                        if first_response is None and body:
                            first_response = body
                            player_info = parse_player_info(body)
                    LIVE_JOBS[uid]["sent"] = total_sent
                    LIVE_JOBS[uid]["success"] = total_success
                    LIVE_JOBS[uid]["fail"] = total_sent - total_success

                    # live progress — har 100 pe
                    if total_sent % 100 == 0:
                        now = time.time()
                        if now - last_edit >= 1.2:
                            last_edit = now
                            percent = min(100, int(total_success * 100 / target_success))
                            filled = int(10 * percent / 100)
                            bar = "█" * filled + "░" * (10 - filled)
                            try:
                                asyncio.create_task(
                                    context.bot.edit_message_text(
                                        chat_id=chat_id, message_id=msg_id,
                                        text=(
                                            f"⏳ PROCESSING....!\n\n"
                                            f"⚡ {percent}% {bar}\n"
                                            f"📤 Sent: {total_sent}/{target_success}\n"
                                            f"✅ OK: {total_success} | ❌ Fail: {total_sent - total_success}"
                                        )
                                    )
                                )
                            except:
                                pass

        tasks = [
            asyncio.create_task(worker(valid_tokens[i % len(valid_tokens)]["token"]))
            for i in range(target_success)
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

    success = total_success
    name, likes = await name_task
    elapsed = f"{time.time() - start_time:.2f}s"

    LIVE_JOBS[uid]["status"] = "done"
    LIVE_JOBS[uid]["finished"] = time.strftime('%H:%M:%S')

    title = "AUTOVISIT SUCCESSFULLY" if is_auto else "VISIT SENT SUCCESSFULLY"

    keyboard = [[InlineKeyboardButton("📢 MAIN CHANNEL", url="https://t.me/KAMOD_CODEX")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if success == 0:
        final_msg = f"""
╭━━━━━━━━━━━━━━━━━━━━✪
│   ❌ VISIT FAILED
╰━━━━━━━━━━━━━━━━━━━━✪

╭━⟮ ✦ 👤 PLAYER INFO ✦ ⟯
│  Name        : {name}
│  UID         : {uid}
│  Region      : {region}
│  Total Likes : {likes}
╰━━━━━━━━━━━━━━━━━━✪

╭━⟮ ✦ 🚀 VISIT DETAILS ✦ ⟯
│  Visits Added : 0
│  Time Taken   : {elapsed}
╰━━━━━━━━━━━━━━━━━━✪
"""
    else:
        final_msg = f"""
╭━━━━━━━━━━━━━━━━━━━━✪
│  ✅ {title}
╰━━━━━━━━━━━━━━━━━━━━✪

╭━⟮ ✦ 👤 PLAYER INFO ✦ ⟯
│  Name        : {name}
│  UID         : {uid}
│  Region      : {region}
│  Total Likes : {likes}
╰━━━━━━━━━━━━━━━━━━✪

╭━⟮ ✦ 🚀 VISIT DETAILS ✦ ⟯
│  Visits Added : +{success}
│  Sent         : {total_sent}
│  Failed       : {total_sent - success}
│  Time Taken   : {elapsed}
╰━━━━━━━━━━━━━━━━━━✪
"""

    try:
        await context.bot.edit_message_text(
            chat_id=chat_id, message_id=msg_id,
            text=final_msg, reply_markup=reply_markup
        )
    except:
        pass

    return success


# ==============================================================================
#             AUTO VISIT
# ==============================================================================
async def auto_visit_loop(chat_id, uid, region, context):
    name, likes = await get_profile_name(uid, MEM_TOKENS, region)
    AUTO_VISIT_STATS[uid] = {"cycles": 0, "total_visits": 0, "name": name}

    while True:
        try:
            msg = await context.bot.send_message(chat_id, f"⚡ AUTOVISIT RUNNING\nUID: {uid}")
            success = await process_visit_task(
                chat_id, ADMIN_ID, uid, region,
                MEM_TOKENS, context, msg.message_id, is_auto=True
            )
            AUTO_VISIT_STATS[uid]["cycles"] += 1
            AUTO_VISIT_STATS[uid]["total_visits"] += success
            await asyncio.sleep(1)
        except asyncio.CancelledError:
            break


async def autovisit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("🚫 OWNER ONLY COMMAND")
        return
    if len(context.args) < 2:
        await update.message.reply_text("/autovisit ind 12345678\n/autovisit stop 12345678")
        return

    action = context.args[0].lower()
    uid = context.args[1]

    if action == "stop":
        if uid in AUTO_VISITS:
            AUTO_VISITS[uid].cancel()
            del AUTO_VISITS[uid]
            stats = AUTO_VISIT_STATS.get(uid, {})
            summary = (
                "━━━━━━━━━━━━━━━━━━━━✪\n"
                "│  🛑 AUTOVISIT STOPPED\n"
                "╰━━━━━━━━━━━━━━━━━━━━✪\n\n"
                "╭━⟮ ✦ 👤 PLAYER INFO ✦ ⟯\n"
                f"│  Name  : {stats.get('name', 'Unknown')}\n"
                f"│  UID   : {uid}\n"
                "╰━━━━━━━━━━━━━━━━━━✪\n\n"
                "╭━⟮ ✦ 📊 SUMMARY ✦ ⟯\n"
                f"│  Total Cycles : {stats.get('cycles', 0)}\n"
                f"│  Total Visits : {stats.get('total_visits', 0)}\n"
                "╰━━━━━━━━━━━━━━━━━━✪"
            )
            await update.message.reply_text(summary)
        else:
            await update.message.reply_text("❌ Not Running")
        return

    region = action.upper()
    if uid in AUTO_VISITS:
        await update.message.reply_text("⚠ Already Running")
        return

    task = asyncio.create_task(auto_visit_loop(update.effective_chat.id, uid, region, context))
    AUTO_VISITS[uid] = task
    await update.message.reply_text(f"🔥 AUTOVISIT STARTED\nUID: {uid}\nRegion: {region}")


# ==============================================================================
#             VISIT BUTTON SYSTEM
# ==============================================================================
async def visit_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    if update.message.text != "📍 Send Visit":
        return

    keyboard = [[
        InlineKeyboardButton("🇮🇳 IND", callback_data="visit_ind"),
        InlineKeyboardButton("🇧🇩 BD", callback_data="visit_bd")
    ]]
    await update.message.reply_text("🌍 SELECT REGION:", reply_markup=InlineKeyboardMarkup(keyboard))


async def visit_region_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "visit_ind":
        region = "IND"
    elif data == "visit_bd":
        region = "BD"
    else:
        return
    context.user_data["visit_region"] = region
    context.user_data["visit_step"] = "uid"
    await query.message.reply_text(f"✅ REGION SELECTED: {region}\n\n📍 NOW SEND UID:")


async def visit_uid_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    if context.user_data.get("visit_step") != "uid":
        return
    uid = update.message.text.strip()
    if not uid.isdigit():
        return await update.message.reply_text("❌ UID must be a number")
    region = context.user_data.get("visit_region", "IND")
    context.user_data.clear()

    if not MEM_TOKENS:
        return await update.message.reply_text("⚠️ System Busy or No Tokens!")

    msg = await update.message.reply_text("⏳ Sending Visits...")
    asyncio.create_task(
        process_visit_task(
            update.effective_chat.id, update.effective_user.id,
            uid, region, MEM_TOKENS, context, msg.message_id
        )
    )


# ==============================================================================
#             COMMANDS
# ==============================================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "╭━━━🔥 COMMAND PANEL 🔥━━━╮\n\n"
        "👤 User:\n"
        "➤ /visit region uid\n\n"
        "👑 Owner:\n"
        "➤ /autovisit ind uid\n"
        "➤ /autovisit stop uid\n"
        "➤ /checkvisit region uid\n"
        "➤ /status\n"
        "➤ /token\n"
        "➤ /log [n]\n"
        "╰━━━━━━━━━━━━━━━━━━━━╯"
    )
    await update.message.reply_text(msg)


async def visit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if update.effective_chat.type == "private" and user_id != ADMIN_ID:
        keyboard = [
            [InlineKeyboardButton("➕ Add Your Group", url=f"https://t.me/{context.bot.username}?startgroup=true")],
            [InlineKeyboardButton("👥 Official Group", url="https://t.me/KAMOD_LIKE_GROUP")]
        ]
        return await update.message.reply_text(
            "╭━━━━━━━━━━━━━━━━━━━━✪\n│   ❌ COMMAND NOT ALLOWED\n╰━━━━━━━━━━━━━━━━━━━━✪\n\n"
            "╭━⟮ 🚫 PRIVATE ACCESS BLOCKED ⟯\n│  WORK ONLY OFFICIAL GROUP.\n╰━━━━━━━━━━━━━━━━━━✪",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    if len(context.args) != 2:
        return await update.message.reply_text("❌ Format: /visit IND 12345678")

    region, uid = context.args[0].upper(), context.args[1]
    if not MEM_TOKENS:
        return await update.message.reply_text("⚠️ System Busy or No Tokens!")

    msg = await update.message.reply_text("⏳ Processing Visit Request...")
    asyncio.create_task(
        process_visit_task(update.effective_chat.id, user_id, uid, region, MEM_TOKENS, context, msg.message_id)
    )


async def check_visit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("🚫 <b>Admin Only Command!</b>", parse_mode='HTML')
    if len(context.args) != 2:
        return await update.message.reply_text("❌ <b>Usage:</b> <code>/checkvisit IND 7737005533</code>", parse_mode='HTML')

    uid = context.args[1]
    region = context.args[0].upper()
    total = len(MEM_TOKENS)
    if total == 0:
        return await update.message.reply_text("❌ No Tokens Loaded to check.", parse_mode='HTML')

    status_msg = await update.message.reply_text(f"🔄 <b>Checking {total} Tokens...</b>\n\nTarget UID: {uid}", parse_mode='HTML')

    url = get_api_url(region)
    host = url.replace("https://", "").split("/")[0]
    data = make_visit_payload(uid)
    sem = asyncio.Semaphore(200)

    async def check_one(session, token):
        async with sem:
            ok, _ = await send_visit(session, url, token, data, host)
            return 200 if ok else 0

    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=None)) as session:
        tasks = [check_one(session, t.get("token")) for t in MEM_TOKENS if t.get("token")]
        results = await asyncio.gather(*tasks)

    working = results.count(200)
    dead = total - working

    report = (
        "📊 <b>VISIT TOKEN HEALTH REPORT</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎯 <b>Target UID:</b> <code>{uid}</code>\n"
        f"🌍 <b>Region:</b> {region}\n"
        f"📂 <b>Total Tokens:</b> {total}\n\n"
        f"✅ <b>Working (Live):</b> {working}\n"
        f"❌ <b>Failed (Dead):</b> {dead}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━\n"
        "<i>Tokens refreshed automatically in background.</i>"
    )
    await context.bot.edit_message_text(chat_id=update.effective_chat.id, message_id=status_msg.message_id, text=report, parse_mode='HTML')


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not LIVE_JOBS:
        return await update.message.reply_text("📊 No jobs yet.")
    lines = ["📊 LIVE JOBS STATUS\n━━━━━━━━━━━━━━━"]
    for uid, j in list(LIVE_JOBS.items())[-10:]:
        percent = min(100, int(j["success"] * 100 / j["target"])) if j["target"] else 0
        filled = int(10 * percent / 100)
        bar = "█" * filled + "░" * (10 - filled)
        lines.append(
            f"🆔 {uid}\n"
            f"   📤 Sent: {j['sent']}/{j['target']}\n"
            f"   ✅ OK: {j['success']} | ❌ Fail: {j['fail']}\n"
            f"   📊 {percent}% {bar}\n"
            f"   ⚙️ {j['status'].upper()} | 🕐 {j['started']}"
        )
    await update.message.reply_text("\n".join(lines))


async def token_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    text = (
        f"🔑 TOKEN INFO\n━━━━━━━━━━━━━━━\n"
        f"📂 File: {OUTPUT_VISIT}\n"
        f"📊 Total Tokens: {len(MEM_TOKENS)}\n"
        f"🔁 Refresh Interval: {REFRESH_INTERVAL//3600}h\n"
        f"🕐 Now: {time.strftime('%H:%M:%S')}\n"
        "━━━━━━━━━━━━━━━"
    )
    await update.message.reply_text(text)


async def log_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    n = int(context.args[0]) if context.args and context.args[0].isdigit() else 50
    n = max(1, min(n, 200))
    lines = LOG_BUFFER[-n:]
    chunk = "\n".join(lines)
    if len(chunk) > 4000:
        chunk = chunk[-4000:]
    await update.message.reply_text(f"📜 LOG (last {len(lines)})\n━━━━━━━━━━━━━━━\n{chunk}")


# ==============================================================================
#             MAIN
# ==============================================================================
if __name__ == '__main__':
    # 🔥 Python 3.14 event loop fix
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    threading.Thread(target=run_auto_refresher, daemon=True).start()
    threading.Thread(target=refresh_tokens_ram, daemon=True).start()

    request = HTTPXRequest(connect_timeout=60, read_timeout=120, write_timeout=60, pool_timeout=60)
    app = ApplicationBuilder().token(BOT_TOKEN).request(request).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("visit", visit_command))
    app.add_handler(CommandHandler("autovisit", autovisit_command))
    app.add_handler(CommandHandler("checkvisit", check_visit_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("token", token_command))
    app.add_handler(CommandHandler("log", log_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, visit_button_handler))
    app.add_handler(CallbackQueryHandler(visit_region_callback, pattern="visit_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, visit_uid_handler))
    print("""
╔══════════════════════════════╗
║      🚀 KAMOD VISIT BOT      ║
╠══════════════════════════════╣
║  ⚡ Status   : ONLINE         ║
║  🔥 Mode     : HYBRID         ║
║  🛡 System   : STABLE         ║
║  📊 OB55     : ENABLED        ║
╚══════════════════════════════╝
""")

    app.run_polling()