import asyncio
import websockets
import json
import aiohttp

# --- CONFIG ---
TELEGRAM_BOT_TOKEN = "ISI_TOKEN_BOT_LU"
TELEGRAM_CHAT_ID = "ISI_CHAT_ID_LU"
PUMP_PORTAL_WSS = "wss://pumpportal.fun/api/data"

# Filter biar gak spam
MIN_SOL_BUY = 0.1  # minimal buy 0.1 SOL baru alert

async def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chatId": TELEGRAM_CHAT_ID, # atau "chat_id" tergantung lib
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    async with aiohttp.ClientSession() as session:
        try:
            await session.post(url, json=payload, timeout=10)
            print("-> Alert terkirim ke Tele")
        except Exception as e:
            print(f"Gagal kirim tele: {e}")

async def main():
    print("Bot PumpFun BUY Alert Jalan... tanpa Helius")
    async with websockets.connect(PUMP_PORTAL_WSS) as ws:
        # Subscribe ke semua new token trade
        await ws.send(json.dumps({
            "method": "subscribeNewTrade"
            # kalau mau token spesifik: tambah "keys": ["mint address"]
        }))

        async for message in ws:
            data = json.loads(message)
            # print(data) # uncomment buat debug
            
            # data dari pumpportal biasanya ada txType
            if data.get("txType") != "buy":
                continue
            
            sol_amount = data.get("solAmount", 0) / 1e9 if data.get("solAmount") else data.get("sol_amount", 0)
            if sol_amount < MIN_SOL_BUY:
                continue

            mint = data.get("mint")
            trader = data.get("traderPublicKey
