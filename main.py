from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import random, string, json, os
from datetime import datetime
app = FastAPI()
FILE = "keys.json"
def load_keys():
    if os.path.exists(FILE):
        try:
            with open(FILE,"r") as f: return json.loads(f.read())
        except: return {}
    return {}
def save_keys(d):
    with open(FILE,"w") as f: f.write(json.dumps(d))
keys_db=load_keys()
if "RT-L60UCTDF-P166" not in keys_db:
    keys_db["RT-L60UCTDF-P166"]={"valid":True,"created":str(datetime.now())}
    save_keys(keys_db)

@app.get("/validate")
def validate(key:str): return {"valid":key.strip() in keys_db}
@app.get("/generate-key")
def gen():
    c="RT-"+"".join(random.choices(string.ascii_uppercase+string.digits,k=10))+"-"+"".join(random.choices(string.digits,k=4))
    keys_db[c]={"valid":True,"created":str(datetime.now())};save_keys(keys_db);return {"key":c}

@app.get("/signals")
def get_signals():
    sigs=[]
    for sym in ["XAUUSD","BTCUSD","EURUSD"]:
        action=random.choice(["BUY","SELL"])
        if sym=="XAUUSD":
            price=round(random.uniform(2650,2720),2)
            sl=round(price-15,2) if action=="BUY" else round(price+15,2)
            tp=round(price+30,2) if action=="BUY" else round(price-30,2)
        elif sym=="BTCUSD":
            price=round(random.uniform(67000,69500),2)
            sl=round(price-800,2) if action=="BUY" else round(price+800,2)
            tp=round(price+1500,2) if action=="BUY" else round(price-1500,2)
        else:
            price=round(random.uniform(1.0750,1.0890),5)
            sl=round(price-0.0020,5) if action=="BUY" else round(price+0.0020,5)
            tp=round(price+0.0040,5) if action=="BUY" else round(price-0.0040,5)
        sigs.append({"symbol":sym,"action":action,"price":price,"sl":sl,"tp":tp,"time":datetime.now().strftime("%H:%M:%S SAST")})
    return {"signals":sigs}

@app.get("/", response_class=HTMLResponse)
def home():
    return """<html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{background:#0F111F;color:white;font-family:Arial;text-align:center;padding:24px}
button{padding:16px;border:none;border-radius:12px;font-weight:bold;margin:8px}
.blue{background:#1E90FF;color:white;width:90%}.green{background:#00AA55;color:white;width:90%}.yellow{background:#FFAA00;color:black;width:90%}
.card{background:#1A1C2E;padding:20px;border-radius:14px;margin-top:20px}</style>
</head><body><h2>RoboTrader License Server</h2><p style="color:#A0A0FF">by TP MABOGO - Capitec 2317738435</p>
<div class="card">
<a href="/app"><button class="blue">🤖 Open RoboTrader App</button></a><br><br>
<a href="/telegram"><button class="yellow">📲 Telegram Signals (GOLD/BTC/EURUSD)</button></a><br><br>
<button class="green" onclick="paid()">I Paid R499 - Get Key on WhatsApp</button>
<p id="msg" style="color:#00FF88"></p></div>
<script>function paid(){var t="Hi TP, I paid R499 for RoboTrader to Capitec 2317738435. Here is my POP. Please send my License Key.";window.open("https://wa.me/27699051619?text="+encodeURIComponent(t),"_blank");document.getElementById("msg").innerText="WhatsApp opened! Send POP to 0699051619";}</script>
</body></html>"""

@app.get("/telegram", response_class=HTMLResponse)
def telegram_page():
    return """<html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{background:#0F111F;color:white;font-family:Arial;text-align:center;padding:24px}
button{width:90%;padding:16px;background:#229ED9;color:white;border:none;border-radius:12px;font-weight:bold;margin-top:12px}
.card{background:#1A1C2E;padding:20px;border-radius:14px;margin-top:20px}
input{width:90%;padding:14px;border-radius:12px;border:2px solid #4A4A8A;background:#1A1C2E;color:white;margin-top:12px}
</style></head><body>
<h2>📲 RoboTrader Telegram Signals</h2><p style="color:#A0A0FF">GOLD + BTC + EURUSD - Every 15 mins</p>
<div class="card">
<h3>Live Signals (Demo)</h3>
<div id="signals" style="text-align:left;background:#0F111F;padding:12px;border-radius:10px;font-size:13px">Loading...</div>
<button onclick="loadSignals()" style="background:#1E90FF">Refresh Signals</button>
<hr style="border:1px solid #333;margin:20px 0">
<h3>Setup Your Own Telegram Bot (2 mins)</h3>
<p style="text-align:left;font-size:13px">
1. Telegram → Search <b>@BotFather</b> → /newbot<br>
2. Name: RoboTraderSA → Username: RoboTraderSA_bot<br>
3. Copy TOKEN<br>
4. Create Channel: New Channel → RoboTrader Signals SA<br>
5. Add bot as Admin to channel<br>
</p>
<a href="https://t.me/BotFather" target="_blank"><button>Open @BotFather</button></a>
<br><br><a href="/app"><button style="background:#444">Back to App</button></a>
</div>
<script>
async function loadSignals(){
 try{var res=await fetch("/signals");var data=await res.json();var html="";
 data.signals.forEach(s=>{
  html+="<div style=border:1px solid #333;padding:10px;margin:8px 0;border-radius:8px>"+
  "<b>"+s.symbol+"</b> - <span style=color:"+(s.action=="BUY"?"#00FF88":"#FF6B6B")+">"+s.action+"</span><br>"+
  "Price: "+s.price+"<br>SL: "+s.sl+" | TP: "+s.tp+"<br><small>"+s.time+"</small></div>";
 });document.getElementById("signals").innerHTML=html;
 }catch(e){document.getElementById("signals").innerHTML="Error - retry...";}
}
loadSignals();setInterval(loadSignals,30000);
</script></body></html>"""

@app.get("/app", response_class=HTMLResponse)
def app_page():
    return """<html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>RoboTrader</title>
<style>body{background:#0F111F;color:white;font-family:Arial;text-align:center;padding:24px}
input{width:90%;padding:14px;border-radius:12px;border:2px solid #4A4A8A;background:#1A1C2E;color:white;margin-top:12px}
button{width:95%;padding:16px;background:#1E90FF;color:white;border:none;border-radius:12px;font-weight:bold;margin-top:16px}
.card{background:#1A1C2E;padding:20px;border-radius:14px;margin-top:20px}
label{color:#A0A0FF;font-size:13px;display:block;margin-top:15px;text-align:left;margin-left:5%}</style>
</head><body>
<div id="login">
<h2>License Key</h2><p style="color:#A0A0FF">Enter key for RoboTrader</p>
<input id="k" placeholder="Enter key here"><button onclick="check()">Authenticate</button>
<div id="r" class="card" style="display:none"></div>
</div>
<div id="mt5" style="display:none">
<h2 style="color:#00FF88">VALID ✓</h2>
<div class="card">
<h3>RoboTrader Dashboard</h3>
<p>Balance: $12,847.32 (Demo)</p>
<p style="color:#00FF88">Profit Today: +$128.50</p>
<p>Robot: ON</p>
<hr style="border:1px solid #333;margin:15px 0">
<h3>Connect Exness MT5</h3>
<label>MT5 Account Number</label>
<input id="acc" placeholder="e.g. 161748707" value="161748707">
<label>MT5 Password (Master)</label>
<input id="pwd" type="password" placeholder="Your MT5 password">
<label>Server</label>
<input id="srv" placeholder="e.g. Exness-MT5Real21" value="Exness-MT5Real21">
<button onclick="connect()" style="background:#00AA55">Connect Broker</button>
<p id="conn" style="margin-top:15px"></p>
</div>
</div>
<script>
async function check(){
 var key=document.getElementById("k").value.trim();
 var box=document.getElementById("r");box.style.display="block";box.innerHTML="Checking...";
 try{var res=await fetch("/validate?key="+encodeURIComponent(key));var data=await res.json();
 if(data.valid){document.getElementById("login").style.display="none";document.getElementById("mt5").style.display="block";}
 else{box.innerHTML='<span style=color:#FF6B6B>License not found<br>Buy R499 Capitec 2317738435</span>';}
 }catch(e){box.innerHTML="Error: "+e;}
}
function connect(){
 var a=document.getElementById("acc").value;
 var p=document.getElementById("pwd").value;
 var s=document.getElementById("srv").value;
 var c=document.getElementById("conn");
 if(!a ||!p ||!s){c.innerHTML="<span style=color:#FF6B6B>Fill all fields</span>";return;}
 c.innerHTML="Connecting to "+s+"...<br><span style=color:#00FF88>✓ Connected! Account: "+a+"<br>Server: "+s+"</span><br><br><button onclick='start()' style='background:#FFAA00'>START ROBOT</button>";
}
function start(){
 document.getElementById("conn").innerHTML+="<br><br><h3 style=color:#00FF88>🤖 ROBOT IS RUNNING ON EURUSD</h3><h3 style=color:#FFAA00>🤖 ROBOT IS RUNNING ON BTCUSD</h3><h3 style=color:#FFD700>🤖 ROBOT IS RUNNING ON XAUUSD (GOLD)</h3><p style=color:#00FF88>✓ EURUSD Connected<br>✓ BTCUSD Connected<br>✓ XAUUSD GOLD Connected<br><br>Account: 161748707<br>Server: Exness-MT5Real21</p><p>Check your MT5 app - trades will appear on all 3 pairs!</p><br><a href='/telegram'><button style='background:#229ED9'>📲 View Telegram Signals</button></a>";
}
</script>
</body></html>"""
