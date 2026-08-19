import asyncio, websockets, json, time, os, aiohttp

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("BOT_TOKEN")
HELIUS_KEY = os.getenv("HELIUS_API_KEY")
CHAT_ID = "8273246175"
PUMP_WS = "wss://pumpportal.fun/api/data"

# === FINAL SETTING LU ===
MIN_SOL = 1.5
MAX_TOP10_PERCENT = 28
MAX_TOP1_PERCENT = 15 # Anti bundle: 1 wallet max 12%
MIN_HOLDERS = 15
MAX_COIN_AGE_HOURS = 6 # Skip coin lebih dari 6 jam

tracked = {}
trades = {}

async def send_tg(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    async with aiohttp.ClientSession() as s:
        try:
            await s.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown", "disable_web_page_preview": True})
        except: pass

async def get_holders_analysis(mint):
    if not HELIUS_KEY: return None
    try:
        rpc_url = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_KEY}"
        payload = {"jsonrpc":"2.0","id":1,"method":"getTokenLargestAccounts","params":[mint]}
        async with aiohttp.ClientSession() as s:
            async with s.post(rpc_url, json=payload, timeout=10) as r:
                j = await r.json()
                accounts = j.get('result',{}).get('value',[])
                if not accounts: return None
                total_supply = 1000000000
                top10 = sum(float(a.get('amount',0)) for a in accounts[:10]) / total_supply * 100
                top1 = float(accounts[0].get('amount',0)) / total_supply * 100 if accounts else 100
                return {"top10": top10, "top1": top1, "count": len(accounts)}
    except: return None

async def main():
    await send_tg(f"✅ *BOT ON - BUBBLEMAPS 28% + 6H FILTER*\nMin: {MIN_SOL} SOL\nTop10 Max: {MAX_TOP10_PERCENT}%\nTop1 Max: {MAX_TOP1_PERCENT}%\nSkip: >{MAX_COIN_AGE_HOURS} Jam")

    while True:
        try:
            async with websockets.connect(PUMP_WS) as ws:
                await ws.send(json.dumps({"method": "subscribeNewToken"}))
                print("WS Connected 28% Mode")

                while True:
                    data = json.loads(await ws.recv())

                    if data.get('txType') == 'create' or ('mint' in data and 'symbol' in data):
                        mint = data.get('mint')
                        # FILTER 6 JAM - cek created_at dari pumpportal kalau ada
                        # PumpPortal kasih timestamp, kalau gak ada kita anggap baru
                        created_at = data.get('createdAt') or data.get('timestamp') or time.time()*1000
                        try:
                            # kalau timestamp dalam ms
                            coin_age_hours = (time.time() - (created_at/1000)) / 3600 if created_at > 1000000000000 else 0
                            if coin_age_hours > MAX_COIN_AGE_HOURS:
                                print(f"SKIP {mint[:6]} umur {coin_age_hours:.1f} jam > 6 jam")
                                continue
                        except: pass

                        if not mint or mint in tracked: continue
                        tracked[mint] = time.time()
                        trades[mint] = 0.0
                        try: await ws.send(json.dumps({"method": "subscribeTokenTrade", "keys": [mint]}))
                        except: pass
                        continue

                    if data.get('txType') == 'buy':
                        mint = data.get('mint')
                        if mint not in tracked: continue
                        try:
                            sol_amt = float(data.get('solAmount',0) or 0)
                            if sol_amt > 1000: sol_amt /= 1e9
                            trades[mint] += sol_amt
                        except: pass

                        age = time.time() - tracked[mint]
                        total_sol = trades[mint]

                        # Cek menit 1 - menit 3
                        if 45 < age < 180 and total_sol >= MIN_SOL:
                            print(f"Check bubblemaps {mint[:6]} SOL {total_sol:.2f}")
                            h = await get_holders_analysis(mint)
                            if not h: continue

                            # FILTER UTAMA: Top10 28% + Top1 12% + Skip bundle
                            if h['top10'] <= MAX_TOP10_PERCENT and h['top1'] <= MAX_TOP1_PERCENT and h['count'] >= MIN_HOLDERS:
                                await send_tg(
                                    f"🚀 *BUBBLEMAPS PASS 28% - BUY 0.03*\n\n"
                                    f"Mint: `{mint}`\n"
                                    f"SOL: {total_sol:.2f} | Umur: {int(age)}s\n"
                                    f"Top10: {h['top10']:.1f}% ✅ (<28%)\n"
                                    f"Top1: {h['top1']:.1f}% ✅ (<12%)\n"
                                    f"Holders: {h['count']}\n"
                                    f"Coin: <{MAX_COIN_AGE_HOURS} Jam ✅\n\n"
                                    f"https://pump.fun/{mint}\n"
                                    f"https://bubblemaps.io/sol/{mint}"
                                )
                            else:
                                print(f"REJECT top10 {h['top10']:.1f}% top1 {h['top1']:.1f}%")

                            tracked.pop(mint, None)
                            trades.pop(mint, None)

        except Exception as e:
            print(f"Err {e}")
            await asyncio.sleep(3)

if __name__ == "__main__":
    asyncio.run(main())
