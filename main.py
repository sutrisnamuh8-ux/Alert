# Alert
import requests, os, asyncio, time

HELIUS_KEY = os.getenv("HELIUS_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
RPC = f"https://mainnet.helius-rpc.com/?api-key={HELIUS_KEY}"

# PROGRAM ID KHUSUS
PUMPFUN = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
PUMPSWAP = "pAMMBay6oceH9fJKBRHGPt5bBfckbFvoQ7KWn88i9j"

tracked = {}
seen = set()

def send_tg(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown", "disable_web_page_preview": True})

def get_mint_from_tx(tx):
    try:
        bals = tx.get("meta", {}).get("postTokenBalances", [])
        if bals:
            # ambil mint yang bukan WSOL
            for b in bals:
                if b.get("mint")!= "So11111111111111111111111111111111111111112":
                    return b.get("mint")
        return None
    except:
        return None

async def main():
    send_tg("🤖 PUMP ALERT ON\nMonitor: PumpFun + PumpSwap | Logic: Menit 2 Organic")
    while True:
        try:
            now = time.time()
            # ambil dari 2 program
            for prog in [PUMPFUN, PUMPSWAP]:
                sigs = requests.post(RPC, json={"jsonrpc":"2.0","id":1,"method":"getSignaturesForAddress","params":[prog, {"limit": 20}]}, timeout=10).json().get("result", [])

                for sig in sigs:
                    s = sig["signature"]
                    if s in seen: continue
                    seen.add(s)

                    tx = requests.post(RPC, json={"jsonrpc":"2.0","id":1,"method":"getTransaction","params":[s, {"maxSupportedTransactionVersion":0}]}, timeout=10).json().get("result")
                    if not tx: continue

                    mint = get_mint_from_tx(tx)
                    if not mint: continue

                    if mint not in tracked:
                        tracked[mint] = {"created": now, "buys": [], "source": prog}

                    age = now - tracked[mint]["created"]
                    if 90 <= age <= 210: # fokus menit 2
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

            # clean
            for k in list(tracked.keys()):
                if now - tracked[k]["created"] > 300:
                    del tracked[k]

        except Exception as e:
            print("err", e)
        await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(main())
