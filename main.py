import requests, os, asyncio, time

HELIUS_KEY = os.getenv("HELIUS_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if not HELIUS_KEY or not BOT_TOKEN or not CHAT_ID:
    print("ERROR: Variables belum lengkap!")
    exit(1)

RPC = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_KEY}"

PUMPFUN = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
PUMPSWAP = "pAMMBay6oceH9fJKBRHGPt5bBfckbFvoQ7KWn88i9j"

tracked = {}
seen = set()

def send_tg(text):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        r = requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown", "disable_web_page_preview": True}, timeout=10)
        print(f"TG sent: {r.status_code}")
    except Exception as e:
        print(f"TG err: {e}")

def get_mint_from_tx(tx):
    try:
        bals = tx.get("meta", {}).get("postTokenBalances", [])
        for b in bals:
            mint = b.get("mint")
            if mint and mint!= "So11111111111111111111111111111111111111112":
                return mint
    except:
        pass
    return None

async def main():
    send_tg("🤖 *PUMP ALERT ON*\nMonitor: PumpFun + PumpSwap | Logic: Menit 2 Organic")
    print("Bot started...")
    while True:
        try:
            now = time.time()
            for prog in [PUMPFUN, PUMPSWAP]:
                # --- FIX UTAMA DI SINI ---
                resp = requests.post(RPC, json={"jsonrpc":"2.0","id":1,"method":"getSignaturesForAddress","params":[prog, {"limit": 20}]}, timeout=15)
                if resp.status_code!= 200:
                    print(f"RPC error {resp.status_code}: {resp.text[:200]}")
                    continue

                data = resp.json()
                sigs = data.get("result", [])
                if not sigs:
                    continue

                for sig in sigs:
                    s = sig["signature"]
                    if s in seen: continue
                    seen.add(s)

                    tx_resp = requests.post(RPC, json={"jsonrpc":"2.0","id":1,"method":"getTransaction","params":[s, {"maxSupportedTransactionVersion":0}]}, timeout=15)
                    if tx_resp.status_code!= 200: continue
                    tx = tx_resp.json().get("result")
                    if not tx: continue

                    mint = get_mint_from_tx(tx)
                    if not mint: continue

                    if mint not in tracked:
                        tracked[mint] = {"created": now, "buys": [], "source": prog}
                        print(f"New mint tracked: {mint[:10]}...")

                    age = now - tracked[mint]["created"]
                    if 90 <= age <= 210:
                        try:
                            pre = tx.get("meta", {}).get("preBalances", [])
                            post = tx.get("meta", {}).get("postBalances", [])
                            if not pre or not post: continue
                            sol = (pre[0] - post[0]) / 1e9
                            if sol <= 0: continue

                            if 0.2 <= sol <= 5:
                                tracked[mint]["buys"].append(sol)

                            total = sum(tracked[mint]["buys"])
                            count = len(tracked[mint]["buys"])
                            avg = total / count if count else 0

                            if count >= 12 and 15 <= total <= 40 and avg <= 2.5:
                                src = "PumpFun" if tracked[mint]["source"] == PUMPFUN else "PumpSwap"
                                send_tg(f"""🔥 *PUMP TRENCHES - {src}*

💰 Vol mnt 2: {total:.1f} SOL
👥 Wallets: {count} | Avg: {avg:.2f} SOL
⏱️ {int(age)}s

🔗 https://gmgn.ai/sol/{mint}
🔗 https://pump.fun/{mint}
""")
                                tracked[mint]["buys"] = []
                        except:
                            continue

            for k in list(tracked.keys()):
                if now - tracked[k]["created"] > 300:
                    del tracked[k]

        except Exception as e:
            print(f"err {e}")
        await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(main())
