import os, asyncio, requests, math
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
    import numpy as np
    CHART=True
except:
    CHART=False
    np=None

app = FastAPI()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
USERS = set()
ADMIN_KEY = "Kimberley2026!"
SIGNAL_HISTORY = []
LAST_STATUS = {"BTC":"WAIT","GOLD":"WAIT"}

@app.get("/")
def home():
    return {"status":"V4.8 + TRENDLINE BTC+GOLD","chart":CHART,"last":LAST_STATUS}

@app.get("/admin")
def admin(key: str = ""):
    if key!=ADMIN_KEY: return {"error":"Wrong key"}
    rows=""
    for s in SIGNAL_HISTORY[-120:][::-1]:
        c="#00ff88" if s['action']=="BUY" else "#ff4444" if s['action']=="SELL" else "#ffaa00"
        rows+=f"<tr><td>{s['time']}</td><td>{s['pair']}</td><td style='color:{c}'>{s['action']}</td><td>{s['conf']}%</td><td>{s['reason']}</td></tr>"
    return HTMLResponse(f"<html><body style='background:#0B0F1C;color:#fff;font-family:Arial;padding:10px'><h3>V4.8 + TRENDLINE {LAST_STATUS}</h3><table>{rows}</table></body></html>")

def get_binance(symbol, interval, limit=200):
    try:
        url=f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
        r=requests.get(url,timeout=10,headers={"User-Agent":"Mozilla/5.0"}).json()
        if isinstance(r, list) and len(r)>50:
            closes=[float(x[4]) for x in r]
            highs=[float(x[2]) for x in r]
            lows=[float(x[3]) for x in r]
            return closes, highs, lows, True
    except: pass
    return None, None, None, False

def get_data(pair):
    symbol = "BTCUSDT" if pair=="BTC" else "PAXGUSDT"
    h1_c,h1_h,h1_l,ok1 = get_binance(symbol,"1h",200)
    h4_c,_,_,_ = get_binance(symbol,"4h",100)
    d1_c,_,_,_ = get_binance(symbol,"1d",60)
    if not ok1: return None,None,None,None,None,None,False
    if h4_c is None: h4_c=h1_c[-100:]
    if d1_c is None: d1_c=h1_c[-60:]
    return h1_c,h1_h,h1_l,h4_c,d1_c,symbol,True

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

# === NEW: TRENDLINE DETECTION ===
def find_swings(highs,lows,look=5):
    swing_highs=[]; swing_lows=[]
    for i in range(look, len(highs)-look):
        if highs[i]==max(highs[i-look:i+look+1]):
            swing_highs.append((i,highs[i]))
        if lows[i]==min(lows[i-look:i+look+1]):
            swing_lows.append((i,lows[i]))
    return swing_highs[-6:], swing_lows[-6:] # last 6

def trendline_fit(points):
    if len(points)<2 or not CHART: return None, None
    try:
        x=[p[0] for p in points]; y=[p[1] for p in points]
        # linear regression
        n=len(x)
        sx=sum(x); sy=sum(y); sxy=sum(a*b for a,b in zip(x,y)); sxx=sum(a*a for a in x)
        slope=(n*sxy - sx*sy)/(n*sxx - sx*sx + 0.0001)
        intercept=(sy - slope*sx)/n
        return slope, intercept
    except:
        return None, None

def check_trendline_break(price, slope, intercept, idx, direction="up"):
    if slope is None: return False
    trend_val = slope*idx + intercept
    if direction=="up": # price breaks above descending resistance
        return price > trend_val*1.001
    else: # price breaks below ascending support
        return price < trend_val*0.999

def analyze_pair(pair):
    h1_c,h1_h,h1_l,h4_c,d1_c,symbol,real = get_data(pair)
    if not real:
        return "SKIP",0,50,0,"No data","",None,None,None

    price=h1_c[-1]; prev=h1_c[-2]
    ema20=sum(h1_c[-20:])/20; ema50=sum(h1_c[-50:])/50; ema200=sum(h1_c[-200:])/200
    ema20_h4=sum(h4_c[-20:])/20; ema50_h4=sum(h4_c[-50:])/50
    ema20_d1=sum(d1_c[-20:])/20; ema50_d1=sum(d1_c[-50:])/20
    rsi=rsi_calc(h1_c); rsi_prev=rsi_calc(h1_c[:-1]); rsi_h4=rsi_calc(h4_c)
    atr=atr_calc(h1_h,h1_l,h1_c)
    dist=abs(price-ema20)/ema20*100

    swing_highs, swing_lows = find_swings(h1_h,h1_l)
    recent_high = max(h1_h[-30:-3]) if len(h1_h)>30 else max(h1_h)
    recent_low = min(h1_l[-30:-3]) if len(h1_l)>30 else min(h1_l)

    # Trendlines
    sh_slope, sh_intercept = trendline_fit(swing_highs) # resistance trendline
    sl_slope, sl_intercept = trendline_fit(swing_lows) # support trendline

    d1_up=ema20_d1>ema50_d1; h4_up=ema20_h4>ema50_h4; h1_up=ema20>ema50 and price>ema200
    h1_down=ema20<ema50 and price<ema200

    good_market = atr > (price*0.0012) and dist>0.25
    if not good_market:
        return "SKIP",0,rsi,dist,"Choppy - ATR low","",None,None,None

    idx = len(h1_c)-1
    # === 1. TRENDLINE BREAKOUT (NEW - BEST STRATEGY) ===
    breaks_resistance = check_trendline_break(price, sh_slope, sh_intercept, idx, "up") if sh_slope is not None else False
    breaks_support = check_trendline_break(price, sl_slope, sl_intercept, idx, "down") if sl_slope is not None else False

    if breaks_resistance and h1_up and price>prev and rsi>45 and rsi<70 and rsi>rsi_prev:
        # confirm descending trendline broken
        if sh_slope is not None and sh_slope < 0: # was descending
            conf=85 + (rsi_h4-50)*0.3
            reason=f"TRENDLINE BREAKOUT BUY: Broke descending resistance TL, price {price:.2f} > TL, HH {recent_high:.2f}, H1+H4 UP"
            levels={"support":recent_high,"hl":min(h1_l[-20:]) if swing_lows else recent_low}
            tl_info=(sh_slope, sh_intercept, "resist")
            return "BUY",int(min(93,conf)),rsi,dist,reason,levels,tl_info,symbol

    if breaks_support and h1_down and price<prev and rsi<55 and rsi>30 and rsi<rsi_prev:
        if sl_slope is not None and sl_slope > 0: # was ascending, now broken
            conf=85 + (50-rsi_h4)*0.3
            reason=f"TRENDLINE BREAKDOWN SELL: Broke ascending support TL, price {price:.2f} < TL, LL {recent_low:.2f}, H1+H4 DOWN"
            levels={"resist":recent_low,"hh":max(h1_h[-20:])}
            tl_info=(sl_slope, sl_intercept, "support")
            return "SELL",int(min(93,conf)),rsi,dist,reason,levels,tl_info,symbol

    # === 2. BOS BREAKOUT ===
    broke_high = price > recent_high and prev <= recent_high and price>prev
    broke_low = price < recent_low and prev >= recent_low and price<prev

    if broke_high and h1_up and h4_up and rsi<68 and rsi>rsi_prev:
        conf=80 + dist*2
        reason=f"BOS BUY: Broke {recent_high:.2f} (HH), new structure, H1+H4 UP RSI {rsi_prev:.0f}->{rsi:.0f}"
        levels={"support":recent_high}
        tl_info=(sh_slope, sh_intercept, "resist") if sh_slope else None
        return "BUY",int(min(90,conf)),rsi,dist,reason,levels,tl_info,symbol

    if broke_low and h1_down and not h4_up and rsi>32 and rsi<rsi_prev:
        conf=80 + dist*2
        reason=f"BOS SELL: Broke {recent_low:.2f} (LL), breakdown, H1+H4 DOWN RSI {rsi_prev:.0f}->{rsi:.0f}"
        levels={"resist":recent_low}
        tl_info=(sl_slope, sl_intercept, "support") if sl_slope else None
        return "SELL",int(min(90,conf)),rsi,dist,reason,levels,tl_info,symbol

    # === 3. TREND PULLBACK ===
    near_ema20 = abs(price-ema20)/ema20*100 < 0.5
    if h1_up and h4_up and d1_up and near_ema20 and price>prev and rsi>rsi_prev and 40<rsi<62:
        reason=f"TREND PULLBACK BUY: Retest EMA20 {ema20:.2f} + support TL bounce, D1 UP"
        levels={"support":ema20}
        tl_info=(sl_slope, sl_intercept, "support") if sl_slope else None
        return "BUY",78,rsi,dist,reason,levels,tl_info,symbol

    if h1_down and not h4_up and not d1_up and near_ema20 and price<prev and rsi<rsi_prev and 38<rsi<60:
        reason=f"TREND PULLBACK SELL: Retest EMA20 {ema20:.2f} + resistance TL reject, D1 DOWN"
        levels={"resist":ema20}
        tl_info=(sh_slope, sh_intercept, "resist") if sh_slope else None
        return "SELL",78,rsi,dist,reason,levels,tl_info,symbol

    return "SKIP",0,rsi,dist,f"Waiting: No TL break, Range {recent_low:.0f}-{recent_high:.0f} RSI {rsi:.0f} TL up={sh_slope}","",None,None,symbol

def make_chart(pair, h1_c, h1_h, h1_l, action, price, levels, tl_info, rsi, dist, conf, reason):
    if not CHART or h1_c is None: return None
    try:
        plt.figure(figsize=(9,5))
        data=h1_c[-70:]
        color='#00ff88' if action=='BUY' else '#ff4444' if action=='SELL' else '#bbbbbb'
        plt.plot(data, color=color, linewidth=2.2, label=f'{pair} H1 {action}')

        ema20_line=[sum(h1_c[i-20:i])/20 if i>=20 else h1_c[i] for i in range(len(h1_c))][-70:]
        plt.plot(ema20_line, color='#ffaa00', linestyle='--', alpha=0.7, label='EMA20')
        ema50_line=[sum(h1_c[i-50:i])/50 if i>=50 else h1_c[i] for i in range(len(h1_c))][-70:]
        plt.plot(ema50_line, color='#aa88ff', linestyle='--', alpha=0.5, label='EMA50')

        # Draw trendlines (diagonal)
        if tl_info:
            slope, intercept, typ = tl_info
            if slope is not None:
                x_vals = list(range(len(h1_c)-70, len(h1_c)))
                tl_vals = [slope*x + intercept for x in x_vals]
                # clip to visible range
                tl_vals = [v for v in tl_vals if min(data)*0.97 < v < max(data)*1.03]
                if len(tl_vals)>10:
                    lbl = f'{"Resist" if typ=="resist" else "Support"} TL'
                    plt.plot(range(len(data)-len(tl_vals), len(data)), tl_vals, color='#00d9ff' if typ=="resist" else '#ffaa00', linewidth=1.8, linestyle='-', label=lbl)

        # Horizontal S/R like your screenshot (black lines)
        if levels:
            if "support" in levels:
                plt.axhline(levels["support"], color='white', linewidth=1.2, alpha=0.9, label=f'Supp {levels["support"]:.2f}')
            if "resist" in levels:
                plt.axhline(levels["resist"], color='white', linewidth=1.2, alpha=0.6, linestyle='-', label=f'Res {levels["resist"]:.2f}')
            if "hl" in levels:
                plt.axhline(levels["hl"], color='#00aaff', linestyle=':', alpha=0.7, label=f'HL {levels["hl"]:.2f}')
            if "hh" in levels:
                plt.axhline(levels["hh"], color='#ff00aa', linestyle=':', alpha=0.7, label=f'HH {levels["hh"]:.2f}')

        sl = price*0.993 if action=="BUY" else price*1.007 if action=="SELL" else price*0.993
        tp = price*1.018 if action=="BUY" else price*0.982 if action=="SELL" else price*1.018
        if action!="SKIP":
            plt.axhline(price, color='white', linewidth=1.5)
            plt.axhline(sl, color='#ff4444', linestyle=':', linewidth=1.5, label=f'SL {sl:.2f}')
            plt.axhline(tp, color='#00ff88', linestyle=':', linewidth=1.5, label=f'TP {tp:.2f}')
            plt.fill_between(range(len(data)), sl, price, color='#ffaa00', alpha=0.12)
            plt.fill_between(range(len(data)), price, tp, color='#00ff88' if action=="BUY" else '#ff4444', alpha=0.1)

        title = f"V4.8 TL {pair} {action} {conf}% RSI {rsi:.0f} Dist {dist:.2f}%\n{reason[:85]}"
        plt.title(title, color='white', fontsize=8)
        plt.legend(fontsize=6, loc='best', ncol=2)
        plt.grid(alpha=0.15)
        ax=plt.gca(); ax.set_facecolor('#0B0F1C'); plt.gcf().set_facecolor('#0B0F1C')
        ax.tick_params(colors='white', labelsize=7)
        buf=io.BytesIO()
        plt.savefig(buf, format='png', dpi=160, bbox_inches='tight')
        plt.close(); buf.seek(0)
        return buf
    except Exception as e:
        print(f"chart err {e}")
        return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    USERS.add(update.effective_chat.id)
    await update.message.reply_text("✅ V4.8 + TRENDLINE LIVE\n📈 BTC + GOLD\nStrategies:\n1. Trendline Breakout (BEST)\n2. BOS HH/HL Break\n3. Trend Pullback EMA20\nH1 boss, market filter, chart with TL\n/signal BTC | GOLD | ALL")

async def signal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    USERS.add(update.effective_chat.id)
    args=context.args
    target="ALL" if not args else args[0].upper()
    pairs=["BTC","GOLD"] if target=="ALL" else [target if target in ["BTC","GOLD"] else "BTC"]
    await update.message.reply_text(f"🔍 V4.8 TL scanning {target} - Trendline + BOS + Pullback...")
    for pair in pairs:
        h1_c,h1_h,h1_l,h4_c,d1_c,symbol,real = get_data(pair)
        if not real:
            await update.message.reply_text(f"⚠️ {pair} blocked")
            continue
        action,conf,rsi,dist,reason,levels,tl_info,_ = analyze_pair(pair)
        LAST_STATUS[pair]=f"{action} {conf}%"
        SIGNAL_HISTORY.append({"time":datetime.now().strftime("%H:%M"),"pair":pair,"action":action,"conf":conf,"reason":reason})
        price=h1_c[-1]
        sl=price*0.993 if action=="BUY" else price*1.007
        tp=price*1.018 if action=="BUY" else price*0.982
        if action=="SKIP":
            txt=f"⏳ {pair} V4.8 TL {reason}\nPrice {price:,.2f} RSI {rsi:.0f} Dist {dist:.2f}%\nNo TL/BOS break yet - watching"
        else:
            txt=(f"🤖 {pair} V4.8 TL {action} {conf}% 🔥\n{reason}\n\nEntry {price:,.2f}\nSL {sl:,.2f}\nTP {tp:,.2f}\nRSI {rsi:.0f} Dist {dist:.2f}%\nTrendline confirmed on H1")
        chart=make_chart(pair,h1_c,h1_h,h1_l,action,price,levels,tl_info,rsi,dist,conf,reason) if CHART else None
        if chart:
            await context.bot.send_photo(chat_id=update.effective_chat.id, photo=chart, caption=txt)
        else:
            await update.message.reply_text(txt)

telegram_app=None
async def auto_loop():
    while True:
        await asyncio.sleep(900)
        if not USERS or not telegram_app: continue
        for pair in ["BTC","GOLD"]:
            try:
                h1_c,h1_h,h1_l,h4_c,d1_c,symbol,real = get_data(pair)
                if not real: continue
                action,conf,rsi,dist,reason,levels,tl_info,_ = analyze_pair(pair)
                prev=LAST_STATUS.get(pair,"WAIT")
                LAST_STATUS[pair]=f"{action} {conf}%"
                if action!="SKIP" and conf>=80 and ("WAIT" in prev or "SKIP" in prev):
                    price=h1_c[-1]; sl=price*0.993 if action=="BUY" else price*1.007; tp=price*1.018 if action=="BUY" else price*0.982
                    chart=make_chart(pair,h1_c,h1_h,h1_l,action,price,levels,tl_info,rsi,dist,conf,reason) if CHART else None
                    for uid in list(USERS):
                        try:
                            txt=f"🚨 AUTO {pair} {action} {conf}% TL BREAK!\nEntry {price:.2f} SL {sl:.2f} TP {tp:.2f}\n{reason}"
                            if chart:
                                await telegram_app.bot.send_photo(chat_id=uid, photo=chart, caption=txt)
                            else:
                                await telegram_app.bot.send_message(chat_id=uid, text=txt)
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
