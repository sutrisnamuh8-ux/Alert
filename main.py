import asyncio, websockets, json, aiohttp, os, time
from collections import defaultdict, deque
from datetime import datetime

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = "8273246175"
PUMP_PORTAL_WSS = "wss://pumpportal.fun/api/data"

MIN_SOL_BUY = float(os.getenv("MIN_SOL_BUY", "0.1"))
MIN_VOL_5M = float(os.getenv("MIN_VOL_5M", "5"))
MAX_VOL_5M = float(os.getenv("MAX_VOL_5M", "25"))
BUBBLE_THRESHOLD = 30

vol_tracker = defaultdict(lambda: deque())

def log(msg):
    now = datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] {msg}")

def check_volume_5m(mint, sol_amount):
    now = time.time()
    dq = vol_tracker[mint]
    dq.append((now, sol_amount))
    while dq and now - dq[0][0] > 300:
        dq.popleft()
    return sum(v for t, v in dq)

async def check_bubblemap(mint):
    url = f"https://api-legacy.bubblemaps.io/map-data?chain=sol&token={mint}"
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=10) as r:
                if r.status!= 200:
                    return False, 0, f"HTTP {r.status}"
                data = await r.json()
                max_pct = 0
                for n in data.get("nodes", []): max_pct = max(max_pct, n.get("percentage", 0))
                for c in data.get("clusters", []): max_pct = max(max_pct, c.get("percentage", 0))
                return max_pct >= BUBBLE_THRESHOLD, max_pct, "OK"
    except Exception as e:
        return False, 0, str(e)

async def check_rugcheck(mint):
    url = f"https://api.rugcheck.xyz/v1/tokens/{mint}/report"
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=10) as r:
                if r.status!= 200: return True, f"HTTP {r.status}", True
                data = await r.json()
                for risk in data.get("risks", []):
                    if risk.get("level") == "danger":
                        return False, risk.get("name","DANGER"), False
                if data.get("score",0) > 7000:
                    return False, f"Score {data.get('score')}", False
                return True, f"Score {data.get('score')}", False
    except Exception as e:
        return True, str(e), True

async def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    async with aiohttp.ClientSession() as s:
        await s.post(url, json=payload, timeout=10)

async def main():
    log(f"BOT START | BUY>{MIN_SOL_BUY} | VOL {MIN_VOL_5M}-{MAX_VOL_5M} | BUBBLE {BUBBLE_THRESHOLD}%")
    while True:
        try:
            async with websockets.connect(PUMP_PORTAL_WSS) as ws:
                await ws.send(json.dumps({"method": "subscribeNewTrade"}))
                log("Connected to PumpPortal WSS")
                async for msg in ws:
                    data = json.loads(msg)
                    if data.get("txType")!= "buy": continue

                    raw = data.get("solAmount") or 0
                    sol_amount = raw / 1e9 if raw > 1_000_000 else float(raw)
                    mint = data.get("mint")
                    if not mint: continue

                    # 1. FILTER BUY
                    if sol_amount < MIN_SOL_BUY:
                        log(f"[SKIP BUY] {mint} | Buy {sol_amount:.3f} < {MIN_SOL_BUY}")
                        continue

                    # 2. FILTER VOLUME
                    total_vol = check_volume_5m(mint, sol_amount)
                    if total_vol < MIN_VOL_5M:
                        log(f"[SKIP SEPI] {mint} | Vol5m {total_vol:.2f} < {MIN_VOL_5M} | Buy {sol_amount:.2f}")
                        continue
                    if total_vol > MAX_VOL_5M:
                        log(f"[SKIP RAME] {mint} | Vol5m {total_vol:.2f} > {MAX_VOL_5M}")
                        continue

                    log(f"[CHECK] {mint} | Buy {sol_amount:.2f} | Vol5m {total_vol:.2f} -> Cek umur...")

                    # 3. FILTER UMUR
                    age_min = 0
                    try:
                        async with aiohttp.ClientSession() as s:
                            async with s.get(f"https://frontend-api.pump.fun/coins/{mint}", timeout=10) as r:
                                if r.status == 200:
                                    coin = await r.json()
                                    ts = coin.get("created_timestamp")
                                    if ts:
                                        age_min = (time.time()*1000 - ts) / 60000
                                        if not (2 <= age_min <= 960):
                                            log(f"[SKIP UMUR] {mint} | Umur {age_min:.1f}m diluar 2-960m")
                                            continue
                    except Exception as e:
                        log(f"[ERR UMUR] {mint} {e}")

                    # 4. FILTER RUGCHECK
                    log(f"[RUGCHECK] {mint} | Umur {age_min:.1f}m OK -> hit rugcheck...")
                    is_safe, rug_info, is_err = await check_rugcheck(mint)
                    if not is_safe:
                        log(f"[SKIP RUG] {mint} | DANGER: {rug_info}")
                        continue
                    if is_err:
                        log(f"[RUG ERR] {mint} | {rug_info} -> anggap SAFE")

                    # 5. FILTER BUBBLEMAP
                    log(f"[BUBBLE] {mint} | Rug {rug_info} SAFE -> hit bubblemap...")
                    is_bundle, pct, b_info = await check_bubblemap(mint)
                    if not is_bundle:
                        log(f"[SKIP BUBBLE] {mint} | Bubble {pct:.1f}% < {BUBBLE_THRESHOLD}% | {b_info}")
                        continue

                    # LOLOS SEMUA
                    log(f"✅ [ALERT] {mint} | Vol {total_vol:.1f} | Bubble {pct:.1f}% | Rug {rug_info}")
                    text = (
                        f"🔥 <b>GOLDEN ZONE + BUNDLE</b>\n"
                        f"🪙 <code>{mint}</code>\n"
                        f"💰 Buy: {sol_amount:.2f} | Vol5m: {total_vol:.2f} SOL\n"
                        f"⏰ Umur: {age_min:.1f}m | 📊 Bubble: {pct:.1f}%\n"
                        f"🛡️ Rug: {rug_info}\n"
                        f"<a href='https://bubblemaps.io/sol/token/{mint}'>Bubble</a> | "
                        f"<a href='https://rugcheck.xyz/tokens/{mint}'>Rug</a> | "
                        f"<a href='https://pump.fun/{mint}'>PUMP</a>"
                    )
                    await send_telegram(text)

        except Exception as e:
            log(f"WS ERROR {e} -> reconnect 5s")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
