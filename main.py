def get_klines_real(sym, interval, limit=100):
    coin = "BTC" if "BTC" in sym else "XAU" if "GOLD" in sym else "BTC"
    # CryptoCompare - works from Render SA!
    try:
        cc_interval = "histohour" if interval in ["1h","4h"] else "histoday"
        agg = 1 if interval=="1h" else 4 if interval=="4h" else 1
        url = f"https://min-api.cryptocompare.com/data/v2/{cc_interval}?fsym={coin}&tsym=USD&limit={limit}&aggregate={agg}"
        r = requests.get(url, timeout=8).json()
        data = r["Data"]["Data"]
        closes = [float(x["close"]) for x in data if x["close"]>0]
        if len(closes)>50:
            return closes, True
    except: pass
    # Coinbase - also works
    try:
        gran = 3600 if interval=="1h" else 14400 if interval=="4h" else 86400
        url = f"https://api.exchange.coinbase.com/products/{coin}-USD/candles?granularity={gran}"
        r = requests.get(url, timeout=8, headers={"User-Agent":"Mozilla/5.0"}).json()
        closes = [float(x[4]) for x in reversed(r)] # x[4]=close
        if len(closes)>50:
            return closes, True
    except: pass
    return [84000+i*12 for i in range(limit)], False
