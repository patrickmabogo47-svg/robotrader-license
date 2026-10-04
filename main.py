import os, asyncio, requests
from fastapi import FastAPI
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

app = FastAPI()
@app.get("/")
def home(): return {"status": "Live", "bot": "V3 Confidence%"}
@app.get("/license/{k}")
def license_check(k: str): return {"valid": True}

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
USERS = set()

def get_price(sym):
    for url in [
        f"https://api.binance.com/api/v3/ticker/price?symbol={sym}",
    ]:
        try:
            r = requests.get(url, timeout=5).json()
            return float(r['price'])
        except: pass
    if "BTC" in sym:
        try:
            r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd", timeout=6).json()
            return float(r['bitcoin']['usd'])
        except: pass
    try:
        y = "BTC-USD" if "BTC" in sym else "GC=F"
        r = requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{y}", headers={"User-Agent":"Mozilla/5.0"}, timeout=6).json()
        return float(r['chart']['result'][0]['meta']['regularMarketPrice'])
    except: return None

def get_klines(sym):
    try:
        data = requests.get(f"https://api.binance.com/api/v3/klines?symbol={sym}&interval=1h&limit=100", timeout=8).json()
        closes = [float(c[4]) for c in data]
        return closes
    except: return []

def analyze(closes):
    if len(closes) < 25:
        return "SELL", 55, 20, 45
    ema20 = sum(closes[-20:])/20
    ema50 = sum(closes[-50:])/50
    price = closes[-1]
    # RSI 14
    gains=losses=0
    for i in range(-14,0):
        d=closes[i]-closes[i-1]
        if d>0: gains+=d
        else: losses+=-d
    rs = gains/(losses+0.0001)
    rsi = 100 - (100/(1+rs))

    # Confidence calc
    dist_ema = (price-ema20)/ema20*100 # %
    trend_strength = (ema20-ema50)/ema50*100

    if price > ema20 and ema20 > ema50:
        action="BUY"
        conf = 50 + min(abs(dist_ema)*15, 25) + min(abs(trend_strength)*100, 15) + (rsi-50)*0.3
    elif price < ema20 and ema20 < ema50:
        action="SELL"
        conf = 50 + min(abs(dist_ema)*15, 25) + min(abs(trend_strength)*100, 15) + (50-rsi)*0.3
    elif price > ema20:
        action="BUY"
        conf = 52 + abs(dist_ema)*5
    else:
        action="SELL"
        conf = 52 + abs(dist_ema)*5

    conf = int(max(50, min(95, conf)))
    return action, conf, ema20, rsi

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    USERS.add(update.effective_chat.id)
    await update.message.reply_text("✅ V3 PRO ONLINE\n/signal = Entry/SL/TP + Confidence%\nConfidence >75% = STRONG take\n50-65% = WEAK skip")

async def signal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    USERS.add(update.effective_chat.id)
    btc = get_price("BTCUSDT")
    gold = get_price("PAXGUSDT")
    if not btc or not gold:
        await update.message.reply_text("⏳ API loading, try /signal in 10s")
        return

    closes = get_klines("BTCUSDT")
    action, conf, ema, rsi = analyze(closes)

    btc_sl = btc*0.99 if action=="BUY" else btc*1.01
    btc_tp = btc*1.02 if action=="BUY" else btc*0.98
    gold_sl = gold-10 if action=="BUY" else gold+10
    gold_tp = gold+20 if action=="BUY" else gold-20

    strength = "🔥 STRONG - TAKE" if conf>=75 else "⚠️ MEDIUM - careful" if conf>=65 else "❌ WEAK - SKIP"

    msg = (
        f"🤖 V3 PRO 1:2 RR + CONFIDENCE\n\n"
        f"₿ BTC {action} - {conf}% {strength}\n"
        f"Entry {btc:,.2f}\n"
        f"SL {btc_sl:,.2f} (1%)\n"
        f"TP {btc_tp:,.2f} (2%)\n"
        f"EMA20 {ema:,.2f} RSI {rsi:.0f}\n\n"
        f"🥇 GOLD {action} - {conf}%\n"
        f"Entry {gold:,.2f}\n"
        f"SL {gold_sl:.2f} (-$10)\n"
        f"TP {gold_tp:.2f} (+$20)\n\n"
        f"📦 0.01 lot per $100 | 1% risk\n"
        f"Rule: Only take if Conf >75%!"
    )
    await update.message.reply_text(msg)

async def btc_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE): await signal_cmd(update, context)
async def gold_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE): await signal_cmd(update, context)
async def calc_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bal = float(context.args[0]) if context.args else 100
    await update.message.reply_text(f"Bal ${bal} Risk 1%=${bal*0.01:.2f}\nGOLD lot {(bal*0.01)/10:.3f}")

telegram_app=None
async def hourly_job():
    while True:
        await asyncio.sleep(3600)
        if not USERS or not telegram_app: continue
        try:
            btc=get_price("BTCUSDT")
            gold=get_price("PAXGUSDT")
            closes=get_klines("BTCUSDT")
            action,conf,_,_=analyze(closes)
            if conf<75: continue
            txt=f"⏰ AUTO 1H ALERT {conf}% {action}\nBTC ${btc:,.0f} GOLD ${gold:.0f}\nType /signal for TP/SL"
            for uid in list(USERS):
                try: await telegram_app.bot.send_message(chat_id=uid, text=txt)
                except: pass
        except: pass

async def run_bot():
    global telegram_app
    if not BOT_TOKEN: return
    while True:
        try:
            app_bot = ApplicationBuilder().token(BOT_TOKEN).build()
            telegram_app=app_bot
            app_bot.add_handler(CommandHandler("start", start))
            app_bot.add_handler(CommandHandler("signal", signal_cmd))
            app_bot.add_handler(CommandHandler("btc", btc_cmd))
            app_bot.add_handler(CommandHandler("gold", gold_cmd))
            app_bot.add_handler(CommandHandler("calc", calc_cmd))
            await app_bot.initialize()
            await app_bot.start()
            await app_bot.updater.start_polling(drop_pending_updates=True)
            asyncio.create_task(hourly_job())
            print("V3 polling")
            while True: await asyncio.sleep(3600)
        except Exception as e:
            print(f"crash {e}"); await asyncio.sleep(5)

@app.on_event("startup")
async def startup_event(): asyncio.create_task(run_bot())
