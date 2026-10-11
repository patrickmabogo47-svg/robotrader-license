import os, time
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
        r = requests.post(url, data={"chat_id": CHAT_ID, "text": text}, timeout=15)
        print(f"Telegram status {r.status_code}")
    except Exception as e:
        print(f"Telegram err {e}")

def get_rsi(symbol):
    for attempt in range(3): # 3 tries for 429
        try:
            time.sleep(2) # anti-429 delay
            df = yf.download(symbol, period="2d", interval="1h", progress=False, auto_adjust=True)
            if df.empty:
                print(f"{symbol} empty attempt {attempt}")
                time.sleep(3)
                continue
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            close = df['Close']
            if len(close) < 20:
                continue
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
            print(f"{symbol} OK ${price:.2f} RSI {rsi_val:.1f}")
            return price, rsi_val, score, ema9>ema21>ema50
        except Exception as e:
            print(f"{symbol} attempt {attempt} err {e}")
            time.sleep(5)
    print(f"{symbol} FAILED after 3 attempts")
    return None

def job_30():
    print("30min run START")
    for name, sym in SYMBOLS.items():
        try:
            res = get_rsi(sym)
            if not res: continue
            price, rsi, score, ema_bull = res
            if score < 2: continue
            tp = price*1.022
            sl = price*0.987
            text = f"🔔 30MIN SNIPER ALERT!\n\n🟢 SNIPER BUY Score {score}\n\n📈 {name} ${price:.2f}\nRSI:{rsi:.1f}\n{'✅ EMA Bull' if ema_bull else '❌ EMA'}\n\n🎯 TP:{tp:.2f}\n🛑 SL:{sl:.2f}\n14-Day: Risk 1%"
            send(text)
        except Exception as e:
            print(f"{name} skip {e}")
            continue
    print("30min run END")

def job_60():
    print("60min run START")
    msg = "⏰ HOURLY MARKET SUMMARY (1h)\n\n"
    ok = 0
    for name, sym in SYMBOLS.items():
        res = get_rsi(sym)
        if res:
            price, rsi, _, _ = res
            msg += f"{name} ${price:.2f} | RSI {rsi:.1f}\n"
            ok+=1
    if ok==0:
        msg += "Yahoo 429 rate-limit - will retry next cycle\n"
    msg += "\nSniper every 30min - 14 Day Plan"
    send(msg)
    print("60min run END")

sched = BackgroundScheduler()
sched.add_job(job_30, 'interval', minutes=30)
sched.add_job(job_60, 'interval', minutes=60)
sched.start()

@app.route('/')
def home():
    return "RoboTrader V6.0 FIXED 429 is running"

@app.route('/send-test')
def test():
    job_60()
    job_30()
    return "Test sent - check Telegram now - check Logs for Sent"

if __name__ == '__main__':
    try:
        send("🔔 ROBOTRADER V6.0 429-FIXED LIVE\nGOLD BTC ETH ready - 14 Day Plan ON")
    except: pass
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))
