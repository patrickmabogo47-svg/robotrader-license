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
ALERT_CHATS = set()

def rsi(s, p=14):
    d = s.diff(); g = d.where(d>0,0).rolling(p).mean(); l = -d.where(d<0,0).rolling(p).mean()
    return 100 - (100/(1+g/l))

def get_power(ticker):
    try:
        df1 = yf.download(ticker, period="10d", interval="1h", progress=False, auto_adjust=True)
        df4 = yf.download(ticker, period="20d", interval="4h", progress=False, auto_adjust=True)
        if df1.empty or len(df1)<60: return None,None,"No data",False
        def clean(df):
            if isinstance(df.columns, pd.MultiIndex):
                c = df['Close'].iloc[:,0] if 'Close' in df.columns.get_level_values(0) else df.iloc[:,3]
            else: c = df['Close']
            return c.dropna()
        c1=clean(df1); c4=clean(df4)
        last=float(c1.iloc[-1]); e9=float(c1.ewm(9).mean().iloc[-1]); e21=float(c1.ewm(21).mean().iloc[-1]); e50=float(c1.ewm(50).mean().iloc[-1])
        r=float(rsi(c1).iloc[-1])
        macd=(c1.ewm(12).mean()-c1.ewm(26).mean()); sig=macd.ewm(9).mean()
        ml=float(macd.iloc[-1]); slast=float(sig.iloc[-1])
        e21_4=float(c4.ewm(21).mean().iloc[-1]); l4=float(c4.iloc[-1])
        htf_up=l4>e21_4; htf_down=l4<e21_4
        score=0; rs=[]
        if e9>e21>e50: score+=1; rs.append("✅ EMA Bull Stack")
        elif e9<e21<e50: score-=1; rs.append("✅ EMA Bear Stack")
        else: rs.append("❌ EMA Mixed - NO TRADE")
        if r<30 or r>70: return None,None,f"⛔ {ticker} BLOCKED RSI {r:.1f} Extreme",False
        if ml>slast and score>0: score+=1; rs.append("✅ MACD Bull")
        elif ml<slast and score<0: score-=1; rs.append("✅ MACD Bear")
        else: rs.append("❌ MACD No Confirm")
        if (score>0 and htf_up) or (score<0 and htf_down): score+=1 if score>0 else -1; rs.append(f"✅ 4H {'UP' if htf_up else 'DOWN'}")
        else: rs.append("❌ 4H Opposite - Weak")
        is_sniper=False
        if score>=2.5: sigt=f"🟢🟢🟢 SNIPER BUY ⬆️ Score {score}"; sl=last*0.988; tp=last*1.022; is_sniper=True
        elif score<=-2.5: sigt=f"🔴🔴🔴 SNIPER SELL ⬇️ Score {score}"; sl=last*1.012; tp=last*0.978; is_sniper=True
        else: return None,None,f"⚪️ {ticker} NO TRADE (Score {score})\n"+"\n".join(rs),False
        plt.figure(figsize=(7,3.5)); plt.plot(c1.tail(80), label='Price', linewidth=1.5)
        plt.plot(c1.ewm(9).mean().tail(80), label='EMA9'); plt.plot(c1.ewm(21).mean().tail(80), label='EMA21'); plt.plot(c1.ewm(50).mean().tail(80), label='EMA50')
        plt.title(f"{ticker} SNIPER RSI:{r:.1f}"); plt.legend(fontsize=7); plt.grid(True, alpha=0.3); plt.tight_layout()
        buf=io.BytesIO(); plt.savefig(buf, format='png', dpi=120); plt.close(); buf.seek(0)
        return (last,sigt,r,e9,e21,sl,tp,"\n".join(rs)),buf,None,is_sniper
    except Exception as e: return None,None,f"Err {e}",False

def get_quick_status(ticker):
    try:
        df = yf.download(ticker, period="5d", interval="1h", progress=False, auto_adjust=True)
        if df.empty: return f"{ticker}: No data"
        if isinstance(df.columns, pd.MultiIndex): c = df['Close'].iloc[:,0]
        else: c = df['Close']
        last=float(c.iloc[-1]); r=float(rsi(c).iloc[-1])
        return f"{ticker}: ${last:.2f} | RSI {r:.1f}"
    except: return f"{ticker}: Error"

# 30 MIN LOOP - Only Sniper alerts
def loop_30min():
    while True:
        time.sleep(1800) # 30 min
        if not ALERT_CHATS: continue
        print("30min Sniper scan...")
        for cid in list(ALERT_CHATS):
            for name in SYMBOLS.keys():
                data,chart,err,sniper = get_power(SYMBOLS[name])
                if not sniper or not data: continue
                last,sigt,r,e9,e21,sl,tp,det=data
                msg=f"🔔 30MIN SNIPER ALERT!\n\n{sigt}\n\n📈 {name} ${last:.2f}\nRSI:{r:.1f}\n{det}\n\n🎯 TP:{tp:.2f}\n🛑 SL:{sl:.2f}"
                try: bot.send_photo(cid, chart, caption=msg)
                except: pass
                time.sleep(1)

# 60 MIN LOOP - Hourly summary
def loop_60min():
    while True:
        time.sleep(3600) # 60 min
        if not ALERT_CHATS: continue
        print("60min Hourly summary...")
        for cid in list(ALERT_CHATS):
            try:
                summary = "⏰ HOURLY MARKET SUMMARY (1h)\n\n"
                for name in SYMBOLS.keys():
                    summary += get_quick_status(SYMBOLS[name]) + "\n"
                summary += "\n🎯 Sniper scans every 30min\nUse /signal ALL for details"
                bot.send_message(cid, summary)
            except: pass

@app.route('/')
def home(): return "V6.2 Dual 30min+60min Live"
@bot.message_handler(commands=['start'])
def start(m):
    ALERT_CHATS.add(m.chat.id)
    bot.reply_to(m,"🎯 V6.2 DUAL AUTO LIVE!\n\n✅ 30min: Sniper alerts ONLY when Score 3/4\n✅ 60min: Hourly summary of all 3\n\nNo spam, only power!\n\n/signal ALL = Instant scan\n/stopauto = Stop all\n/startauto = Resume")
@bot.message_handler(commands=['stopauto'])
def stop(m): ALERT_CHATS.discard(m.chat.id); bot.reply_to(m,"🔕 Both auto scans stopped")
@bot.message_handler(commands=['startauto'])
def sta(m): ALERT_CHATS.add(m.chat.id); bot.reply_to(m,"🔔 30min Sniper + 60min Summary ON!")
@bot.message_handler(commands=['signal'])
def sig(m):
    ALERT_CHATS.add(m.chat.id)
    args=m.text.split(); tgt=args[1].upper() if len(args)>1 else "ALL"
    scan=list(SYMBOLS.keys()) if tgt=="ALL" else [tgt] if tgt in SYMBOLS else list(SYMBOLS.keys())
    bot.send_message(m.chat.id,f"🎯 Scanning {', '.join(scan)} - 6 filters...")
    for name in scan:
        data,chart,err,sniper=get_power(SYMBOLS[name])
        if err: bot.send_message(m.chat.id, err); continue
        if not data: continue
        last,sigt,r,e9,e21,sl,tp,det=data
        bot.send_photo(m.chat.id, chart, caption=f"{sigt}\n\n{name} ${last:.2f}\nRSI:{r:.1f}\n{det}\n\nTP:{tp:.2f} SL:{sl:.2f}")

def run_flask(): app.run(host='0.0.0.0', port=10000)
if __name__=="__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    threading.Thread(target=loop_30min, daemon=True).start()
    threading.Thread(target=loop_60min, daemon=True).start()
    print("V6.2 Dual Auto Running...")
    while True:
        try: bot.infinity_polling(timeout=60)
        except: time.sleep(5)
