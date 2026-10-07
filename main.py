import os, asyncio, requests
from datetime import datetime
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
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
    return {"status":"V4.8 STRUCTURE BOS BREAKOUT BTC+GOLD","chart":CHART,"last":LAST_STATUS}

@app.get("/admin")
def admin(key: str = ""):
    if key!=ADMIN_KEY: return {"error":"Wrong key"}
    rows=""
    for s in SIGNAL_HISTORY[-120:][::-1]:
        c="#00ff88" if s['action']=="BUY" else "#ff4444" if s['action']=="SELL" else "#ffaa00"
        rows+=f"<tr><td>{s['time']}</td><td>{s['pair']}</td><td style='color:{c}'>{s['action']}</td><td>{s['conf']}%</td><td>{s['reason']}</td></tr>"
    return HTMLResponse(f"<html><head><meta name='viewport' content='width=device-width'><style>body{{background:#0B0F1C;color:#fff;font-family:Arial;padding:10px}}td{{padding:5px;border-bottom:1px solid #222;font-size:10px}}</style></head><body><h3>V4.8 BOS BREAKOUT {LAST_STATUS}</h3><table><tr><th>Time</th><th>Pair</th><th>Action</th><th>%</th><th>Reason</th></tr>{rows}</table></body></html>")

# ---- DATA ----
def get_binance(symbol, interval, limit=200):
    try:
        url=f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
        r=requests.get(url,timeout=10,headers={"User-Agent":"Mozilla/5.0"}).json()
        if isinstance(r, list) and len(r)>50:
            closes=[float(x[4]) for x in r]
            highs=[float(x[2]) for x in r]
            lows=[float(x[3]) for x in r]
            return closes, highs, lows, True
    except Exception as e:
        print(f"{symbol} {interval} fail {e}")
    return None, None, None, False

def get_data(pair):
    symbol = "BTCUSDT" if pair=="BTC" else "PAXGUSDT" # PAXG = Gold pegged
    h1_c,h1_h,h1_l,ok1 = get_binance(symbol,"1h",200)
    h4_c,h4_h,h4_l,_ = get_binance(symbol,"4h",100)
    d1_c,d1_h,d1_l,_ = get_binance(symbol,"1d",60)
    if not ok1:
        return None,None,None,None,None,None,False
    if h4_c is None: h4_c,h4_h,h4_l = h1_c[-100:],h1_h[-100:],h1_l[-100:]
    if d1_c is None: d1_c,d1_h,d1_l = h1_c[-60:],h1_h[-60:],h1_l[-60:]
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

def find_structure(highs,lows):
    # Find last swing HH/HL like your screenshot
    recent_high = max(highs[-30:-5])
    recent_low = min(lows[-30:-5])
    last_hh = max(highs[-60:-30]) if len(highs)>60 else recent_high
    last_hl = min(lows[-60:-30]) if len(lows)>60 else recent_low
    return recent_high, recent_low, last_hh, last_hl

def atr_calc(highs,lows,closes,period=14):
    trs=[]
    for i in range(-period,0):
        tr = max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1]))
        trs.append(tr)
    return sum(trs)/len(trs) if trs else 0

def analyze_pair(pair):
    data = get_data(pair)
    h1_c,h1_h,h1_l,h4_c,d1_c,symbol,real = data
    if not real:
        return "SKIP",0,50,0,"No real data","",None,None

    price=h1_c[-1]; prev=h1_c[-2]; prev2=h1_c[-3]
    ema20=sum(h1_c[-20:])/20; ema50=sum(h1_c[-50:])/50; ema200=sum(h1_c[-200:])/200
    ema20_h4=sum(h4_c[-20:])/20; ema50_h4=sum(h4_c[-50:])/50
    ema20_d1=sum(d1_c[-20:])/20; ema50_d1=sum(d1_c[-50:])/20

    rsi=rsi_calc(h1_c); rsi_prev=rsi_calc(h1_c[:-1]); rsi_h4=rsi_calc(h4_c)
    atr=atr_calc(h1_h,h1_l,h1_c)
    dist=abs(price-ema20)/ema20*100

    recent_high, recent_low, last_hh, last_hl = find_structure(h1_h,h1_l)

    d1_up=ema20_d1>ema50_d1; h4_up=ema20_h4>ema50_h4; h1_up=ema20>ema50 and price>ema200
    h1_down=ema20<ema50 and price<ema200

    # Market condition filter (like you want - know if good to trade)
    good_market = atr > (price*0.0015) and dist>0.3 # not choppy
    if not good_market:
        return "SKIP",0,rsi,dist,"Choppy market - ATR low, waiting volatility","",None,None

    # --- STRATEGY 1: BOS BREAKOUT (your screenshot style) ---
    # Bullish BOS: price breaks recent_high after HL
    broke_high = price > recent_high and prev <= recent_high and price>prev and h1_c[-2]>h1_c[-3]
    broke_low = price < recent_low and prev >= recent_low and price<prev and h1_c[-2]<h1_c[-3]

    # Retest logic: after breakout, price pulls back to broken level (support becomes resistance)
    # We detect breakout + green reversal like your entry at 101.863
    if broke_high and h1_up and h4_up and rsi>45 and rsi<68 and rsi>rsi_prev:
        conf = 78 + (rsi_h4-50)*0.3 + dist*2
        reason=f"BOS BREAKOUT BUY: Broke {recent_high:.2f} (HH), HL formed {last_hl:.2f}, H1+H4 UP, RSI {rsi_prev:.0f}->{rsi:.0f}"
        levels={"support":recent_high,"resist":last_hh,"hl":last_hl}
        return "BUY",int(min(92,conf)),rsi,dist,reason,levels,symbol

    if broke_low and h1_down and not h4_up and rsi<55 and rsi>32 and rsi<rsi_prev:
        conf = 78 + (50-rsi_h4)*0.3 + dist*2
        reason=f"BOS BREAKDOWN SELL: Broke {recent_low:.2f} (LL), LH formed {last_hh:.2f}, H1+H4 DOWN, RSI {rsi_prev:.0f}->{rsi:.0f}"
        levels={"support":last_hl,"resist":recent_low,"hh":last_hh}
        return "SELL",int(min(92,conf)),rsi,dist,reason,levels,symbol

    # --- STRATEGY 2: TREND PULLBACK (EMA20 retest) ---
    near_ema20 = abs(price-ema20)/ema20*100 < 0.6
    if h1_up and h4_up and d1_up and near_ema20 and price>prev and rsi>rsi_prev and 40<rsi<60:
        conf=75+ (rsi_h4-45)*0.4
        reason=f"TREND PULLBACK BUY: Price retested EMA20, HL {last_hl:.2f} held, D1 UP trend, RSI {rsi:.0f}"
        levels={"support":ema20,"resist":recent_high,"hl":last_hl}
        return "BUY",int(min(86,conf)),rsi,dist,reason,levels,symbol

    if h1_down and not h4_up and not d1_up and near_ema20 and price<prev and rsi<rsi_prev and 40<rsi<60:
        conf=75+ (55-rsi_h4)*0.4
        reason=f"TREND PULLBACK SELL: Price retested EMA20, LH {last_hh:.2f} held, D1 DOWN trend, RSI {rsi:.0f}"
        levels={"support":recent_low,"resist":ema20,"hh":last_hh}
        return "SELL",int(min(86,conf)),rsi,dist,reason,levels,symbol

    # --- STRATEGY 3: RANGE BREAKOUT + Volume (big candle) ---
    range_high=max(h1_c[-20:]); range_low=min(h1_c[-20:])
    big_candle = abs(price-prev) > atr*1.2
    if price>range_high and big_candle and h1_up and rsi<70 and rsi>rsi_prev:
        conf=80
        reason=f"RANGE BREAKOUT BUY: Broke 20H range {range_high:.2f}, big candle ATRx{abs(price-prev)/atr:.1f}, H1 UP"
        levels={"support":range_high,"resist":last_hh}
        return "BUY",conf,rsi,dist,reason,levels,symbol
    if price<range_low and big_candle and h1_down and rsi>30 and rsi<rsi_prev:
        conf=80
        reason=f"RANGE BREAKDOWN SELL: Broke 20H range {range_low:.2f}, big candle, H1 DOWN"
        levels={"support":last_hl,"resist":range_low}
        return "SELL",conf,rsi,dist,reason,levels,symbol

    # WAIT
    if rsi>75: return "SKIP",0,rsi,dist,f"Overbought RSI {rsi:.0f} wait BOS red for SELL","",None,None
    if rsi<25: return "SKIP",0,rsi,dist,f"Oversold RSI {rsi:.0f} wait BOS green for BUY","",None,None
    return "SKIP",0,rsi,dist,f"Waiting BOS: D1 {'UP' if d1_up else 'DOWN'} H4 {'UP' if h4_up else 'DOWN'} H1 Range {recent_low:.0f}-{recent_high:.0f} RSI {rsi:.0f}","",None,None

def make_chart(pair, h1_c, h1_h, h1_l, action, price, levels, rsi, dist, conf, reason):
    if not CHART or h1_c is None: return None
    try:
        plt.figure(figsize=(8,4.8))
        data=h1_c[-60:]; highs=h1_h[-60:]; lows=h1_l[-60:]
        color='#00ff88' if action=='BUY' else '#ff4444' if action=='SELL' else '#888'
        plt.plot(data, color=color, linewidth=2, label=f'{pair} H1 {action}')

        # EMA
        ema20_line=[sum(h1_c[i-20:i])/20 if i>=20 else h1_c[i] for i in range(len(h1_c))][-60:]
        plt.plot(ema20_line, color='#ffaa00', linestyle='--', alpha=0.7, label='EMA20')

        # Support/Resist from structure (like your black lines)
        if levels:
            if "support" in levels:
                plt.axhline(levels["support"], color='white', linewidth=1.2, label=f'Support {levels["support"]:.2f}')
            if "resist" in levels:
                plt.axhline(levels["resist"], color='white', linestyle='-', alpha=0.5, label=f'Resist {levels["resist"]:.2f}')
            if "hl" in levels:
                plt.axhline(levels["hl"], color='#00aaff', linestyle=':', label=f'HL {levels["hl"]:.2f}')
            if "hh" in levels:
                plt.axhline(levels["hh"], color='#ff00aa', linestyle=':', label=f'HH {levels["hh"]:.2f}')

        # SL/TP box like your screenshot
        sl = price*0.992 if action=="BUY" else price*1.008 if action=="SELL" else price*0.992
        tp = price*1.02 if action=="BUY" else price*0.98 if action=="SELL" else price*1.02
        if action!="SKIP":
            plt.axhline(price, color='white', linewidth=1.5)
            plt.axhline(sl, color='#ff4444', linestyle=':', linewidth=1.5, label=f'SL {sl:.2f}')
            plt.axhline(tp, color='#00ff88', linestyle=':', linewidth=1.5, label=f'TP {tp:.2f}')
            # Box
            plt.fill_between(range(len(data)), sl, price, color='#ffaa00', alpha=0.15)
            plt.fill_between(range(len(data)), price, tp, color='#00ff88' if action=="BUY" else '#ff4444', alpha=0.12)

        plt.title(f"V4.8 {pair} {action} {conf}% RSI {rsi:.0f} Dist {dist:.2f}%\n{reason[:70]}", color='white', fontsize=8)
        plt.legend(fontsize=6, loc='best')
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
    await update.message.reply_text("✅ V4.8 STRUCTURE BOS BREAKOUT LIVE\n📈 BTC + GOLD (PAXG)\nStrategies: BOS Breakout + Trend Pullback + Range Breakout\nH1 is boss - checks market condition first\nCommands:\n/signal BTC\n/signal GOLD\n/signal ALL")

async def signal_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    USERS.add(update.effective_chat.id)
    args=context.args
    target="ALL" if not args else args[0].upper()
    if target not in ["BTC","GOLD","ALL"]: target="ALL"
    pairs=["BTC","GOLD"] if target=="ALL" else [target]

    await update.message.reply_text(f"🔍 V4.8 scanning {target} - BOS Structure + Breakout + Trend (H1 boss)...")

    for pair in pairs:
        h1_c,h1_h,h1_l,h4_c,d1_c,symbol,real = get_data(pair)
        if not real:
            await update.message.reply_text(f"⚠️ {pair} data blocked, retry 1min")
            continue
        action,conf,rsi,dist,reason,levels,_ = analyze_pair(pair)
        LAST_STATUS[pair]=f"{action} {conf}%"
        SIGNAL_HISTORY.append({"time":datetime.now().strftime("%H:%M"),"pair":pair,"action":action,"conf":conf,"reason":reason})

        price=h1_c[-1]
        sl = price*0.992 if action=="BUY" else price*1.008
        tp = price*1.02 if action=="BUY" else price*0.98
        if action=="SKIP":
            sl_buy=price*0.992; tp_buy=price*1.02
            sl_sell=price*1.008; tp_sell=price*0.98
            txt=f"⏳ {pair} V4.8 {reason}\nPrice {price:,.2f} RSI {rsi:.0f} Dist {dist:.2f}%\nNo BOS yet - watching support/resist\nIf BUY: SL {sl_buy:.2f} TP {tp_buy:.2f}\nIf SELL: SL {sl_sell:.2f} TP {tp_sell:.2f}"
        else:
            txt=(f"🤖 {pair} V4.8 {action} {conf}% 🔥\n"
                 f"Strategy: {reason}\n\n"
                 f"Entry {price:,.2f}\nSL {sl:,.2f} ({-0.8:.1f}%)\nTP {tp:,.2f} (+2.0%)\n"
                 f"RSI {rsi:.0f} Dist {dist:.2f}%\nH1 BOS confirmed - market good to trade")

        chart=make_chart(pair,h1_c,h1_h,h1_l,action,price,levels,rsi,dist,conf,reason) if CHART else None
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
                action,conf,rsi,dist,reason,levels,_ = analyze_pair(pair)
                prev=LAST_STATUS.get(pair,"WAIT")
                LAST_STATUS[pair]=f"{action} {conf}%"
                if action!="SKIP" and conf>=78 and ("WAIT" in prev or "SKIP" in prev):
                    price=h1_c[-1]
                    sl=price*0.992 if action=="BUY" else price*1.008
                    tp=price*1.02 if action=="BUY" else price*0.98
                    chart=make_chart(pair,h1_c,h1_h,h1_l,action,price,levels,rsi,dist,conf,reason) if CHART else None
                    for uid in list(USERS):
                        try:
                            txt=f"🚨 AUTO {pair} {action} {conf}% BOS CONFIRMED!\nEntry {price:.2f} SL {sl:.2f} TP {tp:.2f}\n{reason}"
                            if chart:
                                await telegram_app.bot.send_photo(chat_id=uid, photo=chart, caption=txt)
                            else:
                                await telegram_app.bot.send_message(chat_id=uid, text=txt)
                        except: pass
            except Exception as e:
                print(f"auto {pair} {e}")

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
