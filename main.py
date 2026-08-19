import asyncio, websockets, json, time, os, aiohttp
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("BOT_TOKEN")
HELIUS_KEY = os.getenv("HELIUS_API_KEY")
CHAT_ID = "8273246175"
PUMP_WS = "wss://pumpportal.fun/api/data"
MIN_SOL = 0.2 # GUA TURUNIN DULU BIAR KELIATAN LOG NYA
MAX_TOP10_PERCENT = 28
MAX_TOP1_PERCENT = 12
tracked = {}
trades = {}

async def send_tg(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    async with aiohttp.ClientSession() as s:
        try: await s.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"})
        except: pass

async def main():
    print("BOT START DEBUG LOG MODE", flush=True)
    while True:
        try:
            async with websockets.connect(PUMP_WS) as ws:
                await ws.send(json.dumps({"method": "subscribeNewToken"}))
                print("WS Connected OK", flush=True)
                while True:
                    data = json.loads(await ws.recv())
                    if 'mint' in data and 'symbol' in data:
                        mint = data.get('mint')
                        sym = data.get('symbol','?')
                        print(f"NEW COIN DETECTED: {sym} | {mint}", flush=True)
                        tracked[mint] = time.time()
                        trades[mint] = 0.0
                        await ws.send(json.dumps({"method": "subscribeTokenTrade", "keys": [mint]}))
                    if data.get('txType') == 'buy':
                        mint = data.get('mint')
                        if mint not in trades: continue
                        sol = float(data.get('solAmount',0) or 0)
                        if sol > 1000: sol /= 1e9
                        trades[mint] += sol
                        age = time.time() - tracked[mint]
                        print(f"LOG TRADE: {mint[:8]}... SOL={trades[mint]:.3f} age={int(age)}s", flush=True)
                        if age > 60 and trades[mint] >= MIN_SOL:
                            msg = f"TEST PASS\nMint: `{mint}`\nSOL: {trades[mint]:.2f}\nhttps://pump.fun/{mint}"
                            print(f"SENDING TO TG: {mint}", flush=True)
                            await send_tg(msg)
                            tracked.pop(mint,None)
                            trades.pop(mint,None)
        except Exception as e:
            print(f"ERROR {e}", flush=True)
            await asyncio.sleep(3)

if __name__ == "__main__":
    asyncio.run(main())
