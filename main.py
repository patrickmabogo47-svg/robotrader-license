import threading, time, io, telebot
from flask import Flask
import yfinance as yf
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

TOKEN = "8833864287:AAE3sJH5rvSXfhLrmMhj_1o1wT4776X_EMI"
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

SYMBOLS = {
    "EURUSD": "EURUSD=X",
    "GOLD": "GC=F",
    "BTC": "BTC-USD"
}

def get_analysis(ticker):
    try:
        df = yf.download(ticker, period="2d", interval="15m", progress=False)
        if len(df) < 20: return None, None
        close = df['Close']
        sma20 = close.rolling(20).mean().iloc[-1]
        last = close.iloc[-1]
        prev = close.iloc[-2]
        trend = "BUY ⬆️" if last > sma20 else "SELL ⬇️"
        change = ((last-prev)/prev)*100

        # Chart
        plt.figure(figsize=(6,3))
        plt.plot(close.tail(50))
        plt.title(f"{ticker} 15m")
        plt.grid(True)
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        plt.close()
        buf.seek(0)
        return (last, sma20, trend, change), buf
    except Exception as e:
        print(f"Error {ticker}: {e}")
        return None, None

@app.route('/')
def home(): return "Bot V4.9 PRO - EUR GOLD BTC"

@bot.message_handler(commands=['start'])
def start(m):
    bot.reply_to(m, "🤖 RoboTrader SA V4.9 PRO LIVE!\n\n✅ EURUSD\n✅ GOLD (XAU)\n✅ BTC-USD\n\nUse:\n/signal ALL - All 3 with charts\n/signal EURUSD\n/signal GOLD\n/signal BTC")

@bot.message_handler(commands=['status'])
def status(m):
    bot.reply_to(m, "🟢 V4.9 PRO Online\n📡 Charts: Enabled\n📊 Assets: EURUSD, GOLD, BTC")

@bot.message_handler(commands=['signal'])
def signal(m):
    args = m.text.split()
    target = args[1].upper() if len(args)>1 else "ALL"

    to_scan = SYMBOLS.keys() if target=="ALL" else [target] if target in SYMBOLS else SYMBOLS.keys()

    bot.send_message(m.chat.id, f"📊 Analyzing {', '.join(to_scan)}... ⏳")

    for name in to_scan:
        data, chart = get_analysis(SYMBOLS[name])
        if not data:
            bot.send_message(m.chat.id, f"❌ {name}: Data error, try again")
            continue
        last, sma20, trend, change = data
        msg = f"📈 {name} SIGNAL\nPrice: {last:.2f}\nTrend (SMA20): {trend}\nChange: {change:+.2f}%\n\nSL: {last*0.998:.2f} | TP: {last*1.002:.2f}\n⏰ 15m - V4.9"
        if chart:
            bot.send_photo(m.chat.id, chart, caption=msg)
        else:
            bot.send_message(m.chat.id, msg)
        time.sleep(1)

def run_flask(): app.run(host='0.0.0.0', port=10000)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    print("Flask + V4.9 Bot polling...")
    while True:
        try: bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except: time.sleep(5)
