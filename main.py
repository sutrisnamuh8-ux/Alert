import asyncio, websockets, json, aiohttp, os, time
from collections import defaultdict, deque
from datetime import datetime

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "8273246175")
PUMP_PORTAL_WSS = "wss://pumpportal.fun/api/data"
MIN_SOL_BUY = float(os.getenv("MIN_SOL_BUY", "0.02"))
MIN_VOL_5M = float(os.getenv("MIN_VOL_5M", "0.5"))
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
                if r.status!= 200: return False, 0
                data = await r.json()
                max_pct = 0
                for n in data.get("nodes", []): max_pct = max(max_pct, n.get("percentage", 0))
                for c in data.get("clusters", []): max_pct = max(max_pct, c.get("percentage", 0))
                return max_pct >= BUBBLE_THRESHOLD, max_pct
    except: return False, 0

async def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(url, json=payload, timeout=10) as r:
                res = await r.text()
                log(f"TG SEND {r.status}: {res[:200]}")
    except Exception as e:
        log(f"TG ERROR {e}")

async def main():
    log(f"BOT START | BUY>{MIN_SOL_BUY} | VOL {MIN_VOL_5M}-{MAX_VOL_5M} | BUBBLE {BUBBLE_THRESHOLD}% | CHAT {TELEGRAM_CHAT_ID}")
    await send_telegram(f"✅ BOT ON - KETAT\nVOL {MIN_VOL_5M}-{MAX_VOL_5M} SOL | BUBBLE {BUBBLE_THRESHOLD}% | NO RUGCHECK")
    while True:
        try:
            async with websockets.connect(PUMP_PORTAL_WSS) as ws:
                await ws.send(json.dumps({"method": "subscribeNewTrade"}))
                log("Connected to PumpPortal WSS - waiting trades...")
                async for msg in ws:
                    data = json.loads(msg)
                    if data.get("txType")!= "buy": continue
                    raw = data.get("solAmount") or 0
                    sol_amount = raw / 1e9 if raw > 1000000 else float(raw)
                    mint = data.get("mint")
                    if not mint: continue
                    total_vol = check_volume_5m(mint, sol_amount)
