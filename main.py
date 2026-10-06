import os, asyncio, requests, json
from datetime import datetime
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, Response
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

app = FastAPI()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
USERS = set()

# ===== YOUR VAULT - CHANGE KEY =====
ADMIN_KEY = "Kimberley2026!"
SIGNAL_HISTORY = []
LICENSES = {
    "ROBO-1M-DEMO": {"expiry": "2026-11-04", "plan": "1 Month"},
    "ROBO-3M-DEMO": {"expiry": "2027-02-04", "plan": "3 Months"},
    "ROBO-LIFE-001": {"expiry": "2099-12-31", "plan": "Lifetime"},
}

@app.get("/")
def home(): return {"status": "V3 SUPER Live", "signals": len(SIGNAL_HISTORY)}

@app.get("/license/{k}")
def license_check(k: str):
    from datetime import datetime as dt
    if k not in LICENSES: return {"valid": False}
    expiry = dt.strptime(LICENSES[k]["expiry"], "%Y-%m-%d")
    return {"valid": dt.now() < expiry, "plan": LICENSES[k]["plan"], "expiry": LICENSES[k]["expiry"]}

@app.get("/admin")
def admin(key: str = ""):
    if key!= ADMIN_KEY: return {"error": "Wrong key - use?key=Kimberley2026!"}
    rows = "".join([f"<tr><td>{s['time']}</td><td>{s['pair']}</td><td>{s['action']}</td><td>{s['conf']}%</td><td>{s['d1']}</td><td>{s['price']}</td></tr>" for s in SIGNAL_HISTORY[-100:][::-1]])
    html = f"""<html><head><meta name="viewport" content="width=device-width"><style>body{{background:#0B0F1C;color:#fff;font-family:Arial;padding:15px}}.card{{background:#131A2E;border:1px solid #2A3456;border-radius:12px;padding:15px;margin:10px 0}}table{{width:100%;border-collapse:collapse}}td,th{{padding:8px;border-bottom:1px solid #222;font-size:13px}}</style></head><body><h2>🤖 V3 SUPER VAULT</h2><p>Signals: {len(SIGNAL_HISTORY)} | Users: {len(USERS)}</p><div class="card"><h3>📜 Last 100 Signals (All Visions)</h3><table><tr><th>Time</th><th>Pair</th><th>Action</th><th>Conf</th><th>D1 Trend</th><th>Price</th></tr>{rows}</table></div><div class="card"><a href="/export?key={key}"><button>📥 Export CSV</button></a></div></body></html>"""
    return HTMLResponse(html)

@app.get("/export")
def export(key: str=""):
    if key!= ADMIN_KEY: return {"error": "Wrong key"}
    import io, csv
    out=io.StringIO(); w=csv.writer(out); w.writerow(["time","pair","action","conf","d1","price","ema20","rsi"])
    for s in SIGNAL_HISTORY: w.writerow([s['time'],s['pair'],s['action'],s['conf'],s['d1'],s['price'],s['ema'],s['rsi']])
    return Response(out.getvalue(), media_type="text/csv", headers={"Content-Disposition":"attachment; filename=v3_super_signals.csv"})

# ===== PRICE & KLINES WITH FALLBACK =====
def get_price(sym):
    for url in [f"https://api.binance.com/api/v3/ticker/price?symbol={sym}", f"https://api.bybit.com/v5/market/tickers?category=spot&symbol={sym}"]:
        try:
            r=requests.get(url, timeout=5).json()
            if "price" in r: return float(r["price"])
            if "result" in r: return float(r["result"]["list"][0]["lastPrice"])
        except: pass
    return None

def get_klines(sym, interval="1h", limit=100):
    # 1H klines
    try:
        data=requests.get(f"https://api.binance.com/api/v3/klines?symbol={sym}&interval={interval}&limit={limit}", timeout=8).json()
        if isinstance(data, list) and len(data)>20:
            return [float(c[4]) for c in data]
    except: pass
    return []

def get_d1_trend(sym):
    closes = get_klines(sym, "1d", 60)
    if len(closes)<50: return "UNKNOWN"
    ema20 = sum(closes[-20:])/20
    ema50 = sum(closes[-50:])/50
    return "UP" if ema20 > ema50 else "DOWN"

def analyze_super(closes):
    if len(closes)<50: return "SELL", 55, closes[-1] if closes else 0, 50, "UNKNOWN"
    price=closes[-1]
    ema20=sum(closes[-20:])/20
    ema50=sum(closes[-50:])/50
    # RSI
    gains=losses=0
    for i in range(-14,0):
        d=closes[i]-closes[i-1]
        if d>0: gains+=d
        else: losses+=-d
    rs=gains/(losses+0.0001)
    rsi=100-(100/(1+rs))
    # Trend strength
    dist = (price-ema20)/ema20*100
    trend = (ema20-ema50)/ema50*100

    if price > ema20 and ema20 > ema50:
        action="BUY"
        conf = 65 + min(abs(dist)*12, 15) + min(abs(trend)*80, 15) + (rsi-50)*0.2
    elif price < ema20 and ema20 < ema50:
        action="SELL"
        conf = 65 + min(abs(dist)*12, 15) + min(abs(trend)*80, 15) + (50-rsi)*0.2
    elif price > ema20:
        action="BUY"; conf = 55 + abs(dist)*4
    else:
        action="SELL"; conf = 55 + abs(dist)*4

    conf=int(max(50, min(95, conf)))
    return action, conf, ema20, rsi, ema50

# ===== TELEGRAM =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    USERS.add(update.effective_chat.id)
    await update.message.reply_text("✅ V3 SUPER ONLINE\n/signal = Entry/SL/TP + Conf + D1 Trend\nVault: your-render-url/admin?key=Kimberley2026!")

async def signal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    USERS.add(update.effective_chat.id)
    btc=get_price("BTCUSDT"); gold=get_price("PAXGUSDT")
    if not btc: await update.message.reply_text("⏳ Price API loading, try again 10s"); return
    closes=get_klines("BTCUSDT","1h",100)
    if len(closes)<30: await update.message.reply_text("⏳ Candles loading, try /signal again 10s"); return

    action,conf,ema20,rsi,ema50 = analyze_super(closes)
    d1=get_d1_trend("BTCUSDT")

    # Save to vault
    SIGNAL_HISTORY.append({"time": datetime.now().strftime("%m-%d %H:%M"), "pair": "BTC", "action": action, "conf": conf, "d1": d1, "price": btc, "ema": ema20, "rsi": rsi})
    if len(SIGNAL_HISTORY)>500: SIGNAL_HISTORY.pop(0)

    btc_sl = btc*0.99 if action=="BUY" else btc*1.01
    btc_tp = btc*1.02 if action=="BUY" else btc*0.98
    gold_sl = gold-12 if gold and action=="BUY" else gold+12 if gold else 0
    gold_tp = gold+24 if gold and action=="BUY" else gold-24 if gold else 0

    strength = "🔥 STRONG - TAKE" if conf>=75 else "⚠️ MEDIUM - WAIT" if conf>=65 else "❌ WEAK - SKIP"
    conflict = "✅ ALIGNED" if (action=="BUY" and d1=="UP") or (action=="SELL" and d1=="DOWN") else "⚠️ CONFLICT" if d1!="UNKNOWN" else ""

    msg = f"""🤖 V3 SUPER 1:2 RR + D1 FILTER

₿ BTC {action} - {conf}% {strength}
D1 Trend: {d1} {conflict}
Entry {btc:,.2f}
SL {btc_sl:,.2f}
TP {btc_tp:,.2f}
EMA20 {ema20:,.2f} EMA50 {ema50:,.2f} RSI {rsi:.0f}

🥇 GOLD {action} - {conf}%
Entry {gold:,.2f}
SL {gold_sl:.2f} TP {gold_tp:.2f}

📦 Rule: Only take if >75% + D1 ALIGNED!
💾 Saved to vault"""

    await update.message.reply_text(msg)

async def btc_cmd(u,c): await signal_cmd(u,c)
async def gold_cmd(u,c): await signal_cmd(u,c)

telegram_app=None
async def hourly_job():
    while True:
        await asyncio.sleep(3600)
        if not USERS or not telegram_app: continue
        try:
            closes=get_klines("BTCUSDT","1h",100)
            if len(closes)<30: continue
            action,conf,_,_,_=analyze_super(closes)
            d1=get_d1_trend("BTCUSDT")
            if conf<75: continue
            if (action=="BUY" and d1=="DOWN") or (action=="SELL" and d1=="UP"): continue # Skip conflict
            btc=get_price("BTCUSDT")
            txt=f"⏰ V3 SUPER AUTO {conf}% {action}\nD1 {d1} ALIGNED\nBTC ${btc:,.0f}\n/signal for TP/SL"
            for uid in list(USERS):
                try: await telegram_app.bot.send_message(chat_id=uid, text=txt)
                except: pass
        except: pass

async def run_bot():
    global telegram_app
    if not BOT_TOKEN: return
    while True:
        try:
            app_bot=ApplicationBuilder().token(BOT_TOKEN).build()
            telegram_app=app_bot
            app_bot.add_handler(CommandHandler("start", start))
            app_bot.add_handler(CommandHandler("signal", signal_cmd))
            app_bot.add_handler(CommandHandler("btc", btc_cmd))
            app_bot.add_handler(CommandHandler("gold", gold_cmd))
            await app_bot.initialize(); await app_bot.start()
            await app_bot.updater.start_polling(drop_pending_updates=True)
            asyncio.create_task(hourly_job())
            while True: await asyncio.sleep(3600)
        except Exception as e: print(f"crash {e}"); await asyncio.sleep(5)

@app.on_event("startup")
async def startup_event(): asyncio.create_task(run_bot())
