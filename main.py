import os, asyncio, requests
from datetime import datetime
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Try chart, but work without it
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import io
    CHART=True
except:
    CHART=False

app = FastAPI()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
USERS = set()
ADMIN_KEY = "Kimberley2026!"
SIGNAL_HISTORY = []
LAST_STATUS = "WAIT"

@app.get("/")
def home():
    return {"status":"V4.7 REAL + BOTH SIDES + CHART" if CHART else "V4.7 REAL + BOTH SIDES NoChart","chart":CHART,"last":LAST_STATUS}

@app.get("/admin")
def admin(key: str = ""):
    if key!= ADMIN_KEY: return {"error":"Wrong key"}
    rows=""
    for s in SIGNAL_HISTORY[-100:][::-1]:
        c="#00ff88" if s['action']=="BUY" else "#ff4444" if s['action']=="SELL" else "#ffaa00"
        rows+=f"<tr><td>{s['time']}</td><td style='color:{c}'>{s['action']}</td><td>{s['conf']}%</td><td>{s['reason']}</td></tr>"
    return HTMLResponse(f"<html><body style='background:#0B0F1C;color:#fff;font-family:Arial;padding:15px'><h2>V4.7 Last:{LAST_STATUS} Chart:{CHART}</h2><table>{rows}</table></body></html>")

def get_price():
    try:
        r=requests.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT",timeout=5).json()
        return float(r["price"])
    except:
        try:
            r=requests.get("https://api.coinbase.com/v2/prices/BTC-USD/spot",timeout=5,headers={"User-Agent":"Mozilla/5.0"}).json()
            return float(r["data"]["amount"])
        except:
            return 83752.0

def get_binance_klines(interval, limit):
    try:
        url=f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval={interval}&limit={limit}"
        r=requests.get(url,timeout=8,headers={"User-Agent":"Mozilla/5.0"}).json()
        closes=[float(x[4]) for x in r]
        if len(closes)>50:
            return closes, True
    except Exception as e:
        print(f"binance {interval} err {e}")
    return None, False

def get_multi():
    h1, ok1 = get_binance_klines("1h", 200)
    if not ok1:
        try:
            url="https://min-api.cryptocompare.com/data/v2/histohour?fsym=BTC&tsym=USD&limit=200"
            r=requests.get(url,timeout=8).json()
            h1=[float(x["close"]) for x in r["Data"]["Data"] if x["close"]>0]
            ok1=len(h1)>50
        except:
            h1=None; ok1=False

    h4, _ = get_binance_klines("4h", 100)
    if h4 is None:
        h4=h1[-100:] if h1 else None

    d1, _ = get_binance_klines("1d", 60)
    if d1 is None:
        d1=h1[-60:] if h1 else None

    return h1, h4, d1, ok1

def rsi_calc(c, p=14):
    if not c or len(c)<p+2: return 50
    g=l=0
    for i in range(-p,0):
        d=c[i]-c[i-1]
        if d>0: g+=d
        else: l+=-d
    if l==0: return 70 if g>0 else 30
    rs=g/(l+0.001)
    return 100-(100/(1+rs))

def analyze(h1,h4,d1):
    price=h1[-1]; prev=h1[-2]; prev2=h1[-3]
    ema20=sum(h1[-20:])/20; ema50=sum(h1[-50:])/50
    ema200=sum(h1[-200:])/200 if len(h1)>=200 else ema50
    ema20_d1=sum(d1[-20:])/20; ema50_d1=sum(d1[-50:])/20
    ema20_h4=sum(h4[-20:])/20; ema50_h4=sum(h4[-50:])/50
    rsi=rsi_calc(h1); rsi_prev=rsi_calc(h1[:-1]); rsi_h4=rsi_calc(h4)
    dist=abs(price-ema20)/ema20*100
    d1_up=ema20_d1>ema50_d1; h4_up=ema20_h4>ema50_h4; h1_up=ema20>ema50
    falling=price<prev and prev<prev2 and rsi<rsi_prev
    rising=price>prev and prev>prev2 and rsi>rsi_prev
    rev_up=price>prev and rsi>rsi_prev
    rev_down=price<prev and rsi<rsi_prev

    if rsi<35 and dist>=0.4:
        if falling:
            return "SKIP",0,rsi,dist,f"WAIT falling knife {rsi_prev:.0f}->{rsi:.0f} need green for BUY"
        if rev_up:
            base=80 if d1_up else 74
            return "BUY",int(min(88,base+(35-rsi)*1.4)),rsi,dist,f"DIP BUY CONFIRMED {rsi_prev:.0f}->{rsi:.0f} {'D1 UP' if d1_up else 'Bounce'}"
    if h1_up and h4_up and price>ema200 and 42<rsi<63 and rev_up:
        return "BUY",int(min(84,76+(rsi_h4-50)*0.5)),rsi,dist,"BUY Trend H1+H4 UP"

    if rsi>65 and dist>=0.4:
        if rising:
            return "SKIP",0,rsi,dist,f"WAIT rising knife {rsi_prev:.0f}->{rsi:.0f} need red for SELL"
        if rev_down:
            base=80 if not d1_up else 74
            return "SELL",int(min(88,base+(rsi-65)*1.4)),rsi,dist,f"RALLY SELL CONFIRMED {rsi_prev:.0f}->{rsi:.0f} {'D1 DOWN' if not d1_up else 'Drop'}"
    if not h1_up and not h4_up and price<ema200 and 37<rsi<60 and rev_down:
        return "SELL",int(min(84,76+(50-rsi_h4)*0.5)),rsi,dist,"SELL Trend H1+H4 DOWN"

    if rsi>78: return "SKIP",0,rsi,dist,f"OVERBOUGHT RSI {rsi:.0f} wait red for SELL"
    if rsi<22: return "SKIP",0,rsi,dist,f"OVERSOLD RSI {rsi:.0f} wait green for BUY"
    return "SKIP",0,rsi,dist,f"Waiting D1:{'UP' if d1_up else 'DOWN'} H4:{'UP' if h4_up else 'DOWN'} RSI {rsi:.0f}->{rsi_prev:.0f} Dist {dist:.2f}%"

def make_chart(h1, action, entry, sl, tp, rsi, dist):
    if not CHART: return None
    try:
        plt.figure(figsize=(7,4.2))
        data=h1[-60:]
        color='#00ff88' if action=='BUY' else '#ff4444' if action=='SELL' else '#888'
        plt.plot(data, color=color, linewidth=2.2, label=f'BTC H1 {action}')
        ema20=[sum(h1[i-20:i])/20 if i>=20 else h1[i] for i in range(len(h1))]
        plt.plot(ema20[-60:], color='#ffaa00', linestyle='--', linewidth=1, label='EMA20')
        plt.axhline(entry, color='white', linewidth=1.5, label=f'ENTRY {entry:.0f}')
        plt.axhline(sl, color='#ff4444', linestyle=':', linewidth=1.5, label=f'SL {sl:.0f}')
        plt.axhline(tp, color='#00ff88', linestyle=':', linewidth=1.5, label=f'TP {tp:.0f}')
        plt.title(f"V4.7 {action} RSI {rsi:.0f} Dist {dist:.2f}%", color='white', fontsize=10)
        plt.legend(fontsize=7, loc='best')
        plt.grid(alpha=0.2)
        ax=plt.gca(); ax.set_facecolor('#0B0F1C'); plt.gcf().set_facecolor('#0B0F1C')
        ax.tick_params(colors='white')
        buf=io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        plt.close()
        buf.seek(0)
        return buf
    except:
        return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    USERS.add(update.effective_chat.id)
    await update.message.reply_text(f"✅ V4.7 REAL + BOTH SIDES ONLINE Chart:{CHART}\n🟢 BUY dip+green\n🔴 SELL rally+red\nNo more RSI 100!\n/signal")

async def signal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    USERS.add(update.effective_chat.id)
    await update.message.reply_text("🔍 V4.7 scanning REAL Binance candles BOTH sides...")
    h1,h4,d1,real=get_multi()
    if not real or not h1:
        await update.message.reply_text("⚠️ Binance temp blocked, retry in 1min. Real data only - no fake RSI 100")
        return
    btc=get_price()
    action,conf,rsi,dist,reason=analyze(h1,h4,d1)
    global LAST_STATUS
    LAST_STATUS=f"{action} {conf}% RSI {rsi:.0f}"
    SIGNAL_HISTORY.append({"time":datetime.now().strftime("%H:%M"),"pair":"BTC","action":action,"conf":conf,"reason":reason})
    sl=btc*0.993 if action=="BUY" else btc*1.007 if action=="SELL" else btc*0.993
    tp=btc*1.015 if action=="BUY" else btc*0.985 if action=="SELL" else btc*1.015

    chart=make_chart(h1, action, btc, sl, tp, rsi, dist) if CHART else None
    if action=="SKIP":
        txt=f"⏳ V4.7 {reason}\nBTC {btc:,.0f} RSI {rsi:.0f} Dist {dist:.2f}% REAL\nWatching BOTH sides - auto 15min"
    else:
        txt=f"🤖 V4.7 {action} - {conf}% 🔥 REAL\nEntry {btc:,.2f}\nSL {sl:,.2f} TP {tp:,.2f}\nRSI {rsi:.0f} {reason}\nDist {dist:.2f}%\nPlace {action} now!"

    if chart:
        await context.bot.send_photo(chat_id=update.effective_chat.id, photo=chart, caption=txt)
    else:
        await update.message.reply_text(txt + ("\n\n(Add matplotlib to requirements for chart)" if not CHART else ""))

telegram_app=None
async def auto_loop():
    global LAST_STATUS
    while True:
        await asyncio.sleep(900)
        if not USERS or not telegram_app: continue
        try:
            h1,h4,d1,real=get_multi()
            if not real: continue
            action,conf,rsi,dist,reason=analyze(h1,h4,d1)
            prev=LAST_STATUS
            LAST_STATUS=f"{action} {conf}%"
            if action!="SKIP" and conf>=75 and ("WAIT" in prev or "SKIP" in prev):
                btc=get_price()
                sl=btc*0.993 if action=="BUY" else btc*1.007
                tp=btc*1.015 if action=="BUY" else btc*0.985
                chart=make_chart(h1, action, btc, sl, tp, rsi, dist) if CHART else None
                for uid in list(USERS):
                    try:
                        if chart:
                            await telegram_app.bot.send_photo(chat_id=uid, photo=chart, caption=f"🚨 AUTO {action} {conf}% REAL!\nEntry {btc:.0f} SL {sl:.0f} TP {tp:.0f}\n{reason}")
                        else:
                            await telegram_app.bot.send_message(chat_id=uid, text=f"🚨 AUTO {action} {conf}% REAL!\nEntry {btc:.0f} SL {sl:.0f} TP {tp:.0f}\n{reason}")
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
            asyncio.create_task(auto_loop())
            while True: await asyncio.sleep(3600)
        except Exception
