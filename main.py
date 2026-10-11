import os, time, requests, yfinance as yf
from flask import Flask
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime

app = Flask(__name__)

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def send_telegram(text):
    if not TOKEN or not CHAT_ID:
        print("NO TOKEN/CHAT", flush=True)
        return False
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}, timeout=15)
        print(f"Telegram status {r.status_code} {r.text[:200]}", flush=True)
        return r.status_code == 200
    except Exception as e:
        print(f"Telegram FAIL {e}", flush=True)
        return False

def get_data(ticker, period="2d", interval="30m"):
    try:
        # Anti-429: fake Chrome browser
        from curl_cffi import requests as c_req
        session = c_req.Session(impersonate="chrome110")
        tk = yf.Ticker(ticker, session=session)
        df = tk.history(period=period, interval=interval, auto_adjust=True)
        if df.empty:
            print(f"EMPTY {ticker}", flush=True)
            return None
        print(f"DATA OK {ticker} rows={len(df)}", flush=True)
        return df
    except Exception as e:
        print(f"DATA FAIL {ticker}: {e}", flush=True)
        return None

def make_signal(df):
    if df is None or len(df) < 50:
        return None
    # your existing RSI/MACD logic here - keep what you had
    # simplified example:
    close = df['Close'].iloc[-1]
    return f"Price ${close:.2f}"

def job_60():
    print("60min run START", flush=True)
    try:
        gold = get_data("GC=F", "2d", "60m")
        btc = get_data("BTC-USD", "2d", "60m")
        msg = f"⏰ 60MIN CHECK {datetime.now().strftime('%H:%M')}\n"
        if gold is not None: msg += f"GOLD: {make_signal(gold)}\n"
        if btc is not None: msg += f"BTC: {make_signal(btc)}\n"
        if gold is None and btc is None:
            msg += "Yahoo blocked (429) - retrying next hour"
        send_telegram(msg)
    except Exception as e:
        print(f"job_60 FAIL {e}", flush=True)
    print("60min run END", flush=True)

def job_30():
    print("30min run START", flush=True)
    try:
        gold = get_data("GC=F", "2d", "30m")
        btc = get_data("BTC-USD", "2d", "30m")
        msg = f"⏰ 30MIN CHECK {datetime.now().strftime('%H:%M')}\n"
        if gold is not None: msg += f"GOLD: {make_signal(gold)}\n"
        if btc is not None: msg += f"BTC: {make_signal(btc)}\n"
        send_telegram(msg)
    except Exception as e:
        print(f"job_30 FAIL {e}", flush=True)
    print("30min run END", flush=True)

@app.route("/")
def home():
    return "ROBOTRADER V7.1 Live - Anti 429 Fix"

@app.route("/send-test")
def send_test():
    print("TEST HIT", flush=True)
    send_telegram("✅ TEST OK - Bot is working! V7.1 anti-429")
    job_60()
    job_30()
    return "Test sent - check Telegram now - check Logs for Sent"

@app.route("/test-telegram")
def test_telegram():
    ok = send_telegram("🔔 PURE TELEGRAM TEST - If you see this, token/chat is OK")
    return f"Telegram test sent: {ok}"

# Scheduler
sched = BackgroundScheduler()
sched.add_job(job_60, 'cron', minute=0)  # every hour at :00
sched.add_job(job_30, 'cron', minute=30) # every hour at :30
sched.start()

print("////////////////////////////////", flush=True)
print("ROBOTRADER V7.1 STARTED", flush=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
