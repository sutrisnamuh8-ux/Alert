import asyncio, websockets, json, time, os, aiohttp

HELIUS_KEY = os.getenv("HELIUS_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
PUMP_WS = "wss://pumpportal.fun/api/data"

# === SETTING FILTER LU DISINI ===
MIN_SOL = 8
MIN_HOLDERS = 20
MAX_TRACK = 2
RPC_DELAY = 0.8

tracked = {}
last_rpc = 0

async def send_tg(text):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        async with aiohttp.ClientSession() as s:
            await s.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown", "disable_web_page_preview": True})
    except Exception as e:
        print(f"TG err {e}")

async def safe_get(url):
    global last_rpc
    now = time.time()
    if now - last_rpc < RPC_DELAY:
        await asyncio.sleep(RPC_DELAY - (now - last_rpc))
    last_rpc = time.time()
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=10) as r:
                if r.status == 429:
                    print("⚠️ 429 sleep 5s")
                    await asyncio.sleep(5)
                    return None
                return await r.json()
    except Exception as e:
        print(f"GET err {e}")
        return None

async def check_mint(mint):
    start = tracked[mint]
    await asyncio.sleep(100) # tunggu sampe detik 100

    for _ in range(7): # cek dari detik 100 - 170 (menit ke-2)
        elapsed = time.time() - start
        if elapsed > 175:
            break

        # Ambil data dari pump.fun
        data = await safe_get(f"https://frontend-api.pump.fun/coins/{mint}")
        if not data:
            await asyncio.sleep(10)
            continue

        try:
            # data pump kadang beda field, kita coba ambil
            # Estimasi SOL di menit ke-2 kita pakai total market cap / logic sederhana
            # Untuk akurat, pakai trade history, tapi ini versi stabil anti 429

            # Simulasi ambil buys - ganti sesuai logic asli lu kalo punya
            # Di sini kita pakai virtual sol reserves untuk estimasi
            holders = data.get("holder_count", 0) or data.get("num_holders", 0) or 0

            # Hitung SOL: pakai usd market cap / harga sol ~160
            mcap = data.get("usd_market_cap", 0)
            sol_vol = mcap / 160 if mcap else 0

            print(f"Check {mint[:6]} | {int(elapsed)}s | ~{sol_vol:.1f} SOL | {holders} holders")

            # === FILTER UTAMA ===
            if sol_vol >= MIN_SOL and holders >= MIN_HOLDERS:
                msg = f"🚀 *PUMP ALERT*\n\nMint: `{mint}`\nSOL: ~{sol_vol:.1f} (min {MIN_SOL})\nHolders: {holders} (min {MIN_HOLDERS})\nUmur: {int(elapsed)}s\n\nhttps://pump.fun/{mint}\nhttps://photon.so/{mint}"
                await send_tg(msg)
                print(f"🔥 ALERT SENT {mint[:6]}")
                break

        except Exception as e:
            print(f"Check err {e}")

        await asyncio.sleep(10)

    if mint in tracked:
        del tracked[mint]
        print(f"Done {mint[:6]} | Slot {len(tracked)}/{MAX_TRACK}")

async def main():
    await send_tg(f"✅ *BOT ON - SETTING BARU*\nMin: {MIN_SOL} SOL | {MIN_HOLDERS} Holders\nMax Track: {MAX_TRACK} | Anti 429")
    print(f"BOT STARTED {MIN_SOL} SOL / {MIN_HOLDERS} Holders")
    while True:
        try:
            async with websockets.connect(PUMP_WS) as ws:
                await ws.send(json.dumps({"method": "subscribeNewToken"}))
                print("WS Connected")
                async for raw in ws:
                    try:
                        j = json.loads(raw)
                        mint = j.get("mint")
                        if not mint or mint in tracked:
                            continue
                        if len(tracked) >= MAX_TRACK:
                            print(f"Skip {mint[:6]} full {len(tracked)}/{MAX_TRACK}")
                            continue
                        tracked[mint] = time.time()
                        print(f"New mint tracked: {mint} | {len(tracked)}/{MAX_TRACK}")
                        asyncio.create_task(check_mint(mint))
                    except:
                        continue
        except Exception as e:
            print(f"WS DC {e} retry 3s")
            await asyncio.sleep(3)

if __name__ == "__main__":
    asyncio.run(main())
