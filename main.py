import os, asyncio, requests
from fastapi import FastAPI
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

app = FastAPI()
@app.get("/")
def home():
    return {"status": "Live", "bot": "Robo trader SA PRO", "rr": "1:2"}
@app.get("/license/{key}")
def license_check(key: str):
    return {"valid": True}

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
USERS = set()

def get_price(symbol):
    try:
        r = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}", timeout=10).json()
        return float(r['price'])
    except:
        return None

def get_klines(symbol, limit=60):
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1h&limit={limit}"
        data = requests.get(url, timeout=10).json()
        closes = [float(c[4]) for c in data]
        return closes
    except:
        return []

def analyze(closes):
    if len(closes) < 50:
        return "WAIT", 50, closes[-1] if closes else 0
    ema20 = sum(closes[-20:]) / 20
    ema50 = sum(closes[-50:]) / 50
    last = closes[-1]
    gains = [max(0, closes[i]-closes[i-1]) for i in range(1,len(closes))]
    losses = [max(0, closes[i-1]-closes[i]) for i in range(1,len(closes))]
    avg_gain = sum(gains[-14:])/14
    avg_loss = sum(losses[-14:])/14 if sum(losses[-14:])!=0 else 0.001
    rsi = 100 - (100/(1+avg_gain/avg_loss))
    if last > ema20 > ema50 and rsi < 68 and rsi > 45:
        return "BUY", rsi, last
    elif last < ema20 < ema50 and rsi > 32 and rsi < 55:
        return "SELL", rsi, last
    else:
        return "WAIT", rsi, last

def build_signal(symbol_name, symbol_code, is_gold=False):
    closes = get_klines(symbol_code)
    price = closes[-1] if closes else get_price(symbol_code) or (2700 if is_gold else 65000)
    action, rsi, _ = analyze(closes)

    if is_gold:
        # GOLD REAL ACCOUNT: $10 SL, $20 TP = 1:2
        if action == "BUY":
            sl = price - 10
            tp1 = price + 10
            tp2 = price + 20
            tp3 = price + 35
        elif action == "SELL":
            sl = price + 10
            tp1 = price - 10
            tp2 = price - 20
            tp3 = price - 35
        else:
            sl = price - 8
            tp1 = price + 8
            tp2 = price + 16
            tp3 = price + 25
            action = "WAIT - NO TRADE"
        lot_info = "Lot: 0.01 per $100 (10$ risk)"
        rr = "RR 1:2"
    else:
        # BTC REAL ACCOUNT: 1% SL, 2% TP = 1:2
        if action == "BUY":
            sl = price * 0.990  # 1% SL
            tp1 = price * 1.010
            tp2 = price * 1.020  # 2% TP main
            tp3 = price * 1.035
        elif action == "SELL":
            sl = price * 1.010
            tp1 = price * 0.990
            tp2 = price * 0.980
            tp3 = price * 0.965
        else:
            sl = price * 0.992
            tp1 = price * 1.008
            tp2 = price * 1.016
            tp3 = price * 1.025
            action = "WAIT - NO TRADE"
        lot_info = "Lot: 0.01 BTC per $1000 | Risk 1%"
        rr = "RR 1:2"

    msg = (
        f"{'🥇' if is_gold else '₿'} {symbol_name} {action}\n"
        f"💰 Entry: {price:,.2f}\n"
        f"🛑 SL: {sl:,.2f}\n"
        f"✅ TP1: {tp1:,.2f}\n"
        f"✅ TP2: {tp2:,.2f} (MAIN)\n"
        f"✅ TP3: {tp3:,.2f}\n"
        f"📊 RSI: {rsi:.1f} | {rr}\n"
        f"📦 {lot_info}\n"
    )
    return msg, action

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    USERS.add(update.effective_chat.id)
    btc_price = get_price("BTCUSDT") or 0
    gold_price = get_price("PAXGUSDT") or 0
    await update.message.reply_text(
        f"✅ ROBO TRADER SA PRO ONLINE\n\n"
        f"₿ BTC: ${btc_price:,.2f}\n"
        f"🥇 GOLD: ${gold_price:,.2f}\n\n"
        f"📈 Real 1:2 RR | TP/SL for real account\n"
        f"⏰ Auto signals every 1 hour\n\n"
        f"Commands:\n"
        f
