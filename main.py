import asyncio, websockets, json, aiohttp, os, time
from collections import defaultdict, deque
from datetime import datetime

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "8273246175")
PUMP_PORTAL_WSS = "wss://pumpportal.fun/api/data"
MIN_SOL_BUY = float(os.getenv("MIN_SOL_BUY", "0.02"))
MIN_VOL_5M = float(os.getenv("MIN_VOL_5M", "0.5"))
MAX_VOL_5M = float(os.getenv("MAX_VOL_5M", "25"))
BUBBLE_THRESHOLD = float(os.getenv("BUBBLE_THRESHOLD", "5"))
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
        async with a
