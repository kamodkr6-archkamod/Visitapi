# =====================================================
# DEVILS WILL RISE - VISIT API
# OWNER   : @kamod_codex
# CHANNEL : @kamod_codex
# 💀 KAMOD WILL RISE 💀
# =====================================================
from flask import Flask, jsonify
import aiohttp
import asyncio
import json
import os
import threading
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from byte import encrypt_api, Encrypt_ID
from visit_count_pb2 import Info

app = Flask(__name__)

# ================= CONFIG =================
REFRESH_INTERVAL = 21600   # 6 hours
THREAD_COUNT = 30          # 30 threads
BATCH_DELAY = 1.5          # batch ke baad delay
FETCH_RETRY = 2            # fail pe retry
RETRY_DELAY = 3            # retry se pehle delay

INPUT_VISIT = "account.json"
OUTPUT_VISIT = "token_ind.json"

JWT_API_URLS = [
    "https://kamodjwt.vercel.app/token",
    "https://all-in-one-jwt.vercel.app/token",
]
# ==========================================


# ================= JWT FETCH (with retry + fallback) =================
def fetch_jwt(uid, password, retries=FETCH_RETRY):
    for attempt in range(retries + 1):
        for base_url in JWT_API_URLS:
            try:
                params = {"uid": uid, "password": password}
                response = requests.get(base_url, params=params, timeout=20)
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, dict):
                        if data.get("success") and "jwt_token" in data:
                            return data["jwt_token"]
                        if "jwt_token" in data:
                            return data["jwt_token"]
                        if "token" in data:
                            return data["token"]
            except Exception:
                continue
        if attempt < retries:
            time.sleep(RETRY_DELAY)
    return None
# =====================================================================


# ================= AUTO TOKEN REFRESH THREAD =================
def token_refresher_thread():
    while True:
        print("=" * 60)
        print(f"🔄 [AUTO REFRESH] Starting at {time.strftime('%H:%M:%S')}")

        if os.path.exists(INPUT_VISIT):
            try:
                with open(INPUT_VISIT, 'r') as f:
                    accounts = json.load(f)

                total = len(accounts)
                print(f"📋 Total accounts: {total}")
                print(f"⚙️  Threads: {THREAD_COUNT} | Batch delay: {BATCH_DELAY}s | Retry: {FETCH_RETRY}")
                print("-" * 60)

                valid_tokens = []
                failed_uids = []
                done = 0
                start_time = time.time()

                for i in range(0, total, THREAD_COUNT):
                    batch = accounts[i:i + THREAD_COUNT]
                    batch_num = i // THREAD_COUNT + 1
                    total_batches = (total + THREAD_COUNT - 1) // THREAD_COUNT

                    print(f"⏳ Batch {batch_num}/{total_batches} ({len(batch)} accounts)...")

                    with ThreadPoolExecutor(max_workers=THREAD_COUNT) as executor:
                        futures = {
                            executor.submit(fetch_jwt, acc['uid'], acc['password']): acc
                            for acc in batch
                        }

                        for future in as_completed(futures):
                            done += 1
                            token = future.result()
                            acc = futures[future]

                            if token:
                                valid_tokens.append({"token": token})
                                status = "✅ OK  "
                            else:
                                failed_uids.append(acc['uid'])
                                status = "❌ FAIL"

                            elapsed = time.time() - start_time
                            rate = done / elapsed if elapsed > 0 else 0
                            remaining = total - done
                            eta = remaining / rate if rate > 0 else 0

                            print(
                                f"   [{done}/{total}] {status} uid {acc['uid']} "
                                f"| OK: {len(valid_tokens)} | FAIL: {len(failed_uids)} "
                                f"| ETA: {int(eta)}s"
                            )

                    if i + THREAD_COUNT < total:
                        print(f"   😴 Batch delay {BATCH_DELAY}s...")
                        time.sleep(BATCH_DELAY)

                with open(OUTPUT_VISIT, 'w') as f:
                    json.dump(valid_tokens, f, indent=4)

                elapsed_total = time.time() - start_time
                print("-" * 60)
                print(f"📊 [AUTO REFRESH] DONE in {elapsed_total:.1f}s")
                print(f"   ✅ Success : {len(valid_tokens)}/{total}")
                print(f"   ❌ Failed  : {len(failed_uids)}/{total}")
                print(f"💾 Saved: {OUTPUT_VISIT}")
                if failed_uids:
                    print(f"⚠️  Failed UIDs: {failed_uids}")
                print("=" * 60)

            except Exception as e:
                print(f"❌ Refresh error: {e}")
        else:
            print(f"⚠️ {INPUT_VISIT} not found")

        next_time = time.strftime('%H:%M:%S', time.localtime(time.time() + REFRESH_INTERVAL))
        print(f"😴 Sleeping 6 hours (next: {next_time})...")
        time.sleep(REFRESH_INTERVAL)
# =============================================================


# Start refresher thread (daemon — server ke saath chalta hai)
threading.Thread(target=token_refresher_thread, daemon=True).start()


# ================= LOAD TOKENS =================
def load_tokens(server_name):
    try:
        if server_name == "IND":
            path = "token_ind.json"
        elif server_name in {"BR", "US", "SAC", "NA"}:
            path = "token_br.json"
        else:
            path = "token_bd.json"

        with open(path, "r") as f:
            data = json.load(f)

        tokens = [item["token"] for item in data if "token" in item and item["token"] not in ["", "N/A"]]
        return tokens
    except Exception as e:
        app.logger.error(f"❌ Token load error for {server_name}: {e}")
        return []
# ================================================


# ================= URL =================
def get_url(server_name):
    if server_name == "IND":
        return "https://client.ind.freefiremobile.com/GetPlayerPersonalShow"
    elif server_name in {"BR", "US", "SAC", "NA"}:
        return "https://client.us.freefiremobile.com/GetPlayerPersonalShow"
    else:
        return "https://clientbp.ggblueshark.com/GetPlayerPersonalShow"
# ======================================


# ================= PROTOBUF PARSE =================
def parse_protobuf_response(response_data):
    try:
        info = Info()
        info.ParseFromString(response_data)
        player_data = {
            "uid": info.AccountInfo.UID if info.AccountInfo.UID else 0,
            "nickname": info.AccountInfo.PlayerNickname if info.AccountInfo.PlayerNickname else "",
            "likes": info.AccountInfo.Likes if info.AccountInfo.Likes else 0,
            "region": info.AccountInfo.PlayerRegion if info.AccountInfo.PlayerRegion else "",
            "level": info.AccountInfo.Levels if info.AccountInfo.Levels else 0
        }
        return player_data
    except Exception as e:
        app.logger.error(f"❌ Protobuf parsing error: {e}")
        return None
# =================================================


# ================= VISIT =================
async def visit(session, url, token, uid, data):
    headers = {
        "ReleaseVersion": "OB55",
        "X-GA": "v1 1",
        "Authorization": f"Bearer {token}",
        "Host": url.replace("https://", "").split("/")[0]
    }
    try:
        async with session.post(url, headers=headers, data=data, ssl=False) as resp:
            if resp.status == 200:
                response_data = await resp.read()
                return True, response_data
            else:
                return False, None
    except Exception as e:
        app.logger.error(f"❌ Visit error: {e}")
        return False, None


async def send_until_1000_success(tokens, uid, server_name, target_success=1000):
    url = get_url(server_name)
    connector = aiohttp.TCPConnector(limit=0)
    total_success = 0
    total_sent = 0
    first_success_response = None
    player_info = None

    async with aiohttp.ClientSession(connector=connector) as session:
        encrypted = encrypt_api("08" + Encrypt_ID(str(uid)) + "1801")
        data = bytes.fromhex(encrypted)

        while total_success < target_success:
            batch_size = min(target_success - total_success, 20000)
            tasks = [
                asyncio.create_task(visit(session, url, tokens[(total_sent + i) % len(tokens)], uid, data))
                for i in range(batch_size)
            ]
            results = await asyncio.gather(*tasks)

            if first_success_response is None:
                for success, response in results:
                    if success and response is not None:
                        first_success_response = response
                        player_info = parse_protobuf_response(response)
                        break

            batch_success = sum(1 for r, _ in results if r)
            total_success += batch_success
            total_sent += batch_size

            print(f"Batch sent: {batch_size}, Success in batch: {batch_success}, Total success so far: {total_success}")

            # Infinite loop se bachne ke liye
            if batch_success == 0:
                print("⚠️ No success in batch, breaking")
                break

    return total_success, total_sent, player_info
# =========================================


# ================= ROUTES =================
@app.route('/<string:server>/<int:uid>', methods=['GET'])
def send_visits(server, uid):
    server = server.upper()
    tokens = load_tokens(server)
    target_success = 1000

    if not tokens:
        return jsonify({"error": "❌ No valid tokens found", "owner": "@kamod_codex"}), 500

    print(f"🚀 Sending visits to UID: {uid} using {len(tokens)} tokens")
    print(f"Waiting for total {target_success} successful visits...")

    total_success, total_sent, player_info = asyncio.run(send_until_1000_success(
        tokens, uid, server,
        target_success=target_success
    ))

    if player_info:
        player_info_response = {
            "fail": target_success - total_success,
            "level": player_info.get("level", 0),
            "likes": player_info.get("likes", 0),
            "nickname": player_info.get("nickname", ""),
            "region": player_info.get("region", ""),
            "success": total_success,
            "uid": player_info.get("uid", 0),
            "owner": "@kamod_codex",
            "channel": "@kamod_codex"
        }
        return jsonify(player_info_response), 200
    else:
        return jsonify({"error": "Could not decode player information", "owner": "@kamod_codex"}), 500


@app.route('/visit', methods=['GET'])
def send_visits_query():
    """Query param style: /visit?uid=...&server_name=IND"""
    from flask import request
    uid = request.args.get('uid')
    server = request.args.get('server_name', '').upper()

    if not uid or not server:
        return jsonify({"error": "uid and server_name required", "owner": "@kamod_codex"}), 400

    try:
        uid_int = int(uid)
    except ValueError:
        return jsonify({"error": "uid must be integer", "owner": "@kamod_codex"}), 400

    return send_visits(server, uid_int)
# ==========================================


if __name__ == "__main__":
    print("💀 KAMOD WILL RISE - VISIT API 💀")
    print("Owner   : @kamod_codex")
    print("Channel : @kamod_codex")
    print(f"⚙️  Threads: {THREAD_COUNT} | Batch delay: {BATCH_DELAY}s | Retry: {FETCH_RETRY}")
    print("=" * 60)
    app.run(host="0.0.0.0", port=5000)

# =====================================================
# DEVILS WILL RISE - VISIT API
# OWNER   : @kamod_codex
# CHANNEL : @kamod_codex
# 💀 KAMOD WILL RISE 💀
# =====================================================
