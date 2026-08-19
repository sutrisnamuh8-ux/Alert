import asyncio, websockets, json, time, os, aiohttp

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("BOT_TOKEN")
CHAT_ID = "8273246175"
PUMP_WS = "wss://pumpportal.fun/api/data"
MIN_SOL = 0.2

tracked = {}
trades = {}

async def send_tg(text):
    if not TELEGRAM_TOKEN:
        print("NO TOKEN SET", flush=True)
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    async with aiohttp.ClientSession() as s:
        try:
            await s.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown", "disable_web_page_preview": True})
            print(f"SENT TG: {text[:30]}", flush=True)
        except Exception as e:
            print(f"TG ERROR {e}", flush=True)

async def main():
    print("BOT START - NO HELIUS BYPASS 0.2 SOL", flush=True)
    await send_tg("BOT ON - BYPASS HELIUS 0.2 SOL MODE")

    while True:
        try:
            async with websockets.connect(PUMP_WS) as ws:
                await ws.send(json.dumps({"method": "subscribeNewToken"}))
                print("WS CONNECTED OK - waiting coins", flush=True)

                while True:
                    data = json.loads(await ws.recv())

                    # new coin
                    if 'mint' in data and 'symbol' in data:
                        mint = data.get('mint')
                        if mint in tracked: continue
                        sym = data.get('symbol','?')
                        print(f"NEW COIN: {sym} | {mint}", flush=True)
                        tracked[mint] = time.time()
                        trades[mint] = 0.0
                        try:
                            await ws.send(json.dumps({"method": "subscribeTokenTrade", "keys": [mint]}))
                        except: pass

                    # buy trade
                    if data.get('txType') == 'buy':
                        mint = data.get('mint')
                        if mint not in trades: continue
                        sol = float(data.get('solAmount',0) or 0)
                        if sol > 1000: sol /= 1e9
                        trades[mint] += sol
                        age = time.time() - tracked[mint]
                        print(f"TRADE {mint[:8]} SOL={trades[mint]:.3f} age={int(age)}s
