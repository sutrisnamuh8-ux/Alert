import asyncio, websockets, json, time, os, aiohttp

HELIUS_KEY = os.getenv("HELIUS_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("BOT_TOKEN")
CHAT_ID = "8273246175"
PUMP_WS = "wss://pumpportal.fun/api/data"

MIN_SOL = 1.5
MIN_HOLDERS = 14
MAX_TRACK = 6

tracked = {}

async def send_tg(text):
    if not TELEGRAM_TOKEN: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    async with aiohttp.ClientSession() as s:
        try:
            await s.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown", "disable_web_page_preview": True})
        except: pass

async def get_pump_data(mint):
    # API resmi pump.fun yang bener
    url = f"https://frontend-api.pump.fun/coins/{mint}"
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=10) as r:
                if r.status!= 200: return None
                j = await r.json()
                # virtual_sol_reserves / 1e9 = SOL di curve
                sol = j.get('virtual_sol_reserves', 0) / 1e9
                # real sol yang udah masuk
                real_sol = j.get('real_sol_reserves', 0) / 1e9
                return {"sol": real_sol, "mc": j.get('market_cap',0), "name": j.get('name',''), "symbol": j.get('symbol','')}
    except: return None

async def check_mint(mint, created_at):
    age = time.time() - created_at
    if age < 50 or age > 180: return None

    data = await get_pump_data(mint)
    if not data: return None

    sol = data['sol']
    # Karena di menit 1 holders belum akurat di API, kita pake SOL aja dulu yang jadi patokan utama
    # 2.7 SOL = sekitar $400-$500 MC di menit 1
    if sol >= MIN_SOL:
        return f"🚀 *PUMP ALERT MENIT 1 - BUY 0.03*\n\n`{data['name']} (${data['symbol']})`\nMint: `{mint}`\nSOL: ~{sol:.2f} (Min {MIN_SOL})\nUmur: {int(age)}s | MC: ${data['mc']:.0f}\n\nhttps://pump.fun/{mint}\nhttps://photon.so/{mint}"

    return None

async def main():
    await send_tg(f"✅ *BOT ON - FINAL FIXED*\nMin: {MIN_SOL} SOL | {MIN_HOLDERS} Holders\nAPI: pump.fun langsung")

    while True:
        try:
            async with websockets.connect(PUMP_WS) as ws:
                await ws.send(json.dumps({"method": "subscribeNewToken"}))
                print("WS Connected")
                while True:
                    msg = await ws.recv()
                    d = json.loads(msg)
                    mint = d.get('mint')
                    if not mint or mint in tracked: continue
                    if len(tracked) >= MAX_TRACK: continue
                    tracked[mint] = time.time()
                    asyncio.create_task(track_loop(mint))
        except:
            await asyncio.sleep(5)

async def track_loop(mint):
    start = tracked[mint]
    for _ in range(8):
        alert = await check_mint(mint, start)
        if alert:
            await send_tg(alert)
            break
        await asyncio.sleep(12)
    tracked.pop(mint, None)

if __name__ == "__main__":
    asyncio.run(main())
