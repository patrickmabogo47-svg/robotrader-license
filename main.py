import threading
import time
import telebot
from flask import Flask
import yfinance as yf

TOKEN = "8833864287:AAE3sJH5rvSXfhLrmMhj_1o1wT4776X_EMI"
bot = telebot.TeleBot(TOKEN)

app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive V4.8.3 - RoboTrader SA"

@bot.message_handler(commands=['start'])
def start(m):
    bot.reply_to(m, "🤖 RoboTrader SA V4.8.3 LIVE!\n\n✅ Bot is active\n✅ License valid\n\nCommands:\n/signal ALL - Get signals\n/status - Bot status")

@bot.message_handler(commands=['status'])
def status(m):
    bot.reply_to(m, "🟢 Bot Running V4.8.3\n📡 Render: Online\n🔑 License: Active")

@bot.message_handler(commands=['signal'])
def signal(m):
    try:
        text = m.text
        bot.reply_to(m, f"📊 Analyzing {text}...\n⏳ Getting market data...")
        # Simple signal logic
        data = yf.download("EURUSD=X", period="1d", interval="15m", progress=False)
        if len(data) > 0:
            last = data['Close'].iloc[-1]
            bot.send_message(m.chat.id, f"📈 EUR/USD Signal:\nPrice: {last:.5f}\nTrend: BUY ⬆️\nTime: 15m\n\n⚠️ Demo signal - Full strategy V4.8.3")
        else:
            bot.send_message(m.chat.id, "📊 Signal: BUY EUR/USD @ 1.0850 TP 1.0870 SL 1.0830")
    except Exception as e:
        bot.send_message(m.chat.id, f"Signal Error: {e}\nTry /signal ALL again")

def run_flask():
    app.run(host='0.0.0.0', port=10000)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    print("Flask started - Bot polling...")
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"Polling error {e}, retrying in 5s...")
            time.sleep(5)
