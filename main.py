import asyncio, websockets, json, aiohttp, os, time
from collections import defaultdict, deque
from datetime import datetime

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "8273246175")
PUMP_PORTAL_WSS = "wss://pumpportal.fun/api/data"
MIN_SOL_BUY = float(os.getenv("MIN_SOL_BUY", "0.02"))
MIN_VOL_5M = float(os.getenv("MIN_VOL_5M", "5"))
MAX_VOL_5M = float(os.getenv("MAX_VOL_5M", "25"))
BUBBLE_THRESHOLD = float(os.getenv("BUBBLE_THRESHOLD", "30"))
vol_tracker = defaultdict(lambda: deque())

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

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
            async with s.get(url, timeout=8) as r:
                if r.status!= 200:
                    return False, 0
                data = await r.json()
                max_pct = 0
                for n in data.get("nodes", []):
                    max_pct = max(max_pct, n.get("percentage", 0))
                for c in data.get("clusters", []):
                    max_pct = max(max_pct, c.get("percentage", 0))
                return max_pct >= BUBBLE_THRESHOLD, max_pct
    except:
        return False, 0

async def check_rugcheck(mint):
    url = f"https://api.rugcheck.xyz/v1/tokens/{mint}/report"
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=8) as r:
                if r.status!= 200:
                    return True, "UNKNOWN"
                data = await r.json()
                for risk in data.get("risks", []):
                    if risk.get("level") == "danger":
                        return False, risk.get("name", "DANGER")
                if data.get("score", 0) > 7000:
                    return False, f"Score {data.get('score')}"
                return True, f"Score {data.get('score')}"
    except:
        return True, "ERR"

async def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    async with aiohttp.ClientSession() as s:
        await s.post(url, json=payload, timeout=10)

async def main():
    log(f"BOT START | BUY>{MIN_SOL_BUY} | VOL {MIN_VOL_5M}-{MAX_VOL_5M} | BUBBLE {BUBBLE_THRESHOLD}% | CHAT {TELEGRAM_CHAT_ID}")
    while True:
        try:
            async with websockets.connect(PUMP_PORTAL_WSS) as ws:
                await ws.send(json.dumps({"method": "subscribeNewTrade"}))
                log("Connected to PumpPortal WSS - waiting trades...")
                async for msg in ws:
                    data = json.loads(msg)
                    if data.get("txType")!= "buy":
                        continue
                    raw = data.get("solAmount") or 0
                    sol_amount = raw / 1e9 if raw > 1000000 else float(raw)
                    mint = data.get("mint")
                    if not mint:
                        continue
                    total_vol = check_volume_5m(mint, sol_amount)
                    if sol_amount < MIN_SOL_BUY:
                        log(f"[SKIP BUY] {mint} | buy {sol_amount:.3f} < min {MIN_SOL_BUY}")
                        continue
                    if total_vol < MIN_VOL_5M:
                        log(f"[SKIP SEPI] {mint} | Vol5m {total_vol:.2f} < {MIN_VOL_5M}")
                        continue
                    if total_vol > MAX_VOL_5M:
                        log(f"[SKIP RAME] {mint} | Vol5m {total_vol:.2f} > {MAX_VOL_5M}")
                        continue
                    log(f"[CHECK] {mint} | Vol {total_vol:.2f} OK")
                    try:
                        async with aiohttp.ClientSession() as s:
                            async with s.get(f"https://frontend-api.pump.fun/coins/{mint}", timeout=8) as r:
                                if r.status == 200:
                                    coin = await r.json()
                                    ts = coin.get("created_timestamp")
                                    if ts:
                                        age_min = (time.time()*1000 - ts)/60000
                                        if not (2 <= age_min <= 960):
                                            log(f"[SKIP UMUR] {mint} | {age_min:.1f}m")
                                            continue
                    except:
                        pass
                    is_safe, rug_info = await check_rugcheck(mint)
                    if not is_safe:
                        log(f"[SKIP RUG] {mint} | {rug_info}")
                        continue
                    is_bundle, pct = await check_bubblemap(mint)
                    if not is_bundle:
                        log(f"[SKIP BUBBLE] {mint} | {pct:.1f}%")
                        continue
                    log(f"ALERT {mint} | Vol {total_vol:.2f} | Bubble {pct:.1f}%")
                    text = f"🔥 <b>{MIN_VOL_5M}-{MAX_VOL_5M} SOL + BUNDLE</b>\n🪙 <code>{mint}</code>\n💰 Buy {sol_amount:.2f} | Vol5m {total_vol:.2f}\n📊 Bubble {pct:.1f}% | {rug_info}\n<a href='https://pump.fun/{mint}'>PUMP</a>"
                    await send_telegram(text)
        except Exception as e:
            log(f"ERROR {e} reconnect 5s")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
