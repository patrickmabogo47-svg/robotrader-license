import os, asyncio, requests
from fastapi import FastAPI
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

app = FastAPI()
@app.get("/")
def home():
    return {"status": "Live", "bot": "Robo trader SA PRO V2 - Real Price"}
@app.get("/license/{key}")
def license_check(key: str):
    return {"valid": True}

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
USERS = set()

def get_price(symbol):
    # Try 3 sources - never return fake 65000 again
    price = None
    # 1. Binance first
    try:
        r = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}", timeout=5).json()
        price = float(r['price'])
        if price > 0: return price
    except: pass
    # 2. CoinGecko for BTC
    if "BTC" in symbol:
        try:
            r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd", timeout=5).json()
            price = float(r['bitcoin']['usd'])
            if price > 0: return price
        except: pass
    # 3. Yahoo Finance for BTC and GOLD
    try:
        ysym = "BTC-USD" if "BTC" in symbol else "GC=F"
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ysym}"
        r = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=5).json()
        price = float(r['chart']['result'][0]['meta']['regularMarketPrice'])
        if price > 0: return price
    except: pass
    return None

def get_klines(symbol):
    try:
        data = requests.get(f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1h&limit=50", timeout=8).json()
        return [float(c[4]) for c in data]
    except:
        return []

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    USERS.add(update.effective_chat.id)
    btc = get_price("BTCUSDT")
    gold = get_price("PAXGUSDT")
    btc_str = f"${btc:,.2f}" if btc else "Loading..."
    gold_str = f"${gold:,.2f}" if gold else "Loading..."
    await update.message.reply_text(f"✅ PRO V2 ONLINE - REAL PRICE\nBTC {btc_str}\nGOLD {gold_str}\n\n/signal - Real TP/SL 1:2\n/btc /gold /calc 100\nAuto every 1H")

async def signal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    USERS.add(update.effective_chat.id)
    btc = get_price("BTCUSDT")
    gold = get_price("PAXGUSDT")

    if not btc or not gold:
        await update.message.reply_text("⚠️ Price API busy, try /signal again in 10 sec (Yahoo loading)")
        return

    closes = get_klines("BTCUSDT")
    if closes:
        ema20 = sum(closes[-20:])/20
        action = "BUY" if closes[-1] > ema20 else "SELL"
    else:
        action = "SELL" # fallback trend

    # REAL ACCOUNT 1:2 RR
    btc_sl = btc*0.99 if action=="BUY" else btc*1.01
    btc_tp = btc*1.02 if action=="BUY" else btc*0.98
    gold_sl = gold-10 if action=="BUY" else gold+10
    gold_tp = gold+20 if action=="BUY" else gold-20

    msg = (
        f"🤖 PRO V2 REAL PRICE 1:2 RR\n\n"
        f"₿ BTC {action}\n"
        f"Entry {btc:,.2f}\n"
        f"SL {btc_sl:,.2f} (1%)\n"
        f"TP {btc_tp:,.2f} MAIN (2%)\n\n"
        f"🥇 GOLD {action}\n"
        f"Entry {gold:,.2f}\n"
        f"SL {gold_sl:.2f} ($10)\n"
        f"TP {gold_tp:.2f} MAIN ($20)\n\n"
        f"📦 Lot: 0.01 per $100 | Risk 1%\n"
        f"⚠️ Check TradingView before taking!"
    )
    await update.message.reply_text(msg)

async def btc_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await signal_cmd(update, context)
async def gold_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await signal_cmd(update, context)
async def calc_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bal = float(context.args[0]) if context.args else 100
    risk = bal*0.01
    await update.message.reply_text(f"Bal ${bal}\nRisk 1% = ${risk:.2f}\nGOLD lot {risk/10:.2f} (SL $10)\nBTC 0.01 lot per $1000")

telegram_app = None
async def hourly_job():
    while True:
        await asyncio.sleep(3600)
        if not USERS or not telegram_app: continue
        try:
            btc = get_price("BTCUSDT")
            gold = get_price("PAXGUSDT")
            if not btc or not gold: continue
            text = f"⏰ AUTO 1H V2\nBTC ${btc:,.2f}\nGOLD ${gold:,.2f}\nType /signal for full TP/SL"
            for uid in list(USERS):
                try: await telegram_app.bot.send_message(chat_id=uid, text=text)
                except: pass
        except: pass

async def run_bot():
    global telegram_app
    if not BOT_TOKEN: return
    while True:
        try:
            application = ApplicationBuilder().token(BOT_TOKEN).build()
            telegram_app = application
            application.add_handler(CommandHandler("start", start))
            application.add_handler(CommandHandler("signal", signal_cmd))
            application.add_handler(CommandHandler("btc", btc_cmd))
            application.add_handler(CommandHandler("gold", gold_cmd))
            application.add_handler(CommandHandler("calc", calc_cmd))
            await application.initialize()
            await application.start()
            await application.updater.start_polling(drop_pending_updates=True)
            asyncio.create_task(hourly_job())
            print("Bot V2 polling...")
            while True: await asyncio.sleep(3600)
        except Exception as e:
            print(f"Crash {e}"); await asyncio.sleep(5)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(run_bot())
