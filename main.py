import asyncio
import websockets
import json
import time
import os
import aiohttp

# --- CONFIG ---
HELIUS_KEY = os.getenv("HELIUS_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
PUMPFUN_WS = "wss://pumpportal.fun/api/data"

MAX_TRACK = 2
RPC_DELAY = 0.7 # detik, biar aman dari 429

tracked = {} # mint -> start_time
queue = []
last_rpc = 0

async def send_tg(msg):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        async with aiohttp.ClientSession() as s:
            await s.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})
    except Exception as e:
        print(f"TG Error: {e}")

async def safe_rpc(coro_func):
    global last_rpc
    now = time.time()
    diff = now - last_rpc
    if diff < RPC_DELAY:
        await asyncio.sleep(RPC_DELAY - diff)
    last_rpc = time.time()
    try:
        return await coro_func()
    except Exception as e:
        if "429" in str(e):
            print("⚠️ 429! Sleep 6s")
            await asyncio.sleep(6)
        else:
            print(f"RPC err: {e}")
        return None

async def check_mint(mint):
    start = tracked[mint]
    await asyncio.sleep(90) # tunggu menit ke-1.5

    # cek di menit ke-2 (90-150 detik)
    for i in range(6): # cek 6x selama 60 detik
        elapsed = time.time() - start
        if elapsed < 90 or elapsed > 160:
            await asyncio.sleep(10)
            continue

        async def get_vol():
            async with aiohttp.ClientSession() as s:
                # Panggil helius get transaction - ganti sesuai function lu
                url = f"https://api.helius.xyz/v0/token-metadata?api-key={HELIUS_KEY}"
                # Simplifikasi: lu pake logic cek buys lu disini
                # Contoh ambil data pump
                pump_url = f"https://frontend-api.pump.fun/coins/{mint}"
                async with s.get(pump_url) as r:
                    data = await r.json()
                    return data

        data = await safe_rpc(get_vol)
        if not data:
            continue

        # LOGIC ALERT LU TARO DISINI
        # Contoh: kalo volume > 15 SOL
        try:
            # sesuaikan field nya
            print(f"Checking {mint[:8]} | {int(time.time()-start)}s")
            # if data['total_sol'] > 15: dst
        except:
            pass
        await asyncio.sleep(10)

    # selesai
    if mint in tracked:
        del tracked[mint]
        print(f"✅ Done {mint[:6]} | Free slot {len(tracked)}/{MAX_TRACK}")

async def main():
    await send_tg("✅ *PUMP ALERT ON - FIX 429*\nMax track: 2 token\nMode: Anti 429")
    print("Bot started FIX 429")
    while True:
        try:
            async with websockets.connect(PUMPFUN_WS) as ws:
                await ws.send(json.dumps({"method": "subscribeNewToken"}))
                print("WS Connected")
                async for msg in ws:
                    try:
                        data = json.loads(msg)
                        mint = data.get("mint")
                        if not mint:
                            continue

                        if len(tracked) >= MAX_TRACK:
                            print(f"Skip {mint[:6]}... full {len(tracked)}/{MAX_TRACK}")
                            continue

                        if mint not in tracked:
                            tracked[mint] = time.time()
                            print(f"New mint tracked: {mint} | {len(tracked)}/{MAX_TRACK}")
                            asyncio.create_task(check_mint(mint))

                    except Exception as e:
                        print(f"WS loop err: {e}")
        except Exception as e:
            print(f"WS disconnected {e}, reconnect 3s")
            await asyncio.sleep(3)

if __name__ == "__main__":
    asyncio.run(main())
