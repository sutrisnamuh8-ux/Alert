import asyncio, websockets, json, time, os, aiohttp

HELIUS_KEY = os.getenv("HELIUS_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("BOT_TOKEN")
CHAT_ID = "8273246175"
PUMP_WS = "wss://pumpportal.fun/api/data"

MIN_SOL = 1.5
MIN_HOLDERS = 15
MAX_TRACK = 10

tracked = {}

async def send_tg(text):
    if not TELEGRAM_TOKEN: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    async with aiohttp.ClientSession() as s:
        try:
            await s.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown", "disable_web_page_preview": True})
        except: pass

async def get_pump_data(mint):
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"https://frontend-api.pump.fun/coins/{mint}", timeout=10) as r:
                if r.status!=200: return None
                j = await r.json()
                sol = j.get('virtual_sol_reserves', 0) / 1e9
                real_sol = j.get('real_sol_reserves', 0) / 1e9
                return {"sol": real_sol if real_sol > 0 else sol, "mc": j.get('usd_market_cap',0), "name": j.get('name',''), "symbol": j.get('symbol','')}
    except: return None

async def check_mint(mint, created_at):
    age = time.time() - created_at
    if age < 45 or age > 180: return None
    data = await get_pump_data(mint)
    if not data: return None
    if data['sol'] >= MIN_SOL:
        return f"🚀 *PUMP ALERT 1.5 SOL*\n\n`{data['name']} (${data['symbol']})`\nMint: `{mint}`\nSOL: ~{data['sol']:.2f} | Umur: {int(age)}s\nMC: ${data['mc']:.0f}\n\nhttps://pump.fun/{mint}"

async def main():
    await send_tg(f"✅ *BOT ON - 1.5 SOL / 15 Holders*\nFilter aktif, tunggu 3-5 menit")
    while True:
        try:
            async with websockets.connect(PUMP_WS) as ws:
                await ws.send(json.dumps({"method": "subscribeNewToken"}))
                while True:
                    d = json.loads(await ws.recv())
                    mint = d.get('mint')
                    if not mint or mint in tracked or len(tracked) >= MAX_TRACK: continue
                    tracked[mint] = time.time()
                    asyncio.create_task(track_loop(mint))
        except: await asyncio.sleep(5)

async def track_loop(mint):
    start = tracked[mint]
    for _ in range(10):
        alert = await check_mint(mint, start)
        if alert:
            await send_tg(alert)
            break
        await asyncio.sleep(10)
    tracked.pop(mint, None)

if __name__ == "__main__":
    asyncio.run(main())
