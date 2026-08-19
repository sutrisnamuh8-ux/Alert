import asyncio, websockets, json, time, os, aiohttp

HELIUS_KEY = os.getenv("HELIUS_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("BOT_TOKEN")
CHAT_ID = "8273246175"
PUMP_WS = "wss://pumpportal.fun/api/data"

MIN_SOL = 1.0
MIN_HOLDERS = 10
MAX_TRACK = 10
TOP10_MAX = 35
RPC_DELAY = 0.2

tracked = {}
last_rpc = 0

async def send_tg(text):
    if not TELEGRAM_TOKEN: return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    async with aiohttp.ClientSession() as s:
        try:
            await s.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown", "disable_web_page_preview": True})
            print(f"TG sent: {text[:20]}")
        except Exception as e:
            print(f"TG fail: {e}")

async def safe_get(url):
    global last_rpc
    now = time.time()
    if now - last_rpc < RPC_DELAY:
        await asyncio.sleep(RPC_DELAY)
    last_rpc = time.time()
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, timeout=10) as r:
                return await r.json() if r.status == 200 else None
        except: return None

async def check_mint(mint, created_at):
    age = time.time() - created_at
    if age < 55 or age > 180: return None

    data = await safe_get(f"https://api.helius.xyz/v0/token-metadata?api-key={HELIUS_KEY}&mintAccounts={mint}")
    if not data: return None
    try:
        holders = data[0].get('holders', 0) if isinstance(data, list) else data.get('holders', 0)
        sol = float(data[0].get('sol', 0)) if isinstance(data, list) else float(data.get('sol', 0))
    except: return None

    if sol >= MIN_SOL and holders >= MIN_HOLDERS:
        return f"🚀 *PUMP ALERT MENIT 1 - BUY 0.03*\n\nMint: `{mint}`\nSOL: ~{sol:.1f} | Holders: {holders}\nUmur: {int(age)}s\n\nhttps://pump.fun/{mint}\nhttps://photon.so/{mint}"
    return None

async def main():
    # TEST LANGSUNG BUNYI
    await send_tg(f"🚀 *TEST ALERT JALAN BRO!*\n\nKalau ini masuk, bot lu udah 100% connect Github-Railway-Telegram\n\nSetting sekarang: {MIN_SOL} SOL / {MIN_HOLDERS} Holders")
    await asyncio.sleep(2)
    await send_tg(f"✅ *BOT ON - FINAL MENIT 1*\nMin: {MIN_SOL} SOL | {MIN_HOLDERS} Holders")

    while True:
        try:
            async with websockets.connect(PUMP_WS) as ws:
                await ws.send(json.dumps({"method": "subscribeNewToken"}))
                print("WS Connected")
                while True:
                    msg = await ws.recv()
                    data = json.loads(msg)
                    mint = data.get('mint')
                    if not mint or mint in tracked: continue
                    if len(tracked) >= MAX_TRACK: continue
                    tracked[mint] = time.time()
                    asyncio.create_task(track_loop(mint))
        except Exception as e:
            print(f"WS Error {e}, reconnect 5s")
            await asyncio.sleep(5)

async def track_loop(mint):
    start = tracked[mint]
    for _ in range(6):
        alert = await check_mint(mint, start)
        if alert:
            await send_tg(alert)
            break
        await asyncio.sleep(15)
    tracked.pop(mint, None)

if __name__ == "__main__":
    asyncio.run(main())
