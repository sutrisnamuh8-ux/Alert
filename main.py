import asyncio, websockets, json, time, os, aiohttp
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("BOT_TOKEN")
HELIUS_KEY = os.getenv("HELIUS_API_KEY")
CHAT_ID = "8273246175"
PUMP_WS = "wss://pumpportal.fun/api/data"
MIN_SOL = 1
MAX_TOP10_PERCENT = 35
MAX_TOP1_PERCENT = 15
MIN_HOLDERS = 15
MAX_COIN_AGE_HOURS = 6
tracked = {}
trades = {}
async def send_tg(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    async with aiohttp.ClientSession() as s:
        try:
            await s.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown", "disable_web_page_preview": True})
        except: pass
async def get_holders_analysis(mint):
    if not HELIUS_KEY:
        return None
    try:
        rpc_url = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_KEY}"
        payload = {"jsonrpc":"2.0","id":1,"method":"getTokenLargestAccounts","params":[mint]}
        async with aiohttp.ClientSession() as s:
            async with s.post(rpc_url, json=payload, timeout=10) as r:
                j = await r.json()
                accounts = j.get('result',{}).get('value',[])
                if not accounts:
                    return None
                total_supply = 1000000000
                top10 = sum(float(a.get('amount',0)) for a in accounts[:10]) / total_supply * 100
                top1 = float(accounts[0].get('amount',0)) / total_supply * 100 if accounts else 100
                return {"top10": top10, "top1": top1, "count": len(accounts)}
    except:
        return None
async def main():
    await send_tg(f"BOT ON - FINAL 2-16 MENIT Min: {MIN_SOL} SOL Top10: {MAX_TOP10_PERCENT}% Top1: {MAX_TOP1_PERCENT}%")
    while True:
        try:
            async with websockets.connect(PUMP_WS) as ws:
                await ws.send(json.dumps({"method": "subscribeNewToken"}))
                print("WS Connected FINAL 2-16 - waiting coins...")
                while True:
                    data = json.loads(await ws.recv())
                    if data.get('txType') == 'create' or ('mint' in data and 'symbol' in data):
                        mint = data.get('mint')
                        sym = data.get('symbol','?')
                        if not mint or mint in tracked:
                            continue
                        print(f"NEW: {sym} {mint[:6]}")
                        tracked[mint] = time.time()
                        trades[mint] = 0.0
                        try:
                            await ws.send(json.dumps({"method": "subscribeTokenTrade", "keys": [mint]}))
                        except:
                            pass
                        continue
                    if data.get('txType') == 'buy':
                        mint = data.get('mint')
                        if mint not in tracked:
                            continue
                        try:
                            sol_amt = float(data.get('solAmount',0) or 0)
                            if sol_amt > 1000:
                                sol_amt /= 1e9
                            trades[mint] += sol_amt
                        except:
                            pass
                        age = time.time() - tracked[mint]
                        total_sol = trades[mint]
                        print(f"TRADE {mint[:6]} {total_sol:.2f} SOL age {int(age)}s")
                        if 120 < age < 960 and total_sol >= MIN_SOL:
                            h = await get_holders_analysis(mint)
                            if not h:
                                print(f"SKIP {mint[:6]} no holders data")
                                continue
                            print(f"CHECK {mint[:6]} top10 {h['top10']:.1f}% top1 {h['top1']:.1f}%")
                            if h['top10'] <= MAX_TOP10_PERCENT and h['top1'] <= MAX_TOP1_PERCENT and h['count'] >= MIN_HOLDERS:
                                await send_tg(f"BUBBLEMAPS PASS - BUY Mint: {mint} SOL: {total_sol:.2f} Top10: {h['top10']:.1f}%")
                                print(f"PASS {mint}")
                            tracked.pop(mint, None)
                            trades.pop(mint, None)
        except Exception as e:
            print(f"Err {e}")
            await asyncio.sleep(3)
if __name__ == "__main__":
    asyncio.run(main())
