import os, time, threading, requests, mplfinance as mpf
import yfinance as yf
from flask import Flask
from datetime import datetime

app = Flask(__name__)
TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
CHAT = os.getenv("TELEGRAM_CHAT_ID") or os.getenv("CHAT_ID")

def send_tg(text, chart=None):
    try:
        if chart and os.path.exists(chart):
            with open(chart,'rb') as f:
                requests.post(f"https://api.telegram.org/bot{TOKEN}/sendPhoto",
                    data={"chat_id":CHAT,"caption":text}, files={"photo":f}, timeout=20)
        else:
            requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",
                data={"chat_id":CHAT,"text":text}, timeout=10)
        return True
    except Exception as e:
        print(f"TG error {e}"); return False

# GOLD FALLBACK - never disappears
GOLD_SYMBOLS = ["GC=F","XAUUSD=X","PAXG-USD","GLD","XAU/USD"]

def get_data(symbols):
    for sym in symbols:
        try:
            df = yf.download(sym, period="10d", interval="1h", progress=False, auto_adjust=True)
            if df is not None and len(df) > 50:
                return df, sym
        except: continue
    return None, "none"

def analyze_pair(name, symbols):
    df, used = get_data(symbols)
    if df is None:
        return f"{name}: data fail ({used}) - retrying"
    try:
        close = df['Close']
        if hasattr(close, 'iloc'): close = close.squeeze()
        delta = close.diff()
        gain = delta.where(delta>0,0).rolling(14).mean()
        loss = -delta.where(delta<0,0).rolling(14).mean()
        rsi = 100 - (100 / (1 + gain/loss))
        r = float(rsi.iloc[-1])
        price = float(close.iloc[-1])
        ema20 = float(close.ewm(span=20).mean().iloc[-1])

        # V6.0 SCORE LOGIC
        score = 0
        if r < 35: score += 1.5
        elif r < 45: score += 1
        if r > 65: score -= 1.5
        elif r > 55: score -= 1
        if price > ema20: score += 1
        else: score -= 1
        if abs(price-ema20)/price < 0.008: score += 0.5

        # DISPLAY ALWAYS BUY/SELL - V6.0 SMART SEND ONLY SCORE 3
        base = f"{name}: ${price:.2f} RSI {r:.1f} Score {score}"
        
        if score >= 3:
            sig = f"🎯 SNIPER BUY {name} ${price:.2f} RSI {r:.1f} Score {score} ({used})"
            try:
                mpf.plot(df.tail(80), type='candle', style='yahoo', savefig='chart.png')
                send_tg(sig,'chart.png')
            except: send_tg(sig)
            return f"{base} - {sig}"
        elif score <= -3:
            sig = f"🎯 SNIPER SELL {name} ${price:.2f} RSI {r:.1f} Score {score} ({used})"
            send_tg(sig)
            return f"{base} - {sig}"
        elif score >= 2:
            return f"{base} - ⚠️ WEAK BUY (page only)"
        elif score <= -2:
            return f"{base} - ⚠️ WEAK SELL (page only)"
        elif score > 0:
            return f"{base} - → BUY bias"
        elif score < 0:
            return f"{base} - → SELL bias"
        else:
            return f"{base} - No trade"
    except Exception as e:
        return f"{name}: calc error {e}"

def full_scan():
    g = analyze_pair("GOLD", GOLD_SYMBOLS)
    e = analyze_pair("EURUSD", ["EURUSD=X"])
    b = analyze_pair("BTC", ["BTC-USD"])
    return f"{g}\n{e}\n{b}\n\n{datetime.utcnow().strftime('%H:%M UTC')}"

@app.route("/")
def home(): return f"V6.0 ULTIMATE LIVE<br><br>{full_scan().replace(chr(10),'<br>')}"

@app.route("/signal")
def signal(): return full_scan().replace("\n","<br>")

@app.route("/test-telegram")
def testtg():
    ok = send_tg("🔔 V6.0 ULTIMATE TEST - BUY/SELL signals working, auto running")
    return f"Telegram test sent: {ok}"

def loop():
    while True:
        try: full_scan()
        except: pass
        time.sleep(1800)

threading.Thread(target=loop, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))
