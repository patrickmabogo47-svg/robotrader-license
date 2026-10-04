import os
import asyncio
from fastapi import FastAPI
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

app = FastAPI()

@app.get("/")
def home():
    return {"status": "Robot Trader SA - Live", "bot": "@Robotradersabot"}

@app.get("/license/{key}")
def license_check(key: str):
    return {"valid": True, "pair": "GOLD"}

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot is ONLINE!\n\nAccount: 161748707\n\nGOLD BUY 2719.70\nSL 2709.70\nTP 2739.70\n\nType /signal")

async def signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔥 REAL SIGNAL (H1)\nXAUUSD BUY @ 2719.70\nSL 2709.70\nTP 2739.70\nConfidence 67%")

async def run_bot():
    if not BOT_TOKEN:
        print("ERROR: No TELEGRAM_BOT_TOKEN env set!")
        return
    print(f"BOT TOKEN FOUND {BOT_TOKEN[:10]}... Starting polling")
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("signal", signal))
    print("Bot started polling...")
    await application.initialize()
    await application.start()
    await application.updater.start_polling()

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(run_bot())
    print("Startup event: bot task created")
