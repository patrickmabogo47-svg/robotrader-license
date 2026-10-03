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
<html><head><meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="background:#0a0a0a;color:white;text-align:center;padding:25px;font-family:Arial;max-width:400px;margin:auto">
<h1>🤖 ROBOTRADER</h1>
<h2 style="color:#00ff88">R499 Lifetime</h2>
<p style="color:#aaa">Premium MT5 Robot - License Protected</p>

<div style="background:#1a1a1a;padding:20px;border-radius:15px;margin:20px 0;text-align:left;border:1px solid #333">
<h3 style="color:#00ff88;margin-top:0">💳 Pay via Capitec</h3>
<p><b>Bank:</b> Capitec Bank<br>
<b>Acc Holder:</b> TP MABOGO<br>
<b>Acc Number:</b> 2317738435<br>
<b>Branch:</b> 470010<br>
<b>Amount:</b> <b style="color:#00ff88">R499</b><br>
<b>Reference:</b> Your Name</p>
</div>

<p style="font-size:14px;color:#888">1. Pay R499 via Capitec App<br>2. Click below & send POP on WhatsApp<br>3. Get your License Key in 5 mins!</p>

<button onclick="paid()" style="background:#25D366;padding:18px 30px;border:none;border-radius:15px;font-size:18px;font-weight:bold;width:100%;cursor:pointer;color:black">✅ I HAVE PAID - SEND POP ON WHATSAPP</button>

<div id="k" style="margin-top:20px"></div>

<script>
function paid(){
 let msg = "Hi TP, I paid R499 for RoboTrader to Capitec 2317738435. Here is my POP. Please send my License Key.";
 window.open("https://wa.me/27699051619?text=" + encodeURIComponent(msg), "_blank");
 document.getElementById('k').innerHTML='<p style="color:#00ff88">✅ WhatsApp opened! Send your POP to 0699051619 to get key.</p>';
}
</script>

<p style="margin-top:30px;color:#555;font-size:12px">Secure license server • Instant delivery after payment</p>
</body></html>
    """
