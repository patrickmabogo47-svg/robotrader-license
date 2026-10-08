import threading
from flask import Flask
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is alive V4.8.3"

def run_flask():
    app.run(host='0.0.0.0', port=10000)

if __name__ == "__main__":
    # Start Flask for UptimeRobot
    threading.Thread(target=run_flask, daemon=True).start()
    print("Flask started on 10000 - Bot polling starting...")
    # Start Telegram bot polling (THIS WAS MISSING!)
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except Exception as e:
        print(f"Polling error: {e}")
        bot.infinity_polling()
