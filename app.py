# =====================================================
# DEVILS WILL RISE - VISIT API (FULL FIXED)
# OWNER   : @kamod_codex
# CHANNEL : @kamod_codex
# 💀 KAMOD WILL RISE 💀
# =====================================================
from flask import Flask, jsonify, request
import aiohttp
import asyncio
import json
import os
import sys
import threading
import time
import uuid
import requests
import collections
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from byte import encrypt_api, Encrypt_ID
from visit_count_pb2 import Info

app = Flask(__name__)

# ================= CONFIG =================
REFRESH_INTERVAL   = 21600
THREAD_COUNT       = 30
BATCH_DELAY        = 1.5
FETCH_RETRY        = 1
RETRY_DELAY        = 1

VISIT_CONCURRENCY  = 800
VISIT_TIMEOUT      = aiohttp.ClientTimeout(total=15, connect=5)
CONN_KEEPALIVE     = 60
DEFAULT_TARGET     = 2000

INPUT_VISIT  = "account.json"
OUTPUT_VISIT = "token_ind.json"

JWT_API_URLS = [
    "https://all-in-one-jwt.vercel.app/token",
]

START_TIME = time.time()
# ==========================================

# ================= GLOBAL STATE =================
STATE_LOCK = threading.Lock()
JOBS = {}

REFRESH_INFO = {
    "last_start": None,
    "last_end": None,
    "success": 0,
    "failed": 0,
    "total": 0,
}

LOG_BUFFER = collections.deque(maxlen=300)
LOG_LOCK = threading.Lock()

def log(msg):
    ts = time.strftime('%H:%M:%S')
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with LOG_LOCK:
        LOG_BUFFER.append(line)
# ================================================

# ================= JWT FETCH (FAST) =================
def fetch_jwt(uid, password, retries=FETCH_RETRY):
    for attempt in range(retries + 1):
        for base_url in JWT_API_URLS:
            try:
                r = requests.get(
                    base_url,
                    params={"uid": uid, "password": password},
                    timeout=(4, 8)
                )
                if r.status_code == 200:
                    d = r.json()
                    if isinstance(d, dict):
                        if d.get("success") and "jwt_token" in d:
                            return d["jwt_token"]
                        if "jwt_token" in d:
                            return d["jwt_token"]
                        if "token" in d:
                            return d["token"]
            except Exception:
                continue
        if attempt < retries:
            time.sleep(RETRY_DELAY)
    return None
# =============================================

# ================= TOKEN REFRESHER (FIXED) =================
def token_refresher_thread():
    while True:
        log("=" * 60)
        log("🔄 [AUTO REFRESH] Starting")
        REFRESH_INFO["last_start"] = time.strftime('%Y-%m-%d %H:%M:%S')

        if not os.path.exists(INPUT_VISIT):
            log(f"⚠️ {INPUT_VISIT} not found — skipping")
            time.sleep(REFRESH_INTERVAL)
            continue

        try:
            with open(INPUT_VISIT, 'r') as f:
                accounts = json.load(f)

            total = len(accounts)
            log(f"📋 Total accounts: {total}")
            log(f"⚙️  Threads: {THREAD_COUNT} | Retry: {FETCH_RETRY}")

            valid_tokens, failed_uids = [], []
            done = 0
            start = time.time()
            last_log = 0

            with ThreadPoolExecutor(max_workers=THREAD_COUNT) as ex:
                futures = {
                    ex.submit(fetch_jwt, a.get('uid'), a.get('password')): a
                    for a in accounts
                }

                for fut in as_completed(futures, timeout=None):
                    done += 1
                    try:
                        tok = fut.result(timeout=20)
                    except Exception:
                        tok = None
                    acc = futures[fut]

                    if tok:
                        valid_tokens.append({"token": tok})
                    else:
                        failed_uids.append(acc.get('uid'))

                    # har 50 pe log (chhote batches ke liye)
                    if done - last_log >= 50 or done == total:
                        elapsed = time.time() - start
                        rate = done / elapsed if elapsed else 0
                        eta = (total - done) / rate if rate else 0
                        log(f"   📊 Refresh {done}/{total} | OK={len(valid_tokens)} FAIL={len(failed_uids)} | {rate:.1f}/s | ETA {eta:.0f}s")
                        last_log = done

                        # beech me hi save — visit ke liye tokens available
                        if valid_tokens:
                            tmp = OUTPUT_VISIT + ".tmp"
                            with open(tmp, 'w') as f:
                                json.dump(valid_tokens, f, indent=4)
                            os.replace(tmp, OUTPUT_VISIT)

            with open(OUTPUT_VISIT, 'w') as f:
                json.dump(valid_tokens, f, indent=4)

            REFRESH_INFO.update({
                "last_end": time.strftime('%Y-%m-%d %H:%M:%S'),
                "success": len(valid_tokens),
                "failed": len(failed_uids),
                "total": total,
            })
            log(f"📊 REFRESH DONE — OK: {len(valid_tokens)}/{total} in {time.time()-start:.1f}s")

        except Exception as e:
            log(f"❌ Refresh error: {e}")
            log(traceback.format_exc()[:800])

        log(f"😴 Sleeping {REFRESH_INTERVAL//3600}h...")
        time.sleep(REFRESH_INTERVAL)

threading.Thread(target=token_refresher_thread, daemon=True).start()
# =============================================

# ================= TOKEN LOAD =================
def token_file(server_name):
    if server_name == "IND":
        return "token_ind.json"
    if server_name in {"BR", "US", "SAC", "NA"}:
        return "token_br.json"
    return "token_bd.json"

def load_tokens(server_name):
    try:
        with open(token_file(server_name), "r") as f:
            data = json.load(f)
        return [i["token"] for i in data if i.get("token") and i["token"] not in ("", "N/A")]
    except Exception as e:
        log(f"❌ Token load error {server_name}: {e}")
        return []
# =============================================

# ================= URL =================
def get_url(server_name):
    if server_name == "IND":
        return "https://client.ind.freefiremobile.com/GetPlayerPersonalShow"
    if server_name in {"BR", "US", "SAC", "NA"}:
        return "https://client.us.freefiremobile.com/GetPlayerPersonalShow"
    return "https://clientbp.ggblueshark.com/GetPlayerPersonalShow"
# =======================================

# ================= PROTOBUF =================
def parse_protobuf_response(response_data):
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
# =============================================

# ================= VISIT CORE (FIXED + DEBUG) =================
async def send_until_target(tokens, uid, server_name, job_id, target_success=DEFAULT_TARGET):
    url = get_url(server_name)
    host = url.replace("https://", "").split("/")[0]

    connector = aiohttp.TCPConnector(
        limit=0, limit_per_host=0, ttl_dns_cache=600,
        keepalive_timeout=CONN_KEEPALIVE, enable_cleanup_closed=True,
        force_close=False, use_dns_cache=True,
    )
    sem = asyncio.Semaphore(VISIT_CONCURRENCY)

    total_success = 0
    total_sent = 0
    first_response = None
    player_info = None
    debug_count = {"n": 0}

    async with aiohttp.ClientSession(connector=connector, timeout=VISIT_TIMEOUT) as session:
        try:
            await session.head(url, ssl=False, timeout=aiohttp.ClientTimeout(total=5))
        except Exception:
            pass

        encrypted = encrypt_api("08" + Encrypt_ID(str(uid)) + "1801")
        data = bytes.fromhex(encrypted)
        headers_base = {
            "ReleaseVersion": "OB55",
            "X-GA": "v1 1",
            "Host": host,
        }

        lock = asyncio.Lock()
        stop_flag = {"stop": False}

        def update_job():
            with STATE_LOCK:
                j = JOBS.get(job_id)
                if j:
                    j["sent"] = total_sent
                    j["success"] = total_success
                    j["fail"] = total_sent - total_success

        async def worker(tok):
            nonlocal total_success, total_sent, first_response, player_info
            if stop_flag["stop"]:
                return
            async with sem:
                if stop_flag["stop"]:
                    return
                headers = dict(headers_base)
                headers["Authorization"] = f"Bearer {tok}"
                ok = False
                body = None
                err_msg = None
                try:
                    async with session.post(url, headers=headers, data=data, ssl=False) as r:
                        if r.status == 200:
                            body = await r.read()
                            ok = True
                        else:
                            err_msg = f"HTTP {r.status}: {(await r.text())[:120]}"
                except Exception as e:
                    err_msg = f"{type(e).__name__}: {str(e)[:120]}"

                async with lock:
                    total_sent += 1
                    if ok:
                        total_success += 1
                        if first_response is None and body:
                            first_response = body
                            player_info = parse_protobuf_response(body)
                        if total_success >= target_success:
                            stop_flag["stop"] = True
                    else:
                        if debug_count["n"] < 3:
                            debug_count["n"] += 1
                            log(f"[DEBUG] FAIL: {err_msg}")

                if total_sent % 50 == 0 or stop_flag["stop"]:
                    update_job()

        tasks = []
        for i in range(target_success):
            tok = tokens[i % len(tokens)]
            tasks.append(asyncio.create_task(worker(tok)))

        await asyncio.gather(*tasks, return_exceptions=True)
        update_job()

    log(f"[{job_id[:8]}] DONE sent={total_sent} ok={total_success} target={target_success}")
    return total_success, total_sent, player_info
# =============================================

# ================= JOB RUNNER =================
def _run_visit(server, uid, target):
    tf = token_file(server)
    try:
        age = time.time() - os.path.getmtime(tf)
        if age > 3600:
            log(f"⚠️ WARNING: {tf} is {age/60:.0f} min old — tokens may be expired")
    except FileNotFoundError:
        log(f"⚠️ {tf} not found — refresh not done yet")

    tokens = load_tokens(server)
    if not tokens:
        return jsonify({"error": "❌ No valid tokens", "server": server}), 500

    job_id = uuid.uuid4().hex
    with STATE_LOCK:
        JOBS[job_id] = {
            "job_id": job_id, "uid": uid, "server": server,
            "target": target, "sent": 0, "success": 0, "fail": 0,
            "status": "running",
            "started": time.strftime('%Y-%m-%d %H:%M:%S'),
            "finished": None, "player": None,
        }

    log(f"🚀 JOB {job_id[:8]} uid={uid} server={server} target={target} tokens={len(tokens)}")

    try:
        total_success, total_sent, player_info = asyncio.run(
            send_until_target(tokens, uid, server, job_id, target_success=target)
        )
    except Exception as e:
        log(f"❌ JOB {job_id[:8]} error: {e}")
        log(traceback.format_exc()[:500])
        total_success = total_sent = 0
        player_info = None

    with STATE_LOCK:
        j = JOBS[job_id]
        j["status"] = "done" if player_info else "failed"
        j["finished"] = time.strftime('%Y-%m-%d %H:%M:%S')
        j["sent"] = total_sent
        j["success"] = total_success
        j["fail"] = total_sent - total_success
        j["player"] = player_info

    if player_info:
        return jsonify({
            "job_id": job_id,
            "fail": target - total_success,
            "level": player_info.get("level", 0),
            "likes": player_info.get("likes", 0),
            "nickname": player_info.get("nickname", ""),
            "region": player_info.get("region", ""),
            "success": total_success,
            "sent": total_sent,
            "uid": player_info.get("uid", 0),
            "owner": "@kamod_codex",
            "channel": "@kamod_codex",
        }), 200
    return jsonify({"error": "decode failed", "job_id": job_id, "sent": total_sent, "success": total_success}), 500
# =============================================

# ================= ROUTES =================
@app.route('/<string:server>/<int:uid>', methods=['GET'])
def send_visits(server, uid):
    return _run_visit(server.upper(), uid, DEFAULT_TARGET)

@app.route('/visit', methods=['GET'])
def send_visits_query():
    uid = request.args.get('uid')
    server = request.args.get('server_name', '').upper()
    target = int(request.args.get('target', DEFAULT_TARGET))
    if not uid or not server:
        return jsonify({"error": "uid and server_name required"}), 400
    try:
        uid = int(uid)
    except ValueError:
        return jsonify({"error": "uid must be integer"}), 400
    return _run_visit(server, uid, target)

@app.route('/status', methods=['GET'])
@app.route('/status/<job_id>', methods=['GET'])
def status(job_id=None):
    with STATE_LOCK:
        if job_id:
            j = JOBS.get(job_id)
            if not j:
                return jsonify({"error": "job not found"}), 404
            j2 = dict(j)
            j2["uptime_s"] = int(time.time() - START_TIME)
            return jsonify(j2), 200
        active = [j for j in JOBS.values() if j["status"] == "running"]
        return jsonify({
            "uptime_s": int(time.time() - START_TIME),
            "active_jobs": len(active),
            "total_jobs": len(JOBS),
            "jobs": list(JOBS.values())[-20:],
            "refresh": REFRESH_INFO,
        }), 200

@app.route('/port', methods=['GET'])
def port_info():
    return jsonify({
        "port": 5000, "host": "0.0.0.0", "pid": os.getpid(),
        "uptime_s": int(time.time() - START_TIME),
        "python": sys.version.split()[0],
    }), 200

@app.route('/token', methods=['GET'])
@app.route('/token/<server>', methods=['GET'])
def token_info(server=None):
    servers = [server.upper()] if server else ["IND", "BR", "US", "SAC", "NA", "BD"]
    out = {}
    for s in servers:
        out[s] = {"count": len(load_tokens(s)), "file": token_file(s)}
    return jsonify({"tokens": out, "refresh": REFRESH_INFO}), 200

@app.route('/log', methods=['GET'])
def log_info():
    n = int(request.args.get('n', 100))
    n = max(1, min(n, 300))
    with LOG_LOCK:
        lines = list(LOG_BUFFER)[-n:]
    return jsonify({"lines": lines, "count": len(lines)}), 200

@app.route('/refresh', methods=['GET'])
def force_refresh():
    threading.Thread(target=_manual_refresh, daemon=True).start()
    return jsonify({"status": "refresh triggered"}), 200

def _manual_refresh():
    try:
        with open(INPUT_VISIT, 'r') as f:
            accounts = json.load(f)
        total = len(accounts)
        log(f"🔁 MANUAL REFRESH: {total} accounts")
        valid, done = [], 0
        start = time.time()
        with ThreadPoolExecutor(max_workers=THREAD_COUNT) as ex:
            futures = {ex.submit(fetch_jwt, a.get('uid'), a.get('password')): a for a in accounts}
            for fut in as_completed(futures):
                done += 1
                try:
                    tok = fut.result(timeout=20)
                except Exception:
                    tok = None
                if tok:
                    valid.append({"token": tok})
                if done % 50 == 0 or done == total:
                    log(f"   🔁 {done}/{total} OK={len(valid)}")
                    if valid:
                        tmp = OUTPUT_VISIT + ".tmp"
                        with open(tmp, 'w') as f:
                            json.dump(valid, f, indent=4)
                        os.replace(tmp, OUTPUT_VISIT)
        log(f"🔁 MANUAL REFRESH DONE OK={len(valid)}/{total} in {time.time()-start:.0f}s")
    except Exception as e:
        log(f"❌ Manual refresh error: {e}")
# ==========================================

if __name__ == "__main__":
    try:
        import uvloop
        uvloop.install()
        log("⚡ uvloop installed")
    except ImportError:
        log("⚠️ uvloop not installed (pip install uvloop for 2x boost)")

    log("💀 KAMOD WILL RISE - VISIT API 💀")
    log(f"⚙️  Concurrency={VISIT_CONCURRENCY} | Target={DEFAULT_TARGET}")
    app.run(host="0.0.0.0", port=5000, threaded=True)