import os, asyncio, requests
from fastapi import FastAPI
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

app = FastAPI()
@app.get("/")
def home():
    return {"status": "Live", "bot": "PRO"}
@app.get("/license/{key}")
def license_check(key: str):
    return {"valid": True}

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
USERS = set()

def get_price(sym):
    try:
        return float(requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={sym}", timeout=10).json()['price'])
    except:
        return 65000 if "BTC" in sym else 2700

def get_klines(sym):
    try:
        data = requests.get(f"https://api.binance.com/api/v3/klines?symbol={sym}&interval=1h&limit=50", timeout=10).json()
        return [float(c[4]) for c in data]
    except:
        return []

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    USERS.add(update.effective_chat.id)
    btc = get_price("BTCUSDT")
    gold = get_price("PAXGUSDT")
    await update.message.reply_text(f"✅ PRO ONLINE\nBTC ${btc:,.2f}\nGOLD ${gold:,.2f}\n/signal /btc /gold /calc 100\nAuto 1h")

async def signal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    USERS.add(update.effective_chat.id)
    btc = get_price("BTCUSDT")
    gold = get_price("PAXGUSDT")
    closes = get_klines("BTCUSDT")
    action = "BUY" if closes and closes[-1] > sum(closes[-20:])/20 else "SELL"
    # REAL TP/SL 1:2
    btc_sl = btc*0.99 if action=="BUY" else btc*1.01
    btc_tp = btc*1.02 if action=="BUY" else btc*0.98
    gold_sl = gold-10 if action=="BUY" else gold+10
    gold_tp = gold+20 if action=="BUY" else gold-20
    await update.message.reply_text(
        f"🤖 REAL ACCOUNT 1:2 RR\n\n"
        f"₿ BTC {action}\nEntry {btc:,.2f}\nSL {btc_sl:,.2f}\nTP {btc_tp:,.2f} MAIN\n\n"
        f"🥇 GOLD {action}\nEntry {gold:,.2f}\nSL {gold_sl:.2f}\nTP {gold_tp:.2f} MAIN\n\n"
        f"Lot: 0.01 per $100 risk 1%"
    )

async def btc_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await signal_cmd(update, context)
async def gold_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await signal_cmd(update, context)
async def calc_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bal = float(context.args[0]) if context.args else 100
    await update.message.reply_text(f"Bal ${bal} Risk 1% = ${bal*0.01}\nGOLD lot {bal*0.01/10:.2f}\nBTC lot 0.01 per $1000")

telegram_app = None
async def hourly_job():
    while True:
        await asyncio.sleep(3600)
        if not USERS or not telegram_app: continue
        try:
            btc = get_price("BTCUSDT")
            gold = get_price("PAXGUSDT")
            text = f"⏰ AUTO 1H\nBTC ${btc:,.2f} GOLD ${gold:,.2f}\nUse /signal for TP/SL"
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
            print("Bot PRO polling...")
            while True: await asyncio.sleep(3600)
        except Exception as e:
            print(f"Crash {e}"); await asyncio.sleep(5)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(run_bot())
