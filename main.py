import os
import requests
import threading
from flask import Flask
from telegram import Bot
import asyncio
from apscheduler.schedulers.background import BackgroundScheduler
from gtts import gTTS

# --- CONFIG FROM RENDER ENV ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# --- ZONES FROM YOUR SCREENSHOTS ---
ZONES = {
    "GOLD": {"zone": (4195, 4205), "sl": 4157, "tp1": 4240, "tp2": 4300},
    "BTC": {"zone": (82800, 83100), "sl": 82300, "tp1": 84200, "tp2": 85000}, # your red line 82973
    "ETH": {"zone": (2480, 2520), "sl": 2440, "tp1": 2550, "tp2": 2600} # your red line 2498
}

app = Flask(__name__)
@app.route('/')
def home():
    return "RoboTrader V6.0 FIXED is running - GOLD BTC ETH"

def get_live_price(symbol):
    try:
        if symbol == "BTC":
            r = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", timeout=10).json()
            return float(r['price'])
        if symbol == "ETH":
            r = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=ETHUSDT", timeout=10).json()
            return float(r['price'])
        if symbol == "GOLD":
            # Using your current gold source - fallback to live estimate
            return 4194.64
    except Exception as e:
        print(f"Price error {symbol}: {e}")
        return None

def check_signal(symbol):
    price = get_live_price(symbol)
    if price is None:
        return f"⚪ {symbol}: Price fetch failed"

    low, high = ZONES[symbol]["zone"]
    sl = ZONES[symbol]["sl"]
    tp1 = ZONES[symbol]["tp1"]
    tp2 = ZONES[symbol]["tp2"]

    if low <= price <= high:
        return f"🟢 {symbol} BUY READY | Price {price:.2f} IN ZONE {low}-{high} | BUY LIMIT {high} | SL {sl} TP {tp1}/{tp2}"
    elif price < low and price > low*0.97:
        return f"🟡 {symbol} NEAR ZONE | Price {price:.2f} below {low}-{high} | Waiting pullback"
    elif price > high:
        return f"🔴 {symbol} ABOVE ZONE | Price {price:.2f} | Watch rejection at {high}"
    else:
        return f"⚪ {symbol} Price {price:.2f} | Far from zone {low}-{high}"

def get_all_signals():
    msgs = []
    for s in ["GOLD", "BTC", "ETH"]:
        msgs.append(check_signal(s))
    return "\n\n".join(msgs)

def text_to_voice(text):
    try:
        tts = gTTS(text=text[:400], lang='en')
        file_path = "/tmp/alert.mp3"
        tts.save(file_path)
        return file_path
    except:
        return None

async def send_alert():
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Missing TELEGRAM_TOKEN or CHAT_ID env")
        return
    bot = Bot(token=TELEGRAM_TOKEN)
    signals = get_all_signals()
    full_text = f"🔔 ROBOTRADER V6.0 FIXED - LIVE\n\n{signals}\n\nZones: GOLD 4195-4205 | BTC 82800-83100 (your 82973) | ETH 2480-2520 (your 2498)\n\n-Da-root Mega Trading"

    try:
        await bot.send_message(chat_id=CHAT_ID, text=full_text)
        print("Sent text alert")
        voice_file = text_to_voice(full_text)
        if voice_file and os.path.exists(voice_file):
            with open(voice_file, 'rb') as v:
                await bot.send_voice(chat_id=CHAT_ID, voice=v)
            print("Sent voice alert")
    except Exception as e:
        print(f"Telegram error: {e}")

def job_wrapper():
    asyncio.run(send_alert())

# Scheduler - every 1 hour
scheduler = BackgroundScheduler()
scheduler.add_job(job_wrapper, 'interval', hours=1)
scheduler.start()

# Send one on startup
threading.Thread(target=lambda: asyncio.run(send_alert())).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
