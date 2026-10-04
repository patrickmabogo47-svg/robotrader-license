import os
from fastapi import FastAPI
import threading
from telegram.ext import Updater, CommandHandler

app = FastAPI()

@app.get("/")
def home():
    return {"status": "Robot Trader SA - Live", "bot": "@Robotradersabot"}

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

def start(update, context):
    update.message.reply_text("✅ Bot is ONLINE!\n\nAccount: 161748707\n\nGOLD BUY 2719.70\nSL 2709.70\nTP 2739.70\n\nType /signal")

def signal(update, context):
    update.message.reply_text("🔥 REAL SIGNAL (H1)\nXAUUSD BUY @ 2719.70\nSL 2709.70\nTP 2739.70\nConfidence 67%")

def run_bot():
    if not BOT_TOKEN:
        print("No token")
        return
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("signal", signal))
    print("Bot started polling...")
    updater.start_polling()
    updater.idle()

threading.Thread(target=run_bot, daemon=True).start()
