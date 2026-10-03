from fastapi import FastAPI
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
