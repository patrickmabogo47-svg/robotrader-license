from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import random, string, json, os
from datetime import datetime

app = FastAPI()
FILE = "keys.json"
def load_keys():
    if os.path.exists(FILE):
        try:
            with open(FILE, "r") as f:
                return json.loads(f.read())
        except:
            return {}
    return {}
def save_keys(d):
    with open(FILE, "w") as f:
        f.write(json.dumps(d))
keys_db = load_keys()
if "RT-L60UCTDF-P166" not in keys_db:
    keys_db["RT-L60UCTDF-P166"] = {"valid": True, "created": str(datetime.now())}
    save_keys(keys_db)

@app.get("/validate")
def validate(key: str):
    k = key.strip()
    return {"valid": k in keys_db}

@app.get("/generate-key")
def gen():
    c = "RT-" + "".join(random.choices(string.ascii_uppercase+string.digits, k=10)) + "-" + "".join(random.choices(string.digits, k=4))
    keys_db[c] = {"valid": True, "created": str(datetime.now())}
    save_keys(keys_db)
    return {"key": c}

@app.get("/", response_class=HTMLResponse)
def home():
    return """
<html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{background:#0F111F;color:white;font-family:Arial;text-align:center;padding:24px}
button{padding:16px;border:none;border-radius:12px;font-weight:bold;margin:8px}
.blue{background:#1E90FF;color:white;width:90%}.green{background:#00AA55;color:white;width:90%}
.card{background:#1A1C2E;padding:20px;border-radius:14px;margin-top:20px}</style>
</head><body><h2>RoboTrader License Server</h2>
<p style="color:#A0A0FF">by TP MABOGO - Capitec 2317738435</p>
<div class="card">
<a href="/app"><button class="blue">Open RoboTrader App</button></a><br><br>
<button class="green" onclick="paid()">I Paid R499 - Get Key on WhatsApp</button>
<p id="msg" style="color:#00FF88"></p></div>
<script>function paid(){var t="Hi TP, I paid R499 for RoboTrader to Capitec 2317738435. Here is my POP. Please send my License Key.";window.open("https://wa.me/27699051619?text="+encodeURIComponent(t),"_blank");document.getElementById("msg").innerText="WhatsApp opened! Send POP to 0699051619";}</script>
</body></html>"""

@app.get("/app", response_class=HTMLResponse)
def app_page():
    return """
<html><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>RoboTrader</title>
<style>body{background:#0F111F;color:white;font-family:Arial;text-align:center;padding:24px}
input{width:90%;padding:16px;border-radius:12px;border:2px solid #4A4A8A;background:#1A1C2E;color:white;margin-top:20px}
button{width:95%;padding:18px;background:#1E90FF;color:white;border:none;border-radius:12px;font-weight:bold;margin-top:20px}
.card{background:#1A1C2E;padding:20px;border-radius:14px;margin-top:20px}</style>
</head><body><h2>License Key</h2><p style="color:#A0A0FF">Enter key for RoboTrader</p>
<input id="k" placeholder="Enter key here"><button onclick="check()">Authenticate</button>
<div id="r" class="card" style="display:none"></div>
<script>async function check(){var key=document.getElementById("k").value.trim();var box=document.getElementById("r");box.style.display="block";box.innerHTML="Checking...";try{var res=await fetch("/validate?key="+encodeURIComponent(key));var data=await res.json();if(data.valid){document.body.innerHTML='<h1 style=color:#00FF88>VALID</h1><div class=card><h3>RoboTrader Dashboard</h3><p>Balance: $12,847.32</p><p style=color:#00FF88>Profit Today: +$128.50</p><p>Robot: ON - EURUSD</p></div>';}else{box.innerHTML='<span style=color:#FF6B6B>The License key is not found<br>Buy R499 Capitec 2317738435</span>';}}catch(e){box.innerHTML="Error: "+e;}}</script>
</body></html>"""
