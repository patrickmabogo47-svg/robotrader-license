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

SYMBOLS = {"EURUSD":"EURUSD=X", "GOLD":"GC=F", "BTC":"BTC-USD"}

def rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def get_analysis(ticker):
    try:
        # Fix: handle new yfinance format
        df = yf.download(ticker, period="5d", interval="1h", progress=False, auto_adjust=True)
        if df.empty or len(df) < 20:
            print(f"{ticker} empty")
            return None, None
        # Fix for MultiIndex columns in new yfinance
        if isinstance(df.columns, pd.MultiIndex):
            close = df['Close'].iloc[:,0] if 'Close' in df.columns.get_level_values(0) else df.iloc[:,3]
        else:
            close = df['Close']

        close = close.dropna()
        if len(close) < 20:
            return None, None

        last = float(close.iloc[-1])
        ema9 = float(close.ewm(span=9).mean().iloc[-1])
        ema21 = float(close.ewm(span=21).mean().iloc[-1])
        rsi_val = float(rsi(close).iloc[-1])

        if ema9 > ema21 and rsi_val > 52:
            signal = "🟢 BUY ⬆️"
            sl = last * 0.997
            tp = last * 1.005
        elif ema9 < ema21 and rsi_val < 48:
            signal = "🔴 SELL ⬇️"
            sl = last * 1.003
            tp = last * 0.995
        elif ema9 > ema21:
            signal = "🟡 WEAK BUY ⬆️"
            sl = last * 0.998
            tp = last * 1.002
        else:
            signal = "🟡 WEAK SELL ⬇️"
            sl = last * 1.002
            tp = last * 0.998

        plt.figure(figsize=(6,3))
        plt.plot(close.tail(60))
        plt.plot(close.ewm(span=9).mean().tail(60), label='EMA9')
        plt.plot(close.ewm(span=21).mean().tail(60), label='EMA21')
        plt.title(f"{ticker} RSI:{rsi_val:.1f}")
        plt.legend(fontsize=8)
        plt.grid(True)
        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=100)
        plt.close()
        buf.seek(0)
        return (last, signal, rsi_val, ema9, ema21, sl, tp), buf
    except Exception as e:
        print(f"ERROR {ticker}: {e}")
        import traceback; traceback.print_exc()
        return None, None

@app.route('/')
def home(): return "V5.1 Fixed"

@bot.message_handler(commands=['start'])
def start(m):
    bot.reply_to(m, "🤖 V5.1 FIXED LIVE!\n\nTry:\n/signal EURUSD\n/signal GOLD\n/signal BTC\n/signal ALL")

@bot.message_handler(commands=['signal'])
def signal_cmd(m):
    args = m.text.split()
    target = args[1].upper() if len(args)>1 else "ALL"
    to_scan = list(SYMBOLS.keys()) if target=="ALL" else [target] if target in SYMBOLS else list(SYMBOLS.keys())
    bot.send_message(m.chat.id, f"📊 Analyzing {', '.join(to_scan)}... ⏳")

    for name in to_scan:
        data, chart = get_analysis(SYMBOLS[name])
        if not data:
            bot.send_message(m.chat.id, f"⚠️ {name}: Yahoo blocking, retry in 30s - trying again...")
            time.sleep(2)
            data, chart = get_analysis(SYMBOLS[name])
            if not data:
                bot.send_message(m.chat.id, f"❌ {name}: Data error, Yahoo busy. Try /signal {name} again in 1 min")
                continue
        last, sig, rsi_v, e9, e21, sl, tp = data
        msg = f"{sig}\n\n📈 {name}\n💰 {last:.2f}\nRSI: {rsi_v:.1f} | EMA9:{e9:.2f} EMA21:{e21:.2f}\n\n🎯 TP: {tp:.2f}\n🛑 SL: {sl:.2f}\n⏰ 1h TF - V5.1"
        bot.send_photo(m.chat.id, chart, caption=msg)
        time.sleep(1)

def run_flask(): app.run(host='0.0.0.0', port=10000)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    while True:
        try: bot.infinity_polling(timeout=60)
        except Exception as e:
            print(f"Poll error {e}"); time.sleep(5)
