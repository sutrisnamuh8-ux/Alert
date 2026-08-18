import asyncio
import time
from collections import deque

# SETTING - BIAR GAK 429
MAX_TRACK = 2 # cuma track 2 token max barengan
tracked_tokens = {}
token_queue = deque()
last_rpc_call = 0
RPC_DELAY = 0.6 # jeda 0.6 detik tiap nanya Helius (free limit aman)

async def safe_helius_call(func):
    global last_rpc_call
    now = time.time()
    wait = RPC_DELAY - (now - last_rpc_call)
    if wait > 0:
        await asyncio.sleep(wait)
    last_rpc_call = time.time()
    try:
        return await func()
    except Exception as e:
        if "429" in str(e):
            print("⚠️ Helius 429, sleep 5s")
            await asyncio.sleep(5)
        return None

# Di bagian New mint tracked, ganti jadi gini:
def on_new_mint(mint):
    if len(tracked_tokens) >= MAX_TRACK:
        # lagi penuh, skip token baru
        print(f"Skip {mint[:6]}... queue penuh ({len(tracked_tokens)}/{MAX_TRACK})")
        return
    if mint not in tracked_tokens:
        tracked_tokens[mint] = time.time()
        print(f"New mint tracked: {mint} | Tracking: {len(tracked_tokens)}/{MAX_TRACK}")

# Di bagian cek volume menit ke-2, bungkus dengan safe_helius_call
# Contoh:
# sol_data = await safe_helius_call(lambda: get_buys(mint))

# Di bagian token selesai (udah lewat 210 detik), hapus biar slot kosong
def cleanup_tokens():
    now = time.time()
    for mint, start in list(tracked_tokens.items()):
        if now - start > 210: # udah lewat menit ke-2
            del tracked_tokens[mint]
            print(f"Done tracking {mint[:6]} | Slot free: {len(tracked_tokens)}/{MAX_TRACK}")
