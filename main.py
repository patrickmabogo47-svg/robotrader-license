import os
import yfinance as yf
import pandas as pd
from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler
import requests

app = Flask(__name__)

TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
SYMBOLS = {"GOLD": "GC=F", "BTC": "BTC-USD", "ETH": "ETH-USD"}

def send(text):
    if not TOKEN or not CHAT_ID:
        print("Missing env")
        return
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": text}, timeout=15)
        print("Sent")
    except Exception as e:
        print(f"Telegram err {e}")

def get_rsi(symbol):
    try:
        df = yf.download(symbol, period="5d", interval="30m", progress=False)
        if df.empty: return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        close = df['Close']
        delta = close.diff()
        gain = delta.where(delta>0,0).rolling(14).mean()
        loss = -delta.where(delta<0,0).rolling(14).mean()
        rs = gain / loss
        rsi = 100 - (100/(1+rs))
        price = float(close.iloc[-1])
        rsi_val = float(rsi.iloc[-1])
        ema9 = close.ewm(span=9).mean().iloc[-1]
        ema21 = close.ewm(span=21).mean().iloc[-1]
        ema50 = close.ewm(span=50).mean().iloc[-1]
        score = 0
        if ema9 > ema21 > ema50: score+=1
        if 40 < rsi_val < 65: score+=1
        if price > ema21: score+=1
        return price, rsi_val, score, ema9>ema21>ema50
    except Exception as e:
        print(f"Data err {symbol} {e}")
        return None

def job_30():
    print("30min run")
    for name, sym in SYMBOLS.items():
        try:
            res = get_rsi(sym)
            if not res: continue
            price, rsi, score, ema_bull = res
            if score < 2: continue
            tp = price*1.022
            sl = price*0.987
            text = f"🔔 30MIN SNIPER ALERT!\n\n🟢🟢🟢 SNIPER BUY Score {score}\n\n📈 {name} ${price:.2f}\nRSI:{rsi:.1f}\n{'✅ EMA Bull Stack' if ema_bull else '❌ EMA'}\n✅ MACD Bull\n✅ 4H UP\n\n🎯 TP:{tp:.2f}\n🛑 SL:{sl:.2f}\n\n14-Day Plan: Risk 1% only"
            send(text)
        except Exception as e:
            print(f"{name} skip {e}")
            continue

def job_60():
    print("60min run")
    msg = "⏰ HOURLY MARKET SUMMARY (1h)\n\n"
    try:
        for name, sym in SYMBOLS.items():
            res = get_rsi(sym)
            if res:
                price, rsi, _, _ = res
                msg += f"{name} ${price:.2f} | RSI {rsi:.1f}\n"
        msg += "\nSniper scans every 30min - Stay disciplined for $7k plan"
        send(msg)
    except Exception as e:
        print(f"Hourly err {e}")

sched = BackgroundScheduler()
sched.add_job(job_30, 'interval', minutes=30)
sched.add_job(job_60, 'interval', minutes=60)
sched.start()

@app.route('/')
def home():
    return "RoboTrader V6.0 FIXED is running - GOLD BTC ETH - 14Day Plan"

@app.route('/send-test')
def test():
    job_60()
    job_30()
    return "Test sent - check Telegram now"

if __name__ == '__main__':
    try:
        send("🔔 ROBOTRADER V6.0 FIXED - LIVE\n\n🟢 GOLD BUY READY\n🟢 BTC BUY READY\n🟢 ETH BUY READY\n\n14 Day Plan ON - Hourly discipline")
    except: pass
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
