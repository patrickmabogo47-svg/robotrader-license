import asyncio, os, json, threading
from datetime import datetime
import aiohttp
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from io import BytesIO
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_KEY = os.getenv("ADMIN_KEY", "Kimberley2026!")
PORT = int(os.getenv("PORT", 10000))
VERSION = "V4.8.3 SMART BEAST"
USERS_FILE = "/tmp/users.json"

try:
    with open(USERS_FILE, 'r') as f: USERS = set(json.load(f))
except: USERS = set()

def save_users():
    with open(USERS_FILE, 'w') as f: json.dump(list(USERS), f)

flask_app = Flask(__name__)
@flask_app.route('/')
def home(): return f"{VERSION} LIVE {datetime.now()} Users:{len(USERS)}"
@flask_app.route('/admin')
def admin():
    if request.args.get('key')!=ADMIN_KEY: return "Unauthorized",401
    return home()

def calc_rsi(prices, period=14):
    delta = prices.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calc_ema(prices, period):
    return prices.ewm(span=period, adjust=False).mean()

def calc_confidence(df, break_type):
    close=df['close'].iloc[-1]; rsi=df['RSI'].iloc[-1]
    ema50=df['EMA50'].iloc[-1]; ema200=df['EMA200'].iloc[-1]
    recent=df.tail(30)
    range_pct=(recent['high'].max()-recent['low'].min())/close*100
    score=50
    if close>ema50>ema200 or close<ema50<ema200: score+=15
    elif close>ema50: score+=5
    if 40<rsi<70: score+=10
    elif rsi<30 or rsi>75: score-=10
    if range_pct<2.5: score+=20
    elif range_pct<4.0: score+=10
    if break_type in ["BOS","TL BREAK"]: score+=10
    return min(95,max(10,int(score)))

async def fetch_okx(symbol="BTC-USDT", interval="15m", limit=100):
    url=f"https://www.okx.com/api/v5/market/candles?instId={symbol}&bar={interval}&limit={limit}"
    headers={"User-Agent":"Mozilla/5.0"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=10) as resp:
                data=await resp.json()
                if data.get("code")!="0": return None
                candles=data["data"][::-1]
                df=pd.DataFrame(candles, columns=["ts","o","h","l","c","vol","volCcy","volCcyQuote","confirm"])
                df["close"]=df["c"].astype(float)
                df["high"]=df["h"].astype(float)
                df["low"]=df["l"].astype(float)
                df["open"]=df["o"].astype(float)
                df["RSI"]=calc_rsi(df["close"])
                df["EMA50"]=calc_ema(df["close"],50)
                df["EMA200"]=calc_ema(df["close"],200)
                return df
    except Exception as e:
        print(f"fetch error {e}")
        return None

def detect_signal(df):
    if df is None or len(df)<60:
        return {"type":"ERROR","conf":0,"range_low":0,"range_high":0,"price":0,"rsi":0,"is_skip":True}
    close=df["close"].iloc[-1]; rsi=df["RSI"].iloc[-1]
    recent=df.tail(30); range_low=recent["low"].min(); range_high=recent["high"].max()
    if close>range_high*1.001:
        conf=calc_confidence(df,"BOS")
        return {"type":"BUY BOS","conf":conf,"range_low":range_low,"range_high":range_high,"price":close,"rsi":rsi}
    if close<range_low*0.999:
        conf=calc_confidence(df,"BOS")
        return {"type":"SELL BOS","conf":conf,"range_low":range_low,"range_high":range_high,"price":close,"rsi":rsi}
    dist_high=(range_high-close)/close*100; dist_low=(close-range_low)/close*100
    if dist_high<0.4 and df["RSI"].iloc[-1]>df["RSI"].iloc[-5]:
        conf=calc_confidence(df,"TL BREAK")
        if conf>=65: return {"type":"BUY TL BREAK","conf":conf,"range_low":range_low,"range_high":range_high,"price":close,"rsi":rsi}
    if dist_low<0.4 and df["RSI"].iloc[-1]<df["RSI"].iloc[-5]:
        conf=calc_confidence(df,"TL BREAK")
        if conf>=65: return {"type":"SELL TL BREAK","conf":conf,"range_low":range_low,"range_high":range_high,"price":close,"rsi":rsi}
    return {"type":f"Waiting BOS/TL: Range {int(range_low)}-{int(range_high)} RSI {int(rsi)}","conf":0,"range_low":range_low,"range_high":range_high,"price":close,"rsi":rsi,"is_skip":True}

def make_chart(df, name, sig):
    plt.figure(figsize=(6,3), facecolor='#1e1e2f'); ax=plt.gca(); ax.set_facecolor('#1e1e2f')
    plt.plot(df["close"].tail(70).values, color='white', linewidth=1.2)
    plt.plot(df["EMA50"].tail(70).values, color='#f0b429', linestyle='--', linewidth=0.8, alpha=0.7)
    plt.title(f"{VERSION} {sig['type'][:25]} {sig['conf']}% RSI {int(sig['rsi'])}", color='white', fontsize=7)
    plt.tick_params(colors='gray'); buf=BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', facecolor='#1e1e2f'); buf.seek(0); plt.close(); return buf

telegram_app=None; last_signal={"BTC":"SKIP","GOLD":"SKIP"}

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    USERS.add(update.effective_chat.id); save_users()
    await update.message.reply_text(f"✅ {VERSION} Activated! Auto 15min ON (65% threshold). Use /signal ALL")

async def signal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    USERS.add(update.effective_chat.id); save_users()
    target=(context.args[0].upper() if context.args else "ALL")
    await update.message.reply_text(f"🔍 {VERSION} scanning {target} via OKX...")
    syms=[]
    if target in ["BTC","ALL"]: syms.append(("BTC","BTC-USDT"))
    if target in ["GOLD","XAU","ALL"]: syms.append(("GOLD","PAXG-USDT"))
    for name, oid in syms:
        df=await fetch_okx(oid,"15m",100)
        if df is None: df=await fetch_okx("BTC-USDT","15m",100)
        sig=detect_signal(df); chart=make_chart(df,name,sig)
        if sig.get("is_skip"):
            text=f"⏳ {name} {sig['type']}\nPrice {sig['price']:,.2f} RSI {int(sig['rsi'])}"
        else:
            entry=sig['price']; sl=sig['range_low']*0.998 if "BUY" in sig['type'] else sig['range_high']*1.002
            tp1=entry+(entry-sl)*1.5 if "BUY" in sig['type'] else entry-(sl-entry)*1.5
            tp2=entry+(entry-sl)*3 if "BUY" in sig['type'] else entry-(sl-entry)*3
            text=f"🚨 {name} {VERSION} {sig['type']} {sig['conf']}%!\nEntry {entry:,.2f} SL {sl:,.2f} TP1 {tp1:,.2f} TP2 {tp2:,.2f}\nRSI {int(sig['rsi'])} SMART"
        await update.message.reply_photo(photo=chart,caption=text)
        last_signal[name]="SKIP" if sig.get("is_skip") else sig['type']

async def auto_loop():
    await asyncio.sleep(20)
    while True:
        try:
            if not USERS: await asyncio.sleep(60); continue
            for name, oid in [("BTC","BTC-USDT"),("GOLD","PAXG-USDT")]:
                df=await fetch_okx(oid,"15m",100)
                if df is None: continue
                sig=detect_signal(df)
                if not sig.get("is_skip") and sig['conf']>=65:
                    if last_signal.get(name,"SKIP")=="SKIP" or "Waiting" in last_signal.get(name,""):
                        chart=make_chart(df,name,sig); entry=sig['price']
                        sl=sig['range_low']*0.998 if "BUY" in sig['type'] else sig['range_high']*1.002
                        tp1=entry+(entry-sl)*1.5 if "BUY" in sig['type'] else entry-(sl-entry)*1.5
                        caption=f"🚨 AUTO {name} {sig['type']} {sig['conf']}% TL BREAK! Entry {entry:,.2f} SL {sl:,.2f} TP1 {tp1:,.2f}\nSMART BEAST"
                        for uid in list(USERS):
                            try: await telegram_app.bot.send_photo(chat_id=uid, photo=chart, caption=caption)
                            except: pass
                        last_signal[name]=sig['type']
                else:
                    if sig.get("is_skip"): last_signal[name]="SKIP"
        except Exception as e: print(f"auto error {e}")
        await asyncio.sleep(900)

def run_flask(): flask_app.run(host='0.0.0.0', port=PORT)

async def main():
    global telegram_app; threading.Thread(target=run_flask, daemon=True).start()
    telegram_app=Application.builder().token(TOKEN).build()
    telegram_app.add_handler(CommandHandler("start", start_cmd))
    telegram_app.add_handler(CommandHandler("signal", signal_cmd))
    asyncio.create_task(auto_loop()); await telegram_app.initialize()
    await telegram_app.start(); await telegram_app.updater.start_polling()
    print(f"{VERSION} started")
    while True: await asyncio.sleep(3600)

if __name__=="__main__": asyncio.run(main())
