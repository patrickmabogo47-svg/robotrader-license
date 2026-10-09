import threading, time, io, telebot, os
from flask import Flask
import yfinance as yf
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from gtts import gTTS

TOKEN = "8833864287:AAE3sJH5rvSXfhLrmMhj_1o1wT4776X_EMI"
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)
SYMBOLS = {"EURUSD":"EURUSD=X", "GOLD":"GC=F", "BTC":"BTC-USD"}
ALERT_CHATS = set()

def rsi(s, p=14):
    d = s.diff(); g = d.where(d>0,0).rolling(p).mean(); l = -d.where(d<0,0).rolling(p).mean()
    return 100 - (100/(1+g/l))

def get_power_analysis(ticker):
    try:
        df1 = yf.download(ticker, period="10d", interval="1h", progress=False, auto_adjust=True)
        df4 = yf.download(ticker, period="20d", interval="4h", progress=False, auto_adjust=True)
        if df1.empty or len(df1)<60: return None, None, "Data wait", False
        def clean(df):
            if isinstance(df.columns, pd.MultiIndex):
                c = df['Close'].iloc[:,0] if 'Close' in df.columns.get_level_values(0) else df.iloc[:,3]
            else:
                c = df['Close']
            return c.dropna()
        close1 = clean(df1); close4 = clean(df4)
        last = float(close1.iloc[-1])
        ema9 = float(close1.ewm(9).mean().iloc[-1]); ema21 = float(close1.ewm(21).mean().iloc[-1]); ema50 = float(close1.ewm(50).mean().iloc[-1])
        r = float(rsi(close1).iloc[-1])
        exp12 = close1.ewm(12).mean(); exp26 = close1.ewm(26).mean(); macd = exp12-exp26; sig = macd.ewm(9).mean()
        macd_last = float(macd.iloc[-1]); sig_last = float(sig.iloc[-1])
        ema21_4 = float(close4.ewm(21).mean().iloc[-1]); last4 = float(close4.iloc[-1])
        htf_up = last4 > ema21_4; htf_down = last4 < ema21_4
        score = 0; reasons = []
        if ema9 > ema21 > ema50: score+=1; reasons.append("✅ EMA Bull Stack")
        elif ema9 < ema21 < ema50: score-=1; reasons.append("✅ EMA Bear Stack")
        else: reasons.append("❌ EMA Mixed")
        if r < 30 or r > 70: return None, None, f"⛔ {ticker} BLOCKED RSI {r:.1f} Extreme", False
        if macd_last > sig_last and score>0: score+=1; reasons.append("✅ MACD Bull")
        elif macd_last < sig_last and score<0: score-=1; reasons.append("✅ MACD Bear")
        else: reasons.append("❌ MACD No Confirm")
        if (score>0 and htf_up) or (score<0 and htf_down): score+=1 if score>0 else -1; reasons.append(f"✅ 4H { 'UP' if htf_up else 'DOWN'}")
        else: reasons.append("❌ 4H Opposite")
        is_sniper = False
        if score >= 2.5:
            signal = f"🟢🟢🟢 SNIPER BUY ⬆️ Score {score}"; sl=last*0.988; tp=last*1.022; is_sniper=True
        elif score <= -2.5:
            signal = f"🔴🔴🔴 SNIPER SELL ⬇️ Score {score}"; sl=last*1.012; tp=last*0.978; is_sniper=True
        else:
            return None, None, f"⚪️ {ticker} NO TRADE Score {score}\n" + "\n".join(reasons), False
        plt.figure(figsize=(7,3.5))
        plt.plot(close1.tail(80), label='Price', linewidth=1.5)
        plt.plot(close1.ewm(9).mean().tail(80), label='EMA9'); plt.plot(close1.ewm(21).mean().tail(80), label='EMA21'); plt.plot(close1.ewm(50).mean().tail(80), label='EMA50')
        plt.title(f"{ticker} SNIPER RSI:{r:.1f}"); plt.legend(fontsize=7); plt.grid(True, alpha=0.3); plt.tight_layout()
        buf = io.BytesIO(); plt.savefig(buf, format='png', dpi=120); plt.close(); buf.seek(0)
        details = "\n".join(reasons)
        return (last, signal, r, ema9, ema21, sl, tp, details), buf, None, is_sniper
    except Exception as e:
        return None, None, f"Error {e}", False

def send_auto_scan():
    for cid in list(ALERT_CHATS):
        found = []
        for name in SYMBOLS.keys():
            data, chart, err, is_sniper = get_power_analysis(SYMBOLS[name])
            if not is_sniper or not data: continue
            found.append(name)
            last, sigtxt, rsi_v, e9, e21, sl, tp, details = data
            msg = f"🔔 AUTO SNIPER ALERT!\n\n{sigtxt}\n\n📈 {name} ${last:.2f}\nRSI:{rsi_v:.1f}\n{details}\n\n🎯 TP:{tp:.2f}\n🛑 SL:{sl:.2f}"
            try:
                bot.send_photo(cid, chart, caption=msg)
                # Voice
                try:
                    vt = f"{name} Sniper {'Buy' if 'BUY' in sigtxt else 'Sell'} at {last:.0f}, Score 3"
                    tts = gTTS(vt, lang='en'); fp=f"/tmp/{name}.mp3"; tts.save(fp)
                    with open(fp,'rb') as v: bot.send_voice(cid, v, caption=f"🎙️ {name}")
                    os.remove(fp)
                except: pass
            except: pass
            time.sleep(1)
        if not found:
            print(f"Auto scan {cid}: No sniper setup - silent")

def auto_loop():
    while True:
        time.sleep(1800) # 30 min
        if not ALERT_CHATS: continue
        print("Auto scanning...")
        send_auto_scan()

@app.route('/')
def home(): return "V6.1 Auto Sniper Live"

@bot.message_handler(commands=['start'])
def start(m):
