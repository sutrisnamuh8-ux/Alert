import os
import asyncio
import json
import time
from collections import defaultdict
import websockets
import aiohttp

# --- CONFIG DARI RAILWAY VARIABLES ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
BUBBLE_THRESHOLD = float(os.getenv("BUBBLE_THRESHOLD", "30"))
MIN_VOL_5M = float(os.getenv("MIN_VOL_5M", "5"))
MAX_VOL_5M = float(os.getenv("MAX_VOL_5M", "25"))
MIN_SOL_BUY = float(os.getenv("MIN_SOL_BUY", "0.1"))

# Simpan total buy per token dalam 5 menit
vol_tracker = defaultdict(list)

async def send_telegram(text):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    async with aiohttp.ClientSession() as session:
        await session.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"})

async def check_bubblemap(mint):
    # Simple check - nanti bisa ganti API bubblemaps asli
    try:
        url = f"https://api.bubblemaps.io/map-data?token={mint}&chain=solana"
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as r:
                if r.status != 200:
                    return False, 0
                data = await r.json()
                # cek top holder cluster
                max_cluster = 0
                for node in data.get("nodes", []):
                    pct = node.get("percentage", 0)
                    if pct > max_cluster:
                        max_cluster = pct
                # kalau cluster > threshold = bundle/bundled
                if max_cluster > BUBBLE_THRESHOLD:
                    return True, max_cluster
                return False, max_cluster
    except:
        return False, 0

async def main():
    uri = "wss://pumpportal.fun/api/data"
    print("Bot signal jalan...")
    await send_telegram("Bot signal KETAT aktif: 5-25 SOL / 5m")

    async with websockets.connect(uri) as ws:
        payload = {"method": "subscribeNew"}
        await ws.send(json.dumps(payload))
