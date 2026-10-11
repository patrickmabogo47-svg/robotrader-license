import os, requests, yfinance as yf, pandas as pd, mplfinance as mpf
from flask import Flask
import threading, time, os.path

app = Flask(__name__)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN","").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID","").strip()
ASSETS = {"GOLD":"GC=F", "EURUSD":"EURUSD=X", "BTC":"BTC-USD"}

def send_tg(text, chart_path=None):
    if not TELEGRAM_TOKEN or not CHAT_ID: return False
    try:
        # text
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        r = requests.post(url, data={"chat_id":CHAT_ID, "text":text}, timeout=20)
        print(f"TG text {r.status_code}")
        # chart
        if chart_path and os.path.exists(chart_path):
            with open(chart_path,'rb') as f:
                urlp = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
                rp = requests.post(urlp, data={"chat_id":CHAT_ID}, files={"photo":f}, timeout=25)
                print(f"TG photo {rp.status_code}")
        return r.ok
    except Exception as e:
        print(f"TG err {e}"); return False

def get_sniper(symbol, name):
    try:
        df = yf.download(symbol, period="7d", interval="1h", progress=False, auto_adjust=False)
        if len(df)<120: return None
        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
        df['EMA50']=df['Close'].ewm(span=50).mean()
        df['EMA200']=df['Close'].ewm(span=200).mean()
        delta=df['Close'].diff()
        gain=delta.where(delta>0,0).rolling(14).mean()
        loss=-delta.where(delta<0,0).rolling(14).mean()
        rs=gain/(loss+1e-9)
        df['RSI']=100-(100/(1+rs))
        ema12=df['Close'].ewm(span=12).mean()
        ema26=df['Close'].ewm(span=26).mean()
        df['MACD']=ema12-ema26
        df['SIG']=df['MACD'].ewm(span=9).mean()
        last=df.iloc[-1]
        price=float(last['Close']); rsi=float(last['RSI'])
        ema50=float(last['EMA50']); ema200=float(last['EMA200'])
        macd=float(last['MACD']); sig=float(last['SIG'])
        score=0; trend="NONE"
        if price>ema50>ema200 and macd>sig:
            score+=2; trend="4H UP"
        elif price<ema50<ema200 and macd<sig:
            score+=2; trend="4H DOWN"
        if 30<rsi<70: score+=1
        if abs(macd-sig)>0: score+=0.5
        # keep df for chart
        df_tail = df.tail(100)
        if score>=3 and trend!="NONE":
            direction="BUY" if "UP" in trend else "SELL"
            tp=price*1.022 if direction=="BUY" else price*0.978
            sl=price*0.99 if direction=="BUY" else price*1.01
            return {"name":name,"symbol":symbol,"price":price,"rsi":rsi,"trend":trend,"dir":direction,"score":round(score,1),"tp":tp,"sl":sl,"df":df_tail}
        return {"name":name,"symbol":symbol,"price":price,"rsi":rsi,"trend":"NONE","score":round(score,1),"df":df_tail}
    except Exception as e:
        print(f"{name} err {e}"); return None

def make_chart(data):
    try:
        df=data['df']
        path=f"/tmp/{data['name']}_sniper.png"
        mpf.plot(df, type='candle', mav=(50,200), volume=False, style='yahoo', title=f"{data['name']} {data['dir']} Score {data['score']} - {data['trend']}", savefig=path)
        return path
    except Exception as e:
        print(f"chart err {e}"); return None

@app.route("/")
def home(): return "RoboTrader SA V6.0 SMART LIVE - Auto + Chart"

@app.route("/test-telegram")
def test_tg():
    ok=send_tg("🔔 PURE TELEGRAM TEST - V6.0 SMART is OK, auto running")
    return f"Telegram test sent: {ok}"

@app.route("/signal")
def signal_now():
    out=[]
    for n,t in ASSETS.items():
        r=get_sniper(t,n)
        if not r: continue
        if r['trend']!="NONE" and r['score']>=3:
            chart=make_chart(r)
            txt=f"🎯 SNIPER {r['dir']} ⬆️ Score {r['score']}\n{n} ({r['symbol']})\nPrice: ${r['price']
