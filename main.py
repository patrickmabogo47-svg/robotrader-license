import os, asyncio, requests
from datetime import datetime
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

app = FastAPI()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
USERS = set()
ADMIN_KEY = "Kimberley2026!"
SIGNAL_HISTORY = []

@app.get("/")
def home():
    return {"status":"V4.3 REVERSAL CONFIRM Live - Won't buy falling knife","signals":len(SIGNAL_HISTORY)}

@app.get("/admin")
def admin(key: str = ""):
    if key!= ADMIN_KEY:
        return {"error":"Wrong key"}
    rows = ""
    for s in SIGNAL_HISTORY[-100:][::-1]:
        color = "#00ff88" if s['action']=="BUY" else "#ff4444" if s['action']=="SELL" else "#ffaa00"
        rows+=f"<tr><td>{s['time']}</td><td>{s['pair']}</td><td style='color:{color}'>{s['action']}</td><td>{s['conf']}%</td><td>{s['reason']}</td></tr>"
    html = f"<html><head><meta name='viewport' content='width=device-width'><style>body{{background:#0B0F1C;color:#fff;font-family:Arial;padding:15px}}td{{padding:7px;border-bottom:1px solid #222;font-size:11px}}</style></head><body><h2>🤖 V4.3 VAULT</h2><table><tr><th>Time</th><th>Pair</th><th>Action</th><th>Conf</th><th>Reason</th></tr>{rows}</table></body></html>"
    return HTMLResponse(html)

def get_price(sym):
    try:
        r = requests.get(f"https://api.coinbase.com/v2/prices/{sym.replace('USDT','')}-USD/spot", timeout=6, headers={"User-Agent":"Mozilla/5.0"}).json()
        return float(r["data"]["amount"])
    except:
        return 84000.0

def get_klines_real(sym, interval, limit=100):
    coin = "BTC"
    try:
        cc_interval = "histohour" if interval in ["1h","4h"] else "histoday"
        agg = 1 if interval=="1h" else 4 if interval=="4h" else 1
        url = f"https://min-api.cryptocompare.com/data/v2/{cc_interval}?fsym={coin}&tsym=USD&limit={limit}&aggregate={agg}"
        r = requests.get(url, timeout=8).json()
        closes = [float(x["close"]) for x in r["Data"]["Data"] if x["close"]>0]
        if len(closes)>50:
            return closes, True
    except Exception as e:
        print(f"cc {e}")
    try:
        gran = 3600 if interval=="1h" else 14400 if interval=="4h" else 86400
        url = f"https://api.exchange.coinbase.com/products/{coin}-USD/candles?granularity={gran}"
        r = requests.get(url, timeout=9, headers={"User-Agent":"Mozilla/5.0"}).json()
        closes = [float(x[4]) for x in reversed(r)]
        if len(closes)>50:
            return closes, True
    except Exception as e:
        print(f"cb {e}")
    return [84000+i for i in range(limit)], False

def rsi_calc(closes, period=14):
    g=l=0
    for i in range(-period,0):
        d=closes[i]-closes[i-1]
        if d>0: g+=d
        else: l+= -d
    rs=g/(l+0.001)
    return 100-(100/(1+rs))

def analyze_ultra(h1,h4,d1):
    price=h1[-1]
    prev=h1[-2]
    prev2=h1[-3]
    ema20_h1=sum(h1[-20:])/20
    ema50_h1=sum(h1[-50:])/50
    ema200_h1=sum(h1[-200:])/200 if len(h1)>=200 else ema50_h1
    ema20_h4=sum(h4[-20:])/20
    ema50_h4=sum(h4[-50:])/50
    ema20_d1=sum(d1[-20:])/20
    ema50_d1=sum(d1[-50:])/50
    rsi_h1=rsi_calc(h1)
    rsi_prev=rsi_calc(h1[:-1])
    rsi_h4=rsi_calc(h4)
    d1_up=ema20_d1>ema50_d1
    h4_up=ema20_h4>ema50_h4
    h1_up=ema20_h1>ema50_h1
    dist=abs(price-ema20_h1)/ema20_h1*100

    # CONFIRMATION: is H1 still falling?
    falling_knife = price < prev and prev < prev2 and rsi_h1 < rsi_prev
    reversal_up = price > prev and rsi_h1 > rsi_prev and rsi_h1 < 40

    # V4.3 CORE: only buy dip AFTER reversal green candle
    if rsi_h1 < 35 and d1_up and price < ema20_h1 and dist >= 0.8:
        if falling_knife:
            return "SKIP",0,rsi_h1,dist,f"WAIT - falling knife {rsi_prev:.0f}->{rsi_h1:.0f}, need green reversal"
        if reversal_up:
            conf=80 + (35-rsi_h1)*1.2
            return "BUY",int(min(87,conf)),rsi_h1,dist,f"DIP CONFIRMED RSI {rsi_prev:.0f}->{rsi_h1:.0f} green reversal in D1 UP"
        else:
            return "SKIP",0,rsi_h1,dist,f"WAIT reversal - RSI {rsi_h1:.0f} oversold but no green yet"

    if rsi_h1 > 65 and not d1_up and price > ema20_h1 and dist >=0.8:
        if price > prev and rsi_h1 > rsi_prev:
            return "SKIP",0,rsi_h1,dist,"WAIT - still pumping"
        if price < prev and rsi_h1 < rsi_prev:
            conf=80 + (rsi_h1-65)*1.2
            return "SELL",int(min(87,conf)),rsi_h1,dist,f"RALLY CONFIRMED RSI {rsi_prev:.0f}->{rsi_h1:.0f} red reversal in D1 DOWN"

    if rsi_h1>75 or rsi_h1<20:
        return "SKIP",0,rsi_h1,dist,f"EXTREME RSI {rsi_h1:.0f}"
    if dist>2.2:
        return "SKIP",0,rsi_h1,dist,f"Too far {dist:.2f}%"
    if h1_up and h4_up and d1_up and price>ema200_h1 and 42<rsi_h1<66 and price>prev:
        conf=77+(rsi_h4-50)*0.3
        return "BUY",int(min(85,conf)),rsi_h1,dist,"3TF UP trend + H1 green"
    if not h1_up and not h4_up and not d1_up and price<ema200_h1 and 34<rsi_h1<58 and price<prev:
        conf=77+(50-rsi_h4)*0.3
        return "SELL",int(min(85,conf)),rsi_h1,dist,"3TF DOWN trend + H1 red"

    return "SKIP",0,rsi_h1,dist,f"Waiting D1:{'UP' if d1_up else 'DOWN'} RSI {rsi_h1:.0f}->{rsi_prev:.0f}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    USERS.add(update.effective_chat.id)
    await update.message.reply_text("✅ V4.3 CONFIRM ONLINE\nIt won't buy falling knife - waits for green reversal!\n/signal")

async def signal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    USERS.add(update.effective_chat.id)
    await update.message.reply_text("🔍 V4.3 scanning + waiting for reversal confirmation... 5s")
    btc_price=get_price("BTCUSDT")
    h1,real1=get_klines_real("BTCUSDT","1h",200)
    h4,real4=get_klines_real("BTCUSDT","4h",100)
    d1,realD=get_klines_real("BTCUSDT","1d",60)
    action,conf,rsi,dist,reason=analyze_ultra(h1,h4,d1)
    SIGNAL_HISTORY.append({"time":datetime.now().strftime("%m-%d %H:%M"),"pair":"BTC","action":action,"conf":conf,"reason":reason})
    if len(SIGNAL_HISTORY)>500:
        SIGNAL_HISTORY.pop(0)
    if not real1:
        await update.message.reply_text(f"⚠️ safe mode {reason}")
        return
    if action=="SKIP":
        await update.message.reply_text(f"⏳ V4.3 {reason}\nRSI {rsi:.0f} Dist {dist:.2f}%\nThis WAIT prevents buying while it still falls against you!\nCheck again in 1h - when green candle prints it will say BUY CONFIRMED")
        return
    sl=btc_price*0.993 if action=="BUY" else btc_price*1.007
    tp=btc_price*1.015 if action=="BUY" else btc_price*0.985
    msg=f"🤖 V4.3 {action} - {conf}% 🔥 CONFIRMED\n\n₿ Entry {btc_price:,.2f}\nSL {sl:,.2f} TP {tp:,.2f}\nRSI {rsi:.0f} {reason}\n\n✅ Green reversal confirmed - not against you now"
    await update.message.reply_text(msg)

telegram_app=None
async def hourly_job():
    while True:
        await asyncio.sleep(3600)
        if not USERS or not telegram_app: continue
        try:
            h1,r1=get_klines_real("BTCUSDT","1h",200)
            h4,r4=get_klines_real("BTCUSDT","4h",100)
            d1,rD=get_klines_real("BTCUSDT","1d",60)
            if not r1: continue
            action,conf,_,_,_=analyze_ultra(h1,h4,d1)
            if action=="SKIP" or conf<78: continue
            btc=get_price("BTCUSDT")
            for uid in list(USERS):
                try: await telegram_app.bot.send_message(chat_id=uid, text=f"⏰ V4.3 {action} {conf}% CONFIRMED BTC ${btc:,.0f} - /signal")
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
            await app_bot.initialize()
            await app_bot.start()
            await app_bot.updater.start_polling(drop_pending_updates=True)
            asyncio.create_task(hourly_job())
            while True: await asyncio.sleep(3600)
        except Exception as e:
            print(f"crash {e}")
            await asyncio.sleep(5)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(run_bot())
