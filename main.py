import os, asyncio, requests, io
from datetime import datetime
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

app = FastAPI()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
USERS = set()
ADMIN_KEY = "Kimberley2026!"
SIGNAL_HISTORY = []
LAST_STATUS = "WAIT"

@app.get("/")
def home():
    return {"status":"V4.5 BOTH BUY+SELL AUTO Live","last":LAST_STATUS}

@app.get("/admin")
def admin(key: str = ""):
    if key!= ADMIN_KEY:
        return {"error":"Wrong key"}
    rows=""
    for s in SIGNAL_HISTORY[-100:][::-1]:
        c="#00ff88" if s['action']=="BUY" else "#ff4444" if s['action']=="SELL" else "#ffaa00"
        rows+=f"<tr><td>{s['time']}</td><td style='color:{c}'>{s['action']}</td><td>{s['conf']}%</td><td>{s['reason']}</td></tr>"
    return HTMLResponse(f"<html><body style='background:#0B0F1C;color:white;font-family:Arial;padding:15px'><h2>V4.5 Both Sides Last:{LAST_STATUS}</h2><table>{rows}</table></body></html>")

def get_price():
    try:
        r=requests.get("https://api.coinbase.com/v2/prices/BTC-USD/spot",timeout=6,headers={"User-Agent":"Mozilla/5.0"}).json()
        return float(r["data"]["amount"])
    except:
        return 84000.0

def get_klines(limit=200):
    try:
        url=f"https://min-api.cryptocompare.com/data/v2/histohour?fsym=BTC&tsym=USD&limit={limit}&aggregate=1"
        r=requests.get(url,timeout=8).json()
        closes=[float(x["close"]) for x in r["Data"]["Data"] if x["close"]>0]
        if len(closes)>50:
            return closes, True
    except: pass
    return [84000+i*2 for i in range(limit)], False

def get_klines_multi():
    h1,_=get_klines(200)
    try:
        url="https://min-api.cryptocompare.com/data/v2/histohour?fsym=BTC&tsym=USD&limit=100&aggregate=4"
        r=requests.get(url,timeout=8).json()
        h4=[float(x["close"]) for x in r["Data"]["Data"] if x["close"]>0]
    except: h4=h1[-100:]
    try:
        url="https://min-api.cryptocompare.com/data/v2/histoday?fsym=BTC&tsym=USD&limit=60"
        r=requests.get(url,timeout=8).json()
        d1=[float(x["close"]) for x in r["Data"]["Data"] if x["close"]>0]
    except: d1=h1[-60:]
    return h1,h4,d1,True

def rsi_calc(c, p=14):
    g=l=0
    for i in range(-p,0):
        d=c[i]-c[i-1]
        if d>0: g+=d
        else: l+=-d
    rs=g/(l+0.001)
    return 100-(100/(1+rs))

def analyze_both(h1,h4,d1):
    price=h1[-1]; prev=h1[-2]; prev2=h1[-3]
    ema20=sum(h1[-20:])/20; ema50=sum(h1[-50:])/50
    ema200=sum(h1[-200:])/200 if len(h1)>=200 else ema50
    ema20_d1=sum(d1[-20:])/20; ema50_d1=sum(d1[-50:])/50
    ema20_h4=sum(h4[-20:])/20; ema50_h4=sum(h4[-50:])/50
    rsi=rsi_calc(h1); rsi_prev=rsi_calc(h1[:-1]); rsi_h4=rsi_calc(h4)
    dist=abs(price-ema20)/ema20*100
    d1_up=ema20_d1>ema50_d1; h4_up=ema20_h4>ema50_h4; h1_up=ema20>ema50 or price>ema20

    falling_knife=price<prev and prev<prev2 and rsi<rsi_prev
    rising_knife=price>prev and prev>prev2 and rsi>rsi_prev
    reversal_up=price>prev and rsi>rsi_prev
    reversal_down=price<prev and rsi<rsi_prev

    # === BUY SIGNALS ===
    # 1. Oversold dip buy - works both D1 up and down but higher conf if D1 up
    if rsi < 35 and dist>=0.5:
        if falling_knife:
            return "SKIP",0,rsi,dist,f"WAIT - falling knife {rsi_prev:.0f}->{rsi:.0f}, need green reversal for BUY"
        if reversal_up:
            base=78 if d1_up else 72
            conf=base + (35-rsi)*1.3 + (1.5-dist)*2
            trend="D1 UP dip" if d1_up else "Counter-trend bounce D1 DOWN"
            return "BUY",int(min(88,conf)),rsi,dist,f"DIP BUY CONFIRMED {rsi_prev:.0f}->{rsi:.0f} {trend}"

    # 2. Trend continuation BUY
    if h1_up and h4_up and price>ema200 and 40<rsi<62 and reversal_up:
        conf=75 + (rsi_h4-50)*0.4
        return "BUY",int(min(85,conf)),rsi,dist,"BUY Trend continuation H1+H4 UP + green"

    # === SELL SIGNALS ===
    # 1. Overbought rally sell - works both ways
    if rsi > 65 and dist>=0.5:
        if rising_knife:
            return "SKIP",0,rsi,dist,f"WAIT - rising knife {rsi_prev:.0f}->{rsi:.0f}, need red reversal for SELL"
        if reversal_down:
            base=78 if not d1_up else 72
            conf=base + (rsi-65)*1.3 + (1.5-dist)*2
            trend="D1 DOWN rally" if not d1_up else "Counter-trend drop D1 UP"
            return "SELL",int(min(88,conf)),rsi,dist,f"RALLY SELL CONFIRMED {rsi_prev:.0f}->{rsi:.0f} {trend}"

    # 2. Trend continuation SELL
    if not h1_up and not h4_up and price<ema200 and 38<rsi<60 and reversal_down:
        conf=75 + (50-rsi_h4)*0.4
        return "SELL",int(min(85,conf)),rsi,dist,"SELL Trend continuation H1+H4 DOWN + red"

    # EXTREME filters
    if rsi>78:
        return "SKIP",0,rsi,dist,f"OVERBOUGHT RSI {rsi:.0f} waiting red reversal for SELL"
    if rsi<22:
        return "SKIP",0,rsi,dist,f"OVERSOLD RSI {rsi:.0f} waiting green reversal for BUY"
    if dist>2.5:
        return "SKIP",0,rsi,dist,f"Too far {dist:.2f}% from EMA20 - choppy"

    return "SKIP",0,rsi,dist,f"Waiting setup D1:{'UP' if d1_up else 'DOWN'} H4:{'UP' if h4_up else 'DOWN'} RSI {rsi:.0f}->{rsi_prev:.0f}"

def make_chart(h1, action, entry, sl, tp, rsi, dist):
    plt.figure(figsize=(7,4.2))
    data=h1[-60:]
    color='#00ff88' if action=='BUY' else '#ff4444' if action=='SELL' else '#888888'
    plt.plot(data, color=color, linewidth=2.2, label=f'BTC H1 {action}')
    ema20=[sum(h1[i-20:i])/20 if i>=20 else h1[i] for i in range(len(h1))]
    plt.plot(ema20[-60:], color='#ffaa00', linestyle='--', linewidth=1.1, label='EMA20')
    plt.axhline(entry, color='white', linewidth=1.6, label=f'ENTRY {entry:.0f}')
    plt.axhline(sl, color='#ff4444', linestyle=':', linewidth=1.6, label=f'SL {sl:.0f}')
    plt.axhline(tp, color='#00ff88', linestyle=':', linewidth=1.6, label=f'TP {tp:.0f}')
    title=f"V4.5 {action} {rsi:.0f} RSI Dist {dist:.2f}% - {action} CONFIRMED" if action!='SKIP' else f"V4.5 WAIT RSI {rsi:.0f}"
    plt.title(title, color='white', fontsize=10)
    plt.legend(fontsize=7, loc='best')
    plt.grid(alpha=0.2)
    ax=plt.gca(); ax.set_facecolor('#0B0F1C'); plt.gcf().set_facecolor('#0B0F1C')
    ax.tick_params(colors='white')
    buf=io.BytesIO()
    plt.savefig(buf, format='png', dpi=160, bbox_inches='tight')
    plt.close()
    buf.seek(0)
    return buf

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    USERS.add(update.effective_chat.id)
    await update.message.reply_text("✅ V4.5 BOTH SIDES ONLINE\nBUY = oversold dip + green reversal\nSELL = overbought rally + red reversal\nAuto check every 15min + screenshot\n/signal = instant chart")

async def signal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    USERS.add(update.effective_chat.id)
    await update.message.reply_text("🔍 V4.5 scanning BOTH BUY and SELL... 6s")
    h1,h4,d1,_=get_klines_multi()
    btc=get_price()
    action,conf,rsi,dist,reason=analyze_both(h1,h4,d1)
    global LAST_STATUS
    LAST_STATUS=f"{action} {conf}%"
    SIGNAL_HISTORY.append({"time":datetime.now().strftime("%H:%M"),"pair":"BTC","action":action,"conf":conf,"reason":reason})
    sl=btc*0.993 if action=="BUY" else btc*1.007 if action=="SELL" else btc*0.993
    tp=btc*1.015 if action=="BUY" else btc*0.985 if action=="SELL" else btc*1.015
    buf=make_chart(h1, action, btc, sl, tp, rsi, dist)
    if action=="SKIP":
        caption=f"⏳ {reason}\nBTC {btc:,.0f} RSI {rsi:.0f} Dist {dist:.2f}%\nNo BUY/SELL yet - watching both sides\nNext auto-check 15min"
    else:
        caption=f"🤖 V4.5 {action} - {conf}% 🔥 CONFIRMED\nEntry {btc:,.2f}\nSL {sl:,.2f} TP {tp:,.2f}\nRSI {rsi:.0f} {reason}\n\nChart below - {action} setup!"
    await context.bot.send_photo(chat_id=update.effective_chat.id, photo=buf, caption=caption)

telegram_app=None
async def auto_loop():
    global LAST_STATUS
    while True:
        await asyncio.sleep(900)
        if not USERS or not telegram_app: continue
        try:
            h1,h4,d1,_=get_klines_multi()
            action,conf,rsi,dist,reason=analyze_both(h1,h4,d1)
            prev=LAST_STATUS
            LAST_STATUS=f"{action} {conf}%"
            SIGNAL_HISTORY.append({"time":datetime.now().strftime("%H:%M"),"pair":"BTC","action":action,"conf":conf,"reason":reason+" AUTO"})
            if action!="SKIP" and conf>=75 and ("WAIT" in prev or "SKIP" in prev):
                btc=get_price()
                sl=btc*0.993 if action=="BUY" else btc*1.007
                tp=btc*1.015 if action=="BUY" else btc*0.985
                buf=make_chart(h1, action, btc, sl, tp, rsi, dist)
                for uid in list(USERS):
                    try:
                        await telegram_app.bot.send_photo(chat_id=uid, photo=buf, caption=f"🚨 AUTO {action} {conf}% CONFIRMED!\nEntry {btc:,.0f} SL {sl:.0f} TP {tp:.0f}\n{reason}\nFlipped from WAIT to {action}!\nChart 👇")
                    except: pass
        except Exception as e:
            print(f"auto {e}")

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
        except Exception as e:
            print(f"crash {e}"); await asyncio.sleep(5)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(run_bot())
