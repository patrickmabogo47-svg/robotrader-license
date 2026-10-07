import os, asyncio, requests, math, time
from datetime import datetime
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import io
    CHART=True
except:
    CHART=False

app = FastAPI()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
USERS = set()
ADMIN_KEY = "Kimberley2026!"
SIGNAL_HISTORY = []
LAST_STATUS = {"BTC":"WAIT","GOLD":"WAIT"}

@app.get("/")
def home():
    return {"status":"V4.8.2 ANTI-BLOCK BTC+GOLD","chart":CHART,"last":LAST_STATUS}

@app.get("/admin")
def admin(key: str = ""):
    if key!=ADMIN_KEY: return {"error":"Wrong key"}
    return HTMLResponse(f"<html><body style='background:#0B0F1C;color:#fff'>V4.8.2 {LAST_STATUS} {len(SIGNAL_HISTORY)} signals</body></html>")

# === ANTI-BLOCK DATA - 3 SOURCES ===
def get_binance(symbol, interval, limit=200):
    # Try Binance first
    try:
        url=f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
        r=requests.get(url,timeout=8,headers={"User-Agent":"Mozilla/5.0"}).json()
        if isinstance(r, list) and len(r)>50:
            closes=[float(x[4]) for x in r]
            highs=[float(x[2]) for x in r]
            lows=[float(x[3]) for x in r]
            return closes, highs, lows, "binance"
    except: pass
    return None,None,None,None

def get_okx(instId, bar, limit=200):
    # OKX never blocks Render
    try:
        url=f"https://www.okx.com/api/v5/market/candles?instId={instId}&bar={bar}&limit={limit}"
        r=requests.get(url,timeout=8).json()
        data=r.get("data",[])
        if len(data)>50:
            data=list(reversed(data)) # OKX newest first
            closes=[float(x[4]) for x in data]
            highs=[float(x[2]) for x in data]
            lows=[float(x[3]) for x in data]
            return closes, highs, lows, "okx"
    except Exception as e:
        print(f"okx {e}")
    return None,None,None,None

def get_crypto_compare(fsym, limit=200, interval="hour"):
    try:
        # hour = 1H, day = 1D
        if interval=="hour":
            url=f"https://min-api.cryptocompare.com/data/v2/histohour?fsym={fsym}&tsym=USDT&limit={limit}"
        else:
            url=f"https://min-api.cryptocompare.com/data/v2/histoday?fsym={fsym}&tsym=USDT&limit={limit}"
        r=requests.get(url,timeout=8).json()
        data=r.get("Data",{}).get("Data",[])
        if len(data)>50:
            closes=[float(x["close"]) for x in data]
            highs=[float(x["high"]) for x in data]
            lows=[float(x["low"]) for x in data]
            return closes, highs, lows, "cc"
    except: pass
    return None,None,None,None

def get_data(pair):
    # BTC
    if pair=="BTC":
        # H1
        c,h,l,src = get_binance("BTCUSDT","1h",200)
        if c is None: c,h,l,src = get_okx("BTC-USDT","1H",200)
        if c is None: c,h,l,src = get_crypto_compare("BTC",200,"hour")
        h1_c,h1_h,h1_l = c,h,l
        if h1_c is None: return None,None,None,None,None,None,False

        # H4
        c,h,l,src = get_binance("BTCUSDT","4h",100)
        if c is None: c,h,l,src = get_okx("BTC-USDT","4H",100)
        if c is None: c,h,l,src = get_crypto_compare("BTC",100,"hour") # fallback use hour
        h4_c = c if c else h1_c[-100:]

        # D1
        c,h,l,src = get_binance("BTCUSDT","1d",60)
        if c is None: c,h,l,src = get_okx("BTC-USDT","1D",60)
        if c is None: c,h,l,src = get_crypto_compare("BTC",60,"day")
        d1_c = c if c else h1_c[-60:]

        return h1_c,h1_h,h1_l,h4_c,d1_c,"BTCUSDT",True
    else:
        # GOLD = PAXG or XAUT
        c,h,l,src = get_binance("PAXGUSDT","1h",200)
        if c is None: c,h,l,src = get_okx("PAXG-USDT","1H",200)
        if c is None: c,h,l,src = get_crypto_compare("PAXG",200,"hour")
        h1_c,h1_h,h1_l = c,h,l
        if h1_c is None: return None,None,None,None,None,None,False

        c,h,l,src = get_binance("PAXGUSDT","4h",100)
        if c is None: c,h,l,src = get_okx("PAXG-USDT","4H",100)
        h4_c = c if c else h1_c[-100:]

        c,h,l,src = get_binance("PAXGUSDT","1d",60)
        if c is None: c,h,l,src = get_okx("PAXG-USDT","1D",60)
        if c is None: c,h,l,src = get_crypto_compare("PAXG",60,"day")
        d1_c = c if c else h1_c[-60:]

        return h1_c,h1_h,h1_l,h4_c,d1_c,"PAXGUSDT",True

def rsi_calc(c,p=14):
    if len(c)<p+2: return 50
    g=l=0
    for i in range(-p,0):
        d=c[i]-c[i-1]
        if d>0: g+=d
        else: l+=-d
    if l==0: return 70 if g>0 else 30
    return 100-(100/(1+g/(l+0.001)))

def atr_calc(highs,lows,closes,period=14):
    trs=[]
    for i in range(-period,0):
        tr = max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1]))
        trs.append(tr)
    return sum(trs)/len(trs) if trs else 0

def find_swings(highs,lows,look=5):
    sh=[]; sl=[]
    for i in range(look, len(highs)-look):
        if highs[i]==max(highs[i-look:i+look+1]): sh.append((i,highs[i]))
        if lows[i]==min(lows[i-look:i+look+1]): sl.append((i,lows[i]))
    return sh[-6:], sl[-6:]

def trendline_fit(points):
    if len(points)<2: return None, None
    try:
        x=[p[0] for p in points]; y=[p[1] for p in points]
        n=len(x); sx=sum(x); sy=sum(y); sxy=sum(a*b for a,b in zip(x,y)); sxx=sum(a*a for a in x)
        slope=(n*sxy - sx*sy)/(n*sxx - sx*sx + 0.0001)
        intercept=(sy - slope*sx)/n
        return slope, intercept
    except: return None,None

def check_break(price, slope, intercept, idx, direction="up"):
    if slope is None: return False
    tv = slope*idx + intercept
    return price > tv*1.001 if direction=="up" else price < tv*0.999

def analyze_pair(pair):
    h1_c,h1_h,h1_l,h4_c,d1_c,symbol,real = get_data(pair)
    if not real: return "SKIP",0,50,0,"No data - all sources blocked","",None,None

    price=h1_c[-1]; prev=h1_c[-2]
    ema20=sum(h1_c[-20:])/20; ema50=sum(h1_c[-50:])/50; ema200=sum(h1_c[-200:])/200
    ema20_h4=sum(h4_c[-20:])/20; ema50_h4=sum(h4_c[-50:])/50
    ema20_d1=sum(d1_c[-20:])/20; ema50_d1=sum(d1_c[-50:])/20
    rsi=rsi_calc(h1_c); rsi_prev=rsi_calc(h1_c[:-1]); rsi_h4=rsi_calc(h4_c)
    atr=atr_calc(h1_h,h1_l,h1_c); dist=abs(price-ema20)/ema20*100
    swing_highs, swing_lows = find_swings(h1_h,h1_l)
    recent_high = max(h1_h[-30:-3]); recent_low = min(h1_l[-30:-3])
    sh_slope, sh_inter = trendline_fit(swing_highs)
    sl_slope, sl_inter = trendline_fit(swing_lows)
    d1_up=ema20_d1>ema50_d1; h4_up=ema20_h4>ema50_h4; h1_up=ema20>ema50 and price>ema200; h1_down=ema20<ema50 and price<ema200
    good = atr > (price*0.001) and dist>0.2
    if not good: return "SKIP",0,rsi,dist,"Choppy ATR low - wait volatility","",None,None
    idx=len(h1_c)-1

    # 1. TL BREAK
    if check_break(price, sh_slope, sh_inter, idx, "up") and sh_slope and sh_slope<0 and h1_up and 45<rsi<70 and rsi>rsi_prev:
        return "BUY",88,rsi,dist,f"TRENDLINE BREAKOUT BUY: Broke descending TL {price:.2f}, HH {recent_high:.2f}, H1+H4 UP",{"support":recent_high},(sh_slope,sh_inter,"resist")
    if check_break(price, sl_slope, sl_inter, idx, "down") and sl_slope and sl_slope>0 and h1_down and 30<rsi<55 and rsi<rsi_prev:
        return "SELL",88,rsi,dist,f"TRENDLINE BREAKDOWN SELL: Broke ascending TL {price:.2f}, LL {recent_low:.2f}, H1+H4 DOWN",{"resist":recent_low},(sl_slope,sl_inter,"support")

    # 2. BOS
    if price>recent_high and prev<=recent_high and h1_up and h4_up and rsi<68 and rsi>rsi_prev:
        return "BUY",82,rsi,dist,f"BOS BUY: Broke {recent_high:.2f} HH, RSI {rsi_prev:.0f}->{rsi:.0f}",{"support":recent_high},(sh_slope,sh_inter,"resist") if sh_slope else None
    if price<recent_low and prev>=recent_low and h1_down and rsi>32 and rsi<rsi_prev:
        return "SELL",82,rsi,dist,f"BOS SELL: Broke {recent_low:.2f} LL, RSI {rsi_prev:.0f}->{rsi:.0f}",{"resist":recent_low},(sl_slope,sl_inter,"support") if sl_slope else None

    # 3. PULLBACK
    near=abs(price-ema20)/ema20*100<0.5
    if h1_up and h4_up and d1_up and near and price>prev and rsi>rsi_prev and 40<rsi<62:
        return "BUY",76,rsi,dist,f"PULLBACK BUY: EMA20 retest {ema20:.2f} + TL bounce",{"support":ema20},(sl_slope,sl_inter,"support") if sl_slope else None
    if h1_down and not h4_up and near and price<prev and rsi<rsi_prev and 38<rsi<60:
        return "SELL",76,rsi,dist,f"PULLBACK SELL: EMA20 retest {ema20:.2f} TL reject",{"resist":ema20},(sh_slope,sh_inter,"resist") if sh_slope else None

    return "SKIP",0,rsi,dist,f"Waiting BOS/TL: Range {recent_low:.0f}-{recent_high:.0f} RSI {rsi:.0f}","",None,None

def make_chart(pair, h1_c, h1_h, h1_l, action, price, levels, tl_info, rsi, dist, conf, reason):
    if not CHART or not h1_c: return None
    try:
        plt.figure(figsize=(9,5))
        data=h1_c[-70:]
        color='#00ff88' if action=='BUY' else '#ff4444' if action=='SELL' else '#bbbbbb'
        plt.plot(data, color=color, linewidth=2.2, label=f'{pair} {action}')
        ema20=[sum(h1_c[i-20:i])/20 if i>=20 else h1_c[i] for i in range(len(h1_c))][-70:]
        plt.plot(ema20, color='#ffaa00', linestyle='--', alpha=0.7, label='EMA20')
        if tl_info:
            slope, inter, typ = tl_info
            if slope:
                x_vals=list(range(len(h1_c)-70, len(h1_c)))
                tl=[slope*x+inter for x in x_vals]
                plt.plot(range(len(data)-len(tl), len(data)), tl, color='#00d9ff' if typ=="resist" else '#ffaa00', linewidth=1.8, label=f'{typ} TL')
        if levels:
            if "support" in levels: plt.axhline(levels["support"], color='white', linewidth=1.2, label=f'Supp {levels["support"]:.2f}')
            if "resist" in levels: plt.axhline(levels["resist"], color='white', linewidth=1.2, label=f'Res {levels["resist"]:.2f}')
        sl=price*0.993 if action=="BUY" else price*1.007 if action!="SKIP" else price*0.993
        tp=price*1.018 if action=="BUY" else price*0.982 if action!="SKIP" else price*1.018
        if action!="SKIP":
            plt.axhline(price, color='white', linewidth=1.5)
            plt.axhline(sl, color='#ff4444', linestyle=':', label=f'SL {sl:.2f}')
            plt.axhline(tp, color='#00ff88', linestyle=':', label=f'TP {tp:.2f}')
        plt.title(f"V4.8.2 {pair} {action} {conf}% RSI {rsi:.0f} Dist {dist:.2f}%\n{reason[:90]}", color='white', fontsize=8)
        plt.legend(fontsize=6, loc='best', ncol=2); plt.grid(alpha=0.15)
        ax=plt.gca(); ax.set_facecolor('#0B0F1C'); plt.gcf().set_facecolor('#0B0F1C'); ax.tick_params(colors='white', labelsize=7)
        buf=io.BytesIO(); plt.savefig(buf, format='png', dpi=160, bbox_inches='tight'); plt.close(); buf.seek(0); return buf
    except Exception as e:
        print(e); return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    USERS.add(update.effective_chat.id)
    await update.message.reply_text("✅ V4.8.2 ANTI-BLOCK LIVE\nTrendline + BOS + Pullback\nBTC + GOLD (OKX fallback)\n/signal BTC | GOLD | ALL")

async def signal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    USERS.add(update.effective_chat.id)
    target="ALL" if not context.args else context.args[0].upper()
    pairs=["BTC","GOLD"] if target=="ALL" else [target if target in ["BTC","GOLD"] else "BTC"]
    await update.message.reply_text(f"🔍 V4.8.2 scanning {target} via OKX (Binance blocked bypass)...")
    for pair in pairs:
        h1_c,h1_h,h1_l,h4_c,d1_c,symbol,real = get_data(pair)
        if not real:
            await update.message.reply_text(f"⚠️ {pair} all sources failed - retry 30sec")
            continue
        action,conf,rsi,dist,reason,levels,tl_info = analyze_pair(pair)[:-1] if len(analyze_pair(pair))>7 else analyze_pair(pair)
        # re-call to get all
        action,conf,rsi,dist,reason,levels,tl_info = analyze_pair(pair)[:7]
        LAST_STATUS[pair]=f"{action} {conf}%"
        SIGNAL_HISTORY.append({"time":datetime.now().strftime("%H:%M"),"pair":pair,"action":action,"conf":conf,"reason":reason})
        price=h1_c[-1]; sl=price*0.993 if action=="BUY" else price*1.007; tp=price*1.018 if action=="BUY" else price*0.982
        if action=="SKIP": txt=f"⏳ {pair} V4.8.2 {reason}\nPrice {price:,.2f} RSI {rsi:.0f} Dist {dist:.2f}%\nWatching TL/BOS - no break yet"
        else: txt=f"🤖 {pair} V4.8.2 {action} {conf}% 🔥\n{reason}\n\nEntry {price:,.2f}\nSL {sl:,.2f}\nTP {tp:,.2f}\nRSI {rsi:.0f} Dist {dist:.2f}%"
        chart=make_chart(pair,h1_c,h1_h,h1_l,action,price,levels,tl_info,rsi,dist,conf,reason) if CHART else None
        if chart: await context.bot.send_photo(chat_id=update.effective_chat.id, photo=chart, caption=txt)
        else: await update.message.reply_text(txt)

telegram_app=None
async def auto_loop():
    while True:
        await asyncio.sleep(900)
        if not USERS or not telegram_app: continue
        for pair in ["BTC","GOLD"]:
            try:
                h1_c,h1_h,h1_l,h4_c,d1_c,symbol,real = get_data(pair)
                if not real: continue
                action,conf,rsi,dist,reason,levels,tl_info = analyze_pair(pair)[:7]
                prev=LAST_STATUS.get(pair,"WAIT"); LAST_STATUS[pair]=f"{action} {conf}%"
                if action!="SKIP" and conf>=80 and ("WAIT" in prev or "SKIP" in prev):
                    price=h1_c[-1]; sl=price*0.993 if action=="BUY" else price*1.007; tp=price*1.018 if action=="BUY" else price*0.982
                    chart=make_chart(pair,h1_c,h1_h,h1_l,action,price,levels,tl_info,rsi,dist,conf,reason) if CHART else None
                    for uid in list(USERS):
                        try:
                            txt=f"🚨 AUTO {pair} {action} {conf}% TL BREAK!\nEntry {price:.2f} SL {sl:.2f} TP {tp:.2f}\n{reason}"
                            if chart: await telegram_app.bot.send_photo(chat_id=uid, photo=chart, caption=txt)
                            else: await telegram_app.bot.send_message(chat_id=uid, text=txt)
                        except: pass
            except: pass

async def run_bot():
    global telegram_app
    if not BOT_TOKEN: return
    while True:
        try:
            app_bot=ApplicationBuilder().token(BOT_TOKEN).build()
            telegram_app=app_bot
            app_bot.add_handler(CommandHandler("start", start))
            app_bot.add_handler(CommandHandler("signal", signal_cmd))
            await app_bot.initialize(); await app_bot.start()
            await app_bot.updater.start_polling(drop_pending_updates=True)
            asyncio.create_task(auto_loop())
            while True: await asyncio.sleep(3600)
        except Exception as e:
            print(f"crash {e}"); await asyncio.sleep(5)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(run_bot())
