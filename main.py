import os, asyncio
from fastapi import FastAPI
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

app = FastAPI()
@app.get("/")
def home():
    return {"status": "Live", "bot": "@Robotradersabot"}
@app.get("/license/{key}")
def license_check(key: str):
    return {"valid": True}

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Bot ONLINE! GOLD BUY 2719.70 SL 2709.70 TP 2739.70 /signal")
async def signal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔥 GOLD BUY @2719.70 SL 2709 TP 2739")

async def run_bot():
    if not BOT_TOKEN:
        print("ERROR: No TELEGRAM_BOT_TOKEN!")
        return
    print(f"BOT TOKEN FOUND {BOT_TOKEN[:10]}")
    while True:
        try:
            application = ApplicationBuilder().token(BOT_TOKEN).build()
            application.add_handler(CommandHandler("start", start))
            application.add_handler(CommandHandler("signal", signal))
            print("Bot started polling...")
            await application.initialize()
            await application.start()
            await application.updater.start_polling(drop_pending_updates=True)
            while True:
                await asyncio.sleep(3600)
        except Exception as e:
            print(f"Bot crashed: {e} - retry in 5s")
            await asyncio.sleep(5)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(run_bot())
    print("Startup event: bot task created")
