import os, time, threading, requests, mplfinance as mpf
import yfinance as yf
import pandas as pd
from flask import Flask
from datetime import datetime

app = Flask(__name__)
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT = os.getenv("TELEGRAM_CHAT_ID")

def send_tg(text, chart_path=None):
    try:
        if chart_path:
            with open(chart_path,'rb') as f:
                requests.post(f"https://api.telegram.org/bot{TOKEN}/sendPhoto",
                    data={"chat_id":CHAT,"caption":text}, files={"photo":f}, timeout=15)
        else:
            requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                data={"chat_id":CHAT,"text":text}, timeout=10)
        return True
    except: return False

def fetch_yf(symbol_list):
    for sym in symbol_list:
        try:
            df = yf.download(sym, period="5d", interval="1h", progress=False)
            if len(df) > 50:
                return df, sym
        except: continue
    return None, None

def analyze(symbol_name, symbols):
    df, used = fetch_yf(symbols)
    if df is None: return f"{symbol_name}: data fail ({used})"
    close = df['Close']
    delta = close.diff()
    gain = delta.where(delta>0,0).rolling(14).mean()
    loss = -delta.where(delta<0,0).rolling(14).mean()
    rs = gain/loss
    rsi = 100-(100/(1+rs))
    r = float(rsi.iloc[-1])
    price = float(close.iloc[-1])
    ema = float(close.ewm(span=20).mean().iloc[-1])

    score=0
    if r < 35: score+=1
    if r > 65: score-=1
    if price > ema: score+=1
    else: score-=1
    if abs(price-ema)/price < 0.01: score+=1

    if score >=3:
        sig = f"🎯 SNIPER BUY {symbol_name} ${price:.2f} RSI {r:.1f} Score {score}"
        # chart
        try:
            df.tail(100).plot(type='candle', style='yahoo')
            mpf.plot(df.tail(100), type='candle', savefig='chart.png')
            send_tg(sig,'chart.png')
        except:
            send_tg(sig)
        return f"{symbol_name}: ${price:.2f} RSI {r:.1f} Score {score} - {sig}"
    elif score <=-3:
        sig = f"🎯 SNIPER SELL {symbol_name} ${price:.2f} RSI {r:.1f} Score {score}"
        send_tg(sig)
        return f"{symbol_name}: ${price:.2f} RSI {r:.1f} Score {score} - {sig}"
    elif score >=2:
        return f"{symbol_name}: ${price:.2f} RSI {r:.1f} Score {score} - ⚠️ WEAK BUY - No Telegram"
    elif score <=-2:
        return f"{symbol_name}: ${price:.2f} RSI {r:.1f} Score {score} - ⚠️ WEAK SELL - No Telegram"
    else:
        return f"{symbol_name}: ${price:.2f} RSI {r:.1f} Score {score} - No trade"

def full_scan():
    gold = analyze("GOLD", ["GC=F","XAUUSD=X","PAXG-USD","GLD"])
    eurusd = analyze("EURUSD", ["EURUSD=X"])
    btc = analyze("BTC", ["BTC-USD"])
    return f"{gold}\n{eurusd}\n{btc}\n\n{datetime.utcnow()} UTC"

@app.route("/")
def home(): return "V6.1 SMART LIVE - "+full_scan().replace("\n","<br>")

@app.route("/signal")
def signal(): return full_scan().replace("\n","<br>")

@app.route("/test-telegram")
def testtg():
    ok = send_tg("🔔 PURE TELEGRAM TEST - V6.1 SMART BUY/SELL is OK, auto running")
    return f"Telegram test sent: {ok}"

def loop():
    while True:
        try: full_scan()
        except: pass
        time.sleep(1800) # 30min

threading.Thread(target=loop, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))
