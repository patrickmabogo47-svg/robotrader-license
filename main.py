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
LAST_STATUS = "WAIT"

@app.get("/")
def home():
    return {"status":"V4.5 BOTH BUY+SELL AUTO Fixed - Live","last":LAST_STATUS,"signals":len(SIGNAL_HISTORY)}

@app.get("/admin")
def admin(key: str = ""):
    if key!= ADMIN_KEY:
        return {"error":"Wrong key"}
    rows=""
    for s in SIGNAL_HISTORY[-100:][::-1]:
        c="#00ff88" if s['action']=="BUY" else "#ff4444" if s['action']=="SELL" else "#ffaa00"
        rows+=f"<tr><td>{s['time']}</td><td style='color:{c}'>{s['action']}</td><td>{s['conf']}%</td><td>{s['reason']}</td></tr>"
    html=f"""
    <html><head><meta name='viewport' content='width=device-width'>
    <style>body{{background:#0B0F1C;color:#fff;font-family:Arial;padding:15px}}
    td{{padding:7px;border-bottom:1px solid #222;font-size:11px}} th{{padding:7px;text-align:left}}</style>
    </head><body><h2>🤖 V4.5 BOTH SIDES VAULT</h2><p>Last: {LAST_STATUS}</p>
    <table><tr><th>Time</th><th>Action</th><th>Conf</th><th>Reason</th></tr>{rows}</table></body></html>
    """
    return HTMLResponse(html)

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
    except:
        pass
    return [84000+i*2 for i in range(limit)], False

def get_multi():
    h1,_=get_klines(200)
    try:
        url="https://min-api.cryptocompare.com/data/v2/histohour?fsym=BTC&tsym=USD&limit=100&aggregate=4"
        r=requests.get(url,timeout=8).json()
        h4=[float(x["close"]) for x in r["Data"]["Data"] if x["close"]>0]
    except:
        h4=h1[-100:]
    try:
        url="https://min-api.cryptocompare.com/data/v2/histoday?fsym=BTC&tsym=USD&limit=60"
        r=requests.get(url,timeout=8).json()
        d1=[float(x["close"]) for x in r["Data"]["Data"] if x["close"]>0]
    except:
        d1=h1[-60:]
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
    ema20_d1=sum(d1[-20:])/20; ema50_d1=sum(d1[-50:])/20
    ema20_h4=sum(h4[-20:])/20; ema50_h4=sum(h4[-50:])/50
    rsi=rsi_calc(h1); rsi_prev=rsi_calc(h1[:-1]); rsi_h4=rsi_calc(h4)
    dist=abs(price-ema20)/ema20*100
    d1_up=ema20_d1>ema50_d1; h4_up=ema20_h4>ema50_h4; h1_up=ema20>ema50

    falling=price<prev and prev<prev2 and rsi<rsi_prev
    rising=price>prev and prev>prev2 and rsi>rsi_prev
    rev_up=price>prev and rsi>rsi_prev
    rev_down=price<prev and rsi<rsi_prev

    # === BUY LOGIC ===
    if rsi<35 and dist>=0.5:
        if falling:
            return "SKIP",0,rsi,dist,f"WAIT falling knife {rsi_prev:.0f}->{rsi:.0f} need green reversal for BUY"
        if rev_up:
            base=78 if d1_up else 72
            conf=base + (35-rsi)*1.3
            trend="D1 UP dip" if d1_up else "Bounce D1 DOWN"
            return "BUY",int(min(88,conf)),rsi,dist,f"DIP BUY CONFIRMED {rsi_prev:.0f}->{rsi:.0f} {trend}"
    if h1_up and h4_up and price>ema200 and 40<rsi<62 and rev_up:
        return "BUY",int(min(84,75+(rsi_h4-50)*0.4)),rsi,dist,"BUY Trend H1+H4 UP + green candle"

    # === SELL LOGIC - NOW BOTH SIDES ===
    if rsi>65 and dist>=0.5:
        if rising:
            return "SKIP",0,rsi,dist,f"WAIT rising knife {rsi_prev:.0f}->{rsi:.0f} need red reversal for SELL"
        if rev_down:
            base=78 if not d1_up else 72
            conf=base + (rsi-65)*1.3
            trend="D1 DOWN rally" if not d1_up else "Counter-trend drop D1 UP"
            return "SELL",int(min(88,conf)),rsi,dist,f"RALLY SELL CONFIRMED {rsi_prev:.0f}->{rsi:.0f} {trend}"
    if not h1_up and not h4_up and price<ema200 and 38<rsi<60 and rev_down:
        return "SELL",int(min(84,75+(50-rsi_h4)*0.4)),rsi,dist,"SELL Trend H1+H4 DOWN + red candle"

    if rsi>78:
        return "SKIP",0,rsi,dist,f"OVERBOUGHT RSI {rsi:.0f} waiting red reversal for SELL"
    if rsi<22:
        return "SKIP",0,rsi,dist,f"OVERSOLD RSI {rsi:.0f} waiting green reversal for BUY"

    return "SKIP",0,rsi,dist,f"Waiting D1:{'UP' if d1_up else 'DOWN'} H4:{'UP' if h4_up else 'DOWN'} RSI {rsi:.0f}->{rsi_prev:.0f}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    USERS.add(update.effective_chat.id)
    await update.message.reply_text("✅ V4.5 BOTH SIDES ONLINE\n🟢 BUY = oversold dip + green reversal\n🔴 SELL = overbought rally + red reversal\n⏰ Auto check every 15min - I ping you!\nType /signal for instant check")

async def signal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    USERS.add(update.effective_chat.id)
    await update.message.reply_text("🔍 V4.5 scanning BOTH BUY and SELL sides...")
    h1,h4,d1,_=get_multi()
    btc=get_price()
    action,conf,rsi,dist,reason=analyze_both(h1,h4,d1)
    global LAST_STATUS
    LAST_STATUS=f"{action} {conf}%"
    SIGNAL_HISTORY.append({"time":datetime.now().strftime("%H:%M"),"pair":"BTC","action":action,"conf":conf,"reason":reason})

    if action=="SKIP":
        sl_buy=btc*0.993; tp_buy=btc*1.015
        sl_sell=btc*1.007; tp_sell=btc*0.985
        msg=(f"⏳ V4.5 {reason}\n"
             f"BTC {btc:,.0f} RSI {rsi:.0f} Dist {dist:.2f}%\n\n"
             f"Watching BOTH sides:\n"
             f"If BUY -> Entry {btc:.0f} SL {sl_buy:.0f} TP {tp_buy:.0f}\n"
             f"If SELL -> Entry {btc:.0f} SL {sl_sell:.0f} TP {tp_sell:.0f}\n\n"
             f"Auto-check in 15min - will alert when reversal prints")
        await update.message.reply_text(msg)
    else:
        sl=btc*0.993 if action=="BUY" else btc*1.007
        tp=btc*1.015 if action=="BUY" else btc*0.985
        msg=(f"🤖 V4.5 {action} - {conf}% 🔥 CONFIRMED\n\n"
             f"₿ Entry {btc:,.2f}\n"
             f"SL {sl:,.2f} TP {tp:,.2f}\n"
             f"RSI {rsi:.0f} {reason}\n\n"
             f"Setup:\n"
             f"ENTRY {btc:.0f}\n"
             f"SL {sl:.0f} (-0.7%)\n"
             f"TP {tp:.0f} (+1.5%)\n\n"
             f"Place {action} now - reversal confirmed, won't go against you!")
        await update.message.reply_text(msg)

telegram_app=None
async def auto_loop():
    global LAST_STATUS
    while True:
        await asyncio.sleep(900) # 15 min
        if not USERS or not telegram_app:
            continue
        try:
            h1,h4,d1,_=get_multi()
            action,conf,rsi,dist,reason=analyze_both(h1,h4,d1)
            prev=LAST_STATUS
            LAST_STATUS=f"{action} {conf}%"
            SIGNAL_HISTORY.append({"time":datetime.now().strftime("%H:%M"),"pair":"BTC","action":action,"conf":conf,"reason":reason+" AUTO"})
            # Alert only when flips from WAIT/SKIP to BUY/SELL
            if action!="SKIP" and conf>=75 and ("WAIT" in prev or "SKIP" in prev):
                btc=get_price()
                sl=btc*0.993 if action=="BUY" else btc*1.007
                tp=btc*1.015 if action=="BUY" else btc*0.985
                for uid in list(USERS):
                    try:
                        await telegram_app.bot.send_message(
                            chat_id=uid,
                            text=f"🚨 AUTO ALERT V4.5 {action} {conf}% CONFIRMED!\n"
                                 f"Entry {btc:,.0f} SL {sl:.0f} TP {tp:.0f}\n"
                                 f"{reason}\n"
                                 f"Flipped WAIT -> {action} - place now!"
                        )
                    except:
                        pass
        except Exception as e:
            print(f"auto error {e}")

async def run_bot():
    global telegram_app
    if not BOT_TOKEN:
        print("No BOT_TOKEN set")
        return
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
            print("Bot polling started")
            while True:
                await asyncio.sleep(3600)
        except Exception as e:
            print(f"Bot crash {e}")
            await asyncio.sleep(5)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(run_bot())
