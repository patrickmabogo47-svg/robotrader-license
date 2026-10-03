from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import random, string, json, os
app = FastAPI()

FILE = "keys.json"

def load_keys():
    if os.path.exists(FILE):
        with open(FILE, "r") as f:
            return json.load(f)
    return {}

def save_keys(keys):
    with open(FILE, "w") as f:
        json.dump(keys, f)

@app.get("/")
def home():
    return {"status": "Robotrader License Server LIVE"}

@app.get("/generate-key")
def generate_key():
    key = "RT-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8)) + "-" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    keys = load_keys()
    keys[key] = True
    save_keys(keys)
    return {"key": key}

@app.get("/verify/{license_key}")
def verify(license_key: str):
    keys = load_keys()
    valid = license_key in keys and keys[license_key] == True
    return {"valid": valid, "key": license_key}

@app.get("/revoke/{license_key}")
def revoke(license_key: str):
    keys = load_keys()
    if license_key in keys:
        del keys[license_key]
        save_keys(keys)
        return {"revoked": True}
    return {"revoked": False}

@app.get("/store", response_class=HTMLResponse)
def store():
    return """
<html>
<head><meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="background:#0a0a0a;color:white;text-align:center;padding:30px;font-family:Arial">
<h1>🤖 ROBOTRADER</h1>
<h2 style="color:#00ff88">R499 Lifetime</h2>
<p>Premium MT5 Trading Robot<br>License Protected & Secure</p>
<button onclick="buy()" style="background:#00ff88;padding:15px 30px;border:none;border-radius:15px;font-size:18px;font-weight:bold;cursor:pointer">BUY NOW & GET KEY</button>
<div id="k" style="margin-top:20px;font-size:20px;color:#00ff88;word-break:break-all"></div>
<p style="margin-top:30px;color:#888">After payment, WhatsApp seller to activate</p>
<script>
async function buy(){
 document.getElementById('k').innerText='Generating your key...';
 let r=await fetch('/generate-key');
 let d=await r.json();
 document.getElementById('k').innerHTML='🎉 YOUR KEY:<br><b style="font-size:22px">'+d.key+'</b><br><br>Copy this into your EA!';
}
</script>
</body>
</html>
    """
