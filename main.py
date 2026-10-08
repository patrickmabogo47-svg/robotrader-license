import asyncio, os, json, threading
from datetime import datetime
import aiohttp
import pandas as pd
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.getenv("TELEGRAM_TOKEN", "")
ADMIN_KEY = os.getenv("ADMIN_KEY", "Kimberley2026!")
PORT = int(os.getenv("PORT", 10000))
VERSION = "V4.8.3 SMART BEAST FINAL"
USERS_FILE = "/tmp/users.json"

try:
    with open(USERS_FILE, 'r') as f: USERS = set(json.load(f))
except: USERS = set()

def save_users():
    try:
        with open(USERS_FILE, 'w') as f: json.dump(list(USERS), f)
    except: pass

flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return f"{VERSION} LIVE {datetime.now()} Users:{len(USERS)} TokenSet:{bool(TOKEN)}"

@flask_app.route('/admin')
def admin():
    if request.args.get('key')!= ADMIN_KEY:
        return "Unauthorized", 401
    return home()

def calc_rsi(prices, period=14):
    delta = prices.diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ma_up = up.rolling(window=period).mean()
    ma_down = down.rolling(window=period).mean()
    rs = ma_up / ma_down
    return 100 - (100 / (1 + rs))

def calc_ema(prices, period):
    return prices.ewm(span=period, adjust=False).mean()

async def fetch_okx(symbol="BTC-USDT", interval="15m", limit=100):
    url = f"https://www.okx.com/api/v5/market/candles?instId={symbol}&bar={interval}&limit={limit}"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=10) as resp:
                data = await resp.json()
                if data.get("code")!= "0": return None
                candles = data["data"][::-1]
                df = pd.DataFrame(candles, columns=["ts","o","h","l","c","vol","volCcy","volCcyQuote","confirm"])
                df["close"] = df["c"].astype(float)
                df["high"] = df["h"].astype(float)
                df["low"] = df["l"].astype(float)
                df["RSI"] = calc_rsi(df["close"])
                df["EMA50"] = calc_ema(df["close"],50)
                df["EMA200"] = calc_ema(df["close"],200)
                return df
    except Exception as e:
        print(f"fetch error {e}")
        return None

def detect_signal(df):
    if df is None or len(df) < 60:
        return {"type":"ERROR RETRY","conf":0,"range_low":0,"range_high":0,"price":0,"rsi":0,"is_skip":True}
    close = df["close"].iloc[-1]
    rsi = df["RSI"].iloc[-1]
    recent = df.tail(30)
    range_low = recent["low"].min()
    range_high = recent["high"].max()
    if close > range_high * 1.001:
        return {"type":"BUY BOS","conf":78,"range_low":range_low,"range_high":range_high,"price":close,"rsi":rsi}
    if close < range_low * 0.999:
        return {"type":"SELL BOS","conf":78,"range_low":range_low,"range_high":range_high,"price":close,"rsi":rsi}
    dist_high = (range_high - close) / close * 100
    dist_low = (close - range_low) / close * 100
    if dist_high < 0.4 and df["RSI"].iloc[-1] > df["RSI"].iloc[-5]:
        return {"type":"BUY TL BREAK","conf":72,"range_low":range_low,"range_high":range_high,"price":close,"rsi":rsi}
    if dist_low < 0.4 and df["RSI"].iloc[-1] < df["RSI"].iloc[-5]:
        return {"type":"SELL TL BREAK","conf":72,"range_low":range_low,"range_high":range_high,"price":close,"rsi":rsi}
    return {"type":f"Waiting BOS/TL: Range {int(range_low)}-{int(range_high)} RSI {int(rsi)}","conf":0,"range_low":range_low,"range_high":range_high,"price":close,"rsi":rsi,"is_skip":True}

telegram_app = None
last_signal = {"BTC":"SKIP","GOLD":"SKIP"}

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    USERS.add(update.effective_chat.id); save_users()
    await update.message.reply_text(f"✅ {VERSION} Activated! Auto 15min ON (65%). Use /signal ALL")

async def signal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    USERS.add(update.effective_chat.id); save_users()
    target = (context.args[0].upper() if context.args else "ALL")
    await update.message.reply_text(f"🔍 {VERSION} scanning {target} via OKX...")
    pairs = []
    if target in ["BTC","ALL"]: pairs.append(("BTC","BTC-USDT"))
    if target in ["GOLD","XAU","ALL"]: pairs.append(("GOLD","PAXG-USDT"))
    if target not in ["BTC","GOLD","XAU","ALL"]: pairs.append((target, "BTC-USDT"))
    for name, oid in pairs:
        df = await fetch_okx(oid,"15m",100)
        if df is None: df = await fetch_okx("BTC-USDT","15m",100)
        sig = detect_signal(df)
        if sig.get("is_skip"):
            text = f"⏳ {name} {sig['type']}\nPrice {sig['price']:,.2f} RSI {int(sig['rsi'])}\nRange {int(sig['range_low'])}-{int(sig['range_high'])}"
        else:
            entry=sig['price']; sl=sig['range_low']*0.998 if "BUY" in sig['type'] else sig['range_high']*1.002
            tp1=entry+(entry-sl)*1.5 if "BUY" in sig['type'] else entry-(sl-entry)*1.5
            text=f"🚨 {name} {VERSION} {sig['type']} {sig['conf']}%!\nEntry {entry:,.2f} SL {sl:,.2f} TP1 {tp1:,.2f}\nRSI {int(sig['rsi'])} SMART"
        await update.message.reply_text(text)
        last_signal[name]="SKIP" if sig.get("is_skip") else sig['type']

async def auto_loop():
    await asyncio.sleep(20)
    print(f"{VERSION} auto_loop started")
    while True:
        try:
            if not USERS or not telegram_app: await asyncio.sleep(60); continue
            for name, oid in [("BTC","BTC-USDT"),("GOLD","PAXG-USDT")]:
                df = await fetch_okx(oid,"15m",100)
                if df is None: continue
                sig = detect_signal(df)
                if not sig.get("is_skip") and sig['conf']>=65:
                    if last_signal.get(name,"SKIP")=="SKIP" or "Waiting" in last_signal.get(name,""):
                        entry=sig['price']; sl=sig['range_low']*0.998 if "BUY" in sig['type'] else sig['range_high']*1.002
                        tp1=entry+(entry-sl)*1.5 if "BUY" in sig['type'] else entry-(sl-entry)*1.5
                        caption=f"🚨 AUTO {name} {sig['type']} {sig['conf']}%!\nEntry {entry:,.2f} SL {sl:,.2f} TP1 {tp1:,.2f}\nSMART BEAST"
                        for uid in list(USERS):
                            try: await telegram_app.bot.send_message(chat_id=uid, text=caption)
                            except: pass
                        last_signal[name]=sig['type']
                else:
                    if sig.get("is_skip"): last_signal[name]="SKIP"
        except Exception as e: print(f"auto error {e}")
        await asyncio.sleep(900)

def run_flask():
    flask_app.run(host='0.0.0.0', port=PORT)

async def main():
    global telegram_app
    threading.Thread(target=run_flask, daemon=True).start()
    if not TOKEN:
        print("NO TOKEN SET - Flask only running, waiting for env var")
        while True: await asyncio.sleep(3600)
    try:
        telegram_app=Application.builder().token(TOKEN).build()
        telegram_app.add_handler(CommandHandler("start", start_cmd))
        telegram_app.add_handler(CommandHandler("signal", signal_cmd))
        asyncio.create_task(auto_loop())
        await telegram_app.initialize()
        await telegram_app.start()
        await telegram_app.updater.start_polling()
        print(f"{VERSION} Telegram started")
        while True: await asyncio.sleep(3600)
    except Exception as e:
        print(f"Telegram start error: {e}")
        while True: await asyncio.sleep(3600)

if __name__=="__main__":
    asyncio.run(main())
